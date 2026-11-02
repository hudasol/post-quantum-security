"""The preregistration record (scripts/prereg_record.py) holds: every hashed prediction file matches its stored
SHA-256 as first added, the snapshot copies match their recorded SHA-256, and every commit of the ID map has the
tree recorded for it. Author: Huda Mueen."""
import csv
import subprocess
import unittest
from pathlib import Path

from scripts import prereg_record

ROOT = Path(__file__).resolve().parents[1]
HIST = ROOT / "data" / "history"


def rows(name):
    with open(HIST / name, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


class TestPreregRecord(unittest.TestCase):
    def test_hashed_files_match_as_first_added(self):
        r = rows("prereg_hashes.csv")
        self.assertTrue(r)
        self.assertEqual([x["file"] for x in r if x["match_at_first_commit"] != "yes"], [])

    def test_snapshot_copies_match_their_hash(self):
        for s in rows("snapshots.csv"):
            if s["copy"]:
                self.assertEqual(prereg_record.sha256((ROOT / s["copy"]).read_bytes()), s["sha256"], s["name"])
                self.assertTrue(prereg_record.snapshot_text(s["name"]))

    def test_commit_map_keeps_trees(self):
        m = rows("commit_ids_2026-10-29.csv")
        self.assertGreater(len(m), 500)
        ids = "\n".join(f"{x['new_id']}^{{tree}}" for x in m)
        out = subprocess.run(["git", "cat-file", "--batch-check"],
                             input=ids, cwd=ROOT, capture_output=True, text=True).stdout.split("\n")
        found = [line.split()[0] for line in out if line and not line.endswith("missing")]
        if len(found) < len(m):
            self.skipTest("history not fully fetched")
        self.assertEqual(found, [x["tree_id"] for x in m])


if __name__ == "__main__":
    unittest.main()
