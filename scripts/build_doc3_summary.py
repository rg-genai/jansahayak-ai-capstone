"""Build Document 3: 5-6 Page Executive & Team Quick-Reference Summary Sheet (.docx) for JanSahayak AI."""

from __future__ import annotations

import json
from pathlib import Path

from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.shared import Inches, Pt

from docx_helpers import (
    HEX_BLUE,
    HEX_GREEN,
    HEX_LIGHT_BLUE,
    HEX_LIGHT_GREEN,
    HEX_LIGHT_SAFFRON,
    HEX_NAVY,
    HEX_SAFFRON,
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
    add_numbered,
    add_para,
    add_styled_table,
    create_styled_document,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DIAG_DIR = PROJECT_ROOT / "docs" / "diagrams"
CAPTURE_PATH = PROJECT_ROOT / "data" / "live_walkthrough_capture.json"
OUT_PATH = PROJECT_ROOT / "docs" / "deliverables" / "03_JanSahayak_AI_Team_Summary_Sheet.docx"


def _add_banner_header(doc) -> None:
    tbl = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.autofit = False
    cell = tbl.cell(0, 0)
    cell.width = Inches(7.4)
    _set_cell_shading(cell, HEX_NAVY)
    _set_cell_margins(cell, top=120, bottom=120, left=160, right=160)
    p1 = cell.paragraphs[0]
    p1.paragraph_format.space_after = Pt(2)
    r1 = p1.add_run("JANSAHAYAK AI — TEAM BRIEFING & MENTOR VIVA QUICK-REFERENCE SHEET")
    r1.bold = True
    r1.font.name = "Calibri"
    r1.font.size = Pt(14.5)
    r1.font.color.rgb = RGB_WHITE

    p2 = cell.add_paragraph()
    p2.paragraph_format.space_after = Pt(0)
    r2 = p2.add_run(
        "IIT Kharagpur Executive PG Certificate in GenAI & Agentic AI (Track B Capstone)  |  "
        "Multilingual Citizen Welfare Copilot & Assisted CPGRAMS Grievance Agent"
    )
    r2.font.name = "Calibri"
    r2.font.size = Pt(9.2)
    r2.font.color.rgb = RGB_SAFFRON if False else RGB_WHITE

    sp = doc.add_paragraph()
    sp.paragraph_format.space_after = Pt(3)


def _add_kpi_strip(doc) -> None:
    kpis = [
        ("649 Schemes", "7,724 FAQs • 6,059 Chunks"),
        ("95.9% R@5", "MRR@10: 0.925 (Hybrid RRF)"),
        ("100% P3 Acc.", "0.0% Hallucination (Qwen3-8B)"),
        ("100% Safety", "20/20 Red-Team • 15/15 Faults"),
        ("6 Languages", "Voice Mic + Server MP3 TTS"),
    ]
    tbl = doc.add_table(rows=1, cols=len(kpis))
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.autofit = False
    for i, (big, small) in enumerate(kpis):
        c = tbl.cell(0, i)
        c.width = Inches(1.48)
        _set_cell_shading(c, HEX_LIGHT_BLUE if i % 2 == 0 else HEX_LIGHT_SAFFRON)
        _set_cell_margins(c, top=70, bottom=70, left=70, right=70)
        p0 = c.paragraphs[0]
        p0.paragraph_format.space_after = Pt(1)
        rb = p0.add_run(big)
        rb.bold = True
        rb.font.size = Pt(11.0)
        rb.font.color.rgb = RGB_NAVY if i % 2 == 0 else RGB_SAFFRON
        p1 = c.add_paragraph()
        p1.paragraph_format.space_after = Pt(0)
        rs = p1.add_run(small)
        rs.font.size = Pt(7.6)
        rs.font.color.rgb = RGB_NAVY
    sp = doc.add_paragraph()
    sp.paragraph_format.space_after = Pt(3)


def build_summary_sheet() -> Path:
    capture = json.loads(CAPTURE_PATH.read_text(encoding="utf-8"))

    # Tight 0.55" margins -> clean, crisp 5-6 page executive summary sheet!
    doc = create_styled_document(
        header_title="JanSahayak AI — Team Quick-Reference Summary Sheet (6 Pages)",
        margin_in=0.55,
    )
    # Turn off different_first_page so page 1 has clean banner and pages 2-6 have running header/footer
    doc.sections[0].different_first_page_header_footer = True

    # =========================================================================
    # PAGE 1: IDENTITY, PROBLEM/SOLUTION, KPI STRIP & TECH STACK SPLIT
    # =========================================================================
    _add_banner_header(doc)
    _add_kpi_strip(doc)

    add_h1(doc, "1. One-Minute Elevator Pitch (Problem -> Solution -> Differentiator)")
    add_para(
        doc,
        "**The Problem:** Everyday Indian citizens miss Central Government welfare benefits worth lakhs because scheme rules are scattered "
        "across 649 English-heavy pages, exclusion clauses (like Income Tax payer disqualifications) are hidden in fine print, and filing "
        "a formal CPGRAMS complaint requires knowing the exact Central Ministry and staying within 2,000 characters.\n"
        "**Our Solution:** **JanSahayak AI** is a voice-enabled, 6-language **Agentic Hybrid RAG Copilot** that converts natural citizen "
        "questions into citation-backed scheme recommendations, deterministic eligibility verdicts, document checklists, and **Human-in-the-Loop "
        "(HITL) CPGRAMS grievance filings with live Gmail SMTP confirmation receipts**—all audited by an Admin Langfuse-style Trace Console.",
        size=9.5,
    )

    add_h2(doc, "Tech Stack Split: IIT Kharagpur Provided vs. Built by Our Team")
    add_styled_table(
        doc,
        headers=["Layer", "IIT KGP Track B Provided", "Open-Source / Built by Team", "External Live (Zero Paid SaaS)"],
        rows=[
            [
                "**Models & AI**",
                "`Qwen/Qwen3-8B` LLM (8,192 ctx, `enable_thinking=False`) + `bge-small-en-v1.5` (384-dim, VM02) + Custom CA Certs",
                "Local CPU Cross-Encoder (`ms-marco-MiniLM-L-6-v2`) + `rank-bm25` (2x title boost) + NumPy Cosine + RRF (`k=60`)",
                "DuckDuckGo `.gov.in` web fallback (`ddgs`), `gTTS` + `edge-tts` (6-lang MP3), **Gmail SMTP TLS** (real ticket emails)",
            ],
            [
                "**Orchestration & API**",
                "Hosted OpenAI-compatible vLLM endpoints (1 active req/key, 60 RPM ceiling)",
                "Single-worker **FastAPI + Uvicorn**, **7-node LangGraph StateGraph**, 5 Pydantic tools, 1-shot JSON repair, HMAC RBAC, 15 RPM limiter",
                "Browser Web Speech STT (6 Indian languages), Assisted Handoff link to official `pgportal.gov.in`",
            ],
            [
                "**Data & UI**",
                "Verified myScheme Central corpus (649 schemes + 7,724 FAQs -> 6,059 chunks `<=440` tok)",
                "**React 18 + Vite + TypeScript + Tailwind** Civic UI, **SQLite WAL**, `embeddings.npy` (~9 MB), `bm25.pkl`, Langfuse Spans, Docker/Nginx",
                "Built-in HTML Email Outbox fallback (zero-setup receipt preview & download)",
            ],
        ],
        col_widths_in=[0.95, 2.15, 2.35, 1.95],
        font_size=8.2,
    )

    add_callout(
        doc,
        "Core Architectural Thesis (Memorize for Mentor Viva!)",
        "**Why Agentic Hybrid RAG instead of Fine-Tuning or Vanilla RAG?** Welfare schemes change budgets and rules frequently—fine-tuning "
        "freezes stale facts into weights. Vanilla RAG blindly fetches chunks even for greetings and lacks self-checking. Our **Agentic Hybrid RAG** "
        "combines BM25 (exact acronyms) + `bge-small` (semantics) + Cross-Encoder (confidence gate) + deterministic eligibility rules + a **Critic revision loop**.",
        accent_hex=HEX_SAFFRON,
        fill_hex=HEX_LIGHT_SAFFRON,
    )

    # =========================================================================
    # PAGE 2: SYSTEM ARCHITECTURE & 5 CONNECTED AGENT TOOLS
    # =========================================================================
    add_h1(doc, "2. End-to-End Architecture & All 5 Agent Tools", page_break_before=True)
    add_figure(
        doc,
        DIAG_DIR / "02_system_architecture.png",
        "End-to-End Architecture: React SPA (:5173) <-> FastAPI (:8000, 1 worker) <-> 7-Node LangGraph <-> 5 Typed Tools <-> IIT KGP VMs.",
        width_in=7.2,
    )
    add_styled_table(
        doc,
        headers=["Agent Tool", "Purpose & Execution", "Safety / Reliability Mechanism"],
        rows=[
            [
                "**1. `search_schemes`**",
                "Hybrid BM25 + Dense `bge-small` -> RRF (`k=60`) -> CPU Cross-Encoder Top-6 across 6,059 chunks.",
                "Always queries in canonical English (`query_en`) for EN/HI/TA consistency; relaxes filters if score `< 0.5`.",
            ],
            [
                "**2. `check_eligibility`**",
                "Deterministic Python rule engine over SQLite: checks age, income cap, caste, gender, exclusions & documents.",
                "Auto-chained by Executor on real retrieved slugs (Planner cannot hallucinate slugs).",
            ],
            [
                "**3. `web_search_gov_schemes`**",
                "Live DuckDuckGo search strictly restricted to `site:gov.in OR site:nic.in`.",
                "Auto-triggers ONLY when `top_rerank_score < 0.35`; strips indirect prompt injections.",
            ],
            [
                "**4. `draft_grievance`**",
                "Maps scheme to exact 51-Ministry code, masks PII, enforces CPGRAMS `<= 2,000` char limit.",
                "Saves `DRAFT-XXXXXX` and sets `hitl_paused = True` to require human modal review.",
            ],
            [
                "**5. `submit_or_track_grievance`**",
                "Submits to CPGRAMS Sandbox + sends **live Gmail SMTP receipt** + Assisted Handoff, or tracks ticket ID.",
                "Hard code gate blocks submit unless `user_confirmed=True`; degrades to Handoff on 503/bad JSON.",
            ],
        ],
        col_widths_in=[1.65, 3.00, 2.75],
        font_size=8.3,
    )

    # =========================================================================
    # PAGE 3: LIVE STEP-BY-STEP WALKTHROUGH (MUMBAI MRO LOAN EXAMPLE)
    # =========================================================================
    add_h1(doc, "3. Live Query Walkthrough: Mumbai 25yo MRO Manufacturing Loan", page_break_before=True)
    add_para(
        doc,
        f"**Real Captured Live Trace (`{capture['trace_id']}`):** *\"Hi, I am a 25 year old male looking for Loan to start my small business "
        "of Small parts manufacturing like nuts, bolts and other MRO parts in Mumbai, I am eligible for which scheme?\"*",
        size=9.2,
    )
    add_figure(
        doc,
        DIAG_DIR / "04_architect_swimlane_dfd.png",
        f"Enterprise Swimlane Data Flow & Validation Blueprint ({capture['trace_id']}) — 5 Planes, 9 Langfuse Spans, 4 LLM Calls, 8,032 Total Tokens.",
        width_in=7.3,
    )
    add_callout(
        doc,
        "What Makes This Live Trace an Extraordinary Demo Story",
        "1. **Smart Geographic & Profile Extraction:** Planner inferred `state = Maharashtra` automatically from *'Mumbai'*, plus `age=25`, `gender=male`, `occ='Small parts manufacturing'`.\n"
        "2. **Hybrid Rescue:** BM25 gave `0.0` to **PM Vishwakarma** and **PMEGP** (because the user said *'nuts, bolts, MRO'*), but Dense `bge-small-en-v1.5` scored them `0.742` and `0.722` and pulled both into Top-6!\n"
        "3. **Gender Safety Filter:** Chunk `[1]` was *New Swarnima Scheme For Women*; Synthesizer respected `gender=male` and safely excluded it, recommending **PM Vishwakarma** (₹1L + ₹2L collateral-free loans).\n"
        "4. **Live Critic Self-Healing (`SPN-06 -> SPN-07`):** The Critic caught a citation attribution error in Round 0 (`[2]` instead of `[4]`/`[6]`), triggered 1 revision loop, and verified all citations before delivery!",
        accent_hex=HEX_GREEN,
        fill_hex=HEX_LIGHT_GREEN,
    )

    # =========================================================================
    # PAGE 4: CONSTRAINT ENGINEERING + SYLLABUS & RUBRIC MAPPING
    # =========================================================================
    add_h1(doc, "4. Constraint Engineering & IIT KGP Syllabus Correlation", page_break_before=True)
    add_h2(doc, "How We Engineered Around Every Track B Infrastructure Limit")
    add_styled_table(
        doc,
        headers=["Constraint", "Our Engineering Control", "Measured Impact"],
        rows=[
            ["**1 Active LLM Req / Key**", "Single-worker Uvicorn (`--workers 1`) + process-wide `asyncio.Semaphore(1)`", "Zero `429` concurrency collisions across multi-node agent turns."],
            ["**60 RPM Rate Limit**", "55 RPM client bucket + 15 RPM session limiter + `2/4/8s` exponential backoff", "Smooth burst absorption; graceful retries on transient VM hiccups."],
            ["**8,192 Context / <=1024 Out**", "`enforce_context_budget()` trims history/context; `enable_thinking: False`", "0 context overflows (`F5=0`); 3x faster Qwen3-8B replies without `<think>` bloat."],
            ["**512-Token Embedding Cap**", "Section-aware chunker enforces `<=440` tokens + `Batch=16` VM02 ingestion", "6,059 intact chunks (`0 > 512`); exclusions never severed from scheme titles."],
            ["**Latency & Cold Start**", "Startup background CrossEncoder pre-warm + Two-Tier Exact & Semantic (`>=0.96`) Cache", "Warm retrieval `~1.6s` (down from 40s cold); cached repeat queries `<50 ms` & `0` tokens!"],
            ["**Vernacular Voice & Drift**", "Canonical English-pivot retrieval + server `POST /api/voice/tts` (`gTTS` + LRU cache)", "100% EN/HI/TA scheme consistency; instant 6-lang audio on any OS/browser."],
        ],
        col_widths_in=[1.65, 3.25, 2.50],
        font_size=8.3,
    )

    add_h2(doc, "Direct Mapping to IIT Kharagpur 5-Module Curriculum")
    add_styled_table(
        doc,
        headers=["Module", "Syllabus Topics Used", "Concrete Artifact in Repo"],
        rows=[
            ["**M1: LLM Foundations**", "Tokenization, Embeddings, Model trade-offs", "`chunker.py` (440-tok cap), `llm_client.py` (8,192 budgeter, no-think)"],
            ["**M2: Prompting & RAG**", "P1/P2/P3 prompting, Hybrid Search, RRF, Reranking, Evals", "`hybrid_retriever.py`, `prompts.py`, `R1–R4` & `P1–P3` eval reports"],
            ["**M3: Fine-Tuning vs RAG**", "Decision framework: when NOT to fine-tune", "Dynamic welfare policies served via updatable SQLite + RAG instead of LoRA"],
            ["**M4: Multimodal & Agents**", "LangGraph planning, tool use, memory, HITL, voice I/O", "`graph.py` (7 nodes), `tools.py` (5 tools + 1-shot repair), `routes_voice.py`"],
            ["**M5: Deploy & AI Safety**", "FastAPI, Docker, Caching, Observability, Red-Teaming, DPDP", "`pii.py`, `injection.py`, `cache.py`, Langfuse Trace UI, 20/20 Red-Team"],
        ],
        col_widths_in=[1.45, 2.75, 3.20],
        font_size=8.3,
    )

    # =========================================================================
    # PAGE 5: VERIFIED BENCHMARKS & EVAL FORMULAS CHEAT SHEET
    # =========================================================================
    add_h1(doc, "5. Verified Evaluation Benchmarks & Math Cheat Sheet", page_break_before=True)
    add_figure(
        doc,
        DIAG_DIR / "05_eval_benchmarks.png",
        "All 4 Live Benchmark Suites: Retrieval Ablation (R1–R4), Prompting Strategy (P1–P3), Red-Team Hardening & Agent Fault Recovery.",
        width_in=7.2,
    )
    add_styled_table(
        doc,
        headers=["Benchmark Suite", "Dataset / Scope", "Key Verified Result", "Metric Formula (Viva Cheat Sheet)"],
        rows=[
            [
                "**Retrieval Ablation** (`R1–R4`)",
                "73 golden queries across 649 Central schemes",
                "**R3 Hybrid RRF:** R@5 `95.9%`, MRR@10 `0.925`, NDCG@5 `0.933` (`31.7ms`). **R4 + Rerank:** R@5 `95.9%` + calibrated `[0..1]` gate.",
                "• **R@K** = `%` queries with gold slug in top-K\n• **MRR@10** = mean of `1 / rank_gold`\n• **NDCG@5** = `1 / log2(rank + 1)`",
            ],
            [
                "**Prompting Study** (`P1–P3`)",
                "30 stratified queries on fixed `Qwen/Qwen3-8B`",
                "**P1:** 93.3% acc, 10% cite, 66.7% halluc.\n**P2:** 96.7% acc, 100% cite, 6.7% halluc.\n**P3:** **100% acc, 100% cite, 0.0% halluc!**",
                "• **Citations** = regex `[1]` present\n• **Hallucination** = wrong verdict, uncited `₹` claim, or fabricated scheme",
            ],
            [
                "**Agent Fault Injection**",
                "15 scenarios (JSON faults, HITL bypass, 503/bad_json)",
                "**15/15 (100%):** 5/5 JSON repair, 4/4 HITL blocks, 3/3 graceful fallback to Handoff, 3/3 tool accuracy.",
                "Deterministic regex -> 1-shot LLM Pydantic ValidationError repair -> Assisted Handoff fallback.",
            ],
            [
                "**Red-Team Safety**",
                "20 attacks (injection, fraud, CAPTCHA, PII, fake scheme)",
                "Improved from **80% (16/20) -> 100% (20/20)** after hardening `injection.py` & untrusted delimiters.",
                "16/16 attacks blocked/neutralized, 3/3 PII masked (Aadhaar/PAN/IFSC), 1/1 honest fake-scheme refusal.",
            ],
        ],
        col_widths_in=[1.35, 1.45, 2.40, 2.20],
        font_size=8.1,
    )

    # =========================================================================
    # PAGE 6: 10-MINUTE LIVE DEMO PLAYBOOK & TOP 10 MENTOR VIVA Q&AS
    # =========================================================================
    add_h1(doc, "6. 10-Minute Live Demo Playbook & Top 10 Mentor Viva Q&As", page_break_before=True)
    add_h2(doc, "Live Demo Flow (One-Click Launch: `.\\start_local.ps1` -> `http://localhost:5173`)")
    add_numbered(
        doc,
        [
            "**Login & RBAC (1 min):** Show Civic Login screen + Demo Personas. Sign in as **Priya** (`priya`/`citizen123`) — notice Admin tabs (Traces & Evals) are strictly hidden!",
            "**Conversational Intelligence + Eligibility (2 min):** Greet naturally (*\"Namaste, what can you do?\"* -> zero false scheme dump), then ask a scholarship or Mumbai MRO loan query -> highlight live SSE steps, `[1]` clickable official links, Eligibility Card, and **Listen** button (server MP3 audio).",
            "**Multilingual Consistency & Voice (2 min):** Switch language to **Hindi / Tamil / Marathi**, ask the same question -> prove identical scheme retrieval + click **Listen** for crystal-clear Indian audio.",
            "**HITL Grievance + Live Email Action (2.5 min):** Click **Raise Grievance** -> pick *PM-KISAN* (auto-maps `MOAFW`), enter a test email -> show HITL review modal -> click **Confirm & Submit** -> show Registration ID + **live Gmail confirmation email** + Assisted Handoff Packet!",
            "**Admin Langfuse Trace & Eval Console (2.5 min):** Sign out -> log in as **Admin** (`admin`/`admin123`) -> open **Traces & Evals** -> inspect `SPN-01..SPN-09` waterfall, download a structured **JSON/Markdown trace**, and show the live `R1–R4` / `P1–P3` / Red-Team scorecards!",
        ],
        size=9.1,
    )

    add_h2(doc, "Top 10 Anticipated Mentor Viva Questions & Crisp Answers")
    add_styled_table(
        doc,
        headers=["#", "Likely Mentor Question", "Crisp, High-Confidence Team Answer"],
        rows=[
            ["1", "Why didn't you fine-tune Qwen3-8B on the 649 schemes?", "Policy rules & budgets change often; fine-tuning bakes stale facts and causes hallucinations. Agentic RAG + SQLite rules update in minutes with 0% hallucination."],
            ["2", "Why Hybrid Search instead of pure Dense vectors?", "Dense (`bge-small`) misses exact acronyms like `PMEGP`/`CSSS`, while BM25 misses paraphrases like *'nuts & bolts'* -> MSME. RRF lifts Recall@5 to **95.9%**."],
            ["3", "Why keep Cross-Encoder (`R4`) if `R3` had slightly higher MRR?", "`R4` keeps 95.9% R@5 and gives calibrated `[0..1]` probabilities needed to catch fake schemes (`0.280`) and trigger `.gov.in` web fallback."],
            ["4", "How do you prevent `Qwen3-8B` from exceeding 8,192 tokens or emitting broken JSON?", "`enforce_context_budget()` trims history/context before every call, `enable_thinking: False` stops `<think>` bloat, and `parse_and_repair_json` recovers 5/5 malformed JSONs."],
            ["5", "How do you guarantee compliance with the 1-active-request VM rule?", "Single-worker Uvicorn (`--workers 1`) + process-wide `asyncio.Semaphore(1)` + 55 RPM bucket + 2/4/8s backoff + Two-Tier Cache (`<50ms` repeat hits)."],
            ["6", "What stops prompt injection inside retrieved web snippets?", "InputGuardrail blocks direct attacks; retrieved corpus/web chunks are sanitized and wrapped inside `<RETRIEVED_EVIDENCE_UNTRUSTED>` data-only tags."],
            ["7", "Can the agent submit a CPGRAMS grievance by itself?", "**Never.** Code-level HITL gate blocks `submit_or_track_grievance(action='submit')` unless `user_confirmed=True` comes from the human UI confirmation click."],
            ["8", "How do you handle Aadhaar/PAN privacy (DPDP Act 2023)?", "Regex masker redacts Aadhaar (`XXXX-XXXX-1234`), PAN, phone, bank & IFSC *before* LLM calls or SQLite writes; `DELETE /api/sessions` erases user data on demand."],
            ["9", "How do you ensure English, Hindi & Tamil give the same answer?", "English-pivot retrieval runs `search_schemes` strictly on `query_en`, then localizes the Critic-verified answer back to the user's language."],
            ["10", "What are the honest limitations & next steps for production?", "Currently 649 Central schemes (add ~2,500 State schemes), CPGRAMS is a Sandbox + Handoff (integrate API Setu), add Bhashini ULCA + WhatsApp channel + vLLM cluster."],
        ],
        col_widths_in=[0.30, 2.55, 4.55],
        font_size=8.1,
    )

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(OUT_PATH))
    return OUT_PATH


if __name__ == "__main__":
    p = build_summary_sheet()
    print(f"[OK] Built Team Summary Sheet: {p} ({p.stat().st_size:,} bytes)")
