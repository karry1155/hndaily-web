import json
import os
import tempfile
import unittest
from pathlib import Path

from scripts.radar_render import build_site

ROOT = Path(__file__).resolve().parents[1]
SKILL_DATA = ROOT.parent / "hndaily-skill" / "_data"


class RadarRealDateTests(unittest.TestCase):
    def test_committed_two_date_library_renders_both_dates(self):
        self.assertTrue((ROOT / "content/items/2026-07-08").is_dir())
        self.assertTrue((ROOT / "content/items/2026-07-09").is_dir())
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp) / "site"; build_site(ROOT / "content", site)
            homepage = (site / "index.html").read_text(encoding="utf-8")
            self.assertIn("2026-07-09", homepage)
            self.assertTrue((site / "date/2026-07-08/index.html").is_file())
            self.assertTrue((site / "date/2026-07-09/index.html").is_file())

    def test_local_real_0708_and_0709_sources_are_distinct(self):
        required = os.environ.get("RADAR_REAL_DATA_REQUIRED") == "1"
        paths = [SKILL_DATA / "2026-07-08.json", SKILL_DATA / "2026-07-09.json"]
        if not all(path.is_file() for path in paths):
            if required: self.fail("RADAR_REAL_DATA_REQUIRED=1 but a real raw date is missing")
            self.skipTest("local ignored crawler data is unavailable")
        raw_0708 = json.loads(paths[0].read_text(encoding="utf-8")); raw_0709 = json.loads(paths[1].read_text(encoding="utf-8"))
        self.assertEqual(raw_0708["date"], "2026-07-08"); self.assertEqual(raw_0709["date"], "2026-07-09")
        self.assertNotEqual([a["url"] for p in raw_0708["pages"] for a in p["articles"]], [a["url"] for p in raw_0709["pages"] for a in p["articles"]])
