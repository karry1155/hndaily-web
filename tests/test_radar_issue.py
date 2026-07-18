import unittest

from scripts.radar_adapter import adapt_hndaily
from scripts.radar_issue import build_public_issue, validate_public_issue
from scripts.radar_model import build_model_input, validate_model_output
from scripts.radar_scoring import score_semantic
from tests.radar_fixtures import model_output_for, raw_issue


@unittest.skip("retired schema-v5 scored-issue contract")
class RadarIssueTests(unittest.TestCase):
    def test_groups_every_scored_article_in_source_order(self):
        raw = raw_issue(article_count=3)
        candidates, _ = adapt_hndaily(raw)
        model_input = build_model_input(candidates)
        semantic = validate_model_output(
            model_input, model_output_for(model_input), candidates
        )
        scored = [score_semantic(item) for item in semantic]
        issue, issue_items = build_public_issue(raw, candidates, semantic, scored)
        self.assertEqual(issue["date"], "2026-07-08")
        self.assertEqual(issue["scored_article_count"], 3)
        self.assertEqual(
            [article["page_sequence"] for article in issue["pages"][0]["articles"]],
            [1, 2, 3],
        )
        self.assertEqual(len(issue_items), 3)
        self.assertNotIn("final_score", str(issue))
        self.assertNotIn("selected", str(issue_items))
        validate_public_issue(issue)

    def test_keeps_empty_newspaper_page(self):
        raw = raw_issue(article_count=2)
        raw["page_count"] = 2
        raw["pages"].append({
            "page": "008", "page_name": "公益广告",
            "page_url": "https://example.test/page-008",
            "pdf_url": "https://example.test/page-008.pdf",
            "article_count": 0, "articles": [],
        })
        candidates, _ = adapt_hndaily(raw)
        model_input = build_model_input(candidates)
        semantic = validate_model_output(
            model_input, model_output_for(model_input), candidates
        )
        issue, _ = build_public_issue(
            raw, candidates, semantic, [score_semantic(item) for item in semantic]
        )
        self.assertEqual(issue["pages"][-1]["page_name"], "公益广告")
        self.assertEqual(issue["pages"][-1]["articles"], [])


if __name__ == "__main__":
    unittest.main()
