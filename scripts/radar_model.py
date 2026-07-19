from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from scripts.radar_contract import (
    PROMPT_VERSION,
    SCHEMA_VERSION,
    ContractError,
    non_empty,
    normalized_text,
    require_exact_fields,
)
from scripts.radar_locations import find_location_candidates, load_location_catalog

ROOT = Path(__file__).resolve().parents[1]
ENVELOPE_FIELDS = {"schema_version", "prompt_version", "input_fingerprint", "items"}
MODEL_ITEM_FIELDS = {
    "candidate_id", "ai_summary", "scope", "scope_evidence", "subjects",
    "location_mentions", "topic_mentions", "event_relation",
}
SUBJECT_TYPES = {"person", "government", "organization", "company", "project"}
SCOPES = {"national", "hainan", "domestic", "mixed", "foreign"}


class ModelOutputError(ContractError):
    pass


def _topic_catalog() -> list[dict[str, Any]]:
    payload = json.loads((ROOT / "config/topics.json").read_text(encoding="utf-8"))
    return payload["topics"]


def build_model_input(
    candidates: list[dict[str, Any]], event_candidates: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    locations = load_location_catalog()
    topics = [
        {"topic_id": row["topic_id"], "name": row["name"], "aliases": row["aliases"]}
        for row in _topic_catalog()
    ]
    events = list(event_candidates or [])
    items = [
        {
            "candidate_id": item["candidate_id"],
            "title": item["title"],
            "content": item["content"],
            "location_candidates": find_location_candidates(item["title"], item["content"], locations),
            "topic_candidates": topics,
            "event_candidates": events,
        }
        for item in candidates
    ]
    payload = {"schema_version": SCHEMA_VERSION, "prompt_version": PROMPT_VERSION, "items": items}
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {
        **payload,
        "input_fingerprint": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    }


def _evidence(value: Any, source_text: str, location: str) -> str:
    if not non_empty(value) or len(value) > 240:
        raise ModelOutputError(f"{location} is invalid")
    if normalized_text(value) not in source_text:
        raise ModelOutputError(f"{location} is not in source")
    return value.strip()


def validate_model_output(
    model_input: dict[str, Any],
    model_output: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    try:
        require_exact_fields(model_output, ENVELOPE_FIELDS, "model output")
        for field in ("schema_version", "prompt_version", "input_fingerprint"):
            if model_output.get(field) != model_input.get(field):
                raise ModelOutputError(f"model output {field} mismatch")
        items = model_output.get("items")
        if not isinstance(items, list):
            raise ModelOutputError("model output items must be an array")
        if [row.get("candidate_id") for row in items if isinstance(row, dict)] != [
            row["candidate_id"] for row in candidates
        ]:
            raise ModelOutputError("candidate_id order mismatch")

        for index, (item, candidate, input_item) in enumerate(zip(items, candidates, model_input["items"])):
            location = f"items[{index}]"
            require_exact_fields(item, MODEL_ITEM_FIELDS, location)
            summary = item.get("ai_summary")
            if summary is not None and (not non_empty(summary) or len(summary) > 300):
                raise ModelOutputError(f"{location}.ai_summary is invalid")
            if item.get("scope") not in SCOPES:
                raise ModelOutputError(f"{location}.scope is invalid")
            source_text = normalized_text(candidate["title"] + candidate["content"])
            _evidence(item.get("scope_evidence"), source_text, f"{location}.scope_evidence")

            subjects = item.get("subjects")
            if not isinstance(subjects, list) or len(subjects) > 8:
                raise ModelOutputError(f"{location}.subjects is invalid")
            for subject in subjects:
                require_exact_fields(subject, {"name", "type", "role", "evidence"}, f"{location}.subject")
                if not non_empty(subject.get("name")) or len(subject["name"]) > 80:
                    raise ModelOutputError(f"{location}.subject.name is invalid")
                if subject.get("type") not in SUBJECT_TYPES:
                    raise ModelOutputError(f"{location}.subject.type is invalid")
                if subject.get("role") is not None and (
                    not non_empty(subject["role"]) or len(subject["role"]) > 80
                ):
                    raise ModelOutputError(f"{location}.subject.role is invalid")
                _evidence(subject.get("evidence"), source_text, f"{location}.subject.evidence")

            allowed_locations = {row["location_id"] for row in input_item["location_candidates"]}
            mentions = item.get("location_mentions")
            if not isinstance(mentions, list) or len(mentions) > 5:
                raise ModelOutputError(f"{location}.location_mentions is invalid")
            for mention in mentions:
                require_exact_fields(mention, {"location_id", "evidence"}, f"{location}.location")
                if mention.get("location_id") not in allowed_locations:
                    raise ModelOutputError(f"{location}.location_id is outside candidates")
                _evidence(mention.get("evidence"), source_text, f"{location}.location.evidence")

            allowed_topics = {row["topic_id"] for row in input_item["topic_candidates"]}
            topics = item.get("topic_mentions")
            if not isinstance(topics, list) or len(topics) > 5:
                raise ModelOutputError(f"{location}.topic_mentions is invalid")
            for topic in topics:
                require_exact_fields(topic, {"topic_id", "evidence"}, f"{location}.topic")
                if topic.get("topic_id") not in allowed_topics:
                    raise ModelOutputError(f"{location}.topic_id is outside candidates")
                _evidence(topic.get("evidence"), source_text, f"{location}.topic.evidence")

            relation = item.get("event_relation")
            if not isinstance(relation, dict):
                raise ModelOutputError(f"{location}.event_relation is invalid")
            require_exact_fields(
                relation, {"relation", "event_id", "event_name", "evidence", "update_summary"},
                f"{location}.event_relation",
            )
            kind = relation.get("relation")
            if kind == "none":
                if any(relation.get(key) is not None for key in ("event_id", "event_name", "evidence", "update_summary")):
                    raise ModelOutputError(f"{location}.event_relation none values are invalid")
            elif kind == "existing":
                allowed_events = {row["event_id"] for row in input_item["event_candidates"]}
                if relation.get("event_id") not in allowed_events or relation.get("event_name") is not None:
                    raise ModelOutputError(f"{location}.event_relation existing target is invalid")
                _evidence(relation.get("evidence"), source_text, f"{location}.event_relation.evidence")
                if not non_empty(relation.get("update_summary")) or len(relation["update_summary"]) > 180:
                    raise ModelOutputError(f"{location}.event_relation.update_summary is invalid")
            elif kind == "new":
                if relation.get("event_id") is not None or not non_empty(relation.get("event_name")):
                    raise ModelOutputError(f"{location}.event_relation new target is invalid")
                if len(relation["event_name"]) > 120:
                    raise ModelOutputError(f"{location}.event_relation.event_name is invalid")
                _evidence(relation.get("evidence"), source_text, f"{location}.event_relation.evidence")
                if not non_empty(relation.get("update_summary")) or len(relation["update_summary"]) > 180:
                    raise ModelOutputError(f"{location}.event_relation.update_summary is invalid")
            else:
                raise ModelOutputError(f"{location}.event_relation.relation is invalid")
        return items
    except ContractError as exc:
        if isinstance(exc, ModelOutputError):
            raise
        raise ModelOutputError(str(exc)) from exc
