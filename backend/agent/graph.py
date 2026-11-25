"""LangGraph Stateful Agent: InputGuardrail -> LanguagePivot -> Planner -> [Executor <-> Reflector loop] -> Synthesizer -> Critic -> OutputLocalizer."""

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
    REFLECTOR_SYSTEM_PROMPT,
    SYNTHESIZER_SYSTEM_PROMPT,
    build_p1_zero_shot_messages,
    build_p2_few_shot_messages,
)
from backend.agent.profile_matching import CatalogVocabulary, get_catalog_vocabulary
from backend.agent.state import (
    AgentState,
    CitizenProfile,
    CriticOutput,
    PlannedToolCall,
    PlannerOutput,
    ReflectionOutput,
)
from backend.agent.tools import (
    AgentToolbox,
    CheckEligibilityInput,
    DraftGrievanceInput,
    SearchSchemesInput,
    SubmitOrTrackGrievanceInput,
    WebSearchGovInput,
    parse_and_repair_json,
)
from backend.config import get_settings
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

# Evidence chunks kept for the Synthesizer across loop rounds (keeps the 8B prompt within budget).
_MAX_EVIDENCE_CHUNKS = 8
# When a question names one scheme, its official sections fill the evidence except these slots, which keep
# other schemes' search results (a comparison question names two schemes).
_RESERVED_OTHER_SCHEME_SLOTS = 2


# ---- Agent loop (Reflector) helpers ----
# Intents where observing results and adapting is useful; grievance/tracking flows are single-pass.
_REFLECTIVE_INTENTS = ("SCHEME_QA", "ELIGIBILITY_CHECK")
_MAX_SCHEMES_IN_OBSERVATION = 6
_MAX_RECHECK_SLUGS = 3
_NON_WORD_RE = re.compile(r"[^a-z0-9]+")


# Profile facts that most often decide eligibility, with plain-language names for the clarifying question.
_KEY_PROFILE_FACTS = {
    "age": "age",
    "occupation": "occupation",
    "annual_income_inr": "yearly family income",
    "social_category": "social category (SC / ST / OBC / EWS / General)",
}

# A message that is only an ID / number with no request (e.g. "1234 5678 9012"): the 8B planner was seen
# drafting a grievance from such input, so it is routed to a clarifying question before any tool runs.
_MASKED_PII_RE = re.compile(r"\[[A-Z_]+(?::[^\]]*)?\]")
_ID_LIKE_RE = re.compile(r"\d")
_WORD_RE = re.compile(r"[A-Za-z]{2,}")
_ACRONYM_MAX_LEN = 5
# Opening line of every clarifying question this agent asks (lets the next turn recognise an answer to it).
_CLARIFY_PREFIX = "To give you an accurate answer, I need a little more information."
# A question about the citizen's own situation says "I / my / we ...". Without that it is a general rule question
# ("What is the minimum age for X?"), which the 8B Reflector still answered by asking the citizen's age (gold eval).
_FIRST_PERSON_RE = re.compile(r"\b(i|i'm|i've|me|my|mine|myself|we|our|ours|us)\b", re.IGNORECASE)

_BARE_ID_QUESTION = (
    "I can see you've shared a number or ID. What would you like me to do with it? For example: track a "
    "complaint, check a scheme application, or find schemes for you. (For your safety, please don't share "
    "your full Aadhaar number here.)"
)


def _is_bare_identifier(message: str) -> bool:
    text = message or ""
    has_id = bool(_MASKED_PII_RE.search(text) or _ID_LIKE_RE.search(text))
    words = [
        w for w in _WORD_RE.findall(_MASKED_PII_RE.sub(" ", text))
        if not (w.isupper() and len(w) <= _ACRONYM_MAX_LEN)  # "NSP" in "NSP/2024/123456" is part of the ID
    ]
    return has_id and not words


def _verified_continuation(claimed: str | None, history: list[dict[str, str]]) -> str | None:
    """Return the original request being continued, only if it really is an earlier user message."""
    want = _normalize_query(claimed)
    if len(want) < 3:
        return None
    for msg in reversed(history):
        if msg.get("role") == "user":
            have = _normalize_query(msg.get("content"))
            if want == have or (len(want) >= 10 and (want in have or have in want)):
                return msg["content"]
    return None


def _request_before_our_question(history: list[dict[str, str]]) -> str | None:
    """If our last reply was a clarifying question, return the user request that prompted it."""
    if len(history) >= 2 and history[-1].get("role") == "assistant" and history[-2].get("role") == "user":
        if (history[-1].get("content") or "").startswith(_CLARIFY_PREFIX):
            return history[-2].get("content") or None
    return None


def _normalize_query(q: str | None) -> str:
    return _NON_WORD_RE.sub(" ", (q or "").lower()).strip()


def _summarize_observations(state: AgentState, max_tool_calls: int, relevance_threshold: float) -> str:
    """Compact, token-cheap view of what the tools returned, for the Reflector."""
    profile = CitizenProfile.model_validate(state.get("citizen_profile") or {}).non_empty_dict()
    profile.pop("preferred_language", None)
    cards = {c.get("scheme_slug"): c for c in state.get("eligibility_cards") or []}

    schemes: dict[str, dict[str, Any]] = {}
    for ch in state.get("retrieved_chunks") or []:
        slug = ch.get("scheme_slug")
        if not slug:
            continue
        score = float((ch.get("scores") or {}).get("rerank") or 0.0)
        if slug not in schemes or score > schemes[slug]["score"]:
            schemes[slug] = {"name": ch.get("scheme_name"), "score": score}

    lines = []
    for slug, info in list(schemes.items())[:_MAX_SCHEMES_IN_OBSERVATION]:
        card = cards.get(slug)
        verdict = card.get("verdict") if card else "not checked"
        note = ""
        if card and card.get("unmet_criteria"):
            note = f" ({card['unmet_criteria'][0][:90]})"
        elif card and card.get("clarifying_questions"):
            note = f" (needs: {card['clarifying_questions'][0][:90]})"
        lines.append(f"- {slug} | {info['name']} | relevance {info['score']:.2f} | {verdict}{note}")

    used = len(state.get("tool_calls_log") or [])
    intent = (state.get("planner_output") or {}).get("intent", "SCHEME_QA")
    # Spell out what the relevance score means (TRC-6232CFB779: the model ignored a raw "0.05").
    best = max((s["score"] for s in schemes.values()), default=0.0)
    if not schemes:
        relevance_line = "Search relevance: NONE - nothing found.\n"
    elif best < relevance_threshold:
        relevance_line = (
            f"Search relevance: LOW (best {best:.2f}, below {relevance_threshold:.2f}) - these results are probably "
            "off-topic; prefer search_again with the citizen's real need and profile words.\n"
        )
    else:
        relevance_line = f"Search relevance: GOOD (best {best:.2f}).\n"
    missing = [label for key, label in _KEY_PROFILE_FACTS.items() if key not in profile]
    missing_line = (
        f"Key profile facts missing: {', '.join(missing)}\n" if intent == "ELIGIBILITY_CHECK" and missing else ""
    )
    return (
        f"Citizen Question: {state.get('query_en', '')}\n"
        f"Intent: {intent}\n"
        f"Citizen Profile: {json.dumps(profile, ensure_ascii=False) if profile else '(empty - nothing known)'}\n"
        f"{missing_line}"
        f"Queries Already Tried: {json.dumps(state.get('searched_queries') or [], ensure_ascii=False)}\n"
        f"Schemes Found (slug | name | relevance 0-1 | eligibility verdict):\n"
        + ("\n".join(lines) if lines else "- (none)")
        + f"\n{relevance_line}"
        f"Official web results: {len(state.get('web_results') or [])}\n"
        f"Tool calls left: {max(0, max_tool_calls - used)}\n"
        "Output ONLY the Reflector JSON."
    )


def _validate_reflection(
    decision: ReflectionOutput, state: AgentState, max_tool_calls: int
) -> tuple[ReflectionOutput, str | None]:
    """Loop guards: turn an unsafe or pointless Reflector decision into 'answer'. Returns (decision, guard)."""

    def answer(guard: str) -> tuple[ReflectionOutput, str]:
        return ReflectionOutput(decision="answer", reason=decision.reason), guard

    budget = max_tool_calls - len(state.get("tool_calls_log") or [])
    if decision.decision in ("search_again", "check_eligibility") and budget <= 0:
        return answer("tool_call_budget_exhausted")

    if decision.decision == "search_again":
        new_q = _normalize_query(decision.new_query)
        tried = {_normalize_query(q) for q in state.get("searched_queries") or []}
        if len(new_q) < 3 or new_q in tried:
            return answer("repeated_or_empty_query")  # infinite-loop guard
        return decision, None

    if decision.decision == "check_eligibility":
        found = {c.get("scheme_slug") for c in state.get("retrieved_chunks") or []}
        checked = {c.get("scheme_slug") for c in state.get("eligibility_cards") or []}
        slugs = [s for s in dict.fromkeys(decision.scheme_slugs) if s in found and s not in checked]
        slugs = slugs[: min(_MAX_RECHECK_SLUGS, budget)]
        if not slugs:
            return answer("no_valid_unchecked_slugs")  # blocks invented or repeated slugs
        return decision.model_copy(update={"scheme_slugs": slugs}), None

    if decision.decision == "ask_user" and not (decision.question or "").strip():
        return answer("empty_clarifying_question")

    if decision.decision == "ask_user" and not _FIRST_PERSON_RE.search(state.get("query_en") or ""):
        return answer("general_question_not_about_citizen")  # gold eval GQA-031: asked age for a rule question

    return decision, None


def _chunk_key(chunk: dict[str, Any]) -> str:
    return chunk.get("chunk_id") or chunk["citation_id"]


def _lead_scheme_first(results: list[dict[str, Any]], scheme_sections: list[dict[str, Any]],
                       evidence_cap: int) -> list[dict[str, Any]]:
    """Evidence for a question about one named scheme: its retrieved chunks, then the rest of its official
    sections, then other schemes' results in `_RESERVED_OTHER_SCHEME_SLOTS` slots (for comparison questions)."""
    lead = results[0]["scheme_slug"]
    lead_chunks = list({_chunk_key(c): c for c in [*(c for c in results if c["scheme_slug"] == lead),
                                                     *scheme_sections]}.values())
    lead_chunks = lead_chunks[: max(1, evidence_cap - _RESERVED_OTHER_SCHEME_SLOTS)]
    return [*lead_chunks, *(c for c in results if c["scheme_slug"] != lead)]


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


def _drop_ruled_out_schemes(
    chunks: list[dict[str, Any]], cards: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[str]]:
    """In a multi-scheme answer, remove evidence for NOT_ELIGIBLE schemes. Returns (kept_chunks, ruled_out_names).

    Single-scheme checks ("Am I eligible for PM-KISAN?") are untouched: there a NOT_ELIGIBLE verdict IS the answer.
    """
    if len(cards) < 2 or all(c.get("verdict") == "NOT_ELIGIBLE" for c in cards):
        return chunks, []
    ruled_out = {c.get("scheme_slug"): c.get("scheme_name") for c in cards if c.get("verdict") == "NOT_ELIGIBLE"}
    kept = [c for c in chunks if c.get("scheme_slug") not in ruled_out]
    return kept, [n for n in ruled_out.values() if n]


_STATUS_RE = re.compile(
    r"\b(?:likely eligible|partially eligible|not eligible|more details needed|needs more info|eligible)\b", re.I
)
# Writers often shorten long scheme names, so a name may also match on a leading prefix of at least this
# many characters, but only a prefix no other candidate name shares. (TRC-1BAB107B93: "Centrally Sponsored
# Scheme of Pre-matric ..." and "... of Post-Matric ..." share 30 characters, causing a false critic flag.)
_MIN_NAME_PREFIX_LEN = 30


def _distinctive_prefixes(names: list[str]) -> dict[str, str | None]:
    """Shortest word-prefix (>= _MIN_NAME_PREFIX_LEN chars) unique to each name, or None if there is none."""
    lowered = {n: n.lower() for n in names}
    out: dict[str, str | None] = {}
    for name, low in lowered.items():
        words, prefix = low.split(), None
        for k in range(1, len(words)):
            cand = " ".join(words[:k])
            if len(cand) >= _MIN_NAME_PREFIX_LEN and not any(
                other != name and o.startswith(cand) for other, o in lowered.items()
            ):
                prefix = cand
                break
        out[name] = prefix
    return out


def _name_in_line(name: str, prefix: str | None, line_low: str) -> bool:
    return name.lower() in line_low or (prefix is not None and prefix in line_low)


def _verdict_consistency_issues(
    answer: str, cards: list[dict[str, Any]], chunks: list[dict[str, Any]]
) -> list[str]:
    """Flag eligibility statuses given to unchecked schemes, and ruled-out schemes shown as options."""
    if not cards:
        return []
    verdicts = {(c.get("scheme_name") or "").lower(): c.get("verdict") for c in cards if c.get("scheme_name")}
    multi = len(cards) > 1 and any(v != "NOT_ELIGIBLE" for v in verdicts.values())
    names = sorted(
        {c.get("scheme_name") for c in [*chunks, *cards] if c.get("scheme_name")}, key=len, reverse=True
    )
    prefixes = _distinctive_prefixes(names)
    issues: list[str] = []
    for line in answer.splitlines():
        if not _STATUS_RE.search(line):
            continue
        line_low = line.lower()
        for name in names:
            if not _name_in_line(name, prefixes[name], line_low):
                continue
            verdict = verdicts.get(name.lower())
            if verdict is None:
                issues.append(
                    f"Draft gives an eligibility status to '{name}', which was NOT checked; "
                    "remove the status or drop that scheme."
                )
            elif multi and verdict == "NOT_ELIGIBLE":
                issues.append(f"Draft lists '{name}', which the eligibility check ruled NOT_ELIGIBLE; remove it.")
            break  # one scheme per line
    return list(dict.fromkeys(issues))


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

    # 2c. Eligibility statuses must come from the eligibility tool, never invented by the writer
    issues.extend(_verdict_consistency_issues(answer, state.get("eligibility_cards") or [], chunks))

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
    """Compiled LangGraph agent: Planner -> (Executor <-> Reflector, max 10 tool calls) -> Synthesizer -> Critic."""

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

        # Deterministic fast-track 3: only an ID / number, no request -> ask what they need (no tools, no guessing)
        if _is_bare_identifier(state.get("user_message_masked") or query_en):
            plan = PlannerOutput(intent="CONVERSATION_HELP", tool_calls=[], reasoning="Bare ID/number with no request.")
            step_lat = dict(state.get("step_latencies") or {})
            step_lat["planner_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)
            spans = self._append_span(
                state,
                name="Planner (Fast-Track: bare ID -> clarify)",
                span_type="GUARDRAIL",
                t_start=t0,
                inp={"query_en": query_en},
                out=plan.model_dump(),
            )
            return {
                "planner_output": plan.model_dump(),
                "clarifying_question": _BARE_ID_QUESTION,
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

        # Multi-turn continuation: the citizen answered our clarifying question, so the turn works on the
        # ORIGINAL request (with the new profile facts). Accepted only if that request is really in history.
        history = state.get("history") or []
        task_query = _verified_continuation(parsed.continues_request, history)
        if not task_query and parsed.profile_updates:
            # Small models often leave continues_request empty: fall back to our own last clarifying question.
            task_query = _request_before_our_question(history)
        if task_query:
            query_en = task_query
        else:
            parsed.continues_request = None

        # Gold eval GQA-045: a question that names a catalog scheme was refused as OUT_OF_SCOPE ("email address").
        scope_guard = None
        if parsed.intent == "OUT_OF_SCOPE" and get_catalog_vocabulary(self.repo).mentions_specific_scheme(query_en):
            parsed.intent, scope_guard = "SCHEME_QA", "named_catalog_scheme_is_in_scope"

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
        planner_dict["guard"] = scope_guard

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

        out = {
            "planner_output": planner_dict,
            "citizen_profile": merged_profile.model_dump(),
            "prompt_tokens": p_toks,
            "completion_tokens": c_toks,
            "step_latencies": step_lat,
            "spans": spans,
        }
        if task_query:
            out["query_en"] = task_query  # later nodes answer the original request
        return out

    # ---- Node 4: Executor (runs planned Pydantic tools + automatic web fallback / eligibility check) ----
    async def _node_executor(self, state: AgentState) -> dict[str, Any]:
        t0 = time.perf_counter()
        plan = state.get("planner_output") or {}
        intent = plan.get("intent", "SCHEME_QA")
        # Results accumulate across loop rounds (planner round 0, then Reflector-requested rounds).
        round_no = int(state.get("reflection_round") or 0)
        tool_calls = (state.get("pending_tool_calls") if round_no else plan.get("tool_calls")) or []
        profile_dict = state.get("citizen_profile") or {}
        query_en = state.get("query_en") or ""

        settings = get_settings()
        tool_logs: list[dict[str, Any]] = list(state.get("tool_calls_log") or [])
        logs_before = len(tool_logs)
        retrieved_chunks: list[dict[str, Any]] = list(state.get("retrieved_chunks") or [])
        web_results: list[dict[str, Any]] = list(state.get("web_results") or [])
        eligibility_cards: list[dict[str, Any]] = list(state.get("eligibility_cards") or [])
        searched_queries: list[str] = list(state.get("searched_queries") or [])
        grievance_draft: dict[str, Any] | None = None
        grievance_receipt: dict[str, Any] | None = None
        active_slugs: list[str] = list(state.get("active_scheme_slugs") or [])
        low_confidence = False
        # Broad "which schemes am I eligible for?" -> search with the profile and check several schemes.
        # Only on round 0: later search queries are chosen by the Reflector itself.
        vocab = get_catalog_vocabulary(self.repo)
        broad_eligibility = intent == "ELIGIBILITY_CHECK" and _is_broad_eligibility_query(query_en, vocab)
        apply_profile_query = broad_eligibility and round_no == 0
        # Open-ended eligibility need ("I need money for my studies"): keep the citizen's words, add who they are.
        # (TRC-6232CFB779: the bare need text scored 0.05 relevance and missed PM-USP / PM-YASASVI.)
        open_ended_eligibility = intent == "ELIGIBILITY_CHECK" and not vocab.mentions_specific_scheme(query_en)
        apply_need_query = open_ended_eligibility and not broad_eligibility and round_no == 0
        named_scheme_question = intent in _REFLECTIVE_INTENTS and vocab.mentions_specific_scheme(query_en)

        def budget_left() -> int:
            return settings.agent_max_tool_calls - len(tool_logs)

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
            if budget_left() <= 0:
                tool_logs.append({"tool": tname, "args": raw_args, "status": "skipped_step_budget"})
                continue
            await self._emit("tool_call", {"tool": tname, "status": friendly_tool_msg.get(str(tname), "Looking up details...")})

            try:
                if tname == "search_schemes":
                    raw_args.setdefault("query", query_en)
                    if apply_profile_query:
                        profile_query, profile_group = vocab.build_discovery_query(
                            CitizenProfile.model_validate(profile_dict)
                        )
                        raw_args["query"] = profile_query
                        raw_args["top_k"] = 8
                        if profile_group and not raw_args.get("beneficiary_group"):
                            raw_args["beneficiary_group"] = profile_group
                    elif apply_need_query:
                        raw_args["query"] = vocab.build_need_query(
                            raw_args["query"], CitizenProfile.model_validate(profile_dict)
                        )
                    inp = SearchSchemesInput.model_validate(raw_args)
                    # Profile filters (age, income, category) narrow DISCOVERY searches. A question about one named
                    # scheme must reach that scheme even if the citizen does not qualify, so the eligibility check can
                    # say so (task eval ELIG-01: age 60 filtered out PMKVY-RPL, ages 18-45, and no verdict was given).
                    search_profile = {} if named_scheme_question else profile_dict
                    res = await self.toolbox.search_schemes(inp, citizen_profile=search_profile)
                    searched_queries.append(inp.query)
                    # Newer results first; keep earlier evidence the agent may still cite (deduped, capped).
                    # Keyed by chunk_id: a section split into several chunks shares one citation_id, and keying by
                    # it silently dropped every part after the first (gold eval: "how to apply" answers missing).
                    new_chunks = res["results"]
                    if new_chunks and round_no == 0 and named_scheme_question and not settings.retrieval_top_k_override:
                        sections = self.toolbox.retriever.scheme_section_chunks(new_chunks[0]["scheme_slug"], query_en)
                        new_chunks = _lead_scheme_first(new_chunks, sections, _MAX_EVIDENCE_CHUNKS)
                    merged = {_chunk_key(c): c for c in [*new_chunks, *(retrieved_chunks if round_no else [])]}
                    # With a top-k override (evals) the answer sees at most k chunks in total, across all rounds.
                    evidence_cap = settings.retrieval_top_k_override or _MAX_EVIDENCE_CHUNKS
                    retrieved_chunks = list(merged.values())[:evidence_cap]
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
        checked = {c.get("scheme_slug") for c in eligibility_cards}
        new_cards_this_round = len(eligibility_cards) > len(state.get("eligibility_cards") or [])
        if intent == "ELIGIBILITY_CHECK" and not new_cards_this_round and retrieved_chunks:
            distinct_slugs = [
                s for s in dict.fromkeys(c["scheme_slug"] for c in retrieved_chunks if c.get("scheme_slug"))
                if s not in checked
            ]
            limit = _BROAD_ELIGIBILITY_MAX_SCHEMES if (broad_eligibility or open_ended_eligibility) else 1
            for slug in distinct_slugs[: max(0, min(limit, budget_left()))]:
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
        if low_confidence and not web_results and intent in ("SCHEME_QA", "ELIGIBILITY_CHECK") and budget_left() > 0:
            await self._emit("tool_call", {"tool": "web_search_gov_schemes", "status": "Searching official .gov.in portals..."})
            # Same (profile-enriched) query the local search just used, not the bare message (TRC-1BAB107B93).
            web_query = searched_queries[-1] if searched_queries else query_en
            web_res = await self.toolbox.web_search_gov_schemes(WebSearchGovInput(query=web_query, max_results=4))
            web_results.extend(web_res.get("results") or [])
            tool_logs.append({
                "tool": "web_search_gov_schemes",
                "args": {"query": web_query, "auto_fallback": True},
                "status": "ok" if not web_res.get("error") else "degraded",
                "provider": web_res.get("provider"),
                "result_count": len(web_res.get("results") or []),
                "error": web_res.get("error"),
            })

        hitl_paused = grievance_draft is not None
        citations = _extract_citations(retrieved_chunks, web_results)

        lat = round((time.perf_counter() - t0) * 1000.0, 2)
        step_lat = dict(state.get("step_latencies") or {})
        round_logs = tool_logs[logs_before:]
        n_calls = len(round_logs)
        spans = self._append_span(
            state,
            name=f"Executor (round {round_no + 1}, {n_calls} tool call{'s' if n_calls != 1 else ''})",
            span_type="RETRIEVAL" if retrieved_chunks else "TOOL",
            t_start=t0,
            status="error" if any(t.get("status") == "error" for t in round_logs) else "ok",
            inp={"planned_tools": [tc.get("tool_name") for tc in tool_calls], "round": round_no + 1},
            out={
                "tool_calls": round_logs,
                "total_tool_calls_so_far": len(tool_logs),
                "retrieved_count": len(retrieved_chunks),
                "web_results_count": len(web_results),
                "eligibility_cards_count": len(eligibility_cards),
                "hitl_paused": hitl_paused,
            },
        )

        step_lat["executor_ms"] = round(float((state.get("step_latencies") or {}).get("executor_ms", 0.0)) + lat, 2)
        return {
            "tool_calls_log": tool_logs,
            "searched_queries": searched_queries,
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

    # ---- Node 4b: Reflector (observe tool results -> decide the next step; bounded loop) ----
    async def _node_reflector(self, state: AgentState) -> dict[str, Any]:
        t0 = time.perf_counter()
        settings = get_settings()
        round_no = int(state.get("reflection_round") or 0)
        intent = (state.get("planner_output") or {}).get("intent", "SCHEME_QA")
        tokens_used = int(state.get("prompt_tokens", 0)) + int(state.get("completion_tokens", 0))

        # Loop guards that end the loop without spending an LLM call
        stop_reason: str | None = None
        if not settings.agent_reflection_enabled:
            stop_reason = "reflection_disabled"
        elif intent not in _REFLECTIVE_INTENTS:
            stop_reason = f"not_needed_for_{intent.lower()}"
        elif round_no >= settings.agent_max_reflection_rounds:
            stop_reason = "max_reflection_rounds_reached"
        elif len(state.get("tool_calls_log") or []) >= settings.agent_max_tool_calls:
            stop_reason = "tool_call_budget_exhausted"
        elif tokens_used >= settings.agent_token_budget:
            stop_reason = "token_budget_exhausted"

        decision = ReflectionOutput(decision="answer", reason=stop_reason or "")
        guard: str | None = stop_reason
        pt = ct = 0
        llm_used = False
        if stop_reason is None:
            await self._emit("reflect", {"status": "Checking whether these results really answer your question..."})
            try:
                resp = await self.llm.chat_completion(
                    messages=[
                        {"role": "system", "content": REFLECTOR_SYSTEM_PROMPT},
                        {"role": "user", "content": _summarize_observations(
                            state, settings.agent_max_tool_calls, settings.web_fallback_threshold
                        )},
                    ],
                    max_tokens=160,
                    temperature=0.0,
                    disable_thinking=True,
                )
                pt, ct, llm_used = resp.prompt_tokens, resp.completion_tokens, True
                parsed, _ = await parse_and_repair_json(resp.content, ReflectionOutput, llm=self.llm, allow_llm_repair=False)
                if parsed is not None:
                    decision = parsed
                else:
                    guard = "unparseable_reflection_json"
            except Exception as exc:  # tool/LLM failure must never break the turn
                logger.warning("Reflector failed (%s); answering with current evidence.", exc)
                guard = "reflector_error"
            if guard is None:
                decision, guard = _validate_reflection(decision, state, settings.agent_max_tool_calls)

        next_calls: list[dict[str, Any]] = []
        if decision.decision == "search_again":
            next_calls = [{"tool_name": "search_schemes", "arguments": {"query": decision.new_query, "top_k": 6}}]
        elif decision.decision == "check_eligibility":
            next_calls = [{"tool_name": "check_eligibility", "arguments": {"scheme_slug": s}} for s in decision.scheme_slugs]

        record = {"round": round_no + 1, **decision.model_dump(), "guard": guard, "llm_used": llm_used}
        reflections = [*(state.get("reflections") or []), record]

        lat = round((time.perf_counter() - t0) * 1000.0, 2)
        step_lat = dict(state.get("step_latencies") or {})
        step_lat["reflector_ms"] = round(step_lat.get("reflector_ms", 0.0) + lat, 2)
        spans = self._append_span(
            state,
            name=f"Reflector (round {round_no + 1}: {decision.decision})",
            span_type="LLM" if llm_used else "GUARDRAIL",
            t_start=t0,
            inp={"round": round_no + 1, "tool_calls_so_far": len(state.get("tool_calls_log") or []), "tokens_so_far": tokens_used},
            out=record,
            prompt_tokens=pt,
            completion_tokens=ct,
        )
        out: dict[str, Any] = {
            "reflections": reflections,
            "prompt_tokens": int(state.get("prompt_tokens", 0)) + pt,
            "completion_tokens": int(state.get("completion_tokens", 0)) + ct,
            "step_latencies": step_lat,
            "spans": spans,
        }
        if next_calls:
            out["pending_tool_calls"] = next_calls
            out["reflection_round"] = round_no + 1
        if decision.decision == "ask_user":
            out["clarifying_question"] = decision.question
        return out

    # ---- Node 4c: Ask the citizen a clarifying question (ends the turn; answer arrives next turn) ----
    async def _node_ask_user(self, state: AgentState) -> dict[str, Any]:
        question = (state.get("clarifying_question") or "").strip()
        return {
            "draft_answer_en": f"{_CLARIFY_PREFIX}\n\n**{question}**",
            "critic_output": {"passed": True, "issues": [], "needs_revision": False, "mode": "clarification"},
            "status": "awaiting_user_input",
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
            # Schemes the eligibility check ruled out never reach the writer (TRC-6232CFB779 listed them anyway).
            chunks, ruled_out = _drop_ruled_out_schemes(chunks, elig_cards)
            if ruled_out:
                elig_cards = [c for c in elig_cards if c.get("verdict") != "NOT_ELIGIBLE"]
            evidence, ev_flags = _build_evidence_block(chunks, web_results)
            flags.extend(ev_flags)

            extra_blocks: list[str] = []
            if ruled_out:
                extra_blocks.append(
                    "Ruled out by the eligibility check (do NOT mention these): " + "; ".join(ruled_out)
                )
            if len(elig_cards) > 1 or ruled_out:
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
                    "- Give an eligibility status ONLY to schemes listed in the Eligibility Tool Output above. Any other "
                    "scheme from the evidence may be mentioned WITHOUT a status, or skipped.\n"
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

        out: dict[str, Any] = {
            "draft_answer_en": resp.content,
            "guardrail_flags": list(dict.fromkeys(flags)),
            "prompt_tokens": state.get("prompt_tokens", 0) + resp.prompt_tokens,
            "completion_tokens": state.get("completion_tokens", 0) + resp.completion_tokens,
            "step_latencies": step_lat,
            "spans": spans,
        }
        if len(chunks) != len(state.get("retrieved_chunks") or []):
            # Keep [n] numbering consistent for the critic and the UI citation list after filtering.
            out["retrieved_chunks"] = chunks
            out["citations"] = _extract_citations(chunks, web_results)
        return out

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
        if state.get("clarifying_question"):
            return "ask_user"
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
        return "hitl_pause" if state.get("hitl_paused") else "reflect"

    @staticmethod
    def _route_after_reflector(state: AgentState) -> str:
        last = (state.get("reflections") or [{}])[-1]
        decision = last.get("decision")
        if decision == "ask_user":
            return "ask_user"
        if decision in ("search_again", "check_eligibility"):
            return "continue"
        return "synthesize"

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
        sg.add_node("reflector", self._node_reflector)
        sg.add_node("ask_user", self._node_ask_user)
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
                "ask_user": "ask_user",
                "execute": "executor",
            },
        )
        sg.add_edge("conversation_help", "output_localizer")
        sg.add_edge("out_of_scope", "output_localizer")
        sg.add_conditional_edges(
            "executor",
            self._route_after_executor,
            {"hitl_pause": "hitl_pause", "reflect": "reflector"},
        )
        # The agent loop: Reflector observes results and may send the Executor back out (bounded).
        sg.add_conditional_edges(
            "reflector",
            self._route_after_reflector,
            {"continue": "executor", "ask_user": "ask_user", "synthesize": "synthesizer"},
        )
        sg.add_edge("ask_user", "output_localizer")
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
            "reflection_round": 0,
            "reflections": [],
            "searched_queries": [],
            "pending_tool_calls": [],
            "clarifying_question": None,
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
