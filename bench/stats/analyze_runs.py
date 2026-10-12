#!/usr/bin/env python3
"""Summarise raw harness output (bench/mcu/src/*.c) into medians, quantiles and bootstrap CIs.

Input : one or more CSV files produced by the harness (lines starting BENCH,/STACK,/META,/CHECK,).
        Pass one file per power cycle / run (the file name is the run id if BENCH_RUN_ID was 0).
Output: summary CSV + a markdown table. Every row carries the unit from the data
        ("cycles" for MCU, "ns_host" for host self-tests); a table never mixes the two.

Statistics (documented choices, see docs/BENCHMARK_PLAN.md section 5):
  * median and the 5/25/75/95/99th percentiles, min, max, n  (not just the mean);
  * mean is reported only as a convenience and flagged unsuitable for ML-DSA signing;
  * 95% CI for the median by percentile bootstrap (B=10000, seeded, resampling iterations);
  * run-to-run spread: median of each run, then range of those medians across runs;
  * coefficient of variation of the per-run medians when >= 3 runs.
Only the Python standard library is used.
"""
import argparse
import csv
import random
import statistics
import sys
from collections import defaultdict
from pathlib import Path


def percentile(sorted_vals, q):
    """Linear-interpolated percentile, q in [0,100]."""
    if not sorted_vals:
        return float("nan")
    k = (len(sorted_vals) - 1) * q / 100.0
    lo = int(k)
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (k - lo)


def bootstrap_median_ci(vals, rng, b=10000, alpha=0.05):
    n = len(vals)
    if n < 2:
        return (float("nan"), float("nan"))
    meds = []
    for _ in range(b):
        sample = sorted(vals[rng.randrange(n)] for _ in range(n))
        meds.append(percentile(sample, 50))
    meds.sort()
    return (percentile(meds, 100 * alpha / 2), percentile(meds, 100 * (1 - alpha / 2)))


def read_file(path):
    meta, rows, stack, checks = {}, [], {}, []
    with open(path, newline="", encoding="utf-8") as fh:
        for rec in csv.reader(fh):
            if not rec:
                continue
            tag = rec[0]
            if tag == "META" and len(rec) >= 3:
                meta[rec[1]] = ",".join(rec[2:])
            elif tag == "BENCH" and len(rec) == 8:
                _, alg, param, op, run, it, val, unit = rec
                rows.append((alg, param, op, int(run), int(it), float(val), unit))
            elif tag == "STACK" and len(rec) == 5:
                stack[(rec[1], rec[2], rec[3])] = int(rec[4])
            elif tag == "CHECK" and len(rec) == 6:
                checks.append((rec[1], rec[2], rec[3], int(rec[4]), int(rec[5])))
    return meta, rows, stack, checks


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--out-csv", type=Path, default=Path("summary.csv"))
    ap.add_argument("--out-md", type=Path, default=Path("summary.md"))
    ap.add_argument("--seed", type=int, default=20261011)
    ap.add_argument("--boot", type=int, default=10000)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    groups = defaultdict(lambda: defaultdict(list))  # key -> run_label -> values
    units, stacks, fails, targets = set(), defaultdict(list), 0, set()
    for idx, f in enumerate(args.files):
        meta, rows, stack, checks = read_file(f)
        targets.add(meta.get("target", "unknown"))
        for alg, param, op, run, it, val, unit in rows:
            run_label = run if run != 0 else idx  # file index is the run id when the firmware used 0
            groups[(alg, param, op, unit)][run_label].append(val)
            units.add(unit)
        for k, v in stack.items():
            stacks[k].append(v)
        for c in checks:
            fails += c[4]
    if fails:
        print(f"WARNING: {fails} failed correctness checks in the input; timings are not trustworthy", file=sys.stderr)
    if len(units) > 1:
        sys.exit(f"refusing to mix units in one summary: {sorted(units)}")

    out_rows = []
    for (alg, param, op, unit), per_run in sorted(groups.items()):
        allv = sorted(v for vs in per_run.values() for v in vs)
        run_meds = [statistics.median(vs) for vs in per_run.values()]
        lo, hi = bootstrap_median_ci(allv, rng, b=args.boot)
        row = {
            "alg": alg, "param": param, "op": op, "unit": unit, "runs": len(per_run), "n": len(allv),
            "min": allv[0], "p05": percentile(allv, 5), "p25": percentile(allv, 25),
            "median": percentile(allv, 50), "p75": percentile(allv, 75), "p95": percentile(allv, 95),
            "p99": percentile(allv, 99), "max": allv[-1], "mean": statistics.fmean(allv),
            "median_ci95_lo": lo, "median_ci95_hi": hi,
            "run_median_min": min(run_meds), "run_median_max": max(run_meds),
            "run_median_cv_pct": (100 * statistics.pstdev(run_meds) / statistics.fmean(run_meds)
                                  if len(run_meds) >= 3 and statistics.fmean(run_meds) else float("nan")),
            "max_over_median": allv[-1] / percentile(allv, 50) if percentile(allv, 50) else float("nan"),
            "stack_bytes": (",".join(str(x) for x in sorted(set(stacks.get((alg, param, op), [])))) or ""),
            "note": "mean unsuitable for sign (rejection sampling): use median/p95/p99" if op == "sign" else "",
        }
        out_rows.append(row)

    fields = list(out_rows[0].keys())
    with open(args.out_csv, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(out_rows)

    unit = next(iter(units))
    with open(args.out_md, "w", encoding="utf-8") as fh:
        fh.write(f"Unit: **{unit}**; targets seen: {', '.join(sorted(targets))}; input files: {len(args.files)}; bootstrap B={args.boot}, seed={args.seed}\n\n")
        fh.write("| alg | param | op | runs | n | median | 95% CI (median) | p05 | p95 | p99 | max | max/median | stack B |\n")
        fh.write("|---|---|---|---|---|---|---|---|---|---|---|---|---|\n")
        for r in out_rows:
            fh.write(
                f"| {r['alg']} | {r['param']} | {r['op']} | {r['runs']} | {r['n']} | {r['median']:.0f} | "
                f"{r['median_ci95_lo']:.0f}-{r['median_ci95_hi']:.0f} | {r['p05']:.0f} | {r['p95']:.0f} | {r['p99']:.0f} | "
                f"{r['max']:.0f} | {r['max_over_median']:.2f} | {r['stack_bytes']} |\n")
    print(f"wrote {args.out_csv} and {args.out_md} ({len(out_rows)} groups, unit={unit})")


if __name__ == "__main__":
    main()
