#!/usr/bin/env python3
"""Build rtlsim/results/ibex_cycles.csv, rtlsim/results/ibex_vs_cortex_m4.csv and docs/RTL_SIM_RESULTS.md
from the simulation logs in rtlsim/results/logs and the run environment in rtlsim/results/environment.txt.
Published Cortex-M4 comparison rows are read from data/evidence.csv and kept in separate columns.
Author: Huda Mueen.

Usage: python3 rtlsim/report.py
"""
import csv
import math
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import parse_log  # noqa: E402

SEED = 20261020
LABEL = "RTL simulated"
SETS = ["ML-KEM-512", "ML-KEM-768", "ML-KEM-1024", "ML-DSA-44", "ML-DSA-65", "ML-DSA-87"]
OPS = {"ML-KEM": ["keygen", "encaps", "decaps"], "ML-DSA": ["keygen", "sign", "verify"]}
CORE_CONFIG = ("Ibex simple system, named configuration 'small': RV32IMC (RV32Zca), RV32M=RV32MFast, "
               "RV32B none, register file RegFileFF, BranchTargetALU=0, WritebackStage=0 (two stage pipeline), "
               "no instruction cache, no branch predictor, SecureIbex=0, PMP off")
MEMORY_MODEL = ("single 1 MB dual port RAM shared by instruction and data ports; read data returned the cycle after "
                "the request (ram_2p), INSTR_CYCLE_DELAY=0, no wait states, no cache, no flash model")
CLEAN_LIB = "pqm4 implementation 'clean (PQClean reference C)'"
# Cortex-M4 specific (assembly) pqm4 variants: m4fspeed for ML-KEM, m4f for ML-DSA.
ASM_LIBS = {"ML-KEM": "pqm4 implementation 'm4fspeed (Cortex-M4F-specific, label as in file)'",
            "ML-DSA": "pqm4 implementation 'm4f (Cortex-M4F-specific, typically assembly)'"}


def read_env(path):
    env = {}
    with open(path) as fh:
        for line in fh:
            if "=" in line:
                k, v = line.rstrip("\n").split("=", 1)
                env[k] = v
    return env


def fmt_int(x):
    return f"{int(round(x)):,}"


def order_of_magnitude_text(ratio):
    """Plain description of a ratio in powers of ten (ratio between 0.1 and 10 counts as the same order)."""
    if 0.1 < ratio < 10:
        return "same order of magnitude"
    k = round(abs(math.log10(ratio)))
    word = {1: "one", 2: "two", 3: "three"}.get(k, str(k))
    side = "higher" if ratio > 1 else "lower"
    return f"about {word} order{'s' if k > 1 else ''} of magnitude {side}"


def load_published():
    """Published Cortex-M4 rows (pqm4 clean C and Cortex-M4 specific assembly) keyed by (library, parameter set, operation)."""
    out = {}
    with open(ROOT / "data" / "evidence.csv", newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["evidence_type"] != "published" or "M4" not in r["core"] or not r["cycles"]:
                continue
            if r["library"] == CLEAN_LIB or r["library"] in ASM_LIBS.values():
                key = (r["library"], r["parameter_set"], r["operation"])
                out.setdefault(key, r)
    return out


def main():
    env = read_env(HERE / "results" / "environment.txt")
    compiler = env["compiler"]
    cflags = env["cflags"]
    logs, stats, missing = {}, {}, []
    for s in SETS:
        p = HERE / "results" / "logs" / f"{s}.log"
        if not p.exists():
            missing.append(s)
            continue
        logs[s] = parse_log.parse_file(p)
        sp = HERE / "results" / "logs" / f"{s}.simstats.txt"
        stats[s] = sp.read_text().strip().replace("\n", "; ") if sp.exists() else ""

    summary = []
    for s, pl in logs.items():
        lib = "mlkem-native" if s.startswith("ML-KEM") else "mldsa-native"
        commit = env["mlkem_commit"] if lib == "mlkem-native" else env["mldsa_commit"]
        for row in parse_log.summarise(pl.records, seed=SEED):
            row.update(library=lib, library_commit=commit, complete=pl.done,
                       overhead=pl.config.get("timer_overhead_cycles", ""))
            summary.append(row)
    order = {(s, o): i for i, (s, o) in enumerate((s, o) for s in SETS for o in OPS[s[:6]])}
    summary.sort(key=lambda r: order.get((r["parameter_set"], r["operation"]), 99))

    # Main results CSV: one line per statistic.
    out_csv = HERE / "results" / "ibex_cycles.csv"
    cols = ["label", "core", "core_configuration", "memory_model", "compiler", "compiler_flags", "library",
            "library_commit", "backend", "parameter_set", "operation", "statistic", "cycles", "n_runs",
            "median_ci95_low", "median_ci95_high", "correctness_check", "log_complete", "seed",
            "timer_overhead_subtracted_cycles"]
    with open(out_csv, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in summary:
            for st in ("min", "median", "max"):
                w.writerow({
                    "label": LABEL, "core": "lowRISC Ibex (RTL, Verilator)", "core_configuration": CORE_CONFIG,
                    "memory_model": MEMORY_MODEL, "compiler": compiler, "compiler_flags": cflags,
                    "library": r["library"], "library_commit": r["library_commit"], "backend": "portable C",
                    "parameter_set": r["parameter_set"], "operation": r["operation"], "statistic": st,
                    "cycles": int(r[st]) if float(r[st]).is_integer() else r[st], "n_runs": r["n"],
                    "median_ci95_low": r["median_ci95_low"] if st == "median" else "",
                    "median_ci95_high": r["median_ci95_high"] if st == "median" else "",
                    "correctness_check": parse_log.correctness_text(r), "log_complete": r["complete"],
                    "seed": SEED, "timer_overhead_subtracted_cycles": r["overhead"],
                })

    # Comparison CSV: labels in separate columns.
    pub = load_published()
    comp = []
    for r in summary:
        c = pub.get((CLEAN_LIB, r["parameter_set"], r["operation"]))
        m = pub.get((ASM_LIBS[r["parameter_set"][:6]], r["parameter_set"], r["operation"]))
        row = {"parameter_set": r["parameter_set"], "operation": r["operation"], "label": LABEL,
               "cycles_median": r["median"], "cycles_median_ci95_low": r["median_ci95_low"],
               "cycles_median_ci95_high": r["median_ci95_high"],
               "id_clean_published": c["id"] if c else "", "cycles_clean_published": c["cycles"] if c else "",
               "id_asm_published": m["id"] if m else "", "cycles_asm_published": m["cycles"] if m else "",
               "variant_asm_published": m["library"] if m else "",
               "label_published": "published" if (c or m) else ""}
        for tag, src in (("clean", c), ("asm", m)):
            if src:
                p = float(src["cycles"])
                row[f"ratio_to_{tag}"] = round(r["median"] / p, 3)
                row[f"ratio_to_{tag}_ci95_low"] = round(r["median_ci95_low"] / p, 3)
                row[f"ratio_to_{tag}_ci95_high"] = round(r["median_ci95_high"] / p, 3)
                row[f"magnitude_vs_{tag}"] = order_of_magnitude_text(r["median"] / p)
        comp.append(row)
    ccols = ["parameter_set", "operation", "label", "cycles_median", "cycles_median_ci95_low",
             "cycles_median_ci95_high", "label_published", "id_clean_published", "cycles_clean_published",
             "id_asm_published", "variant_asm_published", "cycles_asm_published", "ratio_to_clean", "ratio_to_clean_ci95_low",
             "ratio_to_clean_ci95_high", "magnitude_vs_clean", "ratio_to_asm", "ratio_to_asm_ci95_low",
             "ratio_to_asm_ci95_high", "magnitude_vs_asm"]
    with open(HERE / "results" / "ibex_vs_cortex_m4.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=ccols)
        w.writeheader()
        for row in comp:
            w.writerow({k: row.get(k, "") for k in ccols})

    write_doc(env, summary, comp, pub, stats, missing, logs)
    print(f"wrote {out_csv} ({len(summary)} operation rows), comparison and docs/RTL_SIM_RESULTS.md")
    if missing:
        print("missing logs:", ", ".join(missing))


def write_doc(env, summary, comp, pub, stats, missing, logs):
    L = []
    a = L.append
    a("# RTL simulated cycle counts on the Ibex RISC-V core")
    a("")
    a("Author: Huda Mueen. Generated by `rtlsim/report.py`; do not edit by hand. Every number below is read from "
      "`rtlsim/results/logs/*.log`, `rtlsim/results/environment.txt` or `data/evidence.csv` by that script.")
    a("")
    a("## What this is, and what it is not")
    a("")
    a("These figures carry the label **RTL simulated**. They are cycle accurate counts from a Verilator simulation "
      "of the register transfer level design of lowRISC Ibex, an open source 32 bit RISC-V core. They are not "
      "measurements of Arm silicon, not measurements of any fabricated chip, and not measurements of any board. "
      "No clock frequency, energy or power figure is implied. The counts are only as faithful as the memory model "
      "described below, which is idealised.")
    a("")
    a("## Configuration")
    a("")
    a(f"- Core source: lowRISC Ibex, commit `{env['ibex_commit']}` (`{env['ibex_describe']}`), licence "
      f"{env['ibex_licence']}. No release tag newer than v2.1.0 exists, so a recorded master commit is used.")
    a(f"- Core configuration: {CORE_CONFIG}. FuseSoC options: `{env['ibex_fusesoc_opts']}`. The comment for this "
      "configuration in `ibex_configs.yaml` describes a two stage pipeline with a 3 cycle multiplier (4 cycles for "
      "mulh). It was chosen because it is the documented configuration closest to a small microcontroller class core.")
    a(f"- Memory model: {MEMORY_MODEL}. The RTL RAM size is `{env['ibex_simple_system_ram']}` (1 MB) and was not "
      f"changed. The stock link script uses only part of it, so `rtlsim/build_sw.sh` generates a link script with "
      f"{env['link_ram']}. A real microcontroller fetching from flash with wait states would take more cycles.")
    a(f"- Simulator: {env['verilator']}; FuseSoC {env['fusesoc']}. The Ibex README recommends building Verilator "
      "from source because packaged versions are often too old; the packaged version was used here. It passed the "
      "Ibex tool check (minimum 4.210 in util/tool_requirements.py) but is not the version pinned by Ibex CI "
      "(v4.210 in ci/vars.env).")
    a(f"- Compiler: {env['compiler']}; flags `{env['cflags']}`; C library {env['libc']} for memcpy, memset and "
      "memcmp.")
    a(f"- Libraries (portable C backends, default configuration, no native backend): mlkem-native "
      f"`{env['mlkem_commit']}` and mldsa-native `{env['mldsa_commit']}`; licence {env['mlkem_licence']}.")
    a(f"- Randomness: a fixed seed generator (splitmix64, seed {SEED}) in `rtlsim/sw/bench_rng.c`. It is insecure "
      "by design and exists only so that runs are repeatable.")
    a("- Timing: the `mcycle` CSR is read immediately before and after each call; the cost of two back to back "
      "reads (from the log) is subtracted. ML-KEM runs keygen, encaps and decaps five times each. ML-DSA runs keygen "
      "once, then sign and verify on five distinct 64 byte messages with an empty context string.")
    a("- Checks: decaps must return the encaps shared secret; verify must accept each signature; verify must "
      "reject the first signature after one message bit is flipped (not timed, first run only).")
    a("")
    if missing:
        a(f"**Missing parameter sets (simulation not finished within the time box): {', '.join(missing)}.**")
        a("")
    a("## Results (label: RTL simulated)")
    a("")
    a("Median with a bootstrap 95 percent interval of the median (10,000 resamples, seed 20261020); with five runs "
      "this interval is coarse. Cycles are core clock cycles of the simulated design.")
    a("")
    a("| Parameter set | Operation | Runs | Min | Median | Median 95% CI | Max | Checks |")
    a("|---|---|---|---|---|---|---|---|")
    for r in summary:
        a(f"| {r['parameter_set']} | {r['operation']} | {r['n']} | {fmt_int(r['min'])} | {fmt_int(r['median'])} | "
          f"{fmt_int(r['median_ci95_low'])} to {fmt_int(r['median_ci95_high'])} | {fmt_int(r['max'])} | "
          f"{parse_log.correctness_text(r)} |")
    a("")
    fails = sum(r["n"] - r["ok"] + r["negative_n"] - r["negative_ok"] for r in summary)
    a(f"Total failed checks across all completed runs: {fails}.")
    sign_rows = [r for r in summary if r["operation"] == "sign"]
    if sign_rows:
        spreads = ", ".join(f"{r['parameter_set']} max/min {r['max'] / r['min']:.2f}" for r in sign_rows)
        a("")
        a(f"Signing is variable time because of rejection sampling; spread over five messages: {spreads}.")
    kg = [r for r in summary if r["parameter_set"].startswith("ML-KEM")]
    if kg:
        sp = max(r["max"] - r["min"] for r in kg)
        a("")
        a(f"ML-KEM operations differ between runs by at most {fmt_int(sp)} cycles. This is consistent with rejection "
          "sampling of the public matrix, which is expanded from a different seed in each run.")
    a("")
    a("## Order of magnitude comparison with published Cortex-M4 rows")
    a("")
    a("Published values come from `data/evidence.csv` (pqm4 benchmarks, Cortex-M4F). The `clean` rows are PQClean "
      "reference C; the assembly rows are the Cortex-M4 specific pqm4 variants (`m4fspeed` for ML-KEM, `m4f` for ML-DSA). Labels are kept in separate columns. The "
      "comparison is only of order of magnitude: the libraries differ (mlkem-native and mldsa-native versus "
      "PQClean and pqm4), the compilers and flags differ, the instruction sets differ (RV32IMC versus Armv7E-M), "
      "the published values are means while ours are medians, and the Ibex memory has no wait states. The interval "
      "on each ratio reflects only the spread of our runs; the published value is treated as fixed.")
    a("")
    a("| Parameter set | Operation | Ibex median (RTL simulated) | Cortex-M4 clean (published, id) | Ratio to clean (95% CI) | Cortex-M4 assembly (published, id) | Ratio to assembly | Magnitude vs clean |")
    a("|---|---|---|---|---|---|---|---|")
    for c in comp:
        clean = f"{fmt_int(float(c['cycles_clean_published']))} ({c['id_clean_published']})" if c["id_clean_published"] else "none"
        m4f = f"{fmt_int(float(c['cycles_asm_published']))} ({c['id_asm_published']})" if c["id_asm_published"] else "none"
        rc = (f"{c['ratio_to_clean']:.2f} ({c['ratio_to_clean_ci95_low']:.2f} to {c['ratio_to_clean_ci95_high']:.2f})"
              if "ratio_to_clean" in c else "n/a")
        rm = f"{c['ratio_to_asm']:.2f}" if "ratio_to_asm" in c else "n/a"
        a(f"| {c['parameter_set']} | {c['operation']} | {fmt_int(c['cycles_median'])} | {clean} | {rc} | {m4f} | {rm} | "
          f"{c.get('magnitude_vs_clean', 'n/a')} |")
    a("")
    ratios = [c["ratio_to_clean"] for c in comp if "ratio_to_clean" in c]
    if ratios:
        a(f"Across {len(ratios)} operations the ratio of the Ibex median to the published Cortex-M4 clean C value "
          f"ranges from {min(ratios):.2f} to {max(ratios):.2f}. "
          + ("All fall within the same order of magnitude."
             if all(0.1 < x < 10 for x in ratios) else "Not all fall within the same order of magnitude."))
        a("")
    a("## Simulation statistics")
    a("")
    for s in SETS:
        if s in stats:
            a(f"- {s}: {stats[s]}")
    a("")
    a("## Reproduce")
    a("")
    a("```")
    a("bash rtlsim/fetch.sh        # clone Ibex, mlkem-native, mldsa-native at pinned commits outside the repository")
    a("bash rtlsim/build_sim.sh    # build the Verilator model, configuration small")
    a("bash rtlsim/build_sw.sh     # build one ELF per parameter set")
    a("bash rtlsim/run.sh          # run all six; logs go to rtlsim/results/logs")
    a("bash rtlsim/record_env.sh   # record versions and commits")
    a("python3 rtlsim/report.py    # write the CSV files and this document")
    a("```")
    a("")
    a("Outputs: `rtlsim/results/ibex_cycles.csv` (label, configuration, compiler, flags, library commit, operation, "
      "statistic, cycles, correctness) and `rtlsim/results/ibex_vs_cortex_m4.csv` (comparison, published values in "
      "columns suffixed `_published`).")
    a("")
    (ROOT / "docs" / "RTL_SIM_RESULTS.md").write_text("\n".join(L))


if __name__ == "__main__":
    main()
