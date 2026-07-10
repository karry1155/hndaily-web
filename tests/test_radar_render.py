import unittest

from scripts.radar_render import render_index, render_item
from tests.radar_fixtures import stored_item


class RadarRenderTests(unittest.TestCase):
    def test_all_view_renders_focus_and_card_only_public_fields(self):
        item = stored_item(1, title="科技见习 <计划>", summary="摘要 <script>x</script>")
        summary = {
            "item_id": item["item_id"], "published_date": item["published_date"],
            "daily_rank": 1, "category": "机会", "source": "海南日报",
            "title": item["block"]["title"], "ai_summary": item["block"]["ai_summary"],
            "detail_path": f"/items/{item['published_date']}/{item['item_id']}/",
        }
        rendered = render_index({"page": 1, "page_count": 1, "items": [summary]}, {"updated_through": "2026-07-10", "items": [{**summary, "focus_rank": 1}]}, "全部")
        self.assertIn("当下重点", rendered)
        self.assertIn("海南日报", rendered)
        self.assertIn("科技见习 &lt;计划&gt;", rendered)
        self.assertNotIn("<script>", rendered)
        self.assertNotIn("最终分", rendered)
        self.assertNotIn("第003版", rendered)
        self.assertNotIn("查看原文", rendered)

    def test_formal_category_hides_focus(self):
        rendered = render_index({"page": 1, "page_count": 1, "items": []}, None, "民生")
        self.assertNotIn("当下重点", rendered)
        self.assertIn("今日暂无民生精选", rendered)

    def test_detail_has_two_source_links_and_escaped_body(self):
        item = stored_item(1, content="第一段\n\n第二段 <script>x</script>")
        rendered = render_item(item)
        self.assertEqual(rendered.count(item["block"]["original_url"]), 2)
        self.assertLess(rendered.index("AI 摘要"), rendered.index("第一段"))
        self.assertIn("第二段 &lt;script&gt;x&lt;/script&gt;", rendered)
