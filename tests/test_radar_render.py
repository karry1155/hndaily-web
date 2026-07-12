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

    def test_radar_css_uses_compact_sidebar_and_item_panels(self):
        css = (Path(__file__).resolve().parents[1] / "src/static/styles.css").read_text(encoding="utf-8")
        self.assertIn("--sidebar: 216px", css)
        self.assertIn("grid-template-columns: var(--sidebar) minmax(0, 1fr)", css)
        self.assertIn(".ai-summary, .recommendation-reason", css)

    def test_selected_home_has_one_authoritative_responsive_visual_system(self):
        css = (Path(__file__).resolve().parents[1] / "src/static/styles.css").read_text(encoding="utf-8")
        self.assertEqual(css.count("/* Selected homepage */"), 1)
        self.assertNotIn("/* HN·HOT final visual cascade. */", css)
        self.assertIn(".selected-header", css)
        self.assertIn(".search-submit", css)
        self.assertIn(".story-reason", css)
        self.assertIn(".theme-toggle-track", css)
        self.assertIn(".category-tabs a.active::after", css)
        mobile = css[css.index("@media (max-width: 760px)"):]
        self.assertIn(".selected-story .story-summary { display: none; }", mobile)

    def test_all_view_renders_focus_and_title_only_public_fields(self):
        item = stored_item(1, title="科技见习 <计划>", summary="摘要 <script>x</script>")
        summary = {
            "item_id": item["item_id"], "published_date": item["published_date"],
            "daily_rank": 1, "category": "机会",
            "title": item["block"]["title"], "ai_summary": item["block"]["ai_summary"],
            "recommendation_reason": item["block"]["recommendation_reason"],
            "detail_path": f"/items/{item['published_date']}/{item['item_id']}/",
        }
        manifest = {"dates": ["2026-07-10"], "feeds": ["/static/selected-feed/2026-07-10.json"]}
        rendered = render_index({"page": 1, "page_count": 1, "items": [summary]}, {"updated_through": "2026-07-10", "items": [{**summary, "focus_rank": 1}]}, "全部", manifest)
        self.assertIn("新闻精选", rendered)
        self.assertNotIn("当下重点", rendered)
        self.assertIn('<strong class="current-date">7月10日</strong>', rendered)
        self.assertIn('<span class="current-date-meta">星期五 · 1 条</span>', rendered)
        self.assertIn('class="search-submit"', rendered)
        self.assertIn('data-selected-feed-manifest', rendered)
        self.assertIn("科技见习 &lt;计划&gt;", rendered)
        self.assertNotIn("<script>", rendered)
        self.assertNotIn("最终分", rendered)
        self.assertIn('class="story-summary"', rendered)
        self.assertIn('class="story-reason"', rendered)
        self.assertIn("为什么值得读", rendered)
        self.assertIn('data-search-scope="selected"', rendered)
        self.assertIn("focus-rank-1", rendered)
        self.assertIn("data-star-id", rendered)
        self.assertNotIn("pagination", rendered)

    def test_mobile_home_uses_bottom_navigation_focus_first_and_hides_search(self):
        css = (Path(__file__).resolve().parents[1] / "src/static/styles.css").read_text(encoding="utf-8")
        mobile = css[css.index("@media (max-width: 760px)"):]
        self.assertIn("position: fixed", mobile)
        self.assertIn("inset: auto 0 0", mobile)
        self.assertIn(".selected-search { display: none; }", mobile)

    def test_mobile_density_refresh_is_open_compact_and_safe_area_aware(self):
        css = (Path(__file__).resolve().parents[1] / "src/static/styles.css").read_text(encoding="utf-8")
        mobile = css[css.index("@media (max-width: 760px)"):]
        self.assertIn("@media (max-width: 760px)", css)
        self.assertIn("position: fixed", mobile)
        self.assertIn("inset: auto 0 0", mobile)
        self.assertIn("z-index: 40", mobile)
        self.assertIn("padding-bottom: calc(66px + env(safe-area-inset-bottom))", mobile)
        self.assertIn("overflow-x: auto", css)
        self.assertIn("scrollbar-width: none", css)
        self.assertIn("-webkit-line-clamp: 2", mobile)
        self.assertIn("grid-template-columns: 28px minmax(0, 1fr) 40px", mobile)

    def test_formal_category_hides_focus(self):
        rendered = render_index({"page": 1, "page_count": 1, "items": []}, None, "民生", {"dates": [], "feeds": []})
        self.assertNotIn("当下重点", rendered)
        self.assertIn("今日暂无民生精选", rendered)

    def test_detail_has_two_source_links_and_escaped_body(self):
        item = stored_item(1, content="第一段\n\n第二段 <script>x</script>")
        rendered = render_item(item)
        self.assertEqual(rendered.count(item["block"]["original_url"]), 2)
        self.assertLess(rendered.index("AI 摘要"), rendered.index("第一段"))
        self.assertLess(rendered.index("推荐理由"), rendered.index("第一段"))
        self.assertIn("第二段 &lt;script&gt;x&lt;/script&gt;", rendered)

    def test_issue_page_links_page_pdf_and_local_articles(self):
        issue = {
            "schema_version": 4, "source": "海南日报",
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
