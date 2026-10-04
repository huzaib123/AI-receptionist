"""
Tests for the public-facing protections: admin key rules, rate limits,
real-IP detection behind a proxy, input limits and leak-free errors.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import main
from app.core import security
from app.core.settings import settings

client = TestClient(main.app)
STRONG_KEY = "test-admin-key-0123456789abcdef"


@pytest.fixture
def fake_agent(monkeypatch):
    async def run_agent(message, session_id=None):
        return {"reply": "ok", "tools_called": [], "usage": None}
    monkeypatch.setattr(main, "run_agent", run_agent)


@pytest.mark.parametrize("key", ["", "dev_secret_key_123", "short-key"])
def test_admin_is_disabled_without_a_strong_key(monkeypatch, key):
    monkeypatch.setattr(settings, "ADMIN_API_KEY", key)
    r = client.get("/admin/stats", headers={"X-Admin-API-Key": key or "x"})
    assert r.status_code == 503


def test_admin_locks_out_after_repeated_wrong_keys(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_API_KEY", STRONG_KEY)
    monkeypatch.setattr(settings, "ADMIN_FAILED_ATTEMPTS_PER_HOUR", 3)
    for _ in range(3):
        assert client.get("/admin/stats", headers={"X-Admin-API-Key": "wrong"}).status_code == 403
    # Even the right key is refused until the lockout passes.
    assert client.get("/admin/stats", headers={"X-Admin-API-Key": STRONG_KEY}).status_code == 429


def test_chat_is_rate_limited_per_visitor(monkeypatch, fake_agent):
    monkeypatch.setattr(settings, "CHAT_RATE_LIMIT_PER_MINUTE", 2)
    body = {"message": "hi", "session_id": "s1"}
    assert client.post("/chat", json=body).status_code == 200
    assert client.post("/chat", json=body).status_code == 200
    r = client.post("/chat", json=body)
    assert r.status_code == 429 and "Retry-After" in r.headers


def test_global_cap_protects_the_llm_quota(monkeypatch, fake_agent):
    monkeypatch.setattr(settings, "CHAT_GLOBAL_LIMIT_PER_MINUTE", 2)
    monkeypatch.setattr(settings, "TRUSTED_PROXY_IPS", ["testclient"])
    for ip in ("1.1.1.1", "2.2.2.2"):
        assert client.post("/chat", json={"message": "hi"}, headers={"CF-Connecting-IP": ip}).status_code == 200
    r = client.post("/chat", json={"message": "hi"}, headers={"CF-Connecting-IP": "3.3.3.3"})
    assert r.status_code == 429


def test_real_ip_is_read_only_from_a_trusted_proxy(monkeypatch, fake_agent):
    monkeypatch.setattr(settings, "CHAT_RATE_LIMIT_PER_MINUTE", 1)
    # Behind the trusted proxy, two visitors get separate limits.
    monkeypatch.setattr(settings, "TRUSTED_PROXY_IPS", ["testclient"])
    assert client.post("/chat", json={"message": "a"}, headers={"CF-Connecting-IP": "1.1.1.1"}).status_code == 200
    assert client.post("/chat", json={"message": "b"}, headers={"CF-Connecting-IP": "2.2.2.2"}).status_code == 200
    # From an untrusted peer the header is ignored, so faking it doesn't help.
    security.reset_rate_limits()
    monkeypatch.setattr(settings, "TRUSTED_PROXY_IPS", [])
    assert client.post("/chat", json={"message": "a"}, headers={"CF-Connecting-IP": "1.1.1.1"}).status_code == 200
    assert client.post("/chat", json={"message": "b"}, headers={"CF-Connecting-IP": "9.9.9.9"}).status_code == 429


def test_oversized_and_malformed_input_is_refused(fake_agent):
    assert client.post("/chat", content=b"x" * 20000, headers={"Content-Type": "application/json"}).status_code == 413
    assert client.post("/chat", json={"message": "x" * 1001}).status_code == 422
    assert client.post("/chat", json={"message": "hi", "session_id": "../../etc"}).status_code == 422


def test_agent_errors_are_not_leaked(monkeypatch):
    async def boom(message, session_id=None):
        raise RuntimeError("Error code: 401 - invalid key gsk_secret_value")
    monkeypatch.setattr(main, "run_agent", boom)
    r = client.post("/chat", json={"message": "hi"})
    assert r.status_code == 502
    assert "gsk_" not in r.text and "401" not in r.text


def test_api_docs_are_off_by_default():
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_security_headers_are_set():
    r = client.get("/health")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert "default-src 'none'" in r.headers["Content-Security-Policy"]
    assert r.headers.get("access-control-allow-credentials") != "true"
