import unittest
from pathlib import Path

from scripts.radar_render import render_primary_nav

ROOT = Path(__file__).resolve().parents[1]


@unittest.skip("retired progressive selected-feed interface")
class SelectedHomeJavaScriptTests(unittest.TestCase):
    def test_progressive_feed_search_and_fallback_contracts_exist(self):
        js = (ROOT / "src/static/app.js").read_text(encoding="utf-8")
        self.assertIn("IntersectionObserver", js)
        self.assertIn("data-selected-feed-manifest", js)
        self.assertIn("loadSelectedDate", js)
        self.assertIn("renderSelectedDate", js)
        self.assertIn("data-load-more", js)
        self.assertIn("加载失败，重试", js)
        self.assertIn("recommendation_reason", js)
        self.assertIn("searching: false", js)
        self.assertIn("selectedFeedState.searching", js)
        self.assertIn('choice === "system"', js)
        self.assertIn("final_score", js)
        self.assertIn("推荐理由：", js)

    def test_theme_control_has_three_explicit_modes(self):
        rendered = render_primary_nav("精选")
        self.assertIn('role="group"', rendered)
        self.assertIn("data-theme-toggle", rendered)
        self.assertIn('data-theme-choice="dark"', rendered)
        self.assertIn('data-theme-choice="system"', rendered)
        self.assertIn('data-theme-choice="light"', rendered)
