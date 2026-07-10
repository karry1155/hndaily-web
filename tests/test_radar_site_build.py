import tempfile
import unittest
from pathlib import Path

from scripts.radar_render import build_site, validate_internal_links
from tests.radar_fixtures import write_content_library


class RadarSiteBuildTests(unittest.TestCase):
    def test_builds_all_category_date_detail_and_pagination_routes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); content = root / "content"; site = root / "site"
            write_content_library(content, 21); build_site(content, site)
            self.assertTrue((site / "index.html").is_file())
            self.assertTrue((site / "page/2/index.html").is_file())
            self.assertTrue((site / "category/livelihood/index.html").is_file())
            self.assertTrue((site / "date/2026-07-10/index.html").is_file())
            self.assertEqual(validate_internal_links(site), [])

    def test_preserves_weekly_routes_when_weekly_content_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); content = root / "content"; site = root / "site"
            write_content_library(content, 1, True); build_site(content, site)
            self.assertTrue((site / "weekly/2026-W28/index.html").is_file())
            self.assertTrue((site / "weekly/index.html").is_file())

    def test_broken_build_keeps_previous_public_site(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); site = root / "site"; site.mkdir()
            (site / "index.html").write_text("previous", encoding="utf-8")
            with self.assertRaises(ValueError): build_site(root / "missing-content", site)
            self.assertEqual((site / "index.html").read_text(encoding="utf-8"), "previous")
