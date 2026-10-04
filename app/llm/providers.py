"""
Chat model factory for the configured LLM providers.

Every provider is reached through its OpenAI-compatible API, so switching
between Gemini, Groq, OpenAI or any other compatible host is a matter of
environment variables, not code.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from langchain_openai import ChatOpenAI

from app.core.settings import settings

logger = logging.getLogger(__name__)


def _reasoning_effort(model: str) -> Optional[str]:
    if settings.LLM_REASONING_EFFORT:
        return settings.LLM_REASONING_EFFORT
    return "low" if "gpt-oss" in model else None


def _chat_model(
    api_key: str,
    base_url: Optional[str],
    model: str,
    retries: int,
    timeout: Optional[float] = None,
) -> ChatOpenAI:
    extra = {}
    effort = _reasoning_effort(model)
    if effort:
        extra["reasoning_effort"] = effort
    return ChatOpenAI(
        model=model,
        temperature=settings.LLM_TEMPERATURE,
        api_key=api_key,  # type: ignore[arg-type]
        base_url=base_url or None,
        timeout=timeout or settings.LLM_TIMEOUT_SECONDS,
        max_retries=retries,
        **extra,
    )


def _legacy_openai() -> bool:
    """True for older deployments configured only with OPENAI_API_KEY."""
    return not settings.LLM_API_KEY and bool(settings.OPENAI_API_KEY)


def primary_model_name() -> str:
    if _legacy_openai():
        # Keep the old OpenAI default unless a model was set explicitly.
        return os.getenv("LLM_MODEL_NAME") or "gpt-4o-mini"
    return settings.LLM_MODEL_NAME


def get_primary_llm(has_fallback: bool = False) -> ChatOpenAI:
    """The main chat model. Fails fast to the backup when one is configured."""
    retries = 1 if has_fallback else 2
    if _legacy_openai():
        return _chat_model(settings.OPENAI_API_KEY, None, primary_model_name(), retries)
    return _chat_model(settings.LLM_API_KEY, settings.LLM_BASE_URL, settings.LLM_MODEL_NAME, retries)


def get_fallback_llm() -> Optional[ChatOpenAI]:
    """The backup chat model, or None when no backup is configured."""
    if settings.LLM_FALLBACK_MODEL_NAME.lower() == "none":
        return None
    api_key = settings.LLM_FALLBACK_API_KEY
    if not api_key and settings.LLM_API_KEY and (
        settings.LLM_FALLBACK_BASE_URL.rstrip("/") == settings.LLM_BASE_URL.rstrip("/")
    ):
        api_key = settings.LLM_API_KEY  # same provider: reuse the primary key
    if not api_key:
        return None
    return _chat_model(
        api_key,
        settings.LLM_FALLBACK_BASE_URL,
        settings.LLM_FALLBACK_MODEL_NAME,
        # Fail over quickly when the local model is there to catch it.
        retries=1 if settings.LLM_LOCAL_BASE_URL else 2,
    )


def get_local_llm() -> Optional[ChatOpenAI]:
    """The last-resort model on your own machine (e.g. Ollama), or None."""
    if not settings.LLM_LOCAL_BASE_URL:
        return None
    return _chat_model(
        settings.LLM_LOCAL_API_KEY,
        settings.LLM_LOCAL_BASE_URL,
        settings.LLM_LOCAL_MODEL_NAME,
        retries=0,
        timeout=settings.LLM_LOCAL_TIMEOUT_SECONDS,
    )
