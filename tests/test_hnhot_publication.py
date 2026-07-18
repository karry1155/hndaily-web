import json
import tempfile
import unittest
from pathlib import Path

from scripts.finalize_radar import build_generation, finalize_to_store
from scripts.radar_adapter import adapt_hndaily
from scripts.radar_model import ModelOutputError, build_model_input, validate_model_output
from scripts.radar_render import build_site, render_primary_nav, validate_internal_links
from tests.radar_fixtures import raw_issue


def hnhot_output(model_input, candidates):
    return {
        "schema_version": 7,
        "prompt_version": "hnhot-v1",
        "input_fingerprint": model_input["input_fingerprint"],
        "items": [
            {
                "candidate_id": candidate["candidate_id"],
                "ai_summary": f'{candidate["title"]}的事实摘要。',
                "scope": "hainan",
                "scope_evidence": candidate["title"],
                "subjects": [],
                "location_mentions": [],
                "topic_mentions": [],
                "event_relation": {
                    "relation": "none", "event_id": None, "event_name": None,
                    "evidence": None, "update_summary": None,
                },
            }
            for candidate in candidates
        ],
    }


class HnhotPublicationTests(unittest.TestCase):
    def test_schema_v7_input_and_output_are_exact_and_grounded(self):
        raw = raw_issue(article_count=2)
        candidates = adapt_hndaily(raw)[0]
        model_input = build_model_input(candidates)
        self.assertEqual(model_input["schema_version"], 7)
        self.assertEqual(model_input["prompt_version"], "hnhot-v1")
        self.assertEqual(
            set(model_input["items"][0]),
            {"candidate_id", "title", "content", "location_candidates", "topic_candidates", "event_candidates"},
        )
        output = hnhot_output(model_input, candidates)
        self.assertEqual(validate_model_output(model_input, output, candidates), output["items"])
        output["items"][0]["score"] = 10
        with self.assertRaises(ModelOutputError):
            validate_model_output(model_input, output, candidates)

    def test_every_valid_article_is_published_without_selection_fields(self):
        raw = raw_issue(article_count=11)
        candidates = adapt_hndaily(raw)[0]
        model_input = build_model_input(candidates)
        articles, issue, audit = build_generation(raw, model_input, hnhot_output(model_input, candidates))
        self.assertEqual(len(articles), 11)
        self.assertEqual(issue["article_count"], 11)
        self.assertEqual(audit["published_count"], 11)
        serialized = json.dumps({"articles": articles, "issue": issue}, ensure_ascii=False)
        for retired in ("final_score", "selected", "recommendation_reason", "daily_rank"):
            self.assertNotIn(retired, serialized)

    def test_finalize_writes_hnhot_indexes_and_logical_sections(self):
        raw = raw_issue(article_count=3)
        candidates = adapt_hndaily(raw)[0]
        model_input = build_model_input(candidates)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            finalize_to_store(
                raw, model_input, hnhot_output(model_input, candidates),
                root, root / "audit.json", raw["date"],
            )
            issue = json.loads((root / "issues" / f'{raw["date"]}.json').read_text(encoding="utf-8"))
            self.assertEqual(issue["schema_version"], 7)
            self.assertEqual(issue["sections"][0]["name"], "头版")
            self.assertTrue((root / "indexes/hnhot.json").is_file())
            self.assertTrue((root / f'indexes/front-page/{raw["date"]}.json').is_file())

    def test_bundled_content_builds_four_route_site_without_broken_links(self):
        project = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp) / "site"
            build_site(project / "content", site)
            for route in ("index.html", "all/index.html", "daily/index.html", "more/index.html"):
                self.assertTrue((site / route).is_file(), route)
            home = (site / "index.html").read_text(encoding="utf-8")
            all_page = (site / "all/index.html").read_text(encoding="utf-8")
            self.assertIn("全国要闻 TOP", home)
            self.assertIn("海南关联", home)
            self.assertIn("本省新闻", all_page)
            self.assertNotIn("第002版", all_page)
            self.assertEqual(validate_internal_links(site), [])

    def test_mobile_navigation_uses_final_four_labels(self):
        rendered = render_primary_nav("头版")
        for label in ("头版", "全部", "日报", "更多"):
            self.assertIn(f"<span>{label}</span>", rendered)
        for retired in ("精选", "全部信息", "AI 日报"):
            self.assertNotIn(retired, rendered)


if __name__ == "__main__":
    unittest.main()
