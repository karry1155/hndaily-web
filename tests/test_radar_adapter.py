import unittest

from scripts.radar_adapter import adapt_hndaily
from scripts.radar_contract import ContractError, validate_source_candidate
from tests.radar_fixtures import raw_issue


class RadarAdapterTests(unittest.TestCase):
    def test_adapts_trusted_fields_with_publication_layout(self):
        candidates, audit = adapt_hndaily(raw_issue())
        self.assertEqual(len(candidates), 4)
        self.assertEqual(len(audit), 4)
        self.assertEqual(candidates[0]["source"], "海南日报")
        self.assertEqual(candidates[0]["title"], "原始标题 1")
        self.assertEqual(candidates[0]["page_number"], "001")
        self.assertEqual(candidates[0]["page_name"], "头版")
        self.assertEqual(candidates[0]["page_sequence"], 1)
        self.assertEqual(candidates[0]["page_url"], "http://example.test/2026-07-08/page-1")
        self.assertEqual(candidates[0]["pdf_url"], "http://example.test/2026-07-08/page-1.pdf")

    def test_stable_id_uses_canonical_url_content_id(self):
        raw = raw_issue()
        raw["pages"][0]["articles"][0]["url"] = (
            "http://news.hndaily.cn/html/2026-07/08/content_58466_19684674.htm"
        )
        first, _ = adapt_hndaily(raw)
        second, _ = adapt_hndaily(raw)
        self.assertEqual(first[0]["item_id"], "hndaily-19684674")
        self.assertEqual(first[0]["item_id"], second[0]["item_id"])

    def test_rejects_non_http_source_url(self):
        candidate = {
            "candidate_id": "A001",
            "item_id": "hndaily-1",
            "source": "海南日报",
            "title": "标题",
            "content": "正文",
            "original_url": "javascript:alert(1)",
            "published_date": "2026-07-08",
            "collected_date": "2026-07-10",
            "page_number": "001",
            "page_name": "头版",
            "page_url": "https://example.test/page-001",
            "pdf_url": "https://example.test/page-001.pdf",
            "page_sequence": 1,
        }
        with self.assertRaisesRegex(ContractError, "original_url"):
            validate_source_candidate(candidate)


if __name__ == "__main__":
    unittest.main()
