import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import check_numbers as cn  # noqa: E402


class TestCheckNumbers(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "d.csv").write_text("k,v\na,10\nb,30\n")
        (self.tmp / "doc.md").write_text("The median is 20 cycles.")
        self.old = (cn.ROOT, cn.REG)
        cn.ROOT, cn.REG = self.tmp, self.tmp / "reg.csv"

    def tearDown(self):
        cn.ROOT, cn.REG = self.old

    def reg(self, value, text):
        with open(cn.REG, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["claim_id", "document", "text_in_document", "value", "source_file", "column", "query", "aggregate", "tolerance_rel", "label", "note"])
            w.writerow(["C1", "doc.md", text, value, "d.csv", "v", "", "median", "", "published", ""])

    def test_pass(self):
        self.reg(20, "median is 20")
        self.assertEqual(cn.main(), 0)

    def test_value_drift_fails(self):
        self.reg(21, "median is 20")
        self.assertEqual(cn.main(), 1)

    def test_text_drift_fails(self):
        self.reg(20, "median is 25")
        self.assertEqual(cn.main(), 1)

    def test_single_value_query(self):
        self.assertEqual(cn.compute("d.csv", "v", "k == 'b'", "value"), 30.0)


if __name__ == "__main__":
    unittest.main()
