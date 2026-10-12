"""Tests for the link simulator. Author: Huda Mueen.

Run from the repository root:  python -m unittest discover -s linksim/tests -t .
All expected values below are computed by hand in the comments.
Estimated from published sizes, not measured.
"""
import contextlib
import io
import os
import unittest

from linksim import cli, model, sim

P = model.load_params()
LINKS = model.build_links(P)


class TestParams(unittest.TestCase):
    def test_tags_and_sources(self):
        rows = model.load_param_rows()
        self.assertGreater(len(rows), 30)
        for r in rows:
            self.assertIn(r["tag"], ("cited", "assumption"))
            self.assertTrue(r["source"].strip(), r["name"])
            if r["tag"] == "assumption":
                self.assertIn("ASSUMPTION", r["source"], r["name"])
            else:
                self.assertTrue(
                    "data/" in r["source"], r["name"])

    def test_no_crypto_imports(self):
        here = os.path.dirname(model.__file__)
        banned = ("hashlib", "hmac", "secrets", "cryptography", "Crypto",
                  "nacl", "oqs")
        for fn in os.listdir(here):
            if fn.endswith(".py"):
                with open(os.path.join(here, fn)) as fh:
                    src = fh.read()
                for b in banned:
                    self.assertNotIn("import " + b, src, fn)


class TestArithmetic(unittest.TestCase):
    def test_fragment_counts(self):
        # 2420 / 239 = 10.12 -> 11 ; 1216 / 81 = 15.01 -> 16 ;
        # 4852 / 81 = 59.9 -> 60 ; 1216 / 51 = 23.8 -> 24 ; 1216 / 23 = 52.9 -> 53
        self.assertEqual(model.frames_for_bytes(2420, 239), 11)
        self.assertEqual(model.frames_for_bytes(1216, 81), 16)
        self.assertEqual(model.frames_for_bytes(4852, 81), 60)
        self.assertEqual(model.frames_for_bytes(1216, 51), 24)
        self.assertEqual(model.frames_for_bytes(1216, 23), 53)
        self.assertEqual(model.frames_for_bytes(0, 23), 0)
        self.assertEqual(model.frames_for_bytes(239, 239), 1)
        self.assertEqual(model.frames_for_bytes(240, 239), 2)

    def test_handshake_flights(self):
        # F1 = 32 + 1184 = 1216 ; F2 = 32 + 1088 + 2420 + 1312 = 4852 ;
        # provisioned F2 = 4852 - 1312 = 3540 ; F3 = 16 (assumption)
        fl = model.handshake_flights(P, "hybrid")
        self.assertEqual([f[2] for f in fl], [1216, 4852, 16])
        fp = model.handshake_flights(P, "hybrid_prov")
        self.assertEqual([f[2] for f in fp], [1216, 3540, 16])
        # classical: F2 = 32 + 64 + 32 = 128
        self.assertEqual(model.handshake_flights(P, "classical")[1][2], 128)

    def test_mavlink_wire_sizes(self):
        # overhead = 10 + 2 + 12 = 24 B. 2420 B = 10 * 239 + 30.
        # wire = 10 * 263 + 54 = 2684 B ; air = 8 * 2684 / 57600 s
        sik = LINKS["sik"]
        self.assertEqual(sik.rate_bps, 57600.0)  # 64000 * 0.9
        sizes = model.fragment_wire_sizes(sik, 2420)
        self.assertEqual(sum(sizes), 2684)
        self.assertAlmostEqual(model.transfer_air_s(sik, 2420),
                               8 * 2684 / 57600, places=9)
        signed = model.build_links(P, signed=True)["sik"]
        self.assertEqual(signed.overhead, 37)  # 24 + 13

    def test_ieee802154_and_ble_wire(self):
        # 802.15.4: 81 data in a 127 B frame -> overhead 46 ; BLE 23 in 27 -> 4
        self.assertEqual(LINKS["ieee802154"].overhead, 46)
        self.assertEqual(LINKS["ble"].overhead, 4)
        # 81 B at 250000 bit/s: 8 * 127 / 250000 = 0.004064 s
        self.assertAlmostEqual(LINKS["ieee802154"].air_s(127), 0.004064, 9)

    def test_lorawan_airtime_and_duty(self):
        lw = LINKS["lorawan"]
        # 51 B at 250 bit/s = 408 / 250 = 1.632 s ; off = 1.632 * 99 = 161.568
        self.assertAlmostEqual(lw.air_s(51), 1.632, 9)
        self.assertAlmostEqual(lw.off_s(1.632), 161.568, 9)
        # one fragment: wall = air (the trailing off time does not delay)
        self.assertAlmostEqual(model.blast_wall_s(lw, 51), 1.632, 9)
        # two full fragments: 1.632 + 161.568 + 1.632 = 164.832 s
        self.assertAlmostEqual(model.blast_wall_s(lw, 102), 164.832, 9)
        # 2420 B signature = 48 fragments, 2420 * 8 / 250 = 77.44 s air,
        # matches S3 section 8.3 (77.4 s)
        self.assertEqual(model.frames_for_bytes(2420, 51), 48)
        self.assertAlmostEqual(model.transfer_air_s(lw, 2420), 77.44, 9)

    def test_radio_enforces_duty_cycle(self):
        st = sim.Stats()
        radio = sim.Radio(LINKS["lorawan"], st)
        s1, e1 = radio.send("A", 0.0, 51)
        s2, e2 = radio.send("A", e1, 51)
        # second start >= first end + 161.568
        self.assertAlmostEqual(s2, 1.632 + 161.568, 9)
        self.assertAlmostEqual(st.duty_wait_s, 161.568, 9)
        # the other side has its own budget
        s3, _ = radio.send("B", e1, 51)
        self.assertAlmostEqual(s3, e1, 9)

    def test_tag_latency(self):
        sik = LINKS["sik"]
        # 13 B: 104 / 57600 = 1.80556 ms ; 16 B: 128 / 57600 = 2.22222 ms
        self.assertAlmostEqual(
            model.tag_added_latency_s(sik, P, 13), 104 / 57600, 12)
        self.assertAlmostEqual(
            model.tag_added_latency_s(sik, P, 16), 128 / 57600, 12)
        # LoRaWAN: 13 B -> 104 / 250 = 0.416 s ; occupancy = 0.416 / 0.01
        lw = LINKS["lorawan"]
        self.assertAlmostEqual(model.tag_added_latency_s(lw, P, 13), 0.416, 9)
        self.assertAlmostEqual(
            model.tag_added_occupancy_s(lw, P, 13), 41.6, 9)


class TestSimulation(unittest.TestCase):
    def test_stop_and_wait_closed_form(self):
        # 802.15.4, 81 B: data air 0.004064 ; ack wire 4 + 46 = 50 B ->
        # 400 / 250000 = 0.0016 ; turnaround 0.05 ; wall = 0.055664
        r = sim.run_firmware("ieee802154", 81, "sw", 0.0, 1, P)
        self.assertAlmostEqual(r.wall_s, 0.055664, 9)
        self.assertEqual(r.retransmissions, 0)
        self.assertTrue(r.completed)

    def test_selective_repeat_closed_form(self):
        # 3 fragments of 81 B: 3 * 0.004064 = 0.012192 ; block ack wire
        # 4 + 2 (bitmap for 16) + 46 = 52 B -> 416 / 250000 = 0.001664 ;
        # wall = 0.012192 + 0.05 + 0.001664 = 0.063856
        r = sim.run_firmware("ieee802154", 243, "sr", 0.0, 1, P)
        self.assertAlmostEqual(r.wall_s, 0.063856, 9)

    def test_sik_one_mb_no_loss(self):
        # 1e6 / 239 = 4184.2 -> 4185 fragments ; wire = 1e6 + 4185 * 24
        # = 1100440 B ; data air = 8 * 1100440 / 57600 = 152.8389 s
        r = sim.run_firmware("sik", 1000000, "sr", 0.0, 1, P)
        self.assertEqual(r.unique_frames, 4185)
        self.assertAlmostEqual(r.data_air_s, 8 * 1100440 / 57600, 6)
        self.assertGreater(r.wall_s, r.data_air_s)

    def test_handshake_fragment_counts(self):
        # 802.15.4: 16 + 60 + 1 (confirmation) = 77
        r = sim.run_handshake("ieee802154", "hybrid", "sr", 0.0, 1, P)
        self.assertEqual(r.unique_frames, 77)
        # public key provisioned: 16 + 44 + 1 = 61  (3540 / 81 = 43.7 -> 44)
        r2 = sim.run_handshake("ieee802154", "hybrid_prov", "sr", 0.0, 1, P)
        self.assertEqual(r2.unique_frames, 61)

    def test_determinism(self):
        a = sim.run_firmware("sik", 100000, "sr", 0.1, 7, P)
        b = sim.run_firmware("sik", 100000, "sr", 0.1, 7, P)
        self.assertEqual((a.wall_s, a.data_frames_sent, a.ack_frames_sent),
                         (b.wall_s, b.data_frames_sent, b.ack_frames_sent))
        c = sim.run_firmware("sik", 100000, "sr", 0.1, 8, P)
        self.assertNotEqual(a.wall_s, c.wall_s)
        h1 = sim.run_handshake("ble", "hybrid", "sw", 0.05, 3, P)
        h2 = sim.run_handshake("ble", "hybrid", "sw", 0.05, 3, P)
        self.assertEqual(h1.wall_s, h2.wall_s)

    def test_monotonic_in_loss(self):
        seeds = range(1, 9)
        for proto in ("sw", "sr"):
            prev = 0.0
            for loss in (0.0, 0.05, 0.2):
                m = sim.mean_wall(sim.run_firmware, seeds, link_key="sik",
                                  nbytes=50000, proto=proto, loss=loss, p=P)
                self.assertGreater(m, prev)
                prev = m

    def test_monotonic_in_size_and_rate(self):
        prev = 0.0
        for n in (1000, 10000, 100000):
            w = sim.run_firmware("sik", n, "sw", 0.0, 1, P).wall_s
            self.assertGreater(w, prev)
            prev = w
        slow = sim.run_firmware("generic10k", 50000, "sr", 0.0, 1, P).wall_s
        mid = sim.run_firmware("sik", 50000, "sr", 0.0, 1, P).wall_s
        fast = sim.run_firmware("generic1m", 50000, "sr", 0.0, 1, P).wall_s
        self.assertGreater(slow, mid)
        self.assertGreater(mid, fast)

    def test_provisioned_key_is_faster(self):
        for k in model.LINK_ORDER:
            a = sim.run_handshake(k, "hybrid", "sr", 0.0, 1, P).wall_s
            b = sim.run_handshake(k, "hybrid_prov", "sr", 0.0, 1, P).wall_s
            self.assertLess(b, a, k)

    def test_selective_repeat_not_slower_without_loss(self):
        for k in ("sik", "ieee802154", "ble", "generic1m", "generic10k"):
            sw = sim.run_firmware(k, 20000, "sw", 0.0, 1, P).wall_s
            sr = sim.run_firmware(k, 20000, "sr", 0.0, 1, P).wall_s
            self.assertLessEqual(sr, sw, k)

    def test_lorawan_dominated_by_duty_cycle(self):
        r = sim.run_handshake("lorawan", "hybrid", "sr", 0.0, 1, P)
        self.assertGreater(r.duty_wait_s, 50 * r.data_air_s)
        # sanity: wall >= data air * (1/duty - 1) * 0.9 roughly
        self.assertGreater(r.wall_s, 3600 * 4)

    def test_failure_is_reported(self):
        p = dict(P)
        p["max_retries"] = 1.0
        r = sim.run_firmware("sik", 100000, "sw", 0.9, 1, p)
        self.assertFalse(r.completed)


class TestCli(unittest.TestCase):
    def run_cli(self, args):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cli.main(args)
        return buf.getvalue()

    def test_footer_on_all_scenarios(self):
        for sc in cli.SCENARIOS:
            out = self.run_cli(["--scenario", sc, "--link", "sik",
                                "--fw-bytes", "5000"])
            self.assertIn("estimated from published sizes, not measured", out)


if __name__ == "__main__":
    unittest.main()
