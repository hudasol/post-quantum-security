"""Tests for the energy and CPU headroom model. Author: Huda Mueen.

Run from the repository root:  python3 -m unittest discover -s energy/tests -t .
Expected values are computed by hand in the comments. Label: estimated, not measured.
"""
import unittest

import numpy as np

from energy import mc, model

EV = model.load_evidence()
BENCH = model.load_local("retrieved_benchmarks.csv")
CMAP = model.load_local("cycle_map.csv")
PARTS = model.load_local("parts.csv")
PLATS = model.load_local("platforms.csv")
ASSUME = model.load_assumptions()


class TestArithmetic(unittest.TestCase):
    def test_energy_uj(self):
        # 1,000,000 cycles at 100 uA/MHz and 3 V: 1e6 * 100 * 3 * 1e-6 = 300 uJ
        self.assertAlmostEqual(model.energy_uj(1e6, 100, 3.0), 300.0)

    def test_energy_matches_time_power(self):
        # 1.2e6 cycles at 120 MHz = 10 ms; 110 uA/MHz * 120 MHz = 13.2 mA; 13.2 mA * 3.3 V * 10 ms = 435.6 uJ
        self.assertAlmostEqual(model.energy_uj(1.2e6, 110, 3.3), 435.6, places=6)

    def test_cycles_from_time(self):
        # 40 ms at 64 MHz = 2,560,000 cycles
        self.assertAlmostEqual(model.cycles_from_time(40, 64), 2.56e6)

    def test_cpb(self):
        # 180 MHz / 2.36 MB/s = 76.27 cycles per byte
        self.assertAlmostEqual(model.throughput_to_cpb(2.36, 180), 76.271, places=2)

    def test_hmac_bytes(self):
        # 64 B message: inner ceil((64+64+9)/64) = 3 blocks, outer 2 blocks, total 5 * 64 = 320 B
        self.assertEqual(model.hmac_sha256_bytes(64), 320)
        # 0 B message: inner ceil(73/64) = 2 blocks, total 4 blocks = 256 B
        self.assertEqual(model.hmac_sha256_bytes(0), 256)

    def test_max_rate(self):
        # 20 percent of 100 MHz over 1e6 cycles = 20 per second
        self.assertAlmostEqual(model.max_rate_per_s(1e6, 100, 0.2), 20.0)

    def test_cpu_share(self):
        self.assertAlmostEqual(model.cpu_share(50e6, 100), 0.5)

    def test_battery(self):
        # 1800 mAh at 11.1 V = 19.98 Wh (matches the cited TurtleBot3 figure)
        self.assertAlmostEqual(model.battery_wh(1800, 11.1), 19.98)
        self.assertAlmostEqual(model.platform_power_w(19.98, 2.5), 7.992)

    def test_parse_time(self):
        self.assertEqual(model.parse_time_ms("reported time: 40 ms (statistic not stated)"), 40.0)
        self.assertEqual(model.parse_time_ms("boot time 82.791 ms for ~100 KB"), 82.791)
        self.assertIsNone(model.parse_time_ms("no time here"))

    def test_bootstrap(self):
        lo, hi = model.bootstrap_median_ci([1.0, 2.0, 3.0, 4.0, 5.0])
        self.assertLessEqual(lo, 3.0)
        self.assertGreaterEqual(hi, 3.0)
        self.assertEqual(model.bootstrap_median_ci([7.0]), (7.0, 7.0))


class TestLookups(unittest.TestCase):
    def test_published_row(self):
        r = model.cycles_for("mldsa44_verify", "Cortex-M4", EV, BENCH, CMAP)
        self.assertEqual(r["cycles"], 1421623.0)  # S2-0033
        self.assertEqual(r["cycle_label"], "published")

    def test_proxy(self):
        r = model.cycles_for("lms_verify", "Cortex-M7", EV, BENCH, CMAP)
        self.assertTrue(r["proxy"])
        self.assertIn("proxy", r["cycle_label"])

    def test_derived_time(self):
        r = model.cycles_for("ed25519_verify", "RISC-V", EV, BENCH, CMAP)
        self.assertAlmostEqual(r["cycles"], 41 * 72 * 1000)  # S10D-073: 41 ms at 72 MHz

    def test_classical_baseline_rows(self):
        self.assertEqual(model.cycles_for("ed25519_verify", "Cortex-M4", EV, BENCH, CMAP)["cycles"], 722000.0)  # S12A-331
        self.assertEqual(model.cycles_for("ed25519_sign", "Cortex-M4", EV, BENCH, CMAP)["cycles"], 239000.0)  # S12A-330
        self.assertEqual(model.cycles_for("x25519_shared", "Cortex-M4", EV, BENCH, CMAP)["cycles"], 548873.0)  # S12A-332
        for r in CMAP:
            for i in [x for x in r.get("alternatives", "").split("|") if x]:
                self.assertIn(i, EV, i)

    def test_every_cycle_map_ref_exists(self):
        for r in CMAP:
            if r["method"].startswith("evidence") or r["method"] == "shared":
                self.assertIn(model.cmap_evidence_id(r), EV, r["ref"])

    def test_supply_options(self):
        l4 = next(p for p in PARTS if p["part"] == "STM32L4R5")
        modes = model.part_supply_options(l4)
        self.assertEqual(len(modes), 2)
        esp = next(p for p in PARTS if p["part"] == "ESP32-C3")
        ua = model.part_supply_options(esp)[0][1]
        self.assertAlmostEqual(ua, 23000 / 160)  # 23 mA at 160 MHz = 143.75 uA/MHz

    def test_parts_count(self):
        with_values = [p for p in PARTS if model.part_supply_options(p)]
        self.assertEqual(len(with_values), 5)


class TestWorkload(unittest.TestCase):
    def setUp(self):
        self.c = {k: 1.0 for k in ("x25519_shared", "ed25519_verify", "ed25519_sign", "mlkem768_keygen",
                                    "mlkem768_decaps", "mlkem768_encaps", "mldsa44_verify", "mldsa44_sign", "lms_verify",
                                    "hmac_sha256_msg")}
        self.c["sha256_cpb_sw"] = 0.0
        self.w = {"handshakes_per_h": 1, "rekeys_per_h": 0, "commands_per_s": 1, "boots_per_h": 0, "image_mb": 1}

    def test_pq(self):
        # handshake (design change F1): 2 X25519 + encaps + verify + sign = 5; 3600 commands * 1 = 3605 cycles
        self.assertEqual(model.workload_cycles_per_h(self.c, self.w, "pq_sig"), 3605)

    def test_classical(self):
        # handshake: 2 + 1 + 1 = 4; commands 3600
        self.assertEqual(model.workload_cycles_per_h(self.c, self.w, "classical"), 3604)

    def test_boot(self):
        w = dict(self.w, commands_per_s=0, handshakes_per_h=0, boots_per_h=2)
        c = dict(self.c, sha256_cpb_sw=2.0)
        # 2 boots * (1e6 B * 2 cycles + 1 verify) = 4,000,002
        self.assertEqual(model.workload_cycles_per_h(c, w, "pq_sig"), 4000002)


class TestMonteCarlo(unittest.TestCase):
    def test_deterministic(self):
        a = mc.triangular_samples(ASSUME, 100)
        b = mc.triangular_samples(ASSUME, 100)
        self.assertTrue(np.array_equal(a, b))

    def test_evaluate_positive(self):
        cyc = {op: model.cycles_for(op, "Cortex-M4", EV, BENCH, CMAP)["cycles"] for op in
               ("x25519_shared", "ed25519_verify", "ed25519_sign", "mlkem768_keygen", "mlkem768_decaps",
                "mlkem768_encaps", "mldsa44_verify", "mldsa44_sign", "lms_verify", "hmac_sha256_msg")}
        cyc["sha256_cpb_sw"] = 76.0
        b, c = mc.evaluate(mc.nominal_row(ASSUME), mc.INPUTS, cyc, PLATS[0], "pq_sig")
        self.assertGreater(b[0], 0)
        self.assertGreater(c[0], 0)
        bm, cm = mc.evaluate(mc.nominal_row(ASSUME), mc.INPUTS, cyc, PLATS[0], "mac")
        self.assertLess(cm[0], c[0])


if __name__ == "__main__":
    unittest.main()
