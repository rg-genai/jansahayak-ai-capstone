# Task Completion and Tool Use (80-task suite)

- Tasks: `eval/golden_dataset.json`: scheme questions, FAQs, six Indian languages, eligibility checks, grievance drafting/tracking, and requests that must be refused.
- Runs: live retrieval settings; web fallback disabled (logged); grievance tools on the in-process mock CPGRAMS.
- A task is done only if it passes every rule for its kind (see `eval/score_task_eval.py`) and uses at most 10 tool calls. Grounding judge: `gemini-3.5-flash-lite`.
- 95% CIs are Wilson intervals; with ~80 tasks a difference of a few tasks is within noise.
- Answer-key corrections: 6 eligibility verdicts (ELIG-06, ELIG-10, ELIG-16, ELIG-17, ELIG-19, ELIG-20) are corrected in `eval/golden_dataset_corrections.json` (each with the scheme's own text). The original key is unchanged; completion is shown under both.
- `*_after_elig_fix` runs re-ran only the 20 eligibility tasks after the ELIG-01 fix (named-scheme searches no longer filtered by the citizen profile); `loop` and `single_pass` are the before-fix runs.
- `*_v2` runs re-ran all 80 tasks on the current code: the ELIG-01 fix plus a Reflector guard that stops eligibility checks on plain info questions (QA-21 / ML-07). Their answers are judged with the eligibility tool output the answer writer saw (before, the judge saw only the verdicts).
- **Not a held-out result.** The ELIG-01 fix, the Reflector guard and the answer-key corrections were all found by studying failures in this same 80-task suite, so the `*_after_elig_fix` and `*_v2` scores are likely optimistic. They show the fixes work on the cases that motivated them, not how the agent does on unseen questions; a fresh held-out task set is needed for that.

## Task completion

| Config | Completion (corrected key) | Completion (original key) | Pipeline errors | Status counts |
|---|---|---|---:|---|
| `loop` | **70.0%** (56/80; 95% CI 59.2%-78.9%) | **62.5%** (50/80; 95% CI 51.5%-72.3%) | 0 | {'ok': 66, 'awaiting_hitl_confirmation': 8, 'blocked_by_guardrail': 6} |
| `loop_after_elig_fix` | **100.0%** (20/20; 95% CI 83.9%-100.0%) | **70.0%** (14/20; 95% CI 48.1%-85.5%) | 0 | {'ok': 20} |
| `loop_v2` | **81.2%** (65/80; 95% CI 71.3%-88.3%) | **73.8%** (59/80; 95% CI 63.2%-82.1%) | 0 | {'ok': 66, 'awaiting_hitl_confirmation': 8, 'blocked_by_guardrail': 6} |
| `single_pass` | **71.2%** (57/80; 95% CI 60.5%-80.0%) | **66.2%** (53/80; 95% CI 55.4%-75.6%) | 0 | {'ok': 66, 'awaiting_hitl_confirmation': 8, 'blocked_by_guardrail': 6} |
| `single_pass_after_elig_fix` | **85.0%** (17/20; 95% CI 64.0%-94.8%) | **65.0%** (13/20; 95% CI 43.3%-81.9%) | 0 | {'ok': 20} |
| `single_pass_v2` | **73.8%** (59/80; 95% CI 63.2%-82.1%) | **68.8%** (55/80; 95% CI 57.9%-77.8%) | 0 | {'ok': 66, 'awaiting_hitl_confirmation': 8, 'blocked_by_guardrail': 6} |

## Completion by kind of task

| Kind | `loop` | `loop_after_elig_fix` | `loop_v2` | `single_pass` | `single_pass_after_elig_fix` | `single_pass_v2` |
|---|---|---|---|---|---|---|
| draft_grievance | **85.7%** (6/7; 95% CI 48.7%-97.4%) | - | **85.7%** (6/7; 95% CI 48.7%-97.4%) | **85.7%** (6/7; 95% CI 48.7%-97.4%) | - | **85.7%** (6/7; 95% CI 48.7%-97.4%) |
| eligibility | **65.0%** (13/20; 95% CI 43.3%-81.9%) | **100.0%** (20/20; 95% CI 83.9%-100.0%) | **100.0%** (20/20; 95% CI 83.9%-100.0%) | **55.0%** (11/20; 95% CI 34.2%-74.2%) | **85.0%** (17/20; 95% CI 64.0%-94.8%) | **85.0%** (17/20; 95% CI 64.0%-94.8%) |
| info | **64.4%** (29/45; 95% CI 49.8%-76.8%) | - | **68.9%** (31/45; 95% CI 54.3%-80.5%) | **73.3%** (33/45; 95% CI 59.0%-84.0%) | - | **64.4%** (29/45; 95% CI 49.8%-76.8%) |
| refusal | **100.0%** (7/7; 95% CI 64.6%-100.0%) | - | **100.0%** (7/7; 95% CI 64.6%-100.0%) | **85.7%** (6/7; 95% CI 48.7%-97.4%) | - | **85.7%** (6/7; 95% CI 48.7%-97.4%) |
| track_grievance | **100.0%** (1/1; 95% CI 20.6%-100.0%) | - | **100.0%** (1/1; 95% CI 20.6%-100.0%) | **100.0%** (1/1; 95% CI 20.6%-100.0%) | - | **100.0%** (1/1; 95% CI 20.6%-100.0%) |

## Tool calls, cost and latency per task

| Config | Tool calls (avg / median / max) | Step-cap hits | Reflector rounds (avg) | Loop acted | Tokens (avg) | Cost (avg) | Latency avg / p50 / p95 |
|---|---|---:|---:|---:|---:|---:|---|
| `loop` | 2.02 / 2.0 / 4 | 0 | 1.44 | 60.0% | 7854 | price not set | 15.4s / 14.0s / 35.2s |
| `loop_after_elig_fix` | 2.50 / 2.0 / 4 | 0 | 1.35 | 30.0% | 8468 | price not set | 16.8s / 14.5s / 33.5s |
| `loop_v2` | 1.34 / 1.0 / 4 | 0 | 0.94 | 8.8% | 7092 | price not set | 15.0s / 13.2s / 33.6s |
| `single_pass` | 1.19 / 1.0 / 2 | 0 | 0.82 | 0.0% | 6532 | price not set | 13.6s / 12.0s / 33.3s |
| `single_pass_after_elig_fix` | 2.00 / 2.0 / 2 | 0 | 1.00 | 0.0% | 7717 | price not set | 14.4s / 12.6s / 19.9s |
| `single_pass_v2` | 1.19 / 1.0 / 2 | 0 | 0.82 | 0.0% | 6547 | price not set | 13.7s / 11.6s / 33.1s |

### Average tool calls by kind of task

| Kind | `loop` | `loop_after_elig_fix` | `loop_v2` | `single_pass` | `single_pass_after_elig_fix` | `single_pass_v2` |
|---|---:|---:|---:|---:|---:|---:|
| draft_grievance | 1.00 | - | 1.00 | 1.00 | - | 1.00 |
| eligibility | 2.60 | 2.50 | 2.50 | 2.00 | 2.00 | 2.00 |
| info | 2.18 | - | 1.00 | 1.00 | - | 1.00 |
| refusal | 0.57 | - | 0.57 | 0.29 | - | 0.29 |
| track_grievance | 1.00 | - | 1.00 | 1.00 | - | 1.00 |

## Current code: loop vs single pass (`loop_v2` vs `single_pass_v2`)

- Completion: tasks only `loop_v2` completed = 7, only `single_pass_v2` completed = 1 (n=80); exact McNemar p = 0.0703 (not significant at 0.05).
- On the 7 tasks where the loop acted in `loop_v2`: `loop_v2` completed 7, `single_pass_v2` completed 3.
- Tool calls per task (`loop_v2` minus `single_pass_v2`): +0.15 (95% bootstrap CI +0.05 to +0.28).
- Latency per task (`loop_v2` minus `single_pass_v2`): +1.4s (95% bootstrap CI +0.6s to +2.4s).
- Tokens per task (`loop_v2` minus `single_pass_v2`): +545 (95% bootstrap CI +366 to +730).
- Tasks whose outcome changed: `ELIG-10` (loop_v2 only), `ELIG-15` (loop_v2 only), `ELIG-16` (loop_v2 only), `FAQ-04` (loop_v2 only), `ML-07` (loop_v2 only), `QA-03` (single_pass_v2 only), `QA-12` (loop_v2 only), `REF-03` (loop_v2 only)

## With the loop vs `loop_after_elig_fix` (same tasks)

- Completion: tasks only `loop` completed = 0, only `loop_after_elig_fix` completed = 7 (n=20); exact McNemar p = 0.0156 (significant at 0.05).
- On the 9 tasks where the loop acted in `loop`: `loop` completed 5, `loop_after_elig_fix` completed 9.
- Tool calls per task (`loop` minus `loop_after_elig_fix`): +0.10 (95% bootstrap CI -0.10 to +0.30).
- Latency per task (`loop` minus `loop_after_elig_fix`): -0.1s (95% bootstrap CI -2.3s to +1.8s).
- Tokens per task (`loop` minus `loop_after_elig_fix`): +369 (95% bootstrap CI -135 to +1033).
- Tasks whose outcome changed: `ELIG-01` (loop_after_elig_fix only), `ELIG-02` (loop_after_elig_fix only), `ELIG-03` (loop_after_elig_fix only), `ELIG-05` (loop_after_elig_fix only), `ELIG-13` (loop_after_elig_fix only), `ELIG-14` (loop_after_elig_fix only), `ELIG-15` (loop_after_elig_fix only)

## With the loop vs `loop_v2` (same tasks)

- Completion: tasks only `loop` completed = 5, only `loop_v2` completed = 14 (n=80); exact McNemar p = 0.0636 (not significant at 0.05).
- On the 48 tasks where the loop acted in `loop`: `loop` completed 30, `loop_v2` completed 36.
- Tool calls per task (`loop` minus `loop_v2`): +0.69 (95% bootstrap CI +0.50 to +0.88).
- Latency per task (`loop` minus `loop_v2`): +0.4s (95% bootstrap CI -0.9s to +1.4s).
- Tokens per task (`loop` minus `loop_v2`): +762 (95% bootstrap CI +497 to +1064).
- Tasks whose outcome changed: `ELIG-01` (loop_v2 only), `ELIG-02` (loop_v2 only), `ELIG-03` (loop_v2 only), `ELIG-05` (loop_v2 only), `ELIG-13` (loop_v2 only), `ELIG-14` (loop_v2 only), `ELIG-15` (loop_v2 only), `FAQ-05` (loop_v2 only), `ML-04` (loop_v2 only), `ML-07` (loop_v2 only), `QA-03` (loop only), `QA-05` (loop only), `QA-06` (loop_v2 only), `QA-13` (loop only), `QA-15` (loop_v2 only), `QA-17` (loop only), `QA-18` (loop only), `QA-21` (loop_v2 only), `QA-22` (loop_v2 only)

## With the loop vs `single_pass` (same tasks)

- Completion: tasks only `loop` completed = 7, only `single_pass` completed = 8 (n=80); exact McNemar p = 1.0 (not significant at 0.05).
- On the 48 tasks where the loop acted in `loop`: `loop` completed 30, `single_pass` completed 31.
- Tool calls per task (`loop` minus `single_pass`): +0.84 (95% bootstrap CI +0.65 to +1.02).
- Latency per task (`loop` minus `single_pass`): +1.8s (95% bootstrap CI +1.1s to +2.5s).
- Tokens per task (`loop` minus `single_pass`): +1322 (95% bootstrap CI +995 to +1675).
- Tasks whose outcome changed: `ELIG-10` (loop only), `ELIG-16` (loop only), `FAQ-05` (single_pass only), `ML-03` (single_pass only), `ML-04` (single_pass only), `ML-07` (single_pass only), `ML-09` (loop only), `QA-05` (loop only), `QA-06` (single_pass only), `QA-15` (single_pass only), `QA-17` (loop only), `QA-18` (loop only), `QA-21` (single_pass only), `QA-22` (single_pass only), `REF-03` (loop only)

## With the loop vs `single_pass_after_elig_fix` (same tasks)

- Completion: tasks only `loop` completed = 2, only `single_pass_after_elig_fix` completed = 6 (n=20); exact McNemar p = 0.2891 (not significant at 0.05).
- On the 9 tasks where the loop acted in `loop`: `loop` completed 5, `single_pass_after_elig_fix` completed 6.
- Tool calls per task (`loop` minus `single_pass_after_elig_fix`): +0.60 (95% bootstrap CI +0.30 to +0.95).
- Latency per task (`loop` minus `single_pass_after_elig_fix`): +2.4s (95% bootstrap CI +1.1s to +3.7s).
- Tokens per task (`loop` minus `single_pass_after_elig_fix`): +1120 (95% bootstrap CI +584 to +1798).
- Tasks whose outcome changed: `ELIG-01` (single_pass_after_elig_fix only), `ELIG-02` (single_pass_after_elig_fix only), `ELIG-03` (single_pass_after_elig_fix only), `ELIG-05` (single_pass_after_elig_fix only), `ELIG-10` (loop only), `ELIG-13` (single_pass_after_elig_fix only), `ELIG-14` (single_pass_after_elig_fix only), `ELIG-16` (loop only)

## With the loop vs `single_pass_v2` (same tasks)

- Completion: tasks only `loop` completed = 9, only `single_pass_v2` completed = 12 (n=80); exact McNemar p = 0.6636 (not significant at 0.05).
- On the 48 tasks where the loop acted in `loop`: `loop` completed 30, `single_pass_v2` completed 30.
- Tool calls per task (`loop` minus `single_pass_v2`): +0.84 (95% bootstrap CI +0.65 to +1.02).
- Latency per task (`loop` minus `single_pass_v2`): +1.7s (95% bootstrap CI +0.9s to +2.5s).
- Tokens per task (`loop` minus `single_pass_v2`): +1307 (95% bootstrap CI +954 to +1691).
- Tasks whose outcome changed: `ELIG-01` (single_pass_v2 only), `ELIG-02` (single_pass_v2 only), `ELIG-03` (single_pass_v2 only), `ELIG-05` (single_pass_v2 only), `ELIG-10` (loop only), `ELIG-13` (single_pass_v2 only), `ELIG-14` (single_pass_v2 only), `ELIG-16` (loop only), `FAQ-04` (loop only), `FAQ-05` (single_pass_v2 only), `ML-04` (single_pass_v2 only), `QA-05` (loop only), `QA-06` (single_pass_v2 only), `QA-12` (loop only), `QA-13` (loop only), `QA-15` (single_pass_v2 only), `QA-17` (loop only), `QA-18` (loop only), `QA-21` (single_pass_v2 only), `QA-22` (single_pass_v2 only), `REF-03` (loop only)
