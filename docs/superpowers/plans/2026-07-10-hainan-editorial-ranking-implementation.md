# 海南日报编辑精选 V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把整份《海南日报》经过高置信过滤、模型五维评分、代码最终分、轻量去重和双资格线选择，生成最多 8 篇且主页前 4 篇突出的可用日报。

**Architecture:** `prepare_model_input.py` 调用纯函数过滤模块评估全部原始文章并生成全量候选；`finalize_digest.py` 严格校验模型语义结果，依次调用评分、去重和选择模块。正式日报只发布最多 8 个事件，完整文章级决策保存在审计 sidecar，渲染器把同一排名切成 Top 4 与其余值得看。

**Tech Stack:** Python 3 标准库、`unittest`、`string.Template`、Shell。

## Global Constraints

- V1 只实现高置信硬过滤、全量候选、五维评分、代码最终分、`hainan_relevance >= 6`、轻量去重、`final_score >= 65`、最多 8 篇、主页 Top 4 和真实分类。
- 不强制补足 5 篇；不实现分类配额、复杂聚类、七天完整指标、全参数配置文件或全站原子发布。
- 模型不得返回 `final_score`、`selected` 或 `rank`，不得返回 URL 或来源字段。
- 所有语义内容只能来自《海南日报》正文，不搜索外部资料。
- 不修改 `hndaily-skill` 抓取器，不覆盖 `hndaily-skill/_data/`。
- 所有新增代码只使用 Python 标准库；JSON 输出采用同目录临时文件加 `Path.replace()`。
- 不部署、不推送、不创建 PR。

---

### Task 1: 高置信过滤与全量模型输入

**Files:**
- Create: `scripts/editorial_filter.py`
- Modify: `scripts/prepare_model_input.py`
- Modify: `scripts/run_daily_pipeline.sh`
- Create: `tests/test_editorial_filter.py`
- Modify: `tests/test_prepare_model_input.py`
- Modify: `tests/test_pipeline_cli.py`

**Interfaces:**
- Produces: `evaluate_issue(raw: dict[str, Any]) -> list[dict[str, Any]]`
- Produces: `build_model_input(raw) -> tuple[dict[str, Any], dict[str, Any]]`，依次返回 model input 与 prefilter audit。
- Produces: pipeline stdout 的 `PREFILTER_JSON` 与 `EDITORIAL_AUDIT_JSON` 路径。

- [ ] **Step 1: 写过滤失败测试**

测试构造包含正常文章、导读、理论周刊、公益广告、空正文、抓取错误、短讯和会议标题的原始 issue，断言每篇都有记录，前三类与错误有稳定 `skip_reason`，短讯和会议标题仍通过。

```python
records = evaluate_issue(raw)
self.assertEqual(len(records), raw["article_count"])
self.assertEqual(by_title["导读"]["skip_reason"], "guide")
self.assertEqual(by_title["理论文章"]["skip_reason"], "theory_weekly")
self.assertEqual(by_title["公益广告内容"]["skip_reason"], "public_service_ad_page")
self.assertEqual(by_title["短讯"]["length_band"], "under_200")
self.assertTrue(by_title["工作会议召开"]["passed"])
```

- [ ] **Step 2: 运行过滤测试确认 RED**

Run: `python3 -m unittest tests.test_editorial_filter -v`

Expected: FAIL，`scripts.editorial_filter` 尚不存在。

- [ ] **Step 3: 实现最小过滤模块**

实现 `flatten_articles()` 的结构/数量校验、稳定 `A001` ID、`content_length`、`length_band`，并按 `fetch_error`、`empty_content`、`guide`、`public_service_ad_page`、`theory_weekly` 顺序设置结果。每个记录保留 `page`、`page_name`、`seq`、`original_title`、`url`、`author`、`content`。

- [ ] **Step 4: 运行过滤测试确认 GREEN**

Run: `python3 -m unittest tests.test_editorial_filter -v`

Expected: 全部 PASS。

- [ ] **Step 5: 写全量输入失败测试**

更新测试 API，断言 4 篇正常文章全部进入模型输入而不是前三篇；模型 item 只含 `candidate_id`、`original_title`、`content`、`length_band`；prefilter 审计含全部文章；2026-07-08 真实样本共有 35 条过滤记录且“海南能用住房公积金交物业费了”进入候选。

```python
model_input, audit = build_model_input(raw_issue())
self.assertEqual(len(model_input["items"]), 4)
self.assertEqual(len(audit["items"]), 4)
self.assertEqual(set(model_input["items"][0]), {
    "candidate_id", "original_title", "content", "length_band"
})
```

- [ ] **Step 6: 运行输入测试确认 RED**

Run: `python3 -m unittest tests.test_prepare_model_input -v`

Expected: FAIL，旧 API 仍返回单个三篇输入。

- [ ] **Step 7: 实现全量输入和原子 prefilter 输出**

把 schema/prompt 升为 `2` / `editorial-v1`；删除 `limit` 和 `select_articles()`；CLI 改为 `prepare_model_input.py RAW_JSON MODEL_INPUT_JSON PREFILTER_JSON`，两个结果均原子写入。指纹覆盖全部通过候选。

- [ ] **Step 8: 更新 pipeline 路径并验证 GREEN**

`run_daily_pipeline.sh` 新增 `.prefilter.json` 和 `.editorial-audit.json` 路径并输出四个路径；更新 CLI 测试。

Run: `python3 -m unittest tests.test_editorial_filter tests.test_prepare_model_input tests.test_pipeline_cli -v`

Expected: 全部 PASS。

- [ ] **Step 9: 提交 Task 1**

```bash
git add scripts/editorial_filter.py scripts/prepare_model_input.py scripts/run_daily_pipeline.sh tests/test_editorial_filter.py tests/test_prepare_model_input.py tests/test_pipeline_cli.py
git commit -m "feat: prepare all editorial candidates"
```

### Task 2: 模型五维契约与确定性评分

**Files:**
- Create: `scripts/editorial_scoring.py`
- Create: `tests/test_editorial_scoring.py`
- Modify: `scripts/finalize_digest.py`
- Modify: `tests/test_finalize_digest.py`

**Interfaces:**
- Produces: `validate_semantic_item(item: dict[str, Any], location: str) -> None`
- Produces: `score_candidate(candidate: dict[str, Any], semantic: dict[str, Any]) -> dict[str, Any]`
- Consumes: Task 1 的候选记录与 `editorial-v1` model input。

- [ ] **Step 1: 写评分失败测试**

手算 `{8, 8, 6, 4, 8}` 的基础分为 `70.0`，断言头版 `+4`、本省新闻 `+3`、少于 200 字 `-8`，并保存逐项解释；全国转载且无海南指向时不应用正向版面分。

```python
result = score_candidate(candidate, semantic_scores)
self.assertEqual(result["base_score"], 70.0)
self.assertEqual(result["final_score"], 69.0)
self.assertEqual([x["points"] for x in result["adjustments"]], [4, 3, -8])
```

- [ ] **Step 2: 运行评分测试确认 RED**

Run: `python3 -m unittest tests.test_editorial_scoring -v`

Expected: FAIL，评分模块尚不存在。

- [ ] **Step 3: 实现最小评分模块**

集中定义五维字段、Decimal 权重、版面和长度调整。严格拒绝 bool、非整数和 0–10 外分数。返回 `semantic_scores`、`score_reasons`、`base_score`、`adjustments`、`final_score` 和可读 `score_explanation`。

- [ ] **Step 4: 运行评分测试确认 GREEN**

Run: `python3 -m unittest tests.test_editorial_scoring -v`

Expected: 全部 PASS。

- [ ] **Step 5: 写模型契约失败测试**

把模型 item 扩展为 `suggested_category`、五个评分和五个 `score_reasons`。测试未知分类、越界、浮点、缺维度、`final_score` 越权字段、ID/数量/顺序/指纹不匹配全部失败。

- [ ] **Step 6: 运行 finalize 契约测试确认 RED**

Run: `python3 -m unittest tests.test_finalize_digest -v`

Expected: FAIL，旧契约拒绝新字段或接受旧字段。

- [ ] **Step 7: 更新严格模型验证并确认 GREEN**

`finalize_digest.py` 的字段集合只允许 V1 语义字段；分类只能是固定集合中除“已跳过”外的值；逐条调用评分模块的验证函数。

Run: `python3 -m unittest tests.test_editorial_scoring tests.test_finalize_digest -v`

Expected: 全部 PASS。

- [ ] **Step 8: 提交 Task 2**

```bash
git add scripts/editorial_scoring.py scripts/finalize_digest.py tests/test_editorial_scoring.py tests/test_finalize_digest.py
git commit -m "feat: validate and score editorial semantics"
```

### Task 3: 轻量事件去重与双资格线选择

**Files:**
- Create: `scripts/event_clustering.py`
- Create: `scripts/select_digest.py`
- Create: `tests/test_event_clustering.py`
- Create: `tests/test_select_digest.py`

**Interfaces:**
- Produces: `cluster_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]`
- Produces: `select_events(events: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]`，返回 selected 与全部带决策事件。
- Consumes: Task 2 的 scored candidate。

- [ ] **Step 1: 写去重失败测试**

断言规范化标题相同会合并；高相似正文开头的头版短讯与长文会合并；“启动计划”和“总结计划”这类低相似事件不合并；主条目优先信息密度、正文长度、最终分；来源全部保留且 event ID 稳定。

- [ ] **Step 2: 运行去重测试确认 RED**

Run: `python3 -m unittest tests.test_event_clustering -v`

Expected: FAIL，模块尚不存在。

- [ ] **Step 3: 实现保守轻量去重**

实现 `normalize_text()`、`ngrams()`、Jaccard，相同标题直接合并；否则标题二元或正文前 500 字三元相似度达到集中阈值才合并。按候选 ID 顺序构建事件，主条目按信息密度、正文长度、最终分、版面、seq、ID 选择。

- [ ] **Step 4: 运行去重测试确认 GREEN**

Run: `python3 -m unittest tests.test_event_clustering -v`

Expected: 全部 PASS。

- [ ] **Step 5: 写选择失败测试**

构造 10 个事件，覆盖海南相关性 5/6、最终分 64/65、稳定同分排序、最多 8 篇、不补齐。断言未选原因分别为 `below_hainan_relevance`、`below_final_score`、`daily_limit`、`duplicate_event`。

- [ ] **Step 6: 运行选择测试确认 RED**

Run: `python3 -m unittest tests.test_select_digest -v`

Expected: FAIL，模块尚不存在。

- [ ] **Step 7: 实现选择并确认 GREEN**

集中定义 `HAINAN_RELEVANCE_THRESHOLD=6`、`FINAL_SCORE_THRESHOLD=65`、`MAX_SELECTED=8`、`TOP_COUNT=4`。排序键为最终分降序、信息密度降序、正文长度降序、版面升序、seq 升序、candidate ID 升序；只选双线合格的前 8 个并赋连续 rank。

Run: `python3 -m unittest tests.test_event_clustering tests.test_select_digest -v`

Expected: 全部 PASS。

- [ ] **Step 8: 提交 Task 3**

```bash
git add scripts/event_clustering.py scripts/select_digest.py tests/test_event_clustering.py tests/test_select_digest.py
git commit -m "feat: deduplicate and select editorial events"
```

### Task 4: 日报编排、完整审计与数据契约

**Files:**
- Modify: `scripts/finalize_digest.py`
- Modify: `scripts/validate_digest.py`
- Modify: `scripts/fixtures/daily-valid.json`
- Modify: `tests/test_finalize_digest.py`
- Modify: `tests/test_digest_contract.py`

**Interfaces:**
- Produces: `build_digest(raw, model_input, model_output) -> tuple[digest, audit]`
- Produces: `finalize_to_path(..., output_path, audit_path) -> tuple[digest, audit]`
- Consumes: Task 1–3 的过滤、评分、去重和选择接口。

- [ ] **Step 1: 写编排失败测试**

断言 build 阶段重建 model input 防止串批；把通过候选和语义输出合并评分；被过滤项目进入“已跳过”；选择项按真实分类写入分类桶；`top_items` 最多 4，`more_items` 为第 5–8；同事件来源合并；audit 对全部原始文章都有记录和未选原因。

- [ ] **Step 2: 运行编排测试确认 RED**

Run: `python3 -m unittest tests.test_finalize_digest tests.test_digest_contract -v`

Expected: FAIL，旧 build 仍依赖前三篇和单一列表。

- [ ] **Step 3: 实现 V1 编排**

重写 `build_digest` 依次调用过滤、严格语义验证、评分、去重、选择。正式 item 包含 rank、title、summary、category、why、facts、sources、confidence、event/master IDs、semantic/base/final score、adjustments、score explanation。分类桶复用正式 item 的精简副本；跳过项含来源和 skip reason。

- [ ] **Step 4: 扩展数据契约**

`validate_daily()` 要求 `top_items <= 4`、`more_items <= 4`、两者 rank 连续且总数等于 `selected_count <= 8`；检查双阈值元数据、评分字段、事件 ID 和真实分类；保留 weekly 逻辑。

- [ ] **Step 5: 实现双 JSON 原子写入并确认 GREEN**

CLI 改为 `finalize_digest.py RAW MODEL_INPUT MODEL_OUTPUT DIGEST_JSON AUDIT_JSON`。先在内存验证两个产物，再分别写临时文件，最后先替换 audit、再替换 digest。非法模型输出不得替换旧文件。

Run: `python3 -m unittest tests.test_finalize_digest tests.test_digest_contract -v`

Expected: 全部 PASS。

- [ ] **Step 6: 提交 Task 4**

```bash
git add scripts/finalize_digest.py scripts/validate_digest.py scripts/fixtures/daily-valid.json tests/test_finalize_digest.py tests/test_digest_contract.py
git commit -m "feat: finalize explainable daily digest"
```

### Task 5: Top 4 页面、其余值得看和流水线文档

**Files:**
- Modify: `scripts/render_site.py`
- Modify: `src/templates/daily.html`
- Modify: `src/static/styles.css`
- Modify: `scripts/run_daily_pipeline.sh`
- Modify: `README.md`
- Modify: `docs/data-contract.md`
- Modify: `docs/codex-digest-generation.md`
- Modify: `tests/test_digest_contract.py`
- Modify: `tests/test_pipeline_cli.py`

**Interfaces:**
- Consumes: Task 4 的 `top_items`、`more_items`、真实 categories。
- Produces: 静态 HTML 的“今日重点”和“今日还值得看”。

- [ ] **Step 1: 写渲染失败测试**

用 6 条 fixture 断言前 4 条只出现在“今日重点”，第 5–6 条只出现在“今日还值得看”，摘要/理由/事实/分类/来源均显示且转义；没有 more items 时显示如实空态，不复制重点条目。

- [ ] **Step 2: 运行渲染测试确认 RED**

Run: `python3 -m unittest tests.test_digest_contract -v`

Expected: FAIL，旧模板只有“今日看点”。

- [ ] **Step 3: 实现模板和样式最小改动**

抽取 `render_signal_cards()` 供两段列表复用；模板新增 `$more_signals` 和数量，标题改为“今日重点”，新增“今日还值得看” panel；沿用现有 card class，只增加必要间距/空态样式。

- [ ] **Step 4: 更新 pipeline 与文档**

文档说明 35 篇全量过滤、`editorial-v1` 精确模型字段、五维整数范围、未知分类失败、finalize 六参数、审计路径、双资格线和不补齐规则。pipeline 继续只准备交接路径，不伪造模型输出。

- [ ] **Step 5: 运行页面与 CLI 测试确认 GREEN**

Run: `python3 -m unittest tests.test_digest_contract tests.test_pipeline_cli -v`

Expected: 全部 PASS。

- [ ] **Step 6: 提交 Task 5**

```bash
git add scripts/render_site.py src/templates/daily.html src/static/styles.css scripts/run_daily_pipeline.sh README.md docs/data-contract.md docs/codex-digest-generation.md tests/test_digest_contract.py tests/test_pipeline_cli.py
git commit -m "feat: render ranked daily highlights"
```

### Task 6: 2026-07-08 真实样本闭环与最终验证

**Files:**
- Modify: `data/intermediate/2026-07-08.model-input.json`（ignored local artifact）
- Modify: `data/intermediate/2026-07-08.prefilter.json`（ignored local artifact）
- Modify: `data/intermediate/2026-07-08.model-output.json`（ignored local artifact）
- Modify: `data/intermediate/2026-07-08.editorial-audit.json`（ignored local artifact）
- Modify: `content/daily/2026-07-08.json`
- Regenerate: `site/`

**Interfaces:**
- Consumes: `/Users/skr/Work/hndaily/hndaily-skill/_data/2026-07-08.json`。
- Produces: 可验证日报、完整审计与静态网站。

- [ ] **Step 1: 运行全量准备**

```bash
HNDAILY_RAW_JSON=/Users/skr/Work/hndaily/hndaily-skill/_data/2026-07-08.json bash scripts/run_daily_pipeline.sh
```

Expected: prefilter 共有 35 条记录；模型输入包含全部通过硬过滤的候选；公积金文章存在。

- [ ] **Step 2: 基于正文生成严格模型输出**

逐项读取 model input，只从正文生成标题、摘要、理由、关键事实、建议分类、五维整数分和五维证据；原样复制 schema、prompt、fingerprint 与 candidate ID 顺序。不得使用代码计算或填入最终分。

- [ ] **Step 3: finalize、validate、render**

```bash
python3 scripts/finalize_digest.py \
  /Users/skr/Work/hndaily/hndaily-skill/_data/2026-07-08.json \
  data/intermediate/2026-07-08.model-input.json \
  data/intermediate/2026-07-08.model-output.json \
  content/daily/2026-07-08.json \
  data/intermediate/2026-07-08.editorial-audit.json
python3 scripts/validate_digest.py content/daily/2026-07-08.json
python3 scripts/render_site.py
```

Expected: 三个命令 exit 0；日报 0–8 篇、Top 4 来自同一排名、真实分类非空、同事件不重复。

- [ ] **Step 4: 运行完整测试与质量断言**

```bash
python3 -m unittest discover -s tests -v
python3 - <<'PY'
import json
raw = json.load(open('/Users/skr/Work/hndaily/hndaily-skill/_data/2026-07-08.json'))
prefilter = json.load(open('data/intermediate/2026-07-08.prefilter.json'))
digest = json.load(open('content/daily/2026-07-08.json'))
assert len(prefilter['items']) == raw['article_count'] == 35
assert any(x['original_title'] == '海南能用住房公积金交物业费了' and x['passed'] for x in prefilter['items'])
assert digest['selected_count'] == len(digest['top_items']) + len(digest['more_items']) <= 8
assert len(digest['top_items']) <= 4
print({'evaluated': 35, 'selected': digest['selected_count']})
PY
git diff --check
```

Expected: 全部测试 PASS，断言脚本 exit 0，`git diff --check` 无输出。

- [ ] **Step 5: 检查最终工作树**

Run: `git status --short && git diff --stat HEAD~5`

Expected: 只有 V1 代码、测试、文档、日报与生成站点变化；没有 `hndaily-skill/_data/`、部署、推送或 PR 变化。
