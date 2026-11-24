"""FastAPI Chat, SSE Streaming & Session (DPDP Right to Erasure) Routes."""

from __future__ import annotations

import asyncio
import json
import re
import time
import uuid
from collections import defaultdict, deque
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from backend.agent.graph import JanSahayakAgent
from backend.agent.state import CitizenProfile
from backend.config import get_settings
from backend.db.repositories import Repository, now_ist_iso
from backend.gateway.embedding_client import get_embedding_client
from backend.gateway.translation_client import detect_language
from backend.guardrails.cache import TwoTierResponseCache
from backend.guardrails.injection import check_input_guardrails
from backend.guardrails.pii import mask_pii
from backend.services.auth import get_optional_user

router = APIRouter(prefix="/api", tags=["Chat & Sessions"])

_STATEFUL_KEYWORDS_RE = re.compile(
    r"\b(?:grievance|complaint|shikayat|cpgrams|pgportal|draft|submit|track|status|ticket|MOAFW|MOHFW|/E/20\d{2}/)\b",
    re.IGNORECASE,
)


class SlidingWindowRateLimiter:
    """Per-session/IP sliding-window rate limiter (15 req/min default)."""

    def __init__(self, max_rpm: int = 15, window_seconds: float = 60.0):
        self.max_rpm = max_rpm
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> tuple[bool, int]:
        now = time.monotonic()
        dq = self._hits[key]
        while dq and (now - dq[0]) >= self.window_seconds:
            dq.popleft()
        if len(dq) >= self.max_rpm:
            retry_after = max(1, int(self.window_seconds - (now - dq[0])) + 1)
            return False, retry_after
        dq.append(now)
        return True, 0

    def reset(self) -> None:
        self._hits.clear()


rate_limiter = SlidingWindowRateLimiter(max_rpm=get_settings().rate_limit_rpm_per_session)


def _enforce_rate_limit(request: Request, session_id: str) -> None:
    key = session_id or (request.client.host if request.client else "anonymous")
    allowed, retry_after = rate_limiter.check(key)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded ({rate_limiter.max_rpm} requests/minute per session). Please retry after {retry_after}s.",
            headers={"Retry-After": str(retry_after)},
        )


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    session_id: str = Field(default_factory=lambda: f"sess-{uuid.uuid4().hex[:8]}")
    language: str = Field(default="en")
    profile_overrides: dict[str, Any] | None = None
    bypass_cache: bool = False
    prompt_strategy: str = Field(default="P3")


class SessionUpdateRequest(BaseModel):
    preferred_language: str | None = None
    profile: dict[str, Any] | None = None


def _is_cacheable_query(message: str) -> bool:
    return not bool(_STATEFUL_KEYWORDS_RE.search(message or ""))


def _get_agent(request: Request) -> JanSahayakAgent:
    agent = getattr(request.app.state, "agent", None)
    if agent is None:
        agent = JanSahayakAgent()
        request.app.state.agent = agent
    return agent


async def _run_chat_turn(
    request: Request,
    req: ChatRequest,
    user: dict[str, Any] | None = None,
    event_cb=None,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    settings = get_settings()
    repo = Repository()
    cache = TwoTierResponseCache()
    agent = _get_agent(request)
    user_id = (user or {}).get("username", "anonymous")
    user_role = (user or {}).get("role", "citizen")

    sess = repo.get_or_create_session(req.session_id, preferred_language=req.language)
    profile = CitizenProfile.model_validate(sess["profile"])
    if req.profile_overrides:
        profile = profile.merge(req.profile_overrides)
        repo.update_session(req.session_id, profile=profile.model_dump(), preferred_language=req.language)

    history_rows = repo.get_messages(req.session_id, limit=10)
    history = [{"role": m["role"], "content": m["content"]} for m in history_rows]

    # Mask user message immediately for safe storage & cache lookup
    pii_pre = mask_pii(req.message)
    guard_pre = check_input_guardrails(pii_pre.masked_text)
    detected_lang = detect_language(pii_pre.masked_text, ui_hint=req.language)

    # Tier 1 & Tier 2 Cache Lookup for safe, read-only, English or exact-language Q&A
    allow_cache_write = (
        not guard_pre.blocked
        and not pii_pre.has_pii
        and _is_cacheable_query(pii_pre.masked_text)
        and req.prompt_strategy.upper() == "P3"
    )
    allow_cache_read = allow_cache_write and not req.bypass_cache
    query_emb = None
    if allow_cache_read:
        if detected_lang == "en":
            try:
                query_emb = await get_embedding_client().embed_query(pii_pre.masked_text)
            except Exception:
                query_emb = None
        cached_resp, hit_kind = cache.lookup(
            query_en=pii_pre.masked_text,
            lang=detected_lang,
            profile=profile.non_empty_dict(),
            query_embedding=query_emb,
        )
        if cached_resp is not None:
            trace_id = f"TRC-{uuid.uuid4().hex[:10].upper()}"
            total_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            repo.add_message(req.session_id, "user", pii_pre.masked_text, trace_id=trace_id)
            repo.add_message(
                req.session_id,
                "assistant",
                cached_resp["answer"],
                citations=cached_resp.get("citations"),
                eligibility=cached_resp.get("eligibility_cards"),
                trace_id=trace_id,
            )
            repo.save_trace(
                {
                    "trace_id": trace_id,
                    "session_id": req.session_id,
                    "user_id": user_id,
                    "user_role": user_role,
                    "timestamp": now_ist_iso(),
                    "user_query_masked": pii_pre.masked_text,
                    "final_answer": cached_resp["answer"],
                    "detected_lang": detected_lang,
                    "cache_hit": hit_kind,
                    "model_name": settings.llm_model,
                    "planner": {"cached": True},
                    "retrieved_chunks": cached_resp.get("citations", []),
                    "tool_calls": [],
                    "critic": {"passed": True, "cached": True},
                    "guardrail_flags": [],
                    "spans": [
                        {
                            "span_id": "SPN-01",
                            "name": f"TwoTierCache ({hit_kind} hit)",
                            "type": "RETRIEVAL",
                            "start_offset_ms": 0.0,
                            "duration_ms": total_ms,
                            "status": "ok",
                            "input": {"query": pii_pre.masked_text, "lang": detected_lang},
                            "output": {"cache_hit": hit_kind, "answer_length": len(cached_resp["answer"])},
                            "tokens": {"prompt": 0, "completion": 0, "total": 0},
                            "error": None,
                        }
                    ],
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_latency_ms": total_ms,
                    "step_latencies": {"cache_lookup_ms": total_ms},
                    "status": "ok",
                }
            )
            out = dict(cached_resp)
            out["session_id"] = req.session_id
            out["trace_id"] = trace_id
            out["cache_hit"] = hit_kind
            out["latency_ms"] = total_ms
            out["citizen_profile"] = profile.model_dump()
            return out

    # Run full LangGraph Multi-Agent Pipeline
    state = await agent.run(
        message=req.message,
        session_id=req.session_id,
        ui_language=req.language,
        citizen_profile=profile.model_dump(),
        history=history,
        prompt_strategy=req.prompt_strategy,
        event_callback=event_cb,
    )

    total_ms = round((time.perf_counter() - t0) * 1000.0, 2)
    trace_id = state.get("trace_id") or f"TRC-{uuid.uuid4().hex[:10].upper()}"
    final_answer = state.get("final_answer") or state.get("draft_answer_en") or ""
    updated_profile = state.get("citizen_profile") or profile.model_dump()
    citations = state.get("citations") or []
    eligibility_cards = state.get("eligibility_cards") or []
    grievance_draft = state.get("grievance_draft")
    grievance_receipt = state.get("grievance_receipt")

    # Persist updated profile, conversation messages, and trace
    repo.update_session(
        req.session_id,
        profile=updated_profile,
        preferred_language=state.get("detected_lang") or req.language,
    )
    repo.add_message(req.session_id, "user", state.get("user_message_masked") or pii_pre.masked_text, trace_id=trace_id)
    repo.add_message(
        req.session_id,
        "assistant",
        final_answer,
        citations=citations,
        eligibility=eligibility_cards or None,
        grievance=grievance_draft or grievance_receipt,
        trace_id=trace_id,
    )

    repo.save_trace(
        {
            "trace_id": trace_id,
            "session_id": req.session_id,
            "user_id": user_id,
            "user_role": user_role,
            "timestamp": now_ist_iso(),
            "user_query_masked": state.get("user_message_masked") or pii_pre.masked_text,
            "final_answer": final_answer,
            "detected_lang": state.get("detected_lang") or detected_lang,
            "cache_hit": "miss",
            "model_name": settings.llm_model,
            "planner": state.get("planner_output") or {},
            "retrieved_chunks": [
                {
                    "citation_id": c.get("citation_id"),
                    "scheme_slug": c.get("scheme_slug"),
                    "scheme_name": c.get("scheme_name"),
                    "section": c.get("section"),
                    "source_url": c.get("source_url"),
                    "scores": c.get("scores", {}),
                }
                for c in (state.get("retrieved_chunks") or [])
            ],
            "tool_calls": state.get("tool_calls_log") or [],
            "critic": state.get("critic_output") or {},
            "guardrail_flags": state.get("guardrail_flags") or [],
            "spans": state.get("spans") or [],
            "prompt_tokens": state.get("prompt_tokens", 0),
            "completion_tokens": state.get("completion_tokens", 0),
            "total_latency_ms": total_ms,
            "step_latencies": state.get("step_latencies") or {},
            "status": state.get("status") or "ok",
        }
    )

    response_payload = {
        "session_id": req.session_id,
        "trace_id": trace_id,
        "answer": final_answer,
        "detected_lang": state.get("detected_lang") or detected_lang,
        "cache_hit": "miss",
        "citations": citations,
        "web_results": state.get("web_results") or [],
        "eligibility_cards": eligibility_cards,
        "grievance_draft": grievance_draft,
        "grievance_receipt": grievance_receipt,
        "hitl_paused": bool(state.get("hitl_paused")),
        "citizen_profile": updated_profile,
        "guardrail_flags": state.get("guardrail_flags") or [],
        "critic": state.get("critic_output") or {},
        "tool_calls": state.get("tool_calls_log") or [],
        "latency_ms": total_ms,
        "tokens": {
            "prompt": state.get("prompt_tokens", 0),
            "completion": state.get("completion_tokens", 0),
            "total": state.get("prompt_tokens", 0) + state.get("completion_tokens", 0),
        },
        "status": state.get("status") or "ok",
    }

    # Populate Two-Tier Cache for clean, read-only Q&A turns
    if (
        allow_cache_write
        and state.get("status") == "ok"
        and not grievance_draft
        and not grievance_receipt
        and not state.get("guardrail_blocked")
        and citations
    ):
        try:
            cache_emb = query_emb
            if cache_emb is None and state.get("query_en"):
                cache_emb = await get_embedding_client().embed_query(state["query_en"])
            cache.store(
                query_en=pii_pre.masked_text,
                lang=state.get("detected_lang") or detected_lang,
                profile=profile.non_empty_dict(),
                response_payload=response_payload,
                query_embedding=cache_emb,
            )
        except Exception:
            pass

    return response_payload


@router.post("/chat")
async def chat_sync(
    request: Request,
    req: ChatRequest,
    user: dict[str, Any] | None = Depends(get_optional_user),
) -> dict[str, Any]:
    _enforce_rate_limit(request, req.session_id)
    return await _run_chat_turn(request, req, user=user)


@router.post("/chat/stream")
async def chat_stream(
    request: Request,
    req: ChatRequest,
    user: dict[str, Any] | None = Depends(get_optional_user),
):
    _enforce_rate_limit(request, req.session_id)
    queue: asyncio.Queue[tuple[str, dict[str, Any]] | None] = asyncio.Queue()

    async def on_event(event: str, data: dict[str, Any]) -> None:
        await queue.put((event, data))

    async def worker() -> None:
        try:
            await queue.put(("guardrail", {"status": "Reviewing your question..."}))
            result = await _run_chat_turn(request, req, user=user, event_cb=on_event)
            await queue.put(("final", result))
        except Exception as exc:
            await queue.put(("error", {"detail": str(exc)}))
        finally:
            await queue.put(None)

    asyncio.create_task(worker())

    async def event_generator():
        while True:
            item = await queue.get()
            if item is None:
                break
            ev_name, payload = item
            yield {"event": ev_name, "data": json.dumps(payload, ensure_ascii=False)}

    return EventSourceResponse(event_generator())


@router.get("/sessions")
async def list_user_sessions(
    user: dict[str, Any] | None = Depends(get_optional_user),
) -> dict[str, Any]:
    repo = Repository()
    prefix = f"{user['username']}-" if user else "citizen-"
    primary_id = user.get("session_id") if user else None
    items = repo.list_sessions_for_prefix(prefix=prefix, extra_session_id=primary_id, limit=20)
    return {"sessions": items}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str) -> dict[str, Any]:
    repo = Repository()
    sess = repo.get_or_create_session(session_id)
    messages = repo.get_messages(session_id, limit=50)
    grievances = repo.list_grievances(session_id=session_id, limit=20)
    return {
        "session": sess,
        "messages": messages,
        "grievances": grievances,
    }


@router.put("/sessions/{session_id}")
async def update_session(session_id: str, req: SessionUpdateRequest) -> dict[str, Any]:
    repo = Repository()
    sess = repo.get_or_create_session(session_id)
    updated_profile = sess["profile"]
    if req.profile is not None:
        cleaned = CitizenProfile.model_validate(req.profile).model_dump()
        updated_profile = cleaned
    updated = repo.update_session(
        session_id,
        profile=updated_profile,
        preferred_language=req.preferred_language,
    )
    return {"session": updated}


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str) -> dict[str, Any]:
    """DPDP Act 2023 Right to Erasure endpoint."""
    repo = Repository()
    summary = repo.delete_session(session_id)
    return {
        "status": "erased",
        "session_id": session_id,
        "dpdp_compliance": "All session messages, citizen profile attributes, and unsubmitted drafts have been permanently erased.",
        "summary": summary,
    }
