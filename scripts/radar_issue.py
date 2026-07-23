from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from scripts.radar_contract import (
    BLOCK_FIELDS, SCHEMA_VERSION, ContractError, non_empty, require_allowed_fields,
    require_exact_fields, validate_http_url, validate_iso_date, validate_item_id,
)
from scripts.radar_locations import (
    find_location_candidates, load_location_catalog, resolve_location_mentions,
)
from scripts.radar_model import load_topic_categories

ROOT = Path(__file__).resolve().parents[1]
SCOPES = {"hainan", "domestic", "mixed", "national", "foreign"}
SUBJECT_TYPES = {"person", "company", "organization"}
EVENT_TYPES = {"recurring_edition", "named_event", "incident"}
PLAN_MENTION_TYPES = {
    "proposed", "reviewed", "approved", "released", "implemented", "progress", "mentioned",
}
READER_INTENTS = {
    "apply", "register", "attend", "submit", "lookup", "use_service", "prepare", "avoid",
}
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
    "schema_version", "item_id", "published_date", "collected_date", "page_number",
    "page_name", "page_sequence", "author", "enrichment_status", "scope",
    "scope_evidence", "subjects", "locations", "topics", "events", "plans",
    "reader_leads", "block",
}


def _catalog(path: str) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _semantic_id(prefix: str, value: str) -> str:
    key = re.sub(r"\s+", "", value).casefold()
    return f"{prefix}-{hashlib.sha256(key.encode('utf-8')).hexdigest()[:14]}"


def _subject_id(subject: dict[str, Any]) -> str:
    return _semantic_id(f"subject-{subject['type']}", subject["name"])


def _section_mapping() -> dict[str, tuple[str, str]]:
    config = _catalog("config/page-sections.json")
    names = {row["section_id"]: row["name"] for row in config["sections"]}
    return {
        row["source_page_name"]: (row["section_id"], names[row["section_id"]])
        for row in config["rules"]
    }


def build_sections(pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rules = _section_mapping()
    sections: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for page in pages:
        section_id, name = rules.get(page["page_name"], ("", page["page_name"]))
        if not section_id:
            section_id = f"source-{hashlib.sha256(name.encode('utf-8')).hexdigest()[:10]}"
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
        section["articles"].extend({
            "item_id": article["item_id"],
            "title": article["title"],
            "source_page_number": page["page_number"],
            "page_sequence": article["page_sequence"],
            "detail_path": article["detail_path"],
        } for article in page["articles"])
    return [sections[section_id] for section_id in order]


def validate_public_issue_item(item: dict[str, Any]) -> None:
    require_exact_fields(item, ISSUE_ITEM_FIELDS, "public issue item")
    if item.get("schema_version") != SCHEMA_VERSION:
        raise ContractError("public issue item schema_version is invalid")
    validate_item_id(item.get("item_id"), "public issue item.item_id")
    validate_iso_date(item.get("published_date"), "public issue item.published_date")
    validate_iso_date(item.get("collected_date"), "public issue item.collected_date")
    for field in ("page_number", "page_name"):
        if not non_empty(item.get(field)):
            raise ContractError(f"public issue item.{field} is required")
    if type(item.get("page_sequence")) is not int or item["page_sequence"] < 1:
        raise ContractError("public issue item.page_sequence is invalid")
    if not isinstance(item.get("author"), str) or item.get("enrichment_status") != "complete":
        raise ContractError("public issue item metadata is invalid")
    if item.get("scope") not in SCOPES or not non_empty(item.get("scope_evidence")):
        raise ContractError("public issue item scope is invalid")

    subjects = item.get("subjects")
    if not isinstance(subjects, list):
        raise ContractError("public issue item.subjects is invalid")
    seen_subject_ids: set[str] = set()
    for subject in subjects:
        require_allowed_fields(
            subject, {"subject_id", "name", "type", "activities"},
            {"role", "aliases"}, "public issue item subject",
        )
        if (
            not non_empty(subject.get("subject_id"))
            or subject["subject_id"] in seen_subject_ids
            or not non_empty(subject.get("name"))
            or subject.get("type") not in SUBJECT_TYPES
        ):
            raise ContractError("public issue item subject is invalid")
        seen_subject_ids.add(subject["subject_id"])
        if "aliases" in subject and not isinstance(subject["aliases"], list):
            raise ContractError("public issue item subject aliases are invalid")
        activities = subject.get("activities")
        if not isinstance(activities, list) or not activities:
            raise ContractError("public issue item subject activities are invalid")
        for activity in activities:
            require_allowed_fields(
                activity, {"headline", "evidence"},
                {"occurred_on", "place", "detail_kind", "detail"},
                "public issue item subject activity",
            )
            if not non_empty(activity.get("headline")) or not non_empty(activity.get("evidence")):
                raise ContractError("public issue item subject activity is invalid")

    locations = item.get("locations")
    if not isinstance(locations, list):
        raise ContractError("public issue item.locations is invalid")
    for location in locations:
        require_exact_fields(
            location, {"location_id", "name", "code", "level", "evidence"},
            "public issue item location",
        )

    topics = item.get("topics")
    require_exact_fields(topics, {"primary", "secondary"}, "public issue item topics")
    require_exact_fields(
        topics.get("primary"), {"category_id", "category_name", "evidence"},
        "public issue item primary topic",
    )
    if not isinstance(topics.get("secondary"), list):
        raise ContractError("public issue item secondary topics are invalid")
    for topic in topics["secondary"]:
        require_exact_fields(topic, {"topic_id", "name", "evidence"}, "public issue item topic")

    if not isinstance(item.get("events"), list):
        raise ContractError("public issue item.events is invalid")
    for event in item["events"]:
        require_allowed_fields(
            event, {"event_id", "name", "event_type", "evidence"},
            {"series_id", "series_name", "occurred_on"}, "public issue item event",
        )
        if event.get("event_type") not in EVENT_TYPES:
            raise ContractError("public issue item event type is invalid")
    if not isinstance(item.get("plans"), list):
        raise ContractError("public issue item.plans is invalid")
    for plan in item["plans"]:
        require_exact_fields(
            plan, {"plan_id", "name", "mention_type", "evidence"},
            "public issue item plan",
        )
        if plan.get("mention_type") not in PLAN_MENTION_TYPES:
            raise ContractError("public issue item plan mention type is invalid")
    if not isinstance(item.get("reader_leads"), list):
        raise ContractError("public issue item.reader_leads is invalid")
    for lead in item["reader_leads"]:
        require_allowed_fields(
            lead, {"lead_id", "intent", "headline", "action", "evidence"},
            {"audience", "window", "channel"}, "public issue item reader lead",
        )
        if lead.get("intent") not in READER_INTENTS:
            raise ContractError("public issue item reader lead intent is invalid")

    block = item.get("block")
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
            validate_item_id(article.get("item_id"), "public issue article.item_id")
            sequences.append(article["page_sequence"])
        if sequences != sorted(sequences):
            raise ContractError("public issue articles are not ordered")
        article_total += len(page["articles"])
    if issue.get("article_count") != article_total:
        raise ContractError("public issue.article_count is invalid")
    if not isinstance(issue.get("front_page_item_ids"), list):
        raise ContractError("public issue.front_page_item_ids is invalid")
    sections = issue.get("sections")
    if not isinstance(sections, list):
        raise ContractError("public issue.sections is invalid")
    for section in sections:
        require_exact_fields(section, SECTION_FIELDS, "public issue section")
        for article in section["articles"]:
            require_exact_fields(article, SECTION_ARTICLE_FIELDS, "public issue section article")


def build_public_issue(raw, candidates, semantic_items):
    if len(candidates) != len(semantic_items):
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
    location_catalog = load_location_catalog()
    categories = {row["category_id"]: row for row in load_topic_categories()}
    issue_items = []
    for candidate, semantic in zip(candidates, semantic_items):
        detail_path = f'/items/{candidate["published_date"]}/{candidate["item_id"]}/'
        pages[candidate["page_number"]]["articles"].append({
            "item_id": candidate["item_id"],
            "title": candidate["title"],
            "page_sequence": candidate["page_sequence"],
            "detail_path": detail_path,
        })
        location_candidates = find_location_candidates(
            candidate["title"], candidate["content"], location_catalog
        )
        subjects = [
            {"subject_id": _subject_id(row), **row}
            for row in semantic["subjects"]
        ]
        locations = resolve_location_mentions(
            semantic["location_mentions"], location_candidates, location_catalog
        )
        category = categories[semantic["topics"]["primary"]["category_id"]]
        topics = {
            "primary": {
                "category_id": category["category_id"],
                "category_name": category["name"],
                "evidence": semantic["topics"]["primary"]["evidence"].strip(),
            },
            "secondary": [
                {
                    "topic_id": _semantic_id(
                        f'topic-{category["category_id"]}', row["name"]
                    ),
                    "name": row["name"].strip(),
                    "evidence": row["evidence"].strip(),
                }
                for row in semantic["topics"]["secondary"]
            ],
        }
        events = []
        for row in semantic["events"]:
            event = {
                "event_id": _semantic_id("event", row["name"]),
                "name": row["name"].strip(),
                "event_type": row["event_type"],
                "evidence": row["evidence"].strip(),
            }
            if "series_name" in row:
                event["series_name"] = row["series_name"].strip()
                event["series_id"] = _semantic_id("event-series", row["series_name"])
            if "occurred_on" in row:
                event["occurred_on"] = row["occurred_on"]
            events.append(event)
        plans = [
            {"plan_id": _semantic_id("plan", row["name"]), **row}
            for row in semantic["plans"]
        ]
        reader_leads = [
            {"lead_id": f'lead-{candidate["item_id"]}-{index}', **row}
            for index, row in enumerate(semantic["reader_leads"], 1)
        ]
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
            "subjects": subjects,
            "locations": locations,
            "topics": topics,
            "events": events,
            "plans": plans,
            "reader_leads": reader_leads,
            "block": {
                "source": candidate["source"],
                "title": candidate["title"],
                "content": candidate["content"],
                "ai_summary": semantic["ai_summary"].strip()
                if semantic["ai_summary"] is not None else None,
                "original_url": candidate["original_url"],
            },
        })
    for page in pages.values():
        page["articles"].sort(key=lambda row: row["page_sequence"])
    ordered_pages = [pages[key] for key in sorted(pages)]
    issue = {
        "schema_version": SCHEMA_VERSION,
        "date": raw["date"],
        "source": raw["source"],
        "page_count": len(ordered_pages),
        "article_count": len(candidates),
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
