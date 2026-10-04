"""
Tool‑calling agent — LangChain agent wired to the receptionist tools.

Uses ``create_tool_calling_agent`` + ``AgentExecutor`` which natively
supports OpenAI‑style function‑calling (Gemini, Groq and OpenAI all
provide it through their OpenAI‑compatible APIs).  The agent is lazily built on first
request and cached, just like the old plain‑chat chain.
"""

from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Dict, Any, Optional

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.outputs import LLMResult

from app.core.settings import settings
from app.core.business_profile import get_business_profile
from app.agent.tools import AGENT_TOOLS, faq_lookup
from app.llm.providers import get_fallback_llm, get_local_llm, get_primary_llm, primary_model_name
from app.schemas.chat import TokenUsage

logger = logging.getLogger(__name__)

# ── System prompt ──────────────────────────────────────────────────────────
# Kept short on purpose: the whole prompt is resent on every LLM call, and on
# Groq's free tier the per-minute token limit is what caps chat volume.
AGENT_SYSTEM_PROMPT = """\
You are the receptionist for {name} ({industry}).
Facts:
{facts}
Rules:
- Reply in the customer's language ({languages}, or a mix). Max 3 warm sentences. Prices in {currency}.
- Answer from Facts, matching loosely (\"consultation\" means a listed consultation). Never invent prices, times or medical/legal advice.
- Booking: need service, date, time, name and phone. Call calendar_list_slots, then calendar_create_event once they confirm a listed slot. If send_reminder is true, say we will remind them.
- Wants a person, complains, or Facts lack the answer: call handoff_to_human and share the link (or our phone if there is no link).
"""

# A FAQ longer than this goes behind faq_lookup instead of into the prompt.
MAX_INLINE_FACTS_CHARS = 2000


def _facts(p) -> str:
    kb = p.knowledge_base()
    # The knowledge base stores some answers under several keys; list each once.
    seen: set[str] = set()
    lines = []
    for key, answer in kb.items():
        if answer not in seen:
            seen.add(answer)
            label = "services and prices" if key == "services" else key
            lines.append(f"- {label}: {answer}")
    return "\n".join(lines)


def _inline_faq() -> bool:
    return len(_facts(get_business_profile())) <= MAX_INLINE_FACTS_CHARS


def build_system_prompt() -> str:
    """Fill the system prompt with the configured business profile."""
    p = get_business_profile()
    facts = _facts(p) if _inline_faq() else (
        f"- hours: {p.hours}\n- address: {p.address}\n- anything else: call faq_lookup"
    )
    text = AGENT_SYSTEM_PROMPT.format(
        name=p.name,
        industry=p.industry,
        facts=facts,
        languages=", ".join(p.languages),
        currency=p.currency,
    )
    # Escape braces so ChatPromptTemplate doesn't treat them as variables.
    text = text.replace("{", "{{").replace("}", "}}")
    return text + "Today: {today}\n"


def agent_tools() -> list:
    return AGENT_TOOLS if _inline_faq() else [*AGENT_TOOLS, faq_lookup]

# ── Lazy singleton agent ──────────────────────────────────────────────────
_agent_executor: Optional[AgentExecutor] = None


def _build_agent() -> AgentExecutor:
    """Build the tool‑calling agent (called once, then cached)."""
    global _agent_executor  # noqa: PLW0603
    if _agent_executor is not None:
        return _agent_executor

    backups = [m for m in (get_fallback_llm(), get_local_llm()) if m is not None]
    llm = get_primary_llm(has_fallback=bool(backups))

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", build_system_prompt()),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )

    tools = agent_tools()
    agent = create_tool_calling_agent(llm, tools, prompt)
    if backups:
        # If the primary provider errors or is rate-limited, the same step is
        # retried on each backup in turn so customers still get a reply.
        agent = agent.with_fallbacks(
            [create_tool_calling_agent(m, tools, prompt) for m in backups]
        )

    _agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=settings.LOG_LEVEL == "DEBUG",
        max_iterations=10,
        handle_parsing_errors=True,
        return_intermediate_steps=True,
        # Replies are returned whole, so streaming buys nothing; invoking the
        # agent instead lets the backup provider take over on any error.
        stream_runnable=False,
    )

    logger.info(
        "Agent initialised  model=%s  backups=%s  tools=%s",
        primary_model_name(),
        [m.model_name for m in backups],
        [t.name for t in tools],
    )
    return _agent_executor


def _today() -> str:
    now = datetime.now(ZoneInfo(settings.BUSINESS_TIMEZONE))
    return now.strftime("%A %Y-%m-%d %H:%M")


class _UsageCounter(BaseCallbackHandler):
    """Adds up the token usage of every LLM call made during one turn."""

    def __init__(self) -> None:
        self.usage = TokenUsage()
        self.calls = 0

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        self.calls += 1
        counts = (response.llm_output or {}).get("token_usage") or {}
        if not counts:
            for gens in response.generations:
                for gen in gens:
                    meta = getattr(getattr(gen, "message", None), "usage_metadata", None) or {}
                    counts = {
                        "prompt_tokens": meta.get("input_tokens", 0),
                        "completion_tokens": meta.get("output_tokens", 0),
                        "total_tokens": meta.get("total_tokens", 0),
                    }
        self.usage.prompt_tokens += counts.get("prompt_tokens", 0) or 0
        self.usage.completion_tokens += counts.get("completion_tokens", 0) or 0
        self.usage.total_tokens += counts.get("total_tokens", 0) or 0


# In-memory session history store
_session_history: dict[str, list[BaseMessage]] = {}

# ── Public API ─────────────────────────────────────────────────────────────
async def run_agent(user_message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Invoke the tool‑calling agent with *user_message* and optional *session_id*.

    Returns a dict with:
      - ``reply``  : str — the agent's final answer
      - ``tools_called`` : list[str] — names of tools invoked
      - ``usage``  : TokenUsage | None — best‑effort token stats
    """
    executor = _build_agent()

    # Retrieve memory if session_id is provided
    chat_history = []
    if session_id:
        chat_history = _session_history.setdefault(session_id, [])

    # Feed recent history only: every past message is resent on every LLM call.
    counter = _UsageCounter()
    result = await executor.ainvoke(
        {"input": user_message, "chat_history": chat_history[-6:], "today": _today()},
        config={"callbacks": [counter]},
    )

    reply: str = result.get("output", "")

    # Save turn to history if session_id is provided
    if session_id:
        _session_history[session_id].append(HumanMessage(content=user_message))
        _session_history[session_id].append(AIMessage(content=reply))
        # Prevent memory leak by keeping last 30 messages
        _session_history[session_id] = _session_history[session_id][-30:]

    # Collect which tools were called
    tools_called: list[str] = []
    for step in result.get("intermediate_steps", []):
        action = step[0]
        tools_called.append(action.tool)

    usage: Optional[TokenUsage] = counter.usage if counter.calls else None
    if usage:
        logger.info(
            "Turn usage  llm_calls=%d  prompt=%d  completion=%d  total=%d",
            counter.calls, usage.prompt_tokens, usage.completion_tokens, usage.total_tokens,
        )

    return {
        "reply": reply,
        "tools_called": tools_called,
        "usage": usage,
    }
