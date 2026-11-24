"""Gold-set eval harness and scorer: runs, resume, latency fields, judge cap and cache (fake LLMs, no VM)."""

from __future__ import annotations

import json

from rouge_score import rouge_scorer
from sacrebleu.metrics import BLEU

from backend.config import get_settings
from backend.gateway.llm_client import LLMResponse, QuotaExhaustedError
from backend.retrieval.hybrid_retriever import RetrievalOutput, RetrievedChunk
from eval.run_gold_eval import CONFIGS, gold_rank, run_config, select_items
from eval.score_gold_eval import (
    build_report,
    clean_answer,
    judge_runs,
    render_markdown,
    score_records,
    text_overlap_scores,
)
from tests.test_agent_loop import ScriptedLLM, _search_plan


def _item(n: int, aspect: str, status: str = "unreviewed") -> dict:
    return {"id": f"GQA-{n:03d}", "aspect": aspect, "scheme_slug": "pm-kisan", "question": f"Question {n} about PM-KISAN?",
            "reference_answer": "Rs. 6000 a year is paid in three equal installments.", "review": {"status": status}}


ITEMS = [_item(i, a) for i, a in enumerate(["benefits", "eligibility", "benefits", "documents_required",
                                             "eligibility", "benefits"], start=1)]


class FakeClosedBookLLM:
    model = "fake-closed-book"

    def __init__(self, fail_on: str | None = None):
        self.calls = 0
        self.fail_on = fail_on

    async def chat_completion(self, messages, **_kw) -> LLMResponse:
        self.calls += 1
        if self.fail_on and self.fail_on in messages[-1]["content"]:
            raise RuntimeError("VM returned 503")
        text = "Farmers get Rs. 6000 a year in three installments."
        return LLMResponse(text, text, 30, 12, 42, 250.0, 0, self.model)


class FakeRetriever:
    """Returns one PM-KISAN chunk; low confidence, so the agent wants the web fallback."""

    async def search(self, query, top_k, mode, filters=None):
        chunk = RetrievedChunk(chunk_id="c1", citation_id="SCHEME:pm-kisan#benefits", scheme_slug="pm-kisan",
                               scheme_name="PM-KISAN", ministry="MoAFW", section="overview_benefits",
                               text="Rs. 6000 per year in three installments.", source_url="https://pmkisan.gov.in",
                               rerank_score=0.1)
        return RetrievalOutput(results=[chunk], mode=mode, top_rerank_score=0.1, low_confidence=True, latency_ms=12.5)


def test_subset_is_fixed_balanced_and_skips_dropped_items():
    items = ITEMS + [_item(7, "benefits", status="dropped")]
    assert [i["id"] for i in select_items(items)] == [f"GQA-{n:03d}" for n in range(1, 7)]
    subset = select_items(items, subset=3)
    assert subset == select_items(items, subset=3)
    assert sorted(i["aspect"] for i in subset) == ["benefits", "documents_required", "eligibility"]


def test_gold_rank_counts_distinct_schemes():
    assert gold_rank(["a", "a", "b", "pm-kisan"], "pm-kisan") == 3
    assert gold_rank(["a"], "pm-kisan") is None


def test_answers_are_cleaned_before_text_overlap():
    raw = "**PM-KISAN** pays Rs. 6000 a year [1], in three equal installments [2, 3]. See https://pmkisan.gov.in\n- Apply online."
    assert clean_answer(raw) == "PM-KISAN pays Rs. 6000 a year , in three equal installments . See Apply online."
    ref = "Rs. 6000 a year is paid in three equal installments."
    scores = text_overlap_scores(ref, ref, rouge_scorer.RougeScorer(["rougeL"], use_stemmer=True), BLEU(effective_order=True))
    assert scores["rouge_l"] == 1.0 and scores["bleu"] > 99


async def test_closed_book_run_saves_resumes_and_retries_errors(tmp_path):
    flaky = FakeClosedBookLLM(fail_on="Question 2 ")
    run = await run_config(CONFIGS["no_corpus"], ITEMS[:3], runs_dir=tmp_path, llm=flaky)
    assert [r["status"] for r in run["results"].values()] == ["ok", "error", "ok"]
    assert run["results"]["GQA-001"]["total_ms"] == 250.0 and run["meta"]["faq_chunks_excluded"] is True

    healthy = FakeClosedBookLLM()
    resumed = await run_config(CONFIGS["no_corpus"], ITEMS[:3], runs_dir=tmp_path, llm=healthy)
    assert healthy.calls == 1, "only the failed question is asked again"
    assert all(r["status"] == "ok" for r in resumed["results"].values())


async def test_agent_run_records_retrieval_latency_and_skipped_web_fallback(tmp_path):
    settings = get_settings()
    before = (settings.agent_reflection_enabled, settings.retrieval_top_k_override, settings.retrieval_exclude_faq_chunks)
    llm = ScriptedLLM(_search_plan("SCHEME_QA"), ['{"decision": "answer", "reason": "ok"}'])
    run = await run_config(CONFIGS["top3"], ITEMS[:1], runs_dir=tmp_path, llm=llm, retriever=FakeRetriever())

    record = run["results"]["GQA-001"]
    assert record["answer"] and record["status"] == "ok"
    assert record["gold_scheme_rank"] == 1 and record["chunks_given"] == 1
    assert record["retrieval_ms"] > 0 and record["total_ms"] >= record["retrieval_ms"]
    assert record["web_fallback_skipped"] is True, "low confidence would have triggered the (disabled) web fallback"
    assert run["meta"]["top_k"] == 3
    assert (settings.agent_reflection_enabled, settings.retrieval_top_k_override,
            settings.retrieval_exclude_faq_chunks) == before, "eval settings must be restored"


class FakeJudge:
    model = "fake-judge"

    def __init__(self):
        self.calls = 0

    async def chat_completion(self, messages, **_kw) -> LLMResponse:
        self.calls += 1
        text = '{"score": 4, "reason": "main fact correct"}'
        return LLMResponse(text, text, 50, 10, 60, 100.0, 0, self.model)


async def test_judge_respects_cap_caches_and_skips_errors(tmp_path):
    run = await run_config(CONFIGS["no_corpus"], ITEMS[:3], runs_dir=tmp_path, llm=FakeClosedBookLLM(fail_on="Question 3 "))
    runs, cache_path = {"no_corpus": run}, tmp_path / "judge.json"

    judge = FakeJudge()
    cache = await judge_runs(runs, ["no_corpus"], max_calls=1, cache_path=cache_path, llm=judge)
    assert judge.calls == 1 and len(cache) == 1
    cache = await judge_runs(runs, ["no_corpus"], max_calls=5, cache_path=cache_path, llm=judge)
    assert judge.calls == 2 and len(cache) == 2, "cached verdicts are reused; the errored answer is never judged"

    scored = score_records(runs, cache, use_bertscore=False)
    report = build_report(runs, scored, retrieval=None)
    summary = report["configs"]["no_corpus"]
    assert summary["n"] == 2 and summary["errors"] == 1
    assert summary["judge_mean"] == 4.0 and summary["judge_correct_rate"] == 1.0
    md = render_markdown(report, {"counts": {"items": 3}})
    assert "| `no_corpus` |" in md and "Latency and cost" in md
    assert json.loads(cache_path.read_text(encoding="utf-8"))


class QuotaJudge:
    model = "fake-judge"

    def __init__(self):
        self.calls = 0

    async def chat_completion(self, messages, **_kw) -> LLMResponse:
        self.calls += 1
        raise QuotaExhaustedError("LLM API quota exhausted (fake-judge)")


async def test_judge_stops_at_first_quota_error(tmp_path):
    """24 Nov: a used-up Gemini quota made every judge call fail, but the run kept calling up to its cap."""
    run = await run_config(CONFIGS["no_corpus"], ITEMS[:3], runs_dir=tmp_path, llm=FakeClosedBookLLM())
    judge = QuotaJudge()
    cache = await judge_runs({"no_corpus": run}, ["no_corpus"], max_calls=10, cache_path=tmp_path / "j.json", llm=judge)
    assert judge.calls == 1 and cache == {}