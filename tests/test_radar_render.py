import unittest
from pathlib import Path

from scripts.radar_render import render_index, render_issue, render_item
from tests.radar_fixtures import stored_item


class RadarRenderTests(unittest.TestCase):
    def test_theme_search_and_mobile_contracts_exist(self):
        root = Path(__file__).resolve().parents[1]
        js = (root / "src/static/app.js").read_text(encoding="utf-8")
        css = (root / "src/static/styles.css").read_text(encoding="utf-8")
        base = (root / "src/templates/base.html").read_text(encoding="utf-8")
        self.assertIn("hn-hot-theme", js)
        self.assertIn("matchMedia", js)
        self.assertIn("data-search-input", js)
        self.assertIn('html[data-theme="light"]', css)
        self.assertIn("prefers-color-scheme", base)
        self.assertIn("@media (max-width: 760px)", css)
        self.assertIn("hn-hot-starred", js)
        self.assertIn("backdrop-filter", css)

    def test_radar_css_overrides_legacy_three_column_shell(self):
        css = (Path(__file__).resolve().parents[1] / "src/static/styles.css").read_text(encoding="utf-8")
        self.assertIn(".radar-shell { grid-template-columns: 216px minmax(0, 1fr); }", css)
        self.assertIn(".ai-summary { margin: 28px 0; padding: 20px; background: var(--panel); }", css)

    def test_all_view_renders_focus_and_title_only_public_fields(self):
        item = stored_item(1, title="科技见习 <计划>", summary="摘要 <script>x</script>")
        summary = {
            "item_id": item["item_id"], "published_date": item["published_date"],
            "daily_rank": 1, "category": "机会",
            "title": item["block"]["title"], "ai_summary": item["block"]["ai_summary"],
            "detail_path": f"/items/{item['published_date']}/{item['item_id']}/",
        }
        rendered = render_index({"page": 1, "page_count": 1, "items": [summary]}, {"updated_through": "2026-07-10", "items": [{**summary, "focus_rank": 1}]}, "全部")
        self.assertIn("当下重点", rendered)
        self.assertIn("科技见习 &lt;计划&gt;", rendered)
        self.assertNotIn("<script>", rendered)
        self.assertNotIn("最终分", rendered)
        self.assertEqual(rendered.count("<p>摘要 &lt;script&gt;x&lt;/script&gt;</p>"), 1)
        self.assertIn('data-search-scope="selected"', rendered)
        self.assertIn("focus-rank-1", rendered)
        self.assertIn("data-star-id", rendered)

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

    def test_issue_page_links_page_pdf_and_local_articles(self):
        issue = {
            "schema_version": 3, "source": "海南日报",
            "date": "2026-07-08", "page_count": 2, "scored_article_count": 1,
            "pages": [
                {"page_number": "001", "page_name": "头版", "page_url": "https://example.test/page-001", "pdf_url": "https://example.test/page-001.pdf", "articles": [{"item_id": "hndaily-1", "title": "头版文章", "page_sequence": 1, "detail_path": "/items/2026-07-08/hndaily-1/"}]},
                {"page_number": "008", "page_name": "公益广告", "page_url": "https://example.test/page-008", "pdf_url": "https://example.test/page-008.pdf", "articles": []},
            ],
        }
        rendered = render_issue(issue)
        self.assertIn("第001版：头版", rendered)
        self.assertIn("下载 PDF", rendered)
        self.assertIn("/items/2026-07-08/hndaily-1/", rendered)
        self.assertIn("第008版：公益广告", rendered)
