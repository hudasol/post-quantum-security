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
            make_doc.write_doc(logs, [], sessions, [], times)
            text = (tmp / "docs" / "RTL_BASELINES.md").read_text()
        finally:
            make_doc.ROOT = old
            shutil.rmtree(tmp)
        self.assertIn("| hybrid_f1 over classical | vehicle | 4.00 | 4.00 |", text)
        self.assertIn("| classical | session start | vehicle | 1.50 |", text)
        self.assertIn("**RTL simulated**", text)
        self.assertNotIn(chr(0x2014), text)


if __name__ == "__main__":
    unittest.main()
