from __future__ import annotations

import hashlib
import re
from typing import Any

from scripts.editorial_filter import evaluate_issue
from scripts.radar_contract import validate_iso_date, validate_source_candidate

CONTENT_ID_RE = re.compile(r"content_\d+_(\d+)\.htm(?:\?.*)?$")


def _stable_id(url: str, published_date: str, title: str) -> str:
    match = CONTENT_ID_RE.search(url)
    if match:
        return f"hndaily-{match.group(1)}"
    digest = hashlib.sha256(
        f"{published_date}\n{title}".encode("utf-8")
    ).hexdigest()[:16]
    return f"hndaily-{published_date}-{digest}"


def adapt_hndaily(
    raw: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    published_date = validate_iso_date(raw.get("date"), "raw.date")
    fetched_at = str(raw.get("fetched_at", ""))
    collected_date = validate_iso_date(fetched_at[:10], "raw.fetched_at")
    records = evaluate_issue(raw)
    candidates = []
    for record in records:
        if not record["passed"]:
            continue
        candidate = {
            "candidate_id": record["candidate_id"],
            "item_id": _stable_id(
                record["url"], published_date, record["original_title"]
            ),
            "source": str(raw.get("source", "")).strip(),
            "title": record["original_title"],
            "content": record["content"].strip(),
            "original_url": record["url"],
            "published_date": published_date,
            "collected_date": collected_date,
            "page_number": record["page"],
            "page_name": record["page_name"],
            "page_url": record["page_url"],
            "pdf_url": record["pdf_url"],
            "page_sequence": record["seq"],
            "author": record["author"].strip(),
        }
        validate_source_candidate({key: value for key, value in candidate.items() if key != "author"})
        candidates.append(candidate)
    return candidates, records
