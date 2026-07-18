# Local JSON workspace

HNHOT keeps every private pipeline artifact inside this directory. The current
Radar contract uses the canonical dated paths:

- `raw/YYYY-MM-DD.json`: unmodified crawler output.
- `model-input/YYYY-MM-DD.json`: exact model input and fingerprint.
- `model-output/YYYY-MM-DD.json`: exact model response.
- `audits/YYYY-MM-DD.prefilter.json`: deterministic crawl/filter audit.
- `audits/YYYY-MM-DD.publication.json`: validated publication audit.

The legacy editorial pipeline shares only the raw crawl. Its model and audit
contracts are incompatible with Radar, so those artifacts are isolated under
the `editorial-v1/` namespace:

- `model-input/editorial-v1/YYYY-MM-DD.json`: editorial model input.
- `model-output/editorial-v1/YYYY-MM-DD.json`: editorial model response.
- `audits/editorial-v1/YYYY-MM-DD.prefilter.json`: editorial prefilter audit.
- `audits/editorial-v1/YYYY-MM-DD.editorial-audit.json`: editorial selection audit.

The generated subdirectories are intentionally ignored by Git. Public,
validated static content belongs under `content/`; prompts, schemas and
controlled catalogs belong under `prompts/` and `config/`.
