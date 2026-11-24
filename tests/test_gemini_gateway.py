"""Gemini gateway (evals only): request shape and key handling. No request leaves the machine."""

from __future__ import annotations

import json

import httpx
import pytest
from pydantic import SecretStr

from backend.config import get_settings
from backend.gateway import llm_client
from backend.gateway.llm_client import LLMGateway, QuotaExhaustedError, get_gemini_gateway


def test_gemini_gateway_needs_a_key(monkeypatch):
    monkeypatch.setattr(get_settings(), "gemini_api_key", SecretStr(""))
    monkeypatch.setattr(llm_client, "_GEMINI_GATEWAYS", {})
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        get_gemini_gateway("gemini-test")


async def test_gemini_request_uses_reasoning_effort_and_no_qwen_switch(monkeypatch):
    monkeypatch.setattr(get_settings(), "gemini_api_key", SecretStr("test-key"))
    monkeypatch.setattr(llm_client, "_GEMINI_GATEWAYS", {})
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}],
                                         "usage": {"prompt_tokens": 3, "completion_tokens": 1, "total_tokens": 4}})

    real_client = httpx.AsyncClient
    monkeypatch.setattr(llm_client.httpx, "AsyncClient",
                        lambda **kw: real_client(transport=httpx.MockTransport(handler), timeout=kw.get("timeout")))

    gateway = get_gemini_gateway("gemini-test")
    assert gateway is get_gemini_gateway("gemini-test"), "one gateway per model shares the RPM limiter"
    resp = await gateway.chat_completion([{"role": "user", "content": "hi"}], max_tokens=20)

    body = json.loads(sent[0].content)
    assert resp.content == "ok" and resp.model == "gemini-test"
    assert str(sent[0].url) == f"{get_settings().gemini_base_url}/chat/completions"
    assert sent[0].headers["authorization"] == "Bearer test-key"
    assert body["reasoning_effort"] == get_settings().gemini_reasoning_effort
    assert "chat_template_kwargs" not in body


@pytest.mark.parametrize("body, expected_requests", [
    ({"error": {"code": 429, "message": "You exceeded your current quota, please check your plan"}}, 1),
    ({"error": {"code": 429, "message": "Too many concurrent requests"}}, 4),  # shared Qwen VM: transient, retried
])
async def test_quota_429_is_not_retried_but_transient_429_is(monkeypatch, body, expected_requests):
    monkeypatch.setattr(get_settings(), "gemini_api_key", SecretStr("test-key"))
    monkeypatch.setattr(llm_client, "_GEMINI_GATEWAYS", {})
    monkeypatch.setattr(llm_client, "BACKOFF_SECONDS", (0.0, 0.0, 0.0))
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(429, json=body)

    real_client = httpx.AsyncClient
    monkeypatch.setattr(llm_client.httpx, "AsyncClient",
                        lambda **kw: real_client(transport=httpx.MockTransport(handler), timeout=kw.get("timeout")))

    with pytest.raises(RuntimeError) as err:
        await get_gemini_gateway("gemini-test").chat_completion([{"role": "user", "content": "hi"}], max_tokens=20)
    assert len(sent) == expected_requests
    assert isinstance(err.value, QuotaExhaustedError) == (expected_requests == 1)


def test_qwen_gateway_defaults_are_unchanged():
    gateway = LLMGateway()
    settings = get_settings()
    assert gateway.model == settings.llm_model and not gateway.use_system_ca and gateway.extra_payload == {}
    assert gateway._supports_thinking_kwarg is True
