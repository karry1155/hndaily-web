from __future__ import annotations

from datetime import date
from typing import Any
from urllib.parse import urlparse

SCHEMA_VERSION = 5
PROMPT_VERSION = "radar-v3"
CATEGORIES = ("机会", "民生", "产业", "政策", "城市", "观察")
SCORE_FIELDS = (
    "hainan_relevance",
    "actionability",
    "impact_scope",
    "timeliness",
    "information_density",
)
SOURCE_CANDIDATE_FIELDS = {
    "candidate_id",
    "item_id",
    "source",
    "title",
    "content",
    "original_url",
    "published_date",
    "collected_date",
    "page_number",
    "page_name",
    "page_url",
    "pdf_url",
    "page_sequence",
}
BLOCK_FIELDS = {"source", "title", "content", "ai_summary", "original_url"}
SELECTED_BLOCK_FIELDS = {*BLOCK_FIELDS, "recommendation_reason"}
OPPORTUNITY_FIELDS = {
    "lifecycle",
    "deadline_date",
    "deadline_text",
    "evidence",
}
STORED_ITEM_FIELDS = {
    "schema_version",
    "item_id",
    "published_date",
    "collected_date",
    "category",
    "semantic_scores",
    "score_reasons",
    "base_score",
    "final_score",
    "selected",
    "daily_rank",
    "unselected_reason",
    "opportunity",
    "entities",
    "block",
}


class ContractError(ValueError):
    pass


def non_empty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def normalized_text(value: str) -> str:
    return "".join(value.split())


def require_exact_fields(
    value: dict[str, Any], expected: set[str], location: str
) -> None:
    missing = sorted(expected - set(value))
    unknown = sorted(set(value) - expected)
    if missing or unknown:
        raise ContractError(
            f"{location} fields missing={missing} unknown fields={unknown}"
        )


def validate_iso_date(value: Any, location: str) -> str:
    if not non_empty(value):
        raise ContractError(f"{location} must be an ISO date")
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise ContractError(f"{location} must be an ISO date") from exc


def validate_http_url(value: Any, location: str) -> str:
    if not non_empty(value):
        raise ContractError(f"{location} is required")
    parsed = urlparse(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ContractError(f"{location} must be HTTP/HTTPS")
    return value.strip()


def validate_source_candidate(candidate: dict[str, Any]) -> None:
    require_exact_fields(candidate, SOURCE_CANDIDATE_FIELDS, "source candidate")
    for field in (
        "candidate_id", "item_id", "source", "title", "content",
        "page_number", "page_name",
    ):
        if not non_empty(candidate.get(field)):
            raise ContractError(f"source candidate.{field} is required")
    validate_http_url(
        candidate.get("original_url"), "source candidate.original_url"
    )
    if not candidate["page_number"].isdigit() or len(candidate["page_number"]) != 3:
        raise ContractError("source candidate.page_number is invalid")
    if type(candidate.get("page_sequence")) is not int or candidate["page_sequence"] < 1:
        raise ContractError("source candidate.page_sequence is invalid")
    validate_http_url(candidate.get("page_url"), "source candidate.page_url")
    validate_http_url(candidate.get("pdf_url"), "source candidate.pdf_url")
    validate_iso_date(
        candidate.get("published_date"), "source candidate.published_date"
    )
    validate_iso_date(
        candidate.get("collected_date"), "source candidate.collected_date"
    )


def validate_stored_item(item: dict[str, Any]) -> None:
    require_exact_fields(item, STORED_ITEM_FIELDS, "stored item")
    if item.get("schema_version") != SCHEMA_VERSION:
        raise ContractError("stored item schema_version is invalid")
    for field in ("item_id", "published_date", "collected_date", "category"):
        if not non_empty(item.get(field)):
            raise ContractError(f"stored item.{field} is required")
    validate_iso_date(item["published_date"], "stored item.published_date")
    validate_iso_date(item["collected_date"], "stored item.collected_date")
    if item["category"] not in CATEGORIES:
        raise ContractError("stored item.category is invalid")
    if (
        item.get("selected") is not True
        or type(item.get("daily_rank")) is not int
        or item["daily_rank"] < 1
    ):
        raise ContractError(
            "stored item must be selected with a positive daily_rank"
        )
    scores = item.get("semantic_scores")
    reasons = item.get("score_reasons")
    if not isinstance(scores, dict) or set(scores) != set(SCORE_FIELDS):
        raise ContractError("stored item.semantic_scores is invalid")
    if not isinstance(reasons, dict) or set(reasons) != set(SCORE_FIELDS):
        raise ContractError("stored item.score_reasons is invalid")
    for field in SCORE_FIELDS:
        if type(scores.get(field)) is not int or not 0 <= scores[field] <= 10:
            raise ContractError(
                f"stored item.semantic_scores.{field} is invalid"
            )
        if not non_empty(reasons.get(field)):
            raise ContractError(f"stored item.score_reasons.{field} is required")
    if type(item.get("base_score")) not in (int, float) or type(
        item.get("final_score")
    ) not in (int, float):
        raise ContractError("stored item scores must be numeric")
    block = item.get("block")
    if not isinstance(block, dict):
        raise ContractError("stored item.block must be an object")
    require_exact_fields(block, SELECTED_BLOCK_FIELDS, "block")
    for field in (
        "source", "title", "content", "ai_summary", "recommendation_reason",
    ):
        if not non_empty(block.get(field)):
            raise ContractError(f"block.{field} is required")
    if normalized_text(block["recommendation_reason"]) == normalized_text(
        block["ai_summary"]
    ):
        raise ContractError(
            "block.recommendation_reason must differ from ai_summary"
        )
    validate_http_url(block.get("original_url"), "block.original_url")
    opportunity = item.get("opportunity")
    if not isinstance(opportunity, dict):
        raise ContractError("stored item.opportunity must be an object")
    require_exact_fields(opportunity, OPPORTUNITY_FIELDS, "opportunity")
    lifecycle = opportunity.get("lifecycle")
    if lifecycle not in {"dated", "ongoing", "unspecified", "not_applicable"}:
        raise ContractError("opportunity.lifecycle is invalid")
    deadline_values = [
        opportunity.get("deadline_date"),
        opportunity.get("deadline_text"),
        opportunity.get("evidence"),
    ]
    if item["category"] != "机会" and (
        lifecycle != "not_applicable"
        or any(value is not None for value in deadline_values)
    ):
        raise ContractError("non-opportunity lifecycle is invalid")
    if item["category"] == "机会" and lifecycle not in {
        "dated",
        "ongoing",
        "unspecified",
    }:
        raise ContractError("opportunity item lifecycle is invalid")
    if lifecycle == "dated":
        validate_iso_date(
            opportunity.get("deadline_date"), "opportunity.deadline_date"
        )
        if not all(non_empty(value) for value in deadline_values[1:]):
            raise ContractError("dated opportunity evidence is required")
    elif lifecycle == "ongoing":
        if (
            opportunity.get("deadline_date") is not None
            or opportunity.get("deadline_text") is not None
            or not non_empty(opportunity.get("evidence"))
        ):
            raise ContractError("ongoing opportunity evidence is required")
    elif any(value is not None for value in deadline_values):
        raise ContractError("non-dated opportunity fields must be null")
    entities = item.get("entities")
    if not isinstance(entities, dict) or set(entities) != {"actors", "locations", "action", "action_evidence"}:
        raise ContractError("stored item.entities is invalid")
    if not isinstance(entities["actors"], list) or not isinstance(entities["locations"], list):
        raise ContractError("stored item entity lists are invalid")
    for actor in entities["actors"]:
        if not isinstance(actor, dict) or set(actor) != {"name", "type", "role", "evidence"}:
            raise ContractError("stored item actor is invalid")
    for location in entities["locations"]:
        if not isinstance(location, dict) or set(location) != {"location_id", "name", "code", "level", "evidence"}:
            raise ContractError("stored item location is invalid")
    if not isinstance(entities["action"], str) or not isinstance(entities["action_evidence"], str):
        raise ContractError("stored item action is invalid")
