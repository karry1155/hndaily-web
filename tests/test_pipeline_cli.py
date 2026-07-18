import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

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
                json_root / "model-input/2026-07-08.json",
            )
            self.assertTrue(Path(lines["MODEL_INPUT_JSON"]).is_file())
            self.assertEqual(
                Path(lines["MODEL_OUTPUT_JSON"]),
                json_root / "model-output/2026-07-08.json",
            )
            self.assertEqual(
                Path(lines["PREFILTER_JSON"]),
                json_root / "audits/2026-07-08.prefilter.json",
            )
            self.assertTrue(Path(lines["PREFILTER_JSON"]).is_file())
            self.assertEqual(
                Path(lines["EDITORIAL_AUDIT_JSON"]),
                json_root / "audits/2026-07-08.editorial-audit.json",
            )
            self.assertNotIn("这是第", result.stdout)


if __name__ == "__main__":
    unittest.main()
