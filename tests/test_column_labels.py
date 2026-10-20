"""Every column of the round 2 and 3 result files without a label column has a label in data/column_labels.csv."""
import csv
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VOCAB = {"key", "per row", "published", "host measured", "emulated", "estimated", "modelled", "RTL simulated", "planned"}


class TestColumnLabels(unittest.TestCase):
    def test_every_column_labelled(self):
        rows = list(csv.DictReader(open(ROOT / "data" / "column_labels.csv", encoding="utf-8")))
        by_file = {}
        for r in rows:
            self.assertIn(r["label"], VOCAB, r)
            by_file.setdefault(r["file"], set()).add(r["column"])
        for f, cols in by_file.items():
            header = next(csv.reader(open(ROOT / f, encoding="utf-8")))
            self.assertEqual(set(header), cols, f)


if __name__ == "__main__":
    unittest.main()
