import json
import tempfile
import unittest
from pathlib import Path

from scripts.radar_render import build_site

ROOT = Path(__file__).resolve().parents[1]
RAW_FIXTURES = ROOT / "tests/fixtures/raw-hndaily"


class RadarRealDateTests(unittest.TestCase):
    def test_committed_selected_items_have_distinct_recommendation_reasons(self):
        for published_date in ("2026-07-08", "2026-07-09"):
            for path in (ROOT / "content/items" / published_date).glob("*.json"):
                item = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(item["schema_version"], 5)
                reason = item["block"]["recommendation_reason"].strip()
                summary = item["block"]["ai_summary"].strip()
                self.assertTrue(reason)
                self.assertNotEqual("".join(reason.split()), "".join(summary.split()))

    def test_committed_two_date_library_renders_both_dates(self):
        self.assertTrue((ROOT / "content/items/2026-07-08").is_dir())
        self.assertTrue((ROOT / "content/items/2026-07-09").is_dir())
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp) / "site"; build_site(ROOT / "content", site)
            homepage = (site / "index.html").read_text(encoding="utf-8")
            self.assertIn("2026-07-09", homepage)
            self.assertTrue((site / "date/2026-07-08/index.html").is_file())
            self.assertTrue((site / "date/2026-07-09/index.html").is_file())

    def test_real_july_10_is_newest_and_recent_manifest_has_three_dates(self):
        self.assertTrue((ROOT / "content/items/2026-07-10").is_dir())
        manifest = json.loads(
            (ROOT / "content/indexes/recent-selected.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            manifest["dates"],
            ["2026-07-10", "2026-07-09", "2026-07-08"],
        )
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp) / "site"
            build_site(ROOT / "content", site)
            homepage = (site / "index.html").read_text(encoding="utf-8")
            self.assertIn("7月10日", homepage)
            self.assertTrue(
                (site / "static/selected-feed/2026-07-09.json").is_file()
            )
            self.assertTrue(
                (site / "static/selected-feed/2026-07-08.json").is_file()
            )

    def test_local_real_0708_and_0709_sources_are_distinct(self):
        paths = [
            RAW_FIXTURES / "2026-07-08.json",
            RAW_FIXTURES / "2026-07-09.json",
        ]
        raw_0708 = json.loads(paths[0].read_text(encoding="utf-8"))
        raw_0709 = json.loads(paths[1].read_text(encoding="utf-8"))
        self.assertEqual(raw_0708["date"], "2026-07-08")
        self.assertEqual(raw_0709["date"], "2026-07-09")
        self.assertNotEqual(
            [a["url"] for p in raw_0708["pages"] for a in p["articles"]],
            [a["url"] for p in raw_0709["pages"] for a in p["articles"]],
        )

    def test_real_dates_publish_scored_articles_by_newspaper_page(self):
        for date, page_count, scored_count in (
            ("2026-07-08", 8, 29),
            ("2026-07-09", 7, 27),
        ):
            issue = json.loads((ROOT / "content/issues" / f"{date}.json").read_text(encoding="utf-8"))
            self.assertEqual(issue["page_count"], page_count)
            self.assertEqual(issue["scored_article_count"], scored_count)
            self.assertEqual(scored_count, len(list((ROOT / "content/issue-items" / date).glob("*.json"))))
            self.assertEqual(
                [page["page_number"] for page in issue["pages"]],
                sorted(page["page_number"] for page in issue["pages"]),
            )
