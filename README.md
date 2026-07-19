# HNHOT

HNHOT 放大海南日报编辑已经做出的专业判断，并把每日报道加工为可检索、可关联、可长期积累的海南认知资料。它不是第二套新闻精选系统，也不依赖仓库外的抓取技能。

## Daily workflow

抓取指定日期或最新一期：

```bash
python3 scripts/crawler.py 2026-07-12
python3 scripts/crawler.py
```

原始抓取写入 `data/json/raw/`。运行两阶段发布流水线：

```bash
bash scripts/run_radar_pipeline.sh YYYY-MM-DD
```

首次运行返回 `STATUS=MODEL_OUTPUT_REQUIRED`。按照命令打印的
`MODEL_INPUT_JSON` 和 `prompts/article-enrichment/v1/` 生成
`MODEL_OUTPUT_JSON` 后重跑；成功返回 `STATUS=COMPLETE`。

私有流水线 JSON 位于：

- `data/json/raw/`
- `data/json/model-input/`
- `data/json/model-output/`
- `data/json/audits/`

运行时契约为 `schema_version: 7` / `prompt_version: hnhot-v1`。发布流程保留每一篇通过确定性过滤的有效报道，不评分、不推荐、不二次精选。

## Public data

通过契约验证的数据写入：

- `content/issues/YYYY-MM-DD.json`：整期版面、逻辑栏目与文章顺序。
- `content/issue-items/YYYY-MM-DD/ITEM_ID.json`：文章原文与结构化加工结果。
- `content/indexes/`：头版、全报和搜索所需的精简索引。

私有 JSON 被 Git 忽略；`content/` 只保存通过 `hnhot-v1` 验证的公开数据。当前仓库内已验证的数据集为 2026-07-12 至 2026-07-19：共 71 版、307 篇有效报道，其中头版 59 篇。正文以“上接A0X版”开头的跨版续接块会在预过滤阶段排除，不会作为独立报道重复入库。头版首页按日期倒序连续展示，可向下回看往期头版。

文章身份采用可重放的来源键：常规海南日报链接生成
`hndaily-{YYYYMMDD}-{URL第一段编号}-{URL第二段编号}`，例如
`hndaily-20260712-58464-19696008`。无法解析编号时使用规范化原文链接的
SHA-256 前 16 位作为回退。发布前会在完整历史数据中同时检查 `item_id`
和规范化原文链接，冲突时停止发布，不以抓取时间戳生成身份。

## Build and preview

```bash
python3 scripts/radar_render.py content site
python3 -m scripts.preview
```

本地访问 `http://127.0.0.1:8765`。主要路由：

- `/`：海南日报当日头版与世界新闻信息池，提供 N/H/D/M/F 范围分类和国内、全球排行榜。
- `/all/`、`/all/YYYY-MM-DD/`：按逻辑版面阅读整期报纸。
- `/items/YYYY-MM-DD/ITEM_ID/`：文章详情与结构化摘要。
- `/daily/`、`/more/`：当前产品导航中的后续能力入口。

## Verify

```bash
python3 -m unittest discover -s tests -v
```
