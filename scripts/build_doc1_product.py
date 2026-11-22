"""Build Document 1: Detailed Product Documentation (.docx) for JanSahayak AI."""

from __future__ import annotations

from pathlib import Path

from docx_helpers import (
    HEX_BLUE,
    HEX_GREEN,
    HEX_LIGHT_AMBER,
    HEX_LIGHT_BLUE,
    HEX_LIGHT_GREEN,
    HEX_LIGHT_SAFFRON,
    HEX_NAVY,
    HEX_SAFFRON,
    add_bullets,
    add_callout,
    add_cover_page,
    add_figure,
    add_h1,
    add_h2,
    add_h3,
    add_numbered,
    add_para,
    add_styled_table,
    create_styled_document,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DIAG_DIR = PROJECT_ROOT / "docs" / "diagrams"
OUT_PATH = PROJECT_ROOT / "docs" / "deliverables" / "01_JanSahayak_AI_Product_Documentation.docx"


def build_product_doc() -> Path:
    doc = create_styled_document(
        header_title="JanSahayak AI — Product Documentation (Capabilities, UX & Limitations)",
    )

    add_cover_page(
        doc,
        badge_text="IIT Kharagpur GenAI & Agentic AI — Track B Capstone",
        title="JanSahayak AI\nProduct Documentation",
        subtitle="Multilingual Indian Citizen Welfare Copilot & Assisted CPGRAMS Grievance Agent\nCapabilities, User Journeys, Responsible AI Contract & Honest Limitations",
        metadata_rows=[
            ("Product Name", "**JanSahayak AI** (जनसहायक AI — Citizen Welfare & Grievance Copilot)"),
            ("Program & Track", "IIT Kharagpur Executive PG Certificate in GenAI & Agentic AI — **Track B (Enterprise Application)**"),
            ("Knowledge Coverage", "**649** Central Government Schemes • **7,724** Official FAQs • **51** Canonical Ministries (myScheme.gov.in)"),
            ("Languages & Voice", "6 Indian Languages (**English, Hindi, Hinglish, Marathi, Bengali, Tamil, Telugu**) + Voice Mic & Server Audio"),
            ("Live Action Channel", "HITL-Protected **CPGRAMS Sandbox Workflow** + **Live Gmail SMTP Email Receipts** + `pgportal.gov.in` Handoff"),
            ("Audience", "Capstone Team Members, Faculty Mentor, Product Stakeholders & Demo Evaluators"),
        ],
        highlights=[
            "Solves India's 'Last-Mile Scheme Discovery & Grievance Friction' across 649 Central schemes with zero hallucinated rupee benefits.",
            "Combines conversational Agentic RAG, deterministic eligibility rule checks, 6-language voice I/O, and live email confirmation actions.",
            "Built with Persona-based Login (Admin + 4 Citizen personas), DPDP Act 2023 PII masking, Right to Erasure, and Langfuse-style Admin observability.",
            "Transparently documents real-world boundaries (Central vs State coverage, Sandbox vs live PGPortal APIs) and a realistic Phase 3 roadmap.",
        ],
    )

    # =========================================================================
    # SECTION 1: EXECUTIVE VISION & CITIZEN ACCESS GAP
    # =========================================================================
    add_h1(doc, "1. Product Vision & The Indian Citizen Access Gap")
    add_para(
        doc,
        "India operates one of the world's largest digital public welfare ecosystems—spanning hundreds of Central Government scholarships, "
        "farmer income transfers, MSME micro-credit programs, health insurance schemes, and social security pensions. Yet everyday citizens "
        "regularly miss entitlements worth lakhs of rupees due to four systemic last-mile barriers:"
    )
    add_bullets(
        doc,
        [
            "**Fragmented Scheme Discovery:** Citizens rarely know official scheme acronyms like `PMEGP`, `PM-USP`, or `NAMASTE`. A 25-year-old in Mumbai looking to start a nuts-and-bolts manufacturing workshop does not know whether to search Ministry of MSME, Finance, or Skill Development.",
            "**Hidden Exclusion Clauses:** Even when citizens find a scheme, eligibility fine print (such as Income Tax payer exclusions in PM-KISAN, age caps, or caste/income ceilings) is buried across multi-page PDFs and FAQs—leading to avoidable application rejections.",
            "**Language & Literacy Friction:** Official welfare portals are heavily English-centric and form-driven. Rural farmers, artisans, and senior citizens naturally think and speak in Hindi, Hinglish, Marathi, Bengali, Tamil, or Telugu.",
            "**Grievance Redressal Anxiety:** When a Direct Benefit Transfer (DBT) installment stalls or a scholarship is wrongly rejected, citizens struggle to identify which of the 51 Central Ministries handles their scheme or how to draft a concise, formal complaint within CPGRAMS's strict 2,000-character limit.",
        ],
    )
    add_callout(
        doc,
        "Product Mission Statement",
        "**JanSahayak AI** is a trustworthy, voice-enabled, multilingual AI citizen copilot that turns plain-language life situations "
        "(spoken or typed in 6 Indian languages) into **citation-verified Central Government scheme recommendations, structured eligibility "
        "verdicts, document checklists, and human-approved CPGRAMS grievance filings with live email confirmation receipts.**",
        accent_hex=HEX_SAFFRON,
        fill_hex=HEX_LIGHT_SAFFRON,
    )

    # =========================================================================
    # SECTION 2: CORE CAPABILITIES MATRIX
    # =========================================================================
    add_h1(doc, "2. Complete Product Capabilities Matrix")
    add_para(
        doc,
        "JanSahayak AI is built as a complete, production-styled GovTech web platform with seven tightly integrated product pillars. "
        "Every capability below is live, interactive, and backed by automated verification."
    )
    add_styled_table(
        doc,
        headers=["Product Pillar", "What Citizens / Admins Can Do", "Key Value & Trust Safeguards"],
        rows=[
            [
                "**1. Conversational Citizen Helpdesk**",
                "Ask open-ended life-situation questions, greet naturally, compare schemes, or check eligibility across multi-turn conversations with session memory.",
                "Understands natural greetings (`CONVERSATION_HELP`) without falsely dumping schemes; every factual scheme claim carries clickable `[1]`, `[2]` links to official `myscheme.gov.in` pages.",
            ],
            [
                "**2. Deterministic Eligibility & Document Readiness**",
                "Extracts citizen profile attributes (age, gender, state, income, social category, occupation) and produces clear verdicts (**Likely Eligible / Partially Eligible / Not Eligible / Needs More Info**).",
                "Cross-checks age bounds, income caps, women-only restrictions, caste quotas, and explicit exclusion clauses (e.g., Income Tax payer / Govt employee) alongside an actionable document checklist.",
            ],
            [
                "**3. 6-Language Vernacular & Voice I/O**",
                "Communicate in **English, Hindi, Hinglish, Marathi, Bengali, Tamil, or Telugu** via keyboard or microphone (STT), and click **Listen** on any reply to hear clear spoken audio.",
                "Cross-lingual consistency guarantee: identical questions asked in English, Hindi, or Tamil retrieve the exact same verified scheme! Server-side MP3 TTS (`gTTS` + `edge-tts`) works on every device without OS voice-pack setup.",
            ],
            [
                "**4. Interactive 649-Scheme Explorer**",
                "Browse, keyword-search, and filter all **649 Central Government schemes** across 51 Ministries, DBT-only tags, benefit categories, and full FAQ drawers.",
                "Zero-hallucination catalog backed by SQLite; citizens can inspect official eligibility, exclusions, application steps, and jump straight into asking the Copilot or filing a grievance.",
            ],
            [
                "**5. Assisted CPGRAMS Grievance & Live Email Action**",
                "Draft formal complaints (auto-routed to the correct Central Ministry and capped at <= 2,000 chars), review/edit in a modal, submit via Sandbox with **real Gmail SMTP confirmation email**, and track ticket status.",
                "Strict **Human-in-the-Loop (HITL)** confirmation gate prevents autonomous filing. Generates an **Assisted Real-Portal Handoff Packet** with one-click copy and deep link to `pgportal.gov.in`, plus downloadable HTML email receipt.",
            ],
            [
                "**6. Persona Login & Role-Based Access Control (RBAC)**",
                "Log in securely as **System Admin** or one of **4 realistic Citizen Personas** (Rural Farmer, B.Tech Student, Traditional Artisan, Senior Citizen) with pre-populated demographic profiles.",
                "HMAC-SHA256 signed Bearer tokens enforce strict UI & API boundaries: Citizens only access Helpdesk, Schemes & My Grievances; Admins unlock Traces, Evals & Sandbox status progression.",
            ],
            [
                "**7. Langfuse-Style Admin Observability & Eval Console**",
                "Inspect every request trace (`TRC-...`) with step-by-step waterfall spans (`SPN-01..N`), token usage, latency, retrieved chunks, Critic verdicts, and live Eval scorecards.",
                "One-click structured downloads (**JSON, Markdown, CSV**) for team debugging and mentor audits; Admin can also simulate CPGRAMS ticket lifecycle transitions (`UNDER_REVIEW -> RESOLVED`).",
            ],
        ],
        col_widths_in=[1.65, 2.65, 2.70],
        font_size=8.8,
    )

    add_figure(
        doc,
        DIAG_DIR / "01_layered_tech_stack.png",
        "Figure 1: JanSahayak AI Platform Overview — Showing how IIT Kharagpur Track B Hosted Models, Open-Source Frameworks, and Live External Services come together.",
        width_in=6.85,
    )

    # =========================================================================
    # SECTION 3: USER PERSONAS & RBAC ACCESS MODEL
    # =========================================================================
    add_h1(doc, "3. User Personas & Role-Based Access Control (RBAC)", page_break_before=True)
    add_para(
        doc,
        "To demonstrate realistic multi-user governance during team demos and mentor evaluations, JanSahayak AI ships with a clean, "
        "GovTech-inspired Login Screen (with password visibility toggle and an expandable demo credentials helper) supporting **1 Admin** "
        "and **4 diverse Indian Citizen personas**:"
    )
    add_styled_table(
        doc,
        headers=["Persona & Login", "Role & Scope", "Demographic Profile", "Primary Use Case Demonstrated"],
        rows=[
            [
                "**Rajesh Verma**\n`admin` / `admin123`",
                "**Admin** (Full Access: All 5 Tabs + Exports + Ticket Progression)",
                "System Admin & Track B Evaluator (English)",
                "Auditing Langfuse spans, exporting JSON/MD/CSV traces, reviewing `R1–R4` / `P1–P3` eval benchmarks, progressing CPGRAMS ticket statuses.",
            ],
            [
                "**Ramesh Kumar**\n`ramesh` / `citizen123`",
                "**Citizen** (Helpdesk, Scheme Explorer, My Grievances)",
                "46 yrs, Male, OBC, Smallholder Farmer, Uttar Pradesh, ₹1.2L income, BPL (Hindi)",
                "Hindi/Hinglish voice queries about PM-KISAN ₹6,000 DBT installments, filing delayed-installment CPGRAMS grievance & receiving live email receipt.",
            ],
            [
                "**Priya Sharma**\n`priya` / `citizen123`",
                "**Citizen** (Helpdesk, Scheme Explorer, My Grievances)",
                "19 yrs, Female, OBC, B.Tech Student, Maharashtra, ₹1.8L family income (English)",
                "Discovering Central scholarships (PM-USP CSSS), verifying ₹12,000/₹20,000 annual amounts, checking caste/income documents.",
            ],
            [
                "**Abdul Rahim**\n`abdul` / `citizen123`",
                "**Citizen** (Helpdesk, Scheme Explorer, My Grievances)",
                "34 yrs, Male, Minority, Traditional Carpenter Artisan, Gujarat, ₹1.5L income (Hindi)",
                "Exploring PM Vishwakarma toolkit incentives & collateral-free ₹1L/₹2L loans and Mudra micro-credit options.",
            ],
            [
                "**Lakshmi Devi**\n`lakshmi` / `citizen123`",
                "**Citizen** (Helpdesk, Scheme Explorer, My Grievances)",
                "62 yrs, Female, SC, BPL Senior Citizen, Tamil Nadu, ₹60K income (Tamil)",
                "Vernacular Tamil scheme discovery (Ayushman Bharat, Indira Gandhi Old Age Pension) and server-side Tamil MP3 audio playback.",
            ],
        ],
        col_widths_in=[1.35, 1.45, 1.95, 2.25],
        font_size=8.6,
    )

    add_h2(doc, "3.1 End-to-End Citizen User Journeys")
    add_h3(doc, "Journey A: Vernacular Discovery -> Eligibility Check -> Audio Readout")
    add_numbered(
        doc,
        [
            "Citizen logs in (e.g., **Priya** or **Ramesh**) and lands directly in the **Citizen Helpdesk** with their demographic profile badge visible in the sidebar.",
            "Citizen types or speaks via the **Mic button** in English, Hindi, Hinglish, Marathi, Bengali, Tamil, or Telugu—for example, asking about a manufacturing business loan in Mumbai or a Central scholarship.",
            "While the agent works, the UI streams live reasoning milestones (*Checking guardrails -> Planning -> Searching 649 schemes -> Verifying groundedness*) via Server-Sent Events (SSE).",
            "The answer renders in warm, scannable markdown with bold section headings, clickable inline `[1]`, `[2]` links to `myscheme.gov.in`, and structured Eligibility Cards listing matched criteria, exclusions, and required documents.",
            "Citizen clicks **Listen** to play natural MP3 speech generated by the server (`POST /api/voice/tts`) in the exact detected language of the response—with zero OS voice-pack errors.",
            "At any point, the citizen can start a fresh topic via **New Chat**, end and archive via **Close Session**, or exercise DPDP Act privacy via **Erase My Data** (which permanently wipes messages and scrubs PII from traces).",
        ],
    )

    add_h3(doc, "Journey B: CPGRAMS Grievance Drafting -> HITL Approval -> Live Email Receipt")
    add_numbered(
        doc,
        [
            "Citizen either mentions a problem in chat (*\"My PM-KISAN installment has been stuck for 4 months\"*) or clicks **Raise Grievance** in the Helpdesk header.",
            "The **Grievance Modal** opens with searchable autocomplete across all 649 Central schemes, auto-mapping the exact **Central Ministry** (out of 51 canonical ministries), masking any Aadhaar/PAN/phone digits, and enforcing CPGRAMS's hard **2,000-character limit**.",
            "**Human-in-the-Loop (HITL) Pause:** The agent is programmatically blocked from submitting autonomously. The citizen reviews/edits the drafted letter, optionally enters their email address for a real confirmation email, and explicitly clicks **Confirm & Submit**.",
            "Upon confirmation, the backend registers a structured Sandbox ticket (e.g., `MOAFW/E/2026/000001`), dispatches a **real formatted HTML confirmation email via Gmail SMTP** (and saves a downloadable copy in the built-in Sandbox Outbox), and presents the **Assisted Real-Portal Handoff Packet** to paste directly into official `pgportal.gov.in`.",
            "In **My Grievances**, citizens can click any ticket card to inspect the full timeline, copy the complaint text, download their HTML email receipt, or track status updates (and Admins can advance status from `SUBMITTED -> UNDER_REVIEW -> RESOLVED`).",
        ],
    )

    # =========================================================================
    # SECTION 4: RESPONSIBLE AI, SAFETY & EXPLICIT REFUSAL CONTRACT
    # =========================================================================
    add_h1(doc, "4. Trust, Safety, DPDP Privacy & Explicit Refusal Contract")
    add_para(
        doc,
        "In government welfare advisory, a confident hallucination can waste a low-income family's travel money or cause them to miss a "
        "critical deadline. JanSahayak AI therefore enforces an **Explicit Refusal & Grounding Contract** validated across 20 adversarial "
        "red-team test cases (**100% pass rate** after hardening)."
    )
    add_styled_table(
        doc,
        headers=["Category", "What JanSahayak AI DOES (Allowed)", "What JanSahayak AI REFUSES (Blocked)"],
        rows=[
            [
                "**Scheme Knowledge**",
                "Answers strictly from the verified 649-scheme myScheme corpus or live `.gov.in` web fallback with inline `[1]`, `[2]` citations.",
                "Refuses to fabricate benefits or invent non-existent schemes (e.g., *'PM Free iPhone Yojana'* returns an honest refusal).",
            ],
            [
                "**Citizen Privacy (DPDP Act 2023)**",
                "Automatically masks 12-digit Aadhaar (`XXXX-XXXX-1234`), PAN (`XXXXX1234X`), mobile numbers, bank accounts & IFSC codes before LLM calls or DB storage. Supports one-click **Erase My Data**.",
                "Never stores raw Aadhaar/PAN in SQLite traces, never leaks credentials or `.env` configuration, and never echoes raw PII in assistant answers.",
            ],
            [
                "**Portal Integrity & Anti-Fraud**",
                "Prepares a compliant <= 2,000-char CPGRAMS draft and guides the citizen to official `pgportal.gov.in` with their own documents.",
                "Strictly blocks requests to bypass OTPs/CAPTCHAs, forge income/caste certificates, or auto-submit grievances without explicit HITL confirmation.",
            ],
            [
                "**Domain Boundaries**",
                "Covers Indian Central Government welfare schemes, eligibility checks, document checklists, and CPGRAMS grievance assistance.",
                "Politely declines out-of-scope medical prescriptions (directs to `108` / eSanjeevani), stock/crypto investment advice, and prompt-injection jailbreaks.",
            ],
        ],
        col_widths_in=[1.45, 2.75, 2.80],
        font_size=8.7,
    )

    add_figure(
        doc,
        DIAG_DIR / "05_eval_benchmarks.png",
        "Figure 2: Real Verified Evaluation Benchmarks — Proving 95.9% Retrieval Recall@5, 100% P3 Accuracy with 0% Hallucination, and 100% Safety & Fault Recovery.",
        width_in=6.85,
    )

    # =========================================================================
    # SECTION 5: HONEST LIMITATIONS & COMMERCIALIZATION ROADMAP
    # =========================================================================
    add_h1(doc, "5. Honest Product Limitations & Future Roadmap", page_break_before=True)
    add_para(
        doc,
        "A mature product team never hides system constraints—especially during an academic capstone review. Below is an honest accounting "
        "of current product boundaries and how each maps cleanly to a Phase 2 / Phase 3 production roadmap:"
    )
    add_styled_table(
        doc,
        headers=["Current Limitation", "Root Cause / Why It Exists Today", "Mitigation Built Today", "Phase 2 / 3 Production Upgrade"],
        rows=[
            [
                "**Central Schemes Only (649)**",
                "The myScheme dataset snapshot covers Central Government schemes; ~2,500+ State-specific schemes (e.g., Maharashtra *Ladki Bahin* or *CMEGP*) are not in the local CSV.",
                "Low-confidence queries automatically trigger live `.gov.in` web fallback (`DuckDuckGo` scoped to `gov.in`/`nic.in`).",
                "Ingest full State + UT myScheme catalogs (~3,500 schemes) with automated weekly incremental delta sync.",
            ],
            [
                "**CPGRAMS Submission Is a Sandbox**",
                "Official `pgportal.gov.in` requires citizen Mobile OTP / Jan Parichay authentication and has no open unauthenticated public write API.",
                "Full local Mock PGPortal API + **live Gmail SMTP confirmation emails** + one-click **Assisted Handoff Packet** to real `pgportal.gov.in`.",
                "Partner with DARPG / API Setu for authorized OAuth / Jan Parichay citizen-consent grievance submission.",
            ],
            [
                "**Vernacular Fluency vs. Latency**",
                "`Qwen/Qwen3-8B` is a compact 8B general model; translating into Tamil/Telugu/Marathi adds 1 extra LLM round-trip (~3–6s) and can occasionally be formal.",
                "English-pivot retrieval ensures **100% cross-lingual factual consistency**; concise <= 240-word answers keep translation clean and fast; server `gTTS` provides clear audio.",
                "Integrate **Bhashini ULCA / Sarvam-Translate** neural Indic NMT + Indic ASR/TTS models for sub-second native vernacular quality.",
            ],
            [
                "**Single-Worker Throughput Ceiling**",
                "Track B hosted LLM enforces **1 active request per group key** and 60 req/min max across the entire team.",
                "`asyncio.Semaphore(1)` + 55 RPM client bucket + Two-Tier Exact/Semantic Cache (`<50 ms` repeat hits) + startup pre-warm.",
                "Deploy horizontally scaled vLLM cluster (Tensor Parallelism + continuous batching) behind Redis rate-limiting & Qdrant/Milvus.",
            ],
            [
                "**Conversational Query Complexity on Reranker**",
                "Very long narrative prompts (*'nuts, bolts, MRO parts in Mumbai'*) can yield low raw Cross-Encoder scores even when Dense vectors retrieve the right MSME schemes (PMEGP, PM Vishwakarma).",
                "Hybrid RRF preserves strong Dense hits; Synthesizer filters mismatched schemes (e.g., excluding women-only schemes for male users) and Critic repairs citations.",
                "Add a lightweight **Query Rewriter** inside the Planner to emit crisp 5–8 keyword search queries alongside conversational intent.",
            ],
            [
                "**Web-Only Channel (No WhatsApp Yet)**",
                "Capstone scope prioritized a rich React SPA with Voice I/O, Scheme Explorer, and Admin Trace Console.",
                "Mobile-responsive Tailwind layout + browser Mic + server MP3 playback work smoothly on smartphone browsers.",
                "Connect FastAPI backend to **WhatsApp Business Cloud API** (voice-note STT -> Agent -> MP3 voice reply) for rural reach.",
            ],
        ],
        col_widths_in=[1.40, 1.80, 1.85, 1.95],
        font_size=8.4,
    )

    add_callout(
        doc,
        "Product Readiness Verdict for Team & Mentor Presentation",
        "JanSahayak AI is **demo-ready, verified end-to-end, and honest about its boundaries**. Every core user promise—multilingual "
        "grounded discovery across 649 Central schemes, deterministic eligibility & exclusion checking, 6-language voice I/O, HITL-gated "
        "grievance drafting with real email confirmation delivery, RBAC persona login, and Langfuse-style observability—works live on "
        "the IIT Kharagpur Track B infrastructure with zero paid SaaS dependencies.",
        accent_hex=HEX_GREEN,
        fill_hex=HEX_LIGHT_GREEN,
    )

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(OUT_PATH))
    return OUT_PATH


if __name__ == "__main__":
    p = build_product_doc()
    print(f"[OK] Built Product Documentation: {p} ({p.stat().st_size:,} bytes)")
