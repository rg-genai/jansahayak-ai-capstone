"""Broad "which schemes am I eligible for?" handling: query detection, profile matching, stricter verdicts."""

from __future__ import annotations

import pytest

from backend.agent.graph import _deterministic_critic_check, _is_broad_eligibility_query
from backend.agent.profile_matching import get_catalog_vocabulary, profile_education_stage, scheme_education_stages
from backend.agent.state import CitizenProfile
from backend.agent.tools import AgentToolbox, CheckEligibilityInput
from backend.db.repositories import Repository

PRIYA = CitizenProfile(
    age=19, gender="Female", state="Maharashtra", annual_income_inr=180000,
    social_category="OBC", occupation="Student", is_bpl=False, is_pwd=False, education_level="B.Tech",
)


@pytest.fixture(scope="module")
def vocab():
    return get_catalog_vocabulary(Repository())


@pytest.mark.parametrize(
    "query",
    [
        "Which schemes am I eligible for?",
        "am I eligible for anything?",
        "Which scholarships for OBC students?",
        "Which schemes can a big family get?",  # "big" is a catalog short title, but lowercase
    ],
)
def test_broad_queries_detected(vocab, query):
    assert _is_broad_eligibility_query(query, vocab)


@pytest.mark.parametrize(
    "query",
    [
        "Am I eligible for PM-KISAN?",
        "which benefits for me under pm kisan?",
        "Is PMAY for me?",
        "What schemes are there for Ayushman Bharat?",  # leading segment of a full scheme name
    ],
)
def test_specific_scheme_queries_not_broad(vocab, query):
    assert not _is_broad_eligibility_query(query, vocab)


def test_occupation_groups_come_from_catalog(vocab):
    assert "Student" in vocab.occupation_groups
    assert "Woman" not in vocab.occupation_groups  # profile group, not an occupation
    assert vocab.occupation_group("B.Tech student") == "Student"
    assert vocab.occupation_group("Carpenter") == "Artisan"
    assert vocab.occupation_group("Senior Citizen") is None
    assert "Senior Citizen" in vocab.profile_groups(CitizenProfile(occupation="Senior Citizen"))


def test_discovery_query_uses_profile(vocab):
    query, group = vocab.build_discovery_query(PRIYA)
    assert group == "Student"
    for word in ("19-year-old", "female", "OBC", "student", "180000"):
        assert word in query


@pytest.mark.asyncio
async def test_farmer_only_scheme_not_eligible_for_student():
    """Regression: trace TRC-D886FDB9E5 told a B.Tech student she was ELIGIBLE for National Bamboo Mission."""
    toolbox = AgentToolbox()
    res = await toolbox.check_eligibility(CheckEligibilityInput(scheme_slug="nbm", citizen_profile=PRIYA))
    assert res["verdict"] == "NOT_ELIGIBLE"
    assert any("Farmer" in u for u in res["unmet_criteria"])


@pytest.mark.asyncio
async def test_matching_occupation_scheme_is_eligible():
    toolbox = AgentToolbox()
    res = await toolbox.check_eligibility(CheckEligibilityInput(scheme_slug="nbm", citizen_profile=CitizenProfile(occupation="Farmer")))
    assert res["verdict"] == "ELIGIBLE"


@pytest.mark.parametrize(
    ("education", "expected"),
    [("B.Tech", "undergraduate"), ("12th", "Class 11-12"), ("Class 9", "school (up to Class 10)"),
     ("PhD", "doctoral"), ("M.Sc", "postgraduate"), ("Post Graduate", "postgraduate"), ("", None)],
)
def test_profile_education_stage(education, expected):
    assert profile_education_stage(education) == expected


def test_scheme_education_stages_from_name_and_text():
    assert scheme_education_stages("PM-YASASVI: Pre-Matric Scholarship for OBC", "") == {"school (up to Class 10)"}
    assert "undergraduate" in scheme_education_stages("Scholarship for College and University students", "")
    assert "undergraduate" in scheme_education_stages("Some Scheme", "covers students pursuing studies beyond Class XII")
    assert scheme_education_stages("Agri-Clinics And Agri-Business Centres Scheme", "") == frozenset()  # unknown -> no check


@pytest.mark.asyncio
async def test_btech_student_not_eligible_for_pre_matric_scholarship():
    """Regression: trace TRC-6CBB8CC995 offered a B.Tech student the Pre-Matric (Class 9-10) scholarship."""
    toolbox = AgentToolbox()
    pre = await toolbox.check_eligibility(CheckEligibilityInput(scheme_slug="pmyasasvipmsobcebcdnts", citizen_profile=PRIYA))
    assert pre["verdict"] == "NOT_ELIGIBLE"
    college = await toolbox.check_eligibility(CheckEligibilityInput(scheme_slug="pm-yasasvitcceobcebcdnts", citizen_profile=PRIYA))
    assert college["verdict"] == "ELIGIBLE"


def test_critic_flags_citation_beyond_evidence():
    state = {"draft_answer_en": "Benefit A [1]. Benefit B [3].", "retrieved_chunks": [{}, {}], "web_results": []}
    out = _deterministic_critic_check(state)
    assert not out.passed and "[3]" in out.issues[0]
    state["draft_answer_en"] = "Benefit A [1]. Benefit B [2]."
    assert _deterministic_critic_check(state).passed
