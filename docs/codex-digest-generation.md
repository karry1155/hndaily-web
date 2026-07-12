# Radar v3 生成流程

运行 `bash scripts/run_radar_pipeline.sh YYYY-MM-DD`。首次运行以退出码 2 返回 `STATUS=MODEL_OUTPUT_REQUIRED`，并打印模型输入和输出路径。

模型只读取 `candidate_id`、`title`、`content` 和脚本从正文命中的 `location_candidates`。地点只能返回候选中的 `location_id`，行政区名称、代码和层级由脚本补全；JSON 和页面始终使用包含“市”“县”“自治县”等后缀的完整规范名称。输出 envelope 精确包含 `schema_version`、`prompt_version`、`input_fingerprint`、`items`；每项精确包含候选 ID、AI 摘要、推荐理由、主体数组、地点选择、动作与证据、一个正式分类、五项语义分及理由、机会生命周期与截止证据字段。模型不得返回或覆盖来源、标题、正文、URL、日期、稳定 ID、行政区代码或最终分。

`recommendation_reason` 用一至两句中文解释“为什么值得读”，强调影响、稀缺信息、决策价值、趋势信号或海南关联；不得复述标题或 `ai_summary`，不得返回内部评分过程。

写入打印出的 `MODEL_OUTPUT_JSON` 后重跑同一命令。成功返回退出码 0 和 `STATUS=COMPLETE`。其他非零状态均为失败；publish 前失败不改变公开内容，publish 中失败会统一回滚 content、site 与 audit。
