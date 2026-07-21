from pathlib import Path


def raw_issue(article_count=4, date="2026-07-08"):
    articles = [
        {
            "seq": index,
            "title": f"原始标题 {index}",
            "url": (
                f"http://news.hndaily.cn/html/{date[:7]}/{date[-2:]}/"
                f"content_58466_{19684000 + index}.htm"
            ),
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


def model_output_for(model_input):
    return {
        "schema_version": model_input["schema_version"],
        "prompt_version": model_input["prompt_version"],
        "input_fingerprint": model_input["input_fingerprint"],
        "items": [
            {
                "candidate_id": item["candidate_id"],
                "ai_summary": f'{item["title"]}的正文事实摘要。',
                "scope": "hainan",
                "scope_evidence": item["title"],
                "subjects": [],
                "location_mentions": [],
                "topic_profile": {
                    "primary": {
                        "name": "社区慈善",
                        "evidence": item["title"],
                    },
                    "secondary": [],
                },
                "content_form": "news",
                "events": [],
                "plans": [],
            }
            for item in model_input["items"]
        ],
    }


def write_content_library(root: Path, count: int, date="2026-07-10"):
    from scripts.finalize_radar import finalize_to_store
    from scripts.radar_adapter import adapt_hndaily
    from scripts.radar_model import build_model_input

    raw = raw_issue(article_count=count, date=date)
    candidates, _ = adapt_hndaily(raw)
    model_input = build_model_input(candidates)
    finalize_to_store(
        raw,
        model_input,
        model_output_for(model_input),
        root,
        root / "publication-audit.json",
    )
