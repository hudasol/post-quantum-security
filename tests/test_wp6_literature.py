"""Tests for the round 5 literature package (stream S13): sheets, flow, promotion, merge, quality."""
import csv
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import summarize_verification6 as sv  # noqa: E402


def rows(p):
    with open(ROOT / p, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


class TestS13(unittest.TestCase):
    def test_sheet_is_blank_and_matches_staging(self):
        sheet, staged = rows("data/verify6/sheet_rows.csv"), rows("data/raw/S13_staged.csv")
        self.assertEqual([r["id"] for r in sheet], [r["id"] for r in staged])
        for r in sheet:
            for f in sv.FIELDS:
                self.assertEqual(r[f], "", f"{r['id']} {f} not blank")

    def test_staged_schema(self):
        staged = rows("data/raw/S13_staged.csv")
        hdr = list(staged[0].keys())
        self.assertEqual(hdr, list(rows("data/raw/S12A_staged.csv")[0].keys()))
        for r in staged:
            self.assertTrue(r["source_url"].startswith("http"))
            self.assertEqual(r["evidence_type"], "published")
            self.assertTrue(r["location_in_source"].strip())

    def test_wording_synonyms(self):
        self.assertTrue(sv.same_wording("operation", "keygen", "Key Generation"))
        self.assertTrue(sv.same_wording("operation", "keygen (unmasked, accelerated)", "Key gen."))
        self.assertFalse(sv.same_wording("operation", "sign", "Verify"))
        self.assertFalse(sv.same_wording("cycles", "1000", "1100"))

    def test_promoted_rows_are_confirmed_and_unchanged(self):
        staged = {r["id"]: r for r in rows("data/raw/S13_staged.csv")}
        status = {r["id"]: r["status"] for r in rows("data/verify6/row_status.csv")}
        ver = rows("data/raw/S13_verified.csv")
        self.assertGreaterEqual(len(ver), 150)
        for r in ver:
            self.assertIn(status[r["id"]], ("confirmed", "corrected"))
            if "corrected from" not in r["comparability_warning"]:
                for f in sorted(sv.VALUE & set(r)):
                    self.assertEqual(r[f], staged[r["id"]][f])

    def test_every_disagreement_has_a_third_look(self):
        queue = {(r["id"], r["field"]) for r in rows("data/verify6/third_look_queue.csv")}
        dis = {(r["id"], r["field"]) for r in rows("data/verify6/summary.csv") if r["status"] == "disagree"}
        self.assertTrue(dis <= queue)
        answered = {(r["id"], r["field"]) for r in rows("data/verify6/third_look.csv")}
        self.assertEqual(queue, answered)
        q = rows("data/verify6/third_look_queue.csv")
        self.assertNotIn("staged", ",".join(q[0].keys()))

    def test_merge_includes_s13(self):
        ev = [r for r in rows("data/evidence.csv") if r["stream"] == "S13"]
        self.assertEqual(len(ev), len(rows("data/raw/S13_verified.csv")))

    def test_prisma_regenerates(self):
        before = (ROOT / "data/raw/S13_prisma.csv").read_text()
        subprocess.run([sys.executable, str(ROOT / "scripts/build_s13_prisma.py")], check=True, capture_output=True)
        self.assertEqual(before, (ROOT / "data/raw/S13_prisma.csv").read_text())
        flow = {r["stage"]: int(r["count"]) for r in rows("data/raw/S13_prisma.csv")}
        log = rows("data/raw/S13_search_log.csv")
        self.assertEqual(flow["identified"], sum(int(r["records_returned"]) for r in log))
        self.assertEqual(flow["staged rows"], len(rows("data/raw/S13_staged.csv")))
        self.assertGreaterEqual(flow["identified"], flow["screened on title and snippet"])
        self.assertGreaterEqual(flow["eligible (abstract or full text assessed)"], flow["included sources"])

    def test_search_protocol_lists_every_query(self):
        doc = (ROOT / "docs/SEARCH_PROTOCOL.md").read_text()
        for r in rows("data/raw/S13_search_log.csv"):
            self.assertIn(f"| {r['query_id']} |", doc)

    def test_quality_scores(self):
        q = rows("data/source_quality.csv")
        items = [r["item"] for r in rows("data/source_quality_checklist.csv")]
        self.assertEqual(len(items), 5)
        srcs = {r["source_url"] for r in rows("data/evidence.csv") if r["cycles"].strip()}
        self.assertEqual(srcs, {r["source_url"] for r in q})
        for r in q:
            self.assertEqual(int(r["score"]), sum(int(r[i]) for i in items))
            for i in items:
                self.assertTrue(r[i + "_reason"].strip())


if __name__ == "__main__":
    unittest.main()
