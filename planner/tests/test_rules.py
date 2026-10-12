"""Tests of the named parameters. Author: Huda Mueen"""

import unittest
from fractions import Fraction

from .helpers import Parameters


class ParameterTests(unittest.TestCase):
    def test_defaults_match_rules(self):
        p = Parameters()
        self.assertEqual(p.today_year, 2026)
        self.assertEqual(p.sig_years, 4)
        self.assertEqual(p.conf_years, 9)
        self.assertEqual(p.sig_flash_kb, 31)
        self.assertEqual(p.sig_ram_kb, 3)
        self.assertEqual(p.kem_flash_kb, 14)
        self.assertEqual(p.kem_ram_kb, 9)
        self.assertEqual(p.hs_bytes, 6068)
        self.assertEqual(p.hs_budget_s, 300)
        self.assertEqual(p.both_flash_kb, 45)
        self.assertEqual(p.both_ram_kb, 9)

    def test_hs_bytes_arithmetic(self):
        self.assertEqual(2 * 32 + 1184 + 1088 + 1312 + 2420, 6068)

    def test_override(self):
        p = Parameters().override(today_year=2027, hs_budget_s=Fraction(10), sig_flash_kb=None)
        self.assertEqual(p.sig_years, 3)
        self.assertEqual(p.hs_budget_s, 10)
        self.assertEqual(p.sig_flash_kb, 31)

    def test_invalid_values(self):
        with self.assertRaises(ValueError):
            Parameters(hs_budget_s=0)
        with self.assertRaises(ValueError):
            Parameters(sig_flash_kb=-1)
        with self.assertRaises(ValueError):
            Parameters(sig_horizon_year=2020)
        with self.assertRaises(ValueError):
            Parameters(conf_horizon_year=2020)

    def test_describe_marks_overrides(self):
        rows = {r[0]: r for r in Parameters(hs_budget_s=5).describe()}
        self.assertTrue(rows["hs_budget_s"][4])
        self.assertFalse(rows["today_year"][4])
        self.assertEqual(rows["sig_years"][1], 4)


if __name__ == "__main__":
    unittest.main()
