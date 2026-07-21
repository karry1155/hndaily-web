# HNHOT 配置

这里集中存放数量有限、便于人工审查的受控词表和确定性页面规则。

- `hainan-administrative-divisions.json`：海南地点词表，用于生成模型输入中的
  `location_candidates`，并在发布时解析地点名称。
- `topic-catalog.json`：主题目录的初始根节点和边界定义；生产目录发布后位于
  `content/topics/catalog.json`。它只参与入站后的主题归一，不发送给第一次入库模型。
- `topics.json`：v1/v2 历史主题词表，只读保留，不再生成 `topic_candidates`。
- `page-sections.json`：把报纸的物理版面名称映射为报库中的逻辑版面。它参与页面
  组织，但不会发送给模型。

主体、主题和事件都不维护第一次入库词表。v3 允许智能体从每篇原文中自由提取；
后续归一化管线再维护经过审查的稳定身份、主题 ID 和目录路径。
