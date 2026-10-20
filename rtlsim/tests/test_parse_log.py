"""Unit tests for rtlsim/parse_log.py and the pure helpers in rtlsim/report.py. Author: Huda Mueen."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import parse_log  # noqa: E402
import report  # noqa: E402

SAMPLE = """CFG,seed,20261020
CFG,runs,3
CFG,timer_overhead_cycles,4
RES,ML-DSA-44,keygen,0,100,ok
RES,ML-DSA-44,sign,0,300,ok
RES,ML-DSA-44,verify,0,50,ok
RES,ML-DSA-44,verify_rejects_modified,0,0,ok
RES,ML-DSA-44,sign,1,900,ok
RES,ML-DSA-44,verify,1,51,ok
RES,ML-DSA-44,verify_rejects_modified,1,0,ok
RES,ML-DSA-44,sign,2,500,fail
RES,ML-DSA-44,verify,2,52,ok
RES,ML-DSA-44,verify_rejects_modified,2,0,fail
some unrelated line
DONE,ML-DSA-44,2
"""


class ParseTests(unittest.TestCase):
    def test_parse_lines(self):
        p = parse_log.parse_lines(SAMPLE.splitlines())
        self.assertTrue(p.done)
        self.assertEqual(p.failures_reported, 2)
        self.assertEqual(p.config["seed"], "20261020")
        self.assertEqual(len(p.records), 10)
        self.assertEqual(p.records[1].cycles, 300)
        self.assertFalse(p.records[7].ok)

    def test_incomplete_log(self):
        p = parse_log.parse_lines(SAMPLE.splitlines()[:5])
        self.assertFalse(p.done)
        self.assertEqual(p.failures_reported, -1)

    def test_malformed_res(self):
        with self.assertRaises(ValueError):
            parse_log.parse_lines(["RES,ML-KEM-512,keygen,0,12"])
        with self.assertRaises(ValueError):
            parse_log.parse_lines(["RES,ML-KEM-512,keygen,0,12,maybe"])
        with self.assertRaises(ValueError):
            parse_log.parse_lines(["DONE,ML-KEM-512"])

    def test_summarise(self):
        p = parse_log.parse_lines(SAMPLE.splitlines())
        rows = {(r["parameter_set"], r["operation"]): r for r in parse_log.summarise(p.records)}
        sign = rows[("ML-DSA-44", "sign")]
        self.assertEqual((sign["min"], sign["median"], sign["max"]), (300, 500, 900))
        self.assertEqual(sign["ok"], 2)
        ver = rows[("ML-DSA-44", "verify")]
        self.assertEqual(ver["negative_n"], 3)
        self.assertEqual(ver["negative_ok"], 2)
        self.assertNotIn(("ML-DSA-44", "verify_rejects_modified"), rows)
        self.assertIn("modified message rejected: 2/3", parse_log.correctness_text(ver))

    def test_bootstrap(self):
        self.assertEqual(parse_log.bootstrap_median_ci([7, 7, 7]), (7.0, 7.0))
        lo, hi = parse_log.bootstrap_median_ci([1, 2, 3, 4, 100])
        self.assertLessEqual(lo, 3)
        self.assertGreaterEqual(hi, 3)
        self.assertEqual(parse_log.bootstrap_median_ci([1, 2, 3, 4, 100]), (lo, hi))  # seeded
        with self.assertRaises(ValueError):
            parse_log.bootstrap_median_ci([])


class ReportHelperTests(unittest.TestCase):
    def test_magnitude(self):
        self.assertEqual(report.order_of_magnitude_text(1.0), "same order of magnitude")
        self.assertEqual(report.order_of_magnitude_text(9.0), "same order of magnitude")
        self.assertEqual(report.order_of_magnitude_text(12.0), "about one order of magnitude higher")
        self.assertEqual(report.order_of_magnitude_text(0.05), "about one order of magnitude lower")

    def test_fmt(self):
        self.assertEqual(report.fmt_int(1234567.0), "1,234,567")


if __name__ == "__main__":
    unittest.main()
