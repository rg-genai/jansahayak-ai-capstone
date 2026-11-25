"""Agent loop (Planner -> Executor <-> Reflector) behaviour: re-search, clarifying questions, loop guards.

A scripted fake LLM stands in for Qwen3-8B so the control flow is tested deterministically;
tools (retrieval, eligibility) are the real ones.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from backend.agent.graph import JanSahayakAgent, _is_bare_identifier, _validate_reflection, _verified_continuation
from backend.agent.state import ReflectionOutput
from backend.config import get_settings
from backend.gateway.llm_client import LLMResponse

PRIYA = {
    "age": 19, "gender": "Female", "state": "Maharashtra", "annual_income_inr": 180000,
    "social_category": "OBC", "occupation": "Student", "education_level": "B.Tech",
}


class ScriptedLLM:
    """Returns canned replies per node, recognised by each node's system prompt."""

    model = "fake-qwen"

    def __init__(self, planner: dict, reflections: list[str]):
        self.planner = json.dumps(planner)
        self.reflections = list(reflections)
        self.calls: list[str] = []

    async def chat_completion(self, messages: list[dict[str, str]], **_: Any) -> LLMResponse:
        system = messages[0]["content"]
        if "Planner Node" in system:
            node, content = "planner", self.planner
        elif "Reflector Node" in system:
            node = "reflector"
            content = self.reflections.pop(0) if self.reflections else '{"decision": "answer", "reason": "done"}'
        elif "Critic" in system:
            node, content = "critic", '{"passed": true, "issues": [], "needs_revision": false, "revision_instructions": null}'
        else:
            node, content = "synthesizer", "**Schemes That May Suit You**\n- A matching scheme [1]."
        self.calls.append(node)
        return LLMResponse(content, content, 50, 20, 70, 1.0, 0, self.model)


def _search_plan(intent: str = "ELIGIBILITY_CHECK") -> dict:
    return {"intent": intent, "profile_updates": {}, "reasoning": "search first",
            "tool_calls": [{"tool_name": "search_schemes", "arguments": {"query": "x", "top_k": 6}}]}


def _searches(state: dict) -> list[dict]:
    return [t for t in state["tool_calls_log"] if t["tool"] == "search_schemes"]


@pytest.mark.asyncio
async def test_reflector_searches_again_then_answers():
    llm = ScriptedLLM(_search_plan("SCHEME_QA"), [
        '{"decision": "search_again", "new_query": "post matric scholarship for OBC engineering students", "reason": "off-topic"}',
        '{"decision": "answer", "reason": "good results"}',
    ])
    state = await JanSahayakAgent(llm=llm).run("Tell me about education help for students", "test-loop-1", citizen_profile=PRIYA)

    assert len(_searches(state)) == 2, "the Reflector's new query must trigger a second search"
    assert state["searched_queries"][1] == "post matric scholarship for OBC engineering students"
    assert [r["decision"] for r in state["reflections"]] == ["search_again", "answer"]
    assert llm.calls.count("synthesizer") == 1 and state["final_answer"]


@pytest.mark.asyncio
async def test_reflector_asks_user_instead_of_guessing():
    llm = ScriptedLLM(_search_plan(), [
        '{"decision": "ask_user", "question": "What is your age, occupation and yearly family income?", "reason": "empty profile"}',
    ])
    state = await JanSahayakAgent(llm=llm).run("Which schemes am I eligible for?", "test-loop-2", citizen_profile={})

    assert state["status"] == "awaiting_user_input"
    assert "occupation" in state["final_answer"]
    assert "synthesizer" not in llm.calls, "no answer should be written when the agent is asking"


@pytest.mark.asyncio
async def test_loop_stops_at_max_rounds_even_if_model_keeps_searching():
    """Infinite-loop guard: a model that always wants to search again is stopped by the round cap."""
    llm = ScriptedLLM(_search_plan("SCHEME_QA"), [
        json.dumps({"decision": "search_again", "new_query": f"different query number {i}", "reason": "again"})
        for i in range(10)
    ])
    state = await JanSahayakAgent(llm=llm).run("education schemes", "test-loop-3", citizen_profile=PRIYA)

    settings = get_settings()
    assert state["reflection_round"] == settings.agent_max_reflection_rounds
    assert state["reflections"][-1]["guard"] == "max_reflection_rounds_reached"
    assert len(state["tool_calls_log"]) <= settings.agent_max_tool_calls
    assert state["final_answer"]


@pytest.mark.asyncio
async def test_malformed_reflector_json_falls_back_to_answer():
    llm = ScriptedLLM(_search_plan("SCHEME_QA"), ["this is not json at all"])
    state = await JanSahayakAgent(llm=llm).run("scholarship schemes", "test-loop-4", citizen_profile=PRIYA)

    assert state["reflections"][0]["decision"] == "answer"
    assert state["reflections"][0]["guard"] == "unparseable_reflection_json"
    assert state["final_answer"]


# ---- Pure loop-guard unit tests (no LLM, no retrieval) ----

def _state(**kw: Any) -> dict:
    base = {"tool_calls_log": [{}] * 2, "searched_queries": ["pm kisan farmer"], "eligibility_cards": [],
            "retrieved_chunks": [{"scheme_slug": "pm-kisan"}, {"scheme_slug": "pmfby"}]}
    return {**base, **kw}


def test_guard_blocks_repeated_query():
    d, guard = _validate_reflection(ReflectionOutput(decision="search_again", new_query="PM-Kisan, farmer!"), _state(), 10)
    assert d.decision == "answer" and guard == "repeated_or_empty_query"


def test_guard_drops_invented_and_already_checked_slugs():
    d, guard = _validate_reflection(
        ReflectionOutput(decision="check_eligibility", scheme_slugs=["made-up-slug", "pm-kisan", "pmfby"]),
        _state(eligibility_cards=[{"scheme_slug": "pm-kisan"}]), 10,
    )
    assert guard is None and d.scheme_slugs == ["pmfby"]

    d, guard = _validate_reflection(ReflectionOutput(decision="check_eligibility", scheme_slugs=["made-up-slug"]), _state(), 10)
    assert d.decision == "answer" and guard == "no_valid_unchecked_slugs"


def test_guard_enforces_tool_call_budget():
    d, guard = _validate_reflection(
        ReflectionOutput(decision="search_again", new_query="a brand new query"), _state(tool_calls_log=[{}] * 10), 10
    )
    assert d.decision == "answer" and guard == "tool_call_budget_exhausted"


def test_guard_rejects_empty_question():
    d, guard = _validate_reflection(ReflectionOutput(decision="ask_user", question="  "), _state(), 10)
    assert d.decision == "answer" and guard == "empty_clarifying_question"


@pytest.mark.parametrize("query", [
    "What is the minimum age requirement for someone to apply for the Craftsmen Training Scheme?",  # GQA-031
    "Can someone working in a Non-Governmental Organisation apply for the National Renewable Energy Internship Scheme?",
])
def test_guard_answers_general_rule_questions_instead_of_asking_age(query):
    """Regression gold eval GQA-031 / GQA-038: the Reflector asked the citizen's age for a question about the rules."""
    d, guard = _validate_reflection(
        ReflectionOutput(decision="ask_user", question="What is your current age (in years)?"), _state(query_en=query), 10
    )
    assert d.decision == "answer" and guard == "general_question_not_about_citizen"


def test_guard_still_lets_personal_questions_ask():
    d, guard = _validate_reflection(
        ReflectionOutput(decision="ask_user", question="What is your age?"), _state(query_en="Am I eligible for PM-KISAN?"), 10
    )
    assert d.decision == "ask_user" and guard is None


@pytest.mark.asyncio
@pytest.mark.parametrize("query", [
    "What is the email address for submitting a proposal for a research study under the Research Study/Seminar "
    "(Grant-in-Aid Scheme)?",  # GQA-045
    "What email address should be used to contact SFIO for clarifications about the Internship Programme At Serious "
    "Fraud Investigation Office?",  # GQA-060
])
async def test_question_naming_a_catalog_scheme_is_not_out_of_scope(query):
    """Regression gold eval GQA-045 / GQA-060: the planner refused these as OUT_OF_SCOPE."""
    llm = ScriptedLLM({"intent": "OUT_OF_SCOPE", "tool_calls": [], "reasoning": "contact details"}, [])
    state = await JanSahayakAgent(llm=llm).run(query, "test-loop-10", citizen_profile={})

    assert state["planner_output"]["intent"] == "SCHEME_QA"
    assert state["planner_output"]["guard"] == "named_catalog_scheme_is_in_scope"
    assert _searches(state) and "synthesizer" in llm.calls


@pytest.mark.asyncio
async def test_out_of_scope_without_a_scheme_name_is_still_refused():
    llm = ScriptedLLM({"intent": "OUT_OF_SCOPE", "tool_calls": [], "reasoning": "cricket"}, [])
    state = await JanSahayakAgent(llm=llm).run("Who won the cricket world cup?", "test-loop-11", citizen_profile={})
    assert state["planner_output"]["intent"] == "OUT_OF_SCOPE" and not state.get("tool_calls_log")


def _chunk(slug: str, part: int, section: str = "process_documents") -> dict:
    return {"chunk_id": f"{slug}__{section}__{part}", "citation_id": f"SCHEME:{slug}#{section}", "scheme_slug": slug,
            "scheme_name": slug, "ministry": "M", "section": section, "source_url": "https://x.gov.in",
            "text": f"{slug} {section} part {part}", "scores": {"rerank": 0.9}}


def _fixed_search(results: list[dict]):
    async def search(inp, citizen_profile=None):
        return {"results": results, "top_rerank_score": 0.9, "low_confidence": False}
    return search


@pytest.mark.asyncio
async def test_parts_of_one_section_are_all_kept():
    """Regression gold eval GQA-021: chunks were deduped by citation_id, so parts 2-4 of a section were dropped."""
    agent = JanSahayakAgent(llm=ScriptedLLM(_search_plan("SCHEME_QA"), []))
    agent.toolbox.search_schemes = _fixed_search([_chunk("a", 0), _chunk("a", 1), _chunk("b", 0)])
    state = await agent.run("how do these grants work", "test-loop-12", citizen_profile={})
    assert [c["chunk_id"] for c in state["retrieved_chunks"]] == ["a__process_documents__0", "a__process_documents__1",
                                                                  "b__process_documents__0"]


def test_named_scheme_evidence_keeps_lead_scheme_then_two_other_slots():
    from backend.agent.graph import _lead_scheme_first
    results = [_chunk("lead", 2), _chunk("other1", 0), _chunk("lead", 0), _chunk("other2", 0), _chunk("other3", 0)]
    sections = [_chunk("lead", i) for i in range(4)] + [_chunk("lead", 0, "overview_benefits")]
    ids = [c["chunk_id"] for c in _lead_scheme_first(results, sections, evidence_cap=8)]
    assert ids == [
        "lead__process_documents__2", "lead__process_documents__0",  # what search ranked first stays first
        "lead__process_documents__1", "lead__process_documents__3", "lead__overview_benefits__0",  # rest of the scheme
        "other1__process_documents__0", "other2__process_documents__0", "other3__process_documents__0",
    ]
    many_sections = [_chunk("lead", i) for i in range(10)]
    ids = [c["chunk_id"] for c in _lead_scheme_first(results, many_sections, evidence_cap=8)][:8]
    assert ids[6:] == ["other1__process_documents__0", "other2__process_documents__0"], "2 slots stay for other schemes"


@pytest.mark.asyncio
async def test_named_scheme_question_reads_all_of_its_application_process():
    """Regression gold eval GQA-021: the answer said the scheme does not mention NGO-PS Portal registration."""
    q = ("Do I need to register with the NGO-PS Portal to apply for the Financial Assistance For Promotion Of "
         "Guru-Shishya Parampara (Repertory Grant)?")
    agent = JanSahayakAgent(llm=ScriptedLLM(_search_plan("SCHEME_QA"), []))
    agent.toolbox.search_schemes = _fixed_search([_chunk("fapgsprg", 0, "overview_benefits"), _chunk("other", 0)])
    state = await agent.run(q, "test-loop-13", citizen_profile={})
    ids = [c["chunk_id"] for c in state["retrieved_chunks"]]
    assert "fapgsprg__process_documents__0" in ids, "the only chunk that mentions the NGO-PS Portal must be read"
    assert sum(i.startswith("fapgsprg__") for i in ids) == 6, "the named scheme fills all but the reserved slots"
    assert "other__process_documents__0" in ids and len(ids) <= 8


def _recording_search(results: list[dict], seen_profiles: list):
    async def search(inp, citizen_profile=None):
        seen_profiles.append(citizen_profile)
        return {"results": results, "top_rerank_score": 0.9, "low_confidence": False}
    return search


@pytest.mark.asyncio
async def test_named_scheme_eligibility_is_not_hidden_by_profile_filters():
    """Regression task eval ELIG-01: a 60-year-old asked about PMKVY-RPL (ages 18-45). The age filter removed that
    scheme from the search, so the agent checked other schemes and never said 'not eligible'."""
    q = "I am 60 years old. Am I eligible for Pradhan Mantri Kaushal Vikas Yojana - Recognition Of Prior Learning?"
    seen: list = []
    agent = JanSahayakAgent(llm=ScriptedLLM(_search_plan("ELIGIBILITY_CHECK"), []))
    agent.toolbox.search_schemes = _recording_search([_chunk("pmkvy-rpl", 0, "eligibility_exclusions")], seen)
    state = await agent.run(q, "test-loop-elig01", citizen_profile={"age": 60})
    assert seen and not any(seen), "a named-scheme search must not filter by the citizen's profile"
    verdicts = {t["args"]["scheme_slug"]: t.get("verdict") for t in state["tool_calls_log"] if t["tool"] == "check_eligibility"}
    assert verdicts.get("pmkvy-rpl") == "NOT_ELIGIBLE", "age 60 is over the scheme's 45-year limit"


@pytest.mark.asyncio
async def test_discovery_search_still_uses_the_profile_filters():
    """Filters stay on for questions that name no scheme: there they narrow the catalog to what may fit."""
    seen: list = []
    agent = JanSahayakAgent(llm=ScriptedLLM(_search_plan("ELIGIBILITY_CHECK"), []))
    agent.toolbox.search_schemes = _recording_search([_chunk("a", 0, "eligibility_exclusions")], seen)
    await agent.run("I need money for my studies", "test-loop-discovery", citizen_profile={"age": 19})
    assert seen and seen[0]["age"] == 19


@pytest.mark.parametrize("message", ["1234 5678 9012", "NSP/2024/123456", "[AADHAAR_MASKED:XXXX-XXXX-0124]", "MH12AB1234"])
def test_bare_identifier_detected(message):
    assert _is_bare_identifier(message)


@pytest.mark.parametrize("message", ["track my complaint MOAFW/E/2026/000001", "my PM-KISAN money is late", "hello", "Which schemes am I eligible for?"])
def test_real_requests_are_not_bare_identifiers(message):
    assert not _is_bare_identifier(message)


@pytest.mark.asyncio
async def test_bare_id_asks_instead_of_drafting_grievance():
    """Regression: the 8B planner drafted a PM-KISAN grievance from the bare message '1234 5678 9012'."""
    llm = ScriptedLLM({"intent": "GRIEVANCE_DRAFT", "tool_calls": [{"tool_name": "draft_grievance", "arguments": {
        "scheme_name": "PM-KISAN", "ministry": "MOAFW", "issue_summary": "x"}}]}, [])
    state = await JanSahayakAgent(llm=llm).run("1234 5678 9012", "test-loop-5", citizen_profile=PRIYA)

    assert state["status"] == "awaiting_user_input"
    assert not state.get("grievance_draft") and not state.get("tool_calls_log")
    assert llm.calls == [], "no LLM call or tool should run for a bare ID"


_HISTORY = [{"role": "user", "content": "Which schemes am I eligible for?"},
            {"role": "assistant", "content": "To give you an accurate answer, I need a little more information.\n\n"
                                             "**What is your age, occupation, and yearly family income?**"}]


def test_continuation_accepted_only_if_in_history():
    assert _verified_continuation("Which schemes am I eligible for?", _HISTORY) == "Which schemes am I eligible for?"
    assert _verified_continuation("which schemes am i eligible for", _HISTORY) == "Which schemes am I eligible for?"
    assert _verified_continuation("Tell me about PM-KISAN", _HISTORY) is None  # hallucinated "original request"
    assert _verified_continuation(None, _HISTORY) is None


@pytest.mark.asyncio
async def test_answer_to_clarifying_question_continues_original_request():
    llm = ScriptedLLM({"intent": "ELIGIBILITY_CHECK", "continues_request": "Which schemes am I eligible for?",
                       "profile_updates": {"age": 45, "occupation": "Farmer", "annual_income_inr": 100000},
                       "tool_calls": [{"tool_name": "search_schemes", "arguments": {"query": "x"}}]}, [])
    state = await JanSahayakAgent(llm=llm).run(
        "I am 45, a farmer, and we earn about 1 lakh a year", "test-loop-6", citizen_profile={}, history=_HISTORY)

    assert state["query_en"] == "Which schemes am I eligible for?"
    assert state["citizen_profile"]["occupation"] == "Farmer"
    first_search = state["searched_queries"][0]
    assert "farmer" in first_search.lower() and "45" in first_search, "broad eligibility search should use the new profile"


@pytest.mark.asyncio
async def test_continuation_detected_even_when_model_omits_it():
    """Live Qwen3-8B returned profile_updates but no continues_request; our own question in history is used."""
    llm = ScriptedLLM({"intent": "ELIGIBILITY_CHECK", "profile_updates": {"age": 45, "occupation": "Farmer"},
                       "tool_calls": [{"tool_name": "search_schemes", "arguments": {"query": "x"}}]}, [])
    state = await JanSahayakAgent(llm=llm).run("I am 45 and a farmer", "test-loop-7", citizen_profile={}, history=_HISTORY)
    assert state["query_en"] == "Which schemes am I eligible for?"


# ---- TRC-6232CFB779 ("I need money for my studies"): relevance signal, need query, ruled-out / invented verdicts ----

def _scheme_name(slug: str) -> str:
    from backend.db.repositories import Repository
    return Repository().get_scheme(slug)["scheme_name"]


def _trc_6232_cards_and_chunks() -> tuple[list[dict], list[dict]]:
    verdicts = {"nsigse": "NOT_ELIGIBLE", "csspostmsossi": "ELIGIBLE", "i-mesa-eas": "NOT_ELIGIBLE", "icar-jrf-pgs": "NOT_ELIGIBLE"}
    cards = [{"scheme_slug": s, "scheme_name": _scheme_name(s), "verdict": v} for s, v in verdicts.items()]
    chunks = [{"scheme_slug": s, "scheme_name": _scheme_name(s), "citation_id": f"SCHEME:{s}#x"}
              for s in [*verdicts, "wmcl", "pm-usp-sssjkl"]]
    return cards, chunks


def test_observation_spells_out_low_relevance():
    from backend.agent.graph import _summarize_observations
    state = {"query_en": "I need money for my studies", "planner_output": {"intent": "ELIGIBILITY_CHECK"},
             "citizen_profile": PRIYA, "retrieved_chunks": [{"scheme_slug": "nsigse", "scheme_name": "X", "scores": {"rerank": 0.05}}]}
    text = _summarize_observations(state, 10, 0.25)
    assert "Search relevance: LOW" in text and "0.05" in text


def test_need_query_keeps_citizen_words_and_adds_profile():
    from backend.agent.profile_matching import get_catalog_vocabulary
    from backend.agent.state import CitizenProfile
    from backend.db.repositories import Repository
    vocab = get_catalog_vocabulary(Repository())
    q = vocab.build_need_query("I need money for my studies", CitizenProfile(**PRIYA))
    assert q.startswith("I need money for my studies") and "OBC" in q and "student" in q and "B.Tech" in q
    assert vocab.build_need_query("I need money for my studies", CitizenProfile()) == "I need money for my studies"


def test_ruled_out_schemes_removed_only_in_multi_scheme_answers():
    from backend.agent.graph import _drop_ruled_out_schemes
    cards, chunks = _trc_6232_cards_and_chunks()
    kept, ruled_out = _drop_ruled_out_schemes(chunks, cards)
    assert [c["scheme_slug"] for c in kept] == ["csspostmsossi", "wmcl", "pm-usp-sssjkl"]
    assert len(ruled_out) == 3

    single = [{"scheme_slug": "pm-kisan", "scheme_name": "PM-KISAN", "verdict": "NOT_ELIGIBLE"}]
    assert _drop_ruled_out_schemes(chunks, single) == (chunks, [])  # "Am I eligible for X?" -> "No" IS the answer


def test_critic_flags_invented_and_ruled_out_statuses_from_real_trace():
    from backend.agent.graph import _verdict_consistency_issues
    cards, chunks = _trc_6232_cards_and_chunks()
    n = {c["scheme_slug"]: c["scheme_name"] for c in chunks}
    answer = "\n".join([  # shape of the real TRC-6232CFB779 answer
        f"- **{n['csspostmsossi']}** [2] **Likely Eligible**: support for OBC students.",
        f"- **{n['wmcl']}** [5] **Partially Eligible**: assistance for graduation.",
        f"- **{n['icar-jrf-pgs']}** [4] **Not Eligible**: for agricultural post-graduates.",
    ])
    issues = _verdict_consistency_issues(answer, cards, chunks)
    assert len(issues) == 2
    assert any("NOT checked" in i and n["wmcl"] in i for i in issues)          # invented verdict
    assert any("ruled NOT_ELIGIBLE" in i and n["icar-jrf-pgs"] in i for i in issues)
    assert _verdict_consistency_issues(answer.splitlines()[0], cards, chunks) == []  # the correct line is fine


@pytest.mark.asyncio
async def test_open_ended_need_uses_profile_and_checks_several_schemes():
    llm = ScriptedLLM(_search_plan("ELIGIBILITY_CHECK"), ['{"decision": "answer", "reason": "ok"}'])
    state = await JanSahayakAgent(llm=llm).run("I need money for my studies", "test-loop-8", citizen_profile=PRIYA)

    first_search = state["searched_queries"][0]
    assert first_search.startswith("I need money for my studies") and "OBC" in first_search
    checks = [t for t in state["tool_calls_log"] if t["tool"] == "check_eligibility"]
    assert len(checks) >= 2, "an open-ended need should check several schemes, not only the top one"


def test_shared_name_prefix_does_not_cause_false_flag():
    """Regression TRC-1BAB107B93: Post-Matric (ELIGIBLE) line was flagged as Pre-matric (NOT_ELIGIBLE)."""
    from backend.agent.graph import _verdict_consistency_issues
    post, pre, usp = _scheme_name("csspostmsossi"), _scheme_name("csspremsobcsi"), _scheme_name("csss-cus")
    cards = [{"scheme_slug": "csspostmsossi", "scheme_name": post, "verdict": "ELIGIBLE"},
             {"scheme_slug": "csspremsobcsi", "scheme_name": pre, "verdict": "NOT_ELIGIBLE"},
             {"scheme_slug": "csss-cus", "scheme_name": usp, "verdict": "ELIGIBLE"}]
    good = f"- **{post}** [1] | **Likely Eligible** | Monthly allowance for B.Tech students."
    assert _verdict_consistency_issues(good, cards, []) == []
    bad = f"- **{pre}** [3] | **Not Eligible** | For Class 9-10 students."
    assert len(_verdict_consistency_issues(bad, cards, [])) == 1
    # a shortened but still distinctive name is still caught
    short = "- **Pradhan Mantri Uchchatar Shiksha Protsahan (PM-USP)** [2] | **Likely Eligible** | Rs 12,000."
    assert _verdict_consistency_issues(short, cards, []) == []


@pytest.mark.asyncio
async def test_web_fallback_uses_the_enriched_query():
    """Regression TRC-1BAB107B93: the web fallback searched the bare message and found nothing."""
    agent = JanSahayakAgent(llm=ScriptedLLM(_search_plan("ELIGIBILITY_CHECK"), ['{"decision": "answer", "reason": "ok"}']))
    web_queries: list[str] = []

    async def low_confidence_search(inp, citizen_profile=None):
        return {"results": [{"citation_id": "SCHEME:csss-cus#x", "scheme_slug": "csss-cus", "scheme_name": "PM-USP",
                             "ministry": "MoE", "section": "faq", "source_url": "https://x.gov.in", "text": "t",
                             "scores": {"rerank": 0.1}}],
                "top_rerank_score": 0.1, "low_confidence": True}

    async def spy_web_search(inp):
        web_queries.append(inp.query)
        return {"results": [], "provider": "spy"}

    agent.toolbox.search_schemes = low_confidence_search
    agent.toolbox.web_search_gov_schemes = spy_web_search
    await agent.run("I need money for my studies", "test-loop-9", citizen_profile=PRIYA)

    assert web_queries and web_queries[0].startswith("I need money for my studies - for a 19-year-old")
