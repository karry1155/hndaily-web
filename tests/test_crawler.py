import datetime as dt
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/crawler"


def load_crawler():
    spec = importlib.util.spec_from_file_location(
        "hnhot_crawler", ROOT / "scripts/crawler.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class CrawlerTests(unittest.TestCase):
    def test_default_output_is_project_local_json_raw(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            crawler = load_crawler()
        self.assertEqual(crawler.OUTPUT_DIR, ROOT / "data/json/raw")

    def test_parses_pages_links_and_article_body(self):
        crawler = load_crawler()
        front = (FIXTURES / "front-page.html").read_text(encoding="utf-8")
        article = (FIXTURES / "article.html").read_text(encoding="utf-8")
        self.assertEqual(
            crawler.parse_page_list(front),
            [("001", "头版", "node_1.htm"), ("002", "本省新闻", "node_2.htm")],
        )
        self.assertEqual(
            crawler.parse_article_links(front),
            [("content_1_1001.htm", "头版测试报道")],
        )
        self.assertEqual(
            crawler.parse_article(article),
            {
                "title": "头版测试报道",
                "author": "记者 测试",
                "content": "第一段事实。\n\n第二段事实。",
            },
        )

    def test_main_writes_atomic_dated_json_and_prints_absolute_path(self):
        crawler = load_crawler()
        payload = {
            "source": "海南日报",
            "date": "2026-07-18",
            "page_count": 0,
            "article_count": 0,
            "pages": [],
        }
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            crawler, "OUTPUT_DIR", Path(tmp)
        ), mock.patch.object(
            crawler, "fetch", return_value="front"
        ), mock.patch.object(
            crawler, "crawl", return_value=payload
        ), mock.patch("builtins.print") as printed:
            self.assertEqual(crawler.main(["crawler.py", "2026-07-18"]), 0)
            target = Path(tmp) / "2026-07-18.json"
            self.assertTrue(target.is_file())
            self.assertEqual(printed.call_args_list[0].args, (str(target.resolve()),))
            self.assertFalse((Path(tmp) / ".2026-07-18.json.tmp").exists())


if __name__ == "__main__":
    unittest.main()
