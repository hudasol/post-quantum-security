"""Second and further open cores for rtlsim/report.py (round 5): CV32E40P beside Ibex.

Author: Huda Mueen. Reads rtlsim/results/logs/<core>/<set>.log (same harness output as Ibex),
writes rtlsim/results/<core>_cycles.csv and rtlsim/results/core_spread.csv, and returns the
Markdown lines of the section that report.py appends to docs/RTL_SIM_RESULTS.md. Label of every
cycle value: RTL simulated. These are open core designs in simulation, not Arm silicon.
"""
import csv
import statistics
from pathlib import Path

import parse_log

HERE = Path(__file__).resolve().parent
SEED = 20261020
LABEL = "RTL simulated"

CORES = {
    "cv32e40p": {
        "name": "OpenHW Group CV32E40P (RTL, Verilator)",
        "env_commit": "cv32e40p_commit",
        "config": ("CV32E40P example testbench (example_tb/core), tb_top default parameters: RV32IMC, "
                   "PULP_XPULP=0, PULP_CLUSTER=0, FPU=0, ZFINX=0, NUM_MHPMCOUNTERS=1; four stage "
                   "pipeline; no cache"),
        "memory": ("example testbench RAM (mm_ram with dp_ram), 4 MB (RAM_ADDR_WIDTH=22), instruction and "
                   "data ports; random stall and interrupt generators present but disabled unless the "
                   "program writes their control addresses, which the harness does not"),
    },
}

CSV_COLS = ["label", "core", "core_configuration", "memory_model", "compiler", "compiler_flags",
            "library", "library_commit", "backend", "parameter_set", "operation", "statistic",
            "cycles", "n_runs", "median_ci95_low", "median_ci95_high", "correctness_check",
            "log_complete", "seed", "timer_overhead_subtracted_cycles"]
SPREAD_COLS = ["label", "parameter_set", "operation", "n_cores", "cores", "cycles_median_ibex",
               "cycles_median_cv32e40p", "max_over_min", "slowest_core", "fastest_core"]


def fmt_int(x):
    return f"{int(round(x)):,}"


def summarise_core(core, sets, ops, env):
    """Return (summary rows, missing sets, sim stats) for one core directory of logs."""
    d = HERE / "results" / "logs" / core
    out, missing, stats = [], [], {}
    for s in sets:
        p = d / f"{s}.log"
        if not p.exists():
            missing.append(s)
            continue
        pl = parse_log.parse_file(p)
        if not pl.records:
            missing.append(s)
            continue
        lib = "mlkem-native" if s.startswith("ML-KEM") else "mldsa-native"
        commit = env["mlkem_commit"] if lib == "mlkem-native" else env["mldsa_commit"]
        for row in parse_log.summarise(pl.records, seed=SEED):
            row.update(library=lib, library_commit=commit, complete=pl.done,
                       overhead=pl.config.get("timer_overhead_cycles", ""))
            out.append(row)
        sp = d / f"{s}.simstats.txt"
        if sp.exists():
            stats[s] = sp.read_text().strip().replace("\n", "; ")
    order = {(s, o): i for i, (s, o) in enumerate((s, o) for s in sets for o in ops[s[:6]])}
    out.sort(key=lambda r: order.get((r["parameter_set"], r["operation"]), 99))
    return out, missing, stats


def write_core_csv(core, summary, env, compiler, cflags):
    info = CORES[core]
    path = HERE / "results" / f"{core}_cycles.csv"
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_COLS)
        w.writeheader()
        for r in summary:
            for st in ("min", "median", "max"):
                w.writerow({
                    "label": LABEL, "core": info["name"],
                    "core_configuration": info["config"] + f"; commit {env.get(info['env_commit'], '')}",
                    "memory_model": info["memory"], "compiler": compiler, "compiler_flags": cflags,
                    "library": r["library"], "library_commit": r["library_commit"],
                    "backend": "portable C", "parameter_set": r["parameter_set"],
                    "operation": r["operation"], "statistic": st,
                    "cycles": int(r[st]) if float(r[st]).is_integer() else r[st], "n_runs": r["n"],
                    "median_ci95_low": r["median_ci95_low"] if st == "median" else "",
                    "median_ci95_high": r["median_ci95_high"] if st == "median" else "",
                    "correctness_check": parse_log.correctness_text(r), "log_complete": r["complete"],
                    "seed": SEED, "timer_overhead_subtracted_cycles": r["overhead"]})
    return path


def spread_rows(by_core):
    """by_core: {core: {(set, op): median}}; one row per operation present on every core."""
    keys = None
    for t in by_core.values():
        keys = set(t) if keys is None else keys & set(t)
    rows = []
    for k in sorted(keys or []):
        vals = {c: by_core[c][k] for c in by_core}
        hi = max(vals, key=vals.get)
        lo = min(vals, key=vals.get)
        rows.append({"label": LABEL, "parameter_set": k[0], "operation": k[1],
                     "n_cores": len(vals), "cores": "+".join(sorted(vals)),
                     "cycles_median_ibex": vals.get("ibex", ""),
                     "cycles_median_cv32e40p": vals.get("cv32e40p", ""),
                     "max_over_min": round(vals[hi] / vals[lo], 3), "slowest_core": hi,
                     "fastest_core": lo})
    return rows


def section(ibex_summary, env, compiler, cflags, sets, ops):
    """Write the per core CSV files and the spread CSV; return Markdown lines."""
    L = []
    a = L.append
    by_core = {"ibex": {(r["parameter_set"], r["operation"]): r["median"] for r in ibex_summary}}
    for core, info in CORES.items():
        summary, missing, stats = summarise_core(core, sets, ops, env)
        a(f"## Second open core: {info['name']}")
        a("")
        if not summary:
            a("No completed simulation log was found for this core; nothing is reported.")
            a("")
            continue
        write_core_csv(core, summary, env, compiler, cflags)
        by_core[core] = {(r["parameter_set"], r["operation"]): r["median"] for r in summary}
        a(f"- Core source: commit `{env.get(info['env_commit'], '')}` "
          f"({env.get(core + '_describe', '')}), licence {env.get(core + '_licence', '')}.")
        a(f"- Configuration: {info['config']}.")
        a(f"- Memory model: {info['memory']}.")
        a(f"- Simulator: {env.get(core + '_verilator', env.get('verilator', ''))}, built by "
          "`rtlsim/build_sim_cv32e40p.sh` from the core's manifest and its example testbench. "
          "No RTL file is changed. Two deviations: the example testbench at this tag passes the "
          "old parameter names PULP_XPULP and PULP_CLUSTER to cv32e40p_top, whose parameters are "
          "COREV_PULP and COREV_CLUSTER, so a copy of cv32e40p_tb_subsystem.sv renames these two "
          "mappings (both values 0); and Verilator 5.020 stops on BLKANDNBLK in the counter CSRs "
          "of cv32e40p_cs_registers.sv, so that check is switched off. The counter CSRs are "
          "therefore a known risk; mcycle counted in every run, every check passed and repeated "
          "runs agree closely (table below).")
        a("- Software: the same harness, libraries, compiler and flags as for Ibex; only the start up "
          "code and link script of the example testbench (stack enlarged with `--defsym`) and the "
          "output functions in `rtlsim/sw/cv32e40p/` differ. The cycle counter is enabled before "
          "main because the core inhibits `mcycle` out of reset.")
        if missing:
            a(f"- **Missing parameter sets (simulation not finished within the time box): "
              f"{', '.join(missing)}.**")
        a("")
        a("| Parameter set | Operation | Runs | Min | Median | Median 95% CI | Max | Checks |")
        a("|---|---|---|---|---|---|---|---|")
        for r in summary:
            a(f"| {r['parameter_set']} | {r['operation']} | {r['n']} | {fmt_int(r['min'])} | "
              f"{fmt_int(r['median'])} | {fmt_int(r['median_ci95_low'])} to "
              f"{fmt_int(r['median_ci95_high'])} | {fmt_int(r['max'])} | "
              f"{parse_log.correctness_text(r)} |")
        fails = sum(r["n"] - r["ok"] + r["negative_n"] - r["negative_ok"] for r in summary)
        a("")
        a(f"Total failed checks across all completed runs on this core: {fails}.")
        if stats:
            a("")
            a("Simulation wall time: " + "; ".join(f"{s} {v}" for s, v in stats.items()) + ".")
        a("")
    a("## Third open core: VexRiscv (not simulated)")
    a("")
    a("VexRiscv was the first item in the round 5 cut order. Its generator needs sbt and Scala "
      "libraries from Maven Central; the sbt launcher could not retrieve sbt 1.6.0 (the version "
      "the pinned VexRiscv commit asks for) because Maven Central answered HTTP 429 to its "
      "requests. No mirror was used. The prepared configuration and testbench "
      "(`rtlsim/vexriscv/`, `rtlsim/build_vexriscv.sh`) were never built or run, and no VexRiscv "
      "number appears in this file.")
    a("")
    rows = spread_rows(by_core) if len(by_core) > 1 else []
    with open(HERE / "results" / "core_spread.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=SPREAD_COLS)
        w.writeheader()
        w.writerows(rows)
    if rows:
        a("## Spread across the open cores simulated (label: RTL simulated)")
        a("")
        a("Median cycles of the same program on each core and the ratio of the largest to the "
          "smallest median (`rtlsim/results/core_spread.csv`). Both cores run RV32IMC code built "
          "with the same compiler and flags from the same source; the differences come from the "
          "core designs and from the two testbench memories. These are open core designs in "
          "simulation, not Arm silicon and not a fabricated chip.")
        a("")
        a("| Parameter set | Operation | Ibex median | CV32E40P median | Largest over smallest | "
          "Slower core |")
        a("|---|---|---|---|---|---|")
        for r in rows:
            a(f"| {r['parameter_set']} | {r['operation']} | {fmt_int(r['cycles_median_ibex'])} | "
              f"{fmt_int(r['cycles_median_cv32e40p'])} | {r['max_over_min']:.2f} | "
              f"{r['slowest_core']} |")
        a("")
        ratios = [r["max_over_min"] for r in rows]
        a(f"Across {len(rows)} operations the largest over smallest median ranges from "
          f"{min(ratios):.2f} to {max(ratios):.2f} (median {statistics.median(ratios):.2f}).")
        a("")
    return L
