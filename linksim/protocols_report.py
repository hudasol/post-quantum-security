"""Generate docs/PROTOCOL_SIM.md and the protocol figures from
linksim/results/protocols_*.csv. Author: Huda Mueen.

Run from the repository root after python -m linksim.protocols:
    python -m linksim.protocols_report
Every number in the document is read from the result files written by
linksim/protocols.py. Label: modelled.
"""
import csv
import os

from . import model, protocols as P

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "linksim", "results")
DOC = os.path.join(ROOT, "docs", "PROTOCOL_SIM.md")
PINK = ["#d63384", "#f48fb1", "#ad1457", "#f8bbd0", "#880e4f", "#fce4ec"]


def read(name, res=None):
    with open(os.path.join(res or RES, name), newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return float("nan")


def tfmt(s):
    """Human readable duration from seconds."""
    s = f(s)
    if s != s:
        return "n/a"
    if s < 0.01:
        return "%.2f ms" % (1000 * s)
    if s < 1:
        return "%.0f ms" % (1000 * s)
    if s < 120:
        return "%.2f s" % s
    if s < 7200:
        return "%.1f min" % (s / 60)
    return "%.1f h" % (s / 3600)


def pfmt(x):
    x = f(x)
    return "n/a" if x != x else "%.1f%%" % (100 * x)


def cfg_name(r):
    return "%s / %s" % (r["protocol"], r["variant"])


def figures(grid, sobol_rows, res=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.ticker
    res = res or RES
    out = []
    # Figure 1: time to first authenticated message at 5 percent loss.
    fig, axes = plt.subplots(1, len(P.LINKS), figsize=(14, 4.6), sharey=False)
    for ax, lk in zip(axes, P.LINKS):
        sel = [r for r in grid if r["scenario"] == "ttfam" and r["link"] == lk and f(r["loss"]) == 0.05]
        ys = [f(r["wall_mean"]) for r in sel]
        cols = [PINK[{"classical": 3, "hybrid": 0, "pq_only": 2, "per_message": 4}[r["variant"]]] for r in sel]
        ax.barh(range(len(sel)), ys, color=cols, edgecolor="#880e4f")
        ax.set_yticks(range(len(sel)))
        ax.set_yticklabels([cfg_name(r) for r in sel], fontsize=6)
        ax.set_xscale("log")
        ax.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
        ax.set_title(P.LINK_LABEL[lk], fontsize=9)
        ax.set_xlabel("mean seconds (log)", fontsize=8)
    fig.suptitle("Time to first authenticated message, 5 percent loss (modelled; %s trials per cell; seeds %d + i)"
                 % (grid[0]["trials"], P.SEED), fontsize=10)
    fig.tight_layout()
    p1 = os.path.join(res, "fig_protocols_ttfam.svg")
    fig.savefig(p1)
    plt.close(fig)
    out.append(p1)
    # Figure 2: probability of completion within 60 s against loss, LoRaWAN DR5 and 802.15.4.
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    for ax, (lk, dl) in zip(axes, (("lora_dr5", "1800"), ("ieee802154", "2"))):
        for i, pr in enumerate(P.PROTOCOLS):
            sel = [r for r in grid if r["scenario"] == "ttfam" and r["link"] == lk and r["protocol"] == pr
                   and r["variant"] == "hybrid"]
            sel.sort(key=lambda r: f(r["loss"]))
            ax.plot([100 * f(r["loss"]) for r in sel], [f(r["p_within_%ss" % dl]) for r in sel],
                    marker="o", color=PINK[[0, 2, 4, 1][i]], label=pr + " / hybrid")
        ax.set_title("%s: P(first authenticated message within %s s)" % (P.LINK_LABEL[lk], dl), fontsize=9)
        ax.set_xlabel("frame loss, percent")
        ax.set_ylim(-0.05, 1.05)
        ax.legend(fontsize=7)
    fig.suptitle("Completion within a deadline (modelled; seeds %d + i)" % P.SEED, fontsize=10)
    fig.tight_layout()
    p2 = os.path.join(res, "fig_protocols_deadline.svg")
    fig.savefig(p2)
    plt.close(fig)
    out.append(p2)
    # Figure 3: Sobol total order indices.
    if sobol_rows:
        cases = []
        for r in sobol_rows:
            k = (r["link"], r["protocol"])
            if k not in cases:
                cases.append(k)
        names = [n for n, _, _ in P.SOBOL_INPUTS]
        fig, ax = plt.subplots(figsize=(10, 4.2))
        w = 0.8 / len(cases)
        for i, c in enumerate(cases):
            vals = [f([r for r in sobol_rows if (r["link"], r["protocol"]) == c and r["input"] == n][0]["ST"])
                    for n in names]
            ax.bar([j + i * w for j in range(len(names))], vals, w, color=PINK[i % len(PINK)],
                   edgecolor="#880e4f", label="%s %s hybrid" % c)
        ax.set_xticks([j + 0.4 - w / 2 for j in range(len(names))])
        ax.set_xticklabels(names, rotation=20, fontsize=7)
        ax.set_ylabel("total order Sobol index")
        ax.set_title("Sensitivity of time to first authenticated message (modelled; Saltelli N = %s; seed %d)"
                     % (sobol_rows[0]["N"], P.SEED), fontsize=9)
        ax.legend(fontsize=7)
        fig.tight_layout()
        p3 = os.path.join(res, "fig_protocols_sobol.svg")
        fig.savefig(p3)
        plt.close(fig)
        out.append(p3)
    return out


def _order(rows, lk, col):
    sel = [r for r in rows if r["link"] == lk]
    return [r["protocol"] + "/" + r["variant"] for r in sorted(sel, key=lambda r: f(r[col]))]


def build_doc(res=None):
    res = res or RES
    grid = read("protocols_grid.csv", res)
    flights = read("protocols_flights.csv", res)
    added = read("protocols_added_latency.csv", res)
    flips = read("protocols_rank_flips.csv", res)
    sob = read("protocols_sobol.csv", res)
    sflips = read("protocols_sobol_flips.csv", res)
    cfg = {r["key"]: r["value"] for r in read("protocols_config.csv", res)}
    trials = cfg["trials_per_cell"]
    L = []
    a = L.append
    a("# Protocol simulation over narrow links (fourth round)")
    a("")
    a("Author: Huda Mueen. Generated by `python -m linksim.protocols_report` from `linksim/results/protocols_*.csv`, "
      "which `python -m linksim.protocols` writes; do not edit by hand. Label of every result: **modelled**. "
      "Each cell with loss uses %s seeded trials (seed of trial i is %d + i); zero loss cells are deterministic "
      "single runs. Intervals are 95 percent: mean plus or minus 1.96 standard errors, Wilson score for "
      "proportions. Messages are byte counts; no cryptography is computed and no protocol is implemented. "
      "Configuration: `linksim/results/protocols_config.csv`." % (trials, P.SEED))
    a("")
    from . import validate_v4
    pv = model.load_params()
    diag = [r for r in validate_v4.diagnosis(pv) if r["applied"] in ("baseline", "yes")]
    factor = diag[-1]["factor_below_low_after"]
    nlora = len([r for r in validate_v4.validation(pv) if r["figure"].startswith("LoRa")
                 and "formula" in r["model"] and abs(r["pct_error"]) < 1.0])
    a("The link models carry the validation status of Section 4.4 of `docs/LINKSIM_STUDY.md`: the LoRa time on "
      "air formula matches %d published examples within 1 percent; the IEEE 802.15.4 frame model is still a factor "
      "of %.1f faster than the only published 802.15.4 figure found (a prose statement in ePrint 2021/781), so "
      "802.15.4 times here are optimistic; duty cycle and loss handling are checked only against closed forms, "
      "not against measurements." % (nlora, factor))
    a("")
    a("## Summary (5 percent loss)")
    a("")
    for lk in P.LINKS:
        sel = {(r["protocol"], r["variant"]): r for r in grid
               if r["scenario"] == "ttfam" and r["link"] == lk and f(r["loss"]) == 0.05}
        hyb = sorted([r for (pr, v), r in sel.items() if v == "hybrid"], key=lambda r: f(r["wall_mean"]))
        if not hyb:
            continue
        fast, slow = hyb[0], hyb[-1]
        ratios = ", ".join("%s %.1f" % (pr, f(sel[(pr, "hybrid")]["wall_mean"]) / f(sel[(pr, "classical")]["wall_mean"]))
                           for pr in P.PROTOCOLS)
        raw = sel.get(P.RAW)
        a("- %s: fastest hybrid profile %s (%s), slowest %s (%s), a ratio of %.1f. Hybrid over classical time "
          "ratio by profile: %s. One raw ML-DSA-44 signed command alone takes %s." % (
              P.LINK_LABEL[lk], fast["protocol"], tfmt(fast["wall_mean"]), slow["protocol"], tfmt(slow["wall_mean"]),
              f(slow["wall_mean"]) / f(fast["wall_mean"]), ratios, tfmt(raw["wall_mean"]) if raw else "n/a"))
    a("")
    a("## 1. Profiles and message sizes")
    a("")
    a("Variants: classical (X25519 and Ed25519), hybrid (X25519 plus ML-KEM-768 shares, `data/evidence.csv` "
      "S3-018 and S3-019, with ML-DSA-44 signatures), post quantum only (ML-KEM-768 and ML-DSA-44, S2-0399, "
      "S2-0401, S2-0406, S2-0407), and raw ML-DSA-44 signature per message (no session) as the infeasible bound. "
      "Profiles are simplified: DTLS 1.3 with mutual certificate authentication and no cookie exchange; EDHOC "
      "signature method with credentials by reference (message sizes from draft-ietf-lake-edhoc-17 Figure 1, "
      "`data/raw/S12_link_sources.md` line 79, with the 32 B share and 64 B signature replaced by the variant's); "
      "a MAVLink 2 style signed stream whose session key comes from a four flight post quantum handshake with pinned "
      "keys, the same handshake as the mission study and the formal models with design change F1 of "
      "`docs/FORMAL_VERIFICATION.md` (ground and vehicle each sign the transcript and send a key confirmation tag; "
      "earlier rounds used three flights with one signature and the public key on the air); and a "
      "DDS Security style three message authentication handshake carrying certificates both ways. Certificate "
      "overhead, DTLS, OSCORE, CoAP and DDS framing are ASSUMPTIONS (`linksim/params.csv`) swept in Section 6. "
      "Sizes and link parameters shared with other studies come from `data/shared_inputs.csv`. "
      "Every flight uses the selective repeat transport of `linksim/sim.py`.")
    a("")
    a("| protocol | variant | handshake flights and first command, bytes (A ground, B vehicle) | rekey flights, bytes |")
    a("|---|---|---|---|")
    for pr, v in P.configs():
        hs = [r for r in flights if r["protocol"] == pr and r["variant"] == v and r["scenario"] == "ttfam"]
        rk = [r for r in flights if r["protocol"] == pr and r["variant"] == v and r["scenario"] == "rekey"]
        a("| %s | %s | %s | %s |" % (pr, v, "; ".join("%s %s %s" % (r["sender"], r["message"], r["bytes"]) for r in hs),
                                     "; ".join("%s %s" % (r["sender"], r["bytes"]) for r in rk) or "n/a"))
    a("")
    a("Links: LoRaWAN EU868 DR0 and DR5 with the time on air formula, 13 B LoRaWAN frame overhead and a 1 percent "
      "duty cycle per side; IEEE 802.15.4 with the fourth round frame model (PHY header, 6LoWPAN fragmentation, "
      "MAC acknowledgement, inter frame spacing, CCA and mean backoff, turnaround); SiK at the 64 kbps air rate of `linksim/params.csv`. No Wi-Fi or "
      "cellular profile is simulated, because no parameters for them were retrieved.")
    a("")
    a("## 2. Time to first authenticated message")
    a("")
    a("Handshake followed by one authenticated command (42 B MAVLink 2 command plus the protocol's protection "
      "overhead). Loss 5 percent. Duty budget is the air time of the busier side divided by the 1 percent budget "
      "of one hour (1.0 means a full hour of budget); utilisation is air time (including MAC timing on 802.15.4) "
      "over wall time.")
    a("")
    a("| link | protocol / variant | handshake mean | first message mean (95% interval) | p95 | completed | P within 10 s | P within 600 s | duty budget hours | utilisation |")
    a("|---|---|---|---|---|---|---|---|---|---|")
    for lk in P.LINKS:
        for r in grid:
            if r["scenario"] != "ttfam" or r["link"] != lk or f(r["loss"]) != 0.05:
                continue
            a("| %s | %s | %s | %s (%s to %s) | %s | %s | %s | %s | %s | %s |" % (
                P.LINK_LABEL[lk], cfg_name(r), tfmt(r.get("handshake_mean_s")), tfmt(r["wall_mean"]),
                tfmt(r["wall_ci_lo"]), tfmt(r["wall_ci_hi"]), tfmt(r["wall_p95"]), pfmt(r["completion"]),
                pfmt(r["p_within_10s"]), pfmt(r["p_within_600s"]),
                "n/a" if not r.get("duty_budget_hours") else "%.3g" % f(r["duty_budget_hours"]),
                "%.2f" % f(r["utilisation_mean"])))
    a("")
    a("Loss sweep, mean time to first authenticated message (hybrid variants and the raw bound):")
    a("")
    a("| link | protocol / variant | " + " | ".join("loss %g%%" % (100 * x) for x in P.LOSSES) + " |")
    a("|---|---|" + "---|" * len(P.LOSSES))
    for lk in P.LINKS:
        for pr, v in P.configs():
            if v not in ("hybrid", "per_message"):
                continue
            cells = []
            for x in P.LOSSES:
                r = [r for r in grid if r["scenario"] == "ttfam" and r["link"] == lk and r["protocol"] == pr
                     and r["variant"] == v and abs(f(r["loss"]) - x) < 1e-12][0]
                cells.append(tfmt(r["wall_mean"]) + ("" if f(r["completion"]) == 1 else " (%s done)" % pfmt(r["completion"])))
            a("| %s | %s / %s | %s |" % (P.LINK_LABEL[lk], pr, v, " | ".join(cells)))
    a("")
    a("![Time to first authenticated message](../linksim/results/fig_protocols_ttfam.svg)")
    a("")
    a("_Figure 1. Mean time to first authenticated message at 5 percent loss, log scale; modelled, %s trials per "
      "cell, seeds %d + i._" % (trials, P.SEED))
    a("")
    a("![Completion within a deadline](../linksim/results/fig_protocols_deadline.svg)")
    a("")
    a("_Figure 2. Probability that the first authenticated message arrives within the deadline, hybrid variants; "
      "modelled, seeds %d + i._" % P.SEED)
    a("")
    a("## 3. Rekey inside a session")
    a("")
    a("A fresh ephemeral key exchange without certificates or signatures (ASSUMPTION for every profile), loss 5 percent.")
    a("")
    a("| link | protocol / variant | bytes | mean (95% interval) | completed | duty budget hours |")
    a("|---|---|---|---|---|---|")
    for lk in P.LINKS:
        for r in grid:
            if r["scenario"] == "rekey" and r["link"] == lk and f(r["loss"]) == 0.05:
                a("| %s | %s | %s | %s (%s to %s) | %s | %s |" % (
                    P.LINK_LABEL[lk], cfg_name(r), r["bytes_total"], tfmt(r["wall_mean"]), tfmt(r["wall_ci_lo"]),
                    tfmt(r["wall_ci_hi"]), pfmt(r["completion"]),
                    "n/a" if not r.get("duty_budget_hours") else "%.3g" % f(r["duty_budget_hours"])))
    a("")
    a("## 4. Firmware update transfer")
    a("")
    a("Image of %d B (ASSUMPTION) plus one signature (Ed25519 64 B or ML-DSA-44 2,420 B), one transfer, no "
      "resumption across sessions." % int(model.load_params()["fw_image_bytes"]))
    a("")
    a("| link | signature | loss | mean (95% interval) | completed | P within 3600 s | duty budget hours |")
    a("|---|---|---|---|---|---|---|")
    for lk in P.LINKS:
        for r in grid:
            if r["scenario"] == "firmware" and r["link"] == lk and f(r["loss"]) in (0.0, 0.05, 0.2):
                a("| %s | %s | %g%% | %s (%s to %s) | %s | %s | %s |" % (
                    P.LINK_LABEL[lk], "Ed25519" if r["variant"] == "classical" else "ML-DSA-44",
                    100 * f(r["loss"]), tfmt(r["wall_mean"]), tfmt(r["wall_ci_lo"]), tfmt(r["wall_ci_hi"]),
                    pfmt(r["completion"]), pfmt(r["p_within_3600s"]),
                    "n/a" if not r.get("duty_budget_hours") else "%.3g" % f(r["duty_budget_hours"])))
    a("")
    a("## 5. Added latency per authenticated command after the handshake")
    a("")
    a("Mean delivery time of the protected command minus the unprotected 42 B command on the same seeds.")
    a("")
    a("| link | protocol | overhead B | " + " | ".join("loss %g%%" % (100 * x) for x in P.LOSSES) + " |")
    a("|---|---|---|" + "---|" * len(P.LOSSES))
    for lk in P.LINKS:
        for pr in list(P.PROTOCOLS) + ["raw_mldsa44"]:
            sel = sorted([r for r in added if r["link"] == lk and r["protocol"] == pr], key=lambda r: f(r["loss"]))
            if not sel:
                continue
            a("| %s | %s | %s | %s |" % (P.LINK_LABEL[lk], pr, sel[0]["overhead_bytes"],
                                         " | ".join(tfmt(r["added_mean_s"]) for r in sel)))
    a("")
    a("## 6. Sensitivity and ranking flips")
    a("")
    a("Variance based sensitivity (SALib Saltelli sample, N = %s, %s model runs per case, one run per sample "
      "with the same seed %d for every sample, so the loss pattern is a fixed function of the loss input) of the time to first authenticated message for the hybrid DTLS 1.3 and "
      "EDHOC profiles on IEEE 802.15.4 and LoRaWAN DR5. Inputs and ranges: %s. Indices are total order (ST) with "
      "SALib bootstrap 95 percent half widths. Each profile uses only some of the framing inputs; an input a "
      "profile does not use has a true index of zero, so its estimate shows the numerical noise floor." % (
          cfg["sobol_N"], sob[0]["samples"] if sob else "0", P.SEED,
          "; ".join("%s %g to %g" % s for s in P.SOBOL_INPUTS)))
    a("")
    a("| link | protocol | input | S1 | ST (plus or minus) |")
    a("|---|---|---|---|---|")
    for r in sob:
        a("| %s | %s | %s | %.3f | %.3f (%.3f) |" % (P.LINK_LABEL[r["link"]], r["protocol"], r["input"], f(r["S1"]),
                                                     f(r["ST"]), f(r["ST_conf"])))
    a("")
    a("![Sobol indices](../linksim/results/fig_protocols_sobol.svg)")
    a("")
    a("_Figure 3. Total order Sobol indices; modelled, seed %d._" % P.SEED)
    a("")
    a("Ranking flip across the sensitivity sample (same inputs for both protocols):")
    a("")
    a("| link | comparison | samples | count | fraction (Wilson 95%) |")
    a("|---|---|---|---|---|")
    for r in sflips:
        a("| %s | %s | %s | %s | %s (%s to %s) |" % (P.LINK_LABEL[r["link"]], r["comparison"], r["samples"], r["count"],
                                                     pfmt(r["fraction"]), pfmt(r["fraction_lo"]), pfmt(r["fraction_hi"])))
    a("")
    a("Ranking flips across the loss sweep (order of mean time to first authenticated message compared with the "
      "order at zero loss). A flip whose 95 percent intervals overlap is not resolved by the trials.")
    a("")
    if flips:
        a("| link | loss | now faster | now slower | intervals overlap |")
        a("|---|---|---|---|---|")
        for r in flips:
            a("| %s | %g%% | %s | %s | %s |" % (P.LINK_LABEL[r["link"]], 100 * f(r["loss"]), r["now_faster"],
                                               r["now_slower"], r["intervals_overlap"]))
    else:
        a("No configuration changes rank on any link across the loss sweep.")
    a("")
    lov = read("protocols_lorawan_overhead.csv", res) if os.path.exists(os.path.join(res, "protocols_lorawan_overhead.csv")) else []
    if lov:
        ch = [abs(f(r["relative_change"])) for r in lov if r["relative_change"] not in ("", "nan")]
        hy = [r for r in lov if r["variant"] == "hybrid"]
        a("LoRaWAN frame overhead (stated sensitivity). The ns-3 LoRaWAN module counts %g B of frame overhead where "
          "this simulation counts %g B (`docs/NETSIM_STUDY.md`; `data/shared_inputs.csv` keeps %g B as the default). "
          "With %g B the time to first authenticated message at zero loss changes by %.1f to %.1f percent over all "
          "configurations on DR0 and DR5 (`linksim/results/protocols_lorawan_overhead.csv`); for the hybrid MAVLink "
          "style profile it falls from %s to %s on DR0 and from %s to %s on DR5. The order of the configurations by "
          "this time at zero loss is %s on both links." % (
              f(lov[0]["overhead_alt_bytes"]), f(lov[0]["overhead_default_bytes"]), f(lov[0]["overhead_default_bytes"]),
              f(lov[0]["overhead_alt_bytes"]), 100 * min(ch), 100 * max(ch),
              tfmt([r for r in hy if r["link"] == "lora_dr0" and r["protocol"] == "mavlink2_pq"][0]["wall_default_s"]),
              tfmt([r for r in hy if r["link"] == "lora_dr0" and r["protocol"] == "mavlink2_pq"][0]["wall_alt_s"]),
              tfmt([r for r in hy if r["link"] == "lora_dr5" and r["protocol"] == "mavlink2_pq"][0]["wall_default_s"]),
              tfmt([r for r in hy if r["link"] == "lora_dr5" and r["protocol"] == "mavlink2_pq"][0]["wall_alt_s"]),
              "unchanged" if all(_order(lov, lk, "wall_default_s") == _order(lov, lk, "wall_alt_s")
                                 for lk in ("lora_dr0", "lora_dr5")) else "not the same"))
        a("")
    a("## 7. Limits")
    a("")
    a("- Modelled, not measured. No cryptographic computation time is included; on microcontrollers ML-DSA-44 "
      "signing and verification add time that this simulation leaves out.")
    a("- Profiles are simplified flight structures, not protocol implementations: no DTLS cookie or retransmission "
      "timers of its own, no EDHOC error flows, no DDS discovery, no certificate chains beyond one certificate.")
    a("- Every flight uses the same selective repeat transport and the same independent Bernoulli loss for data "
      "and acknowledgements.")
    a("- LoRaWAN: both directions are treated as equal peers with their own 1 percent budget; class A receive "
      "windows, gateway duty cycle sharing and the network server are not modelled. Coding rate 4/5 and preamble "
      "8 are ASSUMPTIONS.")
    a("- IEEE 802.15.4: single hop, idle channel, mean backoff. The frame model remains %.1f times faster "
      "than the only published 802.15.4 transfer figure found." % factor)
    a("")
    a("_modelled from published sizes, not measured_")
    os.makedirs(os.path.dirname(DOC), exist_ok=True)
    return "\n".join(L) + "\n", grid, sob


def main(res=None, doc=None):
    text, grid, sob = build_doc(res)
    figures(grid, sob, res)
    with open(doc or DOC, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print("wrote %s and figures" % (doc or DOC))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
