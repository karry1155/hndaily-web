import datetime as dt
import importlib.util
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
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
    def test_default_output_is_project_local_production_source(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            crawler = load_crawler()
        self.assertEqual(crawler.OUTPUT_DIR, ROOT / "data/production-json/source")

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

    def test_discovers_latest_issue_from_paperindex_redirect(self):
        crawler = load_crawler()
        paperindex = (
            '<meta http-equiv="refresh" '
            'content="0;URL=html/2026-07/18/node_1.htm">'
        )
        with mock.patch.object(crawler, "fetch", return_value=paperindex) as fetched:
            date, url = crawler.discover_current_issue()

        self.assertEqual(date, dt.date(2026, 7, 18))
        self.assertEqual(url, f"{crawler.BASE}/html/2026-07/18/node_1.htm")
        fetched.assert_called_once_with(f"{crawler.BASE}/paperindex.htm")

    def test_extracts_standalone_body_byline_and_removes_it_from_content(self):
        crawler = load_crawler()
        article = """
            <founder-title>生态修复，黑鳍鲨“如约而至”</founder-title>
            <founder-author></founder-author>
            <founder-content>
                <P>　　■&nbsp;海南日报全媒体记者&nbsp;李艳玫</P>
                <P>　　通讯员&nbsp;陈宏</P>
                <P>　　“快看！那边有鲨鱼！”近日，游客循声望去。</P>
            </founder-content>
        """

        self.assertEqual(
            crawler.parse_article(article),
            {
                "title": "生态修复，黑鳍鲨“如约而至”",
                "author": "海南日报全媒体记者 李艳玫 通讯员 陈宏",
                "content": "“快看！那边有鲨鱼！”近日，游客循声望去。",
            },
        )

    def test_extracts_parenthesized_byline_after_dateline_without_rewriting_content(self):
        crawler = load_crawler()
        article = """
            <founder-title>测试消息稿</founder-title>
            <founder-author><!--<npm:article-author>--><!--</npm:article-author>--></founder-author>
            <founder-content>
                <P>本报讯 （海南日报全媒体记者张琬茜 通讯员林妙莹）近日，双方签署合作协议。</P>
                <P>第二段事实。</P>
            </founder-content>
        """

        self.assertEqual(
            crawler.parse_article(article),
            {
                "title": "测试消息稿",
                "author": "海南日报全媒体记者张琬茜 通讯员林妙莹",
                "content": (
                    "本报讯 （海南日报全媒体记者张琬茜 通讯员林妙莹）"
                    "近日，双方签署合作协议。\n\n第二段事实。"
                ),
            },
        )

    def test_keeps_explicit_author_in_preference_to_body_fallback(self):
        crawler = load_crawler()
        article = """
            <founder-title>旧模板稿件</founder-title>
            <founder-author>记者 测试</founder-author>
            <founder-content><P>■ 正文中的方块行</P><P>事实。</P></founder-content>
        """

        parsed = crawler.parse_article(article)

        self.assertEqual(parsed["author"], "记者 测试")
        self.assertEqual(parsed["content"], "■ 正文中的方块行\n\n事实。")

    def test_main_reuses_fresh_cached_issue_without_fetching(self):
        crawler = load_crawler()
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "2026-07-18.json"
            target.write_text('{"existing": true}\n', encoding="utf-8")
            stdout = io.StringIO()
            with mock.patch.object(crawler, "OUTPUT_DIR", Path(tmp)), mock.patch.object(
                crawler, "fetch"
            ) as fetched, mock.patch.object(crawler, "crawl") as crawled, redirect_stdout(
                stdout
            ), redirect_stderr(io.StringIO()):
                result = crawler.main(["crawler.py", "2026-07-18"])

            self.assertEqual(result, 0)
            self.assertEqual(stdout.getvalue().strip(), str(target))
            fetched.assert_not_called()
            crawled.assert_not_called()

    def test_force_bypasses_fresh_cache_and_rewrites_valid_issue(self):
        crawler = load_crawler()
        payload = {
            "source": "海南日报",
            "date": "2026-07-18",
            "page_count": 1,
            "article_count": 0,
            "pages": [],
        }
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "2026-07-18.json"
            target.write_text('{"existing": true}\n', encoding="utf-8")
            with mock.patch.object(crawler, "OUTPUT_DIR", Path(tmp)), mock.patch.object(
                crawler, "fetch", return_value="front"
            ) as fetched, mock.patch.object(
                crawler, "crawl", return_value=payload
            ) as crawled, redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                result = crawler.main(["crawler.py", "2026-07-18", "--force"])

            self.assertEqual(result, 0)
            self.assertEqual(json.loads(target.read_text(encoding="utf-8")), payload)
            fetched.assert_called_once_with(crawler.front_page_url(dt.date(2026, 7, 18)))
            crawled.assert_called_once_with(dt.date(2026, 7, 18), "front")

    def test_crawl_records_page_and_article_fetch_failures(self):
        crawler = load_crawler()
        front = (FIXTURES / "front-page.html").read_text(encoding="utf-8")
        with mock.patch.object(
            crawler, "fetch_safe", return_value=RuntimeError("offline")
        ):
            payload = crawler.crawl(dt.date(2026, 7, 18), front)

        self.assertEqual(payload["pages"][0]["articles"][0]["error"], "fetch failed: offline")
        self.assertEqual(payload["pages"][1]["error"], "page fetch failed: offline")

    def test_invalid_date_exits_before_fetching(self):
        crawler = load_crawler()
        stderr = io.StringIO()
        with mock.patch.object(crawler, "fetch") as fetched, redirect_stderr(stderr):
            result = crawler.main(["crawler.py", "2026-02-30"])

        self.assertEqual(result, 1)
        self.assertIn("invalid date '2026-02-30'", stderr.getvalue())
        fetched.assert_not_called()

    def test_main_writes_atomic_dated_json_and_prints_absolute_path(self):
        crawler = load_crawler()
        payload = {
            "source": "海南日报",
            "date": "2026-07-18",
            "page_count": 1,
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

    def test_no_pages_exits_nonzero_without_overwriting_existing_issue(self):
        crawler = load_crawler()
        payload = {
            "source": "海南日报",
            "date": "2026-07-18",
            "page_count": 0,
            "article_count": 0,
            "pages": [],
        }
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "2026-07-18.json"
            original = '{"date": "2026-07-18", "page_count": 2}\n'
            target.write_text(original, encoding="utf-8")
            stdout = io.StringIO()
            stderr = io.StringIO()
            with mock.patch.object(crawler, "OUTPUT_DIR", Path(tmp)), mock.patch.object(
                crawler, "fetch", return_value="front"
            ), mock.patch.object(
                crawler, "crawl", return_value=payload
            ), redirect_stdout(stdout), redirect_stderr(stderr):
                result = crawler.main(["crawler.py", "2026-07-18", "--force"])

            self.assertNotEqual(result, 0)
            self.assertEqual(stdout.getvalue(), "")
            self.assertIn("NO_ISSUE", stderr.getvalue())
            self.assertEqual(target.read_text(encoding="utf-8"), original)
            self.assertFalse((Path(tmp) / ".2026-07-18.json.tmp").exists())


if __name__ == "__main__":
    unittest.main()
