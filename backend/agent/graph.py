"""LangGraph Stateful Multi-Agent Orchestrator: InputGuardrail -> LanguagePivot -> Planner -> Executor -> Synthesizer -> Critic -> OutputLocalizer."""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from typing import Any, Awaitable, Callable

from langgraph.graph import END, StateGraph

from backend.agent.prompts import (
    CRITIC_SYSTEM_PROMPT,
    PLANNER_SYSTEM_PROMPT,
    SYNTHESIZER_SYSTEM_PROMPT,
    build_p1_zero_shot_messages,
    build_p2_few_shot_messages,
)
from backend.agent.profile_matching import CatalogVocabulary, get_catalog_vocabulary
from backend.agent.state import AgentState, CitizenProfile, CriticOutput, PlannedToolCall, PlannerOutput
from backend.agent.tools import (
    AgentToolbox,
    CheckEligibilityInput,
    DraftGrievanceInput,
    SearchSchemesInput,
    SubmitOrTrackGrievanceInput,
    WebSearchGovInput,
    parse_and_repair_json,
)
from backend.db.repositories import Repository
from backend.gateway.llm_client import LLMGateway, get_llm_gateway
from backend.gateway.translation_client import TranslationClient, detect_language, normalize_lang_code
from backend.guardrails.injection import check_input_guardrails, sanitize_untrusted_evidence
from backend.guardrails.pii import mask_pii

logger = logging.getLogger(__name__)

EventCallback = Callable[[str, dict[str, Any]], Awaitable[None]]

_TICKET_PATTERN = re.compile(r"\b([A-Z]{4,6}/E/20\d{2}/\d{6})\b")
_CITATION_PATTERN = re.compile(r"\[\d+\]")
_CITATION_NUM_RE = re.compile(r"\[(\d+)\]")

_GREETING_OR_HELP_RE = re.compile(
    r"^\s*(?:(?:hi|hello|hey|namaste|namaskar|namaskaram|vanakkam|nomoshkar|good\s+(?:morning|afternoon|evening)|howdy)[,!.\s]*)*"
    r"(?:who\s+are\s+you|what\s+(?:all\s+)?can\s+you\s+do|how\s+can\s+you\s+help(?:\s+me)?|"
    r"tell\s+me\s+what\s+(?:all\s+)?you\s+can\s+do|what\s+do\s+you\s+do|how\s+do\s+you\s+work|"
    r"what\s+are\s+your\s+(?:features|capabilities|services)|help\s+me\s+get\s+started|"
    r"thanks?|thank\s+you|ok(?:ay)?|got\s+it|bye|goodbye)?\s*[?!.\s]*$",
    re.IGNORECASE,
)

_SCHEME_KEYWORDS_RE = re.compile(
    r"\b(?:scheme|yojana|pension|scholarship|loan|subsidy|kisan|ayushman|awas|mudra|vishwakarma|"
    r"ujjwala|sukanya|grievance|complaint|cpgrams|eligible|eligibility|documents|ration|insurance|farmer|student|artisan)\b",
    re.IGNORECASE,
)


# Phrasing of a broad discovery question ("Which schemes am I eligible for?"). Whether the
# question names a specific scheme is checked against the catalog, not a hardcoded list.
_BROAD_ELIGIBILITY_RE = re.compile(
    r"\b(?:which|what|any|all|list|show|suggest|recommend|find)\b.{0,40}\b(?:schemes?|yojanas?|benefits?|scholarships?|programm?e?s?)\b"
    r"|\b(?:schemes?|yojanas?|benefits?|scholarships?)\b.{0,30}\b(?:for me|eligible|qualify|can i (?:get|apply))\b"
    r"|\b(?:am i|i am|i'm)\s+eligible\s*(?:for)?\s*(?:anything|any|\?|$)",
    re.IGNORECASE,
)

# Order in which eligibility cards are shown: best matches first.
_VERDICT_RANK = {"ELIGIBLE": 0, "PARTIALLY_ELIGIBLE": 1, "NEEDS_MORE_INFO": 2, "NOT_ELIGIBLE": 3}

# How many distinct schemes to eligibility-check for a broad discovery question.
_BROAD_ELIGIBILITY_MAX_SCHEMES = 5


def _is_broad_eligibility_query(query_en: str, vocab: CatalogVocabulary) -> bool:
    q = (query_en or "").strip()
    return bool(q) and bool(_BROAD_ELIGIBILITY_RE.search(q)) and not vocab.mentions_specific_scheme(q)


def _is_greeting_or_capability_query(query_en: str) -> bool:
    q = (query_en or "").strip()
    if not q:
        return True
    if _SCHEME_KEYWORDS_RE.search(q):
        return False
    if _GREETING_OR_HELP_RE.match(q):
        return True
    q_low = q.lower()
    if len(q.split()) <= 12 and any(
        phrase in q_low
        for phrase in (
            "what can you do",
            "what all can you do",
            "tell me what you can do",
            "how can you help",
            "who are you",
            "introduce yourself",
            "what services do you offer",
        )
    ):
        return True
    return False


def _extract_citations(chunks: list[dict[str, Any]], web_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    citations: list[dict[str, Any]] = []
    for idx, ch in enumerate(chunks, start=1):
        citations.append(
            {
                "index": idx,
                "citation_id": ch.get("citation_id"),
                "scheme_slug": ch.get("scheme_slug"),
                "scheme_name": ch.get("scheme_name"),
                "ministry": ch.get("ministry"),
                "section": ch.get("section"),
                "faq_numbers": ch.get("faq_numbers", []),
                "source_url": ch.get("source_url"),
                "scores": ch.get("scores", {}),
                "source_type": "myscheme_corpus",
            }
        )
    offset = len(citations)
    for j, wr in enumerate(web_results, start=1):
        citations.append(
            {
                "index": offset + j,
                "citation_id": f"WEB:{j}",
                "scheme_slug": "",
                "scheme_name": wr.get("title", "Official Government Portal"),
                "ministry": "Official .gov.in Web Result",
                "section": "web_fallback",
                "faq_numbers": [],
                "source_url": wr.get("url", "https://www.myscheme.gov.in/"),
                "scores": {},
                "source_type": "gov_web",
                "retrieved_at": wr.get("retrieved_at"),
            }
        )
    return citations


def _build_evidence_block(chunks: list[dict[str, Any]], web_results: list[dict[str, Any]]) -> tuple[str, list[str]]:
    lines: list[str] = []
    flags: list[str] = []
    for idx, ch in enumerate(chunks, start=1):
        lines.append(
            f"[{idx}] Scheme: {ch.get('scheme_name')} | Ministry: {ch.get('ministry')} | "
            f"Section: {ch.get('section')} | URL: {ch.get('source_url')}\n{ch.get('text', '')}"
        )
    offset = len(chunks)
    for j, wr in enumerate(web_results, start=1):
        lines.append(
            f"[{offset + j}] Official Web Result ({wr.get('retrieved_at', '')}): {wr.get('title')} | "
            f"URL: {wr.get('url')}\n{wr.get('snippet', '')}"
        )
        flags.extend(wr.get("security_flags") or [])
    if not lines:
        return "<RETRIEVED_EVIDENCE_UNTRUSTED>\nNO MATCHING SCHEMES FOUND.\n</RETRIEVED_EVIDENCE_UNTRUSTED>", flags
    wrapped, s_flags = sanitize_untrusted_evidence("\n\n".join(lines))
    return wrapped, list(dict.fromkeys(flags + s_flags))


def _deterministic_critic_check(state: AgentState) -> CriticOutput:
    """Fast deterministic audit for PII leaks, missing citations, and CPGRAMS constraints."""
    answer = state.get("draft_answer_en") or ""
    issues: list[str] = []

    # 1. Check no raw Aadhaar/PAN leaked in generated answer
    pii_check = mask_pii(answer)
    if pii_check.has_pii:
        issues.append(f"Draft answer contains unmasked PII ({', '.join(pii_check.pii_types_found)}).")

    # 2. Check inline citations exist when chunks were retrieved
    chunks = state.get("retrieved_chunks") or []
    web_res = state.get("web_results") or []
    has_evidence = bool(chunks or web_res)
    if has_evidence and not _CITATION_PATTERN.search(answer) and not state.get("hitl_paused"):
        issues.append("Draft answer is missing mandatory inline citations [1], [2].")

    # 2b. Every citation number must point at a real evidence item
    n_evidence = len(chunks) + len(web_res)
    out_of_range = sorted({int(n) for n in _CITATION_NUM_RE.findall(answer) if not 1 <= int(n) <= n_evidence})
    if has_evidence and out_of_range:
        issues.append(
            f"Draft cites {', '.join(f'[{n}]' for n in out_of_range)} but only [1]-[{n_evidence}] exist in the evidence."
        )

    # 3. Check CPGRAMS grievance character count
    draft = state.get("grievance_draft")
    if draft and draft.get("char_count", 0) > 2000:
        issues.append("Grievance draft exceeds CPGRAMS 2,000-character limit.")

    if issues:
        return CriticOutput(
            passed=False,
            issues=issues,
            needs_revision=True,
            revision_instructions="Fix the following issues while staying strictly grounded: " + "; ".join(issues),
        )
    return CriticOutput(passed=True, issues=[], needs_revision=False, revision_instructions=None)


class JanSahayakAgent:
    """Compiled LangGraph Planner -> Executor -> Synthesizer -> Critic agent."""

    def __init__(
        self,
        llm: LLMGateway | None = None,
        toolbox: AgentToolbox | None = None,
        repo: Repository | None = None,
    ):
        self._llm = llm
        self.repo = repo or Repository()
        self.toolbox = toolbox or AgentToolbox(repo=self.repo)
        self._translator: TranslationClient | None = None
        self._event_cb: EventCallback | None = None
        self.graph = self._build_graph()

    @property
    def llm(self) -> LLMGateway:
        if self._llm is None:
            self._llm = get_llm_gateway()
        return self._llm

    @property
    def translator(self) -> TranslationClient:
        if self._translator is None:
            self._translator = TranslationClient(llm=self.llm)
        return self._translator

    async def _emit(self, event: str, data: dict[str, Any]) -> None:
        if self._event_cb is not None:
            try:
                await self._event_cb(event, data)
            except Exception:
                pass

    def _append_span(
        self,
        state: AgentState,
        name: str,
        span_type: str,
        t_start: float,
        status: str = "ok",
        inp: Any = None,
        out: Any = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        error: str | None = None,
    ) -> list[dict[str, Any]]:
        spans = list(state.get("spans") or [])
        t0_trace = float(state.get("trace_start_monotonic") or t_start)
        now = time.perf_counter()
        spans.append(
            {
                "span_id": f"SPN-{len(spans) + 1:02d}",
                "name": name,
                "type": span_type,
                "start_offset_ms": round(max(0.0, (t_start - t0_trace) * 1000.0), 2),
                "duration_ms": round(max(0.0, (now - t_start) * 1000.0), 2),
                "status": status,
                "input": inp,
                "output": out,
                "tokens": {
                    "prompt": int(prompt_tokens),
                    "completion": int(completion_tokens),
                    "total": int(prompt_tokens + completion_tokens),
                },
                "error": error,
            }
        )
        return spans

    # ---- Node 1: Input Guardrail (PII Mask + Prompt-Injection Shield) ----
    async def _node_input_guardrail(self, state: AgentState) -> dict[str, Any]:
        t0 = time.perf_counter()
        raw_text = state.get("user_message_raw") or ""
        flags = list(state.get("guardrail_flags") or [])

        pii_res = mask_pii(raw_text)
        if pii_res.has_pii:
            flags.extend(f"pii_masked:{t}" for t in pii_res.pii_types_found)

        verdict = check_input_guardrails(pii_res.masked_text)
        if verdict.blocked:
            flags.extend(verdict.flags)

        lat = round((time.perf_counter() - t0) * 1000.0, 2)
        step_lat = dict(state.get("step_latencies") or {})
        step_lat["input_guardrail_ms"] = lat

        spans = self._append_span(
            state,
            name="InputGuardrail (PII + Injection Shield)",
            span_type="GUARDRAIL",
            t_start=t0,
            status="blocked" if verdict.blocked else "ok",
            inp={"raw_length": len(raw_text)},
            out={
                "masked_query": pii_res.masked_text,
                "pii_masked": pii_res.pii_types_found,
                "blocked": verdict.blocked,
                "category": verdict.category,
            },
        )

        await self._emit(
            "guardrail",
            {
                "blocked": verdict.blocked,
                "category": verdict.category,
                "pii_masked": pii_res.pii_types_found,
                "latency_ms": lat,
            },
        )

        out: dict[str, Any] = {
            "user_message_masked": pii_res.masked_text,
            "pii_warning": pii_res.warning_message,
            "guardrail_blocked": verdict.blocked,
            "guardrail_category": verdict.category,
            "guardrail_flags": list(dict.fromkeys(flags)),
            "step_latencies": step_lat,
            "spans": spans,
        }
        if verdict.blocked:
            out["draft_answer_en"] = verdict.refusal_message or "I cannot assist with this request."
            out["final_answer"] = out["draft_answer_en"]
            out["status"] = "blocked_by_guardrail"
        return out

    # ---- Node 2: Language Detection & English Pivot ----
    async def _node_language_pivot(self, state: AgentState) -> dict[str, Any]:
        t0 = time.perf_counter()
        masked = state.get("user_message_masked") or ""
        ui_lang = state.get("ui_language") or "en"
        detected = detect_language(masked, ui_hint=ui_lang)

        p_toks = state.get("prompt_tokens", 0)
        c_toks = state.get("completion_tokens", 0)
        pt, ct = 0, 0

        if detected != "en":
            await self._emit("language", {"status": f"Translating {detected} query to English for Hybrid RAG..."})
            query_en, pt, ct = await self.translator.to_english(masked, detected)
            p_toks += pt
            c_toks += ct
        else:
            query_en = masked

        lat = round((time.perf_counter() - t0) * 1000.0, 2)
        step_lat = dict(state.get("step_latencies") or {})
        step_lat["language_pivot_ms"] = lat
        spans = self._append_span(
            state,
            name="LanguagePivot (Detect & EN Translation)",
            span_type="LLM" if detected != "en" else "GUARDRAIL",
            t_start=t0,
            inp={"ui_language": ui_lang, "query_masked": masked},
            out={"detected_lang": detected, "query_en": query_en},
            prompt_tokens=pt,
            completion_tokens=ct,
        )

        return {
            "detected_lang": detected,
            "query_en": query_en,
            "prompt_tokens": p_toks,
            "completion_tokens": c_toks,
            "step_latencies": step_lat,
            "spans": spans,
        }

    # ---- Node 3: Planner ----
    async def _node_planner(self, state: AgentState) -> dict[str, Any]:
        t0 = time.perf_counter()
        query_en = state.get("query_en") or ""
        profile = CitizenProfile.model_validate(state.get("citizen_profile") or {})
        active_slugs = state.get("active_scheme_slugs") or []

        await self._emit("planner", {"status": "Understanding your request..."})

        # Deterministic fast-track 1: Greetings, capability questions ("What can you do?"), thanks/smalltalk
        if _is_greeting_or_capability_query(query_en):
            plan = PlannerOutput(
                intent="CONVERSATION_HELP",
                tool_calls=[],
                reasoning="Conversational greeting or capability overview requested.",
            )
            lat = round((time.perf_counter() - t0) * 1000.0, 2)
            step_lat = dict(state.get("step_latencies") or {})
            step_lat["planner_ms"] = lat
            spans = self._append_span(
                state,
                name="Planner (Conversational Greeting / Help)",
                span_type="GUARDRAIL",
                t_start=t0,
                inp={"query_en": query_en},
                out=plan.model_dump(),
            )
            return {
                "planner_output": plan.model_dump(),
                "step_latencies": step_lat,
                "spans": spans,
            }

        # Deterministic fast-track 2: Explicit ticket tracking queries
        ticket_match = _TICKET_PATTERN.search(query_en.upper())
        if ticket_match and any(w in query_en.lower() for w in ("track", "status", "complaint", "grievance", "ticket")):
            plan = PlannerOutput(
                intent="GRIEVANCE_TRACK",
                tool_calls=[
                    PlannedToolCall(
                        tool_name="submit_or_track_grievance",
                        arguments={"action": "track", "registration_number": ticket_match.group(1)},
                    )
                ],
                reasoning="Direct CPGRAMS ticket tracking requested.",
            )
            lat = round((time.perf_counter() - t0) * 1000.0, 2)
            step_lat = dict(state.get("step_latencies") or {})
            step_lat["planner_ms"] = lat
            spans = self._append_span(
                state,
                name="Planner (Fast-Track Ticket Lookup)",
                span_type="TOOL",
                t_start=t0,
                inp={"query_en": query_en},
                out=plan.model_dump(),
            )
            return {
                "planner_output": plan.model_dump(),
                "step_latencies": step_lat,
                "spans": spans,
            }

        # Call Qwen3-8B Planner with JSON extraction & 1-shot Pydantic repair
        recent_hist = (state.get("history") or [])[-4:]
        hist_str = "\n".join(f"{m['role']}: {m['content'][:250]}" for m in recent_hist)
        user_prompt = (
            f"Existing Citizen Profile: {json.dumps(profile.non_empty_dict(), ensure_ascii=False)}\n"
            f"Active Scheme Slugs: {json.dumps(active_slugs)}\n"
            f"Recent History:\n{hist_str or '(none)'}\n\n"
            f"Current User Message (English): {query_en}\n"
            "Output ONLY the compact Planner JSON (reasoning <= 12 words)."
        )

        p_toks = state.get("prompt_tokens", 0)
        c_toks = state.get("completion_tokens", 0)
        pt_call, ct_call = 0, 0
        repair_diag: dict[str, Any] = {}
        err_msg: str | None = None

        try:
            resp = await self.llm.chat_completion(
                messages=[
                    {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=512,
                temperature=0.0,
                disable_thinking=True,
            )
            pt_call = resp.prompt_tokens
            ct_call = resp.completion_tokens
            p_toks += pt_call
            c_toks += ct_call
            parsed, repair_diag = await parse_and_repair_json(resp.content, PlannerOutput, llm=self.llm)
            if repair_diag.get("repair_tokens"):
                ct_call += int(repair_diag["repair_tokens"])
                c_toks += int(repair_diag["repair_tokens"])
        except Exception as exc:
            logger.warning("Planner LLM call failed (%s); falling back to deterministic search_schemes.", exc)
            parsed = None
            err_msg = str(exc)[:200]
            repair_diag = {"error": err_msg}

        if parsed is None:
            parsed = PlannerOutput(
                intent="ELIGIBILITY_CHECK" if any(w in query_en.lower() for w in ("eligible", "eligibility", "qualify")) else "SCHEME_QA",
                tool_calls=[PlannedToolCall(tool_name="search_schemes", arguments={"query": query_en, "top_k": 6})],
                reasoning="Fallback deterministic search plan after planner JSON recovery.",
            )

        # Safety: Planner must NEVER invoke submit directly
        safe_tools: list[PlannedToolCall] = []
        for tc in parsed.tool_calls[:3]:
            if tc.tool_name == "submit_or_track_grievance" and tc.arguments.get("action") == "submit":
                continue
            safe_tools.append(tc)

        # CONSISTENCY GUARANTEE: For SCHEME_QA & ELIGIBILITY_CHECK, ALWAYS execute search_schemes FIRST
        # using the faithful English query (`query_en`), so English, Hindi, Tamil, Marathi, Bengali & Telugu
        # always retrieve the exact same canonical top schemes instead of skipping search or dropping keywords like "OBC"!
        if parsed.intent in ("SCHEME_QA", "ELIGIBILITY_CHECK"):
            has_search = any(tc.tool_name == "search_schemes" for tc in safe_tools)
            if not has_search:
                safe_tools.insert(
                    0,
                    PlannedToolCall(
                        tool_name="search_schemes",
                        arguments={"query": query_en, "top_k": 6},
                    ),
                )
            else:
                for tc in safe_tools:
                    if tc.tool_name == "search_schemes":
                        # Use canonical query_en to guarantee cross-lingual retrieval determinism
                        tc.arguments["query"] = query_en
                        tc.arguments["top_k"] = 6
                        tc.arguments["category"] = None
                        tc.arguments["beneficiary_group"] = None

        parsed.tool_calls = safe_tools
        merged_profile = profile.merge(parsed.profile_updates)

        planner_dict = parsed.model_dump()
        planner_dict["json_repair_diag"] = repair_diag

        lat = round((time.perf_counter() - t0) * 1000.0, 2)
        step_lat = dict(state.get("step_latencies") or {})
        step_lat["planner_ms"] = lat
        spans = self._append_span(
            state,
            name=f"Planner ({self.llm.model})",
            span_type="LLM",
            t_start=t0,
            status="degraded" if repair_diag.get("error") else "ok",
            inp={"query_en": query_en, "profile": profile.non_empty_dict()},
            out=planner_dict,
            prompt_tokens=pt_call,
            completion_tokens=ct_call,
            error=repair_diag.get("error"),
        )

        return {
            "planner_output": planner_dict,
            "citizen_profile": merged_profile.model_dump(),
            "prompt_tokens": p_toks,
            "completion_tokens": c_toks,
            "step_latencies": step_lat,
            "spans": spans,
        }

    # ---- Node 4: Executor (runs planned Pydantic tools + automatic web fallback / eligibility check) ----
    async def _node_executor(self, state: AgentState) -> dict[str, Any]:
        t0 = time.perf_counter()
        plan = state.get("planner_output") or {}
        intent = plan.get("intent", "SCHEME_QA")
        tool_calls = plan.get("tool_calls") or []
        profile_dict = state.get("citizen_profile") or {}
        query_en = state.get("query_en") or ""

        tool_logs: list[dict[str, Any]] = []
        retrieved_chunks: list[dict[str, Any]] = list(state.get("retrieved_chunks") or [])
        web_results: list[dict[str, Any]] = list(state.get("web_results") or [])
        eligibility_cards: list[dict[str, Any]] = []
        grievance_draft: dict[str, Any] | None = None
        grievance_receipt: dict[str, Any] | None = None
        active_slugs: list[str] = list(state.get("active_scheme_slugs") or [])
        low_confidence = False
        # Broad "which schemes am I eligible for?" -> search with the profile and check several schemes.
        vocab = get_catalog_vocabulary(self.repo)
        broad_eligibility = intent == "ELIGIBILITY_CHECK" and _is_broad_eligibility_query(query_en, vocab)

        friendly_tool_msg = {
            "search_schemes": "Searching 649 Central Government schemes & official FAQs...",
            "check_eligibility": "Checking scheme eligibility rules & required documents...",
            "web_search_gov_schemes": "Checking official .gov.in & myscheme.gov.in portals...",
            "draft_grievance": "Drafting formal CPGRAMS grievance letter...",
            "submit_or_track_grievance": "Checking CPGRAMS grievance status...",
        }

        for tc in tool_calls:
            tname = tc.get("tool_name")
            raw_args = dict(tc.get("arguments") or {})
            t_start = time.perf_counter()
            await self._emit("tool_call", {"tool": tname, "status": friendly_tool_msg.get(str(tname), "Looking up details...")})

            try:
                if tname == "search_schemes":
                    raw_args.setdefault("query", query_en)
                    if broad_eligibility:
                        profile_query, profile_group = vocab.build_discovery_query(
                            CitizenProfile.model_validate(profile_dict)
                        )
                        raw_args["query"] = profile_query
                        raw_args["top_k"] = 8
                        if profile_group and not raw_args.get("beneficiary_group"):
                            raw_args["beneficiary_group"] = profile_group
                    inp = SearchSchemesInput.model_validate(raw_args)
                    res = await self.toolbox.search_schemes(inp, citizen_profile=profile_dict)
                    retrieved_chunks = res["results"]
                    low_confidence = bool(res.get("low_confidence"))
                    for r in retrieved_chunks[:3]:
                        if r["scheme_slug"] and r["scheme_slug"] not in active_slugs:
                            active_slugs.insert(0, r["scheme_slug"])
                    active_slugs = active_slugs[:5]
                    tool_logs.append({
                        "tool": tname,
                        "args": inp.model_dump(),
                        "status": "ok",
                        "top_rerank_score": res.get("top_rerank_score"),
                        "result_count": len(retrieved_chunks),
                        "latency_ms": round((time.perf_counter() - t_start) * 1000.0, 2),
                    })

                elif tname == "check_eligibility":
                    req_slug = str(raw_args.get("scheme_slug") or "").strip()
                    # Validate slug exists in catalog; if Planner guessed a non-existent slug, resolve to top retrieved scheme!
                    if not req_slug or not self.repo.get_scheme(req_slug):
                        if retrieved_chunks and retrieved_chunks[0].get("scheme_slug"):
                            req_slug = retrieved_chunks[0]["scheme_slug"]
                        elif active_slugs and self.repo.get_scheme(active_slugs[0]):
                            req_slug = active_slugs[0]
                    raw_args["scheme_slug"] = req_slug
                    raw_args["citizen_profile"] = CitizenProfile.model_validate(profile_dict)
                    inp = CheckEligibilityInput.model_validate(raw_args)
                    res = await self.toolbox.check_eligibility(inp)
                    # Only attach verified scheme cards (never emit broken placeholder cards)
                    if not res.get("error"):
                        eligibility_cards.append(res)
                    tool_logs.append({
                        "tool": tname,
                        "args": {"scheme_slug": inp.scheme_slug},
                        "status": "ok" if not res.get("error") else "skipped_unknown_slug",
                        "verdict": res.get("verdict"),
                        "latency_ms": round((time.perf_counter() - t_start) * 1000.0, 2),
                    })

                elif tname == "web_search_gov_schemes":
                    raw_args.setdefault("query", query_en)
                    inp = WebSearchGovInput.model_validate(raw_args)
                    res = await self.toolbox.web_search_gov_schemes(inp)
                    web_results.extend(res.get("results") or [])
                    tool_logs.append({
                        "tool": tname,
                        "args": inp.model_dump(),
                        "status": "ok" if not res.get("error") else "degraded",
                        "provider": res.get("provider"),
                        "result_count": len(res.get("results") or []),
                        "error": res.get("error"),
                        "latency_ms": round((time.perf_counter() - t_start) * 1000.0, 2),
                    })

                elif tname == "draft_grievance":
                    raw_args.setdefault("session_id", state.get("session_id", ""))
                    if not raw_args.get("scheme_name") and retrieved_chunks:
                        raw_args["scheme_name"] = retrieved_chunks[0]["scheme_name"]
                        raw_args.setdefault("scheme_slug", retrieved_chunks[0]["scheme_slug"])
                        raw_args.setdefault("ministry", retrieved_chunks[0]["ministry"])
                    raw_args.setdefault("scheme_name", "Central Government Welfare Scheme")
                    raw_args.setdefault("issue_summary", query_en)
                    if not raw_args.get("state") and profile_dict.get("state"):
                        raw_args["state"] = profile_dict["state"]
                    inp = DraftGrievanceInput.model_validate(raw_args)
                    grievance_draft = await self.toolbox.draft_grievance(inp)
                    tool_logs.append({
                        "tool": tname,
                        "args": {"scheme_name": inp.scheme_name, "ministry": grievance_draft["ministry_code"]},
                        "status": "ok",
                        "draft_id": grievance_draft["draft_id"],
                        "char_count": grievance_draft["char_count"],
                        "latency_ms": round((time.perf_counter() - t_start) * 1000.0, 2),
                    })

                elif tname == "submit_or_track_grievance":
                    # Enforce server-side: agent never auto-submits without explicit HITL
                    if raw_args.get("action") == "submit":
                        raw_args["user_confirmed"] = False
                    inp = SubmitOrTrackGrievanceInput.model_validate(raw_args)
                    grievance_receipt = await self.toolbox.submit_or_track_grievance(inp)
                    tool_logs.append({
                        "tool": tname,
                        "args": inp.model_dump(),
                        "status": "ok" if not grievance_receipt.get("error") else "blocked",
                        "latency_ms": round((time.perf_counter() - t_start) * 1000.0, 2),
                    })

            except Exception as exc:
                logger.warning("Tool %s execution failed: %s", tname, exc)
                tool_logs.append({
                    "tool": tname,
                    "args": raw_args,
                    "status": "error",
                    "error": str(exc)[:300],
                    "latency_ms": round((time.perf_counter() - t_start) * 1000.0, 2),
                })

        # Automatic follow-up 1: If intent is ELIGIBILITY_CHECK and we found schemes but haven't checked eligibility yet
        # (broad questions check up to 5 distinct schemes; a specific question checks only the top match)
        if intent == "ELIGIBILITY_CHECK" and not eligibility_cards and retrieved_chunks:
            distinct_slugs = list(dict.fromkeys(c["scheme_slug"] for c in retrieved_chunks if c.get("scheme_slug")))
            for slug in distinct_slugs[: _BROAD_ELIGIBILITY_MAX_SCHEMES if broad_eligibility else 1]:
                try:
                    elig = await self.toolbox.check_eligibility(
                        CheckEligibilityInput(
                            scheme_slug=slug,
                            citizen_profile=CitizenProfile.model_validate(profile_dict),
                        )
                    )
                    if elig.get("error"):
                        continue
                    eligibility_cards.append(elig)
                    tool_logs.append({
                        "tool": "check_eligibility",
                        "args": {"scheme_slug": slug, "auto_chained": True},
                        "status": "ok",
                        "verdict": elig.get("verdict"),
                    })
                except Exception as exc:
                    logger.warning("Auto-chained check_eligibility failed for %s: %s", slug, exc)
            # Best matches first so the answer leads with schemes the citizen can actually use
            eligibility_cards.sort(key=lambda c: _VERDICT_RANK.get(str(c.get("verdict")), 9))

        # Automatic follow-up 2: Low-confidence local retrieval -> restricted .gov.in web fallback
        if low_confidence and not web_results and intent in ("SCHEME_QA", "ELIGIBILITY_CHECK"):
            await self._emit("tool_call", {"tool": "web_search_gov_schemes", "status": "Searching official .gov.in portals..."})
            web_res = await self.toolbox.web_search_gov_schemes(WebSearchGovInput(query=query_en, max_results=4))
            web_results.extend(web_res.get("results") or [])
            tool_logs.append({
                "tool": "web_search_gov_schemes",
                "args": {"query": query_en, "auto_fallback": True},
                "status": "ok" if not web_res.get("error") else "degraded",
                "provider": web_res.get("provider"),
                "result_count": len(web_res.get("results") or []),
                "error": web_res.get("error"),
            })

        hitl_paused = grievance_draft is not None
        citations = _extract_citations(retrieved_chunks, web_results)

        lat = round((time.perf_counter() - t0) * 1000.0, 2)
        step_lat = dict(state.get("step_latencies") or {})
        step_lat["executor_ms"] = lat
        spans = self._append_span(
            state,
            name=f"Executor ({len(tool_logs)} tool call{'s' if len(tool_logs) != 1 else ''})",
            span_type="RETRIEVAL" if retrieved_chunks else "TOOL",
            t_start=t0,
            status="error" if any(t.get("status") == "error" for t in tool_logs) else "ok",
            inp={"planned_tools": [tc.get("tool_name") for tc in tool_calls]},
            out={
                "tool_calls": tool_logs,
                "retrieved_count": len(retrieved_chunks),
                "web_results_count": len(web_results),
                "eligibility_cards_count": len(eligibility_cards),
                "hitl_paused": hitl_paused,
            },
        )

        return {
            "tool_calls_log": tool_logs,
            "retrieved_chunks": retrieved_chunks,
            "web_results": web_results,
            "eligibility_cards": eligibility_cards,
            "grievance_draft": grievance_draft,
            "grievance_receipt": grievance_receipt,
            "active_scheme_slugs": active_slugs,
            "pending_grievance_draft_id": grievance_draft["draft_id"] if grievance_draft else state.get("pending_grievance_draft_id"),
            "hitl_paused": hitl_paused,
            "citations": citations,
            "step_latencies": step_lat,
            "spans": spans,
        }

    # ---- Node 5: HITL Pause Formatter (when draft_grievance was created) ----
    async def _node_hitl_pause(self, state: AgentState) -> dict[str, Any]:
        draft = state.get("grievance_draft") or {}
        chunks = state.get("retrieved_chunks") or []
        cite_note = " [1]" if chunks else ""
        msg = (
            f"I have drafted a formal CPGRAMS grievance for **{draft.get('scheme_name')}**{cite_note}, "
            f"routed to **{draft.get('ministry_name')} (`{draft.get('ministry_code')}`)**.\n\n"
            f"- **Draft ID:** `{draft.get('draft_id')}`\n"
            f"- **Character Count:** `{draft.get('char_count', 0)} / 2000` (CPGRAMS compliant)\n"
            f"- **Status:** Awaiting your explicit confirmation (Human-in-the-Loop safety gate)\n\n"
            "Please review the drafted complaint carefully in the **Review & Confirm Grievance** card below "
            "and click **Confirm & Submit** when ready. Nothing has been submitted yet."
        )
        return {
            "draft_answer_en": msg,
            "critic_output": {"passed": True, "issues": [], "needs_revision": False, "mode": "hitl_gate"},
            "status": "awaiting_hitl_confirmation",
        }

    # ---- Node 6: Synthesizer ----
    async def _node_synthesizer(self, state: AgentState) -> dict[str, Any]:
        t0 = time.perf_counter()
        strategy = (state.get("prompt_strategy") or "P3").upper()
        query_en = state.get("query_en") or ""
        chunks = state.get("retrieved_chunks") or []
        web_results = state.get("web_results") or []
        elig_cards = state.get("eligibility_cards") or []
        grievance_receipt = state.get("grievance_receipt")
        profile = state.get("citizen_profile") or {}
        revision_count = state.get("revision_count", 0)
        critic_out = state.get("critic_output") or {}

        await self._emit("synthesizer", {"status": "Preparing a clear answer with official links..."})

        # Direct concise synthesis for ticket tracking receipt
        if grievance_receipt and not chunks and not elig_cards:
            if grievance_receipt.get("found"):
                answer = (
                    f"**CPGRAMS Grievance Status — `{grievance_receipt['registration_number']}`**\n\n"
                    f"- **Current Status:** `{grievance_receipt['status']}`\n"
                    f"- **Ministry:** {grievance_receipt['ministry_name']} (`{grievance_receipt['ministry_code']}`)\n"
                    f"- **Scheme:** {grievance_receipt.get('scheme_name') or 'N/A'}\n"
                    f"- **Subject:** {grievance_receipt.get('subject')}\n"
                    f"- **Submitted / Updated At:** {grievance_receipt.get('submitted_at')}\n"
                    f"- **Expected Disposal SLA:** {grievance_receipt.get('expected_sla_days', 21)} days\n"
                )
            else:
                answer = grievance_receipt.get("message") or "Could not locate that CPGRAMS registration number."
            lat = round((time.perf_counter() - t0) * 1000.0, 2)
            step_lat = dict(state.get("step_latencies") or {})
            step_lat["synthesizer_ms"] = round(step_lat.get("synthesizer_ms", 0.0) + lat, 2)
            return {"draft_answer_en": answer, "step_latencies": step_lat}

        flags = list(state.get("guardrail_flags") or [])

        if strategy == "P1":
            messages = build_p1_zero_shot_messages(query_en, chunks, profile)
        elif strategy == "P2":
            messages = build_p2_few_shot_messages(query_en, chunks, profile)
        else:
            evidence, ev_flags = _build_evidence_block(chunks, web_results)
            flags.extend(ev_flags)

            extra_blocks: list[str] = []
            if len(elig_cards) > 1:
                # Multi-scheme discovery: compact cards (keeps the prompt small) + explicit answer shape
                compact = [
                    {
                        "scheme_name": c.get("scheme_name"),
                        "verdict": c.get("verdict"),
                        "matched_criteria": c.get("matched_criteria"),
                        "unmet_criteria": c.get("unmet_criteria"),
                        "clarifying_questions": (c.get("clarifying_questions") or [])[:2],
                        "documents_required": (c.get("documents_required") or [])[:4],
                        "source_url": c.get("source_url"),
                    }
                    for c in elig_cards
                ]
                extra_blocks.append(
                    "Structured Eligibility Tool Output (SEVERAL schemes, best match first):\n"
                    + json.dumps(compact, ensure_ascii=False, indent=2)
                )
                extra_blocks.append(
                    "ANSWER SHAPE FOR THIS BROAD ELIGIBILITY QUESTION:\n"
                    "- Under a heading like **Schemes That May Suit You**, list up to 4 schemes whose verdict is "
                    "ELIGIBLE, PARTIALLY_ELIGIBLE or NEEDS_MORE_INFO, in the order given: one bullet each with the scheme "
                    "name in bold, its status, one short benefit line and a citation.\n"
                    "- Do NOT recommend NOT_ELIGIBLE schemes. If every scheme is NOT_ELIGIBLE, say the closest matches "
                    "found do not fit the profile.\n"
                    "- NEVER claim that no other schemes exist or match — only a few top results were checked.\n"
                    "- End with ONE short follow-up question that narrows the search (e.g. the kind of help they want: "
                    "scholarship, skill training, loan, health, housing)."
                )
            elif elig_cards:
                extra_blocks.append("Structured Eligibility Tool Output:\n" + json.dumps(elig_cards, ensure_ascii=False, indent=2))
            if revision_count > 0 and critic_out.get("revision_instructions"):
                extra_blocks.append(f"MANDATORY CRITIC REVISION INSTRUCTIONS:\n{critic_out['revision_instructions']}")

            user_content = (
                f"Citizen Profile: {json.dumps(profile, ensure_ascii=False)}\n\n"
                f"Retrieved Evidence:\n{evidence}\n\n"
                + ("\n\n".join(extra_blocks) + "\n\n" if extra_blocks else "")
                + f"Citizen Question: {query_en}\n"
                "Provide a grounded, helpful answer with inline citations [1], [2]."
            )
            messages = [
                {"role": "system", "content": SYNTHESIZER_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ]

        resp = await self.llm.chat_completion(
            messages=messages,
            max_tokens=560,
            temperature=0.05,
            disable_thinking=True,
        )

        lat = round((time.perf_counter() - t0) * 1000.0, 2)
        step_lat = dict(state.get("step_latencies") or {})
        step_lat["synthesizer_ms"] = round(step_lat.get("synthesizer_ms", 0.0) + lat, 2)
        spans = self._append_span(
            state,
            name=f"Synthesizer ({self.llm.model}, {strategy})",
            span_type="LLM",
            t_start=t0,
            inp={"query_en": query_en, "chunks_used": len(chunks), "revision_round": revision_count},
            out={"answer_preview": resp.content[:600], "char_length": len(resp.content)},
            prompt_tokens=resp.prompt_tokens,
            completion_tokens=resp.completion_tokens,
        )

        return {
            "draft_answer_en": resp.content,
            "guardrail_flags": list(dict.fromkeys(flags)),
            "prompt_tokens": state.get("prompt_tokens", 0) + resp.prompt_tokens,
            "completion_tokens": state.get("completion_tokens", 0) + resp.completion_tokens,
            "step_latencies": step_lat,
            "spans": spans,
        }

    # ---- Node 7: Critic / Groundedness Verifier ----
    async def _node_critic(self, state: AgentState) -> dict[str, Any]:
        t0 = time.perf_counter()
        await self._emit("critic", {"status": "Double-checking accuracy & official links..."})

        # Step 1: Deterministic check always runs
        det = _deterministic_critic_check(state)
        p_toks = state.get("prompt_tokens", 0)
        c_toks = state.get("completion_tokens", 0)
        revision_count = state.get("revision_count", 0)

        critic_out = det
        # Step 2: Run LLM Critic on P3 when deterministic check passes and not skipped (and not already revised)
        should_run_llm_critic = (
            det.passed
            and (state.get("prompt_strategy") or "P3").upper() == "P3"
            and not state.get("skip_critic_llm", False)
            and revision_count == 0
            and bool(state.get("retrieved_chunks") or state.get("eligibility_cards"))
        )

        if should_run_llm_critic:
            # Audit against EXACTLY the numbered evidence the Synthesizer saw; a truncated subset made
            # the critic flag real amounts and citations [5]+ as invented (trace TRC-6CBB8CC995).
            evidence, _ = _build_evidence_block(state.get("retrieved_chunks") or [], state.get("web_results") or [])
            verdicts = [
                {"scheme_name": c.get("scheme_name"), "verdict": c.get("verdict")}
                for c in (state.get("eligibility_cards") or [])
            ]
            verdict_block = (
                f"Eligibility Tool Verdicts:\n{json.dumps(verdicts, ensure_ascii=False)}\n\n" if verdicts else ""
            )
            try:
                resp = await self.llm.chat_completion(
                    messages=[
                        {"role": "system", "content": CRITIC_SYSTEM_PROMPT},
                        {
                            "role": "user",
                            "content": (
                                f"Question: {state.get('query_en', '')}\n\n"
                                f"Retrieved Evidence:\n{evidence}\n\n"
                                f"{verdict_block}"
                                f"Draft Answer:\n{state.get('draft_answer_en', '')}\n\n"
                                "Output ONLY the Critic JSON."
                            ),
                        },
                    ],
                    max_tokens=200,
                    temperature=0.0,
                    disable_thinking=True,
                )
                p_toks += resp.prompt_tokens
                c_toks += resp.completion_tokens
                parsed_critic, _ = await parse_and_repair_json(
                    resp.content, CriticOutput, llm=self.llm, allow_llm_repair=False
                )
                if parsed_critic is not None:
                    critic_out = parsed_critic
            except Exception as exc:
                logger.warning("LLM Critic failed (%s); keeping deterministic critic verdict.", exc)

        # Enforce max 1 corrective loop
        if revision_count >= 1:
            critic_out.needs_revision = False

        lat = round((time.perf_counter() - t0) * 1000.0, 2)
        step_lat = dict(state.get("step_latencies") or {})
        step_lat["critic_ms"] = round(step_lat.get("critic_ms", 0.0) + lat, 2)
        spans = self._append_span(
            state,
            name="Critic / Groundedness Verifier",
            span_type="LLM" if should_run_llm_critic else "GUARDRAIL",
            t_start=t0,
            status="ok" if critic_out.passed else "needs_revision",
            inp={"revision_count": revision_count},
            out=critic_out.model_dump(),
            prompt_tokens=p_toks - state.get("prompt_tokens", 0),
            completion_tokens=c_toks - state.get("completion_tokens", 0),
        )

        return {
            "critic_output": critic_out.model_dump(),
            "revision_count": revision_count + (1 if critic_out.needs_revision else 0),
            "prompt_tokens": p_toks,
            "completion_tokens": c_toks,
            "step_latencies": step_lat,
            "spans": spans,
        }

    # ---- Node 8: Output Localizer ----
    async def _node_output_localizer(self, state: AgentState) -> dict[str, Any]:
        t0 = time.perf_counter()
        draft_en = state.get("draft_answer_en") or ""
        # Always mask any accidental PII on the way out
        draft_en = mask_pii(draft_en).masked_text

        target_lang = normalize_lang_code(state.get("detected_lang") or state.get("ui_language") or "en")
        p_toks = state.get("prompt_tokens", 0)
        c_toks = state.get("completion_tokens", 0)

        if target_lang != "en":
            await self._emit("localize", {"status": f"Localizing response to {target_lang}..."})
            final_text, pt, ct = await self.translator.from_english(draft_en, target_lang)
            p_toks += pt
            c_toks += ct
        else:
            final_text = draft_en

        # Prepend DPDP privacy warning if PII was masked in the user's input
        if state.get("pii_warning"):
            final_text = f"> **{state['pii_warning']}**\n\n{final_text}"

        lat = round((time.perf_counter() - t0) * 1000.0, 2)
        step_lat = dict(state.get("step_latencies") or {})
        step_lat["output_localizer_ms"] = lat
        spans = self._append_span(
            state,
            name=f"OutputLocalizer ({target_lang})",
            span_type="LLM" if target_lang != "en" else "GUARDRAIL",
            t_start=t0,
            inp={"target_lang": target_lang},
            out={"final_length": len(final_text)},
            prompt_tokens=p_toks - state.get("prompt_tokens", 0),
            completion_tokens=c_toks - state.get("completion_tokens", 0),
        )

        return {
            "final_answer": final_text,
            "prompt_tokens": p_toks,
            "completion_tokens": c_toks,
            "step_latencies": step_lat,
            "spans": spans,
            "status": state.get("status") or "ok",
        }

    # ---- Routing Functions ----
    @staticmethod
    def _route_after_guardrail(state: AgentState) -> str:
        return "blocked" if state.get("guardrail_blocked") else "safe"

    @staticmethod
    def _route_after_planner(state: AgentState) -> str:
        plan = state.get("planner_output") or {}
        intent = plan.get("intent")
        if intent == "CONVERSATION_HELP":
            return "conversation_help"
        if intent == "OUT_OF_SCOPE" and not plan.get("tool_calls"):
            return "out_of_scope"
        return "execute"

    async def _node_conversation_help(self, state: AgentState) -> dict[str, Any]:
        t0 = time.perf_counter()
        query_en = (state.get("query_en") or "").strip()
        profile = CitizenProfile.model_validate(state.get("citizen_profile") or {}).non_empty_dict()
        recent_hist = (state.get("history") or [])[-4:]
        hist_str = "\n".join(f"{m['role']}: {m['content'][:200]}" for m in recent_hist)

        resp = await self.llm.chat_completion(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are JanSahayak, a warm, friendly Indian Citizen Welfare & Public Grievance Assistant. "
                        "Reply naturally and concisely (under 140 words) to the citizen's greeting, thank-you, or capability question. "
                        "Briefly explain what you can help with:\n"
                        "- Discovering eligible Central Government welfare schemes (649 schemes across 51 Ministries, such as PM-KISAN, Ayushman Bharat, scholarships, PM Vishwakarma, Mudra, pensions)\n"
                        "- Checking personal eligibility rules, exclusions, and required documents\n"
                        "- Drafting, submitting (with your confirmation & email receipt), and tracking CPGRAMS public grievances\n"
                        "- Communicating in English, Hindi, Marathi, Bengali, Tamil, and Telugu\n"
                        "Do NOT invent or recommend any random specific scheme when the user only greeted you or asked what you can do. "
                        "End with a warm, simple question asking how you can help them today."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Citizen Profile: {json.dumps(profile, ensure_ascii=False)}\n"
                        f"Recent Chat:\n{hist_str or '(new conversation)'}\n\n"
                        f"User Message: {query_en}"
                    ),
                },
            ],
            max_tokens=260,
            temperature=0.3,
            disable_thinking=True,
        )
        lat = round((time.perf_counter() - t0) * 1000.0, 2)
        step_lat = dict(state.get("step_latencies") or {})
        step_lat["conversation_help_ms"] = lat
        spans = self._append_span(
            state,
            name=f"ConversationalReply ({self.llm.model})",
            span_type="LLM",
            t_start=t0,
            inp={"query_en": query_en},
            out={"reply_preview": resp.content[:300]},
            prompt_tokens=resp.prompt_tokens,
            completion_tokens=resp.completion_tokens,
        )
        return {
            "draft_answer_en": resp.content,
            "critic_output": {"passed": True, "issues": [], "needs_revision": False, "mode": "conversational"},
            "prompt_tokens": state.get("prompt_tokens", 0) + resp.prompt_tokens,
            "completion_tokens": state.get("completion_tokens", 0) + resp.completion_tokens,
            "step_latencies": step_lat,
            "spans": spans,
            "status": "ok",
        }

    @staticmethod
    def _route_after_executor(state: AgentState) -> str:
        return "hitl_pause" if state.get("hitl_paused") else "synthesize"

    @staticmethod
    def _route_after_critic(state: AgentState) -> str:
        critic = state.get("critic_output") or {}
        if critic.get("needs_revision") and state.get("revision_count", 0) <= 1:
            return "revise"
        return "localize"

    async def _node_out_of_scope(self, state: AgentState) -> dict[str, Any]:
        return {
            "draft_answer_en": (
                "I specialize in Indian Central Government welfare schemes, eligibility verification, "
                "required documents, and CPGRAMS grievance redressal. Your query appears to be outside this scope. "
                "Please ask me about any Central Government scheme (such as PM-KISAN, Ayushman Bharat, PMAY, Mudra, "
                "scholarships, or pensions) or a scheme-related grievance."
            ),
            "critic_output": {"passed": True, "issues": [], "needs_revision": False},
            "status": "out_of_scope",
        }

    def _build_graph(self):
        sg = StateGraph(AgentState)
        sg.add_node("input_guardrail", self._node_input_guardrail)
        sg.add_node("language_pivot", self._node_language_pivot)
        sg.add_node("planner", self._node_planner)
        sg.add_node("executor", self._node_executor)
        sg.add_node("hitl_pause", self._node_hitl_pause)
        sg.add_node("conversation_help", self._node_conversation_help)
        sg.add_node("out_of_scope", self._node_out_of_scope)
        sg.add_node("synthesizer", self._node_synthesizer)
        sg.add_node("critic", self._node_critic)
        sg.add_node("output_localizer", self._node_output_localizer)

        sg.set_entry_point("input_guardrail")
        sg.add_conditional_edges(
            "input_guardrail",
            self._route_after_guardrail,
            {"blocked": END, "safe": "language_pivot"},
        )
        sg.add_edge("language_pivot", "planner")
        sg.add_conditional_edges(
            "planner",
            self._route_after_planner,
            {
                "conversation_help": "conversation_help",
                "out_of_scope": "out_of_scope",
                "execute": "executor",
            },
        )
        sg.add_edge("conversation_help", "output_localizer")
        sg.add_edge("out_of_scope", "output_localizer")
        sg.add_conditional_edges(
            "executor",
            self._route_after_executor,
            {"hitl_pause": "hitl_pause", "synthesize": "synthesizer"},
        )
        sg.add_edge("hitl_pause", "output_localizer")
        sg.add_edge("synthesizer", "critic")
        sg.add_conditional_edges(
            "critic",
            self._route_after_critic,
            {"revise": "synthesizer", "localize": "output_localizer"},
        )
        sg.add_edge("output_localizer", END)
        return sg.compile()

    async def run(
        self,
        message: str,
        session_id: str,
        ui_language: str = "en",
        citizen_profile: dict[str, Any] | None = None,
        history: list[dict[str, str]] | None = None,
        active_scheme_slugs: list[str] | None = None,
        prompt_strategy: str = "P3",
        skip_critic_llm: bool = False,
        event_callback: EventCallback | None = None,
    ) -> AgentState:
        self._event_cb = event_callback
        trace_id = f"TRC-{uuid.uuid4().hex[:10].upper()}"
        initial_state: AgentState = {
            "session_id": session_id,
            "trace_id": trace_id,
            "user_message_raw": message,
            "ui_language": ui_language,
            "citizen_profile": citizen_profile or {},
            "history": history or [],
            "active_scheme_slugs": active_scheme_slugs or [],
            "guardrail_flags": [],
            "retrieved_chunks": [],
            "web_results": [],
            "eligibility_cards": [],
            "tool_calls_log": [],
            "revision_count": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "step_latencies": {},
            "spans": [],
            "trace_start_monotonic": time.perf_counter(),
            "cache_hit": "miss",
            "prompt_strategy": prompt_strategy,
            "skip_critic_llm": skip_critic_llm,
        }
        try:
            result = await self.graph.ainvoke(initial_state)
            return result
        finally:
            self._event_cb = None
