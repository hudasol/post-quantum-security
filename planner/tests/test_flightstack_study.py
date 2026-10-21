"""Tests of planner/flightstack_study.py.

Author: Huda Mueen
"""

import os
import tempfile
import unittest
from fractions import Fraction

from tests import helpers  # noqa: F401  (puts the planner root on sys.path)

import flightstack_study as fss  # noqa: E402
import profile_study as ps  # noqa: E402

FIELDS = "stack,target,board,build_status,flash_free_bytes,ram_free_static_bytes\n"


class TestMeasuredFree(unittest.TestCase):
    def test_smaller_value_over_stacks(self):
        rows = [{"stack": "px4", "board": "B", "build_status": "built", "flash_free_bytes": "5000",
                 "ram_free_static_bytes": "9000"},
                {"stack": "ardupilot", "board": "B", "build_status": "built", "flash_free_bytes": "7000",
                 "ram_free_static_bytes": "3000"},
                {"stack": "px4", "board": "C", "build_status": "failed", "flash_free_bytes": "",
                 "ram_free_static_bytes": ""}]
        free = fss.measured_free(rows)
        self.assertEqual(set(free), {"B"})
        self.assertEqual(free["B"][:2], (5000, 3000))

    def test_apply_measured(self):
        profiles = ps.load_profiles()
        b = profiles[0]["board"]
        out = fss.apply_measured(profiles, {b: (12345, 678, ["px4"])})
        self.assertEqual(out[0]["free_flash_kb"], Fraction(12345, 1000))
        self.assertEqual(out[0]["free_ram_kb"], Fraction(678, 1000))
        self.assertEqual(out[1]["free_flash_kb"], profiles[1]["free_flash_kb"])
        # the input profiles are not changed
        self.assertIsNone(profiles[0]["free_flash_kb"])

    def test_unknown_board_rejected(self):
        with self.assertRaises(ValueError):
            fss.apply_measured(ps.load_profiles(), {"no such board": (1, 1, ["px4"])})


class TestRun(unittest.TestCase):
    def test_small_run_pairs_draws(self):
        """With a measured file that changes nothing material (huge free memory on one board),
        the measured share never exceeds the assumed share draw by draw."""
        profiles = ps.load_profiles()
        board = profiles[0]["board"]
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "m.csv")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(FIELDS + "px4,t,%s,built,%d,%d\n" % (board, int(profiles[0]["flash_kb"] * 1000),
                                                             int(profiles[0]["ram_kb"] * 1000)))
            out = fss.run(draws=5, measured_path=path)
        for k in fss.THRESHOLDS:
            for a, m in zip(out["mc_assumed"][k], out["mc_measured"][k]):
                self.assertLessEqual(m, a + 1e-12)
        self.assertEqual(len(out["summary"]), len(fss.THRESHOLDS))
        for s in out["summary"]:
            self.assertEqual(s["label"], "estimated")
            self.assertLessEqual(s["change_ci_low"], s["change_ci_high"])

    def test_paired_diff_zero(self):
        a = [0.1, 0.2, 0.3, 0.4]
        self.assertEqual(fss.paired_diff_ci(a, a), (0.0, 0.0))


if __name__ == "__main__":
    unittest.main()
