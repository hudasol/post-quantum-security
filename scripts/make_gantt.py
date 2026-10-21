#!/usr/bin/env python3
"""Draw the work plan of the robotics proposal as a Gantt chart. Author: Huda Mueen.

Reads data/proposal/plan.csv (tasks, label planned) and data/proposal/milestones.csv, and writes
docs/figures/proposal/gantt.png. Phases are ordinal, so they get one pink hue stepped from light to
dark; every bar carries its task id and every phase is named on the axis, so no reading depends on
colour alone. Milestones are dark diamonds with their id. The ramp is monotone in lightness and its
adjacent steps stay apart under colour vision deficiency (checked with a palette validator); as an ordinal
ramp it is not meant to pass the categorical checks, which is why every phase is also named in text.
Run: python3 scripts/make_gantt.py
"""
import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "figures" / "proposal" / "gantt.png"
# one hue (pink), light to dark, for the ordinal phases; ink and milestone colours stay neutral or dark
PINKS = ["#F2A7C6", "#E2779F", "#CC4F86", "#A8346C", "#7E2152", "#521236"]
INK = "#2B1B24"
MUTED = "#6E5A66"
MILESTONE = "#4A1031"


def read(rel):
    with open(ROOT / rel, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def phases(tasks):
    out = []
    for t in tasks:
        if t["phase"] not in out:
            out.append(t["phase"])
    return out


def draw(tasks, milestones, out=OUT):
    ph = phases(tasks)
    colour = {p: PINKS[min(i, len(PINKS) - 1)] for i, p in enumerate(ph)}
    n = len(tasks)
    fig, ax = plt.subplots(figsize=(10, 0.42 * n + 1.8), dpi=150)
    for i, t in enumerate(tasks):
        s, e = int(t["start_month"]), int(t["end_month"])
        y = n - 1 - i
        ax.barh(y, e - s + 1, left=s - 0.5, height=0.62, color=colour[t["phase"]], edgecolor="white", linewidth=2)
        dark = PINKS.index(colour[t["phase"]]) >= 3
        ax.text(s - 0.4, y, t["id"], va="center", ha="left", fontsize=8, color="white" if dark else INK)
    labels = [f"{t['id']}  {t['phase']}" for t in tasks]
    ax.set_yticks(range(n))
    ax.set_yticklabels(list(reversed(labels)), fontsize=8, color=INK)
    for m in milestones:
        x = int(m["month"]) + 0.5
        ax.plot([x], [n - 0.2], marker="D", markersize=8, color=MILESTONE, clip_on=False)
        ax.text(x, n + 0.25, m["id"], ha="center", va="bottom", fontsize=8, color=INK)
    last = max(int(t["end_month"]) for t in tasks)
    ax.set_xlim(0.5, last + 0.5)
    ax.set_ylim(-0.6, n + 0.9)
    ax.set_xticks(range(1, last + 1))
    ax.set_xlabel("Month of the project (planned)", fontsize=9, color=INK)
    ax.grid(axis="x", color="#EBDDE4", linewidth=0.8)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(MUTED)
    ax.tick_params(colors=MUTED)
    ax.set_title("Work plan: tasks by phase and milestones with decision gates (label: planned)", fontsize=10, color=INK, loc="left", pad=22)
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, facecolor="white")
    plt.close(fig)
    return out


def main():
    p = draw(read("data/proposal/plan.csv"), read("data/proposal/milestones.csv"))
    print(f"wrote {p.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
