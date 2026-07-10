# 海南日报精读网页

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
python3 scripts/preview.py
```

Open `http://127.0.0.1:8765`.

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

Prepare the first three crawler articles for Codex:

```bash
bash scripts/run_daily_pipeline.sh
```

The command prints `RAW_JSON`, `MODEL_INPUT_JSON`, and `MODEL_OUTPUT_JSON`. The model input intentionally contains no URL or source object. Codex writes only semantic fields to the reported model-output path; `scripts/finalize_digest.py` then copies the canonical headline, page, and URL from the raw crawler JSON.

See [docs/codex-digest-generation.md](docs/codex-digest-generation.md) for the exact automation steps and output contract.
