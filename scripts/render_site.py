#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import shutil
from pathlib import Path
from string import Template
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
CONTENT_DAILY = ROOT / "content" / "daily"
CONTENT_WEEKLY = ROOT / "content" / "weekly"
TEMPLATES = ROOT / "src" / "templates"
STATIC = ROOT / "src" / "static"
SITE = ROOT / "site"

CATEGORIES = [
    "民生/办事",
    "政策/监管",
    "产业/项目",
    "经济/数据",
    "城市/出行/风险",
    "人事/反腐",
    "重要但不必精读",
    "已跳过",
]


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def is_http_url(url: Any) -> bool:
    if not isinstance(url, str):
        return False
    parsed = urlparse(url.strip())
    return parsed.scheme in {"http", "https"}


def load_template(name: str) -> Template:
    return Template((TEMPLATES / name).read_text(encoding="utf-8"))


def render_base(title: str, body: str) -> str:
    return load_template("base.html").substitute(title=esc(title), body=body)


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def source_links(sources: list[dict[str, Any]]) -> str:
    if not sources:
        return '<li class="source-empty">暂无来源链接</li>'
    links = []
    for source in sources:
        label = f"第{source.get('page', '')}版 · {source.get('headline', '')}"
        if source.get("date"):
            label = f"{source.get('date', '')} · {label}"
        url = source.get("url", "")
        if is_http_url(url):
            links.append(f'<a href="{esc(url)}" target="_blank" rel="noreferrer">{esc(label)}</a>')
        else:
            links.append(esc(label))
    return "".join(f"<li>{link}</li>" for link in links)


def render_daily_archive(current_date: str, daily_reports: list[dict[str, Any]]) -> str:
    links = []
    for report in sorted(daily_reports, key=lambda item: str(item.get("date", "")), reverse=True):
        date = str(report.get("date", ""))
        active = " active" if date == current_date else ""
        count = esc(report.get("article_count", ""))
        links.append(
            f'<a class="date-link{active}" href="/daily/{esc(date)}/">{esc(date)}<span>{count} 篇</span></a>'
        )
    return "".join(links)


def render_weekly_archive(current_week: str, weekly_reports: list[dict[str, Any]]) -> str:
    links = []
    for report in sorted(weekly_reports, key=lambda item: str(item.get("week", "")), reverse=True):
        week = str(report.get("week", ""))
        date_range = report.get("date_range", {})
        active = " active" if week == current_week else ""
        window = f"{date_range.get('start', '')} 至 {date_range.get('end', '')}"
        links.append(
            f'<a class="date-link{active}" href="/weekly/{esc(week)}/">{esc(week)}<span>{esc(window)}</span></a>'
        )
    return "".join(links)


def render_signal_cards(
    source_items: list[dict[str, Any]],
    *,
    empty_title: str,
    empty_reason: str,
) -> str:
    items = []
    for item in source_items:
        facts = "".join(f"<li>{esc(fact)}</li>" for fact in item.get("key_facts", []))
        score = item.get("final_score")
        score_text = f" · 最终分 {esc(score)}" if score is not None else ""
        items.append(
            f"""
            <article class="signal-card">
              <div class="signal-rank">{int(item.get("rank", 0)):02d}</div>
              <div class="signal-main">
                <div class="signal-meta">{esc(item.get("category", ""))} · {esc(item.get("confidence", ""))}{score_text}</div>
                <h2>{esc(item.get("title", ""))}</h2>
                <p class="summary">{esc(item.get("summary", ""))}</p>
                <p class="why">{esc(item.get("why_it_matters", ""))}</p>
                <ul class="facts">{facts}</ul>
                <ul class="sources">{source_links(item.get("sources", []))}</ul>
              </div>
            </article>
            """
        )
    if not items:
        items.append(
            f"""
            <article class="signal-card empty-card">
              <div class="signal-rank">--</div>
              <div class="signal-main">
                <h2>{esc(empty_title)}</h2>
                <p class="why">{esc(empty_reason)}</p>
              </div>
            </article>
            """
        )

    return "".join(items)


def render_daily(data: dict[str, Any], daily_reports: list[dict[str, Any]]) -> str:
    top_items = data.get("top_items", [])
    more_items = data.get("more_items", [])
    top_signals = render_signal_cards(
        top_items,
        empty_title="今日暂无达到精选线的重点",
        empty_reason="今日没有项目同时通过海南相关性和最终分资格线。",
    )
    more_signals = render_signal_cards(
        more_items,
        empty_title="今日没有更多达到精选线的条目",
        empty_reason="不使用低分内容补足篇数。",
    )

    categories = []
    category_data = data.get("categories", {})
    for name in CATEGORIES:
        entries = category_data.get(name, [])
        rows = []
        for entry in entries:
            skip_reason = ""
            if entry.get("skip_reason"):
                skip_reason = f'<em class="skip-reason">{esc(entry.get("skip_reason", ""))}</em>'
            rows.append(
                f"""
                <li>
                  <strong>{esc(entry.get("title", ""))}</strong>
                  <span>{esc(entry.get("summary", ""))}</span>
                  {skip_reason}
                  <ul class="sources">{source_links(entry.get("sources", []))}</ul>
                </li>
                """
            )
        category_markup = "".join(rows) or '<li class="empty">今日无高价值条目</li>'
        categories.append(f"<section class='category'><h3>{esc(name)}</h3><ul>{category_markup}</ul></section>")

    body = load_template("daily.html").substitute(
        date=esc(data.get("date", "")),
        source=esc(data.get("source", "")),
        page_count=esc(data.get("page_count", "")),
        article_count=esc(data.get("article_count", "")),
        reading_minutes=esc(data.get("reading_minutes", "")),
        signals=top_signals,
        more_signals=more_signals,
        top_count=esc(len(top_items)),
        more_count=esc(len(more_items)),
        categories="".join(categories),
        daily_links=render_daily_archive(str(data.get("date", "")), daily_reports),
    )
    return render_base(f"海南日报精读 {data.get('date', '')}", body)


def render_weekly(data: dict[str, Any], weekly_reports: list[dict[str, Any]]) -> str:
    items = []
    for item in data.get("top_items", []):
        facts = "".join(f"<li>{esc(fact)}</li>" for fact in item.get("key_facts", []))
        items.append(
            f"""
            <article class="signal-card">
              <div class="signal-rank">{int(item.get("rank", 0)):02d}</div>
              <div class="signal-main">
                <h2>{esc(item.get("title", ""))}</h2>
                <p class="why">{esc(item.get("why_it_matters", ""))}</p>
                <ul class="facts">{facts}</ul>
                <ul class="sources">{source_links(item.get("sources", []))}</ul>
              </div>
            </article>
            """
        )
    if not items:
        items.append(
            """
            <article class="signal-card empty-card">
              <div class="signal-rank">--</div>
              <div class="signal-main">
                <h2>本周暂无重点条目</h2>
                <p class="why">等待周报聚合结果。</p>
              </div>
            </article>
            """
        )

    themes = "".join(
        f"<li><strong>{esc(theme.get('title', ''))}</strong><span>{esc(theme.get('summary', ''))}</span><ul class='sources'>{source_links(theme.get('sources', []))}</ul></li>"
        for theme in data.get("themes", [])
    ) or '<li class="empty">本周暂无明确趋势主题</li>'
    watch_next = "".join(f"<li>{esc(item)}</li>" for item in data.get("watch_next", [])) or '<li class="empty">暂无继续关注事项</li>'

    body = load_template("weekly.html").substitute(
        week=esc(data.get("week", "")),
        start=esc(data.get("date_range", {}).get("start", "")),
        end=esc(data.get("date_range", {}).get("end", "")),
        reading_minutes=esc(data.get("reading_minutes", "")),
        signals="".join(items),
        themes=themes,
        watch_next=watch_next,
        weekly_links=render_weekly_archive(str(data.get("week", "")), weekly_reports),
    )
    return render_base(f"海南日报周报 {data.get('week', '')}", body)


def copy_static() -> None:
    target = SITE / "static"
    target.mkdir(parents=True, exist_ok=True)
    for path in STATIC.iterdir():
        if path.is_file():
            shutil.copy2(path, target / path.name)


def main() -> int:
    if SITE.exists():
        shutil.rmtree(SITE)

    copy_static()
    daily_files = sorted(CONTENT_DAILY.glob("*.json"))
    weekly_files = sorted(CONTENT_WEEKLY.glob("*.json"))
    daily_reports = [read_json(path) for path in daily_files]
    weekly_reports = [read_json(path) for path in weekly_files]

    latest_daily = None
    latest_weekly = None

    for data in daily_reports:
        latest_daily = data
        write_file(SITE / "daily" / str(data["date"]) / "index.html", render_daily(data, daily_reports))

    for data in weekly_reports:
        latest_weekly = data
        write_file(SITE / "weekly" / str(data["week"]) / "index.html", render_weekly(data, weekly_reports))

    if latest_daily is not None:
        rendered_daily = render_daily(latest_daily, daily_reports)
        write_file(SITE / "index.html", rendered_daily)
        write_file(SITE / "daily" / "index.html", rendered_daily)
    else:
        write_file(
            SITE / "index.html",
            render_base("海南日报精读", "<main class='shell'><h1>海南日报精读</h1><p>暂无日报内容。</p></main>"),
        )

    if latest_weekly is not None:
        write_file(SITE / "weekly" / "index.html", render_weekly(latest_weekly, weekly_reports))

    print(f"Rendered {SITE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
