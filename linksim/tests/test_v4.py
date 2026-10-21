"""Unit tests for the fourth round link modules (lora, mac802154, checks,
validate_v4, protocols, protocols_report, study.write_round4).
Author: Huda Mueen. Modelled values; no cryptographic operation.
"""
import math
import os
import shutil
import tempfile
import unittest

from linksim import (checks, lora, mac802154, model, protocols, protocols_report, sim, study,
                     validate, validate_v4)

P = model.load_params()
SEED = 20261020


def rfc4944_count(dgram, avail):
    """Independent count of link frames for one datagram, written from RFC 4944
    Section 5.3: no header if it fits; else first fragment carries the largest
    multiple of 8 not above avail - 4, later ones the largest multiple of 8 not
    above avail - 5, the last one carries the rest."""
    if dgram <= avail:
        return 1
    first = 8 * ((avail - 4) // 8)
    later = 8 * ((avail - 5) // 8)
    rest = dgram - first
    return 1 + (rest + later - 1) // later


class TestLora(unittest.TestCase):
    def test_symbol_time(self):
        self.assertAlmostEqual(lora.symbol_s(7, 125000), 0.001024)
        self.assertAlmostEqual(lora.symbol_s(12, 125000), 0.032768)

    def test_published_examples(self):
        self.assertEqual(lora.payload_symbols(11, 7, 4, 1, 0, 0), 40)
        self.assertEqual(lora.payload_symbols(11, 7, 4, 0, 1, 0), 32)
        self.assertAlmostEqual(lora.time_on_air_s(11, 12, 125000, 2, 6, 0, 1, 0), 0.794624, places=9)
        self.assertAlmostEqual(lora.time_on_air_s(13, 12, 125000, 1, 8, 1, 0, 1), 1.16, delta=0.006)

    def test_de_default(self):
        self.assertEqual(lora.time_on_air_s(20, 12), lora.time_on_air_s(20, 12, de=1))
        self.assertEqual(lora.time_on_air_s(20, 7), lora.time_on_air_s(20, 7, de=0))

    def test_min_symbols(self):
        self.assertGreaterEqual(lora.payload_symbols(0, 12, 1, 0, 1, 1), 8)

    def test_lora_link(self):
        L0, L5 = lora.LoraLink(P, 0), lora.LoraLink(P, 5)
        self.assertEqual(L0.cap, 51)
        self.assertEqual(L5.cap, 222)
        self.assertAlmostEqual(L0.air_s(0), lora.time_on_air_s(13, 12, 125000, 1, 8, 1, 0, 1))
        self.assertGreater(L0.air_s(51), 8 * 51 / 250.0)
        self.assertAlmostEqual(L0.off_s(1.0), 99.0)


class TestMac802154(unittest.TestCase):
    def test_fragment_counts_independent(self):
        for avail in (81, 102, 60, 40):
            for d in (1, 50, 80, 81, 82, 200, 1280, 2047):
                pl = mac802154.sixlowpan_fragment_payloads(d, avail)
                self.assertEqual(len(pl), rfc4944_count(d, avail), (d, avail))
                self.assertEqual(sum(pl), d)
                if len(pl) > 1:
                    for b in pl[:-1]:
                        self.assertEqual(b % 8, 0)
                    hdr = mac802154.sixlowpan_headers(pl)
                    self.assertEqual(hdr[0], 4)
                    self.assertTrue(all(h == 5 for h in hdr[1:]))
                    for b, h in zip(pl, hdr):
                        self.assertLessEqual(b + h, avail)

    def test_zero_and_small(self):
        self.assertEqual(mac802154.sixlowpan_fragment_payloads(0, 81), [])
        self.assertEqual(mac802154.sixlowpan_headers([10]), [0])
        with self.assertRaises(ValueError):
            mac802154.sixlowpan_fragment_payloads(100, 8)

    def test_no_flags_matches_third_round(self):
        old = model.build_links(P)["ieee802154"]
        new = mac802154.build(P, ())
        self.assertEqual(model.fragment_wire_sizes(old, 5000), new.fragment_wire_sizes(5000))
        self.assertAlmostEqual(old.air_s(127), new.air_s(127))

    def test_flag_costs(self):
        sym = P["ieee802154_symbol_s"]
        base = mac802154.build(P, ())
        phy = mac802154.build(P, ("phy",))
        self.assertEqual(phy.wire_bytes(81) - base.wire_bytes(81), 6)
        ack = mac802154.build(P, ("mac_ack",))
        self.assertAlmostEqual(ack.air_s(127) - base.air_s(127), 12 * sym + 8 * 5 / 250000.0)
        ifs = mac802154.build(P, ("ifs",))
        self.assertAlmostEqual(ifs.frame_extra_s(127), 40 * sym)
        self.assertAlmostEqual(ifs.frame_extra_s(18), 12 * sym)
        cs = mac802154.build(P, ("csma",))
        self.assertAlmostEqual(cs.extra_fixed, 3.5 * 20 * sym + 8 * sym)
        ta = mac802154.build(P, ("turnaround",))
        self.assertAlmostEqual(ta.extra_fixed, 12 * sym)
        with self.assertRaises(ValueError):
            mac802154.build(P, ("bogus",))

    def test_frag_flag_counts(self):
        L = mac802154.build(P, ("frag",))
        n = len(L.fragment_wire_sizes(50000))
        dg = int(P["sixlowpan_datagram_bytes"])
        full, rem = divmod(50000, dg)
        want = full * rfc4944_count(dg, 81) + (rfc4944_count(rem, 81) if rem else 0)
        self.assertEqual(n, want)

    def test_multihop(self):
        self.assertEqual(mac802154.multihop_wall_s(2.0, 3), 6.0)
        with self.assertRaises(ValueError):
            mac802154.multihop_wall_s(1.0, 0)
        self.assertIsNot(mac802154.copy_link(mac802154.build(P)), None)


class TestChecks(unittest.TestCase):
    def test_duty_wait_closed_form(self):
        L = model.build_links(P)["lorawan"]
        for nb in (1, 11, 51):
            air = L.air_s(L.wire_bytes(nb))
            self.assertAlmostEqual(L.off_s(air), 99.0 * air)
            self.assertAlmostEqual(checks.duty_wait_closed_form(air, 0.01), 99.0 * air)
        # two fragments back to back: air, 99 air of silence, air
        a = L.air_s(L.wire_bytes(51))
        self.assertAlmostEqual(model.blast_wall_s(L, 102), a + 99 * a + a)

    def test_mc_transmissions_closed_form(self):
        for p in (0.01, 0.05, 0.1, 0.2, 0.3):
            r = checks.check_row(p, checks.sw_transmissions_data_loss(p, 2000, SEED), 1 / (1 - p))
            self.assertTrue(r["inside"], r)
            self.assertEqual(r["trials"], 2000)

    def test_existing_sim_close_to_closed_form(self):
        # Supplementary: data and ack loss; closed form 1/(1-p)^2; checked to 3.3 standard errors.
        for p in (0.05, 0.2):
            v = checks.sw_transmissions_sim("sik", p, 2000, SEED, P)
            m, lo, hi = checks.mean_ci(v)
            se = (hi - lo) / (2 * checks.Z95)
            self.assertLess(abs(m - 1 / (1 - p) ** 2), 3.3 * se)

    def test_mean_ci(self):
        m, lo, hi = checks.mean_ci([1.0, 1.0, 1.0])
        self.assertEqual((m, lo, hi), (1.0, 1.0, 1.0))


class TestValidateV4(unittest.TestCase):
    def test_diagnosis_baseline_and_order(self):
        d = validate_v4.diagnosis(P)
        self.assertAlmostEqual(d[0]["time_s_modelled_after"], validate.crosscheck_802154(P)["model_s"])
        main = [r for r in d if r["step"] != "9 sweep"]
        self.assertEqual(len(main), len(validate_v4.DIAG_STEPS))
        for a, b in zip(main, main[1:]):
            self.assertGreaterEqual(b["time_s_modelled_after"], a["time_s_modelled_after"])
            self.assertAlmostEqual(b["time_s_modelled_before"], a["time_s_modelled_after"])
        for r in main:
            if r["applied"] == "no":
                self.assertAlmostEqual(r["time_s_modelled_before"], r["time_s_modelled_after"])
        self.assertTrue(all(r["label"] in ("modelled", "assumption") for r in d))

    def test_validation_rows(self):
        v = validate_v4.validation(P)
        t5 = [r for r in v if "Table 5" in r["figure"]]
        self.assertEqual(len(t5), 10)
        lo = [r for r in v if r["figure"].startswith("LoRa") and "formula" in r["model"]]
        self.assertEqual(len(lo), 4)
        for r in lo:
            self.assertLess(abs(r["pct_error"]), 1.0)
        for r in v:
            self.assertAlmostEqual(r["abs_error"], r["value_modelled"] - r["value_published"])

    def test_lora_value(self):
        self.assertEqual(validate_v4.lora_value("payload symbols", (11, 7, 125000, 4, 8, 1, 0, 0)), 40.0)
        self.assertAlmostEqual(validate_v4.pct(110.0, 100.0), 10.0)

    def test_markdown_and_main(self):
        tmp = tempfile.mkdtemp()
        saved = validate_v4.RES
        try:
            validate_v4.RES = tmp
            validate_v4.main()
            for n in ("validation_v4.csv", "diagnosis_v4.csv", "closed_form_v4.csv", "validation_v4.md",
                      "fig_diagnosis_v4.svg"):
                self.assertTrue(os.path.exists(os.path.join(tmp, n)), n)
            with open(os.path.join(tmp, "validation_v4.csv")) as fh:
                self.assertTrue(fh.readline().startswith("label,"))
        finally:
            validate_v4.RES = saved
            shutil.rmtree(tmp)


class TestProtocols(unittest.TestCase):
    def test_crypto_sizes(self):
        self.assertEqual(protocols.crypto_sizes(P, "classical"), (32, 32, 64, 32))
        self.assertEqual(protocols.crypto_sizes(P, "hybrid"), (1216, 1120, 2420, 1312))
        self.assertEqual(protocols.crypto_sizes(P, "pq_only"), (1184, 1088, 2420, 1312))
        with self.assertRaises(ValueError):
            protocols.crypto_sizes(P, "x")
        self.assertEqual(protocols.cert_bytes(P, "hybrid"), 1312 + 2420 + P["proto_cert_overhead_bytes"])

    def test_edhoc_classical_matches_draft(self):
        f = protocols.handshake_flights("edhoc_oscore", "classical", P)
        coap = P["proto_coap_header_bytes"]
        self.assertEqual([b for _, _, b in f], [37 + coap, 102 + coap, 77 + coap])

    def test_flights_shapes(self):
        for pr, v in protocols.configs():
            hs = protocols.handshake_flights(pr, v, P)
            if pr == "raw_mldsa44":
                self.assertEqual(hs, [])
                self.assertEqual(protocols.rekey_flights(pr, v, P), [])
                continue
            expect = ["A", "B", "A", "B"] if pr == "mavlink2_pq" else ["A", "B", "A"]
            self.assertEqual([s for s, _, _ in hs], expect)
            self.assertTrue(all(b > 0 for _, _, b in hs))
            self.assertEqual(len(protocols.rekey_flights(pr, v, P)), 2)
        with self.assertRaises(ValueError):
            protocols.handshake_flights("nope", "classical", P)
        with self.assertRaises(ValueError):
            protocols.command_overhead("nope", "classical", P)
        with self.assertRaises(ValueError):
            protocols.scenario_flights("nope", "dtls13", "classical", P)

    def test_mavlink_hybrid_matches_mission(self):
        # design change F1: the protocol simulation and the mission study describe the same handshake
        from mission import model as mm
        f = protocols.handshake_flights("mavlink2_pq", "hybrid", P)
        g = mm.arch_profile("B")["flights"]
        self.assertEqual([b for _, _, b in f], [int(b) for _, b in g])
        self.assertEqual([s for s, _, _ in f], ["A" if d == "up" else "B" for d, _ in g])
        c = protocols.handshake_flights("mavlink2_pq", "classical", P)
        self.assertEqual([b for _, _, b in c], [int(b) for _, b in mm.arch_profile("A")["flights"]])

    def test_command_and_firmware(self):
        self.assertEqual(protocols.command_base_bytes(P), 42)
        self.assertEqual(protocols.command_overhead("mavlink2_pq", "hybrid", P), 13)
        self.assertEqual(protocols.command_overhead("raw_mldsa44", "per_message", P), 2420)
        self.assertEqual(protocols.firmware_flights("classical", P)[0][2], int(P["fw_image_bytes"]) + 64)
        self.assertEqual(protocols.scenario_flights("ttfam", "raw_mldsa44", "per_message", P)[0][2], 42 + 2420)

    def test_build_link(self):
        for k in protocols.LINKS:
            self.assertGreater(protocols.build_link(k, P).air_s(10), 0)
        with self.assertRaises(ValueError):
            protocols.build_link("wifi", P)

    def test_run_once_deterministic_and_side_air(self):
        L = protocols.build_link("ieee802154", P)
        fl = protocols.scenario_flights("ttfam", "edhoc_oscore", "hybrid", P)
        a = protocols.run_once(L, fl, 0.1, SEED, P)
        b = protocols.run_once(L, fl, 0.1, SEED, P)
        self.assertEqual(a["wall_s"], b["wall_s"])
        self.assertEqual(len(a["flight_ends"]), len(fl))
        self.assertLessEqual(a["side_air_max_s"], a["air_s"] + 1e-12)
        self.assertGreater(a["wall_s"], 0)

    def test_duty_budget_closed_form(self):
        L = protocols.build_link("lora_dr5", P)
        r = protocols.run_once(L, [("A", "one", 10)], 0.0, SEED, P)
        self.assertAlmostEqual(r["air_s"], L.air_s(10) + L.air_s(L.wire_bytes(int(P["ack_payload_bytes"]) + 2)))

    def test_cell_and_flips(self):
        rows = []
        for pr, v in (("mavlink2_pq", "classical"), ("raw_mldsa44", "per_message")):
            for loss in protocols.LOSSES:
                rows.append(protocols.cell(("ttfam", "sik", pr, v, loss, 30, P)))
        for r in rows:
            self.assertEqual(r["trials"], 30)
            self.assertLessEqual(r["completion_lo"], r["completion"])
            self.assertEqual(r["label"], "modelled")
            self.assertLessEqual(r["p_within_1s"], r["p_within_3600s"])
        fl = protocols.ranking_flips(rows)
        for f in fl:
            self.assertIn(f["intervals_overlap"], (True, False))

    def test_added_latency_and_sobol_small(self):
        q = dict(P)
        saved = protocols.LINKS
        try:
            protocols.LINKS = ("sik",)
            rows = protocols.added_latency_rows(q, trials=5)
        finally:
            protocols.LINKS = saved
        z = [r for r in rows if r["loss"] == 0.0 and r["protocol"] == "mavlink2_pq"][0]
        self.assertAlmostEqual(z["added_mean_s"], 8 * 13 / (64000 * 0.9), places=9)
        srows, flips = protocols.sobol(q, n=4)
        # common random numbers: an input a profile does not use has zero total index
        z = [r for r in srows if r["protocol"] == "edhoc_oscore" and r["input"] == "proto_cert_overhead_bytes"]
        self.assertTrue(all(abs(r["ST"]) < 1e-9 for r in z))
        self.assertEqual(len(srows), len(protocols.SOBOL_CASES) * len(protocols.SOBOL_INPUTS))
        self.assertEqual(len(flips), 2)


class TestReport(unittest.TestCase):
    def test_formatters(self):
        self.assertEqual(protocols_report.tfmt(0.5), "500 ms")
        self.assertEqual(protocols_report.tfmt(30), "30.00 s")
        self.assertEqual(protocols_report.tfmt(600), "10.0 min")
        self.assertEqual(protocols_report.tfmt(36000), "10.0 h")
        self.assertEqual(protocols_report.tfmt(""), "n/a")
        self.assertEqual(protocols_report.pfmt("0.5"), "50.0%")
        self.assertEqual(protocols_report.tfmt(0.0005), "0.50 ms")

    def test_end_to_end_small(self):
        tmp = tempfile.mkdtemp()
        saved = protocols.RES
        try:
            protocols.RES = tmp
            protocols.main(["--trials", "3", "--sobol-n", "2", "--workers", "1"])
            self.assertEqual(protocols.main(["--sobol-only", "--sobol-n", "2", "--workers", "1"]), 0)
            doc = os.path.join(tmp, "PROTOCOL_SIM.md")
            protocols_report.main(tmp, doc)
            text = open(doc, encoding="utf-8").read()
            self.assertIn("modelled", text)
            self.assertNotIn(chr(0x2014), text)
            for n in ("fig_protocols_ttfam.svg", "fig_protocols_deadline.svg", "fig_protocols_sobol.svg"):
                self.assertTrue(os.path.exists(os.path.join(tmp, n)))
        finally:
            protocols.RES = saved
            shutil.rmtree(tmp)


class TestStudyRound4(unittest.TestCase):
    def test_write_round4(self):
        L = []
        study.write_round4(L.append)
        text = "\n".join(L)
        self.assertIn("### 4.4 Round 4 validation", text)
        self.assertIn("factor", text)


if __name__ == "__main__":
    unittest.main()
