import copy
import json
import unittest
from pathlib import Path

from scripts.render_site import render_daily
from scripts.validate_digest import validate_daily


FIXTURE = Path(__file__).resolve().parents[1] / "scripts" / "fixtures" / "daily-valid.json"


class DigestContractTests(unittest.TestCase):
    def setUp(self):
        self.digest = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.digest["top_items"][0]["summary"] = "政策允许符合条件的账户支付物业费。"

    def test_daily_top_item_requires_summary(self):
        invalid = copy.deepcopy(self.digest)
        invalid["top_items"][0].pop("summary")

        self.assertIn("top_items[0].summary is required", validate_daily(invalid))

    def test_daily_renderer_displays_escaped_summary_before_reason(self):
        self.digest["top_items"][0]["summary"] = "具体内容 <script>alert(1)</script>"

        rendered = render_daily(self.digest, [self.digest])

        summary = '<p class="summary">具体内容 &lt;script&gt;alert(1)&lt;/script&gt;</p>'
        self.assertIn(summary, rendered)
        self.assertLess(rendered.index(summary), rendered.index('<p class="why">'))

    def test_daily_contract_allows_four_top_and_four_more_with_continuous_ranks(self):
        item = self.digest["top_items"][0]
        self.digest["top_items"] = [dict(item, rank=index) for index in range(1, 5)]
        self.digest["more_items"] = [dict(item, rank=index) for index in range(5, 9)]
        self.digest["selected_count"] = 8

        self.assertEqual(validate_daily(self.digest), [])

    def test_daily_contract_rejects_more_than_eight_or_discontinuous_ranks(self):
        item = self.digest["top_items"][0]
        self.digest["more_items"] = [dict(item, rank=7)]
        self.digest["selected_count"] = 2

        errors = validate_daily(self.digest)

        self.assertTrue(any("rank" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
