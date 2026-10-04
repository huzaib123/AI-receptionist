"""
Security utilities: admin authentication, client IP detection and rate limits.

The chat endpoint is public, so the limits here are what stop one visitor (or
a bot) from flooding the server or burning through the LLM provider's free
quota for every client.
"""

from __future__ import annotations

import hmac
import logging
import threading
import time
from collections import defaultdict, deque

from fastapi import Depends, HTTPException, Request
from fastapi.security import APIKeyHeader

from app.core.settings import settings

logger = logging.getLogger(__name__)

# Keys that must never unlock the admin API: the old shipped default and
# anything too short to resist guessing.
_KNOWN_WEAK_KEYS = {"dev_secret_key_123", "changeme", "admin", "password"}
MIN_ADMIN_KEY_LENGTH = 24

# ── Admin API key ──────────────────────────────────────────────────────────
api_key_header = APIKeyHeader(name="X-Admin-API-Key", auto_error=True)


def admin_key_is_strong(key: str) -> bool:
    return len(key) >= MIN_ADMIN_KEY_LENGTH and key not in _KNOWN_WEAK_KEYS


def verify_admin_key(request: Request, api_key: str = Depends(api_key_header)) -> str:
    """Check the X-Admin-API-Key header. Admin stays locked until a strong key is set."""
    if not admin_key_is_strong(settings.ADMIN_API_KEY):
        raise HTTPException(
            status_code=503,
            detail="Admin API is disabled until a strong ADMIN_API_KEY is set.",
        )
    _enforce(_admin_failures, client_ip(request), settings.ADMIN_FAILED_ATTEMPTS_PER_HOUR, 3600,
             "Too many failed admin attempts. Try again later.", record=False)
    # Constant-time comparison so the key can't be guessed byte by byte.
    if not hmac.compare_digest(api_key.encode(), settings.ADMIN_API_KEY.encode()):
        _record(_admin_failures, client_ip(request))
        logger.warning("Unauthorized admin access attempt from %s", client_ip(request))
        raise HTTPException(status_code=403, detail="Forbidden: Invalid Admin API Key")
    return api_key


# ── Client IP ──────────────────────────────────────────────────────────────
def client_ip(request: Request) -> str:
    """The visitor's IP address.

    Behind Cloudflare Tunnel or another reverse proxy every request reaches
    the app from the proxy's own address, so the real IP is read from the
    proxy's header, but only when the request came from a trusted proxy;
    otherwise anyone could fake the header to dodge the limits.
    """
    peer = request.client.host if request.client else "unknown"
    if peer in settings.TRUSTED_PROXY_IPS:
        forwarded = request.headers.get("cf-connecting-ip") or request.headers.get("x-forwarded-for", "")
        real = forwarded.split(",")[0].strip()
        if real:
            return real[:64]
    return peer


# ── Sliding-window limiter ─────────────────────────────────────────────────
_lock = threading.Lock()
_per_minute: dict[str, deque] = defaultdict(deque)
_per_day: dict[str, deque] = defaultdict(deque)
_global_minute: dict[str, deque] = defaultdict(deque)
_admin_failures: dict[str, deque] = defaultdict(deque)
_last_sweep = 0.0


def _prune(q: deque, now: float, window: float) -> None:
    while q and now - q[0] >= window:
        q.popleft()


def _sweep(now: float) -> None:
    """Forget idle IPs so the tables can't grow without bound."""
    global _last_sweep  # noqa: PLW0603
    if now - _last_sweep < 300:
        return
    _last_sweep = now
    for table, window in ((_per_minute, 60), (_per_day, 86400), (_admin_failures, 3600)):
        for key in list(table):
            _prune(table[key], now, window)
            if not table[key]:
                del table[key]


def _record(table: dict[str, deque], key: str) -> None:
    with _lock:
        table[key].append(time.time())


def _enforce(table: dict[str, deque], key: str, limit: int, window: float, message: str,
             record: bool = True) -> None:
    if limit <= 0:
        return
    now = time.time()
    with _lock:
        _sweep(now)
        q = table[key]
        _prune(q, now, window)
        if len(q) >= limit:
            logger.warning("Rate limit hit  key=%s  limit=%d/%ds", key, limit, int(window))
            raise HTTPException(status_code=429, detail=message, headers={"Retry-After": str(int(window - (now - q[0])) + 1)})
        if record:
            q.append(now)


def check_rate_limit(request: Request) -> None:
    """Limits for the public chat endpoint: per visitor and across all visitors."""
    ip = client_ip(request)
    _enforce(_per_minute, ip, settings.CHAT_RATE_LIMIT_PER_MINUTE, 60,
             "Too many messages. Please wait a minute and try again.")
    _enforce(_per_day, ip, settings.CHAT_DAILY_LIMIT_PER_IP, 86400,
             "Daily message limit reached. Please contact us on WhatsApp instead.")
    # Shared cap across every visitor protects the LLM provider's quota.
    _enforce(_global_minute, "all", settings.CHAT_GLOBAL_LIMIT_PER_MINUTE, 60,
             "We're very busy right now. Please try again in a minute.")


def reset_rate_limits() -> None:
    """Clear all counters (used by tests)."""
    with _lock:
        for table in (_per_minute, _per_day, _global_minute, _admin_failures):
            table.clear()
