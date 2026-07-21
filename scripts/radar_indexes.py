from __future__ import annotations

from scripts.radar_contract import ContractError, canonicalize_source_url
from scripts.radar_issue import validate_public_issue, validate_public_issue_item
from scripts.radar_topics import load_topic_catalog, topic_catalog_by_id


def public_topics(article):
    if article.get("schema_version") == 9:
        return article.get("resolved_topics", [])
    return article.get("topics", [])


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
        "topics": public_topics(article),
        "events": article.get("events", []),
        "plans": article.get("plans", []),
        "detail_path": (
            f'/items/{article["published_date"]}/{article["item_id"]}/'
        ),
    }


def _build_topic_indexes(articles, catalog):
    by_id = topic_catalog_by_id(catalog)
    active = [row for row in catalog["topics"] if row["status"] == "active"]
    memberships = {row["topic_id"]: {"primary": [], "secondary": []} for row in active}
    for article in articles:
        if article.get("schema_version") != 9 or article.get("scope") not in {"hainan", "mixed"}:
            continue
        article_memberships: dict[str, str] = {}
        for resolved in article.get("resolved_topics", []):
            relation = resolved["relation"]
            cursor = resolved["topic_id"]
            while cursor is not None:
                previous = article_memberships.get(cursor)
                if previous != "primary":
                    article_memberships[cursor] = relation
                cursor = by_id[cursor]["parent_id"]
        summary = _article_summary(article)
        for topic_id, relation in article_memberships.items():
            if topic_id in memberships:
                memberships[topic_id][relation].append(summary)
    payloads = {}
    nodes = []
    for topic in active:
        groups = memberships[topic["topic_id"]]
        primary = sorted(
            groups["primary"],
            key=lambda row: (row["published_date"], row["page_number"], row["page_sequence"]),
            reverse=True,
        )
        secondary = sorted(
            groups["secondary"],
            key=lambda row: (row["published_date"], row["page_number"], row["page_sequence"]),
            reverse=True,
        )
        count = len(primary) + len(secondary)
        node = {
            "topic_id": topic["topic_id"],
            "name": topic["name"],
            "parent_id": topic["parent_id"],
            "article_count": count,
            "primary_count": len(primary),
            "detail_path": f'/topics/{topic["topic_id"]}/',
        }
        nodes.append(node)
        payloads[f'topic-feed/{topic["topic_id"]}.json'] = {
            **node,
            "definition": topic["definition"],
            "primary_items": primary,
            "secondary_items": secondary,
        }
    roots = []
    children_by_parent: dict[str, list[dict]] = {}
    for node in nodes:
        if node["parent_id"] is None:
            roots.append(node)
        else:
            children_by_parent.setdefault(node["parent_id"], []).append(node)
    payloads["topics.json"] = {
        "roots": [
            {**root, "children": children_by_parent.get(root["topic_id"], [])}
            for root in roots
        ],
        "nodes": nodes,
    }
    return payloads


def build_hnhot_indexes(issues, articles, topic_catalog=None):
    """Build full-publication indexes without a score or selection layer."""
    for issue in issues:
        validate_public_issue(issue)
    for article in articles:
        validate_public_issue_item(article)
    topic_catalog = topic_catalog or load_topic_catalog()
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
    payloads.update(_build_topic_indexes(articles, topic_catalog))
    return payloads
