import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class RepositoryBoundaryTests(unittest.TestCase):
    def test_active_runtime_has_no_external_crawler_dependency(self):
        runtime_files = [
            ROOT / "scripts/run_radar_pipeline.sh",
            ROOT / "scripts/run_daily_pipeline.sh",
            ROOT / "scripts/crawler.py",
            ROOT / ".env.example",
        ]
        forbidden = (
            "HNDAILY_SKILL_DIR",
            "/Users/skr/Work/hndaily/hndaily-skill",
            "../hndaily-skill",
            "HNDAILY_INTERMEDIATE_DIR",
            "data/intermediate",
        )
        for path in runtime_files:
            text = path.read_text(encoding="utf-8")
            for value in forbidden:
                self.assertNotIn(value, text, f"{path}: {value}")

    def test_readme_names_canonical_json_outputs(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for value in (
            "HNHOT",
            "scripts/crawler.py",
            "data/json/raw/",
            "data/json/model-input/",
            "data/json/model-output/",
            "data/json/audits/",
            "prompts/article-enrichment/v1/",
        ):
            self.assertIn(value, readme)


if __name__ == "__main__":
    unittest.main()
