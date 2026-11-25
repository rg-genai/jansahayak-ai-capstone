"""Run the 80-task suite (eval/golden_dataset.json) through the full agent and save what it did on every task.

This is the GENERATION step; eval/score_task_eval.py grades the saved runs (task completion, tool calls, cost,
latency) and eval/failure_taxonomy.py classifies the failures, so both can be re-scored without calling Qwen again.

The suite covers every kind of task the copilot does: scheme questions, FAQs, questions in six Indian languages,
eligibility checks with a citizen profile, grievance drafting and tracking, and requests it must refuse.

Fixed for every configuration, so runs are comparable and reproducible:
- Live retrieval settings (FAQ chunks included); the live .gov.in web fallback is disabled and logged when it would run.
- Grievance tools run against the in-process mock CPGRAMS and a temporary copy of the database, so eval drafts never
  appear in the real grievance list. The read-only search index is shared.

Calls the hosted Qwen VM (one request at a time): run only with the team's agreement.
Resumable: tasks already done under a configuration are skipped; failed ones are retried.

    python eval/run_task_eval.py --list
    python eval/run_task_eval.py --config loop
    python eval/run_task_eval.py --config single_pass
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import shutil
import sqlite3
import sys
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI

from backend.agent.graph import JanSahayakAgent
from backend.config import get_settings
from backend.db.repositories import Repository
from backend.gateway.llm_client import LLMGateway, get_llm_gateway
from backend.retrieval.hybrid_retriever import HybridRetriever
from backend.services.grievance_provider import SandboxCPGRAMSProvider
from backend.services.mock_cpgrams_router import router as mock_cpgrams_router
from eval.run_gold_eval import EvalConfig, NoWebToolbox, eval_settings, load_run, record_from_state, run_path, save_run

logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("run_task_eval")

TASK_SET_PATH = PROJECT_ROOT / "eval" / "golden_dataset.json"
TASK_RUNS_DIR = PROJECT_ROOT / "eval" / "reports" / "task_runs"
EVAL_DB_FILENAME = "task_eval.db"

TASK_CONFIGS: dict[str, EvalConfig] = {c.name: c for c in [
    EvalConfig("loop", "Full agent with the Reflector loop (production settings)", exclude_faq_chunks=False),
    EvalConfig("single_pass", "Same agent without the Reflector loop (one retrieval pass)", reflection=False,
               exclude_faq_chunks=False),
]}


def load_tasks(path: Path = TASK_SET_PATH) -> list[dict[str, Any]]:
    """The task suite, sorted by id so every run visits tasks in the same order."""
    return sorted(json.loads(path.read_text(encoding="utf-8")), key=lambda t: t["id"])


def _warn_cleanup_failure(_func: Any, path: str, exc_info: tuple[Any, BaseException, Any]) -> None:
    logger.warning("Could not delete the temporary eval database %s (%s); delete it by hand.", path, exc_info[1])


@contextmanager
def sandbox_repository(source_db: Path) -> Iterator[Repository]:
    """A repository on a consistent temporary copy of the database (SQLite backup API), deleted afterwards.

    Results are saved after every task, so a failed clean-up (Windows can briefly lock the file) is only logged.
    """
    tmp = Path(tempfile.mkdtemp(prefix="jansahayak-task-eval-"))
    try:
        copy_path = tmp / EVAL_DB_FILENAME
        src, dst = sqlite3.connect(source_db), sqlite3.connect(copy_path)
        try:
            src.backup(dst)
        finally:
            src.close()
            dst.close()
        yield Repository(db_path=copy_path)
    finally:
        shutil.rmtree(tmp, onerror=_warn_cleanup_failure)  # Python 3.11 (the project's runtime) has no `onexc`


def build_agent(config: EvalConfig, llm: LLMGateway, repo: Repository) -> JanSahayakAgent:
    """The production agent with eval-safe side effects: no live web search, in-process mock CPGRAMS."""
    mock_app = FastAPI()
    mock_app.include_router(mock_cpgrams_router)
    toolbox = NoWebToolbox(retriever=HybridRetriever(exclude_faq_chunks=config.exclude_faq_chunks), repo=repo,
                           grievance_provider=SandboxCPGRAMSProvider(repo=repo, asgi_app=mock_app),
                           retrieval_mode=config.retrieval_mode)
    return JanSahayakAgent(llm=llm, toolbox=toolbox, repo=repo)


async def run_task(agent: JanSahayakAgent, config_name: str, task: dict[str, Any]) -> dict[str, Any]:
    """One task through the agent, in the task's language and with its citizen profile."""
    t0 = time.perf_counter()
    state = await agent.run(task["query"], session_id=f"eval-task-{config_name}-{task['id']}",
                            ui_language=task.get("language") or "en", citizen_profile=task.get("citizen_profile"))
    return record_from_state(state, {"scheme_slug": task.get("gold_scheme_slug") or ""},
                             (time.perf_counter() - t0) * 1000.0)


async def run_task_config(config: EvalConfig, tasks: list[dict[str, Any]], runs_dir: Path = TASK_RUNS_DIR,
                          llm: LLMGateway | None = None, agent: JanSahayakAgent | None = None) -> dict[str, Any]:
    """Run every task not yet done under `config`, saving after each. Tests pass a ready `agent`."""
    llm = llm or get_llm_gateway()
    path = run_path(config.name, runs_dir)
    run = load_run(path, config, llm.model)
    run["meta"]["suite"] = "task"
    todo = [t for t in tasks if run["results"].get(t["id"], {}).get("status", "error") == "error"]
    with eval_settings(config), sandbox_repository(get_settings().db_abs_path) as repo:
        agent = agent or build_agent(config, llm, repo)
        t_start = time.perf_counter()
        for n, task in enumerate(todo, start=1):
            base = {"query": task["query"], "category": task["category"], "language": task.get("language")}
            try:
                record = await run_task(agent, config.name, task)
            except Exception as exc:  # one failure must not stop the run; it is retried on the next run
                logger.warning("%s failed on %s: %s", config.name, task["id"], exc)
                record = {"status": "error", "error": str(exc)[:300], "answer": ""}
            run["results"][task["id"]] = {**base, **record}
            save_run(run, path)
            eta_min = (time.perf_counter() - t_start) / n * (len(todo) - n) / 60
            print(f"[{config.name}] {n}/{len(todo)} {task['id']} {record['status']:<26} "
                  f"{record.get('total_ms', 0) / 1000:5.1f}s | {record.get('tool_calls', 0)} tools | "
                  f"ETA {eta_min:.0f} min", flush=True)
    save_run(run, path)
    errors = sum(1 for r in run["results"].values() if r["status"] == "error")
    print(f"\n{config.name}: {len(run['results'])} tasks run ({errors} errors) -> {path}")
    return run


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--list", action="store_true", help="Show the available configurations")
    action.add_argument("--config", choices=sorted(TASK_CONFIGS), help="Configuration to run")
    args = parser.parse_args()
    if args.list:
        for c in TASK_CONFIGS.values():
            print(f"{c.name:<12} {c.description}")
        return
    tasks = load_tasks()
    print(f"{len(tasks)} tasks")
    asyncio.run(run_task_config(TASK_CONFIGS[args.config], tasks))


if __name__ == "__main__":
    main()
