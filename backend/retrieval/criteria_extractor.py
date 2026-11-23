"""Offline extraction of structured eligibility criteria from a scheme's free-text rules.

The hosted LLM reads each scheme's eligibility/exclusion text ONCE and returns a validated
`EligibilityCriteria` checklist. At query time, plain code can compare a citizen profile
against this checklist instead of re-reading free text with hand-written patterns.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Literal

from pydantic import BaseModel, Field

from backend.agent.prompts import CRITERIA_EXTRACTION_SYSTEM_PROMPT, RESTRICTION_CHECK_SYSTEM_PROMPT
from backend.agent.tools import parse_and_repair_json
from backend.gateway.llm_client import LLMGateway

EducationStage = Literal["school", "class_11_12", "undergraduate", "postgraduate", "doctoral"]
# No "General": [] already means open to all. EBC / DNT appear in real schemes (e.g. PM-YASASVI for
# "OBC, EBC and DNT"); rejecting them made both PM-YASASVI extractions fail validation.
SocialCategory = Literal["SC", "ST", "OBC", "EWS", "Minority", "EBC", "DNT"]

# Per-field cap on scheme text sent to the model (keeps each call small; the longest catalog
# eligibility text seen in testing is ~2,400 chars).
_MAX_FIELD_CHARS = 3000
_MAX_OUTPUT_TOKENS = 450


class EligibilityCriteria(BaseModel):
    applicant_type: Literal["individual", "institution", "both", "unclear"] = "unclear"
    beneficiary_groups: list[str] = Field(default_factory=list)
    education_stages: list[EducationStage] = Field(default_factory=list)
    study_location: Literal["india", "abroad", "any"] = "any"
    required_institution: str | None = None
    required_states: list[str] = Field(default_factory=list)
    gender: Literal["any", "female", "male", "transgender"] = "any"
    age_min: int | None = Field(default=None, ge=0, le=120)
    age_max: int | None = Field(default=None, ge=0, le=120)
    income_max_inr: int | None = Field(default=None, ge=0)
    social_categories: list[SocialCategory] = Field(default_factory=list)
    requires_bpl: bool | None = None
    requires_disability: bool | None = None
    other_requirements: list[str] = Field(default_factory=list)
    exclusions: list[str] = Field(default_factory=list)
    unclear: list[str] = Field(default_factory=list)


# ---- Grounding: accept an extracted value only if the scheme's own text supports it ----
# (The 8B model kept calling "higher education outside the Union Territories" study "abroad".)
_MAX_OTHER_REQUIREMENTS = 3
_ABROAD_RE = re.compile(r"abroad|overseas|foreign (?:countr|universit|institut)|outside india", re.I)
_DISABILITY_RE = re.compile(r"disab|divyang|\bpwd\b|handicap|impairment", re.I)
_BPL_RE = re.compile(r"\bbpl\b|below (?:the )?poverty", re.I)
_CATEGORY_RE: dict[str, re.Pattern[str]] = {
    # abbreviations case-sensitive so "B.Sc" / "1st" are not read as SC / ST
    "SC": re.compile(r"\bSCs?\b|(?i:scheduled caste)"),
    "ST": re.compile(r"\bSTs?\b|(?i:scheduled tribe)"),
    "OBC": re.compile(r"\bOBCs?\b|other backward", re.I),
    "EWS": re.compile(r"\bEWS\b|economically weaker", re.I),
    "Minority": re.compile(r"minorit", re.I),
    "EBC": re.compile(r"\bEBCs?\b|(?i:economically backward)"),
    "DNT": re.compile(r"\bDNTs?\b|(?i:de-?notified)"),
}
# required_institution must be ONE named institution; a kind of institution ("AICTE approved institutions",
# "State Livestock Agencies") is a general requirement. 39 of 67 values in the full run were such types.
_INSTITUTION_TYPE_RE = re.compile(
    r"\b(?:institutions|institutes|universities|colleges|agencies|organi[sz]ations|bodies|centres|centers)\b"
    r"|\b(?:approved|recogni[sz]ed|notified|accredited|affiliated|any|eligible|registered)\b",
    re.I,
)
# "other_requirements" must be must-haves: drop things that are merely allowed ("eligible if ...",
# "eligible for correspondence courses") and restatements of the income ceiling (already in income_max_inr).
_PERMISSION_RE = re.compile(r"^\s*(?:also\s+)?(?:eligible|may|can|allowed)\b|\beligible (?:if|for|to)\b", re.I)
_INCOME_RESTATED_RE = re.compile(r"income.*(?:₹|rs\.?|lakh|\d{2},\d{3})|(?:₹|rs\.?).*income", re.I)
# A state list is kept only if the text names one of the states or a region the model could expand
# (dsctassgcsccm: "traditional coffee-growing states" became a list of 24 states, incl. Delhi and Ladakh).
_REGION_WORD_RE = re.compile(r"north[- ]?east|\bNER\b|\bregion\b|\bJ\s*&\s*K\b|union territor", re.I)
_AMOUNT_RE = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(lakhs?|lacs?|crores?)?", re.I)
_UNIT = {"lakh": 100_000, "lac": 100_000, "crore": 10_000_000}


def _amounts_in(text: str) -> set[int]:
    """Every rupee amount written in the text, e.g. 'Rs. 1.50 lakh' -> 150000, '2,50,000' -> 250000."""
    out: set[int] = set()
    for number, unit in _AMOUNT_RE.findall(text):
        try:
            value = float(number.replace(",", ""))
        except ValueError:
            continue
        unit_key = (unit or "").lower().rstrip("s")
        out.add(int(round(value * _UNIT.get(unit_key, 1))))
    return out


def ground_criteria(criteria: EligibilityCriteria, scheme: dict[str, Any]) -> tuple[EligibilityCriteria, list[str]]:
    """Drop or reset extracted values the source text does not support. Returns (criteria, corrections)."""
    source = " ".join(
        str(scheme.get(k) or "") for k in ("scheme_name", "brief_description", "eligibility", "exclusions")
    )
    c = criteria.model_copy(deep=True)
    fixes: list[str] = []

    if c.study_location == "abroad" and not _ABROAD_RE.search(source):
        c.study_location = "india" if c.education_stages else "any"
        fixes.append(f"study_location abroad -> {c.study_location} (text never mentions studying abroad)")
    if c.study_location != "any" and not c.education_stages:
        c.study_location = "any"  # not a study scheme
    if c.income_max_inr is not None and c.income_max_inr not in _amounts_in(source):
        fixes.append(f"income_max_inr {c.income_max_inr} -> null (amount not in text)")
        c.income_max_inr = None
        c.unclear.append("income_max_inr")
    source_low = source.lower().replace("&", " and ")
    if c.required_states and not _REGION_WORD_RE.search(source) and not any(
        s.lower().replace("&", " and ") in source_low for s in c.required_states
    ):
        fixes.append(f"required_states ({len(c.required_states)}) -> [] (no listed state or region named in text)")
        c.required_states = []
        c.unclear.append("required_states")
    if c.required_institution and c.required_institution.lower() not in source.lower():
        fixes.append(f"required_institution '{c.required_institution}' -> null (not in text)")
        c.required_institution = None
    elif c.required_institution and _INSTITUTION_TYPE_RE.search(c.required_institution):
        fixes.append(f"required_institution '{c.required_institution}' -> other_requirements (a type, not one institution)")
        c.other_requirements.insert(0, c.required_institution)
        c.required_institution = None
    for field in ("age_min", "age_max"):
        age = getattr(c, field)
        if age is not None and not re.search(rf"\b{age}\b", source):
            fixes.append(f"{field} {age} -> null (not in text)")
            setattr(c, field, None)
    unsupported = [cat for cat in c.social_categories if not _CATEGORY_RE[cat].search(source)]
    if unsupported:
        c.social_categories = [cat for cat in c.social_categories if cat not in unsupported]
        fixes.append(f"social_categories dropped {unsupported} (not in text)")
    if c.requires_disability and not _DISABILITY_RE.search(source):
        c.requires_disability = None
        fixes.append("requires_disability -> null (no disability wording)")
    if c.requires_bpl and not _BPL_RE.search(source):
        c.requires_bpl = None
        fixes.append("requires_bpl -> null (no BPL wording)")
    kept = [r for r in c.other_requirements if not _PERMISSION_RE.search(r) and not _INCOME_RESTATED_RE.search(r)]
    if len(kept) != len(c.other_requirements):
        fixes.append(f"other_requirements dropped {len(c.other_requirements) - len(kept)} permission/income restatement(s)")
    c.other_requirements = kept[:_MAX_OTHER_REQUIREMENTS]
    return c, fixes


def prompt_version() -> str:
    """Changes whenever either extraction prompt changes, so stored results can be re-extracted selectively."""
    prompts = CRITERIA_EXTRACTION_SYSTEM_PROMPT + RESTRICTION_CHECK_SYSTEM_PROMPT
    return hashlib.sha256(prompts.encode("utf-8")).hexdigest()[:12]


def _clip(text: str | None) -> str:
    return (text or "").strip()[:_MAX_FIELD_CHARS] or "(none)"


# ---- Verification: a second, narrow question for each value that could wrongly REJECT a citizen ----
# With one long prompt the 8B model still read "33 years for SC/ST/PH candidates" (jrfbio) and
# "SC/ST/OBC ... Teacher" in a list of eligible applicants (tgsctclvccmuo) as category-only schemes.
_MAX_CHECK_OUTPUT_TOKENS = 200
_QUOTE_NORMALIZE_RE = re.compile(r"[^a-z0-9]+")


class RestrictionCheck(BaseModel):
    holds_for_all_applicants: bool
    quote: str = ""
    highest_limit: int | None = Field(default=None, ge=0, le=120)


def _normalize_for_quote(text: str) -> str:
    return _QUOTE_NORMALIZE_RE.sub(" ", text.lower()).strip()


def quote_in_source(quote: str, source: str) -> bool:
    """True if the model's quote really appears in the scheme text (ignoring case, spacing and punctuation)."""
    q = _normalize_for_quote(quote)
    return bool(q) and q in _normalize_for_quote(source)


def restriction_claims(criteria: EligibilityCriteria) -> dict[str, str]:
    """{field: plain-language claim} for every extracted value that would rule citizens out."""
    claims: dict[str, str] = {}
    if criteria.social_categories:
        claims["social_categories"] = f"Only applicants from these categories can apply: {', '.join(criteria.social_categories)}."
    if criteria.requires_disability:
        claims["requires_disability"] = "Only persons with disabilities can apply."
    if criteria.age_max is not None:
        claims["age_max"] = f"No applicant, in any category, may be older than {criteria.age_max} years."
    return claims


def apply_restriction_checks(
    criteria: EligibilityCriteria, checks: dict[str, RestrictionCheck | None], source: str
) -> tuple[EligibilityCriteria, list[str]]:
    """Keep a restriction only if the model confirmed it with a quote that exists in the text."""
    c = criteria.model_copy(deep=True)
    fixes: list[str] = []
    for field, check in checks.items():
        if check is not None and check.holds_for_all_applicants and quote_in_source(check.quote, source):
            continue
        reason = "unparseable check" if check is None else (
            "not a restriction for all applicants" if not check.holds_for_all_applicants else "quote not in text")
        if field == "age_max":
            higher = check.highest_limit if check else None
            if higher is not None and c.age_max is not None and higher > c.age_max and re.search(rf"\b{higher}\b", source):
                fixes.append(f"age_max {c.age_max} -> {higher} (higher limit for some categories)")
                c.age_max = higher
                continue
            c.age_max = None
        elif field == "social_categories":
            c.social_categories = []
        elif field == "requires_disability":
            c.requires_disability = None
        c.unclear.append(field)
        fixes.append(f"{field} -> cleared ({reason})")
    return c, fixes


async def verify_restrictions(
    criteria: EligibilityCriteria, scheme: dict[str, Any], llm: LLMGateway
) -> tuple[EligibilityCriteria, dict[str, Any]]:
    """Ask one yes/no question per restricting value. Returns (criteria, diagnostics)."""
    claims = restriction_claims(criteria)
    if not claims:
        return criteria, {"verification_tokens": 0}
    scheme_text = (f"Scheme Name: {scheme.get('scheme_name', '')}\n"
                   f"Eligibility: {_clip(scheme.get('eligibility'))}\nExclusions: {_clip(scheme.get('exclusions'))}")
    checks: dict[str, RestrictionCheck | None] = {}
    tokens = 0
    for field, claim in claims.items():
        resp = await llm.chat_completion(
            messages=[{"role": "system", "content": RESTRICTION_CHECK_SYSTEM_PROMPT},
                      {"role": "user", "content": f"{scheme_text}\n\nClaim: {claim}\n\nOutput ONLY the JSON."}],
            max_tokens=_MAX_CHECK_OUTPUT_TOKENS,
            temperature=0.0,
            disable_thinking=True,
        )
        tokens += resp.prompt_tokens + resp.completion_tokens
        checks[field], _ = await parse_and_repair_json(resp.content, RestrictionCheck, llm=llm)
    source = " ".join(str(scheme.get(k) or "") for k in ("scheme_name", "brief_description", "eligibility", "exclusions"))
    verified, fixes = apply_restriction_checks(criteria, checks, source)
    diag: dict[str, Any] = {"verification_tokens": tokens,
                            "verification_checks": {f: c.model_dump() if c else None for f, c in checks.items()}}
    if fixes:
        diag["verification_corrections"] = fixes
    return verified, diag


def build_extraction_messages(scheme: dict[str, Any], allowed_groups: list[str]) -> list[dict[str, str]]:
    user = (
        f"Allowed Groups: {', '.join(allowed_groups)}\n\n"
        f"Scheme Name: {scheme.get('scheme_name', '')}\n"
        f"Description: {_clip(scheme.get('brief_description'))}\n"
        f"Eligibility: {_clip(scheme.get('eligibility'))}\n"
        f"Exclusions: {_clip(scheme.get('exclusions'))}\n\n"
        "Output ONLY the JSON checklist."
    )
    return [{"role": "system", "content": CRITERIA_EXTRACTION_SYSTEM_PROMPT}, {"role": "user", "content": user}]


async def extract_criteria(
    scheme: dict[str, Any], allowed_groups: list[str], llm: LLMGateway
) -> tuple[EligibilityCriteria | None, dict[str, Any]]:
    """Extract one scheme's checklist. Returns (criteria or None if unparseable, diagnostics)."""
    resp = await llm.chat_completion(
        messages=build_extraction_messages(scheme, allowed_groups),
        max_tokens=_MAX_OUTPUT_TOKENS,
        temperature=0.0,
        disable_thinking=True,
    )
    criteria, diag = await parse_and_repair_json(resp.content, EligibilityCriteria, llm=llm)
    if criteria is not None:
        # Keep only real catalog groups; the model must not invent new classifications.
        allowed = set(allowed_groups)
        dropped = [g for g in criteria.beneficiary_groups if g not in allowed]
        criteria.beneficiary_groups = [g for g in criteria.beneficiary_groups if g in allowed]
        if dropped:
            diag["dropped_unknown_groups"] = dropped
        criteria, corrections = ground_criteria(criteria, scheme)
        if corrections:
            diag["grounding_corrections"] = corrections
        criteria, verification_diag = await verify_restrictions(criteria, scheme, llm)
        diag.update(verification_diag)
    diag.update({"prompt_tokens": resp.prompt_tokens, "completion_tokens": resp.completion_tokens,
                 "latency_ms": resp.latency_ms})
    return criteria, diag
