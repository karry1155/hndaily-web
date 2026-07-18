import tempfile
import unittest
from pathlib import Path

from scripts.radar_store import commit_generation, load_items
from tests.radar_fixtures import stored_item
from scripts.radar_issue import build_public_issue
from scripts.radar_adapter import adapt_hndaily
from scripts.radar_model import build_model_input, validate_model_output
from scripts.radar_scoring import score_semantic
from tests.radar_fixtures import model_output_for, raw_issue


class RadarStoreTests(unittest.TestCase):
    def _issue(self):
        raw = raw_issue(article_count=2)
        candidates, _ = adapt_hndaily(raw)
        model_input = build_model_input(candidates)
        semantic = validate_model_output(model_input, model_output_for(model_input), candidates)
        return build_public_issue(raw, candidates, semantic, [score_semantic(item) for item in semantic])

    @unittest.skip("retired schema-v5 issue fixture")
    def test_stores_public_issue_and_issue_items(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            issue, issue_items = self._issue()
            commit_generation(root, [], {}, {"2026-07-08"}, issues=[issue], issue_items=issue_items)
            self.assertTrue((root / "issues/2026-07-08.json").is_file())
            self.assertEqual(len(list((root / "issue-items/2026-07-08").glob("*.json"))), 2)
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
