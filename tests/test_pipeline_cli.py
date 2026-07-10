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
            env = os.environ.copy()
            env.update(
                {
                    "HNDAILY_WEB_DIR": str(ROOT),
                    "HNDAILY_RAW_JSON": str(raw_path),
                    "HNDAILY_INTERMEDIATE_DIR": str(temporary_root / "intermediate"),
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
            self.assertTrue(Path(lines["MODEL_INPUT_JSON"]).is_file())
            self.assertTrue(Path(lines["PREFILTER_JSON"]).is_file())
            self.assertEqual(
                lines["MODEL_OUTPUT_JSON"],
                str(temporary_root / "intermediate" / "2026-07-08.model-output.json"),
            )
            self.assertEqual(
                lines["EDITORIAL_AUDIT_JSON"],
                str(temporary_root / "intermediate" / "2026-07-08.editorial-audit.json"),
            )
            self.assertNotIn("这是第", result.stdout)


if __name__ == "__main__":
    unittest.main()
