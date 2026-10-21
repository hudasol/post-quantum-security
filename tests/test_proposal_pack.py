"""Tests of the robotics proposal pack (round 5). Author: Huda Mueen.

Run: python3 -m unittest discover -s tests -t .
"""
import csv
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import proposal_texts  # noqa: E402

PROP = ROOT / "data" / "proposal"
DOCS = ["docs/PROPOSAL_ROBOTICS.md", "docs/PROPOSAL_ROBOTICS_ATRC.md", "docs/PROPOSAL_ROBOTICS_EDGE.md",
        "docs/PROPOSAL_ROBOTICS_ADEO.md", "docs/PROPOSAL_BRIEF.md"]
POLICY_PDF = Path("/mnt/user-data/uploads/sources/UAE National Encryption Policy - Cyber Security Council.pdf")


def rows(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


class TestProposalData(unittest.TestCase):
    def test_every_file_has_a_label(self):
        for p in PROP.glob("*.csv"):
            for r in rows(p):
                self.assertIn(r["label"], {"planned", "estimated", "published"}, p.name)

    def test_plan_months(self):
        plan = rows(PROP / "plan.csv")
        ids = {r["id"] for r in plan}
        for r in plan:
            self.assertLessEqual(int(r["start_month"]), int(r["end_month"]), r["id"])
            for d in r["depends_on"].split():
                self.assertIn(d, ids)
        last = max(int(r["end_month"]) for r in plan)
        for m in rows(PROP / "milestones.csv"):
            self.assertTrue(1 <= int(m["month"]) <= last, m["id"])

    def test_zero_purchases(self):
        self.assertEqual(sum(int(r["purchase_count"]) for r in rows(PROP / "equipment.csv")), 0)

    def test_no_personal_data(self):
        for r in rows(PROP / "data_management.csv"):
            self.assertTrue(r["personal_data"].startswith("none"), r["item"])

    def test_readiness_levels_on_the_scale(self):
        scale = {r["level"] for r in rows(PROP / "trl_scale.csv")}
        self.assertEqual(scale, {str(i) for i in range(1, 10)})
        for r in rows(PROP / "readiness.csv"):
            self.assertIn(r["trl_now"], scale)
            self.assertIn(r["trl_end"], scale)
            self.assertLessEqual(int(r["trl_now"]), int(r["trl_end"]))
            self.assertLessEqual(int(r["trl_end"]), 4, "a lab only project cannot claim more than lab validation")

    def test_fit_ids_exist_and_deliverables_planned(self):
        facts = {r["fact_id"] for r in rows(ROOT / "data" / "context_entities.csv")}
        delivered = {r["deliverable"] for r in rows(PROP / "plan.csv")}
        for r in rows(PROP / "policy_fit.csv"):
            for i in r["entity_fact_ids"].split():
                self.assertIn(i, facts)
            self.assertIn(r["id"], delivered)
            self.assertTrue(r["policy_section_published"].startswith("6.1."))
            self.assertLessEqual(len(r["policy_term_published"].split()), 12, "quotes stay short")

    @unittest.skipUnless(POLICY_PDF.exists() and shutil.which("pdftotext"), "supplied policy PDF not present")
    def test_policy_terms_are_verbatim(self):
        text = subprocess.run(["pdftotext", "-f", "36", "-l", "37", str(POLICY_PDF), "-"], capture_output=True, text=True).stdout
        flat = " ".join(text.split())
        for r in rows(PROP / "policy_fit.csv"):
            self.assertIn(r["policy_term_published"], flat)
            self.assertIn(r["policy_section_published"], flat)


class TestProposalDocs(unittest.TestCase):
    def test_seed_note_on_every_variant(self):
        for d in DOCS:
            self.assertIn(proposal_texts.SEED_NOTE, (ROOT / d).read_text(encoding="utf-8"), d)

    def test_fit_table_uses_ids_only(self):
        text = (ROOT / "docs" / "PROPOSAL_ROBOTICS.md").read_text(encoding="utf-8")
        fit = text.split("## 7. Fit", 1)[1].split("## 8.", 1)[0]
        brief = (ROOT / "docs" / "PROPOSAL_BRIEF.md").read_text(encoding="utf-8")
        for f in rows(ROOT / "data" / "context_entities.csv"):
            self.assertNotIn(f["paraphrase"][:60], fit)
            self.assertNotIn(f["paraphrase"][:60], brief)

    def test_docs_registered_as_claims(self):
        reg = rows(ROOT / "data" / "claims_register.csv")
        for d in DOCS:
            self.assertTrue(any(r["document"] == d for r in reg), d)

    def test_sitl_placeholder_has_no_numbers(self):
        text = (ROOT / "docs" / "PROPOSAL_ROBOTICS.md").read_text(encoding="utf-8")
        sec = text.split("### 2.2", 1)[1].split("## 3.", 1)[0]
        self.assertFalse(any(ch.isdigit() for ch in sec.replace("2.2", "")))

    def test_gantt_draws(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import make_gantt
        with tempfile.TemporaryDirectory() as tmp:
            out = make_gantt.draw(make_gantt.read("data/proposal/plan.csv"), make_gantt.read("data/proposal/milestones.csv"),
                                  Path(tmp) / "g.png")
            self.assertEqual(out.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")


if __name__ == "__main__":
    unittest.main()
