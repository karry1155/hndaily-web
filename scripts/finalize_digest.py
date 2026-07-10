#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.editorial_filter import evaluate_issue
from scripts.event_clustering import cluster_candidates
from scripts.editorial_scoring import SCORE_FIELDS, ScoringError, score_candidate, validate_semantic_item
from scripts.prepare_model_input import build_model_input
from scripts.select_digest import (
    FINAL_SCORE_THRESHOLD,
    HAINAN_RELEVANCE_THRESHOLD,
    TOP_COUNT,
    select_events,
)
from scripts.validate_digest import CATEGORIES, validate_daily


MODEL_ENVELOPE_FIELDS = {"schema_version", "prompt_version", "input_fingerprint", "items"}
MODEL_ITEM_FIELDS = {
    "candidate_id",
    "title",
    "summary",
    "why_it_matters",
    "key_facts",
    "confidence",
    "suggested_category",
    "hainan_relevance",
    "actionability",
    "impact_scope",
    "novelty",
    "information_density",
    "score_reasons",
}
MODEL_CONFIDENCE = {"full_text", "short_item", "partial"}


class ModelOutputError(ValueError):
    pass


def _non_empty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _require_exact_fields(value: dict[str, Any], expected: set[str], location: str) -> None:
    unknown = sorted(set(value) - expected)
    missing = sorted(expected - set(value))
    if unknown:
        raise ModelOutputError(f"{location} has unknown fields: {', '.join(unknown)}")
    if missing:
        raise ModelOutputError(f"{location} is missing fields: {', '.join(missing)}")


def _validate_model_output(model_input: dict[str, Any], model_output: dict[str, Any]) -> list[dict[str, Any]]:
    _require_exact_fields(model_output, MODEL_ENVELOPE_FIELDS, "model output")
    for field in ("schema_version", "prompt_version", "input_fingerprint"):
        if model_output.get(field) != model_input.get(field):
            raise ModelOutputError(f"model output {field} does not match model input")

    items = model_output.get("items")
    if not isinstance(items, list):
        raise ModelOutputError("model output items must be an array")
    expected_ids = [item["candidate_id"] for item in model_input["items"]]
    actual_ids = [item.get("candidate_id") if isinstance(item, dict) else None for item in items]
    if actual_ids != expected_ids:
        raise ModelOutputError(f"candidate_id order must be exactly {expected_ids}; got {actual_ids}")

    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ModelOutputError(f"items[{index}] must be an object")
        _require_exact_fields(item, MODEL_ITEM_FIELDS, f"items[{index}]")
        for field in ("candidate_id", "title", "summary", "why_it_matters"):
            if not _non_empty(item.get(field)):
                raise ModelOutputError(f"items[{index}].{field} must be a non-empty string")
        facts = item.get("key_facts")
        if not isinstance(facts, list) or not facts or not all(_non_empty(fact) for fact in facts):
            raise ModelOutputError(f"items[{index}].key_facts must contain non-empty strings")
        if item.get("confidence") not in MODEL_CONFIDENCE:
            raise ModelOutputError(f"items[{index}].confidence is invalid")
        if item.get("suggested_category") not in set(CATEGORIES) - {"已跳过"}:
            raise ModelOutputError(f"items[{index}].suggested_category is invalid")
        try:
            validate_semantic_item(item, f"items[{index}]")
        except ScoringError as exc:
            raise ModelOutputError(str(exc)) from exc
    return items


def build_digest(
    raw: dict[str, Any],
    model_input: dict[str, Any],
    model_output: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    expected_input, prefilter = build_model_input(raw)
    if model_input != expected_input:
        raise ModelOutputError("model input does not match filtered candidates in raw JSON")
    semantic_items = _validate_model_output(model_input, model_output)
    records = evaluate_issue(raw)
    passed = [record for record in records if record["passed"]]
    scored_candidates: list[dict[str, Any]] = []
    for semantic, article in zip(semantic_items, passed):
        scoring = score_candidate(article, semantic)
        candidate = dict(article)
        candidate.update(
            {
                "title": semantic["title"].strip(),
                "summary": semantic["summary"].strip(),
                "why_it_matters": semantic["why_it_matters"].strip(),
                "key_facts": [fact.strip() for fact in semantic["key_facts"]],
                "confidence": semantic["confidence"],
                "category": semantic["suggested_category"],
                **scoring,
            }
        )
        scored_candidates.append(candidate)

    events = cluster_candidates(scored_candidates)
    selected_events, event_decisions = select_events(events)

    def publish_item(event: dict[str, Any]) -> dict[str, Any]:
        return {
            "rank": event["rank"],
            "title": event["title"],
            "summary": event["summary"],
            "category": event["category"],
            "why_it_matters": event["why_it_matters"],
            "key_facts": event["key_facts"],
            "sources": event["sources"],
            "confidence": event["confidence"],
            "event_id": event["event_id"],
            "master_candidate_id": event["master_candidate_id"],
            "semantic_scores": event["semantic_scores"],
            "score_reasons": event["score_reasons"],
            "base_score": event["base_score"],
            "adjustments": event["adjustments"],
            "final_score": event["final_score"],
            "score_explanation": event["score_explanation"],
        }

    published = [publish_item(event) for event in selected_events]
    categories: dict[str, list[dict[str, Any]]] = {category: [] for category in CATEGORIES}
    for item in published:
        categories[item["category"]].append(
            {
                "title": item["title"],
                "summary": item["summary"],
                "sources": item["sources"],
                "event_id": item["event_id"],
                "final_score": item["final_score"],
            }
        )
    for record in records:
        if not record["passed"]:
            categories["已跳过"].append(
                {
                    "title": record["original_title"],
                    "summary": "由确定性预过滤排除。",
                    "sources": [{
                        "headline": record["original_title"],
                        "page": record["page"],
                        "url": record["url"],
                    }],
                    "skip_reason": record["skip_reason"],
                    "candidate_id": record["candidate_id"],
                }
            )

    digest = {
        "type": "daily",
        "date": raw.get("date"),
        "source": raw.get("source"),
        "page_count": raw.get("page_count"),
        "article_count": raw.get("article_count"),
        "reading_minutes": 5,
        "input_fingerprint": model_input["input_fingerprint"],
        "prompt_version": model_input["prompt_version"],
        "selected_count": len(published),
        "selection_threshold": FINAL_SCORE_THRESHOLD,
        "hainan_relevance_threshold": HAINAN_RELEVANCE_THRESHOLD,
        "ranking_version": "editorial-v1",
        "top_items": published[:TOP_COUNT],
        "more_items": published[TOP_COUNT:],
        "categories": categories,
        "generated_at": datetime.now().astimezone().replace(microsecond=0).isoformat(),
    }
    errors = validate_daily(digest)
    if errors:
        raise ModelOutputError("invalid finalized digest: " + "; ".join(errors))

    event_by_member = {
        candidate_id: event
        for event in event_decisions
        for candidate_id in event["member_candidate_ids"]
    }
    scored_by_id = {candidate["candidate_id"]: candidate for candidate in scored_candidates}
    audit_articles: list[dict[str, Any]] = []
    for record in records:
        audit_item = dict(record)
        if record["passed"]:
            scored = scored_by_id[record["candidate_id"]]
            event = event_by_member[record["candidate_id"]]
            audit_item.update({
                "semantic_scores": scored["semantic_scores"],
                "score_reasons": scored["score_reasons"],
                "base_score": scored["base_score"],
                "adjustments": scored["adjustments"],
                "final_score": scored["final_score"],
                "category": scored["category"],
                "event_id": event["event_id"],
                "master_candidate_id": event["master_candidate_id"],
                "selected": bool(event.get("selected")) and record["candidate_id"] == event["master_candidate_id"],
                "unselected_reason": (
                    "duplicate_event"
                    if record["candidate_id"] != event["master_candidate_id"]
                    else event.get("unselected_reason")
                ),
                "rank": event.get("rank") if record["candidate_id"] == event["master_candidate_id"] else None,
            })
        else:
            audit_item.update(selected=False, unselected_reason=record["skip_reason"], rank=None)
        audit_articles.append(audit_item)

    audit = {
        "schema_version": 2,
        "date": raw.get("date"),
        "article_count": raw.get("article_count"),
        "input_fingerprint": model_input["input_fingerprint"],
        "prompt_version": model_input["prompt_version"],
        "prefilter": prefilter,
        "articles": audit_articles,
        "events": event_decisions,
    }
    return digest, audit


def finalize_to_path(
    raw: dict[str, Any],
    model_input: dict[str, Any],
    model_output: dict[str, Any],
    output_path: Path,
    audit_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    digest, audit = build_digest(raw, model_input, model_output)
    for path in (output_path, audit_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    audit_temporary = audit_path.with_name(f".{audit_path.name}.tmp")
    output_temporary = output_path.with_name(f".{output_path.name}.tmp")
    audit_temporary.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output_temporary.write_text(json.dumps(digest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    audit_temporary.replace(audit_path)
    output_temporary.replace(output_path)
    return digest, audit


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ModelOutputError(f"{path} must contain a JSON object")
    return value


def main(argv: list[str]) -> int:
    if len(argv) != 6:
        print(
            "Usage: finalize_digest.py RAW_JSON MODEL_INPUT_JSON MODEL_OUTPUT_JSON OUTPUT_JSON AUDIT_JSON",
            file=sys.stderr,
        )
        return 1
    try:
        raw, model_input, model_output = (_read_object(Path(value)) for value in argv[1:4])
        finalize_to_path(raw, model_input, model_output, Path(argv[4]), Path(argv[5]))
    except (OSError, json.JSONDecodeError, ModelOutputError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(str(Path(argv[4]).resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
