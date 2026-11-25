# Failure Taxonomy

Each failure gets ONE root cause: the first pipeline stage that went wrong, checked in the order tool-call error -> retrieval miss -> hallucination -> reasoning error (see `eval/failure_taxonomy.py`).

- `task/*`: tasks not completed in the 80-task suite (`eval/score_task_eval.py`).
- `gold/*`: gold Q&A answers the judge scored below 4/5.
- Hallucination is decided by the grounding judge `gemini-3.5-flash-lite` against the exact evidence the answer was written from.

## Root causes

| Run | Failures | tool_call_error | retrieval_miss | hallucination | reasoning_error | Pending judge |
|---|---:|---:|---:|---:|---:|---:|
| `gold/main` | 7 | 1 | 2 | 1 | 3 | 0 |
| `gold/single_pass` | 4 | 1 | 2 | 1 | 0 | 0 |
| `task/loop` | 24 | 2 | 9 | 13 | 0 | 0 |
| `task/loop_v2` | 15 | 2 | 2 | 9 | 2 | 0 |
| `task/single_pass` | 23 | 2 | 9 | 8 | 4 | 0 |
| `task/single_pass_after_elig_fix` | 3 | 0 | 0 | 0 | 3 | 0 |
| `task/single_pass_v2` | 21 | 2 | 2 | 11 | 6 | 0 |

## Subtypes and examples

### `gold/main`

- **reasoning_error/incomplete_or_wrong_answer** (2)
  - GQA-007: The assistant provides the eligibility requirements and relevant scheme details based on the evidence.
  - GQA-015: The answer accurately states the eligible industry types based on the provided evidence.
- **retrieval_miss/gold_scheme_not_retrieved** (2)
  - GQA-033: evidence schemes ['smile-scholarship']
  - GQA-047: evidence schemes ['pmmy', 'ab-pmjay', 'csss-cus', 'pmvky', 'pmuy2', 'pmksypdmc']
- **tool_call_error/required_tool_not_called** (1)
  - GQA-011: needed search_schemes; called ['submit_or_track_grievance']
- **hallucination/unsupported_claims** (1)
  - GQA-017: Proof of ownership or lease agreement for the workshed.
- **reasoning_error/answered_from_wrong_scheme** (1)
  - GQA-020: cited ['pmmy', 'pmvky'], gold pmuy2

### `gold/single_pass`

- **retrieval_miss/gold_scheme_not_retrieved** (2)
  - GQA-033: evidence schemes ['smile-scholarship', 'nap-sdp']
  - GQA-047: evidence schemes ['pmmy', 'ab-pmjay', 'pmvky']
- **tool_call_error/required_tool_not_called** (1)
  - GQA-011: needed search_schemes; called ['submit_or_track_grievance']
- **hallucination/unsupported_claims** (1)
  - GQA-057: the minimum eligible incremental net sales is 40% of X for the first year

### `task/loop`

- **hallucination/unsupported_claims** (13)
  - FAQ-03: Institutions must commit a minimum ₹1,00,000 contribution to the club; having a minimum of 5 years of existence and a full-time faculty coordinator with at least 10 years of experience
  - FAQ-05: PAN; Authority Letter for Nodal Officer; Certificate of Incorporation
  - FAQ-06: Proof of incorporation (for companies).; Business plan and innovation proposal.
- **retrieval_miss/gold_scheme_not_retrieved** (9)
  - ELIG-01: evidence schemes ['pmsby', 'pmvky', 'pmkvy-sp', 'pm-vikas', 'pmuy']
  - ELIG-02: evidence schemes ['sire', 'serbrss']
  - ELIG-03: evidence schemes ['apy', 'nsap-ignoaps']
- **tool_call_error/wrong_tool_arguments** (1)
  - GRV-03: draft addressed to MOSDE, expected MSMEI
- **tool_call_error/required_tool_not_called** (1)
  - ML-02: needed search_schemes; called ['draft_grievance']

### `task/loop_v2`

- **hallucination/unsupported_claims** (9)
  - FAQ-06: Business plan and project proposal.; Proof of incorporation (for companies).; Detailed budget and timeline.
  - FAQ-10: Group 2 (other courses)
  - ML-03: राशन कार्ड या अन्य पहचान के प्रमाण।; पता के प्रमाण।; आय के विवरण।
- **retrieval_miss/gold_scheme_not_retrieved** (2)
  - ML-08: evidence schemes ['pmjdy', 'nikshay', 'cbssc-msy']
  - ML-10: evidence schemes ['pmfby', 'pkvy', 'pm-kisan']
- **reasoning_error/did_not_answer** (1)
  - FAQ-03: The assistant provides general scheme information and benefits instead of answering the specific question about what AICTE expects from the institution.
- **tool_call_error/wrong_tool_arguments** (1)
  - GRV-03: draft addressed to MOSDE, expected MSMEI
- **tool_call_error/required_tool_not_called** (1)
  - ML-02: needed search_schemes; called ['draft_grievance']
- **reasoning_error/answered_from_wrong_scheme** (1)
  - QA-18: cited ['sbm-g-ii'], gold sbm-g-i

### `task/single_pass`

- **retrieval_miss/gold_scheme_not_retrieved** (9)
  - ELIG-01: evidence schemes ['pmsby', 'pmvky', 'pmkvy-sp', 'pm-vikas', 'pmuy']
  - ELIG-02: evidence schemes ['sire', 'serbrss']
  - ELIG-03: evidence schemes ['apy', 'nsap-ignoaps']
- **hallucination/unsupported_claims** (8)
  - FAQ-03: Proof of institution approval.
  - FAQ-06: Proof of incorporation (for companies).; Detailed budget and matching contribution plan.
  - FAQ-10: Eligible students include those from Group 1 (professional courses) and Group 2 (other courses)
- **reasoning_error/checked_wrong_scheme** (2)
  - ELIG-10: checked ['wos-a']
  - ELIG-16: checked ['tce-sc']
- **tool_call_error/wrong_tool_arguments** (1)
  - GRV-03: draft addressed to MOSDE, expected MSMEI
- **tool_call_error/required_tool_not_called** (1)
  - ML-02: needed search_schemes; called ['draft_grievance']
- **reasoning_error/answered_from_wrong_scheme** (1)
  - QA-18: cited ['sbm-g-ii'], gold sbm-g-i
- **reasoning_error/did_not_refuse** (1)
  - REF-03: The assistant correctly states that no such scheme exists and addresses the non-existent request.

### `task/single_pass_after_elig_fix`

- **reasoning_error/checked_wrong_scheme** (3)
  - ELIG-10: checked ['wos-a']
  - ELIG-15: checked ['pm-yasasvitcceobcebcdnts']
  - ELIG-16: checked ['ncscscst']

### `task/single_pass_v2`

- **hallucination/unsupported_claims** (11)
  - FAQ-04: Detailed project proposal; Technical and commercial viability plan; Team profile and expertise
  - FAQ-06: Business plan and project proposal.; Proof of incorporation (for companies).; Detailed budget and timeline.
  - FAQ-10: Group 2 (other courses)
- **reasoning_error/checked_wrong_scheme** (3)
  - ELIG-10: checked ['wos-a']
  - ELIG-15: checked ['pm-yasasvitcceobcebcdnts']
  - ELIG-16: checked ['ncscscst']
- **retrieval_miss/gold_scheme_not_retrieved** (2)
  - ML-08: evidence schemes ['pmjdy', 'nikshay', 'cbssc-msy']
  - ML-10: evidence schemes ['pmfby', 'pkvy', 'pm-kisan']
- **reasoning_error/did_not_answer** (1)
  - FAQ-03: The answer provides general information about the scheme instead of answering the specific question about what AICTE expects from the institution.
- **tool_call_error/wrong_tool_arguments** (1)
  - GRV-03: draft addressed to MOSDE, expected MSMEI
- **tool_call_error/required_tool_not_called** (1)
  - ML-02: needed search_schemes; called ['draft_grievance']
- **reasoning_error/answered_from_wrong_scheme** (1)
  - QA-18: cited ['sbm-g-ii'], gold sbm-g-i
- **reasoning_error/did_not_refuse** (1)
  - REF-03: The assistant correctly identified that the requested scheme does not exist in the official corpus.

## Human audit of the classifier

- 17 of 20 sampled failures labelled by a person: agreement 94%, Cohen's kappa 0.9179.
