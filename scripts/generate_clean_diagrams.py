"""Generate clean, low-text, executive-grade Architecture & Data Flow Diagrams (Mentor Feedback Upgrade).

Design principles per Mentor 24 Nov Sync-Up:
- Large, bold, high-contrast box titles (11-13pt) with at most 1 concise subtitle line (no dense bullet paragraphs!).
- Thick, unmistakable directional arrows (lw=2.4, large arrowheads) with crisp pill labels.
- Generous whitespace so every diagram reads effortlessly on a 16:9 PowerPoint slide AND in a 7-8 page Word report.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Circle

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = PROJECT_ROOT / "docs" / "diagrams"

# Crisp Civic Executive Palette
NAVY = "#0B2239"
BLUE = "#1D4ED8"
LIGHT_BLUE = "#EFF6FF"
TEAL = "#0F766E"
LIGHT_TEAL = "#F0FDFA"
PURPLE = "#6D28D9"
LIGHT_PURPLE = "#F5F3FF"
SAFFRON = "#D95D14"
LIGHT_SAFFRON = "#FFF4EB"
GREEN = "#15803D"
LIGHT_GREEN = "#ECFDF5"
AMBER = "#B45309"
LIGHT_AMBER = "#FFFBEB"
RED = "#B91C1C"
LIGHT_RED = "#FEF2F2"
SLATE = "#334155"
LIGHT_SLATE = "#F8FAFC"
BORDER = "#CBD5E1"
WHITE = "#FFFFFF"

plt.rcParams["font.family"] = "DejaVu Sans"


def clean_box(
    ax,
    x: float,
    y: float,
    w: float,
    h: float,
    title: str,
    sub: str = "",
    edge: str = NAVY,
    face: str = WHITE,
    title_color: str | None = None,
    title_size: float = 11.2,
    sub_size: float = 8.4,
    lw: float = 2.0,
    badge: str | None = None,
    badge_bg: str = NAVY,
):
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.004,rounding_size=0.014",
        facecolor=face,
        edgecolor=edge,
        linewidth=lw,
        zorder=3,
    )
    ax.add_patch(patch)

    if sub:
        ax.text(
            x + w / 2,
            y + h * 0.62,
            title,
            ha="center",
            va="center",
            fontsize=title_size,
            fontweight="bold",
            color=title_color or edge,
            linespacing=1.12,
            zorder=4,
        )
        ax.text(
            x + w / 2,
            y + h * 0.24,
            sub,
            ha="center",
            va="center",
            fontsize=sub_size,
            color=SLATE,
            linespacing=1.18,
            zorder=4,
        )
    else:
        ax.text(
            x + w / 2,
            y + h / 2,
            title,
            ha="center",
            va="center",
            fontsize=title_size,
            fontweight="bold",
            color=title_color or edge,
            linespacing=1.15,
            zorder=4,
        )

    if badge:
        bw = min(w * 0.65, max(0.068, len(badge) * 0.0072 + 0.016))
        bh = 0.026
        bx = x + w - bw - 0.006
        by = y + h - bh * 0.50
        bp = FancyBboxPatch(
            (bx, by),
            bw,
            bh,
            boxstyle="round,pad=0.002,rounding_size=0.008",
            facecolor=badge_bg,
            edgecolor=WHITE,
            lw=1.0,
            zorder=5,
        )
        ax.add_patch(bp)
        ax.text(
            bx + bw / 2,
            by + bh / 2,
            badge,
            ha="center",
            va="center",
            fontsize=7.0,
            fontweight="bold",
            color=WHITE,
            zorder=6,
        )


def clean_arrow(
    ax,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    color: str = NAVY,
    label: str = "",
    rad: float = 0.0,
    ls: str = "-",
    lw: float = 2.4,
    lbl_pos: tuple[float, float] | None = None,
    lbl_size: float = 8.2,
    hop: str = "",
    hop_pos: tuple[float, float] | None = None,
):
    arr = FancyArrowPatch(
        (x1, y1),
        (x2, y2),
        arrowstyle="-|>",
        mutation_scale=17,
        linewidth=lw,
        linestyle=ls,
        color=color,
        connectionstyle=f"arc3,rad={rad}",
        zorder=7,
    )
    ax.add_patch(arr)
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    if label:
        lx, ly = lbl_pos if lbl_pos else (mx, my)
        ax.text(
            lx,
            ly,
            label,
            ha="center",
            va="center",
            fontsize=lbl_size,
            fontweight="bold",
            color=color,
            bbox=dict(boxstyle="round,pad=0.22", facecolor=WHITE, edgecolor=color, lw=0.9, alpha=0.97),
            zorder=9,
        )
    if hop:
        hx, hy = hop_pos if hop_pos else (mx, my)
        c = Circle((hx, hy), radius=0.012, facecolor=color, edgecolor=WHITE, lw=1.2, zorder=10)
        ax.add_patch(c)
        ax.text(hx, hy, hop, ha="center", va="center", fontsize=7.6, fontweight="bold", color=WHITE, zorder=11)


def clean_ortho(
    ax,
    pts: list[tuple[float, float]],
    color: str = NAVY,
    label: str = "",
    ls: str = "-",
    lw: float = 2.4,
    lbl_pos: tuple[float, float] | None = None,
    lbl_size: float = 8.0,
    hop: str = "",
    hop_pos: tuple[float, float] | None = None,
):
    if len(pts) > 2:
        ax.plot([p[0] for p in pts[:-1]], [p[1] for p in pts[:-1]], color=color, lw=lw, linestyle=ls, zorder=6)
    arr = FancyArrowPatch(
        pts[-2],
        pts[-1],
        arrowstyle="-|>",
        mutation_scale=17,
        linewidth=lw,
        linestyle=ls,
        color=color,
        zorder=7,
    )
    ax.add_patch(arr)
    if label and lbl_pos:
        ax.text(
            lbl_pos[0],
            lbl_pos[1],
            label,
            ha="center",
            va="center",
            fontsize=lbl_size,
            fontweight="bold",
            color=color,
            bbox=dict(boxstyle="round,pad=0.22", facecolor=WHITE, edgecolor=color, lw=0.9, alpha=0.97),
            zorder=9,
        )
    if hop and hop_pos:
        c = Circle(hop_pos, radius=0.012, facecolor=color, edgecolor=WHITE, lw=1.2, zorder=10)
        ax.add_patch(c)
        ax.text(hop_pos[0], hop_pos[1], hop, ha="center", va="center", fontsize=7.6, fontweight="bold", color=WHITE, zorder=11)


def draw_lane(ax, y: float, h: float, title: str, bg: str, edge: str):
    lane = FancyBboxPatch((0.015, y), 0.970, h, boxstyle="round,pad=0.002,rounding_size=0.012",
                          facecolor=bg, edgecolor=edge, lw=1.5, alpha=0.55, zorder=1)
    ax.add_patch(lane)
    tab = FancyBboxPatch((0.015, y), 0.042, h, boxstyle="round,pad=0.002,rounding_size=0.012",
                         facecolor=edge, edgecolor=edge, lw=1.0, zorder=2)
    ax.add_patch(tab)
    ax.text(0.036, y + h / 2, title, rotation=90, ha="center", va="center",
            fontsize=9.4, fontweight="bold", color=WHITE, zorder=3)


# ==============================================================================
# Clean Diagram 1: Executive System Architecture (Low Text, Large Headers, Thick Arrows)
# ==============================================================================
def make_clean_system_architecture() -> Path:
    fig, ax = plt.subplots(figsize=(16.0, 9.2), dpi=300)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor(WHITE)

    # Header
    hdr = FancyBboxPatch((0.015, 0.910), 0.970, 0.075, boxstyle="round,pad=0.003,rounding_size=0.012",
                         facecolor=NAVY, edgecolor="none", zorder=2)
    ax.add_patch(hdr)
    ax.text(0.50, 0.958, "JanSahayak AI — High-Level System Architecture",
            ha="center", va="center", fontsize=17.5, fontweight="bold", color=WHITE)
    ax.text(0.50, 0.927, "Agentic Hybrid RAG Platform  •  IIT Kharagpur Track B (Qwen3-8B + bge-small-en-v1.5)",
            ha="center", va="center", fontsize=10.5, color="#FDE68A", fontweight="bold")

    # 4 Clean Horizontal Layers
    draw_lane(ax, 0.745, 0.140, "CLIENT UI", LIGHT_BLUE, BLUE)
    draw_lane(ax, 0.505, 0.215, "AGENT BRAIN", LIGHT_PURPLE, PURPLE)
    draw_lane(ax, 0.265, 0.215, "TOOLS & RAG", LIGHT_TEAL, TEAL)
    draw_lane(ax, 0.040, 0.200, "VMs & DATA", LIGHT_SAFFRON, SAFFRON)

    # LAYER 1: CLIENT UI (3 big clean boxes)
    clean_box(ax, 0.080, 0.768, 0.270, 0.095, "React 18 Civic Web Portal",
              "7 Langs • Voice • Follow-Ups • Glass UI", edge=BLUE, face=WHITE)
    clean_box(ax, 0.390, 0.768, 0.265, 0.095, "FastAPI Gateway (:8000)",
              "HMAC RBAC • 15 RPM • Two-Tier Cache", edge=NAVY, face=WHITE)
    clean_box(ax, 0.695, 0.768, 0.265, 0.095, "Admin Observability",
              "Trace Waterfall • 9 Eval Benchmarks", edge=SLATE, face=WHITE)

    clean_arrow(ax, 0.350, 0.815, 0.390, 0.815, color=BLUE, label="SSE", lbl_pos=(0.370, 0.848))
    clean_arrow(ax, 0.655, 0.815, 0.695, 0.815, color=SLATE, label="Traces", lbl_pos=(0.675, 0.848))

    # LAYER 2: LANGGRAPH AGENT BRAIN (Synced PR #1 with Reflector Loop!)
    clean_box(ax, 0.080, 0.562, 0.122, 0.112, "1. Input\nGuardrail", "PII & Shield",
              edge=AMBER, face=LIGHT_AMBER, title_size=10.2)
    clean_box(ax, 0.222, 0.562, 0.118, 0.112, "2. Language\nPivot", "7 Langs->EN",
              edge=PURPLE, face=WHITE, title_size=10.2)
    clean_box(ax, 0.360, 0.562, 0.118, 0.112, "3. Planner", "Intent+Plan",
              edge=SAFFRON, face=LIGHT_SAFFRON, title_size=10.4, badge="LLM", badge_bg=SAFFRON)
    clean_box(ax, 0.498, 0.562, 0.118, 0.112, "4. Executor", "5 Tools",
              edge=BLUE, face=LIGHT_BLUE, title_size=10.4)
    clean_box(ax, 0.636, 0.562, 0.126, 0.112, "5. Reflector", "ReAct Loop",
              edge=TEAL, face=LIGHT_TEAL, title_size=10.4, badge="MAX 2", badge_bg=TEAL)
    clean_box(ax, 0.790, 0.606, 0.172, 0.092, "6. Synthesizer", "Cited Draft",
              edge=SAFFRON, face=LIGHT_SAFFRON, title_size=10.4, badge="LLM", badge_bg=SAFFRON)
    clean_box(ax, 0.790, 0.515, 0.172, 0.070, "7. Critic & Localizer", "Audit + Translate",
              edge=GREEN, face=LIGHT_GREEN, title_size=9.8)

    # Thick visible arrows in Layer 2
    clean_ortho(ax, [(0.522, 0.768), (0.522, 0.728), (0.141, 0.728), (0.141, 0.677)],
                color=NAVY, label="User Query", lbl_pos=(0.330, 0.728))
    clean_arrow(ax, 0.202, 0.618, 0.222, 0.618, color=PURPLE)
    clean_arrow(ax, 0.340, 0.618, 0.360, 0.618, color=PURPLE)
    clean_arrow(ax, 0.478, 0.618, 0.498, 0.618, color=PURPLE)
    clean_arrow(ax, 0.616, 0.618, 0.636, 0.618, color=BLUE)
    # Reflector -> Executor loop-back arrow (top arc)
    clean_arrow(ax, 0.699, 0.675, 0.557, 0.675, color=TEAL, rad=0.35, ls="--", lw=2.1,
                label="Search / Check Again", lbl_pos=(0.628, 0.710), lbl_size=7.4)
    clean_arrow(ax, 0.762, 0.642, 0.790, 0.650, color=BLUE)
    clean_arrow(ax, 0.876, 0.606, 0.876, 0.585, color=GREEN)
    # Critic revision loop arrow (bold dashed red)
    clean_arrow(ax, 0.790, 0.550, 0.790, 0.630, color=RED, rad=-0.52, ls="--", lw=2.1,
                label="Revise\n(max 1)", lbl_pos=(0.735, 0.530), lbl_size=7.4)

    # LAYER 3: TOOLS & HYBRID RAG (4 clean boxes)
    clean_box(ax, 0.080, 0.305, 0.235, 0.135, "Hybrid RAG Engine",
              "BM25 + Dense -> RRF -> Reranker", edge=TEAL, face=WHITE, badge="TOOL 1", badge_bg=TEAL)
    clean_box(ax, 0.345, 0.305, 0.195, 0.135, "Eligibility Rules",
              "Deterministic (95.6% Acc.)", edge=PURPLE, face=WHITE, badge="TOOL 2", badge_bg=PURPLE)
    clean_box(ax, 0.570, 0.305, 0.185, 0.135, ".gov.in Web Search",
              "Fallback (Score < 0.25)", edge=AMBER, face=WHITE, badge="TOOL 3", badge_bg=AMBER)
    clean_box(ax, 0.785, 0.305, 0.175, 0.135, "CPGRAMS + Email",
              "HITL Code Gate • SMTP", edge=GREEN, face=WHITE, badge="TOOLS 4-5", badge_bg=GREEN)

    # Executor -> Tools bus (thick clean cyan arrow)
    clean_ortho(ax, [(0.557, 0.562), (0.557, 0.482), (0.197, 0.482), (0.197, 0.443)],
                color=TEAL, label="Invoke Typed Pydantic Tools (<=10 calls)", lbl_pos=(0.375, 0.482))
    clean_arrow(ax, 0.442, 0.482, 0.442, 0.443, color=TEAL)
    clean_arrow(ax, 0.662, 0.482, 0.662, 0.443, color=TEAL)
    clean_ortho(ax, [(0.557, 0.482), (0.872, 0.482), (0.872, 0.443)], color=TEAL)

    # LAYER 4: HOSTED VMs & LOCAL DATA (4 big crisp boxes)
    clean_box(ax, 0.080, 0.068, 0.235, 0.135, "IIT KGP LLM VM",
              "Qwen/Qwen3-8B • Semaphore(1)", edge=SAFFRON, face=LIGHT_SAFFRON, title_color=SAFFRON,
              badge="IIT HOSTED", badge_bg=SAFFRON)
    clean_box(ax, 0.345, 0.068, 0.205, 0.135, "IIT KGP Embed VM02",
              "bge-small-en-v1.5 (384-d)", edge=SAFFRON, face=LIGHT_SAFFRON, title_color=SAFFRON,
              badge="IIT HOSTED", badge_bg=SAFFRON)
    clean_box(ax, 0.580, 0.068, 0.190, 0.135, "Local Index & DB",
              "SQLite • 6,059 Vectors • BM25", edge=SLATE, face=WHITE, badge="LOCAL", badge_bg=SLATE)
    clean_box(ax, 0.798, 0.068, 0.162, 0.135, "External Services",
              "gTTS Audio • Gmail • DDG", edge=GREEN, face=LIGHT_GREEN, title_color=GREEN, badge="LIVE", badge_bg=GREEN)

    # Clean accurate connectors to Layer 4 (LLM VM from Agent Brain; Embed & Index from Hybrid RAG; Rules from SQLite; SMTP/Web from Tools)
    clean_ortho(ax, [(0.080, 0.595), (0.066, 0.595), (0.066, 0.135), (0.080, 0.135)],
                color=SAFFRON, label="LLM\nCalls", lbl_pos=(0.066, 0.455), lbl_size=7.6)
    clean_arrow(ax, 0.255, 0.305, 0.410, 0.206, color=SAFFRON, label="Embed Query", lbl_pos=(0.315, 0.254))
    clean_arrow(ax, 0.295, 0.305, 0.620, 0.206, color=SLATE, label="Vectors & BM25", lbl_pos=(0.475, 0.254))
    clean_arrow(ax, 0.475, 0.305, 0.675, 0.206, color=PURPLE, label="SQLite Rules", lbl_pos=(0.615, 0.254))
    clean_arrow(ax, 0.872, 0.305, 0.872, 0.206, color=GREEN, label="SMTP / Web", lbl_pos=(0.916, 0.254))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "clean_01_system_architecture.png"
    tmp = OUT_DIR / "_tmp_clean_01.png"
    plt.savefig(tmp, dpi=300, bbox_inches="tight", pad_inches=0.12)
    plt.close(fig)
    tmp.replace(out)
    return out


# ==============================================================================
# Clean Diagram 2: Executive Data Flow & Hybrid RAG Pipeline (Bigger Titles, Clear Arrows)
# ==============================================================================
def make_clean_dataflow() -> Path:
    fig, ax = plt.subplots(figsize=(16.0, 9.4), dpi=300)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor(WHITE)

    hdr = FancyBboxPatch((0.015, 0.910), 0.970, 0.075, boxstyle="round,pad=0.003,rounding_size=0.012",
                         facecolor=NAVY, edgecolor="none", zorder=2)
    ax.add_patch(hdr)
    ax.text(0.50, 0.958, "JanSahayak AI — End-to-End Request & Hybrid RAG Data Flow",
            ha="center", va="center", fontsize=17.2, fontweight="bold", color=WHITE)
    ax.text(0.50, 0.927, "Numbered Execution Path (1 -> 10)  •  Zero-Leakage Grounding  •  Self-Healing Critic Loop",
            ha="center", va="center", fontsize=10.2, color="#FDE68A", fontweight="bold")

    # ---- TOP ROW: INGESTION SUMMARY BAR ----
    ing = FancyBboxPatch((0.015, 0.780), 0.970, 0.110, boxstyle="round,pad=0.003,rounding_size=0.012",
                         facecolor=LIGHT_SLATE, edgecolor=SLATE, lw=1.4, zorder=1)
    ax.add_patch(ing)
    ax.text(0.030, 0.874, "OFFLINE KNOWLEDGE INDEXING (Run Once)", ha="left", va="center",
            fontsize=9.2, fontweight="bold", color=SLATE)

    clean_box(ax, 0.030, 0.795, 0.195, 0.064, "myScheme CSVs", "649 Schemes • 7,724 FAQs",
              edge=SLATE, face=WHITE, title_size=10.5, sub_size=8.0)
    clean_box(ax, 0.275, 0.795, 0.215, 0.064, "Section Chunker", "6,059 Chunks (<=440 tok)",
              edge=BLUE, face=LIGHT_BLUE, title_size=10.5, sub_size=8.0)
    clean_box(ax, 0.540, 0.795, 0.195, 0.064, "Dual Indexing", "bge-small + 2x BM25",
              edge=SAFFRON, face=LIGHT_SAFFRON, title_color=SAFFRON, title_size=10.5, sub_size=8.0)
    clean_box(ax, 0.785, 0.795, 0.185, 0.064, "Local Index + DB", "9.3MB Vectors • SQLite",
              edge=GREEN, face=LIGHT_GREEN, title_color=GREEN, title_size=10.5, sub_size=8.0)

    clean_arrow(ax, 0.225, 0.827, 0.275, 0.827, color=SLATE, lw=2.2)
    clean_arrow(ax, 0.490, 0.827, 0.540, 0.827, color=BLUE, lw=2.2)
    clean_arrow(ax, 0.735, 0.827, 0.785, 0.827, color=SAFFRON, lw=2.2)

    # ---- MAIN ONLINE FLOW CONTAINER ----
    onl = FancyBboxPatch((0.015, 0.045), 0.970, 0.710, boxstyle="round,pad=0.003,rounding_size=0.012",
                         facecolor=WHITE, edgecolor=BLUE, lw=1.6, zorder=1)
    ax.add_patch(onl)
    ax.text(0.030, 0.735, "ONLINE REAL-TIME CITIZEN REQUEST DATA FLOW (Steps 1 -> 10)", ha="left", va="center",
            fontsize=9.6, fontweight="bold", color=BLUE)

    # Row 1 (Steps 1 -> 2 -> 3 -> 4)
    clean_box(ax, 0.035, 0.575, 0.195, 0.125, "Citizen Query", "Text / Voice • 6 Langs",
              edge=BLUE, face=LIGHT_BLUE, title_size=11.5, badge="STEP 1", badge_bg=BLUE)
    clean_box(ax, 0.275, 0.575, 0.205, 0.125, "Guardrail & Cache", "PII Mask • Injection • Cache",
              edge=AMBER, face=LIGHT_AMBER, title_color=AMBER, title_size=11.2, badge="STEP 2", badge_bg=AMBER)
    clean_box(ax, 0.525, 0.575, 0.200, 0.125, "Language Pivot", "Detect -> Canonical EN",
              edge=TEAL, face=LIGHT_TEAL, title_color=TEAL, title_size=11.2, badge="STEP 3", badge_bg=TEAL)
    clean_box(ax, 0.770, 0.575, 0.195, 0.125, "Planner (Qwen3)", "Intent • Profile • Tool Plan",
              edge=SAFFRON, face=LIGHT_SAFFRON, title_color=SAFFRON, title_size=11.2, badge="STEP 4", badge_bg=SAFFRON)

    clean_arrow(ax, 0.230, 0.638, 0.275, 0.638, color=BLUE, hop="1", hop_pos=(0.252, 0.668))
    clean_arrow(ax, 0.480, 0.638, 0.525, 0.638, color=AMBER, hop="2", hop_pos=(0.502, 0.668))
    clean_arrow(ax, 0.725, 0.638, 0.770, 0.638, color=TEAL, hop="3", hop_pos=(0.747, 0.668))

    # Row 2 (Right to Left: Step 5 Parallel Hybrid -> Step 6 RRF + Cross-Encoder -> Step 7 Rules / Web Fallback)
    clean_box(ax, 0.730, 0.340, 0.235, 0.155, "Parallel Hybrid Search",
              "BM25 (Top-30) + Dense (Top-30)", edge=BLUE, face=WHITE, title_size=11.2, badge="STEP 5", badge_bg=BLUE)
    clean_box(ax, 0.415, 0.340, 0.255, 0.155, "RRF + Cross-Encoder",
              "RRF (k=60) -> CPU Rerank Top-6", edge=PURPLE, face=LIGHT_PURPLE, title_color=PURPLE,
              title_size=11.2, badge="STEP 6", badge_bg=PURPLE)
    clean_box(ax, 0.035, 0.340, 0.320, 0.155, "Rules & .gov.in Fallback",
              "SQLite Eligibility Rules • Web (<0.35)", edge=TEAL, face=LIGHT_TEAL, title_color=TEAL,
              title_size=11.2, badge="STEP 7", badge_bg=TEAL)

    clean_arrow(ax, 0.867, 0.575, 0.867, 0.498, color=SAFFRON, label="Tool Call", lbl_pos=(0.915, 0.536),
                hop="4", hop_pos=(0.840, 0.536))
    clean_arrow(ax, 0.730, 0.418, 0.673, 0.418, color=BLUE, hop="5", hop_pos=(0.701, 0.448))
    clean_arrow(ax, 0.415, 0.418, 0.358, 0.418, color=PURPLE, hop="6", hop_pos=(0.386, 0.448))

    # Row 3 (Left to Right: Step 8 Synthesizer -> Step 9 Critic Audit -> Step 10 Localizer + Trace + SSE UI)
    clean_box(ax, 0.035, 0.100, 0.265, 0.140, "Synthesizer (Qwen3)",
              "Grounded Answer + [1][2] Cites", edge=SAFFRON, face=LIGHT_SAFFRON, title_color=SAFFRON,
              title_size=11.2, badge="STEP 8", badge_bg=SAFFRON)
    clean_box(ax, 0.365, 0.100, 0.260, 0.140, "Critic Auditor",
              "Verify Grounding, Cites & PII", edge=RED, face=LIGHT_RED, title_color=RED,
              title_size=11.2, badge="STEP 9", badge_bg=RED)
    clean_box(ax, 0.695, 0.100, 0.270, 0.140, "Localize, Trace & UI",
              "SSE Stream • SQLite Spans • Audio", edge=GREEN, face=LIGHT_GREEN, title_color=GREEN,
              title_size=11.2, badge="STEP 10", badge_bg=GREEN)

    clean_arrow(ax, 0.155, 0.340, 0.155, 0.243, color=TEAL, label="Evidence + Card", lbl_pos=(0.088, 0.292),
                hop="7", hop_pos=(0.180, 0.292))
    clean_arrow(ax, 0.300, 0.170, 0.365, 0.170, color=SAFFRON, hop="8", hop_pos=(0.332, 0.198))
    # Clear Self-Healing Critic Revision Loop (zero overlap with Evidence label!)
    clean_arrow(ax, 0.495, 0.240, 0.245, 0.240, color=RED, rad=0.22, ls="--", lw=2.4,
                label="FAIL -> Self-Heal Revision (Max 1 Loop)", lbl_pos=(0.415, 0.294), lbl_size=8.2)
    clean_arrow(ax, 0.625, 0.170, 0.695, 0.170, color=GREEN, label="PASS", lbl_pos=(0.660, 0.205),
                hop="9", hop_pos=(0.660, 0.140))

    # Footer bar
    ax.text(
        0.50,
        0.065,
        "Every step logs a structured Langfuse-style Span (SPN-01..N) with latency & tokens to SQLite  •  Repeat queries hit Two-Tier Cache in <50 ms",
        ha="center",
        va="center",
        fontsize=8.8,
        fontweight="bold",
        color=NAVY,
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "clean_02_hybrid_rag_dataflow.png"
    tmp = OUT_DIR / "_tmp_clean_02.png"
    plt.savefig(tmp, dpi=300, bbox_inches="tight", pad_inches=0.12)
    plt.close(fig)
    tmp.replace(out)
    return out


if __name__ == "__main__":
    p1 = make_clean_system_architecture()
    p2 = make_clean_dataflow()
    print(f"[OK] {p1.name} ({p1.stat().st_size:,} B)")
    print(f"[OK] {p2.name} ({p2.stat().st_size:,} B)")
