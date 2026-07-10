#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.editorial_filter import InputError, evaluate_issue, flatten_articles

SCHEMA_VERSION = 2
PROMPT_VERSION = "editorial-v1"

def build_model_input(raw: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    records = evaluate_issue(raw)
    items = [
        {
            "candidate_id": record["candidate_id"],
            "original_title": record["original_title"],
            "content": record["content"],
            "length_band": record["length_band"],
        }
        for record in records
        if record["passed"]
    ]
    fingerprint_payload = {
        "schema_version": SCHEMA_VERSION,
        "prompt_version": PROMPT_VERSION,
        "items": items,
    }
    canonical = json.dumps(
        fingerprint_payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    model_input = {
        "schema_version": SCHEMA_VERSION,
        "prompt_version": PROMPT_VERSION,
        "input_fingerprint": hashlib.sha256(canonical).hexdigest(),
        "items": items,
    }
    audit = {
        "schema_version": SCHEMA_VERSION,
        "date": raw.get("date"),
        "article_count": raw.get("article_count"),
        "items": records,
    }
    return model_input, audit


def write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        print("Usage: prepare_model_input.py RAW_JSON MODEL_INPUT_JSON PREFILTER_JSON", file=sys.stderr)
        return 1
    raw_path = Path(argv[1])
    output_path = Path(argv[2])
    try:
        raw = json.loads(raw_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise InputError("raw JSON must be an object")
        model_input, audit = build_model_input(raw)
        write_json_atomic(output_path, model_input)
        write_json_atomic(Path(argv[3]), audit)
    except (OSError, json.JSONDecodeError, InputError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(str(output_path.resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
