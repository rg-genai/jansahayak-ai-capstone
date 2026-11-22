# Agentic Reliability & Fault-Injection Benchmark (15 Scenarios)

| Reliability Metric | Score | Target |
| :--- | :---: | :---: |
| Tool Selection & Execution Accuracy | **100.0%** | >= 95% |
| Malformed JSON Repair Recovery Rate | **100.0%** | >= 95% |
| External 503 / Bad JSON Graceful Fallback Rate | **100.0%** | >= 95% |
| Human-in-the-Loop (HITL) Gate Enforcement | **100.0%** | **100%** |
| Overall Scenario Pass Rate | **100.0%** (15/15) | >= 95% |

## Scenario Details
| ID | Category | Description | Result |
| :--- | :--- | :--- | :---: |
| `FI-01` | `json_repair` | Think tag + markdown fence + trailing comma | PASS |
| `FI-02` | `json_repair` | Prose preamble + valid JSON object | PASS |
| `FI-03` | `json_repair` | Invalid intent enum requiring 1-shot LLM repair | PASS |
| `FI-04` | `json_repair` | Missing closing brace requiring 1-shot LLM repair | PASS |
| `FI-05` | `json_repair` | Unquoted key / malformed tool_name requiring 1-shot LLM repair | PASS |
| `FI-06` | `hitl_enforcement` | Block unconfirmed submit for MOAFW (Pradhan Mantri Kisan Samman Nidh) | PASS |
| `FI-07` | `hitl_enforcement` | Block unconfirmed submit for MOHFW (Ayushman Bharat - Pradhan Mantri) | PASS |
| `FI-08` | `hitl_enforcement` | Block unconfirmed submit for MSMEI (PM Vishwakarma) | PASS |
| `FI-09` | `hitl_enforcement` | Block unconfirmed submit for MOFIN (Pradhan Mantri Mudra Yojana) | PASS |
| `FI-10` | `tool_fault_fallback` | CPGRAMS gateway fault injection: 503 | PASS |
| `FI-11` | `tool_fault_fallback` | CPGRAMS gateway fault injection: bad_json | PASS |
| `FI-12` | `tool_fault_fallback` | CPGRAMS gateway fault injection: missing_ticket | PASS |
| `FI-13` | `tool_accuracy` | search_schemes returns PM-KISAN #1 | PASS |
| `FI-14` | `tool_accuracy` | check_eligibility produces structured verdict & checklist | PASS |
| `FI-15` | `tool_accuracy` | Confirmed CPGRAMS submit -> track round-trip | PASS |
