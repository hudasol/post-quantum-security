"""One figure from the simulator output. Author: Huda Mueen.

Run from the repository root: python -m linksim.make_plots
Writes docs/figures/linksim_handshake.png.
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from . import model, sim

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "figures", "linksim_handshake.png")
SAKURA, PEARL, ROSE, INK = "#F4C2D0", "#FFE4EC", "#C9577A", "#5B3A46"


def main():
    p = model.load_params()
    links = model.build_links(p)
    keys = model.LINK_ORDER
    hs = [sim.run_handshake(k, "hybrid", "sr", 0.0, 1, p).wall_s for k in keys]
    pv = [sim.run_handshake(k, "hybrid_prov", "sr", 0.0, 1, p).wall_s
          for k in keys]
    fig, ax = plt.subplots(figsize=(8, 4.2), facecolor=PEARL)
    ax.set_facecolor(PEARL)
    xs = range(len(keys))
    w = 0.38
    ax.bar([x - w / 2 for x in xs], hs, w, color=ROSE,
           label="public key sent")
    ax.bar([x + w / 2 for x in xs], pv, w, color=SAKURA,
           edgecolor=ROSE, label="public key provisioned")
    ax.set_yscale("log")
    ax.set_xticks(list(xs))
    ax.set_xticklabels([links[k].label.replace(" ", "\n", 1) for k in keys],
                       color=INK, fontsize=8)
    ax.set_ylabel("handshake wall time (s, log scale)", color=INK)
    ax.set_title("Hybrid handshake wall time by link, no loss",
                 color=INK)
    ax.tick_params(colors=INK)
    for s in ax.spines.values():
        s.set_color(INK)
    ax.legend(facecolor=PEARL, edgecolor=SAKURA, labelcolor=INK)
    fig.text(0.5, 0.01, model.FOOTER, ha="center", color=INK, fontsize=8)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    fig.savefig(OUT, dpi=160, facecolor=PEARL)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
