# Historical JSON archive

This directory preserves private artifacts produced by the earlier pipeline,
including v1 results and the files that were already present before the active
workspace moved. Existing dated files are retained as-is and must not be
overwritten by the daily workflow.

The active reviewable JSON is now under `data/production-json/`:

- `source/YYYY-MM-DD.json`
- `input/YYYY-MM-DD.json`
- `enrichment/YYYY-MM-DD.json`
- `audit/YYYY-MM-DD.prefilter.json`
- `audit/YYYY-MM-DD.publication.json`

Public validated content remains under `content/`; prompts, schemas and
controlled catalogs remain under `prompts/` and `config/`.
