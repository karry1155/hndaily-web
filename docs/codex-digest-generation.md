# Codex 日报生成操作说明

这份说明供 Codex 定时任务使用。模型只负责内容理解；URL、原始标题和版面必须由脚本从爬虫 JSON 注入。

## 1. 准备前三篇文章

在 `hndaily-web` 仓库执行：

```bash
bash scripts/run_daily_pipeline.sh
```

记录 stdout 中的三个绝对路径：

```text
RAW_JSON=...
MODEL_INPUT_JSON=...
MODEL_OUTPUT_JSON=...
```

只读取 `MODEL_INPUT_JSON`。不要把 `RAW_JSON` 交给语义生成步骤，也不要搜索或补充外部信息。

## 2. 写模型输出

对 `MODEL_INPUT_JSON.items` 中的每一项提炼正文，保持原顺序，将结果写到 `MODEL_OUTPUT_JSON`。顶层的 `schema_version`、`prompt_version` 和 `input_fingerprint` 必须原样复制。

输出必须严格符合：

```json
{
  "schema_version": 1,
  "prompt_version": "digest-v1",
  "input_fingerprint": "从模型输入原样复制",
  "items": [
    {
      "candidate_id": "A001",
      "title": "基于正文改写的具体标题",
      "summary": "用一至两句话说明发生了什么",
      "why_it_matters": "用一句话说明用户为什么今天值得关注",
      "key_facts": ["正文支持的日期、数字、地点、主体或动作"],
      "confidence": "full_text"
    }
  ]
}
```

每个 item 只能包含以下六个字段：

- `candidate_id`
- `title`
- `summary`
- `why_it_matters`
- `key_facts`
- `confidence`

不得输出 `url`、`sources`、`page`、原始标题、作者、日期、来源名称或 PDF 地址。`confidence` 只能是 `full_text`、`short_item` 或 `partial`。

## 3. 合并真实来源并发布

使用第 1 步记录的路径执行；日期从 `RAW_JSON` 文件名取得：

```bash
DATE_STEM="$(basename "$RAW_JSON" .json)"
DIGEST_JSON="content/daily/$DATE_STEM.json"
python3 scripts/finalize_digest.py "$RAW_JSON" "$MODEL_INPUT_JSON" "$MODEL_OUTPUT_JSON" "$DIGEST_JSON"
python3 scripts/validate_digest.py "$DIGEST_JSON"
python3 scripts/render_site.py
```

`finalize_digest.py` 会重新读取原始 JSON，并为每条结果插入真实的原始标题、版面和 URL。模型输出中的字段、ID、指纹或数量不符合要求时，命令失败且不会覆盖已有 digest。

只有上述三个命令全部成功后，定时任务才可以提交并推送：

```bash
git add "content/daily/$DATE_STEM.json"
git commit -m "data: publish海南日报 $DATE_STEM"
git push
```

任何步骤失败时停止，不渲染、不提交、不推送。
