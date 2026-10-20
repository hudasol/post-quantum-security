#!/usr/bin/env python3
"""Compare parsed board kit results with published, modelled and RTL simulated rows.

Author: Huda Mueen. Inputs:
  results CSV from parse.py (label 'board measured' or 'emulated'),
  data/evidence.csv (published pqm4 rows, matched by scheme, pqm4 implementation and operation;
      the evidence id is written beside each value),
  cyclemodel/results/board_predictions.csv if it exists at run time (label 'modelled'),
  RTL simulated rows if a file is given with --rtl or found as cyclemodel/results/*rtl*.csv.
Rules enforced here:
  * every value column carries its label as a suffix (cycles_board_measured, cycles_published,
    cycles_modelled, cycles_rtl_simulated, stack_emulated, ...); labels never share a column;
  * cycle counts from an emulator are meaningless: rows labelled 'emulated' get no cycle summary
    and take no part in any cycle ratio (cycles_status says so); emulated stack is kept, labelled;
  * ratios are computed only between board measured cycles and another source, with a bootstrap
    95 percent interval (seed 20261020, 2000 resamples) of the ratio of means (pqm4 publishes means).
Expected columns of the optional files: scheme, operation, cycles (or cycles_modelled), and
optionally variant and a validation error column (any column whose name contains 'error').
"""
import argparse
import csv
import glob
import os
import random
import re
import statistics
import sys

SEED = 20261020
N_BOOT = 2000
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
EVIDENCE = os.path.join(REPO, "data", "evidence.csv")
PREDICTIONS = os.path.join(REPO, "cyclemodel", "results", "board_predictions.csv")

COLUMNS = ["experiment", "label", "board", "scheme", "variant", "operation", "n_runs", "n_values",
           "cycles_status", "cycles_board_measured_mean", "cycles_board_measured_median",
           "cycles_board_measured_mean_ci_low", "cycles_board_measured_mean_ci_high",
           "cycles_published", "published_id", "ratio_board_measured_to_published",
           "ratio_ci_low", "ratio_ci_high", "cycles_modelled", "modelled_validation_error",
           "ratio_board_measured_to_modelled", "cycles_rtl_simulated",
           "ratio_board_measured_to_rtl_simulated", "stack_board_measured", "stack_emulated",
           "stack_published", "cycles_published_pqm4_clean_reference",
           "published_reference_id", "note"]


def slug(label):
    return label.strip().lower().replace(" ", "_")


def read_csv(path):
    with open(path, newline="") as fh:
        return list(csv.DictReader(fh))


def published_index(evidence_rows):
    """Index pqm4 rows of evidence.csv by (scheme, implementation, operation)."""
    idx = {}
    for r in evidence_rows:
        m = re.match(r"pqm4 implementation '([a-z0-9]+)", r.get("library", ""))
        if not m or r.get("evidence_type") != "published" or not r.get("cycles"):
            continue
        key = (r["parameter_set"].upper(), m.group(1), r["operation"])
        idx.setdefault(key, r)  # first matching row (lowest id) wins; ids are recorded
    return idx


def bootstrap_mean_ratio(values, ref, seed=SEED, n=N_BOOT):
    """Bootstrap 95 percent interval of mean(values)/ref."""
    rng = random.Random(seed)
    k = len(values)
    reps = sorted(statistics.fmean(rng.choices(values, k=k)) / ref for _ in range(n))
    return reps[int(0.025 * n)], reps[int(0.975 * n) - 1]


def bootstrap_mean(values, seed=SEED, n=N_BOOT):
    lo, hi = bootstrap_mean_ratio(values, 1.0, seed, n)
    return lo, hi


def optional_rows(path, label):
    if not path or not os.path.exists(path):
        return {}
    out = {}
    for r in read_csv(path):
        c = r.get("cycles") or r.get(f"cycles_{slug(label)}") or r.get("cycles_modelled")
        if not c:
            continue
        err = next((r[k] for k in r if k and "error" in k.lower() and r[k]), "")
        key = (r.get("scheme", "").upper(), r.get("variant", ""), r.get("operation", ""))
        out[key] = (float(c), err)
    return out


def lookup(table, scheme, variant, op):
    return table.get((scheme, variant, op)) or table.get((scheme, "", op))


def fmt(x, nd=0):
    if x is None or x == "":
        return ""
    return f"{x:.{nd}f}" if isinstance(x, float) else str(x)


def compare(results, evidence_rows, modelled=None, rtl=None):
    pub = published_index(evidence_rows)
    modelled = modelled or {}
    rtl = rtl or {}
    groups = {}
    for r in results:
        key = (r["experiment"], r["label"], r["board"], r["scheme"].upper(), r["variant"],
               r["operation"])
        groups.setdefault(key, []).append(r)
    out = []
    for key in sorted(groups):
        exp, label, board, scheme, variant, op = key
        rows = groups[key]
        cyc = [float(r["cycles"]) for r in rows if r["cycles"] not in ("", None)]
        stk = [int(r["stack_bytes"]) for r in rows if r["stack_bytes"] not in ("", None)]
        row = dict.fromkeys(COLUMNS, "")
        row.update(experiment=exp, label=label, board=board, scheme=scheme, variant=variant,
                   operation=op, n_runs=len({r["run"] for r in rows}), n_values=len(cyc))
        p = pub.get((scheme, variant, op)) if exp == "B0" else None
        if p:
            row.update(cycles_published=p["cycles"], published_id=p["id"],
                       stack_published=p.get("stack_bytes", ""))
        if exp == "B1":
            ref = pub.get((scheme, "clean", op))
            if ref:
                row.update(cycles_published_pqm4_clean_reference=ref["cycles"],
                           published_reference_id=ref["id"],
                           note="B1 runs mlkem-native or mldsa-native, not pqm4 code: the pqm4 "
                                "clean value is a reference, not a reproduction target")
        if stk:
            # stack is one value per run; report the maximum over runs
            row["stack_" + slug(label)] = max(stk)
        m = lookup(modelled, scheme, variant, op)
        if m:
            row.update(cycles_modelled=fmt(m[0]), modelled_validation_error=m[1])
        t = lookup(rtl, scheme, variant, op)
        if t:
            row["cycles_rtl_simulated"] = fmt(t[0])
        if label != "board measured":
            row["cycles_status"] = (f"excluded: label {label}; cycle values from this source are "
                                    "not cycle counts and are not compared" if cyc else "no cycles")
        elif cyc:
            mean = statistics.fmean(cyc)
            lo, hi = bootstrap_mean(cyc)
            row.update(cycles_status="compared", cycles_board_measured_mean=fmt(mean),
                       cycles_board_measured_median=fmt(statistics.median(cyc)),
                       cycles_board_measured_mean_ci_low=fmt(lo),
                       cycles_board_measured_mean_ci_high=fmt(hi))
            if p:
                ref = float(p["cycles"])
                rlo, rhi = bootstrap_mean_ratio(cyc, ref)
                row.update(ratio_board_measured_to_published=fmt(mean / ref, 4),
                           ratio_ci_low=fmt(rlo, 4), ratio_ci_high=fmt(rhi, 4))
            if m:
                row["ratio_board_measured_to_modelled"] = fmt(mean / m[0], 4)
            if t:
                row["ratio_board_measured_to_rtl_simulated"] = fmt(mean / t[0], 4)
        else:
            row["cycles_status"] = "no cycles"
        out.append(row)
    return out


def find_rtl(arg):
    if arg:
        return arg
    hits = sorted(glob.glob(os.path.join(REPO, "cyclemodel", "results", "*rtl*.csv")))
    return hits[0] if hits else None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("results", nargs="+", help="result CSV files from parse.py")
    ap.add_argument("--evidence", default=EVIDENCE)
    ap.add_argument("--predictions", default=PREDICTIONS)
    ap.add_argument("--rtl", default=None)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    results = [r for p in a.results for r in read_csv(p)]
    modelled = optional_rows(a.predictions, "modelled")
    rtl_path = find_rtl(a.rtl)
    rtl = optional_rows(rtl_path, "RTL simulated")
    rows = compare(results, read_csv(a.evidence), modelled, rtl)
    with open(a.out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    n_cmp = sum(1 for r in rows if r["cycles_status"] == "compared")
    n_exc = sum(1 for r in rows if r["cycles_status"].startswith("excluded"))
    print(f"groups={len(rows)} cycles_compared={n_cmp} cycles_excluded={n_exc} "
          f"predictions={'yes' if modelled else 'absent'} rtl={'yes' if rtl else 'absent'} "
          f"published_matched={sum(1 for r in rows if r['published_id'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
