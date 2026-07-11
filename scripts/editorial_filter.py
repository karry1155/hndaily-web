from __future__ import annotations

from typing import Any


EXCLUDED_EXACT_TITLES = {"导读"}
PUBLIC_SERVICE_AD_MARKER = "公益广告"
THEORY_WEEKLY_PREFIX = "理论周刊"


class InputError(ValueError):
    pass


def _non_empty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _length_band(length: int) -> str:
    if length < 200:
        return "under_200"
    if length < 400:
        return "200_to_399"
    return "400_plus"


def flatten_articles(raw: dict[str, Any]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    pages = raw.get("pages")
    if not isinstance(pages, list):
        raise InputError("pages must be an array")
    if raw.get("page_count") != len(pages):
        raise InputError("page_count does not match pages")

    flattened: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for page_index, page in enumerate(pages):
        if not isinstance(page, dict):
            raise InputError(f"pages[{page_index}] must be an object")
        articles = page.get("articles")
        if not isinstance(articles, list):
            raise InputError(f"pages[{page_index}].articles must be an array")
        if page.get("article_count") != len(articles):
            raise InputError(f"pages[{page_index}].article_count does not match articles")
        for article in articles:
            if not isinstance(article, dict):
                raise InputError(f"pages[{page_index}] contains a non-object article")
            flattened.append((page, article))

    if raw.get("article_count") != len(flattened):
        raise InputError("article_count does not match flattened articles")
    return flattened


def evaluate_issue(raw: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for index, (page, article) in enumerate(flatten_articles(raw), 1):
        page_number = page.get("page")
        page_name = page.get("page_name")
        title = article.get("title")
        url = article.get("url")
        if not _non_empty(page_number):
            raise InputError(f"article {index} page is required")
        if not _non_empty(page_name):
            raise InputError(f"article {index} page_name is required")
        if not _non_empty(title):
            raise InputError(f"article {index} title is required")
        if not _non_empty(url):
            raise InputError(f"article {index} url is required")

        content = article.get("content") if isinstance(article.get("content"), str) else ""
        content_length = len(content.strip())
        error = article.get("error")
        skip_reason = None
        matched_rules: list[str] = []
        if _non_empty(error):
            skip_reason = "fetch_error"
            matched_rules.append("fetch_error")
        elif not content.strip():
            skip_reason = "empty_content"
            matched_rules.append("empty_content")
        elif title.strip() in EXCLUDED_EXACT_TITLES:
            skip_reason = "guide"
            matched_rules.append("exact_title:导读")
        elif PUBLIC_SERVICE_AD_MARKER in page_name:
            skip_reason = "public_service_ad_page"
            matched_rules.append("page_name:公益广告")
        elif page_name.startswith(THEORY_WEEKLY_PREFIX):
            skip_reason = "theory_weekly"
            matched_rules.append("page_name:理论周刊")

        records.append(
            {
                "candidate_id": f"A{index:03d}",
                "page": page_number.strip(),
                "page_name": page_name.strip(),
                "page_url": page.get("page_url"),
                "pdf_url": page.get("pdf_url"),
                "seq": article.get("seq"),
                "original_title": title.strip(),
                "url": url.strip(),
                "author": article.get("author", "") if isinstance(article.get("author", ""), str) else "",
                "content": content,
                "content_length": content_length,
                "length_band": _length_band(content_length),
                "error": error if _non_empty(error) else None,
                "passed": skip_reason is None,
                "skip_reason": skip_reason,
                "matched_rules": matched_rules,
            }
        )
    return records
