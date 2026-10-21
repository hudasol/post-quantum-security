#!/usr/bin/env python3
"""Draw the main paper figures from result files into docs/figures/paper/ (PNG).

Each figure states one message, names every series in a legend, labels both axes with units and
uses a colour blind safe palette in pink tones (checked with a palette validator: lightness band,
chroma floor, colour vision deficiency separation and contrast all pass). The source file of each
figure is printed in its caption in docs/PAPER.md.

  python3 scripts/make_paper_figures.py
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "figures" / "paper"
ROSE, PINK, INDIGO = "#8E2A5B", "#D9659A", "#4F57B0"
BAND = "#F6D9E6"
INK, MUTED = "#2B2B2B", "#6B6B6B"

FIGURES = {
    "fig1_cycle_model_errors.png": ["stats/results/cycle_cluster_bootstrap.csv", "stats/results/cycle_lofo_summary.csv"],
    "fig2_lrwpan_causes.png": ["netsim/results/gap_sweep.csv"],
    "fig3_fleet_replacement.png": ["planner/results/flightstack_mc_summary.csv"],
}


def _style(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(MUTED)
    ax.tick_params(colors=INK, labelsize=8)
    ax.grid(axis="y", color="#E6E6E6", linewidth=0.6)
    ax.set_axisbelow(True)


def fig_cycle_errors():
    lo = pd.read_csv(ROOT / "stats/results/cycle_lofo_summary.csv")
    cb = pd.read_csv(ROOT / "stats/results/cycle_cluster_bootstrap.csv")
    rows = []
    for model in ("fitted", "reduced"):
        h = cb.query("model == @model and subset == 'test, all'").iloc[0]
        rows.append((model, "held out half\n(split by binary)", h.median_abs_pct, h.median_abs_cluster_ci_lo, h.median_abs_cluster_ci_hi))
        for grp, name in (("binary", "one binary\nleft out"), ("parameter set", "one parameter\nset left out"),
                          ("implementation family", "one implementation\nfamily left out"), ("scheme", "one scheme\nleft out")):
            r = lo.query("left_out_by == @grp and group == 'all groups pooled' and model == @model").iloc[0]
            rows.append((model, name, r.median_abs_pct, r.median_abs_cluster_ci_lo, r.median_abs_cluster_ci_hi))
    d = pd.DataFrame(rows, columns=["model", "design", "med", "lo", "hi"])
    designs = list(dict.fromkeys(d.design))
    fig, ax = plt.subplots(figsize=(6.4, 3.0), dpi=200)
    w = 0.38
    for i, (model, col, name) in enumerate((("fitted", ROSE, "fitted model (12 features)"),
                                            ("reduced", PINK, "reduced model (4 features)"))):
        s = d[d.model == model].set_index("design").loc[designs]
        x = [j + (i - 0.5) * w for j in range(len(designs))]
        ax.bar(x, s.med, width=w - 0.04, color=col, label=name, edgecolor="white", linewidth=1)
        ax.errorbar(x, s.med, yerr=[s.med - s.lo, s.hi - s.med], fmt="none", ecolor=INK, elinewidth=0.8, capsize=2)
    ax.set_xticks(range(len(designs)))
    ax.set_xticklabels(designs, fontsize=7)
    ax.set_ylabel("median absolute error, percent", fontsize=8, color=INK)
    ax.set_xlabel("validation design (rows predicted that the fit did not see)", fontsize=8, color=INK)
    _style(ax)
    ax.legend(fontsize=7, frameon=False, loc="upper left")
    fig.tight_layout()
    fig.savefig(OUT / "fig1_cycle_model_errors.png")
    plt.close(fig)


def fig_lrwpan():
    g = pd.read_csv(ROOT / "netsim/results/gap_sweep.csv").set_index("cell")
    cells = [("base_frame", "1 hop,\ndefaults"), ("minbe_8", "backoff\nexponent 8"), ("hops_3", "3 hops"), ("bg_16", "16 neighbours\nsending")]
    lo, hi = float(g.loc["base_frame", "range_low_s_published"]), float(g.loc["base_frame", "range_high_s_published"])
    fig, ax = plt.subplots(figsize=(6.4, 2.9), dpi=200)
    ax.axhspan(lo, hi, color=BAND, zorder=0, label=f"published range, {lo:.0f} to {hi:.0f} s (published)")
    w = 0.38
    for i, (colname, col, name) in enumerate((("time_s_modelled", PINK, "linksim (modelled)"),
                                              ("time_mean_s_simulated_network", ROSE, "ns-3 mean with 95 percent interval (simulated (network))"))):
        x = [j + (i - 0.5) * w for j in range(len(cells))]
        y = [float(g.loc[c, colname]) for c, _ in cells]
        ax.bar(x, y, width=w - 0.04, color=col, label=name, edgecolor="white", linewidth=1, zorder=2)
        if colname.startswith("time_mean"):
            lo_ci = [float(g.loc[c, "time_ci_lo_s_simulated_network"]) for c, _ in cells]
            hi_ci = [float(g.loc[c, "time_ci_hi_s_simulated_network"]) for c, _ in cells]
            ax.errorbar(x, y, yerr=[[a - b for a, b in zip(y, lo_ci)], [b - a for a, b in zip(y, hi_ci)]],
                        fmt="none", ecolor=INK, elinewidth=0.8, capsize=2, zorder=3)
    ax.set_xticks(range(len(cells)))
    ax.set_xticklabels([n for _, n in cells], fontsize=7)
    ax.set_ylabel("time to transfer 50 kB, s", fontsize=8, color=INK)
    ax.set_xlabel("single cause added to the one hop IEEE 802.15.4 transfer", fontsize=8, color=INK)
    _style(ax)
    ax.set_ylim(0, 75)
    ax.legend(fontsize=7, frameon=False, loc="upper left", ncol=1, bbox_to_anchor=(0.0, 1.0))
    fig.tight_layout()
    fig.savefig(OUT / "fig2_lrwpan_causes.png")
    plt.close(fig)


def fig_fleet():
    d = pd.read_csv(ROOT / "planner/results/flightstack_mc_summary.csv").set_index("thresholds")
    order = [("stack_asm", "stack optimised\nassembly"), ("speed_asm", "speed optimised\nassembly"), ("portable_c", "portable C"),
             ("reference_c", "reference C"), ("uncertain", "uncertain\n(drawn from rows)")]
    fig, ax = plt.subplots(figsize=(6.4, 2.9), dpi=200)
    w = 0.38
    for i, (pre, col, name) in enumerate((("assumed", PINK, "round 4: assumed free memory (estimated)"),
                                          ("measured", ROSE, "round 5: measured flight stack memory, 7 boards (estimated)"))):
        x = [j + (i - 0.5) * w for j in range(len(order))]
        y = [float(d.loc[t, f"{pre}_median"]) for t, _ in order]
        lo = [float(d.loc[t, f"{pre}_ci_low"]) for t, _ in order]
        hi = [float(d.loc[t, f"{pre}_ci_high"]) for t, _ in order]
        ax.bar(x, y, width=w - 0.04, color=col, label=name, edgecolor="white", linewidth=1)
        ax.errorbar(x, y, yerr=[[a - b for a, b in zip(y, lo)], [b - a for a, b in zip(y, hi)]], fmt="none", ecolor=INK, elinewidth=0.8, capsize=2)
    ax.set_xticks(range(len(order)))
    ax.set_xticklabels([n for _, n in order], fontsize=7)
    ax.set_ylabel("share of devices needing\nhardware replacement", fontsize=8, color=INK)
    ax.set_xlabel("memory threshold scenario (ML-DSA implementation footprint)", fontsize=8, color=INK)
    ax.set_ylim(0, 0.6)
    _style(ax)
    ax.legend(fontsize=7, frameon=False, loc="upper left")
    fig.tight_layout()
    fig.savefig(OUT / "fig3_fleet_replacement.png")
    plt.close(fig)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    fig_cycle_errors()
    fig_lrwpan()
    fig_fleet()
    for f in FIGURES:
        print(f"wrote docs/figures/paper/{f}")


if __name__ == "__main__":
    main()
