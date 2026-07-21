#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.radar_contract import non_empty, normalized_text
from scripts.radar_model import ModelOutputError, validate_model_output


def output_matches_input(model_input: dict, model_output: dict) -> bool:
    for field in ("schema_version", "prompt_version", "input_fingerprint"):
        if model_output.get(field) != model_input.get(field):
            return False
    input_items = model_input.get("items")
    output_items = model_output.get("items")
    if not isinstance(input_items, list) or not isinstance(output_items, list):
        return False
    return [row.get("candidate_id") for row in output_items if isinstance(row, dict)] == [
        row.get("candidate_id") for row in input_items if isinstance(row, dict)
    ]


def source_anchor_errors(model_input: dict, model_output: dict) -> list[str]:
    input_items = model_input.get("items")
    output_items = model_output.get("items")
    if not isinstance(input_items, list) or not isinstance(output_items, list):
        return []
    input_by_id = {
        row.get("candidate_id"): row for row in input_items if isinstance(row, dict)
    }
    errors: list[str] = []

    def check(value, source_text: str, location: str) -> None:
        if non_empty(value) and normalized_text(value) not in source_text:
            errors.append(f"{location} is not a verbatim source excerpt")

    for index, item in enumerate(output_items):
        if not isinstance(item, dict):
            continue
        candidate_id = item.get("candidate_id")
        source = input_by_id.get(candidate_id)
        if not isinstance(source, dict):
            continue
        source_text = normalized_text(
            str(source.get("title") or "") + str(source.get("content") or "")
        )
        prefix = f"items[{index}]({candidate_id})"
        check(item.get("scope_evidence"), source_text, f"{prefix}.scope_evidence")
        for subject_index, subject in enumerate(item.get("subjects") or []):
            if not isinstance(subject, dict):
                continue
            check(subject.get("name"), source_text, f"{prefix}.subjects[{subject_index}].name")
            check(subject.get("evidence"), source_text, f"{prefix}.subjects[{subject_index}].evidence")
            for alias_index, alias in enumerate(subject.get("aliases") or []):
                if not isinstance(alias, dict):
                    continue
                check(
                    alias.get("name"), source_text,
                    f"{prefix}.subjects[{subject_index}].aliases[{alias_index}].name",
                )
                check(
                    alias.get("evidence"), source_text,
                    f"{prefix}.subjects[{subject_index}].aliases[{alias_index}].evidence",
                )
        for field in ("location_mentions", "events", "plans"):
            for value_index, value in enumerate(item.get(field) or []):
                if not isinstance(value, dict):
                    continue
                check(value.get("evidence"), source_text, f"{prefix}.{field}[{value_index}].evidence")
                if field == "plans":
                    check(value.get("name"), source_text, f"{prefix}.{field}[{value_index}].name")
        topic_profile = item.get("topic_profile") or {}
        primary = topic_profile.get("primary") or {}
        check(primary.get("evidence"), source_text, f"{prefix}.topic_profile.primary.evidence")
        for topic_index, topic in enumerate(topic_profile.get("secondary") or []):
            if isinstance(topic, dict):
                check(
                    topic.get("evidence"), source_text,
                    f"{prefix}.topic_profile.secondary[{topic_index}].evidence",
                )
    return errors


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("Usage: check_model_output.py MODEL_INPUT_JSON MODEL_OUTPUT_JSON", file=sys.stderr)
        return 1
    try:
        model_input = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
        model_output = json.loads(Path(argv[2]).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"MODEL_OUTPUT_STALE={exc}", file=sys.stderr)
        return 2
    if not output_matches_input(model_input, model_output):
        print("MODEL_OUTPUT_STALE=envelope or candidate order does not match current input", file=sys.stderr)
        return 2
    anchor_errors = source_anchor_errors(model_input, model_output)
    if anchor_errors:
        for error in anchor_errors:
            print(f"MODEL_OUTPUT_INVALID={error}", file=sys.stderr)
        return 2
    try:
        candidates = [
            {
                "candidate_id": row["candidate_id"],
                "title": row["title"],
                "content": row["content"],
            }
            for row in model_input["items"]
        ]
        validate_model_output(model_input, model_output, candidates)
    except (KeyError, TypeError, ModelOutputError) as exc:
        print(f"MODEL_OUTPUT_INVALID={exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
