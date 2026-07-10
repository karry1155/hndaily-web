from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from scripts.radar_contract import SCORE_FIELDS, ContractError, non_empty

WEIGHTS = {
    "hainan_relevance": Decimal("0.30"),
    "actionability": Decimal("0.25"),
    "impact_scope": Decimal("0.20"),
    "timeliness": Decimal("0.15"),
    "information_density": Decimal("0.10"),
}


def score_semantic(item: dict[str, Any]) -> dict[str, Any]:
    reasons = item.get("score_reasons")
    if not isinstance(reasons, dict) or set(reasons) != set(SCORE_FIELDS):
        raise ContractError(
            "score_reasons must contain exactly the five score fields"
        )
    for field in SCORE_FIELDS:
        if type(item.get(field)) is not int or not 0 <= item[field] <= 10:
            raise ContractError(f"{field} must be a 0..10 integer")
        if not non_empty(reasons.get(field)):
            raise ContractError(f"score_reasons.{field} is required")
    weighted = sum(
        Decimal(item[field]) * WEIGHTS[field] for field in SCORE_FIELDS
    )
    score = float(
        (weighted * Decimal("10")).quantize(
            Decimal("0.1"), rounding=ROUND_HALF_UP
        )
    )
    return {
        "semantic_scores": {field: item[field] for field in SCORE_FIELDS},
        "score_reasons": {
            field: reasons[field].strip() for field in SCORE_FIELDS
        },
        "base_score": score,
        "final_score": score,
    }
