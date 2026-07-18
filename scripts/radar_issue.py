from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
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
from scripts.radar_locations import (
    find_location_candidates,
    load_location_catalog,
    resolve_location_mentions,
)

ROOT = Path(__file__).resolve().parents[1]
SCOPES = {"national", "hainan", "mixed"}
ENRICHMENT_STATUSES = {"complete", "legacy-derived", "pending"}
ISSUE_FIELDS = {
    "schema_version", "date", "source", "page_count", "article_count",
    "pages", "sections", "front_page_item_ids",
}
ISSUE_PAGE_FIELDS = {"page_number", "page_name", "page_url", "pdf_url", "articles"}
ISSUE_ARTICLE_FIELDS = {"item_id", "title", "page_sequence", "detail_path"}
SECTION_FIELDS = {"section_id", "name", "source_pages", "articles"}
SECTION_ARTICLE_FIELDS = {
    "item_id", "title", "source_page_number", "page_sequence", "detail_path",
}
ISSUE_ITEM_FIELDS = {
    "schema_version", "item_id", "published_date", "collected_date",
    "page_number", "page_name", "page_sequence", "author",
    "enrichment_status", "scope", "scope_evidence", "subjects", "locations",
    "topics", "event_relation", "block",
}
SUBJECT_FIELDS = {"subject_id", "name", "type", "role", "evidence"}
LOCATION_FIELDS = {"location_id", "name", "code", "level", "evidence"}
TOPIC_FIELDS = {"topic_id", "name", "evidence"}
EVENT_FIELDS = {"relation", "event_id", "event_name", "evidence", "update_summary"}


def _catalog(path: str) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _subject_id(subject: dict[str, Any]) -> str:
    name = re.sub(r"\s+", "", subject["name"]).casefold()
    aliases = _catalog("config/subjects.json").get("subjects", [])
    for row in aliases:
        terms = [row.get("name", ""), *row.get("aliases", [])]
        if name in {re.sub(r"\s+", "", value).casefold() for value in terms}:
            return row["subject_id"]
    digest = hashlib.sha256(f'{subject["type"]}:{name}'.encode("utf-8")).hexdigest()[:14]
    return f"subject-{digest}"


def _event_relation(value: dict[str, Any]) -> dict[str, Any]:
    result = dict(value)
    if result["relation"] == "new":
        normalized = re.sub(r"\s+", "", result["event_name"]).casefold()
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:14]
        result["event_id"] = f"event-{digest}"
    return result


def _section_mapping() -> tuple[dict[str, tuple[str, str]], dict[str, str]]:
    config = _catalog("config/page-sections.json")
    names = {row["section_id"]: row["name"] for row in config["sections"]}
    rules = {
        row["source_page_name"]: (row["section_id"], names[row["section_id"]])
        for row in config["rules"]
    }
    return rules, names


def build_sections(pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rules, _ = _section_mapping()
    sections: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for page in pages:
        section_id, name = rules.get(page["page_name"], ("", page["page_name"]))
        if not section_id:
            digest = hashlib.sha256(name.encode("utf-8")).hexdigest()[:10]
            section_id = f"source-{digest}"
        if section_id not in sections:
            order.append(section_id)
            sections[section_id] = {
                "section_id": section_id,
                "name": name,
                "source_pages": [],
                "articles": [],
            }
        section = sections[section_id]
        section["source_pages"].append(page["page_number"])
        section["articles"].extend(
            {
                "item_id": article["item_id"],
                "title": article["title"],
                "source_page_number": page["page_number"],
                "page_sequence": article["page_sequence"],
                "detail_path": article["detail_path"],
            }
            for article in page["articles"]
        )
    return [sections[section_id] for section_id in order]


def _legacy_scope(item: dict[str, Any]) -> str:
    title = item["block"]["title"]
    lead = item["block"].get("content", "")[:260]
    text = title + lead
    hainan_terms = (
        "海南", "自贸港", "海口", "三亚", "三沙", "儋州", "琼海", "文昌",
        "万宁", "东方", "五指山", "定安", "屯昌", "澄迈", "临高", "白沙",
        "昌江", "乐东", "陵水", "保亭", "琼中",
    )
    national_terms = (
        "新华社", "中共中央", "国务院", "全国", "国际", "全球", "世界",
        "外交", "中央军委", "国家主席", "迪拜", "东盟",
    )
    has_hainan = any(term in text for term in hainan_terms)
    has_national = any(term in text for term in national_terms)
    if has_hainan and has_national:
        return "mixed"
    if has_hainan:
        return "hainan"
    return "national"


def upgrade_legacy_issue_item(item: dict[str, Any]) -> dict[str, Any]:
    if item.get("schema_version") == SCHEMA_VERSION:
        return item
    if item.get("schema_version") != 5:
        raise ContractError("unsupported public issue item schema_version")
    scope = _legacy_scope(item)
    title = item["block"]["title"].strip()
    upgraded = {
        "schema_version": SCHEMA_VERSION,
        "item_id": item["item_id"],
        "published_date": item["published_date"],
        "collected_date": item["collected_date"],
        "page_number": item["page_number"],
        "page_name": item["page_name"],
        "page_sequence": item["page_sequence"],
        "author": item.get("author", ""),
        "enrichment_status": "legacy-derived",
        "scope": scope,
        "scope_evidence": title[:240],
        "subjects": [],
        "locations": [],
        "topics": [],
        "event_relation": {
            "relation": "none", "event_id": None, "event_name": None,
            "evidence": None, "update_summary": None,
        },
        "block": item["block"],
    }
    validate_public_issue_item(upgraded)
    return upgraded


def upgrade_legacy_issue(issue: dict[str, Any]) -> dict[str, Any]:
    if issue.get("schema_version") == SCHEMA_VERSION:
        return issue
    if issue.get("schema_version") != 5:
        raise ContractError("unsupported public issue schema_version")
    pages = issue["pages"]
    upgraded = {
        "schema_version": SCHEMA_VERSION,
        "date": issue["date"],
        "source": issue["source"],
        "page_count": issue["page_count"],
        "article_count": issue["scored_article_count"],
        "pages": pages,
        "sections": build_sections(pages),
        "front_page_item_ids": [
            row["item_id"] for page in pages if page["page_number"] == "001" for row in page["articles"]
        ],
    }
    validate_public_issue(upgraded)
    return upgraded


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
    if not isinstance(item.get("author"), str):
        raise ContractError("public issue item.author is invalid")
    if item.get("enrichment_status") not in ENRICHMENT_STATUSES:
        raise ContractError("public issue item.enrichment_status is invalid")
    if item.get("scope") not in SCOPES:
        raise ContractError("public issue item.scope is invalid")
    if not non_empty(item.get("scope_evidence")):
        raise ContractError("public issue item.scope_evidence is invalid")
    for subject in item.get("subjects", []):
        require_exact_fields(subject, SUBJECT_FIELDS, "public issue item subject")
    for location in item.get("locations", []):
        require_exact_fields(location, LOCATION_FIELDS, "public issue item location")
    for topic in item.get("topics", []):
        require_exact_fields(topic, TOPIC_FIELDS, "public issue item topic")
    if not all(isinstance(item.get(field), list) for field in ("subjects", "locations", "topics")):
        raise ContractError("public issue item semantic lists are invalid")
    relation = item.get("event_relation")
    if not isinstance(relation, dict):
        raise ContractError("public issue item.event_relation is invalid")
    require_exact_fields(relation, EVENT_FIELDS, "public issue item event_relation")
    block = item.get("block")
    if not isinstance(block, dict):
        raise ContractError("public issue item.block must be an object")
    require_exact_fields(block, BLOCK_FIELDS, "public issue item block")
    for field in ("source", "title", "content"):
        if not non_empty(block.get(field)):
            raise ContractError(f"public issue item block.{field} is required")
    if block.get("ai_summary") is not None and not non_empty(block["ai_summary"]):
        raise ContractError("public issue item block.ai_summary is invalid")
    validate_http_url(block.get("original_url"), "public issue item block.original_url")


def validate_public_issue(issue: dict[str, Any]) -> None:
    require_exact_fields(issue, ISSUE_FIELDS, "public issue")
    if issue.get("schema_version") != SCHEMA_VERSION:
        raise ContractError("public issue schema_version is invalid")
    validate_iso_date(issue.get("date"), "public issue.date")
    if not non_empty(issue.get("source")):
        raise ContractError("public issue.source is required")
    pages = issue.get("pages")
    if not isinstance(pages, list) or issue.get("page_count") != len(pages):
        raise ContractError("public issue.page_count is invalid")
    article_total = 0
    previous_page = "000"
    for page in pages:
        require_exact_fields(page, ISSUE_PAGE_FIELDS, "public issue page")
        if page["page_number"] <= previous_page:
            raise ContractError("public issue pages are not ordered")
        previous_page = page["page_number"]
        validate_http_url(page["page_url"], "public issue page.page_url")
        validate_http_url(page["pdf_url"], "public issue page.pdf_url")
        sequences = []
        for article in page["articles"]:
            require_exact_fields(article, ISSUE_ARTICLE_FIELDS, "public issue article")
            sequences.append(article["page_sequence"])
        if sequences != sorted(sequences):
            raise ContractError("public issue articles are not ordered")
        article_total += len(page["articles"])
    if issue.get("article_count") != article_total:
        raise ContractError("public issue.article_count is invalid")
    if not isinstance(issue.get("front_page_item_ids"), list):
        raise ContractError("public issue.front_page_item_ids is invalid")
    for section in issue.get("sections", []):
        require_exact_fields(section, SECTION_FIELDS, "public issue section")
        if not non_empty(section["name"]) or not isinstance(section["source_pages"], list):
            raise ContractError("public issue section is invalid")
        for article in section["articles"]:
            require_exact_fields(article, SECTION_ARTICLE_FIELDS, "public issue section article")
    if not isinstance(issue.get("sections"), list):
        raise ContractError("public issue.sections is invalid")


def build_public_issue(raw, candidates, semantic_items, _legacy_scored=None):
    if len(candidates) != len(semantic_items):
        raise ContractError("public issue candidate alignment mismatch")
    pages = {
        page["page"]: {
            "page_number": page["page"], "page_name": page["page_name"],
            "page_url": page["page_url"], "pdf_url": page["pdf_url"], "articles": [],
        }
        for page in raw["pages"]
    }
    locations = load_location_catalog()
    topic_catalog = {row["topic_id"]: row for row in _catalog("config/topics.json")["topics"]}
    issue_items = []
    for candidate, semantic in zip(candidates, semantic_items):
        detail_path = f'/items/{candidate["published_date"]}/{candidate["item_id"]}/'
        pages[candidate["page_number"]]["articles"].append({
            "item_id": candidate["item_id"], "title": candidate["title"],
            "page_sequence": candidate["page_sequence"], "detail_path": detail_path,
        })
        location_candidates = find_location_candidates(candidate["title"], candidate["content"], locations)
        issue_items.append({
            "schema_version": SCHEMA_VERSION,
            "item_id": candidate["item_id"],
            "published_date": candidate["published_date"],
            "collected_date": candidate["collected_date"],
            "page_number": candidate["page_number"],
            "page_name": candidate["page_name"],
            "page_sequence": candidate["page_sequence"],
            "author": candidate.get("author", ""),
            "enrichment_status": "complete",
            "scope": semantic["scope"],
            "scope_evidence": semantic["scope_evidence"].strip(),
            "subjects": [
                {"subject_id": _subject_id(row), **row} for row in semantic["subjects"]
            ],
            "locations": resolve_location_mentions(semantic["location_mentions"], location_candidates, locations),
            "topics": [
                {
                    "topic_id": row["topic_id"],
                    "name": topic_catalog[row["topic_id"]]["name"],
                    "evidence": row["evidence"].strip(),
                }
                for row in semantic["topic_mentions"]
            ],
            "event_relation": _event_relation(semantic["event_relation"]),
            "block": {
                "source": candidate["source"], "title": candidate["title"],
                "content": candidate["content"],
                "ai_summary": semantic["ai_summary"].strip() if semantic["ai_summary"] is not None else None,
                "original_url": candidate["original_url"],
            },
        })
    for page in pages.values():
        page["articles"].sort(key=lambda row: row["page_sequence"])
    ordered_pages = [pages[key] for key in sorted(pages)]
    issue = {
        "schema_version": SCHEMA_VERSION,
        "date": raw["date"], "source": raw["source"],
        "page_count": len(ordered_pages), "article_count": len(candidates),
        "pages": ordered_pages,
        "sections": build_sections(ordered_pages),
        "front_page_item_ids": [
            row["item_id"] for row in pages.get("001", {}).get("articles", [])
        ],
    }
    validate_public_issue(issue)
    for item in issue_items:
        validate_public_issue_item(item)
    return issue, issue_items
