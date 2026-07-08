# Data Contract

## Daily Digest

Daily digest files live at `content/daily/YYYY-MM-DD.json`.

Required top-level fields:

- `type`: must be `"daily"`.
- `date`: ISO date, for example `"2026-07-08"`.
- `source`: source name, for example `"海南日报"`.
- `page_count`: integer greater than or equal to 0.
- `article_count`: integer greater than or equal to 0.
- `reading_minutes`: integer, expected value `5`.
- `top_items`: array with 0 to 5 items.
- `categories`: object keyed by fixed category name.
- `generated_at`: ISO datetime string.

Required `top_items` fields:

- `rank`: integer starting at 1.
- `title`: readable rewritten title.
- `category`: one fixed category name.
- `why_it_matters`: one sentence explaining why this is worth attention today.
- `key_facts`: array of source-grounded facts.
- `sources`: array with at least one source object.
- `confidence`: one of `full_text`, `short_item`, `headline_only`, `partial`.

Required source object fields:

- `headline`: original article title.
- `page`: original page number string, for example `"001"`.
- `url`: original article URL.

Fixed categories:

- `民生/办事`
- `政策/监管`
- `产业/项目`
- `经济/数据`
- `城市/出行/风险`
- `人事/反腐`
- `重要但不必精读`
- `已跳过`

Category items require:

- `title`
- `summary`
- `sources`
- `skip_reason` only when the category is `已跳过`

## Weekly Digest

Weekly digest files live at `content/weekly/YYYY-Www.json`, for example `content/weekly/2026-W28.json`.

Required top-level fields:

- `type`: must be `"weekly"`.
- `week`: ISO week string.
- `date_range`: object with `start` and `end` ISO dates.
- `reading_minutes`: integer, expected value `15`.
- `top_items`: array with 0 to 15 items.
- `themes`: array of trend theme objects.
- `watch_next`: array of short follow-up items.
- `generated_at`: ISO datetime string.

Weekly source objects must include `date`, `headline`, `page`, and `url`.
