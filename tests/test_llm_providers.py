"""
Tests for app/llm/providers.py and the agent's backup-provider fallback.

Two tiny local servers stand in for OpenAI-compatible providers: one always
answers 429 (rate limited), the other returns a normal chat completion.
"""

from __future__ import annotations

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from app.agent import agent as agent_module
from app.core.settings import settings
from app.llm import providers


def _serve(status: int, reply: str = ""):
    hits: list[dict] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            hits.append(body)
            if status != 200:
                payload = {"error": {"message": "rate limited", "type": "rate_limit"}}
            else:
                payload = {
                    "id": "c1", "object": "chat.completion", "created": 0,
                    "model": body["model"],
                    "choices": [{"index": 0, "finish_reason": "stop",
                                 "message": {"role": "assistant", "content": reply}}],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                }
            data = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_port}/v1", hits


GROQ = "https://api.groq.com/openai/v1"


@pytest.fixture
def llm_env(monkeypatch):
    monkeypatch.setattr(agent_module, "_agent_executor", None)
    for name, value in {
        "LLM_API_KEY": "", "OPENAI_API_KEY": "", "LLM_FALLBACK_API_KEY": "",
        "LLM_BASE_URL": GROQ, "LLM_MODEL_NAME": "openai/gpt-oss-120b",
        "LLM_FALLBACK_BASE_URL": GROQ, "LLM_FALLBACK_MODEL_NAME": "openai/gpt-oss-20b",
    }.items():
        monkeypatch.setattr(settings, name, value)
    monkeypatch.delenv("LLM_MODEL_NAME", raising=False)
    yield monkeypatch
    agent_module._agent_executor = None


def test_default_is_groq_with_same_key_backup(llm_env):
    llm_env.setattr(settings, "LLM_API_KEY", "gsk-key")
    llm = providers.get_primary_llm()
    assert llm.model_name == "openai/gpt-oss-120b"
    assert "api.groq.com" in str(llm.openai_api_base)
    fb = providers.get_fallback_llm()
    assert fb is not None
    assert fb.model_name == "openai/gpt-oss-20b"
    assert fb.openai_api_key.get_secret_value() == "gsk-key"


def test_backup_can_be_turned_off(llm_env):
    llm_env.setattr(settings, "LLM_API_KEY", "gsk-key")
    llm_env.setattr(settings, "LLM_FALLBACK_MODEL_NAME", "none")
    assert providers.get_fallback_llm() is None


def test_backup_on_other_provider_needs_its_own_key(llm_env):
    llm_env.setattr(settings, "LLM_API_KEY", "gsk-key")
    llm_env.setattr(settings, "LLM_FALLBACK_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
    assert providers.get_fallback_llm() is None
    llm_env.setattr(settings, "LLM_FALLBACK_API_KEY", "gemini-key")
    assert providers.get_fallback_llm() is not None


def test_legacy_openai_key_keeps_openai(llm_env):
    llm_env.setattr(settings, "OPENAI_API_KEY", "sk-old")
    llm = providers.get_primary_llm()
    assert llm.model_name == "gpt-4o-mini"
    assert not llm.openai_api_base
    assert providers.get_fallback_llm() is None


def test_agent_switches_to_backup_when_primary_is_rate_limited(llm_env):
    primary, primary_url, primary_hits = _serve(429)
    backup, backup_url, backup_hits = _serve(200, "Hi! How can I help?")
    try:
        llm_env.setattr(settings, "LLM_API_KEY", "k1")
        llm_env.setattr(settings, "LLM_BASE_URL", primary_url)
        llm_env.setattr(settings, "LLM_FALLBACK_API_KEY", "k2")
        llm_env.setattr(settings, "LLM_FALLBACK_BASE_URL", backup_url)

        result = asyncio.run(agent_module.run_agent("hello"))

        assert result["reply"] == "Hi! How can I help?"
        assert primary_hits, "primary provider should be tried first"
        assert backup_hits[0]["model"] == "openai/gpt-oss-20b"
        assert backup_hits[0]["tools"], "backup must receive the receptionist tools"
    finally:
        primary.shutdown()
        backup.shutdown()


def test_mac_backup_answers_when_both_groq_models_fail(llm_env):
    primary, primary_url, primary_hits = _serve(429)
    backup, backup_url, backup_hits = _serve(429)
    local, local_url, local_hits = _serve(200, "Hello from the Mac!")
    try:
        llm_env.setattr(settings, "LLM_API_KEY", "k1")
        llm_env.setattr(settings, "LLM_BASE_URL", primary_url)
        llm_env.setattr(settings, "LLM_FALLBACK_API_KEY", "k2")
        llm_env.setattr(settings, "LLM_FALLBACK_BASE_URL", backup_url)
        llm_env.setattr(settings, "LLM_LOCAL_BASE_URL", local_url)

        result = asyncio.run(agent_module.run_agent("hello"))

        assert result["reply"] == "Hello from the Mac!"
        assert primary_hits and backup_hits
        assert local_hits[0]["model"] == "qwen3:8b"
        assert "reasoning_effort" not in local_hits[0]
        assert result["usage"].total_tokens == 2
    finally:
        primary.shutdown()
        backup.shutdown()
        local.shutdown()


def test_gpt_oss_models_use_low_reasoning_effort(llm_env):
    server, url, hits = _serve(200, "Hi!")
    try:
        llm_env.setattr(settings, "LLM_API_KEY", "k1")
        llm_env.setattr(settings, "LLM_BASE_URL", url)
        llm_env.setattr(settings, "LLM_FALLBACK_MODEL_NAME", "none")
        asyncio.run(agent_module.run_agent("hello"))
        assert hits[0]["reasoning_effort"] == "low"
    finally:
        server.shutdown()


def test_faq_is_in_the_prompt_instead_of_a_tool(llm_env):
    server, url, hits = _serve(200, "Hi!")
    try:
        llm_env.setattr(settings, "LLM_API_KEY", "k1")
        llm_env.setattr(settings, "LLM_BASE_URL", url)
        llm_env.setattr(settings, "LLM_FALLBACK_MODEL_NAME", "none")
        asyncio.run(agent_module.run_agent("hello"))
        system = hits[0]["messages"][0]["content"]
        assert "parking" in system and "Today:" in system
        assert {t["function"]["name"] for t in hits[0]["tools"]} == {
            "calendar_list_slots", "calendar_create_event", "handoff_to_human",
        }
    finally:
        server.shutdown()
