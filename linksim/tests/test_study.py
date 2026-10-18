"""Tests for the second round link modules. Author: Huda Mueen.

Run from the repository root:  python -m unittest discover -s linksim/tests -t .
Expected values are computed by hand in the comments. Estimated from
published sizes, not measured.
"""
import csv
import math
import os
import tempfile
import unittest

from linksim import lowrate, model, montecarlo as mc, sim, validate

P = model.load_params()
LINKS = model.build_links(P)


class TestStats(unittest.TestCase):
    def test_seed_list(self):
        self.assertEqual(mc.seed_list(3, 10), [10, 11, 12])
        self.assertEqual(len(mc.seed_list()), 1000)
        self.assertEqual(mc.seed_list()[0], 20261016)

    def test_percentile(self):
        s = [1.0, 2.0, 3.0, 4.0, 5.0]
        self.assertEqual(mc.percentile(s, 0.5), 3.0)
        # pos = 0.05 * 4 = 0.2 -> 1 + 0.2 * (2 - 1) = 1.2
        self.assertAlmostEqual(mc.percentile(s, 0.05), 1.2)
        self.assertEqual(mc.percentile([7.0], 0.95), 7.0)
        self.assertTrue(math.isnan(mc.percentile([], 0.5)))

    def test_summarise(self):
        r = mc.summarise([1.0, 2.0, 3.0, 4.0])
        # mean 2.5; sample sd = sqrt(5/3) = 1.29099; half = 1.96 * 1.29099 / 2
        self.assertAlmostEqual(r["mean"], 2.5)
        self.assertAlmostEqual(r["sd"], math.sqrt(5.0 / 3.0))
        half = mc.Z95 * math.sqrt(5.0 / 3.0) / 2.0
        self.assertAlmostEqual(r["ci_lo"], 2.5 - half)
        self.assertAlmostEqual(r["ci_hi"], 2.5 + half)
        self.assertEqual(r["median"], 2.5)
        self.assertEqual(mc.summarise([])["n"], 0)

    def test_wilson(self):
        lo, hi = mc.wilson(1000, 1000)
        # all successes: upper bound 1, lower bound n / (n + z^2) = 0.99617
        self.assertEqual(hi, 1.0)
        self.assertAlmostEqual(lo, 1000 / (1000 + mc.Z95 ** 2), places=6)
        lo, hi = mc.wilson(50, 100)
        self.assertAlmostEqual((lo + hi) / 2, 0.5, places=9)
        self.assertTrue(lo < 0.5 < hi)


class TestLinkVariant(unittest.TestCase):
    def test_variant_does_not_touch_original(self):
        base = LINKS["sik"]
        v = mc.link_variant(base, cap=100, rate_scale=2.0, overhead=5)
        self.assertEqual((v.cap, v.overhead), (100, 5))
        self.assertAlmostEqual(v.rate_bps, 2 * base.rate_bps)
        self.assertEqual(base.cap, 239)

    def test_bad_cap(self):
        with self.assertRaises(ValueError):
            mc.link_variant(LINKS["sik"], cap=0)


class TestMonteCarlo(unittest.TestCase):
    def test_zero_loss_is_deterministic(self):
        fl = model.handshake_flights(P, "hybrid")
        r = mc.mc_cell(LINKS["sik"], fl, "sr", 0.0, P, trials=50)
        one = sim._run_flights(LINKS["sik"], fl, "sr", 0.0, mc.BASE_SEED, P)
        self.assertTrue(r["deterministic"])
        self.assertEqual(r["completed"], 50)
        self.assertAlmostEqual(r["mean"], one.wall_s)
        self.assertEqual(r["sd"], 0.0)

    def test_seeded_cells_repeat(self):
        fl = model.handshake_flights(P, "hybrid")
        a = mc.mc_cell(LINKS["ble"], fl, "sr", 0.1, P, trials=30)
        b = mc.mc_cell(LINKS["ble"], fl, "sr", 0.1, P, trials=30)
        self.assertEqual(a, b)
        self.assertGreater(a["mean"], mc.mc_cell(LINKS["ble"], fl, "sr", 0.0,
                                                 P, trials=30)["mean"])

    def test_completion_counts(self):
        q = dict(P)
        q["max_retries"] = 0
        fl = model.handshake_flights(q, "hybrid")
        r = mc.mc_cell(LINKS["ble"], fl, "sw", 0.5, q, trials=40)
        # 265 fragments, each must pass data and ack on the first try:
        # completion probability 0.25 ** 265, effectively zero.
        self.assertEqual(r["completed"], 0)
        self.assertTrue(math.isnan(r["mean"]))


class TestSweep(unittest.TestCase):
    def test_retry_axes_do_nothing_without_loss(self):
        for axis, vals in (("max_retries", (1, 20)), ("rto_factor", (1.5, 4))):
            res = mc.sweep("sik", axis, vals, P, "sr", 0.0, trials=5)
            self.assertEqual(res[0][1]["mean"], res[1][1]["mean"], axis)

    def test_rate_scale_halves_air_time(self):
        res = mc.sweep("generic10k", "rate_scale", (1.0, 2.0), P, "sr", 0.0,
                       trials=1)
        self.assertLess(res[1][1]["mean"], res[0][1]["mean"])

    def test_payload_axis_changes_fragments(self):
        res = mc.sweep("lorawan", "payload", (25, 51), P, "sr", 0.0, trials=1)
        self.assertGreater(res[0][1]["mean"], res[1][1]["mean"])

    def test_relative_change(self):
        res = [(1, {"mean": 2.0}), (2, {"mean": 3.0})]
        self.assertEqual(mc.relative_change(res, 1), [(1, 0.0), (2, 0.5)])

    def test_bad_axis(self):
        with self.assertRaises(ValueError):
            mc.sweep("sik", "colour", (1,), P)


class TestLowRate(unittest.TestCase):
    def test_fragments_by_hand(self):
        # key sent flights 1216, 4852, 16 B; DR0 payload 51 B:
        # ceil(1216/51)=24, ceil(4852/51)=96, ceil(16/51)=1 -> 121
        self.assertEqual(lowrate.handshake_fragments(P, "eu868_dr0"), 121)
        # 4 B header -> 47 B: 26 + 104 + 1 = 131
        self.assertEqual(lowrate.handshake_fragments(P, "eu868_dr0", frag_hdr=4), 131)
        # US915 DR0, 11 B: 111 + 442 + 2 = 555
        self.assertEqual(lowrate.handshake_fragments(P, "us915_dr0"), 555)
        # DR5, 222 B: 6 + 22 + 1 = 29
        self.assertEqual(lowrate.handshake_fragments(P, "eu868_dr5"), 29)

    def test_no_rate_profile(self):
        self.assertIsNone(lowrate.profile_link(P, "us915_dr0"))
        self.assertIsNone(lowrate.one_way_floor_s(P, "us915_dr0"))

    def test_header_too_big(self):
        with self.assertRaises(ValueError):
            lowrate.fragments(P, "us915_dr0", 100, frag_hdr=11)

    def test_floor_single_frame(self):
        # classical: flights 32, 128, 16 B, one frame each on DR5.
        # air = 8 * n / 5470; floor = sum of airs + 2 turnarounds of 1 s
        floor = lowrate.one_way_floor_s(P, "eu868_dr5", "classical")
        exp = 8 * (32 + 128 + 16) / 5470.0 + 2 * 1.0
        self.assertAlmostEqual(floor, exp)

    def test_mac_overhead_slows(self):
        a = lowrate.one_way_floor_s(P, "eu868_dr0", "hybrid", 0, 0)
        b = lowrate.one_way_floor_s(P, "eu868_dr0", "hybrid", 0, 13)
        self.assertGreater(b, a)

    def test_table_rows(self):
        rows = lowrate.table(P)
        # 2 rated profiles x 3 variants x 4 headers x 2 overheads + 1 x 3 x 4
        self.assertEqual(len(rows), 2 * 3 * 4 * 2 + 3 * 4)


class TestValidate(unittest.TestCase):
    def _csv(self):
        fd, path = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        cols = ["id", "parameter_set", "operation", "compiler_flags_or_notes",
                "key_or_sig_size_bytes", "size_kind", "source_url"]
        url = "https://eprint.iacr.org/2026/2343.pdf"
        rows = [
            ["a1", "G", "handshake (two node TLS 1.3, clear profile)", "reported time: 20 ms (median)", "", "", url],
            ["a2", "G", "handshake (two node TLS 1.3, UAV profile)", "reported time: 500 ms (median)", "", "", url],
            ["a3", "G", "handshake (two node TLS 1.3)", "", "1000", "handshake wire bytes server to client", url],
            ["a4", "G", "handshake (two node TLS 1.3)", "", "440", "handshake wire bytes client to server", url],
            ["b1", "H", "handshake (two node TLS 1.3, clear profile)", "reported time: 20 ms (median)", "", "", url],
        ]
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(cols)
            w.writerows(rows)
        return path

    def test_load_skips_incomplete(self):
        path = self._csv()
        try:
            t5 = validate.load_table5(path)
        finally:
            os.remove(path)
        self.assertEqual(list(t5), ["G"])
        self.assertEqual((t5["G"]["rd"], t5["G"]["wr"]), (1000, 440))

    def test_predict_by_hand(self):
        row = {"clear_ms": 20.0, "uav_ms": 500.0, "rd": 1000, "wr": 440}
        # 20 + 1000 * (2 * 0.08 + 8 * 1440 / 57600) = 20 + 160 + 200 = 380
        self.assertAlmostEqual(validate.predict_ms(row, P), 380.0)
        # TCP: one 52 B header each way -> 1544 B -> 8 * 1544 / 57600 = 214.44 ms
        self.assertAlmostEqual(validate.predict_ms(row, P, True),
                               20 + 160 + 1000 * 8 * 1544 / 57600.0)

    def test_tcp_overhead(self):
        self.assertEqual(validate.tcp_overhead_bytes(1448, 1448, 52), 52)
        self.assertEqual(validate.tcp_overhead_bytes(1449, 1448, 52), 104)
        self.assertEqual(validate.tcp_overhead_bytes(0, 1448, 52), 0)

    def test_run_errors(self):
        path = self._csv()
        try:
            out = validate.run(P, path, baseline="G")
        finally:
            os.remove(path)
        self.assertEqual(len(out), 1)
        self.assertAlmostEqual(out[0]["err_plain"], 380.0 / 500.0 - 1.0)
        self.assertEqual(out[0]["meas_diff"], 0.0)
        self.assertTrue(math.isnan(out[0]["diff_err_plain"]))


if __name__ == "__main__":
    unittest.main()


class TestValidationRound3(unittest.TestCase):
    def test_held_out_never_fits_on_test(self):
        with self.assertRaises(ValueError):
            validate.held_out(P, train=("P-256",), test=("P-256",))

    def test_held_out_constant_is_mean_training_residual(self):
        out = validate.held_out(P)
        t5 = validate.load_table5()
        train = [r for r in out if r["split"] == "train"]
        c = sum(t5[r["group"]]["uav_ms"] - validate.predict_ms(t5[r["group"]], P) for r in train) / len(train)
        for r in out:
            self.assertAlmostEqual(r["fitted_overhead_ms"], c)
        self.assertEqual({r["group"] for r in out if r["split"] == "test"}, set(validate.TEST))

    def test_crosscheck_uses_model_only(self):
        cc = validate.crosscheck_802154(P)
        # 50000 B on 81 B fragments: ceil(50000/81) = 618 fragments, each at least 127 B on air at 250 kbit/s
        self.assertGreater(cc["model_s"], 618 * 8 * 127 / 250000.0)
        self.assertAlmostEqual(cc["factor_below_low"], 30.0 / cc["model_s"])

    def test_parts_inventory(self):
        status = dict((p, s) for p, s, _ in validate.PARTS)
        self.assertEqual(status["duty cycle"], "unvalidated")
        self.assertEqual(status["loss and retransmission"], "unvalidated")
