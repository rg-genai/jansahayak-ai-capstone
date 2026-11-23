"""Score stored LLM-extracted eligibility criteria (scheme_criteria table) against hand labels.

No LLM calls. Reads eval/criteria_gold.json and writes eval/reports/criteria_extraction.{json,md}.

    python eval/run_criteria_eval.py
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.db.repositories import Repository

GOLD_PATH = PROJECT_ROOT / "eval" / "criteria_gold.json"
REPORT_DIR = PROJECT_ROOT / "eval" / "reports"
FIELDS = [
    "applicant_type", "groups", "education_stages", "study_location", "required_institution", "required_states",
    "gender", "age_min", "age_max", "income_max_inr", "social_categories", "requires_bpl", "requires_disability",
]
# Fields the code can verify against the source text vs fields that rely on the model's reading.
TEXT_VERIFIED = {"income_max_inr", "age_min", "age_max", "required_institution", "social_categories",
                 "requires_bpl", "requires_disability"}


def _norm(field: str, value: Any) -> Any:
    if field.startswith("requires_"):
        return True if value else None  # false and null both mean "not required"
    if isinstance(value, list):
        return sorted(v.lower() if isinstance(v, str) else v for v in value)
    if isinstance(value, str):
        return value.strip().lower()
    return value


def _field_ok(field: str, extracted: dict[str, Any], gold: dict[str, Any]) -> bool:
    if field == "groups":
        got = set(extracted.get("beneficiary_groups") or [])
        core, allowed = set(gold["groups"]["core"]), set(gold["groups"]["allowed"])
        return got <= allowed and (not core or bool(got & core))
    return _norm(field, extracted.get(field)) in [_norm(field, g) for g in gold["fields"][field]]


def _load_extractions(from_json: Path | None) -> dict[str, dict[str, Any] | None]:
    """{slug: criteria} from the DB, or from an extraction script --out file (to score a trial prompt)."""
    if from_json:
        data = json.loads(from_json.read_text(encoding="utf-8"))
        return {slug: r.get("criteria") for slug, r in data.items()}
    repo = Repository()
    return {slug: (repo.get_scheme_criteria(slug) or {}).get("criteria") for slug in repo.list_scheme_criteria_versions()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--from-json", type=Path, help="Score an extraction --out file instead of the DB "
                        "(only its schemes are scored; reports are not written)")
    args = parser.parse_args()
    gold = json.loads(GOLD_PATH.read_text(encoding="utf-8"))["schemes"]
    extracted = _load_extractions(args.from_json)
    if args.from_json:
        gold = {slug: g for slug, g in gold.items() if slug in extracted}
    per_set: dict[str, dict[str, list[bool]]] = defaultdict(lambda: defaultdict(list))
    errors: list[dict[str, Any]] = []
    missing: list[str] = []
    for slug, g in gold.items():
        crit = extracted.get(slug)
        if not crit:
            missing.append(slug)
            continue
        for field in FIELDS:
            ok = _field_ok(field, crit, g)
            per_set[g["set"]][field].append(ok)
            per_set["all"][field].append(ok)
            if not ok:
                got = crit.get("beneficiary_groups") if field == "groups" else crit.get(field)
                want = g["groups"] if field == "groups" else g["fields"][field]
                errors.append({"scheme": slug, "set": g["set"], "field": field, "extracted": got, "acceptable": want})

    def pct(xs: list[bool]) -> float:
        return round(100.0 * sum(xs) / len(xs), 1) if xs else 0.0

    summary = {
        s: {
            "schemes": len(next(iter(fields.values()))) if fields else 0,
            "field_accuracy": {f: pct(fields[f]) for f in FIELDS},
            "overall_field_accuracy": pct([v for f in FIELDS for v in fields[f]]),
            "text_verified_fields_accuracy": pct([v for f in FIELDS if f in TEXT_VERIFIED for v in fields[f]]),
            "model_judgement_fields_accuracy": pct([v for f in FIELDS if f not in TEXT_VERIFIED for v in fields[f]]),
        }
        for s, fields in per_set.items()
    }
    report = {"summary": summary, "errors": errors, "missing_extractions": missing}
    if not args.from_json:
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        (REPORT_DIR / "criteria_extraction.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    sets = [s for s in ("heldout", "dev", "all") if s in summary]
    lines = ["# Eligibility criteria extraction accuracy", "",
             "Stored LLM extractions vs hand labels (`eval/criteria_gold.json`). "
             "`dev` = schemes used while tuning the prompt; `heldout` = random sample never seen before labelling.", "",
             "| Field | " + " | ".join(f"{s} (n={summary[s]['schemes']})" for s in sets) + " |",
             "|---|" + "---|" * len(sets)]
    for f in FIELDS:
        tag = " *(text-verified)*" if f in TEXT_VERIFIED else ""
        lines.append(f"| {f}{tag} | " + " | ".join(f"{summary[s]['field_accuracy'][f]}%" for s in sets) + " |")
    for key, label in [("text_verified_fields_accuracy", "**Text-verified fields**"),
                       ("model_judgement_fields_accuracy", "**Model-judgement fields**"),
                       ("overall_field_accuracy", "**All fields**")]:
        lines.append(f"| {label} | " + " | ".join(f"**{summary[s][key]}%**" for s in sets) + " |")
    lines += ["", "## Errors", "", "| Scheme | Set | Field | Extracted | Acceptable |", "|---|---|---|---|---|"]
    lines += [f"| {e['scheme']} | {e['set']} | {e['field']} | `{json.dumps(e['extracted'], ensure_ascii=False)}` | "
              f"`{json.dumps(e['acceptable'], ensure_ascii=False)}` |" for e in errors]
    if not args.from_json:
        (REPORT_DIR / "criteria_extraction.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
