# Radar v3 生成流程

运行 `bash scripts/run_radar_pipeline.sh YYYY-MM-DD`。首次运行以退出码 2 返回 `STATUS=MODEL_OUTPUT_REQUIRED`，并打印模型输入和输出路径。

模型只读取 `candidate_id`、`title`、`content`。输出 envelope 精确包含 `schema_version`、`prompt_version`、`input_fingerprint`、`items`；每项精确包含候选 ID、AI 摘要、一个正式分类、五项语义分及理由、机会生命周期与截止证据字段。模型不得返回或覆盖来源、标题、正文、URL、日期或稳定 ID。

写入打印出的 `MODEL_OUTPUT_JSON` 后重跑同一命令。成功返回退出码 0 和 `STATUS=COMPLETE`。其他非零状态均为失败；publish 前失败不改变公开内容，publish 中失败会统一回滚 content、site 与 audit。
