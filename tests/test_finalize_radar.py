import json
import tempfile
import unittest
from pathlib import Path

from scripts.finalize_radar import FinalizeError, build_items, finalize_to_store
from scripts.radar_adapter import adapt_hndaily
from scripts.radar_model import build_model_input
from scripts.radar_store import load_items
from tests.radar_fixtures import model_output_for, raw_issue


class FinalizeRadarTests(unittest.TestCase):
    def test_resolves_model_location_to_canonical_stored_entity(self):
        raw = raw_issue(article_count=1)
        raw["pages"][0]["articles"][0]["title"] = "三沙调研"
        raw["pages"][0]["articles"][0]["content"] = "省委书记冯飞在三沙市调研经济社会发展情况。"
        candidates = adapt_hndaily(raw)[0]
        model_input = build_model_input(candidates)
        output = model_output_for(model_input, 9)
        output["items"][0].update({
            "actors": [{"name":"冯飞","type":"person","role":"省委书记","evidence":"省委书记冯飞在三沙市调研"}],
            "location_mentions": [{"location_id":"hainan-sansha","evidence":"三沙市"}],
            "action": "调研经济社会发展情况",
            "action_evidence": "调研经济社会发展情况",
        })
        items, _ = build_items(raw, model_input, output)
        self.assertEqual(items[0]["entities"]["locations"][0]["name"], "三沙市")
        self.assertEqual(items[0]["entities"]["locations"][0]["code"], "460300")
    def test_source_fields_are_injected_from_raw_and_title_is_not_rewritten(self):
        raw = raw_issue()
        candidates, _ = adapt_hndaily(raw)
        model_input = build_model_input(candidates)
        items, audit = build_items(raw, model_input, model_output_for(model_input, 9))
        self.assertEqual(items[0]["block"]["title"], raw["pages"][0]["articles"][0]["title"])
        self.assertEqual(items[0]["block"]["original_url"], raw["pages"][0]["articles"][0]["url"])
        self.assertEqual(
            items[0]["block"]["recommendation_reason"],
            model_output_for(model_input, 9)["items"][0]["recommendation_reason"],
        )
        self.assertEqual(audit["selected_count"], len(items))

    def test_more_than_eight_qualified_items_are_persisted(self):
        raw = raw_issue(article_count=11)
        candidates, _ = adapt_hndaily(raw)
        model_input = build_model_input(candidates)
        with tempfile.TemporaryDirectory() as tmp:
            finalize_to_store(raw, model_input, model_output_for(model_input, 9), Path(tmp), Path(tmp) / "audit.json", "2026-07-10")
            self.assertEqual(len(load_items(Path(tmp))), 11)

    def test_every_scored_candidate_is_published_to_full_issue(self):
        raw = raw_issue(article_count=3)
        candidates, _ = adapt_hndaily(raw)
        model_input = build_model_input(candidates)
        output = model_output_for(model_input, 9)
        output["items"][2]["hainan_relevance"] = 0
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            finalize_to_store(raw, model_input, output, root, root / "audit.json", "2026-07-10")
            issue = json.loads((root / "issues/2026-07-08.json").read_text(encoding="utf-8"))
            self.assertEqual(issue["scored_article_count"], 3)
            self.assertEqual(len(list((root / "issue-items/2026-07-08").glob("*.json"))), 3)
            self.assertEqual(len(load_items(root)), 2)
            selected_search = json.loads((root / "indexes/search-selected.json").read_text(encoding="utf-8"))
            issue_search = json.loads((root / "indexes/search-issues.json").read_text(encoding="utf-8"))
            issue_dates = json.loads((root / "indexes/issues.json").read_text(encoding="utf-8"))
            self.assertEqual(len(selected_search["items"]), 2)
            self.assertEqual(len(issue_search["items"]), 3)
            self.assertEqual(issue_dates["latest_date"], "2026-07-08")

    def test_replacement_is_recorded_in_audit(self):
        raw = raw_issue()
        candidates, _ = adapt_hndaily(raw)
        model_input = build_model_input(candidates)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit = root / "audit.json"
            finalize_to_store(raw, model_input, model_output_for(model_input, 8), root, audit, "2026-07-10")
            finalize_to_store(raw, model_input, model_output_for(model_input, 9), root, audit, "2026-07-10")
            payload = json.loads(audit.read_text(encoding="utf-8"))
            self.assertEqual(len(payload["replaced_items"]), 4)
            self.assertEqual(payload["replaced_items"][0]["previous_schema_version"], 5)

    def test_rerun_replaces_only_same_source_and_date_selection(self):
        raw = raw_issue(article_count=2)
        candidates, _ = adapt_hndaily(raw)
        model_input = build_model_input(candidates)
        first = model_output_for(model_input, 9)
        second = model_output_for(model_input, 9)
        second["items"][1]["hainan_relevance"] = 0
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            finalize_to_store(raw, model_input, first, root, root / "audit.json", "2026-07-10")
            finalize_to_store(raw, model_input, second, root, root / "audit.json", "2026-07-10")
            self.assertEqual(len(load_items(root)), 1)

    def test_invalid_output_does_not_replace_existing_library(self):
        raw = raw_issue()
        candidates, _ = adapt_hndaily(raw)
        model_input = build_model_input(candidates)
        output = model_output_for(model_input)
        output["items"][0]["title"] = "模型越权"
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FinalizeError):
                finalize_to_store(raw, model_input, output, Path(tmp), Path(tmp) / "audit.json", "2026-07-10")
            self.assertEqual(load_items(Path(tmp)), [])
