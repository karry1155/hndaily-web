import unittest

from scripts.event_clustering import cluster_candidates


def scored(candidate_id, title, content, *, density=7, final_score=70, page="001", seq=1):
    return {
        "candidate_id": candidate_id,
        "original_title": title,
        "content": content,
        "content_length": len(content),
        "page": page,
        "page_name": "头版" if page == "001" else "本省新闻",
        "seq": seq,
        "url": f"http://example.test/{candidate_id}",
        "semantic_scores": {"hainan_relevance": 8, "information_density": density},
        "final_score": final_score,
        "title": f"提炼 {title}",
        "summary": "摘要",
        "why_it_matters": "理由",
        "key_facts": ["事实"],
        "category": "民生/办事",
        "confidence": "full_text",
    }


class EventClusteringTests(unittest.TestCase):
    def test_merges_identical_normalized_titles_and_preserves_sources(self):
        events = cluster_candidates([
            scored("A001", "海南：公积金新政！", "短讯", density=6, page="001"),
            scored("A009", "海南公积金新政", "完整正文" * 100, density=9, page="003"),
        ])

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_id"], "E001")
        self.assertEqual(events[0]["master_candidate_id"], "A009")
        self.assertEqual(events[0]["member_candidate_ids"], ["A001", "A009"])
        self.assertEqual(len(events[0]["sources"]), 2)

    def test_merges_highly_similar_leads_but_keeps_different_events_separate(self):
        shared = "海南启动住房公积金支付物业费新政策符合条件的缴存人可以办理"
        events = cluster_candidates([
            scored("A001", "头版短讯", shared + "甲" * 40),
            scored("A002", "内页详稿", shared + "乙" * 40, page="003"),
            scored("A003", "海南启动大学生科技见习计划", "面向大学生征集科技见习岗位" * 20, page="003"),
        ])

        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["member_candidate_ids"], ["A001", "A002"])
        self.assertEqual(events[1]["member_candidate_ids"], ["A003"])


if __name__ == "__main__":
    unittest.main()
