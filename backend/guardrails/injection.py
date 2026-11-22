"""Layer 1 & Layer 2 Prompt-Injection Shield, Policy Refusal Classifier & Evidence Isolation."""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass, field


@dataclass
class GuardrailVerdict:
    blocked: bool
    category: str | None = None
    reason: str | None = None
    refusal_message: str | None = None
    flags: list[str] = field(default_factory=list)


_INJECTION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("prompt_override", re.compile(r"\b(?:ignore|disregard|forget|override)\s+(?:all\s+)?(?:previous|prior|above|system)\s+(?:instructions|prompts?|rules?)", re.IGNORECASE)),
    ("system_prompt_extract", re.compile(r"\b(?:reveal|show|print|dump|output|repeat)\s+(?:your\s+|the\s+)?(?:system\s+prompt|hidden\s+instructions|developer\s+prompt|secret\s+instructions)", re.IGNORECASE)),
    ("jailbreak_persona", re.compile(r"\b(?:act\s+as\s+dan|jailbreak|developer\s+mode|unfiltered\s+mode|bypass\s+(?:all\s+)?(?:safety|guardrails|restrictions|filters))\b", re.IGNORECASE)),
    ("forced_approval", re.compile(r"\b(?:mark\s+me\s+as\s+eligible\s+regardless|approve\s+my\s+eligibility\s+even\s+if|ignore\s+eligibility\s+rules|skip\s+confirmation\s+and\s+submit)\b", re.IGNORECASE)),
    ("secret_exfil", re.compile(r"\b(?:print|show|reveal|leak|dump)\s+(?:your\s+|the\s+)?(?:api[\s_-]?key|\.env|bearer\s+token|environment\s+variables|secrets?)\b", re.IGNORECASE)),
]

_FRAUD_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("document_forgery", re.compile(r"\b(?:fake|forge|falsify|fabricate|photoshop|counterfeit)\s+(?:an?\s+)?(?:[\w-]+\s+){0,2}(?:certificate|card|document|record|proof|application|claim)\b", re.IGNORECASE)),
    ("income_hiding", re.compile(r"\b(?:hide|underreport|conceal|fake\s+lower)\s+(?:my\s+|our\s+)?(?:family\s+|household\s+|annual\s+)?(?:income|salary|tax|land|assets?)\b", re.IGNORECASE)),
    ("bribe_or_fraud", re.compile(r"\b(?:bribe\b.*\b(?:officer|official|csc|patwari|clerk|approve|scheme|pension|subsidy)|commit\s+subsidy\s+fraud|claim\s+(?:benefit|pension|scholarship)\s+with\s+fake)\b", re.IGNORECASE)),
]

_CAPTCHA_BYPASS_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("captcha_bypass", re.compile(r"\b(?:bypass|crack|solve|defeat|circumvent)\s+(?:the\s+)?(?:captcha|recaptcha|otp|verification)\b", re.IGNORECASE)),
    ("portal_spam", re.compile(r"\b(?:spam|flood|auto[\s-]?submit\s+\d{2,}|bot\s+to\s+submit\s+\d+|ddos)\b.*\b(?:cpgrams|pgportal|myscheme|grievance|complaint|portal)\b", re.IGNORECASE)),
    ("portal_spam_rev", re.compile(r"\b(?:cpgrams|pgportal|myscheme)\b.*\b(?:spam|flood|bypass\s+captcha|auto[\s-]?submit\s+\d{2,}|selenium\s+bot)\b", re.IGNORECASE)),
]

_MEDICAL_LEGAL_INVESTMENT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("medical_advice", re.compile(r"\b(?:which\s+medicine|prescribe\s+me|dosage\s+for|what\s+pills?\s+should\s+i\s+take|treat\s+my\s+chest\s+pain|diagnose\s+my\s+symptoms)\b", re.IGNORECASE)),
    ("investment_advice", re.compile(r"\b(?:which\s+stock\s+should\s+i\s+buy|best\s+crypto\s+to\s+invest|guaranteed\s+stock\s+tip|intraday\s+trading\s+tip)\b", re.IGNORECASE)),
]

_BASE64_TOKEN_RE = re.compile(r"\b[A-Za-z0-9+/]{24,}={0,2}\b")


def _check_base64_payload(text: str) -> str | None:
    """Detect obfuscated base64 prompt-injection payloads."""
    for match in _BASE64_TOKEN_RE.finditer(text):
        token = match.group(0)
        if len(token) % 4 != 0:
            continue
        try:
            decoded = base64.b64decode(token, validate=True).decode("utf-8", errors="ignore")
        except Exception:
            continue
        if decoded and any(p.search(decoded) for _, p in _INJECTION_PATTERNS):
            return "base64_prompt_injection"
    return None


def check_input_guardrails(text: str) -> GuardrailVerdict:
    if not text or not text.strip():
        return GuardrailVerdict(blocked=False)

    flags: list[str] = []

    # 1. Direct Prompt Injection / Jailbreak / Secret Exfiltration
    for tag, pat in _INJECTION_PATTERNS:
        if pat.search(text):
            flags.append(f"injection:{tag}")
            return GuardrailVerdict(
                blocked=True,
                category="PROMPT_INJECTION",
                reason=f"Detected adversarial prompt-injection attempt ({tag}).",
                refusal_message=(
                    "I cannot override my safety guidelines, reveal internal system instructions, "
                    "bypass eligibility rules, or skip mandatory confirmation checks. "
                    "I can help you check official Central Government schemes, eligibility criteria, "
                    "required documents, or draft a legitimate CPGRAMS grievance."
                ),
                flags=flags,
            )

    b64_flag = _check_base64_payload(text)
    if b64_flag:
        flags.append(f"injection:{b64_flag}")
        return GuardrailVerdict(
            blocked=True,
            category="PROMPT_INJECTION",
            reason="Detected base64-obfuscated prompt-injection payload.",
            refusal_message=(
                "I detected an encoded instruction override attempt and cannot process it. "
                "Please ask your government scheme or grievance question in plain language."
            ),
            flags=flags,
        )

    # 2. Fraud / Document Forgery
    for tag, pat in _FRAUD_PATTERNS:
        if pat.search(text):
            flags.append(f"policy:{tag}")
            return GuardrailVerdict(
                blocked=True,
                category="FRAUD_REFUSAL",
                reason=f"Detected request for document forgery or subsidy fraud ({tag}).",
                refusal_message=(
                    "I cannot assist with falsifying documents, hiding income, or bypassing official "
                    "eligibility verification. Government welfare schemes verify income, caste, and "
                    "identity records through state revenue portals and DigiLocker. If you'd like, "
                    "I can help you find schemes you genuinely qualify for or explain how to apply "
                    "for an authentic certificate through your local Tehsil / CSC."
                ),
                flags=flags,
            )

    # 3. CAPTCHA / Portal Bypass / Spam Automation
    for tag, pat in _CAPTCHA_BYPASS_PATTERNS:
        if pat.search(text):
            flags.append(f"policy:{tag}")
            return GuardrailVerdict(
                blocked=True,
                category="CAPTCHA_BYPASS_REFUSAL",
                reason=f"Detected request to bypass CAPTCHA or automate portal spam ({tag}).",
                refusal_message=(
                    "I cannot help bypass CAPTCHAs, automate bulk portal submissions, or circumvent "
                    "government portal security controls. For legitimate grievances, JanSahayak AI "
                    "can draft a formal CPGRAMS complaint (<=2,000 characters), submit it via the "
                    "authorized sandbox/API Setu workflow with your confirmation, and provide a "
                    "ready-to-use Assisted Handoff Packet for https://pgportal.gov.in/."
                ),
                flags=flags,
            )

    # 4. Out-of-scope Medical / Investment Advice
    for tag, pat in _MEDICAL_LEGAL_INVESTMENT_PATTERNS:
        if pat.search(text):
            flags.append(f"out_of_scope:{tag}")
            if tag == "medical_advice":
                msg = (
                    "I cannot provide medical diagnoses or prescribe medicines. If this is an emergency, "
                    "please call **108** (National Ambulance Service) or visit the nearest hospital immediately. "
                    "If you need information on government health coverage such as **Ayushman Bharat (PM-JAY)**, "
                    "I can help you check eligibility and benefits."
                )
            else:
                msg = (
                    "I cannot provide personal stock market, cryptocurrency, or financial investment advice. "
                    "I can, however, explain official Government of India savings, pension, or credit schemes "
                    "such as Atal Pension Yojana, Sukanya Samriddhi Yojana, or PM Mudra Yojana."
                )
            return GuardrailVerdict(
                blocked=True,
                category="OUT_OF_SCOPE_REFUSAL",
                reason=f"Out-of-scope request ({tag}).",
                refusal_message=msg,
                flags=flags,
            )

    return GuardrailVerdict(blocked=False, flags=flags)


# Indirect prompt-injection patterns inside retrieved documents / web snippets
_INDIRECT_INJECTION_RE = re.compile(
    r"(?:ignore\s+(?:all\s+)?previous\s+instructions|system\s+override|reveal\s+system\s+prompt|"
    r"you\s+must\s+now\s+output|disregard\s+all\s+rules|approve\s+every\s+user|"
    r"print\s+the\s+api\s+key|execute\s+tool\s+submit_or_track_grievance)",
    re.IGNORECASE,
)


def sanitize_untrusted_evidence(text: str) -> tuple[str, list[str]]:
    """Neutralize indirect prompt-injection lines inside retrieved snippets and wrap in untrusted delimiters."""
    flags: list[str] = []
    cleaned_lines: list[str] = []
    for line in (text or "").splitlines():
        if _INDIRECT_INJECTION_RE.search(line):
            flags.append("indirect_injection_neutralized")
            cleaned_lines.append("[UNTRUSTED_INSTRUCTION_STRIPPED]")
        else:
            cleaned_lines.append(line)
    body = "\n".join(cleaned_lines)
    wrapped = f"<RETRIEVED_EVIDENCE_UNTRUSTED>\n{body}\n</RETRIEVED_EVIDENCE_UNTRUSTED>"
    return wrapped, list(dict.fromkeys(flags))
