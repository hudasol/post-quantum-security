"""Figures for the second round link study. Author: Huda Mueen.

Reads linksim/results/*.csv (written by python -m linksim.study) and writes
docs/figures/linksim_*.png. Every figure carries its evidence label
(estimated) and the seeds behind it. Published values are never drawn on
the same axis as estimates; the validation against a published figure is a
table in docs/LINKSIM_STUDY.md, not a plot.
"""
import csv
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from . import model

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "linksim", "results")
FIG = os.path.join(ROOT, "docs", "figures")
C = ["#2a78d6", "#eb6834", "#1baf7a", "#8a5cd6", "#c9577a", "#52514e"]
SURFACE, INK, GRID = "#fcfcfb", "#0b0b0b", "#e4e3df"
NAMES = dict(zip(model.LINK_ORDER, ["SiK 64 kbps", "LoRaWAN EU868 DR0",
                                    "IEEE 802.15.4", "BLE", "Generic 1 Mbps",
                                    "Generic 10 kbps"]))


def _read(name):
    with open(os.path.join(RES, name), newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _config():
    return {r["key"]: r["value"] for r in _read("config.csv")}


def _style():
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE, "axes.edgecolor": GRID, "font.size": 8,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
        "axes.axisbelow": True})


def _footer(fig, cfg, extra=""):
    txt = ("Label: estimated (%s). %s trials per cell, seeds %s. %s" % (
        model.FOOTER, cfg["trials_per_cell"], cfg["seeds"], extra)).strip()
    fig.text(0.01, 0.005, txt, fontsize=6.5, color=INK, ha="left",
             va="bottom", wrap=True)


def fig_mc(cfg):
    rows = [r for r in _read("mc_grid.csv") if r["variant"] == "hybrid"
            and r["proto"] == "sr" and float(r["max_retries"]) == 20]
    fig, ax = plt.subplots(figsize=(8, 4.2))
    for i, k in enumerate(model.LINK_ORDER):
        sel = sorted((r for r in rows if r["link"] == k),
                     key=lambda r: float(r["loss"]))
        x = [100 * float(r["loss"]) for r in sel]
        med = [float(r["median"]) for r in sel]
        lo = [m - float(r["p05"]) for m, r in zip(med, sel)]
        hi = [float(r["p95"]) - m for m, r in zip(med, sel)]
        ax.errorbar(x, med, yerr=[lo, hi], marker="o", ms=3, capsize=2,
                    color=C[i], label=NAMES[k])
    ax.set_yscale("log")
    ax.set_xlabel("frame loss (percent, independent per frame)")
    ax.set_ylabel("handshake wall time (s, log scale)")
    ax.set_title("Hybrid handshake, key sent, selective repeat: median and "
                 "5th to 95th percentile")
    ax.legend(fontsize=7, ncol=2)
    _footer(fig, cfg, "Zero loss cells are deterministic.")
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(os.path.join(FIG, "linksim_mc_loss.png"), dpi=160)
    plt.close(fig)


def fig_sweeps(cfg):
    rows = _read("sweeps.csv")
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.8))
    for ax, axis, title in ((axes[0], "payload", "fragment payload (B)"),
                            (axes[1], "rate_scale", "rate multiplier")):
        for i, k in enumerate(model.LINK_ORDER):
            sel = sorted((r for r in rows if r["link"] == k
                          and r["axis"] == axis and float(r["loss"]) == 0.05),
                         key=lambda r: float(r["value"]))
            if not sel:
                continue
            ax.plot([float(r["value"]) for r in sel],
                    [float(r["mean"]) for r in sel], marker="o", ms=3,
                    color=C[i], label=NAMES[k])
        ax.set_yscale("log")
        ax.set_xlabel(title)
        ax.set_ylabel("mean wall time at 5 percent loss (s, log)")
    axes[0].set_title("Fragment payload sweep")
    axes[1].set_title("Rate sweep")
    axes[1].legend(fontsize=7)
    _footer(fig, cfg)
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    fig.savefig(os.path.join(FIG, "linksim_sweeps.png"), dpi=160)
    plt.close(fig)


def fig_lowrate(cfg):
    rows = [r for r in _read("lowrate.csv") if r["variant"] == "hybrid"
            and int(r["mac_overhead_bytes"]) == 0]
    fig, ax = plt.subplots(figsize=(6.5, 3.6))
    for i, prof in enumerate(("eu868_dr0", "eu868_dr5", "us915_dr0")):
        sel = sorted((r for r in rows if r["profile"] == prof),
                     key=lambda r: int(r["frag_hdr_bytes"]))
        ax.plot([int(r["frag_hdr_bytes"]) for r in sel],
                [int(r["fragments"]) for r in sel], marker="o", ms=3,
                color=C[i], label=sel[0]["label"])
    ax.set_xlabel("fragment header per frame (B, ASSUMPTION swept)")
    ax.set_ylabel("fragments for the hybrid handshake")
    ax.set_title("Fragments on the lowest rate LoRaWAN profiles")
    ax.legend(fontsize=7)
    _footer(fig, cfg, "Deterministic arithmetic; no seed involved.")
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    fig.savefig(os.path.join(FIG, "linksim_lowrate.png"), dpi=160)
    plt.close(fig)


def main():
    _style()
    os.makedirs(FIG, exist_ok=True)
    cfg = _config()
    fig_mc(cfg)
    fig_sweeps(cfg)
    fig_lowrate(cfg)
    print("wrote docs/figures/linksim_mc_loss.png, linksim_sweeps.png, "
          "linksim_lowrate.png")


if __name__ == "__main__":
    main()
