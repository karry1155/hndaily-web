from __future__ import annotations

from collections import defaultdict

from scripts.radar_contract import ContractError, canonicalize_source_url
from scripts.radar_issue import validate_public_issue, validate_public_issue_item
from scripts.radar_locations import load_location_catalog
from scripts.radar_model import load_topic_categories


def _sort_articles(rows):
    return sorted(
        rows,
        key=lambda row: (
            row["published_date"], row["page_number"], row["page_sequence"], row["item_id"],
        ),
        reverse=True,
    )


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
        "subjects": [
            {"subject_id": row["subject_id"], "name": row["name"], "type": row["type"]}
            for row in article["subjects"]
        ],
        "locations": article["locations"],
        "topics": article["topics"],
        "events": article["events"],
        "plans": article["plans"],
        "reader_lead_count": len(article["reader_leads"]),
        "detail_path": f'/items/{article["published_date"]}/{article["item_id"]}/',
    }


def _source(article, evidence):
    return {
        "source_item_id": article["item_id"],
        "published_date": article["published_date"],
        "source_title": article["block"]["title"],
        "detail_path": f'/items/{article["published_date"]}/{article["item_id"]}/',
        "evidence": evidence,
    }


def _build_subject_indexes(articles, summaries):
    grouped = {}
    for article in articles:
        for subject in article["subjects"]:
            row = grouped.setdefault(subject["subject_id"], {
                "subject": subject,
                "article_ids": set(),
                "dates": [],
                "aliases": {},
                "activities": [],
            })
            row["article_ids"].add(article["item_id"])
            row["dates"].append(article["published_date"])
            for alias in subject.get("aliases", []):
                row["aliases"].setdefault(alias["name"], alias)
            for activity in subject["activities"]:
                row["activities"].append({
                    **activity,
                    "source": _source(article, activity["evidence"]),
                })
    directory, payloads = [], {}
    for subject_id, value in grouped.items():
        subject = value["subject"]
        activities = sorted(
            value["activities"],
            key=lambda row: (
                row.get("occurred_on") or row["source"]["published_date"],
                row["source"]["source_item_id"],
            ),
            reverse=True,
        )
        item = {
            "subject_id": subject_id,
            "name": subject["name"],
            "type": subject["type"],
            "article_count": len(value["article_ids"]),
            "activity_count": len(activities),
            "first_seen": min(value["dates"]),
            "last_seen": max(value["dates"]),
            "detail_path": f"/subjects/{subject_id}/",
        }
        directory.append(item)
        payloads[f"subject-feed/{subject_id}.json"] = {
            "schema_version": 1,
            "subject": {
                "subject_id": subject_id,
                "canonical_name": subject["name"],
                "type": subject["type"],
                "aliases": list(value["aliases"].values()),
                "first_seen": item["first_seen"],
                "last_seen": item["last_seen"],
            },
            "activities": activities,
            "articles": _sort_articles([summaries[value] for value in value["article_ids"]]),
        }
    type_order = {"person": 0, "company": 1, "organization": 2}
    directory.sort(
        key=lambda row: (
            type_order[row["type"]], -row["article_count"], -row["activity_count"], row["name"],
        )
    )
    payloads["subjects.json"] = {"schema_version": 1, "items": directory}
    return payloads


def _build_region_indexes(articles, summaries):
    catalog = load_location_catalog()
    grouped = {row["location_id"]: set() for row in catalog.divisions}
    for article in articles:
        for location in article["locations"]:
            grouped[location["location_id"]].add(article["item_id"])
    directory, payloads = [], {}
    for region in catalog.divisions:
        ids = grouped[region["location_id"]]
        item = {
            "location_id": region["location_id"],
            "name": region["name"],
            "code": region["code"],
            "level": region["level"],
            "article_count": len(ids),
            "detail_path": f'/regions/{region["location_id"]}/',
        }
        directory.append(item)
        payloads[f'region-feed/{region["location_id"]}.json'] = {
            "schema_version": 1,
            "region": item,
            "articles": _sort_articles([summaries[value] for value in ids]),
        }
    level_order = {"province": 0, "prefecture": 1, "county": 2}
    directory.sort(key=lambda row: (level_order[row["level"]], -row["article_count"], row["code"]))
    payloads["regions.json"] = {"schema_version": 1, "items": directory}
    return payloads


def _build_topic_indexes(articles, summaries):
    categories = load_topic_categories()
    article_ids_by_category = defaultdict(set)
    secondary = defaultdict(lambda: defaultdict(set))
    secondary_names = {}
    secondary_ids = {}
    for article in articles:
        primary = article["topics"]["primary"]
        category_id = primary["category_id"]
        article_ids_by_category[category_id].add(article["item_id"])
        for topic in article["topics"]["secondary"]:
            secondary[category_id][topic["topic_id"]].add(article["item_id"])
            secondary_names[topic["topic_id"]] = topic["name"]
            secondary_ids[topic["topic_id"]] = category_id
    roots, nodes, payloads = [], [], {}
    for category in categories:
        category_id = category["category_id"]
        root_id = f"category-{category_id}"
        children = []
        for topic_id, ids in secondary[category_id].items():
            child = {
                "topic_id": topic_id,
                "name": secondary_names[topic_id],
                "parent_id": root_id,
                "category_id": category_id,
                "article_count": len(ids),
                "detail_path": f"/topics/{topic_id}/",
            }
            children.append(child)
            nodes.append(child)
            payloads[f"topic-feed/{topic_id}.json"] = {
                "schema_version": 1,
                "topic": child,
                "articles": _sort_articles([summaries[value] for value in ids]),
            }
        children.sort(key=lambda row: (-row["article_count"], row["name"]))
        ids = article_ids_by_category[category_id]
        root = {
            "topic_id": root_id,
            "name": category["name"],
            "parent_id": None,
            "category_id": category_id,
            "definition": category["definition"],
            "boundary": category["boundary"],
            "article_count": len(ids),
            "detail_path": f"/topics/{root_id}/",
            "children": children,
        }
        roots.append(root)
        nodes.append({key: value for key, value in root.items() if key != "children"})
        payloads[f"topic-feed/{root_id}.json"] = {
            "schema_version": 1,
            "topic": {key: value for key, value in root.items() if key != "children"},
            "children": children,
            "articles": _sort_articles([summaries[value] for value in ids]),
        }
    payloads["topics.json"] = {"schema_version": 1, "roots": roots, "nodes": nodes}
    return payloads


def _build_event_indexes(articles, summaries):
    grouped, series = {}, {}
    for article in articles:
        for event in article["events"]:
            row = grouped.setdefault(event["event_id"], {"event": event, "article_ids": set()})
            row["article_ids"].add(article["item_id"])
            if event.get("series_id"):
                series_row = series.setdefault(event["series_id"], {
                    "name": event["series_name"], "article_ids": set(), "editions": set(),
                })
                series_row["article_ids"].add(article["item_id"])
                series_row["editions"].add(event["event_id"])
    directory, payloads = [], {}
    for event_id, value in grouped.items():
        event, ids = value["event"], value["article_ids"]
        item = {
            "event_id": event_id,
            "name": event["name"],
            "event_type": event["event_type"],
            "series_id": event.get("series_id"),
            "article_count": len(ids),
            "detail_path": f"/events/{event_id}/",
        }
        directory.append(item)
        payloads[f"event-feed/{event_id}.json"] = {
            "schema_version": 1,
            "event": item,
            "articles": _sort_articles([summaries[value] for value in ids]),
        }
    for series_id, value in series.items():
        item = {
            "event_id": series_id,
            "name": value["name"],
            "event_type": "series",
            "series_id": series_id,
            "edition_ids": sorted(value["editions"]),
            "article_count": len(value["article_ids"]),
            "detail_path": f"/events/{series_id}/",
        }
        directory.append(item)
        payloads[f"event-feed/{series_id}.json"] = {
            "schema_version": 1,
            "event": item,
            "articles": _sort_articles([summaries[value] for value in value["article_ids"]]),
        }
    directory.sort(key=lambda row: (-row["article_count"], row["name"]))
    payloads["events.json"] = {"schema_version": 1, "items": directory}
    return payloads


def _build_plan_indexes(articles, summaries):
    grouped = {}
    for article in articles:
        for plan in article["plans"]:
            row = grouped.setdefault(plan["plan_id"], {
                "name": plan["name"], "article_ids": set(), "mentions": [],
            })
            row["article_ids"].add(article["item_id"])
            row["mentions"].append({
                "mention_type": plan["mention_type"],
                "source": _source(article, plan["evidence"]),
            })
    directory, payloads = [], {}
    for plan_id, value in grouped.items():
        item = {
            "plan_id": plan_id,
            "name": value["name"],
            "article_count": len(value["article_ids"]),
            "detail_path": f"/plans/{plan_id}/",
        }
        directory.append(item)
        payloads[f"plan-feed/{plan_id}.json"] = {
            "schema_version": 1,
            "plan": item,
            "mentions": sorted(
                value["mentions"], key=lambda row: row["source"]["published_date"], reverse=True
            ),
            "articles": _sort_articles([summaries[value] for value in value["article_ids"]]),
        }
    directory.sort(key=lambda row: (-row["article_count"], row["name"]))
    payloads["plans.json"] = {"schema_version": 1, "items": directory}
    return payloads


def _build_reader_indexes(articles):
    rows = []
    for article in articles:
        for lead in article["reader_leads"]:
            rows.append({**lead, "source": _source(article, lead["evidence"])})
    rows.sort(key=lambda row: (row["source"]["published_date"], row["lead_id"]), reverse=True)
    return {
        "reader-leads.json": {
            "schema_version": 1,
            "count": len(rows),
            "items": rows,
        }
    }


def build_hnhot_indexes(issues, articles):
    for issue in issues:
        validate_public_issue(issue)
    for article in articles:
        validate_public_issue_item(article)
    ids = [article["item_id"] for article in articles]
    if len(ids) != len(set(ids)):
        raise ContractError("duplicate item_id in publication")
    ids_by_url = {}
    for article in articles:
        url = canonicalize_source_url(article["block"]["original_url"])
        if url in ids_by_url and ids_by_url[url] != article["item_id"]:
            raise ContractError(f"canonical URL collision: {url}")
        ids_by_url[url] = article["item_id"]

    dates = sorted({issue["date"] for issue in issues}, reverse=True)
    by_id = {article["item_id"]: article for article in articles}
    summaries = {article["item_id"]: _article_summary(article) for article in articles}
    ordered = _sort_articles(list(summaries.values()))
    payloads = {
        "hnhot.json": {"schema_version": 1, "latest_date": dates[0] if dates else None, "dates": dates},
        "issues.json": {"schema_version": 1, "latest_date": dates[0] if dates else None, "dates": dates},
        "search-articles.json": {"schema_version": 1, "items": ordered},
    }
    issues_by_date = {issue["date"]: issue for issue in issues}
    for published_date in dates:
        issue = issues_by_date[published_date]
        front = [summaries[value] for value in issue["front_page_item_ids"] if value in summaries]
        world_ids = [
            article["item_id"] for page in issue["pages"] if page["page_name"] == "世界新闻"
            for article in page["articles"]
        ]
        world = [summaries[value] for value in world_ids if value in summaries]
        front_ids = {row["item_id"] for row in front}
        home_items = front + [row for row in world if row["item_id"] not in front_ids]
        payloads[f"front-page/{published_date}.json"] = {
            "schema_version": 1,
            "date": published_date,
            "source": issue["source"],
            "count": len(home_items),
            "national_ranking": [
                {**row, "rank": rank}
                for rank, row in enumerate([row for row in front if row["scope"] == "national"], 1)
            ],
            "world_ranking": [{**row, "rank": rank} for rank, row in enumerate(world, 1)],
            "items": home_items,
        }
        date_items = [row for row in ordered if row["published_date"] == published_date]
        payloads[f"issue-feed/{published_date}.json"] = {
            "schema_version": 1,
            "date": published_date,
            "count": len(date_items),
            "sections": issue["sections"],
            "items": date_items,
        }
    payloads.update(_build_subject_indexes(articles, summaries))
    payloads.update(_build_region_indexes(articles, summaries))
    payloads.update(_build_topic_indexes(articles, summaries))
    payloads.update(_build_event_indexes(articles, summaries))
    payloads.update(_build_plan_indexes(articles, summaries))
    payloads.update(_build_reader_indexes(articles))
    return payloads
