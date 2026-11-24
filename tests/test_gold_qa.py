"""Gold Q&A builder: sampling, draft checks, resume and review round trip (fake LLM, real scheme DB)."""

from __future__ import annotations

import csv
import json
import re
from collections import Counter

import pytest
from rouge_score import rouge_scorer

from backend.db.repositories import Repository
from backend.gateway.llm_client import LLMResponse
from eval.build_gold_qa import (
    ASPECTS,
    GoldQADraft,
    apply_review,
    build,
    closest_faq,
    dry_run,
    export_review,
    load_dataset,
    rejection_reasons,
)

SCHEME = {"slug": "demo", "scheme_name": "Demo Kisan Support Scheme", "short_title": "DKSS"}
SECTION = ("Financial benefit of Rs. 6000 per annum per family is paid in three equal installments. "
           "The amount is transferred directly into the bank accounts of the beneficiaries.")
GOOD = GoldQADraft(
    question="How is the money paid under the Demo Kisan Support Scheme?",
    answer="Rs. 6,000 a year is paid in three equal installments into the beneficiary's bank account.",
    evidence_quote="Financial benefit of Rs. 6000 per annum per family is paid in three equal installments.",
)


class FakeLLM:
    """Answers like a well-behaved model: names the scheme and quotes the first sentence of the section."""

    model = "fake-model"

    def __init__(self, fail_names: set[str] | None = None):
        self.calls = 0
        self.fail_names = fail_names or set()

    async def chat_completion(self, messages, **_kwargs) -> LLMResponse:
        self.calls += 1
        user = messages[-1]["content"]
        name = re.search(r"Scheme Name: (.+)", user).group(1).strip()
        if name in self.fail_names:
            raise RuntimeError("VM returned 503")
        section = user.split("Section Text:\n", 1)[1].split("\n\nExisting FAQs", 1)[0]
        quote = next(s for s in re.split(r"(?<=[.!?])\s+", section) if len(s.split()) >= 5)
        content = json.dumps({"question": f"What does {name} say about the zebra crossing rules here?",
                              "answer": "It explains the zebra crossing rules.", "evidence_quote": quote})
        return LLMResponse(content=content, raw_content=content, prompt_tokens=10, completion_tokens=10,
                           total_tokens=20, latency_ms=1.0, retries=0, model=self.model)


def test_good_draft_is_accepted_and_commas_in_amounts_do_not_matter():
    assert rejection_reasons(GOOD, SCHEME, SECTION, faq_similarity=0.1) == []


def test_invented_amount_is_rejected():
    draft = GOOD.model_copy(update={"answer": "Rs. 8,000 a year is paid in three installments."})
    assert rejection_reasons(draft, SCHEME, SECTION, 0.1) == ["numbers_not_in_section:8000"]


def test_quote_must_be_real_and_long_enough():
    made_up = GOOD.model_copy(update={"evidence_quote": "Every farmer gets a free tractor every year."})
    too_short = GOOD.model_copy(update={"evidence_quote": "three equal installments"})
    assert "quote_not_in_section" in rejection_reasons(made_up, SCHEME, SECTION, 0.1)
    assert "quote_not_in_section" in rejection_reasons(too_short, SCHEME, SECTION, 0.1)


def test_question_must_name_the_scheme_by_full_name_or_short_title():
    unnamed = GOOD.model_copy(update={"question": "How is the money paid under this scheme?"})
    short = GOOD.model_copy(update={"question": "How is the DKSS money paid?"})
    assert "question_missing_scheme_name" in rejection_reasons(unnamed, SCHEME, SECTION, 0.1)
    assert rejection_reasons(short, SCHEME, SECTION, 0.1) == []


def test_rephrased_real_faq_is_too_close_but_a_new_question_is_not():
    repo = Repository()
    scheme = repo.get_scheme("pm-kisan")
    faqs = [f["question"] for f in repo.get_scheme_faqs("pm-kisan")]
    scorer = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=True)
    _, copied = closest_faq("What are the benefits of the Pradhan Mantri Kisan Samman Nidhi scheme?", faqs, scheme, scorer)
    _, new = closest_faq("Into whose account does Pradhan Mantri Kisan Samman Nidhi send each Rs 2000 payment?",
                         faqs, scheme, scorer)
    assert "too_close_to_faq" in rejection_reasons(GOOD, SCHEME, SECTION, copied)
    assert new < copied and "too_close_to_faq" not in rejection_reasons(GOOD, SCHEME, SECTION, new)


def test_sampling_is_fixed_balanced_and_spread_across_ministries():
    repo = Repository()
    picks = dry_run(60, repo)
    assert picks == dry_run(60, repo)
    assert len({slug for slug, _, _ in picks}) == 60
    assert Counter(a for _, _, a in picks) == {a: 15 for a in ASPECTS}
    assert len({m for _, m, _ in picks}) >= 40


async def test_build_accepts_saves_and_resumes_without_redoing_schemes(tmp_path):
    out = tmp_path / "gold.json"
    llm, repo = FakeLLM(), Repository()
    first = await build(target=4, out_path=out, max_calls=10, llm=llm, repo=repo)
    assert len(first["items"]) == 4 and llm.calls == 4
    assert all(i["review"]["status"] == "unreviewed" and i["generator_model"] == "fake-model" for i in first["items"])
    assert [i["id"] for i in first["items"]] == ["GQA-001", "GQA-002", "GQA-003", "GQA-004"]

    resumed = await build(target=6, out_path=out, max_calls=10, llm=llm, repo=repo)
    slugs = [i["scheme_slug"] for i in resumed["items"]]
    assert len(slugs) == 6 == len(set(slugs)) and llm.calls == 6


async def test_failed_call_is_logged_and_retried_on_the_next_run(tmp_path):
    out, repo = tmp_path / "gold.json", Repository()
    first_name = repo.get_scheme(dry_run(1, repo)[0][0])["scheme_name"]
    failed = await build(target=1, out_path=out, max_calls=1, llm=FakeLLM(fail_names={first_name}), repo=repo)
    assert failed["items"] == [] and failed["rejected"][0]["reasons"] == ["llm_error"]

    retried = await build(target=1, out_path=out, max_calls=1, llm=FakeLLM(), repo=repo)
    assert retried["items"][0]["scheme_name"] == first_name and retried["rejected"] == []


async def test_review_sheet_round_trip(tmp_path):
    out, sheet = tmp_path / "gold.json", tmp_path / "review.csv"
    await build(target=3, out_path=out, max_calls=3, llm=FakeLLM(), repo=Repository())
    dataset = load_dataset(out)
    assert export_review(dataset, sheet) == 3

    with sheet.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    rows[0]["verdict"] = "ok"
    rows[1].update(verdict="FIX", reference_answer="Corrected answer.", notes="answer was vague")
    rows[2]["verdict"] = "drop"
    with sheet.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    assert apply_review(dataset, sheet) == {"ok": 1, "fix": 1, "drop": 1}
    fixed = dataset["items"][1]
    assert [i["review"]["status"] for i in dataset["items"]] == ["approved", "corrected", "dropped"]
    assert fixed["reference_answer"] == "Corrected answer." and fixed["review"]["original_answer"]
    assert fixed["review"]["notes"] == "answer was vague"


def test_review_sheet_with_a_bad_verdict_is_refused(tmp_path):
    sheet = tmp_path / "review.csv"
    dataset = {"items": [{"id": "GQA-001", "question": "q", "reference_answer": "a", "review": {"status": "unreviewed"}}]}
    sheet.write_text("id,question,reference_answer,verdict\nGQA-001,q,a,maybe\n", encoding="utf-8-sig")
    with pytest.raises(ValueError, match="invalid verdicts"):
        apply_review(dataset, sheet)
