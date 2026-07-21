# Production JSON review workspace

This is the active private workspace for the current HNHOT pipeline. Files are
grouped by processing stage so a dated issue can be reviewed from source to
publication without mixing it with historical v1 artifacts.

- `source/YYYY-MM-DD.json`: full crawler result and article text.
- `input/YYYY-MM-DD.json`: exact v3 semantic input, candidates and fingerprint.
- `enrichment/YYYY-MM-DD.json`: complete agent-produced semantic result to review.
- `topic-resolution-input/YYYY-MM-DD.json`: open topics awaiting catalog resolution.
- `topic-resolution/YYYY-MM-DD.json`: reviewed mappings and new leaf decisions.
- `audit/YYYY-MM-DD.prefilter.json`: deterministic inclusion and exclusion record.
- `audit/YYYY-MM-DD.publication.json`: validated publication counts, hashes and replacements.

Run `bash scripts/run_radar_pipeline.sh YYYY-MM-DD`. The command prints the
exact input and enrichment paths for that issue. Do not place edited review
notes inside the JSON response; use `evaluation/gold/` for human benchmark
decisions.
