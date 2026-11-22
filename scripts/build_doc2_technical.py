"""Build Document 2: Comprehensive Technical Architecture & Mentor Deep Dive (.docx) for JanSahayak AI."""

from __future__ import annotations

import json
from pathlib import Path

from docx_helpers import (
    HEX_BLUE,
    HEX_GREEN,
    HEX_LIGHT_AMBER,
    HEX_LIGHT_BLUE,
    HEX_LIGHT_GREEN,
    HEX_LIGHT_SAFFRON,
    HEX_NAVY,
    HEX_PURPLE,
    HEX_SAFFRON,
    add_bullets,
    add_callout,
    add_code_block,
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
CAPTURE_PATH = PROJECT_ROOT / "data" / "live_walkthrough_capture.json"
OUT_PATH = PROJECT_ROOT / "docs" / "deliverables" / "02_JanSahayak_AI_Technical_Architecture_and_Deep_Dive.docx"


def build_technical_doc() -> Path:
    capture = json.loads(CAPTURE_PATH.read_text(encoding="utf-8"))
    ret_rep = json.loads((PROJECT_ROOT / "eval" / "reports" / "retrieval_ablation.json").read_text(encoding="utf-8"))
    prm_rep = json.loads((PROJECT_ROOT / "eval" / "reports" / "prompt_comparison.json").read_text(encoding="utf-8"))
    flt_rep = json.loads((PROJECT_ROOT / "eval" / "reports" / "agent_reliability.json").read_text(encoding="utf-8"))
    rt_rep = json.loads((PROJECT_ROOT / "eval" / "reports" / "red_team_report.json").read_text(encoding="utf-8"))

    doc = create_styled_document(
        header_title="JanSahayak AI — End-to-End Technical Architecture & Engineering Deep Dive",
    )

    add_cover_page(
        doc,
        badge_text="IIT Kharagpur GenAI & Agentic AI — Track B Technical Manual",
        title="JanSahayak AI\nEnd-to-End Technical Architecture & Engineering Deep Dive",
        subtitle="Complete Guide for Team Knowledge Transfer & Faculty Mentor Viva\nSyllabus Correlation • Agentic Hybrid RAG • Tool Orchestration • Live Trace Walkthrough • Evaluation Mathematics",
        metadata_rows=[
            ("Architecture Pattern", "**Agentic Hybrid RAG** (7-Node Compiled LangGraph StateGraph + 5 Typed Pydantic Tools)"),
            ("IIT KGP Hosted Models", "`Qwen/Qwen3-8B` (8,192 ctx, `enable_thinking: False`) + `bge-small-en-v1.5` (384-dim, VM02)"),
            ("Local Retrieval Stack", "**6,059** Section-Aware Chunks (`<=440` tok) • `embeddings.npy` + `bm25.pkl` + CPU `ms-marco-MiniLM-L-6-v2`"),
            ("Backend & Frontend", "Single-Worker **FastAPI / Uvicorn** (Python 3.11) + **React 18 / Vite / TypeScript / Tailwind** + **SQLite WAL**"),
            ("Live Trace Walkthrough", f"Real Captured Trace `{capture['trace_id']}` (Mumbai 25yo MRO Nuts & Bolts Manufacturing Loan Prompt)"),
            ("Verified Evals", "R@5 **95.9%** • MRR@10 **0.925** • P3 Accuracy **100%** / Hallucination **0%** • Safety **20/20** • Faults **15/15**"),
        ],
        highlights=[
            "Written in clear, intuitive Executive PG student language—explaining *why* every architectural choice was made without skipping technical rigor.",
            "Maps every implemented module directly to Modules 1–5 of the IIT Kharagpur GenAI & Agentic AI Curriculum and Track B Grading Rubric.",
            "Walks step-by-step through a REAL live execution trace (`TRC-DB1E35A90D`), including the live Critic revision loop that caught and repaired inline citations!",
            "Demystifies every evaluation metric (Recall@K, MRR@10, NDCG@5, Citation Adherence, Hallucination Rate) with exact formulas and worked numerical examples.",
        ],
    )

    # =========================================================================
    # SECTION 1: IIT KHARAGPUR SYLLABUS & TRACK B RUBRIC CORRELATION
    # =========================================================================
    add_h1(doc, "1. Correlation With the IIT Kharagpur Curriculum & Track B Rubric")
    add_para(
        doc,
        "A common mentor viva question is: *\"How did you apply the concepts taught across our 5 program modules rather than just gluing "
        "an API wrapper together?\"* The table below maps every major module from the official **IIT Kharagpur Executive PG Certificate in "
        "Generative AI & Agentic AI** syllabus directly to concrete files and engineering decisions inside JanSahayak AI."
    )
    add_styled_table(
        doc,
        headers=["IIT KGP Syllabus Module", "Core Concepts Taught", "How We Applied It in JanSahayak AI"],
        rows=[
            [
                "**Module 1**\nFoundations of GenAI & LLMs\n*(Weeks 1–6)*",
                "Tokenisation, Transformer Attention, Dense Embeddings, Foundation Model Selection under compute/cost constraints.",
                "Built exact token estimators (`cl100k_base` + offline fallback) to respect `bge-small-en-v1.5`'s **512-token cap** (`chunker.py`, max 440 tokens) and `Qwen3-8B`'s **8,192-token context window** (`llm_client.py`). Disabled `<think>` reasoning tokens via `enable_thinking: False` to protect latency & output budgets.",
            ],
            [
                "**Module 2**\nAdvanced Prompting & RAG Systems\n*(Weeks 7–12)*",
                "Zero-shot vs Few-shot vs Structured/Tool prompting, Chunking strategies, Hybrid Search (Sparse + Dense), Reranking, RAG evaluation & failure debugging.",
                "Conducted full **4-way Retrieval Ablation (`R1–R4`)** proving Hybrid RRF raises Recall@5 from 93.2% to **95.9%** and MRR@10 to **0.925**, plus **3-way Prompting Study (`P1–P3`)** reducing hallucination from **66.7% -> 0.0%** on fixed `Qwen3-8B`.",
            ],
            [
                "**Module 3**\nLLM Fine-Tuning & Alignment\n*(Weeks 13–18)*",
                "Fine-Tuning Decision Framework: *When to fine-tune (LoRA/QLoRA) vs. Prompt Engineering vs. RAG*.",
                "Explicitly applied the decision framework: Government schemes change budgets, eligibility caps, and circulars frequently—baking them into static model weights causes stale facts and hallucinations. **Agentic RAG + Deterministic Rules** keeps knowledge updatable in minutes without retraining.",
            ],
            [
                "**Module 4**\nMultimodal & Agentic AI\n*(Weeks 19–24)*",
                "Multimodal voice/speech pipelines, Agentic Planning, Tool Use, Memory, Stateful Orchestration (LangGraph), Human-in-the-Loop (HITL) control.",
                "Engineered a **7-node compiled LangGraph StateGraph** with **5 strictly typed Pydantic tools**, session profile memory, automatic **1-shot JSON schema repair**, HITL grievance approval gate, Web Speech STT, and 6-language server MP3 TTS (`routes_voice.py`).",
            ],
            [
                "**Module 5**\nDeployment, Optimisation & AI Safety\n*(Weeks 25–32)*",
                "FastAPI serving, Containerisation (Docker), Latency & Caching, Observability, Guardrails, Privacy, Red-Teaming & Governance.",
                "Shipped single-worker FastAPI + React + Docker/Nginx, `Semaphore(1)` + 55 RPM throttling, Two-Tier Exact+Semantic Cache, DPDP Act PII masker & Right to Erasure, **Langfuse-style SQLite Span Tracing**, and **20/20 Red-Team Hardening**.",
            ],
        ],
        col_widths_in=[1.35, 2.05, 3.60],
        font_size=8.6,
    )

    add_callout(
        doc,
        "Track B Capstone Grading Rubric Alignment (100% Coverage)",
        "• **Core GenAI Engineering (30%):** 4-way Retrieval Ablation (`R1–R4`), 3-way Prompting (`P1–P3`), 6,059 section-aware chunks, deterministic ETL, Cross-Encoder reranking + `.gov.in` fallback.\n"
        "• **Agentic Architecture & Tooling (25%):** 7-node LangGraph (`Planner -> Executor -> Synthesizer -> Critic`), 5 Pydantic tools, 1-shot JSON repair (`5/5`), fault-injection fallback (`3/3`), HITL enforcement (`4/4`), live Gmail SMTP action.\n"
        "• **Safety, Privacy & Reliability (20%):** DPDP PII masking (`3/3`), Prompt-Injection/Fraud/CAPTCHA-Bypass shield (`20/20` after hardening), untrusted evidence delimiters, `Semaphore(1)` + 55 RPM + TLS CA verification.\n"
        "• **Product UX, Observability & Delivery (25%):** React Civic UI, 6-language voice I/O, RBAC Persona Login, Langfuse Trace Explorer + JSON/MD/CSV exports, 21 unit/API tests + 9 live E2E tests, Docker packaging.",
        accent_hex=HEX_GREEN,
        fill_hex=HEX_LIGHT_GREEN,
    )

    # =========================================================================
    # SECTION 2: TECH STACK — IIT KGP PROVIDED VS EXTERNAL / TEAM BUILT
    # =========================================================================
    add_h1(doc, "2. Complete Tech Stack: What IIT Provided vs. What We Built", page_break_before=True)
    add_para(
        doc,
        "A huge strength of our engineering design is **zero paid third-party SaaS lock-in**. We strictly built on top of the two hosted "
        "inference endpoints provided by IIT Kharagpur Track B and surrounded them with lightweight, battle-tested open-source Python and "
        "TypeScript libraries that run reproducibly on a standard laptop or Docker host."
    )
    add_figure(
        doc,
        DIAG_DIR / "01_layered_tech_stack.png",
        "Figure 1: Layered Technology Stack — Color-coded by IIT KGP Provided Infrastructure (Orange), Team/Open-Source Stack (Blue/Purple), and Live External Services (Green).",
        width_in=6.85,
    )

    add_styled_table(
        doc,
        headers=["Component", "Exact Technology / Version", "Provenance", "Why We Chose It"],
        rows=[
            [
                "**Primary LLM**",
                "`Qwen/Qwen3-8B` (OpenAI-compatible REST API, 8,192 context window)",
                "**IIT KGP Provided** (Hosted VM + `llm-ca.crt`)",
                "Mandatory Track B model; natively supports `chat_template_kwargs: {enable_thinking: False}` for fast, deterministic JSON & answers.",
            ],
            [
                "**Embedding Model**",
                "`bge-small-en-v1.5` (384-dim dense vectors, 512 max tokens)",
                "**IIT KGP Provided** (VM02 + `vm02-ca.crt`)",
                "Mandatory Track B embedding server; compact 384-dim vectors allow all 6,059 chunks to fit in **~9 MB RAM** (`embeddings.npy`)!",
            ],
            [
                "**Agent Orchestrator**",
                "**LangGraph** (`StateGraph`) + **Pydantic v2**",
                "Open-Source (Team Built)",
                "Provides explicit cyclic state transitions (Crucial for our **Critic -> Synthesizer 1-loop revision**) and strict typed state passing.",
            ],
            [
                "**Hybrid Search & Reranker**",
                "`rank-bm25` (BM25Okapi) + **NumPy** cosine dot-product + `sentence-transformers` CPU **CrossEncoder** (`cross-encoder/ms-marco-MiniLM-L-6-v2`)",
                "Open-Source (Team Built)",
                "Zero external vector DB container overhead; sub-35ms hybrid search + local CPU joint-attention reranking with calibrated `[0..1]` confidence scores.",
            ],
            [
                "**Backend API Server**",
                "**FastAPI** + **Uvicorn** (`--workers 1`) + `httpx` (async) + `sse-starlette`",
                "Open-Source (Team Built)",
                "Async I/O with live SSE streaming; single worker guarantees our process-wide `asyncio.Semaphore(1)` strictly obeys IIT's 1-active-request limit.",
            ],
            [
                "**Database & Cache**",
                "**SQLite 3 (WAL mode)** (`data/jansahayak.db`)",
                "Stdlib / Local Disk",
                "Stores 649 schemes, 7,724 FAQs, 51 ministries, sessions, messages, grievances, Langfuse spans, two-tier cache & email outbox with ACID durability.",
            ],
            [
                "**Frontend Web App**",
                "**React 18** + **TypeScript** + **Vite 5** + **Tailwind CSS** + `lucide-react`",
                "Open-Source (Team Built)",
                "Fast, responsive Civic GovTech SPA with SSE streaming, searchable 649-scheme catalog, RBAC login, and interactive Admin trace debugger.",
            ],
            [
                "**Live External Tools**",
                "`ddgs` (DuckDuckGo `.gov.in` fallback) • `gTTS` + `edge-tts` (6-lang MP3) • **Gmail SMTP TLS** (`smtplib`)",
                "External Live (Free / Zero-Key)",
                "Gives the agent genuine real-world reach: live `.gov.in` fallback, universal 6-language audio playback, and real confirmation emails to citizens.",
            ],
        ],
        col_widths_in=[1.25, 2.00, 1.35, 2.40],
        font_size=8.4,
    )

    # =========================================================================
    # SECTION 3: SYSTEM ARCHITECTURE & FULL-STACK CONNECTIVITY
    # =========================================================================
    add_h1(doc, "3. End-to-End System Architecture & How Frontend, Backend & Server Connect", page_break_before=True)
    add_para(
        doc,
        "Let's demystify how a user's browser click travels all the way through the frontend, backend API, LangGraph agent, IIT KGP VMs, "
        "and back to the screen in real time."
    )
    add_figure(
        doc,
        DIAG_DIR / "02_system_architecture.png",
        "Figure 2: End-to-End System Architecture & 7-Node LangGraph Compiled State Machine showing exact data paths, guardrails, tools, and storage layers.",
        width_in=6.9,
    )

    add_h2(doc, "3.1 Frontend <-> Backend <-> Server Connectivity Explained Simply")
    add_numbered(
        doc,
        [
            "**Browser SPA (`localhost:5173` in Dev / Port `80` Nginx in Docker):** The user interacts with React (`frontend/src/App.tsx`). All API calls go to relative `/api/...` paths. In local development, Vite's dev proxy (`vite.config.ts`) seamlessly forwards `/api/*` to `http://127.0.0.1:8000` (eliminating CORS headaches); in Docker, `nginx.conf` does the exact same reverse-proxy with SSE buffering disabled (`proxy_buffering off`).",
            "**Authentication & RBAC Handshake (`/api/auth/login`):** On startup, the user logs in as a persona. FastAPI validates the credentials (`backend/services/auth.py`) and returns an **HMAC-SHA256 signed Bearer token** (`24h` TTL). React stores this token in `localStorage` and attaches `Authorization: Bearer <token>` to every subsequent request. Admin endpoints (`/api/traces/*`, `/api/eval/*`) enforce a FastAPI `Depends(require_admin)` dependency—citizens receive HTTP `403 Forbidden` even if they call those URLs directly.",
            "**Single-Worker FastAPI Lifecycle (`backend/main.py`):** When Uvicorn starts (`uvicorn backend.main:app --host 127.0.0.1 --port 8000 --workers 1`), its lifespan hook initializes SQLite WAL tables and immediately spawns an async **background pre-warm task** that loads `embeddings.npy`, `bm25.pkl`, and the CPU Cross-Encoder model into RAM—eliminating the ~40s first-query cold start!",
            "**Real-Time SSE Streaming (`POST /api/chat/stream`):** Instead of making the user stare at a blank spinner for 10–20 seconds while multiple agent nodes run, `ChatWorkspace.tsx` opens a `fetch()` stream to `/api/chat/stream`. FastAPI yields Server-Sent Events (`event: status`, `event: guardrail`, `event: plan`, `event: tool_result`, `event: critic`, `event: done`) as each LangGraph node finishes. The React client normalizes `\r\n` CRLF framing, updates the live progress feed, and falls back gracefully to synchronous `POST /api/chat` if any network proxy drops SSE.",
            "**Outbound TLS Calls to IIT KGP VMs:** Inside `backend/gateway/`, `LLMGateway` (`httpx.AsyncClient`) and `EmbeddingClient` load the custom root CA certificates (`certs/llm-ca.crt` and `certs/vm02-ca.crt`) via `ssl.create_default_context(cafile=...)`—never using insecure `verify=False`—and serialize calls through a single process-wide `asyncio.Semaphore(1)`.",
        ],
    )

    # =========================================================================
    # SECTION 4: VANILLA RAG VS AGENTIC HYBRID RAG
    # =========================================================================
    add_h1(doc, "4. Are We Using RAG or Agentic RAG? (Key Viva Distinction)", page_break_before=True)
    add_callout(
        doc,
        "Short Answer for Mentor Viva",
        "JanSahayak AI implements **Agentic Hybrid RAG** — NOT vanilla static RAG. Retrieval is exposed as one of **5 dynamic tools** "
        "controlled by a stateful **LangGraph Planner -> Executor -> Synthesizer -> Critic** loop that decides *whether* to retrieve, "
        "*which tools* to chain, *when* to fall back to live `.gov.in` web search, and *whether* a draft answer must be revised before "
        "reaching the citizen.",
        accent_hex=HEX_PURPLE,
        fill_hex=HEX_LIGHT_BLUE,
    )
    add_styled_table(
        doc,
        headers=["Dimension", "Vanilla (Static) RAG", "JanSahayak AI (Agentic Hybrid RAG)"],
        rows=[
            [
                "**When Retrieval Runs**",
                "Blindly retrieves top-k chunks on EVERY message—even *'Namaskar, what can you do?'* (which causes hilarious wrong-scheme dumps!).",
                "**Planner** classifies 6 intents (`CONVERSATION_HELP`, `SCHEME_QA`, `ELIGIBILITY_CHECK`, `GRIEVANCE_DRAFT`, `GRIEVANCE_TRACK`, `OUT_OF_SCOPE`) and skips RAG completely for greetings or refusals.",
            ],
            [
                "**Multi-Step Tool Chaining**",
                "Single vector search -> single LLM call. Cannot run rules, call APIs, or take actions.",
                "**Executor** dynamically chains `search_schemes` -> deterministic `check_eligibility` -> `.gov.in` web fallback (if rerank score `< 0.35`) -> `draft_grievance` -> HITL `submit_or_track_grievance` + real SMTP email.",
            ],
            [
                "**Self-Verification / Critique**",
                "No post-generation check; if the LLM hallucinates a rupee amount or wrong citation, it goes straight to the user.",
                "**Critic Node** audits every answer (deterministic PII/citation checks + LLM groundedness/exclusion check) and loops back to **Synthesizer** (max 1 revision) if any flaw is found!",
            ],
            [
                "**Conversational Memory**",
                "Stateless single-turn Q&A; forgets user's age, income, or state on the next message.",
                "Structured `CitizenProfile` state persisted per session in SQLite; Planner incrementally merges new facts (`age=25`, `state=Maharashtra`) across turns.",
            ],
            [
                "**Safety & HITL Gates**",
                "Basic system prompt instruction (easily bypassed by injection).",
                "Deterministic pre-graph `InputGuardrail` + `<RETRIEVED_EVIDENCE_UNTRUSTED>` isolation + hard code-level `user_confirmed=True` gate on grievance submission.",
            ],
        ],
        col_widths_in=[1.45, 2.50, 3.05],
        font_size=8.6,
    )

    # =========================================================================
    # SECTION 5: DATA ETL, CHUNKING, EMBEDDING & HYBRID RETRIEVAL STRATEGY
    # =========================================================================
    add_h1(doc, "5. Data ETL, Chunking, Embedding & Hybrid RAG Deep Dive", page_break_before=True)
    add_figure(
        doc,
        DIAG_DIR / "03_hybrid_rag_pipeline.png",
        "Figure 3: Complete Offline Indexing Pipeline (Phase A) & Online Hybrid Retrieval + RRF + Cross-Encoder Reranking + .gov.in Fallback (Phase B).",
        width_in=6.9,
    )

    add_h2(doc, "5.1 Offline Phase A: ETL Enrichment & Section-Aware Chunking")
    add_para(
        doc,
        "Raw government CSVs (`updated_data.csv` with 649 Central schemes + `scheme_faqs.csv` with 7,724 official FAQs) are rich in "
        "information but messy for raw search. Naive fixed-character splitting (e.g., splitting every 500 characters) cuts eligibility "
        "rules in half and separates exclusion clauses from scheme names. Here is how our pipeline solves that:"
    )
    add_numbered(
        doc,
        [
            "**Deterministic Metadata Enrichment (`backend/retrieval/etl.py`):** Before chunking, regex parsers extract structured metadata directly into SQLite (`schemes_catalog`): `ministry_code` (mapped to 51 canonical CPGRAMS Ministry codes like `MOAFW`, `MSMEI`, `MOFIN`), `age_min`/`age_max`, `income_cap_inr`, `social_categories` (`SC/ST/OBC/EWS/Minority/Women/PwD`), `beneficiary_groups` (`Farmer/Student/Artisan/MSME`), and `dbt_scheme` boolean. Because this extraction is deterministic (zero LLM cost), it runs across all 649 schemes in under 2 seconds!",
            "**Section-Aware Chunking (`backend/retrieval/chunker.py`):** Each scheme is split cleanly along its natural semantic sections: `overview`, `benefits`, `eligibility_exclusions` (kept together intentionally so exclusions are never lost!), `documents_required`, `application_process`, and grouped `faq_group` (3 Q&As per chunk). Every chunk is prepended with a **contextual header**: `[Scheme: <Name> | Ministry: <Ministry> | Section: <Section>]` so the embedding model and LLM always know which scheme a snippet belongs to.",
            "**Hard <= 512-Token Guarantee for `bge-small-en-v1.5`:** Because BERT-based `bge-small-en-v1.5` silently truncates anything past 512 WordPiece tokens, our chunker computes a conservative token count `max(tiktoken_cl100k, word_count * 1.35 + punct_extra)` and targets **<= 440 tokens** (`35`-word sentence overlap when splitting long sections). Verification across all **6,059 generated chunks**: `max_tokens = 440`, **`0` chunks > 512**!",
            "**Dual-Index Construction (`scripts/ingest_data.py`):**\n"
            "  - **Dense Vector Index:** All 6,059 chunks were embedded via IIT KGP VM02 (`bge-small-en-v1.5`) in **379 batches of 16** with TLS CA verification (`vm02-ca.crt`), exponential backoff (`2/4/8s`), and checkpoint/resume safety. Vectors are L2-normalized (`v / ||v||`) and saved as `data/index/embeddings.npy` of shape `(6059, 384)` float32 (~9.3 MB—loads into RAM in ~20 ms!).\n"
            "  - **Sparse Lexical Index:** Built with `rank-bm25` (`BM25Okapi`) over tokenized chunk text with **2x title and tag boosting** so exact Indian scheme acronyms (`PM-KISAN`, `PMEGP`, `MUDRA`, `PMJAY`, `CSSS`) rank immediately at the top, saved as `data/index/bm25.pkl`.",
        ],
    )

    add_h2(doc, "5.2 Online Phase B: How Hybrid Retrieval, RRF, Reranking & Web Fallback Work")
    add_para(
        doc,
        "At query time, `backend/retrieval/hybrid_retriever.py` runs a 4-stage precision funnel:"
    )
    add_numbered(
        doc,
        [
            "**Stage 1 — Permissive Metadata Pre-Filtering:** If explicit filters (e.g., `ministry`, `dbt_only`) or citizen profile hints (`age`, `income`, `social_category`) are present, candidates are filtered **permissively**: a scheme with `null` age or income metadata is *never* excluded (avoiding false drops!). Furthermore, if filters leave `< 5` chunks or produce low confidence (`< 0.5`), the tool automatically relaxes filters and retries unfiltered.",
            "**Stage 2 — Parallel Sparse BM25 (Top-30) + Dense Cosine Search (Top-30):** BM25 computes exact lexical term-frequency/inverse-document-frequency scores (`~28 ms`). In parallel, the query is embedded via `bge-small-en-v1.5` (cached in SQLite `embedding_cache` so repeated queries take `0 ms` network time!) and multiplied against the `(6059, 384)` L2-normalized matrix via fast NumPy dot product (`embeddings @ q_vec`, `~3.2 ms`).",
            "**Stage 3 — Reciprocal Rank Fusion (RRF, $k = 60$):** BM25 scores (range 0–80) and Cosine similarities (range 0–1) cannot be added directly without fragile scaling. RRF fuses their *rank positions* cleanly: `RRF(d) = 1 / (60 + rank_BM25(d)) + 1 / (60 + rank_Dense(d))`. Documents ranked high by BOTH lexical and semantic engines shoot to the top of the **Top-20 candidates**.",
            "**Stage 4 — Local CPU Cross-Encoder Reranking (`cross-encoder/ms-marco-MiniLM-L-6-v2`):** While Bi-Encoders (`bge-small`) encode query and chunk separately for speed, a Cross-Encoder feeds `(query, chunk)` *together* through full self-attention across all 20 candidates, applying sigmoid calibration `1 / (1 + exp(-logit))` to yield a `[0, 1]` relevance probability and selecting the **Top-6 chunks**.",
            "**Stage 5 — Confidence-Gated Official `.gov.in` Web Fallback:** If the highest reranker probability `top_rerank_score < 0.35`, the Executor flags `low_confidence = True` and automatically invokes `web_search_gov_schemes` (DuckDuckGo strictly restricted to `.gov.in` / `.nic.in` domains), strips indirect prompt injections, and attaches a retrieval freshness timestamp.",
        ],
    )

    # =========================================================================
    # SECTION 6: ALL 5 AGENT TOOLS & HOW THE AGENT USES THEM
    # =========================================================================
    add_h1(doc, "6. All 5 Connected Agent Tools, Pydantic Schemas & HITL Safety", page_break_before=True)
    add_para(
        doc,
        "In `backend/agent/tools.py`, the agent interacts with the outside world exclusively through **5 strictly typed Pydantic v2 tools** "
        "(zero arbitrary shell execution, zero raw SQL from the LLM). Because 8B models can occasionally emit malformed JSON (trailing commas, "
        "missing braces, markdown fences, or invalid enum strings), every structured LLM call passes through our **3-tier `parse_and_repair_json` utility**: "
        "(1) Strip `<think>` & fences + direct Pydantic validation -> (2) Deterministic regex trailing-comma fix -> (3) **1-shot LLM Pydantic ValidationError repair** (`100%` recovery across 5/5 injected fault scenarios!)."
    )
    add_styled_table(
        doc,
        headers=["Tool Name", "Typed Inputs (Pydantic)", "What It Executes", "Guardrails & Auto-Chaining"],
        rows=[
            [
                "**1. `search_schemes`**",
                "`query`, `category?`, `ministry?`, `dbt_only?`, `beneficiary_group?`, `top_k (1..8)`",
                "Runs full R4 Hybrid Retrieval (BM25 + Dense + RRF + CPU Cross-Encoder) over 6,059 chunks.",
                "Always uses canonical English `query_en` for cross-lingual consistency; retries unfiltered if guessed filter drops confidence `< 0.5`.",
            ],
            [
                "**2. `check_eligibility`**",
                "`scheme_slug`, `citizen_profile` (age, gender, income, caste, occupation, BPL, PwD)",
                "Deterministic Python rule engine checking SQLite scheme age bounds, income cap, social category, women-only constraints, exclusions & document checklist.",
                "Planner is forbidden from guessing slugs; Executor **auto-chains** `check_eligibility` on real matched scheme slugs whenever `intent == ELIGIBILITY_CHECK`.",
            ],
            [
                "**3. `web_search_gov_schemes`**",
                "`query`, `max_results (1..5)`",
                "Live DuckDuckGo search restricted strictly to `site:gov.in OR site:nic.in` domains.",
                "Auto-triggered when `top_rerank_score < 0.35`; sanitizes untrusted web snippets against indirect prompt injection.",
            ],
            [
                "**4. `draft_grievance`**",
                "`scheme_name`, `ministry`, `issue_summary`, `beneficiary_reference_id?`, `state?`, `district?`, `pending_since?`",
                "Maps scheme to exact 51-Ministry CPGRAMS code, masks PII, formats formal complaint letter strictly `<= 2,000` chars, saves `DRAFT-XXXXXX` in SQLite.",
                "Sets `requires_user_confirmation = True` and pauses the agent (`hitl_paused = True`) so the UI opens the review modal.",
            ],
            [
                "**5. `submit_or_track_grievance`**",
                "`action ('submit' | 'track')`, `draft_id?`, `user_confirmed: bool`, `registration_number?`, `simulate_fault?`",
                "Submits confirmed draft to Mock CPGRAMS PGPortal API, dispatches **live Gmail SMTP HTML confirmation email** + Sandbox Outbox copy, and returns Assisted Handoff packet—or tracks an existing ticket ID.",
                "**Hard HITL Code Gate:** `if action == 'submit' and not user_confirmed: return blocked=True`! On 503/bad_json fault, gracefully degrades to Assisted Handoff packet.",
            ],
        ],
        col_widths_in=[1.30, 1.55, 2.15, 2.00],
        font_size=8.4,
    )

    # =========================================================================
    # SECTION 7: PROMPT ENGINEERING STRATEGY (P1 vs P2 vs P3)
    # =========================================================================
    add_h1(doc, "7. Prompt Engineering Strategy (P1 vs. P2 vs. P3) & Security Isolation", page_break_before=True)
    add_para(
        doc,
        "Prompting on an 8-billion-parameter model (`Qwen/Qwen3-8B`) requires discipline—long unfocused prompts waste context tokens "
        "and invite hallucinations. We systematically engineered and benchmarked **three distinct prompting architectures** (`backend/agent/prompts.py`) "
        "on identical retrieved R4 evidence across 30 stratified golden queries:"
    )
    add_bullets(
        doc,
        [
            "**P1 — Zero-Shot Direct Prompt (Baseline):** Simple 3-line system instruction asking Qwen3-8B to answer from context. Result: **93.3% accuracy**, but **only 10.0% citation adherence** and a dangerous **66.7% hallucination/unsupported-claim rate** (it routinely cited rupee amounts without `[1]` attribution or guessed missing rules).",
            "**P2 — Few-Shot Structured Prompt:** Added `<RETRIEVED_EVIDENCE_UNTRUSTED>` security delimiters, strict no-invention rules, and 2 high-signal few-shot examples (one factual PM-KISAN Q&A with `[1]` citation, one `NOT_ELIGIBLE` income-tax exclusion example). Result: Citations jumped **10% -> 100%** and hallucination plummeted **66.7% -> 6.7%**!",
            "**P3 — Grounded Planner-Executor-Synthesizer-Critic (Production Architecture):** Decomposed reasoning into specialized prompts:\n"
            "  1. `PLANNER_SYSTEM_PROMPT`: Strict JSON-only schema for intent classification (6 intents including `CONVERSATION_HELP`), profile extraction, and tool planning.\n"
            "  2. `SYNTHESIZER_SYSTEM_PROMPT`: Warm citizen-friendly prose capped at `<= 240 words` (clean mobile UX & clean vernacular translation), mandatory inline `[1]`, `[2]` citations, untrusted-evidence data-only rule, and explicit zero-fabrication refusal phrasing.\n"
            "  3. `CRITIC_SYSTEM_PROMPT`: 5-point independent auditor checking (a) Groundedness, (b) Inline citations, (c) Exclusion clauses, (d) PII/Safety, and (e) Non-existent scheme refusal—returning structured JSON `{passed, issues, needs_revision, revision_instructions}`.\n"
            "  4. `JSON_REPAIR_SYSTEM_PROMPT`: Compact 1-shot schema fixer triggered only if Pydantic validation fails.\n"
            "  Result: **100.0% accuracy, 100.0% citation adherence, 100.0% eligibility verdict accuracy, and 0.0% hallucination rate!**",
        ],
    )
    add_callout(
        doc,
        "Crucial Qwen3-8B Engineering Detail: Suppressing `<think>` Reasoning Bloat",
        "By default, `Qwen/Qwen3-8B` enters chain-of-thought reasoning mode (`<think>...</think>`), consuming 400–800 invisible tokens "
        "per call—which slows responses by 3x and truncates JSON outputs under our `max_tokens <= 1024` cap! We verified that the IIT KGP "
        "vLLM server natively supports `chat_template_kwargs: {\"enable_thinking\": False}` AND added a defensive regex `strip_thinking()` "
        "sanitizer in `LLMGateway` as a second layer of protection.",
        accent_hex=HEX_SAFFRON,
        fill_hex=HEX_LIGHT_SAFFRON,
    )

    # =========================================================================
    # SECTION 8: HANDLING TRACK B CONSTRAINTS (TOKENS, CONCURRENCY, LATENCY)
    # =========================================================================
    add_h1(doc, "8. Engineering Around Track B Constraints (Tokens, Rate Limits & Latency)")
    add_para(
        doc,
        "Production AI engineering is defined by how gracefully a system performs under real operational ceilings. Track B imposed strict "
        "infrastructure guardrails on our shared IIT Kharagpur VMs—here is how every single constraint is enforced in code:"
    )
    add_styled_table(
        doc,
        headers=["Track B Constraint", "Risk If Ignored", "Exact Engineering Control Implemented"],
        rows=[
            [
                "**1 Active LLM Request / Group Key**",
                "Parallel LLM calls trigger HTTP `429` or stall the shared vLLM queue for teammates.",
                "Single-worker Uvicorn (`--workers 1`) + process-wide singleton `asyncio.Semaphore(1)` inside `LLMGateway` (`backend/gateway/llm_client.py`).",
            ],
            [
                "**60 Requests / Min (RPM) Hard Cap**",
                "Burst traffic or eval loops exhaust quota and cause cascading timeouts.",
                "Client-side sliding-window throttle capped at **55 RPM** (leaving 5 RPM safety margin) + per-session FastAPI rate limiter (**15 RPM**) + **2s / 4s / 8s** exponential backoff on `429/5xx`.",
            ],
            [
                "**8,192 Total Context Window & `max_tokens <= 1024`**",
                "Long conversation history + 6 chunks causes HTTP `400 context_length_exceeded` crashes.",
                "`enforce_context_budget()` clamps `max_tokens <= 1024`, reserves `192` tokens headroom, drops oldest middle turns first, and trims context safely before any HTTP request is sent.",
            ],
            [
                "**512-Token Cap on `bge-small-en-v1.5`**",
                "Long scheme descriptions get silently truncated during embedding, losing exclusion rules at the bottom.",
                "Section-aware chunker guarantees **max 440 tokens** (`0/6,059` chunks > 512) and embeds in controlled batches of **16**.",
            ],
            [
                "**Self-Signed Campus TLS Certificates**",
                "Standard Python `httpx` throws `SSL: CERTIFICATE_VERIFY_FAILED`; disabling verify is a security violation.",
                "Explicit `ssl.create_default_context(cafile=...)` loading `certs/llm-ca.crt` and `certs/vm02-ca.crt` on every request.",
            ],
            [
                "**End-to-End Latency & Cold Starts**",
                "Loading Cross-Encoder on first chat request caused a ~40–58s cold delay; repeated queries burn redundant LLM seconds.",
                "(1) **Background Startup Pre-Warm** loads `HybridRetriever` + CPU `CrossEncoder` asynchronously on server boot (~1.6s warm retrieval).\n"
                "(2) **Two-Tier SQLite Response Cache**: Tier 1 Exact SHA-256 hash + Tier 2 Semantic cosine similarity `>= 0.96` (24h TTL) returns repeat Q&As in **`<50 ms` & `0` LLM tokens**.\n"
                "(3) **SQLite Embedding Cache** avoids re-calling VM02 for repeated query strings.",
            ],
        ],
        col_widths_in=[1.55, 1.95, 3.50],
        font_size=8.5,
    )

    # =========================================================================
    # SECTION 9: MULTILINGUAL & VOICE ARCHITECTURE
    # =========================================================================
    add_h1(doc, "9. Multilingual & 6-Language Voice Architecture", page_break_before=True)
    add_para(
        doc,
        "A subtle trap in multilingual RAG is **retrieval drift**: because `bge-small-en-v1.5` is an English embedding model, feeding raw "
        "Hindi or Tamil text directly into the retriever yields poor vector matches and inconsistent schemes across languages! We solved "
        "this cleanly with an **English-Pivot Architecture** (`backend/gateway/translation_client.py`):"
    )
    add_numbered(
        doc,
        [
            "**Unicode Script & Hinglish Detection:** Deterministic Unicode range checks instantly distinguish Devanagari (Hindi vs. Marathi via Marathi-specific markers like `ळ`, `मला`, `तू`, `कसे`), Bengali (`\u0980-\u09FF`), Tamil (`\u0B80-\u0BFF`), Telugu (`\u0C00-\u0C7F`), and Romanized Hinglish keywords (`kya`, `yojana`, `paise`, `patrata`). Zero LLM tokens spent on detection!",
            "**Canonical English Pivot (`to_english`):** Non-English queries are translated into crisp English (`query_en`) once. **Crucial Consistency Rule:** `search_schemes` ALWAYS executes using `query_en`, ensuring that the same eligibility question asked in English, Hindi, or Tamil retrieves the **exact same schemes and citations**.",
            "**Zero-Echo Output Localization (`from_english`):** After Synthesizer + Critic approve the grounded English answer (kept concise at `<= 240` words), `from_english()` translates it into the target language while strictly preserving scheme names, INR amounts, and markdown citation links `[1](https://...)`. We explicitly simplified our translation prompt after testing caught `Qwen3-8B` echoing verbose system instructions in Tamil!",
            "**6-Language Voice Input (STT) & Server-Side Audio Playback (TTS):**\n"
            "  - **Voice Input (STT):** Browser Web Speech API (`SpeechRecognition`) configured dynamically for `en-IN`, `hi-IN`, `mr-IN`, `bn-IN`, `ta-IN`, `te-IN` streams spoken transcripts right into the chat composer.\n"
            "  - **Voice Output (TTS):** Early testing showed Windows/Linux browsers frequently lack installed OS voice packs for Tamil/Marathi/Hindi. We solved this permanently with a zero-key server endpoint **`POST /api/voice/tts`** (`backend/api/routes_voice.py`) that strips markdown/URLs, auto-detects the actual reply script, synthesizes crisp MP3 audio via **`gTTS` primary + `edge-tts` fallback**, and caches up to 64 MP3 clips in an in-memory LRU cache for instant replay!",
        ],
    )

    # =========================================================================
    # SECTION 10: LIVE END-TO-END WALKTHROUGH (MUMBAI MRO MANUFACTURING LOAN)
    # =========================================================================
    add_h1(doc, "10. Live Step-by-Step Request Walkthrough (Real Captured Execution)", page_break_before=True)
    add_para(
        doc,
        "To make every concept concrete for both teammates and our mentor, we executed the **exact real-world citizen prompt** requested "
        "by the team against our live `Qwen/Qwen3-8B` + `bge-small-en-v1.5` pipeline and captured the full execution trace (`data/live_walkthrough_capture.json`, "
        f"Trace ID **`{capture['trace_id']}`**):"
    )
    add_callout(
        doc,
        "Live Citizen Prompt Tested",
        f"\"{capture['prompt']}\"",
        accent_hex=HEX_NAVY,
        fill_hex=HEX_LIGHT_BLUE,
    )

    add_figure(
        doc,
        DIAG_DIR / "04_architect_swimlane_dfd.png",
        f"Figure 4: Enterprise Solutions Architect Swimlane Data Flow & Validation Blueprint for Trace {capture['trace_id']} — Showing all 5 planes, exact LLM/Embedding/Tool/DB connections, numbered hops [1..16], and every block's Validation Contract!",
        width_in=6.95,
    )

    add_h2(doc, "10.1 Exact Step-by-Step Execution Breakdown (All 9 Langfuse Spans)")
    span_rows = []
    for sp in capture["spans"]:
        toks = sp.get("tokens") or {}
        t_str = f"{toks.get('prompt', 0)}p + {toks.get('completion', 0)}c" if toks.get("total", 0) > 0 else "0"
        out_summary = ""
        nm = sp["name"]
        if "InputGuardrail" in nm:
            out_summary = "0 PII detected; Injection/Fraud Shield = SAFE (blocked=False)."
        elif "LanguagePivot" in nm:
            out_summary = "Detected `en`; passed straight through (0 translation tokens)."
        elif "Planner" in nm:
            out_summary = "Intent=`ELIGIBILITY_CHECK`; extracted `age=25, gender=male, state=Maharashtra, occ='Small parts manufacturing'`; planned `search_schemes(top_k=6)`; valid JSON on 1st attempt."
        elif "Executor" in nm:
            out_summary = "Ran 3 tools: `search_schemes` (6 chunks, top_rerank=0.0038), auto-chained `check_eligibility(nssw)`, and auto-triggered `web_search_gov_schemes` (.gov.in fallback). *(Note: ~38s of 41.4s was standalone CLI cold-loading CrossEncoder; warm FastAPI server runs in ~1.6s!)*"
        elif "Synthesizer" in nm and sp["input"].get("revision_round") == 0:
            out_summary = "Round 0 draft (967 chars): Smartly excluded women-only `nssw` for male user & recommended **PM Vishwakarma**, but attributed loan amounts & documents loosely to `[2]`."
        elif "Critic" in nm and sp["status"] == "needs_revision":
            out_summary = "**CAUGHT ATTRIBUTION BUG LIVE!** Flagged that ₹1,00,000 / ₹2,00,000 loan & Ration card were not in chunk `[2]` -> triggered 1 revision loop!"
        elif "Synthesizer" in nm and sp["input"].get("revision_round") == 1:
            out_summary = "Round 1 revised draft (1,024 chars): Fixed inline citations accurately (`[2]` eligibility, `[6]` ₹1L+₹2L loan tranches, `[4]` required documents)!"
        elif "Critic" in nm and sp["status"] == "ok":
            out_summary = "Deterministic re-verification **PASSED** (0 PII, valid citations, max-1 revision cap respected)."
        elif "OutputLocalizer" in nm:
            out_summary = "Target `en`; persisted session profile, messages, 9 spans & Two-Tier Cache entry."

        span_rows.append([
            f"`{sp['span_id']}`",
            nm,
            sp["type"],
            f"{sp['duration_ms']:.1f} ms",
            t_str,
            out_summary,
        ])

    add_styled_table(
        doc,
        headers=["Span", "Node / Operation", "Type", "Duration", "Tokens", "What Actually Happened"],
        rows=span_rows,
        col_widths_in=[0.62, 1.35, 0.72, 0.78, 0.80, 2.73],
        font_size=8.1,
    )

    add_h2(doc, "10.2 Real Planner JSON Output & Retrieved Chunk Scoreboard")
    planner_snippet = json.dumps(
        {
            "intent": capture["planner_output"]["intent"],
            "profile_updates": capture["planner_output"]["profile_updates"],
            "tool_calls": [
                {
                    "tool_name": "search_schemes",
                    "arguments": {"query": "Hi, I am a 25 year old male looking for Loan...", "top_k": 6},
                }
            ],
            "reasoning": capture["planner_output"]["reasoning"],
        },
        indent=2,
    )
    add_code_block(doc, "Real Captured Planner Output (SPN-03 — Notice 'Mumbai' Automatically Inferred as state: 'Maharashtra'!)", planner_snippet)

    chunk_rows = []
    for idx, ch in enumerate(capture["retrieved_chunks"], start=1):
        sc = ch["scores"]
        chunk_rows.append([
            f"[{idx}]",
            f"**{ch['scheme_name']}**\n`{ch['scheme_slug']}`",
            ch["section"],
            f"{sc['bm25']:.2f}",
            f"{sc['dense']:.4f}",
            f"{sc['rrf']:.5f}",
            f"{sc['rerank']:.4f}",
        ])
    add_styled_table(
        doc,
        headers=["Cite", "Retrieved Scheme", "Section", "BM25", "Dense", "RRF", "Rerank"],
        rows=chunk_rows,
        col_widths_in=[0.42, 2.38, 1.15, 0.70, 0.75, 0.80, 0.80],
        font_size=8.3,
    )

    add_callout(
        doc,
        "Three Amazing Engineering Insights From This Single Live Trace (Great Viva Talking Points!)",
        "1. **Why Hybrid Search Matters (Look at BM25 vs. Dense above!):** The user wrote *\"nuts, bolts and other MRO parts\"*—words that never appear in official scheme titles, so **BM25 scored `0.00`** for both **PM Vishwakarma** and **PMEGP**! Meanwhile, **Dense `bge-small-en-v1.5`** scored them `0.7419`, `0.7343`, and `0.7223` semantically, rescuing both MSME schemes into the Top-6!\n"
        "2. **Why Agentic Reasoning Beats Blind Top-1 RAG:** Chunk `[1]` was *New Swarnima Scheme For Women* (matched BM25 because its FAQ says *'21 years old entrepreneur'*). Because the Planner extracted `gender: male` and `check_eligibility` surfaced `'The applicant must be a Female'`, the Synthesizer **refused to recommend the women-only scheme** and selected **PM Vishwakarma**!\n"
        "3. **Live Proof Our Critic Loop Works:** In Round 0 (`SPN-05`), Qwen3-8B sloppily attached `[2]` to the ₹1L/₹2L loan and Ration card facts. The **Critic (`SPN-06`) caught this live**, rejected the draft, and forced a **1-shot revision (`SPN-07`)** that corrected citations accurately to `[2]`, `[4]`, and `[6]`!",
        accent_hex=HEX_SAFFRON,
        fill_hex=HEX_LIGHT_SAFFRON,
    )

    add_code_block(
        doc,
        f"Exact Final Grounded Response Delivered to Citizen (Trace {capture['trace_id']})",
        capture["final_answer"],
    )

    # =========================================================================
    # SECTION 11: LANGFUSE-STYLE TRACES & QUANTITATIVE EVALUATION MATHEMATICS
    # =========================================================================
    add_h1(doc, "11. Langfuse-Style Observability & How Every Eval Metric Is Calculated", page_break_before=True)
    add_h2(doc, "11.1 How Our Langfuse-Style Structured Tracing Works")
    add_para(
        doc,
        "Every single chat request generates a globally unique Trace ID (`TRC-XXXXXXXXXX`) persisted in SQLite (`traces` table) with "
        "a nested JSON array of typed waterfall spans (`SPN-01` .. `SPN-N`). Each span records `span_id`, `name`, `type` (`GUARDRAIL | LLM | RETRIEVAL | TOOL`), "
        "`start_offset_ms`, `duration_ms`, `status`, structured `input`, structured `output`, `tokens {prompt, completion, total}`, and `error`. "
        "Inside the **Admin Trace Explorer** tab, Admins can inspect every span visually, inspect cache hit rates, or download any single trace "
        "(or all traces) as **Structured JSON**, **Readable Markdown**, or **Tabular CSV** for offline debugging."
    )

    add_h2(doc, "11.2 Exact Evaluation Formulas + Step-by-Step Worked Numerical Examples")
    add_para(
        doc,
        "In a mentor viva, you may be asked: *\"You report 95.9% Recall@5, 0.925 MRR@10, and 0.933 NDCG@5—how are those actually computed?\"* "
        "Here is the exact math from `eval/run_retrieval_eval.py` and `eval/run_prompt_eval.py`, explained with simple worked examples:"
    )

    add_h3(doc, "A. Retrieval Metrics (Evaluated on 73 Unique-Scheme Queries in `eval/golden_dataset.json`)")
    add_para(
        doc,
        "Suppose we evaluate 3 test queries (`Q1`, `Q2`, `Q3`) and look at the unique scheme slugs ranked by our retriever:"
    )
    add_bullets(
        doc,
        [
            "**Q1** (gold = `pm-kisan`): Retriever ranks `[pm-kisan, pmfby, kcc, ...]` -> Gold found at **Rank 1**.",
            "**Q2** (gold = `pmegp`): Retriever ranks `[mudra, pmv, pmegp, ...]` -> Gold found at **Rank 3**.",
            "**Q3** (gold = `csss-cus`): Retriever ranks `[nsp-1, nsp-2, nsp-3, nsp-4, nsp-5, csss-cus]` -> Gold found at **Rank 6** (missed Top-5!).",
        ],
    )
    add_styled_table(
        doc,
        headers=["Metric", "Exact Formula Used in Code", "Worked Calculation on Q1, Q2, Q3", "Intuition (Plain English)"],
        rows=[
            [
                "**Recall@K**\n*(Hit Rate @ 3, 5, 10)*",
                "`(Number of queries with gold scheme in top K) / N`",
                "• **Recall@3:** Q1 (rank 1 = hit), Q2 (rank 3 = hit), Q3 (rank 6 = miss) -> `2 / 3 = 66.7%`\n• **Recall@5:** `2 / 3 = 66.7%`\n• **Recall@10:** `3 / 3 = 100.0%`",
                "\"Did the right government scheme even make it into the top K chunks we hand to the LLM?\"",
            ],
            [
                "**MRR@10**\n*(Mean Reciprocal Rank)*",
                "`(1 / N) * Sum_{i=1..N} (1 / rank_i)` *(0 if rank > 10)*",
                "• Q1: `1/1 = 1.000`\n• Q2: `1/3 = 0.333`\n• Q3: `1/6 = 0.167`\n• **MRR@10** = `(1.000 + 0.333 + 0.167) / 3 = 0.500`",
                "\"How close to the #1 spot did the right scheme land?\" Rewards putting the best scheme at rank 1 instead of rank 5!",
            ],
            [
                "**NDCG@5**\n*(Normalized Discounted Cumulative Gain)*",
                "`DCG@5 = Sum_{pos=1..5} rel_pos / log2(pos + 1)`\n`NDCG@5 = DCG@5 / IDCG@5` *(here `IDCG@5 = 1 / log2(2) = 1.0`)*",
                "• Q1 (rank 1): `1 / log2(2) = 1.000`\n• Q2 (rank 3): `1 / log2(4) = 1 / 2 = 0.500`\n• Q3 (not in top 5): `0.000`\n• **NDCG@5** = `(1.000 + 0.500 + 0.000) / 3 = 0.500`",
                "Like MRR, but uses a smoother logarithmic penalty (`log2(rank+1)`) so rank 2 (`0.631`) and rank 3 (`0.500`) retain graded credit.",
            ],
        ],
        col_widths_in=[1.15, 1.85, 2.15, 1.85],
        font_size=8.3,
    )

    add_h3(doc, "B. Prompting & Generation Metrics (Evaluated on 30 Stratified Queries across 5 Categories)")
    add_bullets(
        doc,
        [
            "**Answer Accuracy:** For `scheme_qa` / `faq` / `multilingual`, checks if `>= 50%` of ground-truth `expected_keywords` appear in the answer. For `eligibility`, checks exact verdict match (`ELIGIBLE / NOT_ELIGIBLE / NEEDS_MORE_INFO`). For `refusal`, verifies explicit refusal language (`not found`, `cannot`, `official`).",
            "**Citation Adherence:** Regex `\\[\\d+\\]` checks that every non-refusal grounded answer contains at least one inline citation linking back to numbered evidence chunks.",
            "**Hallucination / Unsupported Claim Rate:** Flags an answer as hallucinated if (a) a `NOT_ELIGIBLE` citizen is wrongly told `ELIGIBLE`, (b) a refusal query fabricates a scheme instead of refusing, OR (c) a scheme answer quotes rupee amounts (`₹` / `Rs.`) *without* an inline citation `[1]`, `[2]`! Example: In `P1`, 20 of 30 answers gave uncited rupee figures or missed citations -> `20 / 30 = 66.7%` unsupported rate; in `P3`, `0 / 30 = 0.0%`!",
        ],
    )

    add_h2(doc, "11.3 Real Verified Quantitative Benchmark Results")
    add_figure(
        doc,
        DIAG_DIR / "05_eval_benchmarks.png",
        "Figure 5: Visual Summary of All 4 Quantitative Track B Evaluation Suites (Real Live Runs on Qwen/Qwen3-8B + bge-small-en-v1.5).",
        width_in=6.85,
    )

    # Table 1: Retrieval Ablation
    r_rows = [
        [
            f"**{c['id']}**",
            c["name"],
            f"{c['recall_at_3']*100:.1f}%",
            f"**{c['recall_at_5']*100:.1f}%**",
            f"{c['recall_at_10']*100:.1f}%",
            f"**{c['mrr_at_10']:.3f}**",
            f"{c['ndcg_at_5']:.3f}",
            f"{c['avg_latency_ms']:.1f} ms",
        ]
        for c in ret_rep["configs"]
    ]
    add_styled_table(
        doc,
        headers=["ID", "Retrieval Configuration (73 Golden Queries)", "R@3", "R@5", "R@10", "MRR@10", "NDCG@5", "Avg Lat."],
        rows=r_rows,
        col_widths_in=[0.45, 2.55, 0.62, 0.65, 0.65, 0.70, 0.68, 0.70],
        font_size=8.3,
    )
    add_para(
        doc,
        "**Key Ablation Takeaway:** `R3` (Hybrid RRF) achieves the highest overall Recall@5 (**95.9%**) and MRR@10 (**0.925**) at only **31.7 ms**, "
        "beating both BM25-only (93.2%) and Dense-only (94.5%). Adding the CPU Cross-Encoder (`R4`) maintains **95.9% Recall@5** and gives us "
        "calibrated `[0, 1]` relevance probabilities needed to detect fabricated schemes (`RT-20: 0.280`) and trigger `.gov.in` web fallback.",
        size=9.5,
    )

    # Table 2: Prompt Comparison
    p_rows = [
        [
            f"**{s['id']}**",
            s["name"],
            f"**{s['answer_accuracy']*100:.1f}%**",
            f"{s['citation_adherence']*100:.1f}%",
            f"**{s['hallucination_rate']*100:.1f}%**",
            f"{s['eligibility_accuracy']*100:.1f}%",
            f"{s['avg_latency_s']:.2f}s",
            f"{int(s['avg_tokens']):,}",
        ]
        for s in prm_rep["strategies"]
    ]
    add_styled_table(
        doc,
        headers=["ID", "Prompt Strategy (Fixed Qwen3-8B, 30 Qs)", "Accuracy", "Citations", "Halluc.", "Elig. Acc", "Avg Lat.", "Avg Tok"],
        rows=p_rows,
        col_widths_in=[0.45, 2.25, 0.72, 0.72, 0.72, 0.72, 0.72, 0.70],
        font_size=8.3,
    )

    # Table 3: Agent Reliability + Red-Team Summary + Failure Taxonomy
    ft_rows = [
        [
            f"**{f['code']}**",
            f["category"],
            str(f["count"]),
            f["mitigation"],
        ]
        for f in rt_rep["failure_taxonomy"]
    ]
    add_h2(doc, "11.4 Failure Taxonomy (F1–F6) & Real Engineering Bugs Caught During Build")
    add_styled_table(
        doc,
        headers=["Code", "Failure Class", "Residual Count", "Implemented Engineering Mitigation"],
        rows=ft_rows,
        col_widths_in=[0.55, 2.15, 0.90, 3.40],
        font_size=8.4,
    )

    add_callout(
        doc,
        "Real Production Engineering Bugs We Caught & Fixed (Impressive Viva Evidence!)",
        "• **SSE CRLF Framing Bug:** `sse-starlette` emits `\\r\\n\\r\\n` on Windows while our initial frontend split on `\\n\\n`, silently dropping the final `done` event! Fixed with universal newline normalization + EOF buffer flush + sync fallback.\n"
        "• **58-Second Cold-Start Timeout:** Lazy-loading `CrossEncoder` on the first chat request caused timeouts; moved to FastAPI async startup pre-warm.\n"
        "• **Cross-Lingual Scheme Drift & Tamil Prompt Echo:** Same scholarship query returned different schemes in EN vs. HI vs. TA, and Qwen3-8B echoed Tamil prompt headings. Fixed by locking retrieval strictly to `query_en` and simplifying the localization prompt.\n"
        "• **Greeting Triggering Sanitation Scheme:** Marathi greeting *'नमस्कार मला सांग तू काय काय करू शकतो'* retrieved NAMASTE Sanitation scheme! Added dedicated `CONVERSATION_HELP` intent bypassing RAG with `0` retrieved chunks.\n"
        "• **OS Speech Pack Failures:** Browser `speechSynthesis` failed on Windows for Hindi/Tamil. Built zero-key server `POST /api/voice/tts` (`gTTS` primary + `edge-tts` fallback + LRU MP3 cache) verified HTTP 200 across all 6 languages.\n"
        "• **Red-Team 80% -> 100% Hardening:** Initial 20-case red-team run caught 4 subtle gaps (indirect injection & obfuscated bypasses); hardened `injection.py` & `prompts.py` and re-verified **20/20 (100%)**.",
        accent_hex=HEX_BLUE,
        fill_hex=HEX_LIGHT_BLUE,
    )

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        doc.save(str(OUT_PATH))
        return OUT_PATH
    except PermissionError:
        alt = OUT_PATH.with_name(OUT_PATH.stem + "_v2.docx")
        doc.save(str(alt))
        return alt


if __name__ == "__main__":
    p = build_technical_doc()
    print(f"[OK] Built Technical Documentation: {p} ({p.stat().st_size:,} bytes)")
