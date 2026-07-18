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

## Verified datasets

- 2026-07-08：8 版、35 篇原始文章、20 篇入选。
- 2026-07-09：7 版、28 篇原始文章、17 篇入选；由 2026-07-10 的真实抓取独立生成，未复用 7 月 8 日模型输出。
- 验证命令：`RADAR_REAL_DATA_REQUIRED=1 python3 -m unittest discover -s tests -v`。
- 验证日期：2026-07-10。

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
python3 -m scripts.preview
```

Open `http://127.0.0.1:8765`.

## Public Routes

- `/`：精选、分类、搜索、当下重点和按日期排列的精选标题。
- `/all/`：最新一期完整读报。
- `/all/YYYY-MM-DD/`：按原报版面浏览所有参与 AI 评分的文章，并访问原版 HTML 与 PDF。
- `/daily/`：AI 日报。
- `/about/`、`/changelog/`：关于与更新日志。

生成的私有 JSON 位于本仓库目录内且被 Git 忽略；公开数据仍位于 `content/`。公开站点只发布精选内容与精简后的完整读报数据。

## Codex Digest Pipeline

Prepare every article for deterministic filtering and the full set of eligible candidates for Codex:

```bash
bash scripts/run_daily_pipeline.sh
```

The command prints `RAW_JSON`, `MODEL_INPUT_JSON`, `MODEL_OUTPUT_JSON`, `PREFILTER_JSON`, and `EDITORIAL_AUDIT_JSON`. Every raw article appears in the prefilter audit. The model input contains no URL or source object and includes every candidate that passes the high-confidence filters. Codex writes semantic fields and five 0–10 integer scores to the reported model-output path; code then computes final scores, deduplicates events, applies `hainan_relevance >= 6` and `final_score >= 65`, and publishes at most eight items without padding.

See [docs/codex-digest-generation.md](docs/codex-digest-generation.md) for the exact automation steps and output contract.
