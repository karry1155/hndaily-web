# Entity Location Tags and Scoring Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add strictly constrained news actors, canonical Hainan administrative locations, and action facts to the radar pipeline and homepage, while publishing a truthful HTML audit of the unchanged scoring system.

**Architecture:** A versioned local administrative dictionary supplies deterministic location candidates before model analysis. The model returns evidence-backed actor records, candidate `location_id` values, and an action; Python validation rejects out-of-contract output and resolves IDs into canonical names/codes. Stored entities propagate through indexes to the frontend. A separate report generator reads scoring source code constants and committed content to produce a self-contained audit.

**Tech Stack:** Python 3 standard library, strict JSON contracts, unittest, server-rendered HTML, vanilla JavaScript and CSS.

## Global Constraints

- Administrative names must remain complete and canonical, including `市`, `县`, and `自治县` suffixes.
- The model cannot invent location names/codes or return a location outside the supplied candidate list.
- Missing or uncertain actors/locations are empty arrays; no guessed labels or placeholders.
- Existing scores, ranks, titles, bodies, URLs, categories, and recommendation reasons remain unchanged during backfill.
- The scoring audit documents the current system only; it does not alter scoring behavior.
- Work directly on `main`; preserve untracked `.wrangler/` and `tmp/`.

---

### Task 1: Versioned Hainan Administrative Dictionary

**Files:**
- Create: `data/hainan-administrative-divisions.json`
- Create: `scripts/radar_locations.py`
- Create: `tests/test_radar_locations.py`

**Interfaces:**
- Produces: `load_location_catalog(path: Path | None = None) -> LocationCatalog`
- Produces: `find_location_candidates(title: str, content: str, catalog: LocationCatalog) -> list[dict]`
- Produces: `resolve_location_mentions(mentions: list[dict], candidates: list[dict], catalog: LocationCatalog) -> list[dict]`

- [ ] **Step 1: Verify official codes and write failing catalog tests**

Test exact canonical examples and invalid records:

```python
def test_catalog_uses_canonical_names_and_codes():
    catalog = load_location_catalog()
    assert catalog.by_id["hainan-haikou"]["name"] == "海口市"
    assert catalog.by_id["hainan-sansha"]["code"] == "460300"
    assert catalog.by_id["hainan-baisha"]["name"] == "白沙黎族自治县"

def test_candidates_use_aliases_but_return_canonical_records():
    result = find_location_candidates("在白沙调研", "刘小明来到白沙黎族自治县", load_location_catalog())
    assert result[0]["name"] == "白沙黎族自治县"
```

- [ ] **Step 2: Run the focused test and confirm failure**

Run: `python3 -m unittest tests.test_radar_locations`

Expected: import/file failure because the dictionary and module do not exist.

- [ ] **Step 3: Implement dictionary loading, validation, candidate matching, and resolution**

The JSON root contains exact metadata (`version`, `source`, `verified_on`, `divisions`). Validate unique IDs/codes, official suffixes, levels in `province|prefecture|county`, and aliases as non-empty strings. Candidate output contains only `location_id` and canonical display metadata; resolver accepts only IDs present in that article's candidate set and copies canonical name/code/level from the catalog.

- [ ] **Step 4: Run location tests**

Run: `python3 -m unittest tests.test_radar_locations`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add data/hainan-administrative-divisions.json scripts/radar_locations.py tests/test_radar_locations.py
git commit -m "feat: add canonical Hainan location catalog"
```

### Task 2: Extend the Model Contract With Restricted Entities

**Files:**
- Modify: `scripts/radar_contract.py`
- Modify: `scripts/radar_model.py`
- Modify: `tests/radar_fixtures.py`
- Modify: `tests/test_radar_model.py`
- Modify: `tests/test_finalize_radar.py`
- Modify: `docs/codex-digest-generation.md`

**Interfaces:**
- `build_model_input(candidates)` adds `location_candidates` per item.
- `validate_model_output(...)` returns semantic items with exact `actors`, `location_mentions`, `action`, and `action_evidence` fields.

- [ ] **Step 1: Add failing strict-contract tests**

Cover valid examples, candidate-outside-whitelist rejection, unknown actor type, more than five actors/locations, extra keys, missing evidence, evidence absent from normalized title+content, and empty action paired with non-empty evidence.

```python
def test_rejects_location_outside_article_candidates(self):
    output = model_output_for(model_input)
    output["items"][0]["location_mentions"] = [{"location_id": "hainan-sanya", "evidence": "三亚市"}]
    with self.assertRaisesRegex(ModelOutputError, "location_id"):
        validate_model_output(model_input, output, candidates)
```

- [ ] **Step 2: Run tests and confirm contract failures**

Run: `python3 -m unittest tests.test_radar_model tests.test_finalize_radar`

Expected: failures for missing entity fields and missing location candidates.

- [ ] **Step 3: Upgrade schema/prompt versions and implement validation**

Add exact actor fields `name,type,role,evidence`; allowed types `person|organization|government|company`; exact location mention fields `location_id,evidence`. Validate evidence against normalized title plus content and preserve model order. Model input candidates expose only `location_id` and canonical `name`, never codes.

- [ ] **Step 4: Update prompt documentation**

Document the new exact JSON shape, the candidate-only rule, complete official administrative names, evidence requirement, and prohibition on model-generated codes and scores.

- [ ] **Step 5: Run focused tests**

Run: `python3 -m unittest tests.test_radar_model tests.test_finalize_radar tests.test_prepare_model_input`

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add scripts/radar_contract.py scripts/radar_model.py tests/radar_fixtures.py tests/test_radar_model.py tests/test_finalize_radar.py docs/codex-digest-generation.md
git commit -m "feat: constrain model entity extraction"
```

### Task 3: Persist and Publish Canonical Entities

**Files:**
- Modify: `scripts/finalize_radar.py`
- Modify: `scripts/radar_contract.py`
- Modify: `scripts/radar_indexes.py`
- Modify: `scripts/radar_store.py`
- Modify: `tests/test_radar_contract.py`
- Modify: `tests/test_radar_indexes.py`
- Modify: `tests/test_radar_store.py`

**Interfaces:**
- Stored selected item adds exact top-level `entities` object.
- `_summary(item)` publishes `entities` to every selected index.

- [ ] **Step 1: Write failing stored-entity and propagation tests**

Assert exact stored entity fields and that model `location_id` resolves to official name/code/level. Assert `entities` exists in `all`, `focus`, `dates`, `selected-feed`, and `search-selected`, but scoring fields remain unchanged.

- [ ] **Step 2: Run focused tests and confirm failure**

Run: `python3 -m unittest tests.test_radar_contract tests.test_radar_indexes tests.test_radar_store`

- [ ] **Step 3: Implement normalization and storage**

In `build_generation`, call the location resolver after model validation and store:

```python
"entities": {
    "actors": semantic["actors"],
    "locations": resolved_locations,
    "action": semantic["action"].strip(),
    "action_evidence": semantic["action_evidence"].strip(),
}
```

Extend strict stored-item validation, then pass the object unchanged through selected indexes and catalogs.

- [ ] **Step 4: Run focused tests**

Run: `python3 -m unittest tests.test_radar_contract tests.test_radar_indexes tests.test_radar_store tests.test_finalize_radar`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/finalize_radar.py scripts/radar_contract.py scripts/radar_indexes.py scripts/radar_store.py tests/test_radar_contract.py tests/test_radar_indexes.py tests/test_radar_store.py
git commit -m "feat: persist canonical news entities"
```

### Task 4: Backfill Existing Selected Content Without Rescoring

**Files:**
- Create: `scripts/backfill_radar_entities.py`
- Create: `tests/test_backfill_radar_entities.py`
- Modify: `content/items/*/*.json`
- Modify: `content/indexes/**/*.json`

**Interfaces:**
- Produces: `backfill_entities(content_root: Path, semantic_by_item_id: dict) -> dict`
- CLI accepts validated entity model output and rewrites items/indexes atomically.

- [ ] **Step 1: Write preservation and idempotence tests**

Use a temporary content store and assert the backfill changes only `schema_version` and `entities`; every existing score, rank, category, block field, opportunity field, ID and date remains byte-for-byte equivalent as parsed JSON. Running twice yields identical output.

- [ ] **Step 2: Run test and confirm failure**

Run: `python3 -m unittest tests.test_backfill_radar_entities`

- [ ] **Step 3: Implement atomic backfill**

Reuse strict model validation and location resolution. Rebuild all indexes with `build_indexes` and `build_search_indexes`; do not call `score_semantic` or `select_items` during backfill.

- [ ] **Step 4: Generate and validate entity output for existing dates**

Run the existing model workflow with the upgraded prompt for all committed selected dates, then apply the backfill CLI. Confirm examples resolve to `冯飞 · 三沙市`, `刘小明 · 白沙黎族自治县`, and `省政协 · 海口市`; leave unsupported fourth focus item empty.

- [ ] **Step 5: Run preservation and real-data tests**

Run: `python3 -m unittest tests.test_backfill_radar_entities tests.test_radar_real_dates`

Expected: all pass, including unchanged scores/ranks.

- [ ] **Step 6: Commit**

```bash
git add scripts/backfill_radar_entities.py tests/test_backfill_radar_entities.py content/items content/indexes
git commit -m "data: backfill canonical news entities"
```

### Task 5: Render Focus Entity Labels and Tighten Density

**Files:**
- Modify: `scripts/radar_render.py`
- Modify: `src/static/app.js`
- Modify: `src/static/styles.css`
- Modify: `src/templates/base.html`
- Modify: `tests/test_radar_render.py`
- Modify: `tests/test_selected_home_js.py`

**Interfaces:**
- Static and dynamic selected-story rendering both consume `item.entities`.
- Focus stories render `.story-entities`; ordinary feed stories do not.

- [ ] **Step 1: Add failing markup and CSS tests**

Assert full official labels, `冯飞 · 三沙市`, absent markup for empty entities, `align-items:center` for focus rows, reduced padding, two-line title clamp, and unchanged score/bookmark actions.

- [ ] **Step 2: Run focused frontend tests and confirm failure**

Run: `python3 -m unittest tests.test_radar_render tests.test_selected_home_js`

- [ ] **Step 3: Implement shared display rule**

Use the first actor and first location. Join present values with ` · `; never shorten administrative names. Static render escapes values; JavaScript uses `textContent`. Add `.story-entities` beneath the focus title only.

- [ ] **Step 4: Fix focus alignment and density**

Set focus rows to center alignment, use compact vertical padding, keep the entity line at muted 11–12px, and ensure missing metadata leaves no reserved height.

- [ ] **Step 5: Rebuild and run frontend tests**

Run: `python3 -m scripts.radar_render content site && python3 -m unittest tests.test_radar_render tests.test_selected_home_js tests.test_radar_site_build`

- [ ] **Step 6: Commit**

```bash
git add scripts/radar_render.py src/static/app.js src/static/styles.css src/templates/base.html tests/test_radar_render.py tests/test_selected_home_js.py
git commit -m "feat: show focus actors and locations"
```

### Task 6: Generate the Current Scoring-System HTML Audit

**Files:**
- Create: `scripts/build_scoring_audit.py`
- Create: `src/templates/scoring-audit.html`
- Create: `docs/scoring-system-audit.html`
- Create: `tests/test_scoring_audit.py`

**Interfaces:**
- Produces: `build_scoring_audit(content_root: Path) -> str`
- Reads `WEIGHTS`, selection thresholds, focus decay, and committed item JSON.

- [ ] **Step 1: Write failing report-content and statistics tests**

Calculate expected distributions independently in the test. Assert the generated report contains the five current weights, formulas, model/script ownership labels, thresholds, unique-score count, 80-point count and percentage, daily breakdown, example calculations, source file/function names, diagnosis, and “本报告未修改评分机制”.

- [ ] **Step 2: Run test and confirm failure**

Run: `python3 -m unittest tests.test_scoring_audit`

- [ ] **Step 3: Implement deterministic audit calculations**

Use only standard-library JSON/statistics/HTML escaping. Import scoring constants rather than copying numeric values where possible. Explicitly diagnose whether identical final scores arise from identical model dimension vectors, formula rounding, or absent adjustments by comparing real stored records.

- [ ] **Step 4: Implement self-contained responsive HTML**

Include an overview, flow diagram, formula table, score histogram, per-date table, dimension distributions, trace examples, diagnosis, and future decision checklist. Inline CSS and JavaScript; no external assets or CDN.

- [ ] **Step 5: Generate and test report**

Run: `python3 -m scripts.build_scoring_audit content docs/scoring-system-audit.html && python3 -m unittest tests.test_scoring_audit`

Expected: report is regenerated deterministically and tests pass.

- [ ] **Step 6: Commit**

```bash
git add scripts/build_scoring_audit.py src/templates/scoring-audit.html docs/scoring-system-audit.html tests/test_scoring_audit.py
git commit -m "docs: audit current scoring system"
```

### Task 7: Full Verification and Browser Acceptance

**Files:**
- Modify only if verification finds a defect.

**Interfaces:**
- Verifies the complete feature and report without expanding scope.

- [ ] **Step 1: Run complete automated verification**

Run:

```bash
python3 -m unittest discover -s tests
python3 -m scripts.radar_render content site
git diff --check
```

Expected: zero failures, successful site build, no whitespace errors.

- [ ] **Step 2: Verify score preservation**

Compare committed pre-backfill and current item IDs to assert every existing `final_score`, `base_score`, `daily_rank`, and semantic score is unchanged.

- [ ] **Step 3: Browser-check the homepage at 592×860**

Reload `http://127.0.0.1:8765/`; verify full canonical labels, compact centered TOP4 rows, no blank entity row for item four, scores beside bookmarks, and scroll loading.

- [ ] **Step 4: Browser-check the audit report**

Open the generated HTML through the local server and verify desktop/mobile readability and that displayed statistics match the test output.

- [ ] **Step 5: Commit verification fixes if needed**

If verification required changes, stage each named modified source/test file explicitly, inspect `git diff --cached`, and commit with `git commit -m "fix: address entity audit acceptance findings"`. If no fixes were required, do not create an empty commit.
