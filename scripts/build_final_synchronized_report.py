"""Build the Final Synchronized Technical Capstone Report (.docx) with comfortable
10.5 pt body typography, spacious margins, and full technical depth combining the BEST of BOTH:
1. Executive One-Pager (Problem, Solution, Business Value/USP, Social Impact & Headline Proof)
2. Full Synchronized Technical Depth (PR #1 Reflector Loop, Deterministic Profile Matching,
   5-Way Chunking Ablation, Zero-Leakage 60-Q Gold Q&A with FAQ Exclusion + Top-1/3/5 +
   Gemini 3.5 Flash-Lite Judge + Independent Gemini Audit, 80-Task Agent Suite with McNemar/Wilson
   statistics, Human-Audited Failure Taxonomy [kappa=0.92], 18-Breach DPDP Privacy Matrix,
   Latency & Cost Economics [~Rs 67 / 1,000 tasks], Honest Limitations & DPI Scale Roadmap).
"""

from __future__ import annotations

import json
from pathlib import Path

from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt

from docx_helpers import (
    HEX_BLUE,
    HEX_LIGHT_BLUE,
    HEX_LIGHT_SAFFRON,
    HEX_NAVY,
    RGB_MUTED,
    RGB_NAVY,
    RGB_SAFFRON,
    RGB_WHITE,
    _set_cell_margins,
    _set_cell_shading,
    add_bullets,
    add_callout,
    add_figure,
    add_h1,
    add_h2,
    add_para,
    add_styled_table,
    create_styled_document,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DIAG_DIR = PROJECT_ROOT / "docs" / "diagrams"
SHOT_DIR = PROJECT_ROOT / "docs" / "screenshots"
REPORTS_DIR = PROJECT_ROOT / "eval" / "reports"
OUT_PATH = PROJECT_ROOT / "docs" / "deliverables" / "JanSahayak_AI_Final_Synchronized_Report_v2.docx"


def _add_side_by_side_images(doc, img1: Path, cap1: str, img2: Path, cap2: str) -> None:
    tbl = doc.add_table(rows=2, cols=2)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.autofit = False
    for idx, (im, cap) in enumerate(((img1, cap1), (img2, cap2))):
        c_img = tbl.cell(0, idx)
        c_img.width = Inches(3.55)
        _set_cell_margins(c_img, top=35, bottom=30, left=45, right=45)
        p = c_img.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(3)
        if im.exists():
            p.add_run().add_picture(str(im), width=Inches(3.35))
        c_cap = tbl.cell(1, idx)
        c_cap.width = Inches(3.55)
        _set_cell_margins(c_cap, top=15, bottom=45, left=45, right=45)
        pc = c_cap.paragraphs[0]
        pc.alignment = WD_ALIGN_PARAGRAPH.CENTER
        pc.paragraph_format.space_after = Pt(4)
        rc = pc.add_run(cap)
        rc.italic = True
        rc.font.name = "Calibri"
        rc.font.size = Pt(9.0)
        rc.font.color.rgb = RGB_MUTED


def build_synchronized_report() -> Path:
    gold60_indep = json.loads((REPORTS_DIR / "gold60_comprehensive_eval.json").read_text(encoding="utf-8"))
    nlp_v = gold60_indep["nlp_metrics"]["vanilla_llm"]
    nlp_r = gold60_indep["nlp_metrics"]["agentic_rag"]
    jdg_v = gold60_indep["independent_judge"]["vanilla_llm"]
    jdg_r = gold60_indep["independent_judge"]["agentic_rag"]

    # Airy executive margins (0.68") -> 7.14" usable text width; comfortable 10.5pt body!
    doc = create_styled_document(
        header_title="JanSahayak AI — Final Technical Capstone Report | IIT Kharagpur Track B",
        margin_in=0.68,
    )
    doc.sections[0].different_first_page_header_footer = True

    # ==========================================================================
    # SECTION 1: EXECUTIVE ONE-PAGER (PROBLEM, SOLUTION, BUSINESS VALUE & PROOF)
    # ==========================================================================
    hdr = doc.add_table(rows=1, cols=1)
    hdr.alignment = WD_TABLE_ALIGNMENT.CENTER
    hdr.autofit = False
    hc = hdr.cell(0, 0)
    hc.width = Inches(7.14)
    _set_cell_shading(hc, HEX_NAVY)
    _set_cell_margins(hc, top=140, bottom=140, left=180, right=180)

    p0 = hc.paragraphs[0]
    p0.paragraph_format.space_after = Pt(3)
    r0 = p0.add_run("IIT KHARAGPUR — EXECUTIVE PG IN GENERATIVE AI & AGENTIC AI  |  TRACK B (API-SIDE) CAPSTONE")
    r0.bold = True
    r0.font.size = Pt(9.5)
    r0.font.color.rgb = RGB_SAFFRON

    p1 = hc.add_paragraph()
    p1.paragraph_format.space_after = Pt(4)
    r1 = p1.add_run("JanSahayak AI: Multilingual Citizen Welfare Copilot & CPGRAMS Agent")
    r1.bold = True
    r1.font.size = Pt(18.5)
    r1.font.color.rgb = RGB_WHITE

    p2 = hc.add_paragraph()
    p2.paragraph_format.space_after = Pt(0)
    r2 = p2.add_run(
        "Final Synchronized Technical Report — Executive One-Pager, Agentic Hybrid RAG Architecture, Statistical Evaluations, Failure Taxonomy & Responsible AI"
    )
    r2.font.size = Pt(10.5)
    r2.font.color.rgb = RGB_WHITE

    sp = doc.add_paragraph()
    sp.paragraph_format.space_after = Pt(5)

    # 5-Tile Headline KPI Strip
    kpis = [
        ("649 Schemes", "7,724 FAQs • 51 Ministries"),
        ("100% Hit@5", "Hybrid+Rerank • 98.3% Evid."),
        ("88.3% vs 19%", "Gold QA Judge (p < 0.001)"),
        ("81.2% Tasks", "80-Task Loop (100% Elig.)"),
        ("20/20 • 15/15", "Red-Team & Fault-Inject"),
    ]
    ktbl = doc.add_table(rows=1, cols=5)
    ktbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    ktbl.autofit = False
    for i, (big, sub) in enumerate(kpis):
        c = ktbl.cell(0, i)
        c.width = Inches(1.428)
        _set_cell_shading(c, HEX_LIGHT_BLUE if i % 2 == 0 else HEX_LIGHT_SAFFRON)
        _set_cell_margins(c, top=70, bottom=70, left=55, right=55)
        kp = c.paragraphs[0]
        kp.paragraph_format.space_after = Pt(2)
        rb = kp.add_run(big)
        rb.bold = True
        rb.font.size = Pt(11.5)
        rb.font.color.rgb = RGB_NAVY if i % 2 == 0 else RGB_SAFFRON
        ks = c.add_paragraph()
        ks.paragraph_format.space_after = Pt(0)
        rs = ks.add_run(sub)
        rs.font.size = Pt(8.5)
        rs.font.color.rgb = RGB_NAVY

    add_h1(doc, "1. Executive One-Pager: Problem, Solution & Impact")
    add_para(
        doc,
        "**The Problem — India's Last-Mile Welfare Access Gap:** India administers **649+ Central Government welfare schemes** across **51 Ministries** "
        "(and 4,670+ schemes including States), backed by tens of thousands of dense English policy pages and FAQs. Yet rural farmers, first-generation "
        "students, widows, and artisans routinely miss entitlements worth lakhs of rupees due to four systemic barriers: (1) fragmented English-heavy portals, "
        "(2) opaque exclusion clauses (taxpayer, government-employee, or duplicate-scholarship bars) that cause rejection at Common Service Centres (CSCs), "
        "(3) regional language and voice barriers for >85% of citizens, and (4) steep friction when drafting formal **CPGRAMS** complaints within strict "
        "2,000-character and Ministry-routing rules.",
        size=10.5,
    )
    add_para(
        doc,
        "**The Solution — JanSahayak AI:** An end-to-end, multilingual, voice-and-text **Agentic Hybrid RAG Copilot** built strictly on the IIT Kharagpur "
        "Track B small-model constraint (**`Qwen/Qwen3-8B`** + **`bge-small-en-v1.5`**, zero fine-tuning). Rather than trusting an 8B model's parametric "
        "memory, JanSahayak AI wins reliability through **section-aware hybrid retrieval (BM25 + Dense + RRF + Cross-Encoder)**, a **ReAct Reflector loop**, "
        "a **deterministic eligibility rule engine** (`95.6%` extracted-field accuracy), **code-enforced HITL CPGRAMS grievance filing** (with sandbox API, "
        "live Gmail SMTP receipts, and assisted `pgportal.gov.in` handoff), **DPDP Act 2023 PII masking**, and **full Admin Trace & Evaluation Observability**.",
        size=10.5,
    )

    add_styled_table(
        doc,
        headers=["Dimension", "What JanSahayak AI Delivers", "Verified Engineering / Impact Evidence"],
        rows=[
            ["**Core Scope & Refusal Contract**", "Answers grounded scheme Q&A across 649 Central schemes with `[n]` citations, runs deterministic profile eligibility checks, generates Document Readiness Checklists, drafts/submits/tracks CPGRAMS grievances (HITL-gated), and supports **7 Indian languages** (EN/HI/Hinglish/MR/BN/TA/TE) with voice I/O & localized follow-ups. Strictly refuses document forgery, CAPTCHA bypass, medical/investment advice, and invented schemes.", "Zero unconfirmed grievance submissions (`4/4` blocked); `20/20` Red-Team attacks handled (`>=84%` 95% Wilson lower bound); `15/15` fault-injection recoveries."],
            ["**Unique Selling Proposition (USP)**", "Unlike generic chatbots that hallucinate welfare rules (`81–87%` error rate without RAG), JanSahayak AI pairs **code-enforced eligibility verdicts** with **end-to-end grievance action**, **18 documented privacy/safety controls**, and **low-cost small-model economics**.", "Indicative operating cost of **~₹67 per 1,000 citizen tasks** (`~7.1K` tok/task at illustrative `$0.10/M` blended small-model pricing); runs on a single constrained worker."],
            ["**Social Impact & Sustainability Path**", "Designed as Digital Public Infrastructure (DPI) ready to plug into **Bhashini** (22-language ASR/TTS), **DigiLocker** (verified certificates), **UMANG**, and **5.5L+ Common Service Centres (CSCs)**. Fundable via **Azim Premji Foundation**, **EkStep Foundation**, **Gates Foundation**, and **MeitY IndiaAI Mission** public-good grants plus State GovTech SaaS pilots.", "Production Dockerized React + FastAPI portal with RBAC personas, two-tier caching, right-to-erasure (`DELETE /api/sessions/{id}`), and reproducible offline eval suite."],
        ],
        col_widths_in=[1.35, 3.65, 2.14],
        font_size=9.2,
    )

    add_callout(
        doc,
        "Core Track B Engineering Thesis",
        "An 8B-parameter small model is made production-reliable by measuring every failure in execution traces and fixing it with a deterministic code guard and regression test—never by prompting harder. Every metric in this report is backed by reproducible JSON/MD runs in `eval/reports/` with 95% Wilson confidence intervals and exact paired McNemar tests.",
        fill_hex=HEX_LIGHT_BLUE,
        accent_hex=HEX_BLUE,
    )

    # ==========================================================================
    # SECTION 2: ARCHITECTURE, LANGGRAPH REFLECTOR LOOP & 5 TYPED TOOLS
    # ==========================================================================
    add_h1(doc, "2. System Architecture, LangGraph Orchestration & Full-Stack Flow", page_break_before=True)
    add_figure(
        doc,
        DIAG_DIR / "clean_01_system_architecture.png",
        "Figure 1: JanSahayak AI Synchronized System Architecture — React 18 Glass UI, FastAPI Gateway, 7-Stage LangGraph Brain (with ReAct Reflector Loop & Critic), 5 Pydantic Tools, and IIT KGP Hosted VMs.",
        width_in=7.0,
    )
    add_para(
        doc,
        "A **React 18 + TypeScript + Tailwind** glass-morphism frontend communicates via **Server-Sent Events (SSE)** with a **FastAPI** backend "
        "orchestrating a compiled **LangGraph `StateGraph`** (`backend/agent/graph.py`). All reasoning executes in English: non-English queries "
        "(Hindi, Hinglish, Marathi, Bengali, Tamil, Telugu) are pivoted to English before retrieval and localized back at output using the same "
        "`Qwen/Qwen3-8B` endpoint. Every turn emits live step status events to the UI **'Thinking' indicator**, attaches up to **3 zero-latency "
        "localized `suggested_followups`** in the user's own script (`backend/agent/followups.py`), and persists structured spans to SQLite.",
        size=10.5,
    )

    add_h2(doc, "2.1 Request Lifecycle & ReAct Reflector Loop Safety")
    add_bullets(
        doc,
        [
            "**Pre-Agent Gateway (`<1 ms`):** Loads persistent SQLite session & Citizen Profile, masks Indian PII (`Aadhaar`, `PAN`, `Mobile`, `IFSC`, `Bank Account`) before any LLM or cache call, evaluates Input Guardrails (direct/base64 injection, fraud/forgery, out-of-scope), and checks a **Two-Tier Cache** (Tier-1 SHA-256 exact + Tier-2 cosine `>=0.92` semantic cache; automatically bypassed when PII or stateful actions are present).",
            "**Planner -> Executor -> Reflector Loop:** Planner classifies intent and emits Pydantic-validated tool calls (short-circuiting bare-ID inputs, help requests, or out-of-scope queries). Executor runs tools (pausing immediately for HITL consent on grievance submission). For scheme/eligibility intents, the **Reflector node** inspects compact tool summaries and decides whether to answer, search again with a refined query, check additional schemes, or ask a clarifying question.",
            "**Hard Loop Safety Bounds:** Capped at **max 10 tool calls**, **max 2 reflection rounds**, and a strict per-query token budget. Unsafe reflector outputs (repeated/empty queries, invented scheme slugs, exhausted budget, malformed JSON) deterministically downgrade to `\"answer\"`, with every guard firing logged to the trace.",
            "**Synthesizer -> Critic -> Localizer:** Synthesizer writes a grounded answer with `[n]` inline citations. Critic runs deterministic checks (unmasked PII, missing/out-of-range citations, `<=2,000`-char grievance limit) plus an LLM faithfulness audit, triggering at most **1 automatic revision pass** before translation, persistence, and caching.",
            "**Shared-VM Concurrency Protection:** Because the IIT KGP endpoint key is shared and returns HTTP `429` under concurrency, the backend runs **1 Uvicorn worker** with an `asyncio.Semaphore(1)` LLM queue, per-session `15 RPM` rate limiting, and exponential backoff—trading peak parallelism for 100% reliability on shared infrastructure.",
        ],
        size=10.5,
    )

    add_h2(doc, "2.2 Five Pydantic-Validated Agent Tools")
    add_styled_table(
        doc,
        headers=["Tool Name", "Contract & Mechanism", "Safety & Reproducibility Boundary"],
        rows=[
            ["`search_schemes`", "Hybrid **BM25 + `bge-small-en-v1.5` Dense + RRF (`k=60`) + CPU `ms-marco-MiniLM-L-6-v2` Reranker** over 649 Central schemes & 7,724 FAQs.", "Auto-falls back to `.gov.in` DuckDuckGo only when top rerank score `< 0.25`; web fallback is **disabled in all evaluations** for strict reproducibility."],
            ["`check_eligibility`", "**Deterministic rule engine** (`profile_matching.py`) matching citizen profile fields against pre-extracted scheme rules (`criteria_extractor.py`).", "LLM **never decides eligibility**. Unverifiable schemes return `NEEDS_MORE_INFO` rather than guessing `ELIGIBLE`."],
            ["`web_search_gov_schemes`", "Explicit domain-restricted search (`site:.gov.in OR site:.nic.in`) for newly announced schemes outside the local corpus.", "Retrieved snippets are wrapped in `<UNTRUSTED_WEB_EVIDENCE>` delimiters and neutralized against indirect prompt injection (RT-18/19)."],
            ["`draft_grievance`", "Maps complaint to exact Central Ministry code (51 Ministries) and drafts a formal English CPGRAMS complaint.", "Deterministically enforces CPGRAMS `<= 2,000`-character ceiling and opens the frontend HITL review modal."],
            ["`submit_or_track_grievance`", "Submits confirmed grievance to CPGRAMS Sandbox + dispatches **live Gmail SMTP receipt** + generates `pgportal.gov.in` Assisted Handoff Packet; or tracks registration IDs.", "Code-gated on `user_confirmed=True`. Graph forces `False` on every planner call; only the citizen's explicit **Confirm** click unlocks submission."],
        ],
        col_widths_in=[1.50, 2.94, 2.70],
        font_size=9.2,
    )

    # ==========================================================================
    # SECTION 3: USER JOURNEYS & END-TO-END DATA FLOW
    # ==========================================================================
    add_h1(doc, "3. End-to-End User Journeys & Live Hybrid RAG Data Flow", page_break_before=True)
    add_figure(
        doc,
        DIAG_DIR / "clean_02_hybrid_rag_dataflow.png",
        "Figure 2: End-to-End Hybrid RAG & Agentic Request Data Flow — Offline Ingestion Pipeline (Top) and Online Multilingual Query, Hybrid RRF + Reranking, Reflector/Critic Verification & SSE Delivery (Bottom).",
        width_in=7.0,
    )
    add_para(
        doc,
        "JanSahayak AI serves two distinct RBAC personas in the same unified portal (`frontend/src/App.tsx`): **Citizen Personas** (Priya Sharma, "
        "Ramesh Kumar, Abdul Rahim, Sunita Devi — pre-loaded with realistic profiles, persistent chat sessions via `SessionsSidebar`, Dark/Light glass "
        "theme, 7-language voice STT/MP3 TTS, clickable `[n]` source pills, localized follow-up suggestions, and 1-click CPGRAMS modal) and **Admin Evaluators** "
        "(unlocking the Execution Trace Waterfall, latency/token telemetry, DPDP trace cleanup, and 9 live/static Evaluation Benchmark reports).",
        size=10.5,
    )
    _add_side_by_side_images(
        doc,
        SHOT_DIR / "helpdesk-chat-light.png",
        "Figure 3a: Citizen Helpdesk — Multilingual Chat, Voice I/O, Structured Citations, Eligibility Cards & Suggested Follow-Ups.",
        SHOT_DIR / "grievance-modal.png",
        "Figure 3b: Human-in-the-Loop (HITL) CPGRAMS Review Modal — Mandatory Citizen Confirmation Before Submission & Live Email Receipt.",
    )

    # ==========================================================================
    # SECTION 4: PROMPTING BASELINE & SMALL-MODEL ENGINEERING
    # ==========================================================================
    add_h1(doc, "4. Prompting Baseline & Engineering Around an 8B Small Model", page_break_before=True)
    add_para(
        doc,
        "To quantify how orchestration outperforms raw prompting on `Qwen/Qwen3-8B`, we evaluated three prompting strategies on 30 stratified queries "
        "holding the model and retriever fixed (`eval/reports/prompt_comparison.json`). Structured few-shot JSON lifted citation adherence from `10.0%` "
        "to `100.0%`, while adding the Critic loop eliminated all unsupported numeric claims (`0.0%` hallucination; 95% Wilson CI ~`89–100%` on `n=30`).",
        size=10.5,
    )
    add_styled_table(
        doc,
        headers=["Prompting Strategy (30 Stratified Queries)", "Answer Accuracy", "Citation Adherence", "Hallucination Rate*", "Avg Latency"],
        rows=[
            ["**P1** Zero-Shot Direct (no schema, no critic)", "93.3%", "10.0%", "66.7%", "4.18 s"],
            ["**P2** Few-Shot Structured JSON", "96.7%", "100.0%", "6.7%", "4.11 s"],
            ["**P3** Planner-Executor-Synthesizer-Critic (Production)", "**100.0%**", "**100.0%**", "**0.0%**", "4.49 s"],
        ],
        col_widths_in=[2.85, 1.05, 1.15, 1.20, 0.89],
        font_size=9.4,
    )
    add_para(
        doc,
        "Note: In the P1–P3 comparison, 'hallucination' flags either an inaccurate fact or a rupee figure stated without an inline `[n]` citation. "
        "P1–P3 predated the Reflector loop; chain-of-thought and self-consistency were not tested.",
        size=9.2,
    )

    add_h2(doc, "4.1 Trace-Driven Failure Catalog: How Qwen3-8B Broke & Deterministic Guards Built")
    add_styled_table(
        doc,
        headers=["Observed Qwen3-8B Failure in Traces", "Deterministic Code Guard Added", "Verified Regression Evidence"],
        rows=[
            ["Wrapped JSON in `<think>` tags/markdown fences or dropped braces", "Strip `<think>`, regex JSON extractor, Pydantic validation + 1 LLM repair shot.", "`5/5` malformed-JSON fault cases recovered."],
            ["Drafted a CPGRAMS grievance from a bare Aadhaar-like number (`1234 5678 9012`)", "Bare-ID detector routes directly to a safe clarifying question before planning.", "Regression test named after the captured trace."],
            ["Searched literal words *\"which schemes am I eligible for\"*", "Broad eligibility queries are rebuilt from Citizen Profile + beneficiary-group filter.", "Profile-matching regression test suite."],
            ["Omitted `continues_request` after asking a clarifying question", "Code detects the bot's own clarifying prompt in history and resumes original intent.", "Multi-turn continuation regression test."],
            ["Reflector repeated queries or invented non-existent scheme slugs", "Reflector validator downgrades duplicate/empty queries or unknown slugs to `\"answer\"`.", "Unit tests in `tests/test_agent_loop.py`."],
            ["Marked schemes `ELIGIBLE` when criteria could not be verified", "Deterministic `check_eligibility` rule engine (`criteria_extractor.py` + `profile_matching.py`); unverifiable -> `NEEDS_MORE_INFO`.", "**95.6%** extracted fields correct overall (**94.3%** on 19 held-out schemes)."],
            ["Asked citizen's age on general scheme info questions / refused real schemes", "Questions without `I/my/we` answer as general rules; catalog-named schemes never out-of-scope.", "Gold Q&A answered rose **52/60 -> 60/60**."],
            ["Ran unneeded eligibility checks on plain info queries (`38/45` tasks)", "Reflector loop explicitly skips eligibility checks on non-personal info questions.", "80-Task Loop completion jumped **70.0% -> 81.2%** (corrected key)."],
            ["JSON repair filled `continues_request` text field with boolean `true/false`", "Coerce non-string `continues_request` to empty string while preserving valid plan.", "Fault injection jumped **12/15 -> 15/15** (`FI-03..FI-05`)."],
        ],
        col_widths_in=[2.25, 2.75, 2.14],
        font_size=9.0,
    )

    # ==========================================================================
    # SECTION 5: CORPUS, 5-WAY CHUNKING ABLATION & RETRIEVAL EVALUATION
    # ==========================================================================
    add_h1(doc, "5. Corpus Design, 5-Way Chunking Ablation & Hybrid Retrieval", page_break_before=True)
    add_para(
        doc,
        "The local corpus indexes **649 Central Government schemes** scraped from `schemes.gov.in` (`myScheme`) across **51 Ministries**, plus "
        "**7,724 official FAQs**. Official scheme descriptions are split along structural headers (`benefits`, `eligibility`, `documents`, `how to apply`) "
        "into chunks capped at **440 tokens with 35-word overlap** (`3,204` official-text chunks), while FAQs are indexed separately (`6,059` total "
        "indexed chunks in production). All retrieval metrics below are measured **independently of the LLM**.",
        size=10.5,
    )

    add_h2(doc, "5.1 4-Way Retrieval Ablation (60-Q Zero-Leakage Gold Set & 73-Q Task Suite)")
    add_styled_table(
        doc,
        headers=["Retriever Configuration", "Gold Hit@1", "Gold Hit@5", "Gold MRR", "Task 73Q R@5", "Task 73Q MRR", "Warm Latency"],
        rows=[
            ["**R1** BM25-Only (Sparse Lexical)", "96.7%", "100.0%", "0.983", "93.2%", "0.920", "~0.1 s"],
            ["**R2** Dense-Only (`bge-small-en-v1.5`)", "88.3%", "98.3%", "0.931", "94.5%", "0.877", "<0.01 s"],
            ["**R3** Hybrid RRF (`BM25 + Dense, k=60`)", "**100.0%**", "**100.0%**", "**1.000**", "**95.9%**", "**0.925**", "~0.1 s"],
            ["**R4** Hybrid RRF + Cross-Encoder (Prod)", "98.3%", "**100.0%**", "0.987", "**95.9%**", "0.892", "~1.7 s (CPU)"],
        ],
        col_widths_in=[2.22, 0.78, 0.78, 0.76, 0.88, 0.86, 0.86],
        font_size=9.0,
    )
    add_para(
        doc,
        "**Retrieval Engineering Insight:** Retrieval is *not* the bottleneck—Hybrid RRF (`R3`) achieves **100% Hit@5** on the 60-Q Gold set and "
        "**95.9% Recall@5** on the 73-Q Task Suite (the only 3 misses are 2 multilingual queries `ML-08, ML-10` and 1 grievance query `GRV-08`). "
        "The CPU Cross-Encoder (`R4`) adds `~1.7 s` latency and raises exact-sentence **Evidence Hit@5** from `96.7%` to **`98.3%`** (`100%` source-section "
        "hit), making it a clear latency-vs-precision trade-off candidate for future GPU acceleration or selective reranking.",
        size=10.5,
    )

    add_h2(doc, "5.2 5-Way Chunking Ablation & Context Window (Top-k 1 / 3 / 5) Experiments")
    add_styled_table(
        doc,
        headers=["Chunking Strategy (649 Schemes Re-Indexed)", "Official Chunks", "Evidence Hit@5 (R4)", "McNemar p vs Prod", "Engineering Verdict"],
        rows=[
            ["**Section-aware, 440 tok, 35-word overlap (Prod)**", "3,204", "**98.3%**", "—", "Selected: preserves full rule sections."],
            ["Section-aware, 256 tok, 20-word overlap", "5,350", "96.7%", "1.0", "Statistically tied; splits multi-clause rules."],
            ["Section-aware, 128 tok, 10-word overlap", "12,264", "88.3%", "**0.031** (sig.)", "Significantly worse; fractures evidence."],
            ["Section-aware, 440 tok, no overlap", "3,101", "96.7%", "1.0", "Tied; overlap guards boundary splits."],
            ["Fixed 440-token windows across sections", "2,623", "95.0%", "0.5", "Bleeds benefits into exclusion clauses."],
        ],
        col_widths_in=[2.35, 0.90, 1.15, 1.05, 1.69],
        font_size=9.2,
    )
    add_para(
        doc,
        "**Context Budget Sensitivity (Top-k 1 / 3 / 5 on 30-Q Gold Subset, Full Agent + Gemini 3.5 Flash-Lite Judge):** Passing **Top-1** chunk achieved "
        "`93.3%` (`4.60/5`, `3,870` tok, `11.4 s`), **Top-3** achieved `93.3%` (`4.70/5`, `5,285` tok, `11.2 s`), **Top-5** peaked at **`96.7%` (`29/30`, "
        "`4.73/5`, `6,628` tok, `14.0 s`)**, while the production default (`6–8` chunks) scored `83.3%` (`25/30`, `4.37/5`, `9,227` tok, `15.3 s`). "
        "Top-5 gained `+0.37` judge points (`95% CI: +0.07 to +0.70`, `p=0.125`), suggesting smaller 8B models reason more crisply over tighter top-5 context.",
        size=10.5,
    )

    # ==========================================================================
    # SECTION 6: ANSWER QUALITY, ZERO-LEAKAGE BENCHMARKS & 80-TASK SUITE
    # ==========================================================================
    add_h1(doc, "6. Answer Quality, Zero-Leakage Gold Q&A & 80-Task Agent Suite", page_break_before=True)
    add_figure(
        doc,
        DIAG_DIR / "clean_04_synced_eval_benchmarks.png",
        "Figure 4: Synchronized Quantitative Benchmarks — (A) 60-Q Zero-Leakage Gold QA (FAQ Excluded), (B) 80-Task Agent Suite, (C) 5-Way Chunking Ablation, (D) Root-Cause Failure Reduction.",
        width_in=7.05,
    )

    add_h2(doc, "6.1 Zero-Leakage 60-Question Gold Q&A Evaluation (Dual Independent Verification)")
    add_para(
        doc,
        "To strictly eliminate data leakage between evaluation questions and indexed FAQs, **two complementary zero-leakage 60-question benchmarks** "
        "were built and audited independently using **non-Qwen Gemini judges** (eliminating Qwen-judging-Qwen self-bias):\n"
        "1. **PR #1 Official-Text Gold Suite (`eval/reports/gold_eval.json`, `n=60`):** Balanced 15 questions each across *benefits, eligibility, documents, "
        "how to apply* verified programmatically for exact supporting quotes, exact numbers, and `<=0.5` FAQ similarity (rejecting 35 leaky drafts). "
        "**Crucially, FAQ chunks are completely excluded from retrieval during every run**, and graded by **Gemini 3.5 Flash-Lite**.\n"
        "2. **Independent Scenario Gold Suite (`eval/reports/gold60_comprehensive_eval.json`, `n=60` across 24 Ministries):** Audited against all `7,724` "
        "corpus FAQs (`0` verbatim matches) and independently graded item-by-item by **Antigravity (Gemini)** comparing Vanilla `Qwen3-8B` vs. Hybrid RAG.",
        size=10.5,
    )

    add_styled_table(
        doc,
        headers=["Gold Q&A Run (FAQ Excluded, Gemini 3.5 Flash-Lite)", "n", "Judged Correct", "Judge (1-5)", "ROUGE-L", "BLEU", "BERTScore*", "McNemar p"],
        rows=[
            ["**Full Pipeline (Loop + Hybrid + Reranker)**", "60", "**88.3% (53)**", "**4.53**", "0.230", "7.20", "0.172", "—"],
            ["Single Pass (Reflector Loop Off)", "60", "93.3% (56)", "4.72", "0.250", "8.06", "0.206", "0.375 (n.s.)"],
            ["Before Retrieval Fixes (Guards Only)", "58", "69.0% (40)", "3.91", "0.202", "5.97", "0.144", "**0.013** (sig.)"],
            ["Qwen3-8B Alone (No Corpus Baseline)", "58", "19.0% (11)", "2.59", "0.224", "5.34", "0.233", "**<0.001** (sig.)"],
            ["*Independent 60-Q Audit: Vanilla vs Hybrid RAG*", "60", f"11.7% -> **{jdg_r['pass_rate']*100:.1f}%**", f"{jdg_v['avg_accuracy_5']:.2f} -> **{jdg_r['avg_accuracy_5']:.2f}**", f"{nlp_v['rouge_l_f1']*100:.1f}% -> **{nlp_r['rouge_l_f1']*100:.1f}%**", f"{nlp_v['bleu_corpus']*100:.1f} -> **{nlp_r['bleu_corpus']*100:.1f}**", f"{nlp_v['bertscore_f1']*100:.1f}% -> **{nlp_r['bertscore_f1']*100:.1f}%**", "Halluc: 86.7% -> **3.3%**"],
        ],
        col_widths_in=[2.12, 0.36, 0.96, 0.84, 0.78, 0.64, 0.78, 0.66],
        font_size=8.6,
    )
    add_para(
        doc,
        "Metric Note: PR #1 BERTScore uses `roberta-large` rescaled with baseline (`0.17–0.23`); the independent 60-Q audit uses raw `distilbert-base-uncased` "
        "F1 (`84.4%` vs `85.2%`). **Both studies prove the exact same critical insight:** surface text-overlap metrics (ROUGE-L & BERTScore) score fluent "
        "hallucinated Vanilla LLM answers nearly as high as—or higher than—grounded RAG answers, whereas an independent LLM judge cleanly exposes Vanilla "
        "`Qwen3-8B`'s **`81–87%` numerical hallucination rate** (`p < 0.001`).",
        size=9.5,
    )

    add_h2(doc, "6.2 80-Task End-to-End Agent Suite & Diagnose -> Fix -> Re-Measure Loop")
    add_styled_table(
        doc,
        headers=["Task Category (80-Task Suite)", "n", "Loop (Corrected)", "Loop (Original)", "Single (Corrected)", "Single (Original)"],
        rows=[
            ["Deterministic Eligibility Checks", "20", "**100.0%**", "70.0%", "85.0%", "65.0%"],
            ["Scheme QA, FAQs & 6 Indian Languages", "45", "**68.9%**", "68.9%", "64.4%", "64.4%"],
            ["Adversarial / Out-of-Scope Refusals", "7", "**100.0%**", "100.0%", "85.7%", "85.7%"],
            ["CPGRAMS Grievance Drafting (<=2K chars)", "7", "85.7%", "85.7%", "85.7%", "85.7%"],
            ["CPGRAMS Ticket Tracking", "1", "**100.0%**", "100.0%", "100.0%", "100.0%"],
            ["**ALL 80 END-TO-END TASKS**", "**80**", "**81.2% (65/80)**", "**73.8% (59/80)**", "73.8% (59/80)", "68.8% (55/80)"],
        ],
        col_widths_in=[2.26, 0.44, 1.11, 1.11, 1.11, 1.11],
        font_size=9.2,
    )
    add_para(
        doc,
        "**Diagnose -> Fix -> Re-Measure Proof:** Initially the Reflector loop lagged single-pass (`70.0%` vs `71.2%`). Execution traces disproved our "
        "hypothesis of context overload and pinpointed two real bugs: (1) the loop ran unneeded eligibility checks on `38/45` plain information questions, "
        "and (2) the grounding judge could not see eligibility-tool outputs, falsely penalizing true facts. Fixing both lifted Loop completion from "
        "**`70.0% -> 81.2%`** (`62.5% -> 73.8%` on the unchanged original key, cutting hallucinations `13 -> 9`). On the 7 tasks where the Reflector took "
        "an extra action, it completed **7/7** vs **3/7** for single-pass (overall McNemar `p=0.07`; avg `1.34` tool calls/task, max `4`, never hitting the 10-call cap).",
        size=10.5,
    )

    # ==========================================================================
    # SECTION 7: FAILURE TAXONOMY, LATENCY BREAKDOWN & COST ECONOMICS
    # ==========================================================================
    add_h1(doc, "7. Failure Taxonomy, Latency Breakdown & Token Cost Economics", page_break_before=True)
    add_para(
        doc,
        "Every failed task receives a single root cause assigned in strict pipeline order (`tool_call_error -> retrieval_miss -> hallucination -> "
        "reasoning_error`), verified against the exact evidence chunks seen by the writer using Gemini 3.5 Flash-Lite (`eval/failure_taxonomy.py`). "
        "A manual audit of 17/20 sampled failures agreed with the automatic classifier **`94%` of the time (Cohen's `kappa = 0.92`)**.",
        size=10.5,
    )
    add_styled_table(
        doc,
        headers=["Evaluation Run", "Total Fails", "Tool-Call Error", "Retrieval Miss", "Hallucination", "Reasoning Error"],
        rows=[
            ["**Tasks: Reflector Loop (Current)**", "**15 / 80**", "2", "2 (ML-08, ML-10)", "**9** (mostly doc lists)", "2"],
            ["Tasks: Single Pass (Current)", "21 / 80", "2", "2", "11", "6"],
            ["Tasks: Reflector Loop (Before Fixes)", "24 / 80", "2", "9", "13", "0"],
            ["Gold Q&A: Full Pipeline (60 Qs)", "7 / 60", "1", "2", "1", "3"],
            ["Gold Q&A: Single Pass (60 Qs)", "4 / 60", "1", "2", "1", "0"],
        ],
        col_widths_in=[2.24, 0.88, 0.94, 1.12, 1.12, 0.84],
        font_size=9.2,
    )

    add_h2(doc, "7.1 Stage-by-Stage Latency Breakdown & Cost Economics")
    add_figure(
        doc,
        DIAG_DIR / "clean_03_eval_benchmarks_v2.png",
        "Figure 5: Independent 60-Pair Verification — Top-1/3/5 Ablation, ROUGE/BLEU/BERTScore vs. Gemini Judge, and Retrieval + LLM Latency Split.",
        width_in=7.0,
    )
    add_styled_table(
        doc,
        headers=["Configuration (60-Q Full Agent Gold Run)", "Retrieval", "Plan + Reflect", "Answer Writing", "Total Avg", "Total P95", "Avg Tokens"],
        rows=[
            ["**Full Pipeline (Reflector Loop + R4)**", "3.25 s", "4.53 s", "6.86 s", "14.75 s", "18.15 s", "9,258"],
            ["Single Pass (Loop Off + R4)", "2.55 s", "2.25 s", "6.04 s", "10.91 s", "14.37 s", "7,156"],
            ["Vanilla Qwen3-8B (No Documents)", "0.00 s", "0.00 s", "1.73 s", "1.73 s", "2.35 s", "153"],
            ["*80-Task Suite: Loop vs Single Pass*", "CPU rerank", "+1.4 s loop", "8B generation", "15.0s vs 13.7s", "33.6 s (Loop)", "7,092 vs 6,547"],
        ],
        col_widths_in=[2.22, 0.72, 0.90, 0.90, 0.84, 0.78, 0.78],
        font_size=8.9,
    )
    add_para(
        doc,
        "**Cost Analysis:** On the 80-task suite, the Reflector loop averages `7,092` tokens vs `6,547` for single-pass (`+8.3%` token overhead). "
        "At an illustrative small-model blended price of `$0.10 / 1M` tokens (`~₹94/USD`), **1,000 full citizen welfare tasks cost only ~₹67** "
        "(`~₹0.07` per citizen interaction), while Tier-1/Tier-2 cache hits return in **`<50 ms` at zero LLM token cost**.",
        size=10.5,
    )

    # ==========================================================================
    # SECTION 8: GUARDRAILS, DPDP PRIVACY, SAFETY & OBSERVABILITY
    # ==========================================================================
    add_h1(doc, "8. Guardrails, DPDP Act 2023 Privacy, Red-Teaming & Observability", page_break_before=True)
    add_para(
        doc,
        "Our dedicated security audit (`docs/06_Guardrail_and_Privacy_Analysis.md`) maps **18 concrete privacy and safety breaches** to code-enforced "
        "defences. Re-run on the current codebase (25 Nov), **20/20 Red-Team attacks** were blocked (honest 95% Wilson lower bound: `>=84%` on known "
        "attack families) and **15/15 Fault-Injection scenarios** passed after fixing the `continues_request` JSON-repair boolean regression.",
        size=10.5,
    )
    add_styled_table(
        doc,
        headers=["Privacy / Safety Threat", "Code-Enforced Defense in JanSahayak AI", "Verification / Test Proof"],
        rows=[
            ["Aadhaar, PAN, Mobile, IFSC, Bank No. leakage", "Regex PII masker redacts before LLM, cache, DB, or trace storage (`[AADHAAR_MASKED:XXXX-XXXX-0123]`); Critic re-scans drafts; PII disables cache.", "`test_guardrails.py` + `RT-15..RT-17`"],
            ["Direct, Base64 & Indirect Web Prompt Injection", "Input shield blocks direct/base64 injections & secret exfiltration before planning; web snippets wrapped & neutralized as untrusted text.", "`RT-01..RT-05`, `RT-18`, `RT-19`"],
            ["Fraud, Forgery, CAPTCHA Bypass & Hallucinated Schemes", "Deterministic policy refusal with official portal pointers; low retrieval confidence triggers honest 'not found' instead of fabrication.", "`RT-07..RT-14`, `RT-20`"],
            ["Unconsented CPGRAMS Grievance Filing (HITL)", "Submission code-gated on `user_confirmed=True`; graph forces `False` on planner calls; only citizen's Confirm button submits.", "`RT-06`, `FI-06..FI-09` (4/4 blocked)"],
            ["Cross-Citizen Session Access & DPDP Erasure", "Ownership check (`401/403`) on every session/chat/grievance endpoint; `DELETE /api/sessions/{id}` wipes history/profile/drafts & unlinks traces; strict IIT CA TLS.", "`tests/test_api.py` RBAC & ownership suite"],
            ["CPGRAMS 503 / Malformed JSON Tool Faults", "Graceful fallback to Assisted Portal Handoff Packet + 1-shot JSON repair (`continues_request` non-text coercion).", "`FI-01..FI-15` (**15/15** passed)"],
        ],
        col_widths_in=[1.85, 3.55, 1.74],
        font_size=9.1,
    )

    _add_side_by_side_images(
        doc,
        SHOT_DIR / "trace-dashboard.png",
        "Figure 6a: Admin Execution Trace Waterfall — Live Per-Node Latency, Token Usage, Guardrail Flags, Tool Calls & Markdown/JSON Export.",
        SHOT_DIR / "eval-dashboard.png",
        "Figure 6b: Admin Evaluation Dashboard — Synchronized Static & Live Benchmarks (9 Reports, ROUGE/BLEU/BERTScore, Gemini Judge & Exports).",
    )

    # ==========================================================================
    # SECTION 9: TAKEAWAYS, HONEST LIMITATIONS & POPULATION-SCALE ROADMAP
    # ==========================================================================
    add_h1(doc, "9. Key Takeaways, Honest Limitations & Population-Scale Roadmap", page_break_before=True)

    add_h2(doc, "9.1 Five Empirical Engineering Takeaways")
    add_bullets(
        doc,
        [
            "**Deterministic code for everything that must be right:** Eligibility verdicts, PII masking, citation verification, and the HITL submission gate live in deterministic Python—`Qwen3-8B` plans and explains, never decides eligibility or consent.",
            "**Hybrid retrieval solves discovery (`100%` Hit@5):** Because BM25 + `bge-small` RRF reliably surfaces the right scheme, engineering effort focused where it matters most—context hygiene, reflector guards, and faithfulness.",
            "**LLM-as-a-Judge outperforms text-overlap metrics:** ROUGE-L and BERTScore failed to separate fluent hallucinations (`19%` correct) from grounded answers (`88.3%` correct); external Gemini judging exposed exact factual gaps.",
            "**Audit your own measurements:** Two apparent 'model bugs' were measurement bugs (a judge blind to eligibility tool output, and 6 flawed original answer-key items—disclosed transparently with both keys reported).",
            "**Trace-first debugging beats blind prompt tuning:** Inspecting Langfuse-style traces turned a lagging loop (`70.0%`) into an `81.2%` task-completion agent (`100%` on eligibility checks and refusals).",
        ],
        size=10.5,
    )

    add_h2(doc, "9.2 Transparent Scientific Limitations & Immediate Engineering Next Steps")
    add_styled_table(
        doc,
        headers=["Known Limitation (Disclosed Honestly)", "Concrete Next-Sprint Engineering Fix"],
        rows=[
            ["**Multilingual Gap (`4/10` Loop Tasks):** Indian-language translation loses nuance (`ML-08, ML-10`), and injection regexes are English-only pre-translation.", "Integrate **MeitY Bhashini** Indic ASR/NMT/TTS APIs + run injection detection post-translation + expand multilingual eval to 60 tasks."],
            ["**Hallucinated Document Lists (`9/15` remaining task fails):** Qwen occasionally adds plausible documents (e.g. 'business plan') absent from evidence.", "Add a deterministic **Document-List Critic Guard** matching every cited document phrase against retrieved chunks (same pattern as citation checks)."],
            ["**Evaluation Rigor Caveats:** Post-fix scores are measured on the same 80 tasks/60 Qs (non-held-out); human review of the 60 gold Qs and blind judge audit remain pending; top-5 context (`96.7%`) not yet swapped into prod.", "Lock a fresh **50-task held-out blind test set**, complete 2-reviewer blind human scoring, switch production synthesizer to top-5 chunks, and benchmark a second generator."],
            ["**Privacy Edge Cases:** Regex masker misses free-text names/addresses; weak local eligibility searches send coarse profile terms to DuckDuckGo fallback.", "Add lightweight Indic NER redaction (`Presidio`/spaCy) and strip profile attributes from `.gov.in` web-fallback queries (send only user words or allow admin toggle-off)."],
        ],
        col_widths_in=[3.45, 3.69],
        font_size=9.2,
    )

    add_h2(doc, "9.3 Population-Scale DPI Vision & Social-Impact Funding Roadmap")
    add_styled_table(
        doc,
        headers=["Phase & Horizon", "Product & DPI Milestone", "Distribution & Funding Model"],
        rows=[
            ["**Phase 1 (Months 0–3)**\n*District CSC Pilot*", "Deploy via **500 Common Service Centres (CSCs)** & WhatsApp/Telegram Voice Bot across 2 districts (UP + Maharashtra); add State schemes (4,670+ total).", "Philanthropic seed grant (**Azim Premji Foundation**, **EkStep Foundation**, **MeitY IndiaAI Innovation Challenge**)."],
            ["**Phase 2 (Months 3–9)**\n*DPI Integration*", "Integrate **Bhashini** (22 official languages), **DigiLocker** (auto-verify income/caste/education certificates), and **API Setu / UMANG** live CPGRAMS submission.", "Co-funded Digital Public Good (DPG) partnership with **Gates Foundation / NIC / State IT Departments**."],
            ["**Phase 3 (Months 9–18)**\n*National Scale*", "Dedicated multi-GPU vLLM inference cluster (`<2.5s` P95 latency), proactive WhatsApp DBT-delay alerts, and anonymized policy-gap analytics for Ministries.", "Sustainable **B2G SaaS** (`~₹0.07/query` infra cost) + CSR-sponsored rural voice helplines serving 10M+ citizens annually."],
        ],
        col_widths_in=[1.45, 3.15, 2.54],
        font_size=9.2,
    )

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(OUT_PATH))
    return OUT_PATH


if __name__ == "__main__":
    p = build_synchronized_report()
    print(f"[OK] Built Final Synchronized Technical Report: {p} ({p.stat().st_size:,} bytes)")
