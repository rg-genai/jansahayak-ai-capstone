"""Generate an ultra-detailed Principal Solutions Architect Swimlane Data Flow Diagram (DFD)
showing exact Plane/Swimlane boundaries, LLM/Embedding/Tool/DB connections, Validation Contracts
for every block, and numbered live execution hops for Trace TRC-DB1E35A90D (Mumbai MRO Loan).
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Circle

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = PROJECT_ROOT / "docs" / "diagrams"
CAPTURE_PATH = PROJECT_ROOT / "data" / "live_walkthrough_capture.json"

# Architect Color Palette (High-Contrast Print & Zoom Quality)
NAVY = "#0B2239"
DARK_SLATE = "#1E293B"
SLATE = "#334155"
MUTED = "#64748B"
BORDER = "#CBD5E1"
WHITE = "#FFFFFF"

# Lane / Flow Semantic Colors
C_UI = "#1D4ED8"          # Client / Presentation Blue
BG_UI = "#EFF6FF"
C_API = "#0F766E"         # API / Guardrails / Cache Teal
BG_API = "#F0FDFA"
C_AGENT = "#6D28D9"       # LangGraph Agent Purple
BG_AGENT = "#F5F3FF"
C_TOOL = "#0369A1"        # Hybrid RAG & Tools Cyan-Blue
BG_TOOL = "#F0F9FF"
C_LLM = "#D95D14"         # IIT KGP LLM / Embedding Saffron-Orange
BG_LLM = "#FFF4EB"
C_DB = "#334155"          # SQLite / Local Index Slate
BG_DB = "#F8FAFC"
C_PASS = "#15803D"        # Verified / SSE Output Green
BG_PASS = "#ECFDF5"
C_WARN = "#B45309"        # Validation / Security Amber
BG_WARN = "#FFFBEB"
C_LOOP = "#B91C1C"        # Critic Revision / Blocked Red
BG_LOOP = "#FEF2F2"

plt.rcParams["font.family"] = "DejaVu Sans"


def draw_swimlane(ax, y: float, h: float, label: str, sublabel: str, bg: str, edge: str):
    # Full horizontal lane
    lane = FancyBboxPatch(
        (0.012, y),
        0.976,
        h,
        boxstyle="round,pad=0.002,rounding_size=0.008",
        facecolor=bg,
        edgecolor=edge,
        lw=1.3,
        alpha=0.55,
        zorder=1,
    )
    ax.add_patch(lane)
    # Left vertical title tab
    tab = FancyBboxPatch(
        (0.012, y),
        0.044,
        h,
        boxstyle="round,pad=0.002,rounding_size=0.008",
        facecolor=edge,
        edgecolor=edge,
        lw=1.0,
        zorder=2,
    )
    ax.add_patch(tab)
    ax.text(
        0.028,
        y + h / 2,
        label,
        rotation=90,
        ha="center",
        va="center",
        fontsize=8.3,
        fontweight="bold",
        color=WHITE,
        zorder=3,
    )
    ax.text(
        0.047,
        y + h / 2,
        sublabel,
        rotation=90,
        ha="center",
        va="center",
        fontsize=6.4,
        color="#E2E8F0",
        zorder=3,
    )


def draw_arch_node(
    ax,
    x: float,
    y: float,
    w: float,
    h: float,
    title: str,
    body: str,
    contract: str,
    edge: str = NAVY,
    face: str = WHITE,
    title_color: str | None = None,
    contract_bg: str = "#F1F5F9",
    contract_fg: str = DARK_SLATE,
    tag: str | None = None,
    tag_bg: str = NAVY,
    title_fs: float = 8.1,
    body_fs: float = 6.7,
):
    # Main card
    card = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.002,rounding_size=0.008",
        facecolor=face,
        edgecolor=edge,
        lw=1.5,
        zorder=3,
    )
    ax.add_patch(card)

    # Bottom validation contract bar inside card
    ch = min(0.028, h * 0.25)
    cbar = FancyBboxPatch(
        (x + 0.002, y + 0.002),
        w - 0.004,
        ch,
        boxstyle="round,pad=0.001,rounding_size=0.005",
        facecolor=contract_bg,
        edgecolor="none",
        zorder=4,
    )
    ax.add_patch(cbar)
    ax.text(
        x + w / 2,
        y + 0.002 + ch / 2,
        contract,
        ha="center",
        va="center",
        fontsize=6.0,
        fontweight="bold",
        color=contract_fg,
        zorder=5,
    )

    # Title near top
    top_area_top = y + h - (0.017 if tag else 0.011)
    ax.text(
        x + w / 2,
        top_area_top,
        title,
        ha="center",
        va="top",
        fontsize=title_fs,
        fontweight="bold",
        color=title_color or edge,
        linespacing=1.08,
        zorder=5,
    )

    # Body centered between title and contract bar
    t_lines = title.count("\n") + 1
    body_top = top_area_top - (0.018 if t_lines == 1 else 0.032)
    body_mid = (body_top + (y + ch + 0.004)) / 2.0
    ax.text(
        x + w / 2,
        body_mid,
        body,
        ha="center",
        va="center",
        fontsize=body_fs,
        color=DARK_SLATE,
        linespacing=1.22,
        zorder=5,
    )

    # Optional top-right tag pill
    if tag:
        tw = min(w * 0.62, max(0.048, len(tag) * 0.0045 + 0.012))
        th = 0.017
        tx = x + w - tw - 0.004
        ty = y + h - th * 0.45
        tbox = FancyBboxPatch(
            (tx, ty),
            tw,
            th,
            boxstyle="round,pad=0.001,rounding_size=0.005",
            facecolor=tag_bg,
            edgecolor=WHITE,
            lw=0.7,
            zorder=6,
        )
        ax.add_patch(tbox)
        ax.text(
            tx + tw / 2,
            ty + th / 2,
            tag,
            ha="center",
            va="center",
            fontsize=5.6,
            fontweight="bold",
            color=WHITE,
            zorder=7,
        )


def draw_hop_arrow(
    ax,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    color: str,
    label: str = "",
    hop: str = "",
    rad: float = 0.0,
    ls: str = "-",
    lw: float = 1.6,
    lbl_pos: tuple[float, float] | None = None,
    hop_pos: tuple[float, float] | None = None,
    lbl_fs: float = 6.3,
):
    arr = FancyArrowPatch(
        (x1, y1),
        (x2, y2),
        arrowstyle="-|>",
        mutation_scale=11,
        linewidth=lw,
        linestyle=ls,
        color=color,
        connectionstyle=f"arc3,rad={rad}",
        zorder=8,
    )
    ax.add_patch(arr)
    mx = (x1 + x2) / 2
    my = (y1 + y2) / 2
    if label:
        lx, ly = lbl_pos if lbl_pos else (mx, my)
        ax.text(
            lx,
            ly,
            label,
            ha="center",
            va="center",
            fontsize=lbl_fs,
            fontweight="bold",
            color=color,
            bbox=dict(boxstyle="round,pad=0.16", facecolor=WHITE, edgecolor=color, lw=0.6, alpha=0.96),
            zorder=10,
        )
    if hop:
        hx, hy = hop_pos if hop_pos else (mx, my)
        circ = Circle((hx, hy), radius=0.0085, facecolor=color, edgecolor=WHITE, lw=0.9, zorder=11)
        ax.add_patch(circ)
        ax.text(hx, hy, hop, ha="center", va="center", fontsize=6.0, fontweight="bold", color=WHITE, zorder=12)


def draw_ortho_arrow(
    ax,
    pts: list[tuple[float, float]],
    color: str,
    label: str = "",
    hop: str = "",
    ls: str = "-",
    lw: float = 1.6,
    lbl_pos: tuple[float, float] | None = None,
    hop_pos: tuple[float, float] | None = None,
    lbl_fs: float = 6.3,
):
    # Draw polyline segments then arrow on last segment
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    if len(pts) > 2:
        ax.plot(xs[:-1], ys[:-1], color=color, lw=lw, linestyle=ls, zorder=7)
    arr = FancyArrowPatch(
        pts[-2],
        pts[-1],
        arrowstyle="-|>",
        mutation_scale=11,
        linewidth=lw,
        linestyle=ls,
        color=color,
        zorder=8,
    )
    ax.add_patch(arr)
    if label and lbl_pos:
        ax.text(
            lbl_pos[0],
            lbl_pos[1],
            label,
            ha="center",
            va="center",
            fontsize=lbl_fs,
            fontweight="bold",
            color=color,
            bbox=dict(boxstyle="round,pad=0.16", facecolor=WHITE, edgecolor=color, lw=0.6, alpha=0.96),
            zorder=10,
        )
    if hop and hop_pos:
        circ = Circle(hop_pos, radius=0.0085, facecolor=color, edgecolor=WHITE, lw=0.9, zorder=11)
        ax.add_patch(circ)
        ax.text(hop_pos[0], hop_pos[1], hop, ha="center", va="center", fontsize=6.0, fontweight="bold", color=WHITE, zorder=12)


def build_architect_swimlane_dfd() -> list[Path]:
    cap = json.loads(CAPTURE_PATH.read_text(encoding="utf-8"))
    trace_id = cap["trace_id"]

    fig, ax = plt.subplots(figsize=(21.0, 13.5), dpi=300)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor(WHITE)

    # ==================== HEADER BANNER ====================
    hdr = FancyBboxPatch((0.012, 0.932), 0.976, 0.058, boxstyle="round,pad=0.003,rounding_size=0.009",
                         facecolor=NAVY, edgecolor="none", zorder=2)
    ax.add_patch(hdr)
    ax.text(
        0.50,
        0.970,
        f"JanSahayak AI — Enterprise Solutions Architect Swimlane Data Flow & Validation Blueprint (Live Trace: {trace_id})",
        ha="center",
        va="center",
        fontsize=15.0,
        fontweight="bold",
        color=WHITE,
        zorder=3,
    )
    ax.text(
        0.50,
        0.945,
        'Traced Prompt: "Hi, I am a 25 year old male looking for Loan to start my small business of Small parts manufacturing like nuts, bolts and other MRO parts in Mumbai, I am eligible for which scheme?"',
        ha="center",
        va="center",
        fontsize=8.8,
        color="#FDE68A",
        fontweight="bold",
        zorder=3,
    )

    # ==================== FLOW LEGEND BAR ====================
    legend_specs = [
        (0.015, 0.145, C_UI, "HTTP / SSE Request & UI"),
        (0.168, 0.145, C_API, "Auth / Cache / Guardrail"),
        (0.321, 0.150, C_AGENT, "LangGraph State Edge"),
        (0.479, 0.155, C_TOOL, "Tool / Hybrid RAG Flow"),
        (0.642, 0.150, C_LLM, "IIT KGP LLM / Embed Call"),
        (0.800, 0.095, C_DB, "SQLite / Index"),
        (0.903, 0.085, C_LOOP, "Revision / Block"),
    ]
    for lx, lw_l, lc, lt in legend_specs:
        lp = FancyBboxPatch((lx, 0.904), lw_l, 0.022, boxstyle="round,pad=0.001,rounding_size=0.005",
                            facecolor=WHITE, edgecolor=lc, lw=1.2, zorder=3)
        ax.add_patch(lp)
        ax.plot([lx + 0.006, lx + 0.020], [0.915, 0.915], color=lc, lw=2.2, zorder=4)
        ax.text(lx + 0.024, 0.915, lt, ha="left", va="center", fontsize=6.9, fontweight="bold", color=lc, zorder=4)

    # ==================== 5 HORIZONTAL SWIMLANES ====================
    # Y coordinates (top to bottom):
    # Lane 1 (Client UI):         0.772 .. 0.895 (h=0.123)
    # Lane 2 (API & Guardrails):  0.608 .. 0.758 (h=0.150)
    # Lane 3 (LangGraph Agent):   0.418 .. 0.594 (h=0.176)
    # Lane 4 (Tools & RAG):       0.228 .. 0.404 (h=0.176)
    # Lane 5 (Models & Storage):  0.048 .. 0.214 (h=0.166)
    draw_swimlane(ax, 0.775, 0.120, "PLANE 1: CLIENT UI", "React 18 • Vite :5173", BG_UI, C_UI)
    draw_swimlane(ax, 0.616, 0.145, "PLANE 2: API & SAFETY", "FastAPI :8000 • 1 Worker", BG_API, C_API)
    draw_swimlane(ax, 0.432, 0.168, "PLANE 3: AGENT GRAPH", "LangGraph StateGraph", BG_AGENT, C_AGENT)
    draw_swimlane(ax, 0.246, 0.168, "PLANE 4: TOOLS & RAG", "5 Pydantic Tools • R4", BG_TOOL, C_TOOL)
    draw_swimlane(ax, 0.048, 0.156, "PLANE 5: VMs & DATA", "IIT KGP • SQLite • Disk", BG_LLM, C_LLM)

    # ==================== PLANE 1: CLIENT UI BLOCKS ====================
    draw_arch_node(
        ax, 0.068, 0.785, 0.205, 0.098,
        "1A. React ChatWorkspace",
        "Citizen types/speaks query (180 chars)\nAttaches Authorization: Bearer <HMAC>\nOpens fetch() POST /api/chat/stream",
        "VALID: Non-empty msg <=4000 chars + Auth Token",
        edge=C_UI, face=WHITE, contract_bg=BG_UI, contract_fg=C_UI, tag="BLOCK 1", tag_bg=C_UI,
    )
    draw_arch_node(
        ax, 0.305, 0.785, 0.215, 0.098,
        "1B. Live SSE Stream Consumer",
        "Receives real-time node milestones:\nguardrail -> plan -> tool -> critic -> done\nRenders PM Vishwakarma [2][4][6] + Links",
        "VALID: CRLF Normalize + EOF Flush + Sync Fallback",
        edge=C_PASS, face=WHITE, contract_bg=BG_PASS, contract_fg=C_PASS, tag="BLOCK 9", tag_bg=C_PASS,
    )
    draw_arch_node(
        ax, 0.552, 0.785, 0.195, 0.098,
        "1C. Voice Mic (STT) & Listen (TTS)",
        "Web Speech STT (en/hi/mr/bn/ta/te)\nClick 'Listen' -> POST /api/voice/tts\nPlays server MP3 (gTTS + LRU cache)",
        "VALID: Auto-detect reply script + <=1500 chars",
        edge=C_UI, face=WHITE, contract_bg=BG_UI, contract_fg=C_UI, tag="6-LANG AUDIO", tag_bg=C_UI,
    )
    draw_arch_node(
        ax, 0.778, 0.785, 0.196, 0.098,
        "1D. HITL Grievance & Admin UI",
        "Citizen: Review Modal + Confirm & Submit\nAdmin (RBAC): Langfuse Span Waterfall,\nJSON/MD/CSV Export & Eval Dashboards",
        "VALID: Role Guard (admin vs citizen) + HITL Click",
        edge=NAVY, face=WHITE, contract_bg="#E2E8F0", contract_fg=NAVY, tag="RBAC + HITL", tag_bg=NAVY,
    )

    # ==================== PLANE 2: API, AUTH, CACHE & GUARDRAILS ====================
    draw_arch_node(
        ax, 0.068, 0.622, 0.195, 0.122,
        "2A. FastAPI Gateway + RBAC",
        "Route: POST /api/chat/stream (:8000)\n1. Verify HMAC-SHA256 Token (24h TTL)\n2. Sliding Rate Limit: 1/15 RPM (PASS)\n3. Load Session Profile + Last 10 Turns",
        "VALID: Pydantic ChatRequest + HTTP 429/403 Guard",
        edge=C_API, face=WHITE, contract_bg=BG_API, contract_fg=C_API, tag="GATEWAY", tag_bg=C_API,
    )
    draw_arch_node(
        ax, 0.285, 0.622, 0.200, 0.122,
        "2B. Two-Tier Response Cache",
        "Tier 1: Exact SHA256(query||lang||profile)\nTier 2: Cosine >= 0.96 over cached vectors\nMumbai Prompt -> CACHE MISS\n(Next identical query: <50ms, 0 LLM tok!)",
        "VALID: Bypassed if PII, Grievance, or Attack",
        edge=C_API, face=WHITE, contract_bg=BG_API, contract_fg=C_API, tag="EXACT + SEM", tag_bg=C_API,
    )
    draw_arch_node(
        ax, 0.507, 0.622, 0.218, 0.122,
        "2C. Node 1: InputGuardrail [SPN-01]",
        "DPDP PII Regex: Aadhaar/PAN/Phone/IFSC\nPrompt Injection / Fraud / CAPTCHA Shield\nLive Run: 0 PII, blocked=False (0.14 ms)\nIf Attack -> Immediate Fast Exit (0 LLM!)",
        "VALID: Zero Raw PII Leaves Plane 2 (DPDP 2023)",
        edge=C_WARN, face=BG_WARN, contract_bg="#FDE68A", contract_fg=C_WARN, tag="BLOCK 2A • 0.1ms", tag_bg=C_WARN,
    )
    draw_arch_node(
        ax, 0.747, 0.622, 0.227, 0.122,
        "2D. Node 2: LanguagePivot [SPN-02]",
        "Unicode Range & Hinglish Script Classifier\nLive Run: detected_lang='en' (0.09 ms)\nNon-EN -> Qwen3 to_english() -> query_en\nGuarantees EN/HI/TA Identical Retrieval!",
        "VALID: Canonical query_en Locked for RAG",
        edge=C_API, face=WHITE, contract_bg=BG_API, contract_fg=C_API, tag="BLOCK 2B • 0.1ms", tag_bg=C_API,
    )

    # ==================== PLANE 3: LANGGRAPH AGENT STATE MACHINE ====================
    draw_arch_node(
        ax, 0.068, 0.436, 0.180, 0.142,
        "3A. Node 3: Planner [SPN-03]",
        "Calls Qwen3-8B (891p+117c = 1,008t)\nIntent: ELIGIBILITY_CHECK\nProfile: age=25, male, Maharashtra\n(inferred from Mumbai!), occ=MRO\nPlan: search_schemes(top_k=6)",
        "VALID: PlannerOutput Pydantic + 1-Shot Repair",
        edge=C_AGENT, face=WHITE, contract_bg=BG_AGENT, contract_fg=C_AGENT, tag="BLOCK 3 • 2.89s", tag_bg=C_AGENT,
    )
    draw_arch_node(
        ax, 0.270, 0.436, 0.175, 0.142,
        "3B. Node 4: Executor [SPN-04]",
        "Typed Tool Dispatcher & Auto-Chainer\n1. Runs T1 search_schemes (6 chunks)\n2. Auto-chains T2 check_eligibility\n3. Sees rerank 0.0038 < 0.35 ->\n   Auto-triggers T3 .gov.in Fallback!",
        "VALID: Tool Args Pydantic + Confidence Gate",
        edge=C_AGENT, face=WHITE, contract_bg=BG_AGENT, contract_fg=C_AGENT, tag="BLOCK 4/5 • 3 TOOLS", tag_bg=C_AGENT,
    )
    draw_arch_node(
        ax, 0.467, 0.436, 0.178, 0.142,
        "3C. Node 5: Synthesizer [SPN-05/07]",
        "Wraps 6 chunks + card in Untrusted Tag\nExcludes women-only nssw (user=male!)\nR0 (5.89s, 2,883t): Cited [2] loosely\nR1 Revision (5.90s, 2,932t): Fixed to\nPM Vishwakarma [2], [4] & [6]!",
        "VALID: <RETRIEVED_EVIDENCE_UNTRUSTED> + <=240w",
        edge=C_LLM, face=BG_LLM, contract_bg="#FED7AA", contract_fg=C_LLM, tag="BLOCK 6 • 2 PASSES", tag_bg=C_LLM,
    )
    draw_arch_node(
        ax, 0.667, 0.436, 0.163, 0.142,
        "3D. Node 6: Critic [SPN-06/08]",
        "Deterministic Check (PII + [n] Regex)\n+ LLM 5-Point Audit (1,209t, 3.82s)\nSPN-06: CAUGHT wrong cite [2] for\n₹1L/₹2L loan -> Triggered 1 Revision!\nSPN-08 (0.6ms): PASSED!",
        "VALID: CriticOutput JSON + Max 1 Loop Cap",
        edge=C_LOOP, face=BG_LOOP, contract_bg="#FECACA", contract_fg=C_LOOP, tag="BLOCK 7 • SELF-HEAL", tag_bg=C_LOOP,
    )
    draw_arch_node(
        ax, 0.850, 0.436, 0.125, 0.142,
        "3E. Node 7: Localizer\n[SPN-09]",
        "Target: 'en' (0.32 ms)\nIf Non-EN: Translate\npreserving [1](url)\nBuilds Citation Array\n& Trace Span Log",
        "VALID: Links + Spans Intact",
        edge=C_PASS, face=BG_PASS, contract_bg="#BBF7D0", contract_fg=C_PASS, tag="BLOCK 8", tag_bg=C_PASS,
    )

    # ==================== PLANE 4: HYBRID RAG ENGINE & 5 TYPED TOOLS ====================
    draw_arch_node(
        ax, 0.068, 0.244, 0.175, 0.142,
        "4A. T1a: Sparse BM25\n+ Dense Cosine (Top 30+30)",
        "Permissive Filter (nulls never drop)\n• BM25 (2x title boost): nssw=59.3,\n  kkjby=61.9; PMV/PMEGP=0.0!\n• Dense bge-small: PMV=0.742,\n  PMEGP=0.722 -> RESCUED MSMEs!",
        "VALID: Auto-Relax Filter if <5 Hits / <0.5",
        edge=C_TOOL, face=WHITE, contract_bg=BG_TOOL, contract_fg=C_TOOL, tag="HYBRID RETRIEVAL", tag_bg=C_TOOL,
    )
    draw_arch_node(
        ax, 0.262, 0.244, 0.178, 0.142,
        "4B. T1b: RRF Fusion (k=60)\n+ CPU Cross-Encoder",
        "RRF = 1/(60+r_bm25) + 1/(60+r_dense)\nMerges Top-30+30 -> Top-20\nms-marco-MiniLM-L-6-v2 (Pre-warmed)\nSigmoid [0..1] -> Top-6 Chunks\n(Top=0.0038 -> low_confidence=True)",
        "VALID: Calibrated [0..1] Score + 1.6s Warm",
        edge=C_TOOL, face=WHITE, contract_bg=BG_TOOL, contract_fg=C_TOOL, tag="RERANK + GATE", tag_bg=C_TOOL,
    )
    draw_arch_node(
        ax, 0.459, 0.244, 0.172, 0.142,
        "4C. T2: check_eligibility\n(Deterministic Rule Engine)",
        "Queries SQLite schemes_catalog\nChecks Age (25 fits 18-55), Income,\nCaste, Gender & Exclusion Clauses\nAuto-checked nssw -> Flagged:\n'Applicant must be Female'!",
        "VALID: Zero LLM Math / Exact DB Rules",
        edge=C_AGENT, face=WHITE, contract_bg=BG_AGENT, contract_fg=C_AGENT, tag="TOOL 2 • RULES", tag_bg=C_AGENT,
    )
    draw_arch_node(
        ax, 0.650, 0.244, 0.155, 0.142,
        "4D. T3: web_search_gov\n(.gov.in Live Fallback)",
        "Triggered ONLY if rerank < 0.35\nDuckDuckGo strictly scoped to\nsite:gov.in OR site:nic.in\nStrips indirect prompt injection\n(Live run: 0 hits for long prose)",
        "VALID: Domain Whitelist + Injection Strip",
        edge=C_WARN, face=WHITE, contract_bg=BG_WARN, contract_fg=C_WARN, tag="TOOL 3 • FALLBACK", tag_bg=C_WARN,
    )
    draw_arch_node(
        ax, 0.824, 0.244, 0.151, 0.142,
        "4E. T4 & T5: CPGRAMS\nDraft / Submit / Track",
        "T4: 51-Ministry Map + PII Mask\n    + <=2,000 Chars + DRAFT ID\nT5: Sandbox Ticket + Gmail SMTP\n    + Assisted Handoff Packet\n(Not called on Scheme Q&A turn)",
        "VALID: Hard Gate user_confirmed=True",
        edge=NAVY, face=WHITE, contract_bg="#E2E8F0", contract_fg=NAVY, tag="TOOLS 4-5 • HITL", tag_bg=NAVY,
    )

    # ==================== PLANE 5: HOSTED VMs, LOCAL STORES & LIVE SERVICES ====================
    draw_arch_node(
        ax, 0.068, 0.056, 0.235, 0.130,
        "5A. IIT KGP LLM Gateway (Qwen/Qwen3-8B)",
        "Serves 4 Serialized Calls in Trace TRC-DB1E35A90D:\n• Planner (1,008t)  • Synth R0 (2,883t)\n• Critic (1,209t)   • Synth R1 (2,932t)\nTotal: 7,229p + 803c = 8,032 tok | TLS llm-ca.crt",
        "VALID: Semaphore(1) | 55 RPM | <=8192 Ctx | No-Think",
        edge=C_LLM, face=WHITE, contract_bg="#FED7AA", contract_fg=C_LLM, tag="IIT KGP :1031", tag_bg=C_LLM,
    )
    draw_arch_node(
        ax, 0.320, 0.056, 0.165, 0.130,
        "5B. IIT KGP Embed VM02\nbge-small-en-v1.5",
        "384-Dim L2-Norm Vectors\nOffline: 379 Batches x 16\nOnline: Embeds query_en\n(Cached in SQLite!)\nTLS Verify (vm02-ca.crt)",
        "VALID: <=512 Tok Cap + 2/4/8s Retry",
        edge=C_LLM, face=WHITE, contract_bg="#FED7AA", contract_fg=C_LLM, tag="IIT KGP :1035", tag_bg=C_LLM,
    )
    draw_arch_node(
        ax, 0.502, 0.056, 0.145, 0.130,
        "5C. Local Hybrid Index\n(Loaded in RAM)",
        "embeddings.npy\n(6,059 x 384 float32, ~9MB)\nbm25.pkl\n(6,059 Tokenized Chunks)\n3.2ms Cosine + 28ms BM25",
        "VALID: 0/6,059 Chunks >512 Tok",
        edge=C_DB, face=WHITE, contract_bg="#E2E8F0", contract_fg=C_DB, tag="LOCAL INDEX", tag_bg=C_DB,
    )
    draw_arch_node(
        ax, 0.664, 0.056, 0.175, 0.130,
        "5D. SQLite WAL Database\n(data/jansahayak.db)",
        "• schemes_catalog (649) + FAQs (7,724)\n• chunks_meta (6,059) + ministries (51)\n• sessions, messages, grievances\n• traces (9 Spans saved!) + cache\n• email_notifications outbox",
        "VALID: ACID WAL + Foreign Keys + Masked PII",
        edge=C_DB, face=WHITE, contract_bg="#E2E8F0", contract_fg=C_DB, tag="SQLITE WAL", tag_bg=C_DB,
    )
    draw_arch_node(
        ax, 0.856, 0.056, 0.120, 0.130,
        "5E. Live External\nServices (Free)",
        "• DuckDuckGo (.gov.in)\n• gTTS + edge-tts\n  (6-Lang MP3 Audio)\n• Gmail SMTP TLS\n  (Live Ticket Email)",
        "VALID: Timeouts + Fallbacks",
        edge=C_PASS, face=WHITE, contract_bg=BG_PASS, contract_fg=C_PASS, tag="EXTERNAL LIVE", tag_bg=C_PASS,
    )

    # ==================== EXPLICIT NUMBERED CONNECTIONS (1 .. 15) ====================
    # [1] UI -> FastAPI Gateway
    draw_hop_arrow(ax, 0.165, 0.785, 0.165, 0.746, color=C_UI, label="POST /api/chat/stream", hop="1",
                   lbl_pos=(0.215, 0.766), hop_pos=(0.150, 0.766))
    # [2] FastAPI -> Cache -> InputGuardrail -> LanguagePivot
    draw_hop_arrow(ax, 0.263, 0.685, 0.285, 0.685, color=C_API, hop="2", hop_pos=(0.274, 0.706))
    draw_hop_arrow(ax, 0.485, 0.685, 0.507, 0.685, color=C_API, label="MISS", lbl_pos=(0.496, 0.710))
    draw_hop_arrow(ax, 0.725, 0.685, 0.747, 0.685, color=C_API, label="SAFE", lbl_pos=(0.736, 0.710))

    # [3] LanguagePivot -> Planner (clean horizontal highway between Plane 2 & Plane 3 at y=0.608)
    draw_ortho_arrow(
        ax,
        [(0.860, 0.622), (0.860, 0.608), (0.158, 0.608), (0.158, 0.580)],
        color=C_AGENT,
        label="AgentState(query_en, profile)",
        hop="3",
        lbl_pos=(0.390, 0.608),
        hop_pos=(0.295, 0.608),
    )

    # [4] Planner <-> Qwen3-8B (explicit vertical bus on far-left corridor x=0.060? No, route from Planner bottom-left cleanly into Qwen3!)
    draw_ortho_arrow(
        ax,
        [(0.088, 0.436), (0.088, 0.410), (0.061, 0.410), (0.061, 0.145), (0.068, 0.145)],
        color=C_LLM,
        label="LLM Call #1: Planner\n1,008 tok (2.89s)",
        hop="4",
        lbl_pos=(0.095, 0.410),
        hop_pos=(0.061, 0.300),
        lbl_fs=5.9,
    )

    # [5] Planner -> Executor -> T1a Hybrid Search
    draw_hop_arrow(ax, 0.248, 0.510, 0.270, 0.510, color=C_AGENT, hop="5", hop_pos=(0.259, 0.532))
    draw_ortho_arrow(
        ax,
        [(0.315, 0.436), (0.315, 0.411), (0.155, 0.411), (0.155, 0.388)],
        color=C_TOOL,
        label="T1: search_schemes(query_en, k=6)",
        hop="6",
        lbl_pos=(0.245, 0.411),
        hop_pos=(0.155, 0.411),
        lbl_fs=6.0,
    )

    # [6a] T1a <-> VM02 Embedder & [6b] T1a <-> Local Hybrid Index (spacious corridor between Plane 4 & Plane 5: y=0.236 / 0.220 / 0.203)
    draw_ortho_arrow(
        ax,
        [(0.180, 0.246), (0.180, 0.221), (0.390, 0.221), (0.390, 0.188)],
        color=C_LLM,
        label="Embed Query (384-d)",
        hop="6a",
        lbl_pos=(0.285, 0.221),
        hop_pos=(0.390, 0.221),
        lbl_fs=5.9,
    )
    draw_ortho_arrow(
        ax,
        [(0.215, 0.246), (0.215, 0.237), (0.575, 0.237), (0.575, 0.188)],
        color=C_DB,
        label="Read bm25.pkl + embeddings.npy",
        hop="6b",
        lbl_pos=(0.485, 0.237),
        hop_pos=(0.575, 0.237),
        lbl_fs=5.9,
        ls="--",
    )

    # [7] T1a -> T1b RRF + Cross-Encoder -> back to Executor
    draw_hop_arrow(ax, 0.243, 0.315, 0.262, 0.315, color=C_TOOL, hop="7", hop_pos=(0.252, 0.338))
    draw_ortho_arrow(
        ax,
        [(0.351, 0.386), (0.351, 0.436)],
        color=C_TOOL,
        label="6 Chunks\n(0.0038)",
        lbl_pos=(0.382, 0.411),
        lbl_fs=5.8,
    )

    # [8] Executor -> T2 check_eligibility -> SQLite schemes_catalog
    draw_ortho_arrow(
        ax,
        [(0.415, 0.436), (0.415, 0.411), (0.545, 0.411), (0.545, 0.388)],
        color=C_AGENT,
        label="T2: Auto-Chain check_eligibility(nssw)",
        hop="8",
        lbl_pos=(0.515, 0.411),
        hop_pos=(0.435, 0.411),
        lbl_fs=5.9,
    )
    draw_ortho_arrow(
        ax,
        [(0.595, 0.244), (0.595, 0.218), (0.715, 0.218), (0.715, 0.200)],
        color=C_DB,
        label="Read Scheme Rules",
        lbl_pos=(0.660, 0.218),
        lbl_fs=5.8,
        ls="--",
    )

    # [9] Executor -> T3 web_search_gov -> DuckDuckGo (.gov.in)
    draw_ortho_arrow(
        ax,
        [(0.435, 0.436), (0.435, 0.422), (0.727, 0.422), (0.727, 0.388)],
        color=C_WARN,
        label="T3: Fallback (rerank < 0.35)",
        hop="9",
        lbl_pos=(0.668, 0.422),
        hop_pos=(0.727, 0.422),
        ls="--",
        lbl_fs=5.9,
    )
    draw_ortho_arrow(
        ax,
        [(0.770, 0.244), (0.770, 0.218), (0.910, 0.218), (0.910, 0.200)],
        color=C_PASS,
        label="DuckDuckGo .gov.in",
        lbl_pos=(0.862, 0.218),
        lbl_fs=5.8,
        ls="--",
    )

    # [10] Executor -> Synthesizer -> Qwen3-8B (Calls #2 & #4)
    draw_hop_arrow(ax, 0.445, 0.510, 0.467, 0.510, color=C_AGENT, hop="10", hop_pos=(0.456, 0.532))
    # Route Synthesizer + Critic LLM calls down through clean vertical channel x=0.449 -> y=0.201 -> Qwen3-8B (0.205, 0.188)!
    draw_ortho_arrow(
        ax,
        [(0.485, 0.436), (0.485, 0.402), (0.449, 0.402), (0.449, 0.201), (0.205, 0.201), (0.205, 0.188)],
        color=C_LLM,
        label="LLM Calls #2,#3,#4 (Synth R0 + Critic + Synth R1 = 7,024 tok)",
        hop="11",
        lbl_pos=(0.295, 0.201),
        hop_pos=(0.130, 0.201),
        lbl_fs=5.9,
    )
    # Connect Critic bottom into that same LLM bus cleanly
    ax.plot([0.695, 0.695, 0.449], [0.436, 0.402, 0.402], color=C_LLM, lw=1.3, ls=":", zorder=7)

    # [11/12] Synthesizer -> Critic -> REVISION LOOP BACK -> Synthesizer -> Critic PASS -> Localizer
    draw_hop_arrow(ax, 0.645, 0.505, 0.667, 0.505, color=C_AGENT)
    draw_hop_arrow(
        ax, 0.745, 0.578, 0.560, 0.578,
        color=C_LOOP,
        label="LIVE REVISION LOOP (SPN-06->07): Fixed Cites [2]->[4][6]!",
        hop="12",
        rad=0.24,
        ls="--",
        lw=1.8,
        lbl_pos=(0.680, 0.597),
        hop_pos=(0.565, 0.597),
        lbl_fs=5.9,
    )
    draw_hop_arrow(ax, 0.830, 0.505, 0.850, 0.505, color=C_PASS, label="PASS", hop="13",
                   lbl_pos=(0.840, 0.525), hop_pos=(0.840, 0.483), lbl_fs=5.9)

    # [14] Localizer -> SQLite WAL (Persist 9 Spans + Messages + Two-Tier Cache) along right corridor x=0.980
    draw_ortho_arrow(
        ax,
        [(0.975, 0.490), (0.983, 0.490), (0.983, 0.055), (0.752, 0.055), (0.752, 0.062)],
        color=C_DB,
        label="Persist 9 Spans + Profile + Cache Entry",
        hop="14",
        lbl_pos=(0.865, 0.055),
        hop_pos=(0.983, 0.290),
        lbl_fs=6.0,
    )

    # [15] Localizer -> SSE Stream Consumer (Browser) cleanly up right-top corridor
    draw_ortho_arrow(
        ax,
        [(0.912, 0.578), (0.912, 0.606), (0.982, 0.606), (0.982, 0.765), (0.412, 0.765), (0.412, 0.785)],
        color=C_PASS,
        label="SSE event: done (PM Vishwakarma [2][4][6] + Eligibility Card)",
        hop="15",
        lbl_pos=(0.680, 0.765),
        hop_pos=(0.545, 0.765),
        lbl_fs=6.3,
    )

    # [16] Voice Listen button -> External gTTS/edge-tts
    draw_hop_arrow(ax, 0.520, 0.835, 0.552, 0.835, color=C_UI, label="Listen", hop="16",
                   lbl_pos=(0.536, 0.855), hop_pos=(0.536, 0.815), lbl_fs=5.8)

    # ==================== FOOTER ARCHITECT SUMMARY BAR ====================
    ftr = FancyBboxPatch((0.012, 0.008), 0.976, 0.032, boxstyle="round,pad=0.002,rounding_size=0.006",
                         facecolor=NAVY, edgecolor="none", zorder=2)
    ax.add_patch(ftr)
    ax.text(
        0.50,
        0.024,
        f"Trace {trace_id} Summary:  4 Serialized Qwen3-8B Calls (8,032 tok)  |  1 VM02 Embed Call (384-d)  |  3 Agent Tools Executed  |  "
        "Critic Caught & Fixed Citations Live (SPN-06->07)  |  9 Spans Saved in SQLite  |  Every Block Enforces a Hard Validation Contract",
        ha="center",
        va="center",
        fontsize=7.3,
        fontweight="bold",
        color=WHITE,
        zorder=3,
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    p_arch = OUT_DIR / "04_architect_swimlane_dfd.png"
    p_live = OUT_DIR / "04_live_data_flow_mumbai_mro.png"
    plt.savefig(p_arch, dpi=300, bbox_inches="tight", pad_inches=0.10)
    saved = [p_arch]
    try:
        plt.savefig(p_live, dpi=300, bbox_inches="tight", pad_inches=0.10)
        saved.append(p_live)
    except OSError:
        pass
    plt.close(fig)
    return saved


if __name__ == "__main__":
    paths = build_architect_swimlane_dfd()
    for p in paths:
        print(f"[OK] Generated {p.name} ({p.stat().st_size:,} bytes)")
