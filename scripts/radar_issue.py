from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from scripts.radar_contract import (
    BLOCK_FIELDS,
    SCHEMA_VERSION,
    SUPPORTED_PUBLIC_SCHEMA_VERSIONS,
    ContractError,
    non_empty,
    require_exact_fields,
    validate_http_url,
    validate_item_id,
    validate_iso_date,
)
from scripts.radar_model import CONTENT_FORMS
from scripts.radar_locations import (
    find_location_candidates,
    infer_exact_location_mentions,
    load_location_catalog,
    merge_location_mentions,
    resolve_location_mentions,
)

ROOT = Path(__file__).resolve().parents[1]
SCOPES = {"national", "hainan", "domestic", "mixed", "foreign"}
ENRICHMENT_STATUSES = {"complete"}
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
LEGACY_ISSUE_ITEM_FIELDS = {
    "schema_version", "item_id", "published_date", "collected_date",
    "page_number", "page_name", "page_sequence", "author",
    "enrichment_status", "scope", "scope_evidence", "subjects", "locations",
    "topics", "event_relation", "block",
}
V8_ISSUE_ITEM_FIELDS = {
    "schema_version", "item_id", "published_date", "collected_date",
    "page_number", "page_name", "page_sequence", "author",
    "enrichment_status", "scope", "scope_evidence", "subjects", "locations",
    "topics", "events", "plans", "block",
}
ISSUE_ITEM_FIELDS = {
    "schema_version", "item_id", "published_date", "collected_date",
    "page_number", "page_name", "page_sequence", "author",
    "enrichment_status", "scope", "scope_evidence", "subjects", "locations",
    "topic_profile", "resolved_topics", "content_form", "legacy_topics",
    "events", "plans", "block",
}
SUBJECT_BASE_FIELDS = {"subject_id", "name", "type", "role", "evidence"}
SUBJECT_ALIAS_FIELDS = {"name", "evidence"}
LOCATION_FIELDS = {"location_id", "name", "code", "level", "evidence"}
TOPIC_FIELDS = {"topic_id", "name", "evidence"}
OPEN_TOPIC_FIELDS = {"name", "evidence"}
TOPIC_PROFILE_FIELDS = {"primary", "secondary"}
RESOLVED_TOPIC_FIELDS = {"topic_id", "name", "relation", "path", "evidence"}
EVENT_FIELDS = {"relation", "event_id", "event_name", "evidence", "update_summary"}
EVENT_MENTION_FIELDS = {"name", "evidence"}
PLAN_FIELDS = {"name", "evidence"}


def _catalog(path: str) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _subject_id(subject: dict[str, Any]) -> str:
    name = re.sub(r"\s+", "", subject["name"]).casefold()
    digest = hashlib.sha256(f'{subject["type"]}:{name}'.encode("utf-8")).hexdigest()[:14]
    return f"subject-{digest}"


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


def validate_public_issue_item(item: dict[str, Any]) -> None:
    schema_version = item.get("schema_version")
    if schema_version not in SUPPORTED_PUBLIC_SCHEMA_VERSIONS:
        raise ContractError("public issue item schema_version is invalid")
    require_exact_fields(
        item,
        (
            LEGACY_ISSUE_ITEM_FIELDS
            if schema_version == 7
            else V8_ISSUE_ITEM_FIELDS
            if schema_version == 8
            else ISSUE_ITEM_FIELDS
        ),
        "public issue item",
    )
    for field in ("item_id", "page_number", "page_name"):
        if not non_empty(item.get(field)):
            raise ContractError(f"public issue item.{field} is required")
    validate_item_id(item.get("item_id"), "public issue item.item_id")
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
        subject_fields = set(subject) if isinstance(subject, dict) else set()
        if subject_fields not in (SUBJECT_BASE_FIELDS, SUBJECT_BASE_FIELDS | {"aliases"}):
            raise ContractError("public issue item subject fields are invalid")
        if "aliases" in subject:
            aliases = subject["aliases"]
            if not isinstance(aliases, list) or not aliases or len(aliases) > 6:
                raise ContractError("public issue item subject aliases are invalid")
            for alias in aliases:
                require_exact_fields(alias, SUBJECT_ALIAS_FIELDS, "public issue item subject alias")
                if not non_empty(alias.get("name")) or not non_empty(alias.get("evidence")):
                    raise ContractError("public issue item subject alias is invalid")
    for location in item.get("locations", []):
        require_exact_fields(location, LOCATION_FIELDS, "public issue item location")
    if schema_version in {7, 8}:
        for topic in item.get("topics", []):
            require_exact_fields(topic, TOPIC_FIELDS, "public issue item topic")
    list_fields = ["subjects", "locations"]
    if schema_version in {7, 8}:
        list_fields.append("topics")
    if schema_version in {8, SCHEMA_VERSION}:
        list_fields.extend(["events", "plans"])
        for event in item.get("events", []):
            require_exact_fields(event, EVENT_MENTION_FIELDS, "public issue item event")
            if not non_empty(event.get("name")) or not non_empty(event.get("evidence")):
                raise ContractError("public issue item event is invalid")
        for plan in item.get("plans", []):
            require_exact_fields(plan, PLAN_FIELDS, "public issue item plan")
            if (
                not non_empty(plan.get("name"))
                or not non_empty(plan.get("evidence"))
                or not plan["name"].startswith("《")
                or not plan["name"].endswith("》")
            ):
                raise ContractError("public issue item plan.name is invalid")
    if schema_version == SCHEMA_VERSION:
        profile = item.get("topic_profile")
        if not isinstance(profile, dict):
            raise ContractError("public issue item.topic_profile is invalid")
        require_exact_fields(profile, TOPIC_PROFILE_FIELDS, "public issue item topic_profile")
        primary = profile.get("primary")
        if not isinstance(primary, dict):
            raise ContractError("public issue item topic primary is invalid")
        require_exact_fields(primary, OPEN_TOPIC_FIELDS, "public issue item topic primary")
        if not non_empty(primary.get("name")) or not non_empty(primary.get("evidence")):
            raise ContractError("public issue item topic primary is invalid")
        secondary = profile.get("secondary")
        if not isinstance(secondary, list) or len(secondary) > 3:
            raise ContractError("public issue item topic secondary is invalid")
        for topic in secondary:
            require_exact_fields(topic, OPEN_TOPIC_FIELDS, "public issue item topic secondary")
            if not non_empty(topic.get("name")) or not non_empty(topic.get("evidence")):
                raise ContractError("public issue item topic secondary is invalid")
        resolved_topics = item.get("resolved_topics")
        if (
            not isinstance(resolved_topics, list)
            or len(resolved_topics) != 1 + len(secondary)
        ):
            raise ContractError("public issue item.resolved_topics is invalid")
        primary_count = 0
        source_topics = [primary, *secondary]
        for index, topic in enumerate(resolved_topics):
            require_exact_fields(topic, RESOLVED_TOPIC_FIELDS, "public issue item resolved topic")
            expected_relation = "primary" if index == 0 else "secondary"
            if topic.get("relation") != expected_relation:
                raise ContractError("public issue item resolved topic relation is invalid")
            primary_count += topic.get("relation") == "primary"
            if (
                not non_empty(topic.get("topic_id"))
                or not non_empty(topic.get("name"))
                or not non_empty(topic.get("evidence"))
                or not isinstance(topic.get("path"), list)
                or not topic["path"]
                or not all(non_empty(value) for value in topic["path"])
                or topic["path"][-1] != topic["name"]
                or topic["evidence"] != source_topics[index]["evidence"]
            ):
                raise ContractError("public issue item resolved topic is invalid")
        if primary_count != 1:
            raise ContractError("public issue item must have one primary resolved topic")
        if item.get("content_form") not in CONTENT_FORMS:
            raise ContractError("public issue item.content_form is invalid")
        legacy_topics = item.get("legacy_topics")
        if not isinstance(legacy_topics, list):
            raise ContractError("public issue item.legacy_topics is invalid")
        for topic in legacy_topics:
            require_exact_fields(topic, TOPIC_FIELDS, "public issue item legacy topic")
        list_fields.extend(["resolved_topics", "legacy_topics"])
    if not all(isinstance(item.get(field), list) for field in list_fields):
        raise ContractError("public issue item semantic lists are invalid")
    if schema_version == 7:
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
    if issue.get("schema_version") not in SUPPORTED_PUBLIC_SCHEMA_VERSIONS:
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
            validate_item_id(article.get("item_id"), "public issue article.item_id")
            sequences.append(article["page_sequence"])
        if sequences != sorted(sequences):
            raise ContractError("public issue articles are not ordered")
        article_total += len(page["articles"])
    if issue.get("article_count") != article_total:
        raise ContractError("public issue.article_count is invalid")
    if not isinstance(issue.get("front_page_item_ids"), list):
        raise ContractError("public issue.front_page_item_ids is invalid")
    for item_id in issue["front_page_item_ids"]:
        validate_item_id(item_id, "public issue.front_page_item_ids item")
    for section in issue.get("sections", []):
        require_exact_fields(section, SECTION_FIELDS, "public issue section")
        if not non_empty(section["name"]) or not isinstance(section["source_pages"], list):
            raise ContractError("public issue section is invalid")
        for article in section["articles"]:
            require_exact_fields(article, SECTION_ARTICLE_FIELDS, "public issue section article")
            validate_item_id(
                article.get("item_id"),
                "public issue section article.item_id",
            )
    if not isinstance(issue.get("sections"), list):
        raise ContractError("public issue.sections is invalid")


def build_public_issue(
    raw,
    candidates,
    semantic_items,
    topic_resolution_items,
    topic_catalog,
    _legacy_scored=None,
):
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
    from scripts.radar_topics import resolve_topic_profile
    issue_items = []
    for candidate, semantic in zip(candidates, semantic_items):
        detail_path = f'/items/{candidate["published_date"]}/{candidate["item_id"]}/'
        pages[candidate["page_number"]]["articles"].append({
            "item_id": candidate["item_id"], "title": candidate["title"],
            "page_sequence": candidate["page_sequence"], "detail_path": detail_path,
        })
        location_candidates = find_location_candidates(candidate["title"], candidate["content"], locations)
        location_mentions = merge_location_mentions(
            semantic["location_mentions"],
            infer_exact_location_mentions(
                candidate["title"], candidate["content"], location_candidates, locations
            ),
        )
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
            "locations": resolve_location_mentions(location_mentions, location_candidates, locations),
            "topic_profile": {
                "primary": {
                    "name": semantic["topic_profile"]["primary"]["name"].strip(),
                    "evidence": semantic["topic_profile"]["primary"]["evidence"].strip(),
                },
                "secondary": [
                    {"name": row["name"].strip(), "evidence": row["evidence"].strip()}
                    for row in semantic["topic_profile"]["secondary"]
                ],
            },
            "resolved_topics": resolve_topic_profile(
                semantic["topic_profile"], topic_resolution_items, topic_catalog
            ),
            "content_form": semantic["content_form"],
            "legacy_topics": [],
            "events": [
                {"name": row["name"].strip(), "evidence": row["evidence"].strip()}
                for row in semantic["events"]
            ],
            "plans": [
                {"name": row["name"].strip(), "evidence": row["evidence"].strip()}
                for row in semantic["plans"]
            ],
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
