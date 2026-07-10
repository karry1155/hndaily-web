# Personal Information Radar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the newspaper-shaped daily digest with a source-agnostic, persistent information radar that selects every qualified item, renders “当下重点” Top 4, supports category and opportunity views, and proves incremental operation with real 2026-07-09 crawler data.

**Architecture:** Add a parallel `radar-v3` pipeline instead of breaking `editorial-v1` in place. A Hainan Daily adapter emits trusted source candidates; strict model handoff adds only summaries, categories, scores, and opportunity evidence; deterministic code selects, stores, indexes, and renders items. Once the new path passes real-date acceptance, switch the default preview and operational documentation while retaining the old weekly renderer as a compatibility consumer.

**Tech Stack:** Python 3 standard library, `unittest`, Bash, JSON, `string.Template`, static HTML/CSS.

## Global Constraints

- The stable public block fields are exactly `source`, `title`, `content`, `ai_summary`, and `original_url`.
- `source`, `title`, `content`, `original_url`, `published_date`, and stable IDs come from code; the model cannot return or override them.
- Formal categories are exactly `机会`, `民生`, `产业`, `政策`, `城市`, and `观察`; `全部` is a view, not a category.
- Every item has exactly one formal category. Tags are out of scope.
- Semantic fields are `hainan_relevance`, `actionability`, `impact_scope`, `timeliness`, and `information_density`, weighted `0.30`, `0.25`, `0.20`, `0.15`, and `0.10`.
- Selection requires `hainan_relevance >= 6` and `final_score >= 65`; there is no selected-item cap and no category quota.
- “当下重点” uses selected items from the latest three distinct content dates and returns at most four items using `focus_score = final_score - 3 × older_content_day_index`.
- Index pages contain at most 20 items, group by date, and never embed full article bodies.
- Only the `全部` view renders “当下重点”; formal category views do not.
- Cards render only source, original title, and AI summary, and link to internal detail pages.
- Detail pages render category/date, title, top source link, AI summary, escaped full source body, and a bottom source-link button.
- Dates are day precision. Do not add public hour/minute timestamps.
- Use only Python standard-library dependencies.
- Preserve the last valid public site and content state on any failed completed run.
- Do not deploy, push, or open a PR as part of this plan.

---

## Planned File Structure

### New production files

- `scripts/radar_contract.py`: shared schema constants, exact-field validation, date/URL validation, and JSON helpers.
- `scripts/radar_adapter.py`: Hainan Daily raw JSON to trusted source candidates and filter audit.
- `scripts/radar_model.py`: schema-v3 model input fingerprinting and exact model-output validation.
- `scripts/prepare_radar.py`: direct CLI that writes model input and prefilter audit atomically.
- `scripts/radar_scoring.py`: source-agnostic semantic score calculation.
- `scripts/radar_select.py`: unlimited qualification, daily rank, and three-content-day focus selection.
- `scripts/radar_indexes.py`: all/category/date/opportunity pagination and minimal index records.
- `scripts/radar_store.py`: idempotent item upsert and rollback-capable item/index commit.
- `scripts/radar_transaction.py`: hard-link/copy staging plus coordinated content/site/audit publication rollback.
- `scripts/finalize_radar.py`: merge trusted source fields with model fields, score/select, persist, and audit.
- `scripts/radar_render.py`: render radar routes to staging, validate internal links, and atomically replace `site`.
- `scripts/run_radar_pipeline.sh`: resumable crawler-to-site operational entrypoint.
- `src/templates/radar-index.html`: shared all/category/date index shell.
- `src/templates/radar-item.html`: item detail shell.

### New tests

- `tests/radar_fixtures.py`: reusable raw issue, semantic output, and selected-item builders.
- `tests/test_radar_adapter.py`
- `tests/test_radar_model.py`
- `tests/test_radar_selection.py`
- `tests/test_radar_indexes.py`
- `tests/test_radar_store.py`
- `tests/test_finalize_radar.py`
- `tests/test_radar_render.py`
- `tests/test_radar_pipeline_cli.py`

### Modified files

- `src/static/styles.css`: neutral radar navigation, focus list, cards, pagination, and detail typography.
- `src/static/app.js`: only keyboard/click affordances needed for whole-card navigation; no client-only category state.
- `scripts/preview.py`: invoke the radar renderer after migration.
- `README.md`: describe the radar product and local commands.
- `docs/codex-digest-generation.md`: replace editorial-v1 instructions with the resumable radar-v3 handoff.
- `.gitignore`: ignore radar staging/backup directories and generated intermediate model files.

The existing `editorial-v1` modules and weekly contract remain present during migration. New code must not import `event_clustering.py` or depend on page metadata after adapter output.

---

### Task 1: Trusted Source Candidate Contract and Hainan Daily Adapter

**Files:**
- Create: `scripts/radar_contract.py`
- Create: `scripts/radar_adapter.py`
- Create: `tests/radar_fixtures.py`
- Create: `tests/test_radar_adapter.py`

**Interfaces:**
- Consumes: raw Hainan Daily issue dictionaries accepted by `scripts.editorial_filter.evaluate_issue`.
- Produces: `adapt_hndaily(raw: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]`; the first list contains passed source candidates and the second contains every prefilter audit record.
- Produces: `validate_source_candidate(candidate: dict[str, Any]) -> None` and constants used by every later task.

- [ ] **Step 1: Write failing adapter and contract tests**

```python
# tests/test_radar_adapter.py
import unittest

from scripts.radar_adapter import adapt_hndaily
from scripts.radar_contract import ContractError, validate_source_candidate
from tests.radar_fixtures import raw_issue


class RadarAdapterTests(unittest.TestCase):
    def test_adapts_trusted_fields_without_publication_layout(self):
        candidates, audit = adapt_hndaily(raw_issue())
        self.assertEqual(len(candidates), 4)
        self.assertEqual(len(audit), 4)
        self.assertEqual(
            set(candidates[0]),
            {
                "candidate_id", "item_id", "source", "title", "content",
                "original_url", "published_date", "collected_date",
            },
        )
        self.assertEqual(candidates[0]["source"], "海南日报")
        self.assertEqual(candidates[0]["title"], "原始标题 1")
        self.assertNotIn("page", candidates[0])
        self.assertNotIn("page_name", candidates[0])

    def test_stable_id_uses_canonical_url_content_id(self):
        raw = raw_issue()
        raw["pages"][0]["articles"][0]["url"] = (
            "http://news.hndaily.cn/html/2026-07/08/content_58466_19684674.htm"
        )
        first, _ = adapt_hndaily(raw)
        second, _ = adapt_hndaily(raw)
        self.assertEqual(first[0]["item_id"], "hndaily-19684674")
        self.assertEqual(first[0]["item_id"], second[0]["item_id"])

    def test_rejects_non_http_source_url(self):
        candidate = {
            "candidate_id": "A001", "item_id": "hndaily-1", "source": "海南日报",
            "title": "标题", "content": "正文", "original_url": "javascript:alert(1)",
            "published_date": "2026-07-08", "collected_date": "2026-07-10",
        }
        with self.assertRaisesRegex(ContractError, "original_url"):
            validate_source_candidate(candidate)
```

Add these reusable builders:

```python
# tests/radar_fixtures.py
def raw_issue(article_count=4, date="2026-07-08"):
    articles = [
        {
            "seq": index,
            "title": f"原始标题 {index}",
            "url": f"http://news.hndaily.cn/html/{date[:7]}/{date[-2:]}/content_58466_{19684000 + index}.htm",
            "author": "记者",
            "content": f"这是第 {index} 篇文章的正文，包含海南本地事实和明确细节。",
        }
        for index in range(1, article_count + 1)
    ]
    return {
        "source": "海南日报", "date": date,
        "fetched_at": f"{date}T08:00:00+08:00",
        "page_count": 1, "article_count": article_count,
        "pages": [{
            "page": "001", "page_name": "头版",
            "page_url": f"http://example.test/{date}/page-1",
            "pdf_url": f"http://example.test/{date}/page-1.pdf",
            "article_count": article_count, "articles": articles,
        }],
    }


def raw_issue_with_skips():
    raw = raw_issue(article_count=2)
    raw["pages"][0]["articles"][1]["title"] = "导读"
    return raw
```

- [ ] **Step 2: Run the tests and verify the missing-module failure**

Run: `python3 -m unittest tests.test_radar_adapter -v`

Expected: `ERROR` with `ModuleNotFoundError: No module named 'scripts.radar_adapter'`.

- [ ] **Step 3: Implement contract validation and the adapter**

```python
# scripts/radar_contract.py
from __future__ import annotations

from datetime import date
from typing import Any
from urllib.parse import urlparse

SCHEMA_VERSION = 3
PROMPT_VERSION = "radar-v1"
CATEGORIES = ("机会", "民生", "产业", "政策", "城市", "观察")
SCORE_FIELDS = (
    "hainan_relevance", "actionability", "impact_scope",
    "timeliness", "information_density",
)
SOURCE_CANDIDATE_FIELDS = {
    "candidate_id", "item_id", "source", "title", "content",
    "original_url", "published_date", "collected_date",
}


class ContractError(ValueError):
    pass


def non_empty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def require_exact_fields(value: dict[str, Any], expected: set[str], location: str) -> None:
    missing = sorted(expected - set(value))
    unknown = sorted(set(value) - expected)
    if missing or unknown:
        raise ContractError(f"{location} fields missing={missing} unknown={unknown}")


def validate_iso_date(value: Any, location: str) -> str:
    if not non_empty(value):
        raise ContractError(f"{location} must be an ISO date")
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise ContractError(f"{location} must be an ISO date") from exc


def validate_http_url(value: Any, location: str) -> str:
    if not non_empty(value):
        raise ContractError(f"{location} is required")
    parsed = urlparse(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ContractError(f"{location} must be HTTP/HTTPS")
    return value.strip()


def validate_source_candidate(candidate: dict[str, Any]) -> None:
    require_exact_fields(candidate, SOURCE_CANDIDATE_FIELDS, "source candidate")
    for field in ("candidate_id", "item_id", "source", "title", "content"):
        if not non_empty(candidate.get(field)):
            raise ContractError(f"source candidate.{field} is required")
    validate_http_url(candidate.get("original_url"), "source candidate.original_url")
    validate_iso_date(candidate.get("published_date"), "source candidate.published_date")
    validate_iso_date(candidate.get("collected_date"), "source candidate.collected_date")
```

```python
# scripts/radar_adapter.py
from __future__ import annotations

import hashlib
import re
from typing import Any

from scripts.editorial_filter import evaluate_issue
from scripts.radar_contract import validate_iso_date, validate_source_candidate

CONTENT_ID_RE = re.compile(r"content_\d+_(\d+)\.htm(?:\?.*)?$")


def _stable_id(url: str, published_date: str, title: str) -> str:
    match = CONTENT_ID_RE.search(url)
    if match:
        return f"hndaily-{match.group(1)}"
    digest = hashlib.sha256(f"{published_date}\n{title}".encode("utf-8")).hexdigest()[:16]
    return f"hndaily-{published_date}-{digest}"


def adapt_hndaily(raw: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    published_date = validate_iso_date(raw.get("date"), "raw.date")
    fetched_at = str(raw.get("fetched_at", ""))
    collected_date = validate_iso_date(fetched_at[:10], "raw.fetched_at")
    records = evaluate_issue(raw)
    candidates = []
    for record in records:
        if not record["passed"]:
            continue
        candidate = {
            "candidate_id": record["candidate_id"],
            "item_id": _stable_id(record["url"], published_date, record["original_title"]),
            "source": str(raw.get("source", "")).strip(),
            "title": record["original_title"],
            "content": record["content"].strip(),
            "original_url": record["url"],
            "published_date": published_date,
            "collected_date": collected_date,
        }
        validate_source_candidate(candidate)
        candidates.append(candidate)
    return candidates, records
```

- [ ] **Step 4: Run focused and legacy tests**

Run: `python3 -m unittest tests.test_radar_adapter tests.test_editorial_filter -v`

Expected: all tests pass; the adapter exposes no page metadata.

- [ ] **Step 5: Commit the adapter boundary**

```bash
git add scripts/radar_contract.py scripts/radar_adapter.py tests/radar_fixtures.py tests/test_radar_adapter.py
git commit -m "feat: add source-agnostic radar adapter"
```

---

### Task 2: Strict Radar Model Handoff

**Files:**
- Create: `scripts/radar_model.py`
- Create: `scripts/prepare_radar.py`
- Create: `tests/test_radar_model.py`

**Interfaces:**
- Consumes: trusted candidates from `adapt_hndaily`.
- Produces: `build_model_input(candidates: list[dict]) -> dict`.
- Produces: `validate_model_output(model_input: dict, model_output: dict, candidates: list[dict]) -> list[dict]`.
- Produces CLI: `python3 scripts/prepare_radar.py RAW_JSON MODEL_INPUT_JSON PREFILTER_JSON`.

- [ ] **Step 1: Write failing exact-contract tests**

```python
# tests/test_radar_model.py
import copy
import unittest

from scripts.radar_adapter import adapt_hndaily
from scripts.radar_model import ModelOutputError, build_model_input, validate_model_output
from tests.radar_fixtures import model_output_for, raw_issue


class RadarModelTests(unittest.TestCase):
    def setUp(self):
        self.candidates, _ = adapt_hndaily(raw_issue())
        self.model_input = build_model_input(self.candidates)
        self.output = model_output_for(self.model_input)

    def test_input_exposes_only_id_title_and_content(self):
        self.assertEqual(
            set(self.model_input["items"][0]),
            {"candidate_id", "title", "content"},
        )
        self.assertNotIn("original_url", str(self.model_input))

    def test_accepts_one_category_and_nullable_opportunity_fields(self):
        items = validate_model_output(self.model_input, self.output, self.candidates)
        self.assertEqual(items[0]["category"], "民生")
        self.assertEqual(items[0]["opportunity_lifecycle"], "not_applicable")

    def test_rejects_model_owned_source_field(self):
        invalid = copy.deepcopy(self.output)
        invalid["items"][0]["title"] = "模型改写标题"
        with self.assertRaisesRegex(ModelOutputError, "unknown fields"):
            validate_model_output(self.model_input, invalid, self.candidates)

    def test_rejects_dated_opportunity_without_body_evidence(self):
        invalid = copy.deepcopy(self.output)
        invalid["items"][0].update({
            "category": "机会", "opportunity_lifecycle": "dated",
            "deadline_date": "2026-07-31", "deadline_text": "7月31日截止",
            "deadline_evidence": "正文并不存在的截止信息",
        })
        with self.assertRaisesRegex(ModelOutputError, "deadline_evidence"):
            validate_model_output(self.model_input, invalid, self.candidates)
```

Add this exact semantic-output builder:

```python
# tests/radar_fixtures.py
def model_output_for(model_input, score=8):
    return {
        "schema_version": model_input["schema_version"],
        "prompt_version": model_input["prompt_version"],
        "input_fingerprint": model_input["input_fingerprint"],
        "items": [
            {
                "candidate_id": item["candidate_id"],
                "ai_summary": f"{item['title']}的正文事实摘要。",
                "category": "民生",
                "hainan_relevance": score,
                "actionability": score,
                "impact_scope": score,
                "timeliness": score,
                "information_density": score,
                "score_reasons": {
                    "hainan_relevance": "直接涉及海南",
                    "actionability": "包含可采用的信息",
                    "impact_scope": "影响本地读者",
                    "timeliness": "属于当前出版日期",
                    "information_density": "正文包含具体事实",
                },
                "opportunity_lifecycle": "not_applicable",
                "deadline_date": None,
                "deadline_text": None,
                "deadline_evidence": None,
            }
            for item in model_input["items"]
        ],
    }
```

- [ ] **Step 2: Verify the tests fail before implementation**

Run: `python3 -m unittest tests.test_radar_model -v`

Expected: missing `scripts.radar_model` error.

- [ ] **Step 3: Implement fingerprinting and validation**

```python
# scripts/radar_model.py
from __future__ import annotations

import hashlib
import json
from typing import Any

from scripts.radar_contract import (
    CATEGORIES, PROMPT_VERSION, SCHEMA_VERSION, SCORE_FIELDS,
    ContractError, non_empty, require_exact_fields, validate_iso_date,
)

ENVELOPE_FIELDS = {"schema_version", "prompt_version", "input_fingerprint", "items"}
MODEL_ITEM_FIELDS = {
    "candidate_id", "ai_summary", "category", *SCORE_FIELDS, "score_reasons",
    "opportunity_lifecycle", "deadline_date", "deadline_text", "deadline_evidence",
}
LIFECYCLES = {"dated", "ongoing", "unspecified", "not_applicable"}


class ModelOutputError(ContractError):
    pass


def build_model_input(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    items = [
        {"candidate_id": item["candidate_id"], "title": item["title"], "content": item["content"]}
        for item in candidates
    ]
    payload = {"schema_version": SCHEMA_VERSION, "prompt_version": PROMPT_VERSION, "items": items}
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {**payload, "input_fingerprint": hashlib.sha256(canonical.encode("utf-8")).hexdigest()}


def _normalized(value: str) -> str:
    return "".join(value.split())


def validate_model_output(model_input: dict[str, Any], model_output: dict[str, Any], candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    try:
        require_exact_fields(model_output, ENVELOPE_FIELDS, "model output")
        for field in ("schema_version", "prompt_version", "input_fingerprint"):
            if model_output.get(field) != model_input.get(field):
                raise ModelOutputError(f"model output {field} mismatch")
        items = model_output.get("items")
        if not isinstance(items, list):
            raise ModelOutputError("model output items must be an array")
        expected_ids = [item["candidate_id"] for item in candidates]
        if [item.get("candidate_id") for item in items if isinstance(item, dict)] != expected_ids:
            raise ModelOutputError("candidate_id order mismatch")
        for index, (item, candidate) in enumerate(zip(items, candidates)):
            require_exact_fields(item, MODEL_ITEM_FIELDS, f"items[{index}]")
            if not non_empty(item.get("ai_summary")):
                raise ModelOutputError(f"items[{index}].ai_summary is required")
            if item.get("category") not in CATEGORIES:
                raise ModelOutputError(f"items[{index}].category is invalid")
            for field in SCORE_FIELDS:
                if type(item.get(field)) is not int or not 0 <= item[field] <= 10:
                    raise ModelOutputError(f"items[{index}].{field} must be 0..10 integer")
            reasons = item.get("score_reasons")
            if not isinstance(reasons, dict) or set(reasons) != set(SCORE_FIELDS):
                raise ModelOutputError(f"items[{index}].score_reasons is invalid")
            lifecycle = item.get("opportunity_lifecycle")
            if lifecycle not in LIFECYCLES:
                raise ModelOutputError(f"items[{index}].opportunity_lifecycle is invalid")
            deadline_values = [item.get("deadline_date"), item.get("deadline_text"), item.get("deadline_evidence")]
            if item["category"] != "机会" and (lifecycle != "not_applicable" or any(value is not None for value in deadline_values)):
                raise ModelOutputError(f"items[{index}] non-opportunity lifecycle is invalid")
            if item["category"] == "机会" and lifecycle not in {"dated", "ongoing", "unspecified"}:
                raise ModelOutputError(f"items[{index}] opportunity lifecycle is invalid")
            if lifecycle == "dated":
                validate_iso_date(item.get("deadline_date"), f"items[{index}].deadline_date")
                if not all(non_empty(value) for value in deadline_values[1:]):
                    raise ModelOutputError(f"items[{index}] dated opportunity fields are required")
                if _normalized(item["deadline_evidence"]) not in _normalized(candidate["content"]):
                    raise ModelOutputError(f"items[{index}].deadline_evidence is not in content")
            elif lifecycle == "ongoing":
                if item.get("deadline_date") is not None or item.get("deadline_text") is not None or not non_empty(item.get("deadline_evidence")):
                    raise ModelOutputError(f"items[{index}] ongoing opportunity evidence is required")
                if _normalized(item["deadline_evidence"]) not in _normalized(candidate["content"]):
                    raise ModelOutputError(f"items[{index}].deadline_evidence is not in content")
            elif any(value is not None for value in deadline_values):
                raise ModelOutputError(f"items[{index}] deadline fields must be null")
        return items
    except ContractError as exc:
        if isinstance(exc, ModelOutputError):
            raise
        raise ModelOutputError(str(exc)) from exc
```

Implement `prepare_radar.py` with the existing `write_json_atomic` pattern: load raw JSON, call `adapt_hndaily`, write model input, and write an audit containing all adapter records.

- [ ] **Step 4: Run model and direct-CLI tests**

Run: `python3 -m unittest tests.test_radar_model -v`

Expected: all tests pass, including direct invocation through `subprocess.run` added to the test file.

- [ ] **Step 5: Commit the handoff contract**

```bash
git add scripts/radar_model.py scripts/prepare_radar.py tests/test_radar_model.py tests/radar_fixtures.py
git commit -m "feat: add strict radar model handoff"
```

---

### Task 3: Source-Agnostic Scoring, Unlimited Selection, and Focus Ranking

**Files:**
- Create: `scripts/radar_scoring.py`
- Create: `scripts/radar_select.py`
- Create: `tests/test_radar_selection.py`
- Modify: `tests/radar_fixtures.py`

**Interfaces:**
- Consumes: validated model items and trusted source candidates.
- Produces: `score_semantic(item: dict) -> dict`.
- Produces: `select_items(items: list[dict]) -> tuple[list[dict], list[dict]]`.
- Produces: `select_focus(items: list[dict]) -> list[dict]`.

- [ ] **Step 1: Write failing scoring and ranking tests**

```python
# tests/test_radar_selection.py
import unittest

from scripts.radar_scoring import score_semantic
from scripts.radar_select import select_focus, select_items
from tests.radar_fixtures import scored_item, semantic_item


class RadarSelectionTests(unittest.TestCase):
    def test_score_has_no_page_or_length_adjustments(self):
        result = score_semantic(semantic_item(
            hainan_relevance=8, actionability=8, impact_scope=6,
            timeliness=4, information_density=8,
        ))
        self.assertEqual(result["base_score"], 70.0)
        self.assertEqual(result["final_score"], 70.0)
        self.assertNotIn("adjustments", result)

    def test_selects_every_qualified_item_without_eight_item_cap(self):
        values = [scored_item(index, final_score=80) for index in range(1, 12)]
        selected, decisions = select_items(list(reversed(values)))
        self.assertEqual(len(selected), 11)
        self.assertEqual([item["daily_rank"] for item in selected], list(range(1, 12)))
        self.assertTrue(all(item["selected"] for item in decisions))

    def test_focus_uses_latest_three_content_dates_and_recency_penalty(self):
        values = [
            scored_item(1, date="2026-07-10", final_score=80),
            scored_item(2, date="2026-07-09", final_score=82),
            scored_item(3, date="2026-07-08", final_score=84),
            scored_item(4, date="2026-07-07", final_score=100),
            scored_item(5, date="2026-07-10", final_score=79),
        ]
        focus = select_focus(values)
        self.assertNotIn("item-004", [item["item_id"] for item in focus])
        self.assertEqual([item["focus_score"] for item in focus], [80, 79, 79, 78])
        self.assertEqual([item["focus_rank"] for item in focus], [1, 2, 3, 4])
```

Add the exact builders used above:

```python
# tests/radar_fixtures.py
def semantic_item(**overrides):
    value = model_output_for({
        "schema_version": 3, "prompt_version": "radar-v1",
        "input_fingerprint": "fixture", "items": [{"candidate_id": "A001", "title": "标题", "content": "正文"}],
    })["items"][0]
    value.update(overrides)
    return value


def scored_item(index, date="2026-07-10", final_score=70, relevance=8, density=7):
    return {
        "item_id": f"item-{index:03d}",
        "published_date": date,
        "semantic_scores": {"hainan_relevance": relevance, "information_density": density},
        "final_score": final_score,
    }
```

- [ ] **Step 2: Verify the new tests fail**

Run: `python3 -m unittest tests.test_radar_selection -v`

Expected: missing-module errors.

- [ ] **Step 3: Implement deterministic scoring and selection**

```python
# scripts/radar_scoring.py
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from scripts.radar_contract import SCORE_FIELDS, ContractError, non_empty

WEIGHTS = {
    "hainan_relevance": Decimal("0.30"), "actionability": Decimal("0.25"),
    "impact_scope": Decimal("0.20"), "timeliness": Decimal("0.15"),
    "information_density": Decimal("0.10"),
}


def score_semantic(item: dict[str, Any]) -> dict[str, Any]:
    reasons = item.get("score_reasons")
    if not isinstance(reasons, dict) or set(reasons) != set(SCORE_FIELDS):
        raise ContractError("score_reasons must contain exactly the five score fields")
    for field in SCORE_FIELDS:
        if type(item.get(field)) is not int or not 0 <= item[field] <= 10:
            raise ContractError(f"{field} must be a 0..10 integer")
        if not non_empty(reasons.get(field)):
            raise ContractError(f"score_reasons.{field} is required")
    weighted = sum(Decimal(item[field]) * WEIGHTS[field] for field in SCORE_FIELDS)
    score = float((weighted * Decimal("10")).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))
    return {
        "semantic_scores": {field: item[field] for field in SCORE_FIELDS},
        "score_reasons": {field: reasons[field].strip() for field in SCORE_FIELDS},
        "base_score": score,
        "final_score": score,
    }
```

```python
# scripts/radar_select.py
from typing import Any

HAINAN_RELEVANCE_THRESHOLD = 6
FINAL_SCORE_THRESHOLD = 65
FOCUS_DAYS = 3
FOCUS_LIMIT = 4
FOCUS_DAY_PENALTY = 3


def _rank_key(item: dict[str, Any]) -> tuple[Any, ...]:
    return (
        -float(item["final_score"]),
        -int(item["semantic_scores"]["information_density"]),
        str(item["item_id"]),
    )


def select_items(items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    decisions = [dict(item) for item in sorted(items, key=_rank_key)]
    selected = []
    for item in decisions:
        relevance = item["semantic_scores"]["hainan_relevance"]
        if relevance < HAINAN_RELEVANCE_THRESHOLD:
            item.update(selected=False, daily_rank=None, unselected_reason="below_hainan_relevance")
        elif item["final_score"] < FINAL_SCORE_THRESHOLD:
            item.update(selected=False, daily_rank=None, unselected_reason="below_final_score")
        else:
            item.update(selected=True, daily_rank=len(selected) + 1, unselected_reason=None)
            selected.append(item)
    return selected, decisions


def select_focus(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    dates = sorted({item["published_date"] for item in items}, reverse=True)[:FOCUS_DAYS]
    date_index = {value: index for index, value in enumerate(dates)}
    candidates = []
    for item in items:
        if item["published_date"] not in date_index:
            continue
        copy = dict(item)
        copy["focus_score"] = float(item["final_score"]) - FOCUS_DAY_PENALTY * date_index[item["published_date"]]
        candidates.append(copy)
    candidates.sort(key=lambda item: (-item["focus_score"], -item["final_score"], -int(item["published_date"].replace("-", "")), item["item_id"]))
    focus = candidates[:FOCUS_LIMIT]
    for rank, item in enumerate(focus, 1):
        item["focus_rank"] = rank
    return focus
```

- [ ] **Step 4: Run focused tests and hand-check the score equation**

Run: `python3 -m unittest tests.test_radar_selection -v`

Expected: all tests pass; eleven qualified inputs produce eleven selected outputs.

- [ ] **Step 5: Commit the deterministic editorial core**

```bash
git add scripts/radar_scoring.py scripts/radar_select.py tests/test_radar_selection.py tests/radar_fixtures.py
git commit -m "feat: select unlimited radar items"
```

---

### Task 4: Persistent Item Store, Pagination, and Opportunity Indexes

**Files:**
- Create: `scripts/radar_indexes.py`
- Create: `scripts/radar_store.py`
- Create: `tests/test_radar_indexes.py`
- Create: `tests/test_radar_store.py`
- Modify: `scripts/radar_contract.py`
- Modify: `tests/radar_fixtures.py`

**Interfaces:**
- Consumes: complete selected item dictionaries.
- Produces: `build_indexes(items: list[dict], as_of: str, page_size: int = 20) -> dict[str, dict]`.
- Produces: `load_items(content_root: Path) -> list[dict]`.
- Produces: `commit_generation(content_root: Path, items: list[dict], indexes: dict[str, dict], affected_dates: set[str]) -> None`; `items` is the complete post-merge library, while only affected date directories and the full index tree are swapped.
- Produces: `validate_stored_item(item: dict[str, Any]) -> None`; store and renderer inputs must pass it.

- [ ] **Step 1: Write failing pagination and lifecycle tests**

```python
# tests/test_radar_indexes.py
import unittest

from scripts.radar_indexes import build_indexes
from tests.radar_fixtures import stored_item


class RadarIndexTests(unittest.TestCase):
    def test_paginates_twenty_items_without_full_content(self):
        items = [stored_item(index, category="民生") for index in range(1, 22)]
        indexes = build_indexes(items, "2026-07-10")
        self.assertEqual(len(indexes["all/page-001.json"]["items"]), 20)
        self.assertEqual(len(indexes["all/page-002.json"]["items"]), 1)
        self.assertNotIn("content", str(indexes["all/page-001.json"]))

    def test_opportunity_active_and_expired_indexes_are_separate(self):
        active = stored_item(1, category="机会", deadline="2026-07-11")
        expired = stored_item(2, category="机会", deadline="2026-07-09")
        unspecified = stored_item(3, category="机会", lifecycle="unspecified")
        indexes = build_indexes([expired, unspecified, active], "2026-07-10")
        active_ids = [item["item_id"] for item in indexes["categories/opportunity/active-page-001.json"]["items"]]
        expired_ids = [item["item_id"] for item in indexes["categories/opportunity/expired-page-001.json"]["items"]]
        self.assertEqual(active_ids, [active["item_id"], unspecified["item_id"]])
        self.assertEqual(expired_ids, [expired["item_id"]])
```

```python
# tests/test_radar_store.py
import tempfile
import unittest
from pathlib import Path

from scripts.radar_store import commit_generation, load_items
from tests.radar_fixtures import stored_item


class RadarStoreTests(unittest.TestCase):
    def test_same_item_id_is_upserted_without_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = stored_item(1, summary="第一版摘要")
            second = stored_item(1, summary="第二版摘要")
            commit_generation(root, [first], {}, {"2026-07-10"})
            commit_generation(root, [second], {}, {"2026-07-10"})
            items = load_items(root)
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]["block"]["ai_summary"], "第二版摘要")

    def test_failed_commit_restores_previous_items_and_indexes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old = stored_item(1)
            commit_generation(root, [old], {"all/page-001.json": {"items": []}}, {"2026-07-10"})
            with self.assertRaises(RuntimeError):
                commit_generation(root, [stored_item(2)], {}, {"2026-07-10"}, fail_after_items=True)
            self.assertEqual([item["item_id"] for item in load_items(root)], [old["item_id"]])

    def test_rejects_item_with_model_owned_or_missing_block_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            invalid = stored_item(1)
            invalid["block"]["page"] = "003"
            with self.assertRaisesRegex(ValueError, "block fields"):
                commit_generation(Path(tmp), [invalid], {}, {"2026-07-10"})
```

Add a complete stored-item builder:

```python
# tests/radar_fixtures.py
def stored_item(index, *, date="2026-07-10", category="民生", deadline=None,
                lifecycle=None, title=None, summary=None, content=None):
    lifecycle = lifecycle or ("dated" if deadline else "not_applicable")
    return {
        "schema_version": 3,
        "item_id": f"item-{index:03d}",
        "published_date": date,
        "collected_date": "2026-07-10",
        "category": category,
        "semantic_scores": {
            "hainan_relevance": 8, "actionability": 8, "impact_scope": 8,
            "timeliness": 8, "information_density": 8,
        },
        "score_reasons": {
            "hainan_relevance": "海南", "actionability": "可行动",
            "impact_scope": "有影响", "timeliness": "当前",
            "information_density": "具体",
        },
        "base_score": 80.0,
        "final_score": 80.0,
        "selected": True,
        "daily_rank": index,
        "unselected_reason": None,
        "opportunity": {
            "lifecycle": lifecycle,
            "deadline_date": deadline,
            "deadline_text": f"{deadline}截止" if deadline else None,
            "evidence": f"{deadline}截止" if deadline else ("长期有效" if lifecycle == "ongoing" else None),
        },
        "block": {
            "source": "海南日报",
            "title": title or f"原始标题 {index}",
            "content": content or f"第 {index} 篇完整正文。",
            "ai_summary": summary or f"第 {index} 篇摘要。",
            "original_url": f"https://example.test/articles/{index}",
        },
    }
```

Extend `radar_contract.py` with exact persisted-item validation and call it from `load_items`, `commit_generation`, `build_indexes`, and the renderer:

```python
BLOCK_FIELDS = {"source", "title", "content", "ai_summary", "original_url"}
OPPORTUNITY_FIELDS = {"lifecycle", "deadline_date", "deadline_text", "evidence"}
STORED_ITEM_FIELDS = {
    "schema_version", "item_id", "published_date", "collected_date", "category",
    "semantic_scores", "score_reasons", "base_score", "final_score", "selected",
    "daily_rank", "unselected_reason", "opportunity", "block",
}


def validate_stored_item(item: dict[str, Any]) -> None:
    require_exact_fields(item, STORED_ITEM_FIELDS, "stored item")
    if item.get("schema_version") != SCHEMA_VERSION:
        raise ContractError("stored item schema_version is invalid")
    for field in ("item_id", "published_date", "collected_date", "category"):
        if not non_empty(item.get(field)):
            raise ContractError(f"stored item.{field} is required")
    validate_iso_date(item["published_date"], "stored item.published_date")
    validate_iso_date(item["collected_date"], "stored item.collected_date")
    if item["category"] not in CATEGORIES:
        raise ContractError("stored item.category is invalid")
    if item.get("selected") is not True or type(item.get("daily_rank")) is not int or item["daily_rank"] < 1:
        raise ContractError("stored item must be selected with a positive daily_rank")
    scores = item.get("semantic_scores")
    reasons = item.get("score_reasons")
    if not isinstance(scores, dict) or set(scores) != set(SCORE_FIELDS):
        raise ContractError("stored item.semantic_scores is invalid")
    if not isinstance(reasons, dict) or set(reasons) != set(SCORE_FIELDS):
        raise ContractError("stored item.score_reasons is invalid")
    for field in SCORE_FIELDS:
        if type(scores.get(field)) is not int or not 0 <= scores[field] <= 10:
            raise ContractError(f"stored item.semantic_scores.{field} is invalid")
        if not non_empty(reasons.get(field)):
            raise ContractError(f"stored item.score_reasons.{field} is required")
    if type(item.get("base_score")) not in (int, float) or type(item.get("final_score")) not in (int, float):
        raise ContractError("stored item scores must be numeric")
    block = item.get("block")
    if not isinstance(block, dict):
        raise ContractError("stored item.block must be an object")
    require_exact_fields(block, BLOCK_FIELDS, "block")
    for field in ("source", "title", "content", "ai_summary"):
        if not non_empty(block.get(field)):
            raise ContractError(f"block.{field} is required")
    validate_http_url(block.get("original_url"), "block.original_url")
    opportunity = item.get("opportunity")
    if not isinstance(opportunity, dict):
        raise ContractError("stored item.opportunity must be an object")
    require_exact_fields(opportunity, OPPORTUNITY_FIELDS, "opportunity")
    lifecycle = opportunity.get("lifecycle")
    if lifecycle not in {"dated", "ongoing", "unspecified", "not_applicable"}:
        raise ContractError("opportunity.lifecycle is invalid")
    deadline_values = [opportunity.get("deadline_date"), opportunity.get("deadline_text"), opportunity.get("evidence")]
    if item["category"] != "机会" and (lifecycle != "not_applicable" or any(value is not None for value in deadline_values)):
        raise ContractError("non-opportunity lifecycle is invalid")
    if item["category"] == "机会" and lifecycle not in {"dated", "ongoing", "unspecified"}:
        raise ContractError("opportunity item lifecycle is invalid")
    if lifecycle == "dated":
        validate_iso_date(opportunity.get("deadline_date"), "opportunity.deadline_date")
        if not all(non_empty(value) for value in deadline_values[1:]):
            raise ContractError("dated opportunity evidence is required")
    elif lifecycle == "ongoing":
        if opportunity.get("deadline_date") is not None or opportunity.get("deadline_text") is not None or not non_empty(opportunity.get("evidence")):
            raise ContractError("ongoing opportunity evidence is required")
    elif any(value is not None for value in deadline_values):
        raise ContractError("non-dated opportunity fields must be null")
```

- [ ] **Step 2: Verify index/store tests fail**

Run: `python3 -m unittest tests.test_radar_indexes tests.test_radar_store -v`

Expected: missing-module errors.

- [ ] **Step 3: Implement minimal index records and deterministic pagination**

```python
# scripts/radar_indexes.py
from __future__ import annotations

from datetime import date
from typing import Any

from scripts.radar_contract import CATEGORIES
from scripts.radar_select import select_focus

CATEGORY_SLUGS = {
    "机会": "opportunity", "民生": "livelihood", "产业": "industry",
    "政策": "policy", "城市": "city", "观察": "observation",
}


def _summary(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "item_id": item["item_id"], "published_date": item["published_date"],
        "daily_rank": item["daily_rank"], "category": item["category"],
        "source": item["block"]["source"], "title": item["block"]["title"],
        "ai_summary": item["block"]["ai_summary"],
        "detail_path": f"/items/{item['published_date']}/{item['item_id']}/",
    }


def _pages(prefix: str, values: list[dict[str, Any]], page_size: int, stem: str = "page") -> dict[str, dict[str, Any]]:
    result = {}
    chunks = [values[index:index + page_size] for index in range(0, len(values), page_size)] or [[]]
    for number, chunk in enumerate(chunks, 1):
        result[f"{prefix}/{stem}-{number:03d}.json"] = {
            "page": number, "page_count": len(chunks), "items": [_summary(item) for item in chunk],
        }
    return result


def build_indexes(items: list[dict[str, Any]], as_of: str, page_size: int = 20) -> dict[str, dict[str, Any]]:
    date.fromisoformat(as_of)
    ordered = sorted(items, key=lambda item: (-int(item["published_date"].replace("-", "")), item["daily_rank"], item["item_id"]))
    indexes = _pages("all", ordered, page_size)
    indexes["focus.json"] = {"updated_through": max((item["published_date"] for item in items), default=as_of), "items": [_summary(item) | {"focus_rank": item["focus_rank"]} for item in select_focus(items)]}
    for published_date in sorted({item["published_date"] for item in items}):
        same_date = [item for item in ordered if item["published_date"] == published_date]
        indexes[f"dates/{published_date}.json"] = {"date": published_date, "items": [_summary(item) for item in same_date]}
    for category in CATEGORIES:
        category_items = [item for item in ordered if item["category"] == category]
        slug = CATEGORY_SLUGS[category]
        if category != "机会":
            indexes.update(_pages(f"categories/{slug}", category_items, page_size))
            continue
        expired = []
        active = []
        for item in category_items:
            opportunity = item["opportunity"]
            if opportunity["lifecycle"] == "dated" and opportunity["deadline_date"] < as_of:
                expired.append(item)
            else:
                active.append(item)
        lifecycle_order = {"dated": 0, "ongoing": 1, "unspecified": 2}
        active.sort(key=lambda item: (
            lifecycle_order[item["opportunity"]["lifecycle"]],
            item["opportunity"].get("deadline_date") or "9999-12-31",
            -int(item["published_date"].replace("-", "")), item["item_id"],
        ))
        indexes.update(_pages("categories/opportunity", active, page_size, stem="active-page"))
        indexes.update(_pages("categories/opportunity", expired, page_size, stem="expired-page"))
    return indexes
```

Implement `radar_store.py` with JSON writes to a sibling staging directory, backups for every directory named in `affected_dates` and for `indexes`, `Path.replace` for swaps, and rollback in `except`. Each affected date staging directory is rebuilt from the complete `items` argument, so a rerun can remove a previously selected item without touching other dates. Expose the test-only keyword `fail_after_items: bool = False`; it must raise after item swaps and before index swap so the rollback path is exercised. Item paths are `items/YYYY-MM-DD/<item-id>.json`.

- [ ] **Step 4: Run store/index tests twice to prove idempotence**

Run: `python3 -m unittest tests.test_radar_indexes tests.test_radar_store -v && python3 -m unittest tests.test_radar_store -v`

Expected: both runs pass with no duplicate item files.

- [ ] **Step 5: Commit persistent storage and indexes**

```bash
git add scripts/radar_contract.py scripts/radar_indexes.py scripts/radar_store.py tests/test_radar_indexes.py tests/test_radar_store.py tests/radar_fixtures.py
git commit -m "feat: persist and index radar selections"
```

---

### Task 5: Finalize Trusted Candidates into the Persistent Radar Library

**Files:**
- Create: `scripts/finalize_radar.py`
- Create: `tests/test_finalize_radar.py`

**Interfaces:**
- Consumes: raw issue, exact model input, exact model output, existing item store, and explicit `as_of` date.
- Produces: `build_items(raw, model_input, model_output) -> tuple[list[dict], dict]`.
- Produces CLI: `python3 scripts/finalize_radar.py RAW INPUT OUTPUT CONTENT_ROOT AUDIT AS_OF`.

- [ ] **Step 1: Write failing merge, ownership, and no-cap tests**

```python
# tests/test_finalize_radar.py
import json
import copy
import tempfile
import unittest
from pathlib import Path

from scripts.finalize_radar import FinalizeError, build_items, finalize_to_store
from scripts.radar_adapter import adapt_hndaily
from scripts.radar_model import build_model_input
from scripts.radar_store import load_items
from tests.radar_fixtures import model_output_for, raw_issue


class FinalizeRadarTests(unittest.TestCase):
    def test_source_fields_are_injected_from_raw_and_title_is_not_rewritten(self):
        raw = raw_issue()
        candidates, _ = adapt_hndaily(raw)
        model_input = build_model_input(candidates)
        output = model_output_for(model_input, score=9)
        items, audit = build_items(raw, model_input, output)
        self.assertEqual(items[0]["block"]["title"], raw["pages"][0]["articles"][0]["title"])
        self.assertEqual(items[0]["block"]["original_url"], raw["pages"][0]["articles"][0]["url"])
        self.assertEqual(audit["selected_count"], len(items))

    def test_more_than_eight_qualified_items_are_persisted(self):
        raw = raw_issue(article_count=11)
        candidates, _ = adapt_hndaily(raw)
        model_input = build_model_input(candidates)
        output = model_output_for(model_input, score=9)
        with tempfile.TemporaryDirectory() as tmp:
            finalize_to_store(raw, model_input, output, Path(tmp), Path(tmp) / "audit.json", "2026-07-10")
            self.assertEqual(len(load_items(Path(tmp))), 11)

    def test_replacement_is_recorded_in_audit(self):
        raw = raw_issue()
        candidates, _ = adapt_hndaily(raw)
        model_input = build_model_input(candidates)
        first = model_output_for(model_input, score=8)
        second = model_output_for(model_input, score=9)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit = root / "audit.json"
            finalize_to_store(raw, model_input, first, root, audit, "2026-07-10")
            finalize_to_store(raw, model_input, second, root, audit, "2026-07-10")
            payload = json.loads(audit.read_text(encoding="utf-8"))
            self.assertEqual(len(payload["replaced_items"]), 4)
            self.assertEqual(payload["replaced_items"][0]["previous_schema_version"], 3)

    def test_rerun_replaces_only_same_source_and_date_selection(self):
        raw = raw_issue(article_count=2)
        candidates, _ = adapt_hndaily(raw)
        model_input = build_model_input(candidates)
        first = model_output_for(model_input, score=9)
        second = model_output_for(model_input, score=9)
        second["items"][1]["hainan_relevance"] = 0
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            finalize_to_store(raw, model_input, first, root, root / "audit.json", "2026-07-10")
            finalize_to_store(raw, model_input, second, root, root / "audit.json", "2026-07-10")
            self.assertEqual(len(load_items(root)), 1)

    def test_invalid_output_does_not_replace_existing_library(self):
        raw = raw_issue()
        candidates, _ = adapt_hndaily(raw)
        model_input = build_model_input(candidates)
        output = model_output_for(model_input)
        output["items"][0]["title"] = "模型越权"
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FinalizeError):
                finalize_to_store(raw, model_input, output, Path(tmp), Path(tmp) / "audit.json", "2026-07-10")
            self.assertEqual(load_items(Path(tmp)), [])
```

- [ ] **Step 2: Run the test and verify the missing finalizer**

Run: `python3 -m unittest tests.test_finalize_radar -v`

Expected: missing-module error.

- [ ] **Step 3: Implement the orchestrating finalizer**

```python
# scripts/finalize_radar.py (core function)
def build_items(raw, model_input, model_output):
    candidates, prefilter = adapt_hndaily(raw)
    expected_input = build_model_input(candidates)
    if model_input != expected_input:
        raise FinalizeError("model input does not match adapted raw candidates")
    semantic_items = validate_model_output(model_input, model_output, candidates)
    scored = []
    for candidate, semantic in zip(candidates, semantic_items):
        scoring = score_semantic(semantic)
        opportunity = {
            "lifecycle": semantic["opportunity_lifecycle"],
            "deadline_date": semantic["deadline_date"],
            "deadline_text": semantic["deadline_text"],
            "evidence": semantic["deadline_evidence"],
        }
        scored.append({
            "schema_version": SCHEMA_VERSION,
            "item_id": candidate["item_id"],
            "published_date": candidate["published_date"],
            "collected_date": candidate["collected_date"],
            "category": semantic["category"],
            **scoring,
            "opportunity": opportunity,
            "block": {
                "source": candidate["source"], "title": candidate["title"],
                "content": candidate["content"], "ai_summary": semantic["ai_summary"].strip(),
                "original_url": candidate["original_url"],
            },
        })
    selected, decisions = select_items(scored)
    return selected, {
        "schema_version": SCHEMA_VERSION, "published_date": raw["date"],
        "input_fingerprint": model_input["input_fingerprint"],
        "candidate_count": len(candidates), "selected_count": len(selected),
        "prefilter": prefilter, "decisions": decisions,
    }
```

`finalize_to_store` must load existing items, remove existing items with the same `published_date` and `block.source` as the current adapted batch, add the newly selected items, and reject duplicate IDs in the merged library. It then calls `build_indexes` on the merged set and `commit_generation(..., affected_dates={raw["date"]})`, and atomically writes the audit only after all validation succeeds. This replacement behavior removes items that no longer qualify while preserving other dates and other sources on the same date. Before commit, compare each incoming item with an existing item of the same ID and add `replaced_items` entries containing `item_id`, `previous_schema_version`, `previous_final_score`, `new_final_score`, and the current `prompt_version`; an identical rerun produces an empty replacement list. The CLI must return nonzero on JSON, contract, or filesystem errors.

- [ ] **Step 4: Run finalizer and legacy tests**

Run: `python3 -m unittest tests.test_finalize_radar tests.test_finalize_digest -v`

Expected: both radar-v3 and editorial-v1 finalizer tests pass.

- [ ] **Step 5: Commit the end-to-end data finalizer**

```bash
git add scripts/finalize_radar.py tests/test_finalize_radar.py
git commit -m "feat: finalize radar items into library"
```

---

### Task 6: Radar Index Pages, Category Routes, and Item Detail Pages

**Files:**
- Create: `scripts/radar_render.py`
- Create: `src/templates/radar-index.html`
- Create: `src/templates/radar-item.html`
- Create: `tests/test_radar_render.py`
- Modify: `src/static/styles.css`
- Modify: `src/static/app.js`

**Interfaces:**
- Consumes: `content/items` and `content/indexes` produced by Task 5.
- Produces: `render_index(index: dict, focus: dict | None, active_category: str) -> str`.
- Produces: `render_item(item: dict) -> str`.
- Produces CLI: `python3 scripts/radar_render.py [CONTENT_ROOT] [SITE_ROOT]`.

- [ ] **Step 1: Write failing public-markup tests**

```python
# tests/test_radar_render.py
import unittest

from scripts.radar_render import render_index, render_item
from tests.radar_fixtures import stored_item


class RadarRenderTests(unittest.TestCase):
    def test_all_view_renders_focus_and_card_only_public_fields(self):
        item = stored_item(1, title="科技见习 <计划>", summary="摘要 <script>x</script>")
        summary = {
            "item_id": item["item_id"], "published_date": item["published_date"],
            "daily_rank": 1, "category": "机会", "source": "海南日报",
            "title": item["block"]["title"], "ai_summary": item["block"]["ai_summary"],
            "detail_path": f"/items/{item['published_date']}/{item['item_id']}/",
        }
        rendered = render_index({"page": 1, "page_count": 1, "items": [summary]}, {"updated_through": "2026-07-10", "items": [summary | {"focus_rank": 1}]}, "全部")
        self.assertIn("当下重点", rendered)
        self.assertIn("海南日报", rendered)
        self.assertIn("科技见习 &lt;计划&gt;", rendered)
        self.assertNotIn("<script>", rendered)
        self.assertNotIn("最终分", rendered)
        self.assertNotIn("第003版", rendered)
        self.assertNotIn("查看原文", rendered)

    def test_formal_category_hides_focus(self):
        rendered = render_index({"page": 1, "page_count": 1, "items": []}, None, "民生")
        self.assertNotIn("当下重点", rendered)
        self.assertIn("今日暂无民生精选", rendered)

    def test_detail_has_two_source_links_and_escaped_body(self):
        item = stored_item(1, content="第一段\n\n第二段 <script>x</script>")
        rendered = render_item(item)
        self.assertEqual(rendered.count(item["block"]["original_url"]), 2)
        self.assertLess(rendered.index("AI 摘要"), rendered.index("第一段"))
        self.assertIn("第二段 &lt;script&gt;x&lt;/script&gt;", rendered)
```

- [ ] **Step 2: Verify renderer tests fail**

Run: `python3 -m unittest tests.test_radar_render -v`

Expected: missing renderer module.

- [ ] **Step 3: Create the index and detail templates**

```html
<!-- src/templates/radar-index.html -->
<div class="app-shell radar-shell">
  <aside class="primary-nav">
    <a class="brand" href="/">$product_name</a>
    <nav>$category_links</nav>
  </aside>
  <main class="content-shell radar-content">
    <header class="radar-header"><h1>$view_title</h1><p>更新至 $updated_through</p></header>
    $focus_section
    <section class="radar-feed">$date_groups</section>
    <nav class="pagination" aria-label="分页">$pagination</nav>
  </main>
</div>
```

```html
<!-- src/templates/radar-item.html -->
<main class="item-page">
  <a class="back-link" href="$category_path">← 返回$category</a>
  <p class="item-meta">$category · $published_date</p>
  <h1>$title</h1>
  <a class="source-link" href="$original_url" target="_blank" rel="noopener noreferrer">查看原文</a>
  <section class="ai-summary"><h2>AI 摘要</h2><p>$ai_summary</p></section>
  <article class="source-body">$body_paragraphs</article>
  <a class="source-button" href="$original_url" target="_blank" rel="noopener noreferrer">查看原文</a>
</main>
```

- [ ] **Step 4: Implement route-aware rendering**

Implement exact category paths:

```python
CATEGORY_PATHS = {
    "全部": "/", "机会": "/category/opportunity/",
    "民生": "/category/livelihood/", "产业": "/category/industry/",
    "政策": "/category/policy/", "城市": "/category/city/",
    "观察": "/category/observation/",
}

PRODUCT_NAME = "海南信息雷达"
```

Pass `PRODUCT_NAME` through the `$product_name` template slot instead of embedding source identity in the template. `render_index` must group adjacent index items by `published_date`, render whole-card anchors to `detail_path`, and render focus only when a non-`None` focus object is passed. `render_item` must split normalized source text on blank lines, escape each paragraph, and generate both source links from the code-owned URL. Page 2+ routes use `/page/2/` for all and `/category/<slug>/page/2/` for categories. Opportunity expired pages use `/category/opportunity/expired/`.

Add CSS classes with responsive behavior at the existing `980px` and `720px` breakpoints. Remove no weekly styles. Keep `app.js` limited to adding `js-ready`; whole-card navigation must use semantic `<a>` elements and require no JavaScript.

- [ ] **Step 5: Run renderer tests and inspect generated strings**

Run: `python3 -m unittest tests.test_radar_render -v`

Expected: all tests pass; category output has no focus section and detail output has exactly two source URLs.

- [ ] **Step 6: Commit the radar page system**

```bash
git add scripts/radar_render.py src/templates/radar-index.html src/templates/radar-item.html src/static/styles.css src/static/app.js tests/test_radar_render.py
git commit -m "feat: render radar indexes and detail pages"
```

---

### Task 7: Atomic Site Build, Internal Link Validation, and Coordinated Publication

**Files:**
- Modify: `scripts/radar_render.py`
- Create: `scripts/radar_transaction.py`
- Create: `tests/test_radar_site_build.py`
- Create: `tests/test_radar_transaction.py`
- Modify: `.gitignore`
- Modify: `tests/radar_fixtures.py`

**Interfaces:**
- Consumes: valid item and index files.
- Produces: `build_site(content_root: Path, site_root: Path) -> None`.
- Produces: `validate_internal_links(site_root: Path) -> list[str]`.
- Produces: `prepare_staged_content(content_root: Path, staged_content: Path) -> None`.
- Produces: `publish_staged_generation(content_root: Path, staged_content: Path, site_root: Path, staged_site: Path, audit_path: Path, staged_audit: Path) -> None`.

- [ ] **Step 1: Write failing staging and rollback tests**

```python
# tests/test_radar_site_build.py
import tempfile
import unittest
from pathlib import Path

from scripts.radar_render import build_site, validate_internal_links
from tests.radar_fixtures import write_content_library


class RadarSiteBuildTests(unittest.TestCase):
    def test_builds_all_category_date_detail_and_pagination_routes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            content = root / "content"
            site = root / "site"
            write_content_library(content, count=21)
            build_site(content, site)
            self.assertTrue((site / "index.html").is_file())
            self.assertTrue((site / "page" / "2" / "index.html").is_file())
            self.assertTrue((site / "category" / "livelihood" / "index.html").is_file())
            self.assertTrue((site / "date" / "2026-07-08" / "index.html").is_file())
            self.assertEqual(validate_internal_links(site), [])

    def test_preserves_weekly_routes_when_weekly_content_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            content = root / "content"
            site = root / "site"
            write_content_library(content, count=1, include_weekly_fixture=True)
            build_site(content, site)
            self.assertTrue((site / "weekly" / "2026-W28" / "index.html").is_file())
            self.assertTrue((site / "weekly" / "index.html").is_file())

    def test_broken_build_keeps_previous_public_site(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            site = root / "site"
            site.mkdir()
            (site / "index.html").write_text("previous", encoding="utf-8")
            with self.assertRaises(ValueError):
                build_site(root / "missing-content", site)
            self.assertEqual((site / "index.html").read_text(encoding="utf-8"), "previous")
```

Write the coordinated rollback test:

```python
# tests/test_radar_transaction.py
import tempfile
import unittest
from pathlib import Path

from scripts.radar_transaction import prepare_staged_content, publish_staged_generation
from tests.radar_fixtures import write_content_library


class RadarTransactionTests(unittest.TestCase):
    def test_publish_failure_restores_content_site_and_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            content = root / "content"
            site = root / "site"
            audit = root / "audit.json"
            write_content_library(content, count=1)
            site.mkdir()
            (site / "index.html").write_text("old site", encoding="utf-8")
            audit.write_text("old audit", encoding="utf-8")
            staged_content = root / "run/content"
            staged_site = root / "run/site"
            staged_audit = root / "run/audit.json"
            prepare_staged_content(content, staged_content)
            write_content_library(staged_content, count=2)
            staged_site.mkdir(parents=True)
            (staged_site / "index.html").write_text("new site", encoding="utf-8")
            staged_audit.write_text("new audit", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                publish_staged_generation(
                    content, staged_content, site, staged_site, audit, staged_audit,
                    fail_after_content=True,
                )
            self.assertEqual((site / "index.html").read_text(encoding="utf-8"), "old site")
            self.assertEqual(audit.read_text(encoding="utf-8"), "old audit")
            self.assertEqual(len(list((content / "items/2026-07-10").glob("*.json"))), 1)
            restored = next((content / "items/2026-07-10").glob("*.json")).read_text(encoding="utf-8")
            self.assertIn("第 1 篇摘要", restored)
```

Add the disk fixture helper used by the build tests:

```python
# tests/radar_fixtures.py
import json
import shutil
from pathlib import Path


def write_content_library(root: Path, count: int, include_weekly_fixture: bool = False):
    from scripts.radar_indexes import build_indexes
    items = [stored_item(index, category="民生") for index in range(1, count + 1)]
    for item in items:
        path = root / "items" / item["published_date"] / f"{item['item_id']}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.tmp")
        temporary.write_text(json.dumps(item, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)
    for relative, payload in build_indexes(items, "2026-07-10").items():
        path = root / "indexes" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)
    if include_weekly_fixture:
        fixture = Path(__file__).resolve().parents[1] / "scripts" / "fixtures" / "weekly-valid.json"
        target = root / "weekly" / "2026-W28.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(fixture, target)
    return items
```

- [ ] **Step 2: Run the site-build tests and verify failure**

Run: `python3 -m unittest tests.test_radar_site_build -v`

Expected: failure because `build_site` does not yet stage or generate every route.

- [ ] **Step 3: Implement complete staging and safe replacement**

Use sibling paths `.<site-name>.radar-staging` and `.<site-name>.radar-backup`. Build every route and copy static assets into staging, run `validate_internal_links(staging)`, then perform:

```python
def _replace_site(staging: Path, site_root: Path) -> None:
    backup = site_root.with_name(f".{site_root.name}.radar-backup")
    if backup.exists():
        shutil.rmtree(backup)
    had_site = site_root.exists()
    if had_site:
        site_root.replace(backup)
    try:
        staging.replace(site_root)
    except Exception:
        if had_site and backup.exists() and not site_root.exists():
            backup.replace(site_root)
        raise
    else:
        if backup.exists():
            shutil.rmtree(backup)
```

The internal-link validator must parse local `href` attributes with `html.parser.HTMLParser`, ignore external URLs and fragments, map `/path/` to `site/path/index.html`, and report every missing target before replacement. During staging, load any existing `content/weekly/*.json` files and call the existing `render_site.render_weekly` function to preserve `/weekly/<week>/` and `/weekly/`; radar pages remain the root and category experience.

Implement `prepare_staged_content` by recreating the generated staging root and copying `items`, `indexes`, and `weekly`. Use `os.link` as `copytree(copy_function=...)` when source and staging share a filesystem, with `shutil.copy2` fallback, so a large immutable library is not duplicated on every run. Atomic item replacement inside the staged tree must not mutate hard-linked canonical files.

Implement `publish_staged_generation` as one rollback journal covering canonical `content/items`, `content/indexes`, `site`, and the audit file. Rename each existing target to a generated backup, rename staged targets into place, and restore every backup in reverse order on any exception. Delete backups only after every swap succeeds. `fail_after_content` is a test-only keyword that raises after both content directories are swapped but before site/audit publication.

- [ ] **Step 4: Run atomic-build and renderer tests**

Run: `python3 -m unittest tests.test_radar_site_build tests.test_radar_transaction tests.test_radar_render -v`

Expected: all tests pass and no staging/backup directory remains after success.

- [ ] **Step 5: Ignore generated staging paths and commit**

Add these exact patterns to `.gitignore`:

```gitignore
.site.radar-staging/
.site.radar-backup/
content/.items.radar-backup/
content/.indexes.radar-backup/
data/tmp/radar-*/
```

Then commit:

```bash
git add scripts/radar_render.py scripts/radar_transaction.py tests/test_radar_site_build.py tests/test_radar_transaction.py tests/radar_fixtures.py .gitignore
git commit -m "feat: build radar site atomically"
```

---

### Task 8: Resumable Scheduled Pipeline Entrypoint and Operations Documentation

**Files:**
- Create: `scripts/run_radar_pipeline.sh`
- Create: `tests/test_radar_pipeline_cli.py`
- Modify: `scripts/preview.py`
- Modify: `README.md`
- Modify: `docs/codex-digest-generation.md`

**Interfaces:**
- Consumes: optional positional `YYYY-MM-DD`, optional `HNDAILY_RAW_JSON`, and the existing `HNDAILY_SKILL_DIR`/`HNDAILY_WEB_DIR` overrides.
- Produces: first-pass model handoff with exit code `2` and `STATUS=MODEL_OUTPUT_REQUIRED`; resumed completed run with exit code `0` and `STATUS=COMPLETE`.

- [ ] **Step 1: Write failing prepare/resume CLI tests with a fake crawler**

```python
# tests/test_radar_pipeline_cli.py
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.radar_model import build_model_input
from tests.radar_fixtures import model_output_for, raw_issue

ROOT = Path(__file__).resolve().parents[1]


class RadarPipelineCliTests(unittest.TestCase):
    def test_prepare_then_resume_completes_same_date_idempotently(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            raw = work / "2026-07-09.json"
            raw.write_text(json.dumps(raw_issue(date="2026-07-09"), ensure_ascii=False), encoding="utf-8")
            env = os.environ | {
                "HNDAILY_WEB_DIR": str(ROOT), "HNDAILY_RAW_JSON": str(raw),
                "RADAR_CONTENT_ROOT": str(work / "content"),
                "RADAR_SITE_ROOT": str(work / "site"),
                "RADAR_RUN_ROOT": str(work / "run"),
                "HNDAILY_INTERMEDIATE_DIR": str(work / "intermediate"),
                "RADAR_AS_OF": "2026-07-10",
            }
            first = subprocess.run(["bash", str(ROOT / "scripts/run_radar_pipeline.sh"), "2026-07-09"], env=env, text=True, capture_output=True)
            self.assertEqual(first.returncode, 2)
            paths = dict(line.split("=", 1) for line in first.stdout.splitlines() if "=" in line)
            model_input = json.loads(Path(paths["MODEL_INPUT_JSON"]).read_text(encoding="utf-8"))
            Path(paths["MODEL_OUTPUT_JSON"]).write_text(json.dumps(model_output_for(model_input), ensure_ascii=False), encoding="utf-8")
            second = subprocess.run(["bash", str(ROOT / "scripts/run_radar_pipeline.sh"), "2026-07-09"], env=env, text=True, capture_output=True)
            third = subprocess.run(["bash", str(ROOT / "scripts/run_radar_pipeline.sh"), "2026-07-09"], env=env, text=True, capture_output=True)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(third.returncode, 0, third.stderr)
            self.assertIn("STATUS=COMPLETE", second.stdout)
            self.assertTrue((work / "site" / "index.html").is_file())
            self.assertEqual(len(list((work / "content" / "items" / "2026-07-09").glob("*.json"))), 4)
```

- [ ] **Step 2: Verify the operational test fails**

Run: `python3 -m unittest tests.test_radar_pipeline_cli -v`

Expected: `run_radar_pipeline.sh` not found.

- [ ] **Step 3: Implement the resumable entrypoint**

```bash
#!/usr/bin/env bash
set -euo pipefail

WEB_DIR="${HNDAILY_WEB_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
SKILL_DIR="${HNDAILY_SKILL_DIR:-/Users/skr/Work/hndaily/hndaily-skill}"
DATE_ARG="${1:-}"
INTERMEDIATE_DIR="${HNDAILY_INTERMEDIATE_DIR:-$WEB_DIR/data/intermediate}"
CONTENT_ROOT="${RADAR_CONTENT_ROOT:-$WEB_DIR/content}"
SITE_ROOT="${RADAR_SITE_ROOT:-$WEB_DIR/site}"
AS_OF="${RADAR_AS_OF:-$(date +%F)}"

mkdir -p "$INTERMEDIATE_DIR"
if [ -n "${HNDAILY_RAW_JSON:-}" ]; then
  RAW_JSON="$HNDAILY_RAW_JSON"
elif [ -n "$DATE_ARG" ]; then
  RAW_JSON="$(python3 "$SKILL_DIR/crawler.py" "$DATE_ARG")"
else
  RAW_JSON="$(python3 "$SKILL_DIR/crawler.py")"
fi

DATE_STEM="$(basename "$RAW_JSON" .json)"
MODEL_INPUT_JSON="$INTERMEDIATE_DIR/$DATE_STEM.radar-model-input.json"
MODEL_OUTPUT_JSON="${RADAR_MODEL_OUTPUT_JSON:-$INTERMEDIATE_DIR/$DATE_STEM.radar-model-output.json}"
PREFILTER_JSON="$INTERMEDIATE_DIR/$DATE_STEM.radar-prefilter.json"
AUDIT_JSON="$INTERMEDIATE_DIR/$DATE_STEM.radar-audit.json"
RUN_ROOT="${RADAR_RUN_ROOT:-$WEB_DIR/data/tmp/radar-$DATE_STEM}"
STAGED_CONTENT="$RUN_ROOT/content"
STAGED_SITE="$RUN_ROOT/site"
STAGED_AUDIT="$RUN_ROOT/audit.json"

python3 "$WEB_DIR/scripts/prepare_radar.py" "$RAW_JSON" "$MODEL_INPUT_JSON" "$PREFILTER_JSON" >/dev/null
printf 'RAW_JSON=%s\nMODEL_INPUT_JSON=%s\nMODEL_OUTPUT_JSON=%s\nPREFILTER_JSON=%s\nAUDIT_JSON=%s\n' \
  "$RAW_JSON" "$MODEL_INPUT_JSON" "$MODEL_OUTPUT_JSON" "$PREFILTER_JSON" "$AUDIT_JSON"

if [ ! -s "$MODEL_OUTPUT_JSON" ]; then
  echo "STATUS=MODEL_OUTPUT_REQUIRED"
  exit 2
fi

python3 "$WEB_DIR/scripts/radar_transaction.py" prepare "$CONTENT_ROOT" "$STAGED_CONTENT"
python3 "$WEB_DIR/scripts/finalize_radar.py" \
  "$RAW_JSON" "$MODEL_INPUT_JSON" "$MODEL_OUTPUT_JSON" "$STAGED_CONTENT" "$STAGED_AUDIT" "$AS_OF"
python3 "$WEB_DIR/scripts/radar_render.py" "$STAGED_CONTENT" "$STAGED_SITE"
python3 "$WEB_DIR/scripts/radar_transaction.py" publish \
  "$CONTENT_ROOT" "$STAGED_CONTENT" "$SITE_ROOT" "$STAGED_SITE" "$AUDIT_JSON" "$STAGED_AUDIT"
echo "STATUS=COMPLETE"
```

The scheduled Codex task treats exit `2` as a requested model handoff, writes only the exact model-output contract, and reruns the same command. Any other nonzero code is a failure. A failure before `publish` changes no canonical data; a failure inside `publish` invokes the coordinated rollback. Update `docs/codex-digest-generation.md` with these exact states and the model-output fields. Update `preview.py` to call `radar_render.build_site` before serving `site`.

- [ ] **Step 4: Run pipeline and complete legacy test suite**

Run: `python3 -m unittest tests.test_radar_pipeline_cli -v && python3 -m unittest discover -s tests -v`

Expected: the focused test passes and the complete suite remains green.

- [ ] **Step 5: Commit the operational entrypoint**

```bash
git add scripts/run_radar_pipeline.sh tests/test_radar_pipeline_cli.py scripts/preview.py README.md docs/codex-digest-generation.md
git commit -m "feat: add resumable radar pipeline"
```

---

### Task 9: Migrate 2026-07-08 and Prove Real 2026-07-09 Incremental Operation

**Files:**
- Create: `content/items/2026-07-08/*.json` through the pipeline
- Create: `content/items/2026-07-09/*.json` through the pipeline
- Create/Modify: `content/indexes/**/*.json` through the pipeline
- Create: `data/intermediate/2026-07-08.radar-model-output.json` locally; ignored
- Create: `data/intermediate/2026-07-09.radar-model-output.json` locally; ignored
- Modify: `tests/test_radar_real_dates.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: actual `hndaily-skill/_data/2026-07-08.json` and a fresh execution of `crawler.py 2026-07-09`.
- Produces: two-date item library, current indexes, rendered site, audit evidence, and a regression test that never substitutes 7月8日 data for 7月9日.

- [ ] **Step 1: Add a failing two-date regression test**

```python
# tests/test_radar_real_dates.py
import json
import os
import tempfile
import unittest
from pathlib import Path

from scripts.radar_render import build_site

ROOT = Path(__file__).resolve().parents[1]
SKILL_DATA = ROOT.parent / "hndaily-skill" / "_data"


class RadarRealDateTests(unittest.TestCase):
    def test_committed_two_date_library_renders_both_dates(self):
        self.assertTrue((ROOT / "content/items/2026-07-08").is_dir())
        self.assertTrue((ROOT / "content/items/2026-07-09").is_dir())
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp) / "site"
            build_site(ROOT / "content", site)
            homepage = (site / "index.html").read_text(encoding="utf-8")
            self.assertIn("2026-07-09", homepage)
            self.assertTrue((site / "date/2026-07-08/index.html").is_file())
            self.assertTrue((site / "date/2026-07-09/index.html").is_file())

    def test_local_real_0708_and_0709_sources_are_distinct(self):
        required = os.environ.get("RADAR_REAL_DATA_REQUIRED") == "1"
        paths = [SKILL_DATA / "2026-07-08.json", SKILL_DATA / "2026-07-09.json"]
        if not all(path.is_file() for path in paths):
            if required:
                self.fail("RADAR_REAL_DATA_REQUIRED=1 but a real raw date is missing")
            self.skipTest("local ignored crawler data is unavailable")
        raw_0708 = json.loads((SKILL_DATA / "2026-07-08.json").read_text(encoding="utf-8"))
        raw_0709 = json.loads((SKILL_DATA / "2026-07-09.json").read_text(encoding="utf-8"))
        self.assertEqual(raw_0708["date"], "2026-07-08")
        self.assertEqual(raw_0709["date"], "2026-07-09")
        self.assertNotEqual(
            [article["url"] for page in raw_0708["pages"] for article in page["articles"]],
            [article["url"] for page in raw_0709["pages"] for article in page["articles"]],
        )
```

- [ ] **Step 2: Run the test and verify 2026-07-09 is genuinely absent**

Run: `RADAR_REAL_DATA_REQUIRED=1 python3 -m unittest tests.test_radar_real_dates.RadarRealDateTests.test_local_real_0708_and_0709_sources_are_distinct -v`

Expected before crawl: fail because `RADAR_REAL_DATA_REQUIRED=1` makes the absent `hndaily-skill/_data/2026-07-09.json` a required real input. Without that environment variable, a fresh clone may skip only the local-raw assertion; the committed two-date library rendering test still runs.

- [ ] **Step 3: Run the real crawler for 2026-07-09**

Run: `python3 ../hndaily-skill/crawler.py 2026-07-09`

Expected: exit `0`, stdout is the absolute `_data/2026-07-09.json` path, stderr summary contains `date=2026-07-09`, a positive page count, and a positive article count. If network access is blocked by the sandbox, rerun this exact command with approved network escalation; do not fabricate the file.

Run: `RADAR_REAL_DATA_REQUIRED=1 python3 -m unittest tests.test_radar_real_dates.RadarRealDateTests.test_local_real_0708_and_0709_sources_are_distinct -v`

Expected: pass, proving the two local raw issues have different dates and URL sets.

- [ ] **Step 4: Process 2026-07-08 through the resumable entrypoint**

Run: `bash scripts/run_radar_pipeline.sh 2026-07-08`

Expected first pass: exit `2` and `STATUS=MODEL_OUTPUT_REQUIRED`. Read the emitted model input, generate every item using only its title/content and the exact radar-v3 schema, write `MODEL_OUTPUT_JSON`, then rerun the same command.

Run again: `bash scripts/run_radar_pipeline.sh 2026-07-08`

Expected: exit `0`, `STATUS=COMPLETE`, item files under `content/items/2026-07-08`, and a rendered date route.

- [ ] **Step 5: Process the freshly crawled 2026-07-09 data**

Run: `bash scripts/run_radar_pipeline.sh 2026-07-09`

Expected first pass: exit `2`. Generate the exact model output from the emitted 7月9日 input without copying any 7月8日 semantic output, then rerun.

Run again: `bash scripts/run_radar_pipeline.sh 2026-07-09`

Expected: exit `0`, `STATUS=COMPLETE`, new item files under `content/items/2026-07-09`, preserved 7月8日 files, rebuilt focus/category/opportunity indexes, and both date routes.

- [ ] **Step 6: Prove idempotence and failure preservation**

Run: `bash scripts/run_radar_pipeline.sh 2026-07-09`

Expected: exit `0`; item-file count and stable detail URLs are unchanged.

Create exact before-state checksums:

```bash
shasum site/index.html
shasum content/items/2026-07-08/*.json content/items/2026-07-09/*.json
```

Save the output, then create an invalid temporary model output without changing the canonical intermediate file:

```bash
INVALID_OUTPUT="$(mktemp /tmp/radar-invalid-0709.XXXXXX.json)"
python3 -c 'import json,sys; source,target=sys.argv[1:]; data=json.load(open(source)); data["items"].pop(); json.dump(data,open(target,"w"),ensure_ascii=False,indent=2)' data/intermediate/2026-07-09.radar-model-output.json "$INVALID_OUTPUT"
RADAR_MODEL_OUTPUT_JSON="$INVALID_OUTPUT" bash scripts/run_radar_pipeline.sh 2026-07-09
```

Expected: the last command exits nonzero. Re-run the two `shasum` commands and require byte-for-byte identical output. The invalid file is under `/tmp` and is not added to the repository.

- [ ] **Step 7: Run complete verification and visually inspect desktop/mobile pages**

Run:

```bash
python3 -m unittest discover -s tests -v
python3 scripts/radar_render.py content site
python3 -m http.server 8765 --directory site
```

Expected: all tests pass. Inspect `/`, `/category/opportunity/`, `/category/livelihood/`, both date routes, and at least one detail route at desktop and mobile widths. Confirm cards contain only source/title/summary; focus appears only on `/`; detail has two original links and escaped full body; 7月9日 is the newest date group.

- [ ] **Step 8: Update the acceptance record and commit generated canonical content**

Add to `README.md` a short “Verified datasets” record with the actual 7月8日/7月9日 page counts, article counts, selected counts, test command, and verification date. Do not commit ignored raw crawler data, intermediate model files, audit files, or `site/`.

```bash
git add content/items content/indexes tests/test_radar_real_dates.py README.md
git commit -m "test: verify radar pipeline across real dates"
```

---

## Final Verification

- [ ] Run `python3 -m unittest discover -s tests -v` and record the exact passing test count.
- [ ] Run `git status --short` and confirm no unexpected generated files are tracked.
- [ ] Run `rg -n "第[0-9]+版|最终分|confidence|海南日报精读|今日重点|当前热点" site/index.html site/category site/date` and expect no public matches.
- [ ] Run `rg -n "当下重点" site/category` and expect no matches.
- [ ] Run the internal-link validator and expect an empty error list.
- [ ] Re-run `bash scripts/run_radar_pipeline.sh 2026-07-09` and expect `STATUS=COMPLETE` with no item-count change.
- [ ] Record the final test count, 7月9日 crawler counts, selected counts, and visual routes in the completion handoff.
