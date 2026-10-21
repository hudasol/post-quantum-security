"""Unit tests for the board kit scripts (python3 -m unittest discover bench/board_kit/tests).

Author: Huda Mueen. Synthetic log text below is test input only, never a result.
"""
import csv
import io
import os
import sys
import tempfile
import unittest

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KIT)
import build_b0  # noqa: E402
import build_b1  # noqa: E402
import capture  # noqa: E402
import compare  # noqa: E402
import kit_config as K  # noqa: E402
import make_build_log  # noqa: E402
import parse  # noqa: E402
import run_dry_run  # noqa: E402
import session_plan  # noqa: E402
import cache_check  # noqa: E402
import renode_check  # noqa: E402
import predictions_v5  # noqa: E402
import glob  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402


def fixed_clock():
    return "2026-10-20T00:00:00.000000Z"


def write_capture(path, image, lines, label="emulated", run=1, experiment="B0"):
    meta = {"version": "1", "source": "test", "start_utc": fixed_clock(), "experiment": experiment,
            "image": image, "run": run, "label": label, "board": "TEST", "note": ""}
    with open(path, "w") as fh:
        capture.capture_lines([ln + "\n" for ln in lines], fh, meta, clock=fixed_clock)


SPEED_KEM = ["==========================", "keypair cycles:", "100", "encaps cycles:", "200",
             "decaps cycles:", "300", "OK KEYS", "", "+", "keypair cycles:", "110",
             "encaps cycles:", "210", "decaps cycles:", "310", "OK KEYS", "", "+", "#"]
STACK_SIGN = ["==========================", "keypair stack usage:", "38296", "sign stack usage:",
              "44816", "verify stack usage:", "8912", "Signature valid!", "", "#"]
B1_LOG = ["==========================", "META,platform,test", "META,clock_hz_rcc,20000000",
          "META,flash_ws,0", "META,cache,icache=1 dcache=1 prefetch=1",
          "META,lib,mldsa-native v2.0.0 (commit 834a90d5e846ffa1e1611bd24e160bb2e9b86d35)",
          "BENCH,ML-DSA,ML-DSA-44,keygen,0,0,1000,cycles", "BENCH,ML-DSA,ML-DSA-44,sign,0,0,2000,cycles",
          "STACK,ML-DSA,ML-DSA-44,sign,50008", "CHECK,ML-DSA,ML-DSA-44,sign_verify_and_reject,10,0",
          "META,harness_rc,0", "#"]


class CaptureTests(unittest.TestCase):
    def test_marker_stops_and_header(self):
        out = io.StringIO()
        n, reason = capture.capture_lines([b"a\r\n", b"#\n", b"after\n"], out, {"run": 2},
                                          clock=fixed_clock)
        self.assertEqual((n, reason), (2, "marker"))
        text = out.getvalue().splitlines()
        self.assertEqual(text[0], "# capture,run,2")
        self.assertEqual(text[1], fixed_clock() + "\ta")
        self.assertEqual(text[-1], "# capture,end,marker")

    def test_max_lines_and_eof(self):
        out = io.StringIO()
        self.assertEqual(capture.capture_lines(["x\n"] * 5, out, {}, max_lines=3,
                                               clock=fixed_clock), (3, "max_lines"))
        self.assertEqual(capture.capture_lines(["x\n"], io.StringIO(), {}, clock=fixed_clock),
                         (1, "eof"))

    def test_timeout_on_empty_reads(self):
        t = iter([0.0, 10.0, 20.0])
        n, reason = capture.capture_lines([b"", b"", b""], io.StringIO(), {}, deadline=5.0,
                                          monotonic=lambda: next(t), clock=fixed_clock)
        self.assertEqual((n, reason), (0, "timeout"))

    def test_cli_replay_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "in.txt")
            with open(src, "w") as fh:
                fh.write("\n".join(SPEED_KEM) + "\n")
            out = os.path.join(d, "out.log")
            rc = capture.main(["--replay", src, "--run", "1", "--image",
                               "crypto_kem_ml-kem-768_m4fspeed_speed", "--label", "emulated",
                               "--out", out])
            self.assertEqual(rc, 0)
            r = parse.parse_log(out)
            self.assertEqual(r["n_unrecognised"], 0)
            self.assertEqual(len(r["rows"]), 6)


class ParseTests(unittest.TestCase):
    def test_image_info(self):
        i = parse.image_info("mupq_pqclean_crypto_sign_ml-dsa-44_clean_speed")
        self.assertEqual((i["scheme"], i["variant"], i["kind"]), ("ML-DSA-44", "clean", "speed"))
        self.assertEqual(parse.image_info("b1_mlkem_768")["library"], "mlkem-native")
        with self.assertRaises(ValueError):
            parse.image_info("unknown")

    def test_speed_log(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "a.log")
            write_capture(p, "crypto_kem_ml-kem-768_m4fspeed_speed", SPEED_KEM)
            r = parse.parse_log(p, {"commit": "abc"})
            self.assertEqual(r["n_unrecognised"], 0)
            self.assertEqual(r["n_lines"], len(SPEED_KEM))
            ops = [(x["operation"], x["iter"], x["cycles"]) for x in r["rows"]]
            self.assertEqual(ops[0], ("keygen", "0", "100"))
            self.assertEqual(ops[3], ("keygen", "1", "110"))
            self.assertEqual(r["rows"][0]["clock_hz"], "emulated")
            self.assertEqual(r["checks"][0]["ok"], 2)

    def test_stack_log_and_unknown(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "a.log")
            write_capture(p, "crypto_sign_ml-dsa-44_m4f_stack", STACK_SIGN + ["garbage line"],
                          label="board measured")
            r = parse.parse_log(p, {"clock_hz": "20000000"})
            self.assertEqual(r["n_unrecognised"], 0)  # stops at '#': garbage is after it
            self.assertEqual([x["stack_bytes"] for x in r["rows"]], ["38296", "44816", "8912"])
            self.assertEqual(r["rows"][0]["clock_hz"], "20000000")
            p2 = os.path.join(d, "b.log")
            write_capture(p2, "crypto_sign_ml-dsa-44_m4f_stack", ["noise", "sign stack usage:",
                                                                  "x", "#"])
            self.assertEqual(parse.parse_log(p2)["n_unrecognised"], 2)

    def test_error_lines_count_as_failures(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "a.log")
            write_capture(p, "crypto_kem_ml-kem-768_clean_test", ["ERROR KEYS", "", "+", "#"])
            r = parse.parse_log(p)
            self.assertEqual(r["checks"][0]["fail"], 1)

    def test_b1_log(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "b.log")
            write_capture(p, "b1_mldsa_44", B1_LOG, label="board measured", experiment="B1")
            r = parse.parse_log(p)
            self.assertEqual(r["n_unrecognised"], 0)
            self.assertEqual(len(r["rows"]), 3)
            row = r["rows"][0]
            self.assertEqual((row["clock_hz"], row["flash_ws"], row["scheme"]),
                             ("20000000", "0", "ML-DSA-44"))
            self.assertTrue(row["commit"].startswith("834a90d5"))
            self.assertEqual(r["checks"][0]["ok"], 10)

    def test_template(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "t.csv")
            parse.write_template(p)
            rows = list(csv.DictReader(open(p)))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["label"], "planned")
            self.assertEqual(set(rows[0]), set(parse.RESULT_COLUMNS))

    def test_cli_require_all(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "a.log")
            write_capture(p, "crypto_kem_ml-kem-768_m4fspeed_speed", SPEED_KEM)
            out = os.path.join(d, "r.csv")
            rc = parse.main([p, "--out", out, "--checks-out", os.path.join(d, "c.csv"),
                             "--require-all"])
            self.assertEqual(rc, 0)
            with open(out) as fh:
                self.assertEqual(next(csv.reader(fh)), parse.RESULT_COLUMNS)


EVID = [{"id": "S2-0022", "library": "pqm4 implementation 'm4fspeed (x)'", "evidence_type":
         "published", "cycles": "100", "parameter_set": "ML-KEM-768", "operation": "keygen",
         "stack_bytes": "5396"},
        {"id": "S2-0019", "library": "pqm4 implementation 'clean (x)'", "evidence_type":
         "published", "cycles": "1000", "parameter_set": "ML-KEM-768", "operation": "keygen",
         "stack_bytes": "10248"}]


def res(label, exp="B0", variant="m4fspeed", cycles=("110", "90", "100")):
    return [dict(experiment=exp, label=label, board="b", scheme="ML-KEM-768", variant=variant,
                 operation="keygen", run=str(i % 3 + 1), cycles=c, stack_bytes="")
            for i, c in enumerate(cycles)]


class CompareTests(unittest.TestCase):
    def test_emulated_excluded(self):
        rows = compare.compare(res("emulated"), EVID)
        self.assertTrue(rows[0]["cycles_status"].startswith("excluded"))
        self.assertEqual(rows[0]["ratio_board_measured_to_published"], "")
        self.assertEqual(rows[0]["published_id"], "S2-0022")

    def test_board_measured_ratio_and_interval(self):
        rows = compare.compare(res("board measured"), EVID, {("ML-KEM-768", "", "keygen"):
                                                                  (50.0, "0.1")})
        r = rows[0]
        self.assertEqual(r["cycles_status"], "compared")
        self.assertEqual(r["ratio_board_measured_to_published"], "1.0000")
        self.assertLessEqual(float(r["ratio_ci_low"]), 1.0)
        self.assertGreaterEqual(float(r["ratio_ci_high"]), 1.0)
        self.assertEqual(r["ratio_board_measured_to_modelled"], "2.0000")
        self.assertEqual(r["modelled_validation_error"], "0.1")

    def test_b1_reference_not_ratio(self):
        r = compare.compare(res("board measured", exp="B1", variant="portable_c"), EVID)[0]
        self.assertEqual(r["published_reference_id"], "S2-0019")
        self.assertEqual(r["ratio_board_measured_to_published"], "")

    def test_bootstrap_deterministic(self):
        a = compare.bootstrap_mean_ratio([1.0, 2.0, 3.0], 2.0)
        self.assertEqual(a, compare.bootstrap_mean_ratio([1.0, 2.0, 3.0], 2.0))

    def test_optional_rows_missing_and_present(self):
        self.assertEqual(compare.optional_rows("/nonexistent.csv", "modelled"), {})
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "m.csv")
            with open(p, "w") as fh:
                fh.write("scheme,operation,cycles_modelled,validation_error\n"
                         "ml-kem-768,keygen,123,0.05\n")
            self.assertEqual(compare.optional_rows(p, "modelled"),
                             {("ML-KEM-768", "", "keygen"): (123.0, "0.05")})

    def test_columns_carry_labels(self):
        for c in compare.COLUMNS:
            if c.startswith(("cycles_", "stack_")) and c != "cycles_status":
                self.assertTrue(any(s in c for s in ("board_measured", "published", "modelled",
                                                     "rtl_simulated", "emulated")), c)


class BuildTests(unittest.TestCase):
    def test_parse_size(self):
        txt = "   text\t   data\t    bss\t    dec\t    hex\tfilename\n  22656\t     16\t     16\t  22688\t   58a0\tx.elf\n"
        self.assertEqual(build_b0.parse_size(txt), {"text": 22656, "data": 16, "bss": 16,
                                                    "dec": 22688})

    def test_make_args_and_names(self):
        a = build_b0.make_args("nucleo-l4r5zi", "crypto_kem/ml-kem-768/m4fspeed", "", 100)
        self.assertNotIn("MUPQ_NAMESPACE=", " ".join(a))
        self.assertIn("MUPQ_ITERATIONS=100", a)
        self.assertEqual(K.target_name("crypto_kem/x/y", "speed", "nucleo-l4r5zi"),
                         "bin/crypto_kem_x_y_speed.hex")
        self.assertEqual(K.target_name("crypto_kem/x/y", "speed", "mps2-an386"),
                         "bin/crypto_kem_x_y_speed.bin")

    def test_b1_sets_and_flags(self):
        self.assertEqual(build_b1.parse_sets("mlkem:768,mldsa:44"), [("mlkem", 768), ("mldsa", 44)])
        f = build_b1.harness_flags("mldsa", 87, 100, "nucleo-l4r5zi", "/k", "/d")
        self.assertIn("-DMLD_CONFIG_PARAMETER_SET=87", f)
        self.assertIn("-Dmain=bench_harness_main", f)

    def test_size_rows_label(self):
        rec = {"toolchain": "gcc", "pqm4_commit": "c", "images": [
            {"experiment": "B0", "platform": "p", "scheme": "s", "variant": "v", "kind": "speed",
             "iterations": 1, "image": "i", "text": 1, "data": 2, "bss": 3, "dec": 6}]}
        rows = make_build_log.size_rows([rec])
        self.assertEqual(rows[0]["label"], "host measured")
        self.assertEqual(rows[0]["total_dec_bytes"], 6)


class PlanTests(unittest.TestCase):
    def test_uart_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            write_capture(os.path.join(d, "run1_img.log"), "img", ["ab", "#"])
            write_capture(os.path.join(d, "run2_img.log"), "img", ["abcd", "#"])
            self.assertEqual(session_plan.uart_bytes(d), {"img": 6.0})

    def test_b0_items_use_published(self):
        pub = {}
        for s, v, path, _ in K.B0_VARIANTS:
            for op in ("keygen", "encaps", "decaps", "sign", "verify"):
                pub[(s.upper(), v, op)] = (20_000_000.0, "id")
        items = session_plan.b0_items(pub)
        speed = [i for i in items if i[4] == "speed"]
        self.assertEqual(len(items), len(K.B0_VARIANTS) * 3)
        self.assertTrue(all(i[5] == 3 for i in speed))
        kem = [i for i in speed if i[2] == "ML-KEM-768"][0]
        self.assertEqual(kem[7], 3 * 20_000_000.0 * K.ITERATIONS["ml-kem-768"])

    @unittest.skipUnless(os.path.isdir(os.path.join(K.PQM4_DIR, "libopencm3", "include")),
                         "pqm4 clone not present")
    def test_register_addresses(self):
        ra = session_plan.register_addresses()
        self.assertEqual(ra["RCC_PLLCFGR"] - ra["RCC_CFGR"], 4)
        self.assertEqual(ra["FLASH_ACR"] - ra["RCC_CFGR"], 0x1000 - 8)


class DryRunTests(unittest.TestCase):
    def test_previous_harness_stack_reads_repo_file(self):
        prev = run_dry_run.previous_harness_stack()
        if prev:
            self.assertTrue(all(isinstance(v, str) for v in prev.values()))


B1_OFF_LOG = ["==========================", "META,cache_pass,off", "META,cache_option,BENCH_CACHE_OFF",
              "META,cache_off_applied,1", "META,platform,test", "META,clock_hz_rcc,20000000",
              "META,flash_ws,0", "META,cache,icache=0 dcache=0 prefetch=0",
              "BENCH,ML-KEM,ML-KEM-768,keygen,0,0,1000,cycles",
              "BENCH,ML-KEM,ML-KEM-768,keygen,0,1,1200,cycles",
              "CHECK,ML-KEM,ML-KEM-768,roundtrip,2,0", "META,harness_rc,0", "#"]


class CachePassParseTests(unittest.TestCase):
    def test_image_names(self):
        self.assertEqual(parse.image_info("b1_mlkem_768_cacheoff")["cache_pass"], "off")
        self.assertEqual(parse.image_info("b1_mlkem_768")["cache_pass"], "on")
        self.assertEqual(parse.image_info("crypto_kem_ml-kem-768_m4fspeed_speed")["cache_pass"],
                         "on")
        self.assertEqual(K.image_base("mldsa", 44, "off"), "b1_mldsa_44_cacheoff")

    def test_off_log_rows_and_checks(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "a.log")
            write_capture(p, "b1_mlkem_768_cacheoff", B1_OFF_LOG, label="board measured",
                          experiment="B1")
            r = parse.parse_log(p)
            self.assertEqual(r["n_unrecognised"], 0)
            self.assertEqual({x["cache_pass"] for x in r["rows"]}, {"off"})
            names = {c["check"]: (c["ok"], c["fail"]) for c in r["checks"]}
            self.assertEqual(names["cache_pass_off:image_matches_firmware"], (1, 0))
            self.assertEqual(names["cache_pass_off:writes_applied_at_zero_wait_states"], (1, 0))

    def test_mismatch_and_not_applied_fail(self):
        bad = [x.replace("cache_off_applied,1", "cache_off_applied,0") for x in B1_OFF_LOG]
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "a.log")
            write_capture(p, "b1_mlkem_768_cacheoff", bad, label="board measured", experiment="B1")
            names = {c["check"]: c["fail"] for c in parse.parse_log(p)["checks"]}
            self.assertEqual(names["cache_pass_off:writes_applied_at_zero_wait_states"], 1)
            p2 = os.path.join(d, "b.log")
            write_capture(p2, "b1_mlkem_768", B1_OFF_LOG, label="emulated", experiment="B1")
            names = {c["check"]: c["fail"] for c in parse.parse_log(p2)["checks"]}
            self.assertEqual(names["cache_pass_on:image_matches_firmware"], 1)

    def test_compare_keeps_passes_apart(self):
        rows = []
        for cp, ws in (("on", "0"), ("off", "0")):
            for x in res("board measured", exp="B1", variant="portable_c"):
                rows.append(dict(x, cache_pass=cp, flash_ws=ws))
        out = compare.compare(rows, EVID)
        self.assertEqual(len(out), 2)
        cond = {r["cache_pass"]: r["model_conditions"] for r in out}
        self.assertTrue(cond["off"].startswith("met"))
        self.assertTrue(cond["on"].startswith("not met"))


class EnergyTests(unittest.TestCase):
    def test_multimeter_and_analyzer(self):
        results = [dict(board="B", cache_pass="off", scheme="ML-KEM-768", operation="keygen",
                        cycles=c, clock_hz="20000000") for c in ("1000000", "1000000")]
        base = dict.fromkeys(parse.ENERGY_COLUMNS, "")
        mm = dict(base, board="B", cache_pass="off", scheme="ML-KEM-768", operation="keygen",
                  method="multimeter_phase", supply_v="3.3", current_ma_mean="10",
                  current_ma_idle="2")
        an = dict(base, method="analyzer_gpio_window", supply_v="3.3", charge_uc="100",
                  n_ops="10", window_s="0.5")
        nomatch = dict(mm, scheme="ML-KEM-512")
        out = parse.energy_rows([mm, an, nomatch], results)
        # 3.3 V x 10 mA x (1e6 / 2e7) s = 1650 uJ; net of idle: 3.3 x 8 mA x 0.05 s = 1320 uJ
        self.assertEqual(out[0]["energy_uj_per_op_board_measured"], "1650.000")
        self.assertEqual(out[0]["energy_uj_per_op_net_of_idle_board_measured"], "1320.000")
        self.assertEqual(out[1]["energy_uj_per_op_board_measured"], "33.000")
        self.assertEqual(out[2]["energy_uj_per_op_board_measured"], "")

    def test_read_energy_rejects_bad_files(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "e.csv")
            parse.write_energy_template(p)
            with self.assertRaises(ValueError):  # template method is a placeholder
                parse.read_energy(p)
            with open(p, "w") as fh:
                fh.write("label,board\nplanned,x\n")
            with self.assertRaises(ValueError):
                parse.read_energy(p)


OBJDUMP_OFF = """
080031cc <bench_cache_configure>:
 80031ce:\t4b0a      \tldr\tr3, [pc, #40]\t@ (80031f8 <bench_cache_configure+0x2c>)
 80031d0:\t6819      \tldr\tr1, [r3, #0]
 80031d8:\t681a      \tldr\tr2, [r3, #0]
 80031da:\tf422 62e0 \tbic.w\tr2, r2, #1792\t@ 0x700
 80031de:\t601a      \tstr\tr2, [r3, #0]
 80031f8:\t40022000 \t.word\t0x40022000
"""


class CacheOptionTests(unittest.TestCase):
    def test_find_clear_writes_synthetic(self):
        self.assertEqual(cache_check.find_clear_writes(OBJDUMP_OFF), [(0x40022000, 0x700)])
        self.assertEqual(cache_check.find_clear_writes(OBJDUMP_OFF.replace("bic.w", "orr.w")), [])

    @unittest.skipUnless(shutil.which("arm-none-eabi-gcc"), "arm-none-eabi-gcc not installed")
    def test_flag_symbol_compiled_in(self):
        """Compile b1_main.c for each pass and check the flag symbol with arm-none-eabi-nm."""
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "hal.h"), "w") as fh:
                fh.write("#include <stdint.h>\nenum clock_mode { CLOCK_FAST, CLOCK_BENCHMARK };\n"
                         "void hal_setup(const enum clock_mode c);\n"
                         "void hal_send_str(const char *s);\nuint64_t hal_get_time(void);\n")
            harness = os.path.join(os.path.dirname(KIT), "mcu", "src")
            syms = {}
            for cp in K.CACHE_PASSES:
                o = os.path.join(d, f"{cp}.o")
                flags = ["-DBENCH_CACHE_OFF"] if cp == "off" else []
                subprocess.run(["arm-none-eabi-gcc", "-mcpu=cortex-m4", "-mthumb", "-O2", "-c",
                                f"-I{d}", f"-I{harness}", "-o", o] + flags +
                               [os.path.join(KIT, "b1", "b1_main.c")], check=True)
                syms[cp] = cache_check.symbols(o)
            self.assertIn("bench_cache_off_compiled", syms["off"])
            self.assertNotIn("bench_cache_off_compiled", syms["on"])
            self.assertIn("bench_cache_configure", syms["off"])

    def test_built_images_carry_the_writes(self):
        """Every built image: caches off images clear the bits, caches on images do not."""
        found = 0
        for platform in cache_check.EXPECTED:
            for elf in glob.glob(os.path.join(K.OUT_DIR, platform, "b1", "b1_*.elf")):
                expect = "off" if elf.endswith("_cacheoff.elf") else "on"
                ok, d = cache_check.check(elf, platform, expect)
                self.assertTrue(ok, (elf, d))
                found += 1
        if not found:
            self.skipTest("no board kit images built under BOARD_KIT_WORK")

    def test_renode_log_parser(self):
        txt = ("12:00 [WARNING] sysbus: [cpu: 0x800030C] WriteDoubleWord to non existing "
               "peripheral at 0x40030400, value 0x0.\n12:00 [WARNING] sysbus: [cpu: 0x80002FC] "
               "ReadDoubleWord from non existing peripheral at 0x40022000.\n")
        w = renode_check.parse_log(txt)
        self.assertEqual(w[0x40030400], [(0x800030C, 0)])
        self.assertEqual(w[0x40022000], [])

    def test_register_addresses_match_headers(self):
        ra = session_plan.register_addresses_cmsis()
        if not ra:
            self.skipTest("CMSIS headers not fetched")
        for platform, regs in ra.items():
            self.assertEqual(regs["FLASH_ACR"], K.FLASH_ACR_ADDR[platform])
            if "ICACHE_CR" in regs:
                self.assertEqual(regs["ICACHE_CR"], K.ICACHE_CR_ADDR[platform])


class SessionPlanV5Tests(unittest.TestCase):
    def pub(self):
        pub = {}
        for s in ("ML-KEM-512", "ML-KEM-768", "ML-KEM-1024", "ML-DSA-44", "ML-DSA-65", "ML-DSA-87"):
            for v in ("clean", "m4fspeed", "m4f"):
                for op in ("keygen", "encaps", "decaps", "sign", "verify"):
                    pub[(s, v, op)] = (1_000_000.0, "id")
        return pub

    def test_b1_items_passes_and_m33_iterations(self):
        off = session_plan.b1_items(self.pub(), K.M33_PLATFORM, "off")
        self.assertTrue(all(i[1].endswith("_cacheoff") for i in off))
        self.assertTrue(all(i[6] == K.B1_ITERS_M33["mlkem"] for i in off if "mlkem" in i[1]))

    def test_afternoon_split(self):
        rows = [{"block": "a", "total_s": 3600}, {"block": "b", "total_s": 3600},
                {"block": "c", "total_s": 3000}, {"block": "d", "total_s": 900}]
        inside, outside = session_plan.afternoon(rows, 180)
        self.assertEqual([b for b, _, _ in inside], ["a", "b", "c"])
        self.assertEqual([b for b, _ in outside], ["d"])  # blocks stay in order

    def test_plan_has_both_passes_and_boards(self):
        with tempfile.TemporaryDirectory() as d:
            ev = compare.read_csv(compare.EVIDENCE)
            rows = session_plan.plan(ev, d, 20.0, 30.0, 900.0)
            blocks = {r["block"] for r in rows}
            for b in ("nucleo-l4r5zi B1 off", "nucleo-l4r5zi B1 on", "nucleo-l552ze-q B1 off",
                      "nucleo-l552ze-q B1 on", "nucleo-l4r5zi energy"):
                self.assertIn(b, blocks)
            self.assertTrue(all(r["label"] == "estimated" for r in rows))


class PredictionsV5Tests(unittest.TestCase):
    def test_rows_follow_round4_csv(self):
        res = os.path.join(os.path.dirname(os.path.dirname(KIT)), "cyclemodel", "results")
        bp = predictions_v5.read(os.path.join(res, "board_predictions.csv"))
        rows = predictions_v5.build_rows(bp, predictions_v5.read(os.path.join(res, "split.csv")))
        harness = [r for r in bp if r["target"] == "harness (bench/mcu)"]
        self.assertEqual(len(rows), 2 * len(harness))
        self.assertEqual(len({r["id"] for r in rows}), len(rows))
        by = {(r["parameter_set"], r["operation"]): r for r in harness}
        for r in rows:
            src = by[(r["parameter_set"], r["operation"])]
            self.assertEqual(r["interval_lo_modelled"], src["pi95_envelope_lo_modelled"])
            self.assertEqual(r["cycles_modelled"], src["cycles_modelled"])
            self.assertEqual(r["in_sample"], "no")
            self.assertEqual(r["label"], "modelled")

    def test_registered_file_hash(self):
        repo = os.path.dirname(os.path.dirname(KIT))
        md = os.path.join(repo, "docs", "PREDICTIONS_V5_BOARD.md")
        sha = md + ".sha256"
        if not os.path.exists(sha):
            self.skipTest("hash not written yet")
        import hashlib
        want = open(sha).read().split()[0]
        self.assertEqual(hashlib.sha256(open(md, "rb").read()).hexdigest(), want)


if __name__ == "__main__":
    unittest.main()
