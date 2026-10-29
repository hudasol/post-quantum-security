"""Tests of the round 7 additions to the formal models (python3 -m unittest discover -s formal -t .).

Author: Huda Mueen.

Round 7 answers three review findings: the hybrid session models had no reachability check (R0, RV, RG), no model
broke the signature component (session_b_fixed_sig_*), and the general A2 query of design K reached the time limit
(session_kemauth_a2_retry). These tests check the structure of the new and extended models, that every new query has
a row, and that all 140 rows written before round 7 are unchanged in every column.
"""
import csv
import hashlib
import os
import unittest

from formal import build_models, make_doc, run_all

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SIG_BROKEN = [m[0] for m in build_models.SESSION_SIG_BROKEN_MODELS]
STATIC_KNOWN = [m[0] for m in build_models.KEMAUTH_R7_MODELS]
RETRY = [build_models.KEMAUTH_A2_RETRY[0]]
ROUND7_MODELS = set(SIG_BROKEN + STATIC_KNOWN + RETRY)
SESSION_B = [m[0] for m in build_models.SESSION_MODELS]
WITH_AGREEMENT = (["session_kemauth", "session_kemauth_a2_typed_static", "session_kemauth_replay_cache"]
                  + [m[0] for m in build_models.REPLAY_MODELS if m[7]])

# Fingerprint of every column of the 140 rows of formal/results/proverif_results.csv before round 7.
BEFORE_ROWS = 140
BEFORE_SHA256 = "0bb8762d1407ad4a471e9745e6768520b6da9765188e0cd21819fcdc103ce276"


def is_round7(row):
    """True for a row added in round 7: a row of a new model, a new reachability or matched session query, or R0
    in a session_b_* model (R0 was asked before only in the replay rule models and design K)."""
    m, q = row["model"], row["property_id"]
    return (m in ROUND7_MODELS or q in ("RV", "RG", "SM")
            or (q == "R0" and m.startswith("session_b_")))


def load_rows():
    with open(run_all.CSV_PATH) as f:
        return list(csv.DictReader(f))


def query_ids(name):
    return [q[0] for q in run_all.parse_model(os.path.join(HERE, "models", name + ".pv"))[2]]


class TestRound7Models(unittest.TestCase):
    def setUp(self):
        self.models = build_models.all_models()

    def test_session_b_models_ask_reachability_last(self):
        self.assertEqual(len(SESSION_B), 10)
        for name in SESSION_B:
            self.assertEqual(query_ids(name)[-3:], ["R0", "RV", "RG"], name)
            self.assertIn("event(VAccept(s, k)) ==> false.", self.models[name], name)
            self.assertIn("event(GSAccept(s, k)) ==> false.", self.models[name], name)

    def test_agreement_models_ask_both_sides(self):
        for name in WITH_AGREEMENT + SIG_BROKEN + STATIC_KNOWN:
            ids = query_ids(name)
            self.assertIn("RV", ids, name)
            self.assertIn("RG", ids, name)

    def test_signature_broken_models(self):
        self.assertEqual(len(SIG_BROKEN), 3)
        for name in SIG_BROKEN:
            text = self.models[name]
            proc = text.split("\nprocess", 1)[1]
            self.assertIn("out(c, skG); out(c, skV);", proc, name)
            self.assertNotIn("phase 1", text, name)
            # design B with change F1: the vehicle signs and both sides confirm the key
            self.assertIn("sign((tF4, idV, idG, tr), skV)", text, name)
            self.assertEqual(query_ids(name), build_models.sig_broken_queries(name), name)
            self.assertEqual(sorted(query_ids(name)), sorted(build_models.SIG_BROKEN_QUERIES), name)
        a, b, c = SIG_BROKEN
        self.assertNotIn("out(c, x);", self.models[a])
        self.assertNotIn("out(c, dk);", self.models[a])
        self.assertIn("out(c, dk);", self.models[b])
        self.assertNotIn("out(c, x);", self.models[b])
        self.assertIn("out(c, x);", self.models[c])
        self.assertNotIn("out(c, dk);", self.models[c])
        # apart from the leaked keys, the process is the one of session_b_fixed
        base = self.models["session_b_fixed"].split("(* Ground station:", 1)[1]
        got = self.models[a].split("(* Ground station:", 1)[1].replace("  out(c, skG); out(c, skV);\n", "")
        self.assertEqual(base, got)

    def test_static_known_models(self):
        self.assertEqual(len(STATIC_KNOWN), 2)
        for name in STATIC_KNOWN:
            text = self.models[name]
            proc = text.split("\nprocess", 1)[1]
            self.assertIn("out(c, skKG); out(c, skKV);", proc, name)
            self.assertNotIn("out(c, dk);", text, name)
            self.assertNotIn("out(c, dk2);", text, name)
            self.assertNotIn("phase 1", text, name)
            self.assertEqual(query_ids(name), build_models.KEMAUTH_STATIC_QUERIES, name)
        self.assertNotIn("out(c, x);", self.models[STATIC_KNOWN[0]])
        self.assertIn("out(c, x);", self.models[STATIC_KNOWN[1]])

    def test_retry_is_the_general_model(self):
        """The retry asks A2 of the same process as session_kemauth_a2; only tool settings are added."""
        name = RETRY[0]
        text, base = self.models[name], self.models["session_kemauth_a2"]
        self.assertEqual(query_ids(name), ["A2"])
        self.assertEqual(text.split("(* Ground station:", 1)[1], base.split("(* Ground station:", 1)[1])
        for line in build_models.KEMAUTH_A2_RETRY[2].strip().splitlines():
            self.assertTrue(line.startswith("set "), line)
            self.assertIn(line, text)
        self.assertNotIn("kemssk", text)


class TestRound7Results(unittest.TestCase):
    def setUp(self):
        self.rows = load_rows()
        self.got = {(r["model"], r["property_id"]): r for r in self.rows}

    def test_rows_before_round7_unchanged(self):
        """Gate: every column of every row written before round 7 is unchanged."""
        sel = [r for r in self.rows if not is_round7(r)]
        self.assertEqual(len(sel), BEFORE_ROWS)
        key = "\n".join(sorted("|".join(r[c] for c in run_all.FIELDS) for r in sel))
        self.assertEqual(hashlib.sha256(key.encode()).hexdigest(), BEFORE_SHA256)

    def test_every_new_query_has_a_row(self):
        names = SESSION_B + WITH_AGREEMENT + SIG_BROKEN + STATIC_KNOWN + RETRY
        for name in names:
            _, _, queries = run_all.parse_model(os.path.join(HERE, "models", name + ".pv"))
            for qid, _, qtext in queries:
                self.assertTrue((name, qid) in self.got, (name, qid))
                self.assertEqual(self.got[(name, qid)]["query"], qtext)
                self.assertEqual(self.got[(name, qid)]["label"], "modelled")

    def test_reachability_gives_counterexample(self):
        """Gate: in every model that asks them, R0, RV and RG are reachable (counterexample)."""
        for (m, q), r in self.got.items():
            if q in ("RV", "RG") or (q == "R0" and m.startswith("session_b_")):
                self.assertEqual(r["result"], "counterexample", (m, q))


class TestRound7Document(unittest.TestCase):
    def test_sections(self):
        rows = load_rows()
        make_doc.check_prose(rows)
        text = make_doc.build(rows)
        self.assertIn("### 7.1 Reachability checks of the session models", text)
        self.assertIn("### 7.2 Signature component broken", text)
        for name in SIG_BROKEN + STATIC_KNOWN + RETRY:
            self.assertIn(f"| {name} |", text)


if __name__ == "__main__":
    unittest.main()
