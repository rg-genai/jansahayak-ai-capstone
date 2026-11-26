"""Build a polished 13-Slide 16:9 Executive PowerPoint Deck (.pptx) for JanSahayak AI Capstone Presentation."""

from __future__ import annotations

import json
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches, Pt

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DIAG_DIR = PROJECT_ROOT / "docs" / "diagrams"
SHOT_DIR = PROJECT_ROOT / "docs" / "screenshots"
REPORTS_DIR = PROJECT_ROOT / "eval" / "reports"
OUT_PATH = PROJECT_ROOT / "docs" / "deliverables" / "JanSahayak_AI_Capstone_Presentation.pptx"

# Civic GovTech Executive Palette
C_NAVY = RGBColor(0x0B, 0x22, 0x39)
C_BLUE = RGBColor(0x1D, 0x4E, 0xD8)
C_SAFFRON = RGBColor(0xD9, 0x5D, 0x14)
C_GREEN = RGBColor(0x15, 0x80, 0x3D)
C_RED = RGBColor(0xB9, 0x1C, 0x1C)
C_SLATE = RGBColor(0x33, 0x41, 0x55)
C_MUTED = RGBColor(0x64, 0x74, 0x8B)
C_BG_LIGHT = RGBColor(0xF8, 0xFA, 0xFC)
C_CARD_BLUE = RGBColor(0xEF, 0xF6, 0xFF)
C_CARD_SAFFRON = RGBColor(0xFF, 0xF4, 0xEB)
C_CARD_GREEN = RGBColor(0xEC, 0xFD, 0xF5)
C_BORDER = RGBColor(0xCB, 0xD5, 0xE1)
C_WHITE = RGBColor(0xFF, 0xFF, 0xFF)


def _new_slide(prs: Presentation, title: str, subtitle: str = "", slide_num: int = 1, dark_bg: bool = False):
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # Blank 16:9
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = C_NAVY if dark_bg else C_BG_LIGHT

    if not dark_bg:
        # Top navy header bar
        bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(13.333), Inches(0.95))
        bar.fill.solid()
        bar.fill.fore_color.rgb = C_NAVY
        bar.line.fill.background()

        # Thin saffron accent stripe
        acc = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0.95), Inches(13.333), Inches(0.06))
        acc.fill.solid()
        acc.fill.fore_color.rgb = C_SAFFRON
        acc.line.fill.background()

        tb = slide.shapes.add_textbox(Inches(0.55), Inches(0.12), Inches(11.5), Inches(0.48))
        tf = tb.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        r = p.add_run()
        r.text = title
        r.font.name = "Calibri"
        r.font.size = Pt(24)
        r.font.bold = True
        r.font.color.rgb = C_WHITE

        if subtitle:
            sb = slide.shapes.add_textbox(Inches(0.55), Inches(0.57), Inches(11.5), Inches(0.32))
            stf = sb.text_frame
            stf.word_wrap = True
            sp = stf.paragraphs[0]
            sr = sp.add_run()
            sr.text = subtitle
            sr.font.name = "Calibri"
            sr.font.size = Pt(12)
            sr.font.color.rgb = RGBColor(0xFD, 0xE6, 0x8A)

        # Footer
        ft = slide.shapes.add_textbox(Inches(0.55), Inches(7.12), Inches(12.2), Inches(0.30))
        ftf = ft.text_frame
        fp = ftf.paragraphs[0]
        fp.alignment = PP_ALIGN.RIGHT
        fr = fp.add_run()
        fr.text = f"JanSahayak AI  •  IIT Kharagpur GenAI & Agentic AI Track B Capstone   |   Slide {slide_num}"
        fr.font.name = "Calibri"
        fr.font.size = Pt(9.5)
        fr.font.color.rgb = C_MUTED

    return slide


def _add_card(
    slide,
    left: float,
    top: float,
    width: float,
    height: float,
    heading: str,
    bullets: list[str],
    fill_rgb: RGBColor = C_WHITE,
    border_rgb: RGBColor = C_BORDER,
    heading_rgb: RGBColor = C_NAVY,
    body_size: float = 12.5,
):
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(left), Inches(top), Inches(width), Inches(height))
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill_rgb
    shape.line.color.rgb = border_rgb
    shape.line.width = Pt(1.25)

    tf = shape.text_frame
    tf.word_wrap = True
    tf.margin_left = Inches(0.18)
    tf.margin_right = Inches(0.16)
    tf.margin_top = Inches(0.14)
    tf.margin_bottom = Inches(0.12)

    p0 = tf.paragraphs[0]
    p0.space_after = Pt(6)
    r0 = p0.add_run()
    r0.text = heading
    r0.font.name = "Calibri"
    r0.font.size = Pt(14.5)
    r0.font.bold = True
    r0.font.color.rgb = heading_rgb

    for b in bullets:
        p = tf.add_paragraph()
        p.space_after = Pt(4.5)
        r = p.add_run()
        r.text = f"•  {b}"
        r.font.name = "Calibri"
        r.font.size = Pt(body_size)
        r.font.color.rgb = C_SLATE
    return shape


def _add_kpi_box(slide, left: float, top: float, width: float, height: float, big: str, label: str, sub: str, accent: RGBColor):
    sh = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(left), Inches(top), Inches(width), Inches(height))
    sh.fill.solid()
    sh.fill.fore_color.rgb = C_WHITE
    sh.line.color.rgb = accent
    sh.line.width = Pt(1.75)

    tf = sh.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.margin_left = Inches(0.12)
    tf.margin_right = Inches(0.12)

    p1 = tf.paragraphs[0]
    p1.alignment = PP_ALIGN.CENTER
    r1 = p1.add_run()
    r1.text = big
    r1.font.name = "Calibri"
    r1.font.size = Pt(24)
    r1.font.bold = True
    r1.font.color.rgb = accent

    p2 = tf.add_paragraph()
    p2.alignment = PP_ALIGN.CENTER
    p2.space_before = Pt(2)
    r2 = p2.add_run()
    r2.text = label
    r2.font.name = "Calibri"
    r2.font.size = Pt(11.5)
    r2.font.bold = True
    r2.font.color.rgb = C_NAVY

    p3 = tf.add_paragraph()
    p3.alignment = PP_ALIGN.CENTER
    r3 = p3.add_run()
    r3.text = sub
    r3.font.name = "Calibri"
    r3.font.size = Pt(9.5)
    r3.font.color.rgb = C_MUTED


def _add_table(slide, left: float, top: float, width: float, height: float, headers: list[str], rows: list[list[str]], font_size: float = 11.0):
    tbl_shape = slide.shapes.add_table(len(rows) + 1, len(headers), Inches(left), Inches(top), Inches(width), Inches(height))
    tbl = tbl_shape.table
    for j, h in enumerate(headers):
        cell = tbl.cell(0, j)
        cell.fill.solid()
        cell.fill.fore_color.rgb = C_NAVY
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = cell.text_frame.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER if j > 0 else PP_ALIGN.LEFT
        r = p.add_run()
        r.text = h
        r.font.name = "Calibri"
        r.font.size = Pt(font_size)
        r.font.bold = True
        r.font.color.rgb = C_WHITE

    for i, rdata in enumerate(rows):
        bg = C_WHITE if i % 2 == 0 else C_CARD_BLUE
        for j, val in enumerate(rdata):
            cell = tbl.cell(i + 1, j)
            cell.fill.solid()
            cell.fill.fore_color.rgb = bg
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            p = cell.text_frame.paragraphs[0]
            p.alignment = PP_ALIGN.CENTER if j > 0 else PP_ALIGN.LEFT
            r = p.add_run()
            r.text = str(val)
            r.font.name = "Calibri"
            r.font.size = Pt(font_size)
            if j == 0 or "Agentic" in str(val) or "P3" in str(val) or "R4" in str(val):
                r.font.bold = True
            r.font.color.rgb = C_NAVY if j == 0 else C_SLATE


def _add_pic_fit(slide, path: Path, left: float, top: float, width: float):
    if path.exists():
        slide.shapes.add_picture(str(path), Inches(left), Inches(top), width=Inches(width))


def build_ppt() -> Path:
    gold60 = json.loads((REPORTS_DIR / "gold60_comprehensive_eval.json").read_text(encoding="utf-8"))
    prm30 = json.loads((REPORTS_DIR / "prompt_comparison.json").read_text(encoding="utf-8"))
    nlp_v = gold60["nlp_metrics"]["vanilla_llm"]
    nlp_r = gold60["nlp_metrics"]["agentic_rag"]
    jdg_v = gold60["independent_judge"]["vanilla_llm"]
    jdg_r = gold60["independent_judge"]["agentic_rag"]
    lat = gold60["latency_breakdown"]
    r3_60 = next(c for c in gold60["retrieval_top_k_ablation"] if c["id"] == "R3")
    r4_60 = next(c for c in gold60["retrieval_top_k_ablation"] if c["id"] == "R4")

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    # ==================== SLIDE 1: TITLE COVER ====================
    s1 = _new_slide(prs, "", "", slide_num=1, dark_bg=True)
    # Tricolor top bar
    for idx, col in enumerate((C_SAFFRON, C_WHITE, C_GREEN)):
        b = s1.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(idx * 4.444), Inches(0), Inches(4.445), Inches(0.14))
        b.fill.solid()
        b.fill.fore_color.rgb = col
        b.line.fill.background()

    tb = s1.shapes.add_textbox(Inches(0.85), Inches(1.25), Inches(11.6), Inches(1.1))
    p = tb.text_frame.paragraphs[0]
    r = p.add_run()
    r.text = "IIT KHARAGPUR  •  EXECUTIVE PG IN GENAI & AGENTIC AI  •  TRACK B CAPSTONE"
    r.font.name = "Calibri"
    r.font.size = Pt(14)
    r.font.bold = True
    r.font.color.rgb = RGBColor(0xFD, 0xE6, 0x8A)

    tb2 = s1.shapes.add_textbox(Inches(0.85), Inches(1.85), Inches(11.6), Inches(2.2))
    tf2 = tb2.text_frame
    tf2.word_wrap = True
    p2 = tf2.paragraphs[0]
    r2 = p2.add_run()
    r2.text = "JanSahayak AI"
    r2.font.name = "Calibri"
    r2.font.size = Pt(52)
    r2.font.bold = True
    r2.font.color.rgb = C_WHITE

    p3 = tf2.add_paragraph()
    p3.space_before = Pt(8)
    r3 = p3.add_run()
    r3.text = "Multilingual Indian Citizen Welfare Copilot & Assisted CPGRAMS Grievance Agent"
    r3.font.name = "Calibri"
    r3.font.size = Pt(22)
    r3.font.color.rgb = RGBColor(0x93, 0xC5, 0xFD)

    p4 = tf2.add_paragraph()
    p4.space_before = Pt(16)
    r4 = p4.add_run()
    r4.text = "Agentic Hybrid RAG  •  649 Central Schemes  •  6 Indian Languages + Voice  •  Unbiased External Judge Verified"
    r4.font.name = "Calibri"
    r4.font.size = Pt(14)
    r4.font.color.rgb = RGBColor(0xCB, 0xD5, 0xE1)

    # Bottom KPI Pills on Cover
    cover_stats = [
        ("649 Schemes", "7,724 FAQs • 6,059 Chunks", C_SAFFRON),
        (f"{r4_60['recall_at_5']*100:.1f}% Top-5", "Hybrid RRF + Reranker", C_BLUE),
        (f"{jdg_r['avg_accuracy_5']:.2f} / 5", "Unbiased Gemini Judge", C_GREEN),
        ("100% Safety", "20/20 Red-Team • 15/15 Faults", C_GREEN),
    ]
    for i, (big, sub, acc) in enumerate(cover_stats):
        _add_kpi_box(s1, 0.85 + i * 2.95, 5.15, 2.72, 1.45, big, sub, "Verified Live", acc)

    # ==================== SLIDE 2: PROBLEM & SOLUTION ====================
    s2 = _new_slide(prs, "The Citizen Access Gap & Our Solution", "Why Last-Mile Welfare Discovery Demands Agentic Hybrid RAG", 2)
    _add_card(
        s2, 0.55, 1.30, 5.95, 5.45,
        "4 Systemic Citizen Friction Points",
        [
            "Fragmented Discovery: 649+ Central schemes across 51 Ministries—citizens don't know acronyms like PMEGP, PM-USP, or PM-SYM.",
            "Hidden Exclusion Clauses: Income-tax, landholding, and government-employee disqualifications sit buried in long PDFs & FAQs.",
            "Vernacular & Literacy Barrier: Official portals are English-heavy and form-driven; citizens think & speak in Hindi, Marathi, Tamil, Telugu, Bengali.",
            "Grievance Redressal Friction: Filing CPGRAMS complaints requires knowing the exact Ministry code and staying within 2,000 characters.",
        ],
        fill_rgb=C_CARD_SAFFRON, border_rgb=C_SAFFRON, heading_rgb=C_SAFFRON, body_size=13.5,
    )
    _add_card(
        s2, 6.80, 1.30, 5.95, 5.45,
        "JanSahayak AI: End-to-End Solution",
        [
            "Agentic Hybrid RAG on IIT KGP Small Models: Combines BM25 + bge-small-en-v1.5 + RRF + CPU Cross-Encoder on Qwen/Qwen3-8B.",
            "Deterministic Eligibility & Document Readiness: Python rule engine checks age, income, caste, gender & exclusions with zero LLM math errors.",
            "6-Language Voice & Text: English-pivot retrieval guarantees identical answers across EN/HI/MR/BN/TA/TE + zero-key server MP3 audio.",
            "HITL Grievance Action + Live Email: Drafts <=2,000-char complaints, enforces human confirmation, sends live Gmail SMTP receipts & pgportal Handoff.",
        ],
        fill_rgb=C_CARD_GREEN, border_rgb=C_GREEN, heading_rgb=C_GREEN, body_size=13.5,
    )

    # ==================== SLIDE 3: CLEAN HIGH-LEVEL ARCHITECTURE ====================
    s3 = _new_slide(prs, "High-Level System Architecture", "Clean 4-Layer Separation: Civic Portal, LangGraph Brain, 5 Typed Tools & IIT KGP VMs", 3)
    _add_pic_fit(s3, DIAG_DIR / "clean_01_system_architecture.png", 0.55, 1.15, 12.2)

    # ==================== SLIDE 4: CLEAN DATA FLOW & HYBRID RAG ====================
    s4 = _new_slide(prs, "Offline Indexing & Online Hybrid RAG Data Flow", "6,059 Section-Aware Chunks -> Parallel BM25 + Dense -> RRF -> Reranker -> Critic Loop", 4)
    _add_pic_fit(s4, DIAG_DIR / "clean_02_hybrid_rag_dataflow.png", 0.55, 1.12, 12.1)

    # ==================== SLIDE 5: AGENTIC DESIGN & 5 TYPED TOOLS ====================
    s5 = _new_slide(prs, "Why Agentic RAG? 7-Node LangGraph + 5 Typed Tools", "Controlled Cycles, 1-Shot Pydantic JSON Repair & Code-Level HITL Safety", 5)
    _add_table(
        s5, 0.55, 1.30, 12.2, 3.65,
        ["Tool / Layer", "What It Does", "Reliability & Safety Control"],
        [
            ["T1: search_schemes", "BM25 (2x Title) + Dense bge-small -> RRF (k=60) -> CPU Cross-Encoder Top-6", "Locked to canonical English query_en; permissive filter auto-relaxes if <5 hits"],
            ["T2: check_eligibility", "Deterministic Python rule checks against SQLite (age, income, caste, exclusions)", "Auto-chained by Executor on real slugs—Planner cannot invent scheme slugs"],
            ["T3: web_search_gov", "Live DuckDuckGo search strictly scoped to site:gov.in / site:nic.in", "Auto-triggers ONLY if top_rerank < 0.35; strips indirect prompt injection"],
            ["T4: draft_grievance", "51-Ministry routing + PII masking + strict <=2,000-char CPGRAMS formatting", "Saves DRAFT-ID & sets hitl_paused=True to force citizen modal review"],
            ["T5: submit_or_track", "Registers Sandbox ticket + dispatches LIVE Gmail SMTP HTML email + Handoff", "Hard code gate blocks submit unless user_confirmed=True; 503 graceful fallback"],
        ],
        font_size=11.0,
    )
    _add_card(
        s5, 0.55, 5.20, 12.2, 1.72,
        "Track B Infrastructure & Constraint Engineering (Zero Paid SaaS)",
        [
            "Concurrency & Quota: Single-worker FastAPI + process-wide asyncio.Semaphore(1) + 55 RPM bucket + 2/4/8s backoff + TLS CA verify.",
            "Token & Latency Control: 8,192-token budgeter, enable_thinking=False (3x faster!), startup Cross-Encoder pre-warm, Two-Tier Exact+Semantic Cache (<50 ms).",
        ],
        fill_rgb=C_CARD_BLUE, border_rgb=C_BLUE, heading_rgb=C_NAVY, body_size=12.0,
    )

    # ==================== SLIDE 6: CITIZEN EXPERIENCE & MULTILINGUAL VOICE ====================
    s6 = _new_slide(prs, "Citizen Helpdesk UX, 6-Language Voice & Follow-Ups", "Gemini-Style Glass UI with Dark/Light Mode, Thinking Indicator & Session History", 6)
    _add_pic_fit(s6, SHOT_DIR / "helpdesk-chat-light.png", 0.55, 1.25, 6.45)
    _add_card(
        s6, 7.25, 1.25, 5.50, 5.55,
        "Key Citizen Experience Features",
        [
            "Conversational Intelligence: Dedicated CONVERSATION_HELP intent handles greetings warmly without falsely dumping schemes.",
            "Live 'Thinking' Indicator: Real-time SSE stream displays Guardrail -> Planner -> Retrieval -> Critic milestones.",
            "3 Suggested Follow-Up Questions: Contextual clickable pills after every answer guide citizens to documents, steps & exclusions.",
            "6-Language Voice I/O: Web Speech STT mic + zero-key server MP3 TTS (gTTS + edge-tts + 64-clip LRU cache) works on any OS.",
            "Sessions Sidebar & DPDP Privacy: Multi-session history, Profile Drawer, automatic Aadhaar/PAN masking & 1-click Erase My Data.",
        ],
        fill_rgb=C_WHITE, border_rgb=C_BLUE, heading_rgb=C_NAVY, body_size=12.0,
    )

    # ==================== SLIDE 7: HITL GRIEVANCE + LIVE EMAIL ACTION ====================
    s7 = _new_slide(prs, "Assisted CPGRAMS Grievance Workflow & Live Email Action", "Human-in-the-Loop Approval Gate, Real Gmail SMTP Receipt & Official Portal Handoff", 7)
    _add_pic_fit(s7, SHOT_DIR / "grievance-modal.png", 0.55, 1.25, 6.20)
    _add_card(
        s7, 7.00, 1.25, 5.75, 5.55,
        "From Complaint to Confirmed Action (4 Safeguards)",
        [
            "1. Auto-Routed to 51 Ministries: Searchable 649-scheme picker maps PM-KISAN -> MOAFW, Mudra -> MOFIN, Vishwakarma -> MSMEI.",
            "2. Strict HITL Gate: Agent is blocked in code from submitting; citizen edits letter (<=2,000 chars) and clicks Confirm & Submit.",
            "3. Real Live Email Confirmation: Dispatches formatted HTML receipt via Gmail SMTP TLS to user's inbox (+ built-in HTML Sandbox Outbox).",
            "4. Assisted pgportal.gov.in Handoff: 1-click copy packet + step-by-step instructions for official OTP-authenticated submission.",
            "5. Admin Lifecycle Controls: Citizens track ticket timelines; Admins progress Sandbox status (SUBMITTED -> UNDER_REVIEW -> RESOLVED).",
        ],
        fill_rgb=C_WHITE, border_rgb=C_SAFFRON, heading_rgb=C_SAFFRON, body_size=12.0,
    )

    # ==================== SLIDE 8: EVALUATION OVERVIEW & CHARTS ====================
    s8 = _new_slide(prs, "Comprehensive Model Evaluation — 60-Pair Zero-Leakage Gold QA", "Top-1/3/5 Retrieval Ablation, Vanilla vs. RAG (ROUGE/BLEU/BERTScore/Gemini Judge) & Latency", 8)
    _add_pic_fit(s8, DIAG_DIR / "clean_03_eval_benchmarks_v2.png", 0.45, 1.18, 12.4)
    _add_card(
        s8, 0.55, 5.72, 12.2, 1.25,
        "Zero-Leakage & Anti-Bias Evaluation Methodology",
        [
            f"Zero Data Leakage: 60 freshly authored citizen scenario QAs across 24 Ministries audited against all 7,724 corpus FAQs (0 exact matches!).",
            "Zero Self-Judge Bias: Evaluated independently by Gemini (Frontier External Judge) instead of Qwen3-8B judging itself—published statically in the Admin Portal.",
        ],
        fill_rgb=C_CARD_GREEN, border_rgb=C_GREEN, heading_rgb=C_GREEN, body_size=11.5,
    )

    # ==================== SLIDE 9: VANILLA LLM VS AGENTIC HYBRID RAG MATRIX ====================
    s9 = _new_slide(prs, "Vanilla LLM (No RAG) vs. JanSahayak Agentic Hybrid RAG", "Hard Quantitative Proof of Document Corpus Value on Fixed Qwen/Qwen3-8B (60 Gold Pairs)", 9)
    _add_table(
        s9, 0.55, 1.25, 12.2, 4.45,
        ["Metric (60 Zero-Leakage Gold QA Pairs)", "Vanilla Qwen3-8B (No RAG)", "JanSahayak Agentic RAG", "Measured Gain"],
        [
            ["ROUGE-1 (F1)", f"{nlp_v['rouge_1_f1']*100:.2f}%", f"{nlp_r['rouge_1_f1']*100:.2f}%", f"+{(nlp_r['rouge_1_f1']-nlp_v['rouge_1_f1'])*100:.2f}%"],
            ["ROUGE-2 (F1)", f"{nlp_v['rouge_2_f1']*100:.2f}%", f"{nlp_r['rouge_2_f1']*100:.2f}%", f"+{(nlp_r['rouge_2_f1']-nlp_v['rouge_2_f1'])*100:.2f}%"],
            ["ROUGE-L (F1)", f"{nlp_v['rouge_l_f1']*100:.2f}%", f"{nlp_r['rouge_l_f1']*100:.2f}%", f"+{(nlp_r['rouge_l_f1']-nlp_v['rouge_l_f1'])*100:.2f}%"],
            ["BLEU (Corpus)", f"{nlp_v['bleu_corpus']*100:.2f}%", f"{nlp_r['bleu_corpus']*100:.2f}%", f"+{(nlp_r['bleu_corpus']-nlp_v['bleu_corpus'])*100:.2f}%"],
            ["BERTScore (F1)", f"{nlp_v['bertscore_f1']*100:.2f}%", f"{nlp_r['bertscore_f1']*100:.2f}%", f"+{(nlp_r['bertscore_f1']-nlp_v['bertscore_f1'])*100:.2f}%"],
            ["Independent Gemini Judge: Accuracy (/5)", f"{jdg_v['avg_accuracy_5']:.2f} / 5", f"{jdg_r['avg_accuracy_5']:.2f} / 5", f"+{jdg_r['avg_accuracy_5']-jdg_v['avg_accuracy_5']:.2f}"],
            ["Independent Gemini Judge: Faithfulness (/5)", f"{jdg_v['avg_faithfulness_5']:.2f} / 5", f"{jdg_r['avg_faithfulness_5']:.2f} / 5", f"+{jdg_r['avg_faithfulness_5']-jdg_v['avg_faithfulness_5']:.2f}"],
            ["Independent Gemini Judge: Hallucination Rate", f"{jdg_v['hallucination_rate']*100:.1f}%", f"{jdg_r['hallucination_rate']*100:.1f}%", f"{(jdg_r['hallucination_rate']-jdg_v['hallucination_rate'])*100:.1f}%"],
        ],
        font_size=11.0,
    )
    _add_card(
        s9, 0.55, 5.90, 12.2, 1.05,
        "Average Latency Breakdown Across 60 Live Queries",
        [
            f"Hybrid Retrieval + Rerank: {lat['rag_avg_retrieval_ms']:.0f} ms   |   Qwen3-8B Generation: {lat['rag_avg_llm_ms']/1000:.2f} s   |   Total RAG: {lat['rag_avg_total_ms']/1000:.2f} s  (Two-Tier Cache hit: <50 ms!)",
        ],
        fill_rgb=C_CARD_SAFFRON, border_rgb=C_SAFFRON, heading_rgb=C_SAFFRON, body_size=12.0,
    )

    # ==================== SLIDE 10: PROMPTING, SAFETY & RELIABILITY ====================
    s10 = _new_slide(prs, "Prompting Ablation (P1–P3), Agent Faults & Red-Team Safety", "Structured Engineering Turns an 8B Model Into a Zero-Hallucination Production Agent", 10)
    p_rows = [
        [
            f"{s['id']}: {s['name']}",
            f"{s['answer_accuracy']*100:.1f}%",
            f"{s['citation_adherence']*100:.1f}%",
            f"{s['hallucination_rate']*100:.1f}%",
            f"{s['avg_latency_s']:.2f}s",
        ]
        for s in prm30["strategies"]
    ]
    _add_table(
        s10, 0.55, 1.30, 12.2, 2.30,
        ["Prompt Strategy (30 Stratified Qs, Fixed Qwen3-8B)", "Accuracy", "Citations", "Hallucination", "Avg Latency"],
        p_rows,
        font_size=11.5,
    )
    _add_card(
        s10, 0.55, 3.90, 5.95, 2.95,
        "Agent Fault Injection: 15 / 15 (100%)",
        [
            "5/5 Malformed JSON Recovery (Regex + 1-Shot LLM Pydantic Repair).",
            "4/4 HITL Gate Blocks (Unconfirmed CPGRAMS submit rejected in code).",
            "3/3 Graceful Gateway Fault Fallbacks (503 / bad_json -> Assisted Handoff).",
            "3/3 Tool Selection & Round-Trip Tracking Accuracy.",
        ],
        fill_rgb=C_CARD_BLUE, border_rgb=C_BLUE, heading_rgb=C_NAVY, body_size=12.0,
    )
    _add_card(
        s10, 6.80, 3.90, 5.95, 2.95,
        "Red-Team Safety: Hardened 80% -> 100% (20 / 20)",
        [
            "16/16 Attacks Blocked: Direct/Base64/Indirect Injection, Forgery, CAPTCHA Bypass.",
            "3/3 DPDP PII Masking: Aadhaar, PAN, Mobile, Bank Account & IFSC redacted pre-LLM.",
            "1/1 Fabricated Scheme Refusal: 'PM Free iPhone Yojana' honestly refused (score 0.280).",
            "21/21 Pytest Unit/API Tests + 9/9 Live E2E Tests Passing.",
        ],
        fill_rgb=C_CARD_GREEN, border_rgb=C_GREEN, heading_rgb=C_GREEN, body_size=12.0,
    )

    # ==================== SLIDE 11: ADMIN LANGFUSE TRACES & EVAL CONSOLE ====================
    s11 = _new_slide(prs, "Admin-Only Langfuse Trace Debugger & Eval Console", "Full Per-Span Visibility (SPN-01..N), Latency Monitoring & 1-Click JSON/MD/CSV Exports", 11)
    _add_pic_fit(s11, SHOT_DIR / "trace-dashboard.png", 0.55, 1.25, 6.00)
    _add_pic_fit(s11, SHOT_DIR / "eval-dashboard.png", 6.78, 1.25, 6.00)
    _add_card(
        s11, 0.55, 5.45, 12.2, 1.45,
        "Live Trace Proof (TRC-DB1E35A90D — Mumbai MRO Manufacturing Loan)",
        [
            "Planner inferred Maharashtra from 'Mumbai'; Dense bge-small rescued PM Vishwakarma (0.742) & PMEGP (0.722) when BM25=0.0!",
            "Critic (SPN-06) caught a live citation slip ([2] instead of [4]/[6]), triggered 1 revision (SPN-07), and passed verification (SPN-08)!",
        ],
        fill_rgb=C_CARD_BLUE, border_rgb=C_BLUE, heading_rgb=C_NAVY, body_size=11.5,
    )

    # ==================== SLIDE 12: LIVE DEMO PLAYBOOK ====================
    s12 = _new_slide(prs, "Live Demo Walkthrough & Persona Accounts", "Reproducible 1-Command Launch (start_local.ps1 / start_local.sh) on Any Laptop", 12)
    _add_table(
        s12, 0.55, 1.30, 5.80, 3.60,
        ["Persona", "Login", "Role"],
        [
            ["Rajesh Verma", "admin / admin123", "Admin (All 5 Tabs + Exports)"],
            ["Ramesh Kumar (UP)", "ramesh / citizen123", "Citizen (Hindi Farmer)"],
            ["Priya Sharma (MH)", "priya / citizen123", "Citizen (B.Tech Student)"],
            ["Abdul Rahim (GJ)", "abdul / citizen123", "Citizen (Artisan)"],
            ["Lakshmi Devi (TN)", "lakshmi / citizen123", "Citizen (Tamil Senior)"],
        ],
        font_size=10.8,
    )
    _add_card(
        s12, 6.65, 1.30, 6.10, 5.50,
        "5-Step Live Demo Script (5 Minutes)",
        [
            "1. RBAC Login & Glass UI: Log in as Priya — Admin Traces & Evals tabs are strictly hidden; show Dark/Light theme & Sessions Sidebar.",
            "2. Grounded Eligibility + Follow-Ups: Ask scholarship/MRO loan query -> watch live Thinking steps, [1] links, Eligibility Card & 3 Follow-Up pills.",
            "3. Vernacular Consistency + Voice: Switch to Hindi/Tamil/Marathi -> same verified scheme + click Listen for clear server MP3 audio.",
            "4. HITL Grievance + Real Email: Raise PM-KISAN complaint -> Confirm & Submit -> show Sandbox Ticket + LIVE Gmail inbox receipt!",
            "5. Admin Trace & Eval Console: Switch to Admin -> inspect SPN-01..N waterfall, download JSON trace, and review Gemini Judge + ROUGE/BLEU/BERTScore.",
        ],
        fill_rgb=C_WHITE, border_rgb=C_SAFFRON, heading_rgb=C_NAVY, body_size=12.0,
    )
    _add_card(
        s12, 0.55, 5.15, 5.80, 1.65,
        "GitHub & Zero-Failure Team Setup",
        [
            "Private Repo: github.com/rg-genai/jansahayak-ai-capstone",
            "Full README + private data/secrets bundle = 2-min launch!",
        ],
        fill_rgb=C_CARD_GREEN, border_rgb=C_GREEN, heading_rgb=C_GREEN, body_size=11.5,
    )

    # ==================== SLIDE 13: TAKEAWAYS & ROADMAP ====================
    s13 = _new_slide(prs, "Key Engineering Takeaways & Phase 3 Roadmap", "From IIT Kharagpur Track B Capstone to National Digital Public Infrastructure", 13)
    _add_card(
        s13, 0.55, 1.30, 5.95, 5.45,
        "Key Takeaways Proven With Data",
        [
            f"Hybrid RAG + P3 Architecture Beats Vanilla 8B: Gemini Judge jumped {jdg_v['avg_accuracy_5']:.2f} -> {jdg_r['avg_accuracy_5']:.2f}/5; Hallucinations dropped {jdg_v['hallucination_rate']*100:.1f}% -> {jdg_r['hallucination_rate']*100:.1f}%.",
            "Hybrid Retrieval Solves GovTech Vocabulary Gap: BM25 catches acronyms; Dense bge-small catches citizen narratives; Cross-Encoder calibrates confidence.",
            "Unbiased External Judging + NLP Metrics: Combining ROUGE, BLEU, BERTScore & independent Gemini judging catches blind spots.",
            "Defense-in-Depth Safety: Regex DPDP PII masking + Untrusted tags + code-level HITL gate achieved 100% Red-Team & Fault pass rates.",
        ],
        fill_rgb=C_CARD_BLUE, border_rgb=C_BLUE, heading_rgb=C_NAVY, body_size=12.5,
    )
    _add_card(
        s13, 6.80, 1.30, 5.95, 5.45,
        "Honest Limitations & Phase 3 Roadmap",
        [
            "State Scheme Expansion: Scale from 649 Central schemes to ~3,500 Central + State/UT schemes (~38 MB vector index).",
            "Live API Setu CPGRAMS Integration: Upgrade Sandbox + Assisted Handoff to OAuth / Jan Parichay official filing.",
            "ONNX INT8 Reranker & Query Rewriter: Cut CPU rerank latency from ~1.5s to <150 ms and boost narrative query recall.",
            "Bhashini ULCA + WhatsApp Voice Bot: Native Indic NMT/ASR/TTS over WhatsApp voice notes for rural last-mile accessibility.",
        ],
        fill_rgb=C_CARD_SAFFRON, border_rgb=C_SAFFRON, heading_rgb=C_SAFFRON, body_size=12.5,
    )

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(OUT_PATH))
    return OUT_PATH


if __name__ == "__main__":
    p = build_ppt()
    print(f"[OK] Built 13-Slide Presentation: {p} ({p.stat().st_size:,} bytes)")
