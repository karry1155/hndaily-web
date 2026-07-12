# HN·HOT Radar Pipeline HTML Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a self-contained, evidence-backed HTML report showing how crawler output becomes the HN·HOT selected-news page, including exact script/model boundaries and JSON evolution.

**Architecture:** Extract facts from the crawler, Radar scripts, contracts, tests, and committed content examples. Build one interactive HTML visualization with a stage selector and synchronized stage detail, then render it as a standalone project document and validate it in desktop and mobile browser viewports.

**Tech Stack:** Python 3.9 scripts and contracts, JSON, semantic HTML, inline CSS, vanilla JavaScript, browser verification.

## Global Constraints

- Main scope is the Radar pipeline that powers selected news and focus ranking.
- Daily Digest appears only as an appendix.
- Existing and proposed fields must be visually distinguished.
- Every file path, function, and JSON field must be traceable to the repository.
- Output is `docs/hndaily-radar-pipeline-report.html` and is not imported by production code.

---

### Task 1: Build the Evidence Map

**Files:**
- Read: `../hndaily-skill/crawler.py`
- Read: `scripts/editorial_filter.py`
- Read: `scripts/radar_adapter.py`
- Read: `scripts/prepare_radar.py`
- Read: `scripts/radar_model.py`
- Read: `scripts/radar_scoring.py`
- Read: `scripts/finalize_radar.py`
- Read: `scripts/radar_store.py`
- Read: `scripts/radar_indexes.py`
- Read: `scripts/radar_render.py`
- Read: `scripts/radar_transaction.py`
- Read: `scripts/run_radar_pipeline.sh`
- Read: `scripts/run_daily_pipeline.sh`
- Read: `scripts/radar_contract.py`
- Read: `content/indexes/*.json`, `content/items/**/*.json`, `content/issues/*.json`

- [ ] Record the real execution order and critical function names.
- [ ] Extract compact real JSON examples for raw issue, candidate, model input, model output, stored item, public issue, focus index, category/date index, and rendered summary.
- [ ] Mark each field as crawler-owned, script-owned, model-owned, private audit, or publicly published.
- [ ] Identify the exact insertion points for proposed `recommendation_reason` and infinite loading.

### Task 2: Create and Render the Report

**Files:**
- Create visualization source: `/Users/skr/.codex/visualizations/2026/07/12/019f5456-3a78-7c62-b5e5-1e5f7df5b4ee/radar-pipeline-report.html`
- Create standalone report: `docs/hndaily-radar-pipeline-report.html`

- [ ] Build a responsive stage-flow visualization using semantic buttons and one synchronized detail panel.
- [ ] Include a readable static fallback summary and all required JSON structures.
- [ ] Include explicit “current” versus “proposed” labels for recommendation reasons and scrolling.
- [ ] Render the fragment as a standalone HTML document with the bundled visualization renderer.

### Task 3: Verify Content and Browser Behavior

**Files:**
- Verify: `docs/hndaily-radar-pipeline-report.html`

- [ ] Check for missing referenced project paths, placeholders, undefined JavaScript identifiers, and malformed JSON examples.
- [ ] Open the standalone report in a browser at desktop width and verify stage interaction changes the detail panel.
- [ ] Open at mobile width and verify there is no horizontal overflow, overlap, or clipped content.
- [ ] Save desktop and mobile screenshots under `tmp/` and commit the report, specification, and plan only.

