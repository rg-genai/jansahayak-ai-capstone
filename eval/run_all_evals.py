"""Master Track B Evaluation Runner: executes Retrieval Ablation, Prompt Comparison, Agent Fault-Injection & Red-Team Safety."""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval.run_agent_fault_eval import run_agent_fault_eval
from eval.run_prompt_eval import run_prompt_comparison
from eval.run_redteam_eval import run_redteam_eval
from eval.run_retrieval_eval import run_retrieval_ablation


async def main() -> int:
    t0 = time.perf_counter()
    print("=== [1/4] Running 4-Way Retrieval Ablation (R1-R4) ===")
    run_retrieval_ablation()

    print("\n=== [2/4] Running 3-Way Prompting Strategy Comparison (P1-P3) ===")
    await run_prompt_comparison()

    print("\n=== [3/4] Running 15-Scenario Agent Fault-Injection Benchmark ===")
    await run_agent_fault_eval()

    print("\n=== [4/4] Running 20-Case Red-Team Safety & Failure Taxonomy Eval ===")
    await run_redteam_eval()

    elapsed = round(time.perf_counter() - t0, 1)
    print(f"\n=== ALL 4 TRACK B BENCHMARKS COMPLETED IN {elapsed}s ===")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
