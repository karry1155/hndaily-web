# V4.3 最小示例

`2026-07-23.demo-source.json`、`demo-input.json`、`demo-output.json` 和
`demo-prefilter.json` 共同演示完整合同。它们是人工编写的架构样例，
不是真实报纸数据，也不会被生产管线自动发布。

可在临时目录中验证示例：

```bash
python3 scripts/check_model_output.py \
  examples/2026-07-23.demo-input.json \
  examples/2026-07-23.demo-output.json
```
