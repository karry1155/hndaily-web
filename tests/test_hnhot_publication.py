import json
import tempfile
import unittest
from pathlib import Path

from scripts.finalize_radar import FinalizeError, build_generation, finalize_to_store
from scripts.radar_adapter import adapt_hndaily
from scripts.radar_model import ModelOutputError, build_model_input, validate_model_output
from scripts.radar_render import (
    build_site,
    render_front_page,
    render_item,
    render_primary_nav,
    validate_internal_links,
)
from tests.radar_fixtures import raw_issue


def hnhot_output(model_input, candidates):
    return {
        "schema_version": model_input["schema_version"],
        "prompt_version": model_input["prompt_version"],
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
                "events": [],
                "plans": [],
            }
            for candidate in candidates
        ],
    }


class HnhotPublicationTests(unittest.TestCase):
    def test_schema_v8_input_and_output_are_exact_and_grounded(self):
        raw = raw_issue(article_count=2)
        candidates = adapt_hndaily(raw)[0]
        model_input = build_model_input(candidates)
        self.assertEqual(model_input["schema_version"], 8)
        self.assertEqual(model_input["prompt_version"], "hnhot-v2.1")
        self.assertEqual(
            set(model_input["items"][0]),
            {"candidate_id", "title", "content", "location_candidates", "topic_candidates"},
        )
        output = hnhot_output(model_input, candidates)
        self.assertEqual(validate_model_output(model_input, output, candidates), output["items"])
        output["items"][0]["scope"] = "foreign"
        self.assertEqual(validate_model_output(model_input, output, candidates), output["items"])
        output["items"][0]["score"] = 10
        with self.assertRaises(ModelOutputError):
            validate_model_output(model_input, output, candidates)

    def test_v2_events_and_plans_are_grounded_and_published(self):
        raw = raw_issue(article_count=1)
        raw["pages"][0]["articles"][0]["title"] = "海南部署旅游公路建设"
        raw["pages"][0]["articles"][0]["content"] = (
            "海南印发《海南省旅游公路发展规划》，并召开旅游公路建设推进会。"
        )
        candidates = adapt_hndaily(raw)[0]
        model_input = build_model_input(candidates)
        output = hnhot_output(model_input, candidates)
        output["items"][0]["events"] = [{
            "name": "海南旅游公路建设推进会",
            "evidence": "召开旅游公路建设推进会",
        }]
        output["items"][0]["plans"] = [{
            "name": "《海南省旅游公路发展规划》",
            "evidence": "海南印发《海南省旅游公路发展规划》",
        }]
        articles, _, _ = build_generation(raw, model_input, output)
        self.assertEqual(articles[0]["events"], output["items"][0]["events"])
        self.assertEqual(articles[0]["plans"], output["items"][0]["plans"])
        self.assertNotIn("event_relation", articles[0])

        output["items"][0]["plans"][0]["name"] = "海南省旅游公路发展规划"
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
                root, root / "audit.json",
            )
            issue = json.loads((root / "issues" / f'{raw["date"]}.json').read_text(encoding="utf-8"))
            self.assertEqual(issue["schema_version"], 8)
            self.assertEqual(issue["sections"][0]["name"], "头版")
            self.assertTrue((root / "indexes/hnhot.json").is_file())
            self.assertTrue((root / f'indexes/front-page/{raw["date"]}.json').is_file())

    def test_finalize_rejects_same_canonical_url_under_different_ids(self):
        first_raw = raw_issue(article_count=1, date="2026-07-11")
        second_raw = raw_issue(article_count=1, date="2026-07-12")
        second_raw["pages"][0]["articles"][0]["url"] = (
            first_raw["pages"][0]["articles"][0]["url"]
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for raw in (first_raw,):
                candidates = adapt_hndaily(raw)[0]
                model_input = build_model_input(candidates)
                finalize_to_store(
                    raw,
                    model_input,
                    hnhot_output(model_input, candidates),
                    root,
                    root / "audit.json",
                )
            candidates = adapt_hndaily(second_raw)[0]
            model_input = build_model_input(candidates)
            with self.assertRaisesRegex(FinalizeError, "canonical URL collision"):
                finalize_to_store(
                    second_raw,
                    model_input,
                    hnhot_output(model_input, candidates),
                    root,
                    root / "audit.json",
                )

    def test_bundled_content_builds_four_route_site_without_broken_links(self):
        project = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp) / "site"
            build_site(project / "content", site)
            for route in ("index.html", "all/index.html", "daily/index.html", "more/index.html"):
                self.assertTrue((site / route).is_file(), route)
            home = (site / "index.html").read_text(encoding="utf-8")
            national_page = (site / "front-page/national/index.html").read_text(encoding="utf-8")
            hainan_page = (site / "front-page/hainan/index.html").read_text(encoding="utf-8")
            domestic_page = (site / "front-page/domestic/index.html").read_text(encoding="utf-8")
            mixed_page = (site / "front-page/mixed/index.html").read_text(encoding="utf-8")
            global_page = (site / "front-page/global/index.html").read_text(encoding="utf-8")
            foreign_detail = (
                site / "items/2026-07-20/hndaily-20260720-58469-19717554/index.html"
            ).read_text(encoding="utf-8")
            domestic_detail = (
                site / "items/2026-07-20/hndaily-20260720-58464-19717496/index.html"
            ).read_text(encoding="utf-8")
            all_page = (site / "all/index.html").read_text(encoding="utf-8")
            more_page = (site / "more/index.html").read_text(encoding="utf-8")
            about_page = (site / "about/index.html").read_text(encoding="utf-8")
            daily_page = (site / "daily/index.html").read_text(encoding="utf-8")
            dated_page = (site / "all/2026-07-20/index.html").read_text(encoding="utf-8")
            front_page_archive = (
                site / "all/sections/front-page/index.html"
            ).read_text(encoding="utf-8")
            self.assertNotIn("今日编辑判断", home)
            self.assertNotIn("按头版次序", home)
            self.assertNotIn("<h1>头版</h1><p>", home)
            self.assertIn("H · 海南本地", home)
            self.assertIn("D · 国内关联", home)
            self.assertIn("M · 海南开放", home)
            self.assertIn("N · 全国", home)
            self.assertIn("F · 全球", home)
            self.assertIn("海南日报 · 要闻", home)
            self.assertNotIn("Hainan Daily · Headlines", home)
            self.assertLess(home.index(">H · 海南本地</a>"), home.index(">D · 国内关联</a>"))
            self.assertLess(home.index(">D · 国内关联</a>"), home.index(">M · 海南开放</a>"))
            self.assertLess(home.index(">M · 海南开放</a>"), home.index(">N · 全国</a>"))
            self.assertLess(home.index(">N · 全国</a>"), home.index(">F · 全球</a>"))
            self.assertIn("<h2>全国要闻</h2>", home)
            self.assertIn("强化风险意识 确保安全可控", home)
            self.assertIn("<h2>全球要闻</h2>", home)
            self.assertIn("美沙核协议草案浮出水面", global_page)
            self.assertNotIn("千亿投资推进", global_page)
            self.assertIn("从陵水黎安起步", domestic_page)
            self.assertNotIn("海南竞技体育再", domestic_page)
            for filtered_page in (national_page, hainan_page, domestic_page, mixed_page, global_page):
                self.assertNotIn('class="ranking-dashboard"', filtered_page)
            self.assertIn('scope-domestic" title="D · 国内关联" aria-label="D · 国内关联">D</span>', domestic_detail)
            self.assertIn('scope-foreign" title="F · 全球" aria-label="F · 全球">F</span>', foreign_detail)
            self.assertIn('id="scope-guide-title"', more_page)
            self.assertIn("产品方法与数据边界", more_page)
            self.assertNotIn('id="scope-guide-title"', about_page)
            for label in ("海南本地", "国内关联", "海南开放", "全国", "全球"):
                self.assertIn(label, more_page)
            self.assertIn("海南涉外、跨境与开放信息", more_page)
            self.assertIn("海南日报 · 沉淀", daily_page)
            self.assertNotIn("每日沉淀", daily_page)
            for label in ("日报", "周报", "月报", "今天", "7月19日", "更多"):
                self.assertIn(label, daily_page)
            self.assertIn('data-report-value="7月20日">今天</button>', daily_page)
            self.assertIn('data-report-value="7月19日">7月19日</button>', daily_page)
            self.assertIn("data-report-date-tabs", daily_page)
            self.assertIn("当前先开放周期与日期浏览结构", daily_page)
            self.assertIn('<span class="eyebrow">海南日报</span><h1>报库</h1>', all_page)
            self.assertIn("2 期 · 70 条已入库", all_page)
            self.assertIn("搜索标题、摘要或已提取的人物、地点、主题", all_page)
            self.assertIn('data-search-source="/static/data/search-articles.json"', all_page)
            self.assertNotIn("当心这种极易漏诊的罕见病", all_page)
            self.assertIn("按版面查看", all_page)
            self.assertIn("由报纸编辑维护", all_page)
            self.assertIn("/all/sections/front-page/", all_page)
            self.assertIn("/all/sections/hainan-news/", all_page)
            self.assertNotIn("<h1>全部</h1><p>2026", all_page)
            self.assertNotIn("完整报纸 · 逻辑版面", dated_page)
            self.assertIn("海南日报 · 本期内容", dated_page)
            self.assertIn("<h1>2026年7月20日</h1>", dated_page)
            self.assertIn("<p>星期一 · 49 篇</p>", dated_page)
            self.assertNotIn("<h1>全部</h1>", dated_page)
            self.assertNotIn("搜索全部报道", dated_page)
            self.assertNotIn("搜索本期标题", dated_page)
            self.assertIn('aria-label="本期版面"', dated_page)
            self.assertIn('href="#section-front-page">头版<span>7</span></a>', dated_page)
            self.assertNotIn("合并 1 个原版面", dated_page)
            self.assertNotIn("合并 2 个原版面", dated_page)
            self.assertNotIn("查看原版", dated_page)
            self.assertNotIn("第001版 PDF", dated_page)
            self.assertNotIn("第002版 PDF", dated_page)
            self.assertNotIn("第003版 PDF", dated_page)
            self.assertIn('data-back-to-top href="#issue-start"', dated_page)
            self.assertIn("千亿投资推进“人享其行、物畅其流”", dated_page)
            self.assertIn("头版 · 14 条", front_page_archive)
            self.assertIn("2026年7月20日", front_page_archive)
            self.assertIn("2026年7月19日", front_page_archive)
            self.assertNotIn("2026年7月18日", front_page_archive)
            self.assertIn("本省新闻", all_page)
            self.assertNotIn("第002版", all_page)
            self.assertEqual(validate_internal_links(site), [])

    def test_front_page_uses_reader_facing_ranking_labels(self):
        item = {
            "item_id": "hndaily-20260713-58468-19696050",
            "title": "测试全国要闻",
            "ai_summary": "测试摘要。",
            "scope": "national",
            "detail_path": "/items/2026-07-13/hndaily-20260713-58468-19696050/",
            "rank": 1,
        }
        world_item = {
            **item,
            "item_id": "hndaily-20260713-58469-19696051",
            "title": "测试全球要闻",
            "scope": "foreign",
            "detail_path": "/items/2026-07-13/hndaily-20260713-58469-19696051/",
        }
        rendered = render_front_page([{
            "date": "2026-07-13",
            "national_ranking": [item],
            "world_ranking": [world_item],
            "items": [item, world_item],
        }])
        self.assertIn("国内头版", rendered)
        self.assertIn("世界新闻", rendered)
        self.assertIn("<h2>全国要闻</h2>", rendered)
        self.assertIn("<h2>全球要闻</h2>", rendered)
        self.assertEqual(rendered.count("<span>TOP 1</span>"), 2)
        self.assertNotIn("全国要闻 TOP", rendered)
        self.assertNotIn("今日编辑判断", rendered)
        self.assertNotIn("按头版次序", rendered)
        self.assertNotIn("<h1>头版</h1><p>", rendered)

    def test_front_page_rankings_keep_compact_empty_states(self):
        domestic = {
            "item_id": "hndaily-20260712-58464-19696008",
            "title": "测试国内头版要闻",
            "ai_summary": "测试摘要。",
            "scope": "national",
            "detail_path": "/items/2026-07-12/hndaily-20260712-58464-19696008/",
            "rank": 1,
        }
        domestic_only = render_front_page([{
            "date": "2026-07-12",
            "national_ranking": [domestic],
            "world_ranking": [],
            "items": [domestic],
        }])
        self.assertIn("今日暂无世界新闻", domestic_only)
        self.assertIn("ranking-world is-empty", domestic_only)

        no_news = render_front_page([])
        self.assertEqual(no_news.count("is-empty"), 2)
        self.assertIn("今日暂无国内头版要闻", no_news)
        self.assertIn("今日暂无世界新闻", no_news)

    def test_mobile_navigation_uses_final_four_labels(self):
        rendered = render_primary_nav("头版")
        for label in ("头版", "全部", "日报", "更多"):
            self.assertIn(f"<span>{label}</span>", rendered)
        for retired in ("精选", "全部信息", "AI 日报"):
            self.assertNotIn(retired, rendered)

    def test_mobile_item_page_hides_bottom_navigation(self):
        project = Path(__file__).resolve().parents[1]
        item_path = next((project / "content/issue-items").glob("*/*.json"))
        item = json.loads(item_path.read_text(encoding="utf-8"))
        rendered = render_item(item)
        css = (project / "src/static/styles.css").read_text(encoding="utf-8")
        base = (project / "src/templates/base.html").read_text(encoding="utf-8")
        mobile = css[css.index("@media (max-width: 760px)"):]

        self.assertIn('class="app-shell radar-shell item-shell"', rendered)
        self.assertIn(".item-shell .primary-nav nav { display: none; }", mobile)
        self.assertIn(
            ".radar-shell:not(.item-shell) { padding-bottom: calc(68px + env(safe-area-inset-bottom)); }",
            mobile,
        )
        self.assertIn("styles.css?v=20260720-context-2", base)
        self.assertIn("app.js?v=20260719-global-1", base)

    def test_item_page_groups_structured_extraction_instead_of_flat_tags(self):
        project = Path(__file__).resolve().parents[1]
        item = json.loads((
            project
            / "content/issue-items/2026-07-19/hndaily-20260719-58464-19716156.json"
        ).read_text(encoding="utf-8"))
        rendered = render_item(item)

        self.assertIn("报道标记", rendered)
        self.assertIn("原文结构化提取", rendered)
        self.assertIn('<details class="article-context">', rendered)
        self.assertIn('<summary class="article-context-summary">', rendered)
        self.assertNotIn('<details class="article-context" open>', rendered)
        for label in ("主体", "事件", "规划文件", "地点", "主题"):
            self.assertIn(f">{label} <span>", rendered)
        self.assertIn("政府机构 · 沉香产业“两免两保”政策推出方", rendered)
        self.assertIn("《海南省沉香全产业链创新发展规划（2023—2030年）》", rendered)
        self.assertNotIn("entity-tags", rendered)

    def test_item_page_orders_province_before_city_or_county(self):
        project = Path(__file__).resolve().parents[1]
        item = json.loads((
            project
            / "content/issue-items/2026-07-20/hndaily-20260720-58464-19717494.json"
        ).read_text(encoding="utf-8"))
        rendered = render_item(item)

        self.assertLess(rendered.index("<li>海南省</li>"), rendered.index("<li>琼海市</li>"))


if __name__ == "__main__":
    unittest.main()
