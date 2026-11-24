"""Section-aware chunker guaranteeing <= 512 model tokens per chunk for bge-small-en-v1.5."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import tiktoken

from backend.retrieval.etl import EnrichedScheme


try:
    _ENC = tiktoken.get_encoding("cl100k_base")
except Exception:
    _ENC = None

# Hard upper bound in conservative token estimation (leaves generous margin under BERT 512 WordPiece tokens)
MAX_SAFE_TOKENS = 440
HARD_TOKEN_LIMIT = 512
# Section label of chunks built from a scheme's FAQ pairs (the retriever can exclude them for evaluation).
FAQ_SECTION = "faq_group"


def estimate_tokens(text: str) -> int:
    """Conservative token count: max(tiktoken cl100k, word_count * 1.38) so BERT WordPiece never exceeds 512."""
    if not text:
        return 0
    tk_len = len(_ENC.encode(text, disallowed_special=())) if _ENC is not None else 0
    words = len(text.split())
    # Punctuation-heavy Indic/URL strings can expand slightly in BERT WordPiece
    punct_extra = len(re.findall(r"[/\-_:;.,()\[\]]", text)) // 4
    approx_bert = int(words * 1.35) + punct_extra
    return max(tk_len, approx_bert)


def _split_sentences(text: str) -> list[str]:
    if not text:
        return []
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [p.strip() for p in parts if p.strip()]


def _split_oversized_segment(segment: str, max_tokens: int) -> list[str]:
    """Fallback word-level splitter when a single sentence exceeds max_tokens."""
    words = segment.split()
    if not words:
        return []
    chunks: list[str] = []
    cur: list[str] = []
    for w in words:
        trial = " ".join(cur + [w])
        if cur and estimate_tokens(trial) > max_tokens:
            chunks.append(" ".join(cur))
            cur = [w]
        else:
            cur.append(w)
    if cur:
        chunks.append(" ".join(cur))
    return chunks


def split_body_with_header(
    header: str,
    body: str,
    max_tokens: int = MAX_SAFE_TOKENS,
    overlap_words: int = 35,
) -> list[str]:
    """Split body into chunks prepended with `header`, each strictly <= max_tokens."""
    body = body.strip()
    if not body:
        return []

    full = f"{header}\n{body}"
    if estimate_tokens(full) <= max_tokens:
        return [full]

    header_tokens = estimate_tokens(header) + 4
    body_budget = max(120, max_tokens - header_tokens)

    sentences = _split_sentences(body)
    expanded: list[str] = []
    for s in sentences:
        if estimate_tokens(s) > body_budget:
            expanded.extend(_split_oversized_segment(s, body_budget))
        else:
            expanded.append(s)

    results: list[str] = []
    current: list[str] = []

    for seg in expanded:
        trial_body = " ".join(current + [seg])
        if current and estimate_tokens(f"{header}\n{trial_body}") > max_tokens:
            results.append(f"{header}\n{' '.join(current)}")
            # Keep small overlap from previous chunk if it fits
            prev_words = " ".join(current).split()
            overlap_str = " ".join(prev_words[-overlap_words:]) if len(prev_words) > overlap_words else ""
            if overlap_str and estimate_tokens(f"{header}\n{overlap_str} {seg}") <= max_tokens:
                current = [overlap_str, seg]
            else:
                current = [seg]
        else:
            current.append(seg)

    if current:
        results.append(f"{header}\n{' '.join(current)}")

    # Final safety guard against any edge case > HARD_TOKEN_LIMIT
    safe_results: list[str] = []
    for chunk in results:
        if estimate_tokens(chunk) <= HARD_TOKEN_LIMIT:
            safe_results.append(chunk)
        else:
            # Force word truncation/split preserving header
            content_only = chunk[len(header):].strip()
            for sub in _split_oversized_segment(content_only, max(100, HARD_TOKEN_LIMIT - header_tokens - 20)):
                safe_results.append(f"{header}\n{sub}")
    return safe_results


@dataclass
class SchemeChunk:
    chunk_id: str
    scheme_slug: str
    scheme_name: str
    ministry: str
    section: str
    text: str
    token_count: int
    source_url: str
    faq_numbers: list[int] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


def chunk_scheme(scheme: EnrichedScheme) -> list[SchemeChunk]:
    """Generate section-aware chunks for one scheme + all its FAQs."""
    chunks: list[SchemeChunk] = []
    base_meta = {
        "scheme_slug": scheme.slug,
        "scheme_name": scheme.scheme_name,
        "short_title": scheme.short_title,
        "level": scheme.level,
        "ministry": scheme.ministry,
        "ministry_code": scheme.ministry_code,
        "categories": [c.strip() for c in scheme.categories.split(";") if c.strip()],
        "tags": [t.strip() for t in scheme.tags.split(";") if t.strip()],
        "benefit_type": scheme.benefit_type,
        "dbt_scheme": scheme.dbt_scheme,
        "application_mode": [m.strip() for m in scheme.application_mode.split(";") if m.strip()],
        "social_categories": scheme.social_categories,
        "beneficiary_groups": scheme.beneficiary_groups,
        "age_min": scheme.age_min,
        "age_max": scheme.age_max,
        "income_cap_inr": scheme.income_cap_inr,
    }

    def _emit(section: str, texts: list[str], faq_nums_per_chunk: list[list[int]] | None = None) -> None:
        for idx, txt in enumerate(texts):
            toks = estimate_tokens(txt)
            fnums = faq_nums_per_chunk[idx] if faq_nums_per_chunk else []
            cid = f"{scheme.slug}__{section}__{idx}"
            meta = dict(base_meta)
            meta["section"] = section
            if fnums:
                meta["faq_numbers"] = fnums
            chunks.append(
                SchemeChunk(
                    chunk_id=cid,
                    scheme_slug=scheme.slug,
                    scheme_name=scheme.scheme_name,
                    ministry=scheme.ministry,
                    section=section,
                    text=txt,
                    token_count=toks,
                    source_url=scheme.source_url,
                    faq_numbers=fnums,
                    metadata=meta,
                )
            )

    # 1. Overview & Benefits
    overview_parts: list[str] = []
    if scheme.short_title and scheme.short_title.lower() != scheme.scheme_name.lower():
        overview_parts.append(f"Also known as: {scheme.short_title}.")
    if scheme.brief_description:
        overview_parts.append(f"Overview: {scheme.brief_description}")
    if scheme.detailed_description and scheme.detailed_description != scheme.brief_description:
        overview_parts.append(f"Details: {scheme.detailed_description}")
    if scheme.benefits:
        overview_parts.append(f"Benefits: {scheme.benefits}")
    if scheme.tags:
        overview_parts.append(f"Tags: {scheme.tags}")

    if overview_parts:
        hdr = f"[Scheme: {scheme.scheme_name} | Ministry: {scheme.ministry} | Section: Overview & Benefits]"
        _emit("overview_benefits", split_body_with_header(hdr, "\n".join(overview_parts)))

    # 2. Eligibility & Exclusions (keep together whenever possible)
    elig_parts: list[str] = []
    if scheme.eligibility:
        elig_parts.append(f"Eligibility Criteria: {scheme.eligibility}")
    if scheme.exclusions:
        elig_parts.append(f"Exclusions: {scheme.exclusions}")
    if elig_parts:
        hdr = f"[Scheme: {scheme.scheme_name} | Ministry: {scheme.ministry} | Section: Eligibility & Exclusions]"
        _emit("eligibility_exclusions", split_body_with_header(hdr, "\n".join(elig_parts)))

    # 3. Application Process & Documents Required
    proc_parts: list[str] = []
    if scheme.application_mode:
        proc_parts.append(f"Application Mode: {scheme.application_mode}")
    if scheme.application_process:
        proc_parts.append(f"Application Process: {scheme.application_process}")
    if scheme.documents_required:
        proc_parts.append(f"Documents Required: {scheme.documents_required}")
    if scheme.references_text:
        proc_parts.append(f"Official References: {scheme.references_text}")
    if proc_parts:
        hdr = f"[Scheme: {scheme.scheme_name} | Ministry: {scheme.ministry} | Section: Application Process & Documents]"
        _emit("process_documents", split_body_with_header(hdr, "\n".join(proc_parts)))

    # 4. Grouped FAQs (2-3 consecutive FAQs per chunk up to MAX_SAFE_TOKENS)
    if scheme.faqs:
        hdr = f"[Scheme: {scheme.scheme_name} | Ministry: {scheme.ministry} | Section: FAQs]"
        faq_chunks: list[str] = []
        faq_num_lists: list[list[int]] = []

        cur_entries: list[str] = []
        cur_nums: list[int] = []

        for faq in scheme.faqs:
            fnum = int(faq["faq_number"])
            entry = f"FAQ {fnum} Q: {faq['question']}\nA: {faq['answer']}"
            trial_body = "\n".join(cur_entries + [entry])
            trial_full = f"{hdr}\n{trial_body}"

            if cur_entries and (len(cur_entries) >= 3 or estimate_tokens(trial_full) > MAX_SAFE_TOKENS):
                faq_chunks.append(f"{hdr}\n" + "\n".join(cur_entries))
                faq_num_lists.append(list(cur_nums))
                cur_entries = []
                cur_nums = []

            if estimate_tokens(f"{hdr}\n{entry}") > MAX_SAFE_TOKENS:
                # Oversized single FAQ -> split safely
                sub_chunks = split_body_with_header(hdr, entry)
                for sc in sub_chunks:
                    faq_chunks.append(sc)
                    faq_num_lists.append([fnum])
            else:
                cur_entries.append(entry)
                cur_nums.append(fnum)

        if cur_entries:
            faq_chunks.append(f"{hdr}\n" + "\n".join(cur_entries))
            faq_num_lists.append(list(cur_nums))

        _emit(FAQ_SECTION, faq_chunks, faq_num_lists)

    return chunks


def chunk_all_schemes(schemes: list[EnrichedScheme]) -> list[SchemeChunk]:
    all_chunks: list[SchemeChunk] = []
    for scheme in schemes:
        all_chunks.extend(chunk_scheme(scheme))
    return all_chunks
