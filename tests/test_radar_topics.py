import copy
import unittest

from scripts.radar_topics import (
    TopicResolutionError,
    automatic_topic_resolution,
    build_topic_resolution_input,
    load_topic_catalog,
    merge_topic_catalog,
    resolve_topic_profile,
    validate_topic_catalog,
    validate_topic_resolution_output,
)


class RadarTopicsTests(unittest.TestCase):
    def setUp(self):
        self.catalog = load_topic_catalog()

    def output_with(self, name):
        return {
            "schema_version": 9,
            "items": [{
                "candidate_id": "A001",
                "topic_profile": {
                    "primary": {"name": name, "evidence": "原文证据"},
                    "secondary": [],
                },
            }],
        }

    def test_catalog_is_a_stable_tree_with_unique_surfaces(self):
        catalog = validate_topic_catalog(copy.deepcopy(self.catalog))
        roots = [row for row in catalog["topics"] if row["parent_id"] is None]
        self.assertEqual(len(roots), 15)
        self.assertGreater(len(catalog["topics"]), len(roots))
        self.assertIn("古法制盐", {row["name"] for row in catalog["topics"]})

    def test_exact_open_topic_resolves_automatically_to_stable_id(self):
        resolution_input = build_topic_resolution_input(
            self.output_with("古法制盐"), self.catalog
        )
        self.assertEqual(resolution_input["catalog_topics"], self.catalog["topics"])
        output = automatic_topic_resolution(resolution_input)
        self.assertEqual(output["items"], [{
            "source_name": "古法制盐",
            "decision": "existing",
            "topic_id": "traditional-saltmaking",
        }])
        items = validate_topic_resolution_output(
            resolution_input, output, self.catalog
        )
        resolved = resolve_topic_profile(
            self.output_with("古法制盐")["items"][0]["topic_profile"],
            items,
            self.catalog,
        )
        self.assertEqual(resolved[0]["path"], ["文化与历史", "古法制盐"])

    def test_unseen_topic_requires_explicit_new_node_decision(self):
        resolution_input = build_topic_resolution_input(
            self.output_with("儋州调声"), self.catalog
        )
        self.assertIsNone(automatic_topic_resolution(resolution_input))
        output = {
            "schema_version": 1,
            "input_fingerprint": resolution_input["input_fingerprint"],
            "items": [{
                "source_name": "儋州调声",
                "decision": "new",
                "topic_id": "danzhou-diaosheng",
                "name": "儋州调声",
                "parent_id": "culture-history",
                "aliases": [],
                "definition": "儋州地区的传统民间歌唱艺术及其传承。",
                "include": ["调声表演与传承"],
                "exclude": ["泛音乐活动"],
            }],
        }
        items = validate_topic_resolution_output(
            resolution_input, output, self.catalog
        )
        merged = merge_topic_catalog(self.catalog, items)
        self.assertEqual(merged["topics"][-1]["name"], "儋州调声")

    def test_tampered_resolution_input_fingerprint_is_rejected(self):
        resolution_input = build_topic_resolution_input(
            self.output_with("古法制盐"), self.catalog
        )
        resolution_input["topics"][0]["name"] = "泛文化"
        with self.assertRaisesRegex(TopicResolutionError, "fingerprint"):
            automatic_topic_resolution(resolution_input)


if __name__ == "__main__":
    unittest.main()
