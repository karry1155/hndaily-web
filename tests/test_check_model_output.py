import unittest

from scripts.check_model_output import output_matches_input, source_anchor_errors
from scripts.radar_model import build_model_input
from scripts.radar_adapter import adapt_hndaily
from tests.radar_fixtures import model_output_for, raw_issue


class CheckModelOutputTests(unittest.TestCase):
    def setUp(self):
        candidates, _ = adapt_hndaily(raw_issue(article_count=1))
        self.model_input = build_model_input(candidates)

    def test_valid_output_has_no_source_anchor_errors(self):
        output = model_output_for(self.model_input)
        self.assertTrue(output_matches_input(self.model_input, output))
        self.assertEqual(source_anchor_errors(self.model_input, output), [])

    def test_reports_all_paraphrased_source_anchors_together(self):
        output = model_output_for(self.model_input)
        item = output["items"][0]
        item["scope_evidence"] = "这是一段原文中没有的范围概括"
        item["subjects"] = [
            {
                "name": "原文中不存在的机构",
                "type": "organization",
                "role": None,
                "evidence": "这也是一段概括",
            }
        ]

        errors = source_anchor_errors(self.model_input, output)

        self.assertEqual(len(errors), 3)
        self.assertTrue(any("scope_evidence" in error for error in errors))
        self.assertTrue(any(".name" in error for error in errors))
        self.assertTrue(any(".evidence" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
