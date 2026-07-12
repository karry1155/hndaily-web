import unittest
from pathlib import Path

from scripts.build_scoring_audit import build_scoring_audit


class ScoringAuditTests(unittest.TestCase):
    def test_report_explains_current_formula_and_real_score_concentration(self):
        root = Path(__file__).resolve().parents[1]
        rendered = build_scoring_audit(root / "content")
        for value in ("海南相关性 30%", "可行动性 25%", "影响范围 20%", "时效性 15%", "信息密度 10%"):
            self.assertIn(value, rendered)
        self.assertIn("80 分：44 条", rendered)
        self.assertIn("78.5 分：37 条", rendered)
        self.assertIn("54.3%", rendered)
        self.assertIn("模型判断", rendered)
        self.assertIn("脚本计算", rendered)
        self.assertIn("radar_scoring.py", rendered)
        self.assertIn("本报告未修改评分机制", rendered)


if __name__ == "__main__":
    unittest.main()
