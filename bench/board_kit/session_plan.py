#!/usr/bin/env python3
"""Estimate the board session time and write session_plan.csv and the one page CHECKLIST.md.

Author: Huda Mueen. Label of every time in both files: estimated (planned session, no board run).
Run time per image = (published mean cycles per operation x iterations) / clock + UART time.
  * Cycles: pqm4 rows of data/evidence.csv (published). For B1 (mlkem-native, mldsa-native) the
    pqm4 clean row of the same parameter set is used as a stand in; real B1 cycles are unknown.
  * Clock: 20 MHz, pqm4's benchmark clock for nucleo-l4r5zi in common/hal-opencm3.c at the pin
    (data/raw/S6_pqm4_config.md); B1 reads the real value back at the board.
  * UART: bytes per log from the emulated dry run logs (same text format), at 38400 baud and 10
    bits per byte (8N1); the board waits for each byte, so UART time adds to run time.
  * Handling: ASSUMED values (no source), stated in the CSV: flash per image, power cycle per run,
    fixed set up time. Change them with the command line options.
"""
import argparse
import csv
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kit_config as K  # noqa: E402
import compare  # noqa: E402
import parse  # noqa: E402

CLOCK_HZ = 20_000_000  # nucleo-l4r5zi; nucleo-l552ze-q runs at its 4 MHz reset clock (CLOCKS)
BAUD = 38400
BITS_PER_BYTE = 10
TEST_FACTOR = 30  # rough: pqm4 test binaries repeat each operation of the order of tens of times
OPS = {"kem": ["keygen", "encaps", "decaps"], "sign": ["keygen", "sign", "verify"]}
PLAN_COLUMNS = ["label", "step", "block", "board", "platform", "cache_pass", "experiment", "image",
                "scheme", "variant", "kind", "runs", "clock_hz",
                "iterations", "cycles_source", "compute_s_per_run", "uart_s_per_run",
                "flash_s", "handling_s", "total_s"]


def uart_bytes(logdir):
    """Mean bytes of board output per image name, from emulated dry run logs."""
    sizes = {}
    for p in glob.glob(os.path.join(logdir, "run*_*.log")):
        name = re.sub(r"^run\d+_", "", os.path.basename(p))[:-4]
        n = 0
        with open(p) as fh:
            for line in fh:
                if not line.startswith("# capture"):
                    n += len(line.split("\t", 1)[1])
        sizes.setdefault(name, []).append(n)
    return {k: sum(v) / len(v) for k, v in sizes.items()}


def published_cycles(evidence):
    idx = compare.published_index(evidence)
    return {k: (float(v["cycles"]), v["id"]) for k, v in idx.items()}


def b0_items(pub):
    items = []
    for scheme, variant, path, _ in K.B0_VARIANTS:
        kind_ops = OPS["kem"] if "kem" in path else OPS["sign"]
        per_iter = sum(pub[(scheme.upper(), variant, op)][0] for op in kind_ops)
        ids = "+".join(pub[(scheme.upper(), variant, op)][1] for op in kind_ops)
        it = K.ITERATIONS[scheme]
        for kind in K.B0_KINDS:
            name = f"{path.replace('/', '_')}_{kind}"
            runs = 3 if kind == "speed" else 1
            mult = {"speed": it, "stack": 1, "test": TEST_FACTOR}[kind]
            items.append(("B0", name, scheme.upper(), variant, kind, runs, mult, per_iter * mult,
                          f"published {ids}"))
    return items


CLOCKS = {"nucleo-l4r5zi": 20_000_000, K.M33_PLATFORM: 4_000_000}
BOARDS = {"nucleo-l4r5zi": "NUCLEO-L4R5ZI (Cortex-M4)", K.M33_PLATFORM: "NUCLEO-L552ZE-Q (Cortex-M33)"}
# Block order of the session (round 5): the caches off pass on the Cortex-M4 board first (the
# primary test of the cycle model), then its caches on pass and the energy runs, then the
# Cortex-M33 board, and the B0 reproduction of published pqm4 rows last.
BLOCKS = [("nucleo-l4r5zi", "setup"), ("nucleo-l4r5zi", "B1 off"), ("nucleo-l4r5zi", "B1 on"),
          ("nucleo-l4r5zi", "energy"), (K.M33_PLATFORM, "setup"), (K.M33_PLATFORM, "B1 off"),
          (K.M33_PLATFORM, "B1 on"), ("nucleo-l4r5zi", "B0")]
ENERGY_IMAGES = [("mlkem", 768), ("mldsa", 44)]


def b1_items(pub, platform="nucleo-l4r5zi", cache_pass="on"):
    items = []
    iters_tab = K.B1_ITERS_M33 if platform == K.M33_PLATFORM else K.B1_ITERS
    for alg, pset in K.B1_SETS:
        scheme = f"ML-KEM-{pset}" if alg == "mlkem" else f"ML-DSA-{pset}"
        ops = OPS["kem"] if alg == "mlkem" else OPS["sign"]
        per_iter = sum(pub[(scheme, "clean", op)][0] for op in ops)
        ids = "+".join(pub[(scheme, "clean", op)][1] for op in ops)
        it = iters_tab[alg]
        items.append(("B1", K.image_base(alg, pset, cache_pass), scheme, "portable_c", "harness",
                      3, it, per_iter * it, f"stand in: pqm4 clean {ids}"))
    return items


def _row(rows, board, platform, cache_pass, block, exp, image, scheme, variant, kind, runs, it,
         src, compute, uart, flash_s, handling):
    total = float(flash_s or 0) + (runs or 0) * (compute + uart) + handling
    rows.append({"label": "estimated", "step": len(rows) + 1, "block": block, "board": board,
                 "platform": platform, "cache_pass": cache_pass, "experiment": exp,
                 "image": image, "scheme": scheme, "variant": variant, "kind": kind,
                 "runs": runs, "iterations": it, "cycles_source": src,
                 "clock_hz": CLOCKS.get(platform, ""),
                 "compute_s_per_run": round(compute, 1) if runs else "",
                 "uart_s_per_run": round(uart, 1) if runs else "", "flash_s": flash_s,
                 "handling_s": handling, "total_s": round(total, 1)})


def plan(evidence, logdir, flash_s, power_s, setup_s, swap_s=600.0, energy_wiring_s=600.0):
    pub = published_cycles(evidence)
    ub = uart_bytes(logdir)
    rows = []
    for platform, block in BLOCKS:
        board = BOARDS[platform]
        clock = CLOCKS[platform]
        if block == "setup":
            _row(rows, board, platform, "", f"{platform} {block}", "both",
                 "set up, board check, counter check, wiring" if platform == "nucleo-l4r5zi"
                 else "board swap, set up, board check, counter check", "", "", "", "", "",
                 "assumed", 0.0, 0.0, "", setup_s if platform == "nucleo-l4r5zi" else swap_s)
            continue
        if block == "B0":
            items = [(i, "on") for i in b0_items(pub)]
        elif block == "energy":
            items = []
            for alg, pset in ENERGY_IMAGES:
                for it in b1_items(pub, platform, "off"):
                    if it[1] == K.image_base(alg, pset, "off"):
                        items.append(((it[0], it[1], it[2], it[3], "energy", 1, it[6], it[7],
                                       it[8]), "off"))
        else:
            cp = block.split()[1]
            items = [(i, cp) for i in b1_items(pub, platform, cp)]
        for (exp, name, scheme, variant, kind, runs, it, cyc, src), cp in items:
            compute = cyc / clock
            base = name.replace(K.CACHE_SUFFIX["off"], "")
            iters_logged = K.B1_ITERS[name.split("_")[1]] if exp == "B1" else it
            uart = ub.get(name, ub.get(base, 0.0)) * (it / iters_logged if exp == "B1" else 1.0)
            uart = uart * BITS_PER_BYTE / BAUD
            _row(rows, board, platform, cp, f"{platform} {block}", exp, name, scheme, variant,
                 kind, runs, it, src, compute, uart, flash_s, power_s * runs)
        if block == "energy":
            rows[-1]["handling_s"] += energy_wiring_s
            rows[-1]["total_s"] = round(rows[-1]["total_s"] + energy_wiring_s, 1)
    return rows


def _pqm4_with_libopencm3():
    for d in (K.PQM4_DIR, os.path.join(K.WORK, "pqm4_b1")):
        if os.path.isdir(os.path.join(d, "libopencm3", "include")):
            return d
    return K.PQM4_DIR


def register_addresses_cmsis(libs=K.LIBS_DIR):
    """FLASH_ACR and ICACHE_CR addresses from the pinned vendor CMSIS headers (None if absent)."""
    out = {}
    for platform, rel, names in (
            ("nucleo-l4r5zi", ("cmsis_device_l4", "Include", "stm32l4r5xx.h"),
             ("PERIPH_BASE", "AHB1PERIPH_BASE", "FLASH_R_BASE")),
            (K.M33_PLATFORM, ("cmsis_device_l5", "Include", "stm32l552xx.h"),
             ("PERIPH_BASE_NS", "AHB1PERIPH_BASE_NS", "FLASH_R_BASE_NS", "ICACHE_BASE_NS"))):
        path = os.path.join(libs, *rel)
        if not os.path.exists(path):
            continue
        defs = {}
        with open(path) as fh:
            for line in fh:
                m = re.match(r"#define\s+(\w+)\s+\(([^)]*)\)", line)
                if m and m.group(1) in names:
                    defs.setdefault(m.group(1), m.group(2))
        vals = {}
        for n in names:
            expr = re.sub(r"(0x[0-9A-Fa-f]+)UL", r"\1", defs[n])
            for k, v in vals.items():
                expr = re.sub(rf"\b{k}\b", str(v), expr)
            vals[n] = eval(expr, {"__builtins__": {}})
        out[platform] = {"FLASH_ACR": vals[names[2]]}  # FLASH_ACR is at offset 0
        if len(names) > 3:
            out[platform]["ICACHE_CR"] = vals[names[3]]  # ICACHE_CR is at offset 0
    return out


def register_addresses(pqm4=None):
    """FLASH_ACR, RCC_CFGR and RCC_PLLCFGR addresses for STM32L4 from the pinned libopencm3."""
    pqm4 = pqm4 or _pqm4_with_libopencm3()
    inc = os.path.join(pqm4, "libopencm3", "include", "libopencm3", "stm32", "l4")
    defs = {}
    for f in ("memorymap.h", "rcc.h", "flash.h"):
        with open(os.path.join(inc, f)) as fh:
            for line in fh:
                m = re.match(r"#define\s+(PERIPH_BASE_AHB1|PERIPH_BASE|RCC_BASE|"
                             r"FLASH_MEM_INTERFACE_BASE|RCC_CFGR|RCC_PLLCFGR|FLASH_ACR)\s+(.*)",
                             line)
                if m:
                    defs.setdefault(m.group(1), m.group(2).split("/*")[0].strip())

    def ev(expr):
        expr = re.sub(r"MMIO32\((.*)\)", r"\1", expr).replace("U)", ")")
        for k in sorted(defs, key=len, reverse=True):
            expr = re.sub(rf"\b{k}\b", f"({defs[k]})", expr)
        for _ in range(5):
            expr = re.sub(r"MMIO32\((.*)\)", r"\1", expr)
            for k in sorted(defs, key=len, reverse=True):
                expr = re.sub(rf"\b{k}\b", f"({defs[k]})", expr)
        return eval(re.sub(r"(0x[0-9A-Fa-f]+)U", r"\1", expr), {"__builtins__": {}})

    return {k: ev(defs[k]) for k in ("FLASH_ACR", "RCC_CFGR", "RCC_PLLCFGR")}


def minutes(rows, pred=lambda r: True):
    return sum(float(r["total_s"]) for r in rows if pred(r)) / 60


def write_checklist(path, rows, flash_s, power_s, setup_s, has_uart):
    ra = register_addresses()
    tot = minutes(rows)
    blk = {}
    for r in rows:
        blk.setdefault(r["block"], 0.0)
        blk[r["block"]] += float(r["total_s"]) / 60
    worst = max((r for r in rows if r["runs"]), key=lambda r: float(r["total_s"]))
    L = [
        "# Board session checklist (NUCLEO-L4R5ZI and NUCLEO-L552ZE-Q; B0, B1, both cache passes)",
        "",
        "Author: Huda Mueen. Status: **planned**. Generated by `bench/board_kit/session_plan.py`. "
        f"Estimated length of every block together (label estimated): **{tot:.0f} minutes**; "
        "`ONE_AFTERNOON.md` orders the blocks and keeps those that fit in three hours. "
        f"Longest step {worst['image']} at {float(worst['total_s']) / 60:.0f} minutes. Assumed, "
        f"not sourced: {flash_s} s per flash, {power_s} s per power cycle, set up and board swap "
        "times. Cycle inputs: published pqm4 means; B1 uses pqm4 clean as a stand in; clocks: "
        "20 MHz (nucleo-l4r5zi, pqm4 benchmark clock), 4 MHz (nucleo-l552ze-q, reset clock). "
        "Details: `session_plan.csv`." + ("" if has_uart else " UART time not included (no dry "
                                            "run logs found)."), "",
        "| Block | Minutes (estimated) |", "|---|---|"]
    L += [f"| {b} | {m:.0f} |" for b, m in blk.items()]
    L += [
        "", "## Before the session (at home)", "",
        "1. `python3 bench/board_kit/build_b0.py --platform nucleo-l4r5zi`, "
        "`python3 bench/board_kit/build_b1.py --platform nucleo-l4r5zi --cache both` and "
        "`python3 bench/board_kit/build_b1.py --platform nucleo-l552ze-q --cache both` (all clone "
        "at the pins outside the repository and stop on a commit mismatch). Then "
        "`make_build_log.py`.",
        "2. Check that the caches off option is compiled in: `python3 bench/board_kit/cache_check.py "
        "<elf> --platform <platform> --expect off` on every `_cacheoff` image and `--expect on` on "
        "the others (the unit tests do this for every image found).",
        "3. Dry run: `build_b0.py` and `build_b1.py --cache both` with `--platform mps2-an386`, then "
        "`run_dry_run.py`; it must report 0 unrecognised lines and 0 failed checks for both passes.",
        "4. Install a free flash tool: OpenOCD (pqm4 uses `openocd -f st_nucleo_l4r5.cfg -c "
        "\"program <image>.hex verify reset exit\"`; for the L552 board use OpenOCD's "
        "`board/st_nucleo_l5.cfg` if the installed OpenOCD has it, else STM32CubeProgrammer's free "
        "command line tool) or `st-flash`; install pyserial. No vendor login.",
        "5. Copy `$WORK/board_kit_out/` and the pqm4 clone to the laptop; record "
        "`arm-none-eabi-gcc --version` and the repository commit.", "",
        "## At each board", "",
        "1. Record board name, chip marking and ST-LINK firmware version. The ST-LINK virtual COM "
        "port carries LPUART1 at 38400 baud on both boards (pqm4 setting; UM2581 for the L552 "
        "board).",
        "2. Board check first: flash `b1_mlkem_512_cacheoff.hex`. Its META lines give "
        "`cache_pass` (off), `cache_off_applied` (must be 1), the clock (`clock_hz_rcc`), "
        "`flash_ws` (must be 0) and `cache` (all enable bits 0), and the counter check "
        "(`counter_dwt_cycles` against `counter_systick_cycles`). Stop if the counters disagree. "
        "Then flash `b1_mlkem_512.hex` and check that `cache` shows the enable bits set.",
        f"3. Optional cross check with OpenOCD on nucleo-l4r5zi: `mdw {ra['FLASH_ACR']:#010x}` "
        f"(FLASH_ACR), `mdw {ra['RCC_CFGR']:#010x}` (RCC_CFGR), `mdw {ra['RCC_PLLCFGR']:#010x}` "
        f"(RCC_PLLCFGR); on nucleo-l552ze-q `mdw {K.FLASH_ACR_ADDR[K.M33_PLATFORM]:#010x}` "
        f"(FLASH_ACR) and `mdw {K.ICACHE_CR_ADDR[K.M33_PLATFORM]:#010x}` (ICACHE_CR); addresses "
        "from the pinned libopencm3 and CMSIS headers.",
        "4. Pass the read back values to `parse.py` for B0 (`--clock-hz --flash-ws --cache "
        "--toolchain --commit`).", "",
        "## Runs", "",
        "1. Start `capture.py --port <port> --board <NUCLEO-L4R5ZI|NUCLEO-L552ZE-Q> --run <n> --image <name> --experiment B0|B1 "
        "--label \"board measured\" --out <log>` before each flash or reset; it stops at `#`.",
        "2. Harness images (B1, both passes) and speed images (B0): flash once, then 3 power "
        "cycles, one capture per power cycle with `--run 1`, `2`, `3`. Iterations per run: B1 "
        f"{K.B1_ITERS['mlkem']} on nucleo-l4r5zi and {K.B1_ITERS_M33['mlkem']} on nucleo-l552ze-q "
        "(its clock is five times lower); B0 ML-KEM-768 100 and ML-DSA-44 1000.",
        "3. Test and stack images: one run each. Any line starting `ERROR` stops the session.",
        "4. Energy (`docs/BOARD_RUN_PROTOCOL.md` section 10): with the ammeter in place of the IDD "
        "jumper, one more run of the caches off images of the energy block; write one row per "
        "operation phase into a copy of `ENERGY_TEMPLATE.csv`.",
        "5. Keep every raw log; never edit one.", "",
        "## After", "",
        "1. `parse.py <logs> --out board.csv --checks-out checks.csv --require-all "
        "[--energy energy.csv]` (exit 0 needed; the caches off check fails if a caches off image "
        "did not apply its writes).",
        "2. `compare.py board.csv --checks checks.csv --out compare.csv`: groups are kept apart by board and cache "
        "pass; `model_conditions` says which rows meet the model's conditions. Score "
        "`docs/PREDICTIONS_V5_BOARD.md` with `score_v5_board.py board.csv --checks checks.csv "
        "--out score_v5_board.csv` (caches off rows only, rules 1 to 4 per board).",
        "3. Report board measured numbers in their own table, labelled board measured, with "
        "board, clock, flash wait states, cache bits, cache pass, toolchain and commit. Never merge "
        "them into published, emulated or modelled columns. Copy logs and commands to "
        "`bench/mcu/board_results/<date>/` (`ONE_AFTERNOON.md` gives the commands).", ""]
    with open(path, "w") as fh:
        fh.write("\n".join(L))
    return tot


def afternoon(rows, limit_min=180.0):
    """Split the blocks, in BLOCKS order, into those that fit within limit_min and the rest."""
    order = []
    for r in rows:
        if r["block"] not in order:
            order.append(r["block"])
    inside, outside, cum = [], [], 0.0
    for b in order:
        m = minutes(rows, lambda r, b=b: r["block"] == b)
        if not outside and cum + m <= limit_min:
            cum += m
            inside.append((b, m, cum))
        else:
            outside.append((b, m))
    return inside, outside


STEP_TEXT = {
    "setup": ("Set up the board: plug the NUCLEO into the laptop by USB and find its serial port "
              "(`/dev/ttyACM0` or similar on Linux, a COM port on Windows). Board check, once per "
              "image: start `python3 bench/board_kit/capture.py --port <port> --baud 38400 "
              "--board {board} --run 0 --image b1_mlkem_512_cacheoff --experiment B1 --label "
              "\"board measured\" --echo --out results/<date>/{platform}/check/"
              "run0_b1_mlkem_512_cacheoff.log`, then flash `b1_mlkem_512_cacheoff.hex` (the flash "
              "tool resets the board, so the capture records from the first line); then the same "
              "for `b1_mlkem_512.hex` with `--image b1_mlkem_512` and the file name "
              "`run0_b1_mlkem_512.log`. The check logs stay in `check/`, outside the cycle runs.",
              "META lines with `cache_pass,off`, `cache_off_applied,1`, `flash_ws,0` and all "
              "cache bits 0, then `cache_pass,on` with the enable bits set; "
              "`counter_dwt_cycles` close to `counter_systick_cycles`."),
    "B1 off": ("Caches off pass: for each `b1_*_cacheoff.hex` image, flash once and capture three "
               "power cycles (`--run 1`, `2`, `3`).",
               "Each log ends with `#`; BENCH lines with cycles; CHECK lines with 0 failures."),
    "B1 on": ("Caches on pass: the same for each `b1_*.hex` image without the suffix.",
              "As above, with `cache_pass,on`."),
    "energy": ("Energy: remove the IDD jumper and connect the ammeter in its place. Idle current "
               "first, one method only: hold the board's reset button down, let the meter average "
               "for 10 s, and write that value into `current_ma_idle` of every row of this board. "
               "Then rerun the listed caches off images once with `--echo`. The capture prints "
               "each line as it arrives, and an operation's phase runs while its BENCH lines (for "
               "example `BENCH,ML-KEM,ML-KEM-512,encaps,...`) scroll: restart the meter's average "
               "(its MIN, MAX and AVG mode) at the first BENCH line of an operation and read it at "
               "the first BENCH line of the next operation, or at the STACK lines after the last "
               "one. Write one row per operation phase into a copy of `ENERGY_TEMPLATE.csv` "
               "(results/<date>/energy.csv). The energy logs stay in their own folder: parse.py "
               "joins them through the cycles of the caches off pass, so they are not parsed as "
               "extra cycle runs.",
               "One row per operation phase with supply voltage, mean current and idle current."),
    "B0": ("B0 reproduction of published pqm4 rows: test, speed and stack images of "
           "`build_b0.py`.", "Test images print OK lines; speed images print cycles per "
           "operation; stack images print stack usage."),
}


def write_one_afternoon(path, rows, limit_min=180.0):
    inside, outside = afternoon(rows, limit_min)
    imgs = {}
    for r in rows:
        if r["runs"]:
            imgs.setdefault(r["block"], []).append(r["image"])
    L = ["# One afternoon at the bench (plan for the person at the bench)", "",
         "Author: Huda Mueen. Status: **planned**. Generated by `bench/board_kit/session_plan.py` "
         "from `session_plan.csv`; every time below is estimated (published cycle counts as stand "
         f"ins, assumed handling times). The plan keeps whole blocks, in order, while the total "
         f"stays within {limit_min:.0f} minutes. Commands assume a shell in the repository "
         "clone with the images under `$WORK/board_kit_out/` (built at home, `CHECKLIST.md`).", "",
         "## What to bring", "",
         "1. NUCLEO-L4R5ZI and, if the second block fits, NUCLEO-L552ZE-Q, each with a USB cable.",
         "2. A laptop with OpenOCD or st-flash, Python 3 with pyserial, and the repository clone.",
         "3. For the energy block: a multimeter with a mA range and two leads with jumper sockets, "
         "or a lab power analyzer.", "",
         "## Steps", ""]
    n = 0
    for b, m, cum in inside:
        platform, kind = b.split(" ", 1)
        txt, expect = STEP_TEXT[kind]
        txt = txt.replace("{board}", K.BOARD_NAMES[platform]).replace("{platform}", platform)
        n += 1
        L.append(f"{n}. **{b}** ({m:.0f} minutes, {cum:.0f} minutes so far). {txt}")
        if kind not in ("setup",):
            L.append(f"   Images: {', '.join('`' + i + '`' for i in imgs.get(b, []))}.")
            L.append("   Flash each image with the tool tested at home (`CHECKLIST.md`, before the "
                     "session, step 4).")
            if kind == "energy":
                L.append("   Command per image (one run): `python3 bench/board_kit/capture.py "
                         f"--port <port> --baud 38400 --board {K.BOARD_NAMES[platform]} --run 1 "
                         "--image <image> --experiment B1 --echo "
                         "--label \"board measured\" --out results/<date>/" + platform +
                         "/energy/run1_<image>.log`.")
            else:
                L.append("   Command per image and power cycle: `python3 bench/board_kit/capture.py "
                         f"--port <port> --baud 38400 --board {K.BOARD_NAMES[platform]} "
                         "--run <1|2|3> --image <image> --experiment "
                         f"{'B0' if kind == 'B0' else 'B1'} --label \"board measured\" "
                         "--out results/<date>/" + platform + "/run<n>_<image>.log`.")
        L.append(f"   Expected: {expect}")
    n += 1
    L += [f"{n}. **Parse and check** (on the laptop, a few minutes). "
          "`python3 bench/board_kit/parse.py results/<date>/*/*.log --out results/<date>/board.csv "
          "--checks-out results/<date>/checks.csv --meta-out results/<date>/meta.csv --require-all "
          "--energy results/<date>/energy.csv`.",
          "   Expected: a last line with `unrecognised=0` and `failed_checks=0`; exit code 0.",
          f"{n + 1}. **Compare** `python3 bench/board_kit/compare.py results/<date>/board.csv "
          "--checks results/<date>/checks.csv --out results/<date>/compare.csv`.",
          "   Expected: groups with `cycles_status` compared and `model_conditions` met for the "
          "caches off rows, one group per board (the two boards never share a group).",
          f"{n + 2}. **Score the registered predictions** `python3 bench/board_kit/score_v5_board.py "
          "results/<date>/board.csv --checks results/<date>/checks.csv --out "
          "results/<date>/score_v5_board.csv`.",
          "   Expected: one verdict per row of `docs/PREDICTIONS_V5_BOARD.md` and the verdict of "
          "refutation rules 1 to 4 for each board.",
          f"{n + 3}. **Send the results back** (the author commits and pushes; the person at the "
          "bench hands over the folder):",
          "   ```",
          "   mkdir -p bench/mcu/board_results/<date>",
          "   cp -r results/<date>/* bench/mcu/board_results/<date>/",
          "   git add bench/mcu/board_results/<date>",
          "   git commit -m \"Add board measured B1 logs from <date> (both cache passes)\"",
          "   git push",
          "   ```", ""]
    if outside:
        L += ["## Not in this afternoon (a second session)", ""]
        L += [f"- {b}: {m:.0f} minutes (estimated)." for b, m in outside]
        L.append("")
    total_in = inside[-1][2] if inside else 0.0
    L += [f"Total of the steps kept: {total_in:.0f} minutes (estimated).", ""]
    with open(path, "w") as fh:
        fh.write("\n".join(L))
    return total_in, outside


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--flash-s", type=float, default=20.0, help="assumed seconds per flash")
    ap.add_argument("--power-s", type=float, default=30.0, help="assumed seconds per power cycle")
    ap.add_argument("--setup-s", type=float, default=900.0, help="assumed set up seconds")
    ap.add_argument("--swap-s", type=float, default=600.0, help="assumed board swap seconds")
    ap.add_argument("--energy-wiring-s", type=float, default=600.0,
                    help="assumed seconds to fit the ammeter")
    ap.add_argument("--limit-min", type=float, default=180.0)
    ap.add_argument("--logdir", default=os.path.join(K.OUT_DIR, "dry_run"))
    a = ap.parse_args(argv)
    rows = plan(compare.read_csv(compare.EVIDENCE), a.logdir, a.flash_s, a.power_s, a.setup_s,
                a.swap_s, a.energy_wiring_s)
    with open(os.path.join(HERE, "session_plan.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=PLAN_COLUMNS)
        w.writeheader()
        w.writerows(rows)
    has_uart = bool(uart_bytes(a.logdir))
    tot = write_checklist(os.path.join(HERE, "CHECKLIST.md"), rows, a.flash_s, a.power_s,
                          a.setup_s, has_uart)
    kept, outside = write_one_afternoon(os.path.join(HERE, "ONE_AFTERNOON.md"), rows, a.limit_min)
    parse.write_template(os.path.join(HERE, "RESULT_TEMPLATE.csv"))
    parse.write_energy_template(os.path.join(HERE, "ENERGY_TEMPLATE.csv"))
    print(f"estimated minutes, all blocks: {tot:.1f}; kept in one afternoon: {kept:.1f}; "
          f"left for a second session: {', '.join(b for b, _ in outside) or 'none'}")


if __name__ == "__main__":
    main()
