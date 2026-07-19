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
            item["properties"]["scope"]["enum"],
            ["national", "hainan", "domestic", "mixed", "foreign"],
        )
        self.assertEqual(
            set(item["required"]),
            {
                "candidate_id", "ai_summary", "scope", "scope_evidence",
                "subjects", "location_mentions", "topic_mentions", "event_relation",
            },
        )
        for definition, required in {
            "subject": {"name", "type", "role", "evidence"},
            "location": {"location_id", "evidence"},
            "topic": {"topic_id", "evidence"},
        }.items():
            value = schema["$defs"][definition]
            self.assertFalse(value["additionalProperties"])
            self.assertEqual(set(value["required"]), required)

        variants = schema["$defs"]["event_relation"]["oneOf"]
        self.assertEqual(len(variants), 3)
        self.assertEqual(
            {variant["properties"]["relation"]["const"] for variant in variants},
            {"existing", "new", "none"},
        )
        expected_event_shapes = {
            "existing": {
                "event_id": {"type": "string", "minLength": 1},
                "event_name": {"type": "null"},
                "evidence": {"$ref": "#/$defs/evidence"},
                "update_summary": {"type": "string", "minLength": 1, "maxLength": 180},
            },
            "new": {
                "event_id": {"type": "null"},
                "event_name": {"type": "string", "minLength": 1, "maxLength": 120},
                "evidence": {"$ref": "#/$defs/evidence"},
                "update_summary": {"type": "string", "minLength": 1, "maxLength": 180},
            },
            "none": {
                "event_id": {"type": "null"},
                "event_name": {"type": "null"},
                "evidence": {"type": "null"},
                "update_summary": {"type": "null"},
            },
        }
        expected_keys = {"relation", "event_id", "event_name", "evidence", "update_summary"}
        for variant in variants:
            self.assertFalse(variant["additionalProperties"])
            self.assertEqual(set(variant["required"]), expected_keys)
            self.assertEqual(set(variant["properties"]), expected_keys)
            relation = variant["properties"]["relation"]["const"]
            for key, expected_shape in expected_event_shapes[relation].items():
                self.assertEqual(variant["properties"][key], expected_shape)
        for token in (
            "national", "hainan", "domestic", "mixed", "foreign", "不得猜测", "原文证据",
            "本地生活", "跨境贸易", "外国人在琼服务", "海南救援队赴广西救灾",
            "国际事件仅作为文章由头",
        ):
            self.assertIn(token, prompt)

    def test_seed_data_uses_local_and_open_scope_boundary(self):
        expected = {
            "2026-07-12": {
                "hndaily-20260712-58464-19696009": "hainan",
                "hndaily-20260712-58464-19696011": "mixed",
                "hndaily-20260712-58464-19696012": "hainan",
                "hndaily-20260712-58464-19696013": "domestic",
                "hndaily-20260712-58464-19696014": "mixed",
            },
            "2026-07-13": {
                "hndaily-20260713-58464-19697250": "hainan",
                "hndaily-20260713-58464-19697253": "hainan",
                "hndaily-20260713-58464-19697254": "mixed",
                "hndaily-20260713-58464-19697255": "mixed",
                "hndaily-20260713-58464-19697256": "hainan",
                "hndaily-20260713-58464-19697257": "hainan",
                "hndaily-20260713-58464-19697258": "mixed",
                "hndaily-20260713-58466-19697282": "domestic",
                "hndaily-20260713-58483-19698010": "national",
                "hndaily-20260713-58484-19698015": "national",
            },
            "2026-07-14": {
                "hndaily-20260714-58464-19700602": "national",
                "hndaily-20260714-58464-19700611": "mixed",
                "hndaily-20260714-58465-19700623": "domestic",
                "hndaily-20260714-58465-19700624": "mixed",
                "hndaily-20260714-58469-19700684": "foreign",
                "hndaily-20260714-58471-19700718": "mixed",
            },
        }
        for published_date, items in expected.items():
            for item_id, scope in items.items():
                path = ROOT / "content" / "issue-items" / published_date / f"{item_id}.json"
                payload = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(payload["scope"], scope, item_id)

    def test_controlled_catalogs_have_unique_ids_and_exact_fields(self):
        topics = json.loads((ROOT / "config/topics.json").read_text(encoding="utf-8"))
        self.assertEqual(set(topics), {"schema_version", "topics"})
        self.assertEqual(topics["schema_version"], 1)
        ids = [item["topic_id"] for item in topics["topics"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(
            ids,
            [
                "policy-governance", "industry-projects", "economy-data",
                "livelihood-services", "urban-rural", "ecology",
                "culture-tourism-sports", "education-talent", "health",
                "external-relations",
            ],
        )
        self.assertTrue(all(set(item) == {"topic_id", "name", "aliases"} for item in topics["topics"]))
        sections = json.loads((ROOT / "config/page-sections.json").read_text(encoding="utf-8"))
        self.assertEqual(set(sections), {"schema_version", "sections", "rules", "fallback"})
        self.assertEqual(sections["fallback"], "source_page_name")
        self.assertEqual(
            [section["section_id"] for section in sections["sections"]],
            ["front-page", "hainan-news", "world-news", "domestic-international", "theory"],
        )
        self.assertEqual(
            sections["rules"],
            [
                {"source_page_name": "头版", "section_id": "front-page"},
                {"source_page_name": "本省新闻", "section_id": "hainan-news"},
                {"source_page_name": "世界新闻", "section_id": "world-news"},
                {"source_page_name": "国内新闻", "section_id": "domestic-international"},
                {"source_page_name": "国际新闻", "section_id": "domestic-international"},
                {"source_page_name": "理论周刊", "section_id": "theory"},
            ],
        )
        subjects = json.loads((ROOT / "config/subjects.json").read_text(encoding="utf-8"))
        self.assertEqual(subjects, {"schema_version": 1, "subjects": []})


if __name__ == "__main__":
    unittest.main()
