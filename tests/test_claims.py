"""Tests for the retracted claim guard. Author: Huda Mueen."""
import os
import unittest

from scripts import check_claims

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestClaims(unittest.TestCase):
    def test_flags_retracted_claim(self):
        txt = "1. There are no published ML-KEM, ML-DSA or SLH-DSA cycle counts for a named Cortex-M33 core."
        self.assertEqual(len(check_claims.scan_text(txt, "x.md")), 1)
        self.assertEqual(len(check_claims.scan_text("| Unmeasured | no M33 numbers |", "x.md")), 1)

    def test_correction_lines_pass(self):
        txt = "Correction (2026-10-18): earlier versions said there were no published ML-KEM, ML-DSA cycle counts."
        self.assertEqual(check_claims.scan_text(txt, "x.md"), [])

    def test_unrelated_text_passes(self):
        self.assertEqual(check_claims.scan_text("Cortex-M33 cycles exist for ML-DSA keygen and sign.", "x.md"), [])

    def test_repository_is_clean(self):
        self.assertEqual(check_claims.check(ROOT), [])


if __name__ == "__main__":
    unittest.main()
