# 海南日报现代读报核心 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将当前以评分和精选为中心的公开站点改造成完整展示当天有效文章、复用唯一 AI 摘要并提供原始正文详情的现代读报首页。

**Architecture:** 继续使用现有 Python 静态生成和原子发布架构，把已经覆盖全量候选的 `content/issue-items/` 提升为公开文章事实来源，把 `content/issues/` 作为版面和顺序来源。模型只生成唯一摘要及后续人物、地图会复用的后台实体证据；确定性脚本负责全量发布、索引、页面顺序和降级，公开页面不再依赖评分、精选、推荐理由或人工标注。

**Tech Stack:** Python 3 标准库、`unittest`、`string.Template`、原生 JavaScript、HTML/CSS、Shell、静态 JSON。

## Global Constraints

- 视觉必须沿用当前 `main` 分支基于 AI Hot 参考形成的侧栏、信息密度、颜色、字体层级、亮暗主题和 `760px` 响应式断点。
- 首期信源只有海南日报，页面文案不能暗示覆盖全海南所有信源。
- 当天所有通过高置信过滤的有效文章都公开，默认按版面号和版内顺序排列。
- 首页文章块只显示完整原始标题和唯一 AI 摘要；不显示版面、日期、作者、人物、地点、机构、分类、推荐理由、评分、排名或收藏操作。
- 标题不得使用行数截断或省略号；桌面和移动端都必须显示摘要。
- 首页、详情、搜索索引共用同一个 `ai_summary`；摘要可以为 `null`，页面统一降级为“摘要待生成”。
- 详情页显示同一摘要、抓取保存的完整正文、来源信息、海南日报原文链接和同一期上一篇/下一篇。
- `fetch_error`、`empty_content`、导读、理论周刊和公益广告页继续作为高置信排除项留在预过滤审计中，不进入“有效文章”数量。
- 模型不决定是否公开，不返回分类、评分、推荐理由、机会生命周期或最终排名。
- 人物、地点和动作仍可作为后台字段生成，但阶段一不得显示在首页。
- 不合并 `feature/human-feedback-review`，也不把内部复核后台作为本计划依赖。
- 继续使用临时目录构建和原子替换；单篇摘要为空不能阻断整期发布，结构无效或候选错位必须阻断发布。
- 本计划只实现设计文档的阶段一。预告、人物、地图、公共资源和政策分别使用独立实施计划。

---

## Program Split

本计划完成后，按以下顺序另行编写并执行独立计划：

1. `2026-07-16-upcoming-events-implementation.md`
2. `2026-07-16-person-timeline-implementation.md`
3. `2026-07-16-location-heatmap-implementation.md`
4. `2026-07-16-public-resources-implementation.md`
5. `2026-07-16-policy-framework-implementation.md`

后续页面在完成前不进入主导航，不生成空白占位页。

## File Map

### Data and model boundary

- Modify `scripts/radar_contract.py`: define reader schema v6, source candidate fields, all-article contract, and remove selected-item requirements from the new public path.
- Modify `scripts/radar_adapter.py`: propagate `author` from the crawler record.
- Modify `scripts/radar_model.py`: accept only summary and evidence-backed entity fields.
- Modify `tests/radar_fixtures.py`: produce reader-v1 model output, reader articles, and reader issues.
- Modify `tests/test_radar_adapter.py`: verify author propagation.
- Modify `tests/test_radar_model.py`: verify the reduced model contract and nullable summary degradation.

### Generation and persistence

- Modify `scripts/radar_issue.py`: build ordered issues and all reader articles without scoring input.
- Modify `scripts/finalize_radar.py`: remove scoring and selection from the publication path.
- Modify `scripts/radar_indexes.py`: replace selected feeds and category indexes with reader feeds, issue-date manifest, and reader search index.
- Modify `scripts/radar_store.py`: atomically commit issues, issue-items, and reader indexes without requiring selected items.
- Modify `scripts/radar_transaction.py`: publish the reader families and keep legacy selected data out of the active build dependency.
- Modify `tests/test_radar_issue.py`, `tests/test_radar_indexes.py`, `tests/test_radar_store.py`, `tests/test_radar_transaction.py`, and `tests/test_finalize_radar.py`.

### Rendering and interaction

- Create `src/templates/reader-index.html`: modern reader homepage shell.
- Modify `src/templates/radar-item.html`: source metadata, one summary, body, original link, previous/next navigation.
- Modify `scripts/radar_render.py`: render the latest full issue as `/`, render all article details from issue-items, and stop rendering selected/category/focus routes.
- Modify `src/static/app.js`: retain theme behavior and replace selected-feed logic with current-issue search.
- Modify `src/static/styles.css`: reuse current AI Hot tokens while introducing reader-only rows and removing public scoring/reason/entity presentation.
- Modify `tests/test_radar_render.py`, `tests/test_radar_site_build.py`, and `tests/test_selected_home_js.py`; rename the latter to `tests/test_reader_home_js.py`.

### Migration and documentation

- Create `scripts/migrate_reader_content.py`: migrate committed issue and issue-item JSON to schema v6 and rebuild reader indexes.
- Modify committed `content/issues/*.json`, `content/issue-items/*/*.json`, and `content/indexes/` through the migration command.
- Modify `docs/codex-digest-generation.md` and `README.md`.
- Modify `tests/test_radar_pipeline_cli.py` and `tests/test_radar_real_dates.py`.

---

### Task 1: Reduce the model and article contracts to reader-v1

**Files:**
- Modify: `scripts/radar_contract.py`
- Modify: `scripts/radar_adapter.py`
- Modify: `scripts/radar_model.py`
- Modify: `tests/radar_fixtures.py`
- Modify: `tests/test_radar_adapter.py`
- Modify: `tests/test_radar_model.py`

**Interfaces:**
- Consumes: crawler article fields `title`, `url`, `author`, `content`, and page metadata.
- Produces: `build_model_input(candidates: list[dict]) -> dict`, `validate_model_output(model_input: dict, model_output: dict, candidates: list[dict]) -> list[dict]`, and source candidates with `author: str`.
- Produces model item fields exactly: `candidate_id`, `ai_summary`, `actors`, `location_mentions`, `action`, `action_evidence`.

- [ ] **Step 1: Write failing tests for the reduced model envelope and author propagation**

Add these test methods:

```python
def test_adapts_author_for_reader_detail(self):
    candidates, _ = adapt_hndaily(raw_issue())
    self.assertEqual(candidates[0]["author"], "记者")

def test_accepts_reader_output_without_scoring_or_recommendation(self):
    candidates, _ = adapt_hndaily(raw_issue(article_count=1))
    model_input = build_model_input(candidates)
    output = model_output_for(model_input)
    self.assertEqual(
        set(output["items"][0]),
        {
            "candidate_id",
            "ai_summary",
            "actors",
            "location_mentions",
            "action",
            "action_evidence",
        },
    )
    self.assertEqual(
        validate_model_output(model_input, output, candidates),
        output["items"],
    )

def test_accepts_null_summary_as_per_article_degradation(self):
    candidates, _ = adapt_hndaily(raw_issue(article_count=1))
    model_input = build_model_input(candidates)
    output = model_output_for(model_input)
    output["items"][0]["ai_summary"] = None
    validated = validate_model_output(model_input, output, candidates)
    self.assertIsNone(validated[0]["ai_summary"])

def test_rejects_removed_recommendation_field(self):
    candidates, _ = adapt_hndaily(raw_issue(article_count=1))
    model_input = build_model_input(candidates)
    output = model_output_for(model_input)
    output["items"][0]["recommendation_reason"] = "不应再出现"
    with self.assertRaisesRegex(ModelOutputError, "unknown fields"):
        validate_model_output(model_input, output, candidates)
```

- [ ] **Step 2: Run the focused tests and verify they fail for the old contract**

Run:

```bash
python3 -m unittest \
  tests.test_radar_adapter.RadarAdapterTests.test_adapts_author_for_reader_detail \
  tests.test_radar_model.RadarModelTests.test_accepts_reader_output_without_scoring_or_recommendation \
  tests.test_radar_model.RadarModelTests.test_accepts_null_summary_as_per_article_degradation \
  tests.test_radar_model.RadarModelTests.test_rejects_removed_recommendation_field -v
```

Expected: FAIL because `author` is absent, the old model contract requires recommendation/category/scores, and `ai_summary=None` is rejected.

- [ ] **Step 3: Implement reader schema v6 and the exact reduced fields**

In `scripts/radar_contract.py`, set the version and candidate fields:

```python
SCHEMA_VERSION = 6
PROMPT_VERSION = "reader-v1"

SOURCE_CANDIDATE_FIELDS = {
    "candidate_id",
    "item_id",
    "source",
    "title",
    "author",
    "content",
    "original_url",
    "published_date",
    "collected_date",
    "page_number",
    "page_name",
    "page_url",
    "pdf_url",
    "page_sequence",
}
```

Require all existing trusted fields, but allow `author` to be an empty string:

```python
if not isinstance(candidate.get("author"), str):
    raise ContractError("source candidate.author must be a string")
```

In `scripts/radar_adapter.py`, add the exact field:

```python
"author": record["author"].strip(),
```

In `scripts/radar_model.py`, replace `MODEL_ITEM_FIELDS` with:

```python
MODEL_ITEM_FIELDS = {
    "candidate_id",
    "ai_summary",
    "actors",
    "location_mentions",
    "action",
    "action_evidence",
}
```

Validate summary without making a failed summary abort the issue:

```python
summary = item.get("ai_summary")
if summary is not None:
    if not non_empty(summary):
        raise ModelOutputError(f"items[{index}].ai_summary must be null or non-empty")
    if normalized_text(summary) == normalized_text(candidate["title"]):
        raise ModelOutputError(f"items[{index}].ai_summary must differ from title")
```

Keep the existing actor, location and action evidence validation. Delete category, score, score-reason, recommendation-reason and opportunity validation from this model path.

Replace `model_output_for()` in `tests/radar_fixtures.py` with:

```python
def model_output_for(model_input):
    return {
        "schema_version": model_input["schema_version"],
        "prompt_version": model_input["prompt_version"],
        "input_fingerprint": model_input["input_fingerprint"],
        "items": [
            {
                "candidate_id": item["candidate_id"],
                "ai_summary": f'{item["title"]}的正文事实摘要。',
                "actors": [],
                "location_mentions": [],
                "action": "",
                "action_evidence": "",
            }
            for item in model_input["items"]
        ],
    }
```

- [ ] **Step 4: Run the model and adapter suites**

Run:

```bash
python3 -m unittest tests.test_radar_adapter tests.test_radar_model -v
```

Expected: PASS with all adapter and model contract tests green.

- [ ] **Step 5: Commit the reader contract**

```bash
git add scripts/radar_contract.py scripts/radar_adapter.py scripts/radar_model.py tests/radar_fixtures.py tests/test_radar_adapter.py tests/test_radar_model.py
git commit -m "refactor: define reader model contract"
```

---

### Task 2: Build every valid article without scoring or selection

**Files:**
- Modify: `scripts/radar_issue.py`
- Modify: `scripts/finalize_radar.py`
- Modify: `tests/test_radar_issue.py`
- Modify: `tests/test_finalize_radar.py`

**Interfaces:**
- Consumes: ordered candidates and validated reader-v1 semantic items from Task 1.
- Produces: `build_public_issue(raw: dict, candidates: list[dict], semantic_items: list[dict]) -> tuple[dict, list[dict]]`.
- Produces: `build_generation(raw: dict, model_input: dict, model_output: dict) -> tuple[dict, list[dict], dict]`, returning issue, all articles, and audit.

- [ ] **Step 1: Write failing all-article generation tests**

Add these assertions to `tests/test_radar_issue.py` and `tests/test_finalize_radar.py`:

```python
def test_builds_every_candidate_in_page_order_without_scores(self):
    raw = raw_issue(article_count=4)
    candidates, _ = adapt_hndaily(raw)
    model_input = build_model_input(candidates)
    semantic = model_output_for(model_input)["items"]
    issue, articles = build_public_issue(raw, candidates, semantic)
    self.assertEqual(issue["article_count"], 4)
    self.assertEqual(
        [row["page_sequence"] for row in articles],
        [1, 2, 3, 4],
    )
    self.assertTrue(all("semantic_scores" not in row for row in articles))
    self.assertTrue(all("recommendation_reason" not in row["block"] for row in articles))

def test_null_summary_is_published_as_pending_article(self):
    raw = raw_issue(article_count=2)
    candidates, _ = adapt_hndaily(raw)
    model_input = build_model_input(candidates)
    model_output = model_output_for(model_input)
    model_output["items"][1]["ai_summary"] = None
    issue, articles, audit = build_generation(raw, model_input, model_output)
    self.assertEqual(issue["article_count"], 2)
    self.assertIsNone(articles[1]["block"]["ai_summary"])
    self.assertEqual(audit["summary_pending_count"], 1)
    self.assertEqual(audit["published_count"], 2)
```

- [ ] **Step 2: Run the focused tests and verify the scoring dependency fails them**

Run:

```bash
python3 -m unittest tests.test_radar_issue tests.test_finalize_radar -v
```

Expected: FAIL because `build_public_issue()` still requires scored input, issue count is named `scored_article_count`, and `build_generation()` returns selected items.

- [ ] **Step 3: Define the reader article and issue fields**

In `scripts/radar_issue.py`, use these exact field sets:

```python
ISSUE_FIELDS = {
    "schema_version",
    "date",
    "source",
    "page_count",
    "article_count",
    "pages",
}
ISSUE_ITEM_FIELDS = {
    "schema_version",
    "item_id",
    "published_date",
    "collected_date",
    "page_number",
    "page_name",
    "page_sequence",
    "author",
    "entities",
    "block",
}
```

Allow `block.ai_summary` to be `None` or a non-empty string, and validate `author` as a string. Store background entities in the article but not in the issue article reference.

Replace `build_public_issue()` with this signature and behavior:

```python
def build_public_issue(raw, candidates, semantic_items):
    if len(candidates) != len(semantic_items):
        raise ContractError("public issue candidate alignment mismatch")
    pages = {
        page["page"]: {
            "page_number": page["page"],
            "page_name": page["page_name"],
            "page_url": page["page_url"],
            "pdf_url": page["pdf_url"],
            "articles": [],
        }
        for page in raw["pages"]
    }
    articles = []
    catalog = load_location_catalog()
    for candidate, semantic in zip(candidates, semantic_items):
        detail_path = f'/items/{candidate["published_date"]}/{candidate["item_id"]}/'
        pages[candidate["page_number"]]["articles"].append(
            {
                "item_id": candidate["item_id"],
                "title": candidate["title"],
                "page_sequence": candidate["page_sequence"],
                "detail_path": detail_path,
            }
        )
        articles.append(
            {
                "schema_version": SCHEMA_VERSION,
                "item_id": candidate["item_id"],
                "published_date": candidate["published_date"],
                "collected_date": candidate["collected_date"],
                "page_number": candidate["page_number"],
                "page_name": candidate["page_name"],
                "page_sequence": candidate["page_sequence"],
                "author": candidate["author"],
                "entities": {
                    "actors": semantic["actors"],
                    "locations": resolve_location_mentions(
                        semantic["location_mentions"],
                        find_location_candidates(
                            candidate["title"], candidate["content"], catalog
                        ),
                        catalog,
                    ),
                    "action": semantic["action"].strip(),
                    "action_evidence": semantic["action_evidence"].strip(),
                },
                "block": {
                    "source": candidate["source"],
                    "title": candidate["title"],
                    "content": candidate["content"],
                    "ai_summary": (
                        semantic["ai_summary"].strip()
                        if semantic["ai_summary"] is not None
                        else None
                    ),
                    "original_url": candidate["original_url"],
                },
            }
        )
    for page in pages.values():
        page["articles"].sort(key=lambda article: article["page_sequence"])
    issue = {
        "schema_version": SCHEMA_VERSION,
        "date": raw["date"],
        "source": raw["source"],
        "page_count": len(raw["pages"]),
        "article_count": len(candidates),
        "pages": [pages[key] for key in sorted(pages)],
    }
    validate_public_issue(issue)
    for article in articles:
        validate_public_issue_item(article)
    return issue, articles
```

Add the required imports from `scripts.radar_locations`.

Update the reader fixtures in `tests/radar_fixtures.py` with:

```python
def public_issue(count=1, date="2026-07-10"):
    articles = [public_issue_item(index, date=date) for index in range(1, count + 1)]
    return {
        "schema_version": 6,
        "date": date,
        "source": "海南日报",
        "page_count": 1,
        "article_count": count,
        "pages": [
            {
                "page_number": "001",
                "page_name": "头版",
                "page_url": "https://example.test/page-001",
                "pdf_url": "https://example.test/page-001.pdf",
                "articles": [
                    {
                        "item_id": article["item_id"],
                        "title": article["block"]["title"],
                        "page_sequence": article["page_sequence"],
                        "detail_path": f'/items/{date}/{article["item_id"]}/',
                    }
                    for article in articles
                ],
            }
        ],
    }


def public_issue_item(index, date="2026-07-10", title=None):
    return {
        "schema_version": 6,
        "item_id": f"issue-{index:03d}",
        "published_date": date,
        "collected_date": date,
        "page_number": "001",
        "page_name": "头版",
        "page_sequence": index,
        "author": "记者",
        "entities": {
            "actors": [],
            "locations": [],
            "action": "",
            "action_evidence": "",
        },
        "block": {
            "source": "海南日报",
            "title": title or f"全部标题 {index}",
            "content": f"全部正文 {index}",
            "ai_summary": f"摘要 {index}",
            "original_url": f"https://example.test/issues/{index}",
        },
    }
```

- [ ] **Step 4: Remove scoring and selection from generation**

In `scripts/finalize_radar.py`, remove imports of `score_semantic`, `select_items`, `build_indexes`, and selected-item store helpers. Implement the generation function as:

```python
def build_generation(raw, model_input, model_output):
    candidates, prefilter = adapt_hndaily(raw)
    expected_input = build_model_input(candidates)
    if model_input != expected_input:
        raise FinalizeError("model input does not match adapted raw candidates")
    semantic_items = validate_model_output(model_input, model_output, candidates)
    issue, articles = build_public_issue(raw, candidates, semantic_items)
    audit = {
        "schema_version": SCHEMA_VERSION,
        "published_date": raw["date"],
        "input_fingerprint": model_input["input_fingerprint"],
        "candidate_count": len(candidates),
        "published_count": len(articles),
        "summary_pending_count": sum(
            article["block"]["ai_summary"] is None for article in articles
        ),
        "prefilter": prefilter,
    }
    return issue, articles, audit
```

Delete `build_items()` because it preserves the selected-only abstraction.

- [ ] **Step 5: Run issue and finalization tests**

Run:

```bash
python3 -m unittest tests.test_radar_issue tests.test_finalize_radar -v
```

Expected: PASS; no test imports scoring or selection in the reader generation path.

- [ ] **Step 6: Commit all-article generation**

```bash
git add scripts/radar_issue.py scripts/finalize_radar.py tests/test_radar_issue.py tests/test_finalize_radar.py
git commit -m "refactor: publish every valid reader article"
```

---

### Task 3: Replace selected indexes with reader indexes and atomic reader storage

**Files:**
- Modify: `scripts/radar_indexes.py`
- Modify: `scripts/radar_store.py`
- Modify: `scripts/radar_transaction.py`
- Modify: `scripts/finalize_radar.py`
- Modify: `tests/test_radar_indexes.py`
- Modify: `tests/test_radar_store.py`
- Modify: `tests/test_radar_transaction.py`

**Interfaces:**
- Consumes: validated issues and reader articles from Task 2.
- Produces: `build_reader_indexes(issues: list[dict], articles: list[dict]) -> dict[str, dict]`.
- Produces: `commit_reader_generation(content_root: Path, indexes: dict, affected_dates: set[str], issues: list[dict], articles: list[dict]) -> None`.
- Reader index files: `reader.json`, `reader-feed/YYYY-MM-DD.json`, `search-reader.json`, and `issues.json`.

- [ ] **Step 1: Write failing reader index tests**

Replace selected-index assertions with:

```python
def test_builds_reader_feed_in_page_order_without_selected_fields(self):
    issue = public_issue(count=3)
    articles = [public_issue_item(3), public_issue_item(1), public_issue_item(2)]
    payloads = build_reader_indexes([issue], articles)
    feed = payloads["reader-feed/2026-07-10.json"]
    self.assertEqual(feed["date"], "2026-07-10")
    self.assertEqual(feed["count"], 3)
    self.assertEqual(
        [item["item_id"] for item in feed["items"]],
        ["issue-001", "issue-002", "issue-003"],
    )
    self.assertEqual(
        set(feed["items"][0]),
        {
            "item_id",
            "published_date",
            "page_number",
            "page_name",
            "page_sequence",
            "title",
            "ai_summary",
            "detail_path",
        },
    )

def test_reader_manifest_points_to_latest_complete_issue(self):
    payloads = build_reader_indexes(
        [public_issue(date="2026-07-09"), public_issue(date="2026-07-10")],
        [public_issue_item(1, date="2026-07-09"), public_issue_item(1)],
    )
    self.assertEqual(payloads["reader.json"]["latest_date"], "2026-07-10")
    self.assertEqual(
        payloads["reader.json"]["dates"],
        ["2026-07-10", "2026-07-09"],
    )
```

Add an atomic storage test:

```python
def test_reader_commit_replaces_one_date_and_indexes_atomically(self):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        issue = public_issue(count=2)
        articles = [public_issue_item(1), public_issue_item(2)]
        indexes = build_reader_indexes([issue], articles)
        commit_reader_generation(
            root,
            indexes,
            {"2026-07-10"},
            issues=[issue],
            articles=articles,
        )
        self.assertEqual(len(list((root / "issue-items/2026-07-10").glob("*.json"))), 2)
        self.assertTrue((root / "indexes/reader.json").is_file())
        self.assertFalse((root / "indexes/focus.json").exists())
```

- [ ] **Step 2: Run the index and store tests to verify failure**

Run:

```bash
python3 -m unittest tests.test_radar_indexes tests.test_radar_store tests.test_radar_transaction -v
```

Expected: FAIL because reader index and commit functions do not exist and storage still requires selected items.

- [ ] **Step 3: Implement deterministic reader indexes**

Replace selected index construction in `scripts/radar_indexes.py` with:

```python
def _reader_summary(article):
    return {
        "item_id": article["item_id"],
        "published_date": article["published_date"],
        "page_number": article["page_number"],
        "page_name": article["page_name"],
        "page_sequence": article["page_sequence"],
        "title": article["block"]["title"],
        "ai_summary": article["block"]["ai_summary"],
        "detail_path": f'/items/{article["published_date"]}/{article["item_id"]}/',
    }


def build_reader_indexes(issues, articles):
    for issue in issues:
        validate_public_issue(issue)
    for article in articles:
        validate_public_issue_item(article)
    dates = sorted({issue["date"] for issue in issues}, reverse=True)
    payloads = {
        "reader.json": {
            "latest_date": dates[0] if dates else None,
            "dates": dates,
            "feeds": [f"/static/reader-feed/{value}.json" for value in dates],
        },
        "issues.json": {
            "latest_date": dates[0] if dates else None,
            "dates": dates,
        },
    }
    ordered = sorted(
        articles,
        key=lambda article: (
            article["published_date"],
            article["page_number"],
            article["page_sequence"],
            article["item_id"],
        ),
    )
    payloads["search-reader.json"] = {
        "items": [_reader_summary(article) for article in ordered]
    }
    for published_date in dates:
        rows = [
            _reader_summary(article)
            for article in ordered
            if article["published_date"] == published_date
        ]
        payloads[f"reader-feed/{published_date}.json"] = {
            "date": published_date,
            "count": len(rows),
            "items": rows,
        }
    return payloads
```

- [ ] **Step 4: Implement reader-only atomic storage**

In `scripts/radar_store.py`, add:

```python
def commit_reader_generation(
    content_root,
    indexes,
    affected_dates,
    *,
    issues,
    articles,
    fail_after_articles=False,
):
    content_root = Path(content_root)
    for issue in issues:
        validate_public_issue(issue)
    for article in articles:
        validate_public_issue_item(article)
    ids = [article["item_id"] for article in articles]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate item_id in reader library")
    staging = content_root / ".reader-store-staging"
    if staging.exists():
        shutil.rmtree(staging)
    for published_date in affected_dates:
        date_dir = staging / "issue-items" / published_date
        date_dir.mkdir(parents=True, exist_ok=True)
        for article in articles:
            if article["published_date"] == published_date:
                _write_json(date_dir / f'{article["item_id"]}.json', article)
    for issue in issues:
        _write_json(staging / "issues" / f'{issue["date"]}.json', issue)
    for relative, payload in indexes.items():
        _write_json(staging / "indexes" / relative, payload)
    _swap_reader_staging(
        content_root,
        staging,
        affected_dates,
        fail_after_articles=fail_after_articles,
    )
```

Implement the rollback helper exactly as:

```python
def _replace_path(target, staged, backup, swaps):
    target.parent.mkdir(parents=True, exist_ok=True)
    if backup.exists():
        shutil.rmtree(backup) if backup.is_dir() else backup.unlink()
    had_target = target.exists()
    if had_target:
        target.replace(backup)
    staged.replace(target)
    swaps.append((target, backup, had_target))


def _swap_reader_staging(
    content_root,
    staging,
    affected_dates,
    *,
    fail_after_articles=False,
):
    swaps = []
    try:
        for published_date in sorted(affected_dates):
            _replace_path(
                content_root / "issue-items" / published_date,
                staging / "issue-items" / published_date,
                content_root / "issue-items" / f".{published_date}.reader-backup",
                swaps,
            )
        if fail_after_articles:
            raise RuntimeError("injected failure after reader article swaps")
        for published_date in sorted(affected_dates):
            _replace_path(
                content_root / "issues" / f"{published_date}.json",
                staging / "issues" / f"{published_date}.json",
                content_root / "issues" / f".{published_date}.reader-backup.json",
                swaps,
            )
        _replace_path(
            content_root / "indexes",
            staging / "indexes",
            content_root / ".indexes.reader-backup",
            swaps,
        )
    except Exception:
        for target, backup, had_target in reversed(swaps):
            if target.exists():
                shutil.rmtree(target) if target.is_dir() else target.unlink()
            if had_target and backup.exists():
                backup.replace(target)
        raise
    else:
        for _target, backup, _had_target in swaps:
            if backup.exists():
                shutil.rmtree(backup) if backup.is_dir() else backup.unlink()
    finally:
        if staging.exists():
            shutil.rmtree(staging)
```

Update `scripts/radar_transaction.py` so active publication entries are exactly:

```python
entries = [
    (content_root / "issue-items", staged_content / "issue-items"),
    (content_root / "issues", staged_content / "issues"),
    (content_root / "indexes", staged_content / "indexes"),
    (site_root, staged_site),
    (audit_path, staged_audit),
]
```

Keep copying legacy `items` into staging only until the migration task proves the public build no longer reads it; do not publish or overwrite it in this reader transaction.

- [ ] **Step 5: Wire finalization to reader storage**

In `finalize_to_store()`, merge existing issues and issue-items by publication date, build reader indexes, and call:

```python
indexes = build_reader_indexes(merged_issues, merged_articles)
commit_reader_generation(
    content_root,
    indexes,
    {published_date},
    issues=[issue],
    articles=articles,
)
```

The merged article uniqueness check must use `item_id`. Remove replacement audit fields that compare old and new scores.

- [ ] **Step 6: Run index, storage, transaction, and finalization tests**

Run:

```bash
python3 -m unittest \
  tests.test_radar_indexes \
  tests.test_radar_store \
  tests.test_radar_transaction \
  tests.test_finalize_radar -v
```

Expected: PASS, including injected-failure rollback tests.

- [ ] **Step 7: Commit reader persistence**

```bash
git add scripts/radar_indexes.py scripts/radar_store.py scripts/radar_transaction.py scripts/finalize_radar.py tests/test_radar_indexes.py tests/test_radar_store.py tests/test_radar_transaction.py tests/test_finalize_radar.py
git commit -m "refactor: store reader issues atomically"
```

---

### Task 4: Render the latest complete issue as the homepage

**Files:**
- Create: `src/templates/reader-index.html`
- Modify: `scripts/radar_render.py`
- Modify: `tests/test_radar_render.py`

**Interfaces:**
- Consumes: one validated issue, its ordered article objects, and `reader.json`.
- Produces: `render_reader_home(issue: dict, articles: list[dict], manifest: dict) -> str`.
- Produces homepage row markup with only `.reader-title` and `.reader-summary` inside the article link.

- [ ] **Step 1: Write failing homepage markup tests**

Add:

```python
def test_reader_home_renders_every_title_and_summary_in_issue_order(self):
    issue = public_issue(count=3)
    articles = [public_issue_item(3), public_issue_item(1), public_issue_item(2)]
    rendered = render_reader_home(
        issue,
        articles,
        {"latest_date": "2026-07-10", "dates": ["2026-07-10"]},
    )
    self.assertEqual(rendered.count('class="reader-story"'), 3)
    self.assertLess(rendered.index("全部标题 1"), rendered.index("全部标题 2"))
    self.assertLess(rendered.index("全部标题 2"), rendered.index("全部标题 3"))
    self.assertIn('class="reader-title"', rendered)
    self.assertIn('class="reader-summary"', rendered)
    self.assertNotIn("推荐理由", rendered)
    self.assertNotIn("最终分", rendered)
    self.assertNotIn("story-entities", rendered)
    self.assertNotIn("bookmark-button", rendered)

def test_reader_home_uses_pending_copy_for_null_summary(self):
    issue = public_issue(count=1)
    article = public_issue_item(1)
    article["block"]["ai_summary"] = None
    rendered = render_reader_home(
        issue,
        [article],
        {"latest_date": "2026-07-10", "dates": ["2026-07-10"]},
    )
    self.assertIn("摘要待生成", rendered)
```

- [ ] **Step 2: Run the rendering tests and verify failure**

Run:

```bash
python3 -m unittest tests.test_radar_render -v
```

Expected: FAIL because `render_reader_home()` and `reader-index.html` do not exist.

- [ ] **Step 3: Create the reader homepage template**

Create `src/templates/reader-index.html` with:

```html
<div class="app-shell radar-shell">
  $nav
  <main class="content-shell radar-content" data-reader-home>
    <header class="reader-header">
      <div class="reader-date">$date_heading</div>
      <form class="reader-search" data-reader-search>
        <label class="sr-only" for="reader-search">搜索当天标题和摘要</label>
        <input id="reader-search" type="search" placeholder="搜索当天标题和摘要…">
        <button class="search-submit" type="submit">搜索</button>
      </form>
    </header>
    <nav class="reader-date-nav" aria-label="读报日期">$date_navigation</nav>
    <div class="reader-pages" data-reader-pages>$page_groups</div>
    <p class="empty-state" data-reader-empty hidden>没有匹配结果</p>
  </main>
</div>
```

- [ ] **Step 4: Implement reader row and page-group rendering**

In `scripts/radar_render.py`, add:

```python
def _reader_row(article):
    block = article["block"]
    summary = block["ai_summary"] or "摘要待生成"
    search_text = html.escape(
        f'{block["title"]} {summary}'.lower(), quote=True
    )
    detail_path = f'/items/{article["published_date"]}/{article["item_id"]}/'
    return (
        f'<article class="reader-story" data-reader-story data-search-text="{search_text}">'
        f'<a class="reader-story-link" href="{html.escape(detail_path, quote=True)}">'
        f'<h3 class="reader-title">{html.escape(block["title"])}</h3>'
        f'<p class="reader-summary">{html.escape(summary)}</p>'
        '</a></article>'
    )


def render_reader_home(issue, articles, manifest):
    validate_public_issue(issue)
    by_id = {article["item_id"]: article for article in articles}
    groups = []
    for page in issue["pages"]:
        rows = [
            _reader_row(by_id[reference["item_id"]])
            for reference in page["articles"]
        ]
        if not rows:
            continue
        groups.append(
            '<section class="reader-page">'
            f'<header class="reader-page-heading"><h2>第{html.escape(page["page_number"])}版 · {html.escape(page["page_name"])}</h2>'
            f'<span>{len(rows)} 篇</span></header>'
            f'<div class="reader-list">{"".join(rows)}</div></section>'
        )
    parsed = date.fromisoformat(issue["date"])
    date_heading = (
        f'<strong>{parsed.month}月{parsed.day}日</strong>'
        f'<span>{issue["article_count"]} 篇</span>'
    )
    date_navigation = "".join(
        f'<a href="/all/{value}/">{html.escape(value)}</a>'
        for value in manifest["dates"]
    )
    return _template("reader-index.html").safe_substitute(
        nav=render_primary_nav("今日读报", _mobile_updated_markup(issue["date"])),
        date_heading=date_heading,
        date_navigation=date_navigation,
        page_groups="".join(groups),
    )
```

Define the helper as:

```python
def _mobile_updated_markup(value):
    return f'<span class="mobile-updated">{html.escape(_mobile_updated(value))}</span>'
```

- [ ] **Step 5: Run homepage rendering tests**

Run:

```bash
python3 -m unittest tests.test_radar_render -v
```

Expected: PASS for homepage ordering, exact visible fields, null-summary fallback, escaping, and issue-page rendering.

- [ ] **Step 6: Commit homepage rendering**

```bash
git add src/templates/reader-index.html scripts/radar_render.py tests/test_radar_render.py
git commit -m "feat: render complete daily reader home"
```

---

### Task 5: Preserve the AI Hot visual system while simplifying interaction

**Files:**
- Modify: `scripts/radar_render.py`
- Modify: `src/static/app.js`
- Modify: `src/static/styles.css`
- Rename: `tests/test_selected_home_js.py` to `tests/test_reader_home_js.py`
- Modify: `tests/test_reader_home_js.py`
- Modify: `tests/test_radar_render.py`

**Interfaces:**
- Consumes: server-rendered `[data-reader-story]` rows and `data-search-text`.
- Produces: `initReaderSearch()` client filtering without network fetches.
- Produces navigation labels `今日读报` and `往期`; future modules remain absent until implemented.

- [ ] **Step 1: Write failing JavaScript, navigation, and CSS contract tests**

Rename the test before editing it:

```bash
git mv tests/test_selected_home_js.py tests/test_reader_home_js.py
```

Replace the old selected-home JavaScript test with:

```python
class ReaderHomeJavaScriptTests(unittest.TestCase):
    def test_reader_search_filters_server_rendered_rows_only(self):
        js = (ROOT / "src/static/app.js").read_text(encoding="utf-8")
        self.assertIn("function initReaderSearch()", js)
        self.assertIn("[data-reader-story]", js)
        self.assertIn("data-search-text", js)
        self.assertNotIn("IntersectionObserver", js)
        self.assertNotIn("recommendation_reason", js)
        self.assertNotIn("final_score", js)
        self.assertNotIn("推荐理由：", js)

    def test_theme_control_keeps_three_explicit_modes(self):
        rendered = render_primary_nav("今日读报")
        self.assertIn('data-theme-choice="dark"', rendered)
        self.assertIn('data-theme-choice="system"', rendered)
        self.assertIn('data-theme-choice="light"', rendered)
```

Add CSS assertions:

```python
def test_reader_css_keeps_aihot_tokens_and_never_clamps_titles(self):
    css = (ROOT / "src/static/styles.css").read_text(encoding="utf-8")
    self.assertIn("--accent:", css)
    self.assertIn(".reader-story", css)
    self.assertIn(".reader-title", css)
    self.assertIn(".reader-summary", css)
    reader_css = css[css.index("/* Reader homepage */"):]
    self.assertNotIn("-webkit-line-clamp", reader_css)
    mobile = reader_css[reader_css.index("@media (max-width: 760px)"):]
    self.assertNotIn(".reader-summary { display: none", mobile)
```

- [ ] **Step 2: Run the frontend contract tests and verify failure**

Run:

```bash
python3 -m unittest tests.test_reader_home_js tests.test_radar_render -v
```

Expected: FAIL until selected-feed code, scores, recommendation copy, clamping rules, and old navigation are removed from the active frontend.

- [ ] **Step 3: Replace selected-feed JavaScript with current-issue filtering**

Retain the existing theme functions. Remove selected progressive loading, dynamic selected row construction, score handling, recommendation handling, and bookmark synchronization from the homepage path. Add:

```javascript
function initReaderSearch() {
  const form = document.querySelector("[data-reader-search]");
  const empty = document.querySelector("[data-reader-empty]");
  if (!form) return;
  const input = form.querySelector("input[type='search']");
  const stories = Array.from(document.querySelectorAll("[data-reader-story]"));
  const pages = Array.from(document.querySelectorAll(".reader-page"));

  function apply() {
    const query = input.value.trim().toLocaleLowerCase("zh-CN");
    let visibleCount = 0;
    stories.forEach((story) => {
      const matches = !query || story.dataset.searchText.includes(query);
      story.hidden = !matches;
      if (matches) visibleCount += 1;
    });
    pages.forEach((page) => {
      page.hidden = !page.querySelector("[data-reader-story]:not([hidden])");
    });
    empty.hidden = visibleCount !== 0;
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    apply();
  });
  input.addEventListener("search", apply);
}

initReaderSearch();
```

- [ ] **Step 4: Update navigation without publishing empty future pages**

Use:

```python
NAV_ITEMS = (("今日读报", "/"), ("往期", "/all/"))
MORE_ITEMS = (("关于", "/about/"), ("更新日志", "/changelog/"))

NAV_ICON_PATHS = {
    "今日读报": '<path d="M6 2h9l4 4v16H6z"/><path d="M14 2v5h5M9 13h6M9 17h4"/>',
    "往期": '<path d="M8 6h13M8 12h13M8 18h13"/><path d="M3 6h.01M3 12h.01M3 18h.01"/>',
    "关于": '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>',
    "更新日志": '<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5M12 7v5l3 2"/>',
}
```

Define corresponding icons in `NAV_ICON_PATHS`. Keep legacy routes buildable if they still have committed content, but remove AI 日报 and收藏 from primary navigation in this phase.

- [ ] **Step 5: Add reader CSS using existing tokens**

Replace the selected homepage CSS section with a `/* Reader homepage */` section implementing these exact behaviors:

```css
.reader-header { display: flex; align-items: flex-end; justify-content: space-between; gap: 24px; padding-bottom: 17px; border-bottom: 1px solid var(--line); }
.reader-date { display: flex; align-items: baseline; gap: 10px; }
.reader-date strong { font-size: 28px; font-weight: 800; line-height: 1.2; }
.reader-date span, .reader-page-heading span { color: var(--muted); font-size: 13px; }
.reader-search { display: flex; flex: 0 1 290px; }
.reader-search input { min-width: 0; width: 100%; height: 38px; padding: 8px 11px; border: 1px solid var(--line); border-right: 0; border-radius: 7px 0 0 7px; background: var(--bg-elevated); color: var(--text); }
.reader-date-nav { display: flex; gap: 14px; padding: 13px 0 4px; overflow-x: auto; color: var(--muted); font-size: 12px; }
.reader-page { padding-top: 22px; }
.reader-page-heading { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; padding: 0 2px 7px; }
.reader-page-heading h2 { margin: 0; font-size: 15px; }
.reader-list { border-top: 1px solid var(--line); }
.reader-story { border-bottom: 1px solid var(--line-soft); }
.reader-story-link { display: block; padding: 14px 2px; }
.reader-title { margin: 0; color: var(--text); font-size: 15px; font-weight: 680; line-height: 1.55; overflow: visible; white-space: normal; }
.reader-summary { margin: 6px 0 0; color: var(--muted); font-size: 13.5px; line-height: 1.68; }

@media (max-width: 760px) {
  .reader-header { padding: 0 16px 12px; }
  .reader-date strong { font-size: 20px; }
  .reader-search { display: none; }
  .reader-date-nav { padding-inline: 16px; }
  .reader-page { padding: 18px 16px 0; }
  .reader-story-link { padding: 12px 0; }
  .reader-title { font-size: 14px; line-height: 1.52; }
  .reader-summary { display: block; font-size: 12.5px; line-height: 1.62; }
}
```

Remove selected-specific focus, score, reason, entity and bookmark rules once no remaining public route references them. Keep shared tokens, issue-page rules, detail rules, theme rules and accessibility rules.

- [ ] **Step 6: Run frontend contract tests**

Run:

```bash
python3 -m unittest tests.test_reader_home_js tests.test_radar_render -v
```

Expected: PASS; theme modes remain, reader search is local, titles are not clamped, and mobile summaries are visible.

- [ ] **Step 7: Commit the simplified AI Hot frontend**

```bash
git add scripts/radar_render.py src/static/app.js src/static/styles.css tests/test_reader_home_js.py tests/test_radar_render.py
git commit -m "feat: simplify aihot reader experience"
```

---

### Task 6: Make detail pages the full-reading destination

**Files:**
- Modify: `src/templates/radar-item.html`
- Modify: `scripts/radar_render.py`
- Modify: `tests/test_radar_render.py`

**Interfaces:**
- Consumes: one reader article and optional adjacent issue references.
- Produces: `render_item(article: dict, previous: dict | None = None, next_item: dict | None = None) -> str`.
- Produces HTML with source metadata, shared summary, escaped paragraph body, two original-source links, and adjacent navigation.

- [ ] **Step 1: Write failing detail acceptance tests**

Add:

```python
def test_reader_detail_shows_same_summary_body_source_and_adjacent_links(self):
    article = public_issue_item(2)
    article["author"] = "记者甲"
    article["block"]["content"] = "第一段\n\n第二段 <script>x</script>"
    previous = {
        "title": "上一篇",
        "detail_path": "/items/2026-07-10/issue-001/",
    }
    next_item = {
        "title": "下一篇",
        "detail_path": "/items/2026-07-10/issue-003/",
    }
    rendered = render_item(article, previous=previous, next_item=next_item)
    self.assertIn(article["block"]["ai_summary"], rendered)
    self.assertEqual(rendered.count(article["block"]["ai_summary"]), 1)
    self.assertIn("记者甲", rendered)
    self.assertIn("第001版 · 头版", rendered)
    self.assertIn("第一段", rendered)
    self.assertIn("第二段 &lt;script&gt;x&lt;/script&gt;", rendered)
    self.assertEqual(rendered.count(article["block"]["original_url"]), 2)
    self.assertIn("上一篇", rendered)
    self.assertIn("下一篇", rendered)
    self.assertNotIn("推荐理由", rendered)
```

- [ ] **Step 2: Run the detail test and verify failure**

Run:

```bash
python3 -m unittest tests.test_radar_render.RadarRenderTests.test_reader_detail_shows_same_summary_body_source_and_adjacent_links -v
```

Expected: FAIL because the current signature lacks adjacent items, still branches on selected category, and renders recommendation reason for selected articles.

- [ ] **Step 3: Replace the detail template**

Use this complete `src/templates/radar-item.html` body:

```html
<main class="item-page">
  <a class="back-link" href="$back_path">← 返回当期读报</a>
  <p class="item-meta">$source_meta</p>
  <h1>$title</h1>
  <a class="source-link" href="$original_url" target="_blank" rel="noopener noreferrer">查看海南日报原文</a>
  <section class="ai-summary" aria-labelledby="ai-summary-heading">
    <h2 id="ai-summary-heading">AI 摘要</h2>
    <p>$ai_summary</p>
  </section>
  <article class="source-body" aria-label="海南日报正文">$body_paragraphs</article>
  <a class="source-button" href="$original_url" target="_blank" rel="noopener noreferrer">查看海南日报原文</a>
  <nav class="adjacent-stories" aria-label="同一期相邻文章">$adjacent_navigation</nav>
</main>
```

- [ ] **Step 4: Implement one reader-only detail renderer**

Remove the selected/category branch from `render_item()`. Compute:

```python
summary = block["ai_summary"] or "摘要待生成"
source_parts = [
    block["source"],
    article["published_date"],
    f'第{article["page_number"]}版 · {article["page_name"]}',
]
if article["author"].strip():
    source_parts.append(article["author"].strip())
source_meta = " · ".join(source_parts)
paragraphs = [
    part.strip()
    for part in re.split(
        r"\n\s*\n",
        block["content"].replace("\r\n", "\n"),
    )
    if part.strip()
]
body_paragraphs = "".join(
    f"<p>{html.escape(part)}</p>" for part in paragraphs
)
adjacent = []
if previous is not None:
    adjacent.append(
        f'<a rel="prev" href="{html.escape(previous["detail_path"], quote=True)}">← {html.escape(previous["title"])}</a>'
    )
if next_item is not None:
    adjacent.append(
        f'<a rel="next" href="{html.escape(next_item["detail_path"], quote=True)}">{html.escape(next_item["title"])} →</a>'
    )
```

Pass the escaped values to the template. The only summary value comes from `block["ai_summary"]`.

- [ ] **Step 5: Run detail and rendering tests**

Run:

```bash
python3 -m unittest tests.test_radar_render -v
```

Expected: PASS, including HTML escaping and two original-source links.

- [ ] **Step 6: Commit full-reading details**

```bash
git add src/templates/radar-item.html scripts/radar_render.py tests/test_radar_render.py
git commit -m "feat: make reader details show full source text"
```

---

### Task 7: Build only reader routes and migrate committed content

**Files:**
- Create: `scripts/migrate_reader_content.py`
- Modify: `scripts/radar_render.py`
- Modify: `tests/radar_fixtures.py`
- Modify: `tests/test_radar_site_build.py`
- Create: `tests/test_migrate_reader_content.py`
- Modify through script: `content/issues/*.json`
- Modify through script: `content/issue-items/*/*.json`
- Replace through script: `content/indexes/`

**Interfaces:**
- Consumes: schema-v5 issues and issue-items already committed for 2026-07-08 through 2026-07-10.
- Produces: schema-v6 issues and articles, reader indexes, homepage, dated issue pages, detail pages, about/changelog, and any existing daily/weekly routes that still validate.
- Produces adjacent navigation from the flattened order of each issue.

- [ ] **Step 1: Write failing site-route and migration tests**

Replace selected-route expectations with:

```python
def test_builds_reader_home_archive_and_every_detail_without_selected_routes(self):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        content = root / "content"
        site = root / "site"
        write_reader_content_library(content, count=21)
        build_site(content, site)
        self.assertTrue((site / "index.html").is_file())
        self.assertTrue((site / "all/index.html").is_file())
        self.assertTrue((site / "all/2026-07-10/index.html").is_file())
        self.assertEqual(
            len(list((site / "items/2026-07-10").glob("*/index.html"))),
            21,
        )
        self.assertFalse((site / "category").exists())
        self.assertFalse((site / "starred").exists())
        homepage = (site / "index.html").read_text(encoding="utf-8")
        self.assertEqual(homepage.count('class="reader-story"'), 21)
        self.assertNotIn("精选", homepage)
        self.assertEqual(validate_internal_links(site), [])

def test_migrates_v5_issue_content_to_reader_v6(self):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_legacy_issue_library(root, count=2)
        selected_path = root / "items/2026-07-10/issue-001.json"
        selected_path.parent.mkdir(parents=True, exist_ok=True)
        selected_path.write_text(
            json.dumps(
                {
                    "item_id": "issue-001",
                    "entities": {
                        "actors": [
                            {
                                "name": "测试人物",
                                "type": "person",
                                "role": "测试职务",
                                "evidence": "测试人物",
                            }
                        ],
                        "locations": [],
                        "action": "",
                        "action_evidence": "",
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        migrate_reader_content(root)
        issue = json.loads((root / "issues/2026-07-10.json").read_text(encoding="utf-8"))
        article = json.loads((root / "issue-items/2026-07-10/issue-001.json").read_text(encoding="utf-8"))
        self.assertEqual(issue["schema_version"], 6)
        self.assertEqual(issue["article_count"], 2)
        self.assertNotIn("scored_article_count", issue)
        self.assertEqual(article["schema_version"], 6)
        self.assertEqual(article["author"], "")
        self.assertEqual(article["entities"]["actors"][0]["name"], "测试人物")
        self.assertTrue((root / "indexes/reader.json").is_file())
```

Add these exact fixture helpers to `tests/radar_fixtures.py`:

```python
def write_reader_content_library(root: Path, count: int):
    from scripts.radar_indexes import build_reader_indexes

    issue = public_issue(count=count)
    articles = [public_issue_item(index) for index in range(1, count + 1)]
    for article in articles:
        path = root / "issue-items" / article["published_date"] / f'{article["item_id"]}.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(article, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    issue_path = root / "issues" / f'{issue["date"]}.json'
    issue_path.parent.mkdir(parents=True, exist_ok=True)
    issue_path.write_text(
        json.dumps(issue, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    for relative, payload in build_reader_indexes([issue], articles).items():
        path = root / "indexes" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return issue, articles


def write_legacy_issue_library(root: Path, count: int):
    issue, articles = write_reader_content_library(root, count)
    issue["schema_version"] = 5
    issue["scored_article_count"] = issue.pop("article_count")
    (root / "issues/2026-07-10.json").write_text(
        json.dumps(issue, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    for article in articles:
        article["schema_version"] = 5
        article.pop("author")
        article.pop("entities")
        path = root / "issue-items/2026-07-10" / f'{article["item_id"]}.json'
        path.write_text(
            json.dumps(article, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
```

- [ ] **Step 2: Run route and migration tests to verify failure**

Run:

```bash
python3 -m unittest tests.test_radar_site_build tests.test_migrate_reader_content -v
```

Expected: FAIL because the migration module and reader-only site build do not exist.

- [ ] **Step 3: Implement adjacent navigation and reader-only site build**

In `build_site()`:

1. Load and validate all issues and issue-items.
2. Read `indexes/reader.json` and choose `latest_date`.
3. Render `/index.html` from the latest issue and its articles.
4. Render `/all/index.html` as the date archive.
5. Render `/all/YYYY-MM-DD/index.html` for each issue.
6. Flatten each issue's article references by page order and page sequence.
7. Render every `/items/YYYY-MM-DD/ITEM_ID/index.html` with adjacent references.
8. Preserve about/changelog and valid daily/weekly routes.
9. Do not render category, selected-feed, scoring-audit or starred routes.
10. Copy only `styles.css` and `app.js` into `site/static/`; reader feeds remain content indexes and are not required by homepage JavaScript.

Use this navigation map shape:

```python
navigation = {}
for issue in issues:
    ordered_refs = [
        reference
        for page in issue["pages"]
        for reference in page["articles"]
    ]
    for index, reference in enumerate(ordered_refs):
        navigation[reference["item_id"]] = {
            "previous": ordered_refs[index - 1] if index > 0 else None,
            "next": ordered_refs[index + 1] if index + 1 < len(ordered_refs) else None,
        }
```

- [ ] **Step 4: Implement deterministic schema-v5 migration**

Create `scripts/migrate_reader_content.py` with public function:

```python
def write_json_atomic(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def migrate_reader_content(content_root: Path) -> dict[str, int]:
    legacy_entities = {}
    for path in sorted((content_root / "items").glob("*/*.json")):
        legacy = json.loads(path.read_text(encoding="utf-8"))
        entities = legacy.get("entities")
        if isinstance(entities, dict):
            legacy_entities[legacy["item_id"]] = entities

    issues = []
    for path in sorted((content_root / "issues").glob("*.json")):
        issue = json.loads(path.read_text(encoding="utf-8"))
        issue["schema_version"] = SCHEMA_VERSION
        issue["article_count"] = issue.pop("scored_article_count")
        validate_public_issue(issue)
        write_json_atomic(path, issue)
        issues.append(issue)

    articles = []
    for path in sorted((content_root / "issue-items").glob("*/*.json")):
        article = json.loads(path.read_text(encoding="utf-8"))
        article["schema_version"] = SCHEMA_VERSION
        article.setdefault("author", "")
        article.setdefault(
            "entities",
            legacy_entities.get(
                article["item_id"],
                {"actors": [], "locations": [], "action": "", "action_evidence": ""},
            ),
        )
        validate_public_issue_item(article)
        write_json_atomic(path, article)
        articles.append(article)

    indexes = build_reader_indexes(issues, articles)
    index_root = content_root / "indexes"
    staging = content_root / ".reader-index-migration"
    if staging.exists():
        shutil.rmtree(staging)
    for relative, payload in indexes.items():
        write_json_atomic(staging / relative, payload)
    backup = content_root / ".reader-index-backup"
    if backup.exists():
        shutil.rmtree(backup)
    if index_root.exists():
        index_root.replace(backup)
    staging.replace(index_root)
    if backup.exists():
        shutil.rmtree(backup)
    return {"issue_count": len(issues), "article_count": len(articles)}
```

Add a CLI `main()` that accepts exactly one `CONTENT_ROOT`, prints the returned JSON, and exits nonzero on validation, JSON or file errors.

```python
def main(argv):
    if len(argv) != 2:
        print("Usage: migrate_reader_content.py CONTENT_ROOT", file=sys.stderr)
        return 1
    try:
        result = migrate_reader_content(Path(argv[1]))
    except (ContractError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
```

- [ ] **Step 5: Run migration and site-build tests**

Run:

```bash
python3 -m unittest tests.test_migrate_reader_content tests.test_radar_site_build -v
```

Expected: PASS with no selected/category/starred routes and no broken internal links.

- [ ] **Step 6: Migrate committed content and rebuild the static site**

Run:

```bash
python3 scripts/migrate_reader_content.py content
python3 scripts/radar_render.py content site
```

Expected migration output: JSON with `issue_count: 3` and a positive `article_count`; render exits 0.

- [ ] **Step 7: Verify committed real dates before committing data**

Run:

```bash
python3 -m unittest tests.test_radar_real_dates tests.test_radar_site_build -v
python3 -m scripts.preview
```

Expected: tests PASS. In the local preview, `/` shows the latest committed issue with every effective article title and summary, and a sampled detail page shows the same summary plus the full body. Stop the preview after inspection.

- [ ] **Step 8: Commit migration and reader routes**

```bash
git add scripts/migrate_reader_content.py scripts/radar_render.py tests/radar_fixtures.py tests/test_radar_site_build.py tests/test_migrate_reader_content.py content/issues content/issue-items content/indexes site
git commit -m "feat: migrate published content to reader routes"
```

---

### Task 8: Update the daily pipeline, documentation, and full acceptance suite

**Files:**
- Modify: `scripts/run_radar_pipeline.sh`
- Modify: `docs/codex-digest-generation.md`
- Modify: `README.md`
- Modify: `tests/test_radar_pipeline_cli.py`
- Modify: `tests/test_radar_real_dates.py`
- Modify or remove: scoring/selection tests that no longer describe a public dependency

**Interfaces:**
- Consumes: reader-v1 model input/output files and reader schema v6 content.
- Produces: idempotent `STATUS=COMPLETE`, full issue content, static site, and audit with `candidate_count`, `published_count`, and `summary_pending_count`.

- [ ] **Step 1: Write the end-to-end pipeline acceptance test**

Replace selected-count expectations with:

```python
def test_prepare_then_resume_publishes_every_valid_article_idempotently(self):
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        raw = work / "2026-07-09.json"
        raw.write_text(
            json.dumps(raw_issue(date="2026-07-09"), ensure_ascii=False),
            encoding="utf-8",
        )
        env = os.environ | {
            "HNDAILY_WEB_DIR": str(ROOT),
            "HNDAILY_RAW_JSON": str(raw),
            "RADAR_CONTENT_ROOT": str(work / "content"),
            "RADAR_SITE_ROOT": str(work / "site"),
            "RADAR_RUN_ROOT": str(work / "run"),
            "HNDAILY_INTERMEDIATE_DIR": str(work / "intermediate"),
            "RADAR_AS_OF": "2026-07-10",
        }
        command = ["bash", str(ROOT / "scripts/run_radar_pipeline.sh"), "2026-07-09"]
        first = subprocess.run(command, env=env, text=True, capture_output=True)
        self.assertEqual(first.returncode, 2)
        paths = dict(
            line.split("=", 1)
            for line in first.stdout.splitlines()
            if "=" in line
        )
        model_input = json.loads(
            Path(paths["MODEL_INPUT_JSON"]).read_text(encoding="utf-8")
        )
        Path(paths["MODEL_OUTPUT_JSON"]).write_text(
            json.dumps(model_output_for(model_input), ensure_ascii=False),
            encoding="utf-8",
        )
        second = subprocess.run(command, env=env, text=True, capture_output=True)
        third = subprocess.run(command, env=env, text=True, capture_output=True)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(third.returncode, 0, third.stderr)
        self.assertIn("STATUS=COMPLETE", second.stdout)
        self.assertEqual(
            len(list((work / "content/issue-items/2026-07-09").glob("*.json"))),
            4,
        )
        homepage = (work / "site/index.html").read_text(encoding="utf-8")
        self.assertEqual(homepage.count('class="reader-story"'), 4)
        self.assertFalse((work / "content/indexes/focus.json").exists())
```

- [ ] **Step 2: Run the pipeline test and verify failure against the old docs/expectations**

Run:

```bash
python3 -m unittest tests.test_radar_pipeline_cli -v
```

Expected: FAIL until the transaction and CLI path use only reader content and the test fixture emits reader-v1 output.

- [ ] **Step 3: Update pipeline output and operator documentation**

Keep `scripts/run_radar_pipeline.sh` as the compatibility command, but use reader-named intermediate files:

```bash
MODEL_INPUT_JSON="$INTERMEDIATE_DIR/$DATE_STEM.reader-model-input.json"
MODEL_OUTPUT_JSON="${RADAR_MODEL_OUTPUT_JSON:-$INTERMEDIATE_DIR/$DATE_STEM.reader-model-output.json}"
PREFILTER_JSON="$INTERMEDIATE_DIR/$DATE_STEM.reader-prefilter.json"
AUDIT_JSON="$INTERMEDIATE_DIR/$DATE_STEM.reader-audit.json"
RUN_ROOT="${RADAR_RUN_ROOT:-$WEB_DIR/data/tmp/reader-$DATE_STEM}"
```

Keep the two-pass CLI protocol and these printed paths:

```text
RAW_JSON=/tmp/hndaily/2026-07-10.json
MODEL_INPUT_JSON=/tmp/hndaily/2026-07-10.reader-model-input.json
MODEL_OUTPUT_JSON=/tmp/hndaily/2026-07-10.reader-model-output.json
PREFILTER_JSON=/tmp/hndaily/2026-07-10.reader-prefilter.json
AUDIT_JSON=/tmp/hndaily/2026-07-10.reader-audit.json
```

Update `docs/codex-digest-generation.md` to state the exact reader-v1 envelope and the six allowed item fields. Document that `ai_summary` may be `null`, all IDs must remain in candidate order, and entity evidence validation remains strict.

Update `README.md` routes to:

```text
/: 最新一期完整 AI 读报
/all/: 往期目录
/all/YYYY-MM-DD/: 当期版面目录
/items/YYYY-MM-DD/<item-id>/: AI 摘要、原始正文和海南日报原文
/about/: 关于
/changelog/: 更新日志
```

Document that scoring, selected feeds, recommendation reasons, category routes and the local human-feedback system are not active product dependencies.

- [ ] **Step 4: Remove obsolete test assumptions without deleting useful pure units**

Perform these exact removals after the dependency search shows no reader runtime import:

```bash
git rm \
  scripts/radar_scoring.py \
  scripts/radar_select.py \
  scripts/build_scoring_audit.py \
  tests/test_radar_selection.py \
  tests/test_scoring_audit.py \
  docs/scoring-system-audit.html
git rm -r content/items
```

Keep `scripts/editorial_scoring.py` and `tests/test_editorial_scoring.py` because the separate digest pipeline still imports them. Keep administrative location dictionary and evidence validation tests because the future person and map phases depend on them. Rewrite the already named reader tests in Tasks 1–7; do not delete coverage for transaction rollback, HTML escaping, issue ordering, real-date counts or internal links.

After deleting the legacy selected library, update `prepare_staged_content()` to copy only active content families:

```python
for name in ("issue-items", "issues", "indexes", "daily", "weekly"):
    source = content_root / name
    if source.exists():
        shutil.copytree(
            source,
            staged_content / name,
            copy_function=_link_or_copy,
        )
```

Run the dependency check:

```bash
rg -n "radar_scoring|radar_select|recommendation_reason|final_score|focus.json|selected-feed" scripts src tests README.md docs/codex-digest-generation.md
```

Expected: no active reader runtime reference. Any remaining occurrence must be inside an explicitly named legacy migration fixture or historical design document, not current operator documentation.

- [ ] **Step 5: Run the complete automated suite**

Run:

```bash
python3 -m unittest discover -s tests -v
```

Expected: PASS with 0 failures and 0 errors.

- [ ] **Step 6: Run real-data and static-build verification**

Run:

```bash
RADAR_REAL_DATA_REQUIRED=1 python3 -m unittest discover -s tests -v
python3 scripts/radar_render.py content site
python3 -c 'from pathlib import Path; from scripts.radar_render import validate_internal_links; links = validate_internal_links(Path("site")); print(links); raise SystemExit(bool(links))'
```

Expected: both test runs PASS, render exits 0, and link validation prints `[]`.

- [ ] **Step 7: Perform visual acceptance against the current main-branch style**

Capture `/`, `/all/2026-07-10/`, and `/items/2026-07-10/hndaily-19691668/` at:

```text
1440 × 1000
733 × 860
393 × 852
```

Verify all of the following before accepting:

- Sidebar, mobile bottom navigation, colors, type hierarchy and theme control visibly remain in the current AI Hot-derived family.
- Homepage displays every effective article in edition order.
- Each article row visibly contains only title and summary.
- Long titles wrap fully without clipping or ellipsis.
- Mobile summaries are visible.
- No score, rank, recommendation reason, entity label or bookmark appears.
- Detail summary matches homepage text exactly and full body paragraphs remain readable.
- No horizontal overflow, bottom-navigation overlap or broken dark/light contrast appears.

- [ ] **Step 8: Commit pipeline and documentation completion**

```bash
git add scripts/run_radar_pipeline.sh docs/codex-digest-generation.md README.md tests
git add -u scripts src
git commit -m "docs: complete modern reader rollout"
```

---

## Final Acceptance Gate

Do not start the upcoming-events plan until all of these are true:

- Full automated suite passes with zero failures and errors.
- Real-data-required suite passes.
- Static render and internal link validation pass.
- Latest homepage count equals its issue `article_count`.
- Homepage and detail summaries are byte-identical for sampled and automated cases.
- Detail pages display full escaped source bodies and original links.
- No active runtime imports scoring or selection.
- No public route exposes selected feeds, categories, scoring audit, recommendation reason or homepage entity labels.
- Visual acceptance passes at all three required viewports in light and dark themes.
- The implementation is split into the eight commits above or equally reviewable commits with the same task boundaries.
