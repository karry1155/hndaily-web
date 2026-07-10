import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.finalize_digest import ModelOutputError, build_digest, finalize_to_path
from scripts.prepare_model_input import build_model_input
from tests.test_prepare_model_input import raw_issue


def distinct_raw_issue(article_count=4):
    raw = raw_issue(article_count=article_count)
    topics = [
        "住房公积金物业费办理条件和线上申请渠道",
        "固体废物回收拆解监管体系和专项执法行动",
        "洋浦港保税能源物流国际转运业务进展",
        "住宅小区电力抄表到户改造覆盖居民情况",
        "大学生科技见习岗位征集对象与截止日期",
        "省属国资科技创新债券发行规模和票面利率",
    ]
    for index, article in enumerate(raw["pages"][0]["articles"]):
        article["content"] = topics[index] * 3
    return raw


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
                "suggested_category": "民生/办事",
                "hainan_relevance": 8,
                "actionability": 8,
                "impact_scope": 7,
                "novelty": 6,
                "information_density": 8,
                "score_reasons": {
                    "hainan_relevance": "涉及海南",
                    "actionability": "可以行动",
                    "impact_scope": "影响多人",
                    "novelty": "包含变化",
                    "information_density": "包含事实",
                },
            }
            for item in model_input["items"]
        ],
    }


class FinalizeDigestTests(unittest.TestCase):
    def setUp(self):
        self.raw = distinct_raw_issue()
        self.model_input, self.prefilter = build_model_input(self.raw)
        self.model_output = semantic_output(self.model_input)

    def test_injects_canonical_sources_from_raw_json(self):
        digest, audit = build_digest(self.raw, self.model_input, self.model_output)

        self.assertEqual(len(digest["top_items"]), 4)
        for item in digest["top_items"]:
            source_index = int(item["master_candidate_id"][1:]) - 1
            raw_article = self.raw["pages"][0]["articles"][source_index]
            self.assertEqual(
                item["sources"],
                [{"headline": raw_article["title"], "page": "001", "url": raw_article["url"]}],
            )
            self.assertEqual(item["summary"], f"{raw_article['title']}的事实摘要。")
        self.assertEqual(len(audit["articles"]), 4)
        self.assertTrue(all(item["selected"] for item in audit["articles"]))

    def test_splits_top_four_and_more_items_without_padding(self):
        raw = distinct_raw_issue(article_count=6)
        model_input, _ = build_model_input(raw)

        digest, _ = build_digest(raw, model_input, semantic_output(model_input))

        self.assertEqual([item["rank"] for item in digest["top_items"]], [1, 2, 3, 4])
        self.assertEqual([item["rank"] for item in digest["more_items"]], [5, 6])
        self.assertEqual(digest["selected_count"], 6)
        self.assertEqual(len(digest["categories"]["民生/办事"]), 6)

    def test_rejects_source_fields_from_model(self):
        self.model_output["items"][0]["url"] = "http://evil.test/fake"

        with self.assertRaisesRegex(ModelOutputError, "unknown fields.*url"):
            build_digest(self.raw, self.model_input, self.model_output)

    def test_rejects_unknown_category_score_range_and_model_decisions(self):
        mutations = [
            ("suggested_category", "随意分类"),
            ("hainan_relevance", 11),
            ("actionability", 1.5),
            ("selected", True),
            ("final_score", 99),
            ("rank", 1),
        ]
        for field, value in mutations:
            output = semantic_output(self.model_input)
            output["items"][0][field] = value
            with self.subTest(field=field):
                with self.assertRaises(ModelOutputError):
                    build_digest(self.raw, self.model_input, output)

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
            audit_path = Path(tmp) / "audit.json"
            output_path.write_text('{"existing": true}\n', encoding="utf-8")
            audit_path.write_text('{"existing_audit": true}\n', encoding="utf-8")
            self.model_output["items"][0]["sources"] = []

            with self.assertRaises(ModelOutputError):
                finalize_to_path(self.raw, self.model_input, self.model_output, output_path, audit_path)

            self.assertEqual(json.loads(output_path.read_text(encoding="utf-8")), {"existing": True})
            self.assertEqual(json.loads(audit_path.read_text(encoding="utf-8")), {"existing_audit": True})

    def test_cli_runs_as_a_direct_script(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(__file__).resolve().parents[1]
            directory = Path(tmp)
            raw_path = directory / "raw.json"
            input_path = directory / "input.json"
            model_path = directory / "model.json"
            output_path = directory / "digest.json"
            audit_path = directory / "audit.json"
            raw_path.write_text(json.dumps(self.raw, ensure_ascii=False), encoding="utf-8")
            input_path.write_text(json.dumps(self.model_input, ensure_ascii=False), encoding="utf-8")
            model_path.write_text(json.dumps(self.model_output, ensure_ascii=False), encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(root / "scripts" / "finalize_digest.py"),
                    str(raw_path),
                    str(input_path),
                    str(model_path),
                    str(output_path),
                    str(audit_path),
                ],
                cwd=root,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(output_path.is_file())
            self.assertTrue(audit_path.is_file())


if __name__ == "__main__":
    unittest.main()
