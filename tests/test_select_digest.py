import unittest

from scripts.select_digest import select_events


def event(index, relevance=8, final_score=70, density=7, length=500, page="003", seq=None):
    candidate_id = f"A{index:03d}"
    return {
        "event_id": f"E{index:03d}",
        "master_candidate_id": candidate_id,
        "candidate_id": candidate_id,
        "semantic_scores": {
            "hainan_relevance": relevance,
            "information_density": density,
        },
        "final_score": final_score,
        "content_length": length,
        "page": page,
        "seq": index if seq is None else seq,
    }


class SelectDigestTests(unittest.TestCase):
    def test_applies_both_thresholds_without_filling(self):
        selected, decisions = select_events([
            event(1, relevance=5, final_score=99),
            event(2, relevance=6, final_score=64),
            event(3, relevance=6, final_score=65),
        ])

        self.assertEqual([item["event_id"] for item in selected], ["E003"])
        by_id = {item["event_id"]: item for item in decisions}
        self.assertEqual(by_id["E001"]["unselected_reason"], "below_hainan_relevance")
        self.assertEqual(by_id["E002"]["unselected_reason"], "below_final_score")
        self.assertEqual(by_id["E003"]["rank"], 1)

    def test_limits_to_eight_with_stable_tie_breaks(self):
        values = [event(index, final_score=80, density=7, length=500) for index in range(1, 11)]

        selected, decisions = select_events(list(reversed(values)))

        self.assertEqual([item["master_candidate_id"] for item in selected], [f"A{i:03d}" for i in range(1, 9)])
        self.assertEqual([item["unselected_reason"] for item in decisions if not item["selected"]], ["daily_limit", "daily_limit"])


if __name__ == "__main__":
    unittest.main()
