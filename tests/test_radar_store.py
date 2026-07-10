import tempfile
import unittest
from pathlib import Path

from scripts.radar_store import commit_generation, load_items
from tests.radar_fixtures import stored_item


class RadarStoreTests(unittest.TestCase):
    def test_same_item_id_is_upserted_without_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = stored_item(1, summary="第一版摘要")
            second = stored_item(1, summary="第二版摘要")
            commit_generation(root, [first], {}, {"2026-07-10"})
            commit_generation(root, [second], {}, {"2026-07-10"})
            items = load_items(root)
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]["block"]["ai_summary"], "第二版摘要")

    def test_failed_commit_restores_previous_items_and_indexes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old = stored_item(1)
            commit_generation(
                root,
                [old],
                {"all/page-001.json": {"items": []}},
                {"2026-07-10"},
            )
            with self.assertRaises(RuntimeError):
                commit_generation(
                    root,
                    [stored_item(2)],
                    {},
                    {"2026-07-10"},
                    fail_after_items=True,
                )
            self.assertEqual(
                [item["item_id"] for item in load_items(root)], [old["item_id"]]
            )

    def test_rejects_item_with_model_owned_or_missing_block_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            invalid = stored_item(1)
            invalid["block"]["page"] = "003"
            with self.assertRaisesRegex(ValueError, "block fields"):
                commit_generation(Path(tmp), [invalid], {}, {"2026-07-10"})
