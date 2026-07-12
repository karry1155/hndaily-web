# AIHOT 组件模式

## 1. 顶部品牌栏

- 只承担品牌与日期/更新时间，不承载主导航。
- 移动端高度紧凑，不使用明显底部横线或厚重阴影。
- 内容左右对齐，品牌权重大于日期。

## 2. 热点摘要

结构：标题行 → 排名列表。它是首屏唯一明显卡片。

- 外层约 `12px` 圆角、`1px` 边框、极浅阴影。
- 标题行紧凑，右侧可放 `TOP N` 或低权重说明。
- 每条使用 `flex`/`grid`：排名、标题、元信息/收藏。
- 排名视觉面积小，前三名使用区分色。
- 条目间可有浅分隔线，但标题行下方不需要额外装饰线。
- 标题一至两行；不要在热点中重复长摘要。

HN·HOT 映射：`时下要闻` 保留四条，排名色块与收藏按钮保留，减少面板高度和装饰。

## 3. 分类工具栏

- 章节标题直接位于页面背景。
- 分类胶囊是独立按钮，不放进总胶囊容器。
- 选中项为深色/品牌色实心，未选项为浅底或细边框。
- 移动端单行横向滚动，隐藏滚动条。
- 胶囊高度约 `30–36px`，字体约 `12–14px`。

## 4. 新闻流

- 日期栏直接连接页面背景，可用极浅背景区别日期层级。
- 新闻条目不使用独立卡片。
- 条目通过浅分隔线、标题粗细、摘要颜色和元信息字号建立层级。
- 收藏固定靠右；正文列使用 `min-width: 0`，避免按钮挤压标题。
- 桌面/宽移动布局可显示时间列；窄屏可以把时间并入元信息。
- 摘要默认两行，信息较复杂时最多三行。

推荐结构：

```html
<article class="feed-row">
  <div class="feed-meta">来源 · 时间</div>
  <a class="feed-main">
    <strong class="feed-title">标题</strong>
    <p class="feed-summary">摘要</p>
  </a>
  <button class="feed-save">收藏</button>
</article>
```

## 5. 底部导航

AIHOT 的移动底栏是独立根级组件：

```css
.mobile-tabbar {
  position: fixed;
  inset: auto 0 0;
  z-index: 900;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  padding:
    4px max(6px, env(safe-area-inset-right))
    calc(4px + env(safe-area-inset-bottom))
    max(6px, env(safe-area-inset-left));
}

.page-main {
  padding-bottom: calc(var(--tabbar-height) + env(safe-area-inset-bottom) + 28px);
}
```

关键不是选择器名称，而是两个不变量：底栏相对于视口定位；正文底部补偿引用同一个底栏高度。不要把固定底栏嵌在带 `filter`、`backdrop-filter` 或 `transform` 的祖先中，否则固定定位可能改为相对祖先。

## 6. 可复用规则

```css
@media (max-width: 760px) {
  .benchmark-open-section {
    margin: 0;
    padding-inline: var(--mobile-gutter, 16px);
    border: 0;
    border-radius: 0;
    background: transparent;
    box-shadow: none;
  }

  .benchmark-scroll-pills {
    display: flex;
    gap: 8px;
    overflow-x: auto;
    scrollbar-width: none;
    -webkit-overflow-scrolling: touch;
  }

  .benchmark-scroll-pills::-webkit-scrollbar { display: none; }

  .benchmark-feed-row {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 40px;
    gap: 8px;
    padding-block: 10px;
    border-bottom: 1px solid var(--line-soft);
  }

  .benchmark-clamp-2,
  .benchmark-clamp-3 {
    display: -webkit-box;
    overflow: hidden;
    -webkit-box-orient: vertical;
  }

  .benchmark-clamp-2 { -webkit-line-clamp: 2; }
  .benchmark-clamp-3 { -webkit-line-clamp: 3; }
}
```

这些是抽象规则示例，不应直接以 `benchmark-*` 类加入生产 HTML；实现时映射到 HN·HOT 现有语义类。

