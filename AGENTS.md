# HNHOT agent workflow

This repository is designed for an interactive coding agent to perform the semantic step directly. Do not add or require an external model API for the daily workflow.

## Importing an issue

1. Run `bash scripts/run_radar_pipeline.sh YYYY-MM-DD`.
2. When it prints `STATUS=MODEL_OUTPUT_REQUIRED`, read the printed `MODEL_INPUT_JSON`, then read every file in the printed `PROMPT_DIR` completely.
3. Produce the complete JSON response yourself for every input item. Do not replace semantic work with keyword templates, fixed empty arrays, copied summaries, or a blanket fallback such as making every event empty.
4. Write only the strict JSON response to `MODEL_OUTPUT_JSON`, preserving the input envelope and item order.
5. Run the same pipeline command again. Resolve validation failures against the source evidence; do not weaken the validator to accept incorrect output.
6. Run `python3 -m unittest discover -s tests -v` and rebuild the preview before reporting completion.

The active first-pass contract is `prompts/article-enrichment/v2/`. Version 1 remains read-only historical documentation. First-pass enrichment describes only the current article; it must not decide whether an entity deserves a future page or merge it into a long-term timeline.

The active private workspace is `data/production-json/`: crawler source, semantic input, enrichment output and audits live in separate subdirectories there. `data/json/` is a read-only archive of the earlier pipeline; never overwrite or migrate its dated files in place. Public validated content is stored under `content/`. Never describe an ad-hoc or heuristic-filled output as a model result. If a temporary fallback is unavoidable, stop publication and report the limitation instead.

Preserve unrelated worktree changes. Human benchmark files under `evaluation/gold/` are review evidence, not model output and not a source to copy blindly; only entries marked `reviewed` are authoritative regression expectations.
