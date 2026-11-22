"""Track B Week 1 Evaluation: 3-Way Prompting Strategy Comparison (P1 Zero-Shot vs P2 Few-Shot vs P3 Planner-Critic)."""

from __future__ import annotations

import asyncio
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.agent.prompts import (
    CRITIC_SYSTEM_PROMPT,
    SYNTHESIZER_SYSTEM_PROMPT,
    build_p1_zero_shot_messages,
    build_p2_few_shot_messages,
)
from backend.agent.state import CitizenProfile, CriticOutput
from backend.agent.tools import AgentToolbox, CheckEligibilityInput, parse_and_repair_json
from backend.gateway.llm_client import get_llm_gateway
from backend.guardrails.injection import check_input_guardrails, sanitize_untrusted_evidence
from backend.retrieval.hybrid_retriever import HybridRetriever

REPORTS_DIR = PROJECT_ROOT / "eval" / "reports"
GOLDEN_PATH = PROJECT_ROOT / "eval" / "golden_dataset.json"

_CITATION_RE = re.compile(r"\[\d+\]")
_VERDICT_RE = re.compile(r"\b(NOT_ELIGIBLE|PARTIALLY_ELIGIBLE|NEEDS_MORE_INFO|ELIGIBLE)\b")


def _select_stratified_subset(dataset: list[dict[str, Any]], target_n: int = 30) -> list[dict[str, Any]]:
    by_cat: dict[str, list[dict[str, Any]]] = {}
    for item in dataset:
        by_cat.setdefault(item["category"], []).append(item)
    quotas = {
        "scheme_qa": 10,
        "eligibility": 8,
        "faq": 5,
        "multilingual": 4,
        "refusal": 3,
    }
    selected: list[dict[str, Any]] = []
    for cat, q in quotas.items():
        selected.extend(by_cat.get(cat, [])[:q])
    return selected[:target_n]


def _score_answer(item: dict[str, Any], answer: str, has_evidence: bool) -> dict[str, Any]:
    ans_low = (answer or "").lower()
    cat = item["category"]
    expected_kw = [k.lower() for k in (item.get("expected_keywords") or [])]

    # 1. Citation adherence (when grounded evidence is expected)
    has_citation = bool(_CITATION_RE.search(answer or ""))
    citation_ok = True if cat == "refusal" else (has_citation if has_evidence else True)

    # 2. Answer accuracy
    if cat == "refusal":
        refusal_signals = ("cannot", "can't", "unable", "not found", "no matching", "sorry", "do not have", "official", "108", "refuse")
        accurate = any(s in ans_low for s in refusal_signals)
        hallucinated = not accurate
    elif cat == "eligibility":
        gold_verdict = (item.get("gold_verdict") or "").upper()
        found_verdicts = _VERDICT_RE.findall((answer or "").upper())
        verdict_match = bool(found_verdicts and found_verdicts[0] == gold_verdict)
        kw_hits = sum(1 for k in expected_kw if k in ans_low)
        kw_ratio = (kw_hits / len(expected_kw)) if expected_kw else 1.0
        accurate = verdict_match or kw_ratio >= 0.5
        # Hallucination if contradicts gold NOT_ELIGIBLE with ELIGIBLE
        hallucinated = (gold_verdict == "NOT_ELIGIBLE" and "ELIGIBLE" in found_verdicts and "NOT_ELIGIBLE" not in found_verdicts)
    else:
        kw_hits = sum(1 for k in expected_kw if k in ans_low)
        kw_ratio = (kw_hits / len(expected_kw)) if expected_kw else 1.0
        accurate = kw_ratio >= 0.5
        # Uncited numerical/rupee claims or missed scheme name count as unsupported/hallucinated
        hallucinated = (not accurate) or (has_evidence and not has_citation and bool(re.search(r"₹|rs\.?\s*\d", ans_low)))

    return {
        "accurate": accurate,
        "citation_ok": citation_ok,
        "hallucinated": hallucinated,
    }


async def run_prompt_comparison(golden_path: Path = GOLDEN_PATH) -> dict[str, Any]:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    dataset = json.loads(golden_path.read_text(encoding="utf-8"))
    subset = _select_stratified_subset(dataset, target_n=30)

    retriever = HybridRetriever(load_reranker=True)
    retriever.load()
    llm = get_llm_gateway()
    toolbox = AgentToolbox(retriever=retriever)

    # Pre-fetch R4 retrieved chunks for every query in subset so P1, P2, P3 share identical R4 evidence!
    prepared: list[dict[str, Any]] = []
    for item in subset:
        q_en = item.get("query_en") or item["query"]
        if item["category"] == "refusal":
            chunks = []
        else:
            out = retriever.search_sync(q_en, top_k=5, mode="hybrid_rerank")
            chunks = [r.to_dict() for r in out.results]
        prepared.append({"item": item, "query_en": q_en, "chunks": chunks})

    strategies_meta = [
        ("P1", "Zero-Shot Direct Prompt"),
        ("P2", "Few-Shot Structured Prompt"),
        ("P3", "Grounded Planner-Executor-Synthesizer-Critic"),
    ]
    strategy_reports: list[dict[str, Any]] = []

    for sid, sname in strategies_meta:
        acc_cnt = 0
        cite_cnt = 0
        halluc_cnt = 0
        elig_total = 0
        elig_ok = 0
        lat_sum = 0.0
        tok_sum = 0
        details: list[dict[str, Any]] = []

        for entry in prepared:
            item = entry["item"]
            q_en = entry["query_en"]
            chunks = entry["chunks"]
            profile = item.get("citizen_profile") or {}
            t0 = time.perf_counter()
            tokens_used = 0
            answer = ""

            if sid == "P1":
                msgs = build_p1_zero_shot_messages(q_en, chunks, profile)
                resp = await llm.chat_completion(msgs, max_tokens=420, temperature=0.1, disable_thinking=True)
                answer = resp.content
                tokens_used = resp.prompt_tokens + resp.completion_tokens

            elif sid == "P2":
                msgs = build_p2_few_shot_messages(q_en, chunks, profile)
                resp = await llm.chat_completion(msgs, max_tokens=450, temperature=0.1, disable_thinking=True)
                answer = resp.content
                tokens_used = resp.prompt_tokens + resp.completion_tokens

            else:  # P3: Guardrail + Structured Eligibility Tool + Citation-Strict Synthesizer + Critic Audit
                gv = check_input_guardrails(q_en)
                if gv.blocked:
                    answer = gv.refusal_message or "I cannot assist with this request."
                else:
                    elig_blocks: list[dict[str, Any]] = []
                    if item["category"] == "eligibility" and chunks:
                        ec = await toolbox.check_eligibility(
                            CheckEligibilityInput(
                                scheme_slug=chunks[0]["scheme_slug"],
                                citizen_profile=CitizenProfile.model_validate(profile),
                            )
                        )
                        elig_blocks.append(ec)

                    ev_lines = [
                        f"[{i+1}] Scheme: {c['scheme_name']} | Section: {c['section']} | URL: {c['source_url']}\n{c['text']}"
                        for i, c in enumerate(chunks)
                    ]
                    ev_wrapped, _ = sanitize_untrusted_evidence("\n\n".join(ev_lines) if ev_lines else "NO MATCHING SCHEMES FOUND.")
                    extra = f"\n\nStructured Eligibility Tool Output:\n{json.dumps(elig_blocks, ensure_ascii=False)}" if elig_blocks else ""
                    msgs = [
                        {"role": "system", "content": SYNTHESIZER_SYSTEM_PROMPT},
                        {
                            "role": "user",
                            "content": f"Citizen Profile: {json.dumps(profile)}\n\nEvidence:\n{ev_wrapped}{extra}\n\nCitizen Question: {q_en}\nProvide a concise grounded answer with inline citations [1], [2].",
                        },
                    ]
                    resp = await llm.chat_completion(msgs, max_tokens=500, temperature=0.05, disable_thinking=True)
                    answer = resp.content
                    tokens_used += resp.prompt_tokens + resp.completion_tokens

                    # Deterministic + 1-shot Critic repair if missing citations on evidence-backed turn
                    if chunks and not _CITATION_RE.search(answer):
                        rev_msgs = msgs + [
                            {"role": "assistant", "content": answer},
                            {"role": "user", "content": "Critic Audit: Your response is missing mandatory inline citations [1], [2]. Revise concisely adding inline citations strictly grounded in the evidence."},
                        ]
                        resp2 = await llm.chat_completion(rev_msgs, max_tokens=450, temperature=0.0, disable_thinking=True)
                        answer = resp2.content
                        tokens_used += resp2.prompt_tokens + resp2.completion_tokens

            elapsed = time.perf_counter() - t0
            lat_sum += elapsed
            tok_sum += tokens_used

            sc = _score_answer(item, answer, has_evidence=bool(chunks))
            if sc["accurate"]:
                acc_cnt += 1
            if sc["citation_ok"]:
                cite_cnt += 1
            if sc["hallucinated"]:
                halluc_cnt += 1
            if item["category"] == "eligibility":
                elig_total += 1
                if sc["accurate"]:
                    elig_ok += 1

            details.append({
                "id": item["id"],
                "category": item["category"],
                "accurate": sc["accurate"],
                "citation_ok": sc["citation_ok"],
                "hallucinated": sc["hallucinated"],
                "latency_s": round(elapsed, 2),
                "tokens": tokens_used,
            })

        n = max(1, len(prepared))
        strategy_reports.append({
            "id": sid,
            "name": sname,
            "answer_accuracy": round(acc_cnt / n, 4),
            "citation_adherence": round(cite_cnt / n, 4),
            "hallucination_rate": round(halluc_cnt / n, 4),
            "eligibility_accuracy": round(elig_ok / max(1, elig_total), 4),
            "avg_latency_s": round(lat_sum / n, 2),
            "avg_tokens": round(tok_sum / n, 1),
            "details": details,
        })
        print(
            f"[INFO] {sid} done | acc={acc_cnt/n*100:.1f}% | cite={cite_cnt/n*100:.1f}% | "
            f"halluc={halluc_cnt/n*100:.1f}% | avg_lat={lat_sum/n:.2f}s"
        )

    report = {
        "model": llm.model,
        "num_queries": len(prepared),
        "strategies": strategy_reports,
    }
    (REPORTS_DIR / "prompt_comparison.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    md_lines = [
        "# Prompting Strategy Comparison (`P1` vs `P2` vs `P3`)",
        f"- **Fixed Model:** `{llm.model}` | **Retrieval:** `R4` (Hybrid RRF + Cross-Encoder Reranker) | **Queries:** {len(prepared)} stratified",
        "",
        "| Strategy | Description | Answer Accuracy | Citation Adherence | Hallucination Rate | Eligibility Acc | Avg Latency (s) | Avg Tokens |",
        "| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]
    for s in strategy_reports:
        md_lines.append(
            f"| **{s['id']}** | {s['name']} | **{s['answer_accuracy']*100:.1f}%** | **{s['citation_adherence']*100:.1f}%** | "
            f"{s['hallucination_rate']*100:.1f}% | {s['eligibility_accuracy']*100:.1f}% | {s['avg_latency_s']:.2f}s | {s['avg_tokens']:.0f} |"
        )
    (REPORTS_DIR / "prompt_comparison.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    print("[PASS] Prompt comparison saved to eval/reports/prompt_comparison.json/.md")
    return report


if __name__ == "__main__":
    asyncio.run(run_prompt_comparison())
