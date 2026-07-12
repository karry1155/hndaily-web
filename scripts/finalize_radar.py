#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.radar_adapter import adapt_hndaily
from scripts.radar_contract import PROMPT_VERSION, SCHEMA_VERSION, ContractError
from scripts.radar_indexes import (
    build_indexes, build_issue_date_index, build_search_indexes,
)
from scripts.radar_issue import build_public_issue
from scripts.radar_model import build_model_input, validate_model_output
from scripts.radar_locations import load_location_catalog, resolve_location_mentions
from scripts.radar_scoring import score_semantic
from scripts.radar_select import select_items
from scripts.radar_store import (
    commit_generation, load_issue_items, load_issues, load_items,
)


class FinalizeError(ValueError):
    pass


def build_items(raw, model_input, model_output):
    selected, _issue, _issue_items, audit = build_generation(
        raw, model_input, model_output
    )
    return selected, audit


def build_generation(raw, model_input, model_output):
    candidates, prefilter = adapt_hndaily(raw)
    expected_input = build_model_input(candidates)
    if model_input != expected_input:
        raise FinalizeError("model input does not match adapted raw candidates")
    semantic_items = validate_model_output(model_input, model_output, candidates)
    scored = []
    catalog = load_location_catalog()
    for candidate, semantic in zip(candidates, semantic_items):
        scoring = score_semantic(semantic)
        scored.append(
            {
                "schema_version": SCHEMA_VERSION,
                "item_id": candidate["item_id"],
                "published_date": candidate["published_date"],
                "collected_date": candidate["collected_date"],
                "category": semantic["category"],
                **scoring,
                "opportunity": {
                    "lifecycle": semantic["opportunity_lifecycle"],
                    "deadline_date": semantic["deadline_date"],
                    "deadline_text": semantic["deadline_text"],
                    "evidence": semantic["deadline_evidence"],
                },
                "entities": {
                    "actors": semantic["actors"],
                    "locations": resolve_location_mentions(
                        semantic["location_mentions"],
                        find_candidates := next(
                            row["location_candidates"]
                            for row in model_input["items"]
                            if row["candidate_id"] == candidate["candidate_id"]
                        ),
                        catalog,
                    ),
                    "action": semantic["action"].strip(),
                    "action_evidence": semantic["action_evidence"].strip(),
                },
                "block": {
                    "source": candidate["source"],
                    "title": candidate["title"],
                    "content": candidate["content"],
                    "ai_summary": semantic["ai_summary"].strip(),
                    "recommendation_reason": semantic["recommendation_reason"].strip(),
                    "original_url": candidate["original_url"],
                },
            }
        )
    issue, issue_items = build_public_issue(
        raw, candidates, semantic_items, scored
    )
    selected, decisions = select_items(scored)
    return selected, issue, issue_items, {
        "schema_version": SCHEMA_VERSION,
        "published_date": raw["date"],
        "input_fingerprint": model_input["input_fingerprint"],
        "candidate_count": len(candidates),
        "selected_count": len(selected),
        "prefilter": prefilter,
        "decisions": decisions,
    }


def _write_json_atomic(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def finalize_to_store(raw, model_input, model_output, content_root, audit_path, as_of):
    try:
        incoming, issue, issue_items, audit = build_generation(
            raw, model_input, model_output
        )
        existing = load_items(content_root)
        source = str(raw.get("source", "")).strip()
        published_date = raw.get("date")
        previous_by_id = {item["item_id"]: item for item in existing}
        preserved = [
            item
            for item in existing
            if not (
                item["published_date"] == published_date
                and item["block"]["source"] == source
            )
        ]
        merged = preserved + incoming
        ids = [item["item_id"] for item in merged]
        if len(ids) != len(set(ids)):
            raise FinalizeError("duplicate item_id in merged library")
        replaced = []
        for item in incoming:
            previous = previous_by_id.get(item["item_id"])
            if previous is not None and previous != item:
                replaced.append(
                    {
                        "item_id": item["item_id"],
                        "previous_schema_version": previous["schema_version"],
                        "previous_final_score": previous["final_score"],
                        "new_final_score": item["final_score"],
                        "prompt_version": PROMPT_VERSION,
                    }
                )
        audit["replaced_items"] = replaced
        existing_issues = load_issues(content_root)
        merged_issues = [
            value for value in existing_issues
            if value["date"] != published_date
        ] + [issue]
        existing_issue_items = load_issue_items(content_root)
        merged_issue_items = [
            value for value in existing_issue_items
            if value["published_date"] != published_date
        ] + issue_items
        indexes = build_indexes(merged, as_of)
        indexes.update(build_search_indexes(merged, merged_issue_items))
        indexes["issues.json"] = build_issue_date_index(merged_issues)
        commit_generation(
            content_root, merged, indexes, {published_date},
            issues=[issue], issue_items=issue_items,
        )
        _write_json_atomic(audit_path, audit)
        return audit
    except FinalizeError:
        raise
    except (ContractError, ValueError, OSError, json.JSONDecodeError) as exc:
        raise FinalizeError(str(exc)) from exc


def main(argv):
    if len(argv) != 7:
        print("Usage: finalize_radar.py RAW INPUT OUTPUT CONTENT_ROOT AUDIT AS_OF", file=sys.stderr)
        return 1
    try:
        raw, model_input, model_output = [
            json.loads(Path(path).read_text(encoding="utf-8"))
            for path in argv[1:4]
        ]
        finalize_to_store(raw, model_input, model_output, Path(argv[4]), Path(argv[5]), argv[6])
    except (FinalizeError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
