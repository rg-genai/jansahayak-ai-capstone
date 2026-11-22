"""Capture a real live execution trace for the Mumbai nuts/bolts MRO manufacturing loan example prompt."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.agent.graph import JanSahayakAgent

OUT_PATH = PROJECT_ROOT / "data" / "live_walkthrough_capture.json"


async def main() -> int:
    prompt = (
        "Hi, I am a 25 year old male looking for Loan to start my small business of "
        "Small parts manufacturing like nuts, bolts and other MRO parts in Mumbai, "
        "I am eligible for which scheme?"
    )
    agent = JanSahayakAgent()
    state = await agent.run(
        message=prompt,
        session_id="doc-walkthrough-mumbai-mro",
        ui_language="en",
        citizen_profile={},
    )
    capture = {
        "prompt": prompt,
        "trace_id": state.get("trace_id"),
        "detected_lang": state.get("detected_lang"),
        "query_en": state.get("query_en"),
        "citizen_profile": state.get("citizen_profile"),
        "guardrail_flags": state.get("guardrail_flags"),
        "planner_output": state.get("planner_output"),
        "tool_calls_log": state.get("tool_calls_log"),
        "retrieved_chunks": [
            {
                "citation_id": c.get("citation_id"),
                "scheme_slug": c.get("scheme_slug"),
                "scheme_name": c.get("scheme_name"),
                "ministry": c.get("ministry"),
                "section": c.get("section"),
                "source_url": c.get("source_url"),
                "scores": c.get("scores"),
                "text_preview": (c.get("text") or "")[:320],
            }
            for c in (state.get("retrieved_chunks") or [])
        ],
        "eligibility_cards": state.get("eligibility_cards"),
        "critic_output": state.get("critic_output"),
        "final_answer": state.get("final_answer"),
        "prompt_tokens": state.get("prompt_tokens"),
        "completion_tokens": state.get("completion_tokens"),
        "step_latencies": state.get("step_latencies"),
        "spans": state.get("spans"),
    }
    OUT_PATH.write_text(json.dumps(capture, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[PASS] Saved real live walkthrough to {OUT_PATH}")
    print("Top schemes:", [c["scheme_name"] for c in capture["retrieved_chunks"][:4]])
    print("Tokens:", capture["prompt_tokens"], "prompt +", capture["completion_tokens"], "completion")
    print("Step latencies:", capture["step_latencies"])
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
