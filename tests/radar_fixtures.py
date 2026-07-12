import json
import shutil
from pathlib import Path


def raw_issue(article_count=4, date="2026-07-08"):
    articles = [
        {
            "seq": index,
            "title": f"原始标题 {index}",
            "url": f"http://news.hndaily.cn/html/{date[:7]}/{date[-2:]}/content_58466_{19684000 + index}.htm",
            "author": "记者",
            "content": f"这是第 {index} 篇文章的正文，包含海南本地事实和明确细节。",
        }
        for index in range(1, article_count + 1)
    ]
    return {
        "source": "海南日报",
        "date": date,
        "fetched_at": f"{date}T08:00:00+08:00",
        "page_count": 1,
        "article_count": article_count,
        "pages": [
            {
                "page": "001",
                "page_name": "头版",
                "page_url": f"http://example.test/{date}/page-1",
                "pdf_url": f"http://example.test/{date}/page-1.pdf",
                "article_count": article_count,
                "articles": articles,
            }
        ],
    }


def raw_issue_with_skips():
    raw = raw_issue(article_count=2)
    raw["pages"][0]["articles"][1]["title"] = "导读"
    return raw


def model_output_for(model_input, score=8):
    return {
        "schema_version": model_input["schema_version"],
        "prompt_version": model_input["prompt_version"],
        "input_fingerprint": model_input["input_fingerprint"],
        "items": [
            {
                "candidate_id": item["candidate_id"],
                "ai_summary": f"{item['title']}的正文事实摘要。",
                "recommendation_reason": f"{item['title']}包含影响海南读者判断的具体信号，值得继续追踪。",
                "category": "民生",
                "hainan_relevance": score,
                "actionability": score,
                "impact_scope": score,
                "timeliness": score,
                "information_density": score,
                "score_reasons": {
                    "hainan_relevance": "直接涉及海南",
                    "actionability": "包含可采用的信息",
                    "impact_scope": "影响本地读者",
                    "timeliness": "属于当前出版日期",
                    "information_density": "正文包含具体事实",
                },
                "opportunity_lifecycle": "not_applicable",
                "deadline_date": None,
                "deadline_text": None,
                "deadline_evidence": None,
            }
            for item in model_input["items"]
        ],
    }


def semantic_item(**overrides):
    value = model_output_for(
        {
            "schema_version": 4,
            "prompt_version": "radar-v2",
            "input_fingerprint": "fixture",
            "items": [
                {"candidate_id": "A001", "title": "标题", "content": "正文"}
            ],
        }
    )["items"][0]
    value.update(overrides)
    return value


def scored_item(
    index, date="2026-07-10", final_score=70, relevance=8, density=7
):
    return {
        "item_id": f"item-{index:03d}",
        "published_date": date,
        "semantic_scores": {
            "hainan_relevance": relevance,
            "information_density": density,
        },
        "final_score": final_score,
    }


def stored_item(
    index,
    *,
    date="2026-07-10",
    category="民生",
    deadline=None,
    lifecycle=None,
    title=None,
    summary=None,
    reason=None,
    content=None,
):
    lifecycle = lifecycle or ("dated" if deadline else "not_applicable")
    return {
        "schema_version": 4,
        "item_id": f"item-{index:03d}",
        "published_date": date,
        "collected_date": "2026-07-10",
        "category": category,
        "semantic_scores": {
            "hainan_relevance": 8,
            "actionability": 8,
            "impact_scope": 8,
            "timeliness": 8,
            "information_density": 8,
        },
        "score_reasons": {
            "hainan_relevance": "海南",
            "actionability": "可行动",
            "impact_scope": "有影响",
            "timeliness": "当前",
            "information_density": "具体",
        },
        "base_score": 80.0,
        "final_score": 80.0,
        "selected": True,
        "daily_rank": index,
        "unselected_reason": None,
        "opportunity": {
            "lifecycle": lifecycle,
            "deadline_date": deadline,
            "deadline_text": f"{deadline}截止" if deadline else None,
            "evidence": (
                f"{deadline}截止"
                if deadline
                else ("长期有效" if lifecycle == "ongoing" else None)
            ),
        },
        "block": {
            "source": "海南日报",
            "title": title or f"原始标题 {index}",
            "content": content or f"第 {index} 篇完整正文。",
            "ai_summary": summary or f"第 {index} 篇摘要。",
            "recommendation_reason": reason or f"第 {index} 篇内容提供了值得继续追踪的海南本地信号。",
            "original_url": f"https://example.test/articles/{index}",
        },
    }


def public_issue_item(index, date="2026-07-10", title=None):
    return {
        "schema_version": 4,
        "item_id": f"issue-{index:03d}",
        "published_date": date,
        "collected_date": date,
        "page_number": "001",
        "page_name": "头版",
        "page_sequence": index,
        "block": {
            "source": "海南日报",
            "title": title or f"全部标题 {index}",
            "content": f"全部正文 {index}",
            "ai_summary": f"摘要 {index}",
            "original_url": f"https://example.test/issues/{index}",
        },
    }


def write_content_library(root: Path, count: int, include_weekly_fixture=False):
    from scripts.radar_indexes import build_indexes, build_issue_date_index, build_search_indexes

    items = [stored_item(index, category="民生") for index in range(1, count + 1)]
    for item in items:
        path = root / "items" / item["published_date"] / f"{item['item_id']}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.tmp")
        temporary.write_text(json.dumps(item, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)
    for relative, payload in build_indexes(items, "2026-07-10").items():
        path = root / "indexes" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)
    issue_items = [public_issue_item(index) for index in range(1, count + 1)]
    for item in issue_items:
        path = root / "issue-items" / item["published_date"] / f"{item['item_id']}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(item, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    issue = {"schema_version": 4, "date": "2026-07-10", "source": "海南日报", "page_count": 1, "scored_article_count": count, "pages": [{"page_number": "001", "page_name": "头版", "page_url": "https://example.test/page-001", "pdf_url": "https://example.test/page-001.pdf", "articles": [{"item_id": item["item_id"], "title": item["block"]["title"], "page_sequence": item["page_sequence"], "detail_path": f"/items/{item['published_date']}/{item['item_id']}/"} for item in issue_items]}]}
    (root / "issues").mkdir(parents=True, exist_ok=True)
    (root / "issues/2026-07-10.json").write_text(json.dumps(issue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    extra = {**build_search_indexes(items, issue_items), "issues.json": build_issue_date_index([issue])}
    for relative, payload in extra.items():
        path = root / "indexes" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if include_weekly_fixture:
        fixture = Path(__file__).resolve().parents[1] / "scripts/fixtures/weekly-valid.json"
        target = root / "weekly/2026-W28.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(fixture, target)
    return items
