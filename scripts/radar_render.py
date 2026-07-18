#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import re
import shutil
import sys
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.radar_indexes import build_hnhot_indexes
from scripts.radar_issue import (
    upgrade_legacy_issue,
    upgrade_legacy_issue_item,
    validate_public_issue,
    validate_public_issue_item,
)
from scripts.radar_store import load_issue_items, load_issues
from scripts.render_site import render_base

ROOT = Path(__file__).resolve().parents[1]
PRODUCT_NAME = "HNHOT"
SCOPE_LABELS = {"national": "N", "hainan": "H", "mixed": "M"}
SCOPE_NAMES = {None: "全部", "national": "全国", "hainan": "海南", "mixed": "海南关联"}
SCOPE_PATHS = {
    None: "/", "national": "/front-page/national/",
    "hainan": "/front-page/hainan/", "mixed": "/front-page/mixed/",
}
NAV_ITEMS = (("头版", "/"), ("全部", "/all/"), ("日报", "/daily/"), ("更多", "/more/"))
NAV_ICONS = {
    "头版": '<path d="M5 4h14v16H5zM8 8h8M8 12h8M8 16h5"/>',
    "全部": '<path d="M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01"/>',
    "日报": '<path d="M6 3h9l3 3v15H6zM14 3v4h4M9 12h6M9 16h6"/>',
    "更多": '<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>',
}


def _esc(value, quote=False):
    return html.escape(str(value), quote=quote)


def _weekday(value):
    parsed = date.fromisoformat(value)
    return ("星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日")[parsed.weekday()]


def _date_label(value):
    parsed = date.fromisoformat(value)
    return f"{parsed.year}年{parsed.month}月{parsed.day}日"


def _nav_icon(label):
    return f'<svg class="nav-icon" viewBox="0 0 24 24" aria-hidden="true">{NAV_ICONS[label]}</svg>'


def render_primary_nav(active, mobile_meta=""):
    link_rows = []
    for label, path in NAV_ITEMS:
        current = ' class="active" aria-current="page"' if label == active else ""
        link_rows.append(
            f'<a href="{path}"{current}>{_nav_icon(label)}<span>{label}</span></a>'
        )
    links = "".join(link_rows)
    return (
        '<aside class="primary-nav">'
        '<a class="brand" href="/">HNHOT<span>海南日报信息雷达</span></a>'
        f'<span class="mobile-meta">{_esc(mobile_meta)}</span>'
        f'<nav aria-label="主导航">{links}</nav>'
        '<div class="desktop-tools"><button type="button" data-theme-cycle>切换明暗</button></div>'
        '</aside>'
    )


def _bookmark_button(item):
    return (
        f'<button class="bookmark-button" type="button" data-star-id="{_esc(item["item_id"], True)}" '
        f'aria-label="收藏 {_esc(item["title"], True)}">'
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 4h12v17l-6-4-6 4z"/></svg></button>'
    )


def _story_card(item, rank=None):
    scope = item.get("scope")
    badge = SCOPE_LABELS.get(scope, "–")
    summary = item.get("ai_summary") or "这篇历史报道尚待重新生成结构化摘要。"
    status = (
        '<span class="legacy-note">历史归类</span>'
        if item.get("enrichment_status") == "legacy-derived" else ""
    )
    rank_markup = f'<span class="ranking-number">{rank}</span>' if rank is not None else ""
    search_text = " ".join((item["title"], summary, scope or ""))
    return (
        f'<article class="story-card" data-search-card data-search-text="{_esc(search_text, True)}">'
        f'{rank_markup}<span class="scope-badge scope-{_esc(scope or "pending", True)}">{badge}</span>'
        f'<a class="story-copy" href="{_esc(item["detail_path"], True)}">'
        f'<h3>{_esc(item["title"])}</h3><p>{_esc(summary)}</p>'
        f'<div class="story-meta">{status}</div></a>{_bookmark_button(item)}</article>'
    )


def _scope_tabs(active_scope):
    rows = []
    for scope, path in SCOPE_PATHS.items():
        current = ' class="active" aria-current="page"' if scope == active_scope else ""
        rows.append(f'<a href="{path}"{current}>{SCOPE_NAMES[scope]}</a>')
    return "".join(rows)


def render_front_page(feeds, active_scope=None):
    latest_date = feeds[0]["date"] if feeds else None
    ranking = ""
    if active_scope is None and feeds:
        ranked = feeds[0]["national_ranking"]
        ranking = (
            '<section class="national-ranking"><header><div><span class="eyebrow">今日编辑判断</span>'
            f'<h2>全国要闻 TOP {len(ranked)}</h2></div><span>按头版次序</span></header>'
            f'<div class="ranking-list">{"".join(_story_card(item, item["rank"]) for item in ranked)}</div></section>'
            if ranked else ""
        )
    groups = []
    for feed in feeds:
        items = [row for row in feed["items"] if active_scope is None or row["scope"] == active_scope]
        if not items:
            continue
        groups.append(
            f'<section class="date-group"><header><h2>{_date_label(feed["date"])}</h2>'
            f'<span>{_weekday(feed["date"])} · {len(items)} 条</span></header>'
            f'<div class="story-list">{"".join(_story_card(item) for item in items)}</div></section>'
        )
    empty = '<p class="empty-state">这个分类暂时没有头版报道。</p>' if not groups else ""
    date_text = f'{_date_label(latest_date)} · {_weekday(latest_date)}' if latest_date else "暂无报纸"
    return (
        '<div class="app-shell radar-shell">'
        f'{render_primary_nav("头版", date_text)}'
        '<main class="content-shell front-page">'
        '<header class="page-header"><div><span class="eyebrow">Hainan Daily Front Page</span>'
        f'<h1>头版</h1><p>{_esc(date_text)}</p></div>'
        '<label class="site-search"><span class="sr-only">搜索头版</span>'
        '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="6"/><path d="m16 16 4 4"/></svg>'
        '<input type="search" data-search-input placeholder="搜索标题或摘要"></label></header>'
        f'<nav class="scope-tabs" aria-label="头版分类">{_scope_tabs(active_scope)}</nav>'
        f'{ranking}<div data-search-scope>{"".join(groups)}{empty}</div>'
        '<p class="empty-state" data-search-empty hidden>没有匹配结果</p></main></div>'
    )


def render_index(index, focus=None, active_category="全部", manifest=None):
    scope = {"全国": "national", "海南": "hainan", "海南关联": "mixed"}.get(active_category)
    date_value = max((row["published_date"] for row in index.get("items", [])), default="")
    feed = {
        "date": date_value or date.today().isoformat(),
        "items": index.get("items", []),
        "national_ranking": [],
    }
    return render_front_page([feed] if index.get("items") else [], scope)


def render_issue(issue):
    issue = upgrade_legacy_issue(issue)
    validate_public_issue(issue)
    issue_meta = f'{_date_label(issue["date"])} · {_weekday(issue["date"])}'
    sections = []
    for section in issue["sections"]:
        rows = "".join(
            f'<a class="all-row" data-search-card data-search-text="{_esc(row["title"], True)}" href="{_esc(row["detail_path"], True)}">'
            f'<span>{_esc(row["title"])}</span><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 6 6 6-6 6"/></svg></a>'
            for row in section["articles"]
        )
        sections.append(
            f'<section class="logical-section"><header><h2>{_esc(section["name"])}</h2>'
            f'<span>{len(section["articles"])} 篇 · 合并 {len(section["source_pages"])} 个原版面</span></header>'
            f'<div class="all-list">{rows}</div></section>'
        )
    return (
        '<div class="app-shell radar-shell">'
        f'{render_primary_nav("全部", issue_meta)}'
        '<main class="content-shell all-page">'
        '<header class="page-header"><div><span class="eyebrow">完整报纸 · 逻辑版面</span>'
        f'<h1>全部</h1><p>{_date_label(issue["date"])} · {issue["article_count"]} 篇</p></div>'
        '<label class="site-search"><span class="sr-only">搜索全部报道</span>'
        '<input type="search" data-search-input placeholder="搜索本期标题"></label></header>'
        f'<div data-search-scope>{"".join(sections)}</div>'
        '<p class="empty-state" data-search-empty hidden>没有匹配结果</p></main></div>'
    )


def render_item(item):
    item = upgrade_legacy_issue_item(item)
    validate_public_issue_item(item)
    block = item["block"]
    summary = block.get("ai_summary") or "这篇历史报道尚待重新生成结构化摘要。"
    paragraphs = [
        part.strip() for part in re.split(r"\n\s*\n", block["content"].replace("\r\n", "\n")) if part.strip()
    ]
    tags = [
        *[row["name"] for row in item["subjects"]],
        *[row["name"] for row in item["locations"]],
        *[row["name"] for row in item["topics"]],
    ]
    tag_markup = "".join(f'<span>{_esc(value)}</span>' for value in tags)
    return (
        '<div class="app-shell radar-shell">'
        f'{render_primary_nav("全部", _date_label(item["published_date"]))}'
        '<main class="item-page"><a class="back-link" href="javascript:history.back()">← 返回</a>'
        f'<div class="item-meta"><span class="scope-badge scope-{item["scope"]}">{SCOPE_LABELS[item["scope"]]}</span>'
        f'<span>{_esc(item["page_name"])} · {_date_label(item["published_date"])}</span></div>'
        f'<h1>{_esc(block["title"])}</h1>'
        f'<section class="ai-summary"><span class="eyebrow">AI 摘要</span><p>{_esc(summary)}</p></section>'
        f'<div class="entity-tags">{tag_markup}</div>'
        f'<article class="source-body">{"".join(f"<p>{_esc(part)}</p>" for part in paragraphs)}</article>'
        f'<a class="source-button" href="{_esc(block["original_url"], True)}" target="_blank" rel="noopener noreferrer">在海南日报查看原文</a>'
        '</main></div>'
    )


def _simple_page(active, eyebrow, title, body):
    return (
        '<div class="app-shell radar-shell">'
        f'{render_primary_nav(active)}<main class="content-shell simple-page">'
        f'<header class="page-header"><div><span class="eyebrow">{_esc(eyebrow)}</span><h1>{_esc(title)}</h1></div></header>{body}'
        '</main></div>'
    )


def _more_page():
    cards = (
        '<a class="more-card" href="/starred/"><strong>收藏</strong><span>留住值得反复阅读的报道</span></a>'
        '<a class="more-card" href="/subjects/"><strong>按主体看海南</strong><span>人物、机构、企业与项目的连续报道</span></a>'
        '<a class="more-card" href="/regions/"><strong>按地区看海南</strong><span>沿行政区积累地区记忆</span></a>'
        '<a class="more-card" href="/about/"><strong>关于 HNHOT</strong><span>产品方法与数据边界</span></a>'
    )
    return _simple_page("更多", "Build a memory of Hainan", "更多", f'<div class="more-grid">{cards}</div>')


def _starred_page(catalog):
    payload = json.dumps(catalog, ensure_ascii=False).replace("<", "\\u003c")
    body = (
        '<div class="story-list" data-starred-list></div>'
        '<p class="empty-state" data-starred-empty>还没有收藏。可在头版报道右侧点按书签。</p>'
        f'<script type="application/json" id="starred-catalog">{payload}</script>'
    )
    return _simple_page("更多", "Saved locally on this device", "收藏", body)


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_base(PRODUCT_NAME, body), encoding="utf-8")


class _LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "a" and (href := dict(attrs).get("href")):
            self.links.append(href)


def validate_internal_links(site_root):
    missing = []
    for page in site_root.rglob("*.html"):
        parser = _LinkParser()
        parser.feed(page.read_text(encoding="utf-8"))
        for href in parser.links:
            parsed = urlparse(href)
            if parsed.scheme or parsed.netloc or href.startswith(("#", "javascript:")):
                continue
            target = site_root / parsed.path.lstrip("/")
            if parsed.path.endswith("/"):
                target /= "index.html"
            if not target.exists():
                missing.append(f"{page}: {href}")
    return missing


def build_site(content_root, site_root):
    content_root, site_root = Path(content_root), Path(site_root)
    issues = load_issues(content_root)
    articles = load_issue_items(content_root)
    if not issues:
        raise ValueError("HNHOT requires at least one newspaper issue")
    indexes = build_hnhot_indexes(issues, articles)
    staging = site_root.with_name(f".{site_root.name}.hnhot-staging")
    backup = site_root.with_name(f".{site_root.name}.hnhot-backup")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    try:
        shutil.copytree(ROOT / "src/static", staging / "static")
        for relative, payload in indexes.items():
            target = staging / "static/data" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        feeds = [indexes[f"front-page/{value}.json"] for value in indexes["hnhot.json"]["dates"]]
        _write(staging / "index.html", render_front_page(feeds))
        for scope in ("national", "hainan", "mixed"):
            _write(staging / f"front-page/{scope}/index.html", render_front_page(feeds, scope))
        for issue in issues:
            _write(staging / f'all/{issue["date"]}/index.html', render_issue(issue))
        latest = max(issues, key=lambda value: value["date"])
        _write(staging / "all/index.html", render_issue(latest))
        catalog = []
        for article in articles:
            _write(
                staging / f'items/{article["published_date"]}/{article["item_id"]}/index.html',
                render_item(article),
            )
            catalog.append({
                "item_id": article["item_id"], "published_date": article["published_date"],
                "title": article["block"]["title"], "ai_summary": article["block"]["ai_summary"],
                "scope": article["scope"], "enrichment_status": article["enrichment_status"],
                "detail_path": f'/items/{article["published_date"]}/{article["item_id"]}/',
            })
        _write(staging / "daily/index.html", _simple_page(
            "日报", "Daily synthesis", "日报",
            '<div class="placeholder-panel"><strong>日报能力正在建设</strong><p>这里将根据当日整份报纸生成可回顾、可积累的日报，而不是另一份标题列表。</p></div>',
        ))
        _write(staging / "more/index.html", _more_page())
        _write(staging / "starred/index.html", _starred_page(catalog))
        _write(staging / "subjects/index.html", _simple_page(
            "更多", "Continuous reporting", "按主体看海南",
            '<div class="placeholder-panel"><strong>主体档案正在积累</strong><p>后续将按人物、政府机构、组织、企业与项目聚合连续报道和事件时间线。</p></div>',
        ))
        _write(staging / "regions/index.html", _simple_page(
            "更多", "Administrative geography", "按地区看海南",
            '<div class="placeholder-panel"><strong>地区档案正在积累</strong><p>后续将沿海南行政区呈现报道密度、主体与事件脉络。</p></div>',
        ))
        _write(staging / "about/index.html", _simple_page(
            "更多", "About", "关于 HNHOT",
            '<div class="prose-block"><p>HNHOT 放大海南日报编辑已经做出的版面判断，并把每天的报道连接成对海南的长期理解。</p><p>产品不对新闻重新打分精选；头版来自报纸头版，全部保留每篇有效报道。</p></div>',
        ))
        errors = validate_internal_links(staging)
        if errors:
            raise ValueError("broken internal links: " + "; ".join(errors))
        if backup.exists():
            shutil.rmtree(backup)
        had_site = site_root.exists()
        if had_site:
            site_root.replace(backup)
        try:
            staging.replace(site_root)
        except Exception:
            if had_site and backup.exists() and not site_root.exists():
                backup.replace(site_root)
            raise
        if backup.exists():
            shutil.rmtree(backup)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise


def main(argv):
    content = Path(argv[1]) if len(argv) > 1 else ROOT / "content"
    site = Path(argv[2]) if len(argv) > 2 else ROOT / "site"
    try:
        build_site(content, site)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
