"""Comprehensive 60-Pair Gold QA Evaluation Suite (Mentor Sync-Up Upgrade):
1. Top-1, Top-3, Top-5 Retrieval Ablation (BM25 vs Dense vs Hybrid RRF vs Hybrid + Cross-Encoder)
2. Vanilla LLM Baseline (Qwen3-8B, NO RAG) vs. Agentic Hybrid RAG (Qwen3-8B + R4 Top-5)
3. Exact Latency Breakdown (Avg Retrieval ms, Avg LLM Response ms, Avg Total End-to-End ms)
4. NLP Reference Metrics: ROUGE-1, ROUGE-2, ROUGE-L, BLEU, BERTScore (P/R/F1)
5. Checkpoint/resume support so interrupted runs pick up cleanly.
"""

from __future__ import annotations

import asyncio
import json
import math
import re
import sys
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.agent.prompts import SYNTHESIZER_SYSTEM_PROMPT
from backend.gateway.llm_client import get_llm_gateway
from backend.guardrails.injection import sanitize_untrusted_evidence
from backend.retrieval.hybrid_retriever import HybridRetriever, RetrievalMode

GOLD60_PATH = PROJECT_ROOT / "eval" / "gold_qa_60.json"
REPORTS_DIR = PROJECT_ROOT / "eval" / "reports"
LIVE_OUT_PATH = REPORTS_DIR / "gold60_live_outputs.json"

VANILLA_SYSTEM_PROMPT = (
    "You are a helpful assistant answering questions about Indian Central Government welfare schemes. "
    "Answer concisely in 2-4 sentences using only your own knowledge."
)


def _dcg(rels: list[int], k: int) -> float:
    return sum((rel / math.log2(idx + 2)) for idx, rel in enumerate(rels[:k]))


def _unique_slugs(results) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for r in results:
        if r.scheme_slug not in seen:
            seen.add(r.scheme_slug)
            ordered.append(r.scheme_slug)
    return ordered


def _strip_citations_and_md(text: str) -> str:
    s = text or ""
    s = re.sub(r"\[([^\]]+)\]\(https?:\/\/[^\s)]+\)", r"\1", s)
    s = re.sub(r"\[\d+\]", "", s)
    s = re.sub(r"[#*`>_~]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def run_top135_retrieval_ablation(items: list[dict[str, Any]], retriever: HybridRetriever) -> dict[str, Any]:
    queries = [it["question"] for it in items]
    q_embs = retriever.embedding_client.embed_texts_sync(queries, use_cache=True)

    configs: list[tuple[str, str, RetrievalMode]] = [
        ("R1", "BM25-Only (Sparse Lexical)", "bm25"),
        ("R2", "Dense-Only (bge-small-en-v1.5)", "dense"),
        ("R3", "Hybrid RRF (BM25 + Dense, k=60)", "hybrid_rrf"),
        ("R4", "Hybrid RRF + Cross-Encoder Reranker", "hybrid_rerank"),
    ]
    rows = []
    cached_r4_chunks: list[tuple[list[dict[str, Any]], float]] = []

    for cid, name, mode in configs:
        r1 = r3 = r5 = 0
        mrr = 0.0
        ndcg5 = 0.0
        lat_sum = 0.0

        for idx, it in enumerate(items):
            gold = it["gold_scheme_slug"]
            out = retriever.search_sync(
                query=queries[idx],
                top_k=5,
                mode=mode,
                query_embedding=q_embs[idx],
            )
            lat_sum += out.latency_ms
            slugs = _unique_slugs(out.results)
            if cid == "R4":
                cached_r4_chunks.append(([r.to_dict() for r in out.results], out.latency_ms))

            if slugs[:1] and gold == slugs[0]:
                r1 += 1
            if gold in slugs[:3]:
                r3 += 1
            if gold in slugs[:5]:
                r5 += 1

            rr = 0.0
            for pos, s in enumerate(slugs[:5], start=1):
                if s == gold:
                    rr = 1.0 / pos
                    break
            mrr += rr
            rels = [1 if s == gold else 0 for s in slugs[:5]]
            ndcg5 += _dcg(rels, 5) / 1.0

        n = len(items)
        rows.append({
            "id": cid,
            "name": name,
            "mode": mode,
            "recall_at_1": round(r1 / n, 4),
            "recall_at_3": round(r3 / n, 4),
            "recall_at_5": round(r5 / n, 4),
            "mrr_at_5": round(mrr / n, 4),
            "ndcg_at_5": round(ndcg5 / n, 4),
            "avg_latency_ms": round(lat_sum / n, 2),
        })
        print(
            f"[RET {cid}] R@1={r1/n*100:.1f}% | R@3={r3/n*100:.1f}% | R@5={r5/n*100:.1f}% "
            f"| MRR@5={mrr/n:.3f} | NDCG@5={ndcg5/n:.3f} | Lat={lat_sum/n:.1f}ms"
        )

    return {"configs": rows, "_r4_cache": cached_r4_chunks}


async def run_vanilla_vs_rag_generation(
    items: list[dict[str, Any]],
    r4_cache: list[tuple[list[dict[str, Any]], float]],
) -> list[dict[str, Any]]:
    llm = get_llm_gateway()

    # Load existing checkpoint if available
    done_by_id: dict[str, dict[str, Any]] = {}
    if LIVE_OUT_PATH.exists():
        prev = json.loads(LIVE_OUT_PATH.read_text(encoding="utf-8"))
        for rec in prev.get("records") or []:
            if rec.get("vanilla_answer") and rec.get("rag_answer"):
                done_by_id[rec["id"]] = rec
        if done_by_id:
            print(f"[RESUME] Loaded {len(done_by_id)}/60 already completed pairs from checkpoint.")

    records: list[dict[str, Any]] = []
    for idx, it in enumerate(items):
        qid = it["id"]
        if qid in done_by_id:
            records.append(done_by_id[qid])
            continue

        q = it["question"]
        chunks, ret_ms = r4_cache[idx]

        # 1. Vanilla LLM Baseline (NO retrieved corpus context)
        v_resp = await llm.chat_completion(
            messages=[
                {"role": "system", "content": VANILLA_SYSTEM_PROMPT},
                {"role": "user", "content": q},
            ],
            max_tokens=260,
            temperature=0.05,
            disable_thinking=True,
        )

        # 2. Agentic Hybrid RAG (R4 Top-5 chunks + Untrusted Delimiter + P3 Grounded Prompt)
        ev_lines = [
            f"[{i+1}] Scheme: {c.get('scheme_name')} | Ministry: {c.get('ministry')} | Section: {c.get('section')}\n{c.get('text', '')}"
            for i, c in enumerate(chunks[:5])
        ]
        wrapped, _ = sanitize_untrusted_evidence("\n\n".join(ev_lines))
        r_resp = await llm.chat_completion(
            messages=[
                {"role": "system", "content": SYNTHESIZER_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Evidence:\n{wrapped}\n\n"
                        f"Citizen Question: {q}\n"
                        "Answer concisely in 2-4 crisp sentences strictly grounded in the evidence above with inline citations [1], [2]."
                    ),
                },
            ],
            max_tokens=280,
            temperature=0.05,
            disable_thinking=True,
        )

        rec = {
            "id": qid,
            "domain": it["domain"],
            "gold_scheme_slug": it["gold_scheme_slug"],
            "gold_scheme_name": it["gold_scheme_name"],
            "question": q,
            "reference_answer": it["reference_answer"],
            "vanilla_answer": v_resp.content.strip(),
            "vanilla_llm_ms": round(v_resp.latency_ms, 2),
            "vanilla_tokens": v_resp.total_tokens,
            "rag_answer": r_resp.content.strip(),
            "rag_retrieval_ms": round(ret_ms, 2),
            "rag_llm_ms": round(r_resp.latency_ms, 2),
            "rag_total_ms": round(ret_ms + r_resp.latency_ms, 2),
            "rag_tokens": r_resp.total_tokens,
            "rag_top1_slug": chunks[0]["scheme_slug"] if chunks else "",
            "rag_hit_at_5": any(c["scheme_slug"] == it["gold_scheme_slug"] for c in chunks[:5]),
        }
        records.append(rec)

        if (idx + 1) % 5 == 0 or (idx + 1) == len(items):
            LIVE_OUT_PATH.write_text(
                json.dumps({"records": records}, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            print(
                f"[GEN {idx+1:02d}/60] {qid} | Vanilla={v_resp.latency_ms:.0f}ms | "
                f"RAG Ret={ret_ms:.0f}ms + LLM={r_resp.latency_ms:.0f}ms | Hit@5={rec['rag_hit_at_5']}"
            )

    return records


def compute_nlp_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    from rouge_score import rouge_scorer
    import sacrebleu
    from bert_score import score as bert_score_fn

    scorer = rouge_scorer.RougeScorer(["rouge1", "rouge2", "rougeL"], use_stemmer=True)
    refs = [_strip_citations_and_md(r["reference_answer"]) for r in records]
    van_hyps = [_strip_citations_and_md(r["vanilla_answer"]) for r in records]
    rag_hyps = [_strip_citations_and_md(r["rag_answer"]) for r in records]

    def _calc_block(hyps: list[str], label: str) -> dict[str, Any]:
        r1 = r2 = rl = 0.0
        sent_bleus = []
        for ref, hyp in zip(refs, hyps):
            sc = scorer.score(ref, hyp)
            r1 += sc["rouge1"].fmeasure
            r2 += sc["rouge2"].fmeasure
            rl += sc["rougeL"].fmeasure
            sb = sacrebleu.sentence_bleu(hyp, [ref]).score / 100.0
            sent_bleus.append(sb)

        corpus_bleu = sacrebleu.corpus_bleu(hyps, [refs]).score / 100.0

        print(f"[BERTScore] Computing BERTScore (distilbert-base-uncased) for {label} ({len(hyps)} pairs)...")
        P, R, F1 = bert_score_fn(
            hyps,
            refs,
            model_type="distilbert-base-uncased",
            lang="en",
            device="cpu",
            batch_size=16,
            verbose=False,
        )
        n = len(records)
        return {
            "rouge_1_f1": round(r1 / n, 4),
            "rouge_2_f1": round(r2 / n, 4),
            "rouge_l_f1": round(rl / n, 4),
            "bleu_corpus": round(corpus_bleu, 4),
            "bleu_sentence_avg": round(sum(sent_bleus) / n, 4),
            "bertscore_precision": round(float(P.mean().item()), 4),
            "bertscore_recall": round(float(R.mean().item()), 4),
            "bertscore_f1": round(float(F1.mean().item()), 4),
        }

    van_m = _calc_block(van_hyps, "Vanilla LLM (No RAG)")
    rag_m = _calc_block(rag_hyps, "Agentic Hybrid RAG")
    return {"vanilla_llm": van_m, "agentic_rag": rag_m}


async def main() -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    gold = json.loads(GOLD60_PATH.read_text(encoding="utf-8"))
    items = gold["items"]

    retriever = HybridRetriever(load_reranker=True)
    retriever.load()

    print("=== STEP 1: Top-1 / Top-3 / Top-5 Retrieval Ablation on 60 Zero-Leakage Gold QA Pairs ===")
    ret_out = run_top135_retrieval_ablation(items, retriever)

    print("\n=== STEP 2: Live Vanilla LLM vs. Agentic Hybrid RAG Generation (60 Pairs) ===")
    records = await run_vanilla_vs_rag_generation(items, ret_out["_r4_cache"])

    print("\n=== STEP 3: Computing ROUGE-1/2/L, BLEU & BERTScore ===")
    nlp = compute_nlp_metrics(records)

    n = len(records)
    latency_summary = {
        "vanilla_avg_llm_ms": round(sum(r["vanilla_llm_ms"] for r in records) / n, 1),
        "vanilla_avg_total_ms": round(sum(r["vanilla_llm_ms"] for r in records) / n, 1),
        "rag_avg_retrieval_ms": round(sum(r["rag_retrieval_ms"] for r in records) / n, 1),
        "rag_avg_llm_ms": round(sum(r["rag_llm_ms"] for r in records) / n, 1),
        "rag_avg_total_ms": round(sum(r["rag_total_ms"] for r in records) / n, 1),
        "vanilla_avg_tokens": round(sum(r["vanilla_tokens"] for r in records) / n, 1),
        "rag_avg_tokens": round(sum(r["rag_tokens"] for r in records) / n, 1),
    }

    out_bundle = {
        "eval_trace_id": "EVAL-GOLD60-COMP",
        "model_evaluated": "Qwen/Qwen3-8B",
        "embedding_model": "bge-small-en-v1.5",
        "reranker_model": "cross-encoder/ms-marco-MiniLM-L-6-v2",
        "num_pairs": n,
        "leakage_verification": gold["leakage_verification"],
        "retrieval_top_k_ablation": ret_out["configs"],
        "nlp_metrics": nlp,
        "latency_breakdown": latency_summary,
        "records": records,
    }
    LIVE_OUT_PATH.write_text(json.dumps(out_bundle, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\n=== SUMMARY ===")
    print("NLP Metrics:", json.dumps(nlp, indent=2))
    print("Latency:", json.dumps(latency_summary, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
