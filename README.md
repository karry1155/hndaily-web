# HNHOT

仓库根目录就是当前正式应用。当前文章语义合同为
`schema_version: 13` / `prompt_version: hnhot-v4.3`，不再通过复制整套
`v1/`、`v2/`、`v3/`、`v4/` 应用推进开发。

历史整套程序保存在仓库外的同级目录：

```text
../hndaily-web-radar-snapshots/
```

正式版本由 Git commit 和 tag 保存；仓库外快照只作为迁移保险，不参与运行、
测试或发布。

## 当前语义合同

- `prompts/article-enrichment/v4.3/prompt.md`：模型判断规则。
- `prompts/article-enrichment/v4.3/schema.json`：严格 JSON 结构。
- `config/topics.json`：主题大类的有限目录。
- `config/hainan-administrative-divisions.json`：海南地点有限目录。

首次 JSON 同时提供摘要、范围、主体及动作、海南地点、主题、命名事件、
规划文件和读者提醒。站内不同页面只对同一份 JSON 做确定性的分组、统计和连接。

## 数据目录

```text
data/
├── active-run.json
└── runs/
    └── hnhot-v4.3/
        ├── source/
        ├── input/
        ├── enrichment/
        └── audit/
```

`source` 保存原始报纸，`input` 保存确定性模型输入，`enrichment` 保存首次语义
JSON，`audit` 保存过滤与发布审计。`active-run.json` 声明当前生产网站使用的合同。

## 导入一期

```bash
bash scripts/run_radar_pipeline.sh YYYY-MM-DD
```

命令输出 `STATUS=MODEL_OUTPUT_REQUIRED` 时：

1. 完整读取打印出的 `MODEL_INPUT_JSON`；
2. 完整读取打印出的 `PROMPT_DIR`；
3. 逐篇完成语义提取；
4. 将严格 JSON 写入 `MODEL_OUTPUT_JSON`；
5. 再次运行相同命令完成校验、发布和站点构建。

流程不依赖外部模型 API。语义步骤由进入目录的交互式智能体直接完成。

## 页面导航

- 桌面端左侧直接展示阅读、探索和服务页面。
- 手机端底部固定保留“头版、全部、日报、更多”。
- “更多”统一提供主体、地区、主题、活动、规划、提醒和关于入口。

## 验证与预览

```bash
python3 -m unittest discover -s tests -v
python3 scripts/radar_render.py content site
python3 -m scripts.preview
```

预览地址为 `http://127.0.0.1:8765/`。

## 发布

`site/` 是生成后的静态网站，也是当前 GitHub/Cloudflare Pages 工作流直接发布的
目录，因此需要纳入 Git。每次修改内容、提示词消费逻辑或前端后，应先重新生成：

```bash
python3 scripts/radar_render.py content site
```

确认页面无误后，将源文件、`content/` 和对应的 `site/` 结果放在同一次提交中，
避免线上页面落后于当前数据。Cloudflare Pages 使用仓库根目录，构建命令可留空，
发布目录设为 `site`。
