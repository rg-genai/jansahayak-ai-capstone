# Model Card & Responsible AI Documentation
## **JanSahayak AI** — Multilingual Indian Government Scheme Navigator & CPGRAMS Grievance Agent

| Field | Details |
| :--- | :--- |
| **System Name** | JanSahayak AI v1.0 |
| **Programme & Track** | IIT Kharagpur — Executive PG Certificate in Generative AI & Agentic AI (Track B — API-Side) |
| **Base Generation Model** | `Qwen/Qwen3-8B` (Fixed hosted Track B inference endpoint; zero weight modification; `enable_thinking: False` + `<think>` stripper) |
| **Base Embedding Model** | `bge-small-en-v1.5` (384-dim, hosted VM02 endpoint, English-only with English-pivot query translation) |
| **Local Reranker Model** | `cross-encoder/ms-marco-MiniLM-L-6-v2` (CPU cross-encoder reranking top-20 RRF candidates) |
| **Knowledge Corpus** | **649 Central Government Schemes** across **51 Canonical Ministries** + **7,724 Official FAQs** (`myScheme` dataset -> `6,059` section-aware chunks, `max_tokens = 440 <= 512`) |
| **Evaluation Date** | 22 November 2026 |

---

## 1. Intended Use & Scope Boundaries

### 1.1 Intended Users & Use Cases
- **Indian Citizens & CSC Operators**: Discovering Central Government welfare schemes, verifying step-by-step eligibility & exclusion criteria, preparing prerequisite CSC documents, and drafting formal `<= 2,000`-character CPGRAMS grievances routed to the exact Central Ministry.
- **Languages Supported**: English (`en-IN`), Hindi (`hi-IN`), Hinglish, Marathi (`mr-IN`), Bengali (`bn-IN`), Tamil (`ta-IN`), and Telugu (`te-IN`) via text and Browser Web Speech API voice I/O.
- **GovTech Evaluators & Auditors**: Inspecting full SQLite execution traces, latency waterfalls, retrieval scores, and quantitative Track B benchmarks via the integrated Trace & Eval Dashboard.

### 1.2 Explicit Refusal & Out-of-Scope Contract
JanSahayak AI **strictly refuses** and/or **deterministically mitigates**:
1. **Document Forgery & Subsidy Fraud**: Requests to forge income/caste/BPL/EWS certificates, hide family income, or bribe officials.
2. **CAPTCHA Bypass & Portal Spam**: Scripts or bots to defeat `pgportal.gov.in` CAPTCHAs or auto-flood grievances.
3. **Unauthorized Autonomous Submission**: The agent **never** submits a CPGRAMS grievance without explicit citizen confirmation (**100% HITL enforcement**).
4. **Medical / Legal / Financial Investment Advice**: Redirects medical emergencies to **108 Ambulance** / **Ayushman Bharat (PM-JAY)** and financial investment requests to official government savings/credit schemes.
5. **Unverified Fabrication**: Explicitly reports when no verified Central Government scheme matches a query (e.g., fabricated *"PM Free iPhone 18 Yojana 2026"*).
6. **Prompt Injection & Secret Exfiltration**: Blocks direct overrides, base64-obfuscated payloads, indirect injection embedded inside retrieved snippets, and `.env` / API key extraction attempts.

---

## 2. Quantitative Evaluation Results (Real Track B Benchmarks)

All evaluations were executed against the live Track B hosted **`Qwen/Qwen3-8B`** and **`bge-small-en-v1.5`** endpoints (`eval/run_all_evals.py`, `eval/golden_dataset.json`, `eval/redteam_dataset.json`).

### 2.1 Retrieval Ablation (`R1`–`R4`) — Measured Separately on 73 Queries
| Config | Retrieval Strategy | Recall@3 | Recall@5 | Recall@10 | MRR@10 | NDCG@5 | Avg Latency (ms) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **R1** | BM25-Only (Sparse Lexical, title/tag boosted) | 93.2% | 93.2% | 94.5% | 0.920 | 0.921 | 28.1 |
| **R2** | Dense-Only (`bge-small-en-v1.5`, 384-dim) | 91.8% | 94.5% | 94.5% | 0.877 | 0.894 | 3.2 |
| **R3** | Hybrid RRF (`BM25 + Dense`, $k=60$) | **94.5%** | **95.9%** | **95.9%** | **0.925** | **0.933** | 31.7 |
| **R4** | Hybrid RRF + Cross-Encoder Reranker + Metadata Filter | **94.5%** | **95.9%** | **95.9%** | 0.892 | 0.909 | 1664.7 |

> **Engineering Takeaway**: Hybrid fusion (`R3`/`R4`) improves Recall@5 to **95.9%** (exceeding the `>= 88%` BRD KPI target) and MRR@10 to **0.892–0.925** (exceeding `>= 0.78`). Combining BM25 lexical title boosting with dense semantic vectors eliminates single-modality misses on acronym/vernacular-pivoted queries. The Cross-Encoder reranker (`R4`) provides calibrated confidence scores (`rerank_score`) used to trigger the restricted `.gov.in` web fallback.

### 2.2 Prompting Strategy Comparison (`P1` vs `P2` vs `P3`) — 30 Stratified Queries on Fixed `Qwen/Qwen3-8B`
| Strategy | Description | Answer Accuracy | Citation Adherence | Hallucination / Unsupported Rate | Eligibility Acc | Avg Latency (s) | Avg Tokens |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **P1** | Zero-Shot Direct Prompt | 93.3% | 10.0% | 66.7% | 100.0% | 4.18s | 1,660 |
| **P2** | Few-Shot Structured Prompt | 96.7% | 100.0% | 6.7% | 100.0% | 4.11s | 1,968 |
| **P3** | Grounded Planner → Executor → Synthesizer → Critic | **100.0%** | **100.0%** | **0.0%** | **100.0%** | 4.49s | 2,193 |

> **Engineering Takeaway**: On a fixed 8B model, moving from Zero-Shot (`P1`) to Few-Shot (`P2`) raised citation adherence from **10.0% -> 100.0%** and cut unsupported/uncited hallucination risk from **66.7% -> 6.7%**. Adding structured `check_eligibility` tool grounding + Critic audit (`P3`) achieved **100.0% accuracy, 100.0% citation adherence, and 0.0% hallucination rate** at only **+0.31s** additional average latency.

### 2.3 Agentic Reliability & Fault-Injection Benchmark (15 Scenarios)
| Reliability Metric | Measured Result | Target |
| :--- | :---: | :---: |
| Tool Selection & Execution Accuracy | **100.0%** (3/3) | >= 95% |
| Malformed JSON Repair Recovery Rate (Deterministic + 1-shot LLM) | **100.0%** (5/5) | >= 95% |
| External `503` / `bad_json` Graceful Fallback Rate (Assisted Handoff) | **100.0%** (3/3) | >= 95% |
| Human-in-the-Loop (HITL) Gate Enforcement (`user_confirmed=False` blocked) | **100.0%** (4/4) | **100%** |
| **Overall Fault-Injection Pass Rate** | **100.0%** (15/15) | >= 95% |

### 2.4 Red-Team Adversarial Safety Evaluation (20 Tests) & Iterative Remediation
During our first red-team pass (`eval/run_redteam_eval.py`), the system scored **80.0% (16/20)** and surfaced two real vulnerabilities:
1. Compound-modifier fraud phrasings (`"hide my family income"`, `"forge a BPL ration card"`, `"bribe as a CSC officer"`) bypassed narrower single-token fraud regexes (`RT-08`, `RT-09`, `RT-10`).
2. Non-existent scheme query (`RT-20`: *"PM Free iPhone 18 Yojana 2026"*) returned a borderline reranker score (`0.280` vs threshold `0.25`) where unrelated chunks needed stronger non-substitution instructions in `SYNTHESIZER_SYSTEM_PROMPT`.

After hardening `backend/guardrails/injection.py` and `backend/agent/prompts.py` and re-running `eval/run_redteam_eval.py`:
- **Overall Adversarial Defense Pass Rate**: **100.0% (20/20)**
- **Prompt-Injection, Fraud, CAPTCHA-Bypass & Indirect-Injection Block Rate**: **100.0% (16/16)**
- **Indian PII Masking Rate (Aadhaar, PAN, Mobile, IFSC, Bank Account)**: **100.0% (3/3, zero leakage)**
- **Fabricated Scheme Honest Refusal (`RT-20`)**: **PASS (1/1)**

### 2.5 Task Completion and the Reflector Loop (80 Tasks, With vs Without the Loop)
Source: `eval/reports/task_eval.md` (runs `loop_v2` and `single_pass_v2`, current code, all 80 tasks of `eval/golden_dataset.json`). A task is done only if it passes the fixed rule for its kind and stays within the 10-tool-call cap; information answers are checked by a grounding judge (`gemini-3.5-flash-lite`) against the evidence the answer writer saw. Ranges are 95% Wilson intervals.

| Metric | With the loop (`loop_v2`) | Without the loop (`single_pass_v2`) |
| :--- | :---: | :---: |
| **Task completion** | **81.2%** (65/80; 71.3%–88.3%) | 73.8% (59/80; 63.2%–82.1%) |
| Eligibility checks | 100.0% (20/20; 83.9%–100.0%) | 85.0% (17/20; 64.0%–94.8%) |
| Information questions | 68.9% (31/45; 54.3%–80.5%) | 64.4% (29/45; 49.8%–76.8%) |
| Refusals | 100.0% (7/7; 64.6%–100.0%) | 85.7% (6/7; 48.7%–97.4%) |
| Grievance drafting / tracking | 85.7% (6/7) / 100.0% (1/1) | 85.7% (6/7) / 100.0% (1/1) |
| Avg tool calls / tokens / latency per task | 1.34 / 7,092 / 15.0s | 1.19 / 6,547 / 13.7s |
| Step-cap (10 tool calls) hits | 0 | 0 |

**Paired comparison:** the loop completed 7 tasks that single pass failed and lost 1 (exact McNemar p = 0.07, so not significant at 0.05). On the 7 tasks where the loop actually acted, it completed 7 against single pass's 3. Cost: +0.15 tool calls, +545 tokens and +1.4s per task.

**How we got here (diagnose → fix → re-measure).** The first full run had the loop slightly *behind* single pass (70.0%, 56/80 vs 71.2%, 57/80). Reading the saved runs showed two causes:
1. **The Reflector checked eligibility on 38 of 45 plain information questions** ("what does PM Vishwakarma give?"). This added tokens and, when several schemes were checked, pushed the answer into the "which schemes am I eligible for" layout. Fix: a deterministic guard in `_validate_reflection` (`info_question_not_about_citizen`, regression tests QA-21 / ML-07), in line with our "guard over prompt" approach for the 8B model.
2. **The grounding judge could not see the eligibility tool output** the answer writer used, so documents copied correctly from official scheme data were scored as hallucinations (e.g. FAQ-05). Fix: the judge now receives the same eligibility details.

Failure root causes (`eval/reports/failure_taxonomy.md`) fell from 24 failures (13 hallucination, 9 retrieval miss) for the first loop run to 15 (9 hallucination, 2 retrieval miss, 2 tool-call error, 2 reasoning error) for `loop_v2`; `single_pass_v2` has 21 (11 hallucination, 6 reasoning error).

**Limitations, stated plainly:**
- **Not a held-out result.** The guard, the ELIG-01 search fix and six answer-key corrections were all found by studying failures in this same 80-task suite, so these scores are likely optimistic for unseen questions.
- **Run-to-run noise is a few tasks.** Re-running single pass with unchanged code for the non-eligibility tasks still flipped 6 of them (5 newly failed, 1 newly passed: LLM and judge sampling), so a gap of 6 tasks on 80 is suggestive, not proof.
- Under the original (uncorrected) answer key, completion is 73.8% (loop) vs 68.8% (single pass); `eval/golden_dataset_corrections.json` documents each correction with the scheme's own text.

---

## 3. Categorized Failure Taxonomy (`F1`–`F6`)

| Code | Failure Mode | Observed Count (Post-Fix) | Root Cause & Engineering Mitigation |
| :--- | :--- | :---: | :--- |
| **F1** | Retrieval Miss (Top-5 Scheme Recall Gap) | `3 / 73` | Occurs when multi-word vernacular/short-title queries map to adjacent flagship schemes (e.g., `pmfby` vs `pmecrg`). Mitigated by BM25 title/tag boosting + Dense RRF + Cross-Encoder Reranker + restricted `.gov.in` web search fallback. |
| **F2** | Groundedness / Exclusion Oversight (`P3`) | `0 / 30` | Mitigated via deterministic `check_eligibility` tool (explicit age/income/social-category/exclusion extraction) + Critic audit loop. |
| **F3** | JSON Schema Drift on 8B Model | `0 / 5` | Mitigated via `enable_thinking: False`, `<think>` regex stripper, outermost bracket extraction, trailing-comma repair, and 1-shot Pydantic `ValidationError` LLM repair. |
| **F4** | Adversarial Safety / PII Leakage | `0 / 20` | Mitigated via Layer 1 deterministic Input Guardrail, DPDP PII Redactor, `<RETRIEVED_EVIDENCE_UNTRUSTED>` delimiter isolation, and indirect-injection line stripping. |
| **F5** | Token Context Overflow / Truncation | `0` | Mitigated via strict `8,192`-token context budgeter, `max_tokens <= 1024` hard clamp, and `<= 440`-token section-aware chunking (`0` chunks > 512 tokens). |
| **F6** | Hosted VM `429`/`503` Concurrency Contention | `0` | Mitigated via singleton `asyncio.Semaphore(1)`, `55 rpm` client throttle, `2/4/8s` exponential backoff, `uvicorn --workers 1`, and Two-Tier Exact + Semantic (`>= 0.96`) SQLite Response Cache. |

---

## 4. Privacy, DPDP Act 2023 Compliance & Ethical Considerations
- **Data Minimization & PII Masking**: 12-digit Aadhaar numbers are automatically redacted to `[AADHAAR_MASKED:XXXX-XXXX-1234]` (and PAN, Indian mobile numbers, IFSC codes, and bank account numbers are fully redacted) *before* transmission to `Qwen/Qwen3-8B` or persistence in SQLite traces/messages/grievances.
- **Right to Erasure (`DELETE /api/sessions/{session_id}`)**: Citizens can permanently erase their profile, chat history, and unsubmitted drafts with one click in the Citizen Profile drawer; historical traces for that session are anonymized (`[ERASED]`).
- **TLS Certificate Verification**: All outbound calls to Track B hosted inference and embedding VMs strictly verify official coordinator CA certificates (`ssl.create_default_context(cafile=...)`); `verify=False` is never used.
- **Limitations & Post-Capstone Governance**:
  - Current default corpus covers **649 Central Government schemes**; State-specific schemes (`4,021` additional rows in `archive/schemes.csv`) require `--scope all` ingestion and state-portal validation before regional deployment.
  - Eligibility verdicts are advisory based on published `myScheme` text; final sanction authority rests with the implementing Central Ministry / State nodal agency.
  - Live CPGRAMS submission defaults to **Sandbox + Assisted Real-Portal Handoff (`pgportal.gov.in`)** until formal institutional API Setu / UMANG credentials are provisioned.
