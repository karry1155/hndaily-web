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
