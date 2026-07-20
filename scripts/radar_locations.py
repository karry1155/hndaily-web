from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = ROOT / "config/hainan-administrative-divisions.json"
LEVELS = {"province", "prefecture", "county"}


class LocationCatalogError(ValueError):
    pass


@dataclass(frozen=True)
class LocationCatalog:
    metadata: dict
    divisions: tuple[dict, ...]
    by_id: dict[str, dict]


def load_location_catalog(path: Path | None = None) -> LocationCatalog:
    data = json.loads((path or DEFAULT_CATALOG).read_text(encoding="utf-8"))
    if set(data) != {"version", "source", "verified_on", "divisions"}:
        raise LocationCatalogError("catalog fields are invalid")
    ids, codes, divisions = set(), set(), []
    for row in data["divisions"]:
        if set(row) != {"location_id", "name", "code", "level", "aliases"}:
            raise LocationCatalogError("division fields are invalid")
        if row["location_id"] in ids:
            raise LocationCatalogError("duplicate location_id")
        if row["code"] in codes:
            raise LocationCatalogError("duplicate code")
        if row["level"] not in LEVELS or not row["name"].strip():
            raise LocationCatalogError("division value is invalid")
        if not isinstance(row["aliases"], list) or any(not str(v).strip() for v in row["aliases"]):
            raise LocationCatalogError("aliases are invalid")
        ids.add(row["location_id"]); codes.add(row["code"]); divisions.append(row)
    return LocationCatalog(
        {key: data[key] for key in ("version", "source", "verified_on")},
        tuple(divisions), {row["location_id"]: row for row in divisions},
    )


def find_location_candidates(title: str, content: str, catalog: LocationCatalog) -> list[dict]:
    text = "".join(f"{title}\n{content}".split())
    matched = []
    for row in catalog.divisions:
        terms = [row["name"], *row["aliases"]]
        hits = [term for term in terms if "".join(term.split()) in text]
        if hits:
            matched.append({key: row[key] for key in ("location_id", "name", "level")})
    level_order = {"county": 0, "prefecture": 1, "province": 2}
    return sorted(matched, key=lambda row: (level_order[row["level"]], row["location_id"]))


def infer_exact_location_mentions(
    title: str,
    content: str,
    candidates: list[dict],
    catalog: LocationCatalog,
    limit: int = 5,
) -> list[dict]:
    """Return only unambiguous mentions of catalogued official full names.

    Aliases continue to be model decisions. This deterministic pass prevents an
    explicit name such as ``文昌市`` from disappearing when the model omits it.
    """
    source = f"{title}\n{content}"
    mentions = []
    for candidate in candidates:
        row = catalog.by_id[candidate["location_id"]]
        if row["name"] in source:
            mentions.append({
                "location_id": row["location_id"],
                "evidence": row["name"],
            })
        if len(mentions) >= limit:
            break
    return mentions


def merge_location_mentions(model_mentions, exact_mentions, limit: int = 12) -> list[dict]:
    merged, seen = [], set()
    for mention in [*model_mentions, *exact_mentions]:
        location_id = mention.get("location_id")
        if location_id in seen:
            continue
        seen.add(location_id)
        merged.append(mention)
        if len(merged) >= limit:
            break
    return merged


def resolve_location_mentions(mentions, candidates, catalog: LocationCatalog) -> list[dict]:
    allowed = {row["location_id"] for row in candidates}
    resolved = []
    for mention in mentions:
        location_id = mention.get("location_id")
        if location_id not in allowed:
            raise LocationCatalogError(f"location_id {location_id!r} is not an article candidate")
        row = catalog.by_id[location_id]
        resolved.append({
            "location_id": location_id,
            "name": row["name"],
            "code": row["code"],
            "level": row["level"],
            "evidence": mention["evidence"].strip(),
        })
    level_order = {"province": 0, "prefecture": 1, "county": 2}
    return sorted(
        resolved,
        key=lambda row: (level_order.get(row["level"], 9), row["code"]),
    )
