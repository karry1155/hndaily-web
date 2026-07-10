#!/usr/bin/env python3
from __future__ import annotations

import html
import re
from pathlib import Path
from string import Template

from scripts.radar_contract import validate_stored_item

ROOT = Path(__file__).resolve().parents[1]
PRODUCT_NAME = "海南信息雷达"
CATEGORY_PATHS = {
    "全部": "/", "机会": "/category/opportunity/",
    "民生": "/category/livelihood/", "产业": "/category/industry/",
    "政策": "/category/policy/", "城市": "/category/city/",
    "观察": "/category/observation/",
}


def _template(name):
    return Template((ROOT / "src/templates" / name).read_text(encoding="utf-8"))


def _card(item):
    return (
        f'<a class="radar-card" href="{html.escape(item["detail_path"], quote=True)}">'
        f'<span class="card-source">{html.escape(item["source"])}</span>'
        f'<h3>{html.escape(item["title"])}</h3>'
        f'<p>{html.escape(item["ai_summary"])}</p></a>'
    )


def render_index(index, focus, active_category):
    links = ""
    for name, path in CATEGORY_PATHS.items():
        active = ' class="active"' if name == active_category else ""
        links += f'<a href="{path}"{active}>{name}</a>'
    focus_section = ""
    if focus is not None:
        focus_section = '<section class="focus-section"><h2>当下重点</h2>' + "".join(_card(item) for item in focus["items"]) + "</section>"
    groups = []
    current = None
    for item in index["items"]:
        if item["published_date"] != current:
            if current is not None:
                groups.append("</div></section>")
            current = item["published_date"]
            groups.append(f'<section class="date-group"><h2>{html.escape(current)}</h2><div class="card-list">')
        groups.append(_card(item))
    if current is not None:
        groups.append("</div></section>")
    if not groups:
        groups.append(f'<p class="empty-state">今日暂无{html.escape(active_category)}精选</p>')
    page = index.get("page", 1)
    pages = index.get("page_count", 1)
    pagination = "" if pages <= 1 else f'<span>第 {page} / {pages} 页</span>'
    updated = focus.get("updated_through") if focus else max((item["published_date"] for item in index["items"]), default="—")
    return _template("radar-index.html").safe_substitute(
        product_name=PRODUCT_NAME, category_links=links,
        view_title=html.escape(active_category), updated_through=html.escape(updated),
        focus_section=focus_section, date_groups="".join(groups), pagination=pagination,
    )


def render_item(item):
    validate_stored_item(item)
    block = item["block"]
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", block["content"].replace("\r\n", "\n")) if part.strip()]
    return _template("radar-item.html").safe_substitute(
        category_path=CATEGORY_PATHS[item["category"]], category=html.escape(item["category"]),
        published_date=html.escape(item["published_date"]), title=html.escape(block["title"]),
        original_url=html.escape(block["original_url"], quote=True), ai_summary=html.escape(block["ai_summary"]),
        body_paragraphs="".join(f"<p>{html.escape(part)}</p>" for part in paragraphs),
    )
