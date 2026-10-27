"""Tests for the round 6 dblp search files and the related work table (stream S14).

Run from the repository root: python3 -m unittest discover -s relwork -t .
"""
import csv
import subprocess
import sys
import unittest
from pathlib import Path

from relwork import build_related_work as brw
from relwork import build_s14_dblp as bsd
from relwork import check_s14_counts as csc

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"


def read(name):
    with open(RAW / name, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


class TestKeyHelpers(unittest.TestCase):
    def test_year_from_key(self):
        self.assertEqual(bsd.year_from_key("journals/micro/MisoczkiGGDVF19"), "2019")
        self.assertEqual(bsd.year_from_key("journals/corr/abs-2409-05298"), "2024")
        self.assertEqual(bsd.year_from_key("books/sp/21/BBKPRS2021"), "2021")
        self.assertEqual(bsd.year_from_key("conf/pqcrypto/2013"), "2013")
        self.assertEqual(bsd.year_from_key("journals/iacr/BernsteinL17a"), "2017")
        self.assertEqual(bsd.year_from_key("conf/iccad/OrtegaB98"), "1998")

    def test_arxiv_id(self):
        self.assertEqual(bsd.arxiv_id("journals/corr/abs-2505-02239"), "2505.02239")
        self.assertEqual(bsd.arxiv_id("conf/date/FritzmannSMRSS19"), "")

    def test_clean_title_and_kind(self):
        self.assertEqual(bsd.clean_title("dblp: The SPHINCS<sup>+</sup> Signature Framework."), "The SPHINCS+ Signature Framework")
        self.assertEqual(bsd.page_kind("https://dblp.org/rec/conf/x/Y20.html"), "record")
        self.assertEqual(bsd.page_kind("https://dblp.org/pid/67/675.html"), "person page")
        self.assertEqual(bsd.page_kind("https://dblp.org/db/conf/pqcrypto/index.html"), "venue or volume page")

    def test_match_needs_four_words(self):
        self.assertEqual(bsd.match("Post-quantum WireGuard", "", bsd.norm("post quantum wireguard")), "")
        self.assertEqual(bsd.match("First-Order Masked Kyber on ARM Cortex-M4", "", bsd.norm("x first order masked kyber on arm cortex m4 y")), "title")


class TestDblpFiles(unittest.TestCase):
    def test_build_reproduces_files(self):
        before = {n: (RAW / n).read_text(encoding="utf-8") for n in ("S14_dblp_log.csv", "S14_dblp_records.csv", "S14_screening.csv")}
        bsd.build()
        for n, text in before.items():
            self.assertEqual((RAW / n).read_text(encoding="utf-8"), text, n)

    def test_counts_consistent(self):
        c, problems = csc.problems()
        self.assertEqual(problems, [])
        self.assertEqual(c["results_returned"], len(read("S14_dblp_search_raw.csv")))
        self.assertLessEqual(c["passing_new_to_repository"], c["passing_not_seen_in_round5_screening"])

    def test_every_record_screened_once(self):
        keys = [r["dblp_key"] for r in read("S14_title_screen.csv")]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(set(keys), {r["dblp_key"] for r in read("S14_dblp_records.csv")})
        for r in read("S14_title_screen.csv"):
            self.assertIn(r["decision"], {"pass", "exclude"})
            self.assertTrue(r["reason"])

    def test_refusals_logged(self):
        log = read("S14_dblp_log.csv")
        self.assertTrue(any(r["status"] == "refused" and "api" in r["query"] for r in log))
        for r in log:
            self.assertEqual(r["label"], "published")


class TestRelatedWork(unittest.TestCase):
    def test_usable_only_when_read_directly(self):
        for r in read("S14_related_work.csv"):
            if r["usable_as_evidence"] == "yes":
                self.assertEqual(r["full_text_read"], "yes", r["id"])
                self.assertNotIn("fetch tool", r["read_via"], r["id"])
            if r["full_text_read"] in ("no", "partly") or r["full_text_read"].startswith("yes, through"):
                self.assertEqual(r["usable_as_evidence"], "no", r["id"])

    def test_values_have_locations(self):
        for r in read("S14_related_work.csv"):
            for v, loc in (("handshake_value_as_stated", "handshake_location"), ("per_message_value_as_stated", "per_message_location"),
                           ("other_value_as_stated", "other_location")):
                if r[v] and not r[v].startswith("not usable"):
                    self.assertTrue(r[loc], (r["id"], v))

    def test_doc_current(self):
        self.assertEqual((ROOT / "docs" / "RELATED_WORK.md").read_text(encoding="utf-8"), brw.render())

    def test_doc_rows(self):
        text = brw.render()
        for r in read("S14_related_work.csv"):
            self.assertIn(f"| {r['id']} ", text)
        self.assertIn("This study (round 6)", text)


class TestGeneratedDocs(unittest.TestCase):
    def test_search_protocol_has_round6(self):
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "build_search_protocol.py")], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        text = (ROOT / "docs" / "SEARCH_PROTOCOL.md").read_text(encoding="utf-8")
        self.assertIn("## Round 6 flow", text)
        c, _ = csc.problems()
        self.assertIn(f"| distinct records | {c['distinct_records']} |", text)

    def test_bibliography_lists_retrieved_related_work(self):
        bib = (ROOT / "data" / "bibliography.bib").read_text(encoding="utf-8")
        for r in read("S14_related_work.csv"):
            if r["read_via"].startswith("not retrieved"):
                continue
            self.assertIn(r["url"], bib, r["id"])


if __name__ == "__main__":
    unittest.main()
