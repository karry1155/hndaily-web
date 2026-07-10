import unittest

from scripts.editorial_scoring import ScoringError, score_candidate, validate_semantic_item


def semantic(**overrides):
    value = {
        "candidate_id": "A001",
        "title": "提炼标题",
        "summary": "正文事实摘要。",
        "why_it_matters": "这会影响海南用户。",
        "key_facts": ["事实一"],
        "confidence": "full_text",
        "suggested_category": "民生/办事",
        "hainan_relevance": 8,
        "actionability": 8,
        "impact_scope": 6,
        "novelty": 4,
        "information_density": 8,
        "score_reasons": {
            "hainan_relevance": "直接涉及海南",
            "actionability": "可据此办理",
            "impact_scope": "影响缴存人",
            "novelty": "新增用途",
            "information_density": "含日期与条件",
        },
    }
    value.update(overrides)
    return value


def candidate(**overrides):
    value = {
        "candidate_id": "A001",
        "page": "001",
        "page_name": "本省新闻",
        "seq": 1,
        "original_title": "海南政策有新变化",
        "author": "本报记者",
        "content": "海南" + "甲" * 150,
        "content_length": 152,
        "length_band": "under_200",
    }
    value.update(overrides)
    return value


class EditorialScoringTests(unittest.TestCase):
    def test_calculates_explainable_base_and_adjustments(self):
        result = score_candidate(candidate(), semantic())

        self.assertEqual(result["base_score"], 70.0)
        self.assertEqual(result["final_score"], 69.0)
        self.assertEqual([item["points"] for item in result["adjustments"]], [4, 3, -8])
        self.assertIn("基础语义分 70.0", result["score_explanation"])
        self.assertIn("= 最终分 69.0", result["score_explanation"])

    def test_suppresses_positive_layout_points_for_national_reprint_without_hainan_link(self):
        result = score_candidate(candidate(
            page_name="头版",
            original_title="全国科技事业发展综述",
            author="新华社记者",
            content="全国科技事业发展取得新进展。" * 20,
            content_length=280,
            length_band="200_to_399",
        ), semantic())

        self.assertNotIn(4, [item["points"] for item in result["adjustments"]])
        self.assertTrue(result["national_reprint_without_hainan_link"])

    def test_rejects_non_integer_or_out_of_range_semantic_scores(self):
        for invalid in (True, 1.5, -1, 11):
            item = semantic(hainan_relevance=invalid)
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(ScoringError, "hainan_relevance"):
                    validate_semantic_item(item, "item")


if __name__ == "__main__":
    unittest.main()
