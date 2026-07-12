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

from scripts.radar_contract import validate_stored_item
from scripts.radar_issue import validate_public_issue, validate_public_issue_item
from scripts.render_site import render_base, render_weekly

ROOT = Path(__file__).resolve().parents[1]
PRODUCT_NAME = "HN·HOT"
CATEGORY_PATHS = {
    "全部": "/", "机会": "/category/opportunity/",
    "民生": "/category/livelihood/", "产业": "/category/industry/",
    "政策": "/category/policy/", "城市": "/category/city/",
    "观察": "/category/observation/",
}


def _template(name):
    return Template((ROOT / "src/templates" / name).read_text(encoding="utf-8"))


def _title_row(item, rank=None):
    number = "" if rank is None else f'<span class="title-rank">{rank}</span>'
    return (
        f'<a class="title-row" data-search-title="{html.escape(item["title"], quote=True)}" '
        f'href="{html.escape(item["detail_path"], quote=True)}">{number}'
        f'<span>{html.escape(item["title"])}</span></a>'
    )


def _bookmark_button(item):
    return (
        f'<button class="bookmark-button" type="button" aria-label="收藏 {html.escape(item["title"], quote=True)}" '
        f'data-star-id="{html.escape(item["item_id"], quote=True)}" '
        f'data-star-title="{html.escape(item["title"], quote=True)}" '
        f'data-star-summary="{html.escape(item.get("ai_summary", ""), quote=True)}" '
        f'data-star-date="{html.escape(item["published_date"], quote=True)}" '
        f'data-star-path="{html.escape(item["detail_path"], quote=True)}">'
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 3.75A1.75 1.75 0 0 1 7.75 2h8.5A1.75 1.75 0 0 1 18 3.75v17l-6-3.75-6 3.75z"/></svg></button>'
    )


def _selected_row(item, rank=None):
    rank_markup = "" if rank is None else f'<span class="title-rank focus-rank-{rank}">{rank}</span>'
    modifier = " focus-story" if rank is not None else ""
    title = html.escape(item["title"])
    summary = html.escape(item.get("ai_summary", ""))
    reason = html.escape(item.get("recommendation_reason", ""))
    score = item.get("final_score")
    score_label = f"{score:g}" if isinstance(score, (int, float)) else "—"
    search_text = html.escape(
        " ".join((item["title"], item.get("ai_summary", ""), item.get("recommendation_reason", ""))),
        quote=True,
    )
    return (
        f'<article class="selected-story{modifier}" data-selected-id="{html.escape(item["item_id"], quote=True)}" '
        f'data-search-text="{search_text}">'
        f'{rank_markup}<a class="story-main" href="{html.escape(item["detail_path"], quote=True)}">'
        f'<strong class="story-title">{title}</strong>'
        f'<p class="story-summary">{summary}</p>'
        f'<p class="story-reason"><span>推荐理由：</span>{reason}</p></a>'
        f'<div class="story-actions"><span class="story-score" title="最终分">{score_label}</span>'
        f'{_bookmark_button(item)}</div></article>'
    )


def _feed_date_heading(value, count, is_latest=False):
    parsed = date.fromisoformat(value)
    weekdays = ("星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日")
    return (
        '<span class="desktop-feed-date">'
        f'<strong class="current-date">{parsed.month}月{parsed.day}日</strong>'
        f'<span class="current-date-meta">{weekdays[parsed.weekday()]} · {count} 条</span></span>'
        '<span class="mobile-feed-date">'
        + ('<strong class="mobile-date-today">今天</strong>' if is_latest else '')
        + f'<span class="mobile-date-meta">{parsed.month}月{parsed.day}日 周{weekdays[parsed.weekday()][-1]}</span></span>'
    )


def _selected_header_heading(value):
    parsed = date.fromisoformat(value)
    weekdays = ("星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日")
    return (
        '<strong class="selected-title">精选</strong>'
        f'<span class="selected-subtitle">{parsed.year}年{parsed.month}月{parsed.day}日 {weekdays[parsed.weekday()]}</span>'
    )


def _mobile_updated(value):
    if value == "—":
        return "暂无更新"
    parsed = date.fromisoformat(value)
    weekdays = ("一", "二", "三", "四", "五", "六", "日")
    return f'{parsed.month}月{parsed.day}日 · 周{weekdays[parsed.weekday()]}'


NAV_ITEMS = (("精选", "/"), ("全部信息", "/all/"), ("AI 日报", "/daily/"), ("收藏", "/starred/"))
MORE_ITEMS = (("关于", "/about/"), ("更新日志", "/changelog/"))

NAV_ICON_PATHS = {
    "精选": '<path d="m12 3 1.4 4.1L17.5 8.5l-4.1 1.4L12 14l-1.4-4.1-4.1-1.4 4.1-1.4z"/><path d="m18 14 .8 2.2L21 17l-2.2.8L18 20l-.8-2.2L15 17l2.2-.8z"/>',
    "全部信息": '<path d="M8 6h13M8 12h13M8 18h13"/><path d="M3 6h.01M3 12h.01M3 18h.01"/>',
    "AI 日报": '<path d="M6 2h9l4 4v16H6z"/><path d="M14 2v5h5M9 13h6M9 17h4"/>',
    "收藏": '<path d="M6 3.75A1.75 1.75 0 0 1 7.75 2h8.5A1.75 1.75 0 0 1 18 3.75v17l-6-3.75-6 3.75z"/>',
    "关于": '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>',
    "更新日志": '<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5M12 7v5l3 2"/>',
}


def _nav_icon(label):
    paths = NAV_ICON_PATHS[label]
    return f'<svg class="nav-icon" viewBox="0 0 24 24" aria-hidden="true">{paths}</svg>'


def render_primary_nav(active, mobile_meta=""):
    def links(items):
        result = []
        for label, path in items:
            current = ' class="active" aria-current="page"' if label == active else ""
            result.append(f'<a href="{path}"{current}>{_nav_icon(label)}<span>{label}</span></a>')
        return "".join(result)
    return (
        '<aside class="primary-nav"><a class="brand" href="/">HN·HOT</a>'
        f'{mobile_meta}'
        '<button class="nav-toggle" type="button" aria-expanded="false">菜单</button>'
        f'<div class="nav-body"><span class="nav-label">内容</span><nav>{links(NAV_ITEMS)}</nav>'
        f'<span class="nav-label">更多</span><nav>{links(MORE_ITEMS)}</nav>'
        '<div class="theme-toggle" role="group" aria-label="主题" data-theme-toggle>'
        '<span class="theme-toggle-thumb" aria-hidden="true" data-theme-thumb data-pos="system"></span>'
        '<button class="theme-toggle-opt" type="button" data-theme-choice="dark" aria-label="深色主题">☾</button>'
        '<button class="theme-toggle-opt" type="button" data-theme-choice="system" aria-label="跟随系统">▣</button>'
        '<button class="theme-toggle-opt" type="button" data-theme-choice="light" aria-label="亮色主题">☼</button>'
        '</div></div></aside>'
    )


def render_index(index, focus, active_category, manifest=None):
    links = ""
    for name, path in CATEGORY_PATHS.items():
        active = ' class="active"' if name == active_category else ""
        links += f'<a href="{path}"{active}>{name}</a>'
    focus_section = ""
    if focus is not None:
        focus_section = '<section class="focus-section"><div class="section-heading"><h2>新闻精选</h2></div><div class="focus-list">' + "".join(_selected_row(item, item["focus_rank"]) for item in focus["items"]) + "</div></section>"
    groups = []
    current = None
    latest_date = index["items"][0]["published_date"] if index["items"] else None
    for item in index["items"]:
        if item["published_date"] != current:
            if current is not None:
                groups.append("</div></section>")
            current = item["published_date"]
            count = sum(value["published_date"] == current for value in index["items"])
            heading = _feed_date_heading(current, count, current == latest_date)
            groups.append(f'<section class="date-group" data-feed-date="{current}"><h2>{heading}</h2><div class="story-list">')
        groups.append(_selected_row(item))
    if current is not None:
        groups.append("</div></section>")
    if not groups:
        groups.append(f'<p class="empty-state">今日暂无{html.escape(active_category)}精选</p>')
    updated = focus.get("updated_through") if focus else max((item["published_date"] for item in index["items"]), default="—")
    manifest = manifest or {"dates": [latest_date] if latest_date else [], "feeds": []}
    heading = _selected_header_heading(latest_date) if latest_date else '<strong class="selected-title">精选</strong><span class="selected-subtitle">暂无内容</span>'
    return _template("radar-index.html").safe_substitute(
        nav=render_primary_nav("精选", f'<span class="mobile-updated">{html.escape(_mobile_updated(updated))}</span>'), category_links=links,
        active_category=html.escape(active_category, quote=True), date_heading=heading,
        focus_section=focus_section, date_groups="".join(groups),
        feed_manifest=json.dumps(manifest, ensure_ascii=False).replace("<", "\\u003c"),
    )


def render_issue(issue):
    validate_public_issue(issue)
    pages = []
    for page in issue["pages"]:
        title = f'第{page["page_number"]}版：{page["page_name"]}'
        articles = "".join(_title_row(article) for article in page["articles"])
        pages.append(
            '<section class="issue-page" data-search-group><header>'
            f'<div><a class="issue-page-title" href="{html.escape(page["page_url"], quote=True)}" target="_blank" rel="noopener noreferrer">{html.escape(title)}</a>'
            f'<span>{len(page["articles"])} 篇</span></div>'
            f'<a class="pdf-link" href="{html.escape(page["pdf_url"], quote=True)}" target="_blank" rel="noopener noreferrer">下载 PDF</a>'
            f'</header><div class="title-list">{articles}</div></section>'
        )
    return _template("radar-issue.html").safe_substitute(
        nav=render_primary_nav("全部信息"), date=html.escape(issue["date"]),
        page_count=issue["page_count"], article_count=issue["scored_article_count"],
        pages="".join(pages),
    )


def render_item(item):
    if "category" in item:
        validate_stored_item(item)
        back_path = CATEGORY_PATHS[item["category"]]
        back_label = item["category"]
        category = item["category"]
    else:
        validate_public_issue_item(item)
        back_path = f'/all/{item["published_date"]}/'
        back_label = "全部信息"
        category = f'第{item["page_number"]}版 · {item["page_name"]}'
    block = item["block"]
    recommendation_section = (
        '<section class="recommendation-reason"><h2>推荐理由</h2>'
        f'<p>{html.escape(block["recommendation_reason"])}</p></section>'
        if "category" in item else ""
    )
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", block["content"].replace("\r\n", "\n")) if part.strip()]
    return _template("radar-item.html").safe_substitute(
        category_path=back_path, category=html.escape(category),
        back_label=html.escape(back_label),
        published_date=html.escape(item["published_date"]), title=html.escape(block["title"]),
        original_url=html.escape(block["original_url"], quote=True), ai_summary=html.escape(block["ai_summary"]),
        recommendation_section=recommendation_section,
        body_paragraphs="".join(f"<p>{html.escape(part)}</p>" for part in paragraphs),
    )


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_base(PRODUCT_NAME, value), encoding="utf-8")


class _LinkParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.links = []
    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = dict(attrs).get("href")
            if href: self.links.append(href)


def validate_internal_links(site_root):
    missing = []
    for page in site_root.rglob("*.html"):
        parser = _LinkParser(); parser.feed(page.read_text(encoding="utf-8"))
        for href in parser.links:
            parsed = urlparse(href)
            if parsed.scheme or parsed.netloc or href.startswith("#"): continue
            path = parsed.path
            if not path: continue
            target = site_root / path.lstrip("/")
            if path.endswith("/"): target = target / "index.html"
            if not target.exists(): missing.append(f"{page}: {href}")
    return missing


def build_site(content_root, site_root):
    content_root = Path(content_root); site_root = Path(site_root)
    if not (content_root / "indexes/all/page-001.json").is_file():
        raise ValueError("radar content indexes are missing")
    staging = site_root.with_name(f".{site_root.name}.radar-staging")
    backup = site_root.with_name(f".{site_root.name}.radar-backup")
    if staging.exists(): shutil.rmtree(staging)
    staging.mkdir(parents=True)
    try:
        shutil.copytree(ROOT / "src/static", staging / "static")
        focus = _read(content_root / "indexes/focus.json")
        manifest = _read(content_root / "indexes/recent-selected.json")
        feed_payloads = {}
        for published_date in manifest["dates"]:
            source = content_root / f"indexes/selected-feed/{published_date}.json"
            payload = _read(source)
            feed_payloads[published_date] = payload
            target = staging / f"static/selected-feed/{published_date}.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        latest_date = manifest["dates"][0] if manifest["dates"] else None
        latest_items = feed_payloads.get(latest_date, {}).get("items", [])
        _write(
            staging / "index.html",
            render_index(
                {"page": 1, "page_count": 1, "items": latest_items},
                focus,
                "全部",
                manifest,
            ),
        )
        slug_to_name = {value: key for key, value in {k: v.strip('/').split('/')[-1] for k, v in CATEGORY_PATHS.items() if k != "全部"}.items()}
        for name, route in CATEGORY_PATHS.items():
            if name in {"全部", "机会"}: continue
            slug = route.strip("/").split("/")[-1]
            items = [item for item in latest_items if item["category"] == name]
            _write(
                staging / f"category/{slug}/index.html",
                render_index(
                    {"page": 1, "page_count": 1, "items": items},
                    None,
                    name,
                    manifest,
                ),
            )
        for stem, suffix in (("active-page", ""), ("expired-page", "expired")):
            for path in sorted((content_root / "indexes/categories/opportunity").glob(f"{stem}-*.json")):
                data = _read(path); number = data["page"]
                base = staging / "category/opportunity" / suffix
                target = base / ("index.html" if number == 1 else f"page/{number}/index.html")
                _write(target, render_index(data, None, "机会", manifest))
        for path in sorted((content_root / "indexes/dates").glob("*.json")):
            data = _read(path)
            _write(staging / f"date/{data['date']}/index.html", render_index({"page": 1, "page_count": 1, "items": data["items"]}, None, "全部"))
        for path in sorted((content_root / "items").glob("*/*.json")):
            item = _read(path); validate_stored_item(item)
            _write(staging / f"items/{item['published_date']}/{item['item_id']}/index.html", render_item(item))
        selected_by_key = {}
        for path in sorted((content_root / "items").glob("*/*.json")):
            item = _read(path)
            selected_by_key[(item["published_date"], item["item_id"])] = item
        issues = []
        for path in sorted((content_root / "issues").glob("*.json")):
            issue = _read(path); validate_public_issue(issue); issues.append(issue)
            _write(staging / f"all/{issue['date']}/index.html", render_issue(issue))
        if issues:
            latest = max(issues, key=lambda value: value["date"])
            _write(staging / "all/index.html", render_issue(latest))
        else:
            _write(staging / "all/index.html", f'<div class="app-shell radar-shell">{render_primary_nav("全部信息")}<main class="content-shell prose-page"><h1>全部信息</h1><p>暂无内容</p></main></div>')
        for path in sorted((content_root / "issue-items").glob("*/*.json")):
            item = _read(path); validate_public_issue_item(item)
            key = (item["published_date"], item["item_id"])
            selected = selected_by_key.get(key)
            if selected is not None:
                for field in ("title", "content", "original_url"):
                    if selected["block"][field] != item["block"][field]:
                        raise ValueError(f"selected/issue item mismatch: {item['item_id']}")
                continue
            _write(staging / f"items/{item['published_date']}/{item['item_id']}/index.html", render_item(item))
        _write(staging / "about/index.html", _template("about.html").safe_substitute(nav=render_primary_nav("关于")))
        _write(staging / "changelog/index.html", _template("changelog.html").safe_substitute(nav=render_primary_nav("更新日志")))
        search_selected = _read(content_root / "indexes/search-selected.json")
        catalog = json.dumps(search_selected.get("items", []), ensure_ascii=False).replace("<", "\\u003c")
        _write(staging / "starred/index.html", _template("starred.html").safe_substitute(nav=render_primary_nav("收藏"), catalog=catalog))
        daily = [_read(path) for path in sorted((content_root / "daily").glob("*.json"))]
        if daily:
            report = daily[-1]
            rows = []
            for item in report.get("top_items", []) + report.get("more_items", []):
                rows.append(f'<div class="daily-entry"><h2>{html.escape(item.get("title", ""))}</h2><p>{html.escape(item.get("summary", ""))}</p></div>')
            body = f'<div class="app-shell radar-shell">{render_primary_nav("AI 日报")}<main class="content-shell prose-page"><h1>AI 日报</h1><time>{html.escape(report.get("date", ""))}</time>{"".join(rows)}</main></div>'
            _write(staging / "daily/index.html", body)
        else:
            _write(staging / "daily/index.html", f'<div class="app-shell radar-shell">{render_primary_nav("AI 日报")}<main class="content-shell prose-page"><h1>AI 日报</h1><p>暂无日报</p></main></div>')
        weekly = [_read(path) for path in sorted((content_root / "weekly").glob("*.json"))]
        for report in weekly:
            rendered = render_weekly(report, weekly)
            target = staging / f"weekly/{report['week']}/index.html"; target.parent.mkdir(parents=True, exist_ok=True); target.write_text(rendered, encoding="utf-8")
        if weekly:
            target = staging / "weekly/index.html"; target.parent.mkdir(parents=True, exist_ok=True); target.write_text(render_weekly(weekly[-1], weekly), encoding="utf-8")
        errors = validate_internal_links(staging)
        if errors: raise ValueError("broken internal links: " + "; ".join(errors))
        if backup.exists(): shutil.rmtree(backup)
        had_site = site_root.exists()
        if had_site: site_root.replace(backup)
        try: staging.replace(site_root)
        except Exception:
            if had_site and backup.exists() and not site_root.exists(): backup.replace(site_root)
            raise
        if backup.exists(): shutil.rmtree(backup)
    except Exception:
        if staging.exists(): shutil.rmtree(staging)
        raise


def main(argv):
    content = Path(argv[1]) if len(argv) > 1 else ROOT / "content"
    site = Path(argv[2]) if len(argv) > 2 else ROOT / "site"
    try: build_site(content, site)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr); return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
