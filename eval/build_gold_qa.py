"""Build the gold Q&A dataset (eval/gold_qa.json): new questions with reference answers, written from scheme text.

The questions are NOT taken from the scheme FAQs. For each sampled scheme the hosted LLM drafts one question and a
short reference answer from ONE section of the scheme's official text (benefits, eligibility, documents or how to
apply). Code accepts a draft only if its supporting quote is really in that section, every number in the answer is
in the section, the question names the scheme, and the question is not too close to any of the scheme's FAQ
questions. Rejected drafts are kept with their reasons, so the filtering can be reported. People then check the
accepted pairs through a review sheet.

Calls the shared VM (one call per draft, plus at most one JSON repair): run only with the team's agreement.
Resumable: re-running continues until the target size is reached.

    python eval/build_gold_qa.py --dry-run --target 60     # show which schemes/sections would be used, no LLM
    python eval/build_gold_qa.py --target 5                # small trial
    python eval/build_gold_qa.py --target 60               # full dataset
    python eval/build_gold_qa.py --export-review           # write eval/gold_qa_review.csv for people to check
    python eval/build_gold_qa.py --apply-review            # copy the reviewers' ok / fix / drop into the dataset
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import logging
import math
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from rouge_score import rouge_scorer

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.agent.prompts import GOLD_QA_GENERATION_SYSTEM_PROMPT
from backend.agent.tools import parse_and_repair_json
from backend.db.repositories import Repository, now_ist_iso
from backend.gateway.llm_client import LLMGateway, get_llm_gateway
from backend.retrieval.criteria_extractor import quote_in_source

logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("build_gold_qa")

GOLD_QA_PATH = PROJECT_ROOT / "eval" / "gold_qa.json"
REVIEW_PATH = PROJECT_ROOT / "eval" / "gold_qa_review.csv"

# Scheme sections a question can be written from (schemes_catalog columns), with readable labels.
ASPECTS: dict[str, str] = {
    "benefits": "Benefits",
    "eligibility": "Eligibility",
    "documents_required": "Documents Required",
    "application_process": "Application Process",
}
DEFAULT_TARGET = 60
SAMPLING_SEED = 42  # fixed, so every run (and every resume) visits schemes in the same order
MIN_SECTION_CHARS = 200  # shorter sections rarely hold more than the FAQ already covers
MAX_SECTION_CHARS = 2500  # keeps each call small; the quote must come from this clipped text
MAX_ANSWER_WORDS = 80
MIN_QUOTE_WORDS = 5  # a 1-2 word "quote" matches almost any text and proves nothing
FAQ_SIMILARITY_MAX = 0.5  # ROUGE-L F1 vs the scheme's FAQ questions (scheme name removed); at or above = too close
MAX_OUTPUT_TOKENS = 300
GENERATION_TEMPERATURE = 0.2

REVIEW_COLUMNS = ["id", "scheme_name", "aspect", "question", "reference_answer", "evidence_quote",
                  "closest_faq", "faq_similarity", "verdict", "notes"]
REVIEW_STATUS = {"ok": "approved", "fix": "corrected", "drop": "dropped"}
RETRYABLE_REASONS = {"llm_error"}  # schemes rejected only for these are tried again on the next run

_NORMALIZE_RE = re.compile(r"[^a-z0-9]+")
_NUMBER_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


class GoldQADraft(BaseModel):
    """One LLM-drafted question with its reference answer and supporting quote."""

    question: str = Field(min_length=10)
    answer: str = Field(min_length=5)
    evidence_quote: str = ""


def prompt_version() -> str:
    """Short hash of the generation prompt, stored with the dataset so drafts can be traced to a prompt."""
    return hashlib.sha256(GOLD_QA_GENERATION_SYSTEM_PROMPT.encode("utf-8")).hexdigest()[:12]


def _normalize(text: str) -> str:
    return _NORMALIZE_RE.sub(" ", (text or "").lower()).strip()


def _numbers_in(text: str) -> set[str]:
    """Every number in the text, written the same way: '6,000' -> '6000', '1.50' -> '1.5'."""
    out: set[str] = set()
    for raw in _NUMBER_RE.findall(text or ""):
        value = raw.replace(",", "")
        if "." in value:
            value = value.rstrip("0").rstrip(".")
        out.add(value)
    return out


def section_text(scheme: dict[str, Any], aspect: str) -> str:
    """The scheme's text for one aspect, clipped to what the model is shown."""
    return (scheme.get(aspect) or "").strip()[:MAX_SECTION_CHARS]


def available_aspects(scheme: dict[str, Any]) -> list[str]:
    """Aspects whose section has enough text to write a specific question from."""
    return [a for a in ASPECTS if len((scheme.get(a) or "").strip()) >= MIN_SECTION_CHARS]


def order_schemes(schemes: list[dict[str, Any]], seed: int = SAMPLING_SEED) -> list[dict[str, Any]]:
    """Shuffle schemes with a fixed seed, then take one ministry at a time so the dataset covers many ministries."""
    rng = random.Random(seed)
    by_ministry: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for scheme in sorted(schemes, key=lambda s: s["slug"]):
        by_ministry[scheme.get("ministry_code") or ""].append(scheme)
    ministries = sorted(by_ministry)
    rng.shuffle(ministries)
    for bucket in by_ministry.values():
        rng.shuffle(bucket)
    ordered: list[dict[str, Any]] = []
    while any(by_ministry[m] for m in ministries):
        for ministry in ministries:
            if by_ministry[ministry]:
                ordered.append(by_ministry[ministry].pop())
    return ordered


def choose_aspect(scheme: dict[str, Any], counts: Counter[str], quota: int) -> str | None:
    """The scheme's usable aspect with the fewest accepted questions so far, skipping aspects at their quota."""
    open_aspects = [a for a in available_aspects(scheme) if counts[a] < quota]
    if not open_aspects:
        return None
    return min(open_aspects, key=lambda a: (counts[a], list(ASPECTS).index(a)))


def _without_scheme_name(text: str, scheme: dict[str, Any]) -> str:
    out = f" {_normalize(text)} "
    for name in (scheme.get("scheme_name"), scheme.get("short_title")):
        name_norm = _normalize(name or "")
        if name_norm:
            out = out.replace(f" {name_norm} ", " ")
    return out.strip()


def closest_faq(question: str, faq_questions: list[str], scheme: dict[str, Any],
                scorer: rouge_scorer.RougeScorer) -> tuple[str, float]:
    """(most similar FAQ question, ROUGE-L F1). The scheme name is removed first so it does not inflate the score."""
    candidate = _without_scheme_name(question, scheme)
    best_faq, best = "", 0.0
    for faq in faq_questions:
        score = scorer.score(_without_scheme_name(faq, scheme), candidate)["rougeL"].fmeasure
        if score > best:
            best_faq, best = faq, score
    return best_faq, round(best, 3)


def names_scheme(question: str, scheme: dict[str, Any]) -> bool:
    """True if the question contains the scheme's full name or its short title."""
    padded = f" {_normalize(question)} "
    return any(
        _normalize(name or "") and f" {_normalize(name)} " in padded
        for name in (scheme.get("scheme_name"), scheme.get("short_title"))
    )


def rejection_reasons(draft: GoldQADraft, scheme: dict[str, Any], section: str, faq_similarity: float) -> list[str]:
    """Why a draft cannot be used as gold (empty list = accepted)."""
    reasons: list[str] = []
    if not names_scheme(draft.question, scheme):
        reasons.append("question_missing_scheme_name")
    if len(draft.evidence_quote.split()) < MIN_QUOTE_WORDS or not quote_in_source(draft.evidence_quote, section):
        reasons.append("quote_not_in_section")
    invented = _numbers_in(draft.answer) - _numbers_in(f"{section} {scheme.get('scheme_name', '')}")
    if invented:
        reasons.append(f"numbers_not_in_section:{','.join(sorted(invented))}")
    if len(draft.answer.split()) > MAX_ANSWER_WORDS:
        reasons.append("answer_too_long")
    if faq_similarity >= FAQ_SIMILARITY_MAX:
        reasons.append("too_close_to_faq")
    return reasons


def build_messages(scheme: dict[str, Any], aspect: str, section: str, faq_questions: list[str]) -> list[dict[str, str]]:
    """Chat messages asking the model for one question/answer pair from one section."""
    faqs = "\n".join(f"- {q}" for q in faq_questions) or "(none)"
    user = (
        f"Scheme Name: {scheme['scheme_name']}\n"
        f"Section: {ASPECTS[aspect]}\n"
        f"Section Text:\n{section}\n\n"
        f"Existing FAQs (do not repeat or rephrase these):\n{faqs}\n\n"
        "Output ONLY the JSON."
    )
    return [{"role": "system", "content": GOLD_QA_GENERATION_SYSTEM_PROMPT}, {"role": "user", "content": user}]


async def draft_qa(scheme: dict[str, Any], aspect: str, section: str, faq_questions: list[str],
                   llm: LLMGateway) -> tuple[GoldQADraft | None, dict[str, Any]]:
    """Ask the LLM for one draft. Returns (draft or None if unparseable, diagnostics)."""
    resp = await llm.chat_completion(
        messages=build_messages(scheme, aspect, section, faq_questions),
        max_tokens=MAX_OUTPUT_TOKENS,
        temperature=GENERATION_TEMPERATURE,
        disable_thinking=True,
    )
    draft, diag = await parse_and_repair_json(resp.content, GoldQADraft, llm=llm)
    diag.update({"tokens": resp.prompt_tokens + resp.completion_tokens, "latency_ms": resp.latency_ms,
                 "model": resp.model})
    return draft, diag


def new_dataset() -> dict[str, Any]:
    return {
        "meta": {
            "description": "Gold Q&A pairs written from scheme text (not from the FAQs), with reference answers.",
            "created_at": now_ist_iso(),
            "prompt_version": prompt_version(),
            "sampling_seed": SAMPLING_SEED,
            "thresholds": {"min_section_chars": MIN_SECTION_CHARS, "max_section_chars": MAX_SECTION_CHARS,
                           "max_answer_words": MAX_ANSWER_WORDS, "min_quote_words": MIN_QUOTE_WORDS,
                           "faq_similarity_max": FAQ_SIMILARITY_MAX},
        },
        "items": [],
        "rejected": [],
    }


def load_dataset(path: Path) -> dict[str, Any]:
    """The saved dataset, or a new empty one if the file does not exist yet."""
    if not path.exists():
        return new_dataset()
    return json.loads(path.read_text(encoding="utf-8"))


def save_dataset(dataset: dict[str, Any], path: Path) -> None:
    dataset["meta"]["updated_at"] = now_ist_iso()
    dataset["meta"]["counts"] = {
        "items": len(dataset["items"]),
        "by_aspect": dict(Counter(i["aspect"] for i in dataset["items"])),
        "by_review_status": dict(Counter(i["review"]["status"] for i in dataset["items"])),
        "rejected": len(dataset["rejected"]),
        "rejected_by_reason": dict(Counter(r.split(":")[0] for x in dataset["rejected"] for r in x["reasons"])),
    }
    path.write_text(json.dumps(dataset, ensure_ascii=False, indent=2), encoding="utf-8")


def attempted_slugs(dataset: dict[str, Any]) -> set[str]:
    """Schemes already used or rejected (rejections that are worth retrying are left out)."""
    done = {i["scheme_slug"] for i in dataset["items"]}
    done |= {r["scheme_slug"] for r in dataset["rejected"] if not set(r["reasons"]) <= RETRYABLE_REASONS}
    return done


async def build(target: int, out_path: Path, max_calls: int, llm: LLMGateway, repo: Repository) -> dict[str, Any]:
    """Draft and check pairs until `target` are accepted or `max_calls` drafts were requested. Saves after each."""
    dataset = load_dataset(out_path)
    quota = math.ceil(target / len(ASPECTS))
    counts: Counter[str] = Counter(i["aspect"] for i in dataset["items"])
    done = attempted_slugs(dataset)
    scorer = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=True)
    calls = 0
    for scheme in order_schemes(repo.list_all_schemes()):
        if len(dataset["items"]) >= target or calls >= max_calls:
            break
        aspect = None if scheme["slug"] in done else choose_aspect(scheme, counts, quota)
        if aspect is None:
            continue
        section = section_text(scheme, aspect)
        faq_questions = [f["question"] for f in repo.get_scheme_faqs(scheme["slug"])]
        calls += 1
        base = {"scheme_slug": scheme["slug"], "scheme_name": scheme["scheme_name"], "aspect": aspect}
        dataset["rejected"] = [r for r in dataset["rejected"] if r["scheme_slug"] != scheme["slug"]]
        try:
            draft, diag = await draft_qa(scheme, aspect, section, faq_questions, llm)
        except Exception as exc:  # one failed call must not stop the batch; the scheme is retried next run
            logger.warning("Draft failed for %s: %s", scheme["slug"], exc)
            dataset["rejected"].append({**base, "reasons": ["llm_error"], "error": str(exc)[:300]})
            save_dataset(dataset, out_path)
            continue
        if draft is None:
            dataset["rejected"].append({**base, "reasons": ["unparseable"], "diagnostics": diag})
            status = "UNPARSEABLE"
        else:
            faq, similarity = closest_faq(draft.question, faq_questions, scheme, scorer)
            reasons = rejection_reasons(draft, scheme, section, similarity)
            record = {**base, "question": draft.question, "reference_answer": draft.answer,
                      "evidence_quote": draft.evidence_quote, "closest_faq": faq, "faq_similarity": similarity}
            if reasons:
                dataset["rejected"].append({**record, "reasons": reasons})
                status = "rejected: " + ", ".join(reasons)
            else:
                dataset["items"].append({
                    "id": f"GQA-{len(dataset['items']) + 1:03d}", **record,
                    "ministry_code": scheme.get("ministry_code", ""), "source_section": ASPECTS[aspect],
                    "source_url": scheme.get("source_url", ""), "generator_model": diag.get("model", llm.model),
                    "review": {"status": "unreviewed", "notes": ""},
                })
                counts[aspect] += 1
                status = "ok"
        save_dataset(dataset, out_path)
        print(f"[{len(dataset['items'])}/{target}] call {calls}: {scheme['slug']:<30} {aspect:<20} {status}", flush=True)
    save_dataset(dataset, out_path)
    print(f"\nAccepted {len(dataset['items'])} | rejected {len(dataset['rejected'])} | "
          f"by reason {dataset['meta']['counts']['rejected_by_reason']} | saved to {out_path}")
    return dataset


def dry_run(target: int, repo: Repository) -> list[tuple[str, str, str]]:
    """(slug, ministry, aspect) for the first `target` picks if every draft were accepted. No LLM calls."""
    quota = math.ceil(target / len(ASPECTS))
    counts: Counter[str] = Counter()
    picks: list[tuple[str, str, str]] = []
    for scheme in order_schemes(repo.list_all_schemes()):
        if len(picks) >= target:
            break
        aspect = choose_aspect(scheme, counts, quota)
        if aspect:
            counts[aspect] += 1
            picks.append((scheme["slug"], scheme.get("ministry_code", ""), aspect))
    return picks


def export_review(dataset: dict[str, Any], csv_path: Path) -> int:
    """Write the accepted pairs to a CSV people can fill in (verdict: ok / fix / drop). Returns rows written."""
    verdict_of = {status: verdict for verdict, status in REVIEW_STATUS.items()}
    with csv_path.open("w", encoding="utf-8-sig", newline="") as fh:  # BOM so Excel shows â‚¹ and Hindi correctly
        writer = csv.DictWriter(fh, fieldnames=REVIEW_COLUMNS)
        writer.writeheader()
        for item in dataset["items"]:
            writer.writerow({
                **{k: item.get(k, "") for k in REVIEW_COLUMNS if k in item},
                "aspect": ASPECTS.get(item["aspect"], item["aspect"]),
                "verdict": verdict_of.get(item["review"]["status"], ""),
                "notes": item["review"].get("notes", ""),
            })
    return len(dataset["items"])


def apply_review(dataset: dict[str, Any], csv_path: Path) -> Counter[str]:
    """Copy reviewer verdicts into the dataset. 'fix' rows replace the question/answer with the reviewer's text."""
    items = {i["id"]: i for i in dataset["items"]}
    with csv_path.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    unknown = [r["id"] for r in rows if r["id"] not in items]
    invalid = [r["id"] for r in rows if (r.get("verdict") or "").strip().lower() not in {"", *REVIEW_STATUS}]
    if unknown or invalid:
        raise ValueError(f"Review sheet problems: unknown ids {unknown}, invalid verdicts on {invalid} "
                         f"(use one of {sorted(REVIEW_STATUS)} or leave empty)")
    applied: Counter[str] = Counter()
    for row in rows:
        verdict = (row.get("verdict") or "").strip().lower()
        if not verdict:
            continue
        item = items[row["id"]]
        if verdict == "fix":
            item["review"].setdefault("original_question", item["question"])
            item["review"].setdefault("original_answer", item["reference_answer"])
            item["question"], item["reference_answer"] = row["question"].strip(), row["reference_answer"].strip()
        item["review"].update({"status": REVIEW_STATUS[verdict], "notes": (row.get("notes") or "").strip(),
                               "reviewed_at": now_ist_iso()})
        applied[verdict] += 1
    return applied


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--dry-run", action="store_true", help="Show the schemes and sections that would be used")
    action.add_argument("--export-review", action="store_true", help=f"Write {REVIEW_PATH.name} for reviewers")
    action.add_argument("--apply-review", action="store_true", help=f"Apply verdicts from {REVIEW_PATH.name}")
    parser.add_argument("--target", type=int, default=DEFAULT_TARGET, help="Number of accepted pairs wanted")
    parser.add_argument("--max-calls", type=int, help="Stop after this many drafts (default: 2 x target)")
    parser.add_argument("--out", type=Path, default=GOLD_QA_PATH)
    parser.add_argument("--review-csv", type=Path, default=REVIEW_PATH)
    args = parser.parse_args()
    if args.target < 1:
        parser.error("--target must be at least 1")

    repo = Repository()
    if args.dry_run:
        picks = dry_run(args.target, repo)
        for slug, ministry, aspect in picks:
            print(f"{slug:<35} {ministry:<10} {aspect}")
        print(f"\n{len(picks)} schemes from {len({m for _, m, _ in picks})} ministries | "
              f"by aspect {dict(Counter(a for _, _, a in picks))}")
    elif args.export_review:
        rows = export_review(load_dataset(args.out), args.review_csv)
        print(f"Wrote {rows} rows to {args.review_csv}")
    elif args.apply_review:
        dataset = load_dataset(args.out)
        applied = apply_review(dataset, args.review_csv)
        save_dataset(dataset, args.out)
        print(f"Applied {dict(applied)} | review status now {dataset['meta']['counts']['by_review_status']}")
    else:
        max_calls = args.max_calls or 2 * args.target
        asyncio.run(build(args.target, args.out, max_calls, get_llm_gateway(), repo))


if __name__ == "__main__":
    main()
