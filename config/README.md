# HNHOT 配置

这里集中存放数量有限、便于人工审查的受控词表和确定性页面规则。

- `hainan-administrative-divisions.json`：海南地点词表，用于生成模型输入中的
  `location_candidates`，并在发布时解析地点名称。
- `topics.json`：主题词表，用于生成模型输入中的 `topic_candidates`，并在发布时
  解析主题名称。
- `page-sections.json`：把报纸的物理版面名称映射为报库中的逻辑版面。它参与页面
  组织，但不会发送给模型。

主体和事件不再维护第一次入库词表。v2 允许智能体从每篇原文中自由提取明确出现的
名称；后续的归一化、人物轨迹和长期事件管线再维护经过审查的稳定身份。
