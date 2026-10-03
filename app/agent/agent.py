"""
Tool‑calling agent — LangChain agent wired to the receptionist tools.

Uses ``create_tool_calling_agent`` + ``AgentExecutor`` which natively
supports OpenAI‑style function‑calling (Gemini, Groq and OpenAI all
provide it through their OpenAI‑compatible APIs).  The agent is lazily built on first
request and cached, just like the old plain‑chat chain.
"""

from __future__ import annotations

import logging
from typing import Dict, Any, Optional

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

from app.core.settings import settings
from app.core.business_profile import get_business_profile
from app.agent.tools import ALL_TOOLS
from app.llm.providers import get_fallback_llm, get_primary_llm, primary_model_name
from app.schemas.chat import TokenUsage

logger = logging.getLogger(__name__)

# ── System prompt ──────────────────────────────────────────────────────────
AGENT_SYSTEM_PROMPT = """\
You are the AI receptionist for {name}, a {industry}.
{tagline}

## Business facts
- Address: {address}
- Opening hours: {hours}
- Services and prices: {services}

## Your responsibilities
1. **Classify the customer's intent**: FAQ question, new booking, \
   rescheduling, cancellation, or general chat.
2. **Use the right tools**:
   • For general questions (hours, prices, location, parking, payment, etc.) \
     → call `faq_lookup`.
   • For booking requests → first call `calendar_list_slots` to show \
     availability, then `calendar_create_event` once the customer confirms.
   • After creating a booking → call `db_log_booking` to keep a record. \
     Also call `predict_no_show` (never share the raw probability value \
     with the customer). If the predicted risk level is 'high', politely \
     inform the customer that they will receive a reminder closer to \
     their appointment and ask them to confirm if anything changes.
   • For new customers → call `db_create_customer` to register them \
     (ask for name and phone number).
   • If the customer wants a human, has a complaint, or asks something you \
     cannot answer → call `handoff_to_human` and share the WhatsApp link.
3. **Reply in the customer's language.** Customers may write in {languages} \
   or mix them (e.g. Manglish); answer naturally in the same language.
4. **Be concise and warm** — keep replies under 3 sentences when possible. \
   Quote prices in {currency}.
5. **Ask clarifying questions** if a booking request is missing the \
   service, date, or time.
6. **Never fabricate** availability, prices or medical/legal advice.
7. You may call **multiple tools** in a single step when appropriate.
"""


def build_system_prompt() -> str:
    """Fill the system prompt with the configured business profile."""
    p = get_business_profile()
    services = "; ".join(
        f"{s.name} ({s.price})" if s.price else s.name for s in p.services
    ) or "see faq_lookup"
    text = AGENT_SYSTEM_PROMPT.format(
        name=p.name,
        industry=p.industry,
        tagline=p.tagline,
        address=p.address or "see faq_lookup",
        hours=p.hours or "see faq_lookup",
        services=services,
        languages=", ".join(p.languages),
        currency=p.currency,
    )
    # Escape braces so ChatPromptTemplate doesn't treat them as variables.
    return text.replace("{", "{{").replace("}", "}}")

# ── Lazy singleton agent ──────────────────────────────────────────────────
_agent_executor: Optional[AgentExecutor] = None


def _build_agent() -> AgentExecutor:
    """Build the tool‑calling agent (called once, then cached)."""
    global _agent_executor  # noqa: PLW0603
    if _agent_executor is not None:
        return _agent_executor

    fallback_llm = get_fallback_llm()
    llm = get_primary_llm(has_fallback=fallback_llm is not None)

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", build_system_prompt()),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )

    agent = create_tool_calling_agent(llm, ALL_TOOLS, prompt)
    if fallback_llm is not None:
        # If the primary provider errors or is rate-limited, the same step
        # is retried on the backup provider so customers still get a reply.
        agent = agent.with_fallbacks(
            [create_tool_calling_agent(fallback_llm, ALL_TOOLS, prompt)]
        )

    _agent_executor = AgentExecutor(
        agent=agent,
        tools=ALL_TOOLS,
        verbose=settings.LOG_LEVEL == "DEBUG",
        max_iterations=10,
        handle_parsing_errors=True,
        return_intermediate_steps=True,
        # Replies are returned whole, so streaming buys nothing; invoking the
        # agent instead lets the backup provider take over on any error.
        stream_runnable=False,
    )

    logger.info(
        "Agent initialised  model=%s  fallback=%s  tools=%s",
        primary_model_name(),
        settings.LLM_FALLBACK_MODEL_NAME if fallback_llm is not None else None,
        [t.name for t in ALL_TOOLS],
    )
    return _agent_executor


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

    # Feed history to the agent (limited to last 12 messages for efficiency)
    result = await executor.ainvoke({
        "input": user_message,
        "chat_history": chat_history[-12:]
    })

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

    # Token usage — AgentExecutor doesn't surface this directly, so we
    # return None for now.  (Will be wired via callbacks in a later step.)
    usage: Optional[TokenUsage] = None

    return {
        "reply": reply,
        "tools_called": tools_called,
        "usage": usage,
    }
