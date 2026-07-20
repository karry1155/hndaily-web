import json
import tempfile
import unittest
from pathlib import Path

from scripts.radar_gold_review import (
    REQUIRED_ITEMS,
    build_review_dataset,
    save_gold_payload,
    validate_gold_payload,
    write_review_site,
)


ROOT = Path(__file__).resolve().parents[1]


def gold_payload(dataset):
    items = []
    for row in dataset["items"]:
        if not row["selected"]:
            continue
        items.append(
            {
                "item_id": row["item_id"],
                "candidate_id": row["candidate_id"],
                "published_date": row["published_date"],
                "page_number": row["page_number"],
                "page_name": row["page_name"],
                "page_sequence": row["page_sequence"],
                "title": row["title"],
                "source_fingerprint": row["source_fingerprint"],
                "required": row["required"],
                "review_status": row["review_status"],
                "expected": json.loads(json.dumps(row["expected"], ensure_ascii=False)),
            }
        )
    return {
        "schema_version": 1,
        "benchmark_id": dataset["benchmark_id"],
        "status": "draft",
        "source_dates": dataset["source_dates"],
        "target_count": len(items),
        "reviewed_count": sum(row["review_status"] == "reviewed" for row in items),
        "items": items,
    }


class GoldReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dataset = build_review_dataset(ROOT)

    def test_dataset_selects_42_balanced_cases_and_locks_required_front_page(self):
        selected = [row for row in self.dataset["items"] if row["selected"]]
        self.assertEqual(len(selected), 42)
        self.assertEqual(
            {date: sum(row["published_date"] == date for row in selected) for date in self.dataset["source_dates"]},
            {"2026-07-17": 14, "2026-07-18": 14, "2026-07-19": 14},
        )
        required = {
            (row["published_date"], row["candidate_id"])
            for row in self.dataset["items"]
            if row["required"]
        }
        self.assertEqual(required, REQUIRED_ITEMS)

    def test_required_cases_are_prefilled_with_open_world_expectations(self):
        rows = {
            row["candidate_id"]: row
            for row in self.dataset["items"]
            if row["published_date"] == "2026-07-19" and row["required"]
        }
        self.assertEqual(rows["A002"]["expected"]["background_mentions"], ["习近平"])
        self.assertEqual(
            [row["name"] for row in rows["A002"]["expected"]["primary_subjects"]],
            ["冯飞", "刘小明"],
        )
        self.assertIn("2026世界人工智能大会", rows["A001"]["expected"]["named_events"][0]["name"])
        self.assertEqual(rows["A003"]["expected"]["projects"], [{"name": "海南环岛旅游公路"}])

    def test_dataset_keeps_initial_expected_for_browser_draft_migration(self):
        row = next(
            row for row in self.dataset["items"]
            if row["published_date"] == "2026-07-17" and row["candidate_id"] == "A001"
        )
        self.assertIn("initial_expected", row)
        self.assertNotEqual(row["initial_expected"], row["expected"])

    def test_validated_gold_can_be_saved_atomically(self):
        payload = gold_payload(self.dataset)
        self.assertIs(validate_gold_payload(payload), payload)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "gold.json"
            self.assertEqual(save_gold_payload(payload, path), path)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), payload)

    def test_nested_expected_shapes_are_validated(self):
        payload = gold_payload(self.dataset)
        payload["items"][0]["expected"]["facts"] = [
            {
                "occurred_on": "",
                "actors": [],
                "action": "",
                "object": "",
                "locations": [],
                "summary": "",
            }
        ]
        with self.assertRaises(ValueError):
            validate_gold_payload(payload)

    def test_review_site_contains_data_and_workbench_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp)
            write_review_site(ROOT, site)
            page = (site / "review/gold/index.html").read_text(encoding="utf-8")
            data = json.loads((site / "review/gold/data.json").read_text(encoding="utf-8"))
            self.assertIn("文章语义基准工作台", page)
            self.assertIn("A001–A003 强制回归", page)
            self.assertEqual(data["target_count"], 42)


if __name__ == "__main__":
    unittest.main()
