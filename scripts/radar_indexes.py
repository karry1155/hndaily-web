from __future__ import annotations

from datetime import date
from typing import Any

from scripts.radar_contract import CATEGORIES, validate_stored_item
from scripts.radar_select import select_focus

CATEGORY_SLUGS = {
    "机会": "opportunity",
    "民生": "livelihood",
    "产业": "industry",
    "政策": "policy",
    "城市": "city",
    "观察": "observation",
}


def _summary(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "item_id": item["item_id"],
        "published_date": item["published_date"],
        "daily_rank": item["daily_rank"],
        "category": item["category"],
        "source": item["block"]["source"],
        "title": item["block"]["title"],
        "ai_summary": item["block"]["ai_summary"],
        "detail_path": (
            f"/items/{item['published_date']}/{item['item_id']}/"
        ),
    }


def _pages(prefix, values, page_size, stem="page"):
    chunks = [
        values[index : index + page_size]
        for index in range(0, len(values), page_size)
    ] or [[]]
    return {
        f"{prefix}/{stem}-{number:03d}.json": {
            "page": number,
            "page_count": len(chunks),
            "items": [_summary(item) for item in chunk],
        }
        for number, chunk in enumerate(chunks, 1)
    }


def build_indexes(items, as_of, page_size=20):
    date.fromisoformat(as_of)
    if type(page_size) is not int or page_size < 1:
        raise ValueError("page_size must be positive")
    for item in items:
        validate_stored_item(item)
    ordered = sorted(
        items,
        key=lambda item: (
            -int(item["published_date"].replace("-", "")),
            item["daily_rank"],
            item["item_id"],
        ),
    )
    indexes = _pages("all", ordered, page_size)
    indexes["focus.json"] = {
        "updated_through": max(
            (item["published_date"] for item in items), default=as_of
        ),
        "items": [
            {**_summary(item), "focus_rank": item["focus_rank"]}
            for item in select_focus(items)
        ],
    }
    for published_date in sorted({item["published_date"] for item in items}):
        same_date = [
            item for item in ordered if item["published_date"] == published_date
        ]
        indexes[f"dates/{published_date}.json"] = {
            "date": published_date,
            "items": [_summary(item) for item in same_date],
        }
    for category in CATEGORIES:
        category_items = [
            item for item in ordered if item["category"] == category
        ]
        slug = CATEGORY_SLUGS[category]
        if category != "机会":
            indexes.update(_pages(f"categories/{slug}", category_items, page_size))
            continue
        expired = []
        active = []
        for item in category_items:
            opportunity = item["opportunity"]
            if (
                opportunity["lifecycle"] == "dated"
                and opportunity["deadline_date"] < as_of
            ):
                expired.append(item)
            else:
                active.append(item)
        lifecycle_order = {"dated": 0, "ongoing": 1, "unspecified": 2}
        active.sort(
            key=lambda item: (
                lifecycle_order[item["opportunity"]["lifecycle"]],
                item["opportunity"].get("deadline_date") or "9999-12-31",
                -int(item["published_date"].replace("-", "")),
                item["item_id"],
            )
        )
        indexes.update(
            _pages(
                "categories/opportunity",
                active,
                page_size,
                stem="active-page",
            )
        )
        indexes.update(
            _pages(
                "categories/opportunity",
                expired,
                page_size,
                stem="expired-page",
            )
        )
    return indexes
