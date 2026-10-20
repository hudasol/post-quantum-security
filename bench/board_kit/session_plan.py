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

CLOCK_HZ = 20_000_000
BAUD = 38400
BITS_PER_BYTE = 10
TEST_FACTOR = 30  # rough: pqm4 test binaries repeat each operation of the order of tens of times
OPS = {"kem": ["keygen", "encaps", "decaps"], "sign": ["keygen", "sign", "verify"]}
PLAN_COLUMNS = ["label", "step", "experiment", "image", "scheme", "variant", "kind", "runs",
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


def b1_items(pub):
    items = []
    for alg, pset in K.B1_SETS:
        scheme = f"ML-KEM-{pset}" if alg == "mlkem" else f"ML-DSA-{pset}"
        ops = OPS["kem"] if alg == "mlkem" else OPS["sign"]
        per_iter = sum(pub[(scheme, "clean", op)][0] for op in ops)
        ids = "+".join(pub[(scheme, "clean", op)][1] for op in ops)
        it = K.B1_ITERS[alg]
        items.append(("B1", f"b1_{alg}_{pset}", scheme, "portable_c", "harness", 3, it,
                      per_iter * it, f"stand in: pqm4 clean {ids}"))
    return items


def plan(evidence, logdir, flash_s, power_s, setup_s):
    pub = published_cycles(evidence)
    ub = uart_bytes(logdir)
    rows = []
    for exp, name, scheme, variant, kind, runs, it, cyc, src in b0_items(pub) + b1_items(pub):
        compute = cyc / CLOCK_HZ
        uart = ub.get(name, 0.0) * BITS_PER_BYTE / BAUD
        handling = power_s * runs
        total = flash_s + runs * (compute + uart) + handling
        rows.append({"label": "estimated", "step": len(rows) + 1, "experiment": exp, "image": name,
                     "scheme": scheme, "variant": variant, "kind": kind, "runs": runs,
                     "iterations": it, "cycles_source": src,
                     "compute_s_per_run": round(compute, 1), "uart_s_per_run": round(uart, 1),
                     "flash_s": flash_s, "handling_s": handling, "total_s": round(total, 1)})
    rows.append({"label": "estimated (assumed)", "step": len(rows) + 1, "experiment": "both",
                 "image": "set up, counter check, wiring", "scheme": "", "variant": "", "kind": "",
                 "runs": "", "iterations": "", "cycles_source": "assumed",
                 "compute_s_per_run": "", "uart_s_per_run": "", "flash_s": "", "handling_s": setup_s,
                 "total_s": setup_s})
    return rows


def register_addresses(pqm4=K.PQM4_DIR):
    """FLASH_ACR, RCC_CFGR and RCC_PLLCFGR addresses for STM32L4 from the pinned libopencm3."""
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


def write_checklist(path, rows, flash_s, power_s, setup_s, has_uart):
    ra = register_addresses()
    tot = sum(float(r["total_s"]) for r in rows) / 60
    b0 = sum(float(r["total_s"]) for r in rows if r["experiment"] == "B0") / 60
    b1 = sum(float(r["total_s"]) for r in rows if r["experiment"] == "B1") / 60
    worst = max((r for r in rows if r["experiment"] != "both"), key=lambda r: float(r["total_s"]))
    L = [
        "# Board session checklist (NUCLEO-L4R5ZI, B0 and B1)", "",
        "Author: Huda Mueen. Status: **planned**. Generated by `bench/board_kit/session_plan.py`. "
        f"Estimated session length (label estimated): **{tot:.0f} minutes** (B0 {b0:.0f}, B1 {b1:.0f}, "
        f"set up {setup_s / 60:.0f}); longest step {worst['image']} at {float(worst['total_s']) / 60:.0f} "
        f"minutes. Assumed, not sourced: {flash_s} s per flash, {power_s} s per power cycle. "
        "Cycle inputs: published pqm4 means at 20 MHz; B1 uses pqm4 clean as a stand in. "
        "Details: `session_plan.csv`." + ("" if has_uart else " UART time not included (no dry "
                                            "run logs found)."), "",
        "## Before the session (at home)", "",
        "1. `python3 bench/board_kit/build_b0.py --platform nucleo-l4r5zi` and "
        "`python3 bench/board_kit/build_b1.py --platform nucleo-l4r5zi` (both clone at the pins "
        "outside the repository and stop on a commit mismatch). Then `make_build_log.py`.",
        "2. Dry run: `build_b0.py` and `build_b1.py` with `--platform mps2-an386`, then "
        "`run_dry_run.py`; it must report 0 unrecognised lines and 0 failed checks.",
        "3. Install a free flash tool: OpenOCD (pqm4 uses `openocd -f st_nucleo_l4r5.cfg -c "
        "\"program <image>.hex verify reset exit\"`) or `st-flash`; install pyserial. No vendor "
        "login. Write and hash the prediction file (protocol section 9).",
        "4. Copy `$WORK/board_kit_out/nucleo-l4r5zi/` and the pqm4 clone to the laptop; record "
        "`arm-none-eabi-gcc --version` and the repository commit.", "",
        "## At the board", "",
        "1. Record board name, chip marking and ST-LINK firmware version. The ST-LINK virtual COM "
        "port carries LPUART1 at 38400 baud (pqm4 setting).",
        "2. Board check first: flash `b1_mlkem_512.hex`. Its META lines read back the clock "
        "(`clock_hz_rcc` from RCC registers after pqm4's `hal_setup(CLOCK_BENCHMARK)`), "
        "`flash_ws`, `cache` (icache, dcache, prefetch) and run the counter check "
        "(`counter_dwt_cycles` against `counter_systick_cycles`). Stop if the two counters "
        "disagree, if the clock is not 20000000, or if `flash_ws` is not 0. The same pqm4 set up "
        "code runs in the B0 images, so these values also describe B0.",
        f"3. Optional cross check with OpenOCD: `mdw {ra['FLASH_ACR']:#010x}` (FLASH_ACR), "
        f"`mdw {ra['RCC_CFGR']:#010x}` (RCC_CFGR), `mdw {ra['RCC_PLLCFGR']:#010x}` (RCC_PLLCFGR); "
        "addresses computed from the pinned libopencm3 l4 headers.",
        "4. Pass the read back values to `parse.py` for B0 (`--clock-hz --flash-ws --cache "
        "--toolchain --commit`).", "",
        "## Runs", "",
        "1. Start `capture.py --port <port> --run <n> --image <name> --experiment B0|B1 "
        "--label \"board measured\" --out <log>` before each flash or reset; it stops at `#`.",
        "2. Speed images (B0) and harness images (B1): flash once, then 3 power cycles (unplug "
        "and replug USB), one capture per power cycle with `--run 1`, `2`, `3`. Iterations per "
        "run: ML-KEM-768 100; ML-DSA-44 1000 (B0, matching pqm4's published 1000); B1 100 for "
        "every set (1000 for B1 signing does not fit the session; recorded as a deviation).",
        "3. Test and stack images: one run each. Any line starting `ERROR` stops the session.",
        "4. Keep every raw log; never edit one.", "",
        "## After", "",
        "1. `parse.py <logs> --out board.csv --checks-out checks.csv --require-all` (exit 0 "
        "needed).",
        "2. `compare.py board.csv --out compare.csv`: board measured against published by "
        "evidence id, against `cyclemodel/results/board_predictions.csv` if present, and RTL "
        "simulated rows if present; ratios carry bootstrap 95 percent intervals (seed 20261020).",
        "3. Report board measured numbers in their own table, labelled board measured, with "
        "board, clock, flash wait states, cache bits, toolchain and commit. Never merge them into "
        "published, emulated or modelled columns. Copy logs and commands to "
        "`bench/mcu/board_results/<date>/`.", "",
    ]
    with open(path, "w") as fh:
        fh.write("\n".join(L))
    return tot


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--flash-s", type=float, default=20.0, help="assumed seconds per flash")
    ap.add_argument("--power-s", type=float, default=30.0, help="assumed seconds per power cycle")
    ap.add_argument("--setup-s", type=float, default=900.0, help="assumed set up seconds")
    ap.add_argument("--logdir", default=os.path.join(K.OUT_DIR, "dry_run"))
    a = ap.parse_args(argv)
    rows = plan(compare.read_csv(compare.EVIDENCE), a.logdir, a.flash_s, a.power_s, a.setup_s)
    with open(os.path.join(HERE, "session_plan.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=PLAN_COLUMNS)
        w.writeheader()
        w.writerows(rows)
    has_uart = bool(uart_bytes(a.logdir))
    tot = write_checklist(os.path.join(HERE, "CHECKLIST.md"), rows, a.flash_s, a.power_s,
                          a.setup_s, has_uart)
    print(f"estimated session minutes: {tot:.1f}")


if __name__ == "__main__":
    main()
