# Overnight Autonomous Build Runbook & `.env` Pre-Flight Checklist
## **JanSahayak AI** — Preparation Guide for Unattended IDE Execution

---

## 1. What You MUST Provide Before Going to Sleep (Pre-Flight Checklist)

Everything in the workspace has been audited. Here is the exact status of what is **already present** vs. what **you need to add** before starting the overnight build:

### A. Already Present in Workspace (No Action Needed)
- `archive/schemes.csv` (`4,670` schemes; `649` Central across 51 Ministries)
- `archive/schemes_faqs.csv` (`51,435` FAQs; `7,724` Central FAQs)
- `Capstone_Overview_resources/API/VM02_Embeddings_Access/vm02-ca.crt` (Embeddings CA certificate)
- `Capstone_Overview_resources/API/VM02_Embeddings_Access/shared-embedding-key.txt` (Shared VM02 embedding key)
- Local runtimes verified: **Python 3.11.4**, **Node v22.17.0**, **Git 2.39.1**

### B. MANDATORY Items You Must Add Before Starting (Takes ~2 Minutes)
1. **Your Group's Inference CA Certificate (`vm04-ca.crt`, `vm05-ca.crt`, `vm06-ca.crt`, or `vm07-ca.crt`)**:
   - Create folder `certs/` in `Capstone_Project/` and copy your group's `.crt` file into `certs/` (e.g. `certs/vm04-ca.crt`).
   - Match your Group ID from `Track_B_Inference_API_Learner_Guide.docx.pdf`:
     - Groups `001–015` → `https://103.42.50.41:1031/v1` + `vm07-ca.crt`
     - Groups `016–030` → `https://103.42.50.41:1032/v1` + `vm06-ca.crt`
     - Groups `031–045` → `https://103.42.50.41:1033/v1` + `vm05-ca.crt`
     - Groups `046–065` → `https://103.42.50.41:1034/v1` + `vm04-ca.crt`
2. **Create `.env` from `.env.example`** in `Capstone_Project/.env` and fill in:
   - `LLM_BASE_URL` (your group's assigned URL from above)
   - `LLM_API_KEY` (your group's secret Qwen3-8B API key from coordinator)
   - `LLM_CA_CERT_PATH` (e.g. `certs/vm04-ca.crt`)
   - `EMBEDDING_API_KEY` (copy the key from `Capstone_Overview_resources/API/VM02_Embeddings_Access/shared-embedding-key.txt` into `.env` so all secrets live cleanly in `.env`)
3. **Ensure No Teammate Is Hitting the Group Key Simultaneously During the Overnight Run**:
   - Remember Track B's hard limit: **1 active request per group key**. While our `LLMGateway` queues our own requests with `Semaphore(1)` + retries on `429`, giving the overnight eval suite a quiet window ensures clean latency numbers!

### C. OPTIONAL Keys (100% NOT Required — Built-in Free Fallbacks Work Out-of-the-Box!)
| Env Variable | Purpose | Free Built-in Default If Left Blank |
| :--- | :--- | :--- |
| `TAVILY_API_KEY` | Faster web search fallback for schemes missing from local dataset | Free **`ddgs` (DuckDuckGo)** restricted to `site:myscheme.gov.in OR site:gov.in OR site:nic.in` |
| `BHASHINI_USER_ID` & `BHASHINI_ULCA_API_KEY` | Enterprise Indian language ASR/NMT/TTS | **Qwen3-8B multilingual English-pivot** + **Browser Web Speech API** (`hi-IN`, `mr-IN`, `bn-IN`, `ta-IN`, `te-IN`, `en-IN`) |
| `APISETU_CLIENT_ID` & `APISETU_API_KEY` | Live production CPGRAMS/UMANG submission | **Embedded Local CPGRAMS Mock Official API** + **Assisted Real-Portal Handoff Packet (`pgportal.gov.in`)** |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` | External cloud tracing mirror | **Built-in SQLite + React Trace Dashboard** (no cloud signup required!) |

### D. Quick 30-Second Pre-Flight Verification Command
Run this in PowerShell from `Capstone_Project` AFTER populating `.env` (replace `vm04-ca.crt`, URL, and key with your group's values) to verify network + certs before you sleep:
```powershell
curl.exe --cacert "certs\vm04-ca.crt" -H "Authorization: Bearer YOUR_GROUP_API_KEY" https://103.42.50.41:1034/v1/models
```
If it returns JSON containing `Qwen/Qwen3-8B`, you are 100% cleared for unattended overnight execution!

---

## 2. Autonomous Overnight Milestone Plan (Build → Test → Fix → Retest → Bring Live)

Antigravity IDE must execute these milestones sequentially, verifying every milestone's acceptance tests before advancing. If any test fails, diagnose, fix, and re-run until green (max 3 debug loops per issue; log any unresolvable external blocker cleanly in `BUILD_REPORT.md`).

| Milestone | Scope | Automated Verification Gate |
| :--- | :--- | :--- |
| **M0: Bootstrap & API Smoke Test** | Create project scaffold (`backend/`, `frontend/`, `scripts/`, `eval/`, `tests/`), `.gitignore`, `requirements.txt`, virtual env, install Python + Node deps, write & run `scripts/verify_apis.py` against `Qwen3-8B` and `bge-small-en-v1.5` (including verifying `<think>` toggle behavior!). | `python scripts/verify_apis.py` exits `0` confirming both endpoints + TLS certs + 384-dim embeddings + Qwen3 JSON response. |
| **M1: Data ETL, Chunking & Hybrid Index** | Implement `etl.py`, `chunker.py`, `database.py`, `embedding_client.py` (batch=16, checkpointed), `scripts/ingest_data.py`. Ingest all **649 Central schemes + 7,724 FAQs**. Build `data/jansahayak.db`, `embeddings.npy`, `bm25.pkl`. | `pytest tests/test_ingest.py` passes (649 schemes, 0 chunks > 512 tokens, all 51 ministries mapped, embeddings shape `(N, 384)`). |
| **M2: Phase 1 — Hybrid Retrieval, Reranker & Guardrails** | Implement `hybrid_retriever.py` (BM25 + Dense + RRF + `cross-encoder/ms-marco-MiniLM-L-6-v2`), `web_search.py` (`.gov.in` restricted), `pii.py` (Aadhaar/PAN/Phone/IFSC masker), `injection.py`, `cache.py` (Exact + Semantic), `llm_client.py` (`Semaphore(1)` + backoff `2/4/8s` + token budgeter + `<think>` stripper), `translation_client.py`. | `pytest tests/test_guardrails.py tests/test_retrieval.py` passes (flagship schemes PM-KISAN, Ayushman Bharat, PMAY, Mudra, PM Vishwakarma hit Top-3; PII 100% masked). |
| **M3: Phase 2 — LangGraph Multi-Agent & CPGRAMS Action Layer** | Implement `agent/state.py`, `agent/prompts.py` (`P1`, `P2`, `P3`), `agent/tools.py` (all 5 Pydantic tools + JSON repair), `agent/graph.py` (**Planner → Executor → Synthesizer → Critic** + HITL pause), `services/grievance_provider.py`, `services/mock_cpgrams_router.py`. | `pytest tests/test_agent_tools.py` passes (end-to-end scheme Q&A, eligibility verdict, grievance draft <=2000 chars, HITL gate blocks unconfirmed submit, confirmed submit returns ticket ID + tracks status, simulated 503 & broken JSON recover). |
| **M4: FastAPI Server, Rate Limiting & Trace Logger** | Wire `backend/main.py` + `routes_chat.py` (sync + SSE stream), `routes_schemes.py`, `routes_observability.py`, sliding-window rate limiter (`15 req/min`), and full SQLite Trace persistence. | `pytest tests/test_api.py` passes all REST/SSE contracts, rate-limit `429` test, DPDP `DELETE /api/sessions/{id}`, and trace logging. |
| **M5: Production React Frontend + Trace & Eval UI** | Build `frontend/` (React + Vite + TypeScript + Tailwind): Mobile-first Multilingual Voice/Text Chat (`useVoiceIO`), Citizen Profile Drawer, Eligibility Verdict & Document Checklist Cards, Interactive **Grievance HITL Review/Confirm Modal + Assisted Handoff Packet**, Scheme Explorer (649 schemes), and **Trace & Eval Dashboard**. | `npm run build` exits `0` with zero TS errors; live backend + frontend smoke test verifies UI loads and chat/grievance/trace APIs connect cleanly. |
| **M6: Track B Quantitative Evaluation Suite** | Create `eval/golden_dataset.json` (80 stratified queries verified against actual `schemes.csv` slugs & `schemes_faqs.csv`) and `eval/redteam_dataset.json` (20 adversarial tests). Run `eval/run_all_evals.py`: **Retrieval Ablation (`R1`–`R4`)**, **Prompting Comparison (`P1`–`P3`)**, **Agent Fault-Injection**, and **Red-Team Safety**. Save JSON + Markdown reports in `eval/reports/`. | All 4 benchmark reports generated with real, non-synthetic numbers; `/api/evals/summary` renders live charts in Eval Dashboard. |
| **M7: Model Card, Dockerization & Final Live Verification** | Write `docs/05_MODEL_CARD_AND_RESPONSIBLE_AI.md` (intended use, failure taxonomy from real evals, refusals, red-team results), `docker-compose.yml`, `README.md`, `start_local.ps1`. Run full `pytest` + live end-to-end verification (Phase 1 chat + Hindi query + Phase 2 grievance draft/confirm/track + Trace UI check). Write `BUILD_REPORT.md` summary for the morning! | All unit/integration tests green; live servers verified responding on localhost; `BUILD_REPORT.md` lists exact launch commands & benchmark scores. |

---

## 3. Master Overnight Prompt (Copy & Paste into Antigravity IDE Once `.env` Is Ready)

> **Tip**: Use the `/goal` slash command (or paste directly into a fresh session with workspace permissions granted) once you have copied your `vm0X-ca.crt` into `certs/` and filled `.env`.

```text
You are executing the autonomous overnight build of **JanSahayak AI**, our IIT Kharagpur GenAI & Agentic AI Track B Capstone Project.

First, read ALL four specification documents in `docs/`:
1. `docs/01_BRD_Product_Requirements.md`
2. `docs/02_TRD_Technical_Requirements.md`
3. `docs/03_Technical_Architecture.md`
4. `docs/04_Overnight_Build_Runbook_and_Env_Checklist.md`

Check `.env` and `certs/` first. Never print or commit secret API keys.

Execute Milestones M0 through M7 sequentially:
- **M0**: Scaffold repository, install dependencies in a local `.venv` and `frontend/`, run `scripts/verify_apis.py` to confirm live HTTPS connectivity (using CA certs—never `verify=False`) to `Qwen/Qwen3-8B` and `bge-small-en-v1.5`. Verify how the Qwen3-8B server handles `enable_thinking: False` and `<think>` stripping.
- **M1**: Build and run the resumable ingestion pipeline (`scripts/ingest_data.py`) over all 649 Central Government schemes in `archive/schemes.csv` and their 7,724 FAQs in `archive/schemes_faqs.csv`. Verify chunk token bounds (<=512 tokens), enriched metadata, SQLite catalog, BM25 index, and 384-dim embeddings.
- **M2–M3**: Build Phase 1 (Hybrid RAG: BM25 + Dense + RRF + local cross-encoder reranker, multilingual English-pivot, PII redactor, prompt-injection shield, two-tier cache, single-flight `Semaphore(1)` LLMGateway with 2/4/8s backoff) AND Phase 2 (LangGraph Planner -> Executor -> Synthesizer -> Critic with all 5 Pydantic tools, JSON/tool failure repair, restricted `.gov.in` web search fallback, HITL-gated CPGRAMS grievance drafting/submission/tracking, and embedded Mock CPGRAMS Official API + Assisted Handoff Packet).
- **M4–M5**: Build FastAPI backend + React/Vite/TypeScript/Tailwind mobile-first frontend with Voice I/O, Citizen Profile drawer, Eligibility & Document Readiness cards, Grievance HITL modal, Scheme Explorer, and the built-in Trace & Eval Dashboard.
- **M6**: Build the 80-query Golden Dataset (grounded strictly in real slugs/FAQs from `archive/`) and 20-query Red-Team suite, then run the full Track B evaluation suite (`R1–R4` Retrieval Ablation, `P1–P3` Prompting Strategy Comparison, Agent Fault-Injection, Red-Team Safety) and save report-ready JSON + Markdown tables in `eval/reports/`.
- **M7**: Generate `docs/05_MODEL_CARD_AND_RESPONSIBLE_AI.md`, `README.md`, `docker-compose.yml`, `start_local.ps1`, run the complete test suite (`pytest` + `npm run build` + live API smoke tests covering Phase 1 QA, Hindi query, Phase 2 HITL grievance submit/track, PII redaction, and Trace Dashboard), fix any failures, retest until green, and write a morning summary in `BUILD_REPORT.md` with exact benchmark numbers and how to launch the live app.
```
