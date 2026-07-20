from __future__ import annotations

import hashlib
import html
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from scripts.radar_adapter import adapt_hndaily
from scripts.radar_contract import non_empty, validate_iso_date, validate_item_id


ROOT = Path(__file__).resolve().parents[1]
REVIEW_DATES = ("2026-07-17", "2026-07-18", "2026-07-19")
BENCHMARK_ID = "article-enrichment-v2-2026-07-17_2026-07-19"
GOLD_PATH = ROOT / "evaluation/gold" / f"{BENCHMARK_ID}.json"
REQUIRED_ITEMS = {
    ("2026-07-19", "A001"),
    ("2026-07-19", "A002"),
    ("2026-07-19", "A003"),
}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _source_fingerprint(title: str, content: str) -> str:
    canonical = json.dumps(
        {"title": title, "content": content},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _default_expected(public_item: dict[str, Any]) -> dict[str, Any]:
    subjects = [
        {
            "name": row["name"],
            "type": row["type"],
            "role": row.get("role") or "",
        }
        for row in public_item.get("subjects", [])
        if row.get("type") != "project"
    ]
    projects = [
        {"name": row["name"]}
        for row in public_item.get("subjects", [])
        if row.get("type") == "project"
    ]
    relation = public_item.get("event_relation") or {}
    events = []
    if relation.get("relation") != "none" and (
        relation.get("event_name") or relation.get("event_id")
    ):
        events.append(
            {
                "name": relation.get("event_name") or relation.get("event_id"),
                "kind": "event_occurrence",
                "series_name": "",
            }
        )
    return {
        "primary_subjects": subjects,
        "background_mentions": [],
        "locations": [
            {"location_id": row["location_id"], "name": row["name"]}
            for row in public_item.get("locations", [])
        ],
        "named_events": events,
        "projects": projects,
        "facts": [],
        "notes": "",
    }


def _review_public_item(
    candidate_id: str,
    input_item: dict[str, Any],
    output_item: dict[str, Any],
) -> dict[str, Any]:
    location_names = {
        row["location_id"]: row["name"]
        for row in input_item.get("location_candidates", [])
    }
    topic_names = {
        row["topic_id"]: row["name"]
        for row in input_item.get("topic_candidates", [])
    }
    return {
        "block": {"ai_summary": output_item.get("ai_summary")},
        "scope": output_item.get("scope"),
        "subjects": output_item.get("subjects", []),
        "locations": [
            {**row, "name": location_names.get(row.get("location_id"), row.get("location_id"))}
            for row in output_item.get("location_mentions", [])
        ],
        "topics": [
            {**row, "name": topic_names.get(row.get("topic_id"), row.get("topic_id"))}
            for row in output_item.get("topic_mentions", [])
        ],
        "event_relation": output_item.get("event_relation"),
        "candidate_id": candidate_id,
    }


def _required_override(candidate_id: str) -> dict[str, Any] | None:
    if candidate_id == "A001":
        return {
            "primary_subjects": [
                {"name": "习近平", "type": "person", "role": "国家主席"}
            ],
            "background_mentions": [],
            "locations": [],
            "named_events": [
                {
                    "name": "2026世界人工智能大会暨人工智能全球治理高级别会议",
                    "kind": "event_occurrence",
                    "series_name": "世界人工智能大会",
                }
            ],
            "projects": [],
            "facts": [
                {
                    "occurred_on": "2026-07-17",
                    "actors": ["习近平"],
                    "action": "在开幕式发表主旨讲话并提出四点意见",
                    "object": "全球人工智能治理",
                    "locations": ["上海"],
                    "summary": "习近平在2026世界人工智能大会开幕式上就全球人工智能治理提出四点意见。",
                }
            ],
            "notes": "强制回归：即使 event_candidates 为空，也必须发现原文明示的命名活动。",
        }
    if candidate_id == "A002":
        return {
            "primary_subjects": [
                {"name": "冯飞", "type": "person", "role": "海南省委书记"},
                {"name": "刘小明", "type": "person", "role": "海南省省长"},
            ],
            "background_mentions": ["习近平"],
            "locations": [
                {"location_id": "hainan", "name": "海南省"},
                {"location_id": "hainan-haikou", "name": "海口市"},
            ],
            "named_events": [
                {
                    "name": "2026年（第二十七届）海南国际旅游岛欢乐节",
                    "kind": "event_occurrence",
                    "series_name": "海南国际旅游岛欢乐节",
                }
            ],
            "projects": [],
            "facts": [
                {
                    "occurred_on": "2026-07-18",
                    "actors": ["冯飞"],
                    "action": "宣布开幕",
                    "object": "2026年海南国际旅游岛欢乐节",
                    "locations": ["海口市"],
                    "summary": "冯飞宣布2026年海南国际旅游岛欢乐节开幕。",
                },
                {
                    "occurred_on": "2026-07-18",
                    "actors": ["刘小明"],
                    "action": "致辞",
                    "object": "2026年海南国际旅游岛欢乐节开幕式",
                    "locations": ["海口市"],
                    "summary": "刘小明在2026年海南国际旅游岛欢乐节开幕式上致辞。",
                },
            ],
            "notes": "强制回归：习近平只是背景提及，不能形成这次活动的人物行动节点。",
        }
    if candidate_id == "A003":
        return {
            "primary_subjects": [
                {"name": "刘小明", "type": "person", "role": "海南省省长"}
            ],
            "background_mentions": [],
            "locations": [
                {"location_id": "hainan-sanya", "name": "三亚市"},
                {"location_id": "hainan-ledong", "name": "乐东黎族自治县"},
                {"location_id": "hainan-dongfang", "name": "东方市"},
                {"location_id": "hainan-changjiang", "name": "昌江黎族自治县"},
                {"location_id": "hainan-danzhou", "name": "儋州市"},
            ],
            "named_events": [],
            "projects": [{"name": "海南环岛旅游公路"}],
            "facts": [
                {
                    "occurred_on": "2026-07-18",
                    "actors": ["刘小明"],
                    "action": "调研建管运情况",
                    "object": "海南环岛旅游公路",
                    "locations": ["三亚市", "乐东黎族自治县", "东方市", "昌江黎族自治县", "儋州市"],
                    "summary": "刘小明沿海南环岛旅游公路调研建设、管理和运营情况。",
                }
            ],
            "notes": "强制回归：环岛旅游公路是长期项目；本篇形成一次人物调研事实。",
        }
    return None


def _selected_ids_by_date(rows: list[dict[str, Any]], per_date: int = 14) -> set[str]:
    selected: list[dict[str, Any]] = []
    front = [row for row in rows if row["page_name"] == "头版"]
    selected.extend(front[:per_date])
    remaining = [row for row in rows if row not in selected]
    by_page: dict[str, list[dict[str, Any]]] = {}
    for row in remaining:
        by_page.setdefault(row["page_name"], []).append(row)
    page_names = list(by_page)
    cursor = 0
    while len(selected) < min(per_date, len(rows)) and page_names:
        page_name = page_names[cursor % len(page_names)]
        bucket = by_page[page_name]
        if bucket:
            selected.append(bucket.pop(0))
        if not bucket:
            page_names.remove(page_name)
            cursor = 0
        else:
            cursor += 1
    return {row["item_id"] for row in selected}


def build_review_dataset(project_root: Path = ROOT) -> dict[str, Any]:
    project_root = Path(project_root)
    rows: list[dict[str, Any]] = []
    for published_date in REVIEW_DATES:
        raw = _read_json(_pipeline_artifact_path(project_root, published_date, "source"))
        candidates, _ = adapt_hndaily(raw)
        model_input = _read_json(_pipeline_artifact_path(project_root, published_date, "input"))
        model_output = _read_json(_pipeline_artifact_path(project_root, published_date, "enrichment"))
        inputs = {row["candidate_id"]: row for row in model_input["items"]}
        outputs = {row["candidate_id"]: row for row in model_output["items"]}
        date_rows = []
        for candidate in candidates:
            candidate_id = candidate["candidate_id"]
            public_path = (
                project_root
                / "content/issue-items"
                / published_date
                / f'{candidate["item_id"]}.json'
            )
            public_item = (
                _read_json(public_path)
                if public_path.is_file()
                else _review_public_item(
                    candidate_id, inputs[candidate_id], outputs[candidate_id]
                )
            )
            required = (published_date, candidate_id) in REQUIRED_ITEMS
            expected = _default_expected(public_item)
            if required:
                expected = _required_override(candidate_id) or expected
            initial_expected = json.loads(json.dumps(expected, ensure_ascii=False))
            date_rows.append(
                {
                    "item_id": candidate["item_id"],
                    "candidate_id": candidate_id,
                    "published_date": published_date,
                    "page_number": candidate["page_number"],
                    "page_name": candidate["page_name"],
                    "page_sequence": candidate["page_sequence"],
                    "title": candidate["title"],
                    "content": candidate["content"],
                    "original_url": candidate["original_url"],
                    "detail_path": f'/items/{published_date}/{candidate["item_id"]}/',
                    "source_fingerprint": _source_fingerprint(
                        candidate["title"], candidate["content"]
                    ),
                    "required": required,
                    "selected": False,
                    "review_status": "draft",
                    "current": {
                        "ai_summary": public_item["block"].get("ai_summary"),
                        "scope": public_item.get("scope"),
                        "subjects": public_item.get("subjects", []),
                        "locations": public_item.get("locations", []),
                        "topics": public_item.get("topics", []),
                        "event_relation": public_item.get("event_relation"),
                    },
                    "candidates": {
                        "locations": inputs[candidate_id].get("location_candidates", []),
                        "topics": inputs[candidate_id].get("topic_candidates", []),
                        "events": inputs[candidate_id].get("event_candidates", []),
                    },
                    "raw_model_output": outputs[candidate_id],
                    "initial_expected": initial_expected,
                    "expected": expected,
                }
            )
        selected_ids = _selected_ids_by_date(date_rows)
        for row in date_rows:
            row["selected"] = row["required"] or row["item_id"] in selected_ids
        rows.extend(date_rows)
    dataset = {
        "schema_version": 1,
        "benchmark_id": BENCHMARK_ID,
        "source_dates": list(REVIEW_DATES),
        "target_count": sum(row["selected"] for row in rows),
        "required_item_ids": [
            row["item_id"] for row in rows if row["required"]
        ],
        "items": rows,
    }
    saved_path = (
        project_root / "evaluation/gold" / f"{BENCHMARK_ID}.json"
    )
    if saved_path.is_file():
        saved = validate_gold_payload(_read_json(saved_path))
        saved_by_id = {row["item_id"]: row for row in saved["items"]}
        for row in dataset["items"]:
            previous = saved_by_id.get(row["item_id"])
            row["selected"] = row["required"] or previous is not None
            if previous:
                row["review_status"] = previous["review_status"]
                row["expected"] = previous["expected"]
        dataset["target_count"] = sum(
            row["selected"] for row in dataset["items"]
        )
    return dataset


def _pipeline_artifact_path(project_root: Path, published_date: str, kind: str) -> Path:
    active = {
        "source": "source",
        "input": "input",
        "enrichment": "enrichment",
    }
    legacy = {
        "source": "raw",
        "input": "model-input",
        "enrichment": "model-output",
    }
    current = project_root / "data/production-json" / active[kind] / f"{published_date}.json"
    if current.is_file():
        return current
    return project_root / "data/json" / legacy[kind] / f"{published_date}.json"


def review_inputs_available(project_root: Path = ROOT) -> bool:
    project_root = Path(project_root)
    return all(
        _pipeline_artifact_path(project_root, published_date, kind).is_file()
        for published_date in REVIEW_DATES
        for kind in ("source", "input", "enrichment")
    ) and all(
        (project_root / "content/issue-items" / published_date).is_dir()
        for published_date in REVIEW_DATES
    )


def render_review_page(dataset: dict[str, Any]) -> str:
    title = "文章语义基准工作台 · HNHOT"
    return f'''<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{html.escape(title)}</title>
    <link rel="stylesheet" href="/static/gold-review.css?v=20260720-2">
  </head>
  <body>
    <div class="gold-app" data-gold-review data-benchmark-id="{html.escape(dataset['benchmark_id'])}">
      <header class="gold-topbar">
        <div>
          <span class="gold-eyebrow">HNHOT · INTERNAL</span>
          <h1>文章语义基准工作台</h1>
          <p>7 月 17—19 日 · 默认抽样 {dataset['target_count']} 条 · A001–A003 强制回归</p>
        </div>
        <div class="gold-actions">
          <span class="save-state" data-save-state>尚未保存到项目</span>
          <button type="button" class="button secondary" data-import>导入 JSON</button>
          <button type="button" class="button secondary" data-export>导出 JSON</button>
          <button type="button" class="button primary" data-save-repo>保存到项目</button>
          <input type="file" accept="application/json" hidden data-import-file>
        </div>
      </header>
      <section class="gold-progress" aria-label="审核进度">
        <div><strong data-progress-reviewed>0</strong><span>已确认</span></div>
        <div><strong data-progress-selected>{dataset['target_count']}</strong><span>已选样本</span></div>
        <div><strong data-progress-required>0 / 3</strong><span>强制样本</span></div>
        <div class="progress-track"><span data-progress-bar></span></div>
      </section>
      <main class="gold-workspace">
        <aside class="gold-queue">
          <div class="queue-tools">
            <input type="search" placeholder="搜索标题、编号或正文" data-queue-search>
            <div class="segmented" data-queue-filter>
              <button type="button" class="active" data-filter="selected">已选</button>
              <button type="button" data-filter="draft">未确认</button>
              <button type="button" data-filter="all">全部</button>
            </div>
          </div>
          <div class="queue-list" data-queue-list></div>
        </aside>
        <article class="gold-source" data-source-panel>
          <div class="empty-panel">正在载入审核数据……</div>
        </article>
        <aside class="gold-editor" data-editor-panel></aside>
      </main>
    </div>
    <script>window.HNHOT_GOLD_DATA_URL = "/review/gold/data.json";</script>
    <script src="/static/gold-review.js?v=20260720-2"></script>
  </body>
</html>'''


def write_review_site(project_root: Path, site_root: Path) -> dict[str, Any]:
    dataset = build_review_dataset(project_root)
    target = Path(site_root) / "review/gold"
    target.mkdir(parents=True, exist_ok=True)
    (target / "index.html").write_text(
        render_review_page(dataset), encoding="utf-8"
    )
    (target / "data.json").write_text(
        json.dumps(dataset, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return dataset


def _require_string_list(value: Any, location: str) -> None:
    if not isinstance(value, list) or any(not non_empty(row) for row in value):
        raise ValueError(f"{location} must be an array of non-empty strings")


def validate_gold_payload(payload: dict[str, Any]) -> dict[str, Any]:
    expected_top = {
        "schema_version", "benchmark_id", "status", "source_dates",
        "target_count", "reviewed_count", "items",
    }
    if not isinstance(payload, dict) or set(payload) != expected_top:
        raise ValueError("gold payload has invalid top-level fields")
    if payload["schema_version"] != 1 or payload["benchmark_id"] != BENCHMARK_ID:
        raise ValueError("gold payload version or benchmark_id mismatch")
    if payload["status"] not in {"draft", "approved"}:
        raise ValueError("gold payload status is invalid")
    if payload["source_dates"] != list(REVIEW_DATES):
        raise ValueError("gold payload source_dates mismatch")
    items = payload["items"]
    if not isinstance(items, list) or not 30 <= len(items) <= 50:
        raise ValueError("gold payload must contain 30 to 50 selected items")
    if payload["target_count"] != len(items):
        raise ValueError("gold payload target_count mismatch")
    if payload["reviewed_count"] != sum(
        row.get("review_status") == "reviewed" for row in items
    ):
        raise ValueError("gold payload reviewed_count mismatch")
    seen = set()
    required_seen = set()
    expected_item_fields = {
        "item_id", "candidate_id", "published_date", "page_number", "page_name",
        "page_sequence", "title", "source_fingerprint", "required",
        "review_status", "expected",
    }
    expected_fields = {
        "primary_subjects", "background_mentions", "locations", "named_events",
        "projects", "facts", "notes",
    }
    for index, row in enumerate(items):
        location = f"items[{index}]"
        if not isinstance(row, dict) or set(row) != expected_item_fields:
            raise ValueError(f"{location} has invalid fields")
        item_id = validate_item_id(row["item_id"], f"{location}.item_id")
        if item_id in seen:
            raise ValueError("gold payload contains duplicate item_id")
        seen.add(item_id)
        validate_iso_date(row["published_date"], f"{location}.published_date")
        if row["review_status"] not in {"draft", "reviewed"}:
            raise ValueError(f"{location}.review_status is invalid")
        expected = row["expected"]
        if not isinstance(expected, dict) or set(expected) != expected_fields:
            raise ValueError(f"{location}.expected has invalid fields")
        _require_string_list(
            expected["background_mentions"],
            f"{location}.expected.background_mentions",
        )
        for list_field in (
            "primary_subjects", "locations", "named_events", "projects", "facts"
        ):
            if not isinstance(expected[list_field], list):
                raise ValueError(f"{location}.expected.{list_field} must be an array")
        for subject_index, subject in enumerate(expected["primary_subjects"]):
            subject_location = f"{location}.expected.primary_subjects[{subject_index}]"
            if not isinstance(subject, dict) or set(subject) != {"name", "type", "role"}:
                raise ValueError(f"{subject_location} has invalid fields")
            if not non_empty(subject["name"]) or subject["type"] not in {
                "person", "government", "organization", "company"
            } or not isinstance(subject["role"], str):
                raise ValueError(f"{subject_location} is invalid")
        for location_index, mention in enumerate(expected["locations"]):
            mention_location = f"{location}.expected.locations[{location_index}]"
            if (
                not isinstance(mention, dict)
                or set(mention) != {"location_id", "name"}
                or not non_empty(mention["location_id"])
                or not non_empty(mention["name"])
            ):
                raise ValueError(f"{mention_location} is invalid")
        for event_index, event in enumerate(expected["named_events"]):
            event_location = f"{location}.expected.named_events[{event_index}]"
            if not isinstance(event, dict) or set(event) != {"name", "kind", "series_name"}:
                raise ValueError(f"{event_location} has invalid fields")
            if (
                not non_empty(event["name"])
                or event["kind"] not in {"event_occurrence", "event_series", "incident"}
                or not isinstance(event["series_name"], str)
            ):
                raise ValueError(f"{event_location} is invalid")
        for project_index, project in enumerate(expected["projects"]):
            project_location = f"{location}.expected.projects[{project_index}]"
            if (
                not isinstance(project, dict)
                or set(project) != {"name"}
                or not non_empty(project["name"])
            ):
                raise ValueError(f"{project_location} is invalid")
        for fact_index, fact in enumerate(expected["facts"]):
            fact_location = f"{location}.expected.facts[{fact_index}]"
            fact_fields = {
                "occurred_on", "actors", "action", "object", "locations", "summary"
            }
            if not isinstance(fact, dict) or set(fact) != fact_fields:
                raise ValueError(f"{fact_location} has invalid fields")
            validate_iso_date(fact["occurred_on"], f"{fact_location}.occurred_on")
            _require_string_list(fact["actors"], f"{fact_location}.actors")
            _require_string_list(fact["locations"], f"{fact_location}.locations")
            for field in ("action", "object", "summary"):
                if not non_empty(fact[field]):
                    raise ValueError(f"{fact_location}.{field} is required")
        if not isinstance(expected["notes"], str):
            raise ValueError(f"{location}.expected.notes must be a string")
        if row["required"]:
            required_seen.add((row["published_date"], row["candidate_id"]))
    if required_seen != REQUIRED_ITEMS:
        raise ValueError("gold payload must include all required regression items")
    return payload


def save_gold_payload(payload: dict[str, Any], path: Path = GOLD_PATH) -> Path:
    validate_gold_payload(payload)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        Path(temp_name).replace(path)
        path.chmod(0o644)
    except Exception:
        Path(temp_name).unlink(missing_ok=True)
        raise
    return path
