#!/usr/bin/env python3
from __future__ import annotations

import hashlib
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
from scripts.radar_topics import (
    automatic_topic_resolution,
    build_topic_resolution_input,
    load_topic_catalog,
    merge_topic_catalog,
    validate_topic_resolution_output,
)


class FinalizeError(ValueError):
    pass


def build_generation(
    raw,
    model_input,
    model_output,
    topic_resolution_input=None,
    topic_resolution_output=None,
    topic_catalog=None,
):
    candidates, prefilter = adapt_hndaily(raw)
    expected_input = build_model_input(candidates)
    if model_input != expected_input:
        raise FinalizeError("model input does not match adapted raw candidates")
    semantic_items = validate_model_output(model_input, model_output, candidates)
    topic_catalog = topic_catalog or load_topic_catalog()
    expected_resolution_input = build_topic_resolution_input(model_output, topic_catalog)
    if topic_resolution_input is not None and topic_resolution_input != expected_resolution_input:
        raise FinalizeError("topic resolution input does not match model output and catalog")
    topic_resolution_input = expected_resolution_input
    if topic_resolution_output is None:
        topic_resolution_output = automatic_topic_resolution(topic_resolution_input)
    if topic_resolution_output is None:
        raise FinalizeError("topic resolution output is required for new open topics")
    resolution_items = validate_topic_resolution_output(
        topic_resolution_input, topic_resolution_output, topic_catalog
    )
    merged_topic_catalog = merge_topic_catalog(topic_catalog, resolution_items)
    issue, issue_items = build_public_issue(
        raw, candidates, semantic_items, resolution_items, merged_topic_catalog
    )
    scope_counts = {
        scope: sum(item["scope"] == scope for item in issue_items)
        for scope in ("national", "hainan", "domestic", "mixed", "foreign")
    }
    canonical_output = json.dumps(
        model_output, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return issue_items, issue, {
        "schema_version": SCHEMA_VERSION,
        "prompt_version": PROMPT_VERSION,
        "published_date": raw["date"],
        "input_fingerprint": model_input["input_fingerprint"],
        "model_output_sha256": hashlib.sha256(
            canonical_output.encode("utf-8")
        ).hexdigest(),
        "candidate_count": len(candidates),
        "published_count": len(issue_items),
        "scope_counts": scope_counts,
        "prefilter": prefilter,
    }, merged_topic_catalog


def _write_json_atomic(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def finalize_to_store(
    raw,
    model_input,
    model_output,
    content_root,
    audit_path,
    topic_resolution_input=None,
    topic_resolution_output=None,
):
    try:
        topic_catalog = load_topic_catalog(Path(content_root))
        incoming, issue, audit, topic_catalog = build_generation(
            raw,
            model_input,
            model_output,
            topic_resolution_input,
            topic_resolution_output,
            topic_catalog,
        )
        published_date = issue["date"]
        existing_issues = load_issues(content_root)
        merged_issues = [row for row in existing_issues if row["date"] != published_date] + [issue]
        existing_articles = load_issue_items(content_root)
        previous_by_id = {
            row["item_id"]: row
            for row in existing_articles
            if row["published_date"] == published_date
        }
        for row in incoming:
            previous = previous_by_id.get(row["item_id"])
            if previous is None:
                continue
            if previous.get("schema_version") in {7, 8}:
                row["legacy_topics"] = previous.get("topics", [])
            elif previous.get("schema_version") == 9:
                row["legacy_topics"] = previous.get("legacy_topics", [])
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
        indexes = build_hnhot_indexes(merged_issues, merged_articles, topic_catalog)
        commit_publication(Path(content_root), issue, incoming, indexes, topic_catalog)
        _write_json_atomic(Path(audit_path), audit)
        return audit
    except FinalizeError:
        raise
    except (ContractError, ValueError, OSError, json.JSONDecodeError) as exc:
        raise FinalizeError(str(exc)) from exc


def main(argv):
    if len(argv) != 8:
        print(
            "Usage: finalize_radar.py RAW INPUT OUTPUT TOPIC_INPUT TOPIC_OUTPUT CONTENT_ROOT AUDIT",
            file=sys.stderr,
        )
        return 1
    try:
        raw, model_input, model_output, topic_input, topic_output = [
            json.loads(Path(path).read_text(encoding="utf-8")) for path in argv[1:6]
        ]
        finalize_to_store(
            raw,
            model_input,
            model_output,
            Path(argv[6]),
            Path(argv[7]),
            topic_input,
            topic_output,
        )
    except (FinalizeError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
