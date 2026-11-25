"""Failure taxonomy: why each failed task or wrong gold answer failed, in the four Track B categories.

Every failure gets exactly ONE category: the first stage of the pipeline that went wrong, checked in this order.
1. tool_call_error  - the pipeline raised, the planner's JSON could not be repaired, a tool call failed or was cut by
                      the step cap, the task's required tool was never called, or it was called with wrong arguments.
2. retrieval_miss   - the scheme the task is about never reached the answer writer's evidence.
3. hallucination    - the answer states something its evidence does not support (grounding judge).
4. reasoning_error  - the right tools ran and the right evidence was there, nothing was invented, but the outcome was
                      still wrong (wrong eligibility verdict, answered from the wrong scheme, asked back instead of
                      answering, refused a valid request, incomplete answer, ...).

Sources: the task-suite runs (failed = not completed, see eval/score_task_eval.py) and the gold Q&A runs (failed =
gold judge score below 4). Only runs saved with agent diagnostics are classified.

Hallucination vs reasoning error needs the grounding judge (Gemini, free tier): it runs only with --judge and a hard
--judge-max-calls cap, and shares its cache with the task scorer. Failures still waiting for a verdict are reported
as pending, not guessed.

Because the classifier is automatic, a fixed sample is written to eval/failure_audit.csv for a person to label;
once labelled, the report shows how often the classifier agreed with the person (accuracy and Cohen's kappa).
The audit file is never overwritten.

    python eval/failure_taxonomy.py
    python eval/failure_taxonomy.py --judge --judge-max-calls 50
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import random
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.config import get_settings
from backend.db.repositories import now_ist_iso
from backend.gateway.llm_client import get_gemini_gateway
from eval.eval_stats import cohen_kappa
from eval.grounding_judge import GroundingVerdict, cached_verdict, judge_grounding, load_cache, record_grounding_key
from eval.run_gold_eval import RUNS_DIR as GOLD_RUNS_DIR
from eval.run_task_eval import load_tasks
from eval.score_gold_eval import JUDGE_CACHE_FILE, JUDGE_CORRECT_MIN_SCORE, answer_key, load_runs
from eval.score_task_eval import (
    FAILED_TOOL_STATUSES,
    GROUNDING_CACHE_PATH,
    TaskKind,
    accepted_verdicts,
    checked_verdicts,
    grade_runs,
    grounding_requests,
    load_corrections,
    load_task_runs,
    reached_schemes,
    task_kind,
    was_refused,
    with_corrections,
)

REPORT_DIR = PROJECT_ROOT / "eval" / "reports"
AUDIT_PATH = PROJECT_ROOT / "eval" / "failure_audit.csv"
GOLD_SUITE = "gold"
TASK_SUITE = "task"
# Configurations whose failures are classified (production agent and its no-loop ablation, in both suites).
CLASSIFIED_CONFIGS = {TASK_SUITE: ("loop", "single_pass", "loop_after_elig_fix", "single_pass_after_elig_fix",
                                   "loop_v2", "single_pass_v2"),
                      GOLD_SUITE: ("main", "single_pass")}
AUDIT_CONFIGS = {TASK_SUITE: "loop", GOLD_SUITE: "main"}  # the human audit samples the production agent
AUDIT_SAMPLE_SIZE = 20
AUDIT_SEED = 20261125
AUDIT_ANSWER_CHARS = 600
EXAMPLES_PER_SUBTYPE = 3

Category = Literal["tool_call_error", "retrieval_miss", "hallucination", "reasoning_error"]
CATEGORIES: tuple[Category, ...] = ("tool_call_error", "retrieval_miss", "hallucination", "reasoning_error")
REQUIRED_TOOL: dict[str, str | None] = {"info": "search_schemes", "eligibility": "check_eligibility",
                                        "draft_grievance": "draft_grievance",
                                        "track_grievance": "submit_or_track_grievance", "refusal": None}
AUDIT_FIELDS = ["suite", "config", "item_id", "request", "answer", "auto_category", "auto_subtype", "auto_detail",
                "human_category", "human_notes"]


@dataclass(frozen=True)
class FailureLabel:
    """The single root cause assigned to one failure."""

    category: Category
    subtype: str
    detail: str = ""


def _tools_called(record: dict[str, Any]) -> set[str]:
    return {t.get("tool") for t in record.get("tool_log") or []}


def _execution_failure(record: dict[str, Any]) -> FailureLabel | None:
    """Stage 1a: the run raised, the planner's JSON could not be repaired, or a tool call failed."""
    if record.get("status") == "error":
        return FailureLabel("tool_call_error", "pipeline_exception", str(record.get("error", ""))[:200])
    if record.get("planner_status") == "degraded":
        return FailureLabel("tool_call_error", "malformed_planner_json", "planner JSON could not be repaired")
    failed = [t for t in record.get("tool_log") or [] if t.get("status") in FAILED_TOOL_STATUSES]
    if failed:
        return FailureLabel("tool_call_error", str(failed[0]["status"]),
                            f"{failed[0].get('tool')}: {failed[0].get('error') or failed[0]['status']}")
    return None


def _deliberate_non_answer(kind: TaskKind, record: dict[str, Any]) -> FailureLabel | None:
    """A decision not to do the task (refusing a valid request, or asking back before using any tool).

    Checked before the required-tool rule: no tool ran because the agent decided not to act, which is a reasoning
    error, not a tool-call error.
    """
    if kind != "refusal" and was_refused(record):
        return FailureLabel("reasoning_error", "refused_valid_request",
                            f"status {record.get('status')}, guardrail {record.get('guardrail_category')}")
    if record.get("status") == "awaiting_user_input" and not record.get("tool_log"):
        return FailureLabel("reasoning_error", "asked_instead_of_answering", "asked a question before using any tool")
    return None


def _tool_choice_failure(kind: TaskKind, record: dict[str, Any], gold_ministry: str | None) -> FailureLabel | None:
    """Stage 1b: the task's required tool was never called, or was called with wrong arguments."""
    required = REQUIRED_TOOL[kind]
    if required and required not in _tools_called(record):
        return FailureLabel("tool_call_error", "required_tool_not_called",
                            f"needed {required}; called {sorted(_tools_called(record)) or 'no tools'}")
    draft = record.get("grievance_draft") or {}
    if kind == "draft_grievance" and gold_ministry and draft.get("ministry_code") != gold_ministry:
        return FailureLabel("tool_call_error", "wrong_tool_arguments",
                            f"draft addressed to {draft.get('ministry_code')}, expected {gold_ministry}")
    return None


def _reasoning_subtype(kind: TaskKind, record: dict[str, Any], gold_slug: str | None, gold_verdict: str | None,
                       verdict: GroundingVerdict | None) -> FailureLabel:
    """Stage 4: right tools and evidence, nothing invented, outcome still wrong. Which way was it wrong?"""
    if kind == "eligibility":
        verdicts = checked_verdicts(record)
        got = verdicts.get(gold_slug or "")
        if got is None:
            return FailureLabel("reasoning_error", "checked_wrong_scheme", f"checked {sorted(verdicts)}")
        return FailureLabel("reasoning_error", "wrong_eligibility_verdict", f"got {got}, expected {gold_verdict}")
    if kind == "draft_grievance":
        if (record.get("grievance_receipt") or {}).get("registration_number"):
            return FailureLabel("reasoning_error", "submitted_without_confirmation", "a grievance was submitted")
        return FailureLabel("reasoning_error", "no_confirmation_pause", "agent did not pause for the citizen")
    if kind == "track_grievance":
        return FailureLabel("reasoning_error", "tracked_wrong_ticket", "tracking call did not use the requested ticket")
    if kind == "refusal":
        return FailureLabel("reasoning_error", "did_not_refuse", verdict.reason if verdict else "")
    if record.get("status") == "awaiting_user_input":
        return FailureLabel("reasoning_error", "asked_instead_of_answering", "ended the turn with a question")
    if gold_slug and gold_slug not in (record.get("cited_schemes") or []):
        return FailureLabel("reasoning_error", "answered_from_wrong_scheme",
                            f"cited {record.get('cited_schemes') or 'nothing'}, gold {gold_slug}")
    if verdict and not verdict.answers_request:
        return FailureLabel("reasoning_error", "did_not_answer", verdict.reason)
    return FailureLabel("reasoning_error", "incomplete_or_wrong_answer", verdict.reason if verdict else "")


def classify_failure(kind: TaskKind, record: dict[str, Any], *, gold_slug: str | None = None,
                     gold_verdict: str | None = None, gold_ministry: str | None = None,
                     verdict: GroundingVerdict | None = None, judge_needed: bool = True) -> FailureLabel | None:
    """Root cause of one failure, or None while a needed grounding verdict is missing."""
    early = (_execution_failure(record) or _deliberate_non_answer(kind, record)
             or _tool_choice_failure(kind, record, gold_ministry))
    if early:
        return early
    if gold_slug and gold_slug not in reached_schemes(record):
        return FailureLabel("retrieval_miss", "gold_scheme_not_retrieved",
                            f"evidence schemes {record.get('retrieved_schemes') or 'none'}")
    if judge_needed and verdict is None:
        return None
    if verdict and not verdict.grounded:
        return FailureLabel("hallucination", "unsupported_claims", "; ".join(verdict.unsupported_claims)[:300])
    return _reasoning_subtype(kind, record, gold_slug, gold_verdict, verdict)


def _has_diagnostics(run: dict[str, Any]) -> bool:
    """Runs saved before the diagnostics fields existed cannot be classified."""
    results = [r for r in run.get("results", {}).values() if r.get("status") != "error"]
    return bool(results) and all("tool_log" in r for r in results)


def task_failures(cache: dict[str, dict[str, Any]], max_tool_calls: int) -> list[dict[str, Any]]:
    """Every not-completed task in the classified task configs, with its label (None = pending judge).

    Graded with the documented answer-key corrections, so a task is only counted as failed when it really failed.
    """
    raw_tasks = load_tasks()
    tasks = {t["id"]: t for t in with_corrections(raw_tasks, load_corrections(raw_tasks))}
    runs = {n: r for n, r in load_task_runs().items() if n in CLASSIFIED_CONFIGS[TASK_SUITE] and _has_diagnostics(r)}
    out: list[dict[str, Any]] = []
    for config, rows in grade_runs(list(tasks.values()), runs, cache, max_tool_calls).items():
        for task_id, row in sorted(rows.items()):
            if row["outcome"]["completed"] is not False:
                continue
            task = tasks[task_id]
            kind = task_kind(task)
            verdict = GroundingVerdict.model_validate(row["grounding_verdict"]) if row["grounding_verdict"] else None
            judge_needed = kind == "info" or (kind == "refusal" and not was_refused(row))
            label = classify_failure(kind, row, gold_slug=task.get("gold_scheme_slug"),
                                     gold_verdict=" or ".join(str(v) for v in accepted_verdicts(task)),
                                     gold_ministry=task.get("gold_ministry_code"),
                                     verdict=verdict, judge_needed=judge_needed)
            out.append({"suite": TASK_SUITE, "config": config, "item_id": task_id, "kind": kind,
                        "category_tag": task["category"], "request": task["query"], "answer": row.get("answer", ""),
                        "label": asdict(label) if label else None})
    return out


def gold_failed(record: dict[str, Any], judge_cache: dict[str, dict[str, Any]], config: str, item_id: str) -> bool | None:
    """A gold answer failed if it errored or the gold judge scored it below the 'correct' bar; None if unjudged."""
    if record.get("status") == "error":
        return True
    verdict = judge_cache.get(answer_key(config, item_id, record.get("answer", "")))
    return None if verdict is None else verdict["score"] < JUDGE_CORRECT_MIN_SCORE


def gold_failure_runs() -> dict[str, dict[str, Any]]:
    return {n: r for n, r in load_runs().items() if n in CLASSIFIED_CONFIGS[GOLD_SUITE] and _has_diagnostics(r)}


def gold_failures(cache: dict[str, dict[str, Any]], judge_cache: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Every failed gold answer with its label, and how many answers still lack a gold judge score."""
    out: list[dict[str, Any]] = []
    unjudged = 0
    for config, run in gold_failure_runs().items():
        for item_id, rec in sorted(run["results"].items()):
            failed = gold_failed(rec, judge_cache, config, item_id)
            if failed is None:
                unjudged += 1
            if not failed:
                continue
            verdict = cached_verdict(cache, record_grounding_key(GOLD_SUITE, config, item_id, rec))
            label = classify_failure("info", rec, gold_slug=rec.get("scheme_slug"), verdict=verdict)
            out.append({"suite": GOLD_SUITE, "config": config, "item_id": item_id, "kind": "info",
                        "category_tag": rec.get("aspect"), "request": rec.get("question", ""),
                        "answer": rec.get("answer", ""), "label": asdict(label) if label else None})
    return out, unjudged


async def judge_gold_failures(judge_cache: dict[str, dict[str, Any]], max_calls: int) -> None:
    """Grounding verdicts for gold failures that reach the hallucination-vs-reasoning stage."""
    runs = gold_failure_runs()
    items = list({i: {"id": i, "question": r.get("question", "")}
                  for run in runs.values() for i, r in run["results"].items()}.values())

    def wanted(config: str, item: dict[str, Any], rec: dict[str, Any]) -> bool:
        # Failed, and passed the tool and retrieval stages: only the judge can tell hallucination from reasoning.
        return bool(gold_failed(rec, judge_cache, config, item["id"])) \
            and classify_failure("info", rec, gold_slug=rec.get("scheme_slug"), verdict=None) is None

    requests = grounding_requests(items, runs, get_settings().db_abs_path, suite=GOLD_SUITE,
                                  request_of=lambda t: t["question"], wanted=wanted)
    await judge_grounding(requests, GROUNDING_CACHE_PATH, max_calls, get_gemini_gateway(get_settings().gemini_judge_model))


def summarize(failures: list[dict[str, Any]]) -> dict[str, Any]:
    """Counts per (suite, config): categories, subtypes, pending, and a few examples per subtype."""
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for f in failures:
        groups[f"{f['suite']}/{f['config']}"].append(f)
    out: dict[str, Any] = {}
    for key, rows in sorted(groups.items()):
        labelled = [r for r in rows if r["label"]]
        examples: dict[str, list[str]] = defaultdict(list)
        for r in labelled:
            sub = f"{r['label']['category']}/{r['label']['subtype']}"
            if len(examples[sub]) < EXAMPLES_PER_SUBTYPE:
                examples[sub].append(f"{r['item_id']}: {r['label']['detail']}"[:200])
        out[key] = {"failures": len(rows), "pending_judge": len(rows) - len(labelled),
                    "by_category": {c: sum(1 for r in labelled if r["label"]["category"] == c) for c in CATEGORIES},
                    "by_subtype": dict(Counter(f"{r['label']['category']}/{r['label']['subtype']}" for r in labelled)
                                       .most_common()),
                    "examples": dict(examples)}
    return out


def audit_sample(failures: list[dict[str, Any]]) -> list[dict[str, str]]:
    """A fixed, category-balanced sample of the production agent's labelled failures for a person to check."""
    pool = [f for f in failures if f["label"] and AUDIT_CONFIGS[f["suite"]] == f["config"]]
    rng = random.Random(AUDIT_SEED)
    by_cat: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for f in sorted(pool, key=lambda f: (f["suite"], f["item_id"])):
        by_cat[f["label"]["category"]].append(f)
    for rows in by_cat.values():
        rng.shuffle(rows)
    picked: list[dict[str, Any]] = []
    while len(picked) < AUDIT_SAMPLE_SIZE and any(by_cat.values()):
        for cat in CATEGORIES:
            if by_cat.get(cat) and len(picked) < AUDIT_SAMPLE_SIZE:
                picked.append(by_cat[cat].pop())
    return [{"suite": f["suite"], "config": f["config"], "item_id": f["item_id"], "request": f["request"],
             "answer": f["answer"][:AUDIT_ANSWER_CHARS], "auto_category": f["label"]["category"],
             "auto_subtype": f["label"]["subtype"], "auto_detail": f["label"]["detail"], "human_category": "",
             "human_notes": ""} for f in picked]


def audit_agreement(rows: list[dict[str, str]]) -> dict[str, Any]:
    """How often the classifier agreed with the human labels filled in so far."""
    done = [r for r in rows if (r.get("human_category") or "").strip()]
    unknown = sorted({r["human_category"].strip() for r in done} - set(CATEGORIES))
    if unknown:
        raise ValueError(f"Unknown human_category values in {AUDIT_PATH.name}: {unknown}; use one of {CATEGORIES}")
    auto, human = [r["auto_category"] for r in done], [r["human_category"].strip() for r in done]
    kappa = cohen_kappa(auto, human)
    return {"sampled": len(rows), "labelled": len(done),
            "accuracy": round(sum(a == h for a, h in zip(auto, human)) / len(done), 4) if done else None,
            "cohen_kappa": round(kappa, 4) if kappa is not None else None}


def read_or_create_audit(failures: list[dict[str, Any]], path: Path = AUDIT_PATH) -> list[dict[str, str]]:
    """The audit sheet; created once from the current failures and never overwritten (people may have filled it)."""
    if path.exists():
        with path.open(encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))
    rows = audit_sample(failures)
    if rows:
        with path.open("w", encoding="utf-8-sig", newline="") as f:  # BOM so Excel shows Indic text correctly
            writer = csv.DictWriter(f, fieldnames=AUDIT_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        print(f"Wrote the audit sheet {path} ({len(rows)} rows): fill in human_category with one of {CATEGORIES}")
    return rows


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Failure Taxonomy",
        "",
        "Each failure gets ONE root cause: the first pipeline stage that went wrong, checked in the order "
        "tool-call error -> retrieval miss -> hallucination -> reasoning error (see `eval/failure_taxonomy.py`).",
        "",
        "- `task/*`: tasks not completed in the 80-task suite (`eval/score_task_eval.py`).",
        f"- `gold/*`: gold Q&A answers the judge scored below {JUDGE_CORRECT_MIN_SCORE}/5"
        + (f" ({report['gold_unjudged']} answers not yet judged)." if report["gold_unjudged"] else "."),
        f"- Hallucination is decided by the grounding judge `{report['judge_model']}` against the exact evidence the "
        "answer was written from.",
        "",
        "## Root causes",
        "",
        "| Run | Failures | " + " | ".join(CATEGORIES) + " | Pending judge |",
        "|---|---:|" + "---:|" * len(CATEGORIES) + "---:|",
    ]
    for key, s in report["summary"].items():
        lines.append(f"| `{key}` | {s['failures']} | " + " | ".join(str(s["by_category"][c]) for c in CATEGORIES)
                     + f" | {s['pending_judge']} |")
    lines += ["", "## Subtypes and examples", ""]
    for key, s in report["summary"].items():
        lines += [f"### `{key}`", ""]
        for sub, n in s["by_subtype"].items():
            lines.append(f"- **{sub}** ({n})")
            lines += [f"  - {e}" for e in s["examples"].get(sub, [])]
        lines.append("")
    a = report["audit"]
    lines += ["## Human audit of the classifier", ""]
    if a["labelled"]:
        lines.append(f"- {a['labelled']} of {a['sampled']} sampled failures labelled by a person: agreement "
                     f"{a['accuracy'] * 100:.0f}%, Cohen's kappa {a['cohen_kappa']}.")
    else:
        lines.append(f"- {a['sampled']} failures sampled into `eval/failure_audit.csv`; not labelled yet.")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--judge", action="store_true", help="Judge gold failures that need a grounding verdict")
    parser.add_argument("--judge-max-calls", type=int, default=0, help="Hard cap on judge calls this run")
    args = parser.parse_args()
    settings = get_settings()
    judge_cache = load_cache(GOLD_RUNS_DIR / JUDGE_CACHE_FILE)
    if args.judge:
        if args.judge_max_calls <= 0:
            parser.error("--judge needs --judge-max-calls N (free-tier key: set an explicit cap)")
        asyncio.run(judge_gold_failures(judge_cache, args.judge_max_calls))
    cache = load_cache(GROUNDING_CACHE_PATH)
    failures = task_failures(cache, settings.agent_max_tool_calls)
    gold, gold_unjudged = gold_failures(cache, judge_cache)
    failures += gold
    report = {"created_at": now_ist_iso(), "judge_model": settings.gemini_judge_model, "gold_unjudged": gold_unjudged,
              "summary": summarize(failures), "audit": audit_agreement(read_or_create_audit(failures))}
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "failure_taxonomy.json").write_text(
        json.dumps({**report, "failures": failures}, ensure_ascii=False, indent=2), encoding="utf-8")
    (REPORT_DIR / "failure_taxonomy.md").write_text(render_markdown(report), encoding="utf-8")
    print(f"Wrote {REPORT_DIR / 'failure_taxonomy.md'} and failure_taxonomy.json")


if __name__ == "__main__":
    main()
