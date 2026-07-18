# Local JSON workspace

HNHOT keeps every private pipeline artifact inside this directory:

- `raw/YYYY-MM-DD.json`: unmodified crawler output.
- `model-input/YYYY-MM-DD.json`: exact model input and fingerprint.
- `model-output/YYYY-MM-DD.json`: exact model response.
- `audits/YYYY-MM-DD.prefilter.json`: deterministic crawl/filter audit.
- `audits/YYYY-MM-DD.publication.json`: validated publication audit.

The generated subdirectories are intentionally ignored by Git. Public,
validated static content belongs under `content/`; prompts, schemas and
controlled catalogs belong under `prompts/` and `config/`.
