import json
import tempfile
import unittest
from pathlib import Path

from scripts.finalize_digest import ModelOutputError, build_digest, finalize_to_path
from scripts.prepare_model_input import build_model_input
from tests.test_prepare_model_input import raw_issue


def semantic_output(model_input):
    return {
        "schema_version": model_input["schema_version"],
        "prompt_version": model_input["prompt_version"],
        "input_fingerprint": model_input["input_fingerprint"],
        "items": [
            {
                "candidate_id": item["candidate_id"],
                "title": f"提炼：{item['original_title']}",
                "summary": f"{item['original_title']}的事实摘要。",
                "why_it_matters": "这件事包含今天值得关注的明确变化。",
                "key_facts": ["事实一", "事实二"],
                "confidence": "full_text",
            }
            for item in model_input["items"]
        ],
    }


class FinalizeDigestTests(unittest.TestCase):
    def setUp(self):
        self.raw = raw_issue()
        self.model_input = build_model_input(self.raw)
        self.model_output = semantic_output(self.model_input)

    def test_injects_canonical_sources_from_raw_json(self):
        digest = build_digest(self.raw, self.model_input, self.model_output)

        self.assertEqual(len(digest["top_items"]), 3)
        for index, item in enumerate(digest["top_items"], 1):
            raw_article = self.raw["pages"][0]["articles"][index - 1]
            self.assertEqual(
                item["sources"],
                [{"headline": raw_article["title"], "page": "001", "url": raw_article["url"]}],
            )
            self.assertEqual(item["summary"], f"原始标题 {index}的事实摘要。")

    def test_rejects_source_fields_from_model(self):
        self.model_output["items"][0]["url"] = "http://evil.test/fake"

        with self.assertRaisesRegex(ModelOutputError, "unknown fields.*url"):
            build_digest(self.raw, self.model_input, self.model_output)

    def test_rejects_missing_extra_duplicate_and_reordered_ids(self):
        mutations = []
        mutations.append(self.model_output["items"][:-1])
        extra = list(self.model_output["items"]) + [dict(self.model_output["items"][0], candidate_id="A999")]
        mutations.append(extra)
        duplicate = list(self.model_output["items"])
        duplicate[1] = dict(duplicate[1], candidate_id="A001")
        mutations.append(duplicate)
        mutations.append(list(reversed(self.model_output["items"])))

        for items in mutations:
            output = dict(self.model_output, items=items)
            with self.subTest(ids=[item["candidate_id"] for item in items]):
                with self.assertRaisesRegex(ModelOutputError, "candidate_id order"):
                    build_digest(self.raw, self.model_input, output)

    def test_rejects_empty_semantic_content(self):
        self.model_output["items"][0]["summary"] = ""
        with self.assertRaisesRegex(ModelOutputError, "summary"):
            build_digest(self.raw, self.model_input, self.model_output)

        self.model_output = semantic_output(self.model_input)
        self.model_output["items"][0]["key_facts"] = []
        with self.assertRaisesRegex(ModelOutputError, "key_facts"):
            build_digest(self.raw, self.model_input, self.model_output)

    def test_invalid_output_does_not_replace_existing_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "digest.json"
            output_path.write_text('{"existing": true}\n', encoding="utf-8")
            self.model_output["items"][0]["sources"] = []

            with self.assertRaises(ModelOutputError):
                finalize_to_path(self.raw, self.model_input, self.model_output, output_path)

            self.assertEqual(json.loads(output_path.read_text(encoding="utf-8")), {"existing": True})


if __name__ == "__main__":
    unittest.main()
