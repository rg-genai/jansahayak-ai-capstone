"""Evaluation switches: FAQ chunks can be kept out of retrieval, and top-k can be fixed for the top-1/3/5 runs.

The defaults must leave the live chatbot unchanged. FAQ tests use BM25-only search (no embedding API);
the agent test uses a fake search tool and the scripted LLM from test_agent_loop.
"""

from __future__ import annotations

import pytest

from backend.agent.graph import JanSahayakAgent
from backend.agent.tools import AgentToolbox, SearchSchemesInput
from backend.config import get_settings
from backend.retrieval.chunker import FAQ_SECTION
from backend.retrieval.hybrid_retriever import HybridRetriever, RetrievalOutput
from tests.test_agent_loop import PRIYA, ScriptedLLM, _search_plan

# PM-KISAN's FAQ asks this almost word for word, so an FAQ chunk ranks high when FAQs are searchable.
FAQ_LIKE_QUERY = "PM Kisan how many times the benefit will be given in a year"


@pytest.fixture(scope="module")
def retrievers() -> dict[bool, HybridRetriever]:
    out = {flag: HybridRetriever(load_reranker=False, exclude_faq_chunks=flag) for flag in (False, True)}
    for retriever in out.values():
        retriever.load()
    return out


def _sections(retriever: HybridRetriever, **kwargs) -> list[str]:
    return [r.section for r in retriever.search_sync(FAQ_LIKE_QUERY, top_k=8, mode="bm25", **kwargs).results]


def test_faq_chunks_are_searchable_by_default(retrievers):
    assert get_settings().retrieval_exclude_faq_chunks is False
    assert HybridRetriever(load_reranker=False).exclude_faq_chunks is False
    assert FAQ_SECTION in _sections(retrievers[False])


def test_excluded_faq_chunks_never_come_back(retrievers):
    assert _sections(retrievers[True]) and FAQ_SECTION not in _sections(retrievers[True])
    assert FAQ_SECTION not in _sections(retrievers[True], filters={"beneficiary_group": "Farmer"})
    relaxed = retrievers[True].search_sync(FAQ_LIKE_QUERY, top_k=8, mode="bm25", filters={"ministry": "no-such-ministry"})
    assert relaxed.filter_relaxed and FAQ_SECTION not in [r.section for r in relaxed.results]


class _RecordingRetriever:
    """Records the top_k the search tool asks for."""

    def __init__(self):
        self.top_ks: list[int] = []

    async def search(self, query, top_k, mode, filters=None):
        self.top_ks.append(top_k)
        return RetrievalOutput(results=[], mode=mode, top_rerank_score=0.0, low_confidence=True, latency_ms=0.0)


async def test_search_tool_keeps_live_top_k_limits_without_override():
    retriever = _RecordingRetriever()
    toolbox = AgentToolbox(retriever=retriever)
    for asked in (1, 6, 8):
        await toolbox.search_schemes(SearchSchemesInput(query="farmer income support", top_k=asked))
    assert retriever.top_ks == [5, 6, 8]


async def test_search_tool_uses_exact_top_k_override(monkeypatch):
    monkeypatch.setattr(get_settings(), "retrieval_top_k_override", 1)
    retriever = _RecordingRetriever()
    await AgentToolbox(retriever=retriever).search_schemes(SearchSchemesInput(query="farmer income support", top_k=6))
    assert retriever.top_ks == [1]


def _fake_chunks(prefix: str, n: int) -> list[dict]:
    return [{"citation_id": f"SCHEME:{prefix}{i}#benefits", "scheme_slug": f"{prefix}{i}", "scheme_name": f"Scheme {prefix}{i}",
             "ministry": "MoE", "section": "overview_benefits", "source_url": "https://x.gov.in", "text": "t",
             "scores": {"rerank": 0.9}} for i in range(n)]


@pytest.mark.parametrize("override, expected", [(None, 6), (1, 1), (3, 3)])
async def test_answer_sees_at_most_k_chunks_across_loop_rounds(monkeypatch, override, expected):
    """Two search rounds of 3 new chunks each: with k set, the merged evidence is still capped at k."""
    monkeypatch.setattr(get_settings(), "retrieval_top_k_override", override)
    llm = ScriptedLLM(_search_plan("SCHEME_QA"), [
        '{"decision": "search_again", "new_query": "a completely different query", "reason": "weak"}',
        '{"decision": "answer", "reason": "done"}',
    ])
    agent = JanSahayakAgent(llm=llm)
    rounds = iter([_fake_chunks("a", 3), _fake_chunks("b", 3)])

    async def fake_search(inp, citizen_profile=None):
        return {"results": next(rounds), "top_rerank_score": 0.9, "low_confidence": False}

    agent.toolbox.search_schemes = fake_search
    state = await agent.run("Tell me about education help for students", "test-topk", citizen_profile=PRIYA)

    assert len([t for t in state["tool_calls_log"] if t["tool"] == "search_schemes"]) == 2
    assert len(state["retrieved_chunks"]) == expected
