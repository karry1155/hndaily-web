import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROMPT_DIR = ROOT / "prompts/article-enrichment/v1"


class HnhotAssetTests(unittest.TestCase):
    def test_manifest_binds_prompt_and_strict_schema(self):
        manifest = json.loads((PROMPT_DIR / "manifest.json").read_text(encoding="utf-8"))
        schema = json.loads((PROMPT_DIR / "schema.json").read_text(encoding="utf-8"))
        prompt = (PROMPT_DIR / "prompt.md").read_text(encoding="utf-8")
        self.assertEqual(
            manifest,
            {
                "schema_version": 1,
                "prompt_version": "hnhot-v1",
                "article_schema_version": 7,
                "prompt": "prompt.md",
                "output_schema": "schema.json",
            },
        )
        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertFalse(schema["additionalProperties"])
        item = schema["$defs"]["item"]
        self.assertFalse(item["additionalProperties"])
        self.assertEqual(
            set(item["required"]),
            {
                "candidate_id", "ai_summary", "scope", "scope_evidence",
                "subjects", "location_mentions", "topic_mentions", "event_relation",
            },
        )
        for token in ("national", "hainan", "mixed", "不得猜测", "原文证据"):
            self.assertIn(token, prompt)

    def test_controlled_catalogs_have_unique_ids_and_exact_fields(self):
        topics = json.loads((ROOT / "config/topics.json").read_text(encoding="utf-8"))
        self.assertEqual(set(topics), {"schema_version", "topics"})
        self.assertEqual(topics["schema_version"], 1)
        ids = [item["topic_id"] for item in topics["topics"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(set(item) == {"topic_id", "name", "aliases"} for item in topics["topics"]))
        sections = json.loads((ROOT / "config/page-sections.json").read_text(encoding="utf-8"))
        self.assertEqual(set(sections), {"schema_version", "sections", "rules", "fallback"})
        self.assertEqual(sections["fallback"], "source_page_name")
        subjects = json.loads((ROOT / "config/subjects.json").read_text(encoding="utf-8"))
        self.assertEqual(subjects, {"schema_version": 1, "subjects": []})


if __name__ == "__main__":
    unittest.main()
