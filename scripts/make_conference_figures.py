#!/usr/bin/env python3
"""Figures of the conference paper, drawn from the result files (vector PDF, deterministic, no author metadata).

fig_rtl.pdf: vehicle side cycles of one session start on CV32E40P per design, stacked by primitive class, with
             the range of ML-DSA-44 signing and the measured session median (rtlsim/results/proto_decomposition.csv
             and proto_primitives.csv, label RTL simulated).
fig_sitl.pdf: left, paired differences of the share acknowledged within 0.5 s with 95 percent intervals
              (sitl/results_r6/paired.csv); right, share acknowledged against the deadline
              (sitl/results_r6/deadline_sweep.csv); label SITL measured.
The figures carry no author, because the anonymised paper includes them.
"""
import os
import re
import sys

import matplotlib

matplotlib.use("Agg")
matplotlib.rcParams.update({"font.family": "serif", "font.size": 7.5, "axes.spines.top": False,
                            "axes.spines.right": False, "pdf.fonttype": 42})
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "conference")
INK, BLUE, PINK, GREY, GREEN, GOLD, LIGHT = "#222222", "#3b6ea8", "#c2577a", "#9a9a9a", "#5a8f6a", "#c99a2e", "#d9c2cf"
GROUPS = [("X25519", ("x25519",), BLUE), ("Ed25519", ("ed25519",), "#7fa7d4"), ("ML-KEM-768", ("mlkem768",), GREEN),
          ("ML-DSA-44 sign", ("mldsa44_sign",), PINK), ("ML-DSA-44 verify", ("mldsa44_verify",), LIGHT), ("SHAKE256", ("shake256",), GREY)]


def save(fig, name):
    fig.savefig(os.path.join(OUT, name), metadata={"CreationDate": None, "ModDate": None, "Producer": None, "Creator": None, "Author": None},
                bbox_inches="tight")
    plt.close(fig)


def parts(components):
    """{group: cycles} from 'name xk = cycles; ...'."""
    out = {g: 0.0 for g, _, _ in GROUPS}
    for p in components.split(";"):
        m = re.match(r"\s*(\S+) x(\d+) = (\d+)", p)
        if not m:
            continue
        name, cyc = m.group(1), float(m.group(3))
        for g, prefixes, _ in GROUPS:
            if name.startswith(prefixes):
                out[g] += cyc
                break
    return out


def fig_rtl():
    d = pd.read_csv(os.path.join(ROOT, "rtlsim/results/proto_decomposition.csv"))
    pr = pd.read_csv(os.path.join(ROOT, "rtlsim/results/proto_primitives.csv"))
    sign = pr[(pr.core == "cv32e40p") & (pr.operation == "mldsa44_sign")].iloc[0]
    designs = [("classical", "Classical"), ("pq_only", "PQ only"), ("hybrid_f1", "Hybrid, F1"), ("kem_auth", "Design K")]
    fig, ax = plt.subplots(figsize=(3.45, 1.9))
    for i, (k, _) in enumerate(designs):
        r = d[(d.core == "cv32e40p") & (d.design == k) & (d.side == "vehicle")].iloc[0]
        p = parts(r.components)
        left = 0.0
        for g, _, col in GROUPS:
            if p[g]:
                ax.barh(i, p[g] / 1e6, left=left, color=col, height=0.6, label=g if i == 0 or g not in ("X25519", "Ed25519", "SHAKE256") else None)
                left += p[g] / 1e6
        if p["ML-DSA-44 sign"]:
            # range of the stacked total if the one signature took the fastest or the slowest signing observed
            lo = left - (sign.cycles_median - sign.cycles_min) / 1e6
            hi = left + (sign.cycles_max - sign.cycles_median) / 1e6
            ax.plot([lo, hi], [i, i], color=INK, lw=0.8)
            ax.plot([lo, lo], [i - 0.15, i + 0.15], color=INK, lw=0.8)
            ax.plot([hi, hi], [i - 0.15, i + 0.15], color=INK, lw=0.8)
        ax.plot(r.measured_cycles_median / 1e6, i, "o", color=INK, ms=3)
    ax.set_yticks(range(len(designs)))
    ax.set_yticklabels([n for _, n in designs])
    ax.invert_yaxis()
    ax.set_xlabel("million cycles, vehicle side, one session start (CV32E40P)")
    ax.grid(axis="x", color="#dddddd", linewidth=0.5)
    ax.set_axisbelow(True)
    h, lab = ax.get_legend_handles_labels()
    seen = {}
    for hh, ll in zip(h, lab):
        seen.setdefault(ll, hh)
    ax.legend(seen.values(), seen.keys(), frameon=False, fontsize=6.2, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=3,
              handlelength=1.2, columnspacing=0.8)
    save(fig, "fig_rtl.pdf")


def fig_sitl():
    from conference_texts import PAIRS
    p = pd.read_csv(os.path.join(ROOT, "sitl/results_r6/paired.csv"))
    dl = pd.read_csv(os.path.join(ROOT, "sitl/results_r6/deadline_sweep.csv"))
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(3.45, 1.85), gridspec_kw={"width_ratios": [1.15, 1]})
    for i, (k, m, name) in enumerate(PAIRS):
        r = p[(p.profile == "sik") & (p.config == k) & (p.minus_config == m) & (p.metric == "availability_rt_all")].iloc[0]
        col = PINK if "strict" in k else (BLUE if "cache" in k else INK)
        a1.errorbar(r.difference, i, xerr=[[r.difference - r.ci_lo], [r.ci_hi - r.difference]], fmt="o", color=col, ms=3, capsize=1.8, lw=0.8)
    a1.axvline(0, color=GREY, lw=0.6)
    a1.set_yticks(range(len(PAIRS)))
    a1.set_yticklabels([n.replace("$-$", "−") for _, _, n in PAIRS], fontsize=6.3)
    a1.invert_yaxis()
    a1.set_xlabel("paired difference")
    lo = min(-0.04, min(a1.get_xlim()))
    a1.set_xticks([t for t in (-0.06, -0.04, 0.0, 0.04) if lo - 1e-9 <= t <= max(a1.get_xlim())])
    a1.set_xticklabels([("\u2212%g" % -t) if t < 0 else "%g" % t for t in a1.get_xticks()])
    a1.grid(axis="x", color="#dddddd", linewidth=0.5)
    a1.set_axisbelow(True)
    for k, name, col, ls in (("none", "none", GREY, "-"), ("hybrid_published", "hybrid", INK, "-"), ("hybrid_strict", "strict", PINK, "-"),
                             ("kem_auth", "design K", GREEN, "--"), ("pqsig_real", "sig. per cmd", GOLD, "-")):
        z = dl[(dl.profile == "sik") & (dl.config == k)].sort_values("deadline_s")
        if len(z):
            a2.plot(z.deadline_s, z.availability_rt_all, ls, color=col, lw=0.9, marker="o", ms=2, label=name)
    a2.set_xlabel("deadline (s)")
    a2.set_ylabel("share acknowledged")
    a2.set_xticks([0.5, 1, 1.5, 2])
    a2.set_xticklabels(["0.5", "1", "1.5", "2"])
    a2.set_ylim(0, 1)
    a2.set_yticks([0, 0.5, 1])
    a2.grid(color="#dddddd", linewidth=0.5)
    a2.set_axisbelow(True)
    a2.legend(frameon=False, fontsize=5.6, loc="lower center", bbox_to_anchor=(0.45, 1.0), ncol=2, handlelength=1.2, columnspacing=0.6)
    fig.tight_layout(w_pad=0.6)
    save(fig, "fig_sitl.pdf")


def main():
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    os.makedirs(OUT, exist_ok=True)
    fig_rtl()
    fig_sitl()
    print("wrote docs/conference/fig_rtl.pdf and fig_sitl.pdf")


if __name__ == "__main__":
    main()
