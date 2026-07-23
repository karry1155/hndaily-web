# HNHOT current application

The repository root is the only active HNHOT application. It uses article
schema 13 and `prompt_version: hnhot-v4.3`. Do not create another full runtime
directory for a prompt, schema or UI revision.

Historical full-application snapshots live outside the repository at the sibling
path `../hndaily-web-radar-snapshots/`. They are recovery material only: never
read their runtime data, prompts, generated content or tests unless the user
explicitly requests a historical comparison or recovery.

Before changing article semantics or importing an issue, read this file, every
file under `prompts/article-enrichment/v4.3/`, and
`docs/hnhot-article-enrichment-v4.3-design.md` completely.

## Importing an issue

1. Run `bash scripts/run_radar_pipeline.sh YYYY-MM-DD` from the repository root.
2. On `STATUS=MODEL_OUTPUT_REQUIRED`, read the printed model input and the full
   prompt package under `prompts/article-enrichment/v4.3/`.
3. Perform the semantic extraction directly. Do not add an external model API,
   keyword templates, copied summaries, fabricated evidence or blanket empty arrays.
4. Write only the strict JSON response to the printed enrichment path, preserving
   the envelope and article order, then rerun the same pipeline command.
5. Fix validation failures against the article's exact source text. Never weaken
   validation to admit an incorrect output.
6. Run the tests, rebuild the site, and inspect the article plus subject, event,
   region, topic, plan and reader-reminder pages before reporting completion.
7. `site/` is the versioned static deployment artifact. Keep it synchronized
   with `content/` and include both in the same reviewed Git change.

## Contract boundary

The first JSON is the only semantic response. The publisher may create stable
technical IDs and may count, sort, group and join objects, but may not perform a
second semantic generation.

- `subjects[].activities` contains subject actions and results.
- `location_mentions` uses only the finite Hainan administrative catalog.
- `topics.primary` chooses one finite category; `topics.secondary` is open text.
- `events` contains named events only, never ordinary subject actions.
- `plans` contains explicit planning documents in Chinese book-title marks.
- `reader_leads` contains source-backed reader actions, not generic news value.

Do not introduce `observations`, article-local refs, page titles, content-form
labels, a second topic-resolution prompt, or a knowledge sidecar.

## Versioning

- Use Git commits for checkpoints, short-lived branches for experiments and tags
  for accepted releases.
- A prompt/schema revision receives a versioned package below `prompts/`; it does
  not receive a copied frontend.
- Production runs live below `data/runs/`; the current contract is declared in
  `data/active-run.json`.
- Preserve unrelated worktree changes. Never present heuristic or placeholder
  semantic data as a model result.
