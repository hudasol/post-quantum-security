"""Unit tests for rtlsim/proto (log parser, aggregation, known answer generator, document generator).
Author: Huda Mueen."""
import hashlib
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent / "proto"))

import gen_kat  # noqa: E402
import make_doc  # noqa: E402
import parse_proto as pp  # noqa: E402


def session_log(design, cyc, fail_check_run=None, bad_line=False):
    """Synthetic log of a session design: per run the vehicle steps cost cyc[run] and cyc[run] * 2."""
    lines = [f"CFG,set,{design}", "CFG,seed_first,20261021", "CFG,runs,3",
             f"MSG,{design},F1,ground_to_vehicle,32", f"MSG,{design},F2,vehicle_to_ground,32",
             f"MSG,{design},F3,ground_to_vehicle,80", f"MSG,{design},F4,vehicle_to_ground,80"]
    for r, c in enumerate(cyc):
        for step, mult in (("ground_f1", 1), ("vehicle_f2", 1), ("ground_f3", 3), ("vehicle_f4", 2),
                           ("ground_accept", 1)):
            lines.append(f"RES,{design},{step},{r},{c * mult},ok")
            lines.append(f"STK,{design},{step},{r},{1000 + 100 * mult + r},ok")
        ok = "fail" if fail_check_run == r else "ok"
        lines.append(f"CHK,{design},same_session_key,{r},{ok}")
    if bad_line:
        lines.append(f"RES,{design},ground_f1,9,12")
    lines.append(f"DONE,{design},{1 if fail_check_run is not None else 0}")
    return lines


def kem_auth_log(cyc):
    """Synthetic log of the KEM authenticated design: per run ground_f1 c, vehicle_f2 2c, ground_f3 3c,
    vehicle_accept 1."""
    lines = ["CFG,set,kem_auth", "CFG,seed_first,20261021", f"CFG,runs,{len(cyc)}",
             "MSG,kem_auth,F1,ground_to_vehicle,2304", "MSG,kem_auth,F2,vehicle_to_ground,2224",
             "MSG,kem_auth,F3,ground_to_vehicle,16"]
    for r, c in enumerate(cyc):
        for step, v in (("ground_f1", c), ("vehicle_f2", 2 * c), ("ground_f3", 3 * c), ("vehicle_accept", 1)):
            lines.append(f"RES,kem_auth,{step},{r},{v},ok")
            lines.append(f"STK,kem_auth,{step},{r},2000,ok")
        lines.append(f"CHK,kem_auth,same_session_key,{r},ok")
    lines.append("DONE,kem_auth,0")
    return lines


PRIM_OPS = ["x25519_keygen", "x25519_shared", "ed25519_sign", "ed25519_verify", "shake256_kdf",
            "shake256_confirm_tag", "shake256_transcript_hybrid", "shake256_transcript_classical",
            "shake256_transcript_pq_only", "shake256_transcript_kem_auth", "shake256_kdf_kem_auth",
            "mlkem768_keygen", "mlkem768_encaps", "mlkem768_decaps", "mldsa44_sign", "mldsa44_verify"]


def prim_rows(core, scale=1):
    """Synthetic primitive rows: every call costs 10 * scale, signing 100 * scale (min 50, max 300)."""
    rows = []
    for op in PRIM_OPS:
        m = (100 if op == "mldsa44_sign" else 10) * scale
        rows.append({"core": core, "operation": op, "cycles_median": m,
                     "cycles_min": 50 * scale if op == "mldsa44_sign" else m,
                     "cycles_max": 300 * scale if op == "mldsa44_sign" else m})
    return rows


class ParseTests(unittest.TestCase):
    def test_parse_and_totals(self):
        lg = pp.parse_lines(session_log("hybrid_f1", [100, 300, 200]) + ["simulator noise"])
        self.assertTrue(lg.done)
        self.assertEqual(lg.failures_reported, 0)
        self.assertEqual(len(lg.res), 15)
        self.assertEqual(len(lg.msg), 4)
        v = pp.unit_totals(lg, "hybrid_f1", pp.SESSION_STEPS["vehicle"])
        self.assertEqual(v["totals"], [300, 900, 600])
        self.assertEqual(v["median"], 600)
        self.assertEqual(v["runs_correct"], 3)
        self.assertEqual(v["stack_max"], 1000 + 200 + 2)
        g = pp.unit_totals(lg, "hybrid_f1", pp.SESSION_STEPS["ground"])
        self.assertEqual(g["totals"], [500, 1500, 1000])

    def test_failed_check_counts(self):
        lg = pp.parse_lines(session_log("classical", [10, 20, 30], fail_check_run=1))
        v = pp.unit_totals(lg, "classical", pp.SESSION_STEPS["vehicle"])
        self.assertEqual(v["runs_correct"], 2)
        self.assertEqual(pp.checks_for(lg, "classical"), (2, 3))

    def test_incomplete_run_not_counted(self):
        lines = [x for x in session_log("pq_only", [10, 20]) if not x.startswith("RES,pq_only,vehicle_f4,1")]
        lg = pp.parse_lines(lines)
        v = pp.unit_totals(lg, "pq_only", pp.SESSION_STEPS["vehicle"])
        self.assertEqual(v["n"], 1)

    def test_malformed(self):
        with self.assertRaises(ValueError):
            pp.parse_lines(session_log("classical", [1], bad_line=True))
        for bad in ("STK,a,b,0,12,maybe", "CHK,a,b,0", "MSG,a,b,c", "DONE,a"):
            with self.assertRaises(ValueError):
                pp.parse_lines([bad])

    def test_op_summary(self):
        lg = pp.parse_lines(session_log("hybrid_f1", [100, 300, 200]))
        rows = {r["operation"]: r for r in pp.op_summary(lg)}
        self.assertEqual(rows["ground_f3"]["median"], 600)
        self.assertEqual(rows["ground_f3"]["ok"], 3)
        self.assertFalse(rows["ground_f3"]["stack_saturated"])

    def test_kem_auth_steps(self):
        lg = pp.parse_lines(kem_auth_log([100, 300, 200]))
        self.assertIn("kem_auth", pp.DESIGNS)
        v = pp.unit_totals(lg, "kem_auth", pp.UNITS["kem_auth"][0][1]["vehicle"])
        self.assertEqual(v["totals"], [201, 601, 401])
        g = pp.unit_totals(lg, "kem_auth", pp.KEM_AUTH_STEPS["ground"])
        self.assertEqual(g["median"], 800)
        self.assertEqual(pp.flights(lg, "kem_auth")[2], ("F3", "ground_to_vehicle", 16))

    def test_runs_filter_and_run_values(self):
        lg = pp.parse_lines(kem_auth_log([100, 300, 200, 50, 70, 900]))
        first = pp.unit_totals(lg, "kem_auth", pp.KEM_AUTH_STEPS["ground"], runs=range(5))
        self.assertEqual(first["n"], 5)
        self.assertEqual(first["median"], 400)
        self.assertEqual(pp.unit_totals(lg, "kem_auth", pp.KEM_AUTH_STEPS["ground"])["n"], 6)
        self.assertIsNone(pp.unit_totals(lg, "kem_auth", pp.KEM_AUTH_STEPS["ground"], runs=[]))
        self.assertEqual(pp.run_values(lg, "kem_auth", "vehicle_f2")[5], 1800)

    def test_bootstrap_ratio(self):
        self.assertEqual(pp.bootstrap_ratio_ci([4, 4], [2, 2, 2]), (2.0, 2.0))
        a, b = [10, 12, 30, 11, 13], [5, 6, 5, 7, 6]
        lo, hi = pp.bootstrap_ratio_ci(a, b)
        self.assertLessEqual(lo, 12 / 6)
        self.assertGreaterEqual(hi, 12 / 6)
        self.assertEqual((lo, hi), pp.bootstrap_ratio_ci(a, b))
        with self.assertRaises(ValueError):
            pp.bootstrap_ratio_ci([], [1])

    def test_decompose(self):
        total, rows = pp.decompose({"a": 10, "b": 3}, [("a", 2), ("b", 1)])
        self.assertEqual(total, 23)
        self.assertEqual(rows[0], ("a", 2, 10, 20))
        with self.assertRaises(KeyError):
            pp.decompose({"a": 1}, [("c", 1)])

    def test_sections(self):
        tmp = tempfile.mkdtemp()
        try:
            p = os.path.join(tmp, "s.txt")
            with open(p, "w") as fh:
                fh.write("hybrid_f1.elf  :\nsection   size   addr\n.vectors 256 0\n.text 1000 0\n.rodata 24 0\n"
                         ".sdata 8 0\n.sbss 4 0\n.bss 100 0\n.heap 4096 0\n.stack 262144 0\nTotal 9\n\n"
                         "classical.elf  :\nsection size addr\n.text 10 0\n.bss 2 0\n.stack 8192 0\n")
            sec = pp.read_size_sections(p)
            self.assertEqual(set(sec), {"hybrid_f1", "classical"})
            self.assertEqual(pp.image_sizes(sec["hybrid_f1"]), {"text": 1280, "data": 8, "bss": 104})
            self.assertEqual(pp.image_sizes(sec["classical"]), {"text": 10, "data": 0, "bss": 2})
        finally:
            shutil.rmtree(tmp)


class KatTests(unittest.TestCase):
    def test_tag_formula(self):
        key = bytes(32)
        header = bytes([0xFD, 1, 1, 0, 0, 1, 1, 0, 0, 0])
        payload = b"\x05"
        crc = b"\x00\x00"
        ts = 0x010203040506
        data = key + header + payload + crc + b"\x07" + bytes([6, 5, 4, 3, 2, 1])
        self.assertEqual(gen_kat.mavlink_tag(key, header, payload, crc, 7, ts), hashlib.sha256(data).digest()[:6])

    def test_header(self):
        h = gen_kat.header_text()
        self.assertIn("static const uint8_t KAT_TAG_OUT[6]", h)
        self.assertIn("static const uint8_t LABEL_KDF[14]", h)
        self.assertIn("KAT_SHA256_IN[60]", h)
        out = hashlib.shake_256(b"r6 session key" + gen_kat.KDF_SSX + gen_kat.KDF_SSKEM + gen_kat.KDF_TH).digest(32)
        self.assertIn(", ".join(f"0x{b:02x}" for b in out), h)


class KatKemAuthTests(unittest.TestCase):
    def test_kdf4(self):
        h = gen_kat.header_text()
        out = hashlib.shake_256(b"r6 session key" + gen_kat.KDF_SSX + gen_kat.KDF_SSKEM + gen_kat.KDF_SSKEM2
                                + gen_kat.KDF_SSKEM3 + gen_kat.KDF_TH).digest(32)
        self.assertIn("KAT_KDF4_OUT[32] = {" + ", ".join(f"0x{b:02x}" for b in out), h)
        self.assertIn("KAT_KDF_SSKEM3[32]", h)


class DecompositionTests(unittest.TestCase):
    def setUp(self):
        self.logs = {}
        for core, f in (("ibex", 3), ("cv32e40p", 2)):
            self.logs[(core, "classical")] = pp.parse_lines(session_log("classical", [10 * f] * 5 + [11 * f]))
            self.logs[(core, "hybrid_f1")] = pp.parse_lines(session_log("hybrid_f1", [40 * f, 60 * f, 50 * f]))
            self.logs[(core, "pq_only")] = pp.parse_lines(session_log("pq_only", [30 * f, 35 * f, 50 * f]))
            self.logs[(core, "kem_auth")] = pp.parse_lines(kem_auth_log([20 * f, 20 * f, 20 * f]))
        self.sessions = make_doc.build_sessions(self.logs)
        self.prims = prim_rows("ibex", 3) + prim_rows("cv32e40p", 2)

    def test_decomposition(self):
        d = make_doc.build_decomposition(self.prims, self.sessions)
        k = make_doc.get(d, core="cv32e40p", design="kem_auth", side="vehicle")
        # 9 calls of 20 cycles; measured vehicle_f2 + vehicle_accept = 2 * 40 + 1
        self.assertEqual(k["primitive_sum_cycles"], 9 * 20)
        self.assertEqual(k["measured_cycles_median"], 81)
        self.assertFalse(k["has_mldsa44_sign"])
        self.assertEqual(k["primitive_sum_sign_min"], k["primitive_sum_sign_max"])
        h = make_doc.get(d, core="cv32e40p", design="hybrid_f1", side="vehicle")
        self.assertTrue(h["has_mldsa44_sign"])
        self.assertEqual(h["primitive_sum_cycles"], 8 * 20 + 200)
        self.assertEqual(h["primitive_sum_sign_min"], 8 * 20 + 100)
        self.assertEqual(h["primitive_sum_sign_max"], 8 * 20 + 600)
        self.assertEqual(h["label"], "RTL simulated")
        self.assertIn("mldsa44_sign x1 = 200", h["components"])
        g = make_doc.get(d, core="ibex", design="kem_auth", side="ground")
        self.assertEqual(g["primitive_sum_cycles"], 10 * 30)

    def test_ratios(self):
        d = make_doc.build_decomposition(self.prims, self.sessions)
        r = make_doc.build_ratios(self.logs, self.sessions, d)
        m = make_doc.get(r, core="cv32e40p", side="vehicle", numerator="hybrid_f1", denominator="classical",
                         basis="session medians")
        self.assertAlmostEqual(m["ratio"], 300 / 60, places=4)
        self.assertLessEqual(m["ci95_low"], m["ratio"])
        self.assertGreaterEqual(m["ci95_high"], m["ratio"])
        p = make_doc.get(r, core="cv32e40p", side="vehicle", numerator="hybrid_f1", denominator="pq_only",
                         basis="primitive sums")
        self.assertAlmostEqual(p["ratio"], round(360 / (6 * 20 + 200), 4))
        pmin = make_doc.get(r, core="cv32e40p", side="vehicle", numerator="hybrid_f1", denominator="pq_only",
                            basis="primitive sums, signing at its min")
        self.assertAlmostEqual(pmin["ratio"], round(260 / 220, 4))
        self.assertIsNotNone(make_doc.get(r, numerator="kem_auth", denominator="hybrid_f1", side="ground"))

    def test_doc_sections(self):
        d = make_doc.build_decomposition(self.prims, self.sessions)
        r = make_doc.build_ratios(self.logs, self.sessions, d)
        sizes = [{"label": "host measured", "core": c, "image": i, "variant": v, "text_bytes": 1000,
                  "data_bytes": 4, "bss_bytes": 50} for c in ("ibex", "cv32e40p") for i in ("classical", "kem_auth")
                 for v in ("timing", "gc")]
        prims = [dict(x, label="RTL simulated", round5_cycles_median="", cycles_ci95_low=x["cycles_median"],
                      cycles_ci95_high=x["cycles_median"], peak_stack_bytes=400,
                      stack_saturated=False) for x in self.prims]
        tmp = Path(tempfile.mkdtemp())
        old_root, old_rtl = make_doc.ROOT, make_doc.RTL
        try:
            (tmp / "docs").mkdir()
            (tmp / "data").mkdir()
            (tmp / "rtl" / "results").mkdir(parents=True)
            shutil.copy(old_root / "data" / "shared_inputs.csv", tmp / "data" / "shared_inputs.csv")
            snap = [{"core": "cv32e40p", "design": "classical", "unit": "session start", "side": "vehicle",
                     "cycles_median": "60"}]
            make_doc.write_csv(tmp / "rtl" / "results" / make_doc.SNAPSHOT_SESSIONS, snap)
            make_doc.ROOT, make_doc.RTL = tmp, tmp / "rtl"
            make_doc.write_doc(self.logs, prims, self.sessions, sizes, [], d, r)
            text = (tmp / "docs" / "RTL_BASELINES.md").read_text()
        finally:
            make_doc.ROOT, make_doc.RTL = old_root, old_rtl
            shutil.rmtree(tmp)
        self.assertIn("## Where the cycles go", text)
        self.assertIn("| sum of primitive medians | | 270 | 180 | |", text)
        self.assertIn("| hybrid_f1 over pq_only | ground | CV32E40P |", text)
        self.assertIn("## The classical baseline is one portable C library", text)
        self.assertIn("portable C on these two cores only", text)
        self.assertIn("| kem_auth | 1,000 | 4 | 50 | 1,000 | 4 | 50 |", text)
        self.assertIn("| classical | vehicle | CV32E40P | 60 | 60 | yes | 60 |", text)
        self.assertNotIn("| hybrid_f1 | vehicle | CV32E40P | 60 |", text)
        self.assertIn("Reproduced exactly: 1 of 1 rows.", text)
        self.assertNotIn(chr(0x2014), text)


class DocTests(unittest.TestCase):
    def test_sessions_ratios_and_doc(self):
        logs = {}
        for core, f in (("ibex", 3), ("cv32e40p", 2)):
            logs[(core, "classical")] = pp.parse_lines(session_log("classical", [10 * f, 10 * f, 10 * f]))
            logs[(core, "hybrid_f1")] = pp.parse_lines(session_log("hybrid_f1", [40 * f, 40 * f, 40 * f]))
        sessions = make_doc.build_sessions(logs)
        h = make_doc.get(sessions, core="cv32e40p", design="hybrid_f1", side="vehicle")
        self.assertEqual(h["cycles_median"], 240)
        self.assertEqual(h["bytes_total"], 224)
        self.assertEqual(h["label"], "RTL simulated")
        times = make_doc.build_time(sessions)
        t = make_doc.get(times, core="cv32e40p", design="hybrid_f1", side="vehicle", clock_mhz=64)
        self.assertAlmostEqual(t["time_ms"], round(240 / 64e3, 4))
        self.assertEqual(t["label"], "estimated")
        tmp = Path(tempfile.mkdtemp())
        old = make_doc.ROOT
        try:
            (tmp / "docs").mkdir()
            (tmp / "data").mkdir()
            shutil.copy(old / "data" / "shared_inputs.csv", tmp / "data" / "shared_inputs.csv")
            make_doc.ROOT = tmp
            make_doc.write_doc(logs, [], sessions, [], times, [], make_doc.build_ratios(logs, sessions, []))
            text = (tmp / "docs" / "RTL_BASELINES.md").read_text()
        finally:
            make_doc.ROOT = old
            shutil.rmtree(tmp)
        self.assertIn("| hybrid_f1 over classical | vehicle | CV32E40P | 4.00 [4.00 to 4.00] | not available |", text)
        self.assertIn("| classical | session start | vehicle | 1.50 |", text)
        self.assertIn("**RTL simulated**", text)
        self.assertNotIn(chr(0x2014), text)


if __name__ == "__main__":
    unittest.main()
