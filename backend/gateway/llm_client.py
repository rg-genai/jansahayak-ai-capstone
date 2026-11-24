"""Singleton Qwen/Qwen3-8B LLMGateway with Semaphore(1), 55 RPM throttle, TLS CA verify, 2/4/8s backoff, 8192 token budgeter & <think> stripper."""

from __future__ import annotations

import asyncio
import logging
import re
import ssl
import time
from collections import deque
from dataclasses import dataclass
from typing import Any

import httpx
import tiktoken

from backend.config import get_settings

logger = logging.getLogger(__name__)

try:
    _ENC = tiktoken.get_encoding("cl100k_base")
except Exception:
    _ENC = None
_THINK_RE = re.compile(r"<think>[\s\S]*?</think>\s*", re.IGNORECASE)
_UNCLOSED_THINK_RE = re.compile(r"<think>[\s\S]*$", re.IGNORECASE)

CONTEXT_WINDOW_LIMIT = 8192
MAX_OUTPUT_HARD_CAP = 1024
BACKOFF_SECONDS = (2.0, 4.0, 8.0)
# Gemini's 429 body when a per-day/per-minute quota is used up: retrying cannot help and burns free-tier quota.
_QUOTA_EXHAUSTED_MARKER = "exceeded your current quota"


class QuotaExhaustedError(RuntimeError):
    """The provider refused the call because the account's quota is used up (not a transient 429)."""


def count_tokens(text: str) -> int:
    if not text:
        return 0
    if _ENC is not None:
        return len(_ENC.encode(text, disallowed_special=()))
    return max(1, int(len(text.split()) * 1.35))


def count_messages_tokens(messages: list[dict[str, str]]) -> int:
    total = 0
    for m in messages:
        total += 4 + count_tokens(m.get("role", "")) + count_tokens(m.get("content", ""))
    return total + 3


def strip_thinking(text: str) -> str:
    """Strip Qwen3 <think>...</think> blocks cleanly."""
    if not text:
        return ""
    cleaned = _THINK_RE.sub("", text)
    if "<think>" in cleaned.lower():
        cleaned = _UNCLOSED_THINK_RE.sub("", cleaned)
    return cleaned.strip()


def truncate_to_tokens(text: str, max_tokens: int) -> str:
    if max_tokens <= 0:
        return ""
    if _ENC is not None:
        tokens = _ENC.encode(text, disallowed_special=())
        if len(tokens) <= max_tokens:
            return text
        return _ENC.decode(tokens[:max_tokens])
    words = text.split()
    max_words = max(1, int(max_tokens / 1.35))
    return " ".join(words[:max_words])


@dataclass
class LLMResponse:
    content: str
    raw_content: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: float
    retries: int
    model: str


class LLMGateway:
    """Application-level singleton gateway enforcing Track B VM constraints."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        max_rpm: int | None = None,
        use_system_ca: bool = False,
        extra_payload: dict[str, Any] | None = None,
    ):
        """Defaults: the hosted Qwen VM from settings. Another OpenAI-compatible provider (e.g. Gemini) passes
        its own URL/model/key, `use_system_ca=True` (public CA, TLS still verified) and provider-specific fields."""
        self.settings = get_settings()
        self.base_url = (base_url or self.settings.llm_base_url).rstrip("/")
        self.model = model or self.settings.llm_model
        self.api_key = api_key if api_key is not None else self.settings.llm_api_key.get_secret_value()
        self.ca_cert = self.settings.llm_ca_cert_abs
        self.use_system_ca = use_system_ca
        self.extra_payload = dict(extra_payload or {})
        self.max_rpm = min(max_rpm or self.settings.llm_max_rpm, 60)
        self.max_output_cap = min(self.settings.llm_max_output_tokens, MAX_OUTPUT_HARD_CAP)

        self._semaphore = asyncio.Semaphore(self.settings.llm_max_concurrent_requests)
        self._rpm_lock = asyncio.Lock()
        self._request_timestamps: deque[float] = deque()
        # Qwen's chat_template_kwargs switch is vLLM-specific; other providers get their own fields instead.
        self._supports_thinking_kwarg: bool | None = not use_system_ca

    def enforce_context_budget(
        self,
        messages: list[dict[str, str]],
        max_tokens: int,
    ) -> tuple[list[dict[str, str]], int]:
        """Ensure input_tokens + max_tokens <= 8192 with safety headroom, clamping max_tokens <= 1024."""
        clamped_out = max(16, min(int(max_tokens), self.max_output_cap, MAX_OUTPUT_HARD_CAP))
        safety_headroom = 192
        input_budget = CONTEXT_WINDOW_LIMIT - clamped_out - safety_headroom

        msgs = [{"role": m["role"], "content": str(m.get("content", ""))} for m in messages]
        if count_messages_tokens(msgs) <= input_budget:
            return msgs, clamped_out

        # Step 1: Drop oldest middle conversation turns (keep system [0] and final user [-1])
        while len(msgs) > 2 and count_messages_tokens(msgs) > input_budget:
            msgs.pop(1)

        if count_messages_tokens(msgs) <= input_budget:
            return msgs, clamped_out

        # Step 2: Trim final user message (which holds retrieved context) to fit remaining budget
        system_toks = count_messages_tokens(msgs[:-1]) if len(msgs) > 1 else 0
        avail_for_last = max(256, input_budget - system_toks - 16)
        msgs[-1]["content"] = truncate_to_tokens(msgs[-1]["content"], avail_for_last)

        # Step 3: If system prompt itself is huge, trim it as last resort
        if count_messages_tokens(msgs) > input_budget and len(msgs) > 1:
            sys_budget = max(256, input_budget - count_tokens(msgs[-1]["content"]) - 32)
            msgs[0]["content"] = truncate_to_tokens(msgs[0]["content"], sys_budget)

        return msgs, clamped_out

    async def _wait_for_rpm_slot(self) -> None:
        async with self._rpm_lock:
            now = time.monotonic()
            while self._request_timestamps and (now - self._request_timestamps[0]) >= 60.0:
                self._request_timestamps.popleft()
            if len(self._request_timestamps) >= self.max_rpm:
                wait_for = 60.0 - (now - self._request_timestamps[0]) + 0.1
                if wait_for > 0:
                    logger.info("LLMGateway RPM ceiling (%d/min) reached; sleeping %.2fs", self.max_rpm, wait_for)
                    await asyncio.sleep(wait_for)
                now = time.monotonic()
                while self._request_timestamps and (now - self._request_timestamps[0]) >= 60.0:
                    self._request_timestamps.popleft()
            self._request_timestamps.append(time.monotonic())

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        max_tokens: int = 512,
        temperature: float = 0.1,
        disable_thinking: bool = True,
        timeout: float = 90.0,
    ) -> LLMResponse:
        if not self.use_system_ca and not self.ca_cert.exists():
            raise FileNotFoundError(f"LLM CA certificate not found: {self.ca_cert}")

        budgeted_msgs, clamped_max_tokens = self.enforce_context_budget(messages, max_tokens)

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": budgeted_msgs,
            "max_tokens": clamped_max_tokens,
            "temperature": temperature,
            **self.extra_payload,
        }
        if disable_thinking and self._supports_thinking_kwarg:
            payload["chat_template_kwargs"] = {"enable_thinking": False}

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self.base_url}/chat/completions"

        retries = 0
        t0 = time.perf_counter()

        ssl_ctx = ssl.create_default_context() if self.use_system_ca else ssl.create_default_context(cafile=str(self.ca_cert))
        async with self._semaphore:
            await self._wait_for_rpm_slot()
            async with httpx.AsyncClient(verify=ssl_ctx, timeout=timeout) as client:
                for attempt in range(len(BACKOFF_SECONDS) + 1):
                    try:
                        resp = await client.post(url, json=payload, headers=headers)
                        if resp.status_code == 200:
                            data = resp.json()
                            raw_content = data["choices"][0]["message"].get("content") or ""
                            clean_content = strip_thinking(raw_content)
                            usage = data.get("usage") or {}
                            latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)
                            return LLMResponse(
                                content=clean_content,
                                raw_content=raw_content,
                                prompt_tokens=int(usage.get("prompt_tokens") or count_messages_tokens(budgeted_msgs)),
                                completion_tokens=int(usage.get("completion_tokens") or count_tokens(raw_content)),
                                total_tokens=int(usage.get("total_tokens") or 0),
                                latency_ms=latency_ms,
                                retries=retries,
                                model=self.model,
                            )

                        # Graceful fallback if server rejects chat_template_kwargs
                        if (
                            resp.status_code in (400, 422)
                            and "chat_template_kwargs" in payload
                            and "chat_template_kwargs" in resp.text
                        ):
                            logger.warning("Server rejected chat_template_kwargs; falling back without it.")
                            self._supports_thinking_kwarg = False
                            payload.pop("chat_template_kwargs", None)
                            continue

                        if resp.status_code == 429 and _QUOTA_EXHAUSTED_MARKER in resp.text.lower():
                            raise QuotaExhaustedError(f"LLM API quota exhausted ({self.model}): {resp.text[:300]}")

                        if resp.status_code in (429, 500, 502, 503, 504) and attempt < len(BACKOFF_SECONDS):
                            wait = BACKOFF_SECONDS[attempt]
                            retries += 1
                            logger.warning("LLM API HTTP %s; retry %d in %.1fs", resp.status_code, retries, wait)
                            await asyncio.sleep(wait)
                            continue

                        raise RuntimeError(f"LLM API HTTP {resp.status_code}: {resp.text[:300]}")
                    except (httpx.TimeoutException, httpx.TransportError) as exc:
                        if attempt < len(BACKOFF_SECONDS):
                            wait = BACKOFF_SECONDS[attempt]
                            retries += 1
                            logger.warning("LLM transport error (%s); retry %d in %.1fs", exc, retries, wait)
                            await asyncio.sleep(wait)
                            continue
                        raise RuntimeError(f"LLM API transport failure after retries: {exc}") from exc

        raise RuntimeError("LLM API failed after exhausting retries")


_SINGLETON_GATEWAY: LLMGateway | None = None


def get_llm_gateway() -> LLMGateway:
    global _SINGLETON_GATEWAY
    if _SINGLETON_GATEWAY is None:
        _SINGLETON_GATEWAY = LLMGateway()
    return _SINGLETON_GATEWAY


_GEMINI_GATEWAYS: dict[str, LLMGateway] = {}


def get_gemini_gateway(model: str) -> LLMGateway:
    """Gateway for a Gemini model via Google's OpenAI-compatible endpoint (evals only: second LLM and judge).

    One gateway per model, so its RPM limiter covers every caller. Raises if GEMINI_API_KEY is not set."""
    settings = get_settings()
    api_key = settings.gemini_api_key.get_secret_value().strip()
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set in .env")
    if model not in _GEMINI_GATEWAYS:
        _GEMINI_GATEWAYS[model] = LLMGateway(
            base_url=settings.gemini_base_url,
            model=model,
            api_key=api_key,
            max_rpm=settings.gemini_max_rpm,
            use_system_ca=True,
            extra_payload={"reasoning_effort": settings.gemini_reasoning_effort},
        )
    return _GEMINI_GATEWAYS[model]
