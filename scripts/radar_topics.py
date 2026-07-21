from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from scripts.radar_contract import ContractError, non_empty, normalized_text, require_exact_fields

ROOT = Path(__file__).resolve().parents[1]
CATALOG_FIELDS = {"schema_version", "topics"}
TOPIC_NODE_FIELDS = {
    "topic_id", "name", "aliases", "parent_id", "definition", "include",
    "exclude", "status",
}
RESOLUTION_INPUT_FIELDS = {
    "schema_version", "article_schema_version", "catalog_fingerprint",
    "input_fingerprint", "catalog_topics", "topics",
}
RESOLUTION_INPUT_TOPIC_FIELDS = {"name", "occurrences", "exact_matches"}
OCCURRENCE_FIELDS = {"candidate_id", "relation", "evidence"}
RESOLUTION_OUTPUT_FIELDS = {"schema_version", "input_fingerprint", "items"}
EXISTING_RESOLUTION_FIELDS = {"source_name", "decision", "topic_id"}
NEW_RESOLUTION_FIELDS = {
    "source_name", "decision", "topic_id", "name", "parent_id", "aliases",
    "definition", "include", "exclude",
}
TOPIC_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
TOPIC_RELATIONS = {"primary", "secondary"}


class TopicResolutionError(ContractError):
    pass


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def validate_topic_catalog(catalog: dict[str, Any]) -> dict[str, Any]:
    require_exact_fields(catalog, CATALOG_FIELDS, "topic catalog")
    if catalog.get("schema_version") != 1 or not isinstance(catalog.get("topics"), list):
        raise TopicResolutionError("topic catalog envelope is invalid")
    by_id: dict[str, dict[str, Any]] = {}
    surfaces: dict[str, str] = {}
    for index, topic in enumerate(catalog["topics"]):
        location = f"topic catalog.topics[{index}]"
        if not isinstance(topic, dict):
            raise TopicResolutionError(f"{location} is invalid")
        require_exact_fields(topic, TOPIC_NODE_FIELDS, location)
        topic_id = topic.get("topic_id")
        if not non_empty(topic_id) or not TOPIC_ID_RE.fullmatch(topic_id):
            raise TopicResolutionError(f"{location}.topic_id is invalid")
        if topic_id in by_id:
            raise TopicResolutionError(f"{location}.topic_id is duplicated")
        if not non_empty(topic.get("name")) or len(topic["name"]) > 40:
            raise TopicResolutionError(f"{location}.name is invalid")
        if topic.get("parent_id") is not None and not non_empty(topic["parent_id"]):
            raise TopicResolutionError(f"{location}.parent_id is invalid")
        if topic.get("status") not in {"active", "retired"}:
            raise TopicResolutionError(f"{location}.status is invalid")
        for field in ("aliases", "include", "exclude"):
            values = topic.get(field)
            if not isinstance(values, list) or not all(non_empty(value) for value in values):
                raise TopicResolutionError(f"{location}.{field} is invalid")
        if not non_empty(topic.get("definition")):
            raise TopicResolutionError(f"{location}.definition is invalid")
        for surface in [topic["name"], *topic["aliases"]]:
            key = normalized_text(surface).casefold()
            previous = surfaces.get(key)
            if previous is not None and previous != topic_id:
                raise TopicResolutionError(f"topic surface {surface!r} maps to multiple IDs")
            surfaces[key] = topic_id
        by_id[topic_id] = topic
    for topic in catalog["topics"]:
        parent_id = topic["parent_id"]
        if parent_id is not None and parent_id not in by_id:
            raise TopicResolutionError(f"topic {topic['topic_id']} has unknown parent")
        seen = {topic["topic_id"]}
        cursor = parent_id
        while cursor is not None:
            if cursor in seen:
                raise TopicResolutionError(f"topic {topic['topic_id']} has a parent cycle")
            seen.add(cursor)
            cursor = by_id[cursor]["parent_id"]
    return catalog


def load_topic_catalog(content_root: Path | None = None) -> dict[str, Any]:
    candidates = []
    if content_root is not None:
        candidates.append(Path(content_root) / "topics" / "catalog.json")
    candidates.append(ROOT / "config" / "topic-catalog.json")
    for path in candidates:
        if path.is_file():
            return validate_topic_catalog(json.loads(path.read_text(encoding="utf-8")))
    raise TopicResolutionError("topic catalog is missing")


def topic_catalog_by_id(catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    validate_topic_catalog(catalog)
    return {row["topic_id"]: row for row in catalog["topics"]}


def topic_surface_map(catalog: dict[str, Any]) -> dict[str, str]:
    result = {}
    for row in validate_topic_catalog(catalog)["topics"]:
        for surface in [row["name"], *row["aliases"]]:
            result[normalized_text(surface).casefold()] = row["topic_id"]
    return result


def build_topic_resolution_input(
    model_output: dict[str, Any], catalog: dict[str, Any]
) -> dict[str, Any]:
    validate_topic_catalog(catalog)
    occurrences: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for item in model_output.get("items", []):
        profile = item.get("topic_profile") or {}
        rows = [("primary", profile.get("primary"))]
        rows.extend(("secondary", row) for row in profile.get("secondary", []))
        for relation, topic in rows:
            if not isinstance(topic, dict) or not non_empty(topic.get("name")):
                continue
            key = normalized_text(topic["name"]).casefold()
            if key not in occurrences:
                order.append(key)
                occurrences[key] = {"name": topic["name"], "occurrences": []}
            occurrences[key]["occurrences"].append({
                "candidate_id": item.get("candidate_id"),
                "relation": relation,
                "evidence": topic.get("evidence"),
            })
    surfaces = topic_surface_map(catalog)
    topics = []
    for key in order:
        row = occurrences[key]
        match = surfaces.get(key)
        topics.append({**row, "exact_matches": [match] if match else []})
    base = {
        "schema_version": 1,
        "article_schema_version": model_output.get("schema_version"),
        "catalog_fingerprint": _fingerprint(catalog),
        "catalog_topics": catalog["topics"],
        "topics": topics,
    }
    return {**base, "input_fingerprint": _fingerprint(base)}


def validate_topic_resolution_input(
    resolution_input: dict[str, Any], catalog: dict[str, Any] | None = None
) -> dict[str, Any]:
    require_exact_fields(resolution_input, RESOLUTION_INPUT_FIELDS, "topic resolution input")
    if resolution_input.get("schema_version") != 1:
        raise TopicResolutionError("topic resolution input schema_version is invalid")
    if resolution_input.get("article_schema_version") != 9:
        raise TopicResolutionError("topic resolution article_schema_version is invalid")
    topics = resolution_input.get("topics")
    if not isinstance(topics, list):
        raise TopicResolutionError("topic resolution input topics is invalid")
    known = topic_catalog_by_id(catalog) if catalog is not None else None
    catalog_topics = resolution_input.get("catalog_topics")
    try:
        embedded_catalog = validate_topic_catalog({
            "schema_version": 1,
            "topics": catalog_topics,
        })
    except (ContractError, TypeError) as exc:
        raise TopicResolutionError("topic resolution embedded catalog is invalid") from exc
    if catalog is not None and embedded_catalog["topics"] != catalog["topics"]:
        raise TopicResolutionError("topic resolution embedded catalog mismatch")
    seen_names: set[str] = set()
    for index, topic in enumerate(topics):
        location = f"topic resolution input.topics[{index}]"
        if not isinstance(topic, dict):
            raise TopicResolutionError(f"{location} is invalid")
        require_exact_fields(topic, RESOLUTION_INPUT_TOPIC_FIELDS, location)
        if not non_empty(topic.get("name")) or len(topic["name"]) > 40:
            raise TopicResolutionError(f"{location}.name is invalid")
        key = normalized_text(topic["name"]).casefold()
        if key in seen_names:
            raise TopicResolutionError(f"{location}.name is duplicated")
        seen_names.add(key)
        occurrences = topic.get("occurrences")
        if not isinstance(occurrences, list) or not occurrences:
            raise TopicResolutionError(f"{location}.occurrences is invalid")
        for occurrence_index, occurrence in enumerate(occurrences):
            occurrence_location = f"{location}.occurrences[{occurrence_index}]"
            if not isinstance(occurrence, dict):
                raise TopicResolutionError(f"{occurrence_location} is invalid")
            require_exact_fields(occurrence, OCCURRENCE_FIELDS, occurrence_location)
            if not non_empty(occurrence.get("candidate_id")):
                raise TopicResolutionError(f"{occurrence_location}.candidate_id is invalid")
            if occurrence.get("relation") not in TOPIC_RELATIONS:
                raise TopicResolutionError(f"{occurrence_location}.relation is invalid")
            if not non_empty(occurrence.get("evidence")):
                raise TopicResolutionError(f"{occurrence_location}.evidence is invalid")
        matches = topic.get("exact_matches")
        if (
            not isinstance(matches, list)
            or len(matches) > 1
            or not all(non_empty(value) for value in matches)
            or (known is not None and any(value not in known for value in matches))
        ):
            raise TopicResolutionError(f"{location}.exact_matches is invalid")
    base = {key: resolution_input[key] for key in RESOLUTION_INPUT_FIELDS - {"input_fingerprint"}}
    if resolution_input.get("input_fingerprint") != _fingerprint(base):
        raise TopicResolutionError("topic resolution input fingerprint mismatch")
    if catalog is not None and resolution_input.get("catalog_fingerprint") != _fingerprint(catalog):
        raise TopicResolutionError("topic resolution catalog fingerprint mismatch")
    return resolution_input


def automatic_topic_resolution(resolution_input: dict[str, Any]) -> dict[str, Any] | None:
    validate_topic_resolution_input(resolution_input)
    if any(len(row.get("exact_matches", [])) != 1 for row in resolution_input["topics"]):
        return None
    return {
        "schema_version": 1,
        "input_fingerprint": resolution_input["input_fingerprint"],
        "items": [
            {
                "source_name": row["name"],
                "decision": "existing",
                "topic_id": row["exact_matches"][0],
            }
            for row in resolution_input["topics"]
        ],
    }


def validate_topic_resolution_output(
    resolution_input: dict[str, Any], resolution_output: dict[str, Any], catalog: dict[str, Any]
) -> list[dict[str, Any]]:
    try:
        validate_topic_resolution_input(resolution_input, catalog)
        require_exact_fields(resolution_output, RESOLUTION_OUTPUT_FIELDS, "topic resolution output")
        if resolution_output.get("schema_version") != 1:
            raise TopicResolutionError("topic resolution output schema_version is invalid")
        if resolution_output.get("input_fingerprint") != resolution_input.get("input_fingerprint"):
            raise TopicResolutionError("topic resolution output fingerprint mismatch")
        items = resolution_output.get("items")
        if not isinstance(items, list):
            raise TopicResolutionError("topic resolution output items is invalid")
        expected_names = [row["name"] for row in resolution_input["topics"]]
        if [row.get("source_name") for row in items if isinstance(row, dict)] != expected_names:
            raise TopicResolutionError("topic resolution source_name order mismatch")
        known = topic_catalog_by_id(catalog)
        pending_ids = set(known)
        for index, item in enumerate(items):
            location = f"topic resolution output.items[{index}]"
            if not isinstance(item, dict):
                raise TopicResolutionError(f"{location} is invalid")
            decision = item.get("decision")
            if decision == "existing":
                require_exact_fields(item, EXISTING_RESOLUTION_FIELDS, location)
                if item.get("topic_id") not in known:
                    raise TopicResolutionError(f"{location}.topic_id is unknown")
            elif decision == "new":
                require_exact_fields(item, NEW_RESOLUTION_FIELDS, location)
                topic_id = item.get("topic_id")
                if not non_empty(topic_id) or not TOPIC_ID_RE.fullmatch(topic_id):
                    raise TopicResolutionError(f"{location}.topic_id is invalid")
                if topic_id in pending_ids:
                    raise TopicResolutionError(f"{location}.topic_id already exists")
                pending_ids.add(topic_id)
                if not non_empty(item.get("name")) or len(item["name"]) > 40:
                    raise TopicResolutionError(f"{location}.name is invalid")
                if item.get("parent_id") not in known:
                    raise TopicResolutionError(f"{location}.parent_id must be an existing topic")
                for field in ("aliases", "include", "exclude"):
                    if not isinstance(item.get(field), list) or not all(
                        non_empty(value) for value in item[field]
                    ):
                        raise TopicResolutionError(f"{location}.{field} is invalid")
                if not non_empty(item.get("definition")):
                    raise TopicResolutionError(f"{location}.definition is invalid")
                source_key = normalized_text(item["source_name"]).casefold()
                canonical_surfaces = [item["name"], *item["aliases"]]
                if source_key not in {
                    normalized_text(value).casefold() for value in canonical_surfaces
                }:
                    raise TopicResolutionError(
                        f"{location} must preserve source_name as name or alias"
                    )
            else:
                raise TopicResolutionError(f"{location}.decision is invalid")
        return items
    except ContractError as exc:
        if isinstance(exc, TopicResolutionError):
            raise
        raise TopicResolutionError(str(exc)) from exc


def merge_topic_catalog(
    catalog: dict[str, Any], resolution_items: list[dict[str, Any]]
) -> dict[str, Any]:
    topics = [dict(row) for row in validate_topic_catalog(catalog)["topics"]]
    for item in resolution_items:
        if item["decision"] != "new":
            continue
        topics.append({
            "topic_id": item["topic_id"],
            "name": item["name"],
            "aliases": item["aliases"],
            "parent_id": item["parent_id"],
            "definition": item["definition"],
            "include": item["include"],
            "exclude": item["exclude"],
            "status": "active",
        })
    return validate_topic_catalog({"schema_version": 1, "topics": topics})


def _topic_path(topic_id: str, by_id: dict[str, dict[str, Any]]) -> list[str]:
    path = []
    cursor = topic_id
    while cursor is not None:
        topic = by_id[cursor]
        path.append(topic["name"])
        cursor = topic["parent_id"]
    return list(reversed(path))


def resolve_topic_profile(
    profile: dict[str, Any], resolution_items: list[dict[str, Any]], catalog: dict[str, Any]
) -> list[dict[str, Any]]:
    resolution_by_surface = {
        normalized_text(row["source_name"]).casefold(): row["topic_id"]
        for row in resolution_items
    }
    by_id = topic_catalog_by_id(catalog)
    result = []
    rows = [("primary", profile["primary"])] + [
        ("secondary", row) for row in profile["secondary"]
    ]
    for relation, topic in rows:
        topic_id = resolution_by_surface[normalized_text(topic["name"]).casefold()]
        canonical = by_id[topic_id]
        result.append({
            "topic_id": topic_id,
            "name": canonical["name"],
            "relation": relation,
            "path": _topic_path(topic_id, by_id),
            "evidence": topic["evidence"].strip(),
        })
    return result
