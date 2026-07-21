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
from string import Template
from urllib.parse import urlparse

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.radar_indexes import build_hnhot_indexes, public_topics
from scripts.radar_issue import validate_public_issue, validate_public_issue_item
from scripts.radar_store import load_issue_items, load_issues
from scripts.radar_topics import load_topic_catalog
from scripts.radar_gold_review import review_inputs_available, write_review_site

ROOT = Path(__file__).resolve().parents[1]
PRODUCT_NAME = "HNHOT"
SCOPE_LABELS = {
    "national": "N", "hainan": "H", "domestic": "D", "mixed": "M", "foreign": "F",
}
SCOPE_NAMES = {
    None: "全部", "hainan": "H · 海南本地", "domestic": "D · 国内关联",
    "mixed": "M · 海南开放", "national": "N · 全国", "foreign": "F · 全球",
}
SCOPE_DESCRIPTIONS = {
    "hainan": "海南本地生活、产业、治理与建设",
    "domestic": "海南与国内其他地区的直接联系",
    "mixed": "海南涉外、跨境与开放信息",
    "national": "无海南直接参与的国内信息",
    "foreign": "无海南直接参与的全球信息",
}
SCOPE_PATHS = {
    None: "/", "hainan": "/front-page/hainan/",
    "domestic": "/front-page/domestic/", "mixed": "/front-page/mixed/",
    "national": "/front-page/national/",
    "foreign": "/front-page/global/",
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


def _subject_occurrence_counts(paragraphs, variant_to_subject):
    variants = sorted(variant_to_subject, key=lambda name: (-len(name), name))
    counts = {name: 0 for name in set(variant_to_subject.values())}
    if not variants:
        return counts
    pattern = re.compile("|".join(re.escape(name) for name in variants))
    for paragraph in paragraphs:
        for match in pattern.finditer(paragraph):
            counts[variant_to_subject[match.group(0)]] += 1
    return counts


def _highlight_subjects(
    value, variant_to_subject, subject_anchors, subject_types, anchored_subjects
):
    variants = sorted(variant_to_subject, key=lambda name: (-len(name), name))
    if not variants:
        return _esc(value)
    pattern = re.compile("|".join(re.escape(name) for name in variants))
    fragments = []
    cursor = 0
    for match in pattern.finditer(value):
        fragments.append(_esc(value[cursor:match.start()]))
        matched_text = match.group(0)
        subject_name = variant_to_subject[matched_text]
        anchor_markup = ""
        if subject_name not in anchored_subjects:
            anchor_markup = f' id="{_esc(subject_anchors[subject_name], True)}"'
            anchored_subjects.add(subject_name)
        if subject_types.get(subject_name) == "person":
            fragments.append(
                f'<strong class="subject-mention subject-person" '
                f'data-subject-id="{_esc(subject_anchors[subject_name], True)}"{anchor_markup}>'
                f'{_esc(matched_text)}</strong>'
            )
        else:
            fragments.append(
                f'<span class="subject-mention subject-entity" '
                f'data-subject-id="{_esc(subject_anchors[subject_name], True)}"{anchor_markup}>'
                f'{_esc(matched_text)}</span>'
            )
        cursor = match.end()
    fragments.append(_esc(value[cursor:]))
    return "".join(fragments)


def _location_group_count(rows):
    specific_rows = [row for row in rows if row.get("level") != "province"]
    return len(specific_rows) if specific_rows else len(rows)


def render_base(title, body):
    template = Template(
        (ROOT / "src/templates/base.html").read_text(encoding="utf-8")
    )
    return template.substitute(title=_esc(title), body=body)


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


def _scope_badge(scope):
    badge = SCOPE_LABELS.get(scope, "–")
    label = SCOPE_NAMES.get(scope, "尚未分类")
    return (
        f'<span class="scope-badge scope-{_esc(scope or "pending", True)}" '
        f'title="{_esc(label, True)}" aria-label="{_esc(label, True)}">{badge}</span>'
    )


def _story_card(item, rank=None, searchable=True):
    scope = item.get("scope")
    summary = item.get("ai_summary") or "该报道暂无结构化摘要。"
    rank_markup = f'<span class="ranking-number">{rank}</span>' if rank is not None else ""
    search_text = item.get("search_text") or " ".join((item["title"], summary, scope or ""))
    search_attrs = (
        f' data-search-card data-search-text="{_esc(search_text, True)}"'
        if searchable else ""
    )
    return (
        f'<article class="story-card"{search_attrs}>'
        f'{rank_markup}{_scope_badge(scope)}'
        f'<a class="story-copy" href="{_esc(item["detail_path"], True)}">'
        f'<h3>{_esc(item["title"])}</h3><p>{_esc(summary)}</p>'
        f'<div class="story-meta"></div></a>{_bookmark_button(item)}</article>'
    )


def _scope_tabs(active_scope):
    rows = []
    for scope, path in SCOPE_PATHS.items():
        current = ' class="active" aria-current="page"' if scope == active_scope else ""
        rows.append(f'<a href="{path}"{current}>{SCOPE_NAMES[scope]}</a>')
    return "".join(rows)


def _ranking_panel(kind, eyebrow, title, items, empty_text):
    ranking_rows = "".join(_story_card(item, item["rank"]) for item in items)
    content = (
        f'<div class="ranking-list">{ranking_rows}</div>'
        if items else f'<p class="ranking-empty">{_esc(empty_text)}</p>'
    )
    empty_class = " is-empty" if not items else ""
    return (
        f'<section class="national-ranking ranking-panel ranking-{kind}{empty_class}">'
        f'<header><div><span class="eyebrow">{_esc(eyebrow)}</span>'
        f'<h2>{_esc(title)}</h2></div><span>TOP {len(items)}</span></header>{content}</section>'
    )


def render_front_page(feeds, active_scope=None):
    latest_date = feeds[0]["date"] if feeds else None
    latest_feed = feeds[0] if feeds else {}
    ranking = "" if active_scope is not None else (
        '<div class="ranking-dashboard">'
        + _ranking_panel(
            "domestic", "国内头版", "全国要闻",
            latest_feed.get("national_ranking", []), "今日暂无国内头版要闻",
        )
        + _ranking_panel(
            "world", "世界新闻", "全球要闻",
            latest_feed.get("world_ranking", []), "今日暂无世界新闻",
        )
        + '</div>'
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
    empty = '<p class="empty-state">这个分类暂时没有可显示的报道。</p>' if not groups else ""
    date_text = f'{_date_label(latest_date)} · {_weekday(latest_date)}' if latest_date else "暂无报纸"
    return (
        '<div class="app-shell radar-shell">'
        f'{render_primary_nav("头版", date_text)}'
        '<main class="content-shell front-page">'
        '<header class="page-header"><div><span class="eyebrow">海南日报 · 要闻</span>'
        '<h1>头版</h1></div>'
        '<label class="site-search"><span class="sr-only">搜索今日要闻</span>'
        '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="6"/><path d="m16 16 4 4"/></svg>'
        '<input type="search" data-search-input placeholder="搜索标题或摘要"></label></header>'
        f'<nav class="scope-tabs" aria-label="今日要闻分类">{_scope_tabs(active_scope)}</nav>'
        f'{ranking}<div data-search-scope>{"".join(groups)}{empty}</div>'
        '<p class="empty-state" data-search-empty hidden>没有匹配结果</p></main></div>'
    )


def render_issue(issue, articles=None):
    validate_public_issue(issue)
    issue_meta = f'{_date_label(issue["date"])} · {_weekday(issue["date"])}'
    article_by_id = {
        article["item_id"]: article for article in (articles or [])
        if article["published_date"] == issue["date"]
    }
    page_by_number = {page["page_number"]: page for page in issue["pages"]}
    tabs = ['<a class="active" href="#issue-start" aria-current="page">全部</a>']
    tabs.extend(
        f'<a href="#section-{_esc(section["section_id"], True)}">'
        f'{_esc(section["name"])}<span>{len(section["articles"])}</span></a>'
        for section in issue["sections"]
        if section["articles"]
    )
    sections = []
    for section in issue["sections"]:
        if not section["articles"]:
            continue
        story_rows = []
        for row in section["articles"]:
            article = article_by_id.get(row["item_id"])
            if article is None:
                story = {
                    "item_id": row["item_id"],
                    "title": row["title"],
                    "ai_summary": None,
                    "scope": "pending",
                    "detail_path": row["detail_path"],
                }
            else:
                story = _archive_story(article)
            story_rows.append(_story_card(story, searchable=False))
        pdf_links = []
        for page_number in section["source_pages"]:
            page = page_by_number.get(page_number)
            if page and page.get("pdf_url"):
                pdf_links.append(
                    page["pdf_url"]
                )
        if len(pdf_links) == 1:
            pdf_markup = (
                f'<a class="section-pdf-link" href="{_esc(pdf_links[0], True)}" '
                f'target="_blank" rel="noopener noreferrer" '
                f'aria-label="打开{_esc(section["name"], True)} PDF">PDF</a>'
            )
        elif pdf_links:
            pdf_items = "".join(
                f'<a href="{_esc(pdf_url, True)}" target="_blank" rel="noopener noreferrer">第{index}份</a>'
                for index, pdf_url in enumerate(pdf_links, start=1)
            )
            pdf_markup = (
                '<details class="section-pdf-menu">'
                f'<summary>PDF · {len(pdf_links)}</summary><div>{pdf_items}</div></details>'
            )
        else:
            pdf_markup = ""
        sections.append(
            f'<section class="logical-section issue-section" id="section-{_esc(section["section_id"], True)}">'
            f'<header><h2>{_esc(section["name"])}</h2><div class="issue-section-meta">'
            f'<span>{len(section["articles"])} 篇</span>{pdf_markup}</div></header>'
            f'<div class="story-list issue-story-list">{"".join(story_rows)}</div></section>'
        )
    return (
        '<div class="app-shell radar-shell">'
        f'{render_primary_nav("全部", issue_meta)}'
        '<main class="content-shell all-page issue-page" id="issue-start">'
        '<header class="page-header"><div><span class="eyebrow">海南日报 · 本期内容</span>'
        f'<h1>{_date_label(issue["date"])}</h1><p>{_weekday(issue["date"])} · {issue["article_count"]} 篇</p></div></header>'
        f'<nav class="scope-tabs issue-section-tabs" aria-label="本期版面">{"".join(tabs)}</nav>'
        f'<div>{"".join(sections)}</div>'
        '<a class="back-to-top" data-back-to-top href="#issue-start" hidden>返回顶部</a>'
        '</main></div>'
    )


def _archive_story(article):
    block = article["block"]
    detail_path = f'/items/{article["published_date"]}/{article["item_id"]}/'
    search_terms = [
        block["title"], block.get("ai_summary") or "", article["published_date"],
        article["page_name"],
        *[row["name"] for row in article["subjects"]],
        *[
            alias["name"]
            for row in article["subjects"]
            for alias in row.get("aliases", [])
        ],
        *[row["name"] for row in article["locations"]],
        *[row["name"] for row in public_topics(article)],
        *[row["name"] for row in article.get("events", [])],
        *[row["name"] for row in article.get("plans", [])],
    ]
    return {
        "item_id": article["item_id"],
        "published_date": article["published_date"],
        "page_number": article["page_number"],
        "page_sequence": article["page_sequence"],
        "title": block["title"],
        "ai_summary": block.get("ai_summary"),
        "scope": article["scope"],
        "detail_path": detail_path,
        "search_text": " ".join(search_terms),
    }


def _archive_catalog(issues, articles):
    issue_rows = sorted(issues, key=lambda row: row["date"], reverse=True)
    article_by_id = {article["item_id"]: article for article in articles}
    sections = []
    section_by_id = {}
    for issue in issue_rows:
        for section in issue["sections"]:
            item_ids = [
                row["item_id"] for row in section["articles"]
                if row["item_id"] in article_by_id
            ]
            if not item_ids:
                continue
            entry = section_by_id.get(section["section_id"])
            if entry is None:
                entry = {
                    "section_id": section["section_id"],
                    "name": section["name"],
                    "item_ids": [],
                }
                sections.append(entry)
                section_by_id[section["section_id"]] = entry
            for item_id in item_ids:
                if item_id not in entry["item_ids"]:
                    entry["item_ids"].append(item_id)
    stories = [_archive_story(article) for article in articles]
    stories.sort(
        key=lambda row: (row["page_number"], row["page_sequence"], row["item_id"])
    )
    stories.sort(key=lambda row: row["published_date"], reverse=True)
    return issue_rows, stories, sections, article_by_id


def _archive_tabs(sections, active_section_id):
    rows = [
        '<a href="/all/"'
        + (' class="active" aria-current="page"' if active_section_id is None else "")
        + '>全部</a>'
    ]
    for section in sections:
        current = (
            ' class="active" aria-current="page"'
            if section["section_id"] == active_section_id else ""
        )
        rows.append(
            f'<a href="/all/sections/{_esc(section["section_id"], True)}/"{current}>'
            f'{_esc(section["name"])}<span>{len(section["item_ids"])}</span></a>'
        )
    return "".join(rows)


def _archive_date_groups(stories):
    groups = []
    dates = sorted({row["published_date"] for row in stories}, reverse=True)
    for published_date in dates:
        items = [row for row in stories if row["published_date"] == published_date]
        groups.append(
            f'<section class="date-group"><header><h2>{_date_label(published_date)}</h2>'
            f'<span>{_weekday(published_date)} · {len(items)} 条</span></header>'
            f'<div class="story-list">{"".join(_story_card(item) for item in items)}</div></section>'
        )
    return "".join(groups)


def render_archive(issues, articles, active_section_id=None):
    issue_rows, stories, sections, article_by_id = _archive_catalog(issues, articles)
    latest_date = issue_rows[0]["date"]
    mobile_meta = f'{_date_label(latest_date)} · {_weekday(latest_date)}'
    active_section = next(
        (row for row in sections if row["section_id"] == active_section_id), None
    )
    if active_section_id is not None and active_section is None:
        raise ValueError(f"unknown archive section: {active_section_id}")

    tabs = _archive_tabs(sections, active_section_id)
    if active_section is not None:
        selected_ids = set(active_section["item_ids"])
        selected = [row for row in stories if row["item_id"] in selected_ids]
        content = (
            '<section class="archive-results-heading">'
            f'<h2>{_esc(active_section["name"])}</h2><span>{len(selected)} 条历史信息</span></section>'
            f'<div data-archive-search-results data-search-scope>{_archive_date_groups(selected)}</div>'
        )
        header_meta = f'{active_section["name"]} · {len(selected)} 条'
    else:
        issue_cards = []
        for issue in issue_rows:
            preview = [
                _archive_story(article_by_id[item_id])
                for item_id in issue["front_page_item_ids"][:3]
                if item_id in article_by_id
            ]
            issue_cards.append(
                '<section class="archive-issue">'
                '<header><div>'
                f'<h3>{_date_label(issue["date"])}</h3><span>{_weekday(issue["date"])}</span>'
                f'</div><span>{issue["article_count"]} 篇 · {issue["page_count"]} 版</span></header>'
                f'<div class="story-list archive-preview">{"".join(_story_card(item, searchable=False) for item in preview)}</div>'
                f'<a class="archive-issue-link" href="/all/{issue["date"]}/">查看本期全部 {issue["article_count"]} 篇</a>'
                '</section>'
            )
        content = (
            '<div data-archive-default>'
            '<section class="archive-overview"><header class="archive-results-heading">'
            '<h2>最近入库</h2><span>按日期查看整期</span></header>'
            f'<div class="archive-issues">{"".join(issue_cards)}</div></section></div>'
            '<div data-archive-search-results data-search-scope '
            'data-search-source="/static/data/search-articles.json" hidden></div>'
            '<p class="archive-search-note" data-archive-search-note hidden></p>'
        )
        header_meta = f'{len(issue_rows)} 期 · {len(stories)} 条已入库'

    return (
        '<div class="app-shell radar-shell">'
        f'{render_primary_nav("全部", mobile_meta)}'
        '<main class="content-shell all-page archive-page">'
        '<header class="page-header"><div><span class="eyebrow">海南日报</span>'
        f'<h1>报库</h1><p>{_esc(header_meta)}</p></div>'
        '<label class="site-search"><span class="sr-only">搜索历史报道</span>'
        '<input type="search" data-search-input '
        'placeholder="搜索标题、摘要或已提取的人物、地点、主题、事件、规划"></label></header>'
        '<section class="archive-section-picker"><header class="archive-results-heading">'
        '<h2>按版面查看</h2><span>由报纸编辑维护</span></header>'
        f'<nav class="scope-tabs archive-tabs" aria-label="按版面筛选">{tabs}</nav></section>'
        f'{content}<p class="empty-state" data-search-empty hidden>没有匹配结果</p>'
        '</main></div>'
    )


def render_item(item):
    validate_public_issue_item(item)
    block = item["block"]
    summary = block.get("ai_summary") or "该报道暂无结构化摘要。"
    paragraphs = [
        part.strip() for part in re.split(r"\n\s*\n", block["content"].replace("\r\n", "\n")) if part.strip()
    ]
    type_labels = {
        "person": "人物",
        "government": "政府机构",
        "organization": "组织机构",
        "company": "企业",
        "project": "项目",
    }
    subject_type_order = {
        "government": 0,
        "organization": 1,
        "company": 2,
        "project": 3,
        "person": 4,
    }
    variant_to_subject = {}
    for row in item["subjects"]:
        variant_to_subject[row["name"]] = row["name"]
        for alias in row.get("aliases", []):
            variant_to_subject[alias["name"]] = row["name"]
    subject_counts = _subject_occurrence_counts(paragraphs, variant_to_subject)
    subject_anchors = {
        row["name"]: f"subject-{index}"
        for index, row in enumerate(item["subjects"], start=1)
        if subject_counts.get(row["name"], 0) > 0
    }
    subject_types = {row["name"]: row["type"] for row in item["subjects"]}
    context_groups = []
    if item["subjects"]:
        ordered_subjects = sorted(
            item["subjects"], key=lambda row: subject_type_order.get(row["type"], 9)
        )
        subject_rows = []
        for row in ordered_subjects:
            label = (
                '<strong>' + _esc(row["name"]) + '</strong><span>'
                + _esc(type_labels.get(row["type"], row["type"]))
                + (f' · {_esc(row["role"])}' if row.get("role") else "")
                + '</span>'
            )
            if row["name"] in subject_anchors:
                anchor = _esc(subject_anchors[row["name"]], True)
                subject_rows.append(
                    '<li><a class="context-subject-link" '
                    f'href="#{anchor}" data-subject-link data-subject-id="{anchor}" '
                    f'aria-label="{_esc(row["name"], True)}：高亮正文中的全部出现位置">'
                    f'{label}<small class="context-subject-count">正文 '
                    f'{subject_counts[row["name"]]} 处 ↓</small></a></li>'
                )
            else:
                subject_rows.append(
                    f'<li><div class="context-subject-static">{label}</div></li>'
                )
        context_groups.append(
            '<section class="context-group context-subjects">'
            f'<h3>主体 <span>{len(item["subjects"])}</span></h3>'
            f'<ul class="context-subject-list">{"".join(subject_rows)}</ul></section>'
        )
    location_level_order = {"province": 0, "prefecture": 1, "county": 2}
    for key, label, class_name in (
        ("events", "事件", "context-name-list"),
        ("plans", "规划文件", "context-name-list context-plans"),
        ("locations", "地点", "context-token-list"),
        ("topics", "主题", "context-token-list"),
    ):
        rows = public_topics(item) if key == "topics" else item.get(key, [])
        if key == "locations":
            rows = sorted(
                rows,
                key=lambda row: (location_level_order.get(row.get("level"), 9), row.get("code", "")),
            )
        if not rows:
            continue
        values = "".join(f'<li>{_esc(row["name"])}</li>' for row in rows)
        context_groups.append(
            f'<section class="context-group context-{key}"><h3>{label} '
            f'<span>{_location_group_count(rows) if key == "locations" else len(rows)}</span>'
            f'</h3><ul class="{class_name}">{values}</ul></section>'
        )
    context_markup = (
        '<details class="article-context">'
        '<summary class="article-context-summary"><span>'
        '<span class="eyebrow">原文结构化提取</span>'
        '<span class="article-context-title">报道标记</span></span>'
        '<span class="context-toggle"><span class="when-closed">展开</span>'
        '<span class="when-open">收起</span></span></summary>'
        f'<div class="context-groups">{"".join(context_groups)}</div></details>'
        if context_groups else ""
    )
    anchored_subjects = set()
    source_body = "".join(
        f'<p>{_highlight_subjects(part, variant_to_subject, subject_anchors, subject_types, anchored_subjects)}</p>'
        for part in paragraphs
    )
    return (
        '<div class="app-shell radar-shell item-shell">'
        f'{render_primary_nav("全部", _date_label(item["published_date"]))}'
        '<main class="item-page"><a class="back-link" href="javascript:history.back()">← 返回</a>'
        f'<div class="item-meta">{_scope_badge(item["scope"])}'
        f'<span>{_esc(item["page_name"])} · {_date_label(item["published_date"])}</span></div>'
        f'<h1>{_esc(block["title"])}</h1>'
        f'<section class="ai-summary"><span class="eyebrow">AI 摘要</span><p>{_esc(summary)}</p></section>'
        f'{context_markup}'
        f'<article class="source-body">{source_body}</article>'
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


def _scope_guide():
    guide_rows = "".join(
        '<div class="scope-guide-row">'
        f'{_scope_badge(scope)}<div><strong>{_esc(SCOPE_NAMES[scope].split(" · ", 1)[1])}</strong>'
        f'<p>{_esc(SCOPE_DESCRIPTIONS[scope])}</p></div></div>'
        for scope in ("hainan", "domestic", "mixed", "national", "foreign")
    )
    guide = (
        '<section class="scope-guide" aria-labelledby="scope-guide-title">'
        '<header><span class="eyebrow">阅读范围</span><h2 id="scope-guide-title">分类说明</h2></header>'
        f'<div class="scope-guide-list">{guide_rows}</div></section>'
    )
    return guide


def _more_page():
    cards = (
        '<a class="more-card" href="/starred/"><strong>收藏</strong><span>留住值得反复阅读的报道</span></a>'
        '<a class="more-card" href="/subjects/"><strong>按主体看海南</strong><span>人物、机构、企业与项目的连续报道</span></a>'
        '<a class="more-card" href="/regions/"><strong>按地区看海南</strong><span>沿行政区积累地区记忆</span></a>'
        '<a class="more-card" href="/topics/"><strong>按主题看海南</strong><span>从准确议题进入海南的长期脉络</span></a>'
        '<a class="more-card" href="/about/"><strong>关于 HNHOT</strong><span>产品方法与数据边界</span></a>'
    )
    return _simple_page(
        "更多", "沉淀海南记忆", "更多",
        f'<div class="more-grid">{cards}</div>{_scope_guide()}',
    )


def render_topics_index(topic_index):
    cards = []
    for root in topic_index.get("roots", []):
        children = [row for row in root.get("children", []) if row["article_count"]]
        child_links = "".join(
            f'<a href="{_esc(row["detail_path"], True)}">{_esc(row["name"])}'
            f'<span>{row["article_count"]}</span></a>'
            for row in children
        )
        cards.append(
            '<section class="archive-issue topic-root-card"><header><div>'
            f'<h2><a href="{_esc(root["detail_path"], True)}">{_esc(root["name"])}</a></h2>'
            f'</div><span>{root["article_count"]} 篇</span></header>'
            f'<div class="topic-child-links">{child_links}</div></section>'
        )
    body = (
        '<div class="app-shell radar-shell">'
        f'{render_primary_nav("更多")}<main class="content-shell all-page archive-page">'
        '<header class="page-header"><div><span class="eyebrow">长期主题目录</span>'
        '<h1>按主题看海南</h1><p>只收录海南本地及有海南主体直接参与的报道</p></div></header>'
        f'<div class="archive-issues">{"".join(cards)}</div></main></div>'
    )
    return body


def render_topic_page(feed):
    primary = feed.get("primary_items", [])
    secondary = feed.get("secondary_items", [])
    sections = []
    if primary:
        sections.append(
            '<section class="date-group"><header><h2>核心相关</h2>'
            f'<span>{len(primary)} 篇</span></header><div class="story-list">'
            f'{"".join(_story_card(row) for row in primary)}</div></section>'
        )
    if secondary:
        sections.append(
            '<section class="date-group"><header><h2>延伸相关</h2>'
            f'<span>{len(secondary)} 篇</span></header><div class="story-list">'
            f'{"".join(_story_card(row) for row in secondary)}</div></section>'
        )
    if not sections:
        sections.append(
            '<p class="empty-state topic-empty">这个主题目前还没有海南相关报道。</p>'
        )
    return (
        '<div class="app-shell radar-shell">'
        f'{render_primary_nav("更多")}<main class="content-shell all-page">'
        '<a class="back-link" href="/topics/">← 全部主题</a>'
        '<header class="page-header"><div><span class="eyebrow">按主题看海南</span>'
        f'<h1>{_esc(feed["name"])}</h1><p>{_esc(feed["definition"])}</p></div></header>'
        f'{"".join(sections)}</main></div>'
    )


def _starred_page(catalog):
    payload = json.dumps(catalog, ensure_ascii=False).replace("<", "\\u003c")
    body = (
        '<div class="story-list" data-starred-list></div>'
        '<p class="empty-state" data-starred-empty>还没有收藏。可在头版报道右侧点按书签。</p>'
        f'<script type="application/json" id="starred-catalog">{payload}</script>'
    )
    return _simple_page("更多", "本机收藏", "收藏", body)


def _daily_page(issues):
    issue_dates = sorted((issue["date"] for issue in issues), reverse=True)
    visible_dates = issue_dates[:3]
    date_buttons = []
    for index, date_value in enumerate(visible_dates):
        month_day = f"{int(date_value[5:7])}月{int(date_value[8:10])}日"
        label = "今天" if index == 0 else month_day
        active = ' class="active"' if index == 0 else ""
        pressed = "true" if index == 0 else "false"
        date_buttons.append(
            f'<button{active} type="button" aria-pressed="{pressed}" '
            f'data-report-value="{_esc(month_day)}">{_esc(label)}</button>'
        )
    date_buttons.append(
        '<button type="button" aria-pressed="false" data-report-value="更多">更多</button>'
    )
    latest_label = (
        f"{int(issue_dates[0][5:7])}月{int(issue_dates[0][8:10])}日"
        if issue_dates else "今天"
    )
    body = (
        f'<section class="report-browser" data-report-browser data-report-period="日报" data-report-date="{_esc(latest_label)}">'
        '<nav class="report-period-tabs" aria-label="报告周期" data-report-control="period">'
        '<button class="active" type="button" aria-pressed="true" data-report-value="日报">日报</button>'
        '<button type="button" aria-pressed="false" data-report-value="周报">周报</button>'
        '<button type="button" aria-pressed="false" data-report-value="月报">月报</button></nav>'
        '<nav class="report-date-tabs" aria-label="报告日期" data-report-control="date" data-report-date-tabs>'
        f'{"".join(date_buttons)}</nav>'
        '<section class="report-development" aria-live="polite">'
        f'<span class="eyebrow" data-report-selection>日报 · {_esc(latest_label)}</span>'
        '<h2 data-report-title>日报能力正在建设</h2>'
        '<p>这里将综合整份报纸，生成可回顾、可积累的内容，而不是另一份标题列表。当前先开放周期与日期浏览结构。</p>'
        '</section></section>'
    )
    return _simple_page("日报", "海南日报 · 沉淀", "日报", body)


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
    indexes = build_hnhot_indexes(issues, articles, load_topic_catalog(content_root))
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
        for scope in ("national", "hainan", "domestic", "mixed", "foreign"):
            route_scope = "global" if scope == "foreign" else scope
            _write(staging / f"front-page/{route_scope}/index.html", render_front_page(feeds, scope))
        for issue in issues:
            _write(staging / f'all/{issue["date"]}/index.html', render_issue(issue, articles))
        _write(staging / "all/index.html", render_archive(issues, articles))
        _, _, archive_sections, _ = _archive_catalog(issues, articles)
        for section in archive_sections:
            _write(
                staging / f'all/sections/{section["section_id"]}/index.html',
                render_archive(issues, articles, section["section_id"]),
            )
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
        _write(staging / "daily/index.html", _daily_page(issues))
        _write(staging / "more/index.html", _more_page())
        topic_index = indexes["topics.json"]
        _write(staging / "topics/index.html", render_topics_index(topic_index))
        for node in topic_index["nodes"]:
            feed = indexes.get(f'topic-feed/{node["topic_id"]}.json')
            if feed is not None:
                _write(
                    staging / f'topics/{node["topic_id"]}/index.html',
                    render_topic_page(feed),
                )
        _write(staging / "starred/index.html", _starred_page(catalog))
        _write(staging / "subjects/index.html", _simple_page(
            "更多", "连续报道", "按主体看海南",
            '<div class="placeholder-panel"><strong>主体档案正在积累</strong><p>后续将按人物、政府机构、组织、企业与项目聚合连续报道和事件时间线。</p></div>',
        ))
        _write(staging / "regions/index.html", _simple_page(
            "更多", "行政区划", "按地区看海南",
            '<div class="placeholder-panel"><strong>地区档案正在积累</strong><p>后续将沿海南行政区呈现报道密度、主体与事件脉络。</p></div>',
        ))
        _write(staging / "about/index.html", _simple_page(
            "更多", "产品说明", "关于 HNHOT",
            '<div class="prose-block"><p>HNHOT 放大海南日报编辑已经做出的版面判断，并把每天的报道连接成对海南的长期理解。</p><p>产品不对新闻重新打分精选；头版来自报纸头版，全部保留每篇有效报道。</p></div>',
        ))
        if review_inputs_available(ROOT):
            write_review_site(ROOT, staging)
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
