"""
Security utilities including admin authentication and in-memory rate limiting.
"""

from __future__ import annotations

import time
import logging
from collections import defaultdict
from fastapi import HTTPException, Request, Depends
from fastapi.security import APIKeyHeader
from app.core.settings import settings

logger = logging.getLogger(__name__)

# Admin API Key Authentication
api_key_header = APIKeyHeader(name="X-Admin-API-Key", auto_error=True)

def verify_admin_key(api_key: str = Depends(api_key_header)) -> str:
    """
    Dependency to verify the incoming X-Admin-API-Key header against the settings.
    """
    if api_key != settings.ADMIN_API_KEY:
        logger.warning("Unauthorized admin access attempt with invalid API key.")
        raise HTTPException(
            status_code=403,
            detail="Forbidden: Invalid Admin API Key",
        )
    return api_key


# In-memory IP rate limiter: client_ip -> list of request timestamps
_rate_limit_history: dict[str, list[float]] = defaultdict(list)

def check_rate_limit(request: Request) -> None:
    """
    Dependency to enforce rate limits on incoming requests based on the client IP.
    """
    # Fallback to 'unknown' if host is not available
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    
    # Filter out timestamps older than 60 seconds
    timestamps = [t for t in _rate_limit_history[client_ip] if now - t < 60]
    
    if len(timestamps) >= settings.CHAT_RATE_LIMIT_PER_MINUTE:
        logger.warning(
            "Rate limit exceeded for IP %s: %d requests in last 60s (limit is %d)",
            client_ip,
            len(timestamps),
            settings.CHAT_RATE_LIMIT_PER_MINUTE,
        )
        raise HTTPException(
            status_code=429,
            detail="Too Many Requests: Chat rate limit exceeded. Please wait a minute before trying again.",
        )
        
    # Record current request timestamp
    timestamps.append(now)
    _rate_limit_history[client_ip] = timestamps
