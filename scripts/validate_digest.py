#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

CATEGORIES = [
    "民生/办事",
    "政策/监管",
    "产业/项目",
    "经济/数据",
    "城市/出行/风险",
    "人事/反腐",
    "重要但不必精读",
    "已跳过",
]

CONFIDENCE = {"full_text", "short_item", "headline_only", "partial"}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
WEEK_RE = re.compile(r"^\d{4}-W\d{2}$")


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_sources(sources: Any, errors: list[str], weekly: bool) -> None:
    require(isinstance(sources, list), "sources must be an array", errors)
    if not isinstance(sources, list):
        return
    for index, source in enumerate(sources):
        require(isinstance(source, dict), f"sources[{index}] must be an object", errors)
        if not isinstance(source, dict):
            continue
        if weekly:
            require(
                DATE_RE.match(str(source.get("date", ""))) is not None,
                f"sources[{index}].date must be ISO date",
                errors,
            )
        require(is_non_empty_string(source.get("headline")), f"sources[{index}].headline is required", errors)
        require(is_non_empty_string(source.get("page")), f"sources[{index}].page is required", errors)
        require(is_non_empty_string(source.get("url")), f"sources[{index}].url is required", errors)


def validate_daily(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    require(data.get("type") == "daily", "type must be daily", errors)
    require(DATE_RE.match(str(data.get("date", ""))) is not None, "date must be ISO date", errors)
    require(is_non_empty_string(data.get("source")), "source is required", errors)
    require(isinstance(data.get("page_count"), int) and data["page_count"] >= 0, "page_count must be >= 0", errors)
    require(isinstance(data.get("article_count"), int) and data["article_count"] >= 0, "article_count must be >= 0", errors)
    require(data.get("reading_minutes") == 5, "daily reading_minutes must be 5", errors)

    top_items = data.get("top_items")
    require(isinstance(top_items, list), "top_items must be an array", errors)
    if isinstance(top_items, list):
        require(len(top_items) <= 5, "daily top_items must contain at most 5 items", errors)
        for index, item in enumerate(top_items):
            require(isinstance(item, dict), f"top_items[{index}] must be an object", errors)
            if not isinstance(item, dict):
                continue
            require(item.get("rank") == index + 1, f"top_items[{index}].rank must be {index + 1}", errors)
            require(is_non_empty_string(item.get("title")), f"top_items[{index}].title is required", errors)
            require(item.get("category") in CATEGORIES, f"top_items[{index}].category is invalid", errors)
            require(is_non_empty_string(item.get("why_it_matters")), f"top_items[{index}].why_it_matters is required", errors)
            require(isinstance(item.get("key_facts"), list), f"top_items[{index}].key_facts must be an array", errors)
            validate_sources(item.get("sources"), errors, weekly=False)
            require(item.get("confidence") in CONFIDENCE, f"top_items[{index}].confidence is invalid", errors)

    categories = data.get("categories")
    require(isinstance(categories, dict), "categories must be an object", errors)
    if isinstance(categories, dict):
        for category in CATEGORIES:
            require(category in categories, f"missing category {category}", errors)
            require(isinstance(categories.get(category), list), f"category {category} must be an array", errors)

    require(is_non_empty_string(data.get("generated_at")), "generated_at is required", errors)
    return errors


def validate_weekly(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    require(data.get("type") == "weekly", "type must be weekly", errors)
    require(WEEK_RE.match(str(data.get("week", ""))) is not None, "week must look like YYYY-Www", errors)
    require(data.get("reading_minutes") == 15, "weekly reading_minutes must be 15", errors)
    date_range = data.get("date_range")
    require(isinstance(date_range, dict), "date_range must be an object", errors)
    if isinstance(date_range, dict):
        require(DATE_RE.match(str(date_range.get("start", ""))) is not None, "date_range.start must be ISO date", errors)
        require(DATE_RE.match(str(date_range.get("end", ""))) is not None, "date_range.end must be ISO date", errors)
    top_items = data.get("top_items")
    require(isinstance(top_items, list), "top_items must be an array", errors)
    if isinstance(top_items, list):
        require(len(top_items) <= 15, "weekly top_items must contain at most 15 items", errors)
        for index, item in enumerate(top_items):
            require(isinstance(item, dict), f"top_items[{index}] must be an object", errors)
            if not isinstance(item, dict):
                continue
            require(item.get("rank") == index + 1, f"top_items[{index}].rank must be {index + 1}", errors)
            require(is_non_empty_string(item.get("title")), f"top_items[{index}].title is required", errors)
            require(is_non_empty_string(item.get("why_it_matters")), f"top_items[{index}].why_it_matters is required", errors)
            validate_sources(item.get("sources"), errors, weekly=True)
    require(isinstance(data.get("themes"), list), "themes must be an array", errors)
    require(isinstance(data.get("watch_next"), list), "watch_next must be an array", errors)
    require(is_non_empty_string(data.get("generated_at")), "generated_at is required", errors)
    return errors


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: validate_digest.py <digest.json>", file=sys.stderr)
        return 1
    path = Path(argv[1])
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"ERROR: cannot read JSON: {exc}", file=sys.stderr)
        return 1
    if not isinstance(data, dict):
        print("ERROR: top-level JSON must be an object", file=sys.stderr)
        return 1
    errors = validate_weekly(data) if data.get("type") == "weekly" else validate_daily(data)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"OK: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
