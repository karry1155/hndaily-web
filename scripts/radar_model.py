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
    require_exact_fields,
    validate_iso_date,
)

ENVELOPE_FIELDS = {
    "schema_version",
    "prompt_version",
    "input_fingerprint",
    "items",
}
MODEL_ITEM_FIELDS = {
    "candidate_id",
    "ai_summary",
    "category",
    *SCORE_FIELDS,
    "score_reasons",
    "opportunity_lifecycle",
    "deadline_date",
    "deadline_text",
    "deadline_evidence",
}
LIFECYCLES = {"dated", "ongoing", "unspecified", "not_applicable"}


class ModelOutputError(ContractError):
    pass


def build_model_input(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    items = [
        {
            "candidate_id": item["candidate_id"],
            "title": item["title"],
            "content": item["content"],
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


def _normalized(value: str) -> str:
    return "".join(value.split())


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
            if item.get("category") not in CATEGORIES:
                raise ModelOutputError(f"items[{index}].category is invalid")
            for field in SCORE_FIELDS:
                if type(item.get(field)) is not int or not 0 <= item[field] <= 10:
                    raise ModelOutputError(
                        f"items[{index}].{field} must be 0..10 integer"
                    )
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
                if _normalized(item["deadline_evidence"]) not in _normalized(
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
                if _normalized(item["deadline_evidence"]) not in _normalized(
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
