"""Generate clean 300-DPI Mentor-Upgraded Evaluation Charts (`docs/diagrams/clean_03_eval_benchmarks_v2.png`).

Reads real verified numbers from `eval/reports/gold60_comprehensive_eval.json` and `eval/reports/prompt_comparison.json`.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = PROJECT_ROOT / "docs" / "diagrams"
GOLD60_PATH = PROJECT_ROOT / "eval" / "reports" / "gold60_comprehensive_eval.json"

NAVY = "#0B2239"
BLUE = "#1D4ED8"
SAFFRON = "#D95D14"
GREEN = "#15803D"
RED = "#B91C1C"
SLATE = "#334155"
MUTED = "#64748B"
WHITE = "#FFFFFF"

plt.rcParams["font.family"] = "DejaVu Sans"


def make_eval_charts_v2() -> Path:
    rep = json.loads(GOLD60_PATH.read_text(encoding="utf-8"))
    ret = rep["retrieval_top_k_ablation"]
    nlp_v = rep["nlp_metrics"]["vanilla_llm"]
    nlp_r = rep["nlp_metrics"]["agentic_rag"]
    jdg_v = rep["independent_judge"]["vanilla_llm"]
    jdg_r = rep["independent_judge"]["agentic_rag"]
    lat = rep["latency_breakdown"]

    fig = plt.figure(figsize=(16.6, 5.8), dpi=300)
    fig.patch.set_facecolor(WHITE)
    gs = fig.add_gridspec(1, 3, width_ratios=[1.15, 1.12, 0.95], wspace=0.25, top=0.79, bottom=0.16, left=0.045, right=0.985)

    fig.suptitle(
        "JanSahayak AI — 60-Pair Zero-Leakage Gold QA Evaluation (Mentor Sync-Up Benchmarks)",
        fontsize=15.0,
        fontweight="bold",
        color=NAVY,
        y=0.95,
    )
    fig.text(
        0.50,
        0.885,
        "Top-1/3/5 Retrieval Ablation  •  Vanilla Qwen3-8B vs. Agentic Hybrid RAG (ROUGE, BLEU, BERTScore & Unbiased Gemini Judge)  •  Latency Breakdown",
        ha="center",
        fontsize=9.5,
        color=SLATE,
    )

    # Panel A: Top-1 / Top-3 / Top-5 Retrieval Ablation
    ax1 = fig.add_subplot(gs[0, 0])
    x = np.arange(len(ret))
    w = 0.27
    r1 = [c["recall_at_1"] * 100 for c in ret]
    r3 = [c["recall_at_3"] * 100 for c in ret]
    r5 = [c["recall_at_5"] * 100 for c in ret]

    b1 = ax1.bar(x - w, r1, w * 0.92, label="Top-1 (R@1)", color=SAFFRON)
    b2 = ax1.bar(x, r3, w * 0.92, label="Top-3 (R@3)", color=BLUE)
    b3 = ax1.bar(x + w, r5, w * 0.92, label="Top-5 (R@5)", color=GREEN)

    for idx_b, bars in enumerate((b1, b2, b3)):
        for bar in bars:
            h = bar.get_height()
            y_off = 1.2 if idx_b != 1 else 4.2
            ax1.text(bar.get_x() + bar.get_width() / 2, h + y_off, f"{h:.0f}%", ha="center", va="bottom",
                     fontsize=6.6, fontweight="bold", color=NAVY)

    ax1.set_ylim(0, 116)
    ax1.set_xticks(x)
    ax1.set_xticklabels(["R1\nBM25", "R2\nDense", "R3\nHybrid\nRRF", "R4\nHybrid+\nRerank"], fontsize=8.6, fontweight="bold")
    ax1.set_ylabel("Recall (%)", fontsize=9.2, fontweight="bold", color=NAVY)
    ax1.set_title("A. Top-1 / 3 / 5 Ablation (60 Gold Qs)", fontsize=10.8, fontweight="bold", color=NAVY, pad=10)
    ax1.legend(loc="lower right", fontsize=7.6, frameon=True)
    ax1.grid(axis="y", linestyle="--", alpha=0.35)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)

    # Panel B: Vanilla LLM (No RAG) vs. Agentic Hybrid RAG (ROUGE, BLEU, BERTScore, Gemini Judge)
    ax2 = fig.add_subplot(gs[0, 1])
    metrics_lbl = ["ROUGE-1", "ROUGE-L", "BLEU", "BERTScore\nF1", "Gemini\nJudge (%)"]
    van_vals = [
        nlp_v["rouge_1_f1"] * 100,
        nlp_v["rouge_l_f1"] * 100,
        nlp_v["bleu_corpus"] * 100,
        nlp_v["bertscore_f1"] * 100,
        jdg_v["overall_score_pct"],
    ]
    rag_vals = [
        nlp_r["rouge_1_f1"] * 100,
        nlp_r["rouge_l_f1"] * 100,
        nlp_r["bleu_corpus"] * 100,
        nlp_r["bertscore_f1"] * 100,
        jdg_r["overall_score_pct"],
    ]

    x2 = np.arange(len(metrics_lbl))
    w2 = 0.34
    p_v = ax2.bar(x2 - w2 / 2, van_vals, w2, label="Vanilla LLM (No RAG)", color="#94A3B8")
    p_r = ax2.bar(x2 + w2 / 2, rag_vals, w2, label="Agentic Hybrid RAG", color=BLUE)

    for bars in (p_v, p_r):
        for bar in bars:
            h = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width() / 2, h + 1.4, f"{h:.1f}", ha="center", va="bottom",
                     fontsize=6.9, fontweight="bold", color=NAVY)

    ax2.set_ylim(0, 112)
    ax2.set_xticks(x2)
    ax2.set_xticklabels(metrics_lbl, fontsize=8.0, fontweight="bold")
    ax2.set_ylabel("Score (%)", fontsize=9.2, fontweight="bold", color=NAVY)
    ax2.set_title("B. Vanilla LLM vs. Agentic Hybrid RAG", fontsize=10.8, fontweight="bold", color=NAVY, pad=10)
    ax2.legend(loc="upper left", fontsize=7.6, frameon=True)
    ax2.grid(axis="y", linestyle="--", alpha=0.35)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)

    # Panel C: Unbiased Judge Hallucination Drop & Latency Breakdown
    ax3 = fig.add_subplot(gs[0, 2])
    cats = [
        "Vanilla LLM\nHallucination",
        "Agentic RAG\nHallucination",
        "Vanilla LLM\nTotal Lat. (s)",
        "RAG Retrieval\nLatency (s)",
        "RAG LLM\nLatency (s)",
        "RAG Total\nLatency (s)",
    ]
    # Show clean latency & judge pass bars (actually let's keep Panel C pure 0..100% Judge & Safety or split cleanly — let's make Panel C pure Latency Breakdown stacked bar + Judge Hallucination callout!)
    ax3.clear()
    bars_x = np.arange(2)
    ret_s = [0.0, lat["rag_avg_retrieval_ms"] / 1000.0]
    llm_s = [lat["vanilla_avg_llm_ms"] / 1000.0, lat["rag_avg_llm_ms"] / 1000.0]

    ax3.bar(bars_x, ret_s, width=0.48, label="Retrieval + Rerank (s)", color=SAFFRON)
    ax3.bar(bars_x, llm_s, width=0.48, bottom=ret_s, label="Qwen3-8B Generation (s)", color=NAVY)

    for i in range(2):
        tot = ret_s[i] + llm_s[i]
        ax3.text(i, tot + 0.18, f"Total: {tot:.2f}s", ha="center", va="bottom",
                 fontsize=9.0, fontweight="bold", color=NAVY)
        if ret_s[i] > 0.2:
            ax3.text(i, ret_s[i] / 2, f"Ret\n{ret_s[i]:.2f}s", ha="center", va="center",
                     fontsize=7.6, fontweight="bold", color=WHITE)
        ax3.text(i, ret_s[i] + llm_s[i] / 2, f"LLM\n{llm_s[i]:.2f}s", ha="center", va="center",
                 fontsize=8.0, fontweight="bold", color=WHITE)

    max_y = max(ret_s[1] + llm_s[1], llm_s[0]) * 1.42
    ax3.set_ylim(0, max_y)
    ax3.set_xticks(bars_x)
    ax3.set_xticklabels(["Vanilla LLM\n(No Corpus)", "Agentic Hybrid RAG\n(649 Schemes)"], fontsize=8.8, fontweight="bold")
    ax3.set_ylabel("Avg Latency (seconds)", fontsize=9.2, fontweight="bold", color=NAVY)
    ax3.set_title("C. Average Latency Breakdown (60 Qs)", fontsize=10.8, fontweight="bold", color=NAVY, pad=10)
    ax3.legend(loc="upper left", fontsize=7.6, frameon=True)
    ax3.grid(axis="y", linestyle="--", alpha=0.35)
    ax3.spines["top"].set_visible(False)
    ax3.spines["right"].set_visible(False)

    # Add crisp Judge Hallucination callout pill inside Panel C top-right
    ax3.text(
        0.97,
        0.95,
        f"Gemini Judge Hallucination:\nVanilla: {jdg_v['hallucination_rate']*100:.1f}%  ->  RAG: {jdg_r['hallucination_rate']*100:.1f}%",
        transform=ax3.transAxes,
        ha="right",
        va="top",
        fontsize=7.4,
        fontweight="bold",
        color=GREEN,
        bbox=dict(boxstyle="round,pad=0.35", facecolor="#ECFDF5", edgecolor=GREEN, lw=1.0),
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "clean_03_eval_benchmarks_v2.png"
    tmp = OUT_DIR / "_tmp_clean_03.png"
    plt.savefig(tmp, dpi=300, bbox_inches="tight", pad_inches=0.14)
    plt.close(fig)
    tmp.replace(out)
    return out


if __name__ == "__main__":
    p = make_eval_charts_v2()
    print(f"[OK] Generated {p.name} ({p.stat().st_size:,} bytes)")
