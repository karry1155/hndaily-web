from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from scripts.radar_contract import (
    PROMPT_VERSION, SCHEMA_VERSION, ContractError, non_empty, normalized_text,
    require_allowed_fields, require_exact_fields,
)
from scripts.radar_locations import find_location_candidates, load_location_catalog

ROOT = Path(__file__).resolve().parents[1]
TOPICS_PATH = ROOT / "config/topics.json"
ENVELOPE_FIELDS = {"schema_version", "prompt_version", "input_fingerprint", "items"}
MODEL_ITEM_FIELDS = {
    "candidate_id", "ai_summary", "scope", "scope_evidence", "subjects",
    "location_mentions", "topics", "events", "plans", "reader_leads",
}
SCOPES = {"hainan", "domestic", "mixed", "national", "foreign"}
SUBJECT_TYPES = {"person", "company", "organization"}
SUBJECT_ALIAS_CUES = ("以下简称", "简称", "下称", "又称", "俗称")
EVENT_TYPES = {"recurring_edition", "named_event", "incident"}
PLAN_MENTION_TYPES = {
    "proposed", "reviewed", "approved", "released", "implemented", "progress", "mentioned",
}
READER_INTENTS = {
    "apply", "register", "attend", "submit", "lookup", "use_service", "prepare", "avoid",
}
DATE_OR_RANGE_RE = re.compile(
    r"^[0-9]{4}(?:-[0-9]{2}(?:-[0-9]{2})?)?"
    r"(?:/[0-9]{4}(?:-[0-9]{2}(?:-[0-9]{2})?)?)?$"
)
WINDOW_DATE_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}(?::\d{2})?\+08:00)?$"
)


class ModelOutputError(ContractError):
    pass


def load_topic_categories(path: Path | None = None) -> list[dict[str, str]]:
    try:
        value = json.loads((path or TOPICS_PATH).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ModelOutputError(f"topic catalog cannot be read: {exc}") from exc
    require_exact_fields(value, {"schema_version", "categories"}, "topic catalog")
    if value["schema_version"] != 1 or not isinstance(value["categories"], list):
        raise ModelOutputError("topic catalog is invalid")
    seen: set[str] = set()
    rows = []
    for index, row in enumerate(value["categories"]):
        require_exact_fields(
            row, {"category_id", "name", "definition", "boundary"},
            f"topic catalog.categories[{index}]",
        )
        if not all(non_empty(row[field]) for field in row):
            raise ModelOutputError(f"topic catalog.categories[{index}] is invalid")
        if row["category_id"] in seen:
            raise ModelOutputError("topic catalog contains duplicate category_id")
        seen.add(row["category_id"])
        rows.append({key: row[key].strip() for key in row})
    return rows


def build_model_input(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    locations = load_location_catalog()
    topic_categories = load_topic_categories()
    items = [
        {
            "candidate_id": item["candidate_id"],
            "item_id": item["item_id"],
            "published_date": item["published_date"],
            "title": item["title"],
            "content": item["content"],
            "location_candidates": find_location_candidates(
                item["title"], item["content"], locations
            ),
        }
        for item in candidates
    ]
    payload = {
        "schema_version": SCHEMA_VERSION,
        "prompt_version": PROMPT_VERSION,
        "topic_categories": topic_categories,
        "items": items,
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {
        **payload,
        "input_fingerprint": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    }


def _string(value: Any, limit: int, location: str) -> str:
    if not non_empty(value) or len(value) > limit:
        raise ModelOutputError(f"{location} is invalid")
    return value.strip()


def _evidence(value: Any, source_text: str, location: str) -> str:
    result = _string(value, 1200, location)
    if normalized_text(result) not in source_text:
        raise ModelOutputError(f"{location} is not a verbatim source excerpt")
    return result


def _optional_string(value: Any, limit: int, location: str) -> None:
    if value is not None:
        _string(value, limit, location)


def validate_model_output(
    model_input: dict[str, Any], model_output: dict[str, Any], candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    require_exact_fields(model_output, ENVELOPE_FIELDS, "model output")
    for field in ("schema_version", "prompt_version", "input_fingerprint"):
        if model_output.get(field) != model_input.get(field):
            raise ModelOutputError(f"model output {field} mismatch")
    items = model_output.get("items")
    if not isinstance(items, list) or len(items) != len(candidates):
        raise ModelOutputError("model output items do not align with input")
    if [row.get("candidate_id") for row in items if isinstance(row, dict)] != [
        row["candidate_id"] for row in candidates
    ]:
        raise ModelOutputError("candidate_id order mismatch")

    category_ids = {row["category_id"] for row in model_input.get("topic_categories", [])}
    if not category_ids:
        raise ModelOutputError("model input topic_categories is invalid")

    for item_index, (item, candidate, input_item) in enumerate(
        zip(items, candidates, model_input["items"])
    ):
        prefix = f"items[{item_index}]"
        require_exact_fields(item, MODEL_ITEM_FIELDS, prefix)
        source_text = normalized_text(str(candidate["title"]) + str(candidate["content"]))
        summary = item.get("ai_summary")
        if summary is not None:
            _string(summary, 300, f"{prefix}.ai_summary")
        if item.get("scope") not in SCOPES:
            raise ModelOutputError(f"{prefix}.scope is invalid")
        _evidence(item.get("scope_evidence"), source_text, f"{prefix}.scope_evidence")

        subjects = item.get("subjects")
        if not isinstance(subjects, list) or len(subjects) > 24:
            raise ModelOutputError(f"{prefix}.subjects is invalid")
        seen_surfaces: set[str] = set()
        for subject_index, subject in enumerate(subjects):
            where = f"{prefix}.subjects[{subject_index}]"
            require_allowed_fields(
                subject, {"name", "type", "activities"}, {"role", "aliases"}, where
            )
            name = _string(subject.get("name"), 100, f"{where}.name")
            if normalized_text(name) not in source_text:
                raise ModelOutputError(f"{where}.name is not in source")
            key = normalized_text(name).casefold()
            if key in seen_surfaces:
                raise ModelOutputError(f"{where}.name is duplicated")
            seen_surfaces.add(key)
            if subject.get("type") not in SUBJECT_TYPES:
                raise ModelOutputError(f"{where}.type is invalid")
            _optional_string(subject.get("role"), 120, f"{where}.role")
            aliases = subject.get("aliases", [])
            if not isinstance(aliases, list) or not aliases or len(aliases) > 6:
                if "aliases" in subject:
                    raise ModelOutputError(f"{where}.aliases is invalid")
                aliases = []
            for alias_index, alias in enumerate(aliases):
                alias_where = f"{where}.aliases[{alias_index}]"
                require_exact_fields(alias, {"name", "evidence"}, alias_where)
                alias_name = _string(alias.get("name"), 40, f"{alias_where}.name")
                if normalized_text(alias_name) not in source_text:
                    raise ModelOutputError(f"{alias_where}.name is not in source")
                alias_key = normalized_text(alias_name).casefold()
                if alias_key in seen_surfaces:
                    raise ModelOutputError(f"{alias_where}.name is duplicated")
                declaration = _evidence(
                    alias.get("evidence"), source_text, f"{alias_where}.evidence"
                )
                normalized_declaration = normalized_text(declaration)
                if (
                    normalized_text(name) not in normalized_declaration
                    or normalized_text(alias_name) not in normalized_declaration
                    or not any(cue in normalized_declaration for cue in SUBJECT_ALIAS_CUES)
                ):
                    raise ModelOutputError(f"{alias_where}.evidence is not an explicit alias declaration")
                seen_surfaces.add(alias_key)

            activities = subject.get("activities")
            if not isinstance(activities, list) or not activities or len(activities) > 8:
                raise ModelOutputError(f"{where}.activities is invalid")
            for activity_index, activity in enumerate(activities):
                activity_where = f"{where}.activities[{activity_index}]"
                require_allowed_fields(
                    activity, {"headline", "evidence"},
                    {"occurred_on", "place", "detail_kind", "detail"}, activity_where,
                )
                headline = _string(activity.get("headline"), 80, f"{activity_where}.headline")
                if name not in headline and not any(alias["name"] in headline for alias in aliases):
                    raise ModelOutputError(f"{activity_where}.headline must name its subject")
                if "occurred_on" in activity and not DATE_OR_RANGE_RE.fullmatch(activity["occurred_on"]):
                    raise ModelOutputError(f"{activity_where}.occurred_on is invalid")
                _optional_string(activity.get("place"), 40, f"{activity_where}.place")
                detail_kind, detail = activity.get("detail_kind"), activity.get("detail")
                if (detail_kind is None) != (detail is None):
                    raise ModelOutputError(f"{activity_where}.detail fields must appear together")
                if detail_kind is not None:
                    if detail_kind not in {"goal", "result", "object"}:
                        raise ModelOutputError(f"{activity_where}.detail_kind is invalid")
                    _string(detail, 160, f"{activity_where}.detail")
                _evidence(activity.get("evidence"), source_text, f"{activity_where}.evidence")

        allowed_locations = {row["location_id"] for row in input_item["location_candidates"]}
        mentions = item.get("location_mentions")
        if not isinstance(mentions, list) or len(mentions) > 12:
            raise ModelOutputError(f"{prefix}.location_mentions is invalid")
        seen_locations: set[str] = set()
        for mention_index, mention in enumerate(mentions):
            where = f"{prefix}.location_mentions[{mention_index}]"
            require_exact_fields(mention, {"location_id", "evidence"}, where)
            location_id = mention.get("location_id")
            if location_id not in allowed_locations or location_id in seen_locations:
                raise ModelOutputError(f"{where}.location_id is invalid or duplicated")
            seen_locations.add(location_id)
            _evidence(mention.get("evidence"), source_text, f"{where}.evidence")

        topics = item.get("topics")
        require_exact_fields(topics, {"primary", "secondary"}, f"{prefix}.topics")
        primary = topics.get("primary")
        require_exact_fields(primary, {"category_id", "evidence"}, f"{prefix}.topics.primary")
        if primary.get("category_id") not in category_ids:
            raise ModelOutputError(f"{prefix}.topics.primary.category_id is invalid")
        _evidence(primary.get("evidence"), source_text, f"{prefix}.topics.primary.evidence")
        secondary = topics.get("secondary")
        if not isinstance(secondary, list) or len(secondary) > 3:
            raise ModelOutputError(f"{prefix}.topics.secondary is invalid")
        seen_topics: set[str] = set()
        for topic_index, topic in enumerate(secondary):
            where = f"{prefix}.topics.secondary[{topic_index}]"
            require_exact_fields(topic, {"name", "evidence"}, where)
            name = _string(topic.get("name"), 20, f"{where}.name")
            if len(name) < 2 or normalized_text(name).casefold() in seen_topics:
                raise ModelOutputError(f"{where}.name is invalid or duplicated")
            seen_topics.add(normalized_text(name).casefold())
            _evidence(topic.get("evidence"), source_text, f"{where}.evidence")

        events = item.get("events")
        if not isinstance(events, list) or len(events) > 8:
            raise ModelOutputError(f"{prefix}.events is invalid")
        seen_events: set[str] = set()
        for event_index, event in enumerate(events):
            where = f"{prefix}.events[{event_index}]"
            require_allowed_fields(
                event, {"name", "event_type", "evidence"}, {"series_name", "occurred_on"}, where
            )
            name = _string(event.get("name"), 160, f"{where}.name")
            if normalized_text(name) not in source_text or normalized_text(name) in seen_events:
                raise ModelOutputError(f"{where}.name is invalid or duplicated")
            seen_events.add(normalized_text(name))
            if event.get("event_type") not in EVENT_TYPES:
                raise ModelOutputError(f"{where}.event_type is invalid")
            series_name = event.get("series_name")
            if event["event_type"] == "recurring_edition":
                _string(series_name, 140, f"{where}.series_name")
            elif series_name is not None:
                raise ModelOutputError(f"{where}.series_name is only valid for recurring_edition")
            if "occurred_on" in event and not DATE_OR_RANGE_RE.fullmatch(event["occurred_on"]):
                raise ModelOutputError(f"{where}.occurred_on is invalid")
            _evidence(event.get("evidence"), source_text, f"{where}.evidence")

        plans = item.get("plans")
        if not isinstance(plans, list) or len(plans) > 8:
            raise ModelOutputError(f"{prefix}.plans is invalid")
        seen_plans: set[str] = set()
        for plan_index, plan in enumerate(plans):
            where = f"{prefix}.plans[{plan_index}]"
            require_exact_fields(plan, {"name", "mention_type", "evidence"}, where)
            name = _string(plan.get("name"), 200, f"{where}.name")
            if not (name.startswith("《") and name.endswith("》")):
                raise ModelOutputError(f"{where}.name must use Chinese book-title marks")
            if normalized_text(name) not in source_text or normalized_text(name) in seen_plans:
                raise ModelOutputError(f"{where}.name is invalid or duplicated")
            seen_plans.add(normalized_text(name))
            if plan.get("mention_type") not in PLAN_MENTION_TYPES:
                raise ModelOutputError(f"{where}.mention_type is invalid")
            _evidence(plan.get("evidence"), source_text, f"{where}.evidence")

        leads = item.get("reader_leads")
        if not isinstance(leads, list) or len(leads) > 3:
            raise ModelOutputError(f"{prefix}.reader_leads is invalid")
        for lead_index, lead in enumerate(leads):
            where = f"{prefix}.reader_leads[{lead_index}]"
            require_allowed_fields(
                lead, {"intent", "headline", "action", "evidence"},
                {"audience", "window", "channel"}, where,
            )
            if lead.get("intent") not in READER_INTENTS:
                raise ModelOutputError(f"{where}.intent is invalid")
            _string(lead.get("headline"), 60, f"{where}.headline")
            _string(lead.get("action"), 240, f"{where}.action")
            _optional_string(lead.get("audience"), 120, f"{where}.audience")
            _optional_string(lead.get("channel"), 160, f"{where}.channel")
            evidence = _evidence(lead.get("evidence"), source_text, f"{where}.evidence")
            window = lead.get("window")
            if window is not None:
                require_allowed_fields(window, {"text"}, {"start", "end"}, f"{where}.window")
                text = _string(window.get("text"), 100, f"{where}.window.text")
                if normalized_text(text) not in normalized_text(evidence):
                    raise ModelOutputError(f"{where}.window.text must be in lead evidence")
                for field in ("start", "end"):
                    if field in window and not WINDOW_DATE_RE.fullmatch(window[field]):
                        raise ModelOutputError(f"{where}.window.{field} is invalid")
    return items
