import unittest

from scripts.radar_filter import evaluate_issue


def article(seq, title, content="这是足够具体的正文内容。", **extra):
    return {
        "seq": seq,
        "title": title,
        "url": f"http://example.test/{seq}",
        "author": "记者",
        "content": content,
        **extra,
    }


def page(number, name, articles):
    return {
        "page": number,
        "page_name": name,
        "page_url": f"http://example.test/page-{number}",
        "pdf_url": f"http://example.test/page-{number}.pdf",
        "article_count": len(articles),
        "articles": articles,
    }


class RadarFilterTests(unittest.TestCase):
    def test_records_every_article_with_high_confidence_skip_reasons(self):
        pages = [
            page(
                "001",
                "头版",
                [
                    article(1, "正常报道", "甲" * 450),
                    article(2, "导读", "今日导读"),
                    article(3, "短讯", "短消息"),
                    article(4, "工作会议召开", "会议听取了工作汇报。"),
                    article(5, "空正文", ""),
                    article(6, "抓取失败", "残缺", error="fetch failed: timeout"),
                    article(7, "正常报道", "◀上接A01版\n\n这是前文的续接内容。"),
                ],
            ),
            page("004", "理论周刊 新论", [article(1, "理论文章", "乙" * 500)]),
            page("008", "公益广告", [article(1, "公益广告内容", "丙" * 500)]),
        ]
        raw = {"page_count": len(pages), "article_count": 9, "pages": pages}

        records = evaluate_issue(raw)
        by_title = {item["original_title"]: item for item in records}

        self.assertEqual(len(records), raw["article_count"])
        self.assertEqual(by_title["导读"]["skip_reason"], "guide")
        self.assertEqual(by_title["理论文章"]["skip_reason"], "theory_weekly")
        self.assertEqual(
            by_title["公益广告内容"]["skip_reason"], "public_service_ad_page"
        )
        self.assertEqual(by_title["空正文"]["skip_reason"], "empty_content")
        self.assertEqual(by_title["抓取失败"]["skip_reason"], "fetch_error")
        continuation = next(
            item for item in records if item["content"].startswith("◀上接A01版")
        )
        self.assertEqual(
            continuation["skip_reason"], "continued_from_previous_page"
        )
        self.assertEqual(continuation["matched_rules"], ["content_prefix:上接版"])
        self.assertEqual(by_title["短讯"]["length_band"], "under_200")
        self.assertTrue(by_title["短讯"]["passed"])
        self.assertTrue(by_title["工作会议召开"]["passed"])
        self.assertEqual(
            [item["candidate_id"] for item in records],
            [f"A{i:03d}" for i in range(1, 10)],
        )

    def test_continuation_prefix_accepts_common_punctuation_and_spacing(self):
        variants = [
            "上接A01版\n正文",
            "◀ 上接 A01 版\n正文",
            "（上接A1版）\n正文",
        ]
        pages = [page("002", "本省新闻", [article(i + 1, f"续篇{i}", text) for i, text in enumerate(variants)])]
        raw = {"page_count": 1, "article_count": len(variants), "pages": pages}
        self.assertTrue(
            all(
                record["skip_reason"] == "continued_from_previous_page"
                for record in evaluate_issue(raw)
            )
        )


if __name__ == "__main__":
    unittest.main()
