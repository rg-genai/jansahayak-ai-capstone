"""Track B Week 2 Evaluation: 4-Way Retrieval Ablation (R1 BM25 vs R2 Dense vs R3 Hybrid RRF vs R4 Hybrid+Reranker)."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.retrieval.hybrid_retriever import HybridRetriever, RetrievalMode

REPORTS_DIR = PROJECT_ROOT / "eval" / "reports"
GOLDEN_PATH = PROJECT_ROOT / "eval" / "golden_dataset.json"


def _dcg(relevances: list[int], k: int) -> float:
    return sum((rel / math.log2(idx + 2)) for idx, rel in enumerate(relevances[:k]))


def _unique_scheme_ranking(results) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for r in results:
        if r.scheme_slug not in seen:
            seen.add(r.scheme_slug)
            ordered.append(r.scheme_slug)
    return ordered


def run_retrieval_ablation(golden_path: Path = GOLDEN_PATH) -> dict[str, Any]:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    dataset = json.loads(golden_path.read_text(encoding="utf-8"))
    retrieval_items = [item for item in dataset if item.get("gold_scheme_slug")]

    retriever = HybridRetriever(load_reranker=True)
    retriever.load()

    # Pre-embed all English retrieval queries once (cached in SQLite) to ensure fair apples-to-apples timing
    queries_en = [item.get("query_en") or item["query"] for item in retrieval_items]
    q_embs = retriever.embedding_client.embed_texts_sync(queries_en, use_cache=True)

    configs: list[tuple[str, str, RetrievalMode, bool]] = [
        ("R1", "BM25-Only (Sparse Lexical)", "bm25", False),
        ("R2", "Dense-Only (bge-small-en-v1.5)", "dense", False),
        ("R3", "Hybrid RRF (BM25 + Dense)", "hybrid_rrf", False),
        ("R4", "Hybrid RRF + Cross-Encoder Reranker + Metadata Filter", "hybrid_rerank", True),
    ]

    summary_configs: list[dict[str, Any]] = []
    misses_r4: list[dict[str, Any]] = []

    for cid, name, mode, use_filters in configs:
        r3_hits = 0
        r5_hits = 0
        r10_hits = 0
        mrr_sum = 0.0
        ndcg5_sum = 0.0
        lat_sum = 0.0

        for idx, item in enumerate(retrieval_items):
            q_text = queries_en[idx]
            gold_slugs = set([item["gold_scheme_slug"]] + list(item.get("alt_valid_slugs") or []))
            filters = item.get("retrieval_filters") if use_filters else None

            out = retriever.search_sync(
                query=q_text,
                top_k=10,
                mode=mode,
                filters=filters,
                query_embedding=q_embs[idx],
            )
            lat_sum += out.latency_ms
            ranked_slugs = _unique_scheme_ranking(out.results)

            # Hit metrics
            if any(s in gold_slugs for s in ranked_slugs[:3]):
                r3_hits += 1
            if any(s in gold_slugs for s in ranked_slugs[:5]):
                r5_hits += 1
            if any(s in gold_slugs for s in ranked_slugs[:10]):
                r10_hits += 1

            # MRR@10
            rr = 0.0
            for rank_pos, s in enumerate(ranked_slugs[:10], start=1):
                if s in gold_slugs:
                    rr = 1.0 / rank_pos
                    break
            mrr_sum += rr

            # NDCG@5 (binary relevance over unique schemes)
            rels = [1 if s in gold_slugs else 0 for s in ranked_slugs[:5]]
            ideal = sorted(rels, reverse=True)
            idcg = _dcg([1] + [0] * 4, 5)
            ndcg5_sum += (_dcg(rels, 5) / idcg) if idcg > 0 else 0.0

            if cid == "R4" and not any(s in gold_slugs for s in ranked_slugs[:5]):
                misses_r4.append({
                    "id": item["id"],
                    "query": q_text,
                    "gold_slug": item["gold_scheme_slug"],
                    "top5_retrieved": ranked_slugs[:5],
                })

        n = max(1, len(retrieval_items))
        summary_configs.append({
            "id": cid,
            "name": name,
            "mode": mode,
            "recall_at_3": round(r3_hits / n, 4),
            "recall_at_5": round(r5_hits / n, 4),
            "recall_at_10": round(r10_hits / n, 4),
            "mrr_at_10": round(mrr_sum / n, 4),
            "ndcg_at_5": round(ndcg5_sum / n, 4),
            "avg_latency_ms": round(lat_sum / n, 2),
        })

    report = {
        "num_queries": len(retrieval_items),
        "configs": summary_configs,
        "r4_misses_top5": misses_r4,
    }

    (REPORTS_DIR / "retrieval_ablation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    md_lines = [
        "# Retrieval Ablation Benchmark (`R1`–`R4`)",
        f"- **Evaluated Queries:** {len(retrieval_items)} (stratified across Scheme QA, Eligibility, FAQs & Multilingual English-Pivot)",
        "",
        "| Config | Strategy | Recall@3 | Recall@5 | Recall@10 | MRR@10 | NDCG@5 | Avg Latency (ms) |",
        "| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]
    for c in summary_configs:
        md_lines.append(
            f"| **{c['id']}** | {c['name']} | {c['recall_at_3']*100:.1f}% | **{c['recall_at_5']*100:.1f}%** | "
            f"{c['recall_at_10']*100:.1f}% | **{c['mrr_at_10']:.3f}** | {c['ndcg_at_5']:.3f} | {c['avg_latency_ms']:.1f} |"
        )
    if misses_r4:
        md_lines.append("")
        md_lines.append(f"## R4 Top-5 Misses ({len(misses_r4)})")
        for m in misses_r4[:10]:
            md_lines.append(f"- `{m['id']}` (`{m['gold_slug']}`): got `{m['top5_retrieved'][:3]}`")

    (REPORTS_DIR / "retrieval_ablation.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    print("[PASS] Retrieval ablation saved to eval/reports/retrieval_ablation.json/.md")
    return report


if __name__ == "__main__":
    run_retrieval_ablation()
