#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
PROMPT_VERSION = "digest-v1"


class InputError(ValueError):
    pass


def _non_empty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def flatten_articles(raw: dict[str, Any]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    pages = raw.get("pages")
    if not isinstance(pages, list):
        raise InputError("pages must be an array")
    if raw.get("page_count") != len(pages):
        raise InputError("page_count does not match pages")

    flattened: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for page_index, page in enumerate(pages):
        if not isinstance(page, dict):
            raise InputError(f"pages[{page_index}] must be an object")
        articles = page.get("articles")
        if not isinstance(articles, list):
            raise InputError(f"pages[{page_index}].articles must be an array")
        if page.get("article_count") != len(articles):
            raise InputError(f"pages[{page_index}].article_count does not match articles")
        for article in articles:
            if not isinstance(article, dict):
                raise InputError(f"pages[{page_index}] contains a non-object article")
            flattened.append((page, article))

    if raw.get("article_count") != len(flattened):
        raise InputError("article_count does not match flattened articles")
    return flattened


def select_articles(raw: dict[str, Any], limit: int = 3) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    if limit < 1:
        raise InputError("limit must be at least 1")
    selected = flatten_articles(raw)[:limit]
    for index, (page, article) in enumerate(selected):
        prefix = f"selected article {index + 1}"
        if not _non_empty(page.get("page")):
            raise InputError(f"{prefix} page is required")
        for field in ("title", "content", "url"):
            if not _non_empty(article.get(field)):
                raise InputError(f"{prefix} {field} is required")
    return selected


def build_model_input(raw: dict[str, Any], limit: int = 3) -> dict[str, Any]:
    items = [
        {
            "candidate_id": f"A{index:03d}",
            "original_title": article["title"],
            "content": article["content"],
        }
        for index, (_page, article) in enumerate(select_articles(raw, limit), 1)
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
    return {
        "schema_version": SCHEMA_VERSION,
        "prompt_version": PROMPT_VERSION,
        "input_fingerprint": hashlib.sha256(canonical).hexdigest(),
        "items": items,
    }


def write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("Usage: prepare_model_input.py RAW_JSON OUTPUT_JSON", file=sys.stderr)
        return 1
    raw_path = Path(argv[1])
    output_path = Path(argv[2])
    try:
        raw = json.loads(raw_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise InputError("raw JSON must be an object")
        model_input = build_model_input(raw)
        write_json_atomic(output_path, model_input)
    except (OSError, json.JSONDecodeError, InputError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(str(output_path.resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
