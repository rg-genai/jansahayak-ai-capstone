"""Matching a citizen profile against the scheme catalog's vocabulary.

Everything that exists in the catalog (beneficiary groups, scheme names, categories) is read
from the database at runtime. Only two small mappings live here, because the catalog cannot
supply them:

* ``PROFILE_FIELD_GROUPS`` - which catalog group a structured profile field implies
  (gender, age, PwD, BPL).
* ``OCCUPATION_SYNONYMS`` - free-text occupation words that do not literally contain the
  catalog group name (e.g. "carpenter" -> "Artisan").
"""

from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass
from typing import Any

from backend.agent.state import CitizenProfile
from backend.db.repositories import Repository

logger = logging.getLogger(__name__)

# National Youth Policy (2014) defines youth as 15-29; many schemes use up to 35.
YOUTH_AGE_RANGE = (15, 35)
SENIOR_CITIZEN_MIN_AGE = 60

# Catalog group name -> predicate on the profile. These groups describe WHO the person is,
# not their work, so they are treated separately from occupation groups.
PROFILE_FIELD_GROUPS: dict[str, Any] = {
    "Woman": lambda p: (p.gender or "").strip().lower() in ("female", "woman", "girl", "f"),
    "Youth": lambda p: p.age is not None and YOUTH_AGE_RANGE[0] <= p.age <= YOUTH_AGE_RANGE[1],
    "Senior Citizen": lambda p: p.age is not None and p.age >= SENIOR_CITIZEN_MIN_AGE,
    "Differently Abled": lambda p: bool(p.is_pwd),
    "BPL": lambda p: bool(p.is_bpl),
}

# Catalog group name -> extra words people type in the free-text occupation field.
OCCUPATION_SYNONYMS: dict[str, tuple[str, ...]] = {
    "Student": ("studying", "college", "school", "pupil", "b.tech", "btech"),
    "Researcher": ("research", "phd", "fellow", "scientist"),
    "Farmer": ("kisan", "cultivator", "agricultur"),
    "Fisherman": ("fisher", "fishing"),
    "Artisan": ("carpenter", "weaver", "potter", "blacksmith", "craft", "tailor", "cobbler", "goldsmith"),
    "MSME": ("small business", "shop owner", "trader", "vendor"),
    "Entrepreneur": ("business", "startup", "self-employed", "self employed"),
    "Ex-Servicemen": ("ex-servicem", "ex servicem", "veteran", "armed forces"),
    "Worker": ("labour", "labor", "construction", "driver", "domestic help", "daily wage"),
}

# ---- Education stages ----
# The catalog has no structured education field, so a scheme's stage is read from its name
# (most reliable) or, failing that, from unambiguous phrases in its eligibility text.
SCHOOL, HIGHER_SECONDARY, UNDERGRADUATE, POSTGRADUATE, DOCTORAL = (
    "school (up to Class 10)", "Class 11-12", "undergraduate", "postgraduate", "doctoral",
)
_POST_SCHOOL = frozenset({UNDERGRADUATE, POSTGRADUATE, DOCTORAL})
_POST_MATRIC = frozenset({HIGHER_SECONDARY}) | _POST_SCHOOL

# (pattern, stages) - checked against the scheme NAME.
_SCHEME_NAME_STAGES: list[tuple[re.Pattern[str], frozenset[str]]] = [
    (re.compile(r"pre[- ]?matric", re.I), frozenset({SCHOOL})),
    (re.compile(r"\bschool\b", re.I), frozenset({SCHOOL, HIGHER_SECONDARY})),
    (re.compile(r"post[- ]?matric", re.I), _POST_MATRIC),
    (re.compile(r"\b(?:college|university|degree|undergraduate|bachelor)", re.I), frozenset({UNDERGRADUATE, POSTGRADUATE})),
    (re.compile(r"post[- ]?graduate|\bmasters?\b|\bm\.?tech\b", re.I), frozenset({POSTGRADUATE})),
    (re.compile(r"\bph\.?\s?d\b|doctoral|research fellowship", re.I), frozenset({POSTGRADUATE, DOCTORAL})),
]
# (pattern, stages) - checked against ELIGIBILITY text only when the name says nothing.
_ELIGIBILITY_TEXT_STAGES: list[tuple[re.Pattern[str], frozenset[str]]] = [
    (re.compile(r"pre[- ]?matric|studying in class(?:es)? (?:ix|x|9|10)\b", re.I), frozenset({SCHOOL})),
    (re.compile(r"post[- ]?matric", re.I), _POST_MATRIC),
    (re.compile(r"beyond class (?:xii|12)", re.I), _POST_SCHOOL),
    # Text that mentions PhD often also covers Master's (e.g. overseas scholarships), so stay permissive.
    (re.compile(r"pursuing (?:a |an )?(?:ph\.?\s?d|doctoral)", re.I), frozenset({POSTGRADUATE, DOCTORAL})),
]
# (pattern, stage) - free-text profile education level ("B.Tech", "12th", "PhD"). First match wins.
_PROFILE_EDUCATION_STAGES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"ph\.?\s?d|doctor", re.I), DOCTORAL),
    (re.compile(r"\bm\.?\s?(?:tech|sc|a|com|e|ba|ca|phil)\b|master|post[- ]?grad", re.I), POSTGRADUATE),
    (re.compile(r"\bb\.?\s?(?:tech|sc|a|com|e|ba|ca|ed|pharm|arch)\b|bachelor|graduat|degree|mbbs|llb|college|diploma|polytechnic", re.I), UNDERGRADUATE),
    (re.compile(r"\b(?:11|12)(?:th)?\b|\bx?ii\b|\bxi\b|higher secondary|intermediate|puc", re.I), HIGHER_SECONDARY),
    (re.compile(r"\b(?:[1-9]|10)(?:st|nd|rd|th)\b|\bclass\b|school|matric|primary|secondary", re.I), SCHOOL),
]
# Catalog groups for which an education-stage mismatch makes a scheme unusable.
EDUCATION_GROUPS = ("Student", "Researcher")


def scheme_education_stages(scheme_name: str, eligibility_text: str) -> frozenset[str]:
    """Education stages a scheme is meant for; empty if it cannot be determined."""
    for source, rules in ((scheme_name, _SCHEME_NAME_STAGES), (eligibility_text, _ELIGIBILITY_TEXT_STAGES)):
        stages = frozenset().union(*(s for pattern, s in rules if pattern.search(source or "")))
        if stages:
            return stages
    return frozenset()


def profile_education_stage(education_level: str | None) -> str | None:
    text = (education_level or "").strip()
    return next((stage for pattern, stage in _PROFILE_EDUCATION_STAGES if pattern.search(text)), None) if text else None


# Short-title matching rules (the catalog has acronyms like "BIG", "TIP", "AMI" that are also
# everyday words, so short ones must be typed in capitals to count as a scheme mention):
_MIN_TITLE_LEN = 3            # ignore 1-2 letter titles entirely ("AA", "AE")
_CASE_SENSITIVE_MAX_LEN = 4   # titles up to this length must appear in UPPERCASE in the query
# A long scheme name's leading segment ("Ayushman Bharat" in "Ayushman Bharat - PM-JAY")
# is also an alias, if it has at least this many words.
_MIN_ALIAS_WORDS = 2
_ALIAS_SPLIT_RE = re.compile(r"\s+-\s+|\(")
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_RAW_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")


def _tokens(text: str) -> tuple[str, ...]:
    return tuple(_TOKEN_RE.findall((text or "").lower()))


def _contains_sequence(haystack: tuple[str, ...], needle: tuple[str, ...]) -> bool:
    n = len(needle)
    return n > 0 and any(haystack[i : i + n] == needle for i in range(len(haystack) - n + 1))


@dataclass(frozen=True)
class CatalogVocabulary:
    groups: tuple[str, ...]
    occupation_groups: tuple[str, ...]
    group_top_categories: dict[str, tuple[str, ...]]
    short_titles: tuple[tuple[str, ...], ...]   # tokenised short titles, e.g. ("pm", "kisan")
    name_aliases: tuple[tuple[str, ...], ...]   # tokenised full names + leading segments

    # ---- Profile -> groups ----

    def occupation_group(self, occupation: str | None) -> str | None:
        """Catalog occupation group for free-text occupation, or None if unrecognised."""
        occ = (occupation or "").strip().lower()
        if not occ:
            return None
        for group in self.occupation_groups:
            if group.lower() in occ:
                return group
        for group in self.occupation_groups:
            if any(word in occ for word in OCCUPATION_SYNONYMS.get(group, ())):
                return group
        return None

    def profile_groups(self, profile: CitizenProfile) -> set[str]:
        """Non-occupation catalog groups that apply to this citizen."""
        found = {g for g, applies in PROFILE_FIELD_GROUPS.items() if g in self.groups and applies(profile)}
        # The occupation box sometimes holds a profile group (e.g. "Senior Citizen").
        occ = (profile.occupation or "").strip().lower()
        found.update(g for g in self.groups if g not in self.occupation_groups and occ and g.lower() in occ)
        return found

    # ---- Query analysis ----

    def mentions_specific_scheme(self, query: str) -> bool:
        """True if the query names a scheme from the catalog (full name or short title)."""
        q_tokens = _tokens(query)
        if any(_contains_sequence(q_tokens, alias) for alias in self.name_aliases):
            return True
        upper_tokens = {t.lower() for t in _RAW_TOKEN_RE.findall(query or "") if t.isupper()}
        for title in self.short_titles:
            squashed = "".join(title)
            if len(squashed) <= _CASE_SENSITIVE_MAX_LEN:
                if squashed in upper_tokens:
                    return True
            elif _contains_sequence(q_tokens, title) or squashed in q_tokens:
                return True  # "pm kisan", "PM-KISAN" and "pmkisan" all count
        return False

    def build_discovery_query(self, profile: CitizenProfile) -> tuple[str, str | None]:
        """Retrieval query + beneficiary-group filter that describe this citizen."""
        occ_group = self.occupation_group(profile.occupation)
        p_groups = self.profile_groups(profile)
        filter_group = occ_group or next(
            (g for g in ("Senior Citizen", "Differently Abled") if g in p_groups), None
        )

        topics = self.group_top_categories.get(filter_group or "", ())
        topic = f"{' and '.join(topics)} schemes" if topics else "welfare schemes"
        return f"Central Government {topic} for a {self.describe_citizen(profile)}", filter_group

    def build_need_query(self, need: str, profile: CitizenProfile) -> str:
        """The citizen's own words plus who they are (no group filter: the need may differ from their occupation)."""
        who = self.describe_citizen(profile)
        return f"{need.strip()} - for a {who}" if who != "citizen" else need.strip()

    def describe_citizen(self, profile: CitizenProfile) -> str:
        """Short retrieval-friendly description, e.g. '19-year-old female OBC student, education B.Tech, ...'."""
        p_groups = self.profile_groups(profile)
        who: list[str] = []
        if profile.age is not None:
            who.append(f"{profile.age}-year-old")
        if "Woman" in p_groups:
            who.append("female")
        elif profile.gender:
            who.append(profile.gender.lower())
        if profile.social_category and profile.social_category.lower() not in ("general", "all"):
            who.append(profile.social_category)
        if profile.is_pwd:
            who.append("person with disability")
        who.append(profile.occupation.lower() if profile.occupation else "citizen")

        parts = [" ".join(who)]
        if profile.education_level:
            parts.append(f"education {profile.education_level}")
        if profile.annual_income_inr is not None:
            parts.append(f"family annual income Rs {profile.annual_income_inr}")
        if profile.is_bpl:
            parts.append("below poverty line (BPL)")
        return ", ".join(parts)


_TOP_CATEGORIES_PER_GROUP = 2
_cache: dict[str, CatalogVocabulary] = {}
_cache_lock = threading.Lock()


def get_catalog_vocabulary(repo: Repository) -> CatalogVocabulary:
    """Build once per database (the catalog is static at runtime) and reuse."""
    key = str(repo.db_path)
    with _cache_lock:
        if key in _cache:
            return _cache[key]

        group_cats = repo.beneficiary_group_categories()
        groups = tuple(sorted(group_cats))
        missing = [g for g in PROFILE_FIELD_GROUPS if g not in group_cats]
        if missing:
            logger.warning("Profile groups not present in catalog (ignored): %s", missing)
        occupation_groups = tuple(g for g in groups if g not in PROFILE_FIELD_GROUPS)

        top_cats = {
            g: tuple(c for c, _ in sorted(cats.items(), key=lambda kv: -kv[1])[:_TOP_CATEGORIES_PER_GROUP])
            for g, cats in group_cats.items()
        }

        titles = repo.list_scheme_titles()
        short_titles = tuple(
            dict.fromkeys(
                tok for tok in (_tokens(t.get("short_title") or "") for t in titles)
                if len("".join(tok)) >= _MIN_TITLE_LEN
            )
        )
        aliases: dict[tuple[str, ...], None] = {}
        for t in titles:
            name = t.get("scheme_name") or ""
            aliases[_tokens(name)] = None
            lead = _tokens(_ALIAS_SPLIT_RE.split(name, maxsplit=1)[0])
            if len(lead) >= _MIN_ALIAS_WORDS:
                aliases[lead] = None
        aliases.pop((), None)

        vocab = CatalogVocabulary(
            groups=groups,
            occupation_groups=occupation_groups,
            group_top_categories=top_cats,
            short_titles=short_titles,
            name_aliases=tuple(aliases),
        )
        _cache[key] = vocab
        return vocab
