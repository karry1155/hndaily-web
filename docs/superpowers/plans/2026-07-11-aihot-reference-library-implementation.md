# AIHOT Reference Library Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve a project-local, traceable AIHOT reference snapshot and analysis so future agents can reliably compare HN·HOT against the benchmark.

**Architecture:** Store raw public-page snapshots separately from authored analysis. Provide one README as the routing entrypoint, a machine-readable manifest for provenance, screenshots at mobile and desktop viewports, and focused notes for tokens, components, responsive behavior, and HN·HOT comparison.

**Tech Stack:** HTML, CSS, Markdown, JSON, browser screenshots.

## Global Constraints

- Reference files live under `references/aihot/` and are never imported by production templates.
- Raw files preserve their source URL and capture date in `manifest.json`.
- Analysis paraphrases patterns instead of presenting copied source as original project code.
- The library must be understandable without reopening the external website.

### Task 1: Capture the benchmark

- [ ] Create `references/aihot/raw/` and save the homepage HTML plus its three loaded CSS files.
- [ ] Capture mobile and desktop screenshots from the live page.
- [ ] Record URLs, sizes, timestamps, and viewport dimensions in `manifest.json`.

### Task 2: Write reusable analysis

- [ ] Create an entrypoint README with reading order and usage boundaries.
- [ ] Document design tokens, responsive breakpoints, density rules, hot-topic structure, feed structure, and bottom navigation.
- [ ] Add an HN·HOT comparison checklist for future implementation and visual reviews.

### Task 3: Verify the library

- [ ] Confirm every manifest path exists and raw CSS sizes match captured metadata.
- [ ] Check Markdown and JSON for placeholders and syntax errors.
- [ ] Commit only the reference library and implementation plan.

