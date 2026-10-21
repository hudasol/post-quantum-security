"""One parameter, one value, one source: every study reads the values of data/shared_inputs.csv.

Author: Huda Mueen.

Each study's effective parameters are loaded through that study's own code path and compared with the shared
file. The test fails when a study reads a different value, when a shared parameter is defined again in a study's
own input file, or when a shared value disagrees with the evidence row it cites.
Run: python3 -m unittest tests.test_shared_inputs
"""
import csv
import math
import os
import statistics
import unittest

from shared import inputs as si

ROOT = si.ROOT
SH = si.values()


def close(a, b):
    return math.isclose(float(a), float(b), rel_tol=1e-12, abs_tol=1e-12)


class TestSharedFile(unittest.TestCase):
    def test_columns_and_labels(self):
        rows = si.rows()
        names = [r["parameter"] for r in rows]
        self.assertEqual(len(names), len(set(names)), "a parameter is listed twice")
        for r in rows:
            self.assertIn(r["label"], ("published", "derived from published", "assumption"), r["parameter"])
            self.assertTrue(r["source"].strip(), r["parameter"])
            used = r["used_by"].split(";")
            self.assertGreaterEqual(len(used), 2, r["parameter"] + " is used by one study only")
            self.assertTrue(set(used) <= si.STUDIES, r["parameter"])

    def test_evidence_sources_match(self):
        with open(os.path.join(ROOT, "data", "evidence.csv"), newline="", encoding="utf-8") as fh:
            ev = {r["id"]: r for r in csv.DictReader(fh)}
        n = 0
        for r in si.rows():
            eid = si.evidence_id(r["parameter"])
            if eid is None:
                continue
            e = ev[eid]
            got = e["cycles"] or e["key_or_sig_size_bytes"]
            self.assertTrue(close(got, r["value"]), "%s: %s against %s" % (r["parameter"], got, r["value"]))
            n += 1
        self.assertGreaterEqual(n, 10)

    def test_derived_values(self):
        from energy import model as em
        bench = em.read_csv(os.path.join(ROOT, "energy", "retrieved_benchmarks.csv"))
        cpb = statistics.median(em.sha256_cpb(bench, "sw"))
        self.assertTrue(close(cpb, SH["sha256_cpb_sw_m4"]))
        self.assertTrue(close(em.hmac_sha256_bytes(int(SH["mac_message_bytes"])) * cpb, SH["mac_cycles_per_message"]))

    def test_not_defined_twice(self):
        own = {}
        for path, key in (("linksim/params.csv", "name"), ("mission/assumptions.csv", "name"),
                          ("bootchain/inputs.csv", "name")):
            with open(os.path.join(ROOT, path), newline="", encoding="utf-8") as fh:
                own[path] = {r[key] for r in csv.DictReader(fh)}
        for path, names in own.items():
            self.assertFalse(names & set(SH), "%s redefines %s" % (path, sorted(names & set(SH))))
        from mission import model as mm
        self.assertFalse(own["mission/assumptions.csv"] & set(mm.SHARED_ASSUMPTIONS))


class TestStudiesReadShared(unittest.TestCase):
    def test_linksim(self):
        from linksim import model as lm
        p = lm.load_params()
        for name in si.used_by("linksim"):
            self.assertTrue(close(p[name], SH[name]), name)

    def test_mission(self):
        from mission import model as mm
        p = mm.load_link_params()
        for name in si.used_by("mission"):
            self.assertTrue(close(p[name], SH[name]), name)
        a = mm.load_assumptions()
        for name, (sname, mult) in mm.SHARED_ASSUMPTIONS.items():
            self.assertTrue(close(a[name], SH[sname] * mult), name)
        cyc = mm.cycle_table()
        for op, (sname, count, *_rest) in mm.CYCLE_SOURCES.items():
            self.assertTrue(close(cyc[op][0], SH[sname] * count), op)
            self.assertIn(si.evidence_id(sname), cyc[op][2])
        # links: rates and overheads as the simulation sees them
        sik = mm.link_profile("sik")
        self.assertTrue(close(sik["rate"], SH["sik_air_rate_bps"] * SH["sik_usable_fraction"]))
        lo = mm.link_profile("lora_dr5")
        self.assertEqual(lo["wire_extra"], int(SH["lorawan_frame_overhead_bytes"]))
        self.assertTrue(close(lo["rate"], SH["lorawan_dr5_bitrate_bps"]))
        # handshake of architecture B with design change F1
        fl = mm.arch_profile("B")["flights"]
        self.assertEqual(fl[-1], ("down", SH["mldsa44_sig_bytes"] + SH["confirm_bytes"]))

    def test_energy(self):
        from energy import model as em
        ev = em.load_evidence()
        bench = em.load_local("retrieved_benchmarks.csv")
        cmap = em.load_local("cycle_map.csv")
        ops = {"mldsa44_verify": "mldsa44_verify_cycles_m4", "mldsa44_sign": "mldsa44_sign_cycles_m4",
               "mlkem768_encaps": "mlkem768_encaps_cycles_m4", "lms_verify": "lms_verify_cycles_m4",
               "ed25519_verify": "ed25519_verify_cycles_m4", "ed25519_sign": "ed25519_sign_cycles_m4",
               "x25519_shared": "x25519_scalarmult_cycles_m4", "x25519_keygen": "x25519_scalarmult_cycles_m4",
               "hmac_sha256_msg": "mac_cycles_per_message"}
        for op, sname in ops.items():
            got = em.cycles_for(op, "Cortex-M4", ev, bench, cmap, msg_bytes=int(SH["mac_message_bytes"]))["cycles"]
            self.assertTrue(close(got, SH[sname]), op)
        cf = [r for r in em.load_local("platforms.csv") if r["mcu"] == "STM32F405"][0]
        self.assertTrue(close(cf["clock_mhz"], SH["clock_m4_ref_mhz"]))
        self.assertTrue(close(em.load_assumptions()["command_msg_bytes"]["nominal"], SH["mac_message_bytes"]))

    def test_bootchain(self):
        from bootchain import model as bm
        from bootchain import run_all as br
        from energy import model as em
        inp = bm.load_inputs()
        for name in si.used_by("bootchain"):
            self.assertTrue(close(bm.inval(inp, name), SH[name]), name)
        m4 = [t for t in br.TARGETS if t[1] == "Cortex-M4"][0]
        self.assertTrue(close(m4[2], SH["clock_m4_ref_mhz"]))
        rates = bm.link_rates(bm.link_param_rows())
        self.assertTrue(close(rates["SiK 64 kbit/s air rate, 90 percent usable"][0],
                              SH["sik_air_rate_bps"] * SH["sik_usable_fraction"]))
        ev = em.load_evidence()
        bench = em.load_local("retrieved_benchmarks.csv")
        cmap = em.load_local("cycle_map.csv")
        for s in bm.load_schemes():
            if s["scheme"] in ("ML-DSA-44", "LMS", "Ed25519"):
                c = em.cycles_for(s["verify_op"], "Cortex-M4", ev, bench, cmap)["cycles"]
                sname = {"ML-DSA-44": "mldsa44_verify_cycles_m4", "LMS": "lms_verify_cycles_m4",
                         "Ed25519": "ed25519_verify_cycles_m4"}[s["scheme"]]
                self.assertTrue(close(c, SH[sname]), s["scheme"])

    def test_stats(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("e2e", os.path.join(ROOT, "stats", "end_to_end.py"))
        e2e = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(e2e)
        lo, hi = e2e.cpb_range()
        self.assertLessEqual(lo, SH["sha256_cpb_sw_m4"])
        self.assertGreaterEqual(hi, SH["sha256_cpb_sw_m4"])
        ch = e2e.Chain(runs=1)
        self.assertTrue(close(ch.mldsa, SH["mldsa44_verify_cycles_m4"]))
        self.assertTrue(close(ch.mldsa_sign, SH["mldsa44_sign_cycles_m4"]))
        self.assertTrue(close(ch.mlkem, SH["mlkem768_encaps_cycles_m4"]))
        cfg = ch.cfg["B"]
        self.assertTrue(close(cfg["link"]["rate"], SH["sik_air_rate_bps"] * SH["sik_usable_fraction"]))


if __name__ == "__main__":
    unittest.main()
