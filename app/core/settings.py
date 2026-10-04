"""
Centralised configuration loaded from environment variables / .env file.

Reads the .env file once at import time and exposes a singleton `settings`
object used throughout the application.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the project root (two levels up from this file)
_env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(_env_path)


def _parse_int_list(raw: str) -> list[int]:
    """Parse a comma-separated string of ints (e.g. '0,1,2,3,4,5')."""
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


class Settings:
    """Application‑wide settings sourced from environment variables."""

    # ── LLM ────────────────────────────────────────────────
    # Any OpenAI-compatible endpoint works. The default is Groq's free tier
    # (no card needed). A backup model takes over when the primary errors or
    # hits its rate limit; by default it is a smaller Groq model on the same
    # key, which has its own separate free quota.
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL") or "https://api.groq.com/openai/v1"
    LLM_MODEL_NAME: str = os.getenv("LLM_MODEL_NAME") or "openai/gpt-oss-120b"
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.3"))
    LLM_TIMEOUT_SECONDS: float = float(os.getenv("LLM_TIMEOUT_SECONDS", "30"))

    # Leave the key empty to reuse LLM_API_KEY when the backup is on the same
    # provider. Set LLM_FALLBACK_MODEL_NAME=none to turn the backup off.
    LLM_FALLBACK_API_KEY: str = os.getenv("LLM_FALLBACK_API_KEY", "")
    LLM_FALLBACK_BASE_URL: str = os.getenv("LLM_FALLBACK_BASE_URL") or "https://api.groq.com/openai/v1"
    LLM_FALLBACK_MODEL_NAME: str = os.getenv("LLM_FALLBACK_MODEL_NAME") or "openai/gpt-oss-20b"

    # How hard reasoning models think before answering (low/medium/high).
    # Empty means "low" for gpt-oss models, which keeps replies fast and cheap
    # on tokens, and is not sent at all to other models.
    LLM_REASONING_EFFORT: str = os.getenv("LLM_REASONING_EFFORT", "")

    # Last-resort backup on your own machine, e.g. Ollama on a Mac:
    #   LLM_LOCAL_BASE_URL=http://localhost:11434/v1  LLM_LOCAL_MODEL_NAME=qwen3:8b
    # Used only after the main and backup models have both failed. Empty = off.
    LLM_LOCAL_BASE_URL: str = os.getenv("LLM_LOCAL_BASE_URL", "")
    LLM_LOCAL_MODEL_NAME: str = os.getenv("LLM_LOCAL_MODEL_NAME") or "qwen3:8b"
    LLM_LOCAL_API_KEY: str = os.getenv("LLM_LOCAL_API_KEY") or "ollama"
    LLM_LOCAL_TIMEOUT_SECONDS: float = float(os.getenv("LLM_LOCAL_TIMEOUT_SECONDS", "90"))
    # Appended to the local model's system prompt. "/no_think" stops Qwen3
    # from reasoning before every reply; set it empty for other local models.
    LLM_LOCAL_SYSTEM_SUFFIX: str = os.getenv("LLM_LOCAL_SYSTEM_SUFFIX", "/no_think\n")

    # Legacy: deployments configured only with OPENAI_API_KEY keep using OpenAI.
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    # ── App ────────────────────────────────────────────────
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

    # ── Security ───────────────────────────────────────────
    # Admin endpoints stay locked (503) until this is set to 24+ random
    # characters, e.g. the output of: python3 -c "import secrets;print(secrets.token_urlsafe(32))"
    ADMIN_API_KEY: str = os.getenv("ADMIN_API_KEY", "")
    ADMIN_FAILED_ATTEMPTS_PER_HOUR: int = int(os.getenv("ADMIN_FAILED_ATTEMPTS_PER_HOUR", "10"))

    # Chat limits. Per visitor IP per minute and per day, plus one shared cap
    # across all visitors so a flood can't use up the LLM provider's quota.
    CHAT_RATE_LIMIT_PER_MINUTE: int = int(os.getenv("CHAT_RATE_LIMIT_PER_MINUTE", "15"))
    CHAT_DAILY_LIMIT_PER_IP: int = int(os.getenv("CHAT_DAILY_LIMIT_PER_IP", "200"))
    CHAT_GLOBAL_LIMIT_PER_MINUTE: int = int(os.getenv("CHAT_GLOBAL_LIMIT_PER_MINUTE", "40"))

    # Proxies whose CF-Connecting-IP / X-Forwarded-For header is trusted for
    # the visitor's real IP. cloudflared on the same machine connects from
    # localhost, so that is the default.
    TRUSTED_PROXY_IPS: list[str] = [
        ip.strip() for ip in os.getenv("TRUSTED_PROXY_IPS", "127.0.0.1,::1").split(",") if ip.strip()
    ]

    # Browser origins allowed to call the API. "*" lets the widget run on any
    # client website; it is safe because no cookies or credentials are used.
    CORS_ALLOW_ORIGINS: list[str] = [
        o.strip() for o in os.getenv("CORS_ALLOW_ORIGINS", "*").split(",") if o.strip()
    ]

    # Interactive API docs (/docs, /redoc). Off by default so the public
    # server doesn't advertise every endpoint; set true while testing.
    ENABLE_API_DOCS: bool = os.getenv("ENABLE_API_DOCS", "false").lower() in ("1", "true", "yes")

    # Chat sessions kept in memory; the oldest are dropped beyond this.
    MAX_CHAT_SESSIONS: int = int(os.getenv("MAX_CHAT_SESSIONS", "2000"))

    # ── Database ───────────────────────────────────────────
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./receptionist.db")

    # ── Google Calendar ────────────────────────────────────
    GOOGLE_SERVICE_ACCOUNT_FILE: str = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "")
    GOOGLE_CALENDAR_ID: str = os.getenv("GOOGLE_CALENDAR_ID", "primary")

    # ── Business Profile ───────────────────────────────────
    # JSON file with name, services, prices, hours, FAQ, WhatsApp, etc.
    BUSINESS_PROFILE_FILE: str = os.getenv("BUSINESS_PROFILE_FILE", "config/business_profile.json")

    # ── Business Rules ─────────────────────────────────────
    BUSINESS_TIMEZONE: str = os.getenv("BUSINESS_TIMEZONE", "Asia/Kuala_Lumpur")
    BUSINESS_HOURS_START: int = int(os.getenv("BUSINESS_HOURS_START", "9"))
    BUSINESS_HOURS_END: int = int(os.getenv("BUSINESS_HOURS_END", "19"))
    BUSINESS_DAYS: list[int] = _parse_int_list(
        os.getenv("BUSINESS_DAYS", "0,1,2,3,4,5")  # Mon–Sat
    )
    BOOKING_BUFFER_MINUTES: int = int(os.getenv("BOOKING_BUFFER_MINUTES", "15"))
    DEFAULT_SLOT_WINDOW_DAYS: int = int(os.getenv("DEFAULT_SLOT_WINDOW_DAYS", "14"))


settings = Settings()

