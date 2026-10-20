"""Every flag the column lint raises on the current evidence table must have been reviewed and judged a false
positive (real errors are fixed in data/corrections.csv). Author: Huda Mueen."""
import csv
import os
import unittest

from scripts import lint_columns

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestLintColumns(unittest.TestCase):
    def test_tables_parser(self):
        self.assertEqual(lint_columns.tables("Tables 4 and 5 give the mean; Table 6 the rest"), {"4", "5", "6"})
        self.assertEqual(lint_columns.tables("Tables 8, 9 and 10"), {"8", "9", "10"})

    def test_rules(self):
        base = {k: "" for k in ("cycles", "comparability_warning", "compiler_flags_or_notes", "key_or_sig_size_bytes",
                                "size_kind", "stack_bytes", "location_in_source", "device_class", "clock_mhz",
                                "flash_or_code_bytes")}
        r = dict(base, cycles="54111000", comparability_warning="Table gives 54111 KiloTicks")
        self.assertIn("T1", [f[0] for f in lint_columns.lint(r)])
        r = dict(base, cycles="1536343", comparability_warning="cycles via SysTick")
        self.assertNotIn("T1", [f[0] for f in lint_columns.lint(r)])
        r = dict(base, key_or_sig_size_bytes="2420")
        self.assertIn("S1", [f[0] for f in lint_columns.lint(r)])

    def test_all_current_flags_reviewed_as_false_positives(self):
        rows = list(csv.DictReader(open(os.path.join(ROOT, "data", "evidence.csv"), newline="", encoding="utf-8")))
        review = {}
        for rel in (("data", "verify4", "lint_review.csv"), ("data", "verify5", "lint_review_s12.csv")):
            review.update({r["id"]: r["verdict"] for r in csv.DictReader(
                open(os.path.join(ROOT, *rel), newline="", encoding="utf-8"))})
        for r in rows:
            for rule, why in lint_columns.lint(r):
                self.assertEqual(review.get(r["id"]), "false", f"{r['id']} {rule}: {why} (not reviewed)")


if __name__ == "__main__":
    unittest.main()
