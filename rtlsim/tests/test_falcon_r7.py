"""Round 7 Falcon-512 RTL results: the result files regenerate from the committed logs and the runs are complete and
correct. Author: Huda Mueen."""
import csv
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class TestFalconR7(unittest.TestCase):
    def test_runs_complete_and_correct(self):
        rows = list(csv.DictReader(open(ROOT / "rtlsim/results/proto_falcon.csv", encoding="utf-8")))
        self.assertEqual({r["core"] for r in rows}, {"ibex", "cv32e40p"})
        for r in rows:
            self.assertEqual(r["log_complete"], "True")
            self.assertEqual(r["calls_succeeded"], r["n_runs"])
            self.assertEqual(r["checks_passed"], r["checks_total"])
            self.assertEqual(r["stack_saturated"], "False")
            self.assertEqual(r["signature_bytes"], "666")
            self.assertEqual(r["n_runs"], "1" if r["operation"] == "provisioning_keypair" else "15")

    def test_regenerates(self):
        before = {p: (ROOT / p).read_bytes() for p in ("rtlsim/results/proto_falcon.csv",
                                                       "rtlsim/results/proto_falcon_ratios.csv",
                                                       "docs/RTL_FALCON_R7.md")}
        subprocess.run([sys.executable, str(ROOT / "rtlsim/proto/parse_falcon.py")], check=True, capture_output=True)
        for p, b in before.items():
            self.assertEqual((ROOT / p).read_bytes(), b, p)


if __name__ == "__main__":
    unittest.main()
