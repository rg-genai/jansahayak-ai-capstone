"""Deterministic Indian PII Detector & Masker (DPDP Act 2023 compliance).

Masks Aadhaar, PAN, Indian mobile numbers, IFSC codes, and context-tagged bank account numbers
while explicitly preserving CPGRAMS registration numbers (e.g., MOAFW/E/2026/000001) and draft IDs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


# Whitelisted official reference IDs (never mask)
_TICKET_RE = re.compile(r"\b[A-Z]{4,6}/E/20\d{2}/\d{6}\b")
_DRAFT_RE = re.compile(r"\bDRAFT-[A-Za-z0-9]{6,12}\b")

# Indian PII patterns
_AADHAAR_RE = re.compile(r"(?<!\d)([2-9]\d{3})[\s-]?(\d{4})[\s-]?(\d{4})(?!\d)")
_PAN_RE = re.compile(r"\b([A-Z]{5}\d{4}[A-Z])\b")
_IFSC_RE = re.compile(r"\b([A-Z]{4}0[A-Z0-9]{6})\b")
_PHONE_RE = re.compile(r"(?<!\d)(?:\+91[\s-]?|0)?([6-9]\d{9})(?!\d)")
_BANK_ACCT_RE = re.compile(
    r"((?:account|a/c|acct|bank\s*account)\s*(?:no\.?|number|#|:|is)?\s*)(\d{9,18})\b",
    re.IGNORECASE,
)


@dataclass
class PIIMaskResult:
    masked_text: str
    pii_types_found: list[str] = field(default_factory=list)
    warning_message: str | None = None

    @property
    def has_pii(self) -> bool:
        return len(self.pii_types_found) > 0


def mask_pii(text: str) -> PIIMaskResult:
    if not text:
        return PIIMaskResult(masked_text="")

    # Protect whitelisted ticket / draft tokens using temporary placeholders
    protected: dict[str, str] = {}

    def _protect(pattern: re.Pattern[str], s: str, prefix: str) -> str:
        def _repl(m: re.Match[str]) -> str:
            key = f"__{prefix}_{len(protected)}__"
            protected[key] = m.group(0)
            return key
        return pattern.sub(_repl, s)

    working = _protect(_TICKET_RE, text, "TICKET")
    working = _protect(_DRAFT_RE, working, "DRAFT")

    found: list[str] = []

    # 1. Context-tagged bank account numbers first (before generic digit patterns)
    if _BANK_ACCT_RE.search(working):
        found.append("BANK_ACCOUNT")
        working = _BANK_ACCT_RE.sub(r"\1[ACCOUNT_MASKED]", working)

    # 2. Aadhaar (12 digits starting 2-9) -> preserve last 4 digits only
    if _AADHAAR_RE.search(working):
        found.append("AADHAAR")
        working = _AADHAAR_RE.sub(lambda m: f"[AADHAAR_MASKED:XXXX-XXXX-{m.group(3)}]", working)

    # 3. PAN Card
    if _PAN_RE.search(working):
        found.append("PAN")
        working = _PAN_RE.sub("[PAN_MASKED]", working)

    # 4. IFSC Code
    if _IFSC_RE.search(working):
        found.append("IFSC")
        working = _IFSC_RE.sub("[IFSC_MASKED]", working)

    # 5. Indian Mobile Number (10 digits starting 6-9)
    if _PHONE_RE.search(working):
        found.append("PHONE")
        working = _PHONE_RE.sub("[PHONE_MASKED]", working)

    # Restore protected tokens
    for key, orig in protected.items():
        working = working.replace(key, orig)

    unique_found = list(dict.fromkeys(found))
    warning = None
    if unique_found:
        warning = (
            "Privacy Notice (DPDP Act 2023): Sensitive personal details "
            f"({', '.join(unique_found)}) were automatically masked before processing. "
            "Please never share your full Aadhaar number, OTPs, or banking passwords."
        )

    return PIIMaskResult(
        masked_text=working,
        pii_types_found=unique_found,
        warning_message=warning,
    )
