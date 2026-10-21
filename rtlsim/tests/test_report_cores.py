"""Unit tests for rtlsim/report_cores.py. Author: Huda Mueen. Values below are test input only."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import report_cores  # noqa: E402


class SpreadTests(unittest.TestCase):
    def test_spread_on_common_operations(self):
        rows = report_cores.spread_rows({
            "ibex": {("ML-KEM-512", "keygen"): 200.0, ("ML-KEM-512", "encaps"): 300.0},
            "cv32e40p": {("ML-KEM-512", "keygen"): 100.0}})
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertEqual(r["max_over_min"], 2.0)
        self.assertEqual((r["slowest_core"], r["fastest_core"]), ("ibex", "cv32e40p"))
        self.assertEqual(r["label"], "RTL simulated")

    def test_missing_core_logs_give_no_rows(self):
        summary, missing, _ = report_cores.summarise_core(
            "no_such_core", ["ML-KEM-512"], {"ML-KEM": ["keygen"]}, {})
        self.assertEqual(summary, [])
        self.assertEqual(missing, ["ML-KEM-512"])


if __name__ == "__main__":
    unittest.main()
