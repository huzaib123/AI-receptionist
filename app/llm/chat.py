"""
LangChain chat pipeline — single‑turn for now.

Uses lazy initialisation: the ChatOpenAI client and Runnable chain are built
on the **first** call to ``get_chat_reply()`` and cached for all subsequent
requests.  This avoids a hard crash at import time when the API key is not
yet configured (e.g. during tests or CI).
"""

from __future__ import annotations

import logging
from typing import Tuple, Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from langchain_openai import ChatOpenAI

from app.core.settings import settings
from app.schemas.chat import TokenUsage

logger = logging.getLogger(__name__)

# ── System prompt ──────────────────────────────────────────────────────────
SYSTEM_PROMPT = """\
You are an AI receptionist prototype for service businesses such as clinics, \
salons, and co‑working spaces.

Guidelines:
• Be concise and professional — keep replies under 3 sentences when possible.
• If a booking request is ambiguous (missing date, time, or service), ask a \
  clarification question instead of guessing.
• Never fabricate availability — say you'll check and confirm.
• Greet warmly on first contact.
"""

# ── Lazy singleton chain ──────────────────────────────────────────────────
_chain: Optional[Runnable] = None


def _build_chain() -> Runnable:
    """Construct the prompt → LLM chain (called once, then cached)."""
    global _chain  # noqa: PLW0603
    if _chain is not None:
        return _chain

    llm = ChatOpenAI(
        model=settings.LLM_MODEL_NAME,
        temperature=settings.LLM_TEMPERATURE,
        api_key=settings.OPENAI_API_KEY,  # type: ignore[arg-type]
    )

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT),
            ("human", "{user_message}"),
        ]
    )

    _chain = prompt | llm
    logger.info(
        "LangChain chain initialised  model=%s  temp=%s",
        settings.LLM_MODEL_NAME,
        settings.LLM_TEMPERATURE,
    )
    return _chain


# ── Public API ─────────────────────────────────────────────────────────────
async def get_chat_reply(user_message: str) -> Tuple[str, Optional[TokenUsage]]:
    """
    Send *user_message* through the LangChain chain and return
    ``(reply_text, token_usage | None)``.
    """
    chain = _build_chain()
    result = await chain.ainvoke({"user_message": user_message})

    reply_text: str = result.content  # type: ignore[union-attr]

    # Best‑effort token usage — depends on the provider's response metadata
    usage: Optional[TokenUsage] = None
    raw_usage = getattr(result, "usage_metadata", None)
    if raw_usage and isinstance(raw_usage, dict):
        usage = TokenUsage(
            prompt_tokens=raw_usage.get("input_tokens", 0),
            completion_tokens=raw_usage.get("output_tokens", 0),
            total_tokens=raw_usage.get("total_tokens", 0),
        )

    return reply_text, usage
