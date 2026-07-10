from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any


SCORE_FIELDS = (
    "hainan_relevance",
    "actionability",
    "impact_scope",
    "novelty",
    "information_density",
)
SCORE_WEIGHTS = {
    "hainan_relevance": Decimal("0.30"),
    "actionability": Decimal("0.25"),
    "impact_scope": Decimal("0.20"),
    "novelty": Decimal("0.15"),
    "information_density": Decimal("0.10"),
}
FRONT_PAGE_BONUS = 4
LOCAL_NEWS_BONUS = 3
LENGTH_ADJUSTMENTS = {"under_200": -8, "200_to_399": -4, "400_plus": 0}
HAINAN_MARKERS = (
    "海南", "琼", "海口", "三亚", "儋州", "洋浦", "文昌", "琼海", "万宁", "陵水",
    "保亭", "五指山", "东方", "昌江", "乐东", "澄迈", "临高", "定安", "屯昌", "白沙",
)

if sum(SCORE_WEIGHTS.values(), Decimal("0")) != Decimal("1.00"):
    raise RuntimeError("semantic score weights must total 1.00")


class ScoringError(ValueError):
    pass


def _non_empty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_semantic_item(item: dict[str, Any], location: str) -> None:
    for field in SCORE_FIELDS:
        value = item.get(field)
        if type(value) is not int or not 0 <= value <= 10:
            raise ScoringError(f"{location}.{field} must be an integer from 0 to 10")
    reasons = item.get("score_reasons")
    if not isinstance(reasons, dict) or set(reasons) != set(SCORE_FIELDS):
        raise ScoringError(f"{location}.score_reasons must contain exactly the five score fields")
    for field in SCORE_FIELDS:
        if not _non_empty(reasons.get(field)):
            raise ScoringError(f"{location}.score_reasons.{field} must be a non-empty string")


def _one_decimal(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def _is_national_reprint_without_hainan_link(candidate: dict[str, Any]) -> bool:
    author = str(candidate.get("author", ""))
    page_name = str(candidate.get("page_name", ""))
    is_reprint = "新华社" in author or page_name.startswith("中国新闻")
    text = f"{candidate.get('original_title', '')}\n{candidate.get('content', '')}"
    return is_reprint and not any(marker in text for marker in HAINAN_MARKERS)


def score_candidate(candidate: dict[str, Any], semantic: dict[str, Any]) -> dict[str, Any]:
    validate_semantic_item(semantic, f"semantic {candidate.get('candidate_id', '')}")
    weighted = sum(
        Decimal(semantic[field]) * SCORE_WEIGHTS[field]
        for field in SCORE_FIELDS
    )
    base_score = _one_decimal(weighted * Decimal("10"))
    national_reprint = _is_national_reprint_without_hainan_link(candidate)
    adjustments: list[dict[str, Any]] = []

    if candidate.get("page") == "001" and not national_reprint:
        adjustments.append({"rule": "front_page", "points": FRONT_PAGE_BONUS, "reason": "头版文章"})
    if str(candidate.get("page_name", "")).startswith("本省新闻") and not national_reprint:
        adjustments.append({"rule": "local_news_page", "points": LOCAL_NEWS_BONUS, "reason": "海南本地新闻版"})
    length_points = LENGTH_ADJUSTMENTS.get(str(candidate.get("length_band")))
    if length_points is None:
        raise ScoringError(f"unknown length_band: {candidate.get('length_band')}")
    if length_points:
        adjustments.append({
            "rule": "short_content",
            "points": length_points,
            "reason": f"正文 {candidate.get('content_length', 0)} 字",
        })

    final_decimal = Decimal(str(base_score)) + sum(
        (Decimal(item["points"]) for item in adjustments), Decimal("0")
    )
    final_score = _one_decimal(max(Decimal("0"), min(Decimal("100"), final_decimal)))
    parts = [f"基础语义分 {base_score:.1f}"]
    parts.extend(
        f"{'+' if item['points'] > 0 else ''}{item['points']} {item['reason']}"
        for item in adjustments
    )
    parts.append(f"= 最终分 {final_score:.1f}")

    return {
        "semantic_scores": {field: semantic[field] for field in SCORE_FIELDS},
        "score_reasons": {field: semantic["score_reasons"][field].strip() for field in SCORE_FIELDS},
        "base_score": base_score,
        "adjustments": adjustments,
        "final_score": final_score,
        "score_explanation": "；".join(parts),
        "national_reprint_without_hainan_link": national_reprint,
    }
