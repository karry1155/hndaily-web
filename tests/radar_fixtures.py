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
