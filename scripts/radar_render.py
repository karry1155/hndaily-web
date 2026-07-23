#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import math
import shutil
import sys
from collections import defaultdict
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[1]
SCOPE_LABELS = {
    "hainan": ("H", "海南本地"), "domestic": ("D", "国内关联"),
    "mixed": ("M", "海南开放"), "national": ("N", "全国"),
    "foreign": ("F", "全球"),
}
SUBJECT_LABELS = {"person": "人物", "company": "企业", "organization": "机构"}
EVENT_LABELS = {
    "recurring_edition": "周期活动", "named_event": "命名事件",
    "incident": "突发事件", "series": "活动系列",
}
PLAN_LABELS = {
    "proposed": "拟编制", "reviewed": "审议中", "approved": "已通过",
    "released": "已发布", "implemented": "实施中", "progress": "进展",
    "mentioned": "提及",
}
READER_LABELS = {
    "apply": "申请", "register": "报名/预约", "attend": "参加",
    "submit": "提交", "lookup": "查询", "use_service": "使用服务",
    "prepare": "提前准备", "avoid": "风险提醒",
}
NAV_ICONS = {
    "front": '<path d="M5 4h14v16H5zM8 8h8M8 12h8M8 16h5"/>',
    "all": '<path d="M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01"/>',
    "daily": '<path d="M6 3h9l3 3v15H6zM14 3v4h4M9 12h6M9 16h6"/>',
    "subjects": '<circle cx="12" cy="8" r="3"/><path d="M6 20c.7-4 3-6 6-6s5.3 2 6 6"/>',
    "regions": '<path d="M12 21s6-5.1 6-11a6 6 0 1 0-12 0c0 5.9 6 11 6 11z"/><circle cx="12" cy="10" r="2"/>',
    "topics": '<path d="M4 6h7M4 12h11M4 18h16"/>',
    "events": '<rect x="4" y="5" width="16" height="15" rx="2"/><path d="M8 3v4M16 3v4M4 10h16"/>',
    "plans": '<path d="M6 3h9l3 3v15H6zM14 3v4h4M9 12h6M9 16h6"/>',
    "reminders": '<path d="M6 17h12l-1.5-2v-4a4.5 4.5 0 0 0-9 0v4zM10 20h4"/>',
    "about": '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7h.01"/>',
    "more": '<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>',
}
FEATURE_NAV_KEYS = {"subjects", "regions", "topics", "events", "plans", "reminders", "about"}


def esc(value) -> str:
    return html.escape(str(value or ""), quote=True)


def read_json(path: Path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_page(site_root: Path, route: str, value: str) -> None:
    path = site_root / route.strip("/") / "index.html" if route != "/" else site_root / "index.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def _nav_icon(key: str) -> str:
    return f'<svg class="nav-icon" viewBox="0 0 24 24" aria-hidden="true">{NAV_ICONS[key]}</svg>'


def nav(active: str) -> str:
    groups = [
        ("阅读", [
            ("front", "/", "头版"), ("all", "/all/", "全部"),
            ("daily", "/daily/", "日报"),
        ]),
        ("探索", [
            ("subjects", "/subjects/", "主体"), ("regions", "/regions/", "地区"),
            ("topics", "/topics/", "主题"), ("events", "/events/", "活动"),
            ("plans", "/plans/", "规划"),
        ]),
        ("服务", [
            ("reminders", "/reminders/", "提醒"), ("about", "/about/", "关于"),
        ]),
    ]
    rows = []
    for group_name, links in groups:
        rows.append(f'<span class="nav-group-label">{group_name}</span>')
        for key, href, label in links:
            classes = []
            if key in FEATURE_NAV_KEYS:
                classes.append("desktop-only")
            if key == active:
                classes.append("active")
            current = ' aria-current="page"' if key == active else ""
            class_attr = f' class="{" ".join(classes)}"' if classes else ""
            rows.append(
                f'<a href="{href}"{class_attr}{current}>{_nav_icon(key)}<span>{label}</span></a>'
            )
    more_active = active == "more" or active in FEATURE_NAV_KEYS
    more_current = ' aria-current="page"' if more_active else ""
    rows.append(
        f'<a href="/more/" class="mobile-only{" active" if more_active else ""}"'
        f'{more_current}>{_nav_icon("more")}<span>更多</span></a>'
    )
    return (
        '<aside class="primary-nav"><a class="brand" href="/">HNHOT'
        '<span>海南日报信息雷达</span></a><nav aria-label="主导航">'
        + "".join(rows)
        + '</nav><div class="desktop-tools"><button type="button" data-theme-cycle>切换明暗</button></div></aside>'
    )


def page(title: str, body: str, active: str = "") -> str:
    return f'''<!doctype html><html lang="zh-CN" data-theme="dark"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} · HNHOT</title><link rel="stylesheet" href="/static/styles.css">
<script defer src="/static/app.js"></script></head><body><div class="app-shell radar-shell">
{nav(active)}{body}</div></body></html>'''


def header(eyebrow: str, title: str, meta: str = "") -> str:
    return f'<header class="page-header"><div><span class="eyebrow">{esc(eyebrow)}</span><h1>{esc(title)}</h1><p>{esc(meta)}</p></div></header>'


def date_cn(value: str) -> str:
    if not value:
        return "日期未标明"
    y, m, d = value.split("-")
    return f"{int(y)}年{int(m)}月{int(d)}日"


def scope_badge(scope: str) -> str:
    short, label = SCOPE_LABELS.get(scope, ("–", "未分类"))
    return f'<span class="scope-badge scope-{esc(scope)}" title="{esc(label)}">{short}</span>'


def story_card(item, rank=None, searchable=True) -> str:
    summary = item.get("ai_summary") or "正文已入库，暂无摘要。"
    rank_markup = f'<span class="ranking-number">{rank}</span>' if rank is not None else ""
    search_attrs = ""
    if searchable:
        search_text = " ".join((item.get("title", ""), summary, item.get("scope", "")))
        search_attrs = f' data-search-card data-search-text="{esc(search_text)}"'
    return f'''<article class="story-card"{search_attrs}>{rank_markup}{scope_badge(item.get("scope", ""))}
<a class="story-copy" href="{esc(item['detail_path'])}"><h3>{esc(item['title'])}</h3><p>{esc(summary)}</p></a>
<button class="bookmark-button" type="button" data-star-id="{esc(item['item_id'])}" aria-label="收藏 {esc(item['title'])}"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 4h12v17l-6-4-6 4z"/></svg></button></article>'''


def story_list(items) -> str:
    if not items:
        return '<p class="empty-state">当前没有入库报道。</p>'
    return '<div class="story-list">' + "".join(story_card(item) for item in items) + '</div>'


def _scope_tabs(active_scope) -> str:
    rows = [(None, "/", "全部"), *[
        (scope, f"/front-page/{scope}/", f"{short} · {label}")
        for scope, (short, label) in SCOPE_LABELS.items()
    ]]
    links = []
    for scope, href, label in rows:
        is_active = scope == active_scope
        current = ' aria-current="page"' if is_active else ""
        links.append(
            f'<a href="{href}" class="{"active" if is_active else ""}"'
            f'{current}>{esc(label)}</a>'
        )
    return "".join(links)


def _ranking_panel(kind, eyebrow, title, items, empty_text) -> str:
    ranking_rows = "".join(story_card(item, item["rank"], searchable=False) for item in items)
    meta = f'<span>TOP {len(items)}</span>' if items else ""
    content = (
        f'<div class="ranking-list">{ranking_rows}</div>'
        if items else f'<p class="ranking-empty">{esc(empty_text)}</p>'
    )
    empty_class = " is-empty" if not items else ""
    return (
        f'<section class="national-ranking ranking-panel ranking-{kind}{empty_class}">'
        f'<header><div><span class="eyebrow">{esc(eyebrow)}</span><h2>{esc(title)}</h2></div>'
        f'{meta}</header>{content}</section>'
    )


def render_home(indexes: Path, active_scope=None) -> str:
    hnhot = read_json(indexes / "hnhot.json", {"dates": [], "latest_date": None})
    feeds = [
        read_json(indexes / "front-page" / f"{date}.json", {"date": date, "items": []})
        for date in hnhot.get("dates", [])
    ]
    latest = feeds[0] if feeds else {}
    ranking = "" if active_scope is not None else (
        '<div class="ranking-dashboard">'
        + _ranking_panel(
            "domestic", "今日头版", "全国要闻",
            latest.get("national_ranking", []), "今日暂无全国要闻",
        )
        + _ranking_panel(
            "world", "今日世界新闻", "全球要闻",
            latest.get("world_ranking", []), "今日暂无全球要闻",
        )
        + "</div>"
    )
    groups = []
    for feed in feeds:
        date = feed["date"]
        items = [row for row in feed["items"] if active_scope is None or row["scope"] == active_scope]
        if not items:
            continue
        groups.append(
            f'<section class="date-group" data-search-group><header><h2>{date_cn(date)}</h2><span>{len(items)} 条</span></header>'
            + story_list(items) + '</section>'
        )
    if not groups:
        groups.append('<p class="empty-state">这个分类暂时没有可显示的报道。</p>')
    body = (
        '<main class="content-shell front-page"><header class="page-header"><div>'
        '<span class="eyebrow">海南日报 · 要闻</span><h1>头版</h1></div>'
        '<label class="site-search"><span class="sr-only">搜索头版报道</span>'
        '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="6"/>'
        '<path d="m16 16 4 4"/></svg><input type="search" data-search-input '
        'placeholder="搜索标题或摘要"></label></header>'
        f'<nav class="scope-tabs" aria-label="头版分类">{_scope_tabs(active_scope)}</nav>'
        f'{ranking}<div data-search-scope>{"".join(groups)}</div>'
        '<p class="empty-state" data-search-empty hidden>没有匹配结果</p></main>'
    )
    return page("头版", body, "front")


def render_archive(indexes: Path) -> str:
    catalog = read_json(indexes / "search-articles.json", {"items": []})
    by_date = defaultdict(list)
    for item in catalog["items"]:
        by_date[item["published_date"]].append(item)
    groups = []
    for date in sorted(by_date, reverse=True):
        groups.append(
            f'<section class="date-group"><header><h2><a href="/all/{date}/">{date_cn(date)}</a></h2>'
            f'<span>{len(by_date[date])} 条</span></header>{story_list(by_date[date][:5])}'
            f'<a class="archive-issue-link" href="/all/{date}/">查看本期全部 {len(by_date[date])} 条 →</a></section>'
        )
    body = '<main class="content-shell all-page">' + header(
        "海南日报", "报库", f'{len(by_date)} 期 · {len(catalog["items"])} 条已入库'
    ) + '<label class="site-search"><input data-search-input placeholder="搜索标题、摘要和结构化对象"></label>'
    body += '<div data-archive-default>' + (''.join(groups) or '<p class="empty-state">尚未导入报纸。</p>') + '</div>'
    body += '<div data-archive-search-results data-search-source="/static/search-articles.json" hidden></div><p data-search-empty hidden>没有匹配报道。</p></main>'
    return page("报库", body, "all")


def render_issue(feed) -> str:
    sections = []
    by_id = {item["item_id"]: item for item in feed["items"]}
    for section in feed["sections"]:
        items = [by_id[row["item_id"]] for row in section["articles"] if row["item_id"] in by_id]
        sections.append(
            f'<section class="issue-section"><header><h2>{esc(section["name"])}</h2><span>{len(items)} 篇</span></header>{story_list(items)}</section>'
        )
    body = '<main class="content-shell all-page">' + header(
        "海南日报 · 本期内容", date_cn(feed["date"]), f'{feed["count"]} 篇'
    ) + ''.join(sections) + '<a class="back-to-top" href="#">返回顶部</a></main>'
    return page(date_cn(feed["date"]), body, "all")


def _subject_link(subject) -> str:
    role = f'<span>{esc(SUBJECT_LABELS[subject["type"]])} · {esc(subject.get("role", ""))}</span>'
    return f'<li><a class="context-subject-link" href="/subjects/{esc(subject["subject_id"])}/"><strong>{esc(subject["name"])}</strong>{role}<small class="context-subject-count">{len(subject["activities"])} 项动作</small></a></li>'


def _named_links(rows, prefix: str, id_key: str, name_key: str = "name") -> str:
    return ''.join(
        f'<li><a href="/{prefix}/{esc(row[id_key])}/">{esc(row[name_key])}</a></li>' for row in rows
    )


def _highlight_paragraph(value: str, subjects) -> str:
    surfaces = []
    for subject in subjects:
        surfaces.append((subject["name"], subject["type"]))
        surfaces.extend((alias["name"], subject["type"]) for alias in subject.get("aliases", []))
    surfaces.sort(key=lambda row: len(row[0]), reverse=True)
    positions = []
    occupied = [False] * len(value)
    for surface, kind in surfaces:
        start = 0
        while True:
            index = value.find(surface, start)
            if index < 0:
                break
            end = index + len(surface)
            if not any(occupied[index:end]):
                positions.append((index, end, kind))
                occupied[index:end] = [True] * (end - index)
            start = end
    positions.sort()
    result, cursor = [], 0
    for start, end, kind in positions:
        result.append(esc(value[cursor:start]))
        css = "subject-person" if kind == "person" else "subject-entity"
        result.append(f'<mark class="subject-mention {css}">{esc(value[start:end])}</mark>')
        cursor = end
    result.append(esc(value[cursor:]))
    return ''.join(result)


def render_article(item) -> str:
    topics = item["topics"]
    topic_rows = [{
        "topic_id": f'category-{topics["primary"]["category_id"]}',
        "name": topics["primary"]["category_name"],
    }, *topics["secondary"]]
    context = f'''<details class="article-context"><summary class="article-context-summary"><span><span class="eyebrow">原文结构化提取</span><strong>报道标记</strong></span><span class="context-toggle"><i class="when-closed">展开</i><i class="when-open">收起</i></span></summary>
<div class="context-groups"><section class="context-group context-subjects"><h3>主体 <span>{len(item["subjects"])}</span></h3><ul class="context-subject-list">{''.join(_subject_link(row) for row in item["subjects"]) or '<li>无</li>'}</ul></section>
<section class="context-group"><h3>事件 <span>{len(item["events"])}</span></h3><ul class="context-name-list">{_named_links(item["events"], "events", "event_id") or '<li>无</li>'}</ul></section>
<section class="context-group"><h3>地点 <span>{len(item["locations"])}</span></h3><ul class="context-token-list">{_named_links(item["locations"], "regions", "location_id") or '<li>无</li>'}</ul></section>
<section class="context-group"><h3>主题 <span>{len(topic_rows)}</span></h3><ul class="context-token-list">{_named_links(topic_rows, "topics", "topic_id")}</ul></section>
<section class="context-group context-plans"><h3>规划 <span>{len(item["plans"])}</span></h3><ul class="context-name-list">{_named_links(item["plans"], "plans", "plan_id") or '<li>无</li>'}</ul></section></div></details>'''
    short, label = SCOPE_LABELS[item["scope"]]
    paragraphs = ''.join(
        f'<p>{_highlight_paragraph(paragraph, item["subjects"])}</p>'
        for paragraph in item["block"]["content"].split("\n\n") if paragraph.strip()
    )
    lead_note = ''
    if item["reader_leads"]:
        lead_note = f'<p class="reader-inline-note"><a href="/reminders/">这篇报道含 {len(item["reader_leads"])} 条读者提醒 →</a></p>'
    body = f'''<main class="item-page"><p><a href="javascript:history.back()">← 返回</a></p>
<div class="item-meta">{scope_badge(item["scope"])}<span>{esc(label)} · {date_cn(item["published_date"])} · {esc(item["page_name"])}</span></div>
<h1>{esc(item["block"]["title"])}</h1><section class="ai-summary"><span class="eyebrow">AI 摘要</span><p>{esc(item["block"]["ai_summary"] or "暂无摘要")}</p></section>
{context}{lead_note}<article class="source-body">{paragraphs}</article>
<p><a class="source-link" href="{esc(item["block"]["original_url"])}">在海南日报查看原文</a></p></main>'''
    return page(item["block"]["title"], body)


def directory_card(path: str, name: str, count: int, meta: str = "") -> str:
    return f'<a class="knowledge-card" href="{esc(path)}"><div><h2>{esc(name)}</h2><p>{esc(meta)}</p></div><span class="knowledge-card-count"><strong>{count}</strong> 篇</span></a>'


def render_subjects(index) -> str:
    groups = [("person", "人物"), ("company", "企业"), ("organization", "机构")]
    chunks = []
    for kind, label in groups:
        rows = [row for row in index["items"] if row["type"] == kind]
        cards = ''.join(
            directory_card(
                row["detail_path"], row["name"], row["article_count"],
                f'{row["activity_count"]} 项动作',
            )
            for row in rows
        )
        content = f'<div class="knowledge-grid">{cards}</div>' if rows else '<p class="empty-state">暂无主体。</p>'
        chunks.append(
            f'<section class="subject-directory-group"><header><h2>{label}</h2>'
            f'<span>{len(rows)} 个主体</span></header>{content}</section>'
        )
    body = '<main class="content-shell knowledge-page">' + header(
        "从首次 JSON 生长", "按主体看海南", "人物、企业、机构分别按入站报道数量排序"
    ) + ''.join(chunks) + '</main>'
    return page("按主体看海南", body, "subjects")


def render_subject(feed) -> str:
    subject = feed["subject"]
    activities = []
    for activity in feed["activities"]:
        detail = ''
        if activity.get("detail"):
            label = {"goal": "目标", "result": "结果", "object": "对象"}[activity["detail_kind"]]
            detail = f'<p class="activity-detail"><strong>{label}</strong> {esc(activity["detail"])}</p>'
        source = activity["source"]
        activities.append(f'''<article class="activity-card"><time>{esc(activity.get("occurred_on") or source["published_date"])}</time><div><h2>{esc(activity["headline"])}</h2>{detail}
<p>{esc(activity.get("place", ""))}</p><a href="{esc(source["detail_path"])}">来源：{esc(source["source_title"])} →</a><blockquote>{esc(source["evidence"])}</blockquote></div></article>''')
    body = '<main class="content-shell knowledge-page">' + header(
        f'{SUBJECT_LABELS[subject["type"]]} · {subject["first_seen"]} 起入站',
        subject["canonical_name"], f'{len(feed["activities"])} 项动作 · {len(feed["articles"])} 篇来源报道'
    ) + '<section class="activity-list">' + (''.join(activities) or '<p class="empty-state">暂无动作。</p>') + '</section></main>'
    return page(subject["canonical_name"], body, "subjects")


def _geo_paths(region_index) -> str:
    geo = read_json(ROOT / "config/hainan-administrative-divisions.geojson", {"features": []})
    by_code = {row["code"]: row for row in region_index["items"]}
    points = []
    for feature in geo["features"]:
        coordinates = feature["geometry"]["coordinates"]
        polygons = coordinates if feature["geometry"]["type"] == "MultiPolygon" else [coordinates]
        for polygon in polygons:
            for ring in polygon:
                points.extend(ring)
    if not points:
        return ''
    min_x, max_x = min(p[0] for p in points), max(p[0] for p in points)
    min_y, max_y = min(p[1] for p in points), max(p[1] for p in points)
    scale = min(720 / (max_x - min_x), 520 / (max_y - min_y))
    def project(point):
        return ((point[0] - min_x) * scale + 20, (max_y - point[1]) * scale + 20)
    maximum = max((row["article_count"] for row in region_index["items"]), default=0)
    paths = []
    for feature in geo["features"]:
        code = str(feature["properties"]["adcode"])
        region = by_code.get(code)
        if not region:
            continue
        coordinates = feature["geometry"]["coordinates"]
        polygons = coordinates if feature["geometry"]["type"] == "MultiPolygon" else [coordinates]
        commands = []
        for polygon in polygons:
            for ring in polygon:
                projected = [project(point) for point in ring]
                commands.append('M' + ' L'.join(f'{x:.1f},{y:.1f}' for x, y in projected) + ' Z')
        density = 0 if not maximum else min(4, math.ceil(region["article_count"] / maximum * 4))
        paths.append(f'<a href="{esc(region["detail_path"])}"><path class="region-map-shape density-{density}" d="{" ".join(commands)}"><title>{esc(region["name"])} · {region["article_count"]} 篇</title></path></a>')
    return f'<svg viewBox="0 0 760 560" role="img" aria-label="海南各市县入站新闻分布">{"".join(paths)}</svg>'


def render_regions(index) -> str:
    rows = [row for row in index["items"] if row["level"] != "province"]
    cards = ''.join(directory_card(row["detail_path"], row["name"], row["article_count"]) for row in rows)
    body = '<main class="content-shell knowledge-page">' + header(
        "报道地区分类", "按地点看海南", "地图深浅表示入站报道数量"
    ) + f'<section class="region-density"><div class="region-map">{_geo_paths(index)}</div></section><div class="knowledge-grid">{cards}</div></main>'
    return page("按地点看海南", body, "regions")


def render_feed_page(title: str, eyebrow: str, meta: str, articles, active: str) -> str:
    body = '<main class="content-shell knowledge-page">' + header(eyebrow, title, meta) + story_list(articles) + '</main>'
    return page(title, body, active)


def render_topics(index) -> str:
    roots = []
    for root in sorted(index["roots"], key=lambda row: (-row["article_count"], row["name"])):
        roots.append(f'''<article class="topic-root-card"><h2><a href="{esc(root["detail_path"])}">{esc(root["name"])}</a></h2>
<p>{esc(root["definition"])}</p><span>{root["article_count"]} 篇</span></article>''')
    body = '<main class="content-shell knowledge-page">' + header(
        "有限大类 · 自由细主题", "按主题看海南", "首页只显示大类；进入大类后查看具体主题与报道"
    ) + '<div class="knowledge-grid">' + ''.join(roots) + '</div></main>'
    return page("按主题看海南", body, "topics")


def render_topic(feed) -> str:
    topic = feed["topic"]
    children = feed.get("children", [])
    child_html = ''
    if children:
        child_html = '<section class="topic-children"><h2>具体主题</h2><div class="topic-child-links">' + ''.join(
            f'<a href="{esc(row["detail_path"])}">{esc(row["name"])} <span>{row["article_count"]}</span></a>' for row in children
        ) + '</div></section>'
    body = '<main class="content-shell knowledge-page">' + header(
        "主题目录", topic["name"], f'{topic["article_count"]} 篇入站报道'
    ) + child_html + '<h2>相关报道</h2>' + story_list(feed["articles"]) + '</main>'
    return page(topic["name"], body, "topics")


def render_object_directory(index, kind: str, title: str, active: str) -> str:
    cards = ''.join(
        directory_card(row["detail_path"], row["name"], row["article_count"],
                       EVENT_LABELS.get(row.get("event_type"), "") if kind == "事件" else "")
        for row in index["items"]
    )
    body = '<main class="content-shell knowledge-page">' + header(
        "从首次 JSON 聚合", title, f'{len(index["items"])} 个{kind}'
    ) + '<div class="knowledge-grid">' + (cards or '<p class="empty-state">暂无数据。</p>') + '</div></main>'
    return page(title, body, active)


def render_plan(feed) -> str:
    mentions = ''.join(
        f'<article class="activity-card"><time>{esc(row["source"]["published_date"])}</time><div><h2>{esc(PLAN_LABELS[row["mention_type"]])}</h2><a href="{esc(row["source"]["detail_path"])}">{esc(row["source"]["source_title"])} →</a><blockquote>{esc(row["source"]["evidence"])}</blockquote></div></article>'
        for row in feed["mentions"]
    )
    body = '<main class="content-shell knowledge-page">' + header(
        "规划文件", feed["plan"]["name"], f'{len(feed["articles"])} 篇站内报道提及'
    ) + '<p class="knowledge-brief">规划正文与 PDF 可在后续人工维护；本页只聚合首次 JSON 中的站内提及。</p><section class="activity-list">' + mentions + '</section></main>'
    return page(feed["plan"]["name"], body, "plans")


def render_reminders(index) -> str:
    cards = []
    for lead in index["items"]:
        window = lead.get("window", {})
        meta = ' · '.join(value for value in [lead.get("audience"), window.get("text"), lead.get("channel")] if value)
        cards.append(f'''<article class="action-card"><header><div><span class="action-intent">{esc(READER_LABELS[lead["intent"]])}</span><h2>{esc(lead["headline"])}</h2></div></header>
<p>{esc(lead["action"])}</p><p>{esc(meta)}</p><a href="{esc(lead["source"]["detail_path"])}">来源：{esc(lead["source"]["source_title"])} →</a></article>''')
    body = '<main class="content-shell knowledge-page">' + header(
        "AI 替你读完报纸", "读者提醒", f'{index["count"]} 条可行动信息'
    ) + '<div class="action-list">' + (''.join(cards) or '<p class="empty-state">当前没有需要读者行动的提醒。</p>') + '</div></main>'
    return page("读者提醒", body, "reminders")


def render_daily(indexes: Path, reader_index) -> str:
    hnhot = read_json(indexes / "hnhot.json", {"dates": []})
    dates = hnhot.get("dates", [])[:3]
    date_buttons = []
    for index, date_value in enumerate(dates):
        month_day = f"{int(date_value[5:7])}月{int(date_value[8:10])}日"
        label = "今天" if index == 0 else month_day
        active = ' class="active"' if index == 0 else ""
        pressed = "true" if index == 0 else "false"
        date_buttons.append(
            f'<button{active} type="button" aria-pressed="{pressed}" '
            f'data-report-value="{esc(month_day)}">{esc(label)}</button>'
        )
    date_buttons.append(
        '<button type="button" aria-pressed="false" data-report-value="更多">更多</button>'
    )
    latest_label = (
        f"{int(dates[0][5:7])}月{int(dates[0][8:10])}日" if dates else "今天"
    )
    lead_cards = []
    for lead in reader_index.get("items", [])[:3]:
        source = lead["source"]
        lead_cards.append(
            f'<article class="action-card"><span class="action-intent">'
            f'{esc(READER_LABELS[lead["intent"]])}</span><h2>{esc(lead["headline"])}</h2>'
            f'<p>{esc(lead["action"])}</p><a href="{esc(source["detail_path"])}">'
            f'来源：{esc(source["source_title"])} →</a></article>'
        )
    reminders = (
        '<section class="daily-actions"><header><div><span class="eyebrow">读者服务</span>'
        '<h2>近期提醒</h2></div><a href="/reminders/">查看全部</a></header>'
        f'<div class="action-list">{"".join(lead_cards)}</div></section>'
        if lead_cards else
        '<section class="daily-actions"><header><div><span class="eyebrow">读者服务</span>'
        '<h2>近期提醒</h2></div></header><p class="empty-state">当前没有需要额外行动的提醒。</p></section>'
    )
    body = (
        '<main class="content-shell simple-page">'
        + header("海南日报 · 沉淀", "日报")
        + f'<section class="report-browser" data-report-browser data-report-period="日报" '
        f'data-report-date="{esc(latest_label)}"><nav class="report-period-tabs" '
        'aria-label="报告周期" data-report-control="period">'
        '<button class="active" type="button" aria-pressed="true" data-report-value="日报">日报</button>'
        '<button type="button" aria-pressed="false" data-report-value="周报">周报</button>'
        '<button type="button" aria-pressed="false" data-report-value="月报">月报</button></nav>'
        '<nav class="report-date-tabs" aria-label="报告日期" data-report-control="date" data-report-date-tabs>'
        f'{"".join(date_buttons)}</nav><section class="report-development" aria-live="polite">'
        f'<span class="eyebrow" data-report-selection>日报 · {esc(latest_label)}</span>'
        '<h2 data-report-title>日报能力正在建设</h2>'
        '<p>这里将综合整份报纸，生成可回顾、可积累的内容，而不是另一份标题列表。</p>'
        f'</section></section>{reminders}</main>'
    )
    return page("日报", body, "daily")


def render_more() -> str:
    links = [
        ("/subjects/", "按主体看海南", "人物、企业和机构的长期信息入口"),
        ("/regions/", "按地点看海南", "从海南行政区热力图查看入站报道"),
        ("/topics/", "按主题看海南", "按有限大类进入自然增长的细主题"),
        ("/events/", "大型活动与事件", "聚合命名事件和周期活动"),
        ("/plans/", "规划文件", "聚合报道中明确提到的规划"),
        ("/reminders/", "读者提醒", "申请、报名、查询、避险等可行动消息"),
        ("/about/", "关于 HNHOT", "查看字段边界、版本和运行说明"),
    ]
    body = '<main class="content-shell simple-page">' + header("探索与服务", "更多") + '<div class="more-grid">' + ''.join(
        f'<a class="more-card" href="{href}"><strong>{label}</strong><span>{desc}</span></a>' for href, label, desc in links
    ) + '</div></main>'
    return page("更多", body, "more")


def render_about() -> str:
    body = '<main class="content-shell simple-page">' + header("海南日报信息雷达", "关于 HNHOT") + '''<section class="knowledge-brief"><p>当前所有页面只消费 schema 13 的首次 JSON。主体动作保存在 subjects.activities；地区只使用有限行政区；主题由有限大类和自由细主题组成；事件、规划和读者提醒各自聚合。提示词版本不会产生一套复制的前端，正式历史由 Git 保存。</p></section></main>'''
    return page("关于 HNHOT", body, "about")


def validate_internal_links(site_root: Path) -> None:
    import re
    for path in site_root.rglob("*.html"):
        text = path.read_text(encoding="utf-8")
        for href in re.findall(r'href="(/[^"]*)"', text):
            route = href.split("#", 1)[0].split("?", 1)[0]
            if not route or route.startswith("/static/"):
                continue
            target = site_root / route.lstrip("/")
            if route.endswith("/"):
                target = target / "index.html"
            if not target.exists():
                raise ValueError(f"broken internal link in {path}: {href}")


def build_site(content_root: Path, site_root: Path) -> None:
    content_root, site_root = Path(content_root), Path(site_root)
    if site_root.exists():
        shutil.rmtree(site_root)
    (site_root / "static").mkdir(parents=True)
    for asset in ("styles.css", "app.js"):
        shutil.copy2(ROOT / "src/static" / asset, site_root / "static" / asset)
    indexes = content_root / "indexes"
    if indexes.exists():
        shutil.copytree(indexes, site_root / "static", dirs_exist_ok=True)

    write_page(site_root, "/", render_home(indexes))
    for scope in SCOPE_LABELS:
        write_page(site_root, f"/front-page/{scope}/", render_home(indexes, scope))
    write_page(site_root, "/all/", render_archive(indexes))
    for path in sorted((indexes / "issue-feed").glob("*.json")) if indexes.exists() else []:
        feed = read_json(path)
        write_page(site_root, f'/all/{feed["date"]}/', render_issue(feed))
    for path in sorted((content_root / "issue-items").glob("*/*.json")):
        item = read_json(path)
        write_page(
            site_root, f'/items/{item["published_date"]}/{item["item_id"]}/', render_article(item)
        )

    subjects = read_json(indexes / "subjects.json", {"items": []})
    write_page(site_root, "/subjects/", render_subjects(subjects))
    for row in subjects["items"]:
        feed = read_json(indexes / "subject-feed" / f'{row["subject_id"]}.json')
        write_page(site_root, row["detail_path"], render_subject(feed))

    regions = read_json(indexes / "regions.json", {"items": []})
    write_page(site_root, "/regions/", render_regions(regions))
    for row in regions["items"]:
        feed = read_json(indexes / "region-feed" / f'{row["location_id"]}.json')
        write_page(site_root, row["detail_path"], render_feed_page(
            row["name"], "报道地区", f'{row["article_count"]} 篇入站报道', feed["articles"], "regions"
        ))

    topics = read_json(indexes / "topics.json", {"roots": [], "nodes": []})
    write_page(site_root, "/topics/", render_topics(topics))
    for row in topics["nodes"]:
        feed = read_json(indexes / "topic-feed" / f'{row["topic_id"]}.json')
        write_page(site_root, row["detail_path"], render_topic(feed))

    events = read_json(indexes / "events.json", {"items": []})
    write_page(site_root, "/events/", render_object_directory(events, "事件", "大型活动与事件", "events"))
    for row in events["items"]:
        feed = read_json(indexes / "event-feed" / f'{row["event_id"]}.json')
        write_page(site_root, row["detail_path"], render_feed_page(
            row["name"], EVENT_LABELS.get(row["event_type"], "事件"),
            f'{row["article_count"]} 篇入站报道', feed["articles"], "events"
        ))

    plans = read_json(indexes / "plans.json", {"items": []})
    write_page(site_root, "/plans/", render_object_directory(plans, "规划", "规划文件", "plans"))
    for row in plans["items"]:
        feed = read_json(indexes / "plan-feed" / f'{row["plan_id"]}.json')
        write_page(site_root, row["detail_path"], render_plan(feed))

    reader = read_json(indexes / "reader-leads.json", {"count": 0, "items": []})
    write_page(site_root, "/daily/", render_daily(indexes, reader))
    write_page(site_root, "/reminders/", render_reminders(reader))
    write_page(site_root, "/more/", render_more())
    write_page(site_root, "/about/", render_about())
    validate_internal_links(site_root)


def main(argv):
    if len(argv) != 3:
        print("Usage: radar_render.py CONTENT_ROOT SITE_ROOT", file=sys.stderr)
        return 1
    try:
        build_site(Path(argv[1]), Path(argv[2]))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
