import json
import tempfile
import unittest
from pathlib import Path

from scripts.finalize_radar import build_generation, finalize_to_store
from scripts.radar_adapter import adapt_hndaily
from scripts.radar_indexes import build_hnhot_indexes
from scripts.radar_locations import find_location_candidates, load_location_catalog
from scripts.radar_model import build_model_input, validate_model_output
from scripts.radar_render import build_site, validate_internal_links
from scripts.radar_store import load_issue_items, load_issues


ROOT = Path(__file__).resolve().parents[1]


class V43Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = json.loads(
            (ROOT / "examples/2026-07-23.demo-source.json").read_text(encoding="utf-8")
        )
        cls.model_input = json.loads(
            (ROOT / "examples/2026-07-23.demo-input.json").read_text(encoding="utf-8")
        )
        cls.model_output = json.loads(
            (ROOT / "examples/2026-07-23.demo-output.json").read_text(encoding="utf-8")
        )

    def test_contract_is_v43_without_legacy_fact_array(self):
        schema = json.loads(
            (ROOT / "prompts/article-enrichment/v4.3/schema.json").read_text(encoding="utf-8")
        )
        self.assertEqual(schema["properties"]["schema_version"]["const"], 13)
        self.assertEqual(schema["properties"]["prompt_version"]["const"], "hnhot-v4.3")
        item_properties = schema["$defs"]["item"]["properties"]
        self.assertNotIn("observations", item_properties)
        self.assertIn("activities", schema["$defs"]["subject"]["properties"])
        self.assertEqual(
            schema["$defs"]["event"]["properties"]["event_type"]["enum"],
            ["recurring_edition", "named_event", "incident"],
        )
        topics = json.loads((ROOT / "config/topics.json").read_text(encoding="utf-8"))
        self.assertEqual(
            schema["$defs"]["primaryTopic"]["properties"]["category_id"]["enum"],
            [row["category_id"] for row in topics["categories"]],
        )

    def test_location_candidates_drop_province_ancestor(self):
        candidates = find_location_candidates(
            "海南省海口市", "报道发生在海南省海口市", load_location_catalog()
        )
        self.assertEqual([row["location_id"] for row in candidates], ["hainan-haikou"])

    def test_example_input_is_deterministic_and_output_validates(self):
        candidates, _ = adapt_hndaily(self.raw)
        self.assertEqual(build_model_input(candidates), self.model_input)
        semantics = validate_model_output(self.model_input, self.model_output, candidates)
        self.assertEqual(len(semantics), 3)
        self.assertEqual(semantics[0]["subjects"][1]["activities"][0]["place"], "海口市")
        self.assertEqual(semantics[2]["reader_leads"][0]["intent"], "register")

    def test_generation_grows_each_page_from_first_json(self):
        articles, issue, audit = build_generation(
            self.raw, self.model_input, self.model_output
        )
        indexes = build_hnhot_indexes([issue], articles)
        self.assertEqual(audit["schema_version"], 13)
        self.assertNotIn("observations", articles[0])
        self.assertTrue(indexes["subjects.json"]["items"])
        self.assertTrue(indexes["events.json"]["items"])
        self.assertTrue(indexes["regions.json"]["items"])
        self.assertTrue(indexes["topics.json"]["roots"])
        self.assertTrue(indexes["plans.json"]["items"])
        self.assertEqual(indexes["reader-leads.json"]["count"], 1)
        liu_id = articles[0]["subjects"][1]["subject_id"]
        feed = indexes[f"subject-feed/{liu_id}.json"]
        self.assertEqual(feed["activities"][0]["headline"], "刘小明主持服务业例会并部署重点工作")
        self.assertEqual(feed["activities"][0]["source"]["source_title"], self.raw["pages"][0]["articles"][0]["title"])

    def test_finalize_and_render_are_self_contained(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            content, site = root / "content", root / "site"
            audit = root / "audit.json"
            finalize_to_store(
                self.raw, self.model_input, self.model_output, content, audit
            )
            self.assertEqual(len(load_issues(content)), 1)
            self.assertEqual(len(load_issue_items(content)), 3)
            build_site(content, site)
            validate_internal_links(site)
            for route in (
                "index.html", "subjects/index.html", "regions/index.html",
                "topics/index.html", "events/index.html", "plans/index.html",
                "reminders/index.html",
            ):
                self.assertTrue((site / route).is_file(), route)
            article_html = next((site / "items").glob("*/*/index.html")).read_text(encoding="utf-8")
            self.assertIn("报道标记", article_html)
            self.assertNotIn("可复用事实", article_html)


if __name__ == "__main__":
    unittest.main()
