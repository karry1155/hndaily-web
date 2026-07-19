#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.radar_adapter import adapt_hndaily
from scripts.radar_contract import PROMPT_VERSION, SCHEMA_VERSION, ContractError
from scripts.radar_indexes import build_hnhot_indexes
from scripts.radar_issue import build_public_issue
from scripts.radar_model import build_model_input, validate_model_output
from scripts.radar_store import (
    commit_publication,
    load_issue_items,
    load_issues,
)


class FinalizeError(ValueError):
    pass


def build_generation(raw, model_input, model_output):
    candidates, prefilter = adapt_hndaily(raw)
    expected_input = build_model_input(candidates)
    if model_input != expected_input:
        raise FinalizeError("model input does not match adapted raw candidates")
    semantic_items = validate_model_output(model_input, model_output, candidates)
    issue, issue_items = build_public_issue(raw, candidates, semantic_items)
    scope_counts = {
        scope: sum(item["scope"] == scope for item in issue_items)
        for scope in ("national", "hainan", "domestic", "mixed", "foreign")
    }
    return issue_items, issue, {
        "schema_version": SCHEMA_VERSION,
        "prompt_version": PROMPT_VERSION,
        "published_date": raw["date"],
        "input_fingerprint": model_input["input_fingerprint"],
        "candidate_count": len(candidates),
        "published_count": len(issue_items),
        "scope_counts": scope_counts,
        "prefilter": prefilter,
    }


def _write_json_atomic(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def finalize_to_store(raw, model_input, model_output, content_root, audit_path):
    try:
        incoming, issue, audit = build_generation(raw, model_input, model_output)
        published_date = issue["date"]
        existing_issues = load_issues(content_root)
        merged_issues = [row for row in existing_issues if row["date"] != published_date] + [issue]
        existing_articles = load_issue_items(content_root)
        previous_by_id = {
            row["item_id"]: row
            for row in existing_articles
            if row["published_date"] == published_date
        }
        merged_articles = [
            row for row in existing_articles if row["published_date"] != published_date
        ] + incoming
        audit["replaced_items"] = [
            {
                "item_id": row["item_id"],
                "previous_schema_version": previous_by_id[row["item_id"]]["schema_version"],
                "previous_enrichment_status": previous_by_id[row["item_id"]]["enrichment_status"],
                "new_enrichment_status": row["enrichment_status"],
                "prompt_version": PROMPT_VERSION,
            }
            for row in incoming
            if row["item_id"] in previous_by_id and previous_by_id[row["item_id"]] != row
        ]
        indexes = build_hnhot_indexes(merged_issues, merged_articles)
        commit_publication(Path(content_root), issue, incoming, indexes)
        _write_json_atomic(Path(audit_path), audit)
        return audit
    except FinalizeError:
        raise
    except (ContractError, ValueError, OSError, json.JSONDecodeError) as exc:
        raise FinalizeError(str(exc)) from exc


def main(argv):
    if len(argv) != 6:
        print("Usage: finalize_radar.py RAW INPUT OUTPUT CONTENT_ROOT AUDIT", file=sys.stderr)
        return 1
    try:
        raw, model_input, model_output = [
            json.loads(Path(path).read_text(encoding="utf-8")) for path in argv[1:4]
        ]
        finalize_to_store(
            raw, model_input, model_output, Path(argv[4]), Path(argv[5])
        )
    except (FinalizeError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
