#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.prepare_model_input import build_model_input, select_articles
from scripts.validate_digest import CATEGORIES, validate_daily


MODEL_ENVELOPE_FIELDS = {"schema_version", "prompt_version", "input_fingerprint", "items"}
MODEL_ITEM_FIELDS = {
    "candidate_id",
    "title",
    "summary",
    "why_it_matters",
    "key_facts",
    "confidence",
}
MODEL_CONFIDENCE = {"full_text", "short_item", "partial"}


class ModelOutputError(ValueError):
    pass


def _non_empty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _require_exact_fields(value: dict[str, Any], expected: set[str], location: str) -> None:
    unknown = sorted(set(value) - expected)
    missing = sorted(expected - set(value))
    if unknown:
        raise ModelOutputError(f"{location} has unknown fields: {', '.join(unknown)}")
    if missing:
        raise ModelOutputError(f"{location} is missing fields: {', '.join(missing)}")


def _validate_model_output(model_input: dict[str, Any], model_output: dict[str, Any]) -> list[dict[str, Any]]:
    _require_exact_fields(model_output, MODEL_ENVELOPE_FIELDS, "model output")
    for field in ("schema_version", "prompt_version", "input_fingerprint"):
        if model_output.get(field) != model_input.get(field):
            raise ModelOutputError(f"model output {field} does not match model input")

    items = model_output.get("items")
    if not isinstance(items, list):
        raise ModelOutputError("model output items must be an array")
    expected_ids = [item["candidate_id"] for item in model_input["items"]]
    actual_ids = [item.get("candidate_id") if isinstance(item, dict) else None for item in items]
    if actual_ids != expected_ids:
        raise ModelOutputError(f"candidate_id order must be exactly {expected_ids}; got {actual_ids}")

    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ModelOutputError(f"items[{index}] must be an object")
        _require_exact_fields(item, MODEL_ITEM_FIELDS, f"items[{index}]")
        for field in ("candidate_id", "title", "summary", "why_it_matters"):
            if not _non_empty(item.get(field)):
                raise ModelOutputError(f"items[{index}].{field} must be a non-empty string")
        facts = item.get("key_facts")
        if not isinstance(facts, list) or not facts or not all(_non_empty(fact) for fact in facts):
            raise ModelOutputError(f"items[{index}].key_facts must contain non-empty strings")
        if item.get("confidence") not in MODEL_CONFIDENCE:
            raise ModelOutputError(f"items[{index}].confidence is invalid")
    return items


def build_digest(
    raw: dict[str, Any],
    model_input: dict[str, Any],
    model_output: dict[str, Any],
) -> dict[str, Any]:
    expected_input = build_model_input(raw)
    if model_input != expected_input:
        raise ModelOutputError("model input does not match the first articles in raw JSON")
    semantic_items = _validate_model_output(model_input, model_output)
    selected = select_articles(raw)

    top_items = []
    for rank, (semantic, (page, article)) in enumerate(zip(semantic_items, selected), 1):
        top_items.append(
            {
                "rank": rank,
                "title": semantic["title"].strip(),
                "summary": semantic["summary"].strip(),
                "category": "重要但不必精读",
                "why_it_matters": semantic["why_it_matters"].strip(),
                "key_facts": [fact.strip() for fact in semantic["key_facts"]],
                "sources": [
                    {
                        "headline": article["title"],
                        "page": page["page"],
                        "url": article["url"],
                    }
                ],
                "confidence": semantic["confidence"],
            }
        )

    digest = {
        "type": "daily",
        "date": raw.get("date"),
        "source": raw.get("source"),
        "page_count": raw.get("page_count"),
        "article_count": raw.get("article_count"),
        "reading_minutes": 5,
        "input_fingerprint": model_input["input_fingerprint"],
        "prompt_version": model_input["prompt_version"],
        "top_items": top_items,
        "categories": {category: [] for category in CATEGORIES},
        "generated_at": datetime.now().astimezone().replace(microsecond=0).isoformat(),
    }
    errors = validate_daily(digest)
    if errors:
        raise ModelOutputError("invalid finalized digest: " + "; ".join(errors))
    return digest


def finalize_to_path(
    raw: dict[str, Any],
    model_input: dict[str, Any],
    model_output: dict[str, Any],
    output_path: Path,
) -> dict[str, Any]:
    digest = build_digest(raw, model_input, model_output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(f".{output_path.name}.tmp")
    temporary.write_text(json.dumps(digest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output_path)
    return digest


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ModelOutputError(f"{path} must contain a JSON object")
    return value


def main(argv: list[str]) -> int:
    if len(argv) != 5:
        print(
            "Usage: finalize_digest.py RAW_JSON MODEL_INPUT_JSON MODEL_OUTPUT_JSON OUTPUT_JSON",
            file=sys.stderr,
        )
        return 1
    try:
        raw, model_input, model_output = (_read_object(Path(value)) for value in argv[1:4])
        finalize_to_path(raw, model_input, model_output, Path(argv[4]))
    except (OSError, json.JSONDecodeError, ModelOutputError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(str(Path(argv[4]).resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
