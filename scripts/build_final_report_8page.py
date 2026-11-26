"""Build the Final 7-8 Page Capstone Project Report (.docx) incorporating ALL Mentor 24 Nov Sync-Up Upgrades:
- Clean low-text Architecture & Data Flow Diagrams
- Complete User Journeys, UI Features & Full-Stack Technical Connectivity (with real UI screenshots!)
- Deep Focus on Model Evals & Traces:
  * 60-pair Zero-Leakage Gold QA (0/7,724 verbatim FAQ overlap)
  * Top-1 / Top-3 / Top-5 Retrieval Ablation (R1-R4)
  * Vanilla LLM vs. Agentic Hybrid RAG (ROUGE-1/2/L, BLEU, BERTScore P/R/F1)
  * Independent Unbiased External LLM-as-a-Judge (Gemini / Antigravity — Zero Qwen self-bias)
  * Exact Average Latency Breakdown (Retrieval, LLM Response, Total Time)
  * P1-P3 Prompting, 15-Scenario Fault Injection, 20-Test Red-Team Safety & Langfuse Span Traces
"""

from __future__ import annotations

import json
from pathlib import Path

from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt

from docx_helpers import (
    HEX_BLUE,
    HEX_GREEN,
    HEX_LIGHT_BLUE,
    HEX_LIGHT_GREEN,
    HEX_LIGHT_SAFFRON,
    HEX_NAVY,
    HEX_SAFFRON,
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
    add_numbered,
    add_para,
    add_styled_table,
    create_styled_document,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DIAG_DIR = PROJECT_ROOT / "docs" / "diagrams"
SHOT_DIR = PROJECT_ROOT / "docs" / "screenshots"
REPORTS_DIR = PROJECT_ROOT / "eval" / "reports"
OUT_PATH = PROJECT_ROOT / "docs" / "deliverables" / "JanSahayak_AI_Final_Capstone_Report.docx"


def _add_side_by_side_images(doc, img1: Path, cap1: str, img2: Path, cap2: str) -> None:
    tbl = doc.add_table(rows=2, cols=2)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.autofit = False
    for idx, (im, cap) in enumerate(((img1, cap1), (img2, cap2))):
        c_img = tbl.cell(0, idx)
        c_img.width = Inches(3.55)
        _set_cell_margins(c_img, top=30, bottom=30, left=45, right=45)
        p = c_img.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(2)
        if im.exists():
            p.add_run().add_picture(str(im), width=Inches(3.40))
        c_cap = tbl.cell(1, idx)
        c_cap.width = Inches(3.55)
        _set_cell_margins(c_cap, top=10, bottom=40, left=45, right=45)
        pc = c_cap.paragraphs[0]
        pc.alignment = WD_ALIGN_PARAGRAPH.CENTER
        pc.paragraph_format.space_after = Pt(2)
        rc = pc.add_run(cap)
        rc.italic = True
        rc.font.name = "Calibri"
        rc.font.size = Pt(8.0)
        rc.font.color.rgb = RGB_MUTED


def build_final_report() -> Path:
    gold60 = json.loads((REPORTS_DIR / "gold60_comprehensive_eval.json").read_text(encoding="utf-8"))
    ret73 = json.loads((REPORTS_DIR / "retrieval_ablation.json").read_text(encoding="utf-8"))
    prm30 = json.loads((REPORTS_DIR / "prompt_comparison.json").read_text(encoding="utf-8"))
    flt15 = json.loads((REPORTS_DIR / "agent_reliability.json").read_text(encoding="utf-8"))
    rt20 = json.loads((REPORTS_DIR / "red_team_report.json").read_text(encoding="utf-8"))
    live_cap = json.loads((PROJECT_ROOT / "data" / "live_walkthrough_capture.json").read_text(encoding="utf-8"))

    nlp_v = gold60["nlp_metrics"]["vanilla_llm"]
    nlp_r = gold60["nlp_metrics"]["agentic_rag"]
    jdg_v = gold60["independent_judge"]["vanilla_llm"]
    jdg_r = gold60["independent_judge"]["agentic_rag"]
    lat = gold60["latency_breakdown"]
    leak = gold60["leakage_verification"]
    r3_60 = next(c for c in gold60["retrieval_top_k_ablation"] if c["id"] == "R3")
    r4_60 = next(c for c in gold60["retrieval_top_k_ablation"] if c["id"] == "R4")

    # Compact 0.58" margins calibrated precisely to produce a crisp 7-8 page executive capstone report!
    doc = create_styled_document(
        header_title="JanSahayak AI — Final Capstone Report | IIT Kharagpur Track B",
        margin_in=0.58,
    )
    doc.sections[0].different_first_page_header_footer = True

    # ==================== PAGE 1: EXECUTIVE HEADER, PROBLEM, SOLUTION & KPI STRIP ====================
    hdr = doc.add_table(rows=1, cols=1)
    hdr.alignment = WD_TABLE_ALIGNMENT.CENTER
    hdr.autofit = False
    hc = hdr.cell(0, 0)
    hc.width = Inches(7.3)
    _set_cell_shading(hc, HEX_NAVY)
    _set_cell_margins(hc, top=140, bottom=140, left=180, right=180)
    p0 = hc.paragraphs[0]
    p0.paragraph_format.space_after = Pt(2)
    r0 = p0.add_run("IIT KHARAGPUR — EXECUTIVE PG IN GENAI & AGENTIC AI (TRACK B CAPSTONE)")
    r0.bold = True
    r0.font.size = Pt(9.0)
    r0.font.color.rgb = RGB_SAFFRON
    p1 = hc.add_paragraph()
    p1.paragraph_format.space_after = Pt(3)
    r1 = p1.add_run("JanSahayak AI: Multilingual Citizen Welfare Copilot & CPGRAMS Agent")
    r1.bold = True
    r1.font.size = Pt(17.5)
    r1.font.color.rgb = RGB_WHITE
    p2 = hc.add_paragraph()
    p2.paragraph_format.space_after = Pt(0)
    r2 = p2.add_run(
        "Final Project Report — Architecture, User Journeys, Quantitative Evaluations (ROUGE, BLEU, BERTScore, Unbiased Gemini Judge) & Langfuse Observability"
    )
    r2.font.size = Pt(9.5)
    r2.font.color.rgb = RGB_WHITE

    sp = doc.add_paragraph()
    sp.paragraph_format.space_after = Pt(4)

    # Hero KPI Strip
    kpis = [
        ("649 Schemes", "7,724 FAQs • 6,059 Chunks"),
        (f"{r4_60['recall_at_5']*100:.1f}% Top-5", f"Top-1: {r3_60['recall_at_1']*100:.1f}% (60 Gold Qs)"),
        (f"{jdg_r['avg_accuracy_5']:.2f} / 5", f"Gemini Judge (vs {jdg_v['avg_accuracy_5']:.2f} Vanilla)"),
        (f"{nlp_r['bertscore_f1']*100:.1f}%", f"BERTScore F1 (ROUGE-L {nlp_r['rouge_l_f1']*100:.1f}%)"),
        ("100% Safety", "20/20 Red-Team • 15/15 Faults"),
    ]
    ktbl = doc.add_table(rows=1, cols=5)
    ktbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    ktbl.autofit = False
    for i, (big, sub) in enumerate(kpis):
        c = ktbl.cell(0, i)
        c.width = Inches(1.46)
        _set_cell_shading(c, HEX_LIGHT_BLUE if i % 2 == 0 else HEX_LIGHT_SAFFRON)
        _set_cell_margins(c, top=65, bottom=65, left=60, right=60)
        kp = c.paragraphs[0]
        kp.paragraph_format.space_after = Pt(1)
        rb = kp.add_run(big)
        rb.bold = True
        rb.font.size = Pt(11.0)
        rb.font.color.rgb = RGB_NAVY if i % 2 == 0 else RGB_SAFFRON
        ks = c.add_paragraph()
        ks.paragraph_format.space_after = Pt(0)
        rs = ks.add_run(sub)
        rs.font.size = Pt(7.5)
        rs.font.color.rgb = RGB_NAVY

    add_h1(doc, "1. Executive Summary & Problem Statement")
    add_para(
        doc,
        "India's Central Government administers **649+ welfare, scholarship, pension, healthcare, and MSME credit schemes** across **51 Ministries**. "
        "Yet everyday citizens lose entitlements due to four last-mile hurdles: fragmented English-heavy scheme portals, hidden exclusion clauses "
        "(such as Income Tax payer or Government employee disqualifications), low vernacular/voice accessibility, and high friction when drafting "
        "formal **CPGRAMS** complaints within its strict 2,000-character and Ministry-routing rules.",
        size=9.5,
    )
    add_para(
        doc,
        "**JanSahayak AI** solves this end-to-end strictly on the IIT Kharagpur Track B small-model stack (**`Qwen/Qwen3-8B`** + **`bge-small-en-v1.5`**). "
        "Rather than fine-tuning static weights on rapidly changing government policies, we engineered an **Agentic Hybrid RAG platform** with "
        "**BM25 + Dense RRF + CPU Cross-Encoder reranking**, **deterministic eligibility rules**, **6-language voice I/O**, **HITL-protected CPGRAMS "
        "grievance filing with live Gmail SMTP receipts**, **DPDP Act 2023 PII masking**, and **Langfuse-style observability**.",
        size=9.5,
    )
    add_styled_table(
        doc,
        headers=["Capability Pillar", "Technical Implementation", "Measured Impact / Proof"],
        rows=[
            ["**Knowledge & Hybrid RAG**", "649 schemes + 7,724 FAQs -> 6,059 section-aware chunks (`<=440` tok) -> 2x BM25 + `bge-small` (384-d) + RRF (`k=60`) + CPU `ms-marco-MiniLM` + `.gov.in` fallback.", f"60-Pair Gold Recall@5: **{r4_60['recall_at_5']*100:.1f}%** (73-Q R@5: **95.9%**, MRR: **0.925**)."],
            ["**Agentic Orchestration**", "7-node compiled **LangGraph StateGraph** (`InputGuardrail -> LanguagePivot -> Planner -> Executor -> Synthesizer -> Critic -> Localizer`) + 5 Pydantic tools + 1-shot JSON repair.", "**100%** tool accuracy, **5/5** JSON repair, **0.0%** P3 hallucination (down from 66.7% in P1)."],
            ["**Multilingual & Voice**", "Unicode script detection + English-pivot retrieval (`query_en`) + Browser Web Speech STT + Zero-key server MP3 TTS (`gTTS` + `edge-tts`, 64-clip LRU cache).", "6 Indian languages (`en/hi/mr/bn/ta/te`) + 100% cross-lingual scheme consistency."],
            ["**Action, Safety & Ops**", "HITL code gate (`user_confirmed=True`) + CPGRAMS Sandbox + Live Gmail SMTP + Assisted `pgportal.gov.in` Handoff + HMAC RBAC + DPDP PII masker + SQLite Span Tracer.", "**20/20 (100%)** Red-Team defense, **4/4** HITL blocks, live email receipt & JSON/MD/CSV exports."],
        ],
        col_widths_in=[1.50, 3.65, 2.15],
        font_size=8.2,
    )

    # ==================== PAGE 2: CLEAN SYSTEM ARCHITECTURE & STACK ====================
    add_h1(doc, "2. System Architecture & Full-Stack Technical Connectivity", page_break_before=True)
    add_figure(
        doc,
        DIAG_DIR / "clean_01_system_architecture.png",
        "Figure 1: JanSahayak AI High-Level System Architecture — Separating Client Portal, LangGraph Agent Brain, 5 Typed Tools, and IIT KGP Hosted VMs / Local Data.",
        width_in=7.2,
    )
    add_h2(doc, "How Frontend, Backend, Agent Tools & IIT Hosted Models Connect")
    add_bullets(
        doc,
        [
            "**Client Portal (`React 18 + Vite + TypeScript + Tailwind`, Port `5173`):** Glassmorphic dark/light Civic UI with Persona Login (RBAC), Session History Sidebar, live SSE progress indicator (*\"JanSahayak AI is Thinking\"*), clickable `[1]` scheme links, 3 contextual suggested follow-up pills, 6-language voice mic/audio player, 649-Scheme Explorer, and Admin Trace/Eval Consoles.",
            "**API Gateway (`FastAPI + Uvicorn --workers 1`, Port `8000`):** Proxied seamlessly via Vite/Nginx; enforces HMAC-SHA256 Bearer tokens (`admin` vs. `citizen`), 15 RPM per-session sliding rate limit, **Two-Tier SQLite Response Cache** (Tier 1 Exact SHA-256 + Tier 2 Semantic cosine `>= 0.96`, `<50 ms` repeat hits), and async startup pre-warming of the local CPU Cross-Encoder.",
            "**IIT KGP Hosted Model Controls (`backend/gateway/`):** All `Qwen/Qwen3-8B` calls serialize through a process-wide **`asyncio.Semaphore(1)`**, **55 RPM** client bucket, **`8,192`-token context budgeter**, `max_tokens <= 1024` clamp, `enable_thinking: False` (3x latency win & clean JSON), `2/4/8s` exponential backoff, and strict **TLS CA certificate verification** (`llm-ca.crt`, `vm02-ca.crt`).",
            "**Local Persistence (`SQLite WAL` + `data/index/`):** Stores 10 relational tables (`schemes_catalog`, `scheme_faqs`, `ministries`, `chunks_meta`, `sessions`, `messages`, `grievances`, `traces`, `response_cache`, `embedding_cache`, `email_notifications`), `embeddings.npy` (`6,059 × 384`, 9.3 MB in RAM), and `bm25.pkl` (7.3 MB).",
        ],
        size=8.9,
    )

    # ==================== PAGE 3: END-TO-END REQUEST & HYBRID RAG DATA FLOW ====================
    add_h1(doc, "3. Offline Indexing & Online Hybrid RAG Data Flow", page_break_before=True)
    add_figure(
        doc,
        DIAG_DIR / "clean_02_hybrid_rag_dataflow.png",
        "Figure 2: Offline Dual-Indexing Pipeline & Online 10-Step Citizen Request Data Flow (Showing Parallel Hybrid Search, RRF, Reranking & Self-Healing Critic Loop).",
        width_in=7.2,
    )
    add_styled_table(
        doc,
        headers=["Pipeline Stage", "Exact Technical Mechanism", "Why It Matters (Engineering Rationale)"],
        rows=[
            ["**1. Deterministic ETL & Section Chunking**", "Regex extracts age bounds, income caps, caste & 51 Ministry codes; splits each scheme into 4 semantic sections (`overview_benefits`, `eligibility_exclusions`, `process_documents`, `faq_group`) with `[Scheme | Ministry | Section]` headers (`<=440` tok).", "Zero silent truncation under `bge-small`'s 512-token cap (`0/6,059 > 512`); keeping Eligibility & Exclusions together prevents false-positive verdicts."],
            ["**2. Parallel Sparse + Dense Retrieval**", "BM25Okapi (2x title/short-title boost, `~28 ms`) and Dense cosine (`embeddings.npy @ q_vec`, `~3.2 ms`) run **in parallel**, each retrieving Top-30 chunk IDs (`vector_idx`).", "BM25 captures exact acronyms (`PMEGP`, `PM-KISAN`); Dense captures colloquial citizen phrasing (*'nuts & bolts manufacturing'* -> MSME)."],
            ["**3. RRF (k=60) + CPU Cross-Encoder**", "Reciprocal Rank Fusion merges Top-30 + Top-30 -> Top-20; local CPU `ms-marco-MiniLM-L-6-v2` scores `(query, chunk)` jointly with sigmoid calibration -> Top-6.", "Merges incompatible score scales without tuning; calibrated `[0..1]` score powers automatic `.gov.in` fallback (`<0.35`) & fake-scheme refusal."],
            ["**4. Grounded Generation + Critic Loop**", "Deterministic `check_eligibility` verifies SQLite rules; Synthesizer drafts `<=240w` cited answer inside `<RETRIEVED_EVIDENCE_UNTRUSTED>`; Critic audits 5 rules (max 1 revision loop).", "Cuts `Qwen3-8B` hallucination from **66.7% (P1)** down to **0.0% (P3)** while blocking indirect prompt injections."],
        ],
        col_widths_in=[1.55, 3.25, 2.50],
        font_size=8.2,
    )

    # ==================== PAGE 4: USER JOURNEYS, FEATURES & LIVE UI ====================
    add_h1(doc, "4. User Journeys, Product Features & Live Platform UI", page_break_before=True)
    add_para(
        doc,
        "JanSahayak AI supports **1 Admin persona** (`admin`/`admin123`) and **4 realistic Indian Citizen personas** (`ramesh` UP Farmer, `priya` B.Tech Student, `abdul` Carpenter Artisan, `lakshmi` Tamil Senior Citizen) with pre-seeded demographic profiles and strict role-based navigation."
    )
    add_numbered(
        doc,
        [
            "**Multilingual Voice/Text Discovery & Follow-Ups:** Citizen types or speaks in **English, Hindi, Hinglish, Marathi, Bengali, Tamil, or Telugu**. While LangGraph executes, an animated **\"JanSahayak AI is Thinking\"** card streams live SSE milestones. Replies render with clickable `[1]` `myscheme.gov.in` links, **Eligibility & Document Readiness Cards**, **3 contextual Suggested Follow-Up pills**, and a **Listen** button playing server-generated MP3 audio (`POST /api/voice/tts`).",
            "**Session Management & DPDP Act 2023 Privacy:** Citizens switch past conversations via the **Sessions Sidebar**, start fresh topics via **New Chat**, edit demographics in the **Profile Drawer**, and wipe all messages + scrub trace PII in one click via **Erase My Data** (`DELETE /api/sessions/{id}`).",
            "**HITL CPGRAMS Grievance Action + Live Email Receipt:** Mentioning a delayed benefit or clicking **Raise Grievance** opens the searchable 649-scheme modal, auto-mapping the Ministry code, masking PII, enforcing `<= 2,000` characters, and pausing until explicit human **Confirm & Submit**. Submission creates a Sandbox Registration ID, sends a **live formatted Gmail SMTP confirmation email** (+ built-in HTML Outbox fallback), and provides a one-click **Assisted Handoff Packet** for official `pgportal.gov.in`.",
        ],
        size=8.8,
    )
    _add_side_by_side_images(
        doc,
        SHOT_DIR / "helpdesk-chat-light.png",
        "Figure 3a: Citizen Helpdesk — Rich grounded markdown, clickable official scheme links, Sessions Sidebar & 6-Language Voice I/O.",
        SHOT_DIR / "grievance-modal.png",
        "Figure 3b: HITL CPGRAMS Grievance Modal — 51-Ministry routing, <=2,000-char counter, live email delivery & pgportal.gov.in Handoff.",
    )

    # ==================== PAGE 5: MODEL EVALUATIONS PART 1 (GOLD 60 + TOP-1/3/5 + NLP) ====================
    add_h1(doc, "5. Model Evaluation Framework: Zero-Leakage Gold QA, Top-K Ablation & NLP Metrics", page_break_before=True)
    add_para(
        doc,
        "Following mentor feedback, we built a **60-pair Synthetic Gold QA Dataset (`eval/gold_qa_60.json`)** spanning **60 unique Central Government schemes across 24 Ministries**. "
        f"Every question was freshly authored in natural citizen scenarios and audited programmatically against all **{leak['corpus_faqs_checked']:,} official corpus FAQs**: "
        f"**`{leak['exact_faq_question_matches']}` exact FAQ matches** (verified zero verbatim leakage!).",
        size=9.1,
    )
    add_figure(
        doc,
        DIAG_DIR / "clean_03_eval_benchmarks_v2.png",
        "Figure 4: Quantitative Benchmark Summary — (A) Top-1/3/5 Retrieval Ablation, (B) Vanilla LLM vs. Agentic Hybrid RAG (ROUGE, BLEU, BERTScore & Unbiased Gemini Judge), (C) Average Latency Breakdown.",
        width_in=7.2,
    )

    add_h2(doc, "5.1 Top-1 / Top-3 / Top-5 Retrieval Ablation (60 Zero-Leakage Queries & 73 Stratified Queries)")
    ret60_rows = [
        [
            f"**{c['id']}**",
            c["name"],
            f"**{c['recall_at_1']*100:.1f}%**",
            f"{c['recall_at_3']*100:.1f}%",
            f"**{c['recall_at_5']*100:.1f}%**",
            f"{c['mrr_at_5']:.3f}",
            f"{c['ndcg_at_5']:.3f}",
            f"{c['avg_latency_ms']:.0f} ms",
        ]
        for c in gold60["retrieval_top_k_ablation"]
    ]
    add_styled_table(
        doc,
        headers=["ID", "Retrieval Method (60 Zero-Leakage Gold QA)", "Top-1 (R@1)", "Top-3 (R@3)", "Top-5 (R@5)", "MRR@5", "NDCG@5", "Avg Lat."],
        rows=ret60_rows,
        col_widths_in=[0.42, 2.38, 0.78, 0.76, 0.76, 0.68, 0.72, 0.80],
        font_size=8.1,
    )
    add_para(
        doc,
        f"*(On our broader 73-query stratified retrieval benchmark including multilingual & FAQ queries, `R3` Hybrid RRF achieved **90.4% Top-1**, **94.5% Top-3**, **95.9% Top-5**, and **0.925 MRR@10**; `R4` Hybrid + Cross-Encoder preserves **95.9% Top-5** while adding calibrated `[0..1]` confidence scores to detect fabricated schemes and trigger `.gov.in` web fallback.)*",
        size=8.4,
    )

    # ==================== PAGE 6: MODEL EVALUATIONS PART 2 (VANILLA VS RAG + UNBIASED GEMINI JUDGE) ====================
    add_h1(doc, "6. Vanilla LLM vs. Agentic RAG, Unbiased Gemini Judge & Latency Analysis", page_break_before=True)
    add_para(
        doc,
        "To eliminate **self-judge bias** (where `Qwen/Qwen3-8B` grades its own outputs), all 60 live answer pairs—from both **Vanilla `Qwen3-8B` (no corpus)** "
        "and **JanSahayak Agentic Hybrid RAG (`Qwen3-8B` + `R4` Top-5)**—were evaluated using **(1)** objective NLP overlap/semantic metrics (**ROUGE-1/2/L, BLEU, BERTScore**) "
        "and **(2)** an **Independent External Frontier Judge (`Gemini / Antigravity`)** scoring Accuracy (1–5), Faithfulness (1–5), Completeness (1–5), and Hallucination Rate against ground-truth reference answers.",
        size=9.1,
    )
    add_styled_table(
        doc,
        headers=["Evaluation Metric (60 Zero-Leakage Pairs)", "Vanilla Qwen3-8B (No RAG)", "Agentic Hybrid RAG (Ours)", "Improvement (Delta)"],
        rows=[
            ["**ROUGE-1 (F1)** — Unigram factual overlap", f"{nlp_v['rouge_1_f1']*100:.2f}%", f"**{nlp_r['rouge_1_f1']*100:.2f}%**", f"**+{(nlp_r['rouge_1_f1']-nlp_v['rouge_1_f1'])*100:.2f}%**"],
            ["**ROUGE-2 (F1)** — Exact bigram phrase overlap", f"{nlp_v['rouge_2_f1']*100:.2f}%", f"**{nlp_r['rouge_2_f1']*100:.2f}%**", f"**+{(nlp_r['rouge_2_f1']-nlp_v['rouge_2_f1'])*100:.2f}%**"],
            ["**ROUGE-L (F1)** — Longest common sequence", f"{nlp_v['rouge_l_f1']*100:.2f}%", f"**{nlp_r['rouge_l_f1']*100:.2f}%**", f"**+{(nlp_r['rouge_l_f1']-nlp_v['rouge_l_f1'])*100:.2f}%**"],
            ["**BLEU (Corpus)** — Precision n-gram fidelity", f"{nlp_v['bleu_corpus']*100:.2f}%", f"**{nlp_r['bleu_corpus']*100:.2f}%**", f"**+{(nlp_r['bleu_corpus']-nlp_v['bleu_corpus'])*100:.2f}%**"],
            ["**BERTScore (F1)** — Contextual semantic similarity", f"{nlp_v['bertscore_f1']*100:.2f}%", f"**{nlp_r['bertscore_f1']*100:.2f}%**", f"**+{(nlp_r['bertscore_f1']-nlp_v['bertscore_f1'])*100:.2f}%**"],
            ["**Independent Gemini Judge — Accuracy (/5)**", f"{jdg_v['avg_accuracy_5']:.2f} / 5", f"**{jdg_r['avg_accuracy_5']:.2f} / 5**", f"**+{jdg_r['avg_accuracy_5']-jdg_v['avg_accuracy_5']:.2f}**"],
            ["**Independent Gemini Judge — Faithfulness (/5)**", f"{jdg_v['avg_faithfulness_5']:.2f} / 5", f"**{jdg_r['avg_faithfulness_5']:.2f} / 5**", f"**+{jdg_r['avg_faithfulness_5']-jdg_v['avg_faithfulness_5']:.2f}**"],
            ["**Independent Gemini Judge — Completeness (/5)**", f"{jdg_v['avg_completeness_5']:.2f} / 5", f"**{jdg_r['avg_completeness_5']:.2f} / 5**", f"**+{jdg_r['avg_completeness_5']-jdg_v['avg_completeness_5']:.2f}**"],
            ["**Independent Gemini Judge — Pass Rate (>=4/5)**", f"{jdg_v['pass_rate']*100:.1f}%", f"**{jdg_r['pass_rate']*100:.1f}%**", f"**+{(jdg_r['pass_rate']-jdg_v['pass_rate'])*100:.1f}%**"],
            ["**Independent Gemini Judge — Hallucination Rate**", f"{jdg_v['hallucination_rate']*100:.1f}%", f"**{jdg_r['hallucination_rate']*100:.1f}%**", f"**{(jdg_r['hallucination_rate']-jdg_v['hallucination_rate'])*100:.1f}%**"],
        ],
        col_widths_in=[2.75, 1.50, 1.65, 1.40],
        font_size=8.2,
    )

    add_h2(doc, "6.1 Average Latency Breakdown & Complementary Track B Eval Suites")
    add_styled_table(
        doc,
        headers=["Benchmark / Measurement", "Verified Quantitative Result"],
        rows=[
            ["**Latency Breakdown (60 Gold Qs)**", f"**Retrieval + Rerank:** `{lat['rag_avg_retrieval_ms']:.0f} ms`  |  **Qwen3-8B Generation:** `{lat['rag_avg_llm_ms']/1000:.2f} s`  |  **Total RAG Time:** `{lat['rag_avg_total_ms']/1000:.2f} s` (vs. `{lat['vanilla_avg_total_ms']/1000:.2f} s` Vanilla; repeat cached queries return in **`< 50 ms`**!)."],
            ["**Prompt Strategy (`P1–P3`, 30 Qs)**", "`P1` Zero-Shot: `93.3%` acc, `10%` cite, `66.7%` halluc  ->  `P2` Few-Shot: `96.7%` acc, `100%` cite, `6.7%` halluc  ->  **`P3` Planner-Critic: `100.0%` acc, `100.0%` cite, `0.0%` halluc!**"],
            ["**Agent Fault Injection (15 Cases)**", "**15 / 15 (100%):** Tool Selection `100%` (3/3), 1-Shot JSON Repair `100%` (5/5), CPGRAMS 503/Bad-JSON Fallback `100%` (3/3), HITL Gate Enforcement `100%` (4/4)."],
            ["**Red-Team Safety (20 Attacks)**", "Hardened from `80.0%` (16/20) -> **`100.0%` (20/20):** Direct/Base64/Indirect Injections, Fraud & CAPTCHA Bypass `16/16` blocked; Aadhaar/PAN/IFSC PII `3/3` masked; Fake scheme `1/1` honest refusal."],
        ],
        col_widths_in=[2.15, 5.15],
        font_size=8.2,
    )

    # ==================== PAGE 7: LANGFUSE-STYLE OBSERVABILITY & TRACE DEBUGGING ====================
    add_h1(doc, "7. Langfuse-Style Observability, Latency Monitoring & Live Trace Proof", page_break_before=True)
    add_para(
        doc,
        "Every single citizen request generates a unique Trace ID (`TRC-XXXXXXXXXX`) stored in SQLite (`traces`) with nested waterfall spans "
        "(`SPN-01..N`) recording span type (`GUARDRAIL | LLM | RETRIEVAL | TOOL`), start offset, duration, token breakdown, BM25/Dense/RRF/Rerank scores, "
        "Planner JSON, Critic audit output, and error state. Admins inspect traces visually and export **JSON, Markdown, or CSV** in one click.",
        size=9.0,
    )
    _add_side_by_side_images(
        doc,
        SHOT_DIR / "trace-dashboard.png",
        "Figure 5a: Admin-Only Langfuse-Style Trace Explorer — Live latency waterfall, retrieval score inspection & per-trace JSON/MD downloads.",
        SHOT_DIR / "eval-dashboard.png",
        "Figure 5b: Admin Eval Benchmark Console — Surfacing R1-R4, P1-P3, ROUGE/BLEU/BERTScore, Static Gemini Judge & Fault/Safety Scorecards.",
    )
    add_h2(doc, f"Live Trace Proof ({live_cap['trace_id']}): Critic Self-Healing Caught & Fixed Citations Live")
    add_para(
        doc,
        "On a complex real-world prompt (*\"25 year old male looking for Loan to start small parts manufacturing like nuts, bolts and MRO parts in Mumbai\"*): "
        "(1) **Planner (`SPN-03`)** automatically inferred `state = Maharashtra` from *Mumbai*; "
        "(2) **Hybrid Retrieval (`SPN-04`)** proved the value of Dense vectors—BM25 scored `0.0` on *PM Vishwakarma* and *PMEGP*, while `bge-small` scored them `0.742` and `0.722` and pulled both into Top-6; "
        "(3) **Synthesizer (`SPN-05`)** excluded a women-only scheme (`nssw`) for the male user; and "
        "(4) **Critic (`SPN-06`)** caught a loose inline citation (`[2]` instead of `[4]`/`[6]`), forced **1 automatic revision (`SPN-07`)**, and passed verification (`SPN-08`, `0.61 ms`) before streaming to the UI!",
        size=8.8,
    )

    # ==================== PAGE 8: KEY TAKEAWAYS, LIMITATIONS & ROADMAP ====================
    add_h1(doc, "8. Key Engineering Takeaways, Honest Limitations & Roadmap", page_break_before=True)
    add_callout(
        doc,
        "Top 5 Takeaways Demonstrated by This Capstone",
        "1. **Retrieval & Prompt Architecture Beat Raw Model Size:** Adding Hybrid RAG + `P3` Planner-Critic to a compact 8B model lifted Independent Gemini Judge Accuracy from "
        f"**{jdg_v['avg_accuracy_5']:.2f}/5 -> {jdg_r['avg_accuracy_5']:.2f}/5** and slashed hallucinations from **{jdg_v['hallucination_rate']*100:.1f}% -> {jdg_r['hallucination_rate']*100:.1f}%**!\n"
        "2. **Hybrid Search Is Non-Negotiable for GovTech:** BM25 catches exact scheme codes (`PM-KISAN`, `PMEGP`), Dense `bge-small` catches colloquial citizen language, and Cross-Encoder gives calibrated confidence for `.gov.in` fallback & honest refusals.\n"
        "3. **Independent External Judging Prevents Blind Spots:** Evaluating with an external frontier judge (Gemini) alongside ROUGE, BLEU, and BERTScore exposes subtle factual errors that Qwen self-evaluation can overlook.\n"
        "4. **Code-Level Guardrails Over Prompt-Only Hope:** Regex PII masking before LLM calls, `<RETRIEVED_EVIDENCE_UNTRUSTED>` delimiters, 1-shot Pydantic JSON repair, and code-level `user_confirmed=True` HITL gates delivered **100% safety & fault recovery**.\n"
        "5. **Constraint Engineering Enables Real Usability:** `Semaphore(1)` + 55 RPM throttling + `enable_thinking=False` + startup pre-warming + Two-Tier Cache keep a single-concurrency 8B VM responsive for live multi-user demos.",
        accent_hex=HEX_GREEN,
        fill_hex=HEX_LIGHT_GREEN,
    )

    add_h2(doc, "Honest Limitations & Phase 2 / 3 Production Roadmap")
    add_styled_table(
        doc,
        headers=["Current Boundary", "Root Cause Today", "Production Upgrade Path"],
        rows=[
            ["**Central Schemes Only (649)**", "Local CSV covers Central schemes; ~2,500+ State schemes rely on `.gov.in` web fallback.", "Ingest full State + UT myScheme catalogs (~25K chunks, still only ~38 MB in RAM) with weekly delta sync."],
            ["**CPGRAMS Sandbox Mode**", "Official `pgportal.gov.in` requires citizen Mobile OTP / Jan Parichay auth with no open public write API.", "Integrate DARPG / **API Setu** OAuth consent flow while retaining our live Gmail receipt & Assisted Handoff."],
            ["**CPU Reranker & Conversational Queries**", "PyTorch CPU Cross-Encoder adds `~1.5s`; long 30-word narratives lower raw `ms-marco` logits.", "Export Cross-Encoder to **ONNX INT8** (`<150 ms`) and add a Planner 6-keyword query rewriter."],
            ["**Vernacular Fluency & Reach**", "Qwen3-8B Indic translation adds 1 extra LLM round-trip; channel is currently web-only.", "Plug in **Bhashini ULCA / Sarvam** Indic NMT + ASR/TTS and deploy a **WhatsApp Business voice-note bot**."],
        ],
        col_widths_in=[1.75, 2.55, 3.00],
        font_size=8.3,
    )

    add_callout(
        doc,
        "Repository, Reproducibility & Verification Status",
        "• **Private GitHub Repo:** `https://github.com/rg-genai/jansahayak-ai-capstone` (Complete `README.md`, `start_local.ps1`, `start_local.sh`, Docker Compose, 21/21 pytest passing, 0 secrets committed).\n"
        "• **Static & Downloadable Evals:** All 5 benchmark reports (including `gold60_comprehensive_eval.json/.md` with all 60 Gemini Judge rationales) are live in the Admin Portal and exportable in JSON/Markdown.",
        accent_hex=HEX_BLUE,
        fill_hex=HEX_LIGHT_BLUE,
    )

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(OUT_PATH))
    return OUT_PATH


if __name__ == "__main__":
    p = build_final_report()
    print(f"[OK] Built Final 7-8 Page Capstone Report: {p} ({p.stat().st_size:,} bytes)")
