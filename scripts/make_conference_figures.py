#!/usr/bin/env python3
"""Figures of the conference paper, drawn from the result files (vector PDF, deterministic).

fig_rtl.pdf: vehicle and ground side million cycles of one session start per design and core
             (rtlsim/results/proto_sessions.csv, label RTL simulated).
fig_sitl.pdf: share of commands acknowledged within 0.5 s with outages, per configuration, with the 95 percent
              interval over missions (sitl/results_r6/summary.csv, label SITL measured) and the mission model value
              of the same configuration (sitl/results_r6/comparison.csv, label estimated).
"""
import os

import matplotlib

matplotlib.use("Agg")
matplotlib.rcParams.update({"font.family": "serif", "font.size": 8, "axes.spines.top": False,
                            "axes.spines.right": False, "pdf.fonttype": 42})
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "conference")
INK, BLUE, PINK, GREY = "#222222", "#3b6ea8", "#c2577a", "#9a9a9a"


def save(fig, name):
    fig.savefig(os.path.join(OUT, name), metadata={"CreationDate": None, "ModDate": None, "Producer": None, "Creator": None, "Author": "Huda Mueen"},
                bbox_inches="tight")
    plt.close(fig)


def fig_rtl():
    s = pd.read_csv(os.path.join(ROOT, "rtlsim/results/proto_sessions.csv"))
    s = s[s.unit == "session start"]
    designs = [("classical", "Classical"), ("pq_only", "PQ\nonly"), ("hybrid_f1", "Hybrid\nwith F1")]
    fig, axes = plt.subplots(1, 2, figsize=(3.45, 1.9), sharey=True)
    for ax, side in zip(axes, ("vehicle", "ground")):
        for j, (core, col, name) in enumerate((("ibex", PINK, "Ibex"), ("cv32e40p", BLUE, "CV32E40P"))):
            vals = [float(s[(s.core == core) & (s.design == d) & (s.side == side)].cycles_median.iloc[0]) / 1e6 for d, _ in designs]
            xs = [i + (j - 0.5) * 0.36 for i in range(len(designs))]
            ax.bar(xs, vals, width=0.34, color=col, label=name)
        ax.set_xticks(range(len(designs)))
        ax.set_xticklabels([n for _, n in designs], fontsize=7)
        ax.set_title(f"{side} side", fontsize=8)
        ax.grid(axis="y", color="#dddddd", linewidth=0.5)
        ax.set_axisbelow(True)
    axes[0].set_ylabel("million cycles per session start")
    axes[0].legend(frameon=False, loc="upper left", fontsize=7)
    save(fig, "fig_rtl.pdf")


def fig_sitl():
    from conference_texts import CFGS
    s = pd.read_csv(os.path.join(ROOT, "sitl/results_r6/summary.csv"))
    cmp_ = pd.read_csv(os.path.join(ROOT, "sitl/results_r6/comparison.csv"))
    fig, ax = plt.subplots(figsize=(2.3, 1.9))
    for i, (k, name) in enumerate(CFGS):
        r = s[(s.profile == "sik") & (s.config == k) & (s.metric == "availability_rt_all")].iloc[0]
        col = PINK if k.startswith("hybrid") else (GREY if k == "pqsig_real" else BLUE)
        ax.errorbar(r.value, i, xerr=[[r.value - r.ci_lo], [r.ci_hi - r.value]], fmt="o", color=col, ms=3.5, capsize=2, lw=0.9)
        m = cmp_[(cmp_.profile == "sik") & (cmp_.config == k) & (cmp_.quantity.str.startswith("share acknowledged"))]
        if len(m):
            ax.plot(float(m.mission_model_estimated.iloc[0]), i, marker="x", color=INK, ms=3.5, lw=0)
    ax.set_yticks(range(len(CFGS)))
    ax.set_yticklabels([n for _, n in CFGS], fontsize=7)
    ax.invert_yaxis()
    ax.set_xlabel("share acknowledged within 0.5 s")
    ax.grid(axis="x", color="#dddddd", linewidth=0.5)
    ax.set_axisbelow(True)
    ax.plot([], [], "o", color=INK, ms=3.5, label="SITL measured, 95% CI")
    ax.plot([], [], "x", color=INK, ms=3.5, label="mission model (estimated)")
    ax.legend(frameon=False, fontsize=6.5, loc="lower center", bbox_to_anchor=(0.3, 1.0), ncol=1)
    save(fig, "fig_sitl.pdf")


def main():
    import sys
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    os.makedirs(OUT, exist_ok=True)
    fig_rtl()
    fig_sitl()
    print("wrote docs/conference/fig_rtl.pdf and fig_sitl.pdf")


if __name__ == "__main__":
    main()
