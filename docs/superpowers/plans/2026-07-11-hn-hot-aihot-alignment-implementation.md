# HN·HOT AIHOT-Aligned Experience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the HN·HOT selected-news homepage, dynamic focus ranking, full newspaper reading routes, static search, three-state themes, and AIHOT-aligned responsive navigation.

**Architecture:** Preserve the selected-item library and add a separate public issue layer containing every article that passed deterministic filtering and entered AI scoring. Generate selected, issue, focus, and search indexes during the existing atomic publication, then render every route as static HTML with progressively enhanced client-side search and theme controls.

**Tech Stack:** Python 3.9 standard library, `unittest`, `string.Template`, static HTML/CSS/JavaScript, JSON content artifacts.

## Global Constraints

- Product name is exactly `HN·HOT`.
- Navigation labels are exactly `精选`, `全部信息`, `AI 日报`, `关于`, and `更新日志`.
- The UI contains no brand slogan, feature introduction, tutorial, or instructive helper copy.
- The selected homepage order is: heading, categories/search, `当下重点`, date-grouped selected titles, pagination.
- `当下重点` contains only selected items and uses `focus_score = final_score - 3 × older_content_day_index`.
- Selected and date lists display titles only; no source, summary, excerpt, or public score.
- Full newspaper routes contain every article that passed deterministic filtering and entered AI scoring, grouped in original page and article order.
- Page headings link to the original HTML page; a separate `下载 PDF` link targets the page PDF; article titles target local full-text routes.
- Prefiltered advertisements, declarations, empty records, internal scores, selection decisions, and audit fields are not published as article records.
- The site remains static and a failed data validation, render, or internal-link check must not replace the last successful generation.
- Theme choices are dark, system, and light; the first visit defaults to system and later visits restore the saved choice.
- Do not add accounts, favorites, feedback, Agent integration, or topic aggregation.

---

## File Map

**Create**

- `scripts/radar_issue.py`: validate and build public issue metadata, issue items, and issue/search indexes.
- `src/templates/radar-issue.html`: one full-newspaper date page.
- `src/templates/about.html`: minimal About page.
- `src/templates/changelog.html`: minimal changelog page.
- `tests/test_radar_issue.py`: public issue contract and construction tests.

**Modify**

- `scripts/radar_contract.py`: add publication-layout fields to source candidates and public issue validators.
- `scripts/radar_adapter.py`: preserve page number, page name, page URL, PDF URL, and source sequence on candidates.
- `scripts/finalize_radar.py`: build public issue artifacts from every scored candidate, not only selected items.
- `scripts/radar_store.py`: atomically store selected items, issue items, issue documents, and all indexes.
- `scripts/radar_indexes.py`: remove summaries from selected lists and build selected-title search data.
- `scripts/radar_render.py`: render HN·HOT navigation, selected title lists, full newspaper routes, AI Daily, About, and Changelog.
- `src/templates/radar-index.html`: AIHOT-aligned selected-page structure.
- `src/templates/radar-item.html`: shared local full-text route for selected and unselected scored articles.
- `src/templates/base.html`: early theme initialization and metadata.
- `src/static/styles.css`: responsive navigation, title lists, full newspaper layout, and light/dark variables.
- `src/static/app.js`: theme state, mobile navigation, selected search, and issue search.
- `tests/radar_fixtures.py`: issue-aware fixtures.
- `tests/test_radar_adapter.py`: candidate layout preservation tests.
- `tests/test_radar_indexes.py`: title-only selected/search index tests.
- `tests/test_radar_store.py`: issue-layer atomicity tests.
- `tests/test_finalize_radar.py`: all scored candidates publication tests.
- `tests/test_radar_render.py`: copy, hierarchy, escaping, and full-newspaper rendering tests.
- `tests/test_radar_site_build.py`: new route and link integration tests.
- `README.md`: corrected preview command and route summary.

---

### Task 1: Preserve Newspaper Layout on Scoring Candidates

**Files:**
- Modify: `scripts/radar_contract.py`
- Modify: `scripts/radar_adapter.py`
- Modify: `tests/radar_fixtures.py`
- Test: `tests/test_radar_adapter.py`

**Interfaces:**
- Consumes: raw `pages[].page`, `page_name`, `page_url`, `pdf_url`, and `articles[].seq`.
- Produces: `adapt_hndaily(raw) -> tuple[list[dict], list[dict]]` candidates containing `page_number`, `page_name`, `page_url`, `pdf_url`, and `page_sequence`.

- [ ] **Step 1: Replace the layout-discarding adapter assertion with a failing preservation test**

```python
def test_adapts_trusted_fields_with_publication_layout(self):
    candidates, audit = adapt_hndaily(raw_issue())
    self.assertEqual(len(candidates), 4)
    self.assertEqual(len(audit), 4)
    self.assertEqual(candidates[0]["page_number"], "001")
    self.assertEqual(candidates[0]["page_name"], "头版")
    self.assertEqual(candidates[0]["page_sequence"], 1)
    self.assertEqual(candidates[0]["page_url"], "https://example.com/page-001")
    self.assertEqual(candidates[0]["pdf_url"], "https://example.com/page-001.pdf")
```

- [ ] **Step 2: Run the focused test and verify the missing fields fail**

Run: `python3 -m unittest tests.test_radar_adapter.RadarAdapterTests.test_adapts_trusted_fields_with_publication_layout -v`

Expected: `ERROR` or `FAIL` because `page_number` is absent.

- [ ] **Step 3: Extend the exact source-candidate contract**

```python
SOURCE_CANDIDATE_FIELDS = {
    "candidate_id", "item_id", "source", "title", "content",
    "original_url", "published_date", "collected_date",
    "page_number", "page_name", "page_url", "pdf_url", "page_sequence",
}

def validate_source_candidate(candidate: dict[str, Any]) -> None:
    require_exact_fields(candidate, SOURCE_CANDIDATE_FIELDS, "source candidate")
    for field in (
        "candidate_id", "item_id", "source", "title", "content",
        "page_number", "page_name",
    ):
        if not non_empty(candidate.get(field)):
            raise ContractError(f"source candidate.{field} is required")
    if not candidate["page_number"].isdigit() or len(candidate["page_number"]) != 3:
        raise ContractError("source candidate.page_number is invalid")
    if type(candidate.get("page_sequence")) is not int or candidate["page_sequence"] < 1:
        raise ContractError("source candidate.page_sequence is invalid")
    for field in ("original_url", "page_url", "pdf_url"):
        validate_http_url(candidate.get(field), f"source candidate.{field}")
    validate_iso_date(candidate.get("published_date"), "source candidate.published_date")
    validate_iso_date(candidate.get("collected_date"), "source candidate.collected_date")
```

- [ ] **Step 4: Populate layout fields while iterating raw pages and articles**

```python
candidate = {
    "candidate_id": record["candidate_id"],
    "item_id": _stable_id(record["url"], published_date, record["original_title"]),
    "source": str(raw.get("source", "")).strip(),
    "title": record["original_title"],
    "content": record["content"].strip(),
    "original_url": record["url"],
    "published_date": published_date,
    "collected_date": collected_date,
    "page_number": record["page"],
    "page_name": record["page_name"],
    "page_url": record["page_url"],
    "pdf_url": record["pdf_url"],
    "page_sequence": record["seq"],
}
```

Update `scripts/editorial_filter.py` so every returned audit record copies `page`, `page_name`, `page_url`, `pdf_url`, and article `seq` from its enclosing raw page/article before `adapt_hndaily()` consumes the passed records.

- [ ] **Step 5: Run adapter and filter tests**

Run: `python3 -m unittest tests.test_radar_adapter tests.test_editorial_filter -v`

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add scripts/radar_contract.py scripts/radar_adapter.py scripts/editorial_filter.py tests/radar_fixtures.py tests/test_radar_adapter.py tests/test_editorial_filter.py
git commit -m "feat: preserve newspaper layout metadata"
```

---

### Task 2: Build and Validate the Public Full-Newspaper Layer

**Files:**
- Create: `scripts/radar_issue.py`
- Create: `tests/test_radar_issue.py`
- Modify: `scripts/finalize_radar.py`
- Modify: `tests/test_finalize_radar.py`

**Interfaces:**
- Consumes: raw issue metadata, layout-aware candidates, validated semantic model items, and scored items before selection.
- Produces: `build_public_issue(raw, candidates, semantic_items, scored) -> tuple[dict, list[dict]]`, where the tuple is `(issue, issue_items)`.
- Produces: `validate_public_issue(issue) -> None` and `validate_public_issue_item(item) -> None`.

- [ ] **Step 1: Add failing tests for scored and empty pages**

```python
def test_public_issue_groups_all_scored_articles_in_source_order(self):
    raw, candidates, semantic, scored = issue_inputs()
    issue, issue_items = build_public_issue(raw, candidates, semantic, scored)
    self.assertEqual(issue["date"], "2026-07-08")
    self.assertEqual([page["page_number"] for page in issue["pages"]], ["001", "002"])
    self.assertEqual([a["page_sequence"] for a in issue["pages"][0]["articles"]], [1, 2])
    self.assertEqual(len(issue_items), len(candidates))
    self.assertNotIn("final_score", str(issue))
    self.assertNotIn("selected", str(issue_items))

def test_public_issue_keeps_empty_advertising_page(self):
    raw, candidates, semantic, scored = issue_inputs(include_empty_page=True)
    issue, _ = build_public_issue(raw, candidates, semantic, scored)
    empty = issue["pages"][-1]
    self.assertEqual(empty["page_name"], "公益广告")
    self.assertEqual(empty["articles"], [])
    self.assertTrue(empty["pdf_url"].endswith("008.pdf"))
```

- [ ] **Step 2: Run the new test module and verify import failure**

Run: `python3 -m unittest tests.test_radar_issue -v`

Expected: `ImportError` for `scripts.radar_issue`.

- [ ] **Step 3: Implement exact public issue validators**

```python
ISSUE_FIELDS = {"schema_version", "date", "source", "page_count", "scored_article_count", "pages"}
ISSUE_PAGE_FIELDS = {"page_number", "page_name", "page_url", "pdf_url", "articles"}
ISSUE_ARTICLE_FIELDS = {"item_id", "title", "page_sequence", "detail_path"}
ISSUE_ITEM_FIELDS = {
    "schema_version", "item_id", "published_date", "collected_date",
    "page_number", "page_name", "page_sequence", "block",
}

def validate_public_issue(issue: dict[str, Any]) -> None:
    require_exact_fields(issue, ISSUE_FIELDS, "public issue")
    validate_iso_date(issue["date"], "public issue.date")
    if type(issue["page_count"]) is not int or issue["page_count"] != len(issue["pages"]):
        raise ContractError("public issue.page_count is invalid")
    article_total = 0
    previous_page = "000"
    for page in issue["pages"]:
        require_exact_fields(page, ISSUE_PAGE_FIELDS, "public issue page")
        validate_http_url(page["page_url"], "public issue page.page_url")
        validate_http_url(page["pdf_url"], "public issue page.pdf_url")
        if page["page_number"] <= previous_page:
            raise ContractError("public issue pages are not ordered")
        previous_page = page["page_number"]
        sequences = [article["page_sequence"] for article in page["articles"]]
        if sequences != sorted(sequences):
            raise ContractError("public issue articles are not ordered")
        article_total += len(page["articles"])
    if article_total != issue["scored_article_count"]:
        raise ContractError("public issue scored_article_count is invalid")
```

- [ ] **Step 4: Implement publication construction without private scoring fields**

```python
def build_public_issue(raw, candidates, semantic_items, scored):
    if not (len(candidates) == len(semantic_items) == len(scored)):
        raise ContractError("public issue candidate alignment mismatch")
    by_page = {page["page"]: {"page_number": page["page"], "page_name": page["page_name"], "page_url": page["page_url"], "pdf_url": page["pdf_url"], "articles": []} for page in raw["pages"]}
    issue_items = []
    for candidate, semantic, scored_item in zip(candidates, semantic_items, scored):
        detail_path = f'/items/{candidate["published_date"]}/{candidate["item_id"]}/'
        by_page[candidate["page_number"]]["articles"].append({"item_id": candidate["item_id"], "title": candidate["title"], "page_sequence": candidate["page_sequence"], "detail_path": detail_path})
        issue_items.append({"schema_version": SCHEMA_VERSION, "item_id": candidate["item_id"], "published_date": candidate["published_date"], "collected_date": candidate["collected_date"], "page_number": candidate["page_number"], "page_name": candidate["page_name"], "page_sequence": candidate["page_sequence"], "block": {"source": candidate["source"], "title": candidate["title"], "content": candidate["content"], "ai_summary": semantic["ai_summary"].strip(), "original_url": candidate["original_url"]}})
    issue = {"schema_version": SCHEMA_VERSION, "date": raw["date"], "source": raw["source"], "page_count": len(raw["pages"]), "scored_article_count": len(candidates), "pages": list(by_page.values())}
    validate_public_issue(issue)
    for item in issue_items:
        validate_public_issue_item(item)
    return issue, issue_items
```

- [ ] **Step 5: Return public issue artifacts from finalization**

Refactor `build_items()` to return `(selected, issue, issue_items, audit)`. Build the public issue after `scored` is complete and before `select_items(scored)`, guaranteeing that low-scoring but evaluated candidates remain publishable.

- [ ] **Step 6: Run issue and finalization tests**

Run: `python3 -m unittest tests.test_radar_issue tests.test_finalize_radar -v`

Expected: all tests pass, including an assertion that `candidate_count == len(issue_items)` while `selected_count <= len(issue_items)`.

- [ ] **Step 7: Commit**

```bash
git add scripts/radar_issue.py scripts/finalize_radar.py tests/test_radar_issue.py tests/test_finalize_radar.py
git commit -m "feat: build public full-newspaper records"
```

---

### Task 3: Atomically Store Issues and Build Search Indexes

**Files:**
- Modify: `scripts/radar_indexes.py`
- Modify: `scripts/radar_store.py`
- Modify: `scripts/finalize_radar.py`
- Modify: `tests/test_radar_indexes.py`
- Modify: `tests/test_radar_store.py`

**Interfaces:**
- Consumes: selected items, one public issue, and issue items.
- Produces: `build_search_indexes(selected_items, issue_items) -> dict[str, dict]`.
- Produces: `commit_generation(content_root, items, indexes, affected_dates, *, issues, issue_items, fail_after_items=False, fail_after_issues=False)`.

- [ ] **Step 1: Add failing title-only and search-index tests**

```python
def test_selected_indexes_are_title_only_and_searchable(self):
    items = [stored_item(1, summary="private summary")]
    indexes = build_indexes(items, "2026-07-10")
    row = indexes["all/page-001.json"]["items"][0]
    self.assertEqual(set(row), {"item_id", "published_date", "daily_rank", "category", "title", "detail_path"})
    self.assertNotIn("private summary", str(indexes))

def test_search_indexes_separate_selected_and_issue_titles(self):
    indexes = build_search_indexes([stored_item(1)], [public_issue_item(1), public_issue_item(2)])
    self.assertEqual(len(indexes["search-selected.json"]["items"]), 1)
    self.assertEqual(len(indexes["search-issues.json"]["items"]), 2)
```

- [ ] **Step 2: Run focused tests and verify expected failures**

Run: `python3 -m unittest tests.test_radar_indexes -v`

Expected: failure because selected summaries are still present and `build_search_indexes` is absent.

- [ ] **Step 3: Make selected summaries title-only and add search builders**

```python
def _summary(item):
    return {"item_id": item["item_id"], "published_date": item["published_date"], "daily_rank": item["daily_rank"], "category": item["category"], "title": item["block"]["title"], "detail_path": f'/items/{item["published_date"]}/{item["item_id"]}/'}

def build_search_indexes(selected_items, issue_items):
    def rows(values):
        return [{"item_id": item["item_id"], "published_date": item["published_date"], "title": item["block"]["title"], "detail_path": f'/items/{item["published_date"]}/{item["item_id"]}/'} for item in values]
    return {"search-selected.json": {"items": rows(selected_items)}, "search-issues.json": {"items": rows(issue_items)}}
```

- [ ] **Step 4: Add failing atomic rollback coverage**

```python
def test_issue_failure_restores_previous_selected_issue_and_indexes(self):
    with self.assertRaisesRegex(RuntimeError, "issue swaps"):
        commit_generation(content, items, indexes, {date}, issues=[issue], issue_items=issue_items, fail_after_issues=True)
    self.assertEqual((content / "sentinel.txt").read_text(), "previous")
```

- [ ] **Step 5: Extend staging and swaps to include issue data**

Write selected items to `staging/items/{date}`, issue items to `staging/issue-items/{date}`, issues to `staging/issues/{date}.json`, and every index to `staging/indexes`. Swap and roll back all four target families in one `try/except`, using the existing backup pattern. Validate every public issue and issue item before creating staging.

- [ ] **Step 6: Wire finalization to the expanded commit**

```python
search_indexes = build_search_indexes(merged, merged_issue_items)
indexes = {**build_indexes(merged, as_of), **search_indexes, "issues.json": build_issue_date_index(merged_issues)}
commit_generation(content_root, merged, indexes, {published_date}, issues=merged_issues, issue_items=merged_issue_items)
```

Load existing issues and issue items before replacing the affected date, following the selected-library merge rule.

- [ ] **Step 7: Run store, index, transaction, and finalization tests**

Run: `python3 -m unittest tests.test_radar_indexes tests.test_radar_store tests.test_radar_transaction tests.test_finalize_radar -v`

Expected: all tests pass and rollback leaves the previous generation intact.

- [ ] **Step 8: Commit**

```bash
git add scripts/radar_indexes.py scripts/radar_store.py scripts/finalize_radar.py tests/test_radar_indexes.py tests/test_radar_store.py tests/test_radar_transaction.py tests/test_finalize_radar.py
git commit -m "feat: atomically publish issue and search indexes"
```

---

### Task 4: Render Selected and Full-Newspaper Routes

**Files:**
- Create: `src/templates/radar-issue.html`
- Modify: `src/templates/radar-index.html`
- Modify: `src/templates/radar-item.html`
- Modify: `scripts/radar_render.py`
- Modify: `tests/test_radar_render.py`
- Modify: `tests/test_radar_site_build.py`

**Interfaces:**
- Consumes: title-only selected indexes, `focus.json`, public issues, selected items, and issue items.
- Produces: `render_index(index, focus, active_category) -> str`, `render_issue(issue) -> str`, and one local detail route per unique item ID.

- [ ] **Step 1: Add failing rendering assertions for concise selected content**

```python
def test_selected_page_renders_focus_and_date_titles_without_summary(self):
    rendered = render_index(selected_index(), focus_index(), "全部")
    self.assertIn("精选", rendered)
    self.assertIn("当下重点", rendered)
    self.assertIn("data-search-scope=\"selected\"", rendered)
    self.assertNotIn("自动筛选", rendered)
    self.assertNotIn("海南日报", rendered)
    self.assertNotIn("摘要文字", rendered)
```

- [ ] **Step 2: Add failing full-newspaper rendering assertions**

```python
def test_issue_page_links_page_pdf_and_local_articles(self):
    rendered = render_issue(public_issue())
    self.assertIn("第001版：头版", rendered)
    self.assertIn('href="https://example.com/page-001"', rendered)
    self.assertIn('href="https://example.com/page-001.pdf"', rendered)
    self.assertIn("下载 PDF", rendered)
    self.assertIn('/items/2026-07-08/hndaily-1/', rendered)
    self.assertIn("第008版：公益广告", rendered)
```

- [ ] **Step 3: Run rendering tests and verify failures**

Run: `python3 -m unittest tests.test_radar_render -v`

Expected: failures because the old cards contain source/summary and `render_issue` is undefined.

- [ ] **Step 4: Replace selected cards with accessible title rows**

```python
def _title_row(item, rank=None):
    number = "" if rank is None else f'<span class="title-rank">{rank}</span>'
    return f'<a class="title-row" data-search-title="{html.escape(item["title"], quote=True)}" href="{html.escape(item["detail_path"], quote=True)}">{number}<span>{html.escape(item["title"])}</span></a>'
```

Use `_title_row(item, item["focus_rank"])` for focus and `_title_row(item)` for date groups. Render category links and `<input type="search" aria-label="搜索精选标题" data-search-input="selected">` above focus.

- [ ] **Step 5: Implement full-newspaper template rendering**

```python
def render_issue(issue):
    pages = []
    for page in issue["pages"]:
        page_title = f'第{page["page_number"]}版：{page["page_name"]}'
        articles = "".join(_title_row(article) for article in page["articles"])
        pages.append(_template("radar-issue.html").safe_substitute(page_title=html.escape(page_title), page_url=html.escape(page["page_url"], quote=True), pdf_url=html.escape(page["pdf_url"], quote=True), article_count=len(page["articles"]), articles=articles))
    return '<main class="issue-content" data-search-scope="issues">' + "".join(pages) + "</main>"
```

The template must use visible link text `下载 PDF`, `target="_blank"`, and `rel="noopener noreferrer"` for external page/PDF links.

- [ ] **Step 6: Build issue and unique detail routes**

In `build_site()`, read `indexes/issues.json`, render `/all/index.html` from the latest date, render `/all/{date}/index.html` for every `content/issues/{date}.json`, then merge selected items and issue items by `(published_date, item_id)`. If a selected and issue item disagree on title, original URL, or content, raise `ValueError`; otherwise render one detail page, preferring the selected item.

- [ ] **Step 7: Run render and site-build tests**

Run: `python3 -m unittest tests.test_radar_render tests.test_radar_site_build -v`

Expected: all tests pass; `/all/`, dated issue routes, unique detail routes, and internal links exist.

- [ ] **Step 8: Commit**

```bash
git add src/templates/radar-index.html src/templates/radar-issue.html src/templates/radar-item.html scripts/radar_render.py tests/test_radar_render.py tests/test_radar_site_build.py
git commit -m "feat: render selected and full-newspaper routes"
```

---

### Task 5: Add HN·HOT Navigation, Static Pages, and AI Daily

**Files:**
- Create: `src/templates/about.html`
- Create: `src/templates/changelog.html`
- Modify: `src/templates/base.html`
- Modify: `scripts/radar_render.py`
- Modify: `tests/test_radar_site_build.py`

**Interfaces:**
- Produces a shared sidebar on every radar route.
- Produces `/daily/`, `/about/`, and `/changelog/` static routes.

- [ ] **Step 1: Add failing route and copy tests**

```python
def test_builds_hn_hot_navigation_and_supporting_routes(self):
    build_site(content, site)
    home = (site / "index.html").read_text(encoding="utf-8")
    self.assertIn("HN·HOT", home)
    for label in ("精选", "全部信息", "AI 日报", "关于", "更新日志"):
        self.assertIn(label, home)
    self.assertNotIn("自动筛选值得持续关注", home)
    self.assertTrue((site / "daily/index.html").is_file())
    self.assertTrue((site / "about/index.html").is_file())
    self.assertTrue((site / "changelog/index.html").is_file())
```

- [ ] **Step 2: Run the route test and verify failure**

Run: `python3 -m unittest tests.test_radar_site_build.RadarSiteBuildTests.test_builds_hn_hot_navigation_and_supporting_routes -v`

Expected: failure because the routes and brand are absent.

- [ ] **Step 3: Centralize navigation rendering**

```python
NAV_ITEMS = (("精选", "/"), ("全部信息", "/all/"), ("AI 日报", "/daily/"))
MORE_ITEMS = (("关于", "/about/"), ("更新日志", "/changelog/"))

def render_primary_nav(active):
    def links(items):
        return "".join(f'<a href="{path}"' + (' class="active" aria-current="page"' if label == active else "") + f'>{html.escape(label)}</a>' for label, path in items)
    return f'<a class="brand" href="/">HN·HOT</a><span class="nav-label">内容</span><nav>{links(NAV_ITEMS)}</nav><span class="nav-label">更多</span><nav>{links(MORE_ITEMS)}</nav>'
```

- [ ] **Step 4: Render minimal About and Changelog pages**

`about.html` contains only the heading `关于` and concise factual paragraphs describing HN·HOT. `changelog.html` contains heading `更新日志` and a dated list whose first entry is `2026-07-11 · HN·HOT 界面与完整读报设计`.

- [ ] **Step 5: Render AI Daily without inventing content**

Use existing `content/daily/*.json`. If records exist, render the latest daily at `/daily/index.html` with `render_daily()` from `scripts/render_site.py`; if none exist, render a minimal page with heading `AI 日报` and `暂无日报`. Do not create new report data.

- [ ] **Step 6: Run site-build and digest rendering tests**

Run: `python3 -m unittest tests.test_radar_site_build tests.test_radar_render tests.test_digest_contract -v`

Expected: all tests pass and every navigation route exists.

- [ ] **Step 7: Commit**

```bash
git add src/templates/about.html src/templates/changelog.html src/templates/base.html scripts/radar_render.py tests/test_radar_site_build.py
git commit -m "feat: add HN HOT navigation and supporting routes"
```

---

### Task 6: Implement Themes, Search, and Responsive Behavior

**Files:**
- Modify: `src/templates/base.html`
- Modify: `src/static/app.js`
- Modify: `src/static/styles.css`
- Modify: `tests/test_radar_render.py`

**Interfaces:**
- Uses `data-search-input`, `data-search-title`, and `data-search-scope` emitted by Task 4.
- Uses `localStorage["hn-hot-theme"]` with values `dark`, `system`, or `light`.
- Applies `document.documentElement.dataset.theme` as `dark` or `light` and keeps `data-theme-choice` as the persisted three-state choice.

- [ ] **Step 1: Add failing static asset contract tests**

```python
def test_theme_search_and_mobile_contracts_exist(self):
    js = STATIC.joinpath("app.js").read_text(encoding="utf-8")
    css = STATIC.joinpath("styles.css").read_text(encoding="utf-8")
    base = TEMPLATE.joinpath("base.html").read_text(encoding="utf-8")
    self.assertIn("hn-hot-theme", js)
    self.assertIn("matchMedia", js)
    self.assertIn("data-search-input", js)
    self.assertIn("data-theme=\"light\"", css)
    self.assertIn("prefers-color-scheme", base)
    self.assertIn("@media (max-width: 760px)", css)
```

- [ ] **Step 2: Run the asset test and verify failure**

Run: `python3 -m unittest tests.test_radar_render.RadarRenderTests.test_theme_search_and_mobile_contracts_exist -v`

Expected: failure because theme/search contracts are absent.

- [ ] **Step 3: Add early theme initialization to the document head**

```html
<script>
  (() => {
    const choice = localStorage.getItem("hn-hot-theme") || "system";
    const dark = choice === "dark" || (choice === "system" && matchMedia("(prefers-color-scheme: dark)").matches);
    document.documentElement.dataset.themeChoice = choice;
    document.documentElement.dataset.theme = dark ? "dark" : "light";
  })();
</script>
```

- [ ] **Step 4: Implement three-state theme behavior and search filtering**

```javascript
const THEME_KEY = "hn-hot-theme";
const media = matchMedia("(prefers-color-scheme: dark)");
function applyTheme(choice) {
  const dark = choice === "dark" || (choice === "system" && media.matches);
  document.documentElement.dataset.themeChoice = choice;
  document.documentElement.dataset.theme = dark ? "dark" : "light";
}
document.querySelectorAll("[data-theme-choice]").forEach((button) => button.addEventListener("click", () => {
  localStorage.setItem(THEME_KEY, button.dataset.themeChoice);
  applyTheme(button.dataset.themeChoice);
}));
media.addEventListener("change", () => {
  if ((localStorage.getItem(THEME_KEY) || "system") === "system") applyTheme("system");
});
document.querySelectorAll("[data-search-input]").forEach((input) => input.addEventListener("input", () => {
  const query = input.value.trim().toLocaleLowerCase("zh-CN");
  const scope = input.closest("[data-search-scope]");
  scope.querySelectorAll("[data-search-title]").forEach((row) => {
    row.hidden = query !== "" && !row.dataset.searchTitle.toLocaleLowerCase("zh-CN").includes(query);
  });
  scope.querySelectorAll("[data-search-group]").forEach((group) => {
    group.hidden = !group.querySelector("[data-search-title]:not([hidden])");
  });
  scope.querySelector("[data-search-empty]").hidden = Boolean(scope.querySelector("[data-search-title]:not([hidden])"));
}));
```

- [ ] **Step 5: Replace the dark-only CSS with semantic theme variables and responsive layout**

Define variables under `:root, html[data-theme="dark"]` and override them under `html[data-theme="light"]`. Add a 216px sticky sidebar above 760px; below 760px switch to one column, show a menu button, make navigation collapsible, allow category wrapping, and preserve visible focus outlines. Do not hide overflowing titles or set a fixed content height.

- [ ] **Step 6: Run render tests and full unit suite**

Run: `python3 -m unittest tests.test_radar_render -v`

Expected: all asset and markup contract tests pass.

Run: `python3 -m unittest discover -s tests -v`

Expected: the entire suite passes.

- [ ] **Step 7: Commit**

```bash
git add src/templates/base.html src/static/app.js src/static/styles.css tests/test_radar_render.py
git commit -m "feat: add HN HOT themes search and responsive UI"
```

---

### Task 7: Real-Data Migration, Documentation, and Visual Verification

**Files:**
- Modify: `README.md`
- Modify: `tests/test_radar_real_dates.py`
- Generated and committed: `content/issues/2026-07-08.json`, `content/issues/2026-07-09.json`, `content/issue-items/2026-07-08/*.json`, `content/issue-items/2026-07-09/*.json`, `content/indexes/issues.json`, `content/indexes/search-selected.json`, `content/indexes/search-issues.json`
- Generated and committed: updated selected indexes if their public shape changes.

**Interfaces:**
- Consumes the existing real raw/model artifacts through the documented radar pipeline.
- Produces a fully rendered static site and screenshot evidence at desktop dark, desktop light, and mobile widths.

- [ ] **Step 1: Add real-date publication assertions**

```python
def test_real_dates_publish_complete_scored_issues(self):
    for date, expected_pages in (("2026-07-08", 8), ("2026-07-09", 7)):
        issue = load_json(CONTENT / "issues" / f"{date}.json")
        self.assertEqual(issue["page_count"], expected_pages)
        self.assertEqual(issue["scored_article_count"], len(list((CONTENT / "issue-items" / date).glob("*.json"))))
        self.assertEqual([p["page_number"] for p in issue["pages"]], sorted(p["page_number"] for p in issue["pages"]))
```

- [ ] **Step 2: Run the real-data test and verify missing issue files fail**

Run: `RADAR_REAL_DATA_REQUIRED=1 python3 -m unittest tests.test_radar_real_dates -v`

Expected: failure because real issue publication files do not exist yet.

- [ ] **Step 3: Regenerate real dates through the radar pipeline**

Run: `bash scripts/run_radar_pipeline.sh 2026-07-08`

Expected: `STATUS=COMPLETE`. If it reports `STATUS=MODEL_OUTPUT_REQUIRED`, write only the requested semantic model-output artifact using the exact candidate IDs and fingerprint printed by the pipeline, then rerun the same command.

Run: `bash scripts/run_radar_pipeline.sh 2026-07-09`

Expected: `STATUS=COMPLETE` under the same contract. Do not hand-edit generated publishable JSON.

Expected: both dates produce issue documents, issue items, selected indexes, search indexes, and a successful site build.

- [ ] **Step 4: Correct and expand README commands**

Document `python3 -m scripts.preview` rather than the broken direct-script import form. Add the route list and explain that `/all/{date}/` publishes scored articles by newspaper page while raw and audit files remain local.

- [ ] **Step 5: Run all automated verification**

Run: `python3 -m unittest discover -s tests -v`

Expected: all tests pass.

Run: `RADAR_REAL_DATA_REQUIRED=1 python3 -m unittest discover -s tests -v`

Expected: all tests pass with both verified dates.

Run: `python3 -m scripts.radar_render`

Expected: exit code 0 and `site/` contains `/`, `/all/`, both dated issue routes, `/daily/`, `/about/`, `/changelog/`, and unique detail routes.

- [ ] **Step 6: Visually compare against AIHOT at matched desktop viewport**

Start `python3 -m scripts.preview`, capture HN·HOT at the same approximate viewport used for the AIHOT evidence, and compare sidebar width, content width, category/search density, focus visibility, title spacing, borders, and dark-theme hierarchy. Any correction in this step is limited to CSS variables, spacing, widths, borders, radii, font weight, and responsive breakpoints; rerun `python3 -m unittest tests.test_radar_render tests.test_radar_site_build -v` after each correction.

- [ ] **Step 7: Verify light and mobile states**

Capture desktop light mode and a 390px-wide mobile state. Confirm no clipping or horizontal page overflow, title wrapping, visible navigation access, working theme controls, correct PDF placement, and readable focus/search states.

- [ ] **Step 8: Inspect console and internal links**

Confirm browser console has no errors on `/`, `/all/`, and one detail page. Run the existing `validate_internal_links(site)` assertion and manually open one original page link and one PDF link from the 2026-07-08 issue.

- [ ] **Step 9: Commit generated content and documentation**

```bash
git add README.md tests/test_radar_real_dates.py content/items content/issues content/issue-items content/indexes
git commit -m "feat: publish HN HOT complete reading experience"
```

- [ ] **Step 10: Final verification before completion claim**

Run: `git status --short`

Expected: only known local audit screenshots under ignored or intentionally untracked temporary paths; no uncommitted source, test, template, content, or documentation changes.

Run: `git log -7 --oneline`

Expected: one focused commit per completed task.
