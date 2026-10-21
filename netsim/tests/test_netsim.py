"""Tests of the network simulator check that run without ns-3.

Author: Huda Mueen. Run from the repository root:
    python3 -m unittest discover -s netsim -t .
"""
import csv
import os
import random
import unittest

from linksim import checks, model, sim
from netsim import cells, compare, make_study

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RES = os.path.join(ROOT, "netsim", "results")


class ClosedForm(unittest.TestCase):
    def test_values(self):
        self.assertAlmostEqual(checks.sr_closed_form(0.2), 1.25)
        self.assertAlmostEqual(checks.sr_closed_form(0.0), 1.0)

    def test_no_loss_is_one(self):
        v = checks.sr_transmissions_sim("ieee802154", 0.0, 5, 1, n_frames=40)
        self.assertEqual(v, [1.0] * 5)

    def test_error_free_acks_near_closed_form(self):
        v = checks.sr_transmissions_sim("ieee802154", 0.1, 400, 12345, n_frames=50)
        m, lo, hi = checks.mean_ci(v)
        self.assertLess(abs(m - checks.sr_closed_form(0.1)), 5 * (hi - lo))

    def test_wrapper_with_ack_loss_reproduces_plain_sim(self):
        """With ack_loss True the wrappers must not change linksim's run."""
        p = model.load_params()
        link = model.build_links(p)["ieee802154"]
        sizes = [link.wire_bytes(link.cap)] * 50
        for seed in (3, 4, 5):
            st = sim.Stats()
            radio = sim.Radio(link, st)
            sim.selective_repeat(radio, random.Random(seed), 0.2, "A", "B", sizes, p, 0.0)
            v = checks.sr_transmissions_sim("ieee802154", 0.2, 1, seed, p, 50, ack_loss=True)
            self.assertAlmostEqual(v[0], st.data_frames_sent / 50.0)

    def test_seed_blocks_disjoint(self):
        starts = [checks.sr_seed_block(k) for k in range(2 * len(checks.SR_LOSSES))]
        for a, b in zip(starts, starts[1:]):
            self.assertGreaterEqual(b - a, 2000)


class Cells(unittest.TestCase):
    def test_run_blocks_disjoint(self):
        seen = set()
        for c in cells.lrwpan_cells():
            for r in c["runs"]:
                self.assertNotIn(r, seen)
                seen.add(r)

    def test_csma_values_in_cited_ranges(self):
        # Ranges of netsim/SOURCES.md N1 and N2.
        for c in cells.lrwpan_cells():
            a = c["args"]
            self.assertTrue(3 <= a["maxBe"] <= 8)
            self.assertTrue(0 <= a["minBe"] <= a["maxBe"])
            self.assertTrue(0 <= a["maxBackoffs"] <= 5)
            self.assertTrue(0 <= a["retries"] <= 7)

    def test_lora_flights_from_protocol_profiles(self):
        fl = dict(cells.lora_flights())
        self.assertEqual(set(fl), {"dtls13", "edhoc_oscore", "mavlink2_pq", "dds_security"})
        for f in fl.values():
            self.assertEqual(len(f), 3)

    def test_fetch_script_pins(self):
        s = open(os.path.join(ROOT, "netsim", "fetch_build.sh"), encoding="utf-8").read()
        self.assertIn('NS3_TAG="ns-3.48"', s)
        self.assertIn("a13219eebab664729eeed2694fa1cedf89e9c8d8", s)
        self.assertIn("nice -n 10", s)


class Study(unittest.TestCase):
    def test_verdict(self):
        self.assertEqual(make_study.verdict(45.0, 44.0), "both")
        self.assertEqual(make_study.verdict(45.0, 7.0), "published")
        self.assertEqual(make_study.verdict(7.5, 7.0), "model")
        self.assertEqual(make_study.verdict(3.0, 7.0), "neither")

    def test_linksim_same_settings_baseline(self):
        rows = compare.linksim_rows()
        base = [r for r in rows if r["cell"] == "base_frame"][0]
        h2 = [r for r in rows if r["cell"] == "hops_2"][0]
        self.assertAlmostEqual(h2["time_s_linksim"], 2 * base["time_s_linksim"])

    @unittest.skipUnless(os.path.exists(os.path.join(RES, "lrwpan_runs.csv")), "no committed ns-3 results")
    def test_document_regenerates_and_labels_columns(self):
        doc = make_study.build()
        self.assertIn("simulated (network)", doc)
        self.assertIn("modelled", doc)
        with open(os.path.join(RES, "lrwpan_cells.csv"), newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                self.assertEqual(r["label"], "simulated (network)")
        with open(os.path.join(RES, "validation.csv"), newline="", encoding="utf-8") as fh:
            hdr = next(csv.reader(fh))
        self.assertIn("value_simulated_network", hdr)
        self.assertIn("value_modelled", hdr)


if __name__ == "__main__":
    unittest.main()
