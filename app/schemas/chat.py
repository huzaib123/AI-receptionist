"""
Pydantic models for the /chat endpoint.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Incoming chat payload."""

    message: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="The user's message to the AI receptionist.",
        examples=["I'd like to book a haircut for tomorrow at 3 PM."],
    )
    session_id: Optional[str] = Field(
        default=None,
        max_length=64,
        pattern=r"^[A-Za-z0-9_-]+$",
        description="The session identifier to track chat history context.",
    )


class TokenUsage(BaseModel):
    """Token‑usage counters returned by the LLM (best‑effort)."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatResponse(BaseModel):
    """Structured reply from the AI receptionist."""

    reply: str = Field(..., description="The assistant's response text.")
    tools_called: List[str] = Field(
        default_factory=list,
        description="Names of tools the agent invoked during this turn.",
    )
    usage: Optional[TokenUsage] = Field(
        default=None,
        description="Token usage statistics (null when unavailable).",
    )

