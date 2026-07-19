import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL_NAME = "hndaily" + "-skill"


class RepositoryBoundaryTests(unittest.TestCase):
    def test_active_runtime_has_no_external_crawler_dependency(self):
        tracked_runtime_paths = subprocess.check_output(
            ["git", "-C", str(ROOT), "ls-files", "--", "scripts", ".env.example"],
            text=True,
        ).splitlines()
        forbidden = (
            "HNDAILY_SKILL_DIR",
            f"/Users/skr/Work/hndaily/{SKILL_NAME}",
            f"../{SKILL_NAME}",
            "HNDAILY_INTERMEDIATE_DIR",
            "data/intermediate",
        )
        self.assertIn(".env.example", tracked_runtime_paths)
        self.assertIn("scripts/run_radar_pipeline.sh", tracked_runtime_paths)
        for relative_path in tracked_runtime_paths:
            path = ROOT / relative_path
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
            for value in forbidden:
                self.assertNotIn(value, text, f"{path}: {value}")

    def test_tracked_tests_have_no_adjacent_skill_fixtures(self):
        tracked_paths = subprocess.check_output(
            ["git", "-C", str(ROOT), "ls-files", "tests"], text=True
        ).splitlines()
        parent_markers = ("ROOT" + ".parent /", "parents[" + "2] /")
        for relative_path in tracked_paths:
            path = ROOT / relative_path
            if not path.exists():
                continue
            if path.suffix != ".py":
                continue
            text = path.read_text(encoding="utf-8")
            self.assertNotIn(SKILL_NAME, text, f"{path}: adjacent skill fixture")
            for marker in parent_markers:
                self.assertNotIn(marker, text, f"{path}: parent fixture path")

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

    def test_json_readme_documents_only_hnhot_v1_artifacts(self):
        readme = (ROOT / "data/json/README.md").read_text(encoding="utf-8")
        for value in (
            "model-input/YYYY-MM-DD.json",
            "model-output/YYYY-MM-DD.json",
            "audits/YYYY-MM-DD.prefilter.json",
            "audits/YYYY-MM-DD.publication.json",
            "hnhot-v1",
        ):
            self.assertIn(value, readme)
        self.assertNotIn("editorial-v1", readme)

    def test_runtime_has_no_retired_selection_or_digest_modules(self):
        retired = (
            "run_daily_pipeline.sh",
            "finalize_digest.py",
            "radar_scoring.py",
            "radar_select.py",
            "content/items",
            "editorial-v1",
        )
        runtime = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (ROOT / "scripts").glob("*")
            if path.is_file() and path.suffix in {".py", ".sh"}
        )
        for value in retired:
            self.assertNotIn(value, runtime)


if __name__ == "__main__":
    unittest.main()
