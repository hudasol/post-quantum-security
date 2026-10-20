import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import summarize_verification5 as sv  # noqa: E402


class TestVerification5(unittest.TestCase):
    def test_numbers_with_separators_and_rounding(self):
        self.assertTrue(sv.same("cycles", "1,234,567", "1234567"))
        self.assertTrue(sv.same("cycles", "3550000", "3.55e6"))
        self.assertFalse(sv.same("cycles", "3550000", "3650000"))

    def test_text_case_and_containment(self):
        self.assertTrue(sv.same("core", "Cortex-M4F", "cortex-m4f"))
        self.assertFalse(sv.same("operation", "sign", "verify"))

    def test_wilson_interval(self):
        lo, hi = sv.wilson(0, 100)
        self.assertEqual(lo, 0.0)
        self.assertAlmostEqual(hi, 0.037, places=3)

    def test_compare_marks_missing_sheet(self):
        res = sv.compare({"A": {"cycles": "10"}}, {}, {"A": {"cycles": "10"}}, ["cycles"])
        self.assertIn(("A", "cycles", "reader1", "10", None, "missing_sheet"), res)
        self.assertIn(("A", "cycles", "reader2", "10", "10", "agree"), res)


if __name__ == "__main__":
    unittest.main()
