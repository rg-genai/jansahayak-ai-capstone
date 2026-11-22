"""Generate 5 publication-grade 300-DPI architecture, pipeline, data-flow & evaluation diagrams for JanSahayak AI docs."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = PROJECT_ROOT / "docs" / "diagrams"
CAPTURE_PATH = PROJECT_ROOT / "data" / "live_walkthrough_capture.json"

# Civic GovTech Palette
NAVY = "#0F2942"
BLUE = "#1E4E79"
ACCENT_BLUE = "#2563EB"
LIGHT_BLUE = "#EFF6FF"
SAFFRON = "#D95D14"
LIGHT_SAFFRON = "#FFF4EB"
GREEN = "#138808"
LIGHT_GREEN = "#ECFDF5"
PURPLE = "#6D28D9"
LIGHT_PURPLE = "#F5F3FF"
AMBER = "#B45309"
LIGHT_AMBER = "#FEF3C7"
RED = "#B91C1C"
LIGHT_RED = "#FEF2F2"
SLATE = "#334155"
MUTED = "#64748B"
LIGHT_BG = "#F8FAFC"
BORDER = "#CBD5E1"
WHITE = "#FFFFFF"

plt.rcParams["font.family"] = "DejaVu Sans"
plt.rcParams["axes.edgecolor"] = BORDER


def draw_box(
    ax,
    x: float,
    y: float,
    w: float,
    h: float,
    title: str,
    subtitle: str = "",
    facecolor: str = WHITE,
    edgecolor: str = NAVY,
    title_color: str = NAVY,
    sub_color: str = SLATE,
    title_size: float = 9.3,
    sub_size: float = 7.4,
    lw: float = 1.4,
    radius: float = 0.014,
    badge: str | None = None,
    badge_color: str = SAFFRON,
    align: str = "center",
):
    box = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle=f"round,pad=0.004,rounding_size={radius}",
        facecolor=facecolor,
        edgecolor=edgecolor,
        linewidth=lw,
        zorder=2,
    )
    ax.add_patch(box)

    tx = x + w / 2 if align == "center" else x + 0.014
    ha = "center" if align == "center" else "left"

    if subtitle:
        t_lines = title.count("\n") + 1
        # Place title comfortably below any top-right badge
        if badge:
            top_margin = max(h * 0.22, 0.026)
        else:
            top_margin = max(h * 0.16, 0.018)
        if t_lines == 1:
            title_y = y + h - top_margin
            sub_top = title_y - max(h * 0.12, 0.015)
        else:
            title_y = y + h - top_margin - 0.008
            sub_top = title_y - max(h * 0.19, 0.024)
        sub_y = (y + 0.010 + sub_top) / 2.0

        ax.text(
            tx,
            title_y,
            title,
            ha=ha,
            va="center",
            fontsize=title_size,
            fontweight="bold",
            color=title_color,
            linespacing=1.12,
            zorder=3,
        )
        ax.text(
            tx,
            sub_y,
            subtitle,
            ha=ha,
            va="center",
            fontsize=sub_size,
            color=sub_color,
            linespacing=1.26,
            zorder=3,
        )
    else:
        ax.text(
            tx,
            y + h / 2,
            title,
            ha=ha,
            va="center",
            fontsize=title_size,
            fontweight="bold",
            color=title_color,
            zorder=3,
        )

    if badge:
        bw = min(w * 0.56, max(0.080, len(badge) * 0.0063 + 0.016))
        bh = 0.023
        bx = x + w - bw - 0.008
        by = y + h - bh * 0.45
        bpatch = FancyBboxPatch(
            (bx, by),
            bw,
            bh,
            boxstyle="round,pad=0.002,rounding_size=0.008",
            facecolor=badge_color,
            edgecolor=WHITE,
            lw=0.8,
            zorder=4,
        )
        ax.add_patch(bpatch)
        ax.text(
            bx + bw / 2,
            by + bh / 2,
            badge,
            ha="center",
            va="center",
            fontsize=6.2,
            fontweight="bold",
            color=WHITE,
            zorder=5,
        )


def draw_arrow(
    ax,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    color: str = SLATE,
    lw: float = 1.5,
    rad: float = 0.0,
    style: str = "-|>",
    ls: str = "-",
    label: str = "",
    label_offset: tuple[float, float] = (0.0, 0.0),
    label_size: float = 7.2,
):
    arr = FancyArrowPatch(
        (x1, y1),
        (x2, y2),
        arrowstyle=style,
        mutation_scale=11.5,
        linewidth=lw,
        linestyle=ls,
        color=color,
        connectionstyle=f"arc3,rad={rad}",
        zorder=4,
    )
    ax.add_patch(arr)
    if label:
        mx = (x1 + x2) / 2 + label_offset[0]
        my = (y1 + y2) / 2 + label_offset[1]
        ax.text(
            mx,
            my,
            label,
            ha="center",
            va="center",
            fontsize=label_size,
            fontweight="bold",
            color=color,
            bbox=dict(boxstyle="round,pad=0.16", facecolor=WHITE, edgecolor="none", alpha=0.92),
            zorder=6,
        )


# ==============================================================================
# Diagram 1: Layered Tech Stack (IIT KGP Provided vs Open-Source / External)
# ==============================================================================
def make_diagram_01_tech_stack():
    fig, ax = plt.subplots(figsize=(14.0, 8.6), dpi=300)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor(WHITE)

    hdr = FancyBboxPatch((0.02, 0.910), 0.96, 0.072, boxstyle="round,pad=0.004,rounding_size=0.012",
                         facecolor=NAVY, edgecolor="none")
    ax.add_patch(hdr)
    ax.text(0.50, 0.956, "JanSahayak AI — Full-Stack Technology Architecture & Provenance",
            ha="center", va="center", fontsize=14.5, fontweight="bold", color=WHITE)
    ax.text(0.50, 0.926, "Clear separation of IIT Kharagpur Track B Provided Infrastructure vs. Open-Source / External Stack Built by Team",
            ha="center", va="center", fontsize=9.0, color="#CBD5E1")

    # Legend pills (generous width so text fits cleanly inside!)
    legend_items = [
        (0.03, 0.34, SAFFRON, LIGHT_SAFFRON, "IIT KGP Track B Provided (Hosted VMs & CA Certs)"),
        (0.39, 0.31, ACCENT_BLUE, LIGHT_BLUE, "Open-Source / Built by Team (Python + React)"),
        (0.72, 0.25, GREEN, LIGHT_GREEN, "External Live Services (Free / Zero-Key)"),
    ]
    for lx, lw_p, ec, fc, lbl in legend_items:
        p = FancyBboxPatch((lx, 0.858), lw_p, 0.032, boxstyle="round,pad=0.002,rounding_size=0.01",
                           facecolor=fc, edgecolor=ec, lw=1.3)
        ax.add_patch(p)
        ax.text(lx + lw_p / 2, 0.874, lbl, ha="center", va="center", fontsize=7.6, fontweight="bold", color=ec)

    # Layer strips with generous headroom for strip label above badges
    layers = [
        (0.690, 0.148, "L1: PRESENTATION, CIVIC UX & MULTILINGUAL VOICE UI", LIGHT_BLUE, ACCENT_BLUE),
        (0.505, 0.165, "L2: API GATEWAY, SECURITY, RBAC & AGENT ORCHESTRATION", LIGHT_PURPLE, PURPLE),
        (0.305, 0.180, "L3: AI MODELS, HYBRID RETRIEVAL & LIVE EXTERNAL TOOLS", LIGHT_SAFFRON, SAFFRON),
        (0.115, 0.170, "L4: LOCAL PERSISTENCE, INDEXING, OBSERVABILITY & DEVOPS", LIGHT_BG, SLATE),
    ]
    for ly, lh, ltitle, lbg, lec in layers:
        strip = FancyBboxPatch((0.02, ly), 0.96, lh, boxstyle="round,pad=0.004,rounding_size=0.012",
                               facecolor=lbg, edgecolor=lec, lw=1.1, alpha=0.55)
        ax.add_patch(strip)
        ax.text(0.034, ly + lh - 0.016, ltitle, ha="left", va="center", fontsize=8.3, fontweight="bold", color=lec)

    # L1 boxes
    draw_box(ax, 0.035, 0.700, 0.285, 0.098,
             "React 18 + TypeScript + Vite SPA",
             "Tailwind CSS • Civic GovTech UI\nCitizen Helpdesk • Scheme Explorer • Grievance Modal",
             facecolor=WHITE, edgecolor=ACCENT_BLUE, badge="TEAM BUILT", badge_color=ACCENT_BLUE)
    draw_box(ax, 0.340, 0.700, 0.215, 0.098,
             "SSE Streaming Client",
             "Live Agent Reasoning Steps\nProgress Feed + Sync Fallback",
             facecolor=WHITE, edgecolor=ACCENT_BLUE, badge="TEAM BUILT", badge_color=ACCENT_BLUE)
    draw_box(ax, 0.575, 0.700, 0.185, 0.098,
             "Multilingual Voice I/O",
             "Web Speech STT (6 Indian langs)\n+ Server MP3 Audio Player",
             facecolor=WHITE, edgecolor=ACCENT_BLUE, badge="TEAM BUILT", badge_color=ACCENT_BLUE)
    draw_box(ax, 0.780, 0.700, 0.185, 0.098,
             "Admin Observability UI",
             "Langfuse-Style Trace Explorer\nEval Dashboard + JSON/MD/CSV",
             facecolor=WHITE, edgecolor=ACCENT_BLUE, badge="TEAM BUILT", badge_color=ACCENT_BLUE)

    # L2 boxes
    draw_box(ax, 0.035, 0.517, 0.220, 0.115,
             "FastAPI + Uvicorn (1 Worker)",
             "Async REST + SSE Endpoints\nBackground CrossEncoder Pre-Warm\nVite Proxy (:5173 -> :8000)",
             facecolor=WHITE, edgecolor=ACCENT_BLUE, badge="OPEN SOURCE", badge_color=ACCENT_BLUE)
    draw_box(ax, 0.275, 0.517, 0.220, 0.115,
             "Auth, RBAC & Guardrails",
             "HMAC-SHA256 Bearer (5 Personas)\nDPDP PII Masker (Aadhaar/PAN)\nPrompt Injection & Fraud Shield",
             facecolor=WHITE, edgecolor=PURPLE, badge="TEAM BUILT", badge_color=PURPLE)
    draw_box(ax, 0.515, 0.517, 0.235, 0.115,
             "LangGraph Stateful Agent",
             "7-Node Compiled StateGraph\nPlanner -> Executor -> Synth -> Critic\n1-Shot Pydantic JSON Repair Loop",
             facecolor=WHITE, edgecolor=PURPLE, badge="OPEN SOURCE", badge_color=PURPLE)
    draw_box(ax, 0.770, 0.517, 0.195, 0.115,
             "Traffic & Budget Control",
             "15 RPM Session Rate Limiter\nTwo-Tier Exact + Semantic Cache\n8,192-Token Context Budgeter",
             facecolor=WHITE, edgecolor=PURPLE, badge="TEAM BUILT", badge_color=PURPLE)

    # L3 boxes
    draw_box(ax, 0.035, 0.317, 0.265, 0.130,
             "Qwen/Qwen3-8B LLM (Hosted VM)",
             "OpenAI-Compatible API • 8,192 ctx\nTLS Verify (llm-ca.crt) • No-Think\nSemaphore(1) • 55 RPM • 2/4/8s Retry",
             facecolor=LIGHT_SAFFRON, edgecolor=SAFFRON, title_color=SAFFRON, lw=2.0,
             badge="IIT KGP PROVIDED", badge_color=SAFFRON)
    draw_box(ax, 0.318, 0.317, 0.235, 0.130,
             "bge-small-en-v1.5 (VM02)",
             "384-Dim L2-Normalized Vectors\nBatch=16 • TLS Verify (vm02-ca.crt)\nSQLite Embedding Cache",
             facecolor=LIGHT_SAFFRON, edgecolor=SAFFRON, title_color=SAFFRON, lw=2.0,
             badge="IIT KGP PROVIDED", badge_color=SAFFRON)
    draw_box(ax, 0.571, 0.317, 0.195, 0.130,
             "Local CPU Reranker + BM25",
             "ms-marco-MiniLM-L-6-v2 (CPU)\nrank-bm25 (2x Title/Tag Boost)\nReciprocal Rank Fusion (k=60)",
             facecolor=WHITE, edgecolor=ACCENT_BLUE, badge="OPEN SOURCE", badge_color=ACCENT_BLUE)
    draw_box(ax, 0.784, 0.317, 0.181, 0.130,
             "Live External Services",
             "DuckDuckGo (.gov.in Fallback)\ngTTS + edge-tts (6-Lang Audio)\nGmail SMTP (Live Ticket Email)",
             facecolor=LIGHT_GREEN, edgecolor=GREEN, title_color=GREEN, lw=1.6,
             badge="EXTERNAL LIVE", badge_color=GREEN)

    # L4 boxes
    draw_box(ax, 0.035, 0.127, 0.235, 0.120,
             "SQLite WAL (jansahayak.db)",
             "649 Schemes • 7,724 FAQs • 51 Min.\nSessions, Messages, Grievances,\nTraces, Cache & Email Outbox",
             facecolor=WHITE, edgecolor=SLATE, badge="LOCAL DB", badge_color=SLATE)
    draw_box(ax, 0.288, 0.127, 0.220, 0.120,
             "Hybrid Vector & Sparse Index",
             "embeddings.npy (6,059 x 384)\nbm25.pkl (6,059 Tokenized Chunks)\nAll Chunks <= 440 Tokens (0 > 512)",
             facecolor=WHITE, edgecolor=SLATE, badge="LOCAL INDEX", badge_color=SLATE)
    draw_box(ax, 0.526, 0.127, 0.215, 0.120,
             "CPGRAMS Sandbox & Evals",
             "Mock PGPortal + Fault Injection\n80-Query Golden + 20 Red-Team\nLangfuse Spans & Eval Reports",
             facecolor=WHITE, edgecolor=SLATE, badge="TEAM BUILT", badge_color=SLATE)
    draw_box(ax, 0.759, 0.127, 0.206, 0.120,
             "Packaging & Verification",
             "Docker + docker-compose + Nginx\nstart_local.ps1 One-Click Launcher\n21 Pytest Unit/API + 9 E2E Tests",
             facecolor=WHITE, edgecolor=SLATE, badge="DEVOPS", badge_color=SLATE)

    ax.text(
        0.50,
        0.052,
        "Zero Paid Third-Party SaaS Dependencies: 100% reproducible on IIT Kharagpur Track B VMs + Local Python 3.11 / Node.js 20.\n"
        "Strict Compliance: Single-worker Uvicorn + Asyncio Semaphore(1) guarantees <= 1 active LLM call per group key; TLS CA verification enforced everywhere.",
        ha="center",
        va="center",
        fontsize=8.2,
        color=SLATE,
        bbox=dict(boxstyle="round,pad=0.45", facecolor=LIGHT_BG, edgecolor=BORDER, lw=1.0),
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    plt.savefig(OUT_DIR / "01_layered_tech_stack.png", dpi=300, bbox_inches="tight", pad_inches=0.12)
    plt.close(fig)


# ==============================================================================
# Diagram 2: End-to-End System & LangGraph Multi-Agent Architecture
# ==============================================================================
def make_diagram_02_system_architecture():
    fig, ax = plt.subplots(figsize=(14.8, 9.0), dpi=300)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor(WHITE)

    hdr = FancyBboxPatch((0.015, 0.915), 0.97, 0.070, boxstyle="round,pad=0.004,rounding_size=0.012",
                         facecolor=NAVY, edgecolor="none")
    ax.add_patch(hdr)
    ax.text(0.50, 0.960, "JanSahayak AI — End-to-End System & LangGraph Agentic Architecture",
            ha="center", va="center", fontsize=14.2, fontweight="bold", color=WHITE)
    ax.text(0.50, 0.930, "Frontend SPA <-> FastAPI Gateway <-> 7-Node LangGraph StateGraph <-> 5 Typed Tools <-> IIT KGP Hosted Models & Local Stores",
            ha="center", va="center", fontsize=8.8, color="#CBD5E1")

    # Left Column: Client & API Gateway
    draw_box(ax, 0.020, 0.720, 0.175, 0.170,
             "React 18 Web Client",
             "localhost:5173 (Vite)\n• Persona Login (RBAC)\n• Citizen Helpdesk (SSE)\n• 6-Lang Voice Mic & TTS\n• Scheme Explorer (649)\n• CPGRAMS Modal + Admin",
             facecolor=LIGHT_BLUE, edgecolor=ACCENT_BLUE, title_size=9.0, sub_size=7.0)

    draw_box(ax, 0.020, 0.480, 0.175, 0.185,
             "FastAPI Server (:8000)",
             "uvicorn --workers 1\n• HMAC Bearer Auth\n• 15 RPM Rate Limiter\n• Two-Tier Cache\n  (Exact + >=0.96 Sem.)\n• Pre-Warmed Reranker\n• POST /api/chat/stream",
             facecolor=WHITE, edgecolor=NAVY, title_size=9.0, sub_size=6.9)

    draw_box(ax, 0.020, 0.255, 0.175, 0.165,
             "Observability & DPDP",
             "• Langfuse Trace Spans\n  (SPN-01..N in SQLite)\n• JSON / MD / CSV Export\n• DELETE /api/sessions\n  (Right to Erasure)\n• Eval Benchmark Suites",
             facecolor=LIGHT_BG, edgecolor=SLATE, title_size=8.8, sub_size=6.9)

    draw_box(ax, 0.020, 0.045, 0.175, 0.155,
             "Voice & Email Services",
             "• POST /api/voice/tts\n  (gTTS + edge-tts, LRU)\n• Real Gmail SMTP TLS\n• Built-in HTML Outbox\n  (Zero-Setup Fallback)",
             facecolor=LIGHT_GREEN, edgecolor=GREEN, title_color=GREEN, title_size=8.8, sub_size=6.9)

    draw_arrow(ax, 0.115, 0.720, 0.115, 0.668, color=ACCENT_BLUE, label="HTTP / SSE", label_offset=(0.048, 0.0))
    draw_arrow(ax, 0.075, 0.668, 0.075, 0.720, color=ACCENT_BLUE, ls="--")
    draw_arrow(ax, 0.107, 0.480, 0.107, 0.423, color=SLATE, label="Traces", label_offset=(0.036, 0.0))
    draw_arrow(ax, 0.107, 0.255, 0.107, 0.203, color=GREEN, ls=":")

    # Center-Right Container: LangGraph Compiled State Machine (leave thin corridor on right for Executor->Tools arrow!)
    lg_bg = FancyBboxPatch((0.220, 0.435), 0.742, 0.455, boxstyle="round,pad=0.005,rounding_size=0.015",
                           facecolor=LIGHT_PURPLE, edgecolor=PURPLE, lw=1.6, alpha=0.42)
    ax.add_patch(lg_bg)
    ax.text(0.235, 0.873, "COMPILED LANGGRAPH MULTI-AGENT STATE MACHINE (backend/agent/graph.py)",
            ha="left", va="center", fontsize=8.8, fontweight="bold", color=PURPLE)

    # Top Row inside LangGraph (Nodes 1 -> 2 -> 3 -> 4)
    draw_box(ax, 0.233, 0.715, 0.156, 0.132,
             "1. InputGuardrail",
             "• Mask Aadhaar/PAN/\n  Phone/IFSC (DPDP)\n• Block Prompt Inject,\n  Fraud, CAPTCHA Bypass",
             facecolor=LIGHT_AMBER, edgecolor=AMBER, title_color=AMBER, title_size=8.5, sub_size=6.9)

    draw_box(ax, 0.413, 0.715, 0.156, 0.132,
             "2. LanguagePivot",
             "• Unicode Script Detect\n  (EN/HI/MR/BN/TA/TE)\n• Translate to Canonical\n  English (query_en)",
             facecolor=WHITE, edgecolor=PURPLE, title_size=8.5, sub_size=6.9)

    draw_box(ax, 0.593, 0.715, 0.160, 0.132,
             "3. Planner (Qwen3)",
             "• Classify 6 Intents\n• Extract Citizen Profile\n• Plan Tool Calls JSON\n• 1-Shot Schema Repair",
             facecolor=LIGHT_SAFFRON, edgecolor=SAFFRON, title_color=SAFFRON, title_size=8.5, sub_size=6.9)

    draw_box(ax, 0.777, 0.715, 0.172, 0.132,
             "4. Executor (Tools)",
             "• Dispatch Typed Tools\n• Auto-Chain Eligibility\n• Confidence Gate ->\n  .gov.in Web Fallback",
             facecolor=LIGHT_BLUE, edgecolor=ACCENT_BLUE, title_color=ACCENT_BLUE, title_size=8.5, sub_size=6.9)

    # Bottom Row inside LangGraph (Nodes 7 <- 6 <- 5)
    draw_box(ax, 0.777, 0.475, 0.172, 0.132,
             "5. Synthesizer (Qwen3)",
             "• Grounded Draft <=240w\n• Untrusted Evidence Tag\n• Mandatory [1],[2] Cites\n• Structured Citizen UX",
             facecolor=LIGHT_SAFFRON, edgecolor=SAFFRON, title_color=SAFFRON, title_size=8.5, sub_size=6.9)

    draw_box(ax, 0.550, 0.475, 0.192, 0.132,
             "6. Critic Auditor",
             "• Deterministic PII/Cite\n• LLM Groundedness &\n  Exclusion Verification\n• Max 1 Revision Loop",
             facecolor=LIGHT_AMBER, edgecolor=AMBER, title_color=AMBER, title_size=8.5, sub_size=6.9)

    draw_box(ax, 0.343, 0.475, 0.172, 0.132,
             "7. OutputLocalizer",
             "• Localize to User Lang\n  preserving [1] Links\n• Assemble Citations,\n  Cards & Trace Spans",
             facecolor=LIGHT_GREEN, edgecolor=GREEN, title_color=GREEN, title_size=8.5, sub_size=6.9)

    draw_box(ax, 0.233, 0.495, 0.088, 0.112,
             "Fast Exit",
             "Refusal /\nGreeting\n(0 RAG)",
             facecolor=LIGHT_RED, edgecolor=RED, title_color=RED, title_size=8.1, sub_size=6.9)

    # Arrows inside LangGraph
    draw_arrow(ax, 0.195, 0.625, 0.233, 0.765, color=NAVY, rad=-0.12)
    draw_arrow(ax, 0.389, 0.781, 0.413, 0.781, color=PURPLE)
    draw_arrow(ax, 0.569, 0.781, 0.593, 0.781, color=PURPLE)
    draw_arrow(ax, 0.753, 0.781, 0.777, 0.781, color=PURPLE)
    draw_arrow(ax, 0.863, 0.715, 0.863, 0.609, color=ACCENT_BLUE, label="Evidence", label_offset=(-0.042, 0.0))
    draw_arrow(ax, 0.777, 0.541, 0.744, 0.541, color=SAFFRON)
    draw_arrow(ax, 0.550, 0.541, 0.517, 0.541, color=GREEN, label="PASS", label_offset=(0.0, 0.025))
    draw_arrow(ax, 0.675, 0.607, 0.815, 0.607, color=RED, rad=-0.26, ls="--",
               label="FAIL (max 1 retry)", label_offset=(0.0, 0.044), label_size=6.7)
    draw_arrow(ax, 0.277, 0.715, 0.277, 0.609, color=RED, ls="--", label="Blocked", label_offset=(0.033, 0.0), label_size=6.7)

    # Route OutputLocalizer -> FastAPI cleanly BELOW Fast Exit (zero overlap!)
    ax.plot([0.429, 0.429, 0.208], [0.475, 0.448, 0.448], color=GREEN, lw=1.6, zorder=4)
    draw_arrow(ax, 0.208, 0.448, 0.197, 0.515, color=GREEN, rad=-0.12, label="SSE Done", label_offset=(0.068, -0.025), label_size=7.0)

    # Route Executor -> 5 Tools cleanly along right outer corridor (x=0.976, zero crossing over Synthesizer!)
    ax.plot([0.949, 0.976, 0.976], [0.781, 0.781, 0.370], color=ACCENT_BLUE, lw=1.6, ls="-.", zorder=4)
    draw_arrow(ax, 0.976, 0.370, 0.962, 0.370, color=ACCENT_BLUE, ls="-.")
    ax.text(0.976, 0.575, "Tool Calls", rotation=90, ha="center", va="center", fontsize=7.0,
            fontweight="bold", color=ACCENT_BLUE,
            bbox=dict(boxstyle="round,pad=0.14", facecolor=WHITE, edgecolor="none"))

    # Bottom Section: 5 Typed Tools
    tools_bg = FancyBboxPatch((0.220, 0.220), 0.742, 0.185, boxstyle="round,pad=0.004,rounding_size=0.012",
                              facecolor=LIGHT_BLUE, edgecolor=ACCENT_BLUE, lw=1.2, alpha=0.45)
    ax.add_patch(tools_bg)
    ax.text(0.235, 0.389, "5 STRICTLY TYPED PYDANTIC AGENT TOOLS (backend/agent/tools.py)",
            ha="left", va="center", fontsize=8.5, fontweight="bold", color=ACCENT_BLUE)

    t_specs = [
        ("T1: search_schemes", "BM25 + Dense + RRF\n+ CrossEncoder Rerank\n(6,059 chunks / 649)"),
        ("T2: check_eligibility", "Deterministic Rules:\nAge/Income/Caste/\nExclusions & Docs"),
        ("T3: web_search_gov", "DuckDuckGo Scoped\nSTRICTLY to .gov.in\n(if score < 0.35)"),
        ("T4: draft_grievance", "51-Ministry Routing\n<=2,000 Chars CPGRAMS\nPII Masked Draft"),
        ("T5: submit_or_track", "HITL Confirmation Gate\nMock PGPortal + SMTP\n+ Assisted Handoff"),
    ]
    tw = 0.136
    for i, (tname, tdesc) in enumerate(t_specs):
        tx = 0.231 + i * 0.145
        draw_box(ax, tx, 0.238, tw, 0.128, tname, tdesc,
                 facecolor=WHITE, edgecolor=BLUE, title_size=7.7, sub_size=6.8)

    # Bottom-most row: IIT KGP Gateways & Local Persistence
    draw_box(ax, 0.220, 0.045, 0.252, 0.142,
             "IIT KGP Hosted LLM Gateway",
             "Qwen/Qwen3-8B (103.42.50.41:1031)\nSingleton Semaphore(1) • 55 RPM\n8,192 Context Budget • <=1,024 Out\nTLS Verify (llm-ca.crt) • 2/4/8s Retry",
             facecolor=LIGHT_SAFFRON, edgecolor=SAFFRON, title_color=SAFFRON, lw=1.8, title_size=8.4, sub_size=6.9,
             badge="IIT KGP VM", badge_color=SAFFRON)

    draw_box(ax, 0.490, 0.045, 0.228, 0.142,
             "IIT KGP Embedding VM02",
             "bge-small-en-v1.5 (103.42.50.41:1035)\n384-Dim Vectors • Batch=16\nTLS Verify (vm02-ca.crt)\nSQLite Vector Cache",
             facecolor=LIGHT_SAFFRON, edgecolor=SAFFRON, title_color=SAFFRON, lw=1.8, title_size=8.4, sub_size=6.9,
             badge="IIT KGP VM02", badge_color=SAFFRON)

    draw_box(ax, 0.736, 0.045, 0.226, 0.142,
             "Local Knowledge & State Store",
             "SQLite WAL (jansahayak.db)\nembeddings.npy (6059x384 float32)\nbm25.pkl + CrossEncoder (CPU)\nCPGRAMS Sandbox + Email Outbox",
             facecolor=LIGHT_BG, edgecolor=SLATE, title_size=8.4, sub_size=6.9,
             badge="LOCAL DISK", badge_color=SLATE)

    draw_arrow(ax, 0.346, 0.220, 0.346, 0.190, color=SAFFRON, ls=":")
    draw_arrow(ax, 0.604, 0.220, 0.604, 0.190, color=SAFFRON, ls=":")
    draw_arrow(ax, 0.849, 0.220, 0.849, 0.190, color=SLATE, ls=":")

    plt.savefig(OUT_DIR / "02_system_architecture.png", dpi=300, bbox_inches="tight", pad_inches=0.12)
    plt.close(fig)


# ==============================================================================
# Diagram 3: Hybrid RAG, Chunking, Embedding & Reranking Pipeline
# ==============================================================================
def make_diagram_03_hybrid_rag():
    fig, ax = plt.subplots(figsize=(14.2, 8.4), dpi=300)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor(WHITE)

    hdr = FancyBboxPatch((0.02, 0.910), 0.96, 0.072, boxstyle="round,pad=0.004,rounding_size=0.012",
                         facecolor=NAVY, edgecolor="none")
    ax.add_patch(hdr)
    ax.text(0.50, 0.957, "JanSahayak AI — Data Ingestion, Chunking, Embedding & Agentic Hybrid RAG Pipeline",
            ha="center", va="center", fontsize=14.0, fontweight="bold", color=WHITE)
    ax.text(0.50, 0.927, "Offline Indexing (649 Schemes + 7,724 FAQs -> 6,059 Chunks)  +  Online Hybrid Retrieval (BM25 + Dense + RRF + Reranker + .gov.in Fallback)",
            ha="center", va="center", fontsize=8.7, color="#CBD5E1")

    # ---- TOP PANEL: OFFLINE INGESTION ----
    p1 = FancyBboxPatch((0.02, 0.560), 0.96, 0.328, boxstyle="round,pad=0.004,rounding_size=0.012",
                        facecolor=LIGHT_BG, edgecolor=BLUE, lw=1.4)
    ax.add_patch(p1)
    ax.text(0.035, 0.868, "PHASE A: OFFLINE DATA ETL, SECTION-AWARE CHUNKING & DUAL-INDEX BUILD (scripts/ingest_data.py)",
            ha="left", va="center", fontsize=8.9, fontweight="bold", color=BLUE)

    draw_box(ax, 0.035, 0.625, 0.165, 0.215,
             "Raw myScheme Data",
             "• 649 Central Schemes\n  (updated_data.csv)\n• 7,724 Official FAQs\n  (scheme_faqs.csv)\n• 51 Canonical Ministries",
             facecolor=WHITE, edgecolor=SLATE, title_size=8.6, sub_size=7.2)

    draw_box(ax, 0.223, 0.625, 0.175, 0.215,
             "Deterministic ETL",
             "backend/retrieval/etl.py\n• Regex Extract: Age Bounds,\n  Income Cap, Caste, DBT Flag,\n  Beneficiary Groups\n• 51-Ministry Code Map",
             facecolor=WHITE, edgecolor=BLUE, title_size=8.6, sub_size=7.1)

    draw_box(ax, 0.421, 0.625, 0.184, 0.215,
             "Section-Aware Chunker",
             "backend/retrieval/chunker.py\n• Overview, Benefits, Eligibility,\n  Docs, Application, Exclusions,\n  and Grouped FAQs\n• Max 440 tok (0 > 512!)\n• Output: 6,059 Chunks",
             facecolor=LIGHT_BLUE, edgecolor=ACCENT_BLUE, title_size=8.6, sub_size=7.0)

    draw_box(ax, 0.630, 0.742, 0.168, 0.105,
             "Dense Embeddings",
             "bge-small-en-v1.5 (VM02)\nBatch=16 (379 Batches)\nL2-Norm 384-Dim Float32",
             facecolor=LIGHT_SAFFRON, edgecolor=SAFFRON, title_color=SAFFRON, title_size=8.4, sub_size=7.0)

    draw_box(ax, 0.630, 0.618, 0.168, 0.108,
             "Sparse BM25 Index",
             "rank-bm25 BM25Okapi\n2x Title & Tag Boosting\nExact Acronyms (PM-KISAN)",
             facecolor=LIGHT_PURPLE, edgecolor=PURPLE, title_color=PURPLE, title_size=8.4, sub_size=7.0)

    draw_box(ax, 0.822, 0.618, 0.144, 0.228,
             "Persisted Artifacts",
             "• embeddings.npy\n  (6059 x 384, ~9 MB)\n• bm25.pkl\n  (Tokenized Index)\n• jansahayak.db\n  (chunks_meta +\n   schemes_catalog)",
             facecolor=LIGHT_GREEN, edgecolor=GREEN, title_color=GREEN, title_size=8.5, sub_size=7.0)

    draw_arrow(ax, 0.200, 0.732, 0.221, 0.732, color=BLUE)
    draw_arrow(ax, 0.398, 0.732, 0.419, 0.732, color=BLUE)
    draw_arrow(ax, 0.605, 0.770, 0.628, 0.790, color=SAFFRON)
    draw_arrow(ax, 0.605, 0.692, 0.628, 0.672, color=PURPLE)
    draw_arrow(ax, 0.798, 0.790, 0.820, 0.768, color=GREEN)
    draw_arrow(ax, 0.798, 0.672, 0.820, 0.695, color=GREEN)

    ax.text(0.50, 0.582,
            "Why Section-Aware Chunking? Keeps Eligibility & Exclusions intact with Scheme Title/Ministry headers -> prevents 'lost-in-the-middle' & fits bge-small's 512-token cap.",
            ha="center", va="center", fontsize=7.8, style="italic", color=SLATE)

    # ---- BOTTOM PANEL: ONLINE HYBRID RAG ----
    p2 = FancyBboxPatch((0.02, 0.042), 0.96, 0.498, boxstyle="round,pad=0.004,rounding_size=0.012",
                        facecolor=WHITE, edgecolor=GREEN, lw=1.4)
    ax.add_patch(p2)
    ax.text(0.035, 0.520, "PHASE B: ONLINE AGENTIC HYBRID RETRIEVAL, FUSION, RERANKING & WEB FALLBACK (backend/retrieval/hybrid_retriever.py)",
            ha="left", va="center", fontsize=8.9, fontweight="bold", color=GREEN)

    draw_box(ax, 0.035, 0.268, 0.148, 0.205,
             "1. Canonical Query",
             "English Pivot (query_en)\n+ Citizen Profile\nPermissive Metadata Filter\n(null fields NEVER exclude;\nauto-relaxes if <5 hits)",
             facecolor=LIGHT_BLUE, edgecolor=ACCENT_BLUE, title_size=8.3, sub_size=6.9)

    draw_box(ax, 0.208, 0.375, 0.175, 0.115,
             "2a. Sparse BM25 (Top 30)",
             "Exact Lexical Match:\nAcronyms (PMEGP, MUDRA),\nLoan Limits, Age/Caste Terms",
             facecolor=LIGHT_PURPLE, edgecolor=PURPLE, title_color=PURPLE, title_size=8.2, sub_size=6.9)

    draw_box(ax, 0.208, 0.232, 0.175, 0.125,
             "2b. Dense Search (Top 30)",
             "Embed Query via VM02\nCosine Similarity (np.dot)\nSemantic Paraphrase Match\n('nuts & bolts' -> 'MSME')",
             facecolor=LIGHT_SAFFRON, edgecolor=SAFFRON, title_color=SAFFRON, title_size=8.2, sub_size=6.9)

    draw_box(ax, 0.410, 0.268, 0.168, 0.205,
             "3. Reciprocal Rank\nFusion (RRF, k=60)",
             "Score(d) = 1/(60 + r_BM25)\n         + 1/(60 + r_Dense)\nMerges Top-30 + Top-30\n-> Top-20 Candidates\n(Recall@5 = 95.9%!)",
             facecolor=LIGHT_BLUE, edgecolor=BLUE, title_size=8.2, sub_size=6.9)

    draw_box(ax, 0.605, 0.268, 0.175, 0.205,
             "4. Cross-Encoder\nReranker (Local CPU)",
             "ms-marco-MiniLM-L-6-v2\nJoint (Query, Chunk) Attention\nSigmoid Calibrated [0..1]\nSelects Top-6 Evidence Chunks\n(Pre-warmed at Startup)",
             facecolor=LIGHT_GREEN, edgecolor=GREEN, title_color=GREEN, title_size=8.2, sub_size=6.9)

    draw_box(ax, 0.822, 0.342, 0.144, 0.150,
             "5a. Grounded Context",
             "Score >= 0.35 (High Conf.)\nWrap in Untrusted Tag\n+ Numbered Citations [1..6]\n-> Synthesizer + Critic",
             facecolor=LIGHT_GREEN, edgecolor=GREEN, title_color=GREEN, title_size=8.1, sub_size=6.8)

    draw_box(ax, 0.822, 0.105, 0.144, 0.178,
             "5b. .gov.in Fallback",
             "IF top_rerank < 0.35:\nDuckDuckGo Scoped to\nsite:gov.in / nic.in\n+ Indirect Injection Strip\n+ Freshness Timestamp",
             facecolor=LIGHT_AMBER, edgecolor=AMBER, title_color=AMBER, title_size=8.1, sub_size=6.8)

    draw_box(ax, 0.035, 0.068, 0.755, 0.128,
             "Why Agentic Hybrid RAG Beats Vanilla RAG on Indian Welfare Schemes",
             "1. BM25 catches exact scheme codes (PM-KISAN, PMEGP, MUDRA) while Dense bge-small catches colloquial phrasing ('start nuts & bolts factory').\n"
             "2. RRF merges rankings without fragile score normalization (Recall@5 jumps 93.2% -> 95.9%; MRR@10 hits 0.925).\n"
             "3. Cross-Encoder gives calibrated relevance [0..1] to reliably detect unknown/fabricated schemes (RT-20: 0.280 -> honest refusal) & trigger .gov.in fallback.",
             facecolor=LIGHT_BG, edgecolor=BORDER, title_size=8.5, sub_size=7.2, align="left")

    draw_arrow(ax, 0.183, 0.410, 0.206, 0.430, color=PURPLE)
    draw_arrow(ax, 0.183, 0.325, 0.206, 0.295, color=SAFFRON)
    draw_arrow(ax, 0.383, 0.430, 0.408, 0.400, color=PURPLE)
    draw_arrow(ax, 0.383, 0.295, 0.408, 0.340, color=SAFFRON)
    draw_arrow(ax, 0.578, 0.370, 0.603, 0.370, color=BLUE)
    draw_arrow(ax, 0.780, 0.415, 0.820, 0.415, color=GREEN, label=">=0.35", label_offset=(-0.002, 0.025), label_size=6.7)
    draw_arrow(ax, 0.780, 0.315, 0.820, 0.220, color=AMBER, ls="--", label="<0.35", label_offset=(0.002, 0.032), label_size=6.7)

    plt.savefig(OUT_DIR / "03_hybrid_rag_pipeline.png", dpi=300, bbox_inches="tight", pad_inches=0.12)
    plt.close(fig)


# ==============================================================================
# Diagram 4: Live Data Flow Diagram (Mumbai 25yo MRO Nuts & Bolts Loan Query)
# ==============================================================================
def make_diagram_04_live_data_flow():
    if not CAPTURE_PATH.exists():
        print("[SKIP] Diagram 04 waiting for live_walkthrough_capture.json")
        return
    cap = json.loads(CAPTURE_PATH.read_text(encoding="utf-8"))

    chunks = cap.get("retrieved_chunks") or []
    lats = cap.get("step_latencies") or {}
    trace_id = cap.get("trace_id", "TRC-DB1E35A90D")
    ptok = cap.get("prompt_tokens", 0)
    ctok = cap.get("completion_tokens", 0)
    spans = cap.get("spans") or []

    g_ms = lats.get("input_guardrail_ms", 0.13)
    l_ms = lats.get("language_pivot_ms", 0.08)
    p_ms = lats.get("planner_ms", 2891.27)
    e_ms = lats.get("executor_ms", 41443.37)
    syn_ms = lats.get("synthesizer_ms", 11787.37)
    cr_ms = lats.get("critic_ms", 3822.92)
    loc_ms = lats.get("output_localizer_ms", 0.31)

    fig, ax = plt.subplots(figsize=(14.6, 9.4), dpi=300)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor(WHITE)

    # Taller header banner so 2-line prompt fits cleanly with generous margin
    hdr = FancyBboxPatch((0.02, 0.898), 0.96, 0.088, boxstyle="round,pad=0.004,rounding_size=0.012",
                         facecolor=NAVY, edgecolor="none")
    ax.add_patch(hdr)
    ax.text(0.50, 0.963, f"Live End-to-End Request Data Flow — Real Captured Trace ({trace_id})",
            ha="center", va="center", fontsize=14.0, fontweight="bold", color=WHITE)
    ax.text(
        0.50,
        0.923,
        'Live Prompt: "Hi, I am a 25 year old male looking for Loan to start my small business of Small parts\n'
        'manufacturing like nuts, bolts and other MRO parts in Mumbai, I am eligible for which scheme?"',
        ha="center",
        va="center",
        fontsize=8.3,
        color="#FDE68A",
        fontweight="bold",
        linespacing=1.25,
    )

    bw, bh = 0.286, 0.182
    xs = [0.028, 0.357, 0.686]
    ys = [0.680, 0.405, 0.130]

    # Step 1
    draw_box(ax, xs[0], ys[0], bw, bh,
             "Step 1: React UI -> FastAPI SSE",
             "• Browser POST /api/chat/stream\n• HMAC Bearer Token verified (RBAC)\n• Rate Limiter: 1 / 15 RPM (PASS)\n• Two-Tier Cache: MISS (fresh query)\n• Start Trace ID & Span Clock",
             facecolor=LIGHT_BLUE, edgecolor=ACCENT_BLUE, title_size=8.9, sub_size=7.2,
             badge="HTTP SSE", badge_color=ACCENT_BLUE)

    # Step 2
    draw_box(ax, xs[1], ys[0], bw, bh,
             "Step 2: Guardrail & Language Pivot",
             f"• SPN-01 PII Scan: 0 leaks ({g_ms:.2f} ms)\n• Injection / Fraud Shield: SAFE\n• SPN-02 Script Detect: 'en' ({l_ms:.2f} ms)\n• Canonical query_en passed directly\n  (0 translation tokens spent)",
             facecolor=LIGHT_AMBER, edgecolor=AMBER, title_color=AMBER, title_size=8.9, sub_size=7.2,
             badge=f"{g_ms + l_ms:.2f} ms", badge_color=AMBER)

    # Step 3
    draw_box(ax, xs[2], ys[0], bw, bh,
             "Step 3: Planner Node (Qwen3-8B)",
             "• SPN-03 Intent: ELIGIBILITY_CHECK\n• Auto-Extracted Citizen Profile:\n  age=25, Male, state=Maharashtra (Mumbai!)\n  occ='Small parts manufacturing'\n• Planned: search_schemes(top_k=6) • Valid JSON",
             facecolor=LIGHT_SAFFRON, edgecolor=SAFFRON, title_color=SAFFRON, title_size=8.9, sub_size=7.1,
             badge=f"{p_ms:.0f} ms | 1,008 tok", badge_color=SAFFRON)

    # Step 4 (Row 2, Right)
    draw_box(ax, xs[2], ys[1], bw, bh,
             "Step 4: Hybrid RAG + .gov.in Fallback",
             "• SPN-04 BM25 + bge-small Dense -> RRF -> Rerank\n• Dense surfaced PM Vishwakarma (0.742) &\n  PMEGP (0.722) even where BM25 = 0.0!\n• Top rerank = 0.0038 (<0.35 threshold) ->\n  Auto-triggered DuckDuckGo .gov.in fallback",
             facecolor=LIGHT_BLUE, edgecolor=BLUE, title_size=8.9, sub_size=7.0,
             badge="6 chunks | 3 tools", badge_color=BLUE)

    # Step 5 (Row 2, Mid)
    draw_box(ax, xs[1], ys[1], bw, bh,
             "Step 5: Auto-Chain check_eligibility",
             "• Auto-checked #1 chunk (nssw: New Swarnima)\n• Eligibility Excerpt: 'Must be a Female' ->\n  Synthesizer safely excluded it for Male user!\n• Retained PM Vishwakarma [2][4][6] &\n  PMEGP [5] from Ministry of MSME",
             facecolor=LIGHT_PURPLE, edgecolor=PURPLE, title_color=PURPLE, title_size=8.9, sub_size=7.0,
             badge="1.6s warm / 41s cold", badge_color=PURPLE)

    # Step 6 (Row 2, Left)
    draw_box(ax, xs[0], ys[1], bw, bh,
             "Step 6: Grounded Synthesizer (Qwen3)",
             "• Wraps 6 Chunks in <RETRIEVED_EVIDENCE>\n• Round 0 (SPN-05, 5.89s, 2,883 tok):\n  Recommended PM Vishwakarma, cited [2]\n• Round 1 Revision (SPN-07, 5.90s, 2,932 tok):\n  Corrected citations to [2], [4] & [6]!",
             facecolor=LIGHT_SAFFRON, edgecolor=SAFFRON, title_color=SAFFRON, title_size=8.9, sub_size=7.0,
             badge=f"{syn_ms/1000:.2f}s (2 passes)", badge_color=SAFFRON)

    # Step 7 (Row 3, Left)
    draw_box(ax, xs[0], ys[2], bw, bh,
             "Step 7: Critic Audit & Revision Loop!",
             "• SPN-06 LLM Critic (3.82s, 1,209 tok):\n  CAUGHT wrong citation [2] for ₹1L/₹2L loan\n  & Ration card -> Triggered 1 Revision Loop!\n• SPN-08 Re-Check (0.61 ms, 0 tok):\n  PASSED! Citations [2][4][6] verified.",
             facecolor=LIGHT_GREEN, edgecolor=GREEN, title_color=GREEN, title_size=8.9, sub_size=7.0,
             badge="CAUGHT & FIXED!", badge_color=GREEN)

    # Step 8 (Row 3, Mid)
    draw_box(ax, xs[1], ys[2], bw, bh,
             "Step 8: Localizer & SQLite Persist",
             f"• SPN-09 OutputLocalizer: 'en' ({loc_ms:.2f} ms)\n• Persists Session Profile (Maharashtra, 25M)\n• Saves all {len(spans)} Langfuse Spans ({trace_id})\n• Writes Response to Two-Tier SQLite Cache\n  (Next repeat returns in <50 ms, 0 LLM tok!)",
             facecolor=LIGHT_BG, edgecolor=SLATE, title_size=8.9, sub_size=7.0,
             badge=f"{ptok + ctok:,} total tok", badge_color=SLATE)

    # Step 9 (Row 3, Right)
    draw_box(ax, xs[2], ys[2], bw, bh,
             "Step 9: Live SSE Render in Browser",
             "• Streams PM Vishwakarma recommendation:\n  ₹1L + ₹2L collateral-free loans [6], Docs [4],\n  Eligibility [2] + official portal link\n• Enables 'Listen' (6-Lang MP3 TTS) &\n  one-click 'Raise Grievance' workflow",
             facecolor=LIGHT_GREEN, edgecolor=GREEN, title_color=GREEN, title_size=8.9, sub_size=7.0,
             badge="DELIVERED", badge_color=GREEN)

    # Snake Arrows
    draw_arrow(ax, xs[0] + bw, ys[0] + bh/2, xs[1], ys[0] + bh/2, color=NAVY)
    draw_arrow(ax, xs[1] + bw, ys[0] + bh/2, xs[2], ys[0] + bh/2, color=NAVY)
    draw_arrow(ax, xs[2] + bw/2, ys[0], xs[2] + bw/2, ys[1] + bh, color=BLUE, label="Tool Dispatch", label_offset=(0.056, 0.0))
    draw_arrow(ax, xs[2], ys[1] + bh/2, xs[1] + bw, ys[1] + bh/2, color=PURPLE)
    draw_arrow(ax, xs[1], ys[1] + bh/2, xs[0] + bw, ys[1] + bh/2, color=SAFFRON)
    draw_arrow(ax, xs[0] + bw/2, ys[1], xs[0] + bw/2, ys[2] + bh, color=GREEN, label="Draft / Revise", label_offset=(0.058, 0.0))
    draw_arrow(ax, xs[0] + bw, ys[2] + bh/2, xs[1], ys[2] + bh/2, color=GREEN)
    draw_arrow(ax, xs[1] + bw, ys[2] + bh/2, xs[2], ys[2] + bh/2, color=GREEN)

    # Bottom summary metrics strip
    ax.text(
        0.50,
        0.052,
        f"Real Trace {trace_id}:  4 LLM Calls = {ptok:,} prompt + {ctok:,} completion ({ptok+ctok:,} tok)  |  "
        f"9 Langfuse Spans  |  Warm Server Latency ~21s (59.95s CLI run includes ~38s cold CrossEncoder load)  |  Critic Caught & Repaired Citations Live!",
        ha="center",
        va="center",
        fontsize=8.0,
        fontweight="bold",
        color=NAVY,
        bbox=dict(boxstyle="round,pad=0.48", facecolor=LIGHT_BLUE, edgecolor=ACCENT_BLUE, lw=1.2),
    )

    plt.savefig(OUT_DIR / "04_live_data_flow_mumbai_mro.png", dpi=300, bbox_inches="tight", pad_inches=0.12)
    plt.close(fig)


# ==============================================================================
# Diagram 5: Quantitative Evaluation Benchmarks (R1-R4, P1-P3, Safety/Faults)
# ==============================================================================
def make_diagram_05_eval_benchmarks():
    ret_data = json.loads((PROJECT_ROOT / "eval" / "reports" / "retrieval_ablation.json").read_text(encoding="utf-8"))
    prm_data = json.loads((PROJECT_ROOT / "eval" / "reports" / "prompt_comparison.json").read_text(encoding="utf-8"))

    fig = plt.figure(figsize=(14.6, 5.9), dpi=300)
    fig.patch.set_facecolor(WHITE)
    gs = fig.add_gridspec(1, 3, wspace=0.29, top=0.79, bottom=0.16, left=0.05, right=0.98)

    fig.suptitle(
        "JanSahayak AI — Verified Track B Quantitative Evaluation Results (Real Live Runs)",
        fontsize=14.0,
        fontweight="bold",
        color=NAVY,
        y=0.95,
    )
    fig.text(
        0.50,
        0.885,
        "Evaluated on 80-Query Golden Dataset (73 Retrieval + 30 Stratified Prompting), 15 Agent Fault Scenarios & 20 Red-Team Adversarial Attacks",
        ha="center",
        fontsize=9.0,
        color=SLATE,
    )

    # Panel 1: Retrieval Ablation R1-R4
    ax1 = fig.add_subplot(gs[0, 0])
    cfgs = ret_data["configs"]
    labels = [c["id"] for c in cfgs]
    r5 = [c["recall_at_5"] * 100 for c in cfgs]
    mrr = [c["mrr_at_10"] * 100 for c in cfgs]
    ndcg = [c["ndcg_at_5"] * 100 for c in cfgs]

    x = np.arange(len(labels))
    w = 0.26
    b1 = ax1.bar(x - w, r5, w, label="Recall@5 (%)", color=NAVY)
    b2 = ax1.bar(x, mrr, w, label="MRR@10 (x100)", color=ACCENT_BLUE)
    b3 = ax1.bar(x + w, ndcg, w, label="NDCG@5 (x100)", color=SAFFRON)

    for bars in (b1, b2, b3):
        for bar in bars:
            h = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width() / 2, h + 0.55, f"{h:.1f}", ha="center", va="bottom", fontsize=6.4, fontweight="bold")

    ax1.set_ylim(80, 102)
    ax1.set_xticks(x)
    ax1.set_xticklabels(["R1\nBM25", "R2\nDense", "R3\nHybrid\nRRF", "R4\nHybrid+\nRerank"], fontsize=8.0)
    ax1.set_ylabel("Score (% / x100)", fontsize=8.5, fontweight="bold", color=NAVY)
    ax1.set_title("A. Retrieval Ablation (73 Queries)", fontsize=10.2, fontweight="bold", color=NAVY, pad=10)
    ax1.legend(loc="lower right", fontsize=7.2, frameon=True)
    ax1.grid(axis="y", linestyle="--", alpha=0.4)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)

    # Panel 2: Prompting Comparison P1-P3 (wider spacing so 100% labels never collide)
    ax2 = fig.add_subplot(gs[0, 1])
    strats = prm_data["strategies"]
    s_labels = ["P1\nZero-Shot", "P2\nFew-Shot", "P3\nPlanner+\nCritic"]
    acc = [s["answer_accuracy"] * 100 for s in strats]
    cite = [s["citation_adherence"] * 100 for s in strats]
    hall = [s["hallucination_rate"] * 100 for s in strats]

    x2 = np.arange(len(s_labels))
    w2 = 0.25
    p1 = ax2.bar(x2 - 0.27, acc, w2, label="Accuracy (%)", color=GREEN)
    p2 = ax2.bar(x2, cite, w2, label="Citations (%)", color=ACCENT_BLUE)
    p3 = ax2.bar(x2 + 0.27, hall, w2, label="Hallucination (%)", color=RED)

    for bars in (p1, p2, p3):
        for bar in bars:
            h = bar.get_height()
            lbl = "100%" if h >= 99.9 else f"{h:.1f}%"
            ax2.text(bar.get_x() + bar.get_width() / 2, h + 1.6, lbl, ha="center", va="bottom", fontsize=6.6, fontweight="bold")

    ax2.set_ylim(0, 114)
    ax2.set_xticks(x2)
    ax2.set_xticklabels(s_labels, fontsize=8.2)
    ax2.set_ylabel("Percentage (%)", fontsize=8.5, fontweight="bold", color=NAVY)
    ax2.set_title("B. Prompt Engineering on Qwen3-8B (30 Qs)", fontsize=10.2, fontweight="bold", color=NAVY, pad=10)
    ax2.legend(loc="center right", fontsize=7.2, frameon=True)
    ax2.grid(axis="y", linestyle="--", alpha=0.4)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)

    # Panel 3: Agent Reliability & Safety Hardening
    ax3 = fig.add_subplot(gs[0, 2])
    cats = [
        "Red-Team\n(Before Fix)",
        "Red-Team\n(Hardened)",
        "PII Masking\n(DPDP)",
        "JSON Repair\n(5 Faults)",
        "Fault Fallback\n(503/BadJSON)",
        "HITL Gate\nEnforcement",
    ]
    vals = [80.0, 100.0, 100.0, 100.0, 100.0, 100.0]
    cols = [AMBER, GREEN, GREEN, ACCENT_BLUE, ACCENT_BLUE, PURPLE]

    y3 = np.arange(len(cats))
    bars3 = ax3.barh(y3, vals, height=0.58, color=cols)
    for bar, v in zip(bars3, vals):
        ax3.text(v + 1.5, bar.get_y() + bar.get_height() / 2, f"{v:.0f}%", va="center", ha="left", fontsize=8.2, fontweight="bold", color=NAVY)

    ax3.set_xlim(0, 116)
    ax3.set_yticks(y3)
    ax3.set_yticklabels(cats, fontsize=7.8)
    ax3.invert_yaxis()
    ax3.set_xlabel("Pass Rate (%)", fontsize=8.5, fontweight="bold", color=NAVY)
    ax3.set_title("C. Agent Reliability & Red-Team Safety", fontsize=10.2, fontweight="bold", color=NAVY, pad=10)
    ax3.grid(axis="x", linestyle="--", alpha=0.4)
    ax3.spines["top"].set_visible(False)
    ax3.spines["right"].set_visible(False)

    plt.savefig(OUT_DIR / "05_eval_benchmarks.png", dpi=300, bbox_inches="tight", pad_inches=0.14)
    plt.close(fig)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    make_diagram_01_tech_stack()
    print("[OK] Generated 01_layered_tech_stack.png")
    make_diagram_02_system_architecture()
    print("[OK] Generated 02_system_architecture.png")
    make_diagram_03_hybrid_rag()
    print("[OK] Generated 03_hybrid_rag_pipeline.png")
    make_diagram_04_live_data_flow()
    if (OUT_DIR / "04_live_data_flow_mumbai_mro.png").exists():
        print("[OK] Generated 04_live_data_flow_mumbai_mro.png")
    make_diagram_05_eval_benchmarks()
    print("[OK] Generated 05_eval_benchmarks.png")


if __name__ == "__main__":
    main()
