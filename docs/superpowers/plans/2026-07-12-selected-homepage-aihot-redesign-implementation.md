# HN·HOT Selected Homepage AIHOT Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add recommendation reasons to the radar pipeline and rebuild only the selected homepage as an AIHOT-aligned, three-date, progressively loaded responsive feed.

**Architecture:** Keep the static Python/Jinja-like template architecture. The content pipeline publishes schema-v4 selected records and summary indexes; the site builder embeds the newest date and writes one JSON feed payload per recent date, while native JavaScript progressively appends older dates, expands search across all three payloads, and manages the two-state theme switch.

**Tech Stack:** Python 3.9+, `unittest`, static HTML templates, CSS custom properties, native browser JavaScript (`fetch`, `IntersectionObserver`, `matchMedia`, `localStorage`).

## Global Constraints

- Scope is limited to the selected homepage, selected category pages, selected item detail fields, and their direct data contracts; do not change `/all/` or `/all/{date}/` templates, layout, routes, or interactions.
- Use the approved “A · AIHOT high-fidelity” direction and do not add AIHOT's timeline.
- Desktop rows show title, AI summary, and recommendation reason; viewports `<= 760px` show title and recommendation reason only.
- The initial HTML contains the newest selected date; progressive loading covers at most the newest three dates that actually contain selected items.
- Remove selected-home pagination HTML and generated `/page/{n}/` routes.
- Search covers title, AI summary, and recommendation reason across all three recent dates.
- `recommendation_reason` is required, non-empty, one or two Chinese sentences, explains why the article is worth reading, and must not equal the normalized AI summary.
- Backfill 2026-07-08 and 2026-07-09 with genuine model-generated reasons; do not synthesize them by copying summaries.
- Run the new pipeline with real 2026-07-10 input and verify the homepage displays July 10 first, then loads July 9 and July 8.
- Keep the project dependency-free and preserve atomic content/site publication.

---

### Task 1: Extend the selected-item and model-output contracts

**Files:**
- Modify: `scripts/radar_contract.py`
- Modify: `scripts/radar_model.py`
- Modify: `scripts/finalize_radar.py`
- Modify: `tests/radar_fixtures.py`
- Modify: `tests/test_radar_model.py`
- Modify: `tests/test_finalize_radar.py`
- Modify: `docs/codex-digest-generation.md`

**Interfaces:**
- Consumes: `validate_model_output(model_input, model_output, candidates) -> list[dict]` and `validate_stored_item(item) -> None`.
- Produces: schema version `4`, prompt version `radar-v2`, model item field `recommendation_reason: str`, and stored field `block.recommendation_reason: str`.

- [ ] **Step 1: Update fixtures and add failing model-contract tests**

Change `model_output_for()` and `stored_item()` in `tests/radar_fixtures.py` so every generated selected item contains a reason distinct from its summary:

```python
"recommendation_reason": f"{item['title']}包含影响海南读者判断的具体信号，值得继续追踪。",
```

and:

```python
"recommendation_reason": reason or f"第 {index} 篇内容提供了值得继续追踪的海南本地信号。",
```

Add a `reason=None` keyword argument to `stored_item()`.

Add these cases to `tests/test_radar_model.py`:

```python
def test_recommendation_reason_is_required(self):
    output = model_output_for(self.model_input)
    del output["items"][0]["recommendation_reason"]
    with self.assertRaisesRegex(ModelOutputError, "recommendation_reason"):
        validate_model_output(self.model_input, output, self.candidates)

def test_recommendation_reason_must_not_equal_summary(self):
    output = model_output_for(self.model_input)
    output["items"][0]["recommendation_reason"] = output["items"][0]["ai_summary"]
    with self.assertRaisesRegex(ModelOutputError, "must differ from ai_summary"):
        validate_model_output(self.model_input, output, self.candidates)
```

- [ ] **Step 2: Run the focused tests and confirm the contract fails**

Run:

```bash
python3 -m unittest tests.test_radar_model tests.test_finalize_radar -v
```

Expected: FAIL because `recommendation_reason` is not yet an accepted model or stored block field.

- [ ] **Step 3: Implement schema-v4 validation and propagation**

In `scripts/radar_contract.py`, set:

```python
SCHEMA_VERSION = 4
PROMPT_VERSION = "radar-v2"
BLOCK_FIELDS = {
    "source", "title", "content", "ai_summary",
    "recommendation_reason", "original_url",
}
```

Validate the new stored value beside `ai_summary`:

```python
for field in ("source", "title", "content", "ai_summary", "recommendation_reason"):
    if not non_empty(block.get(field)):
        raise ContractError(f"block.{field} is required")
if _normalized(block["recommendation_reason"]) == _normalized(block["ai_summary"]):
    raise ContractError("block.recommendation_reason must differ from ai_summary")
```

Move or add a shared whitespace-normalization helper in `radar_contract.py` so both stored and model validation use the same behavior.

In `scripts/radar_model.py`, add `recommendation_reason` to `MODEL_ITEM_FIELDS`, require it to be non-empty, and reject normalized equality with `ai_summary`:

```python
if not non_empty(item.get("recommendation_reason")):
    raise ModelOutputError(f"items[{index}].recommendation_reason is required")
if normalized_text(item["recommendation_reason"]) == normalized_text(item["ai_summary"]):
    raise ModelOutputError(
        f"items[{index}].recommendation_reason must differ from ai_summary"
    )
```

In `scripts/finalize_radar.py`, propagate the stripped value:

```python
"recommendation_reason": semantic["recommendation_reason"].strip(),
```

- [ ] **Step 4: Update the model-generation contract documentation**

In `docs/codex-digest-generation.md`, explicitly require this field in each model item and include this instruction:

```text
recommendation_reason 用一至两句中文解释“为什么值得读”，强调影响、稀缺信息、决策价值、趋势信号或海南关联；不得复述标题或 ai_summary，不得返回内部评分过程。
```

- [ ] **Step 5: Run contract tests**

Run:

```bash
python3 -m unittest tests.test_radar_model tests.test_finalize_radar tests.test_radar_store -v
```

Expected: PASS.

- [ ] **Step 6: Commit the contract change**

```bash
git add scripts/radar_contract.py scripts/radar_model.py scripts/finalize_radar.py tests/radar_fixtures.py tests/test_radar_model.py tests/test_finalize_radar.py docs/codex-digest-generation.md
git commit -m "feat: add selected recommendation reasons"
```

---

### Task 2: Publish recent-date feed and search payloads

**Files:**
- Modify: `scripts/radar_indexes.py`
- Modify: `tests/test_radar_indexes.py`
- Modify: `tests/radar_fixtures.py`

**Interfaces:**
- Consumes: valid schema-v4 selected items.
- Produces: `_summary(item)` rows containing `recommendation_reason`; `build_recent_selected_feeds(items, limit=3) -> dict[str, dict]`; `recent-selected.json` with ordered dates; `selected-feed/{date}.json` payloads.

- [ ] **Step 1: Write failing index tests**

Replace the existing summary-field expectation in `tests/test_radar_indexes.py` and add three-date behavior:

```python
def test_selected_indexes_include_summary_and_recommendation_reason(self):
    indexes = build_indexes(
        [stored_item(1, summary="私有摘要", reason="这条信息揭示海南本地变化。")],
        "2026-07-10",
    )
    row = indexes["all/page-001.json"]["items"][0]
    self.assertEqual(row["ai_summary"], "私有摘要")
    self.assertEqual(row["recommendation_reason"], "这条信息揭示海南本地变化。")

def test_recent_selected_feeds_publish_newest_three_nonempty_dates(self):
    items = [
        stored_item(1, date="2026-07-07"),
        stored_item(2, date="2026-07-08"),
        stored_item(3, date="2026-07-09"),
        stored_item(4, date="2026-07-10"),
    ]
    indexes = build_indexes(items, "2026-07-10")
    self.assertEqual(
        indexes["recent-selected.json"]["dates"],
        ["2026-07-10", "2026-07-09", "2026-07-08"],
    )
    self.assertNotIn("selected-feed/2026-07-07.json", indexes)
    self.assertEqual(indexes["selected-feed/2026-07-10.json"]["count"], 1)
```

Also assert that `search-selected.json` rows contain `recommendation_reason`.

- [ ] **Step 2: Run and confirm index tests fail**

Run:

```bash
python3 -m unittest tests.test_radar_indexes -v
```

Expected: FAIL because summary rows and recent feed indexes lack the new fields.

- [ ] **Step 3: Implement summary propagation and recent-date indexes**

Add the reason to `_summary()` and selected search rows:

```python
"recommendation_reason": item["block"]["recommendation_reason"],
```

Add:

```python
def build_recent_selected_feeds(items, limit=3):
    dates = sorted({item["published_date"] for item in items}, reverse=True)[:limit]
    ordered = sorted(items, key=lambda item: (item["daily_rank"], item["item_id"]))
    payloads = {
        f"selected-feed/{published_date}.json": {
            "date": published_date,
            "count": sum(item["published_date"] == published_date for item in items),
            "items": [
                _summary(item) for item in ordered
                if item["published_date"] == published_date
            ],
        }
        for published_date in dates
    }
    return {
        "recent-selected.json": {
            "dates": dates,
            "feeds": [f"/static/selected-feed/{value}.json" for value in dates],
        },
        **payloads,
    }
```

Merge this result into `build_indexes()` after the normal date indexes.

- [ ] **Step 4: Run index and transaction tests**

Run:

```bash
python3 -m unittest tests.test_radar_indexes tests.test_radar_transaction -v
```

Expected: PASS and the atomic store accepts the additional index paths.

- [ ] **Step 5: Commit the published-feed indexes**

```bash
git add scripts/radar_indexes.py tests/test_radar_indexes.py tests/radar_fixtures.py
git commit -m "feat: publish recent selected feeds"
```

---

### Task 3: Rebuild selected homepage markup without pagination

**Files:**
- Modify: `scripts/radar_render.py`
- Modify: `src/templates/radar-index.html`
- Modify: `src/templates/radar-item.html`
- Modify: `tests/test_radar_render.py`
- Modify: `tests/test_radar_site_build.py`

**Interfaces:**
- Consumes: newest `selected-feed/{date}.json`, `recent-selected.json`, and `focus.json`.
- Produces: `render_selected_row(item, focus_rank=None) -> str`, initial homepage HTML with an embedded feed manifest, and `/static/selected-feed/*.json` files.

- [ ] **Step 1: Replace render expectations with the approved markup contract**

Update `tests/test_radar_render.py` to assert:

```python
self.assertIn('<strong class="current-date">7月10日</strong>', rendered)
self.assertIn('<span class="current-date-meta">星期五 · 1 条</span>', rendered)
self.assertIn('class="search-submit"', rendered)
self.assertIn("新闻精选", rendered)
self.assertIn('class="story-summary"', rendered)
self.assertIn('class="story-reason"', rendered)
self.assertIn("为什么值得读", rendered)
self.assertIn('data-selected-feed-manifest', rendered)
self.assertNotIn("pagination", rendered)
self.assertNotIn("第 1 /", rendered)
```

Update the detail test to require “推荐理由” between AI summary and source body.

Update `tests/test_radar_site_build.py` so it no longer expects `site/page/2/index.html`, and instead expects:

```python
self.assertFalse((site / "page/2/index.html").exists())
self.assertTrue((site / "static/selected-feed/2026-07-10.json").is_file())
```

- [ ] **Step 2: Run focused render tests and confirm failure**

Run:

```bash
python3 -m unittest tests.test_radar_render tests.test_radar_site_build -v
```

Expected: FAIL on the old title, pagination route, absent recommendation markup, and absent feed JSON.

- [ ] **Step 3: Refactor renderer functions around selected-feed semantics**

Replace `_feed_date_heading()` output with `月日 + 星期X · N条`. Use `星期一` through `星期日`, not `周一` labels.

Replace `_selected_row()` with markup that always contains both text layers:

```python
return (
    f'<article class="selected-story" data-selected-id="{item_id}" '
    f'data-search-text="{search_text}">'
    f'{rank_markup}<a class="story-main" href="{detail_path}">'
    f'<strong class="story-title">{title}</strong>'
    f'<p class="story-summary">{summary}</p>'
    f'<p class="story-reason"><span>为什么值得读</span>{reason}</p>'
    f'</a>{_bookmark_button(item)}</article>'
)
```

Use escaped concatenated title, summary, and reason for `data-search-text`.

Render focus rows with the same function plus a `focus_rank`; omit summary and reason using a `focus-story` modifier so the focus panel remains title-only.

- [ ] **Step 4: Update the selected template and detail template**

Change `src/templates/radar-index.html` to:

```html
<div class="app-shell radar-shell">
  $nav
  <main class="content-shell radar-content" data-search-scope="selected">
    <header class="selected-header">
      <div class="selected-date">$date_heading</div>
      <form class="selected-search" data-selected-search>
        <label class="sr-only" for="selected-search">搜索精选</label>
        <input id="selected-search" type="search" placeholder="搜索标题/摘要/推荐理由…">
        <button class="search-submit" type="submit">搜索</button>
      </form>
    </header>
    <nav class="category-tabs" aria-label="精选分类">$category_links</nav>
    $focus_section
    <section class="radar-feed" data-selected-feed>$date_groups</section>
    <div class="feed-loader" data-feed-loader aria-live="polite"></div>
    <script type="application/json" data-selected-feed-manifest>$feed_manifest</script>
    <p class="empty-state" data-search-empty hidden>没有匹配结果</p>
  </main>
</div>
```

Add a `$recommendation_section` slot to `src/templates/radar-item.html` immediately after the AI summary. In `render_item()`, populate it only for selected items (`"category" in item`) and use an empty string for unselected complete-reading items, so the complete-reading contract remains unchanged:

```html
recommendation_section = (
    '<section class="recommendation-reason"><h2>推荐理由</h2>'
    f'<p>{html.escape(block["recommendation_reason"])}</p></section>'
    if "category" in item else ""
)
```

- [ ] **Step 5: Copy feed JSON into the built site's static directory and stop generating pagination routes**

In `build_site()`:

- Read `indexes/recent-selected.json`.
- Copy each indexed `indexes/selected-feed/{date}.json` to `staging/static/selected-feed/{date}.json`.
- Render only the newest `all/page-001.json` items belonging to the newest manifest date into `/index.html`.
- Do not iterate later `all/page-*.json` files into `/page/{n}/index.html`.
- Add `data-selected-category="$active_category"` to the homepage main element. Apply the same recent feed manifest to category pages; `render_index()` filters the initial date and `renderSelectedDate()` filters fetched items where `item.category !== activeCategory`, except when `activeCategory === "全部"`.
- Keep `/date/{date}/` routes as static date archives.

- [ ] **Step 6: Run renderer and site-builder tests**

Run:

```bash
python3 -m unittest tests.test_radar_render tests.test_radar_site_build -v
```

Expected: PASS with no selected pagination route.

- [ ] **Step 7: Commit the markup and build changes**

```bash
git add scripts/radar_render.py src/templates/radar-index.html src/templates/radar-item.html tests/test_radar_render.py tests/test_radar_site_build.py
git commit -m "feat: rebuild selected homepage markup"
```

---

### Task 4: Add progressive loading, complete search, and the theme slider

**Files:**
- Modify: `src/static/app.js`
- Modify: `scripts/radar_render.py`
- Modify: `tests/test_radar_render.py`
- Create: `tests/test_selected_home_js.py`

**Interfaces:**
- Consumes: `<script data-selected-feed-manifest>` and `/static/selected-feed/{date}.json`.
- Produces: `initSelectedFeed()`, `loadSelectedDate(date)`, `renderSelectedDate(payload)`, `runSelectedSearch(query)`, and accessible `[data-theme-toggle]` state.

- [ ] **Step 1: Add failing static-JS contract tests**

Create `tests/test_selected_home_js.py`:

```python
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class SelectedHomeJavaScriptTests(unittest.TestCase):
    def test_progressive_feed_search_and_fallback_contracts_exist(self):
        js = (ROOT / "src/static/app.js").read_text(encoding="utf-8")
        self.assertIn("IntersectionObserver", js)
        self.assertIn("data-selected-feed-manifest", js)
        self.assertIn("loadSelectedDate", js)
        self.assertIn("renderSelectedDate", js)
        self.assertIn("data-load-more", js)
        self.assertIn("加载失败，重试", js)
        self.assertIn("recommendation_reason", js)
        self.assertNotIn('choice === "system"', js)

    def test_theme_control_has_switch_semantics(self):
        rendered = render_primary_nav("精选")
        self.assertIn('role="switch"', rendered)
        self.assertIn('data-theme-toggle', rendered)
```

- [ ] **Step 2: Run and confirm JS contract tests fail**

Run:

```bash
python3 -m unittest tests.test_selected_home_js -v
```

Expected: FAIL because the old script has no progressive feed and still exposes three theme buttons.

- [ ] **Step 3: Implement a two-state accessible theme switch**

Change `render_primary_nav()` to output:

```html
<button class="theme-toggle" type="button" role="switch"
        aria-checked="false" data-theme-toggle>
  <span aria-hidden="true" class="theme-toggle-track"><span></span></span>
  <span class="sr-only">切换亮色或暗色主题</span>
</button>
```

Keep the inline boot script's no-preference system detection. Replace three-button listeners in `app.js` with one toggle that writes only `light` or `dark`, updates `aria-checked`, and updates `documentElement.dataset.theme`.

- [ ] **Step 4: Implement progressive feed loading and fallback**

Use a `Set` of loaded dates. Parse the embedded manifest once. Render payloads with DOM methods (`createElement`, `textContent`, `setAttribute`) rather than interpolating untrusted strings into `innerHTML`.

Required state machine:

```javascript
const selectedFeedState = {
  dates: [],
  loaded: new Set(),
  failed: null,
  loading: false,
};
```

`loadSelectedDate(date)` must:

- no-op if `loading` or already loaded;
- fetch the exact manifest path;
- verify `payload.date === date` and `Array.isArray(payload.items)`;
- append one date group;
- add the date to `loaded` only after successful render;
- on failure show a button with `data-load-more` and text `加载失败，重试`.

Use `IntersectionObserver` with `rootMargin: "500px 0px"`. If unavailable, show a `加载更多` button that calls the same function.

- [ ] **Step 5: Implement search across all recent feeds**

On form submit, load every manifest feed using `Promise.all`, flatten items, filter the normalized concatenation of `title`, `ai_summary`, and `recommendation_reason`, and replace the feed with grouped matching results. On empty query, restore the normal progressive feed using cached payloads and the previous loaded-date set.

- [ ] **Step 6: Run JS and renderer tests**

Run:

```bash
python3 -m unittest tests.test_selected_home_js tests.test_radar_render -v
```

Expected: PASS.

- [ ] **Step 7: Commit behavior changes**

```bash
git add src/static/app.js scripts/radar_render.py tests/test_radar_render.py tests/test_selected_home_js.py
git commit -m "feat: load and search recent selected feeds"
```

---

### Task 5: Replace selected-home CSS with the approved responsive visual system

**Files:**
- Modify: `src/static/styles.css`
- Modify: `tests/test_radar_render.py`

**Interfaces:**
- Consumes: semantic classes from Task 3 and the theme toggle from Task 4.
- Produces: one authoritative selected-home style section with desktop and `<= 760px` rules.

- [ ] **Step 1: Replace brittle legacy-CSS tests with visual invariants**

Remove assertions that require old duplicate cascade markers. Add assertions for:

```python
self.assertIn(".selected-header", css)
self.assertIn(".search-submit", css)
self.assertIn(".story-reason", css)
self.assertIn(".theme-toggle-track", css)
self.assertIn(".category-tabs a.active::after", css)
self.assertIn("@media (max-width: 760px)", css)
self.assertIn(".selected-story .story-summary { display: none; }", mobile)
self.assertIn(".date-group {", mobile)
self.assertIn("background: transparent", mobile)
```

Also assert that the file contains exactly one `/* Selected homepage */` marker and no `/* HN·HOT final visual cascade. */` marker.

- [ ] **Step 2: Run CSS contract tests and confirm failure**

Run:

```bash
python3 -m unittest tests.test_radar_render -v
```

Expected: FAIL on missing approved classes and remaining legacy cascade markers.

- [ ] **Step 3: Delete superseded selected-home cascades and add one authoritative section**

Preserve styles used by issue, daily, weekly, article detail, and navigation pages. Remove only duplicate blocks for `.content-tools`, `.focus-section`, `.date-group`, `.selected-row`, `.category-tabs`, `.pagination`, and the old `.theme-switch` that are replaced by the new markup.

Add a single `/* Selected homepage */` section implementing:

- a `216px` desktop sidebar with 13–14px navigation labels;
- open header and category areas on the page background;
- category active underline via `::after`;
- connected search input and button;
- focus as the only bordered/shadowed card;
- transparent date groups and divider-only stories;
- `.story-summary` in secondary text and `.story-reason` in the recommendation color role;
- no hover vertical movement on news rows;
- an accessible 40px theme toggle hit target with a sliding thumb;
- `prefers-reduced-motion: reduce` disabling thumb and color transitions.

- [ ] **Step 4: Add mobile information hierarchy**

Inside the existing `@media (max-width: 760px)` boundary:

```css
.selected-story .story-summary { display: none; }
.selected-story .story-reason { display: block; }
.selected-header { padding-inline: 16px; }
.selected-search { display: none; }
.date-group { margin: 0; padding: 12px 16px 0; background: transparent; }
```

Keep horizontal scrolling for categories, fixed bottom navigation, safe-area padding, and at least a 40px bookmark target.

- [ ] **Step 5: Run CSS and full renderer tests**

Run:

```bash
python3 -m unittest tests.test_radar_render tests.test_selected_home_js tests.test_radar_site_build -v
```

Expected: PASS.

- [ ] **Step 6: Commit the responsive visual system**

```bash
git add src/static/styles.css tests/test_radar_render.py
git commit -m "feat: align selected homepage with AIHOT"
```

---

### Task 6: Backfill July 8 and July 9 selected records

**Files:**
- Modify: `content/items/2026-07-08/*.json`
- Modify: `content/items/2026-07-09/*.json`
- Regenerate: `content/indexes/**/*.json`
- Modify: `tests/test_radar_real_dates.py`

**Interfaces:**
- Consumes: the original July 8/9 model inputs and raw content plus the schema-v4 model contract.
- Produces: validated schema-v4 selected content for both dates and regenerated indexes with real recommendation reasons.

- [ ] **Step 1: Add a failing committed-content completeness test**

Add to `tests/test_radar_real_dates.py`:

```python
def test_committed_selected_items_have_distinct_recommendation_reasons(self):
    for published_date in ("2026-07-08", "2026-07-09"):
        for path in (ROOT / "content/items" / published_date).glob("*.json"):
            item = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(item["schema_version"], 4)
            reason = item["block"]["recommendation_reason"].strip()
            summary = item["block"]["ai_summary"].strip()
            self.assertTrue(reason)
            self.assertNotEqual("".join(reason.split()), "".join(summary.split()))
```

- [ ] **Step 2: Run and confirm the committed data test fails**

Run:

```bash
python3 -m unittest tests.test_radar_real_dates.RadarRealDateTests.test_committed_selected_items_have_distinct_recommendation_reasons -v
```

Expected: FAIL because committed items are schema v3 and have no reasons.

- [ ] **Step 3: Regenerate model outputs for each date**

Run both dates explicitly:

```bash
bash scripts/run_radar_pipeline.sh 2026-07-08
bash scripts/run_radar_pipeline.sh 2026-07-09
```

Use the printed `MODEL_INPUT_JSON` to create a new schema-v4 `MODEL_OUTPUT_JSON`. Generate every reason from that candidate's title, content, and summary. Do not copy a reason between candidates and do not use the previous date's output. Re-run the same command until it prints `STATUS=COMPLETE`.

- [ ] **Step 4: Verify both backfills and generated indexes**

Run:

```bash
RADAR_REAL_DATA_REQUIRED=1 python3 -m unittest tests.test_radar_real_dates tests.test_radar_indexes -v
python3 scripts/radar_render.py content /tmp/hndaily-selected-backfill-site
```

Expected: PASS, and rendering completes without a contract error.

- [ ] **Step 5: Commit the backfilled public content**

```bash
git add content/items/2026-07-08 content/items/2026-07-09 content/indexes tests/test_radar_real_dates.py
git commit -m "data: backfill selected recommendation reasons"
```

Do not add ignored raw files, model inputs, model outputs, audits, `site/`, `.wrangler/`, `tmp/`, or `.superpowers/`.

---

### Task 7: Process real July 10 data and complete end-to-end acceptance

**Files:**
- Create through pipeline: `content/items/2026-07-10/*.json`
- Create through pipeline: `content/issues/2026-07-10.json`
- Create through pipeline: `content/issue-items/2026-07-10/*.json`
- Regenerate: `content/indexes/**/*.json`
- Modify: `tests/test_radar_real_dates.py`
- Save screenshots: `tmp/design-audit-selected-home/`

**Interfaces:**
- Consumes: real crawler output for `2026-07-10`, schema-v4 model output, and the completed homepage implementation.
- Produces: a three-date public library and verified desktop/mobile screenshots.

- [ ] **Step 1: Add a failing three-date site acceptance test**

Add:

```python
def test_real_july_10_is_newest_and_recent_manifest_has_three_dates(self):
    self.assertTrue((ROOT / "content/items/2026-07-10").is_dir())
    manifest = json.loads(
        (ROOT / "content/indexes/recent-selected.json").read_text(encoding="utf-8")
    )
    self.assertEqual(
        manifest["dates"],
        ["2026-07-10", "2026-07-09", "2026-07-08"],
    )
    with tempfile.TemporaryDirectory() as tmp:
        site = Path(tmp) / "site"
        build_site(ROOT / "content", site)
        homepage = (site / "index.html").read_text(encoding="utf-8")
        self.assertIn("7月10日", homepage)
        self.assertTrue((site / "static/selected-feed/2026-07-09.json").is_file())
        self.assertTrue((site / "static/selected-feed/2026-07-08.json").is_file())
```

- [ ] **Step 2: Run and confirm the July 10 acceptance test fails**

Run:

```bash
RADAR_REAL_DATA_REQUIRED=1 python3 -m unittest tests.test_radar_real_dates.RadarRealDateTests.test_real_july_10_is_newest_and_recent_manifest_has_three_dates -v
```

Expected: FAIL until July 10 content is published.

- [ ] **Step 3: Run the real July 10 pipeline**

Run:

```bash
bash scripts/run_radar_pipeline.sh 2026-07-10
```

Create the printed schema-v4 model output using only July 10 candidates, then rerun. Expected final output:

```text
STATUS=COMPLETE
```

- [ ] **Step 4: Run the complete automated suite**

Run:

```bash
RADAR_REAL_DATA_REQUIRED=1 python3 -m unittest discover -s tests -v
python3 scripts/radar_render.py content site
```

Expected: all tests PASS and static render completes.

- [ ] **Step 5: Verify progressive load and search in a local browser**

Start `python3 -m scripts.preview`. At `1440 × 1000`, verify:

- header reads `7月10日` followed by weekday and count;
- search has a visible button;
- focus is the only strong card;
- initial feed contains July 10;
- scrolling appends July 9 then July 8 exactly once;
- searching a known July 8 title before scrolling still returns it;
- the bottom contains no page number or pagination control;
- the theme slider persists light/dark selection.

Repeat at `733 × 860` and `393 × 852`; verify summaries are hidden and recommendation reasons remain visible.

- [ ] **Step 6: Capture and inspect visual evidence**

Save accepted screenshots as:

```text
tmp/design-audit-selected-home/01-desktop-light-1440x1000.png
tmp/design-audit-selected-home/02-desktop-dark-1440x1000.png
tmp/design-audit-selected-home/03-mobile-393x852.png
tmp/design-audit-selected-home/04-wide-mobile-733x860.png
```

Inspect each file and compare desktop/mobile screenshots against `references/aihot/screenshots/desktop-1440x1000.png` and `references/aihot/screenshots/mobile-393x852.png`. Reject and recapture blank, loading, cropped, overflowing, or bottom-nav-obscured states.

- [ ] **Step 7: Commit July 10 public content and acceptance tests**

```bash
git add content/items/2026-07-10 content/issues/2026-07-10.json content/issue-items/2026-07-10 content/indexes tests/test_radar_real_dates.py
git commit -m "data: publish july 10 selected acceptance"
```

- [ ] **Step 8: Final clean-tree and scope check**

Run:

```bash
git status --short
git diff HEAD~7 -- src/templates/radar-issue.html
```

Expected: only pre-existing ignored/untracked `.wrangler/` and `tmp/` may remain; the issue template diff is empty, proving the “全部信息” layout stayed out of scope.
