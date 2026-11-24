"""Run the gold Q&A set (eval/gold_qa.json) through the system under named configurations and save every answer.

This is the GENERATION step. Scores come from eval/score_gold_eval.py, which reads the saved answers, so
ROUGE-L / BLEU / BERTScore can be recomputed by anyone without API keys.

Fixed for every configuration, so runs are comparable and reproducible:
- FAQ chunks are excluded from retrieval (the gold set must not be answerable from the scheme FAQs).
- The live .gov.in web fallback is disabled (live search results change between runs, and BM25-only retrieval has
  no relevance score, so the fallback would fire on every BM25 question). Each record notes when it would have run.

Calls the hosted Qwen VM (and Gemini for the gemini* configs): run only with the team's agreement.
Resumable: questions already answered under a configuration are skipped; failed ones are retried.

    python eval/run_gold_eval.py --list
    python eval/run_gold_eval.py --config main
    python eval/run_gold_eval.py --config top1 --subset 30
    python eval/run_gold_eval.py --retrieval-only        # BM25 vs dense vs hybrid ranking (embedding API only, no LLM)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterator, Literal

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.agent.graph import JanSahayakAgent
from backend.agent.prompts import CLOSED_BOOK_SYSTEM_PROMPT
from backend.agent.tools import AgentToolbox, WebSearchGovInput
from backend.config import get_settings
from backend.db.repositories import now_ist_iso
from backend.gateway.llm_client import LLMGateway, get_gemini_gateway, get_llm_gateway
from backend.retrieval.hybrid_retriever import HybridRetriever, RetrievalMode

logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("run_gold_eval")

GOLD_QA_PATH = PROJECT_ROOT / "eval" / "gold_qa.json"
RUNS_DIR = PROJECT_ROOT / "eval" / "reports" / "gold_runs"
RETRIEVAL_ONLY_FILE = "retrieval_only.json"
CLOSED_BOOK_MAX_TOKENS = 300
CLOSED_BOOK_TEMPERATURE = 0.1
RETRIEVAL_ONLY_TOP_K = 5
RETRIEVAL_ONLY_MODES: tuple[RetrievalMode, ...] = ("bm25", "dense", "hybrid_rrf", "hybrid_rerank")
# Which retrieval chunk section holds each gold aspect's source text (see backend/retrieval/chunker.py).
ASPECT_CHUNK_SECTION = {
    "benefits": "overview_benefits",
    "eligibility": "eligibility_exclusions",
    "documents_required": "process_documents",
    "application_process": "process_documents",
}


@dataclass(frozen=True)
class EvalConfig:
    """One system variant to evaluate."""

    name: str
    description: str
    kind: Literal["agent", "closed_book"] = "agent"
    llm: Literal["qwen", "gemini"] = "qwen"
    retrieval_mode: RetrievalMode = "hybrid_rerank"
    top_k: int | None = None  # None = the live chatbot's retrieval depth
    reflection: bool = True


CONFIGS: dict[str, EvalConfig] = {c.name: c for c in [
    EvalConfig("main", "Full pipeline: agent loop + hybrid BM25/dense/RRF + reranker (live settings)"),
    EvalConfig("main_before_guards", "Main pipeline before the two gold-eval guards (archived 24 Nov run of `main`)"),
    EvalConfig("single_pass","Same, without the Reflector loop (one retrieval pass)", reflection=False),
    EvalConfig("top1", "Main pipeline, answer sees 1 retrieved chunk", top_k=1),
    EvalConfig("top3", "Main pipeline, answer sees 3 retrieved chunks", top_k=3),
    EvalConfig("top5", "Main pipeline, answer sees 5 retrieved chunks", top_k=5),
    EvalConfig("bm25", "Main pipeline with BM25-only retrieval", retrieval_mode="bm25"),
    EvalConfig("dense", "Main pipeline with dense-only retrieval (bge-small-en-v1.5)", retrieval_mode="dense"),
    EvalConfig("hybrid_rrf", "Main pipeline with hybrid RRF, no reranker", retrieval_mode="hybrid_rrf"),
    EvalConfig("no_corpus", "Qwen alone, no documents (closed-book baseline)", kind="closed_book"),
    EvalConfig("gemini", "Main pipeline with Gemini as the LLM", llm="gemini"),
    EvalConfig("gemini_no_corpus", "Gemini alone, no documents (closed-book baseline)", kind="closed_book", llm="gemini"),
]}


class NoWebToolbox(AgentToolbox):
    """The live web fallback is disabled in evals; the agent still logs when it would have searched."""

    async def web_search_gov_schemes(self, args: WebSearchGovInput) -> dict[str, Any]:
        return {"results": [], "provider": "disabled_for_eval"}


@contextmanager
def eval_settings(config: EvalConfig) -> Iterator[None]:
    """Apply a configuration's settings for the duration of a run, then restore them."""
    settings = get_settings()
    wanted = {"agent_reflection_enabled": config.reflection, "retrieval_top_k_override": config.top_k,
              "retrieval_exclude_faq_chunks": True}
    saved = {key: getattr(settings, key) for key in wanted}
    for key, value in wanted.items():
        setattr(settings, key, value)
    try:
        yield
    finally:
        for key, value in saved.items():
            setattr(settings, key, value)


def llm_for(config: EvalConfig) -> LLMGateway:
    return get_gemini_gateway(get_settings().gemini_model) if config.llm == "gemini" else get_llm_gateway()


def select_items(items: list[dict[str, Any]], subset: int | None = None) -> list[dict[str, Any]]:
    """Gold items not dropped in review; with `subset`, a fixed sample taking aspects in turn (same every run)."""
    usable = sorted((i for i in items if i["review"]["status"] != "dropped"), key=lambda i: i["id"])
    if not subset or subset >= len(usable):
        return usable
    by_aspect: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in usable:
        by_aspect[item["aspect"]].append(item)
    picked: list[dict[str, Any]] = []
    while len(picked) < subset:
        for aspect in sorted(by_aspect):
            if by_aspect[aspect] and len(picked) < subset:
                picked.append(by_aspect[aspect].pop(0))
    return sorted(picked, key=lambda i: i["id"])


def gold_rank(slugs: list[str], gold_slug: str) -> int | None:
    """1-based rank of the gold scheme among the distinct retrieved schemes, or None if missing."""
    distinct = list(dict.fromkeys(slugs))
    return distinct.index(gold_slug) + 1 if gold_slug in distinct else None


def record_from_state(state: dict[str, Any], item: dict[str, Any], total_ms: float) -> dict[str, Any]:
    """The answer plus everything needed for the retrieval, latency and cost tables."""
    logs = state.get("tool_calls_log") or []
    searches = [t for t in logs if t.get("tool") == "search_schemes"]
    lat = state.get("step_latencies") or {}
    slugs = [c.get("scheme_slug", "") for c in state.get("retrieved_chunks") or []]
    return {
        "answer": state.get("final_answer") or "",
        "status": state.get("status") or "ok",
        "retrieved_schemes": list(dict.fromkeys(slugs)),
        "chunks_given": len(slugs),
        "gold_scheme_rank": gold_rank(slugs, item["scheme_slug"]),
        "retrieval_ms": round(sum(float(t.get("latency_ms") or 0.0) for t in searches), 1),
        "answer_ms": round(float(lat.get("synthesizer_ms", 0.0)) + float(lat.get("critic_ms", 0.0)), 1),
        "planning_ms": round(float(lat.get("planner_ms", 0.0)) + float(lat.get("reflector_ms", 0.0)), 1),
        "total_ms": round(total_ms, 1),
        "prompt_tokens": int(state.get("prompt_tokens") or 0),
        "completion_tokens": int(state.get("completion_tokens") or 0),
        "tool_calls": len(logs),
        "search_calls": len(searches),
        "reflection_rounds": len(state.get("reflections") or []),
        "web_fallback_skipped": any(t.get("tool") == "web_search_gov_schemes" for t in logs),
    }


async def answer_with_agent(agent: JanSahayakAgent, item: dict[str, Any]) -> dict[str, Any]:
    t0 = time.perf_counter()
    state = await agent.run(item["question"], session_id=f"eval-{item['id']}")
    return record_from_state(state, item, (time.perf_counter() - t0) * 1000.0)


async def answer_closed_book(llm: LLMGateway, item: dict[str, Any]) -> dict[str, Any]:
    resp = await llm.chat_completion(
        [{"role": "system", "content": CLOSED_BOOK_SYSTEM_PROMPT}, {"role": "user", "content": item["question"]}],
        max_tokens=CLOSED_BOOK_MAX_TOKENS,
        temperature=CLOSED_BOOK_TEMPERATURE,
        disable_thinking=True,
    )
    return {"answer": resp.content, "status": "ok", "retrieved_schemes": [], "chunks_given": 0,
            "gold_scheme_rank": None, "retrieval_ms": 0.0, "answer_ms": resp.latency_ms, "planning_ms": 0.0,
            "total_ms": resp.latency_ms, "prompt_tokens": resp.prompt_tokens,
            "completion_tokens": resp.completion_tokens, "tool_calls": 0, "search_calls": 0,
            "reflection_rounds": 0, "web_fallback_skipped": False}


def run_path(config_name: str, runs_dir: Path = RUNS_DIR) -> Path:
    return runs_dir / f"{config_name}.json"


def load_run(path: Path, config: EvalConfig, model: str) -> dict[str, Any]:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"meta": {**asdict(config), "model": model, "faq_chunks_excluded": True, "web_fallback": "disabled",
                     "started_at": now_ist_iso()}, "results": {}}


def save_run(run: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    run["meta"]["updated_at"] = now_ist_iso()
    path.write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding="utf-8")


async def run_config(config: EvalConfig, items: list[dict[str, Any]], runs_dir: Path = RUNS_DIR,
                     llm: LLMGateway | None = None, retriever: HybridRetriever | None = None) -> dict[str, Any]:
    """Answer every item under `config`, saving after each. Already-answered items are skipped."""
    llm = llm or llm_for(config)
    path = run_path(config.name, runs_dir)
    run = load_run(path, config, llm.model)
    # Not answered yet, or failed last time.
    todo = [i for i in items if run["results"].get(i["id"], {}).get("status", "error") == "error"]
    with eval_settings(config):
        agent = None
        if config.kind == "agent":
            retriever = retriever or HybridRetriever(exclude_faq_chunks=True)
            toolbox = NoWebToolbox(retriever=retriever, retrieval_mode=config.retrieval_mode)
            agent = JanSahayakAgent(llm=llm, toolbox=toolbox)
        t_start = time.perf_counter()
        for n, item in enumerate(todo, start=1):
            base = {"question": item["question"], "reference_answer": item["reference_answer"],
                    "aspect": item["aspect"], "scheme_slug": item["scheme_slug"]}
            try:
                record = await (answer_with_agent(agent, item) if agent else answer_closed_book(llm, item))
            except Exception as exc:  # one failure must not stop the run; it is retried on the next run
                logger.warning("%s failed on %s: %s", config.name, item["id"], exc)
                record = {"status": "error", "error": str(exc)[:300], "answer": ""}
            run["results"][item["id"]] = {**base, **record}
            save_run(run, path)
            elapsed = time.perf_counter() - t_start
            eta_min = elapsed / n * (len(todo) - n) / 60
            print(f"[{config.name}] {n}/{len(todo)} {item['id']} {record['status']:<20} "
                  f"{record.get('total_ms', 0) / 1000:5.1f}s | ETA {eta_min:.0f} min", flush=True)
    save_run(run, path)
    errors = sum(1 for r in run["results"].values() if r["status"] == "error")
    print(f"\n{config.name}: {len(run['results'])} answered ({errors} errors) -> {path}")
    return run


def retrieval_only(items: list[dict[str, Any]], retriever: HybridRetriever, runs_dir: Path = RUNS_DIR) -> dict[str, Any]:
    """Rank the gold scheme with each retriever on the same questions (FAQ chunks excluded). No LLM calls."""
    per_mode: dict[str, list[dict[str, Any]]] = {m: [] for m in RETRIEVAL_ONLY_MODES}
    for item in items:
        q_emb = retriever.embedding_client.embed_texts_sync([item["question"]], use_cache=True)[0]
        section = ASPECT_CHUNK_SECTION.get(item["aspect"])
        for mode in RETRIEVAL_ONLY_MODES:
            out = retriever.search_sync(item["question"], top_k=RETRIEVAL_ONLY_TOP_K, mode=mode, query_embedding=q_emb)
            per_mode[mode].append({
                "id": item["id"],
                "gold_scheme_rank": gold_rank([r.scheme_slug for r in out.results], item["scheme_slug"]),
                "source_section_hit": any(r.scheme_slug == item["scheme_slug"] and r.section == section
                                          for r in out.results),
                "latency_ms": out.latency_ms,
            })
    result = {"meta": {"top_k": RETRIEVAL_ONLY_TOP_K, "faq_chunks_excluded": True, "questions": len(items),
                       "created_at": now_ist_iso()}, "modes": per_mode}
    runs_dir.mkdir(parents=True, exist_ok=True)
    (runs_dir / RETRIEVAL_ONLY_FILE).write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--list", action="store_true", help="Show the available configurations")
    action.add_argument("--config", choices=sorted(CONFIGS), help="Configuration to run")
    action.add_argument("--retrieval-only", action="store_true", help="Compare retrievers without the LLM")
    parser.add_argument("--subset", type=int, help="Use a fixed, aspect-balanced sample of this many questions")
    parser.add_argument("--gold", type=Path, default=GOLD_QA_PATH)
    args = parser.parse_args()

    if args.list:
        for c in CONFIGS.values():
            print(f"{c.name:<18} {c.description}")
        return
    if not args.gold.exists():
        parser.error(f"{args.gold} not found: build it with eval/build_gold_qa.py first")
    items = select_items(json.loads(args.gold.read_text(encoding="utf-8"))["items"], args.subset)
    print(f"{len(items)} gold questions")
    if args.retrieval_only:
        retriever = HybridRetriever(exclude_faq_chunks=True)
        retriever.load()
        retrieval_only(items, retriever)
        print(f"Saved {RUNS_DIR / RETRIEVAL_ONLY_FILE}")
    else:
        asyncio.run(run_config(CONFIGS[args.config], items))


if __name__ == "__main__":
    main()
