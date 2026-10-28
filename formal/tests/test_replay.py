"""Tests of the replay rule models (python3 -m unittest discover -s formal -t .).

Author: Huda Mueen.

These tests check the structure of the rendered replay rule models, the result rows that the
runner wrote for them, and the section of docs/FORMAL_VERIFICATION.md that the generator writes
from those rows. They also check that the results of the models of earlier rounds are unchanged.
"""
import csv
import hashlib
import os
import unittest

from formal import build_models, make_doc, run_all

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPLAY = [m[0] for m in build_models.REPLAY_MODELS]
WITH_RESTRICTION = {"session_replay_cache", "session_replay_cache_fresh_counters", "session_replay_window"}
FULL_HANDSHAKE = {m[0] for m in build_models.REPLAY_MODELS if m[7]}

# Fingerprint of (model, property id, result, weaker form) of every row that is not a replay rule
# model, taken from formal/results/proverif_results.csv before the replay models were added.
EARLIER_ROWS = 57
EARLIER_SHA256 = "d4a0b7d6a32bd144d66fda082096e55327eb6a46e04f8e616acbb44a4d7e07b7"


def load_rows():
    with open(run_all.CSV_PATH) as f:
        return list(csv.DictReader(f))


class TestReplayModels(unittest.TestCase):
    def setUp(self):
        self.models = build_models.all_models()

    def test_all_replay_models_rendered(self):
        self.assertEqual(len(REPLAY), 7)
        for name in REPLAY:
            self.assertIn(name, self.models)
            self.assertTrue(os.path.exists(os.path.join(HERE, "models", name + ".pv")), name)

    def test_restriction_only_where_stated(self):
        for name in REPLAY:
            has = "\nrestriction " in self.models[name]
            self.assertEqual(has, name in WITH_RESTRICTION, name)

    def test_control_does_not_check(self):
        text = self.models["session_replay_cache_broken_no_check"]
        vblock = text.split("let VCmds", 1)[1].split("let GS(", 1)[0]
        self.assertNotIn("Mark", vblock)
        self.assertNotIn("get seen", vblock)
        self.assertIn("event Acc(sid, t, m)", vblock)

    def test_table_models_use_tables(self):
        for name in ("session_replay_cache_table_concurrent", "session_replay_cache_table_sequential"):
            text = self.models[name]
            self.assertIn("get seen(=sid, =t)", text, name)
            self.assertIn("insert seen(sid, t)", text, name)
        self.assertIn("!( in(c, (=tCmd", self.models["session_replay_cache_table_concurrent"])
        self.assertNotIn("!( in(c, (=tCmd", self.models["session_replay_cache_table_sequential"])

    def test_window_test_and_bound(self):
        for name in ("session_replay_window", "session_replay_window_no_restriction"):
            text = self.models[name]
            self.assertIn(f"t + {build_models.WINDOW_W} > hi", text)
            # one reading process per message the vehicle reads under one key
            for i in range(1, build_models.SEQ_READS_PER_KEY + 1):
                self.assertIn(f"let VWin{i}(", text)
            self.assertNotIn(f"let VWin{build_models.SEQ_READS_PER_KEY + 1}(", text)
        # the two window models differ only in the restriction
        a = self.models["session_replay_window"].split("let GSCmds", 1)[1]
        b = self.models["session_replay_window_no_restriction"].split("let GSCmds", 1)[1]
        self.assertEqual(a, b)

    def test_full_and_command_layer(self):
        self.assertEqual(FULL_HANDSHAKE, {"session_replay_cache", "session_replay_cache_fresh_counters",
                                          "session_replay_cache_broken_no_check",
                                          "session_replay_cache_table_concurrent"})
        for name in REPLAY:
            text = self.models[name]
            self.assertEqual("sign((tF3, idG, idV, tr), skG)" in text, name in FULL_HANDSHAKE, name)
            self.assertEqual("command layer only" in text, name not in FULL_HANDSHAKE, name)

    def test_several_commands_per_key(self):
        self.assertGreaterEqual(build_models.CMDS_PER_KEY, 2)
        text = self.models["session_replay_cache"]
        for i in range(1, build_models.CMDS_PER_KEY + 1):
            self.assertIn(f"event Send(sid, {i}, m{i})", text)
        self.assertIn("!(new t: ctr; new m: bitstring; event Send(sid, t, m)",
                      self.models["session_replay_cache_fresh_counters"])

    def test_headers_state_bounds(self):
        for name in REPLAY:
            design, setting, queries = run_all.parse_model(os.path.join(HERE, "models", name + ".pv"))
            self.assertIn("unbounded sessions", design, name)
            self.assertIn("C1", [q[0] for q in queries], name)


class TestReplayResults(unittest.TestCase):
    def setUp(self):
        self.rows = load_rows()
        self.got = {(r["model"], r["property_id"]): r for r in self.rows}

    def test_every_replay_query_has_a_row(self):
        for name in REPLAY:
            _, _, queries = run_all.parse_model(os.path.join(HERE, "models", name + ".pv"))
            for qid, _, qtext in queries:
                self.assertIn((name, qid), self.got)
                r = self.got[(name, qid)]
                self.assertEqual(r["label"], "modelled")
                self.assertEqual(r["query"], qtext)
                self.assertEqual(list(r.keys()), run_all.FIELDS)

    def test_control_gives_a_counterexample(self):
        """Gate: the control without the check fails C1, and the cache rule removes the failure."""
        self.assertEqual(self.got[("session_replay_cache_broken_no_check", "C1")]["result"], "counterexample")
        self.assertEqual(self.got[("session_replay_cache", "C1")]["result"], "proved")

    def test_window_accepts_out_of_order(self):
        """The window model is not the strict rule: a late command is reachable (R1 counterexample)."""
        self.assertEqual(self.got[("session_replay_window", "R1")]["result"], "counterexample")

    def test_secrecy_sanity(self):
        for name in REPLAY:
            for q in ("S0", "S1", "S2", "S3", "S4"):
                if (name, q) in self.got:
                    self.assertEqual(self.got[(name, q)]["result"], "proved", (name, q))

    def test_earlier_results_unchanged(self):
        rows = [r for r in self.rows if not r["model"].startswith(("session_replay", "session_kemauth"))]
        self.assertEqual(len(rows), EARLIER_ROWS)
        key = "\n".join(sorted(f"{r['model']},{r['property_id']},{r['result']},{r['weaker_form']}" for r in rows))
        self.assertEqual(hashlib.sha256(key.encode()).hexdigest(), EARLIER_SHA256)


class TestReplayDocument(unittest.TestCase):
    def test_section_written_from_results(self):
        rows = load_rows()
        make_doc.check_prose(rows)
        text = make_doc.build(rows)
        self.assertIn("## 9. Replay rules that accept commands out of order", text)
        self.assertIn("### 9.5 What these proofs do not say about a real replay window", text)
        for name in REPLAY:
            self.assertIn(f"| {name} |", text)
        self.assertIn(f"W = {build_models.WINDOW_W}", text)
        self.assertNotIn("not run", text.split("## 9.", 1)[1])

    def test_bounds_table_reads_constants(self):
        bounds = {b[0]: b for b in make_doc.replay_bounds()}
        self.assertEqual(set(bounds), set(REPLAY))
        self.assertEqual(bounds["session_replay_window"][5], str(build_models.SEQ_READS_PER_KEY))
        self.assertEqual(bounds["session_replay_window"][4], str(build_models.ABSTRACT_CMDS_PER_KEY))
        self.assertEqual(bounds["session_replay_cache"][4], str(build_models.CMDS_PER_KEY))
        self.assertEqual(bounds["session_replay_cache_fresh_counters"][4], "unbounded")

    def test_document_on_disk_is_current(self):
        rows = load_rows()
        with open(make_doc.DOC) as f:
            self.assertEqual(f.read(), make_doc.build(rows))


if __name__ == "__main__":
    unittest.main()
