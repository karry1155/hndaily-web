from __future__ import annotations

import re
from datetime import date
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlsplit, urlunsplit

SCHEMA_VERSION = 8
PROMPT_VERSION = "hnhot-v2.2"
SUPPORTED_PUBLIC_SCHEMA_VERSIONS = {7, SCHEMA_VERSION}
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
ITEM_ID_RE = re.compile(
    r"^hndaily-\d{8}-(?:\d+-\d+|url-[0-9a-f]{16})$"
)
TRACKING_QUERY_KEYS = {"from", "spm", "source"}


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


def canonicalize_source_url(value: Any) -> str:
    """Return a stable identity URL, independent of transport and tracking."""
    source = validate_http_url(value, "source URL")
    parsed = urlsplit(source)
    hostname = (parsed.hostname or "").lower()
    port = parsed.port
    netloc = hostname
    if port and not (
        (parsed.scheme.lower() == "http" and port == 80)
        or (parsed.scheme.lower() == "https" and port == 443)
    ):
        netloc = f"{hostname}:{port}"
    query = urlencode(
        sorted(
            (key, item)
            for key, item in parse_qsl(parsed.query, keep_blank_values=True)
            if not key.lower().startswith("utm_")
            and key.lower() not in TRACKING_QUERY_KEYS
        )
    )
    path = parsed.path.rstrip("/") or "/"
    return urlunsplit(("https", netloc, path, query, ""))


def validate_item_id(value: Any, location: str) -> str:
    if not non_empty(value) or not ITEM_ID_RE.fullmatch(value.strip()):
        raise ContractError(f"{location} is invalid")
    return value.strip()


def validate_source_candidate(candidate: dict[str, Any]) -> None:
    require_exact_fields(candidate, SOURCE_CANDIDATE_FIELDS, "source candidate")
    for field in (
        "candidate_id",
        "item_id",
        "source",
        "title",
        "content",
        "page_number",
        "page_name",
    ):
        if not non_empty(candidate.get(field)):
            raise ContractError(f"source candidate.{field} is required")
    validate_http_url(
        candidate.get("original_url"), "source candidate.original_url"
    )
    validate_item_id(candidate.get("item_id"), "source candidate.item_id")
    if not candidate["page_number"].isdigit() or len(candidate["page_number"]) != 3:
        raise ContractError("source candidate.page_number is invalid")
    if (
        type(candidate.get("page_sequence")) is not int
        or candidate["page_sequence"] < 1
    ):
        raise ContractError("source candidate.page_sequence is invalid")
    validate_http_url(candidate.get("page_url"), "source candidate.page_url")
    validate_http_url(candidate.get("pdf_url"), "source candidate.pdf_url")
    validate_iso_date(
        candidate.get("published_date"), "source candidate.published_date"
    )
    validate_iso_date(
        candidate.get("collected_date"), "source candidate.collected_date"
    )
