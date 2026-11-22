"""Deterministic ETL & regex metadata enricher for myScheme CSV datasets (zero LLM calls)."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# Canonical CPGRAMS-style codes for all 51 Central Ministries present in archive/schemes.csv
CANONICAL_MINISTRY_CODES: dict[str, str] = {
    "Comptroller And Auditor General Of India": "CAGIN",
    "Ministry Of Agriculture and Farmers Welfare": "MOAFW",
    "Ministry Of Ayush": "AYUSH",
    "Ministry Of Chemicals And Fertilizers": "MOCAF",
    "Ministry Of Commerce And Industry": "MOCAI",
    "Ministry Of Communication": "MOCOM",
    "Ministry Of Consumer Affairs, Food And Public Distribution": "CAFPD",
    "Ministry Of Culture": "MOCUL",
    "Ministry Of Defence": "MODEF",
    "Ministry Of Development Of North Eastern Region": "DONER",
    "Ministry Of Earth Sciences": "MOESC",
    "Ministry Of Environment,forests and climate change": "MOEFC",
    "Ministry Of External Affairs": "MOEAF",
    "Ministry Of Finance": "MOFIN",
    "Ministry Of Health & Family Welfare": "MOHFW",
    "Ministry Of Home Affairs": "MOHAF",
    "Ministry Of Housing & Urban Affairs": "MOHUA",
    "Ministry Of Information And Broadcasting": "MOIAB",
    "Ministry Of Jal Shakti": "MOJSH",
    "Ministry Of Labour and Employment": "MOLAE",
    "Ministry Of Law and Justice": "MOLAJ",
    "Ministry Of Micro, Small and Medium Enterprises": "MSMEI",
    "Ministry Of Mines": "MOMIN",
    "Ministry Of Minority Affairs": "MOMAF",
    "Ministry Of New and Renewable Energy": "MONRE",
    "Ministry Of Panchayati Raj": "MOPRJ",
    "Ministry Of Personnel, Public Grievances And Pensions": "DARPG",
    "Ministry Of Petroleum and Natural Gas": "MOPNG",
    "Ministry Of Power": "MOPWR",
    "Ministry Of Railways": "MORLY",
    "Ministry Of Road Transport & Highways": "MORTH",
    "Ministry Of Rural Development": "MORUD",
    "Ministry Of Science And Technology": "MOSAT",
    "Ministry Of Skill Development And Entrepreneurship": "MOSDE",
    "Ministry Of Social Justice and Empowerment": "MOSJE",
    "Ministry Of Statistics and Programme Implementation": "MOSPI",
    "Ministry Of Steel": "MOSTL",
    "Ministry Of Textiles": "MOTEX",
    "Ministry Of Tourism": "MOTOU",
    "Ministry Of Tribal Affairs": "MOTAF",
    "Ministry Of Youth Affairs & Sports": "MOYAS",
    "Ministry of Corporate Affairs": "MOCPA",
    "Ministry of Education": "MOEDU",
    "Ministry of Electronics and Information Technology": "MEITY",
    "Ministry of Fisheries,Animal Husbandry and Dairying": "MFAHD",
    "Ministry of Food Processing Industries": "MOFPI",
    "Ministry of Heavy Industries": "MOHIN",
    "Ministry of Ports,Shipping and Waterways": "MOPSW",
    "Ministry of Women and Child Development": "MOWCD",
    "NITI Aayog (National Institution for Transforming India)": "NITIA",
    "The Lokpal of India": "LOKPL",
}

_CANONICAL_BY_LOWER: dict[str, tuple[str, str]] = {
    k.lower(): (v, k) for k, v in CANONICAL_MINISTRY_CODES.items()
}


def normalize_whitespace(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip()


def normalize_multiline(text: str | None) -> str:
    if not text:
        return ""
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in str(text).splitlines()]
    return "\n".join(ln for ln in lines if ln).strip()


def get_ministry_code(ministry_raw: str) -> tuple[str, str]:
    """Return (ministry_code, canonical_ministry_name)."""
    cleaned = normalize_whitespace(ministry_raw)
    if not cleaned:
        return "GENRL", "Government of India"
    key = cleaned.lower()
    if key in _CANONICAL_BY_LOWER:
        return _CANONICAL_BY_LOWER[key]
    # Fallback code generation for state/unlisted ministries
    words = [w for w in re.findall(r"[A-Za-z]+", cleaned) if w.lower() not in {"of", "and", "the", "for", "in"}]
    code = "".join(w[0] for w in words[:5]).upper()
    if len(code) < 3:
        code = (re.sub(r"[^A-Za-z]", "", cleaned)[:5] or "MINST").upper()
    return code, cleaned


SOCIAL_CATEGORY_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("SC", re.compile(r"\b(?:scheduled\s+caste|sc\b|sc/st|dalit)", re.IGNORECASE)),
    ("ST", re.compile(r"\b(?:scheduled\s+tribe|st\b|sc/st|tribal|adivasi|pvtg)", re.IGNORECASE)),
    ("OBC", re.compile(r"\b(?:other\s+backward\s+class|obc\b|backward\s+class|ebc\b|dnt\b)", re.IGNORECASE)),
    ("EWS", re.compile(r"\b(?:economically\s+weaker\s+section|ews\b)", re.IGNORECASE)),
    ("Minority", re.compile(r"\b(?:minorit(?:y|ies)|muslim|christian|sikh|buddhist|jain|parsi)", re.IGNORECASE)),
    ("PwD", re.compile(r"\b(?:pwd\b|divyang|differently\s+abled|person(?:s)?\s+with\s+disabilit|benchmark\s+disabilit|handicapped)", re.IGNORECASE)),
    ("Women", re.compile(r"\b(?:women|woman|female|girl\s+child|widow|pregnant|lactating|mahila)", re.IGNORECASE)),
    ("General", re.compile(r"\b(?:general\s+category|all\s+categories|irrespective\s+of\s+caste)", re.IGNORECASE)),
]

BENEFICIARY_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("Farmer", re.compile(r"\b(?:farmer|kisan|agricultur|cultivat|krishi|crop|landholding|horticult)", re.IGNORECASE)),
    ("Student", re.compile(r"\b(?:student|scholarship|fellowship|school|college|universit|undergraduate|postgraduate|phd|doctoral|matric)", re.IGNORECASE)),
    ("Woman", re.compile(r"\b(?:women|woman|female|girl|mahila|widow|maternity|pregnant)", re.IGNORECASE)),
    ("Senior Citizen", re.compile(r"\b(?:senior\s+citizen|elderly|old\s+age|aged\s+60|pensioner)", re.IGNORECASE)),
    ("MSME", re.compile(r"\b(?:msme|micro[\s,]+small|small\s+enterprise|udyog|udyam|mudra|startup)", re.IGNORECASE)),
    ("Artisan", re.compile(r"\b(?:artisan|craftsperson|weaver|handloom|handicraft|vishwakarma|carpenter|blacksmith|potter|tailor)", re.IGNORECASE)),
    ("Worker", re.compile(r"\b(?:worker|labour|labor|unorganised|unorganized|shram|street\s+vendor|construction\s+worker|gig\s+worker)", re.IGNORECASE)),
    ("Entrepreneur", re.compile(r"\b(?:entrepreneur|self[\s-]employ|business|venture|startup|innovator)", re.IGNORECASE)),
    ("Researcher", re.compile(r"\b(?:research|scientist|fellowship|phd|post[\s-]?doctoral|academic|faculty)", re.IGNORECASE)),
    ("Differently Abled", re.compile(r"\b(?:divyang|disabilit|differently\s+abled|pwd\b|handicapped)", re.IGNORECASE)),
    ("BPL", re.compile(r"\b(?:bpl\b|below\s+poverty\s+line|antyodaya|economically\s+weaker|poorest)", re.IGNORECASE)),
    ("Fisherman", re.compile(r"\b(?:fisher(?:man|men|folk|ies)|matsya|aquaculture)", re.IGNORECASE)),
    ("Youth", re.compile(r"\b(?:youth|young\s+adult|apprentice|skill\s+development|yuva)", re.IGNORECASE)),
    ("Ex-Servicemen", re.compile(r"\b(?:ex[\s-]servicem|veteran|armed\s+forces|martyr|defence\s+personnel|sainik)", re.IGNORECASE)),
]


def extract_social_categories(text: str) -> list[str]:
    found: list[str] = []
    for label, pattern in SOCIAL_CATEGORY_PATTERNS:
        if pattern.search(text):
            found.append(label)
    return found


def extract_beneficiary_groups(text: str) -> list[str]:
    found: list[str] = []
    for label, pattern in BENEFICIARY_PATTERNS:
        if pattern.search(text):
            found.append(label)
    return found


def extract_age_bounds(eligibility_text: str) -> tuple[int | None, int | None]:
    if not eligibility_text:
        return None, None
    text = eligibility_text
    age_min: int | None = None
    age_max: int | None = None

    # Range patterns: "between 18 and 40 years", "18 to 60 years", "18-50 years", "age group of 18 - 40"
    range_patterns = [
        re.compile(r"(?:between|from|aged?)\s+(\d{1,2})\s*(?:to|and|-|–)\s*(\d{1,2})\s*(?:years?|yrs?)", re.IGNORECASE),
        re.compile(r"age\s*(?:group|limit|bracket)?\s*(?:of|:|is|should\s+be)?\s*(\d{1,2})\s*(?:to|and|-|–)\s*(\d{1,2})\s*(?:years?|yrs?)?", re.IGNORECASE),
        re.compile(r"(\d{1,2})\s*(?:to|-|–)\s*(\d{1,2})\s*(?:years?|yrs?)\s*(?:of\s+age|old)", re.IGNORECASE),
    ]
    for pat in range_patterns:
        m = pat.search(text)
        if m:
            lo, hi = int(m.group(1)), int(m.group(2))
            if 0 <= lo < hi <= 100:
                return lo, hi

    min_patterns = [
        re.compile(r"(?:minimum\s+age|at\s+least|not\s+(?:less|below)\s+than|above|attained\s+(?:the\s+)?age\s+of)\s*(?:of|:|is|should\s+be)?\s*(\d{1,2})\s*(?:years?|yrs?)", re.IGNORECASE),
        re.compile(r"(\d{1,2})\s*(?:years?|yrs?)\s*(?:and\s+above|or\s+above|or\s+older)", re.IGNORECASE),
    ]
    for pat in min_patterns:
        m = pat.search(text)
        if m:
            val = int(m.group(1))
            if 1 <= val <= 90:
                age_min = val
                break

    max_patterns = [
        re.compile(r"(?:maximum\s+age|upper\s+age\s+limit|not\s+(?:more|exceed|above|older)\s+than|below|up\s*to)\s*(?:of|:|is|should\s+be)?\s*(\d{1,2})\s*(?:years?|yrs?)", re.IGNORECASE),
        re.compile(r"below\s+(?:the\s+age\s+of\s+)?(\d{1,2})\s*(?:years?|yrs?)", re.IGNORECASE),
    ]
    for pat in max_patterns:
        m = pat.search(text)
        if m:
            val = int(m.group(1))
            if 5 <= val <= 100 and (age_min is None or val >= age_min):
                age_max = val
                break

    return age_min, age_max


def extract_annual_income_cap(eligibility_text: str) -> int | None:
    if not eligibility_text:
        return None
    # Look within sentences mentioning income / annum / annual
    sentences = re.split(r"[\n\.;]+", eligibility_text)
    candidates: list[int] = []
    money_pat = re.compile(
        r"(?:₹|rs\.?|inr)\s*([\d,]+(?:\.\d+)?)\s*(lakh|lakhs|lac|lacs|crore|crores|thousand)?",
        re.IGNORECASE,
    )
    for sent in sentences:
        low = sent.lower()
        if not any(k in low for k in ("income", "earning", "annum", "annual family", "family income", "parental income", "household income")):
            continue
        for m in money_pat.finditer(sent):
            num_str = m.group(1).replace(",", "")
            try:
                val = float(num_str)
            except ValueError:
                continue
            unit = (m.group(2) or "").lower()
            if unit.startswith(("lakh", "lac")):
                inr = int(round(val * 100_000))
            elif unit.startswith("crore"):
                inr = int(round(val * 10_000_000))
            elif unit == "thousand":
                inr = int(round(val * 1_000))
            else:
                inr = int(round(val))
            # Plausible annual income caps in Indian welfare schemes: 10,000 to 50,00,000
            if 10_000 <= inr <= 5_000_000:
                candidates.append(inr)
    if not candidates:
        return None
    # Use the highest stated cap when multiple slabs exist (permissive filtering)
    return max(candidates)


@dataclass
class EnrichedScheme:
    slug: str
    scheme_name: str
    short_title: str
    level: str
    state: str
    ministry: str
    ministry_code: str
    department: str
    categories: str
    sub_categories: str
    tags: str
    benefit_type: str
    dbt_scheme: bool
    application_mode: str
    age_min: int | None
    age_max: int | None
    income_cap_inr: int | None
    social_categories: list[str]
    beneficiary_groups: list[str]
    brief_description: str
    detailed_description: str
    benefits: str
    eligibility: str
    exclusions: str
    application_process: str
    documents_required: str
    references_text: str
    source_url: str
    faq_count: int = 0
    faqs: list[dict[str, Any]] = field(default_factory=list)


def load_and_enrich_schemes(
    archive_dir: Path,
    scope: str = "central",
) -> tuple[list[EnrichedScheme], dict[str, dict[str, Any]]]:
    """Load schemes.csv and schemes_faqs.csv, filter by scope, and deterministically enrich."""
    schemes_csv = archive_dir / "schemes.csv"
    faqs_csv = archive_dir / "schemes_faqs.csv"

    schemes: list[EnrichedScheme] = []
    by_slug: dict[str, EnrichedScheme] = {}
    ministries_map: dict[str, dict[str, Any]] = {}

    with schemes_csv.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            level = normalize_whitespace(row.get("level"))
            if scope == "central" and level != "Central":
                continue
            slug = normalize_whitespace(row.get("slug"))
            if not slug or slug in by_slug:
                continue

            scheme_name = normalize_whitespace(row.get("scheme_name")) or slug
            short_title = normalize_whitespace(row.get("short_title"))
            state = normalize_whitespace(row.get("state"))
            ministry_raw = normalize_whitespace(row.get("ministry"))
            ministry_code, canonical_ministry = get_ministry_code(ministry_raw)
            department = normalize_whitespace(row.get("department"))
            categories = normalize_whitespace(row.get("categories"))
            sub_categories = normalize_whitespace(row.get("sub_categories"))
            tags = normalize_whitespace(row.get("tags"))
            benefit_type = normalize_whitespace(row.get("benefit_type"))
            dbt_raw = normalize_whitespace(row.get("dbt_scheme")).lower()
            dbt_scheme = dbt_raw in {"true", "1", "yes"}
            application_mode = normalize_whitespace(row.get("application_mode"))

            brief_description = normalize_multiline(row.get("brief_description"))
            detailed_description = normalize_multiline(row.get("detailed_description"))
            benefits = normalize_multiline(row.get("benefits"))
            eligibility = normalize_multiline(row.get("eligibility"))
            exclusions = normalize_multiline(row.get("exclusions"))
            application_process = normalize_multiline(row.get("application_process"))
            documents_required = normalize_multiline(row.get("documents_required"))
            references_text = normalize_multiline(row.get("references"))
            source_url = normalize_whitespace(row.get("source_url")) or f"https://www.myscheme.gov.in/schemes/{slug}"

            enrichment_blob = " ".join([
                scheme_name,
                tags,
                categories,
                sub_categories,
                normalize_whitespace(row.get("target_beneficiaries")),
                eligibility,
            ])
            social_cats = extract_social_categories(f"{eligibility} {tags}")
            beneficiary_groups = extract_beneficiary_groups(enrichment_blob)
            age_min, age_max = extract_age_bounds(eligibility)
            income_cap = extract_annual_income_cap(eligibility)

            scheme = EnrichedScheme(
                slug=slug,
                scheme_name=scheme_name,
                short_title=short_title,
                level=level,
                state=state,
                ministry=canonical_ministry,
                ministry_code=ministry_code,
                department=department,
                categories=categories,
                sub_categories=sub_categories,
                tags=tags,
                benefit_type=benefit_type,
                dbt_scheme=dbt_scheme,
                application_mode=application_mode,
                age_min=age_min,
                age_max=age_max,
                income_cap_inr=income_cap,
                social_categories=social_cats,
                beneficiary_groups=beneficiary_groups,
                brief_description=brief_description,
                detailed_description=detailed_description,
                benefits=benefits,
                eligibility=eligibility,
                exclusions=exclusions,
                application_process=application_process,
                documents_required=documents_required,
                references_text=references_text,
                source_url=source_url,
                faq_count=0,
            )
            schemes.append(scheme)
            by_slug[slug] = scheme

            if ministry_code not in ministries_map:
                ministries_map[ministry_code] = {
                    "ministry_code": ministry_code,
                    "ministry_name": canonical_ministry,
                    "aliases": set(),
                    "scheme_count": 0,
                }
            if ministry_raw:
                ministries_map[ministry_code]["aliases"].add(ministry_raw)
            ministries_map[ministry_code]["scheme_count"] += 1

    # Load FAQs linked to loaded schemes
    with faqs_csv.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            slug = normalize_whitespace(row.get("scheme_slug"))
            if slug not in by_slug:
                continue
            try:
                faq_num = int(float(row.get("faq_number") or 0))
            except ValueError:
                faq_num = len(by_slug[slug].faqs) + 1
            q = normalize_whitespace(row.get("question"))
            a = normalize_multiline(row.get("answer"))
            if not q and not a:
                continue
            by_slug[slug].faqs.append({
                "faq_number": faq_num,
                "question": q,
                "answer": a,
            })

    for scheme in schemes:
        scheme.faqs.sort(key=lambda x: x["faq_number"])
        scheme.faq_count = len(scheme.faqs)

    # Convert alias sets to sorted lists
    for m in ministries_map.values():
        m["aliases"] = sorted(m["aliases"])

    return schemes, ministries_map
