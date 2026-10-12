#!/usr/bin/env python3
"""Build all figures from data/evidence.csv (published rows only).

Rules (PROTOCOL sections 6 and 9):
  * every bar is a published value copied from data/evidence.csv; the row ids behind each
    figure are written to plots/<figure>_rows.csv so a reader can trace them;
  * figures 1-3 use ONE source (pqm4 benchmarks.csv, Cortex-M4F, 24 MHz) so series are comparable;
  * figure 6 is arithmetic on published sizes and is captioned "derived (estimate)".
"""
import csv
import math
import re
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "plots"
OUT.mkdir(exist_ok=True)
ROWS = list(csv.DictReader(open(ROOT / "data" / "evidence.csv", newline="", encoding="utf-8")))

# dataviz default palette, first three slots (validated all-pairs, light mode)
C1, C2, C3 = "#2a78d6", "#eb6834", "#1baf7a"
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "text.color": INK,
    "xtick.color": INK2, "ytick.color": INK2, "font.size": 9,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True,
    "font.family": "DejaVu Sans",
})
PQM4_URL = "pqm4/master/benchmarks.csv"
IMPL = lambda r: re.search(r"implementation '(\w+)", r["library"]).group(1)


def save(fig, name, rows_used, caption):
    fig.text(0.01, 0.005, caption, fontsize=7, color=INK2, ha="left", va="bottom", wrap=True)
    fig.savefig(OUT / f"{name}.png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    with open(OUT / f"{name}_rows.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["row_id"])
        for i in sorted(set(rows_used)):
            w.writerow([i])


def pqm4_rows(family):
    return [r for r in ROWS if PQM4_URL in r["source_url"] and r["scheme_family"] == family
            and r["standard_status"] == "final-FIPS-name" and r["cycles"]]


def grouped_cycles(family, ops, impl_order, impl_colors, name, title, params, caption):
    rows = pqm4_rows(family)
    fig, axes = plt.subplots(1, len(params), figsize=(9.2, 3.3), sharey=False)
    used = []
    for ax, p in zip(axes, params):
        w = 0.26
        for k, impl in enumerate(impl_order):
            vals = []
            for op in ops:
                m = [r for r in rows if r["parameter_set"] == p and r["operation"] == op and IMPL(r) == impl]
                if len(m) != 1:
                    raise SystemExit(f"{name}: expected 1 row for {p} {op} {impl}, got {len(m)}")
                vals.append(int(m[0]["cycles"]) / 1e6)
                used.append(m[0]["id"])
            xs = [i + (k - 1) * w for i in range(len(ops))]
            ax.bar(xs, vals, width=w - 0.03, color=impl_colors[impl], label=impl)
        ax.set_xticks(range(len(ops)))
        ax.set_xticklabels(ops)
        ax.set_title(p, fontsize=9, color=INK, loc="left")
        ax.set_ylabel("million cycles")
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, frameon=False, fontsize=8, loc="upper right", ncol=3, title="pqm4 implementation", title_fontsize=8)
    fig.suptitle(title, x=0.01, ha="left", fontsize=10.5, color=INK)
    fig.tight_layout(rect=(0, 0.06, 1, 0.88))
    save(fig, name, used, caption)


def fig1():
    grouped_cycles(
        "ML-KEM", ["keygen", "encaps", "decaps"], ["clean", "m4fspeed", "m4fstack"],
        {"clean": C1, "m4fspeed": C2, "m4fstack": C3}, "fig1_mlkem_cycles",
        "ML-KEM on Cortex-M4F: cycles per operation (published, pqm4 benchmarks.csv)",
        ["ML-KEM-512", "ML-KEM-768", "ML-KEM-1024"],
        "Published numbers, not measured here. Source: pqm4 benchmarks.csv (retrieved 2026-10-11), board not named in the CSV; pqm4 README says 24 MHz, "
        "its L4R5ZI code uses 20 MHz (unresolved). Means as stated by pqm4. 'clean' = PQClean reference C; others = M4F-specific code.")


def fig2():
    grouped_cycles(
        "ML-DSA", ["keygen", "sign", "verify"], ["clean", "m4f", "m4fstack"],
        {"clean": C1, "m4f": C2, "m4fstack": C3}, "fig2_mldsa_cycles",
        "ML-DSA on Cortex-M4F: cycles per operation (published, pqm4 benchmarks.csv)",
        ["ML-DSA-44", "ML-DSA-65", "ML-DSA-87"],
        "Published numbers, not measured here. Source: pqm4 benchmarks.csv (retrieved 2026-10-11; board and clock as in fig. 1 caveat). Signing is a mean over a "
        "variable-time rejection loop; verification is the firmware-signing-relevant operation.")


def fig3():
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.3))
    used = []
    spec = [
        ("ML-KEM", "decaps", ["ML-KEM-512", "ML-KEM-768", "ML-KEM-1024"], ["clean", "m4fspeed", "m4fstack"],
         {"clean": C1, "m4fspeed": C2, "m4fstack": C3}, "ML-KEM decapsulation: stack"),
        ("ML-DSA", "sign", ["ML-DSA-44", "ML-DSA-65", "ML-DSA-87"], ["clean", "m4f", "m4fstack"],
         {"clean": C1, "m4f": C2, "m4fstack": C3}, "ML-DSA signing: stack"),
    ]
    for ax, (fam, op, params, impls, cols, title) in zip(axes, spec):
        rows = pqm4_rows(fam)
        w = 0.26
        for k, impl in enumerate(impls):
            vals = []
            for p in params:
                m = [r for r in rows if r["parameter_set"] == p and r["operation"] == op and IMPL(r) == impl]
                if len(m) != 1 or not m[0]["stack_bytes"]:
                    raise SystemExit(f"fig3 missing {fam} {p} {op} {impl}")
                vals.append(int(m[0]["stack_bytes"]) / 1024)
                used.append(m[0]["id"])
            ax.bar([i + (k - 1) * w for i in range(len(params))], vals, width=w - 0.03, color=cols[impl], label=impl)
        ax.set_xticks(range(len(params)))
        ax.set_xticklabels(params)
        ax.set_title(title, fontsize=9, loc="left", color=INK)
        ax.set_ylabel("stack, KiB")
    h, l = axes[0].get_legend_handles_labels()
    h2, l2 = axes[1].get_legend_handles_labels()
    fig.legend(h + [x for x, y in zip(h2, l2) if y not in l], l + [y for y in l2 if y not in l],
               frameon=False, fontsize=8, loc="upper right", ncol=4, title="pqm4 implementation", title_fontsize=8)
    fig.suptitle("Stack usage on Cortex-M4F (published, pqm4 benchmarks.csv)", x=0.01, ha="left", fontsize=10.5)
    fig.tight_layout(rect=(0, 0.06, 1, 0.88))
    save(fig, "fig3_stack", used, "Published numbers, not measured here. Source: pqm4 benchmarks.csv (retrieved 2026-10-11; board/clock ambiguity as in fig. 1). "
         "pqm4 stack figures exclude caller-provided buffers. Orange = m4fspeed (ML-KEM) and m4f (ML-DSA); green = m4fstack.")


def size_rows():
    return [r for r in ROWS if r["size_kind"] == "standard" and "signature" in r["operation"]]


def short(r):
    p = r["parameter_set"].replace("SLH-DSA-{SHA2,SHAKE}-", "SLH-DSA-")
    return p


def fig4():
    rows = size_rows()
    rows = sorted(rows, key=lambda r: int(r["key_or_sig_size_bytes"]))
    fig, ax = plt.subplots(figsize=(7.6, 5.2))
    colors = {"ML-DSA": C1, "SLH-DSA": C2, "XMSS": C3}
    ys = list(range(len(rows)))
    ax.barh(ys, [int(r["key_or_sig_size_bytes"]) for r in rows],
            color=[colors[r["scheme_family"]] for r in rows], height=0.62)
    ax.set_yticks(ys)
    ax.set_yticklabels([short(r) for r in rows], fontsize=8)
    for y, r in zip(ys, rows):
        ax.text(int(r["key_or_sig_size_bytes"]) * 1.05, y, f"{int(r['key_or_sig_size_bytes']):,}", va="center", fontsize=7.5, color=INK2)
    ax.set_xscale("log")
    ax.set_xlim(500, 120000)
    ax.axvline(255, color=INK2, lw=0.8, ls="--")
    ax.set_xlabel("signature size, bytes (log scale)")
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in colors.values()]
    ax.legend(handles, list(colors), frameon=False, fontsize=8, loc="lower right")
    ax.set_title("Signature sizes defined by the standards", loc="left", fontsize=10.5, color=INK)
    ax.set_xlim(40, 120000)
    ax.text(290, len(rows) - 0.55, "255 B: MAVLink 2 maximum payload", fontsize=7.5, color=INK2, va="bottom")
    ax.set_ylim(-0.6, len(rows) + 0.2)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    save(fig, "fig4_sizes", [r["id"] for r in rows],
         "Published sizes (FIPS 204, FIPS 205, RFC 8391 Table 3; retrieved 2026-10-11). 255 B marker: mavlink.io serialization guide.")


def fig5():
    ids = {"S2-0319": "LMS (SHA-256, h=10)", "S2-0322": "XMSS ROBUST (SHA-256, h=10)"}
    sel = [r for r in ROWS if r["id"] in ids]
    if len(sel) != 2:
        raise SystemExit("fig5 rows missing")
    fig, ax = plt.subplots(figsize=(5.8, 2.6))
    vals = [int(r["cycles"]) / 1e6 for r in sel]
    ax.barh([0, 1], vals, color=[C1, C3], height=0.5)
    ax.set_yticks([0, 1])
    ax.set_yticklabels([ids[r["id"]] for r in sel])
    for y, v in enumerate(vals):
        ax.text(v + 0.2, y, f"{v:.2f} M", va="center", fontsize=8, color=INK2)
    ax.set_xlabel("verification, million cycles")
    ax.set_xlim(0, 16)
    ax.set_title("Stateful hash-based verification on STM32F4DISCOVERY (published, slides)", loc="left", fontsize=9.5, color=INK)
    fig.tight_layout(rect=(0, 0.14, 1, 1))
    save(fig, "fig5_hash_verify", [r["id"] for r in sel],
         "Published numbers from conference slides (Campos et al., 2020); parameter variants and clock not stated; one setup, "
         "do not compare with fig 1-2.")


def fig6():
    """Derived arithmetic: chunks = ceil(N / C). N from published standard sizes; C from vendor/spec pages (S3)."""
    pick = ["ML-DSA-44", "ML-DSA-65", "ML-DSA-87", "SLH-DSA-{SHA2,SHAKE}-128s", "XMSS-SHA2_10_256"]
    rows = [r for r in size_rows() if r["parameter_set"] in pick]
    rows.sort(key=lambda r: int(r["key_or_sig_size_bytes"]))
    chunk = {"MAVLink FTP data per message (239 B)": 239, "LoRaWAN EU868 DR0 payload (51 B)": 51}
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.0))
    for ax, (label, c), col in zip(axes, chunk.items(), (C1, C2)):
        vals = [math.ceil(int(r["key_or_sig_size_bytes"]) / c) for r in rows]
        ax.barh(range(len(rows)), vals, color=col, height=0.55, hatch="//", edgecolor=SURFACE, lw=0)
        ax.set_yticks(range(len(rows)))
        ax.set_yticklabels([short(r) for r in rows], fontsize=8)
        for y, v in enumerate(vals):
            ax.text(v + max(vals) * 0.015, y, str(v), va="center", fontsize=8, color=INK2)
        ax.set_title(label, loc="left", fontsize=9, color=INK)
        ax.set_xlabel("messages / frames needed for one signature")
        ax.set_xlim(0, max(vals) * 1.15)
    fig.suptitle("ESTIMATE (derived): how many frames one signature needs", x=0.01, ha="left", fontsize=10.5)
    fig.tight_layout(rect=(0, 0.07, 1, 0.94))
    save(fig, "fig6_chunks_derived", [r["id"] for r in rows],
         "Derived estimate = ceil(published signature size / published payload size). Ignores headers, acknowledgements, "
         "retransmission. Payload sizes: mavlink.io FTP page (251 B payload minus 12 B header); TTN LoRaWAN EU868 parameters.")


if __name__ == "__main__":
    for f in (fig1, fig2, fig3, fig4, fig5, fig6):
        f()
        print("ok", f.__name__)
