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

    def test_selected_indexes_are_title_only(self):
        indexes = build_indexes([stored_item(1, summary="私有摘要")], "2026-07-10")
        row = indexes["all/page-001.json"]["items"][0]
        self.assertEqual(
            set(row),
            {"item_id", "published_date", "daily_rank", "category", "title", "detail_path"},
        )
        self.assertNotIn("私有摘要", str(indexes))

    def test_search_indexes_separate_selected_and_issue_titles(self):
        indexes = build_search_indexes(
            [stored_item(1)], [public_issue_item(1), public_issue_item(2)]
        )
        self.assertEqual(len(indexes["search-selected.json"]["items"]), 1)
        self.assertEqual(len(indexes["search-issues.json"]["items"]), 2)

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
