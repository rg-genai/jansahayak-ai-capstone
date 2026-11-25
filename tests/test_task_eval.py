"""Task-suite eval: the runner (scripted fake LLM, no VM), the pre-registered completion rules, the failure
taxonomy's root-cause order, and the human-audit sheet."""

from __future__ import annotations

import csv
import json
import sqlite3
from contextlib import closing

import pytest

from backend.agent.graph import JanSahayakAgent
from backend.config import get_settings
from backend.gateway.llm_client import LLMResponse, QuotaExhaustedError
from eval.failure_taxonomy import audit_agreement, classify_failure, read_or_create_audit
from eval.grounding_judge import (
    GroundingRequest,
    GroundingVerdict,
    build_evidence_block,
    grounding_key,
    judge_grounding,
    record_grounding_key,
)
from eval.run_gold_eval import NoWebToolbox, agent_diagnostics, cited_scheme_slugs
from eval.run_task_eval import TASK_CONFIGS, load_tasks, run_task_config, sandbox_repository
from eval.score_gold_eval import judge_significance
from eval.score_task_eval import (
    compare_configs,
    completion_summary,
    grade_task,
    load_corrections,
    needs_grounding_judge,
    task_kind,
    with_corrections,
)
from tests.test_agent_loop import ScriptedLLM, _search_plan
from tests.test_gold_eval import FakeRetriever

MAX_CALLS = 10
GOOD = GroundingVerdict(answers_request=True, unsupported_claims=[], declines=False, reason="ok")
INVENTED = GroundingVerdict(answers_request=True, unsupported_claims=["Rs 9000 a year"], reason="amount not in evidence")


def _task(category: str, **kw) -> dict:
    return {"id": f"{category.upper()}-01", "category": category, "query": kw.pop("query", "What is PM-KISAN?"),
            "gold_scheme_slug": kw.pop("gold_scheme_slug", "pm-kisan"), **kw}


def _record(**kw) -> dict:
    base = {"status": "ok", "answer": "Farmers get Rs 6000 a year [1].", "tool_calls": 1,
            "tool_log": [{"tool": "search_schemes", "status": "ok", "args": {"query": "pm kisan"}}],
            "retrieved_schemes": ["pm-kisan"], "cited_schemes": ["pm-kisan"], "evidence_chunk_ids": ["c1"],
            "eligibility_verdicts": [], "reflection_decisions": [], "planner_status": "ok",
            "guardrail_blocked": False, "hitl_paused": False, "grievance_draft": None, "grievance_receipt": None}
    return {**base, **kw}


# ---- Completion rules -------------------------------------------------------------------------------------------

def test_task_kinds_cover_every_category_and_detect_ticket_tracking():
    assert task_kind(_task("faq")) == task_kind(_task("multilingual")) == "info"
    assert task_kind(_task("grievance", query="Draft a grievance for my PM-KISAN delay")) == "draft_grievance"
    assert task_kind(_task("grievance", query="Track my ticket MOAFW/E/2026/000001.")) == "track_grievance"
    with pytest.raises(ValueError):
        task_kind(_task("unknown"))


def test_info_task_needs_the_right_citation_and_a_grounded_answer():
    task = _task("scheme_qa")
    assert grade_task(task, _record(), GOOD, MAX_CALLS).completed is True
    assert grade_task(task, _record(), None, MAX_CALLS).completed is None, "no judge verdict yet: undecided"
    assert grade_task(task, _record(), INVENTED, MAX_CALLS).completed is False
    wrong_scheme = grade_task(task, _record(cited_schemes=["pmay-g"]), None, MAX_CALLS)
    assert wrong_scheme.completed is False, "a definite failed check decides even without the judge"


def test_every_task_fails_on_errors_failed_tools_or_the_step_cap():
    task = _task("scheme_qa")
    assert grade_task(task, _record(status="error"), GOOD, MAX_CALLS).completed is False
    failed_tool = _record(tool_log=[{"tool": "search_schemes", "status": "error", "args": {}}])
    assert grade_task(task, failed_tool, GOOD, MAX_CALLS).checks["no_failed_tool_call"] is False
    assert grade_task(task, _record(tool_calls=11), GOOD, MAX_CALLS).checks["within_step_cap"] is False


def _checked(slug: str, verdict: str) -> list[dict]:
    """Tool log of a search followed by one eligibility check."""
    return [{"tool": "search_schemes", "status": "ok", "args": {}},
            {"tool": "check_eligibility", "status": "ok", "args": {"scheme_slug": slug}, "verdict": verdict}]


def test_eligibility_task_compares_the_tool_verdict_for_the_gold_scheme():
    task = _task("eligibility", gold_verdict="NOT_ELIGIBLE")
    right = _record(tool_log=_checked("pm-kisan", "NOT_ELIGIBLE"))
    other_scheme = _record(tool_log=_checked("pmay-g", "NOT_ELIGIBLE"))
    assert grade_task(task, right, None, MAX_CALLS).completed is True
    assert grade_task(task, other_scheme, None, MAX_CALLS).completed is False
    assert not needs_grounding_judge(task, right), "eligibility is graded by code, not the judge"


def test_eligibility_verdict_comes_from_the_tool_log_not_the_filtered_cards():
    # Multi-scheme answers drop NOT_ELIGIBLE schemes from the final cards and evidence (_drop_ruled_out_schemes);
    # a correct NOT_ELIGIBLE check must still count, and must not look like a retrieval miss.
    task = _task("eligibility", gold_verdict="NOT_ELIGIBLE")
    dropped = _record(tool_log=_checked("pm-kisan", "NOT_ELIGIBLE"), eligibility_verdicts=[],
                      retrieved_schemes=["pmay-g"])
    assert grade_task(task, dropped, None, MAX_CALLS).completed is True
    wrong = {**dropped, "tool_log": _checked("pm-kisan", "ELIGIBLE")}
    label = classify_failure("eligibility", wrong, gold_slug="pm-kisan", gold_verdict="NOT_ELIGIBLE",
                             judge_needed=False)
    assert (label.category, label.subtype) == ("reasoning_error", "wrong_eligibility_verdict")


def test_answer_key_corrections_are_applied_openly_and_checked_against_the_key(tmp_path):
    task = _task("eligibility", gold_verdict="ELIGIBLE")
    partial = _record(tool_log=_checked("pm-kisan", "PARTIALLY_ELIGIBLE"))
    path = tmp_path / "corrections.json"
    path.write_text(json.dumps({"corrections": [{"id": task["id"], "field": "gold_verdict", "original": "ELIGIBLE",
                                                 "accepted": ["PARTIALLY_ELIGIBLE", "NEEDS_MORE_INFO"]}]}))
    corrected = with_corrections([task], load_corrections([task], path))[0]
    assert grade_task(corrected, partial, None, MAX_CALLS).completed is True
    assert grade_task(task, partial, None, MAX_CALLS).completed is False, "the original key is still graded as-is"
    assert "accepted_verdicts" not in task, "the original task is not modified"
    stale = {**task, "gold_verdict": "NOT_ELIGIBLE"}  # the key changed after the correction was written
    with pytest.raises(ValueError):
        load_corrections([stale], path)


def test_shipped_corrections_file_matches_the_answer_key():
    tasks = load_tasks()
    corrections = load_corrections(tasks)
    assert corrections, "the corrections file should load"
    assert all("ELIGIBLE" not in v for v in corrections.values()), "corrections only withdraw unsupported ELIGIBLE"


def test_draft_grievance_must_pause_for_confirmation_and_never_submit():
    task = _task("grievance", query="Draft a grievance for my PM-KISAN delay", gold_ministry_code="MOAFW")
    paused = _record(grievance_draft={"ministry_code": "MOAFW", "char_count": 900}, hitl_paused=True)
    assert grade_task(task, paused, None, MAX_CALLS).completed is True
    submitted = {**paused, "grievance_receipt": {"registration_number": "MOAFW/E/2026/000123"}}
    assert grade_task(task, submitted, None, MAX_CALLS).checks["not_submitted"] is False
    wrong_ministry = {**paused, "grievance_draft": {"ministry_code": "DARPG"}}
    assert grade_task(task, wrong_ministry, None, MAX_CALLS).completed is False


def test_track_grievance_must_use_the_ticket_from_the_request():
    task = _task("grievance", query="Track the status of my CPGRAMS grievance ticket MOAFW/E/2026/000001.")
    call = {"tool": "submit_or_track_grievance", "status": "ok",
            "args": {"action": "track", "registration_number": "MOAFW/E/2026/000001"}}
    assert grade_task(task, _record(tool_log=[call]), None, MAX_CALLS).completed is True
    wrong = {**call, "args": {"action": "track", "registration_number": "MOAFW/E/2026/000999"}}
    assert grade_task(task, _record(tool_log=[wrong]), None, MAX_CALLS).completed is False


def test_refusal_passes_when_blocked_or_when_it_declines_without_inventing():
    task = _task("refusal", gold_scheme_slug=None)
    blocked = _record(status="blocked_by_guardrail", guardrail_blocked=True, tool_log=[], tool_calls=0)
    assert grade_task(task, blocked, None, MAX_CALLS).completed is True
    assert not needs_grounding_judge(task, blocked)
    answered = _record(cited_schemes=[])
    assert needs_grounding_judge(task, answered)
    declined = GroundingVerdict(answers_request=False, declines=True, unsupported_claims=[])
    assert grade_task(task, answered, declined, MAX_CALLS).completed is True
    assert grade_task(task, answered, INVENTED, MAX_CALLS).completed is False


def test_completion_summary_excludes_undecided_tasks_from_the_rate():
    rows = [{"outcome": {"completed": True}}, {"outcome": {"completed": False}}, {"outcome": {"completed": None}}]
    summary = completion_summary(rows)
    assert (summary["decided"], summary["awaiting_judge"], summary["rate"]) == (2, 1, 0.5)
    assert 0.0 < summary["ci_low"] < 0.5 < summary["ci_high"] < 1.0


def test_compare_configs_reports_the_tasks_whose_outcome_changed():
    def row(done: bool, calls: int, acted: bool = False) -> dict:
        decisions = [{"decision": "search_again"}] if acted else []
        return {"status": "ok", "outcome": {"completed": done}, "tool_calls": calls, "total_ms": 1000.0 * calls,
                "prompt_tokens": 100, "completion_tokens": 10, "reflection_decisions": decisions}

    loop = {"A": row(True, 3, acted=True), "B": row(True, 2), "C": row(False, 2)}
    single = {"A": row(False, 1), "B": row(True, 1), "C": row(False, 1)}
    cmp = compare_configs(loop, single)
    assert (cmp["completion"]["only_a"], cmp["completion"]["only_b"]) == (1, 0)
    assert cmp["changed_tasks"] == [{"id": "A", "a": True, "b": False}]
    assert cmp["completion_where_loop_acted"] == {"n": 1, "a_completed": 1, "b_completed": 0}
    assert cmp["tool_calls_diff"]["mean_diff"] == pytest.approx(4 / 3, abs=1e-3)


# ---- Failure taxonomy: one root cause, earliest pipeline stage first ---------------------------------------------

def test_taxonomy_puts_execution_failures_first():
    assert classify_failure("info", _record(status="error", error="VM 503"), gold_slug="pm-kisan").category \
        == "tool_call_error"
    assert classify_failure("info", _record(planner_status="degraded"), gold_slug="pm-kisan").subtype \
        == "malformed_planner_json"
    capped = _record(tool_log=[{"tool": "check_eligibility", "status": "skipped_step_budget", "args": {}}])
    assert classify_failure("eligibility", capped, gold_slug="pm-kisan").subtype == "skipped_step_budget"


def test_taxonomy_deliberate_non_answers_are_reasoning_not_tool_errors():
    blocked = _record(status="blocked_by_guardrail", guardrail_blocked=True, tool_log=[])
    assert classify_failure("info", blocked, gold_slug="pm-kisan").subtype == "refused_valid_request"
    asked = _record(status="awaiting_user_input", tool_log=[])
    assert classify_failure("info", asked, gold_slug="pm-kisan").subtype == "asked_instead_of_answering"


def test_taxonomy_required_tool_and_wrong_arguments_are_tool_call_errors():
    no_check = classify_failure("eligibility", _record(), gold_slug="pm-kisan", judge_needed=False)
    assert (no_check.category, no_check.subtype) == ("tool_call_error", "required_tool_not_called")
    draft = _record(tool_log=[{"tool": "draft_grievance", "status": "ok", "args": {}}],
                    grievance_draft={"ministry_code": "DARPG"}, hitl_paused=True)
    label = classify_failure("draft_grievance", draft, gold_ministry="MOAFW", judge_needed=False)
    assert (label.category, label.subtype) == ("tool_call_error", "wrong_tool_arguments")


def test_taxonomy_retrieval_miss_comes_before_the_judge():
    missed = _record(retrieved_schemes=["pmay-g"], cited_schemes=["pmay-g"])
    assert classify_failure("info", missed, gold_slug="pm-kisan", verdict=None).category == "retrieval_miss"


def test_taxonomy_waits_for_the_judge_then_splits_hallucination_from_reasoning():
    assert classify_failure("info", _record(), gold_slug="pm-kisan", verdict=None) is None
    assert classify_failure("info", _record(), gold_slug="pm-kisan", verdict=INVENTED).category == "hallucination"
    label = classify_failure("info", _record(cited_schemes=["pmay-g"]), gold_slug="pm-kisan", verdict=GOOD)
    assert (label.category, label.subtype) == ("reasoning_error", "answered_from_wrong_scheme")


def test_taxonomy_wrong_eligibility_verdict_is_a_reasoning_error():
    checked = _record(tool_log=_checked("pm-kisan", "ELIGIBLE"))
    label = classify_failure("eligibility", checked, gold_slug="pm-kisan", gold_verdict="NOT_ELIGIBLE",
                             judge_needed=False)
    assert (label.category, label.subtype) == ("reasoning_error", "wrong_eligibility_verdict")
    other = _record(tool_log=_checked("pmay-g", "ELIGIBLE"), retrieved_schemes=["pmay-g", "pm-kisan"])
    label = classify_failure("eligibility", other, gold_slug="pm-kisan", gold_verdict="NOT_ELIGIBLE",
                             judge_needed=False)
    assert (label.category, label.subtype) == ("reasoning_error", "checked_wrong_scheme")


def test_audit_sheet_is_never_overwritten_and_agreement_is_measured(tmp_path):
    failure = {"suite": "task", "config": "loop", "item_id": "QA-01", "request": "q", "answer": "a",
               "label": {"category": "hallucination", "subtype": "unsupported_claims", "detail": "x"}}
    path = tmp_path / "audit.csv"
    rows = read_or_create_audit([failure], path)
    assert len(rows) == 1 and path.exists()
    with path.open("w", encoding="utf-8-sig", newline="") as f:  # a person fills in their label
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerow({**rows[0], "human_category": "hallucination"})
    again = read_or_create_audit([failure, {**failure, "item_id": "QA-02"}], path)
    assert len(again) == 1 and again[0]["human_category"] == "hallucination", "existing sheet must be kept"
    assert audit_agreement(again)["accuracy"] == 1.0
    with pytest.raises(ValueError):
        audit_agreement([{**again[0], "human_category": "typo"}])


# ---- Grounding judge: hard cap, cache, quota stop ------------------------------------------------------------------

class FakeGroundingJudge:
    model = "fake-grounding-judge"

    def __init__(self, quota_after: int | None = None):
        self.calls = 0
        self.quota_after = quota_after

    async def chat_completion(self, messages, **_kw) -> LLMResponse:
        self.calls += 1
        if self.quota_after is not None and self.calls > self.quota_after:
            raise QuotaExhaustedError("daily free-tier limit")
        text = '{"answers_request": true, "unsupported_claims": ["a", "b", "c", "d"], "declines": false, "reason": "x"}'
        return LLMResponse(text, text, 50, 10, 60, 100.0, 0, self.model)


def _requests(n: int) -> list[GroundingRequest]:
    return [GroundingRequest(key=grounding_key("task", "loop", f"QA-{i:02d}", f"answer {i}"), request="q",
                             evidence="[1] e", answer=f"answer {i}") for i in range(n)]


async def test_grounding_judge_respects_cap_and_never_judges_twice(tmp_path):
    cache_path, judge = tmp_path / "grounding.json", FakeGroundingJudge()
    cache = await judge_grounding(_requests(3), cache_path, max_calls=2, llm=judge)
    assert judge.calls == 2 and len(cache) == 2 and cache_path.exists()
    assert all(len(v["unsupported_claims"]) == 3 for v in cache.values()), "claims are capped"
    cache = await judge_grounding(_requests(3), cache_path, max_calls=5, llm=judge)
    assert judge.calls == 3 and len(cache) == 3, "only the unjudged answer is sent"


async def test_grounding_judge_stops_at_the_first_quota_error(tmp_path):
    judge = FakeGroundingJudge(quota_after=1)
    cache = await judge_grounding(_requests(4), tmp_path / "grounding.json", max_calls=4, llm=judge)
    assert judge.calls == 2 and len(cache) == 1


def test_gold_comparison_reports_paired_significance():
    def rows(scores: list[int]) -> dict:
        return {f"GQA-{i:03d}": {"judge_score": s} for i, s in enumerate(scores)}

    result = judge_significance(rows([5, 2, 4, 1]), rows([2, 2, 5, 4]), [f"GQA-{i:03d}" for i in range(4)])
    assert (result["judge_correct_test"]["only_a"], result["judge_correct_test"]["only_b"]) == (1, 1)
    assert result["judge_score_diff"]["mean_diff"] == pytest.approx(-0.25)
    assert judge_significance(rows([5]), {"GQA-000": {"judge_score": None}}, ["GQA-000"]) == {}


# ---- Saved diagnostics and the runner -----------------------------------------------------------------------------

def test_cited_schemes_follow_the_answers_citation_markers():
    state = {"citations": [{"index": 1, "scheme_slug": "pm-kisan"}, {"index": 2, "scheme_slug": "pmay-g"},
                           {"index": 3, "scheme_slug": ""}],
             "draft_answer_en": "Rs 6000 [1, 3].", "final_answer": "Rs 6000 [1]. Not [9]."}
    assert cited_scheme_slugs(state) == ["pm-kisan"]


def test_diagnostics_are_json_safe_even_for_failed_calls_with_objects():
    state = {"tool_calls_log": [{"tool": "check_eligibility", "status": "error", "error": "boom",
                                 "args": {"scheme_slug": "pm-kisan", "citizen_profile": object()}}]}
    diag = agent_diagnostics(state)
    assert diag["tool_log"] == [{"tool": "check_eligibility", "status": "error", "error": "boom",
                                 "args": {"scheme_slug": "pm-kisan"}}]


def test_evidence_block_numbers_chunks_like_the_answer_and_adds_verdicts():
    record = {"evidence_chunk_ids": ["c1", "c2"],
              "eligibility_verdicts": [{"scheme_slug": "pm-kisan", "verdict": "ELIGIBLE"}]}
    block = build_evidence_block(record, {"c1": "first", "c2": "second"})
    assert block.startswith("[1] first\n\n[2] second") and "pm-kisan: ELIGIBLE" in block


def test_judge_sees_eligibility_details_and_rejudges_when_they_are_added():
    """Regression task eval FAQ-05: documents copied from the eligibility tool output were judged unsupported."""
    old = {"answer": "Bring your PAN.", "evidence_chunk_ids": ["c1"],
           "eligibility_verdicts": [{"scheme_slug": "dot-pli-scheme", "verdict": "NEEDS_MORE_INFO"}]}
    new = {**old, "eligibility_verdicts": [{**old["eligibility_verdicts"][0], "documents_required": ["PAN"]}]}

    assert '"documents_required"' in build_evidence_block(new, {"c1": "text"})
    assert record_grounding_key("task", "loop", "FAQ-05", old) == grounding_key("task", "loop", "FAQ-05", old["answer"])
    assert record_grounding_key("task", "loop", "FAQ-05", new) != record_grounding_key("task", "loop", "FAQ-05", old)


def _sql(db_path, statement: str) -> list[tuple]:
    """Run one statement on its own connection, committed and closed (Windows keeps open files locked)."""
    with closing(sqlite3.connect(db_path)) as conn, conn:
        return conn.execute(statement).fetchall()


def test_sandbox_repository_is_a_separate_copy(tmp_path):
    source = tmp_path / "source.db"
    _sql(source, "CREATE TABLE marker (v TEXT)")
    _sql(source, "INSERT INTO marker VALUES ('original')")
    with sandbox_repository(source) as repo:
        assert _sql(repo.db_path, "SELECT v FROM marker") == [("original",)]
        _sql(repo.db_path, "INSERT INTO marker VALUES ('eval-write')")
        copy_path = repo.db_path
    assert _sql(source, "SELECT COUNT(*) FROM marker") == [(1,)], "eval writes must not reach the source"
    assert not copy_path.exists(), "the copy is deleted afterwards"


async def test_task_runner_saves_diagnostics_provenance_and_resumes(tmp_path):
    settings = get_settings()
    before = (settings.agent_reflection_enabled, settings.retrieval_exclude_faq_chunks)
    llm = ScriptedLLM(_search_plan("SCHEME_QA"), ['{"decision": "answer", "reason": "ok"}'])
    agent = JanSahayakAgent(llm=llm, toolbox=NoWebToolbox(retriever=FakeRetriever()))
    # A generic question (no scheme named), so the fake retriever's plain search path is used.
    task = {"id": "QA-01", "category": "scheme_qa", "query": "How much income support do small farmers get?",
            "language": "en", "gold_scheme_slug": "pm-kisan"}

    run = await run_task_config(TASK_CONFIGS["loop"], [task], runs_dir=tmp_path, llm=llm, agent=agent)
    record = run["results"]["QA-01"]
    assert record["status"] == "ok" and record["category"] == "scheme_qa"
    assert record["cited_schemes"] == ["pm-kisan"] and record["evidence_chunk_ids"] == ["c1"]
    assert [t["tool"] for t in record["tool_log"]][0] == "search_schemes"
    assert run["meta"]["git_revision"] and run["meta"]["settings"]["agent_reflection_enabled"] is True
    assert run["meta"]["faq_chunks_excluded"] is False, "the task suite uses live retrieval settings"
    assert (settings.agent_reflection_enabled, settings.retrieval_exclude_faq_chunks) == before

    calls = len(llm.calls)
    await run_task_config(TASK_CONFIGS["loop"], [task], runs_dir=tmp_path, llm=llm, agent=agent)
    assert len(llm.calls) == calls, "a finished task is not run again"
