"""Evidence-grounded LLM judge shared by the task-completion eval and the failure taxonomy.

The judge sees exactly the evidence the agent's answer writer saw (chunk texts looked up by the saved chunk ids, in
the same [n] order, plus the eligibility tool verdicts) and reports whether the answer gives what was asked, which
claims the evidence does not support, and whether the answer declines.

Calls Gemini (free-tier key): every call is capped by `max_calls`, each verdict is cached on disk as soon as it
arrives, and an answer already judged is never sent again (the cache key includes a hash of the answer text).
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from backend.agent.prompts import GROUNDING_JUDGE_SYSTEM_PROMPT
from backend.agent.tools import parse_and_repair_json
from backend.db.database import get_connection
from backend.db.repositories import now_ist_iso
from backend.gateway.llm_client import LLMGateway, QuotaExhaustedError

logger = logging.getLogger(__name__)

# Generous ceiling: the reply itself is ~60 tokens, but Gemini's hidden reasoning can count against it and a cut-off
# reply is unparseable (6 of 53 verdicts were lost at 300 on 25 Nov).
JUDGE_MAX_TOKENS = 1024
RAW_REPLY_LOG_CHARS = 400
MAX_UNSUPPORTED_CLAIMS = 3


class GroundingVerdict(BaseModel):
    """The judge's reading of one answer against its evidence."""

    answers_request: bool
    unsupported_claims: list[str] = Field(default_factory=list)
    declines: bool = False
    reason: str = ""

    @property
    def grounded(self) -> bool:
        return not self.unsupported_claims


@dataclass(frozen=True)
class GroundingRequest:
    """One answer to judge. `key` identifies it in the cache (see `grounding_key`)."""

    key: str
    request: str
    evidence: str
    answer: str


def grounding_key(suite: str, config: str, item_id: str, answer: str) -> str:
    """Cache key; changes whenever the answer text changes, so a re-run answer is judged again."""
    return f"{suite}:{config}:{item_id}:{hashlib.sha256(answer.encode('utf-8')).hexdigest()[:12]}"


def load_chunk_texts(db_path: Path, chunk_ids: list[str]) -> dict[str, str]:
    """{chunk_id: text} for the given ids from the index metadata table."""
    if not chunk_ids:
        return {}
    wanted = list(dict.fromkeys(chunk_ids))
    found: dict[str, str] = {}
    with get_connection(db_path) as conn:
        for start in range(0, len(wanted), 500):  # stay below SQLite's parameter limit
            batch = wanted[start:start + 500]
            rows = conn.execute(f"SELECT chunk_id, text FROM chunks_meta WHERE chunk_id IN ({','.join('?' * len(batch))})",
                                batch).fetchall()
            found.update({r["chunk_id"]: r["text"] for r in rows})
    return found


def build_evidence_block(record: dict[str, Any], chunk_texts: dict[str, str]) -> str:
    """The numbered evidence of one saved record, in the order the answer's [n] citations refer to."""
    lines = [f"[{n}] {chunk_texts.get(cid, '(chunk text unavailable)')}"
             for n, cid in enumerate(record.get("evidence_chunk_ids") or [], start=1)]
    verdicts = record.get("eligibility_verdicts") or []
    if verdicts:
        lines.append("Eligibility tool verdicts: " + "; ".join(f"{v['scheme_slug']}: {v['verdict']}" for v in verdicts))
    return "\n\n".join(lines) or "(no evidence was retrieved)"


def build_messages(req: GroundingRequest) -> list[dict[str, str]]:
    user = (f"REQUEST: {req.request}\n\nEVIDENCE:\n{req.evidence}\n\nANSWER:\n{req.answer}\n\n"
            "Output ONLY the JSON.")
    return [{"role": "system", "content": GROUNDING_JUDGE_SYSTEM_PROMPT}, {"role": "user", "content": user}]


def load_cache(cache_path: Path) -> dict[str, dict[str, Any]]:
    return json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}


def cached_verdict(cache: dict[str, dict[str, Any]], key: str) -> GroundingVerdict | None:
    entry = cache.get(key)
    return GroundingVerdict.model_validate(entry) if entry else None


async def judge_grounding(requests: list[GroundingRequest], cache_path: Path, max_calls: int,
                          llm: LLMGateway) -> dict[str, dict[str, Any]]:
    """Judge requests not in the cache, at most `max_calls` LLM calls; returns the updated cache."""
    cache = load_cache(cache_path)
    calls = 0
    for req in requests:
        if req.key in cache:
            continue
        if calls >= max_calls:
            print(f"Grounding judge call cap ({max_calls}) reached; re-run to continue.")
            break
        calls += 1
        try:
            resp = await llm.chat_completion(build_messages(req), max_tokens=JUDGE_MAX_TOKENS, temperature=0.0)
            verdict, _ = await parse_and_repair_json(resp.content, GroundingVerdict, allow_llm_repair=False)
        except QuotaExhaustedError as exc:  # every later call would fail too: stop and keep what is judged
            print(f"Grounding judge stopped at call {calls}: quota used up. {exc}")
            break
        except Exception as exc:  # left unjudged; retried on the next run
            logger.warning("Grounding judge failed on %s: %s", req.key, exc)
            continue
        if verdict is None:
            logger.warning("Unparseable grounding verdict for %s (%d completion tokens): %r", req.key,
                           resp.completion_tokens, resp.content[:RAW_REPLY_LOG_CHARS])
            continue
        verdict.unsupported_claims = verdict.unsupported_claims[:MAX_UNSUPPORTED_CLAIMS]
        cache[req.key] = {**verdict.model_dump(), "judge_model": llm.model, "judged_at": now_ist_iso()}
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[grounding judge {calls}/{max_calls}] {req.key}: answers={verdict.answers_request} "
              f"unsupported={len(verdict.unsupported_claims)} declines={verdict.declines}", flush=True)
    return cache
