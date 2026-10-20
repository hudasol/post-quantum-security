import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import check_labels as cl  # noqa: E402


class TestLabels(unittest.TestCase):
    def write(self, header, rows):
        d = Path(tempfile.mkdtemp())
        p = d / "r.csv"
        with open(p, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(header)
            w.writerows(rows)
        return p

    def test_good_file(self):
        p = self.write(["op", "cycles_published", "cycles_modelled", "label"], [["x", 1, 2, "modelled"]])
        self.assertEqual(cl.check_file(p), [])

    def test_unknown_label(self):
        p = self.write(["op", "label"], [["x", "measured on board"]])
        self.assertTrue(cl.check_file(p))

    def test_missing_label_column(self):
        p = self.write(["op", "cycles"], [["x", 1]])
        self.assertTrue(cl.check_file(p))

    def test_unknown_suffix(self):
        p = self.write(["op", "cycles_guessed_simulated", "label"], [["x", 1, "estimated"]])
        self.assertTrue(cl.check_file(p))


if __name__ == "__main__":
    unittest.main()
