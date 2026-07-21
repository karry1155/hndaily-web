# HNHOT 主题归一提示词 v1

## 任务

把第一次入库产生的开放主题映射到长期稳定的主题目录。此阶段只做名称归一、父级选择和新叶子提议，不改写文章的原始 `topic_profile`。

读取流水线打印的 `TOPIC_RESOLUTION_INPUT_JSON`。`catalog_topics` 是当前完整主题目录，包含稳定 ID、名称、别名、父级、定义以及收录/排除边界；`topics` 中每个开放主题包含原始名称、文章内关系与证据，以及按规范名称或别名找到的精确匹配。

## 决策

- 依据 `definition`、`include` 和 `exclude` 判断语义边界；不要只按词面相似度选择。
- 确属已有主题或其别名时输出 `decision: existing` 和已有 `topic_id`。
- 没有语义边界合适的节点时输出 `decision: new`，建立具体叶子主题；不得为了减少新节点而硬塞到相近大类。
- 新主题必须挂到一个已经存在的父节点，不得在本次输出里同时建立父子两级。
- `topic_id` 使用稳定、简短的英文 kebab-case，改名后也不改变。
- `name` 是规范中文名；原始 `source_name` 与规范名不同时，必须收入 `aliases`。
- `definition` 说明主题是什么；`include` 和 `exclude` 用具体边界防止以后仅靠关键词匹配。
- 保持输入主题顺序，不遗漏、不合并输入项。

## 输出

只写符合 `schema.json` 的严格 JSON。原样返回 `input_fingerprint`，不添加解释、评分或 schema 外字段。
