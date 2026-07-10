# Codex 日报生成操作说明（editorial-v1）

模型只负责语义理解。过滤、最终分、海南相关性资格线、去重、入选和排名全部由 Python 代码决定。不得搜索或补充《海南日报》正文之外的信息。

## 1. 准备全量候选

```bash
bash scripts/run_daily_pipeline.sh
```

记录命令输出的五个绝对路径：

```text
RAW_JSON=...
MODEL_INPUT_JSON=...
MODEL_OUTPUT_JSON=...
PREFILTER_JSON=...
EDITORIAL_AUDIT_JSON=...
```

`PREFILTER_JSON.items` 必须覆盖原始报纸全部文章；被跳过项包含明确 `skip_reason`。语义生成步骤只读取 `MODEL_INPUT_JSON`，不得从原始 JSON 复制或生成 URL。

## 2. 写严格模型输出

顶层 `schema_version`、`prompt_version` 和 `input_fingerprint` 必须从模型输入原样复制。`items` 数量、候选 ID 和顺序必须完全一致。

每项只能包含：

```json
{
  "candidate_id": "A005",
  "title": "海南住房公积金新增物业费支付用途",
  "summary": "用一至两句话陈述正文中的变化。",
  "why_it_matters": "说明这对海南用户今天为何值得关注。",
  "key_facts": ["只写正文支持的日期、数字、对象、地点或措施"],
  "confidence": "full_text",
  "suggested_category": "民生/办事",
  "hainan_relevance": 10,
  "actionability": 9,
  "impact_scope": 8,
  "novelty": 8,
  "information_density": 8,
  "score_reasons": {
    "hainan_relevance": "正文证据或简短理由",
    "actionability": "正文证据或简短理由",
    "impact_scope": "正文证据或简短理由",
    "novelty": "正文证据或简短理由",
    "information_density": "正文证据或简短理由"
  }
}
```

五个分数必须是 JSON 整数且位于 0–10。分类只能是数据契约中除“已跳过”外的固定类别。`confidence` 只能为 `full_text`、`short_item` 或 `partial`。

模型不得返回 `url`、`sources`、`page`、原始标题、作者、日期、`final_score`、`selected` 或 `rank`。未知字段、未知分类、浮点分、越界分、缺项、错序或指纹不一致都会使 finalize 失败。

## 3. 确定性 finalize 和渲染

```bash
DATE_STEM="$(basename "$RAW_JSON" .json)"
DIGEST_JSON="content/daily/$DATE_STEM.json"
python3 scripts/finalize_digest.py \
  "$RAW_JSON" \
  "$MODEL_INPUT_JSON" \
  "$MODEL_OUTPUT_JSON" \
  "$DIGEST_JSON" \
  "$EDITORIAL_AUDIT_JSON"
python3 scripts/validate_digest.py "$DIGEST_JSON"
python3 scripts/render_site.py
```

V1 基础语义分按 30% 海南相关性、25% 行动价值、20% 影响范围、15% 新颖性、10% 信息密度换算为 0–100，再由代码应用版面和短讯调整。事件必须同时达到 `hainan_relevance >= 6` 与 `final_score >= 65` 才能入选，按稳定顺序最多取 8 篇，不补齐。前 4 篇进入“今日重点”，第 5–8 篇进入“今日还值得看”。

任一步骤失败都必须停止；不得发布半成品。本项目不会自动提交、推送或部署。
