#!/usr/bin/env python3
"""Crawl the complete Hainan Daily newspaper issue into project-local JSON."""

from __future__ import annotations

import datetime as _dt
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BASE = "http://news.hndaily.cn"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
ROOT = Path(__file__).resolve().parents[1]


def _resolve_output_dir() -> Path:
    env = os.environ.get("HNDAILY_DATA_DIR")
    if env:
        return Path(env).expanduser().resolve()
    return ROOT / "data/json/raw"


def _write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


OUTPUT_DIR = _resolve_output_dir()
TIMEOUT = 20
MAX_WORKERS = 8


# ---------- HTTP ----------


def _fetch_bytes(url: str) -> bytes:
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                if resp.status >= 400:
                    raise urllib.error.HTTPError(url, resp.status, "bad status", resp.headers, None)
                return resp.read()
        except Exception as e:
            last_err = e
            if attempt < 2:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"fetch failed after retries: {url} ({last_err})")


def fetch(url: str) -> str:
    return _fetch_bytes(url).decode("utf-8", errors="replace")


def fetch_safe(url: str) -> str | Exception:
    try:
        return fetch(url)
    except Exception as e:
        return e


# ---------- Parsing ----------


_PAGE_LIST_RE = re.compile(
    r'<a[^>]+id="pageLink"[^>]+href="(node_\d+\.htm)"[^>]*>\s*第\s*(\d+)\s*版\s*[:：]?\s*(.*?)</a>',
    re.DOTALL,
)
_ARTICLE_LINK_RE = re.compile(
    r'<div[^>]*id="(content_\d+_\d+)"[^>]*>\s*<a[^>]*href="(content_\d+_\d+\.htm)"[^>]*>(.*?)</a>',
    re.DOTALL,
)
_TITLE_RE = re.compile(r"<founder-title>(.*?)</founder-title>", re.DOTALL | re.IGNORECASE)
_AUTHOR_RE = re.compile(r"<founder-author>(.*?)</founder-author>", re.DOTALL | re.IGNORECASE)
_CONTENT_RE = re.compile(r"<founder-content>(.*?)</founder-content>", re.DOTALL | re.IGNORECASE)
_NPM_COMMENT_RE = re.compile(r"<!--\s*</?npm:[^>]+>\s*-->", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_PARA_SPLIT_RE = re.compile(r"<\s*[Pp]\b[^>]*>")
_BR_RE = re.compile(r"<\s*br\s*/?\s*>", re.IGNORECASE)
_WS_RE = re.compile(r"[ \t　]+")
_PAPERINDEX_RE = re.compile(r'URL=(html/(\d{4})-(\d{2})/(\d{2})/node_1\.htm)', re.IGNORECASE)


def _clean_text(s: str) -> str:
    s = html.unescape(s)
    s = s.replace("\xa0", " ")
    s = _WS_RE.sub(" ", s)
    return s.strip()


def parse_page_list(html_str: str) -> list[tuple[str, str, str]]:
    """Return ordered, deduped list of (page_num_str, page_name, relative_node_url).

    Page numbers may have gaps (e.g. publisher skips a number).
    """
    seen: dict[str, tuple[str, str, str]] = {}
    order: list[str] = []
    for m in _PAGE_LIST_RE.finditer(html_str):
        rel, page_num, raw_name = m.group(1), m.group(2), m.group(3)
        page_num = page_num.zfill(3)
        name = _clean_text(_TAG_RE.sub("", raw_name))
        if page_num in seen:
            continue
        seen[page_num] = (page_num, name, rel)
        order.append(page_num)
    return [seen[k] for k in sorted(order, key=lambda x: int(x))]


def parse_article_links(html_str: str) -> list[tuple[str, str]]:
    """From a node_X.htm page, return (relative_url, title_hint) deduped in order."""
    seen: dict[str, tuple[str, str]] = {}
    order: list[str] = []
    for m in _ARTICLE_LINK_RE.finditer(html_str):
        cid, href, raw_title = m.group(1), m.group(2), m.group(3)
        title = _clean_text(_TAG_RE.sub("", raw_title))
        if not title:
            continue
        if cid in seen:
            continue
        seen[cid] = (href, title)
        order.append(cid)
    return [seen[cid] for cid in order]


def parse_article(html_str: str) -> dict:
    title = ""
    m = _TITLE_RE.search(html_str)
    if m:
        raw = _NPM_COMMENT_RE.sub("", m.group(1))
        raw = _BR_RE.sub("\n", raw)
        raw = _TAG_RE.sub("", raw)
        title = "\n".join(_clean_text(line) for line in raw.split("\n") if _clean_text(line))

    author = ""
    m = _AUTHOR_RE.search(html_str)
    if m:
        raw = _NPM_COMMENT_RE.sub("", m.group(1))
        author = _clean_text(_TAG_RE.sub("", raw))

    content = ""
    m = _CONTENT_RE.search(html_str)
    if m:
        raw = _NPM_COMMENT_RE.sub("", m.group(1))
        raw = _BR_RE.sub("\n", raw)
        parts = _PARA_SPLIT_RE.split(raw)
        paragraphs: list[str] = []
        for p in parts:
            stripped = _TAG_RE.sub("", p)
            cleaned = _clean_text(stripped)
            if cleaned:
                paragraphs.append(cleaned)
        content = "\n\n".join(paragraphs)

    return {"title": title, "author": author, "content": content}


# ---------- URL helpers ----------


def front_page_url(d: _dt.date) -> str:
    return f"{BASE}/html/{d.year:04d}-{d.month:02d}/{d.day:02d}/node_1.htm"


def page_url_at(d: _dt.date, rel: str) -> str:
    return f"{BASE}/html/{d.year:04d}-{d.month:02d}/{d.day:02d}/{rel}"


def page_pdf_url(d: _dt.date, page_num: str) -> str:
    yyyymmdd = f"{d.year:04d}{d.month:02d}{d.day:02d}"
    return f"{BASE}/resfile/{d.isoformat()}/{page_num}/hnrb{yyyymmdd}{page_num}.pdf"


def discover_current_issue() -> tuple[_dt.date, str]:
    """Follow paperindex.htm meta-refresh to find the current issue's date+URL.

    Used when no date arg is supplied — handles the case where today's paper
    hasn't been published yet (it falls back to the most recent issue).
    """
    body = fetch(f"{BASE}/paperindex.htm")
    m = _PAPERINDEX_RE.search(body)
    if not m:
        raise RuntimeError("could not parse paperindex.htm redirect")
    rel, y, mo, d = m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4))
    return _dt.date(y, mo, d), f"{BASE}/{rel}"


# ---------- Main ----------


def now_iso_local() -> str:
    return _dt.datetime.now().astimezone().replace(microsecond=0).isoformat()


def crawl(date: _dt.date, front_html: str) -> dict:
    """Build the full payload for one issue. `front_html` is node_1.htm body."""
    pages_info = parse_page_list(front_html)

    # Map page -> node URL (node_1.htm body == first page's content; reuse it)
    node_urls: list[str] = []
    cached_html: list[str | None] = []
    for i, (_pnum, _name, rel) in enumerate(pages_info):
        node_urls.append(page_url_at(date, rel))
        cached_html.append(front_html if i == 0 else None)

    # Fetch all node_X.htm pages we don't already have
    missing_idx = [i for i, h in enumerate(cached_html) if h is None]
    missing_urls = [node_urls[i] for i in missing_idx]
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        results = list(ex.map(fetch_safe, missing_urls))
    for idx, res in zip(missing_idx, results):
        cached_html[idx] = res  # could be Exception

    # Per page: parse article links
    page_links: list[list[tuple[str, str]]] = []
    page_errors: list[str | None] = []
    for i, body in enumerate(cached_html):
        if isinstance(body, Exception):
            page_links.append([])
            page_errors.append(f"page fetch failed: {body}")
        else:
            page_links.append(parse_article_links(body))
            page_errors.append(None)

    # Flatten all article URLs across all pages
    flat_specs: list[tuple[int, int, str, str]] = []  # (page_idx, seq, rel, title_hint)
    for pi, links in enumerate(page_links):
        for seq, (rel, title) in enumerate(links, 1):
            flat_specs.append((pi, seq, rel, title))

    article_urls = [page_url_at(date, rel) for _, _, rel, _ in flat_specs]
    if article_urls:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            article_htmls = list(ex.map(fetch_safe, article_urls))
    else:
        article_htmls = []

    # Build per-page article lists, in order
    page_articles: list[list[dict]] = [[] for _ in pages_info]
    for spec, body in zip(flat_specs, article_htmls):
        pi, seq, rel, title_hint = spec
        url = page_url_at(date, rel)
        item: dict = {
            "seq": seq,
            "title": title_hint,
            "url": url,
            "author": "",
            "content": "",
        }
        if isinstance(body, Exception):
            item["error"] = f"fetch failed: {body}"
        else:
            parsed = parse_article(body)
            if parsed["title"]:
                item["title"] = parsed["title"]
            item["author"] = parsed["author"]
            item["content"] = parsed["content"]
            if not parsed["content"]:
                item["error"] = "empty content"
        page_articles[pi].append(item)

    pages_payload: list[dict] = []
    total_articles = 0
    for i, (page_num, page_name, rel) in enumerate(pages_info):
        articles = page_articles[i]
        total_articles += len(articles)
        page_obj: dict = {
            "page": page_num,
            "page_name": page_name,
            "page_url": page_url_at(date, rel),
            "pdf_url": page_pdf_url(date, page_num),
            "article_count": len(articles),
            "articles": articles,
        }
        if page_errors[i]:
            page_obj["error"] = page_errors[i]
        pages_payload.append(page_obj)

    yyyymmdd = f"{date.year:04d}{date.month:02d}{date.day:02d}"
    return {
        "source": "海南日报",
        "date": date.isoformat(),
        "front_page_url": front_page_url(date),
        "pdf_url_template": (
            f"{BASE}/resfile/{date.isoformat()}/{{NNN}}/hnrb{yyyymmdd}{{NNN}}.pdf"
        ),
        "fetched_at": now_iso_local(),
        "page_count": len(pages_info),
        "article_count": total_articles,
        "pages": pages_payload,
    }


# 幂等复用：30 分钟内已经爬过的 JSON 默认直接复用，不重爬。
# 想强制刷新就传 --force。
CACHE_TTL_SECONDS = 30 * 60


def _try_reuse_cached(date: _dt.date) -> Path | None:
    """如果 {date}.json 存在且新鲜，返回路径；否则返回 None。"""
    out_path = OUTPUT_DIR / f"{date.isoformat()}.json"
    if not out_path.exists():
        return None
    age = time.time() - out_path.stat().st_mtime
    if age >= CACHE_TTL_SECONDS:
        return None
    return out_path


def main(argv: list[str]) -> int:
    # 解析参数：日期（位置参数）和 --force 标志
    args = [a for a in argv[1:] if a not in ("--force", "-f")]
    force = ("--force" in argv) or ("-f" in argv)
    arg = args[0] if args else None

    try:
        if arg is None:
            # 不传日期：先看默认输出目录里今天/昨天的 JSON 在不在
            # 但因为不传日期时我们也不知道"当前一期"是哪天，所以无法预先判幂等，
            # 只能先 discover 拿到日期再看
            date, front_url = discover_current_issue()
        else:
            try:
                date = _dt.date.fromisoformat(arg)
            except ValueError as e:
                print(f"ERROR: invalid date '{arg}', expected YYYY-MM-DD: {e}", file=sys.stderr)
                return 1
            front_url = front_page_url(date)

        # 幂等检查：拿到日期后立刻看缓存
        if not force:
            cached = _try_reuse_cached(date)
            if cached is not None:
                age_min = int((time.time() - cached.stat().st_mtime) / 60)
                print(str(cached))
                print(
                    f"date={date.isoformat()} cached=yes age_min={age_min} "
                    f"(--force 可强制重爬)",
                    file=sys.stderr,
                )
                return 0

        front_html = fetch(front_url)
    except Exception as e:
        print(f"ERROR: failed to load front page: {e}", file=sys.stderr)
        return 2

    payload = crawl(date, front_html)
    if payload["page_count"] == 0:
        print(f"NO_ISSUE: no pages found for {date.isoformat()}", file=sys.stderr)
        return 3

    out_path = OUTPUT_DIR / f"{date.isoformat()}.json"
    _write_json_atomic(out_path, payload)
    print(str(out_path.resolve()))
    print(
        f"date={date.isoformat()} pages={payload['page_count']} articles={payload['article_count']}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
