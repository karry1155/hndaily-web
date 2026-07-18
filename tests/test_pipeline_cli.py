import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.radar_fixtures import model_output_for, raw_issue as radar_raw_issue
from tests.test_prepare_model_input import raw_issue


ROOT = Path(__file__).resolve().parents[1]


class PipelineCliTests(unittest.TestCase):
    def test_pipeline_prepares_stable_codex_handoff_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            temporary_root = Path(tmp)
            raw_path = temporary_root / "2026-07-08.json"
            raw_path.write_text(json.dumps(raw_issue(), ensure_ascii=False), encoding="utf-8")
            json_root = temporary_root / "data/json"
            env = os.environ.copy()
            env.update(
                {
                    "HNDAILY_WEB_DIR": str(ROOT),
                    "HNDAILY_RAW_JSON": str(raw_path),
                    "HNDAILY_JSON_ROOT": str(json_root),
                }
            )

            result = subprocess.run(
                ["bash", str(ROOT / "scripts" / "run_daily_pipeline.sh")],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            lines = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
            self.assertEqual(lines["RAW_JSON"], str(raw_path))
            self.assertEqual(
                Path(lines["MODEL_INPUT_JSON"]),
                json_root / "model-input/editorial-v1/2026-07-08.json",
            )
            self.assertTrue(Path(lines["MODEL_INPUT_JSON"]).is_file())
            self.assertEqual(
                Path(lines["MODEL_OUTPUT_JSON"]),
                json_root / "model-output/editorial-v1/2026-07-08.json",
            )
            self.assertEqual(
                Path(lines["PREFILTER_JSON"]),
                json_root / "audits/editorial-v1/2026-07-08.prefilter.json",
            )
            self.assertTrue(Path(lines["PREFILTER_JSON"]).is_file())
            self.assertEqual(
                Path(lines["EDITORIAL_AUDIT_JSON"]),
                json_root / "audits/editorial-v1/2026-07-08.editorial-audit.json",
            )
            self.assertNotIn("这是第", result.stdout)

    @unittest.skip("retired radar-v3 model fixture; namespace coverage remains elsewhere")
    def test_radar_and_editorial_runs_keep_same_date_artifacts_isolated(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            raw_path = work / "2026-07-09.json"
            raw_path.write_text(
                json.dumps(radar_raw_issue(date="2026-07-09"), ensure_ascii=False),
                encoding="utf-8",
            )
            json_root = work / "data/json"
            env = os.environ | {
                "HNDAILY_WEB_DIR": str(ROOT),
                "HNDAILY_RAW_JSON": str(raw_path),
                "HNDAILY_JSON_ROOT": str(json_root),
                "RADAR_CONTENT_ROOT": str(work / "content"),
                "RADAR_SITE_ROOT": str(work / "site"),
                "RADAR_RUN_ROOT": str(work / "run"),
                "RADAR_AS_OF": "2026-07-10",
            }
            radar_command = [
                "bash",
                str(ROOT / "scripts" / "run_radar_pipeline.sh"),
                "2026-07-09",
            ]

            radar_first = subprocess.run(
                radar_command,
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(radar_first.returncode, 2, radar_first.stderr)
            radar_paths = dict(
                line.split("=", 1)
                for line in radar_first.stdout.splitlines()
                if "=" in line
            )
            radar_input_path = Path(radar_paths["MODEL_INPUT_JSON"])
            radar_input_before = radar_input_path.read_bytes()

            editorial = subprocess.run(
                ["bash", str(ROOT / "scripts" / "run_daily_pipeline.sh")],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(editorial.returncode, 0, editorial.stderr)
            editorial_paths = dict(
                line.split("=", 1)
                for line in editorial.stdout.splitlines()
                if "=" in line
            )

            for radar_key, editorial_key in (
                ("MODEL_INPUT_JSON", "MODEL_INPUT_JSON"),
                ("MODEL_OUTPUT_JSON", "MODEL_OUTPUT_JSON"),
                ("PREFILTER_JSON", "PREFILTER_JSON"),
            ):
                self.assertNotEqual(
                    Path(radar_paths[radar_key]),
                    Path(editorial_paths[editorial_key]),
                )
            self.assertEqual(radar_input_path.read_bytes(), radar_input_before)

            radar_input = json.loads(radar_input_path.read_text(encoding="utf-8"))
            Path(radar_paths["MODEL_OUTPUT_JSON"]).write_text(
                json.dumps(model_output_for(radar_input), ensure_ascii=False),
                encoding="utf-8",
            )
            radar_complete = subprocess.run(
                radar_command,
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(radar_complete.returncode, 0, radar_complete.stderr)
            self.assertIn("STATUS=COMPLETE", radar_complete.stdout)


if __name__ == "__main__":
    unittest.main()
