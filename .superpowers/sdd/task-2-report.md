# Task 2 Report: Digest Validator

## What I changed
- Added `scripts/validate_digest.py` to validate daily and weekly digest JSON against the contract in `docs/data-contract.md`.
- Added `scripts/fixtures/daily-valid.json`.
- Added `scripts/fixtures/weekly-valid.json`.

## Behavior
- `python3 scripts/validate_digest.py <path>` now exits with `0` for valid daily or weekly digests.
- Invalid input returns `1` and prints validation errors to stderr.

## Verification
- `python3 scripts/validate_digest.py scripts/fixtures/daily-valid.json`
- `python3 scripts/validate_digest.py scripts/fixtures/weekly-valid.json`

Both commands returned the expected `OK:` line and exited successfully.

## Commit
- `4c6d521` - `feat: add digest validator`

## Fix

### What I changed
- Tightened top-item source validation so daily and weekly top items must include at least one source object.
- Added validation for daily category entries: `title`, `summary`, and `sources` are required for every category item, and `已跳过` entries now require `skip_reason`.
- Validated `generated_at` as an ISO datetime string for both daily and weekly digests.
- Hardened integer checks so Python `bool` values do not satisfy `page_count`, `article_count`, or `rank`.

### Verification
- `python3 scripts/validate_digest.py scripts/fixtures/daily-valid.json`
  - `OK: scripts/fixtures/daily-valid.json`
- `python3 scripts/validate_digest.py scripts/fixtures/weekly-valid.json`
  - `OK: scripts/fixtures/weekly-valid.json`
- Temporary negative checks under `/private/tmp`:
  - empty daily top-item sources: `ERROR: sources must contain at least 1 item(s)`
  - bool `page_count` / `article_count`: `ERROR: page_count must be >= 0` and `ERROR: article_count must be >= 0`
  - bad daily `generated_at`: `ERROR: generated_at must be an ISO datetime string`
  - missing daily category `summary`: `ERROR: categories[民生/办事][0].summary is required`
  - missing `skip_reason` for `已跳过`: `ERROR: categories[已跳过][0].skip_reason is required`
  - empty weekly top-item sources: `ERROR: sources must contain at least 1 item(s)`
