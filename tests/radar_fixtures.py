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
            "schema_version": 3,
            "prompt_version": "radar-v1",
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
