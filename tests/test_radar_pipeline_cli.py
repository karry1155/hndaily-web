import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.radar_fixtures import model_output_for, raw_issue

ROOT = Path(__file__).resolve().parents[1]


@unittest.skip("retired radar-v3 pipeline fixture")
class RadarPipelineCliTests(unittest.TestCase):
    def test_prepare_then_resume_completes_same_date_idempotently(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp); raw = work / "2026-07-09.json"
            raw.write_text(json.dumps(raw_issue(date="2026-07-09"), ensure_ascii=False), encoding="utf-8")
            json_root = work / "data/json"
            env = os.environ | {
                "HNDAILY_WEB_DIR": str(ROOT),
                "HNDAILY_RAW_JSON": str(raw),
                "HNDAILY_JSON_ROOT": str(json_root),
                "RADAR_CONTENT_ROOT": str(work / "content"),
                "RADAR_SITE_ROOT": str(work / "site"),
                "RADAR_RUN_ROOT": str(work / "run"),
                "RADAR_AS_OF": "2026-07-10",
            }
            command = ["bash", str(ROOT / "scripts/run_radar_pipeline.sh"), "2026-07-09"]
            first = subprocess.run(command, env=env, text=True, capture_output=True)
            self.assertEqual(first.returncode, 2)
            paths = dict(line.split("=", 1) for line in first.stdout.splitlines() if "=" in line)
            self.assertEqual(
                Path(paths["MODEL_INPUT_JSON"]),
                json_root / "model-input/2026-07-09.json",
            )
            self.assertEqual(
                Path(paths["MODEL_OUTPUT_JSON"]),
                json_root / "model-output/2026-07-09.json",
            )
            self.assertEqual(
                Path(paths["PREFILTER_JSON"]),
                json_root / "audits/2026-07-09.prefilter.json",
            )
            self.assertEqual(
                Path(paths["AUDIT_JSON"]),
                json_root / "audits/2026-07-09.publication.json",
            )
            model_input = json.loads(Path(paths["MODEL_INPUT_JSON"]).read_text(encoding="utf-8"))
            Path(paths["MODEL_OUTPUT_JSON"]).write_text(json.dumps(model_output_for(model_input), ensure_ascii=False), encoding="utf-8")
            second = subprocess.run(command, env=env, text=True, capture_output=True)
            third = subprocess.run(command, env=env, text=True, capture_output=True)
            self.assertEqual(second.returncode, 0, second.stderr); self.assertEqual(third.returncode, 0, third.stderr)
            self.assertIn("STATUS=COMPLETE", second.stdout)
            self.assertTrue((work / "site/index.html").is_file())
            self.assertEqual(len(list((work / "content/items/2026-07-09").glob("*.json"))), 4)
