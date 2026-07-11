# 海南日报精读网页

新版产品为“海南信息雷达”：来源无关、按日持久化、无精选数量上限，并提供全部、分类、日期与详情路由。

Radar 流水线先运行 `bash scripts/run_radar_pipeline.sh YYYY-MM-DD`。首次返回退出码 2 和 `STATUS=MODEL_OUTPUT_REQUIRED`；按操作文档写入精确模型输出后重跑，成功返回 `STATUS=COMPLETE`。随后运行 `python3 -m scripts.preview`，访问 <http://127.0.0.1:8765>。

## Verified datasets

- 2026-07-08：8 版、35 篇原始文章、20 篇入选。
- 2026-07-09：7 版、28 篇原始文章、17 篇入选；由 2026-07-10 的真实抓取独立生成，未复用 7 月 8 日模型输出。
- 验证命令：`RADAR_REAL_DATA_REQUIRED=1 python3 -m unittest discover -s tests -v`。
- 验证日期：2026-07-10。

这个目录是未来同步到云端的网页项目。它负责展示本地定时任务生成好的海南日报精读内容，包括每日 5 分钟日报和每周 15 分钟周报。

## 项目边界

- 入库：网页源码、配置模板、设计与实现文档、可发布的静态内容结构。
- 不入库：抓取原始数据、中间处理文件、缓存、PDF、音频、日志、本地环境变量。
- 数据流：本地定时任务抓取并生成日报/周报产物，再把可发布产物同步到云端。

## 当前状态

项目已初始化为独立 git 仓库。正式实现前先完成实施计划。

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

原始抓取、预过滤和评分审计仍保存在忽略的本地目录；公开站点只发布精选内容与精简后的完整读报数据。

## Scheduled Job Boundary

The future scheduled job should:

1. Run the crawler from `HNDAILY_SKILL_DIR`.
2. Store raw crawler output under ignored local data directories.
3. Generate publishable daily digest JSON under `content/daily/`.
4. Validate the digest with `scripts/validate_digest.py`.
5. Render `site/` with `scripts/render_site.py`.
6. Sync `site/` or the chosen publishable output to the cloud host.

Raw files, temporary files, logs, PDFs, audio, and caches must remain outside git.

## Codex Digest Pipeline

Prepare every article for deterministic filtering and the full set of eligible candidates for Codex:

```bash
bash scripts/run_daily_pipeline.sh
```

The command prints `RAW_JSON`, `MODEL_INPUT_JSON`, `MODEL_OUTPUT_JSON`, `PREFILTER_JSON`, and `EDITORIAL_AUDIT_JSON`. Every raw article appears in the prefilter audit. The model input contains no URL or source object and includes every candidate that passes the high-confidence filters. Codex writes semantic fields and five 0–10 integer scores to the reported model-output path; code then computes final scores, deduplicates events, applies `hainan_relevance >= 6` and `final_score >= 65`, and publishes at most eight items without padding.

See [docs/codex-digest-generation.md](docs/codex-digest-generation.md) for the exact automation steps and output contract.
