from __future__ import annotations

import hashlib
import json
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

ENVELOPE_FIELDS = {"schema_version", "prompt_version", "input_fingerprint", "items"}
MODEL_ITEM_FIELDS = {
    "candidate_id", "ai_summary", "scope", "scope_evidence", "subjects",
    "location_mentions", "topic_profile", "content_form", "events", "plans",
}
SUBJECT_TYPES = {"person", "government", "organization", "company", "project"}
SCOPES = {"national", "hainan", "domestic", "mixed", "foreign"}
CONTENT_FORMS = {
    "news", "photo-news", "feature", "profile", "analysis", "commentary",
    "essay", "explainer", "interview", "book-review", "book-list",
    "film-review",
}
SUBJECT_BASE_FIELDS = {"name", "type", "role", "evidence"}
SUBJECT_ALIAS_FIELDS = {"name", "evidence"}
SUBJECT_ALIAS_CUES = ("以下简称", "简称", "下称", "又称", "俗称")
TOPIC_PROFILE_FIELDS = {"primary", "secondary"}
OPEN_TOPIC_FIELDS = {"name", "evidence"}


class ModelOutputError(ContractError):
    pass


def build_model_input(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    locations = load_location_catalog()
    items = [
        {
            "candidate_id": item["candidate_id"],
            "title": item["title"],
            "content": item["content"],
            "location_candidates": find_location_candidates(item["title"], item["content"], locations),
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
            if not isinstance(subjects, list) or len(subjects) > 24:
                raise ModelOutputError(f"{location}.subjects is invalid")
            seen_subject_surfaces: set[str] = set()
            for subject in subjects:
                subject_fields = set(subject) if isinstance(subject, dict) else set()
                if subject_fields not in (SUBJECT_BASE_FIELDS, SUBJECT_BASE_FIELDS | {"aliases"}):
                    raise ModelOutputError(f"{location}.subject fields are invalid")
                if not non_empty(subject.get("name")) or len(subject["name"]) > 80:
                    raise ModelOutputError(f"{location}.subject.name is invalid")
                if normalized_text(subject["name"]) not in source_text:
                    raise ModelOutputError(f"{location}.subject.name is not in source")
                canonical_key = normalized_text(subject["name"]).casefold()
                if canonical_key in seen_subject_surfaces:
                    raise ModelOutputError(f"{location}.subject.name is duplicated")
                seen_subject_surfaces.add(canonical_key)
                if subject.get("type") not in SUBJECT_TYPES:
                    raise ModelOutputError(f"{location}.subject.type is invalid")
                if subject.get("role") is not None and (
                    not non_empty(subject["role"]) or len(subject["role"]) > 80
                ):
                    raise ModelOutputError(f"{location}.subject.role is invalid")
                _evidence(subject.get("evidence"), source_text, f"{location}.subject.evidence")
                aliases = subject.get("aliases", [])
                if not isinstance(aliases, list) or not aliases or len(aliases) > 6:
                    if "aliases" in subject:
                        raise ModelOutputError(f"{location}.subject.aliases is invalid")
                for alias in aliases:
                    require_exact_fields(alias, SUBJECT_ALIAS_FIELDS, f"{location}.subject.alias")
                    alias_name = alias.get("name")
                    if not non_empty(alias_name) or len(alias_name) > 40:
                        raise ModelOutputError(f"{location}.subject.alias.name is invalid")
                    alias_key = normalized_text(alias_name).casefold()
                    if alias_key in seen_subject_surfaces:
                        raise ModelOutputError(f"{location}.subject.alias.name is duplicated")
                    if normalized_text(alias_name) not in source_text:
                        raise ModelOutputError(f"{location}.subject.alias.name is not in source")
                    alias_evidence = _evidence(
                        alias.get("evidence"), source_text, f"{location}.subject.alias.evidence"
                    )
                    normalized_evidence = normalized_text(alias_evidence)
                    if (
                        normalized_text(subject["name"]) not in normalized_evidence
                        or normalized_text(alias_name) not in normalized_evidence
                        or not any(cue in normalized_evidence for cue in SUBJECT_ALIAS_CUES)
                    ):
                        raise ModelOutputError(
                            f"{location}.subject.alias.evidence is not an explicit declaration"
                        )
                    seen_subject_surfaces.add(alias_key)

            allowed_locations = {row["location_id"] for row in input_item["location_candidates"]}
            mentions = item.get("location_mentions")
            if not isinstance(mentions, list) or len(mentions) > 12:
                raise ModelOutputError(f"{location}.location_mentions is invalid")
            for mention in mentions:
                require_exact_fields(mention, {"location_id", "evidence"}, f"{location}.location")
                if mention.get("location_id") not in allowed_locations:
                    raise ModelOutputError(f"{location}.location_id is outside candidates")
                _evidence(mention.get("evidence"), source_text, f"{location}.location.evidence")

            topic_profile = item.get("topic_profile")
            if not isinstance(topic_profile, dict):
                raise ModelOutputError(f"{location}.topic_profile is invalid")
            require_exact_fields(topic_profile, TOPIC_PROFILE_FIELDS, f"{location}.topic_profile")
            primary = topic_profile.get("primary")
            if not isinstance(primary, dict):
                raise ModelOutputError(f"{location}.topic_profile.primary is invalid")
            require_exact_fields(primary, OPEN_TOPIC_FIELDS, f"{location}.topic_profile.primary")
            if not non_empty(primary.get("name")) or len(primary["name"]) > 40:
                raise ModelOutputError(f"{location}.topic_profile.primary.name is invalid")
            _evidence(
                primary.get("evidence"), source_text,
                f"{location}.topic_profile.primary.evidence",
            )
            secondary = topic_profile.get("secondary")
            if not isinstance(secondary, list) or len(secondary) > 3:
                raise ModelOutputError(f"{location}.topic_profile.secondary is invalid")
            seen_topics = {normalized_text(primary["name"]).casefold()}
            for topic_index, topic in enumerate(secondary):
                topic_location = f"{location}.topic_profile.secondary[{topic_index}]"
                require_exact_fields(topic, OPEN_TOPIC_FIELDS, topic_location)
                if not non_empty(topic.get("name")) or len(topic["name"]) > 40:
                    raise ModelOutputError(f"{topic_location}.name is invalid")
                topic_key = normalized_text(topic["name"]).casefold()
                if topic_key in seen_topics:
                    raise ModelOutputError(f"{topic_location}.name is duplicated")
                seen_topics.add(topic_key)
                _evidence(topic.get("evidence"), source_text, f"{topic_location}.evidence")
            if item.get("content_form") not in CONTENT_FORMS:
                raise ModelOutputError(f"{location}.content_form is invalid")

            events = item.get("events")
            if not isinstance(events, list) or len(events) > 8:
                raise ModelOutputError(f"{location}.events is invalid")
            for event in events:
                require_exact_fields(event, {"name", "evidence"}, f"{location}.event")
                if not non_empty(event.get("name")) or len(event["name"]) > 140:
                    raise ModelOutputError(f"{location}.event.name is invalid")
                _evidence(event.get("evidence"), source_text, f"{location}.event.evidence")

            plans = item.get("plans")
            if not isinstance(plans, list) or len(plans) > 8:
                raise ModelOutputError(f"{location}.plans is invalid")
            for plan in plans:
                require_exact_fields(plan, {"name", "evidence"}, f"{location}.plan")
                name = plan.get("name")
                if (
                    not non_empty(name)
                    or len(name) > 180
                    or not name.startswith("《")
                    or not name.endswith("》")
                    or normalized_text(name) not in source_text
                ):
                    raise ModelOutputError(f"{location}.plan.name is invalid")
                _evidence(plan.get("evidence"), source_text, f"{location}.plan.evidence")
        return items
    except ContractError as exc:
        if isinstance(exc, ModelOutputError):
            raise
        raise ModelOutputError(str(exc)) from exc
