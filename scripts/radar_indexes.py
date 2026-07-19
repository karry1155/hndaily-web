from __future__ import annotations

from scripts.radar_contract import ContractError, canonicalize_source_url
from scripts.radar_issue import validate_public_issue, validate_public_issue_item


def _article_summary(article):
    return {
        "item_id": article["item_id"],
        "published_date": article["published_date"],
        "page_number": article["page_number"],
        "page_name": article["page_name"],
        "page_sequence": article["page_sequence"],
        "title": article["block"]["title"],
        "ai_summary": article["block"]["ai_summary"],
        "scope": article["scope"],
        "enrichment_status": article["enrichment_status"],
        "subjects": article["subjects"],
        "locations": article["locations"],
        "topics": article["topics"],
        "detail_path": (
            f'/items/{article["published_date"]}/{article["item_id"]}/'
        ),
    }


def build_hnhot_indexes(issues, articles):
    """Build full-publication indexes without a score or selection layer."""
    for issue in issues:
        validate_public_issue(issue)
    for article in articles:
        validate_public_issue_item(article)
    ids = [article["item_id"] for article in articles]
    if len(set(ids)) != len(ids):
        raise ContractError("duplicate item_id in historical publication")
    ids_by_url: dict[str, str] = {}
    for article in articles:
        canonical_url = canonicalize_source_url(article["block"]["original_url"])
        previous_id = ids_by_url.get(canonical_url)
        if previous_id is not None and previous_id != article["item_id"]:
            raise ContractError(
                f"canonical URL collision: {canonical_url} maps to both "
                f"{previous_id} and {article['item_id']}"
            )
        ids_by_url[canonical_url] = article["item_id"]
    dates = sorted({issue["date"] for issue in issues}, reverse=True)
    by_id = {article["item_id"]: article for article in articles}
    payloads = {
        "hnhot.json": {
            "latest_date": dates[0] if dates else None,
            "dates": dates,
            "front_page_feeds": [
                f"/static/front-page/{value}.json" for value in dates
            ],
            "issue_feeds": [f"/static/issue-feed/{value}.json" for value in dates],
        },
        "issues.json": {"latest_date": dates[0] if dates else None, "dates": dates},
    }
    ordered = sorted(
        articles,
        key=lambda article: (
            article["published_date"],
            article["page_number"],
            article["page_sequence"],
            article["item_id"],
        ),
    )
    payloads["search-articles.json"] = {
        "items": [_article_summary(article) for article in ordered]
    }
    issue_by_date = {issue["date"]: issue for issue in issues}
    for published_date in dates:
        issue = issue_by_date[published_date]
        front_page = [
            _article_summary(by_id[item_id])
            for item_id in issue["front_page_item_ids"]
            if item_id in by_id
        ]
        world_item_ids = [
            row["item_id"]
            for page in issue["pages"]
            if page["page_name"] == "世界新闻"
            for row in page["articles"]
        ]
        world_news = [
            _article_summary(by_id[item_id])
            for item_id in world_item_ids
            if item_id in by_id
        ]
        front_page_ids = {row["item_id"] for row in front_page}
        home_items = front_page + [
            row for row in world_news if row["item_id"] not in front_page_ids
        ]
        national = [row for row in front_page if row["scope"] == "national"]
        payloads[f"front-page/{published_date}.json"] = {
            "date": published_date,
            "count": len(home_items),
            "front_page_count": len(front_page),
            "world_count": len(world_news),
            "national_ranking": [
                {**row, "rank": rank} for rank, row in enumerate(national, 1)
            ],
            "world_ranking": [
                {**row, "rank": rank} for rank, row in enumerate(world_news, 1)
            ],
            "items": home_items,
        }
        date_articles = [
            _article_summary(article)
            for article in ordered
            if article["published_date"] == published_date
        ]
        payloads[f"issue-feed/{published_date}.json"] = {
            "date": published_date,
            "count": len(date_articles),
            "sections": issue["sections"],
            "items": date_articles,
        }
    return payloads
