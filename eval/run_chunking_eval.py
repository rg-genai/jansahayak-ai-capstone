"""Chunking experiments: how the scheme text is cut into chunks changes what retrieval can find.

Each strategy re-chunks the official text of all 649 schemes, builds a TEMPORARY hybrid index in memory (BM25 +
bge-small-en-v1.5 embeddings) and runs the same queries through every retriever. The production index in
`data/index` is never read for writing and never changed.

Strategies differ only in how the three official-text sections are chunked; FAQ chunks are identical in every
strategy (and excluded for the gold questions anyway), so differences come from the chunking alone.
- size sweep at ~8% overlap: 440 tokens (production), 256, 128
- 440 tokens without overlap
- 440-token fixed windows that ignore section boundaries

Two query sets:
- gold Q&A (60 questions written from scheme text, FAQ chunks excluded): Hit@k for the right scheme, plus EVIDENCE
  hit@5 = the gold evidence sentence appears (>= EVIDENCE_COVERAGE_MIN of it, contiguous) inside one top-5 chunk.
  This is fair to every strategy because it does not depend on section labels.
- the 73 scheme-specific queries of the task suite (FAQ chunks included, as in the live system): Hit@k and MRR.

Calls the hosted EMBEDDING model only (no LLM). Chunk texts already in the production index reuse its vectors;
new texts are embedded once and cached in data/eval_cache/, so a re-run costs nothing.

    python eval/run_chunking_eval.py
    python eval/run_chunking_eval.py --strategies section_440_ov35,fixed_440_ov35 --no-rerank
"""

from __future__ import annotations

import argparse
import difflib
import json
import logging
import re
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
from rank_bm25 import BM25Okapi

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.config import get_settings
from backend.db.database import get_connection
from backend.db.repositories import now_ist_iso
from backend.gateway.embedding_client import EmbeddingClient
from backend.retrieval.chunker import (
    DEFAULT_OVERLAP_WORDS,
    MAX_SAFE_TOKENS,
    SchemeChunk,
    build_chunks,
    chunk_faqs,
    scheme_sections,
    section_header,
    split_body_with_header,
)
from backend.retrieval.etl import EnrichedScheme, load_and_enrich_schemes
from backend.retrieval.hybrid_retriever import HybridRetriever, RetrievalMode
from eval.eval_stats import paired_outcome_test, wilson_interval
from eval.run_gold_eval import GOLD_QA_PATH, gold_rank, select_items
from eval.run_task_eval import TASK_SET_PATH
from scripts.ingest_data import build_bm25_doc_tokens

logger = logging.getLogger("run_chunking_eval")

REPORT_DIR = PROJECT_ROOT / "eval" / "reports"
EVAL_CACHE_DB_NAME = "chunking_embeddings.db"
TOP_K = 5
HIT_KS = (1, 3, 5)
MODES: tuple[RetrievalMode, ...] = ("bm25", "dense", "hybrid_rrf", "hybrid_rerank")
PRODUCTION_MODE: RetrievalMode = "hybrid_rerank"
EVIDENCE_COVERAGE_MIN = 0.8  # share of the gold evidence sentence that must appear contiguously in one chunk
FIXED_WINDOW_SECTION = "fixed_window"
_WORD_RE = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class ChunkingStrategy:
    """One way of cutting the official scheme text into chunks."""

    name: str
    description: str
    max_tokens: int
    overlap_words: int
    section_aware: bool = True


BASELINE = ChunkingStrategy("section_440_ov35", "Production: section-aware, 440 tokens, 35-word overlap",
                            MAX_SAFE_TOKENS, DEFAULT_OVERLAP_WORDS)
STRATEGIES: dict[str, ChunkingStrategy] = {s.name: s for s in [
    BASELINE,
    ChunkingStrategy("section_256_ov20", "Section-aware, 256 tokens, 20-word overlap", 256, 20),
    ChunkingStrategy("section_128_ov10", "Section-aware, 128 tokens, 10-word overlap", 128, 10),
    ChunkingStrategy("section_440_ov0", "Section-aware, 440 tokens, no overlap", MAX_SAFE_TOKENS, 0),
    ChunkingStrategy("fixed_440_ov35", "Fixed 440-token windows across section boundaries, 35-word overlap",
                     MAX_SAFE_TOKENS, DEFAULT_OVERLAP_WORDS, section_aware=False),
]}


def chunk_with_strategy(scheme: EnrichedScheme, strategy: ChunkingStrategy) -> list[SchemeChunk]:
    """One scheme's chunks under `strategy` (FAQ chunks always as in production)."""
    sections = scheme_sections(scheme)
    chunks: list[SchemeChunk] = []
    if strategy.section_aware:
        for section in sections:
            texts = split_body_with_header(section_header(scheme, section.title), section.body,
                                           max_tokens=strategy.max_tokens, overlap_words=strategy.overlap_words)
            chunks.extend(build_chunks(scheme, section.key, texts))
    elif sections:
        texts = split_body_with_header(section_header(scheme, None), "\n".join(s.body for s in sections),
                                       max_tokens=strategy.max_tokens, overlap_words=strategy.overlap_words)
        chunks.extend(build_chunks(scheme, FIXED_WINDOW_SECTION, texts))
    chunks.extend(chunk_faqs(scheme))
    return chunks


def chunk_record(chunk: SchemeChunk, idx: int) -> dict[str, Any]:
    """A chunk in the shape HybridRetriever keeps in memory (same fields as a `chunks_meta` row)."""
    return {"chunk_id": chunk.chunk_id, "vector_idx": idx, "scheme_slug": chunk.scheme_slug,
            "scheme_name": chunk.scheme_name, "ministry": chunk.ministry, "section": chunk.section,
            "faq_numbers": chunk.faq_numbers, "text": chunk.text, "token_count": chunk.token_count,
            "source_url": chunk.source_url, "metadata": chunk.metadata}


def production_vectors(db_path: Path, index_dir: Path) -> dict[str, np.ndarray]:
    """{chunk text: vector} from the production index, so unchanged chunks are never re-embedded."""
    with get_connection(db_path) as conn:
        texts = [r["text"] for r in conn.execute("SELECT text FROM chunks_meta ORDER BY vector_idx ASC")]
    vectors = np.load(str(index_dir / "embeddings.npy"))
    if len(texts) != len(vectors):
        raise RuntimeError(f"Production index mismatch: {len(texts)} chunks vs {len(vectors)} vectors")
    return dict(zip(texts, vectors))


def embed_chunks(chunks: list[SchemeChunk], known: dict[str, np.ndarray], client: EmbeddingClient) -> tuple[np.ndarray, int]:
    """Row-aligned embeddings for `chunks`; returns them and how many texts were not in the production index."""
    missing = list(dict.fromkeys(c.text for c in chunks if c.text not in known))
    if missing:
        print(f"  embedding {len(missing)} new chunk texts (cached in data/eval_cache) ...", flush=True)
        known.update(zip(missing, client.embed_texts_sync(missing, use_cache=True, progress_every=50)))
    return np.vstack([known[c.text] for c in chunks]).astype(np.float32), len(missing)


def build_index(strategy: ChunkingStrategy, schemes: list[EnrichedScheme], known: dict[str, np.ndarray],
                client: EmbeddingClient) -> tuple[list[dict[str, Any]], np.ndarray, BM25Okapi, dict[str, Any]]:
    """Chunks, embeddings and BM25 for one strategy, plus index statistics."""
    chunks = [c for scheme in schemes for c in chunk_with_strategy(scheme, strategy)]
    embeddings, newly_embedded = embed_chunks(chunks, known, client)
    bm25 = BM25Okapi([build_bm25_doc_tokens(c) for c in chunks])
    official = [c.token_count for c in chunks if c.section != "faq_group"]
    stats = {"chunks_total": len(chunks), "official_text_chunks": len(official),
             "official_tokens_avg": round(float(np.mean(official)), 1), "official_tokens_max": max(official),
             "newly_embedded": newly_embedded}
    return [chunk_record(c, i) for i, c in enumerate(chunks)], embeddings, bm25, stats


def _words(text: str) -> list[str]:
    return _WORD_RE.findall((text or "").lower())


def evidence_coverage(quote: str, chunk_text: str) -> float:
    """Longest contiguous run of the quote's words found in the chunk, as a share of the quote."""
    q, c = _words(quote), _words(chunk_text)
    if not q or not c:
        return 0.0
    match = difflib.SequenceMatcher(None, q, c, autojunk=False).find_longest_match(0, len(q), 0, len(c))
    return match.size / len(q)


def retriever_for(chunks: list[dict[str, Any]], embeddings: np.ndarray, bm25: BM25Okapi, exclude_faq: bool,
                  client: EmbeddingClient) -> HybridRetriever:
    retriever = HybridRetriever(embedding_client=client, exclude_faq_chunks=exclude_faq)
    retriever.load_from_memory(chunks, embeddings, bm25)
    return retriever


def score_queries(retriever: HybridRetriever, queries: list[dict[str, Any]], q_embs: np.ndarray,
                  modes: tuple[RetrievalMode, ...]) -> dict[str, list[dict[str, Any]]]:
    """Per mode, per query: rank of the gold scheme, evidence hit (when a quote is given), tokens shown, latency."""
    tokens_by_id = {c["chunk_id"]: int(c["token_count"]) for c in retriever.chunks}
    out: dict[str, list[dict[str, Any]]] = {m: [] for m in modes}
    for q, emb in zip(queries, q_embs):
        for mode in modes:
            res = retriever.search_sync(q["text"], top_k=TOP_K, mode=mode, query_embedding=emb)
            row: dict[str, Any] = {
                "id": q["id"],
                "gold_scheme_rank": gold_rank([r.scheme_slug for r in res.results], q["gold_slug"]),
                "context_tokens": sum(tokens_by_id.get(r.chunk_id, 0) for r in res.results),
                "latency_ms": res.latency_ms,
            }
            if q.get("evidence_quote"):
                row["evidence_hit"] = any(r.scheme_slug == q["gold_slug"]
                                          and evidence_coverage(q["evidence_quote"], r.text) >= EVIDENCE_COVERAGE_MIN
                                          for r in res.results)
            out[mode].append(row)
    return out


def _mean(values: list[float]) -> float | None:
    return round(float(np.mean(values)), 4) if values else None


def summarize_mode(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Hit@k, MRR, evidence hit@5 (with a Wilson interval), context size and latency for one retriever."""
    ranks = [r["gold_scheme_rank"] for r in rows]
    out: dict[str, Any] = {"n": len(rows),
                           **{f"hit@{k}": _mean([float(r is not None and r <= k) for r in ranks]) for k in HIT_KS},
                           "mrr": _mean([1.0 / r if r else 0.0 for r in ranks]),
                           "context_tokens_avg": _mean([r["context_tokens"] for r in rows]),
                           "latency_ms_avg": _mean([r["latency_ms"] for r in rows])}
    hits = [r["evidence_hit"] for r in rows if "evidence_hit" in r]
    if hits:
        low, high = wilson_interval(sum(hits), len(hits))
        out.update({"evidence_hit@5": _mean([float(h) for h in hits]), "evidence_ci": [round(low, 4), round(high, 4)]})
    return out


def _hit_at_top_k(row: dict[str, Any]) -> bool:
    return row["gold_scheme_rank"] is not None and row["gold_scheme_rank"] <= TOP_K


def compare_to_baseline(rows: list[dict[str, Any]], base_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Paired McNemar tests against the production chunking on the same queries."""
    base = {r["id"]: r for r in base_rows}
    common = [r for r in rows if r["id"] in base]
    out = {"hit@5": paired_outcome_test([_hit_at_top_k(r) for r in common],
                                        [_hit_at_top_k(base[r["id"]]) for r in common])}
    if common and "evidence_hit" in common[0]:
        out["evidence_hit@5"] = paired_outcome_test([r["evidence_hit"] for r in common],
                                                    [base[r["id"]]["evidence_hit"] for r in common])
    return out


def load_query_sets() -> dict[str, list[dict[str, Any]]]:
    """{set name: queries} with id, text, gold scheme and (gold set only) the evidence sentence."""
    gold = select_items(json.loads(GOLD_QA_PATH.read_text(encoding="utf-8"))["items"])
    tasks = json.loads(TASK_SET_PATH.read_text(encoding="utf-8"))
    return {
        "gold_qa": [{"id": i["id"], "text": i["question"], "gold_slug": i["scheme_slug"],
                     "evidence_quote": i.get("evidence_quote")} for i in gold],
        "task_queries": [{"id": t["id"], "text": t.get("query_en") or t["query"], "gold_slug": t["gold_scheme_slug"]}
                         for t in sorted(tasks, key=lambda t: t["id"]) if t.get("gold_scheme_slug")],
    }


# Gold answers must not come from the FAQs; the task queries mirror the live app (FAQs included).
QUERY_SET_EXCLUDES_FAQ = {"gold_qa": True, "task_queries": False}


def run_strategy(strategy: ChunkingStrategy, schemes: list[EnrichedScheme], known: dict[str, np.ndarray],
                 client: EmbeddingClient, query_sets: dict[str, list[dict[str, Any]]],
                 query_embs: dict[str, np.ndarray], modes: tuple[RetrievalMode, ...]) -> dict[str, Any]:
    """Build one strategy's temporary index and score every query set against it."""
    t0 = time.perf_counter()
    chunks, embeddings, bm25, stats = build_index(strategy, schemes, known, client)
    per_set = {}
    for set_name, queries in query_sets.items():
        retriever = retriever_for(chunks, embeddings, bm25, QUERY_SET_EXCLUDES_FAQ[set_name], client)
        per_set[set_name] = score_queries(retriever, queries, query_embs[set_name], modes)
    print(f"  {strategy.name}: {stats['official_text_chunks']} official-text chunks, done in "
          f"{time.perf_counter() - t0:.0f}s", flush=True)
    return {"strategy": asdict(strategy), "index": stats, "rows": per_set}


def build_report(results: dict[str, dict[str, Any]], reproduces_production: bool) -> dict[str, Any]:
    """Per strategy and query set: retriever summaries and paired tests against production."""
    summary: dict[str, Any] = {}
    for name, res in results.items():
        summary[name] = {"strategy": res["strategy"], "index": res["index"], "sets": {}}
        for set_name, by_mode in res["rows"].items():
            entry: dict[str, Any] = {mode: summarize_mode(rows) for mode, rows in by_mode.items()}
            if name != BASELINE.name and BASELINE.name in results:
                base_rows = results[BASELINE.name]["rows"][set_name]
                entry["vs_baseline"] = {mode: compare_to_baseline(rows, base_rows[mode])
                                        for mode, rows in by_mode.items() if mode in base_rows}
            summary[name]["sets"][set_name] = entry
    return {"created_at": now_ist_iso(), "top_k": TOP_K, "evidence_coverage_min": EVIDENCE_COVERAGE_MIN,
            "baseline": BASELINE.name, "baseline_reproduces_production_index": reproduces_production,
            "summary": summary}


def _pct(v: float | None) -> str:
    return "-" if v is None else f"{v * 100:.1f}%"


QUERY_SET_TITLES = {"gold_qa": "Gold Q&A questions (FAQ chunks excluded)",
                    "task_queries": "Task-suite scheme queries (FAQ chunks included, as live)"}


def _mode_table(summary: dict[str, Any], set_name: str, mode: str) -> list[str]:
    present = {name: s["sets"][set_name][mode] for name, s in summary.items() if mode in s["sets"].get(set_name, {})}
    if not present:
        return []
    evidence = any("evidence_hit@5" in m for m in present.values())
    cols = ["Strategy", "Hit@1", "Hit@3", "Hit@5", "MRR"] + (["Evidence hit@5 (95% CI)"] if evidence else []) \
        + ["Context tokens", "Latency", "p (Hit@5 vs prod)"] + (["p (evidence vs prod)"] if evidence else [])
    lines = [f"### `{mode}`" + (" (production retriever)" if mode == PRODUCTION_MODE else ""), "",
             "| " + " | ".join(cols) + " |", "|---|" + "---:|" * (len(cols) - 1)]
    for name, m in present.items():
        vs = summary[name]["sets"][set_name].get("vs_baseline", {}).get(mode, {})
        cells = [f"`{name}`", _pct(m["hit@1"]), _pct(m["hit@3"]), _pct(m["hit@5"]), f"{m['mrr']:.3f}"]
        if evidence:
            low, high = m.get("evidence_ci", [None, None])
            cells.append(f"{_pct(m.get('evidence_hit@5'))} ({_pct(low)}-{_pct(high)})")
        cells += [f"{m['context_tokens_avg']:.0f}", f"{m['latency_ms_avg']:.0f} ms",
                  str(vs.get("hit@5", {}).get("p_value", "-"))]
        if evidence:
            cells.append(str(vs.get("evidence_hit@5", {}).get("p_value", "-")))
        lines.append("| " + " | ".join(cells) + " |")
    return lines + [""]


def render_markdown(report: dict[str, Any]) -> str:
    """The report tables in Markdown."""
    summary = report["summary"]
    lines = [
        "# Chunking Experiments",
        "",
        "Each strategy re-chunks the official text of all 649 schemes into a temporary hybrid index; FAQ chunks are "
        "identical in every strategy. Retrieval only (no LLM).",
        "",
        f"- `{report['baseline']}` is production; it reproduces the live index exactly: "
        f"**{'yes' if report['baseline_reproduces_production_index'] else 'NO - check before trusting results'}**.",
        f"- Top-{report['top_k']} chunks per query. Evidence hit@5 = the gold evidence sentence (at least "
        f"{report['evidence_coverage_min'] * 100:.0f}% of it, contiguous) is inside one top-5 chunk of the right scheme.",
        "- p-values: exact McNemar against production on the same queries (paired); p < 0.05 = a real difference.",
        "",
        "## Index size",
        "",
        "| Strategy | Description | Official-text chunks | Avg / max tokens | Newly embedded |",
        "|---|---|---:|---|---:|",
    ]
    for name, s in summary.items():
        i = s["index"]
        lines.append(f"| `{name}` | {s['strategy']['description']} | {i['official_text_chunks']} | "
                     f"{i['official_tokens_avg']:.0f} / {i['official_tokens_max']} | {i['newly_embedded']} |")
    for set_name, title in QUERY_SET_TITLES.items():
        lines += ["", f"## {title}", ""]
        for mode in MODES:
            lines += _mode_table(summary, set_name, mode)
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--strategies", help=f"Comma-separated subset of: {', '.join(STRATEGIES)}")
    parser.add_argument("--no-rerank", action="store_true", help="Skip the (slow, CPU) cross-encoder reranker mode")
    args = parser.parse_args()
    names = [n.strip() for n in args.strategies.split(",")] if args.strategies else list(STRATEGIES)
    unknown = [n for n in names if n not in STRATEGIES]
    if unknown:
        parser.error(f"Unknown strategies {unknown}; choose from {list(STRATEGIES)}")
    if BASELINE.name not in names:
        names.insert(0, BASELINE.name)  # every comparison is against production
    modes = tuple(m for m in MODES if not (args.no_rerank and m == PRODUCTION_MODE))

    settings = get_settings()
    schemes, _ = load_and_enrich_schemes(settings.archive_dir, scope=settings.ingest_scope)
    client = EmbeddingClient(db_path=settings.db_abs_path.parent / "eval_cache" / EVAL_CACHE_DB_NAME)
    known = production_vectors(settings.db_abs_path, settings.index_abs_dir)
    production_texts = set(known)
    query_sets = load_query_sets()
    query_embs = {name: client.embed_texts_sync([q["text"] for q in qs], use_cache=True)
                  for name, qs in query_sets.items()}
    print(f"{len(schemes)} schemes; strategies {names}; modes {list(modes)}; "
          f"queries { {k: len(v) for k, v in query_sets.items()} }", flush=True)

    baseline_texts = {c.text for scheme in schemes for c in chunk_with_strategy(scheme, BASELINE)}
    reproduces = baseline_texts == production_texts
    if not reproduces:
        logger.warning("Baseline chunking does not reproduce the production index: results are not comparable.")

    results = {name: run_strategy(STRATEGIES[name], schemes, known, client, query_sets, query_embs, modes)
               for name in names}
    report = build_report(results, reproduces)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "chunking_eval.json").write_text(
        json.dumps({**report, "per_query": {n: r["rows"] for n, r in results.items()}}, indent=2), encoding="utf-8")
    (REPORT_DIR / "chunking_eval.md").write_text(render_markdown(report), encoding="utf-8")
    print(f"Wrote {REPORT_DIR / 'chunking_eval.md'} and chunking_eval.json")


if __name__ == "__main__":
    main()


