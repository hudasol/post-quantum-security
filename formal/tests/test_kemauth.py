"""Tests of the sanity queries and of the KEM authenticated session models (python3 -m unittest discover -s formal -t .).

Author: Huda Mueen.

These tests check the structure of the rendered models of design K, the reachability query R0 and the handshake
agreement queries added to the replay rule models, the merge of a rerun into the results file, the summary log of a
model with restrictions, and that the rows written before these additions are unchanged.
"""
import csv
import hashlib
import os
import unittest

from formal import build_models, make_doc, run_all
from formal.tests.test_round7 import is_round7

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPLAY = [m[0] for m in build_models.REPLAY_MODELS]
FULL_HANDSHAKE = [m[0] for m in build_models.REPLAY_MODELS if m[7]]
KEMAUTH = [m[0] for m in build_models.KEMAUTH_MODELS] + build_models.KEMAUTH_REPLAY_MODELS

# Fingerprint of (model, property id, query, result, weaker form, run time, version, label) of every row of
# formal/results/proverif_results.csv before the sanity queries and design K were added (86 rows). The design and
# attacker setting columns are left out: the header of session_timestamp_rule was corrected (a documented fix that
# changes no result).
EARLIER_ROWS = 86
EARLIER_SHA256 = "c56700415f1e2a3043effdaad6f0efe84498f4a531371a0c8df9db1023bdf403"
EARLIER_COLS = ["model", "property_id", "query", "result", "weaker_form", "run_time_s_host_measured",
                "proverif_version", "label"]


def load_rows():
    with open(run_all.CSV_PATH) as f:
        return list(csv.DictReader(f))


def query_ids(name):
    return [q[0] for q in run_all.parse_model(os.path.join(HERE, "models", name + ".pv"))[2]]


class TestSanityQueries(unittest.TestCase):
    def setUp(self):
        self.models = build_models.all_models()

    def test_every_replay_model_asks_reachability(self):
        for name in REPLAY:
            self.assertIn("R0", query_ids(name), name)
            self.assertIn("event(Acc(s, t, m)) ==> false.", self.models[name], name)

    def test_full_handshake_replay_models_ask_agreement(self):
        self.assertEqual(len(FULL_HANDSHAKE), 4)
        for name in FULL_HANDSHAKE:
            ids = query_ids(name)
            self.assertIn("A1", ids, name)
            self.assertIn("A2", ids, name)
            self.assertIn(build_models.SESSION_QUERIES["A1"][1], self.models[name], name)

    def test_new_queries_come_last(self):
        """The queries of the earlier run keep their position, so their results map to the same rows."""
        for name in REPLAY:
            ids = query_ids(name)
            extra = [q for q in ids if q in ("R0", "A1", "A2", "RV", "RG")]
            self.assertEqual(ids[-len(extra):], extra, name)

    def test_timestamp_header_fixed(self):
        text = self.models["session_timestamp_rule"]
        self.assertNotIn("The other models use", text)
        self.assertIn("section 9", text)

    def test_summary_log_keeps_restriction_summary(self):
        out = ("RESULT not event(A(x)) is false.\n"
               "-- Query not event(A(x)) in process 1.\n"
               "Query(ies):\n"
               " - Query not event(A(x)) is false.\n"
               "Verification summary:\n"
               "Query not attacker(k) is true.\n")
        log = run_all.summary_log(out)
        self.assertIn(" - Query not event(A(x)) is false.", log)
        self.assertIn("Query(ies):", log)
        self.assertIn("Query not attacker(k) is true.", log)
        self.assertNotIn("-- Query", log)

    def test_restriction_logs_have_summary(self):
        for name in ("session_replay_cache", "session_replay_cache_fresh_counters", "session_replay_window",
                     "session_kemauth_replay_cache"):
            with open(os.path.join(run_all.LOGS, name + ".txt")) as f:
                self.assertIn(" - Query ", f.read(), name)


class TestMerge(unittest.TestCase):
    def row(self, model, pid, result, t="1.0", design="d"):
        return dict(model=model, design=design, attacker_setting="a", property_id=pid, property="p", query="q",
                    result=result, weaker_form="", run_time_s_host_measured=t, proverif_version="2.05",
                    label="modelled", note="n")

    def test_keeps_earlier_rows_and_adds_new(self):
        old = [self.row("m", "C1", "proved", "5.0", "old design")]
        new = [self.row("m", "C1", "proved", "9.0", "new design"), self.row("m", "R0", "counterexample", "9.0")]
        rows, changed = run_all.merge_rows(old, new)
        self.assertEqual(changed, [])
        got = {r["property_id"]: r for r in rows}
        self.assertEqual(got["C1"]["run_time_s_host_measured"], "5.0")
        self.assertEqual(got["C1"]["design"], "new design")
        self.assertEqual(got["R0"]["result"], "counterexample")

    def test_reports_a_changed_result(self):
        old = [self.row("m", "C1", "proved")]
        new = [self.row("m", "C1", "counterexample")]
        rows, changed = run_all.merge_rows(old, new)
        self.assertEqual(len(changed), 1)
        self.assertEqual(rows[0]["result"], "proved")


class TestKemauthModels(unittest.TestCase):
    def setUp(self):
        self.models = build_models.all_models()

    def test_rendered(self):
        self.assertEqual(len(KEMAUTH), 9)
        for name in KEMAUTH:
            self.assertIn(name, self.models)
            self.assertTrue(os.path.exists(os.path.join(HERE, "models", name + ".pv")), name)

    def test_no_signature_in_design_k(self):
        for name in KEMAUTH:
            body = self.models[name].split("let GS(", 1)[1]
            self.assertNotIn("sign(", body, name)
            self.assertNotIn("verify(", body, name)

    def test_messages_of_design_k(self):
        for name in KEMAUTH:
            if name == "session_kemauth_a2_typed_static":
                continue
            text = self.models[name]
            self.assertIn("out(c, (tF1, gx, ek, ct1));", text)
            self.assertIn("let ct1 = kct(pkKV, r1) in", text)
            self.assertIn("out(c, (tF2, gy, ct2, ct3, mac((tConfV, sid), k)));", text)
            self.assertIn("let ct3 = kct(pkKG, r3) in", text)
            self.assertIn("out(c, (tF3, mac((tConfG, sid), k)));", text)
            # key from the Diffie Hellman secret, the three KEM secrets and the transcript
            self.assertIn("kdf(exp(gy, x), (kss(pkKV, r1), decaps(dk, ct2), decaps(skKG, ct3)), sid)", text)
            self.assertIn("kdf(exp(gx, y), (decaps(skKV, ct1), kss(ek, r2), kss(pkKG, r3)), sid)", text)
            self.assertIn("let tr = (idG, idV, gx, ek, ct1, gy, ct2, ct3) in", text)
            # implicit rejection
            self.assertIn("otherwise forall sk: kemsk, ct: bitstring; decaps(sk, ct) = krej(sk, ct).", text)

    def test_typed_static_variant(self):
        text = self.models["session_kemauth_a2_typed_static"]
        self.assertIn("let ct1 = kcts(pkKV, r1) in", text)
        self.assertIn("let ct3 = kcts(pkKG, r3) in", text)
        self.assertIn("kdf(exp(gx, y), (decapss(skKV, ct1), kss(ek, r2), ksss(pkKG, r3)), sid)", text)
        self.assertIn("in(c, (=tF1, gx: G, ek: kempk, ct1: bitstring));", text)
        # apart from the types of the static keys, the process is the one of session_kemauth_a2
        base = self.models["session_kemauth_a2"]
        for a, b in build_models.TYPED_STATIC_REPLACEMENTS:
            base = base.replace(a, b)
        self.assertEqual(base.split("(* Ground station:", 1)[1], text.split("(* Ground station:", 1)[1])

    def test_vehicle_names_without_arguments(self):
        for name in KEMAUTH:
            self.assertIn("new y[]: expo; new r2[]: coins; new r3[]: coins;", self.models[name], name)

    def test_ground_names_without_arguments_only_where_stated(self):
        for name in KEMAUTH:
            has = "new x2[]: expo; new dk2[]: kemsk;" in self.models[name]
            self.assertEqual(has, name in build_models.GROUND_NOARGS, name)
        self.assertEqual(build_models.GROUND_NOARGS, {"session_kemauth_kem_broken", "session_kemauth_both_broken"})

    def test_settings(self):
        m = self.models
        self.assertIn("out(c, skKG); out(c, skKV);\n", m["session_kemauth_kem_broken"].split("process", 1)[1])
        self.assertIn("out(c, dk);", m["session_kemauth_kem_broken"])
        self.assertNotIn("out(c, x);", m["session_kemauth_kem_broken"])
        self.assertIn("out(c, x);", m["session_kemauth_classical_broken"])
        self.assertNotIn("out(c, dk);", m["session_kemauth_classical_broken"])
        self.assertIn("phase 1; out(c, skKG); out(c, skKV)", m["session_kemauth_fs_longterm"])
        self.assertNotIn("phase 1", m["session_kemauth"])
        self.assertIn("\nrestriction ", m["session_kemauth_replay_cache"])
        self.assertNotIn("\nrestriction ", m["session_kemauth"])

    def test_queries(self):
        main = [q for q in build_models.ALL_KEMAUTH if q != "A2"]
        self.assertEqual(query_ids("session_kemauth"), main + ["RV", "RG"])
        self.assertEqual(query_ids("session_kemauth_replay_cache"), main + ["RV", "RG"])
        self.assertEqual(query_ids("session_kemauth_a2"), ["A2"])
        self.assertEqual(query_ids("session_kemauth_a2_typed_static"), ["A2", "R0", "RV", "RG"])
        for name, _, _, _, _, qs, _ in build_models.KEMAUTH_MODELS[3:]:
            self.assertEqual(query_ids(name), build_models.SECRECY, name)


class TestResultsRound6b(unittest.TestCase):
    def setUp(self):
        self.rows = load_rows()
        self.got = {(r["model"], r["property_id"]): r for r in self.rows}

    def test_earlier_rows_unchanged(self):
        """Gate: the rows written before this work keep every result and run time."""
        with open(os.path.join(HERE, "results", "proverif_results.csv")) as f:
            rows = list(csv.DictReader(f))
        earlier_keys = set()
        for name in build_models.all_models():
            if name in KEMAUTH:
                continue
            for qid in query_ids(name):
                if not (name in REPLAY and qid in ("R0", "A1", "A2")):
                    earlier_keys.add((name, qid))
        sel = [r for r in rows if (r["model"], r["property_id"]) in earlier_keys and not is_round7(r)]
        self.assertEqual(len(sel), EARLIER_ROWS)
        key = "\n".join(sorted("|".join(r[c] for c in EARLIER_COLS) for r in sel))
        self.assertEqual(hashlib.sha256(key.encode()).hexdigest(), EARLIER_SHA256)

    def test_every_new_query_has_a_row(self):
        for name in KEMAUTH + REPLAY:
            _, _, queries = run_all.parse_model(os.path.join(HERE, "models", name + ".pv"))
            for qid, _, qtext in queries:
                self.assertIn((name, qid), self.got)
                r = self.got[(name, qid)]
                self.assertEqual(r["label"], "modelled")
                self.assertEqual(r["query"], qtext)

    def test_reachability_gives_counterexample(self):
        """Gate: in every replay rule model and in design K the vehicle accepts a command (R0 counterexample)."""
        for name in REPLAY + ["session_kemauth", "session_kemauth_replay_cache", "session_kemauth_a2_typed_static"]:
            self.assertEqual(self.got[(name, "R0")]["result"], "counterexample", name)

    def test_design_k_control(self):
        """Gate: the control with both components broken loses secrecy, so design K is not secret by construction."""
        self.assertEqual(self.got[("session_kemauth_both_broken", "S1")]["result"], "counterexample")


class TestDocument(unittest.TestCase):
    def test_sections(self):
        rows = load_rows()
        make_doc.check_prose(rows)
        text = make_doc.build(rows)
        self.assertIn("## 10. KEM authenticated hybrid session (design K)", text)
        self.assertIn("## 11. Bounds of every model", text)
        for name in KEMAUTH:
            self.assertIn(f"| {name} |", text)
        self.assertNotIn("not run", text.split("## 10.", 1)[1])
        self.assertIn("The author's reading, which the manual does not state", text)


if __name__ == "__main__":
    unittest.main()
