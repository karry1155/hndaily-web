#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import re
import shutil
import sys
from html.parser import HTMLParser
from pathlib import Path
from string import Template
from urllib.parse import urlparse

from scripts.radar_contract import validate_stored_item
from scripts.render_site import render_base, render_weekly

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
        for path in sorted((content_root / "indexes/all").glob("page-*.json")):
            data = _read(path); number = data["page"]
            target = staging / ("index.html" if number == 1 else f"page/{number}/index.html")
            _write(target, render_index(data, focus, "全部"))
        slug_to_name = {value: key for key, value in {k: v.strip('/').split('/')[-1] for k, v in CATEGORY_PATHS.items() if k != "全部"}.items()}
        for name, route in CATEGORY_PATHS.items():
            if name in {"全部", "机会"}: continue
            slug = route.strip("/").split("/")[-1]
            for path in sorted((content_root / f"indexes/categories/{slug}").glob("page-*.json")):
                data = _read(path); number = data["page"]
                target = staging / f"category/{slug}" / ("index.html" if number == 1 else f"page/{number}/index.html")
                _write(target, render_index(data, None, name))
        for stem, suffix in (("active-page", ""), ("expired-page", "expired")):
            for path in sorted((content_root / "indexes/categories/opportunity").glob(f"{stem}-*.json")):
                data = _read(path); number = data["page"]
                base = staging / "category/opportunity" / suffix
                target = base / ("index.html" if number == 1 else f"page/{number}/index.html")
                _write(target, render_index(data, None, "机会"))
        for path in sorted((content_root / "indexes/dates").glob("*.json")):
            data = _read(path)
            _write(staging / f"date/{data['date']}/index.html", render_index({"page": 1, "page_count": 1, "items": data["items"]}, None, "全部"))
        for path in sorted((content_root / "items").glob("*/*.json")):
            item = _read(path); validate_stored_item(item)
            _write(staging / f"items/{item['published_date']}/{item['item_id']}/index.html", render_item(item))
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
