import copy
import unittest

from scripts.prepare_model_input import InputError, build_model_input


def raw_issue(article_count=4):
    articles = [
        {
            "seq": index,
            "title": f"原始标题 {index}",
            "url": f"http://example.test/article-{index}",
            "author": "记者",
            "content": f"这是第 {index} 篇文章的正文。",
        }
        for index in range(1, article_count + 1)
    ]
    return {
        "source": "海南日报",
        "date": "2026-07-08",
        "fetched_at": "2026-07-08T08:00:00+08:00",
        "page_count": 1,
        "article_count": article_count,
        "pages": [
            {
                "page": "001",
                "page_name": "头版",
                "page_url": "http://example.test/page-1",
                "pdf_url": "http://example.test/page-1.pdf",
                "article_count": article_count,
                "articles": articles,
            }
        ],
    }


class BuildModelInputTests(unittest.TestCase):
    def test_selects_first_three_and_exposes_only_semantic_input(self):
        result = build_model_input(raw_issue())

        self.assertEqual([item["candidate_id"] for item in result["items"]], ["A001", "A002", "A003"])
        self.assertEqual(result["items"][0]["original_title"], "原始标题 1")
        self.assertEqual(result["items"][2]["content"], "这是第 3 篇文章的正文。")
        for item in result["items"]:
            self.assertEqual(set(item), {"candidate_id", "original_title", "content"})
        self.assertEqual(set(result), {"schema_version", "prompt_version", "input_fingerprint", "items"})

    def test_fingerprint_is_stable_and_changes_with_selected_content(self):
        raw = raw_issue()
        first = build_model_input(raw)
        second = build_model_input(copy.deepcopy(raw))
        raw["pages"][0]["articles"][0]["content"] += "变化"
        changed = build_model_input(raw)

        self.assertEqual(first["input_fingerprint"], second["input_fingerprint"])
        self.assertNotEqual(first["input_fingerprint"], changed["input_fingerprint"])

    def test_uses_all_articles_when_issue_has_fewer_than_three(self):
        result = build_model_input(raw_issue(article_count=2))
        self.assertEqual([item["candidate_id"] for item in result["items"]], ["A001", "A002"])

    def test_rejects_selected_article_missing_canonical_url(self):
        raw = raw_issue()
        raw["pages"][0]["articles"][1]["url"] = ""

        with self.assertRaisesRegex(InputError, "url"):
            build_model_input(raw)

    def test_rejects_declared_article_count_mismatch(self):
        raw = raw_issue()
        raw["article_count"] = 99

        with self.assertRaisesRegex(InputError, "article_count"):
            build_model_input(raw)


if __name__ == "__main__":
    unittest.main()
