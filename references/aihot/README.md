# AIHOT 对标资料库

这是 HN·HOT 的长期对标资料，保存了 AIHOT 在 2026-07-11（America/Los_Angeles）公开页面的源码快照、视觉截图和结构化分析。后续进行首页、移动端密度、热点摘要、分类导航或新闻列表调整前，应先阅读本文件和 `analysis/hn-hot-checklist.md`。

## 阅读顺序

1. `analysis/design-system.md`：颜色、字体、间距、断点和密度规律。
2. `analysis/component-patterns.md`：热点、分类、新闻流和底部导航的组件规则。
3. `analysis/hn-hot-checklist.md`：应用到 HN·HOT 时的实施与截图验收清单。
4. `screenshots/`：移动端和桌面端视觉基准。
5. `raw/`：需要核对具体选择器或级联顺序时再读原始 HTML/CSS。

## 目录

```text
references/aihot/
├── README.md
├── manifest.json
├── analysis/
│   ├── component-patterns.md
│   ├── design-system.md
│   └── hn-hot-checklist.md
├── raw/
│   ├── index.html
│   └── css/
└── screenshots/
    ├── desktop-1440x1000.png
    └── mobile-393x852.png
```

## 使用边界

- 这些文件只用于内部设计研究，不被生产模板或构建流程引用。
- 学习其信息架构、密度、响应式和层级关系，不复制品牌、文案或整套视觉身份。
- 优先把规律转译为 HN·HOT 的设计变量和组件规则，不把压缩后的原始 CSS 直接粘贴到 `src/static/styles.css`。
- AIHOT 会持续变化；需要重新对标时，应新建带日期的快照或更新 `manifest.json`，不要无记录覆盖。

## 快速结论

- 移动端主断点约为 `960px`，进一步紧凑化使用 `640px`。
- 移动内容列最大宽度约 `640px`，常用页面边距为 `12–18px`。
- 热点模块是唯一较明显的摘要容器；分类和新闻流直接连接页面背景。
- 新闻流依赖分隔线和文字层级，而不是重复卡片。
- 底部导航是页面根级固定元素，并为安全区和正文底部留白使用同一高度变量。

