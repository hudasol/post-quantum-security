"""Tests of the formal verification study (python3 -m unittest discover -s formal -t .).

Author: Huda Mueen.

The parser tests run without ProVerif. The parse check of the models runs
only when ProVerif is installed (sh formal/install.sh), so CI without the tool
still runs the parser tests.
"""
import csv
import os
import subprocess
import unittest

from formal import build_models, run_all

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestModels(unittest.TestCase):
    def test_rendered_models_match_files(self):
        for name, text in build_models.all_models().items():
            path = os.path.join(HERE, "models", name + ".pv")
            self.assertTrue(os.path.exists(path), name)
            self.assertEqual(open(path).read(), text.lstrip("\n"), f"{name} differs; rerun formal.build_models")

    def test_every_model_has_queries_and_header(self):
        for name in build_models.all_models():
            design, setting, queries = run_all.parse_model(os.path.join(HERE, "models", name + ".pv"))
            self.assertTrue(design and setting, name)
            self.assertGreater(len(queries), 0, name)
            ids = [q[0] for q in queries]
            self.assertEqual(len(ids), len(set(ids)), name)


class TestResults(unittest.TestCase):
    def setUp(self):
        self.rows = list(csv.DictReader(open(run_all.CSV_PATH)))

    def test_columns_and_label(self):
        self.assertEqual(list(self.rows[0].keys()), run_all.FIELDS)
        for r in self.rows:
            self.assertEqual(r["label"], "modelled")
            self.assertEqual(r["proverif_version"], run_all.PINNED_VERSION)

    def test_every_property_has_a_result(self):
        got = {(r["model"], r["property_id"]): r["result"] for r in self.rows}
        for name in build_models.all_models():
            _, _, queries = run_all.parse_model(os.path.join(HERE, "models", name + ".pv"))
            for qid, _, _ in queries:
                self.assertIn((name, qid), got)
                self.assertTrue(got[(name, qid)] in ("proved", "counterexample")
                                or got[(name, qid)].startswith("cannot be proved"), (name, qid))

    def test_every_counterexample_has_a_fixed_model_that_proves(self):
        """Gate: each counterexample in a stated design is removed by a design change."""
        got = {(r["model"], r["property_id"]): r["result"] for r in self.rows}
        pairs = {"session_b_stated": "session_b_fixed", "fallback_d_stated": "fallback_d_fixed",
                 "firmware_stated_no_counter": "firmware_fixed_counter"}
        for stated, fixed in pairs.items():
            for (m, q), res in got.items():
                if m == stated and res == "counterexample":
                    self.assertEqual(got.get((fixed, q)), "proved", (stated, q))

    def test_output_parser(self):
        out = ("RESULT inj-event(A(x)) ==> inj-event(B(x)) is false.\n"
               "RESULT (but event(A(x)) ==> event(B(x)) is true.)\n"
               "RESULT not attacker(k) is true.\n"
               "RESULT event(C) ==> event(D) cannot be proved.\n")
        self.assertEqual(run_all.parse_output(out), [("counterexample", "non injective form proved"),
                                                     ("proved", ""), ("cannot be proved", "")])


@unittest.skipUnless(run_all.find_proverif(), "ProVerif not installed")
class TestProVerifParses(unittest.TestCase):
    def test_all_models_parse(self):
        """Parsing and type checking come first in a ProVerif run; a short run of each
        model shows no syntax or type error (long proofs are left to formal.run_all)."""
        binary = run_all.find_proverif()
        for name in build_models.all_models():
            try:
                p = subprocess.run([binary, os.path.join(HERE, "models", name + ".pv")],
                                   capture_output=True, text=True, timeout=3)
                out = p.stdout + p.stderr
            except subprocess.TimeoutExpired as e:
                out = (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
            self.assertNotIn("Error", out, name)

if __name__ == "__main__":
    unittest.main()
