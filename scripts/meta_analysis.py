#!/usr/bin/env python3
"""Meta analysis of published cycle counts in data/evidence.csv (label: published).

Groups microcontroller rows by scheme family, parameter set, operation and core class, and
reports how many rows, sources and libraries stand behind each group, the median with a
bootstrap 95 percent interval (seed 20261020, 2000 resamples, groups of at least 5 rows),
the range, and the fields that differ inside the group (library, clock, notes on
optimisation). Ratios between core classes use group medians of the same parameter set and
operation only. Nothing is normalised: cycle counts are compared as published, and the clock
and library of every row are listed so a reader can judge comparability.

Writes data/meta/cycle_groups.csv, data/meta/core_ratios.csv, plots/meta_cycles_by_core.png
and docs/META_ANALYSIS.md.
"""
import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SEED = 20261020
OPS = {"keygen": "keygen", "encaps": "encaps", "decaps": "decaps",
       "sign": "sign", "verify": "verify"}


def core_class(core):
    t = str(core).lower()
    for pat, name in ((r"m0\+", "Cortex-M0+"), (r"m33", "Cortex-M33"), (r"m55", "Cortex-M55"),
                      (r"m7", "Cortex-M7"), (r"m4", "Cortex-M4"), (r"m3\b", "Cortex-M3"),
                      (r"risc", "RISC-V")):
        if re.search(pat, t):
            return name
    return "other"


def op_class(op):
    t = str(op).strip().lower()
    return OPS.get(t)


def boot_ci(values, rng, n=2000):
    v = np.asarray(values, dtype=float)
    if len(v) < 5:
        return (np.nan, np.nan)
    meds = np.median(rng.choice(v, size=(n, len(v)), replace=True), axis=1)
    return (float(np.percentile(meds, 2.5)), float(np.percentile(meds, 97.5)))


def load():
    d = pd.read_csv(ROOT / "data" / "evidence.csv")
    d = d[d.cycles.notna() & (d.device_class == "mcu") & (d.evidence_type == "published")].copy()
    d["core_class"] = d.core.map(core_class)
    d["op_class"] = d.operation.map(op_class)
    d = d[d.op_class.notna()]
    d["param"] = d.parameter_set.astype(str).str.strip()
    return d


def groups(d):
    rng = np.random.default_rng(SEED)
    out = []
    for (fam, param, op, core), g in d.groupby(["scheme_family", "param", "op_class", "core_class"], sort=True):
        lo, hi = boot_ci(g.cycles, rng)
        out.append({
            "scheme_family": fam, "parameter_set": param, "operation": op, "core_class": core,
            "rows": len(g), "sources": g.source_url.nunique(), "libraries": g.library.nunique(),
            "median_cycles": float(g.cycles.median()), "ci95_low": lo, "ci95_high": hi,
            "min_cycles": float(g.cycles.min()), "max_cycles": float(g.cycles.max()),
            "max_over_min": float(g.cycles.max() / g.cycles.min()) if g.cycles.min() > 0 else np.nan,
            "clocks_mhz": "; ".join(sorted({str(x) for x in g.clock_mhz.dropna()})),
            "row_ids": " ".join(g.id),
        })
    return pd.DataFrame(out)


def core_ratios(gr):
    base = gr[gr.core_class == "Cortex-M4"].set_index(["scheme_family", "parameter_set", "operation"])
    out = []
    for _, r in gr[gr.core_class != "Cortex-M4"].iterrows():
        k = (r.scheme_family, r.parameter_set, r.operation)
        if k in base.index:
            b = base.loc[k]
            out.append({"scheme_family": k[0], "parameter_set": k[1], "operation": k[2],
                        "core_class": r.core_class, "median_cycles": r.median_cycles,
                        "cortex_m4_median_cycles": b.median_cycles,
                        "ratio_to_cortex_m4": r.median_cycles / b.median_cycles,
                        "rows": r.rows, "cortex_m4_rows": b.rows})
    return pd.DataFrame(out)


def figure(d, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    colours = {"Cortex-M0+": "#fce4ec", "Cortex-M3": "#f8bbd0", "Cortex-M4": "#f48fb1",
               "Cortex-M7": "#d63384", "Cortex-M33": "#ad1457", "RISC-V": "#880e4f", "other": "#9e9e9e"}
    sel = d[d.param.isin(["ML-KEM-768", "ML-DSA-44"])]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    cats = [(p, o) for p in ["ML-KEM-768", "ML-DSA-44"] for o in ["keygen", "encaps", "decaps", "sign", "verify"]
            if len(sel[(sel.param == p) & (sel.op_class == o)])]
    for i, (p, o) in enumerate(cats):
        g = sel[(sel.param == p) & (sel.op_class == o)]
        for j, (core, gg) in enumerate(g.groupby("core_class")):
            x = i + (j - 2) * 0.12
            ax.scatter([x] * len(gg), gg.cycles, s=18, color=colours.get(core, "#9e9e9e"),
                       edgecolor="#4a0024", linewidth=0.4, label=core)
    h, l = ax.get_legend_handles_labels()
    uniq = dict(zip(l, h))
    ax.legend(uniq.values(), uniq.keys(), fontsize=8, frameon=False)
    ax.set_yscale("log")
    ax.set_xticks(range(len(cats)))
    ax.set_xticklabels([f"{p}\n{o}" for p, o in cats], fontsize=7)
    ax.set_ylabel("cycles (log scale)")
    ax.set_title("Published cycle counts on microcontrollers, one point per row (label: published)", fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def fmt(x):
    return "" if pd.isna(x) else f"{x:,.0f}"


def report(d, gr, cr):
    multi = gr[gr.sources >= 2]
    lines = [
        "# Meta analysis of published cycle counts",
        "",
        "Author: Huda Mueen. Generated by `scripts/meta_analysis.py` from `data/evidence.csv`; do not edit by hand. Label: published. Seed for the bootstrap: 20261020.",
        "",
        f"Scope: {len(d)} microcontroller rows with a cycle count and a plain operation (keygen, encaps, decaps, sign, verify), "
        f"in {len(gr)} groups of scheme family, parameter set, operation and core class; {int((gr.sources >= 2).sum())} groups have rows from two or more sources. "
        "Cycle counts are compared as published. They differ in library, optimisation, compiler, clock, flash wait states, cache state, counter and statistic (minimum, mean or median); the clock and the row ids of every group are listed in `data/meta/cycle_groups.csv` so that comparability can be judged row by row.",
        "",
        "## Groups with two or more sources",
        "",
        "| family | parameter set | operation | core | rows | sources | libraries | median | 95% interval | min | max | max / min |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for _, r in multi.sort_values(["scheme_family", "parameter_set", "operation", "core_class"]).iterrows():
        ci = "" if pd.isna(r.ci95_low) else f"{fmt(r.ci95_low)} to {fmt(r.ci95_high)}"
        lines.append(f"| {r.scheme_family} | {r.parameter_set} | {r.operation} | {r.core_class} | {r.rows} | {r.sources} | {r.libraries} | "
                     f"{fmt(r.median_cycles)} | {ci} | {fmt(r.min_cycles)} | {fmt(r.max_cycles)} | {r.max_over_min:.2f} |")
    spread = multi.max_over_min.dropna()
    lines += ["", "## What the spread says", ""]
    if len(spread):
        lines.append(f"Inside groups with two or more sources, the largest published value is {spread.median():.2f} times the smallest at the median group "
                     f"(range {spread.min():.2f} to {spread.max():.2f} over {len(spread)} groups). The spread mixes implementation choices (portable C against assembly, "
                     "stack against speed optimisation) with measurement conditions; a single published number for an operation on a core class therefore carries "
                     "an uncertainty of that order before any board is measured.")
    lines += ["", "## Ratios between core classes (group medians, same parameter set and operation)", "",
              "| family | parameter set | operation | core | median | Cortex-M4 median | ratio to Cortex-M4 | rows | Cortex-M4 rows |",
              "|---|---|---|---|---|---|---|---|---|"]
    for _, r in cr.sort_values(["core_class", "scheme_family", "parameter_set", "operation"]).iterrows():
        lines.append(f"| {r.scheme_family} | {r.parameter_set} | {r.operation} | {r.core_class} | {fmt(r.median_cycles)} | {fmt(r.cortex_m4_median_cycles)} | {r.ratio_to_cortex_m4:.2f} | {r.rows} | {r.cortex_m4_rows} |")
    lines += ["", "These ratios compare medians of different libraries and conditions on different cores; they show the order of magnitude, not a core effect isolated from the code.",
              "", "Figure: `plots/meta_cycles_by_core.png` (published rows only).", ""]
    return "\n".join(lines)


def main():
    d = load()
    gr = groups(d)
    cr = core_ratios(gr)
    (ROOT / "data" / "meta").mkdir(exist_ok=True)
    gr.to_csv(ROOT / "data" / "meta" / "cycle_groups.csv", index=False)
    cr.to_csv(ROOT / "data" / "meta" / "core_ratios.csv", index=False)
    figure(d, ROOT / "plots" / "meta_cycles_by_core.png")
    (ROOT / "docs" / "META_ANALYSIS.md").write_text(report(d, gr, cr), encoding="utf-8")
    print(f"{len(d)} rows, {len(gr)} groups, {len(cr)} core ratios")


if __name__ == "__main__":
    main()
