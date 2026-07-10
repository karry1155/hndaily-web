import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.radar_adapter import adapt_hndaily
from scripts.radar_model import (
    ModelOutputError,
    build_model_input,
    validate_model_output,
)
from tests.radar_fixtures import model_output_for, raw_issue

ROOT = Path(__file__).resolve().parents[1]


class RadarModelTests(unittest.TestCase):
    def setUp(self):
        self.candidates, _ = adapt_hndaily(raw_issue())
        self.model_input = build_model_input(self.candidates)
        self.output = model_output_for(self.model_input)

    def test_input_exposes_only_id_title_and_content(self):
        self.assertEqual(
            set(self.model_input["items"][0]),
            {"candidate_id", "title", "content"},
        )
        self.assertNotIn("original_url", str(self.model_input))

    def test_accepts_one_category_and_nullable_opportunity_fields(self):
        items = validate_model_output(
            self.model_input, self.output, self.candidates
        )
        self.assertEqual(items[0]["category"], "民生")
        self.assertEqual(items[0]["opportunity_lifecycle"], "not_applicable")

    def test_rejects_model_owned_source_field(self):
        invalid = copy.deepcopy(self.output)
        invalid["items"][0]["title"] = "模型改写标题"
        with self.assertRaisesRegex(ModelOutputError, "unknown fields"):
            validate_model_output(self.model_input, invalid, self.candidates)

    def test_rejects_dated_opportunity_without_body_evidence(self):
        invalid = copy.deepcopy(self.output)
        invalid["items"][0].update(
            {
                "category": "机会",
                "opportunity_lifecycle": "dated",
                "deadline_date": "2026-07-31",
                "deadline_text": "7月31日截止",
                "deadline_evidence": "正文并不存在的截止信息",
            }
        )
        with self.assertRaisesRegex(ModelOutputError, "deadline_evidence"):
            validate_model_output(self.model_input, invalid, self.candidates)

    def test_prepare_cli_writes_model_input_and_full_prefilter_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw_path = root / "raw.json"
            input_path = root / "model-input.json"
            audit_path = root / "prefilter.json"
            raw_path.write_text(
                json.dumps(raw_issue(), ensure_ascii=False), encoding="utf-8"
            )
            result = subprocess.run(
                [
                    "python3",
                    str(ROOT / "scripts/prepare_radar.py"),
                    str(raw_path),
                    str(input_path),
                    str(audit_path),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                len(json.loads(input_path.read_text(encoding="utf-8"))["items"]),
                4,
            )
            self.assertEqual(
                len(json.loads(audit_path.read_text(encoding="utf-8"))["records"]),
                4,
            )


if __name__ == "__main__":
    unittest.main()
