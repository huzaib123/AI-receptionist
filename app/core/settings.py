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
    LLM_MODEL_NAME: str = os.getenv("LLM_MODEL_NAME") or "llama-3.3-70b-versatile"
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.3"))
    LLM_TIMEOUT_SECONDS: float = float(os.getenv("LLM_TIMEOUT_SECONDS", "30"))

    # Leave the key empty to reuse LLM_API_KEY when the backup is on the same
    # provider. Set LLM_FALLBACK_MODEL_NAME=none to turn the backup off.
    LLM_FALLBACK_API_KEY: str = os.getenv("LLM_FALLBACK_API_KEY", "")
    LLM_FALLBACK_BASE_URL: str = os.getenv("LLM_FALLBACK_BASE_URL") or "https://api.groq.com/openai/v1"
    LLM_FALLBACK_MODEL_NAME: str = os.getenv("LLM_FALLBACK_MODEL_NAME") or "llama-3.1-8b-instant"

    # Legacy: deployments configured only with OPENAI_API_KEY keep using OpenAI.
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    # ── App ────────────────────────────────────────────────
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

    # ── Security ───────────────────────────────────────────
    ADMIN_API_KEY: str = os.getenv("ADMIN_API_KEY", "dev_secret_key_123")
    CHAT_RATE_LIMIT_PER_MINUTE: int = int(os.getenv("CHAT_RATE_LIMIT_PER_MINUTE", "60"))

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

