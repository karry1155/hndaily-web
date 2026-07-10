import unittest

from scripts.radar_scoring import score_semantic
from scripts.radar_select import select_focus, select_items
from tests.radar_fixtures import scored_item, semantic_item


class RadarSelectionTests(unittest.TestCase):
    def test_score_has_no_page_or_length_adjustments(self):
        result = score_semantic(
            semantic_item(
                hainan_relevance=8,
                actionability=8,
                impact_scope=6,
                timeliness=4,
                information_density=8,
            )
        )
        self.assertEqual(result["base_score"], 70.0)
        self.assertEqual(result["final_score"], 70.0)
        self.assertNotIn("adjustments", result)

    def test_selects_every_qualified_item_without_eight_item_cap(self):
        values = [scored_item(index, final_score=80) for index in range(1, 12)]
        selected, decisions = select_items(list(reversed(values)))
        self.assertEqual(len(selected), 11)
        self.assertEqual(
            [item["daily_rank"] for item in selected], list(range(1, 12))
        )
        self.assertTrue(all(item["selected"] for item in decisions))

    def test_focus_uses_latest_three_content_dates_and_recency_penalty(self):
        values = [
            scored_item(1, date="2026-07-10", final_score=80),
            scored_item(2, date="2026-07-09", final_score=82),
            scored_item(3, date="2026-07-08", final_score=84),
            scored_item(4, date="2026-07-07", final_score=100),
            scored_item(5, date="2026-07-10", final_score=79),
        ]
        focus = select_focus(values)
        self.assertNotIn("item-004", [item["item_id"] for item in focus])
        self.assertEqual(
            [item["focus_score"] for item in focus], [80, 79, 79, 78]
        )
        self.assertEqual([item["focus_rank"] for item in focus], [1, 2, 3, 4])


if __name__ == "__main__":
    unittest.main()
