"""5 Strictly Typed Pydantic Agent Tools + Automatic JSON Extraction & 1-Shot Pydantic Repair Utility."""

from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any, Literal, TypeVar

from pydantic import BaseModel, Field, ValidationError

from backend.agent.prompts import JSON_REPAIR_SYSTEM_PROMPT
from backend.agent.state import CitizenProfile
from backend.db.repositories import Repository
from backend.gateway.llm_client import LLMGateway, get_llm_gateway, strip_thinking
from backend.guardrails.pii import mask_pii
from backend.retrieval.hybrid_retriever import HybridRetriever, get_hybrid_retriever
from backend.retrieval.web_search import search_gov_web
from backend.services.grievance_provider import PGPORTAL_URL, GrievanceProvider, get_grievance_provider

logger = logging.getLogger(__name__)

TModel = TypeVar("TModel", bound=BaseModel)
CPGRAMS_MAX_CHARS = 2000


# ==============================================================================
# Automatic JSON Extraction & 1-Shot Pydantic JSON Repair Utility
# ==============================================================================

def extract_json_candidate(raw_text: str) -> str:
    """Strip <think> blocks, markdown fences, and extract outermost JSON object."""
    cleaned = strip_thinking(raw_text or "").strip()
    # Strip ```json ... ``` fences
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned, re.IGNORECASE)
    if fence_match:
        cleaned = fence_match.group(1).strip()
    # If already starts with {, try as-is; else extract outermost {...}
    if not cleaned.startswith("{"):
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            cleaned = cleaned[start : end + 1]
    return cleaned


async def parse_and_repair_json(
    raw_text: str,
    model_cls: type[TModel],
    llm: LLMGateway | None = None,
    allow_llm_repair: bool = True,
) -> tuple[TModel | None, dict[str, Any]]:
    """Parse raw LLM JSON into `model_cls`, with deterministic cleanup + 1-shot LLM schema repair.

    Returns (parsed_model_or_none, diagnostics_dict).
    """
    diag: dict[str, Any] = {
        "initial_valid": False,
        "repaired": False,
        "repair_method": None,
        "error": None,
        "repair_tokens": 0,
    }
    candidate = extract_json_candidate(raw_text)

    # Attempt 1: direct JSON + Pydantic validation
    try:
        data = json.loads(candidate)
        parsed = model_cls.model_validate(data)
        diag["initial_valid"] = True
        return parsed, diag
    except (json.JSONDecodeError, ValidationError) as err1:
        # Attempt 2: deterministic trailing-comma / single-quote quick fix
        fixed_str = re.sub(r",\s*([}\]])", r"\1", candidate)
        try:
            data = json.loads(fixed_str)
            parsed = model_cls.model_validate(data)
            diag["repaired"] = True
            diag["repair_method"] = "deterministic_regex"
            return parsed, diag
        except (json.JSONDecodeError, ValidationError) as err2:
            diag["error"] = str(err2)[:400]

    # Attempt 3: 1-shot LLM JSON Repair via Qwen3-8B
    if allow_llm_repair:
        try:
            gateway = llm or get_llm_gateway()
            compact_fields = list(model_cls.model_fields.keys())
            resp = await gateway.chat_completion(
                messages=[
                    {"role": "system", "content": JSON_REPAIR_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            f"Model: {model_cls.__name__} | Required top-level keys: {compact_fields}\n"
                            f"Validation Error:\n{diag['error']}\n\n"
                            f"Broken Output:\n{raw_text[:1200]}\n\n"
                            "Keep reasoning concise (<15 words) and return ONLY the corrected valid JSON object."
                        ),
                    },
                ],
                max_tokens=512,
                temperature=0.0,
                disable_thinking=True,
            )
            diag["repair_tokens"] = resp.prompt_tokens + resp.completion_tokens
            repaired_candidate = extract_json_candidate(resp.content)
            data = json.loads(repaired_candidate)
            parsed = model_cls.model_validate(data)
            diag["repaired"] = True
            diag["repair_method"] = "llm_1shot_repair"
            diag["error"] = None
            return parsed, diag
        except Exception as repair_exc:
            diag["error"] = f"Repair failed: {str(repair_exc)[:300]}"
            logger.warning("1-shot JSON repair failed for %s: %s", model_cls.__name__, repair_exc)

    return None, diag


# ==============================================================================
# Tool Input Pydantic Schemas
# ==============================================================================

class SearchSchemesInput(BaseModel):
    query: str = Field(..., min_length=2)
    category: str | None = None
    ministry: str | None = None
    dbt_only: bool | None = None
    beneficiary_group: str | None = None
    top_k: int = Field(default=6, ge=1, le=8)


class CheckEligibilityInput(BaseModel):
    scheme_slug: str = Field(..., min_length=1)
    citizen_profile: CitizenProfile = Field(default_factory=CitizenProfile)


class WebSearchGovInput(BaseModel):
    query: str = Field(..., min_length=2)
    max_results: int = Field(default=4, ge=1, le=5)


class DraftGrievanceInput(BaseModel):
    scheme_name: str = Field(..., min_length=2)
    ministry: str = Field(default="")
    issue_summary: str = Field(..., min_length=5)
    beneficiary_reference_id: str | None = None
    state: str | None = None
    district: str | None = None
    pending_since: str | None = None
    scheme_slug: str | None = None
    session_id: str = ""


class SubmitOrTrackGrievanceInput(BaseModel):
    action: Literal["submit", "track"]
    draft_id: str | None = None
    user_confirmed: bool = False
    registration_number: str | None = None
    simulate_fault: str | None = None


# ==============================================================================
# Tool Implementations
# ==============================================================================

def _parse_documents_list(docs_text: str) -> list[str]:
    if not docs_text:
        return []
    raw_lines = re.split(r"\n+|(?<=\.)\s+(?=\d+\.)|;", docs_text)
    items: list[str] = []
    for ln in raw_lines:
        clean = re.sub(r"^\s*(?:[-•*]|\d+[\.\)])\s*", "", ln).strip()
        if 3 <= len(clean) <= 180:
            items.append(clean)
    # Deduplicate preserving order
    return list(dict.fromkeys(items))[:12]


def _extract_exclusion_bullets(exclusions_text: str) -> list[str]:
    if not exclusions_text:
        return []
    parts = re.split(r"\n+|(?<=[.;])\s+", exclusions_text)
    bullets: list[str] = []
    for p in parts:
        clean = re.sub(r"^\s*(?:[-•*]|\d+[\.\)]|[a-z][\.\)])\s*", "", p).strip()
        if len(clean) >= 12:
            bullets.append(clean[:220])
    return bullets[:6]


class AgentToolbox:
    """Executes all 5 typed tools with clean dependency injection for testing and evaluation."""

    def __init__(
        self,
        retriever: HybridRetriever | None = None,
        repo: Repository | None = None,
        grievance_provider: GrievanceProvider | None = None,
    ):
        self._retriever = retriever
        self.repo = repo or Repository()
        self._grievance_provider = grievance_provider

    @property
    def retriever(self) -> HybridRetriever:
        if self._retriever is None:
            self._retriever = get_hybrid_retriever()
        return self._retriever

    @property
    def grievance_provider(self) -> GrievanceProvider:
        if self._grievance_provider is None:
            self._grievance_provider = get_grievance_provider(repo=self.repo)
        return self._grievance_provider

    # ---- Tool 1: search_schemes ----
    async def search_schemes(
        self,
        args: SearchSchemesInput,
        citizen_profile: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        filters: dict[str, Any] = {}
        if args.category:
            filters["category"] = args.category
        if args.ministry:
            filters["ministry"] = args.ministry
        if args.dbt_only is not None:
            filters["dbt_only"] = args.dbt_only
        if args.beneficiary_group:
            filters["beneficiary_group"] = args.beneficiary_group
        if citizen_profile:
            if citizen_profile.get("age") is not None:
                filters["age"] = citizen_profile["age"]
            if citizen_profile.get("annual_income_inr") is not None:
                filters["annual_income_inr"] = citizen_profile["annual_income_inr"]
            if citizen_profile.get("social_category"):
                filters["social_category"] = citizen_profile["social_category"]

        effective_top_k = max(5, min(int(args.top_k), 8))
        out = await self.retriever.search(
            query=args.query,
            top_k=effective_top_k,
            mode="hybrid_rerank",
            filters=filters or None,
        )
        # Safety net: if LLM-emitted metadata filter overly narrowed results (low rerank score),
        # retry unfiltered so the true flagship scheme is never filtered out by a guessed category string.
        if filters and out.top_rerank_score < 0.5:
            unfiltered = await self.retriever.search(
                query=args.query,
                top_k=effective_top_k,
                mode="hybrid_rerank",
                filters=None,
            )
            if unfiltered.top_rerank_score > out.top_rerank_score:
                out = unfiltered
        return {
            "results": [r.to_dict() for r in out.results],
            "top_rerank_score": out.top_rerank_score,
            "low_confidence": out.low_confidence,
            "latency_ms": out.latency_ms,
            "filter_applied": out.filter_applied,
            "filter_relaxed": out.filter_relaxed,
        }

    # ---- Tool 2: check_eligibility ----
    async def check_eligibility(self, args: CheckEligibilityInput) -> dict[str, Any]:
        scheme = self.repo.get_scheme(args.scheme_slug)
        if not scheme:
            # Attempt fallback lookup by name substring
            matches, _ = self.repo.list_schemes(q=args.scheme_slug, limit=1)
            if matches:
                scheme = self.repo.get_scheme(matches[0]["slug"])
        if not scheme:
            return {
                "scheme_slug": args.scheme_slug,
                "scheme_name": args.scheme_slug,
                "verdict": "NEEDS_MORE_INFO",
                "matched_criteria": [],
                "exclusion_warnings": [],
                "missing_fields": ["scheme_identification"],
                "clarifying_questions": ["Could you confirm the exact Central Government scheme name?"],
                "documents_required": [],
                "source_url": "https://www.myscheme.gov.in/",
                "error": f"Scheme '{args.scheme_slug}' not found in local catalog.",
            }

        profile = args.citizen_profile
        matched: list[str] = []
        unmet: list[str] = []
        missing: list[str] = []
        questions: list[str] = []

        elig_low = (scheme.get("eligibility") or "").lower()
        excl_low = (scheme.get("exclusions") or "").lower()
        docs = _parse_documents_list(scheme.get("documents_required") or "")
        exclusions = _extract_exclusion_bullets(scheme.get("exclusions") or "")

        # 1. Age check
        a_min = scheme.get("age_min")
        a_max = scheme.get("age_max")
        if a_min is not None or a_max is not None:
            if profile.age is None:
                missing.append("age")
                questions.append("What is your current age (in years)?")
            else:
                if a_min is not None and profile.age < a_min:
                    unmet.append(f"Age {profile.age} is below the minimum required age of {a_min} years.")
                elif a_max is not None and profile.age > a_max:
                    unmet.append(f"Age {profile.age} exceeds the maximum age limit of {a_max} years.")
                else:
                    bounds = f"{a_min or 0}–{a_max or 'any'} years"
                    matched.append(f"Age ({profile.age} years) fits scheme age criteria ({bounds}).")

        # 2. Income cap check
        inc_cap = scheme.get("income_cap_inr")
        if inc_cap is not None:
            if profile.annual_income_inr is None:
                missing.append("annual_income_inr")
                questions.append(f"What is your annual family income in INR? (Scheme mentions an income ceiling around ₹{inc_cap:,}/year)")
            else:
                if profile.annual_income_inr > inc_cap:
                    unmet.append(
                        f"Annual family income (₹{profile.annual_income_inr:,}) exceeds the scheme ceiling (₹{inc_cap:,})."
                    )
                else:
                    matched.append(
                        f"Annual family income (₹{profile.annual_income_inr:,}) is within the ₹{inc_cap:,} ceiling."
                    )

        # 3. Social Category check
        scats: list[str] = scheme.get("social_categories") or []
        restricted_scats = [s for s in scats if s in ("SC", "ST", "OBC", "EWS", "Minority", "PwD")]
        if restricted_scats and "General" not in scats:
            if profile.social_category:
                if profile.social_category.upper() in {s.upper() for s in restricted_scats}:
                    matched.append(f"Social category ({profile.social_category}) matches target categories ({', '.join(restricted_scats)}).")
                else:
                    unmet.append(
                        f"Scheme targets {', '.join(restricted_scats)} categories; your profile lists {profile.social_category}."
                    )
            else:
                missing.append("social_category")
                questions.append(f"Which social category do you belong to ({', '.join(restricted_scats)} / General)?")

        # 4. Gender check (women-specific schemes)
        women_only = (
            "Women" in scats
            and any(k in elig_low for k in ("only women", "female applicant", "girl child", "pregnant woman", "widow", "mahila"))
        )
        if women_only:
            if profile.gender:
                if profile.gender.lower() in ("female", "woman", "girl", "f"):
                    matched.append("Gender matches women/girl-child beneficiary requirement.")
                else:
                    unmet.append("This scheme is specifically targeted at women/girl-child beneficiaries.")
            else:
                missing.append("gender")
                questions.append("Is the beneficiary female/a woman or girl child?")

        # 5. Occupation / Beneficiary group match
        bgroups: list[str] = scheme.get("beneficiary_groups") or []
        if profile.occupation and bgroups:
            occ_low = profile.occupation.lower()
            if any(occ_low in b.lower() or b.lower() in occ_low for b in bgroups):
                matched.append(f"Occupation ({profile.occupation}) aligns with target group ({', '.join(bgroups[:4])}).")
            elif "farmer" in occ_low and "Farmer" in bgroups:
                matched.append("Farmer occupation matches target beneficiary.")
        elif bgroups and not profile.occupation:
            missing.append("occupation")
            questions.append("What is your primary occupation (e.g., Farmer, Student, Artisan, MSME, Worker)?")

        # 6. Explicit exclusion triggers (income tax payer, government employee, landholding)
        if "income tax" in excl_low:
            missing.append("income_tax_payer_status")
            questions.append("Did you or any family member pay Income Tax in the last assessment year?")
        if "government employee" in excl_low or "govt employee" in excl_low or "central/state government" in excl_low:
            missing.append("govt_employee_status")
            questions.append("Are you or an eligible family member a regular Central/State Government employee?")
        if "cultivable land" in elig_low or "landholding" in elig_low:
            missing.append("landholding_status")
            questions.append("Do you own cultivable land recorded in your family's name?")

        # Determine structured verdict
        if unmet:
            verdict = "NOT_ELIGIBLE"
        elif missing and not matched:
            verdict = "NEEDS_MORE_INFO"
        elif missing and matched:
            verdict = "NEEDS_MORE_INFO" if len(missing) >= 2 else "PARTIALLY_ELIGIBLE"
        else:
            verdict = "ELIGIBLE"

        return {
            "scheme_slug": scheme["slug"],
            "scheme_name": scheme["scheme_name"],
            "ministry": scheme["ministry"],
            "verdict": verdict,
            "matched_criteria": matched,
            "unmet_criteria": unmet,
            "exclusion_warnings": exclusions,
            "missing_fields": list(dict.fromkeys(missing)),
            "clarifying_questions": list(dict.fromkeys(questions))[:4],
            "documents_required": docs,
            "eligibility_excerpt": (scheme.get("eligibility") or "")[:600],
            "source_url": scheme["source_url"],
        }

    # ---- Tool 3: web_search_gov_schemes ----
    async def web_search_gov_schemes(self, args: WebSearchGovInput) -> dict[str, Any]:
        return await search_gov_web(query=args.query, max_results=args.max_results)

    # ---- Tool 4: draft_grievance ----
    async def draft_grievance(self, args: DraftGrievanceInput) -> dict[str, Any]:
        # Resolve canonical scheme and 51-Ministry mapping
        resolved_ministry = None
        scheme_slug = args.scheme_slug or ""
        scheme_name = args.scheme_name.strip()

        scheme_rec = self.repo.get_scheme(scheme_slug) if scheme_slug else None
        if not scheme_rec:
            matches, _ = self.repo.list_schemes(q=scheme_name, limit=1)
            if matches:
                scheme_rec = self.repo.get_scheme(matches[0]["slug"])
                scheme_slug = scheme_rec["slug"]
                scheme_name = scheme_rec["scheme_name"]

        if args.ministry:
            resolved_ministry = self.repo.resolve_ministry(args.ministry)
        if not resolved_ministry and scheme_rec:
            resolved_ministry = {
                "ministry_code": scheme_rec["ministry_code"],
                "ministry_name": scheme_rec["ministry"],
            }
        if not resolved_ministry:
            # Fallback to DARPG (Public Grievances) if unmapped
            resolved_ministry = self.repo.resolve_ministry("DARPG") or {
                "ministry_code": "DARPG",
                "ministry_name": "Ministry Of Personnel, Public Grievances And Pensions",
            }

        # Mask any PII before composing formal grievance text
        clean_issue = mask_pii(args.issue_summary).masked_text
        clean_ref = mask_pii(args.beneficiary_reference_id).masked_text if args.beneficiary_reference_id else None

        subject = f"Grievance regarding {scheme_name}"[:180]
        location_parts = [p for p in (args.district, args.state) if p]
        location_str = ", ".join(location_parts) if location_parts else "Not specified"

        lines = [
            f"To,\nThe Public Grievance Officer,\n{resolved_ministry['ministry_name']},\nGovernment of India.",
            "",
            f"Subject: {subject}",
            "",
            "Respected Sir/Madam,",
            "",
            f"I am writing to respectfully submit a grievance concerning the Central Government scheme \"{scheme_name}\".",
            f"Issue Details: {clean_issue}",
        ]
        if clean_ref:
            lines.append(f"Beneficiary / Application Reference ID: {clean_ref}")
        if args.pending_since:
            lines.append(f"Pending Since: {args.pending_since}")
        lines.append(f"Location (District / State): {location_str}")
        lines.extend(
            [
                "",
                "I kindly request your good office to examine my case, verify the status in the relevant DBT/scheme portal, "
                "and arrange for early resolution and disbursement/correction of my entitlement as per scheme guidelines.",
                "",
                "Thanking you,",
                "Yours faithfully,",
                "Applicant Citizen (Submitted via JanSahayak AI Assisted CPGRAMS Workflow)",
            ]
        )
        body = "\n".join(lines).strip()

        # Hard CPGRAMS <= 2,000 character enforcement
        if len(body) > CPGRAMS_MAX_CHARS:
            body = body[: CPGRAMS_MAX_CHARS - 3].rstrip() + "..."

        draft_id = f"DRAFT-{uuid.uuid4().hex[:6].upper()}"
        draft_record = {
            "draft_id": draft_id,
            "session_id": args.session_id,
            "scheme_slug": scheme_slug,
            "scheme_name": scheme_name,
            "ministry_code": resolved_ministry["ministry_code"],
            "ministry_name": resolved_ministry["ministry_name"],
            "subject": subject,
            "grievance_text": body,
            "char_count": len(body),
            "within_cpgrams_limit": len(body) <= CPGRAMS_MAX_CHARS,
            "requires_user_confirmation": True,
            "portal_handoff_url": PGPORTAL_URL,
            "beneficiary_reference_id": clean_ref,
            "state": args.state,
            "district": args.district,
            "pending_since": args.pending_since,
        }
        self.repo.save_grievance_draft(draft_record)
        return draft_record

    # ---- Tool 5: submit_or_track_grievance ----
    async def submit_or_track_grievance(self, args: SubmitOrTrackGrievanceInput) -> dict[str, Any]:
        if args.action == "track":
            if not args.registration_number:
                return {
                    "error": "registration_number is required for tracking a grievance.",
                    "found": False,
                }
            return await self.grievance_provider.track_grievance(
                args.registration_number,
                simulate_fault=args.simulate_fault,
            )

        # action == "submit": MANDATORY HITL ENFORCEMENT
        if not args.user_confirmed:
            return {
                "blocked": True,
                "error": "HITL_CONFIRMATION_REQUIRED: Grievance submission is strictly blocked until explicit user confirmation (user_confirmed=True).",
                "requires_user_confirmation": True,
            }
        if not args.draft_id:
            return {
                "blocked": True,
                "error": "draft_id is required to submit a confirmed grievance.",
            }
        draft = self.repo.get_grievance_by_draft_id(args.draft_id)
        if not draft:
            return {
                "blocked": True,
                "error": f"Grievance draft '{args.draft_id}' not found.",
            }
        return await self.grievance_provider.submit_grievance(
            draft=draft,
            simulate_fault=args.simulate_fault,
        )
