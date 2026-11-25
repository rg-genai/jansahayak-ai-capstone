"""Score the saved gold-set runs (eval/reports/gold_runs/*.json) and write eval/reports/gold_eval.{json,md}.

ROUGE-L, BLEU and BERTScore are computed locally from the saved answers (no API keys). The LLM judge (Gemini)
runs only with --judge and a hard --judge-max-calls cap; its scores are cached in gold_runs/judge_scores.json,
so an answer is never judged twice and reviewers can re-read the saved verdicts without a key.

    python eval/score_gold_eval.py                                     # local metrics only
    python eval/score_gold_eval.py --judge --judge-max-calls 60 --judge-configs main
    python eval/score_gold_eval.py --no-bertscore                      # quick run without the BERTScore model
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
from pydantic import BaseModel, Field
from rouge_score import rouge_scorer
from sacrebleu.metrics import BLEU

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.agent.prompts import ANSWER_JUDGE_SYSTEM_PROMPT
from backend.agent.tools import parse_and_repair_json
from backend.config import get_settings
from backend.db.repositories import now_ist_iso
from backend.gateway.llm_client import LLMGateway, QuotaExhaustedError, get_gemini_gateway
from eval.eval_stats import paired_bootstrap_diff, paired_outcome_test
from eval.run_gold_eval import CONFIGS, RETRIEVAL_ONLY_FILE, RUNS_DIR

logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("score_gold_eval")

REPORT_DIR = PROJECT_ROOT / "eval" / "reports"
JUDGE_CACHE_FILE = "judge_scores.json"
BERTSCORE_MODEL = "roberta-large"  # bert-score's default for English; scores rescaled with its shipped baseline
MAIN_CONFIG = "main"
JUDGE_MAX_TOKENS = 1024  # ceiling only; Gemini's hidden reasoning can count against it and cut the JSON off
JUDGE_CORRECT_MIN_SCORE = 4  # judge score at or above this counts as a correct answer
LATENCY_PERCENTILE = 95

_CITATION_RE = re.compile(r"\[\d+(?:\s*,\s*\d+)*\]")
_URL_RE = re.compile(r"https?://\S+")
_MARKDOWN_RE = re.compile(r"[*_#`>|]+")
_BULLET_RE = re.compile(r"^\s*(?:[-•]|\d+\.)\s+", re.MULTILINE)
_SPACE_RE = re.compile(r"\s+")


class JudgeVerdict(BaseModel):
    """The judge's grade for one answer."""

    score: int = Field(ge=1, le=5)
    reason: str = ""


def clean_answer(text: str) -> str:
    """Plain text for text-overlap metrics: no citation markers, links, markdown or bullets."""
    text = _CITATION_RE.sub("", text or "")
    text = _URL_RE.sub("", text)
    text = _BULLET_RE.sub("", text)
    text = _MARKDOWN_RE.sub("", text)
    return _SPACE_RE.sub(" ", text).strip()


def text_overlap_scores(answer: str, reference: str, scorer: rouge_scorer.RougeScorer, bleu: BLEU) -> dict[str, float]:
    """ROUGE-L F1 (0-1) and sentence BLEU (0-100) of one cleaned answer against its reference."""
    hyp = clean_answer(answer)
    return {"rouge_l": round(scorer.score(reference, hyp)["rougeL"].fmeasure, 4),
            "bleu": round(bleu.sentence_score(hyp, [reference]).score, 2)}


def bertscore_f1(answers: list[str], references: list[str]) -> list[float]:
    """Rescaled BERTScore F1 for each pair (local model, downloaded once)."""
    from bert_score import score  # heavy import, only when needed

    _, _, f1 = score([clean_answer(a) for a in answers], references, model_type=BERTSCORE_MODEL, lang="en",
                     rescale_with_baseline=True, verbose=False)
    return [round(float(x), 4) for x in f1]


def load_runs(runs_dir: Path = RUNS_DIR) -> dict[str, dict[str, Any]]:
    """{config name: run} for every saved run of a known configuration."""
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(runs_dir.glob("*.json"))
            if p.stem in CONFIGS}


def answer_key(config: str, item_id: str, answer: str) -> str:
    return f"{config}:{item_id}:{hashlib.sha256(answer.encode('utf-8')).hexdigest()[:12]}"


def build_judge_messages(record: dict[str, Any]) -> list[dict[str, str]]:
    user = (f"Question: {record['question']}\n\nREFERENCE answer: {record['reference_answer']}\n\n"
            f"Assistant's answer:\n{record['answer']}\n\nOutput ONLY the JSON.")
    return [{"role": "system", "content": ANSWER_JUDGE_SYSTEM_PROMPT}, {"role": "user", "content": user}]


async def judge_runs(runs: dict[str, dict[str, Any]], configs: list[str], max_calls: int, cache_path: Path,
                     llm: LLMGateway) -> dict[str, dict[str, Any]]:
    """Judge not-yet-judged answers of `configs`, at most `max_calls` calls. Saves the cache after each verdict."""
    cache: dict[str, dict[str, Any]] = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    calls = 0
    for config in configs:
        for item_id, record in sorted(runs.get(config, {}).get("results", {}).items()):
            key = answer_key(config, item_id, record.get("answer", ""))
            if record.get("status") == "error" or key in cache:
                continue
            if calls >= max_calls:
                print(f"Judge call cap ({max_calls}) reached; re-run to continue.")
                return cache
            calls += 1
            try:
                resp = await llm.chat_completion(build_judge_messages(record), max_tokens=JUDGE_MAX_TOKENS,
                                                 temperature=0.0)
                verdict, _ = await parse_and_repair_json(resp.content, JudgeVerdict, allow_llm_repair=False)
            except QuotaExhaustedError as exc:  # every later call would fail too: stop and keep what is judged
                print(f"Judge stopped at call {calls}: quota used up. {exc}")
                return cache
            except Exception as exc:  # leave it unjudged; it is retried next time
                logger.warning("Judge failed on %s/%s: %s", config, item_id, exc)
                continue
            if verdict is None:
                logger.warning("Unparseable judge output for %s/%s", config, item_id)
                continue
            cache[key] = {**verdict.model_dump(), "judge_model": llm.model, "judged_at": now_ist_iso()}
            cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"[judge {calls}/{max_calls}] {config} {item_id}: {verdict.score}", flush=True)
    return cache


def score_records(runs: dict[str, dict[str, Any]], judge_cache: dict[str, dict[str, Any]],
                  use_bertscore: bool) -> dict[str, dict[str, dict[str, Any]]]:
    """{config: {item id: record + metric fields}} for every answered (non-error) record."""
    scorer, bleu = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=True), BLEU(effective_order=True)
    scored: dict[str, dict[str, dict[str, Any]]] = {}
    for config, run in runs.items():
        ok = {i: r for i, r in run["results"].items() if r.get("status") != "error"}
        rows = {i: {**r, **text_overlap_scores(r["answer"], r["reference_answer"], scorer, bleu)} for i, r in ok.items()}
        if use_bertscore and rows:
            ids = sorted(rows)
            for i, f1 in zip(ids, bertscore_f1([rows[i]["answer"] for i in ids], [rows[i]["reference_answer"] for i in ids])):
                rows[i]["bertscore_f1"] = f1
        for i, row in rows.items():
            verdict = judge_cache.get(answer_key(config, i, row["answer"]))
            row["judge_score"] = verdict["score"] if verdict else None
        scored[config] = rows
    return scored


def _mean(values: list[float]) -> float | None:
    return round(float(np.mean(values)), 4) if values else None


def summarize(rows: dict[str, dict[str, Any]], errors: int = 0) -> dict[str, Any]:
    """Averages for one configuration over the given records."""
    recs = list(rows.values())
    judged = [r["judge_score"] for r in recs if r.get("judge_score") is not None]
    ranks = [r.get("gold_scheme_rank") for r in recs if r.get("chunks_given")]
    total = [r["total_ms"] for r in recs if r.get("total_ms") is not None]
    return {
        "n": len(recs),
        "errors": errors,
        "status": dict(Counter(r["status"] for r in recs)),
        "rouge_l": _mean([r["rouge_l"] for r in recs]),
        "bleu": _mean([r["bleu"] for r in recs]),
        "bertscore_f1": _mean([r["bertscore_f1"] for r in recs if "bertscore_f1" in r]),
        "judge_n": len(judged),
        "judge_mean": _mean(judged),
        "judge_correct_rate": _mean([float(s >= JUDGE_CORRECT_MIN_SCORE) for s in judged]),
        "gold_scheme_in_context": _mean([float(rank is not None) for rank in ranks]),
        "avg_chunks_given": _mean([r.get("chunks_given", 0) for r in recs]),
        "retrieval_ms_avg": _mean([r.get("retrieval_ms", 0.0) for r in recs]),
        "answer_ms_avg": _mean([r.get("answer_ms", 0.0) for r in recs]),
        "planning_ms_avg": _mean([r.get("planning_ms", 0.0) for r in recs]),
        "total_ms_avg": _mean(total),
        "total_ms_p95": round(float(np.percentile(total, LATENCY_PERCENTILE)), 1) if total else None,
        "tokens_avg": _mean([r.get("prompt_tokens", 0) + r.get("completion_tokens", 0) for r in recs]),
        "web_fallback_skipped_rate": _mean([float(bool(r.get("web_fallback_skipped"))) for r in recs]),
    }


def summarize_retrieval(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Hit@1/3/5, MRR, source-section hit and latency per retriever from the retrieval-only run."""
    out: dict[str, dict[str, Any]] = {}
    for mode, rows in data["modes"].items():
        ranks = [r["gold_scheme_rank"] for r in rows]
        out[mode] = {
            "n": len(rows),
            **{f"hit@{k}": _mean([float(r is not None and r <= k) for r in ranks]) for k in (1, 3, 5)},
            "mrr": _mean([1.0 / r if r else 0.0 for r in ranks]),
            "source_section_hit@5": _mean([float(r["source_section_hit"]) for r in rows]),
            "latency_ms_avg": _mean([r["latency_ms"] for r in rows]),
        }
    return out


def judge_significance(rows: dict[str, dict[str, Any]], main_rows: dict[str, dict[str, Any]],
                       common: list[str]) -> dict[str, Any]:
    """Paired tests on questions both configs have judge scores for: McNemar on 'correct', bootstrap on the score."""
    both = [i for i in common if rows[i].get("judge_score") is not None and main_rows[i].get("judge_score") is not None]
    if not both:
        return {}
    config_scores = [float(rows[i]["judge_score"]) for i in both]
    main_scores = [float(main_rows[i]["judge_score"]) for i in both]
    return {"judge_correct_test": paired_outcome_test([s >= JUDGE_CORRECT_MIN_SCORE for s in config_scores],
                                                      [s >= JUDGE_CORRECT_MIN_SCORE for s in main_scores]),
            "judge_score_diff": paired_bootstrap_diff(config_scores, main_scores)}


def build_report(runs: dict[str, dict[str, Any]], scored: dict[str, dict[str, dict[str, Any]]],
                 retrieval: dict[str, Any] | None) -> dict[str, Any]:
    """Per-config summaries, same-question comparisons against the main pipeline, and the retriever table."""
    configs = {
        name: {"description": CONFIGS[name].description, "model": runs[name]["meta"].get("model"),
               **summarize(rows, sum(1 for r in runs[name]["results"].values() if r.get("status") == "error"))}
        for name, rows in scored.items()
    }
    paired: dict[str, Any] = {}
    main_rows = scored.get(MAIN_CONFIG, {})
    for name, rows in scored.items():
        common = sorted(set(rows) & set(main_rows))
        if name != MAIN_CONFIG and common:
            paired[name] = {"n": len(common), name: summarize({i: rows[i] for i in common}),
                            MAIN_CONFIG: summarize({i: main_rows[i] for i in common}),
                            **judge_significance(rows, main_rows, common)}
    return {"created_at": now_ist_iso(), "bertscore_model": BERTSCORE_MODEL,
            "judge_model": get_settings().gemini_judge_model, "configs": configs,
            "paired_with_main": paired, "retrieval_only": summarize_retrieval(retrieval) if retrieval else None}


def _fmt(value: Any, pct: bool = False, ms: bool = False) -> str:
    if value is None:
        return "-"
    if pct:
        return f"{value * 100:.1f}%"
    if ms:
        return f"{value / 1000:.2f}s"
    return f"{value:.3f}" if isinstance(value, float) else str(value)


def render_markdown(report: dict[str, Any], gold_meta: dict[str, Any]) -> str:
    """The report tables in Markdown."""
    counts = gold_meta.get("counts", {})
    lines = [
        "# Gold Q&A Evaluation",
        "",
        f"- Gold set: {counts.get('items', '?')} questions written from scheme text (not the FAQs); "
        f"review status {counts.get('by_review_status', {})}.",
        "- Every run: FAQ chunks excluded from retrieval; live web fallback disabled (noted per answer).",
        f"- ROUGE-L F1 and BLEU on answers with citations/links/markdown removed; BERTScore F1 = `{report['bertscore_model']}`, "
        f"rescaled. Judge = `{report['judge_model']}` (1-5; correct = score >= {JUDGE_CORRECT_MIN_SCORE}).",
        "",
        "## Answer quality",
        "",
        "| Config | Model | n | ROUGE-L | BLEU | BERTScore | Judge (1-5) | Judge correct | Gold scheme in context |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, c in report["configs"].items():
        lines.append(f"| `{name}` | {c['model']} | {c['n']} | {_fmt(c['rouge_l'])} | {_fmt(c['bleu'])} | "
                     f"{_fmt(c['bertscore_f1'])} | {_fmt(c['judge_mean'])} (n={c['judge_n']}) | "
                     f"{_fmt(c['judge_correct_rate'], pct=True)} | {_fmt(c['gold_scheme_in_context'], pct=True)} |")
    lines += ["", "## Latency and cost", "",
              "| Config | Retrieval | Planning | Answer writing | Total (avg) | Total (p95) | Tokens | Web fallback skipped |",
              "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for name, c in report["configs"].items():
        lines.append(f"| `{name}` | {_fmt(c['retrieval_ms_avg'], ms=True)} | {_fmt(c['planning_ms_avg'], ms=True)} | "
                     f"{_fmt(c['answer_ms_avg'], ms=True)} | {_fmt(c['total_ms_avg'], ms=True)} | "
                     f"{_fmt(c['total_ms_p95'], ms=True)} | {c['tokens_avg'] or 0:.0f} | "
                     f"{_fmt(c['web_fallback_skipped_rate'], pct=True)} |")
    if report["paired_with_main"]:
        lines += ["", "## Compared with the main pipeline on the same questions", "",
                  "| Config | n | ROUGE-L (config / main) | BERTScore (config / main) | Judge (config / main) |",
                  "|---|---:|---:|---:|---:|"]
        for name, p in report["paired_with_main"].items():
            a, b = p[name], p[MAIN_CONFIG]
            lines.append(f"| `{name}` | {p['n']} | {_fmt(a['rouge_l'])} / {_fmt(b['rouge_l'])} | "
                         f"{_fmt(a['bertscore_f1'])} / {_fmt(b['bertscore_f1'])} | "
                         f"{_fmt(a['judge_mean'])} / {_fmt(b['judge_mean'])} |")
        tested = {name: p for name, p in report["paired_with_main"].items() if p.get("judge_correct_test")}
        if tested:
            lines += ["", "### Is the difference real? (paired tests on questions both configs were judged on)", "",
                      "| Config | n | Only config correct | Only main correct | McNemar p | "
                      "Judge score diff (config - main), 95% CI |",
                      "|---|---:|---:|---:|---:|---|"]
            for name, p in tested.items():
                t, d = p["judge_correct_test"], p["judge_score_diff"]
                lines.append(f"| `{name}` | {t['n']} | {t['only_a']} | {t['only_b']} | {t['p_value']} | "
                             f"{d['mean_diff']:+.2f} ({d['ci_low']:+.2f} to {d['ci_high']:+.2f}) |")
    if report["retrieval_only"]:
        lines += ["", "## Retrievers on the gold questions (no LLM)", "",
                  "| Retriever | n | Hit@1 | Hit@3 | Hit@5 | MRR | Source section in top 5 | Avg latency |",
                  "|---|---:|---:|---:|---:|---:|---:|---:|"]
        for mode, r in report["retrieval_only"].items():
            lines.append(f"| `{mode}` | {r['n']} | {_fmt(r['hit@1'], pct=True)} | {_fmt(r['hit@3'], pct=True)} | "
                         f"{_fmt(r['hit@5'], pct=True)} | {_fmt(r['mrr'])} | {_fmt(r['source_section_hit@5'], pct=True)} | "
                         f"{r['latency_ms_avg'] or 0:.0f} ms |")
    lines += ["", "## Answer status counts", ""]
    lines += [f"- `{name}`: {c['status']} (errors excluded: {c['errors']})" for name, c in report["configs"].items()]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--no-bertscore", action="store_true", help="Skip BERTScore (no model download)")
    parser.add_argument("--judge", action="store_true", help="Call the Gemini judge for unjudged answers")
    parser.add_argument("--judge-max-calls", type=int, default=0, help="Hard cap on judge calls this run")
    parser.add_argument("--judge-configs", default=MAIN_CONFIG, help="Comma-separated configs to judge")
    args = parser.parse_args()

    runs = load_runs()
    if not runs:
        parser.error(f"No runs in {RUNS_DIR}: run eval/run_gold_eval.py first")
    cache_path = RUNS_DIR / JUDGE_CACHE_FILE
    if args.judge:
        if args.judge_max_calls <= 0:
            parser.error("--judge needs --judge-max-calls N (free-tier key: set an explicit cap)")
        configs = [c.strip() for c in args.judge_configs.split(",") if c.strip()]
        judge = get_gemini_gateway(get_settings().gemini_judge_model)
        asyncio.run(judge_runs(runs, configs, args.judge_max_calls, cache_path, judge))
    judge_cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}

    scored = score_records(runs, judge_cache, use_bertscore=not args.no_bertscore)
    retrieval_path = RUNS_DIR / RETRIEVAL_ONLY_FILE
    retrieval = json.loads(retrieval_path.read_text(encoding="utf-8")) if retrieval_path.exists() else None
    report = build_report(runs, scored, retrieval)
    gold_meta = json.loads((PROJECT_ROOT / "eval" / "gold_qa.json").read_text(encoding="utf-8"))["meta"]
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "gold_eval.json").write_text(
        json.dumps({**report, "per_answer": scored}, ensure_ascii=False, indent=2), encoding="utf-8")
    (REPORT_DIR / "gold_eval.md").write_text(render_markdown(report, gold_meta), encoding="utf-8")
    print(f"Wrote {REPORT_DIR / 'gold_eval.md'} and gold_eval.json")


if __name__ == "__main__":
    main()
