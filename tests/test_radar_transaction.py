import tempfile
import unittest
from pathlib import Path

from scripts.radar_transaction import prepare_staged_content, publish_staged_generation
from tests.radar_fixtures import write_content_library


class RadarTransactionTests(unittest.TestCase):
    def test_publishes_issue_families_with_content_generation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); content = root / "content"; site = root / "site"; audit = root / "audit.json"
            write_content_library(content, 1)
            staged_content = root / "run/content"; staged_site = root / "run/site"; staged_audit = root / "run/audit.json"
            prepare_staged_content(content, staged_content)
            write_content_library(staged_content, 2)
            staged_site.mkdir(parents=True); (staged_site / "index.html").write_text("new", encoding="utf-8")
            staged_audit.write_text("audit", encoding="utf-8")
            publish_staged_generation(content, staged_content, site, staged_site, audit, staged_audit)
            self.assertTrue((content / "issues/2026-07-10.json").is_file())
            self.assertEqual(len(list((content / "issue-items/2026-07-10").glob("*.json"))), 2)

    def test_publish_failure_restores_content_site_and_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); content = root / "content"; site = root / "site"; audit = root / "audit.json"
            write_content_library(content, 1); site.mkdir(); (site / "index.html").write_text("old site", encoding="utf-8"); audit.write_text("old audit", encoding="utf-8")
            staged_content = root / "run/content"; staged_site = root / "run/site"; staged_audit = root / "run/audit.json"
            prepare_staged_content(content, staged_content); write_content_library(staged_content, 2)
            staged_site.mkdir(parents=True); (staged_site / "index.html").write_text("new site", encoding="utf-8"); staged_audit.write_text("new audit", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                publish_staged_generation(content, staged_content, site, staged_site, audit, staged_audit, fail_after_content=True)
            self.assertEqual((site / "index.html").read_text(encoding="utf-8"), "old site")
            self.assertEqual(audit.read_text(encoding="utf-8"), "old audit")
            self.assertEqual(
                len(list((content / "issue-items/2026-07-10").glob("*.json"))),
                1,
            )
