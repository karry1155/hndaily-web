from __future__ import annotations

from typing import Any

from scripts.radar_contract import (
    BLOCK_FIELDS,
    SCHEMA_VERSION,
    ContractError,
    non_empty,
    require_exact_fields,
    validate_http_url,
    validate_iso_date,
)

ISSUE_FIELDS = {
    "schema_version", "date", "source", "page_count",
    "scored_article_count", "pages",
}
ISSUE_PAGE_FIELDS = {
    "page_number", "page_name", "page_url", "pdf_url", "articles",
}
ISSUE_ARTICLE_FIELDS = {
    "item_id", "title", "page_sequence", "detail_path",
}
ISSUE_ITEM_FIELDS = {
    "schema_version", "item_id", "published_date", "collected_date",
    "page_number", "page_name", "page_sequence", "block",
}


def validate_public_issue_item(item: dict[str, Any]) -> None:
    require_exact_fields(item, ISSUE_ITEM_FIELDS, "public issue item")
    if item.get("schema_version") != SCHEMA_VERSION:
        raise ContractError("public issue item schema_version is invalid")
    for field in ("item_id", "page_number", "page_name"):
        if not non_empty(item.get(field)):
            raise ContractError(f"public issue item.{field} is required")
    validate_iso_date(item.get("published_date"), "public issue item.published_date")
    validate_iso_date(item.get("collected_date"), "public issue item.collected_date")
    if type(item.get("page_sequence")) is not int or item["page_sequence"] < 1:
        raise ContractError("public issue item.page_sequence is invalid")
    block = item.get("block")
    if not isinstance(block, dict):
        raise ContractError("public issue item.block must be an object")
    require_exact_fields(block, BLOCK_FIELDS, "public issue item block")
    for field in ("source", "title", "content", "ai_summary"):
        if not non_empty(block.get(field)):
            raise ContractError(f"public issue item block.{field} is required")
    validate_http_url(block.get("original_url"), "public issue item block.original_url")


def validate_public_issue(issue: dict[str, Any]) -> None:
    require_exact_fields(issue, ISSUE_FIELDS, "public issue")
    if issue.get("schema_version") != SCHEMA_VERSION:
        raise ContractError("public issue schema_version is invalid")
    validate_iso_date(issue.get("date"), "public issue.date")
    if not non_empty(issue.get("source")):
        raise ContractError("public issue.source is required")
    pages = issue.get("pages")
    if not isinstance(pages, list):
        raise ContractError("public issue.pages must be an array")
    if type(issue.get("page_count")) is not int or issue["page_count"] != len(pages):
        raise ContractError("public issue.page_count is invalid")
    article_total = 0
    previous_page = "000"
    for page in pages:
        require_exact_fields(page, ISSUE_PAGE_FIELDS, "public issue page")
        if page["page_number"] <= previous_page:
            raise ContractError("public issue pages are not ordered")
        previous_page = page["page_number"]
        if not non_empty(page["page_name"]):
            raise ContractError("public issue page.page_name is required")
        validate_http_url(page["page_url"], "public issue page.page_url")
        validate_http_url(page["pdf_url"], "public issue page.pdf_url")
        sequences = []
        for article in page["articles"]:
            require_exact_fields(article, ISSUE_ARTICLE_FIELDS, "public issue article")
            sequences.append(article["page_sequence"])
        if sequences != sorted(sequences):
            raise ContractError("public issue articles are not ordered")
        article_total += len(page["articles"])
    if article_total != issue.get("scored_article_count"):
        raise ContractError("public issue scored_article_count is invalid")


def build_public_issue(raw, candidates, semantic_items, scored):
    if not (len(candidates) == len(semantic_items) == len(scored)):
        raise ContractError("public issue candidate alignment mismatch")
    pages = {
        page["page"]: {
            "page_number": page["page"],
            "page_name": page["page_name"],
            "page_url": page["page_url"],
            "pdf_url": page["pdf_url"],
            "articles": [],
        }
        for page in raw["pages"]
    }
    issue_items = []
    for candidate, semantic, _scoring in zip(candidates, semantic_items, scored):
        detail_path = f'/items/{candidate["published_date"]}/{candidate["item_id"]}/'
        pages[candidate["page_number"]]["articles"].append({
            "item_id": candidate["item_id"],
            "title": candidate["title"],
            "page_sequence": candidate["page_sequence"],
            "detail_path": detail_path,
        })
        issue_items.append({
            "schema_version": SCHEMA_VERSION,
            "item_id": candidate["item_id"],
            "published_date": candidate["published_date"],
            "collected_date": candidate["collected_date"],
            "page_number": candidate["page_number"],
            "page_name": candidate["page_name"],
            "page_sequence": candidate["page_sequence"],
            "block": {
                "source": candidate["source"],
                "title": candidate["title"],
                "content": candidate["content"],
                "ai_summary": semantic["ai_summary"].strip(),
                "original_url": candidate["original_url"],
            },
        })
    for page in pages.values():
        page["articles"].sort(key=lambda article: article["page_sequence"])
    issue = {
        "schema_version": SCHEMA_VERSION,
        "date": raw["date"],
        "source": raw["source"],
        "page_count": len(raw["pages"]),
        "scored_article_count": len(candidates),
        "pages": [pages[key] for key in sorted(pages)],
    }
    validate_public_issue(issue)
    for item in issue_items:
        validate_public_issue_item(item)
    return issue, issue_items
