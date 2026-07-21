#!/usr/bin/env python3
"""One-time, auditable migration from v2 topic mentions to v3 open topics."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.radar_contract import PROMPT_VERSION, SCHEMA_VERSION
from scripts.radar_model import CONTENT_FORMS
from scripts.radar_topics import validate_topic_catalog


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def mapping_for_date(mapping, published_date: str):
    rows = {
        row["candidate_id"]: row
        for row in mapping["items"]
        if row["date"] == published_date
    }
    if not rows:
        raise ValueError(f"mapping has no rows for {published_date}")
    return rows


def migrate(model_input, legacy_output, mapping, published_date: str):
    if legacy_output.get("schema_version") != 8:
        raise ValueError("legacy enrichment must use schema version 8")
    rows = mapping_for_date(mapping, published_date)
    input_by_id = {row["candidate_id"]: row for row in model_input["items"]}
    legacy_by_id = {row["candidate_id"]: row for row in legacy_output["items"]}
    expected = [row["candidate_id"] for row in model_input["items"]]
    if set(rows) != set(expected):
        raise ValueError("mapping candidate IDs do not exactly match model input")
    if set(legacy_by_id) != set(expected):
        raise ValueError("legacy enrichment candidate IDs do not exactly match model input")
    items = []
    for candidate_id in expected:
        old = legacy_by_id[candidate_id]
        rule = rows[candidate_id]
        if rule["content_form"] not in CONTENT_FORMS:
            raise ValueError(f"invalid content form for {published_date} {candidate_id}")
        title = input_by_id[candidate_id]["title"]
        secondary = [
            {"name": topic["name"], "evidence": topic["evidence"]}
            for topic in rule.get("secondary", [])
        ]
        items.append({
            "candidate_id": candidate_id,
            "ai_summary": old["ai_summary"],
            "scope": old["scope"],
            "scope_evidence": old["scope_evidence"],
            "subjects": old["subjects"],
            "location_mentions": old["location_mentions"],
            "topic_profile": {
                "primary": {"name": rule["primary"], "evidence": title},
                "secondary": secondary,
            },
            "content_form": rule["content_form"],
            "events": old["events"],
            "plans": old["plans"],
        })
    return {
        "schema_version": SCHEMA_VERSION,
        "prompt_version": PROMPT_VERSION,
        "input_fingerprint": model_input["input_fingerprint"],
        "items": items,
    }


def seed_catalog(catalog, mapping):
    validate_topic_catalog(catalog)
    by_id = {row["topic_id"]: row for row in catalog["topics"]}
    by_name = {row["name"]: row["topic_id"] for row in catalog["topics"]}
    rules = []
    for article in mapping["items"]:
        rules.append({
            "topic_id": article["topic_id"],
            "name": article["primary"],
            "parent_id": article["parent_id"],
        })
        rules.extend(article.get("secondary", []))
    for rule in rules:
        topic_id = rule["topic_id"]
        name = rule["name"]
        if topic_id in by_id:
            existing = by_id[topic_id]
            if existing["name"] != name or existing["parent_id"] != rule["parent_id"]:
                raise ValueError(f"catalog conflict for {topic_id}")
            continue
        if name in by_name:
            raise ValueError(f"catalog name conflict for {name}")
        node = {
            "topic_id": topic_id,
            "name": name,
            "aliases": [],
            "parent_id": rule["parent_id"],
            "definition": f"聚合以“{name}”为主要议题的报道、进展与解释。",
            "include": [f"正文主要讨论{name}"],
            "exclude": ["仅作为背景、例子或顺带提及的内容"],
            "status": "active",
        }
        catalog["topics"].append(node)
        by_id[topic_id] = node
        by_name[name] = topic_id
    return validate_topic_catalog(catalog)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--legacy-output", required=True, type=Path)
    parser.add_argument("--mapping", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--catalog", type=Path)
    args = parser.parse_args(argv)
    try:
        mapping = read_json(args.mapping)
        output = migrate(
            read_json(args.input), read_json(args.legacy_output), mapping, args.date
        )
        write_json(args.output, output)
        if args.catalog:
            write_json(args.catalog, seed_catalog(read_json(args.catalog), mapping))
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
