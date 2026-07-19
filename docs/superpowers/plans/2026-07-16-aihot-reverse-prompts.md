# AIHOT Reverse Prompts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refresh the AIHOT benchmark library with current desktop/mobile evidence and a screenshot-backed Chinese guide of efficient reverse-engineered prompts.

**Architecture:** Treat public UI states and downloaded assets as evidence, keep deterministic frontend interactions separate from inferred model-assisted content processing, and connect every prompt template to observable output. Store source snapshots, screenshots, change analysis, and the final guide under the existing `references/aihot/` library.

**Tech Stack:** Codex in-app Browser, HTML/CSS/Next.js public assets, Markdown, JSON, SHA-256 verification.

## Global Constraints

- Do not claim access to AIHOT's private prompts or backend source.
- Use only evidence captured in the current run for new audit claims.
- Capture desktop at `1440 × 1000` and mobile at `393 × 852`.
- Follow GPT-5.6 prompting best practices from the official OpenAI guide.
- Preserve unrelated worktree changes, including `.wrangler/` and `tmp/`.

---

### Task 1: Capture current public evidence

**Files:**
- Create: `references/aihot/screenshots/*.png`
- Replace: `references/aihot/raw/index.html`
- Replace/Create: `references/aihot/raw/css/*.css`
- Create: `references/aihot/raw/js/*.js`

**Interfaces:**
- Consumes: `https://aihot.virxact.com/` public pages and observed page assets.
- Produces: accepted screenshots and timestamped public-source snapshots for Tasks 2–4.

- [ ] Capture stable desktop and mobile homepage screenshots.
- [ ] Capture search, item detail, daily report, topics, starred, theme, and changelog states needed by the guide.
- [ ] Inspect each saved screenshot at original resolution and reject blank/loading/wrong-state captures.
- [ ] Download the current homepage HTML and referenced CSS/interaction JavaScript assets.

### Task 2: Record verified changes

**Files:**
- Create: `references/aihot/analysis/latest-changes.md`
- Modify: `references/aihot/analysis/design-system.md`
- Modify: `references/aihot/analysis/component-patterns.md`
- Modify: `references/aihot/analysis/hn-hot-checklist.md`

**Interfaces:**
- Consumes: Task 1 evidence plus the 2026-07-11 committed snapshot.
- Produces: a dated, evidence-based change record and corrected reusable patterns.

- [ ] Compare navigation, visual system, mobile layout, timeline cards, reports, item detail, and selection behavior.
- [ ] Separate changelog-confirmed changes from visual inferences.
- [ ] Update old analysis statements that conflict with AIHOT 2.0.

### Task 3: Write screenshot-backed reverse prompts

**Files:**
- Create: `references/aihot/analysis/reverse-engineered-prompts.md`

**Interfaces:**
- Consumes: Task 1 screenshots, Task 2 change log, and the official GPT-5.6 prompting guidance.
- Produces: one standalone Chinese guide with relative image links and copyable prompt blocks.

- [ ] Explain the inference method, confidence labels, and official prompting principles.
- [ ] Document deterministic frontend blocks: responsive navigation, search/filter, local favorites/read state/theme, detail/export, and report period switching.
- [ ] Document inferred model-assisted blocks: extraction/translation, event deduplication, source priority, classification/tags, scoring/selection, hot ranking, summary/recommendation, and report composition.
- [ ] Give every prompt a goal, inputs, lean rules, output schema, boundary/failure behavior, and evidence note.

### Task 4: Refresh library metadata

**Files:**
- Modify: `references/aihot/README.md`
- Modify: `references/aihot/manifest.json`

**Interfaces:**
- Consumes: all final files from Tasks 1–3.
- Produces: the canonical reading order and machine-verifiable inventory.

- [ ] Update capture dates, directory tree, reading order, and AIHOT 2.0 quick conclusions.
- [ ] Generate exact byte sizes and SHA-256 hashes for all tracked reference artifacts.

### Task 5: Verify the deliverable

**Files:**
- Verify: `references/aihot/**`

**Interfaces:**
- Consumes: final reference library.
- Produces: fresh verification output supporting the handoff.

- [ ] Parse `manifest.json` as JSON.
- [ ] Verify every manifest size and hash against the corresponding file.
- [ ] Verify every Markdown image link resolves to an existing screenshot.
- [ ] Inspect final desktop/mobile screenshots at original resolution.
- [ ] Review `git diff --check`, `git status --short`, and the scoped diff under `references/aihot/`.
