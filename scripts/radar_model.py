from __future__ import annotations

import hashlib
import json
from typing import Any

from scripts.radar_contract import (
    CATEGORIES,
    PROMPT_VERSION,
    SCHEMA_VERSION,
    SCORE_FIELDS,
    ContractError,
    non_empty,
    normalized_text,
    require_exact_fields,
    validate_iso_date,
)
from scripts.radar_locations import find_location_candidates, load_location_catalog

ENVELOPE_FIELDS = {
    "schema_version",
    "prompt_version",
    "input_fingerprint",
    "items",
}
MODEL_ITEM_FIELDS = {
    "candidate_id",
    "ai_summary",
    "recommendation_reason",
    "category",
    *SCORE_FIELDS,
    "score_reasons",
    "opportunity_lifecycle",
    "deadline_date",
    "deadline_text",
    "deadline_evidence",
    "actors",
    "location_mentions",
    "action",
    "action_evidence",
}
LIFECYCLES = {"dated", "ongoing", "unspecified", "not_applicable"}
ACTOR_TYPES = {"person", "organization", "government", "company"}


class ModelOutputError(ContractError):
    pass


def build_model_input(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    catalog = load_location_catalog()
    items = [
        {
            "candidate_id": item["candidate_id"],
            "title": item["title"],
            "content": item["content"],
            "location_candidates": find_location_candidates(
                item["title"], item["content"], catalog
            ),
        }
        for item in candidates
    ]
    payload = {
        "schema_version": SCHEMA_VERSION,
        "prompt_version": PROMPT_VERSION,
        "items": items,
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return {
        **payload,
        "input_fingerprint": hashlib.sha256(
            canonical.encode("utf-8")
        ).hexdigest(),
    }


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
        expected_ids = [item["candidate_id"] for item in candidates]
        actual_ids = [
            item.get("candidate_id")
            for item in items
            if isinstance(item, dict)
        ]
        if actual_ids != expected_ids:
            raise ModelOutputError("candidate_id order mismatch")
        for index, (item, candidate) in enumerate(zip(items, candidates)):
            require_exact_fields(item, MODEL_ITEM_FIELDS, f"items[{index}]")
            if not non_empty(item.get("ai_summary")):
                raise ModelOutputError(
                    f"items[{index}].ai_summary is required"
                )
            if not non_empty(item.get("recommendation_reason")):
                raise ModelOutputError(
                    f"items[{index}].recommendation_reason is required"
                )
            if normalized_text(item["recommendation_reason"]) == normalized_text(
                item["ai_summary"]
            ):
                raise ModelOutputError(
                    f"items[{index}].recommendation_reason must differ from ai_summary"
                )
            if item.get("category") not in CATEGORIES:
                raise ModelOutputError(f"items[{index}].category is invalid")
            for field in SCORE_FIELDS:
                if type(item.get(field)) is not int or not 0 <= item[field] <= 10:
                    raise ModelOutputError(
                        f"items[{index}].{field} must be 0..10 integer"
                    )
            source_text = normalized_text(candidate["title"] + candidate["content"])
            actors = item.get("actors")
            if not isinstance(actors, list) or len(actors) > 5:
                raise ModelOutputError(f"items[{index}].actors is invalid")
            for actor in actors:
                if not isinstance(actor, dict) or set(actor) != {"name", "type", "role", "evidence"}:
                    raise ModelOutputError(f"items[{index}].actors fields are invalid")
                if not non_empty(actor.get("name")) or actor.get("type") not in ACTOR_TYPES:
                    raise ModelOutputError(f"items[{index}].actors value is invalid")
                if actor.get("role") is not None and not non_empty(actor.get("role")):
                    raise ModelOutputError(f"items[{index}].actors role is invalid")
                if not non_empty(actor.get("evidence")) or normalized_text(actor["evidence"]) not in source_text:
                    raise ModelOutputError(f"items[{index}].actors evidence is invalid")
            mentions = item.get("location_mentions")
            allowed_ids = {
                row["location_id"] for row in model_input["items"][index]["location_candidates"]
            }
            if not isinstance(mentions, list) or len(mentions) > 5:
                raise ModelOutputError(f"items[{index}].location_mentions is invalid")
            for mention in mentions:
                if not isinstance(mention, dict) or set(mention) != {"location_id", "evidence"}:
                    raise ModelOutputError(f"items[{index}].location_mentions fields are invalid")
                if mention.get("location_id") not in allowed_ids:
                    raise ModelOutputError(f"items[{index}].location_id is outside candidates")
                if not non_empty(mention.get("evidence")) or normalized_text(mention["evidence"]) not in source_text:
                    raise ModelOutputError(f"items[{index}].location evidence is invalid")
            action = item.get("action")
            action_evidence = item.get("action_evidence")
            if not isinstance(action, str) or len(action.strip()) > 60:
                raise ModelOutputError(f"items[{index}].action is invalid")
            if bool(action.strip()) != bool(isinstance(action_evidence, str) and action_evidence.strip()):
                raise ModelOutputError(f"items[{index}].action evidence pair is invalid")
            if action.strip() and normalized_text(action_evidence) not in source_text:
                raise ModelOutputError(f"items[{index}].action_evidence is invalid")
            reasons = item.get("score_reasons")
            if not isinstance(reasons, dict) or set(reasons) != set(SCORE_FIELDS):
                raise ModelOutputError(
                    f"items[{index}].score_reasons is invalid"
                )
            lifecycle = item.get("opportunity_lifecycle")
            if lifecycle not in LIFECYCLES:
                raise ModelOutputError(
                    f"items[{index}].opportunity_lifecycle is invalid"
                )
            deadline_values = [
                item.get("deadline_date"),
                item.get("deadline_text"),
                item.get("deadline_evidence"),
            ]
            if item["category"] != "机会" and (
                lifecycle != "not_applicable"
                or any(value is not None for value in deadline_values)
            ):
                raise ModelOutputError(
                    f"items[{index}] non-opportunity lifecycle is invalid"
                )
            if item["category"] == "机会" and lifecycle not in {
                "dated",
                "ongoing",
                "unspecified",
            }:
                raise ModelOutputError(
                    f"items[{index}] opportunity lifecycle is invalid"
                )
            if lifecycle == "dated":
                validate_iso_date(
                    item.get("deadline_date"),
                    f"items[{index}].deadline_date",
                )
                if not all(non_empty(value) for value in deadline_values[1:]):
                    raise ModelOutputError(
                        f"items[{index}] dated opportunity fields are required"
                    )
                if normalized_text(item["deadline_evidence"]) not in normalized_text(
                    candidate["content"]
                ):
                    raise ModelOutputError(
                        f"items[{index}].deadline_evidence is not in content"
                    )
            elif lifecycle == "ongoing":
                if (
                    item.get("deadline_date") is not None
                    or item.get("deadline_text") is not None
                    or not non_empty(item.get("deadline_evidence"))
                ):
                    raise ModelOutputError(
                        f"items[{index}] ongoing opportunity evidence is required"
                    )
                if normalized_text(item["deadline_evidence"]) not in normalized_text(
                    candidate["content"]
                ):
                    raise ModelOutputError(
                        f"items[{index}].deadline_evidence is not in content"
                    )
            elif any(value is not None for value in deadline_values):
                raise ModelOutputError(
                    f"items[{index}] deadline fields must be null"
                )
        return items
    except ContractError as exc:
        if isinstance(exc, ModelOutputError):
            raise
        raise ModelOutputError(str(exc)) from exc
