# Hndaily Web Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a static, mobile-friendly 海南日报精读 website that displays daily top signals, category archives, and weekly reports generated locally before cloud sync.

**Architecture:** Use a dependency-light static site. Python scripts read crawler JSON and curated digest JSON, validate the data contract, and render publishable HTML/CSS/JSON into `site/`. Source files and templates are committed; raw data, intermediate files, generated build output, PDFs, audio, and logs stay ignored.

**Tech Stack:** Python 3 standard library, vanilla HTML/CSS/JavaScript, static files deployable to any cloud host.

## Global Constraints

- The web project lives at `/Users/skr/Work/hndaily/hndaily-web` and is an independent git repository.
- This directory is the future cloud website source; the local scheduled job will generate new reports locally and sync publishable output to cloud.
- Do not commit construction intermediates: raw crawler data, temporary processing files, caches, PDFs, audio, logs, local environment files, or dependency folders.
- Daily page shows up to 5 high-value items, usually 5, with 5-minute estimated reading time.
- Do not force-fill to 5 items when fewer than 5 items are genuinely worth reading.
- Every top item must include a clickable source URL and a `why_it_matters` field.
- Daily page includes fixed category sections below the top items.
- Weekly page aggregates a week into a 15-minute report instead of concatenating seven daily pages.
- Layout must work on mobile and desktop without text overflow.
- Visual direction follows `https://aihot.virxact.com/daily`: dark interface, left primary navigation, secondary date/report navigation, centered editorial hero, compact bordered "今日看点" panel, and category content below. Use 海南日报精读 branding and do not copy AI HOT logos or brand text.

---

## File Structure

- `README.md`: project boundary and local workflow notes.
- `.gitignore`: excludes dependencies, generated build output, raw data, intermediate files, logs, PDFs, audio, and local env files.
- `docs/superpowers/plans/2026-07-08-hndaily-web-implementation.md`: this implementation plan.
- `docs/data-contract.md`: digest and weekly JSON schemas with examples.
- `content/daily/.gitkeep`: optional publishable daily digest JSON location. Generated files can be synced or committed intentionally later.
- `content/weekly/.gitkeep`: optional publishable weekly digest JSON location.
- `scripts/validate_digest.py`: validates daily and weekly digest JSON files.
- `scripts/render_site.py`: renders static HTML files from `content/`.
- `src/templates/base.html`: shared HTML shell.
- `src/templates/daily.html`: daily page template.
- `src/templates/weekly.html`: weekly page template.
- `src/static/styles.css`: responsive visual design.
- `src/static/app.js`: small client-side navigation helpers.
- `site/`: generated publishable static output; ignored.

---

### Task 1: Project Contract And Empty Content Directories

**Files:**
- Create: `docs/data-contract.md`
- Create: `content/daily/.gitkeep`
- Create: `content/weekly/.gitkeep`
- Modify: `.gitignore`

**Interfaces:**
- Produces: documented daily digest schema used by `scripts/validate_digest.py`.
- Produces: documented weekly digest schema used by `scripts/validate_digest.py`.
- Produces: stable `content/daily/` and `content/weekly/` directories.

- [ ] **Step 1: Write the data contract document**

Create `docs/data-contract.md` with this content:

```markdown
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
```

- [ ] **Step 2: Create tracked content directory placeholders**

Run:

```bash
mkdir -p content/daily content/weekly
touch content/daily/.gitkeep content/weekly/.gitkeep
```

- [ ] **Step 3: Keep publish output ignored but allow content placeholders**

Ensure `.gitignore` contains:

```gitignore
site/
data/raw/
data/intermediate/
data/cache/
data/tmp/
data/audio/
data/pdf/
*.tmp
*.log
*.mp3
*.pdf
```

- [ ] **Step 4: Verify git sees only contract files and placeholders**

Run: `git status --short`

Expected output includes:

```text
?? content/
?? docs/
```

- [ ] **Step 5: Commit**

Run:

```bash
git add .gitignore docs/data-contract.md content/daily/.gitkeep content/weekly/.gitkeep
git commit -m "docs: define digest data contract"
```

---

### Task 2: Digest Validator

**Files:**
- Create: `scripts/validate_digest.py`
- Create: `scripts/fixtures/daily-valid.json`
- Create: `scripts/fixtures/weekly-valid.json`

**Interfaces:**
- Consumes: JSON files matching `docs/data-contract.md`.
- Produces: CLI command `python3 scripts/validate_digest.py <path>`.
- Produces: exit code `0` when valid, `1` when invalid.

- [ ] **Step 1: Create valid daily fixture**

Create `scripts/fixtures/daily-valid.json`:

```json
{
  "type": "daily",
  "date": "2026-07-08",
  "source": "海南日报",
  "page_count": 8,
  "article_count": 35,
  "reading_minutes": 5,
  "top_items": [
    {
      "rank": 1,
      "title": "海南住房公积金可用于交物业费",
      "category": "民生/办事",
      "why_it_matters": "这会直接影响有公积金账户的居民日常支出安排。",
      "key_facts": ["影响事项：物业费支付", "原文来源：第001版"],
      "sources": [
        {
          "headline": "海南能用住房公积金交物业费了",
          "page": "001",
          "url": "http://news.hndaily.cn/html/2026-07/08/content_58469_20380144.htm"
        }
      ],
      "confidence": "full_text"
    }
  ],
  "categories": {
    "民生/办事": [],
    "政策/监管": [],
    "产业/项目": [],
    "经济/数据": [],
    "城市/出行/风险": [],
    "人事/反腐": [],
    "重要但不必精读": [],
    "已跳过": [
      {
        "title": "公益广告",
        "summary": "广告版不进入精读。",
        "sources": [],
        "skip_reason": "公益广告"
      }
    ]
  },
  "generated_at": "2026-07-08T09:00:00+08:00"
}
```

- [ ] **Step 2: Create valid weekly fixture**

Create `scripts/fixtures/weekly-valid.json`:

```json
{
  "type": "weekly",
  "week": "2026-W28",
  "date_range": {
    "start": "2026-07-06",
    "end": "2026-07-12"
  },
  "reading_minutes": 15,
  "top_items": [
    {
      "rank": 1,
      "title": "本周民生办事政策集中更新",
      "why_it_matters": "多条信息会影响个人办事和生活支出。",
      "key_facts": ["覆盖住房、公积金、出行等主题"],
      "sources": [
        {
          "date": "2026-07-08",
          "headline": "海南能用住房公积金交物业费了",
          "page": "001",
          "url": "http://news.hndaily.cn/html/2026-07/08/content_58469_20380144.htm"
        }
      ]
    }
  ],
  "themes": [
    {
      "title": "民生办事",
      "summary": "本周值得优先回看的信息集中在个人办事变化。",
      "sources": []
    }
  ],
  "watch_next": ["继续关注公积金政策后续执行细则"],
  "generated_at": "2026-07-12T18:00:00+08:00"
}
```

- [ ] **Step 3: Write validator**

Create `scripts/validate_digest.py`:

```python
#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

CATEGORIES = [
    "民生/办事",
    "政策/监管",
    "产业/项目",
    "经济/数据",
    "城市/出行/风险",
    "人事/反腐",
    "重要但不必精读",
    "已跳过",
]

CONFIDENCE = {"full_text", "short_item", "headline_only", "partial"}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
WEEK_RE = re.compile(r"^\d{4}-W\d{2}$")


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_sources(sources: Any, errors: list[str], weekly: bool) -> None:
    require(isinstance(sources, list), "sources must be an array", errors)
    if not isinstance(sources, list):
        return
    for index, source in enumerate(sources):
        require(isinstance(source, dict), f"sources[{index}] must be an object", errors)
        if not isinstance(source, dict):
            continue
        if weekly:
            require(DATE_RE.match(str(source.get("date", ""))) is not None, f"sources[{index}].date must be ISO date", errors)
        require(is_non_empty_string(source.get("headline")), f"sources[{index}].headline is required", errors)
        require(is_non_empty_string(source.get("page")), f"sources[{index}].page is required", errors)
        require(is_non_empty_string(source.get("url")), f"sources[{index}].url is required", errors)


def validate_daily(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    require(data.get("type") == "daily", "type must be daily", errors)
    require(DATE_RE.match(str(data.get("date", ""))) is not None, "date must be ISO date", errors)
    require(is_non_empty_string(data.get("source")), "source is required", errors)
    require(isinstance(data.get("page_count"), int) and data["page_count"] >= 0, "page_count must be >= 0", errors)
    require(isinstance(data.get("article_count"), int) and data["article_count"] >= 0, "article_count must be >= 0", errors)
    require(data.get("reading_minutes") == 5, "daily reading_minutes must be 5", errors)

    top_items = data.get("top_items")
    require(isinstance(top_items, list), "top_items must be an array", errors)
    if isinstance(top_items, list):
        require(len(top_items) <= 5, "daily top_items must contain at most 5 items", errors)
        for index, item in enumerate(top_items):
            require(isinstance(item, dict), f"top_items[{index}] must be an object", errors)
            if not isinstance(item, dict):
                continue
            require(item.get("rank") == index + 1, f"top_items[{index}].rank must be {index + 1}", errors)
            require(is_non_empty_string(item.get("title")), f"top_items[{index}].title is required", errors)
            require(item.get("category") in CATEGORIES, f"top_items[{index}].category is invalid", errors)
            require(is_non_empty_string(item.get("why_it_matters")), f"top_items[{index}].why_it_matters is required", errors)
            require(isinstance(item.get("key_facts"), list), f"top_items[{index}].key_facts must be an array", errors)
            validate_sources(item.get("sources"), errors, weekly=False)
            require(item.get("confidence") in CONFIDENCE, f"top_items[{index}].confidence is invalid", errors)

    categories = data.get("categories")
    require(isinstance(categories, dict), "categories must be an object", errors)
    if isinstance(categories, dict):
        for category in CATEGORIES:
            require(category in categories, f"missing category {category}", errors)
            require(isinstance(categories.get(category), list), f"category {category} must be an array", errors)

    require(is_non_empty_string(data.get("generated_at")), "generated_at is required", errors)
    return errors


def validate_weekly(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    require(data.get("type") == "weekly", "type must be weekly", errors)
    require(WEEK_RE.match(str(data.get("week", ""))) is not None, "week must look like YYYY-Www", errors)
    require(data.get("reading_minutes") == 15, "weekly reading_minutes must be 15", errors)
    date_range = data.get("date_range")
    require(isinstance(date_range, dict), "date_range must be an object", errors)
    if isinstance(date_range, dict):
        require(DATE_RE.match(str(date_range.get("start", ""))) is not None, "date_range.start must be ISO date", errors)
        require(DATE_RE.match(str(date_range.get("end", ""))) is not None, "date_range.end must be ISO date", errors)
    top_items = data.get("top_items")
    require(isinstance(top_items, list), "top_items must be an array", errors)
    if isinstance(top_items, list):
        require(len(top_items) <= 15, "weekly top_items must contain at most 15 items", errors)
        for index, item in enumerate(top_items):
            require(isinstance(item, dict), f"top_items[{index}] must be an object", errors)
            if not isinstance(item, dict):
                continue
            require(item.get("rank") == index + 1, f"top_items[{index}].rank must be {index + 1}", errors)
            require(is_non_empty_string(item.get("title")), f"top_items[{index}].title is required", errors)
            require(is_non_empty_string(item.get("why_it_matters")), f"top_items[{index}].why_it_matters is required", errors)
            validate_sources(item.get("sources"), errors, weekly=True)
    require(isinstance(data.get("themes"), list), "themes must be an array", errors)
    require(isinstance(data.get("watch_next"), list), "watch_next must be an array", errors)
    require(is_non_empty_string(data.get("generated_at")), "generated_at is required", errors)
    return errors


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: validate_digest.py <digest.json>", file=sys.stderr)
        return 1
    path = Path(argv[1])
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"ERROR: cannot read JSON: {exc}", file=sys.stderr)
        return 1
    if not isinstance(data, dict):
        print("ERROR: top-level JSON must be an object", file=sys.stderr)
        return 1
    errors = validate_weekly(data) if data.get("type") == "weekly" else validate_daily(data)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"OK: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
```

- [ ] **Step 4: Run validator on fixtures**

Run:

```bash
python3 scripts/validate_digest.py scripts/fixtures/daily-valid.json
python3 scripts/validate_digest.py scripts/fixtures/weekly-valid.json
```

Expected output:

```text
OK: scripts/fixtures/daily-valid.json
OK: scripts/fixtures/weekly-valid.json
```

- [ ] **Step 5: Commit**

Run:

```bash
git add scripts/validate_digest.py scripts/fixtures/daily-valid.json scripts/fixtures/weekly-valid.json
git commit -m "feat: add digest validator"
```

---

### Task 3: Static Renderer And Base Templates

**Files:**
- Create: `scripts/render_site.py`
- Create: `src/templates/base.html`
- Create: `src/templates/daily.html`
- Create: `src/templates/weekly.html`
- Create: `src/static/styles.css`
- Create: `src/static/app.js`

**Interfaces:**
- Consumes: valid JSON files from `content/daily/` and `content/weekly/`.
- Produces: static output in `site/`.
- Produces: `site/index.html`, `site/daily/YYYY-MM-DD/index.html`, `site/weekly/YYYY-Www/index.html`, `site/static/styles.css`, and `site/static/app.js`.

- [ ] **Step 1: Add renderer script skeleton**

Create `scripts/render_site.py` with:

```python
#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import shutil
from pathlib import Path
from string import Template
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTENT_DAILY = ROOT / "content" / "daily"
CONTENT_WEEKLY = ROOT / "content" / "weekly"
TEMPLATES = ROOT / "src" / "templates"
STATIC = ROOT / "src" / "static"
SITE = ROOT / "site"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def load_template(name: str) -> Template:
    return Template((TEMPLATES / name).read_text(encoding="utf-8"))


def render_base(title: str, body: str) -> str:
    return load_template("base.html").substitute(title=esc(title), body=body)


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def source_links(sources: list[dict[str, Any]]) -> str:
    links = []
    for source in sources:
        label = f"第{source.get('page', '')}版 · {source.get('headline', '')}"
        links.append(f'<a href="{esc(source.get("url", ""))}" target="_blank" rel="noreferrer">{esc(label)}</a>')
    return "".join(f"<li>{link}</li>" for link in links)


def render_daily(data: dict[str, Any]) -> str:
    items = []
    for item in data.get("top_items", []):
        facts = "".join(f"<li>{esc(fact)}</li>" for fact in item.get("key_facts", []))
        items.append(
            f"""
            <article class="signal-card">
              <div class="signal-rank">{int(item.get("rank", 0)):02d}</div>
              <div class="signal-main">
                <div class="signal-meta">{esc(item.get("category", ""))} · {esc(item.get("confidence", ""))}</div>
                <h2>{esc(item.get("title", ""))}</h2>
                <p class="why">{esc(item.get("why_it_matters", ""))}</p>
                <ul class="facts">{facts}</ul>
                <ul class="sources">{source_links(item.get("sources", []))}</ul>
              </div>
            </article>
            """
        )
    categories = []
    for name, entries in data.get("categories", {}).items():
        rows = []
        for entry in entries:
            rows.append(
                f"""
                <li>
                  <strong>{esc(entry.get("title", ""))}</strong>
                  <span>{esc(entry.get("summary", ""))}</span>
                  <ul class="sources">{source_links(entry.get("sources", []))}</ul>
                </li>
                """
            )
        categories.append(f"<section class='category'><h3>{esc(name)}</h3><ul>{''.join(rows) or '<li class=\"empty\">今日无高价值条目</li>'}</ul></section>")
    body = load_template("daily.html").substitute(
        date=esc(data.get("date", "")),
        source=esc(data.get("source", "")),
        page_count=esc(data.get("page_count", "")),
        article_count=esc(data.get("article_count", "")),
        reading_minutes=esc(data.get("reading_minutes", "")),
        signals="".join(items),
        categories="".join(categories),
    )
    return render_base(f"海南日报精读 {data.get('date', '')}", body)


def render_weekly(data: dict[str, Any]) -> str:
    items = []
    for item in data.get("top_items", []):
        facts = "".join(f"<li>{esc(fact)}</li>" for fact in item.get("key_facts", []))
        items.append(
            f"""
            <article class="signal-card">
              <div class="signal-rank">{int(item.get("rank", 0)):02d}</div>
              <div class="signal-main">
                <h2>{esc(item.get("title", ""))}</h2>
                <p class="why">{esc(item.get("why_it_matters", ""))}</p>
                <ul class="facts">{facts}</ul>
                <ul class="sources">{source_links(item.get("sources", []))}</ul>
              </div>
            </article>
            """
        )
    themes = "".join(f"<li><strong>{esc(t.get('title', ''))}</strong><span>{esc(t.get('summary', ''))}</span></li>" for t in data.get("themes", []))
    watch_next = "".join(f"<li>{esc(item)}</li>" for item in data.get("watch_next", []))
    body = load_template("weekly.html").substitute(
        week=esc(data.get("week", "")),
        start=esc(data.get("date_range", {}).get("start", "")),
        end=esc(data.get("date_range", {}).get("end", "")),
        reading_minutes=esc(data.get("reading_minutes", "")),
        signals="".join(items),
        themes=themes,
        watch_next=watch_next,
    )
    return render_base(f"海南日报周报 {data.get('week', '')}", body)


def copy_static() -> None:
    target = SITE / "static"
    target.mkdir(parents=True, exist_ok=True)
    for path in STATIC.iterdir():
        if path.is_file():
            shutil.copy2(path, target / path.name)


def main() -> int:
    if SITE.exists():
        shutil.rmtree(SITE)
    copy_static()
    daily_files = sorted(CONTENT_DAILY.glob("*.json"))
    weekly_files = sorted(CONTENT_WEEKLY.glob("*.json"))
    latest_daily = None
    for path in daily_files:
        data = read_json(path)
        latest_daily = data
        write_file(SITE / "daily" / data["date"] / "index.html", render_daily(data))
    for path in weekly_files:
        data = read_json(path)
        write_file(SITE / "weekly" / data["week"] / "index.html", render_weekly(data))
    if latest_daily is not None:
        write_file(SITE / "index.html", render_daily(latest_daily))
    else:
        write_file(SITE / "index.html", render_base("海南日报精读", "<main class='shell'><h1>海南日报精读</h1><p>暂无日报内容。</p></main>"))
    print(f"Rendered {SITE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Create templates**

Create `src/templates/base.html`:

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>$title</title>
    <link rel="stylesheet" href="/static/styles.css">
  </head>
  <body>
    $body
    <script src="/static/app.js"></script>
  </body>
</html>
```

Create `src/templates/daily.html`:

```html
<div class="app-shell">
  <aside class="primary-nav">
    <a class="brand" href="/">
      <span>HN</span><strong>DAILY</strong>
    </a>
    <nav>
      <a href="/" class="active">日报</a>
      <a href="/weekly/">周报</a>
      <a href="#categories">分类</a>
    </nav>
  </aside>
  <aside class="date-rail">
    <div class="tabs"><a class="active" href="/">日报</a><a href="/weekly/">周报</a></div>
    <h2>归档</h2>
    <a class="date-link active" href="/daily/$date/">$date<span>$article_count 篇</span></a>
  </aside>
  <main class="content-shell">
    <header class="hero">
      <p class="eyebrow">$source · $page_count 版 · $article_count 篇 · HN DAILY</p>
      <h1><span>海南</span>日报精读</h1>
      <p class="subhead">$date · 约 $reading_minutes 分钟</p>
    </header>
    <section class="panel highlight-panel">
      <div class="section-heading">
        <h2>今日看点</h2>
        <span>$article_count 篇报道 · 约 $reading_minutes 分钟</span>
      </div>
      <div class="signals">$signals</div>
    </section>
    <section id="categories" class="category-grid">$categories</section>
  </main>
</div>
```

Create `src/templates/weekly.html`:

```html
<div class="app-shell">
  <aside class="primary-nav">
    <a class="brand" href="/">
      <span>HN</span><strong>DAILY</strong>
    </a>
    <nav>
      <a href="/">日报</a>
      <a href="/weekly/" class="active">周报</a>
      <a href="#themes">主题</a>
    </nav>
  </aside>
  <aside class="date-rail">
    <div class="tabs"><a href="/">日报</a><a class="active" href="/weekly/">周报</a></div>
    <h2>周报</h2>
    <a class="date-link active" href="/weekly/$week/">$week<span>$start 至 $end</span></a>
  </aside>
  <main class="content-shell">
    <header class="hero">
      <p class="eyebrow">$start 至 $end · HN WEEKLY</p>
      <h1><span>海南</span>日报周报</h1>
      <p class="subhead">$week · 约 $reading_minutes 分钟</p>
    </header>
    <section class="panel highlight-panel">
      <div class="section-heading">
        <h2>本周看点</h2>
        <span>最多 15 条</span>
      </div>
      <div class="signals">$signals</div>
    </section>
    <section id="themes" class="panel">
      <h2>趋势主题</h2>
      <ul class="theme-list">$themes</ul>
    </section>
    <section class="panel">
      <h2>继续关注</h2>
      <ul class="theme-list">$watch_next</ul>
    </section>
  </main>
</div>
```

- [ ] **Step 3: Create responsive CSS and JS**

Create `src/static/styles.css`:

```css
:root {
  color-scheme: light dark;
  --bg: #0d1117;
  --panel: #151b23;
  --line: #27313d;
  --text: #eef3f8;
  --muted: #98a6b5;
  --accent: #24c08b;
  --soft: #10261f;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  line-height: 1.6;
}

a {
  color: var(--accent);
  text-decoration: none;
}

a:hover {
  text-decoration: underline;
}

.shell {
  width: min(1040px, calc(100% - 32px));
  margin: 0 auto;
  padding: 56px 0;
}

.hero {
  padding: 32px 0 48px;
  border-bottom: 1px solid var(--line);
}

.eyebrow,
.subhead,
.signal-meta,
.section-heading span {
  color: var(--muted);
  letter-spacing: 0;
}

.hero h1 {
  margin: 12px 0;
  font-size: clamp(48px, 8vw, 104px);
  line-height: 1;
}

.panel {
  margin-top: 40px;
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 28px;
  background: var(--panel);
}

.section-heading {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  border-bottom: 1px solid var(--line);
  margin-bottom: 16px;
}

.section-heading h2 {
  margin: 0 0 14px;
}

.signals {
  display: grid;
  gap: 0;
}

.signal-card {
  display: grid;
  grid-template-columns: 48px 1fr;
  gap: 20px;
  padding: 22px 0;
  border-bottom: 1px solid var(--line);
}

.signal-card:last-child {
  border-bottom: 0;
}

.signal-rank {
  color: var(--accent);
  font-weight: 700;
}

.signal-main h2 {
  margin: 0 0 8px;
  font-size: 22px;
}

.why {
  margin: 0 0 12px;
  color: var(--text);
}

.facts,
.sources,
.theme-list {
  margin: 10px 0 0;
  padding-left: 20px;
  color: var(--muted);
}

.category-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
  margin-top: 24px;
}

.category {
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 20px;
  background: var(--panel);
}

.category h3 {
  margin: 0 0 10px;
}

.category ul {
  margin: 0;
  padding-left: 18px;
}

.category li {
  margin: 10px 0;
}

.category span,
.theme-list span {
  display: block;
  color: var(--muted);
}

.empty {
  color: var(--muted);
}

@media (max-width: 720px) {
  .shell {
    width: min(100% - 24px, 640px);
    padding: 28px 0;
  }

  .hero {
    padding: 16px 0 32px;
  }

  .panel {
    padding: 20px;
    margin-top: 24px;
  }

  .section-heading {
    align-items: flex-start;
    flex-direction: column;
    gap: 4px;
  }

  .signal-card {
    grid-template-columns: 1fr;
    gap: 8px;
  }

  .category-grid {
    grid-template-columns: 1fr;
  }
}
```

Create `src/static/app.js`:

```javascript
document.documentElement.classList.add("js-ready");
```

- [ ] **Step 4: Copy fixtures into content and render**

Run:

```bash
cp scripts/fixtures/daily-valid.json content/daily/2026-07-08.json
cp scripts/fixtures/weekly-valid.json content/weekly/2026-W28.json
python3 scripts/render_site.py
```

Expected output:

```text
Rendered /Users/skr/Work/hndaily/hndaily-web/site
```

- [ ] **Step 5: Verify generated files exist**

Run:

```bash
test -f site/index.html
test -f site/daily/2026-07-08/index.html
test -f site/weekly/2026-W28/index.html
test -f site/static/styles.css
```

Expected: all commands exit with status `0`.

- [ ] **Step 6: Remove fixture content files before commit**

Run:

```bash
rm content/daily/2026-07-08.json content/weekly/2026-W28.json
```

Expected: generated `site/` remains ignored and fixture copies are not committed.

- [ ] **Step 7: Commit**

Run:

```bash
git add scripts/render_site.py src/templates/base.html src/templates/daily.html src/templates/weekly.html src/static/styles.css src/static/app.js
git commit -m "feat: render static digest site"
```

---

### Task 4: Local Preview Workflow

**Files:**
- Create: `scripts/preview.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: generated `site/` directory.
- Produces: local preview server at `http://127.0.0.1:8765`.

- [ ] **Step 1: Create preview script**

Create `scripts/preview.py`:

```python
#!/usr/bin/env python3
from __future__ import annotations

import http.server
import socketserver
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
PORT = 8765


def main() -> int:
    if not SITE.exists():
        print("site/ does not exist. Run: python3 scripts/render_site.py")
        return 1
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("127.0.0.1", PORT), handler) as httpd:
        print(f"Serving http://127.0.0.1:{PORT}")
        import os

        os.chdir(SITE)
        httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Update README workflow**

Append to `README.md`:

```markdown
## Local Workflow

Validate a digest:

```bash
python3 scripts/validate_digest.py content/daily/YYYY-MM-DD.json
```

Render the static site:

```bash
python3 scripts/render_site.py
```

Preview locally:

```bash
python3 scripts/preview.py
```

Open `http://127.0.0.1:8765`.
```

- [ ] **Step 3: Verify preview script fails clearly without site**

Run:

```bash
mv site site.backup
python3 scripts/preview.py
mv site.backup site
```

Expected output includes:

```text
site/ does not exist. Run: python3 scripts/render_site.py
```

- [ ] **Step 4: Commit**

Run:

```bash
git add scripts/preview.py README.md
git commit -m "docs: add local preview workflow"
```

---

### Task 5: Scheduled Job Boundary

**Files:**
- Create: `scripts/run_daily_pipeline.sh`
- Create: `.env.example`
- Modify: `README.md`

**Interfaces:**
- Consumes: environment variables `HNDAILY_SKILL_DIR` and `HNDAILY_DATE`.
- Produces: a documented local pipeline placeholder that keeps raw and intermediate data outside git.

- [ ] **Step 1: Create env example**

Create `.env.example`:

```bash
HNDAILY_SKILL_DIR=/Users/skr/Work/hndaily/hndaily-skill
HNDAILY_WEB_DIR=/Users/skr/Work/hndaily/hndaily-web
```

- [ ] **Step 2: Create daily pipeline shell**

Create `scripts/run_daily_pipeline.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

WEB_DIR="${HNDAILY_WEB_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
SKILL_DIR="${HNDAILY_SKILL_DIR:-/Users/skr/Work/hndaily/hndaily-skill}"
DATE_ARG="${HNDAILY_DATE:-}"

mkdir -p "$WEB_DIR/data/raw" "$WEB_DIR/data/intermediate" "$WEB_DIR/data/tmp"

if [ -n "$DATE_ARG" ]; then
  RAW_JSON="$(python3 "$SKILL_DIR/crawler.py" "$DATE_ARG")"
else
  RAW_JSON="$(python3 "$SKILL_DIR/crawler.py")"
fi

echo "Raw crawler JSON: $RAW_JSON"
echo "Next step: generate content/daily/<date>.json from raw data, validate it, then render site/."
echo "Raw and intermediate files stay ignored by git."
```

- [ ] **Step 3: Make script executable**

Run:

```bash
chmod +x scripts/run_daily_pipeline.sh
```

- [ ] **Step 4: Update README scheduled job section**

Append to `README.md`:

```markdown
## Scheduled Job Boundary

The future scheduled job should:

1. Run the crawler from `HNDAILY_SKILL_DIR`.
2. Store raw crawler output under ignored local data directories.
3. Generate publishable daily digest JSON under `content/daily/`.
4. Validate the digest with `scripts/validate_digest.py`.
5. Render `site/` with `scripts/render_site.py`.
6. Sync `site/` or the chosen publishable output to the cloud host.

Raw files, temporary files, logs, PDFs, audio, and caches must remain outside git.
```

- [ ] **Step 5: Commit**

Run:

```bash
git add .env.example scripts/run_daily_pipeline.sh README.md
git commit -m "chore: define scheduled pipeline boundary"
```

---

### Task 6: Visual Verification

**Files:**
- Modify: no source files unless verification finds layout problems.

**Interfaces:**
- Consumes: `site/` generated by `scripts/render_site.py`.
- Produces: verified desktop and mobile layout.

- [ ] **Step 1: Render fixture site**

Run:

```bash
cp scripts/fixtures/daily-valid.json content/daily/2026-07-08.json
cp scripts/fixtures/weekly-valid.json content/weekly/2026-W28.json
python3 scripts/render_site.py
```

Expected output:

```text
Rendered /Users/skr/Work/hndaily/hndaily-web/site
```

- [ ] **Step 2: Start preview server**

Run:

```bash
python3 scripts/preview.py
```

Expected output:

```text
Serving http://127.0.0.1:8765
```

- [ ] **Step 3: Check desktop viewport**

Open `http://127.0.0.1:8765` at desktop width. Verify:

- Header, date, source counts, and reading time are visible.
- 今日看点 appears before categories.
- Source links are clickable.
- Text does not overlap or overflow.

- [ ] **Step 4: Check mobile viewport**

Open `http://127.0.0.1:8765` at mobile width. Verify:

- Content is single-column.
- Rank, title, why-it-matters, facts, and source links remain readable.
- Category sections stack vertically.
- No horizontal scrolling is needed.

- [ ] **Step 5: Remove fixture content copies**

Run:

```bash
rm content/daily/2026-07-08.json content/weekly/2026-W28.json
```

- [ ] **Step 6: Commit verification fixes if any**

If CSS or templates changed, run:

```bash
git add src/templates src/static
git commit -m "fix: polish responsive digest layout"
```

If no source files changed, do not create an empty commit.
