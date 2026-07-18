# HNHOT Self-Contained Data Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `hndaily-web-radar` 在不读取任何相邻项目文件的情况下完成海南日报抓取，把原始、模型输入、模型输出和审计 JSON 按日期写入统一项目目录，并把 HNHOT v1 提示词、JSON Schema 和受控配置纳入版本管理。

**Architecture:** 保留现有 Python 标准库抓取器和两阶段 Shell 流水线，但把抓取器迁入 `scripts/`，把所有私有 JSON 收敛到 `data/json/`，并从流水线中删除 `HNDAILY_SKILL_DIR`。本阶段只建立 HNHOT 结构化加工的版本化资产，不切换当前公开内容 schema；下一阶段再把 `hnhot-v1` 契约接入正式发布，保证每个提交都保持现有站点可构建。

**Tech Stack:** Python 3 标准库、`unittest`、Bash、JSON Schema Draft 2020-12、Markdown、静态 JSON。

## Global Constraints

- 正式产品名统一写作 `HNHOT`；不得继续新增 `HN·HOT`、`HN HOT` 或“海南信息雷达”品牌文案。
- 抓取器、提示词、JSON Schema、配置、测试夹具和操作文档全部位于 `hndaily-web-radar`。
- 运行时不得读取 `hndaily-skill`、`HNDAILY_SKILL_DIR` 或其他仓库文件。
- 原始抓取固定写入 `data/json/raw/YYYY-MM-DD.json`；模型输入、模型输出和审计分别进入同级专用目录。
- 生成的原始和中间 JSON 留在项目目录但不进入 Git；提示词、Schema、配置、测试夹具和目录说明必须进入 Git。
- 抓取器保留指定日期、最新一期发现、30 分钟缓存、`--force`、并发抓取、正文错误记录和 stdout 首行绝对路径契约。
- 本阶段不改变公开内容 schema、评分逻辑、页面路由或渲染结果；这些变更属于后续独立计划。
- 所有文件写入继续使用临时文件加原子替换；失败不得留下半写 JSON。
- 不新增第三方 Python 依赖。

---

## Program Split

HNHOT 总设计拆为以下可独立验收阶段：

1. **本计划：自包含数据基础。** 迁入抓取器，统一项目内 JSON 目录，落盘提示词、Schema 和受控配置。
2. **全量结构化发布契约。** 新建 schema v7，将摘要、N/H/M、主体、地区、议题和事件关系接入模型校验与正式文章存储，移除公开发布对评分和精选的依赖。
3. **头版与全部体验。** 实现四筛选、动态全国要闻 TOP N、完整头版信息流、版面归并、四个移动端一级路由和日报空状态。
4. **长期认知索引与更多。** 实现收藏对象升级、主体目录、地区目录、保守事件关联和时间线页面。

每个阶段完成后单独运行全量测试并提交。后续计划不得重新引入外部抓取器或第二套数据目录。

## File Map

### Project-local acquisition

- Create `scripts/crawler.py`: project-local Hainan Daily crawler; default output is `data/json/raw/`.
- Create `tests/test_crawler.py`: parser, output path, cache and CLI contract tests.
- Create `tests/fixtures/crawler/front-page.html`: minimal front-page and page-list fixture.
- Create `tests/fixtures/crawler/article.html`: minimal article body fixture.

### Canonical JSON workspace

- Create `data/json/README.md`: authoritative directory ownership, Git policy and filenames.
- Modify `scripts/run_radar_pipeline.sh`: call the local crawler and resolve canonical JSON paths.
- Modify `tests/test_radar_pipeline_cli.py`: verify first-pass and resumed paths live under the canonical directories.
- Modify `.gitignore`: ignore generated JSON families without hiding the directory documentation.
- Modify `.env.example`: remove external skill settings and document project-local overrides.

### Versioned HNHOT enrichment assets

- Create `prompts/article-enrichment/v1/prompt.md`: source-grounded HNHOT enrichment instructions.
- Create `prompts/article-enrichment/v1/schema.json`: strict model-output JSON Schema.
- Create `prompts/article-enrichment/v1/manifest.json`: prompt/schema version binding.
- Create `config/topics.json`: controlled topic catalog.
- Create `config/page-sections.json`: canonical page-section mapping seed.
- Create `config/subjects.json`: explicit subject alias/merge override seed.
- Create `tests/test_hnhot_assets.py`: exact-field, version, enum and cross-file consistency tests.

### Repository boundary and documentation

- Modify `README.md`: HNHOT name, self-contained commands and canonical output locations.
- Create `tests/test_repository_boundary.py`: prevent reintroduction of external crawler dependencies.

---

### Task 1: Bring the crawler into the web repository

**Files:**
- Create: `scripts/crawler.py`
- Create: `tests/test_crawler.py`
- Create: `tests/fixtures/crawler/front-page.html`
- Create: `tests/fixtures/crawler/article.html`

**Interfaces:**
- Consumes: `http://news.hndaily.cn/paperindex.htm` and dated `node_1.htm`, page and article HTML.
- Produces: `crawl(date: datetime.date, front_html: str) -> dict`, `parse_page_list(html_str: str) -> list[tuple[str, str, str]]`, `parse_article_links(html_str: str) -> list[tuple[str, str]]`, `parse_article(html_str: str) -> dict`, and `main(argv: list[str]) -> int`.
- Produces CLI stdout line 1 as the absolute path to `data/json/raw/YYYY-MM-DD.json` unless `HNDAILY_DATA_DIR` explicitly overrides the raw directory.

- [ ] **Step 1: Add minimal publisher HTML fixtures**

Create `tests/fixtures/crawler/front-page.html` with this exact structure:

```html
<!doctype html>
<html><body>
  <a id="pageLink" href="node_1.htm">第 1 版：头版</a>
  <a id="pageLink" href="node_2.htm">第 2 版：本省新闻</a>
  <div id="content_1_1"><a href="content_1_1001.htm">头版测试报道</a></div>
</body></html>
```

Create `tests/fixtures/crawler/article.html`:

```html
<!doctype html>
<html><body>
  <founder-title>头版测试报道</founder-title>
  <founder-author>记者 测试</founder-author>
  <founder-content><P>第一段事实。</P><P>第二段事实。</P></founder-content>
</body></html>
```

- [ ] **Step 2: Write failing crawler tests**

Create `tests/test_crawler.py`:

```python
import datetime as dt
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/crawler"


def load_crawler():
    spec = importlib.util.spec_from_file_location(
        "hnhot_crawler", ROOT / "scripts/crawler.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class CrawlerTests(unittest.TestCase):
    def test_default_output_is_project_local_json_raw(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            crawler = load_crawler()
        self.assertEqual(crawler.OUTPUT_DIR, ROOT / "data/json/raw")

    def test_parses_pages_links_and_article_body(self):
        crawler = load_crawler()
        front = (FIXTURES / "front-page.html").read_text(encoding="utf-8")
        article = (FIXTURES / "article.html").read_text(encoding="utf-8")
        self.assertEqual(
            crawler.parse_page_list(front),
            [("001", "头版", "node_1.htm"), ("002", "本省新闻", "node_2.htm")],
        )
        self.assertEqual(
            crawler.parse_article_links(front),
            [("content_1_1001.htm", "头版测试报道")],
        )
        self.assertEqual(
            crawler.parse_article(article),
            {
                "title": "头版测试报道",
                "author": "记者 测试",
                "content": "第一段事实。\n\n第二段事实。",
            },
        )

    def test_main_writes_atomic_dated_json_and_prints_absolute_path(self):
        crawler = load_crawler()
        payload = {
            "source": "海南日报",
            "date": "2026-07-18",
            "page_count": 0,
            "article_count": 0,
            "pages": [],
        }
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            crawler, "OUTPUT_DIR", Path(tmp)
        ), mock.patch.object(
            crawler, "fetch", return_value="front"
        ), mock.patch.object(
            crawler, "crawl", return_value=payload
        ), mock.patch("builtins.print") as printed:
            self.assertEqual(crawler.main(["crawler.py", "2026-07-18"]), 0)
            target = Path(tmp) / "2026-07-18.json"
            self.assertTrue(target.is_file())
            self.assertEqual(printed.call_args_list[0].args, (str(target.resolve()),))
            self.assertFalse((Path(tmp) / ".2026-07-18.json.tmp").exists())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run the crawler tests and verify they fail**

Run:

```bash
python3 -m unittest tests.test_crawler -v
```

Expected: FAIL because `scripts/crawler.py` does not exist.

- [ ] **Step 4: Create the project-local crawler**

Use `/Users/skr/Work/hndaily/hndaily-skill/crawler.py` only as migration input. Add its complete HTTP, parsing, URL, discovery, concurrency, caching and CLI implementation to `scripts/crawler.py`, then make these project-local changes:

```python
ROOT = Path(__file__).resolve().parents[1]


def _resolve_output_dir() -> Path:
    env = os.environ.get("HNDAILY_DATA_DIR")
    if env:
        return Path(env).expanduser().resolve()
    return ROOT / "data/json/raw"


def _write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)
```

Replace the direct final `write_text` in `main()` with:

```python
out_path = OUTPUT_DIR / f"{date.isoformat()}.json"
_write_json_atomic(out_path, payload)
print(str(out_path.resolve()))
```

Keep `BASE`, `UA`, `TIMEOUT`, `MAX_WORKERS`, retry behavior, parser expressions, URL formats, `discover_current_issue()`, `CACHE_TTL_SECONDS`, `--force` and error exit codes identical to the source implementation. The resulting file must not import or open any path outside this repository.

- [ ] **Step 5: Run focused tests**

Run:

```bash
python3 -m unittest tests.test_crawler -v
```

Expected: 3 tests PASS.

- [ ] **Step 6: Verify the CLI help failure and a fixture-free syntax check**

Run:

```bash
python3 -m py_compile scripts/crawler.py
python3 scripts/crawler.py invalid-date
```

Expected: compilation succeeds; the invalid date command exits 1 and stderr contains `expected YYYY-MM-DD`.

- [ ] **Step 7: Commit the crawler migration**

```bash
git add scripts/crawler.py tests/test_crawler.py tests/fixtures/crawler/front-page.html tests/fixtures/crawler/article.html
git commit -m "feat: make Hainan Daily crawler project-local"
```

---

### Task 2: Route every private JSON artifact into `data/json`

**Files:**
- Create: `data/json/README.md`
- Modify: `scripts/run_radar_pipeline.sh`
- Modify: `tests/test_radar_pipeline_cli.py`
- Modify: `.gitignore`
- Modify: `.env.example`

**Interfaces:**
- Consumes: optional `HNDAILY_RAW_JSON`, `HNDAILY_DATA_DIR`, `HNDAILY_JSON_ROOT`, `RADAR_MODEL_OUTPUT_JSON`, `RADAR_CONTENT_ROOT`, `RADAR_SITE_ROOT`, `RADAR_RUN_ROOT`, and `RADAR_AS_OF`.
- Produces default paths `data/json/raw/{date}.json`, `data/json/model-input/{date}.json`, `data/json/model-output/{date}.json`, `data/json/audits/{date}.prefilter.json`, and `data/json/audits/{date}.publication.json`.
- Removes: `HNDAILY_SKILL_DIR` and `HNDAILY_INTERMEDIATE_DIR`.

- [ ] **Step 1: Extend the pipeline test with canonical-path assertions**

In `tests/test_radar_pipeline_cli.py`, replace the environment construction with:

```python
json_root = work / "data/json"
env = os.environ | {
    "HNDAILY_WEB_DIR": str(ROOT),
    "HNDAILY_RAW_JSON": str(raw),
    "HNDAILY_JSON_ROOT": str(json_root),
    "RADAR_CONTENT_ROOT": str(work / "content"),
    "RADAR_SITE_ROOT": str(work / "site"),
    "RADAR_RUN_ROOT": str(work / "run"),
    "RADAR_AS_OF": "2026-07-10",
}
```

Immediately after parsing `paths`, add:

```python
self.assertEqual(
    Path(paths["MODEL_INPUT_JSON"]),
    json_root / "model-input/2026-07-09.json",
)
self.assertEqual(
    Path(paths["MODEL_OUTPUT_JSON"]),
    json_root / "model-output/2026-07-09.json",
)
self.assertEqual(
    Path(paths["PREFILTER_JSON"]),
    json_root / "audits/2026-07-09.prefilter.json",
)
self.assertEqual(
    Path(paths["AUDIT_JSON"]),
    json_root / "audits/2026-07-09.publication.json",
)
```

- [ ] **Step 2: Run the pipeline test and verify it fails on the old layout**

Run:

```bash
python3 -m unittest tests.test_radar_pipeline_cli -v
```

Expected: FAIL because the pipeline still writes `*.radar-model-input.json` under `data/intermediate`.

- [ ] **Step 3: Implement canonical JSON path resolution in the shell pipeline**

Replace the path and crawler section at the start of `scripts/run_radar_pipeline.sh` with:

```bash
#!/usr/bin/env bash
set -euo pipefail
WEB_DIR="${HNDAILY_WEB_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
JSON_ROOT="${HNDAILY_JSON_ROOT:-$WEB_DIR/data/json}"
RAW_DIR="${HNDAILY_DATA_DIR:-$JSON_ROOT/raw}"
MODEL_INPUT_DIR="$JSON_ROOT/model-input"
MODEL_OUTPUT_DIR="$JSON_ROOT/model-output"
AUDIT_DIR="$JSON_ROOT/audits"
DATE_ARG="${1:-}"
CONTENT_ROOT="${RADAR_CONTENT_ROOT:-$WEB_DIR/content}"
SITE_ROOT="${RADAR_SITE_ROOT:-$WEB_DIR/site}"
AS_OF="${RADAR_AS_OF:-$(date +%F)}"
mkdir -p "$RAW_DIR" "$MODEL_INPUT_DIR" "$MODEL_OUTPUT_DIR" "$AUDIT_DIR"

if [ -n "${HNDAILY_RAW_JSON:-}" ]; then
  RAW_JSON="$HNDAILY_RAW_JSON"
elif [ -n "$DATE_ARG" ]; then
  RAW_JSON="$(HNDAILY_DATA_DIR="$RAW_DIR" python3 "$WEB_DIR/scripts/crawler.py" "$DATE_ARG")"
else
  RAW_JSON="$(HNDAILY_DATA_DIR="$RAW_DIR" python3 "$WEB_DIR/scripts/crawler.py")"
fi

DATE_STEM="$(basename "$RAW_JSON" .json)"
MODEL_INPUT_JSON="$MODEL_INPUT_DIR/$DATE_STEM.json"
MODEL_OUTPUT_JSON="${RADAR_MODEL_OUTPUT_JSON:-$MODEL_OUTPUT_DIR/$DATE_STEM.json}"
PREFILTER_JSON="$AUDIT_DIR/$DATE_STEM.prefilter.json"
AUDIT_JSON="${RADAR_AUDIT_JSON:-$AUDIT_DIR/$DATE_STEM.publication.json}"
RUN_ROOT="${RADAR_RUN_ROOT:-$WEB_DIR/data/tmp/radar-$DATE_STEM}"
STAGED_CONTENT="$RUN_ROOT/content"
STAGED_SITE="$RUN_ROOT/site"
STAGED_AUDIT="$RUN_ROOT/audit.json"
```

Keep the existing prepare, model-handoff, staged build, render and publish commands after this block unchanged. Keep stdout keys `RAW_JSON`, `MODEL_INPUT_JSON`, `MODEL_OUTPUT_JSON`, `PREFILTER_JSON`, and `AUDIT_JSON` unchanged so external automation can parse them.

- [ ] **Step 4: Document and ignore the generated JSON families**

Create `data/json/README.md`:

```markdown
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
```

Replace the old generated-data entries in `.gitignore` with:

```gitignore
# Local generated newspaper data and intermediate artifacts
data/json/raw/
data/json/model-input/
data/json/model-output/
data/json/audits/
# Legacy locations remain ignored during migration; active code must not write them.
data/raw/
data/intermediate/
data/cache/
data/tmp/
data/tmp/radar-*/
data/audio/
data/pdf/
*.tmp
*.log
*.mp3
*.pdf
```

Do not ignore `data/json/README.md`.

Replace `.env.example` with:

```dotenv
# Optional project-local overrides. Defaults already point inside this repo.
HNDAILY_WEB_DIR=/absolute/path/to/hndaily-web-radar
HNDAILY_JSON_ROOT=/absolute/path/to/hndaily-web-radar/data/json

# Optional publish/build overrides.
RADAR_CONTENT_ROOT=/absolute/path/to/hndaily-web-radar/content
RADAR_SITE_ROOT=/absolute/path/to/hndaily-web-radar/site
```

- [ ] **Step 5: Run the focused pipeline test**

Run:

```bash
python3 -m unittest tests.test_radar_pipeline_cli -v
```

Expected: PASS; first run returns `STATUS=MODEL_OUTPUT_REQUIRED`, second and third runs return `STATUS=COMPLETE`, and all private artifacts use the canonical directory families.

- [ ] **Step 6: Verify no legacy path remains in active configuration**

Run:

```bash
rg -n "HNDAILY_SKILL_DIR|HNDAILY_INTERMEDIATE_DIR|data/intermediate" scripts/run_radar_pipeline.sh .env.example data/json/README.md
```

Expected: no matches; `rg` exits 1.

- [ ] **Step 7: Commit canonical JSON storage**

```bash
git add data/json/README.md scripts/run_radar_pipeline.sh tests/test_radar_pipeline_cli.py .gitignore .env.example
git commit -m "refactor: keep HNHOT pipeline data inside repository"
```

---

### Task 3: Version the HNHOT enrichment prompt and controlled catalogs

**Files:**
- Create: `prompts/article-enrichment/v1/prompt.md`
- Create: `prompts/article-enrichment/v1/schema.json`
- Create: `prompts/article-enrichment/v1/manifest.json`
- Create: `config/topics.json`
- Create: `config/page-sections.json`
- Create: `config/subjects.json`
- Create: `tests/test_hnhot_assets.py`

**Interfaces:**
- Produces prompt version `hnhot-v1` and target article schema version `7`.
- Produces exact model item fields `candidate_id`, `ai_summary`, `scope`, `scope_evidence`, `subjects`, `location_mentions`, `topic_mentions`, and `event_relation`.
- Produces controlled topic IDs and deterministic page-section/subject override files for later runtime loaders.

- [ ] **Step 1: Write failing cross-file asset tests**

Create `tests/test_hnhot_assets.py`:

```python
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROMPT_DIR = ROOT / "prompts/article-enrichment/v1"


class HnhotAssetTests(unittest.TestCase):
    def test_manifest_binds_prompt_and_strict_schema(self):
        manifest = json.loads((PROMPT_DIR / "manifest.json").read_text(encoding="utf-8"))
        schema = json.loads((PROMPT_DIR / "schema.json").read_text(encoding="utf-8"))
        prompt = (PROMPT_DIR / "prompt.md").read_text(encoding="utf-8")
        self.assertEqual(
            manifest,
            {
                "schema_version": 1,
                "prompt_version": "hnhot-v1",
                "article_schema_version": 7,
                "prompt": "prompt.md",
                "output_schema": "schema.json",
            },
        )
        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertFalse(schema["additionalProperties"])
        item = schema["$defs"]["item"]
        self.assertFalse(item["additionalProperties"])
        self.assertEqual(
            set(item["required"]),
            {
                "candidate_id", "ai_summary", "scope", "scope_evidence",
                "subjects", "location_mentions", "topic_mentions", "event_relation",
            },
        )
        for token in ("national", "hainan", "mixed", "不得猜测", "原文证据"):
            self.assertIn(token, prompt)

    def test_controlled_catalogs_have_unique_ids_and_exact_fields(self):
        topics = json.loads((ROOT / "config/topics.json").read_text(encoding="utf-8"))
        self.assertEqual(set(topics), {"schema_version", "topics"})
        self.assertEqual(topics["schema_version"], 1)
        ids = [item["topic_id"] for item in topics["topics"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(set(item) == {"topic_id", "name", "aliases"} for item in topics["topics"]))
        sections = json.loads((ROOT / "config/page-sections.json").read_text(encoding="utf-8"))
        self.assertEqual(set(sections), {"schema_version", "sections", "rules", "fallback"})
        self.assertEqual(sections["fallback"], "source_page_name")
        subjects = json.loads((ROOT / "config/subjects.json").read_text(encoding="utf-8"))
        self.assertEqual(subjects, {"schema_version": 1, "subjects": []})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the asset tests and verify they fail**

Run:

```bash
python3 -m unittest tests.test_hnhot_assets -v
```

Expected: FAIL because the prompt and config assets do not exist.

- [ ] **Step 3: Add the manifest and controlled catalogs**

Create `prompts/article-enrichment/v1/manifest.json`:

```json
{
  "schema_version": 1,
  "prompt_version": "hnhot-v1",
  "article_schema_version": 7,
  "prompt": "prompt.md",
  "output_schema": "schema.json"
}
```

Create `config/topics.json` with this initial closed catalog:

```json
{
  "schema_version": 1,
  "topics": [
    {"topic_id": "policy-governance", "name": "政策治理", "aliases": ["政策", "政务", "治理"]},
    {"topic_id": "industry-projects", "name": "产业项目", "aliases": ["产业", "项目", "招商"]},
    {"topic_id": "economy-data", "name": "经济数据", "aliases": ["经济", "统计", "消费"]},
    {"topic_id": "livelihood-services", "name": "民生服务", "aliases": ["民生", "公共服务", "办事"]},
    {"topic_id": "urban-rural", "name": "城乡建设", "aliases": ["城市", "乡村振兴", "基础设施"]},
    {"topic_id": "ecology", "name": "生态环境", "aliases": ["生态", "环保", "自然资源"]},
    {"topic_id": "culture-tourism-sports", "name": "文旅体育", "aliases": ["文化", "旅游", "体育"]},
    {"topic_id": "education-talent", "name": "教育人才", "aliases": ["教育", "人才", "就业"]},
    {"topic_id": "health", "name": "医疗健康", "aliases": ["医疗", "健康", "卫生"]},
    {"topic_id": "external-relations", "name": "对外交流", "aliases": ["外事", "国际", "区域合作"]}
  ]
}
```

Create `config/page-sections.json`:

```json
{
  "schema_version": 1,
  "sections": [
    {"section_id": "front-page", "name": "头版"},
    {"section_id": "hainan-news", "name": "本省新闻"},
    {"section_id": "domestic-international", "name": "国内国际"},
    {"section_id": "theory", "name": "理论周刊"}
  ],
  "rules": [
    {"source_page_name": "头版", "section_id": "front-page"},
    {"source_page_name": "本省新闻", "section_id": "hainan-news"},
    {"source_page_name": "国内新闻", "section_id": "domestic-international"},
    {"source_page_name": "国际新闻", "section_id": "domestic-international"},
    {"source_page_name": "理论周刊", "section_id": "theory"}
  ],
  "fallback": "source_page_name"
}
```

Create `config/subjects.json`:

```json
{
  "schema_version": 1,
  "subjects": []
}
```

- [ ] **Step 4: Add the strict output schema**

Create `prompts/article-enrichment/v1/schema.json` as Draft 2020-12 with this exact root and definitions:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://hnhot.local/schema/article-enrichment-v1.json",
  "type": "object",
  "additionalProperties": false,
  "required": ["schema_version", "prompt_version", "input_fingerprint", "items"],
  "properties": {
    "schema_version": {"const": 7},
    "prompt_version": {"const": "hnhot-v1"},
    "input_fingerprint": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
    "items": {"type": "array", "items": {"$ref": "#/$defs/item"}}
  },
  "$defs": {
    "evidence": {"type": "string", "minLength": 1, "maxLength": 240},
    "subject": {
      "type": "object",
      "additionalProperties": false,
      "required": ["name", "type", "role", "evidence"],
      "properties": {
        "name": {"type": "string", "minLength": 1, "maxLength": 80},
        "type": {"enum": ["person", "government", "organization", "company", "project"]},
        "role": {"type": ["string", "null"], "maxLength": 80},
        "evidence": {"$ref": "#/$defs/evidence"}
      }
    },
    "location": {
      "type": "object",
      "additionalProperties": false,
      "required": ["location_id", "evidence"],
      "properties": {
        "location_id": {"type": "string", "minLength": 1, "maxLength": 80},
        "evidence": {"$ref": "#/$defs/evidence"}
      }
    },
    "topic": {
      "type": "object",
      "additionalProperties": false,
      "required": ["topic_id", "evidence"],
      "properties": {
        "topic_id": {"type": "string", "minLength": 1, "maxLength": 80},
        "evidence": {"$ref": "#/$defs/evidence"}
      }
    },
    "event_relation": {
      "oneOf": [
        {
          "type": "object", "additionalProperties": false,
          "required": ["relation", "event_id", "event_name", "evidence", "update_summary"],
          "properties": {
            "relation": {"const": "existing"},
            "event_id": {"type": "string", "minLength": 1},
            "event_name": {"type": "null"},
            "evidence": {"$ref": "#/$defs/evidence"},
            "update_summary": {"type": "string", "minLength": 1, "maxLength": 180}
          }
        },
        {
          "type": "object", "additionalProperties": false,
          "required": ["relation", "event_id", "event_name", "evidence", "update_summary"],
          "properties": {
            "relation": {"const": "new"},
            "event_id": {"type": "null"},
            "event_name": {"type": "string", "minLength": 1, "maxLength": 120},
            "evidence": {"$ref": "#/$defs/evidence"},
            "update_summary": {"type": "string", "minLength": 1, "maxLength": 180}
          }
        },
        {
          "type": "object", "additionalProperties": false,
          "required": ["relation", "event_id", "event_name", "evidence", "update_summary"],
          "properties": {
            "relation": {"const": "none"},
            "event_id": {"type": "null"},
            "event_name": {"type": "null"},
            "evidence": {"type": "null"},
            "update_summary": {"type": "null"}
          }
        }
      ]
    },
    "item": {
      "type": "object",
      "additionalProperties": false,
      "required": ["candidate_id", "ai_summary", "scope", "scope_evidence", "subjects", "location_mentions", "topic_mentions", "event_relation"],
      "properties": {
        "candidate_id": {"type": "string", "minLength": 1},
        "ai_summary": {"type": ["string", "null"], "maxLength": 300},
        "scope": {"enum": ["national", "hainan", "mixed"]},
        "scope_evidence": {"$ref": "#/$defs/evidence"},
        "subjects": {"type": "array", "maxItems": 8, "items": {"$ref": "#/$defs/subject"}},
        "location_mentions": {"type": "array", "maxItems": 5, "items": {"$ref": "#/$defs/location"}},
        "topic_mentions": {"type": "array", "maxItems": 5, "items": {"$ref": "#/$defs/topic"}},
        "event_relation": {"$ref": "#/$defs/event_relation"}
      }
    }
  }
}
```

- [ ] **Step 5: Add the source-grounded prompt**

Create `prompts/article-enrichment/v1/prompt.md` with these normative sections and field rules:

```markdown
# HNHOT article enrichment prompt v1

## Role

You enrich every valid Hainan Daily article for long-term retrieval. The
newspaper editor has already decided what to publish. Do not score, select,
recommend, rank, discard or rewrite the source as commentary.

## Input boundary

Use only each item's title, full article content, `location_candidates`,
`topic_candidates` and `event_candidates`. Never use outside knowledge to
complete a missing fact. Every semantic decision must be grounded in 原文证据.

## Output boundary

Return one JSON object that conforms exactly to `schema.json`. Preserve the
input item order and candidate IDs. Do not add URLs, source metadata, scores,
recommendation reasons, final IDs or extra keys. 不得猜测; when an event cannot
be linked safely, return relation `none`.

## Summary

Write one factual `ai_summary`, normally 1–3 Chinese sentences. Remove meeting
ritual, slogans, empty praise and repeated background. Preserve concrete
actions, places, dates, numbers, policy changes, project progress and next
steps. If the body is missing, return `null`; never infer a summary from the
headline alone.

## N/H/M scope

- `national` (N): nationwide actor/action with no direct Hainan action or effect.
- `hainan` (H): the main event, action or governance object occurs in Hainan.
- `mixed` (M): a national/international context has a directly citable Hainan
  person, institution, company, project, competition or activity connection.

Apply precedence: mixed first, then hainan, then national. Copy a short
`scope_evidence` excerpt from the title or body.

## Subjects, locations and topics

Extract stable subjects only: person, government, organization, company or
project. Preserve the source name and evidence; use `role: null` when absent.
Choose locations only from `location_candidates` and topics only from
`topic_candidates`. Return empty arrays when the source does not support a
choice.

## Event relation

Choose `existing` only when one supplied event candidate is clearly the same
continuing matter. Choose `new` for a distinct event that can accumulate future
coverage. Choose `none` for commentary, weak similarity or insufficient facts.
For existing/new events, describe only the new development in `update_summary`
and copy a supporting evidence excerpt.
```

- [ ] **Step 6: Run asset validation**

Run:

```bash
python3 -m unittest tests.test_hnhot_assets -v
python3 -m json.tool prompts/article-enrichment/v1/schema.json >/dev/null
python3 -m json.tool prompts/article-enrichment/v1/manifest.json >/dev/null
python3 -m json.tool config/topics.json >/dev/null
python3 -m json.tool config/page-sections.json >/dev/null
python3 -m json.tool config/subjects.json >/dev/null
```

Expected: 2 tests PASS and all JSON commands exit 0.

- [ ] **Step 7: Commit the versioned assets**

```bash
git add prompts/article-enrichment/v1 config tests/test_hnhot_assets.py
git commit -m "feat: version HNHOT enrichment contract assets"
```

---

### Task 4: Document and enforce the self-contained repository boundary

**Files:**
- Modify: `README.md`
- Create: `tests/test_repository_boundary.py`

**Interfaces:**
- Produces: one README workflow from local crawl to the existing two-pass build.
- Enforces: active runtime files contain no `HNDAILY_SKILL_DIR`, absolute adjacent-repository path or runtime import of `hndaily-skill`.

- [ ] **Step 1: Write the repository-boundary test**

Create `tests/test_repository_boundary.py`:

```python
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class RepositoryBoundaryTests(unittest.TestCase):
    def test_active_runtime_has_no_external_crawler_dependency(self):
        runtime_files = [
            ROOT / "scripts/run_radar_pipeline.sh",
            ROOT / "scripts/crawler.py",
            ROOT / ".env.example",
        ]
        forbidden = (
            "HNDAILY_SKILL_DIR",
            "/Users/skr/Work/hndaily/hndaily-skill",
            "../hndaily-skill",
        )
        for path in runtime_files:
            text = path.read_text(encoding="utf-8")
            for value in forbidden:
                self.assertNotIn(value, text, f"{path}: {value}")

    def test_readme_names_canonical_json_outputs(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for value in (
            "HNHOT",
            "scripts/crawler.py",
            "data/json/raw/",
            "data/json/model-input/",
            "data/json/model-output/",
            "data/json/audits/",
            "prompts/article-enrichment/v1/",
        ):
            self.assertIn(value, readme)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the boundary test and verify README expectations fail**

Run:

```bash
python3 -m unittest tests.test_repository_boundary -v
```

Expected: the runtime boundary passes after Tasks 1–2, while the README test FAILS because the current README still names the old product and scheduled-job dependency.

- [ ] **Step 3: Rewrite the README project boundary and workflow**

Replace the opening and scheduled-job sections of `README.md` so they contain these exact operational commands and path explanations:

````markdown
# HNHOT

HNHOT 放大海南日报编辑已经做出的专业判断，并把每日报道加工为可检索、可关联、可长期积累的海南认知资料。它不是第二套新闻精选系统，也不依赖仓库外的抓取技能。

## Self-contained daily workflow

抓取指定日期或最新一期：

```bash
python3 scripts/crawler.py 2026-07-18
python3 scripts/crawler.py
```

原始抓取写入 `data/json/raw/`。运行当前两阶段发布流水线：

```bash
bash scripts/run_radar_pipeline.sh YYYY-MM-DD
```

首次运行返回 `STATUS=MODEL_OUTPUT_REQUIRED`。按照命令打印的
`MODEL_INPUT_JSON` 生成 `MODEL_OUTPUT_JSON` 后重跑；成功返回
`STATUS=COMPLETE`。

项目内私有 JSON 分别位于：

- `data/json/raw/`
- `data/json/model-input/`
- `data/json/model-output/`
- `data/json/audits/`

HNHOT 下一版结构化提示词和严格输出契约位于
`prompts/article-enrichment/v1/`。当前公开 schema 的切换由后续实施阶段完成。
````

保留当前仍有效的预览命令、公开路由和已验证数据说明，但删除“从 `HNDAILY_SKILL_DIR` 运行抓取器”以及“原始抓取必须位于仓库外”的陈述。明确生成的私有 JSON 在仓库目录内、被 Git 忽略，公开数据仍位于 `content/`。

- [ ] **Step 4: Run boundary and documentation tests**

Run:

```bash
python3 -m unittest tests.test_repository_boundary -v
```

Expected: 2 tests PASS.

- [ ] **Step 5: Commit the repository boundary documentation**

```bash
git add README.md tests/test_repository_boundary.py
git commit -m "docs: define self-contained HNHOT workflow"
```

---

### Task 5: Run phase-one acceptance and record the clean boundary

**Files:**
- Modify only if a verification failure exposes a defect in a file owned by Tasks 1–4.

**Interfaces:**
- Consumes: all phase-one files and the unchanged current public-content pipeline.
- Produces: a verified, self-contained data foundation with no public schema or route regression.

- [ ] **Step 1: Run focused phase-one tests**

Run:

```bash
python3 -m unittest \
  tests.test_crawler \
  tests.test_hnhot_assets \
  tests.test_repository_boundary \
  tests.test_radar_pipeline_cli -v
```

Expected: all focused tests PASS.

- [ ] **Step 2: Run the complete unit suite**

Run:

```bash
python3 -m unittest discover -s tests -v
```

Expected: all tests PASS. Do not weaken existing scoring or rendering tests in this phase because the public schema is intentionally unchanged.

- [ ] **Step 3: Build the current static site and validate internal links**

Run:

```bash
python3 scripts/radar_render.py content site
python3 -c 'from pathlib import Path; from scripts.radar_render import validate_internal_links; errors = validate_internal_links(Path("site")); print(errors); raise SystemExit(bool(errors))'
```

Expected: both commands exit 0 and the link validator prints `[]`.

- [ ] **Step 4: Verify the tracked diff contains no generated private JSON**

Run:

```bash
git status --short
git ls-files 'data/json/*' 'data/json/**/*'
```

Expected: `git status` contains no files under `data/json/raw`, `model-input`, `model-output` or `audits`; `git ls-files` lists only `data/json/README.md` under that tree.

- [ ] **Step 5: Verify external-dependency strings are absent from runtime files**

Run:

```bash
rg -n "HNDAILY_SKILL_DIR|/Users/skr/Work/hndaily/hndaily-skill|\.\./hndaily-skill" scripts .env.example
```

Expected: no matches; `rg` exits 1.

- [ ] **Step 6: Commit any verification-only correction**

If Steps 1–5 required a correction, stage only the defect-related files and commit:

```bash
git add \
  .env.example .gitignore README.md data/json/README.md \
  scripts/crawler.py scripts/run_radar_pipeline.sh \
  prompts/article-enrichment/v1 config/topics.json \
  config/page-sections.json config/subjects.json \
  tests/test_crawler.py tests/test_hnhot_assets.py \
  tests/test_repository_boundary.py tests/test_radar_pipeline_cli.py \
  tests/fixtures/crawler/front-page.html tests/fixtures/crawler/article.html
git diff --cached --quiet || git commit -m "fix: close HNHOT data foundation acceptance gap"
```

If no correction was needed, do not create an empty commit.
