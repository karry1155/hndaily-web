# AIHOT 2.0 对标资料库

这是 HN·HOT 的长期对标资料，当前快照采集于 2026-07-16（America/Los_Angeles；站点页面日期为北京时间 2026-07-17）。资料包含 AIHOT 2.0 的公开 DOM、响应式 CSS、关键前端脚本、公开 API 示例、桌面/手机截图、版本差异和逐功能逆向提示词。

## 推荐阅读顺序

1. `analysis/reverse-engineered-prompts.md`：截图、前端逻辑和可复制的高效提示词。
2. `analysis/latest-changes.md`：相对 2026-07-11 快照发生了什么。
3. `analysis/design-system.md`：当前颜色、断点、密度和两端布局。
4. `analysis/component-patterns.md`：组件、路由和浏览器状态合同。
5. `analysis/hn-hot-checklist.md`：应用到 HN·HOT 时的验收清单。
6. `raw/`：需要核对选择器、压缩脚本或公开 API 字段时再读。

## 目录

```text
references/aihot/
├── README.md
├── manifest.json
├── analysis/
│   ├── component-patterns.md
│   ├── design-system.md
│   ├── hn-hot-checklist.md
│   ├── latest-changes.md
│   └── reverse-engineered-prompts.md
├── raw/
│   ├── index.html
│   ├── public-skill.md
│   ├── route-scripts.json
│   ├── api/*.json
│   ├── css/*.css
│   └── js/*.js
└── screenshots/
    ├── 01-home-desktop-1440x1000.png
    ├── 02-home-mobile-393x852.png
    ├── 03-search-mobile-openai-393x852.png
    ├── 04-starred-mobile-393x852.png
    ├── 05-item-detail-mobile-393x852.png
    ├── 06-daily-mobile-393x852.png
    ├── 07-topics-mobile-393x852.png
    ├── 08-more-theme-mobile-393x852.png
    ├── 09-changelog-mobile-393x852.png
    ├── 10-agent-mobile-393x852.png
    └── 11-about-method-mobile-393x852.png
```

## 使用边界

- 这些文件只用于内部设计与提示词研究，不被生产构建引用。
- 学习信息架构、响应式、内容合同和沟通方式，不复制品牌身份或原站文案。
- `analysis/reverse-engineered-prompts.md` 中的提示词是从公开结果推导的学习模板，不是 AIHOT 私有提示词泄露。
- 压缩 CSS/JS 只用于核对公开前端行为，不应直接复制到生产代码。

## 当前快速结论

- 桌面端与手机端是同一应用的两种响应式呈现，不存在独立“手机端源码”。
- `960px` 切换移动外壳，`640px` 再压缩 gutter 和排版。
- 桌面新闻为卡片时间线，手机新闻为连续阅读流。
- 热点以已聚类信源强度排序，但必须经过精选锚点门槛。
- 搜索、筛选、收藏、已读、主题和导航属于确定性前端逻辑；摘要、聚类、分类、评分、精选和日报编排属于可能的模型辅助流程。
