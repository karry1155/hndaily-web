# HNHOT

HNHOT 放大海南日报编辑已经做出的专业判断，并把每日报道加工为可检索、可关联、可长期积累的海南认知资料。它不是第二套新闻精选系统，也不依赖仓库外的抓取技能。

## Daily workflow

抓取指定日期或最新一期：

```bash
python3 scripts/crawler.py 2026-07-12
python3 scripts/crawler.py
```

原始抓取写入 `data/production-json/source/`。运行两阶段发布流水线：

```bash
bash scripts/run_radar_pipeline.sh YYYY-MM-DD
```

首次运行返回 `STATUS=MODEL_OUTPUT_REQUIRED`。按照命令打印的
`MODEL_INPUT_JSON` 和 `prompts/article-enrichment/v3/` 生成
`MODEL_OUTPUT_JSON` 后重跑。已知主题会自动归一；遇到新主题时返回
`STATUS=TOPIC_RESOLUTION_REQUIRED`，按照打印的 `TOPIC_RESOLUTION_INPUT_JSON`
和 `prompts/topic-resolution/v1/` 生成归一结果后再次运行；成功返回
`STATUS=COMPLETE`。

当前生产 JSON 位于独立审查目录：

- `data/production-json/source/`：海南日报原始抓取。
- `data/production-json/input/`：逐篇语义处理输入。
- `data/production-json/enrichment/`：智能体生成并待审查的 v3 结果。
- `data/production-json/topic-resolution-input/`：开放主题的归一输入。
- `data/production-json/topic-resolution/`：稳定主题 ID 的审核结果。
- `data/production-json/audit/`：预过滤与发布审计。

`data/json/` 保留此前各版本生成的私有数据，只读留档；当前流水线不会再向其中写入或覆盖文件。

当前运行时契约为 `schema_version: 9` / `prompt_version: hnhot-v3.0`。v3 自由提取本篇的核心主题和少量次级主题，并把文章体裁独立记录为 `content_form`；第一次入库不再接收 `topic_candidates`，也不生成长期主题 ID。后续主题归一阶段将开放名称映射到带定义、边界和稳定 ID 的主题树，无法准确映射时停止发布并要求建立新叶子节点。发布流程保留每一篇通过确定性过滤的有效报道，不评分、不推荐、不二次精选。

## Public data

通过契约验证的数据写入：

- `content/issues/YYYY-MM-DD.json`：整期版面、逻辑栏目与文章顺序。
- `content/issue-items/YYYY-MM-DD/ITEM_ID.json`：文章原文与结构化加工结果。
- `content/indexes/`：头版、全报、搜索和主题页所需的精简索引。
- `content/topics/catalog.json`：长期稳定的主题目录、别名和边界定义。

生产与历史私有 JSON 均被 Git 忽略；`content/` 保存通过版本化契约验证的公开数据。当前仓库内已验证的数据集为 2026-07-19 至 2026-07-20，共 70 篇有效报道；两天数据均已迁移到 v9 开放主题契约。正文以“上接A0X版”开头的跨版续接块会在预过滤阶段排除，不会作为独立报道重复入库。头版首页按日期倒序连续展示，可向下回看往期头版。

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
- `/review/gold/`：仅本地开放的文章语义人工基准工作台；可把审核结果直接保存到 `evaluation/gold/`。

## Verify

```bash
python3 -m unittest discover -s tests -v
```
