import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestCitations(unittest.TestCase):
    def test_bibliography_current_and_complete(self):
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "check_citations.py")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_key_is_stable(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import build_bibliography as b
        self.assertEqual(b.key_for("https://eprint.iacr.org/2026/1333.pdf"), "iacr_2026_1333")


if __name__ == "__main__":
    unittest.main()
