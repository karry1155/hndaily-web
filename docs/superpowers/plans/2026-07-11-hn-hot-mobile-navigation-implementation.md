# HN·HOT Mobile Navigation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the narrow HN·HOT layout follow AIHOT's top metadata, focus-first content order, hidden search, and fixed bottom navigation.

**Architecture:** Keep one semantic navigation tree and restyle it into a bottom bar at `<= 760px`. Add mobile metadata to the shared navigation renderer and use CSS ordering for the homepage so desktop DOM behavior remains stable.

**Tech Stack:** Python static renderer, HTML templates, CSS media queries, unittest.

## Global Constraints

- Do not change selected-content data, ranking, local favorites, or search behavior.
- Narrow screens are `<= 760px`; search remains visible above that breakpoint.
- Bottom navigation contains 精选、全部信息、AI 日报、收藏.

---

### Task 1: Render mobile metadata and date labels

**Files:**
- Modify: `scripts/radar_render.py`
- Test: `tests/test_radar_render.py`

**Interfaces:**
- Consumes: `render_index(index, focus, active_category)` and `render_primary_nav(active, mobile_meta="")`.
- Produces: escaped mobile update metadata and `YYYY-MM-DD 精选` headings.

- [ ] **Step 1: Add failing render assertions** for `mobile-updated` and `2026-07-10 精选`.
- [ ] **Step 2: Run** `python3 -m unittest tests.test_radar_render -v` and confirm failure.
- [ ] **Step 3: Add optional metadata to `render_primary_nav` and append 精选 to date headings.**
- [ ] **Step 4: Re-run the focused tests and confirm they pass.**

### Task 2: Implement narrow-screen hierarchy

**Files:**
- Modify: `src/static/styles.css`
- Test: `tests/test_radar_render.py`

**Interfaces:**
- Consumes: `.primary-nav`, `.nav-body`, `.mobile-updated`, `.focus-section`, `.content-tools`, `.search-box`.
- Produces: fixed bottom navigation and focus-first mobile layout at `<= 760px`.

- [ ] **Step 1: Add failing CSS contract assertions** for fixed bottom navigation, hidden search, and ordered sections.
- [ ] **Step 2: Run the focused test and confirm failure.**
- [ ] **Step 3: Add final cascade rules at the end of `styles.css`.**
- [ ] **Step 4: Rebuild with `python3 -m scripts.radar_render`.**
- [ ] **Step 5: Run `RADAR_REAL_DATA_REQUIRED=1 python3 -m unittest discover -s tests -v` and confirm all tests pass.**
