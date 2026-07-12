# HN·HOT Mobile Density Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the HN·HOT mobile homepage substantially denser and more open while preserving the existing desktop interface unchanged.

**Architecture:** Keep the existing semantic HTML and data flow, and append a final mobile-only cascade to `styles.css` under `@media (max-width: 760px)`. Use a focused CSS contract test to lock the breakpoint, open-list treatment, compact focus rows, horizontally scrolling categories, safe-area-aware bottom navigation, and desktop isolation.

**Tech Stack:** Python 3.9 `unittest`, static HTML templates, CSS media queries.

## Global Constraints

- Only the homepage at `<= 760px` changes.
- The desktop layout at `> 760px` remains unchanged.
- Keep the current HN·HOT colors, content, data, ordering, routes, search, and local favorites behavior.
- Do not duplicate mobile markup and do not move nodes with JavaScript.
- The fixed bottom navigation must include iPhone safe-area spacing and must not cover feed content.
- Focus titles are limited to two lines; feed summaries are limited to three lines.
- Mobile categories are independent pills in a horizontally scrollable row, not one enclosing capsule.

---

### Task 1: Lock the Mobile Density Contract

**Files:**
- Modify: `tests/test_radar_render.py`
- Test: `tests/test_radar_render.py`

**Interfaces:**
- Consumes: `src/static/styles.css` as UTF-8 text.
- Produces: a regression test anchored at `/* HN·HOT mobile density refresh. */` so only the final mobile cascade satisfies the new contract.

- [ ] **Step 1: Add the failing CSS contract test**

Add this method to `RadarRenderTests`:

```python
def test_mobile_density_refresh_is_open_compact_and_safe_area_aware(self):
    css = (Path(__file__).resolve().parents[1] / "src/static/styles.css").read_text(encoding="utf-8")
    marker = css.index("/* HN·HOT mobile density refresh. */")
    mobile = css[marker:]
    self.assertIn("@media (max-width: 760px)", mobile)
    self.assertIn("padding-bottom: calc(64px + env(safe-area-inset-bottom))", mobile)
    self.assertIn("overflow-x: auto", mobile)
    self.assertIn("scrollbar-width: none", mobile)
    self.assertIn("border: 0", mobile)
    self.assertIn("box-shadow: none", mobile)
    self.assertIn("-webkit-line-clamp: 2", mobile)
    self.assertIn("-webkit-line-clamp: 3", mobile)
    self.assertIn("grid-template-columns: 26px minmax(0,1fr) 32px", mobile)
    self.assertNotIn("@media (min-width: 761px)", mobile)
```

- [ ] **Step 2: Run the focused test and verify the marker is missing**

Run: `python3 -m unittest tests.test_radar_render.RadarRenderTests.test_mobile_density_refresh_is_open_compact_and_safe_area_aware -v`

Expected: `ERROR` with `ValueError: substring not found` for the new cascade marker.

- [ ] **Step 3: Commit the red test**

```bash
git add tests/test_radar_render.py
git commit -m "test: define mobile density contract"
```

---

### Task 2: Implement the Mobile-Only Layout Cascade

**Files:**
- Modify: `src/static/styles.css`
- Test: `tests/test_radar_render.py`

**Interfaces:**
- Consumes: existing `.radar-content`, `.content-tools`, `.category-tabs`, `.focus-section`, `.date-group`, `.selected-row`, `.star-button`, and mobile navigation selectors.
- Produces: the final `/* HN·HOT mobile density refresh. */` cascade, scoped exclusively to `@media (max-width: 760px)`.

- [ ] **Step 1: Append the minimal mobile-only cascade**

Append the following rules after the existing final cascade:

```css
/* HN·HOT mobile density refresh. */
@media (max-width: 760px) {
  body { padding-bottom: calc(64px + env(safe-area-inset-bottom)); }
  .radar-shell .primary-nav { min-height: 52px; padding: 9px 18px; }
  .radar-content { padding: 12px 0 calc(20px + env(safe-area-inset-bottom)); }

  .focus-section {
    margin: 0 16px 18px;
    padding: 12px 16px 6px;
    border-radius: 10px;
    box-shadow: none;
  }
  .focus-section .section-heading { padding: 0 0 4px; border-bottom: 0; }
  .focus-section .section-heading h2 { font-size: 17px; font-weight: 650; }
  .focus-section .selected-row {
    grid-template-columns: 26px minmax(0,1fr) 32px;
    gap: 8px;
    padding: 8px 0;
  }
  .focus-section .selected-row strong {
    display: -webkit-box;
    overflow: hidden;
    font-size: 13.5px;
    line-height: 1.42;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
  }
  .focus-section .title-rank {
    display: grid;
    width: 24px;
    height: 24px;
    border-radius: 6px;
    place-items: center;
    color: #fff;
    font-size: 12px;
  }
  .focus-section .focus-rank-1 { background: #d85762; }
  .focus-section .focus-rank-2 { background: #d59a32; }
  .focus-section .focus-rank-3 { background: #28a9c3; }
  .focus-section .focus-rank-4 { background: #71839b; }
  .focus-section .star-button { width: 32px; height: 32px; padding: 7px; justify-self: end; }

  .content-tools {
    margin: 0 0 12px;
    padding: 0 16px;
    border: 0;
    border-radius: 0;
    background: transparent;
    box-shadow: none;
  }
  .content-tools .radar-header { margin: 0 0 8px; padding: 0; border: 0; }
  .content-tools .radar-header h1 { font-size: 17px; font-weight: 650; }
  .tool-filter-row { display: block; }
  .category-tabs {
    display: flex;
    gap: 7px;
    margin: 0 -16px;
    padding: 0 16px 2px;
    overflow-x: auto;
    border: 0;
    border-radius: 0;
    background: transparent;
    box-shadow: none;
    scrollbar-width: none;
    -webkit-overflow-scrolling: touch;
  }
  .category-tabs::-webkit-scrollbar { display: none; }
  .category-tabs a { min-height: 30px; padding: 5px 12px; border: 1px solid var(--line); font-size: 12px; }
  .category-tabs a.active { border-color: transparent; color: #fff; background: var(--accent); box-shadow: none; }

  .radar-feed { border-top: 1px solid var(--line-soft); }
  .date-group {
    margin: 0;
    padding: 12px 16px 0;
    border: 0;
    border-radius: 0;
    background: transparent;
    box-shadow: none;
  }
  .date-group h2 { margin: 0 0 4px; font-size: 14px; }
  .date-group .selected-row { grid-template-columns: minmax(0,1fr) 32px; gap: 8px; padding: 10px 0; }
  .date-group .selected-row strong { font-size: 13.5px; line-height: 1.42; }
  .date-group .selected-row p {
    margin-top: 3px;
    font-size: 12px;
    line-height: 1.45;
    -webkit-line-clamp: 3;
  }
  .date-group .star-button { width: 32px; height: 32px; padding: 7px; justify-self: end; }

  html[data-theme="light"] .content-tools,
  html[data-theme="light"] .date-group {
    border: 0;
    background: transparent;
    box-shadow: none;
  }
  html[data-theme="light"] .category-tabs { border: 0; background: transparent; box-shadow: none; }
  html[data-theme="light"] .category-tabs a.active { border-color: transparent; color: #fff; background: var(--accent); box-shadow: none; }

  .radar-shell .nav-body,
  .radar-shell .primary-nav.nav-open .nav-body { padding: 5px 10px max(5px,env(safe-area-inset-bottom)); }
  .radar-shell .nav-body nav:first-of-type a { gap: 1px; padding: 2px; font-size: 10px; }
  .radar-shell .nav-body .nav-icon { width: 19px; height: 19px; }
}
```

- [ ] **Step 2: Run the focused contract test**

Run: `python3 -m unittest tests.test_radar_render.RadarRenderTests.test_mobile_density_refresh_is_open_compact_and_safe_area_aware -v`

Expected: `OK` with one passing test.

- [ ] **Step 3: Run all render tests**

Run: `python3 -m unittest tests.test_radar_render -v`

Expected: all tests pass.

- [ ] **Step 4: Commit the mobile cascade**

```bash
git add src/static/styles.css
git commit -m "feat: densify mobile news layout"
```

---

### Task 3: Verify the Built Site and Responsive Isolation

**Files:**
- Verify: `src/static/styles.css`
- Verify: generated site output under a temporary directory created by tests.

**Interfaces:**
- Consumes: the full Python test suite and static site renderer.
- Produces: evidence that all routes build and the CSS change is limited to the mobile breakpoint.

- [ ] **Step 1: Run the complete test suite**

Run: `python3 -m unittest discover -s tests -v`

Expected: exit code `0` with no failures or errors.

- [ ] **Step 2: Check CSS syntax hygiene and scope**

Run: `git diff HEAD~2 --check`

Expected: no output and exit code `0`.

Run: `python3 -c 'from pathlib import Path; s=Path("src/static/styles.css").read_text(); m=s[s.index("/* HN·HOT mobile density refresh. */"):]; assert "@media (max-width: 760px)" in m and "@media (min-width: 761px)" not in m'`

Expected: no output and exit code `0`.

- [ ] **Step 3: Review the final diff against the acceptance checklist**

Run: `git show --stat --oneline HEAD && git status --short`

Expected: only the intended CSS/test/spec/plan changes are committed; pre-existing `.wrangler/` and `tmp/` remain untracked and untouched.

