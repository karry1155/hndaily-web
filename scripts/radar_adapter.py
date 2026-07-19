from __future__ import annotations

import hashlib
import re
from typing import Any
from urllib.parse import urlsplit

from scripts.radar_contract import (
    ContractError,
    canonicalize_source_url,
    validate_iso_date,
    validate_source_candidate,
)
from scripts.radar_filter import evaluate_issue

CONTENT_ID_RE = re.compile(r"(?:^|/)content_(\d+)_(\d+)\.htm$")


def _stable_id(url: str, published_date: str) -> str:
    date_key = published_date.replace("-", "")
    match = CONTENT_ID_RE.search(urlsplit(url).path)
    if match:
        return f"hndaily-{date_key}-{match.group(1)}-{match.group(2)}"
    canonical_url = canonicalize_source_url(url)
    digest = hashlib.sha256(canonical_url.encode("utf-8")).hexdigest()[:16]
    return f"hndaily-{date_key}-url-{digest}"


def adapt_hndaily(
    raw: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    published_date = validate_iso_date(raw.get("date"), "raw.date")
    fetched_at = str(raw.get("fetched_at", ""))
    collected_date = validate_iso_date(fetched_at[:10], "raw.fetched_at")
    records = evaluate_issue(raw)
    candidates = []
    canonical_urls_by_id: dict[str, str] = {}
    for record in records:
        if not record["passed"]:
            continue
        item_id = _stable_id(record["url"], published_date)
        canonical_url = canonicalize_source_url(record["url"])
        previous_url = canonical_urls_by_id.get(item_id)
        if previous_url is not None and previous_url != canonical_url:
            raise ContractError(
                f"item_id collision: {item_id} maps to both "
                f"{previous_url} and {canonical_url}"
            )
        canonical_urls_by_id[item_id] = canonical_url
        candidate = {
            "candidate_id": record["candidate_id"],
            "item_id": item_id,
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
