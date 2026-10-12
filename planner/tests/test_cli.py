"""End to end tests of the command line interface. Author: Huda Mueen"""

import csv
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest

from .helpers import ROOT, CONF, SIG, csv_text
from fleetplan.__main__ import main
from fleetplan.loader import parse_text

SYNTH = os.path.join(ROOT, "examples", "synthetic_inventory.csv")
FOOTER = "This tool supports planning. It is not a security guarantee."
CLASSES = {"FIRMWARE_UPDATE", "HYBRID", "HARDWARE_REPLACEMENT",
           "NO_ACTION_BEFORE_RETIREMENT", "UNKNOWN"}


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    code = main(list(argv), out, err)
    return code, out.getvalue(), err.getvalue()


def csv_rows(text):
    lines = [l for l in text.splitlines() if not l.startswith("#")]
    return list(csv.DictReader(lines))


class SyntheticEndToEnd(unittest.TestCase):
    def setUp(self):
        self.ids = [r.device_id for r in parse_text(open(SYNTH).read()).records]

    def test_csv(self):
        code, out, _ = run(SYNTH, "--format", "csv")
        self.assertEqual(code, 0)
        rows = csv_rows(out)
        self.assertEqual([r["device_id"] for r in rows], self.ids)
        self.assertEqual(list(rows[0].keys()), ["device_id", "class", "reasons",
                                                "missing_fields", "handshake_s_estimate", "flags"])
        for r in rows:
            self.assertIn(r["class"], CLASSES)
            self.assertRegex(r["reasons"], r"Rule [1-8]")
            if r["class"] == "UNKNOWN":
                self.assertTrue(r["missing_fields"])
            float(r["handshake_s_estimate"])
        self.assertTrue(out.startswith("# SYNTHETIC"))
        self.assertIn(f"# {FOOTER}", out)
        self.assertIn("# Summary: 12 devices", out)

    def test_json(self):
        code, out, _ = run(SYNTH, "--format", "json")
        self.assertEqual(code, 0)
        doc = json.loads(out)
        self.assertEqual([d["device_id"] for d in doc["devices"]], self.ids)
        self.assertIn("SYNTHETIC", doc["banner"])
        self.assertEqual(doc["footer"], FOOTER)
        self.assertEqual(doc["summary"]["total"], len(self.ids))
        self.assertEqual(sum(doc["summary"]["counts"].values()), len(self.ids))
        for d in doc["devices"]:
            self.assertIn(d["class"], CLASSES)
            self.assertIsInstance(d["reasons"], list)
            self.assertTrue(d["reasons"])
        self.assertTrue(any("not measured" in n for n in doc["notes"]))

    def test_table(self):
        code, out, _ = run(SYNTH)
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith("SYNTHETIC"))
        self.assertTrue(out.rstrip().endswith(FOOTER))
        for i in self.ids:
            self.assertEqual(sum(1 for l in out.splitlines() if l.split(" ")[0] == i), 1, i)
        self.assertIn("Summary: 12 devices", out)

    def test_md(self):
        code, out, _ = run(SYNTH, "--format", "md")
        self.assertEqual(code, 0)
        self.assertIn("SYNTHETIC", out.splitlines()[0])
        for i in self.ids:
            self.assertEqual(sum(1 for l in out.splitlines() if l.startswith(f"| {i} |")), 1, i)
        self.assertIn(FOOTER, out)

    def test_explain_lists_every_reason(self):
        code, out, _ = run(SYNTH, "--explain")
        self.assertEqual(code, 0)
        self.assertIn("Parameters", out)
        self.assertIn("Explanations", out)
        self.assertIn("estimated from published sizes, not measured", out)

    def test_output_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "plan.csv")
            code, out, _ = run(SYNTH, "--format", "csv", "-o", path)
            self.assertEqual(code, 0)
            self.assertEqual(out, "")
            with open(path, encoding="utf-8") as h:
                self.assertEqual(h.read(), run(SYNTH, "--format", "csv")[1])

    def test_deterministic(self):
        for fmt in ("table", "csv", "json", "md"):
            self.assertEqual(run(SYNTH, "--format", fmt), run(SYNTH, "--format", fmt))

    def test_subprocess_module_entry(self):
        proc = subprocess.run([sys.executable, "-m", "fleetplan", SYNTH, "--format", "csv"],
                              cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(len(csv_rows(proc.stdout)), len(self.ids))


class FixtureEndToEnd(unittest.TestCase):
    """Rule level expectations derived from docs/PLANNER_RULES.md, small fixtures."""

    def write(self, d, text):
        path = os.path.join(d, "inv.csv")
        with open(path, "w", encoding="utf-8") as h:
            h.write(text)
        return path

    def classes(self, text, *extra):
        with tempfile.TemporaryDirectory() as d:
            code, out, err = run(self.write(d, text), "--format", "csv", *extra)
        self.assertEqual(code, 0, err)
        return {r["device_id"]: r for r in csv_rows(out)}, out

    def test_expected_classes(self):
        text = csv_text(
            {"device_id": "a", **SIG},
            {"device_id": "b", "bootrom_verifier_updatable": "no", "updatable_bootloader_stage": "yes", **SIG},
            {"device_id": "c", "bootrom_verifier_updatable": "no", "updatable_bootloader_stage": "no", **SIG},
            {"device_id": "d", **CONF},
            {"device_id": "e", "link_bandwidth_bps": "100", **CONF},
            {"device_id": "f"},
            {"device_id": "g", "flash_kb": ""},
            {"device_id": "h", "free_flash_kb": "1", **SIG},
        )
        rows, out = self.classes(text)
        got = {k: v["class"] for k, v in rows.items()}
        self.assertEqual(got, {
            "a": "FIRMWARE_UPDATE", "b": "HYBRID", "c": "HARDWARE_REPLACEMENT",
            "d": "FIRMWARE_UPDATE", "e": "HYBRID", "f": "NO_ACTION_BEFORE_RETIREMENT",
            "g": "UNKNOWN", "h": "HARDWARE_REPLACEMENT"})
        self.assertNotIn("SYNTHETIC", out)
        self.assertIn(f"# {FOOTER}", out)
        self.assertEqual(rows["g"]["missing_fields"], "flash_kb")

    def test_parameter_flags(self):
        text = csv_text({"device_id": "a", "service_life_remaining_years": "6"})
        rows, _ = self.classes(text)
        self.assertEqual(rows["a"]["class"], "FIRMWARE_UPDATE")
        rows, _ = self.classes(text, "--sig-horizon-year", "2032")   # SIG_YEARS 6, equal
        self.assertEqual(rows["a"]["class"], "NO_ACTION_BEFORE_RETIREMENT")
        rows, _ = self.classes(text, "--today-year", "2027")        # SIG_YEARS 3
        self.assertEqual(rows["a"]["class"], "FIRMWARE_UPDATE")
        text = csv_text({"device_id": "b", "link_bandwidth_bps": "100", **CONF})
        rows, _ = self.classes(text, "--hs-budget-s", "1000")
        self.assertEqual(rows["b"]["class"], "FIRMWARE_UPDATE")
        rows, _ = self.classes(text, "--conf-horizon-year", "2040")   # CONF_YEARS 14, 20 still exposed
        self.assertEqual(rows["b"]["class"], "HYBRID")
        rows, _ = self.classes(text, "--conf-horizon-year", "2050")   # CONF_YEARS 24
        self.assertEqual(rows["b"]["class"], "NO_ACTION_BEFORE_RETIREMENT")
        rows, _ = self.classes(csv_text({"device_id": "c", "free_flash_kb": "40", **SIG}),
                               "--sig-flash-kb", "50")
        self.assertEqual(rows["c"]["class"], "HARDWARE_REPLACEMENT")

    def test_synthetic_banner_from_notes_and_not_otherwise(self):
        _, out = self.classes(csv_text({"notes": "SYNTHETIC"}))
        self.assertTrue(out.startswith("# SYNTHETIC"))
        _, out = self.classes(csv_text({}))
        self.assertNotIn("SYNTHETIC", out)
        with tempfile.TemporaryDirectory() as d:
            for fmt in ("table", "json", "md"):
                path = self.write(d, csv_text({}, comments=["# SYNTHETIC: fixture"]))
                code, out, _ = run(path, "--format", fmt)
                self.assertEqual(code, 0)
                self.assertIn("SYNTHETIC", out, fmt)

    def test_errors_exit_two_with_clear_message(self):
        with tempfile.TemporaryDirectory() as d:
            code, out, err = run(os.path.join(d, "missing.csv"))
            self.assertEqual((code, out), (2, ""))
            self.assertIn("cannot read", err)
            bad = self.write(d, "device_id,ram_kb\nA,1\n")
            code, out, err = run(bad)
            self.assertEqual(code, 2)
            self.assertIn("required column", err)
            good = self.write(d, csv_text({}))
            code, _, err = run(good, "--hs-budget-s", "0")
            self.assertEqual(code, 2)
            self.assertIn("hs_budget_s", err)
            code, _, err = run(good, "--sig-horizon-year", "2000")
            self.assertEqual(code, 2)
            code, _, _ = run(good, "--format", "xml")
            self.assertEqual(code, 2)
            code, _, err = run(good, "--hs-bytes", "abc")
            self.assertEqual(code, 2)

    def test_malformed_values_end_to_end(self):
        text = csv_text({"device_id": "a", "link_bandwidth_bps": "0"},
                        {"device_id": "b", "ram_kb": "-4"},
                        {"device_id": "c", "flash_kb": "lots"})
        rows, _ = self.classes(text)
        for k in "abc":
            self.assertEqual(rows[k]["class"], "UNKNOWN")
        self.assertEqual(rows["a"]["handshake_s_estimate"], "")


if __name__ == "__main__":
    unittest.main()
