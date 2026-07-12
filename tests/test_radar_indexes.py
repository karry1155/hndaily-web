import unittest

from scripts.radar_indexes import build_indexes, build_search_indexes
from tests.radar_fixtures import public_issue_item, stored_item


class RadarIndexTests(unittest.TestCase):
    def test_paginates_twenty_items_without_full_content(self):
        items = [stored_item(index, category="民生") for index in range(1, 22)]
        indexes = build_indexes(items, "2026-07-10")
        self.assertEqual(len(indexes["all/page-001.json"]["items"]), 20)
        self.assertEqual(len(indexes["all/page-002.json"]["items"]), 1)
        self.assertNotIn("content", str(indexes["all/page-001.json"]))

    def test_selected_indexes_include_summary_and_recommendation_reason(self):
        indexes = build_indexes(
            [stored_item(1, summary="私有摘要", reason="这条信息揭示海南本地变化。")],
            "2026-07-10",
        )
        row = indexes["all/page-001.json"]["items"][0]
        self.assertEqual(
            set(row),
            {"item_id", "published_date", "daily_rank", "category", "title", "ai_summary", "recommendation_reason", "final_score", "detail_path"},
        )
        self.assertEqual(row["ai_summary"], "私有摘要")
        self.assertEqual(row["recommendation_reason"], "这条信息揭示海南本地变化。")
        self.assertEqual(row["final_score"], 80.0)

    def test_selected_feeds_publish_all_nonempty_dates(self):
        items = [
            stored_item(1, date="2026-07-07"),
            stored_item(2, date="2026-07-08"),
            stored_item(3, date="2026-07-09"),
            stored_item(4, date="2026-07-10"),
        ]
        indexes = build_indexes(items, "2026-07-10")
        self.assertEqual(
            indexes["recent-selected.json"]["dates"],
            ["2026-07-10", "2026-07-09", "2026-07-08", "2026-07-07"],
        )
        self.assertIn("selected-feed/2026-07-07.json", indexes)
        self.assertEqual(indexes["selected-feed/2026-07-10.json"]["count"], 1)

    def test_search_indexes_separate_selected_and_issue_titles(self):
        indexes = build_search_indexes(
            [stored_item(1)], [public_issue_item(1), public_issue_item(2)]
        )
        self.assertEqual(len(indexes["search-selected.json"]["items"]), 1)
        self.assertEqual(len(indexes["search-issues.json"]["items"]), 2)
        self.assertIn(
            "recommendation_reason", indexes["search-selected.json"]["items"][0]
        )
        self.assertNotIn(
            "recommendation_reason", indexes["search-issues.json"]["items"][0]
        )

    def test_opportunity_active_and_expired_indexes_are_separate(self):
        active = stored_item(1, category="机会", deadline="2026-07-11")
        expired = stored_item(2, category="机会", deadline="2026-07-09")
        unspecified = stored_item(3, category="机会", lifecycle="unspecified")
        indexes = build_indexes([expired, unspecified, active], "2026-07-10")
        active_ids = [
            item["item_id"]
            for item in indexes[
                "categories/opportunity/active-page-001.json"
            ]["items"]
        ]
        expired_ids = [
            item["item_id"]
            for item in indexes[
                "categories/opportunity/expired-page-001.json"
            ]["items"]
        ]
        self.assertEqual(active_ids, [active["item_id"], unspecified["item_id"]])
        self.assertEqual(expired_ids, [expired["item_id"]])
