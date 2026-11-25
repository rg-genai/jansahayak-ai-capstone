# Task Completion and Tool Use (80-task suite)

- Tasks: `eval/golden_dataset.json`: scheme questions, FAQs, six Indian languages, eligibility checks, grievance drafting/tracking, and requests that must be refused.
- Runs: live retrieval settings; web fallback disabled (logged); grievance tools on the in-process mock CPGRAMS.
- A task is done only if it passes every rule for its kind (see `eval/score_task_eval.py`) and uses at most 10 tool calls. Grounding judge: `gemini-3.5-flash-lite`.
- 95% CIs are Wilson intervals; with ~80 tasks a difference of a few tasks is within noise.

## Task completion

| Config | Completion | Pipeline errors | Status counts |
|---|---|---:|---|
| `loop` | **65.8%** (50/76; 95% CI 54.6%-75.5%, 4 awaiting judge) | 0 | {'ok': 66, 'awaiting_hitl_confirmation': 8, 'blocked_by_guardrail': 6} |
| `single_pass` | **44.0%** (11/25; 95% CI 26.7%-62.9%, 1 awaiting judge) | 0 | {'ok': 26} |

## Completion by kind of task

| Kind | `loop` | `single_pass` |
|---|---|---|
| draft_grievance | **85.7%** (6/7; 95% CI 48.7%-97.4%) | - |
| eligibility | **35.0%** (7/20; 95% CI 18.1%-56.7%) | **35.0%** (7/20; 95% CI 18.1%-56.7%) |
| info | **70.7%** (29/41; 95% CI 55.5%-82.4%, 4 awaiting judge) | **80.0%** (4/5; 95% CI 37.5%-96.4%, 1 awaiting judge) |
| refusal | **100.0%** (7/7; 95% CI 64.6%-100.0%) | - |
| track_grievance | **100.0%** (1/1; 95% CI 20.6%-100.0%) | - |

## Tool calls, cost and latency per task

| Config | Tool calls (avg / median / max) | Step-cap hits | Reflector rounds (avg) | Loop acted | Tokens (avg) | Cost (avg) | Latency avg / p50 / p95 |
|---|---|---:|---:|---:|---:|---:|---|
| `loop` | 2.02 / 2.0 / 4 | 0 | 1.44 | 60.0% | 7854 | price not set | 15.4s / 14.0s / 35.2s |
| `single_pass` | 1.77 / 2.0 / 2 | 0 | 1.00 | 0.0% | 7954 | price not set | 14.6s / 12.9s / 20.4s |

### Average tool calls by kind of task

| Kind | `loop` | `single_pass` |
|---|---:|---:|
| draft_grievance | 1.00 | - |
| eligibility | 2.60 | 2.00 |
| info | 2.18 | 1.00 |
| refusal | 0.57 | - |
| track_grievance | 1.00 | - |

## With the loop vs `single_pass` (same tasks)

- Completion: tasks only `loop` completed = 0, only `single_pass` completed = 1 (n=25); exact McNemar p = 1.0 (not significant at 0.05).
- On the 12 tasks where the loop acted: `loop` completed 2, `single_pass` completed 3.
- Tool calls per task (`loop` minus `single_pass`): +0.62 (95% bootstrap CI +0.35 to +0.88).
- Latency per task (`loop` minus `single_pass`): +2.0s (95% bootstrap CI +0.7s to +3.3s).
- Tokens per task (`loop` minus `single_pass`): +1207 (95% bootstrap CI +564 to +1886).
- Tasks whose outcome changed: `FAQ-05` (single_pass only)
