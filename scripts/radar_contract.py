from __future__ import annotations

from datetime import date
from typing import Any
from urllib.parse import urlparse

SCHEMA_VERSION = 3
PROMPT_VERSION = "radar-v1"
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
}


class ContractError(ValueError):
    pass


def non_empty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


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
    for field in ("candidate_id", "item_id", "source", "title", "content"):
        if not non_empty(candidate.get(field)):
            raise ContractError(f"source candidate.{field} is required")
    validate_http_url(
        candidate.get("original_url"), "source candidate.original_url"
    )
    validate_iso_date(
        candidate.get("published_date"), "source candidate.published_date"
    )
    validate_iso_date(
        candidate.get("collected_date"), "source candidate.collected_date"
    )
