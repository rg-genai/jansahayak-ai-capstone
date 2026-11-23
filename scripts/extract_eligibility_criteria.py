"""Extract structured eligibility criteria for schemes with the hosted LLM (offline, one call per scheme).

Calls the shared VM: run only with the team's agreement. Resumable: with --write-db, schemes already
extracted with the current prompt version are skipped (use --force to redo them).

    python scripts/extract_eligibility_criteria.py --slugs fssdu,pm-kisan --out sample.json   # review only
    python scripts/extract_eligibility_criteria.py --all --write-db                           # full catalog
    python scripts/extract_eligibility_criteria.py --reground                                 # re-check stored, no LLM
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.agent.profile_matching import get_catalog_vocabulary
from backend.db.repositories import Repository
from backend.gateway.llm_client import get_llm_gateway
from backend.retrieval.criteria_extractor import EligibilityCriteria, extract_criteria, ground_criteria, prompt_version

logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("extract_criteria")


async def run(slugs: list[str], out_path: Path | None, write_db: bool, force: bool) -> None:
    repo = Repository()
    allowed_groups = list(get_catalog_vocabulary(repo).groups)
    llm = get_llm_gateway()
    version = prompt_version()

    if write_db and not force:
        done = {s for s, v in repo.list_scheme_criteria_versions().items() if v == version}
        skipped = [s for s in slugs if s in done]
        slugs = [s for s in slugs if s not in done]
        if skipped:
            print(f"Skipping {len(skipped)} schemes already extracted with prompt {version}.")

    results: dict[str, dict] = {}
    stats: Counter[str] = Counter()
    t0 = time.perf_counter()
    for i, slug in enumerate(slugs, start=1):
        scheme = repo.get_scheme(slug)
        if not scheme:
            logger.warning("Unknown scheme slug: %s", slug)
            stats["unknown"] += 1
            continue
        try:
            criteria, diag = await extract_criteria(scheme, allowed_groups, llm)
        except Exception as exc:  # one failure must not stop the batch; it is retried on the next run
            logger.warning("Extraction failed for %s: %s", slug, exc)
            results[slug] = {"scheme_name": scheme["scheme_name"], "criteria": None, "error": str(exc)[:300]}
            stats["error"] += 1
            continue
        stats["ok" if criteria else "unparseable"] += 1
        stats["tokens"] += (diag.get("prompt_tokens", 0) + diag.get("completion_tokens", 0)
                            + diag.get("verification_tokens", 0))
        if diag.get("grounding_corrections"):
            stats["with_corrections"] += 1
        if diag.get("verification_corrections"):
            stats["with_verification_corrections"] += 1
        results[slug] = {"scheme_name": scheme["scheme_name"],
                         "criteria": criteria.model_dump() if criteria else None, "diagnostics": diag}
        if write_db and criteria:
            repo.save_scheme_criteria(slug, criteria.model_dump(), diag, version, llm.model)
        elapsed = time.perf_counter() - t0
        print(f"[{i}/{len(slugs)}] {slug:<40} {'ok' if criteria else 'UNPARSEABLE':<12} "
              f"{diag.get('latency_ms', 0):>6.0f} ms | elapsed {elapsed / 60:.1f} min", flush=True)

    if out_path:
        out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nDone in {(time.perf_counter() - t0) / 60:.1f} min | prompt {version} | " + ", ".join(
        f"{k}={v}" for k, v in sorted(stats.items())))


def reground_stored() -> None:
    """Re-apply the (code-only) grounding checks to stored criteria. No LLM calls."""
    repo = Repository()
    changed = 0
    for slug in repo.list_scheme_criteria_versions():
        row, scheme = repo.get_scheme_criteria(slug), repo.get_scheme(slug)
        if not row or not scheme:
            continue
        grounded, fixes = ground_criteria(EligibilityCriteria.model_validate(row["criteria"]), scheme)
        if fixes:
            diag = row["diagnostics"]
            diag["grounding_corrections"] = [*diag.get("grounding_corrections", []), *fixes]
            repo.save_scheme_criteria(slug, grounded.model_dump(), diag, row["prompt_version"], row["model_name"])
            changed += 1
    print(f"Re-grounded stored criteria: {changed} scheme(s) updated.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--slugs", help="Comma-separated scheme slugs")
    target.add_argument("--all", action="store_true", help="Every scheme in the catalog")
    target.add_argument("--reground", action="store_true", help="Re-apply code grounding to stored results (no LLM)")
    parser.add_argument("--out", type=Path, help="Write results to this JSON file for review")
    parser.add_argument("--write-db", action="store_true", help="Store results in the scheme_criteria table")
    parser.add_argument("--force", action="store_true", help="Re-extract schemes already done with this prompt")
    args = parser.parse_args()
    if args.reground:
        reground_stored()
        return
    if not args.out and not args.write_db:
        parser.error("choose --out and/or --write-db")

    slugs = Repository().list_scheme_slugs() if args.all else [s.strip() for s in args.slugs.split(",") if s.strip()]
    asyncio.run(run(slugs, args.out, args.write_db, args.force))


if __name__ == "__main__":
    main()
