"""Generate docs/NETSIM_STUDY.md, the summary CSVs and the figures from the
committed result CSVs of the network simulator check. Needs no ns-3.

Author: Huda Mueen.

Run from the repository root:  python3 -m netsim.make_study
Inputs (netsim/results/): lrwpan_runs.csv, lora_toa.csv, lora_flights.csv
(simulated (network)); linksim_same_settings.csv, linksim_lora_toa.csv,
linksim_lora_flights.csv, sr_closed_form.csv (modelled; python3 -m
netsim.compare writes them).
Outputs: netsim/results/lrwpan_cells.csv, gap_sweep.csv, validation.csv,
lora_toa_compare.csv, lora_flights_compare.csv, fig_netsim_*.svg and
docs/NETSIM_STUDY.md.
"""
import csv
import math
import os

from . import cells

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "netsim", "results")
DOC = os.path.join(ROOT, "docs", "NETSIM_STUDY.md")
SIM = "simulated (network)"
PINK, DARK, BAND, GREY = "#d63384", "#880e4f", "#f8bbd0", "#6c757d"


def read(name):
    with open(os.path.join(RES, name), newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def read_linksim(name):
    with open(os.path.join(ROOT, "linksim", "results", name), newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def write(name, rows, fields):
    with open(os.path.join(RES, name), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: ("%.6g" % r[k]) if isinstance(r.get(k), float) else r.get(k, "") for k in fields})


def t95(n):
    from scipy import stats
    return float(stats.t.ppf(0.975, n - 1)) if n > 1 else float("nan")


def summarise(vals):
    n = len(vals)
    m = sum(vals) / n
    sd = math.sqrt(sum((v - m) ** 2 for v in vals) / (n - 1)) if n > 1 else 0.0
    h = t95(n) * sd / math.sqrt(n) if n > 1 else 0.0
    return m, sd, m - h, m + h


MIN_FOR_CI = 3  # fewest completed runs for which an interval is printed
SVG_SALT = "netsim-study-%s" % cells.SEED  # fixed ids so regenerated figures do not change


def savefig(fig, name):
    """Save an SVG figure deterministically (fixed element ids, no date)."""
    fig.savefig(os.path.join(RES, name), metadata={"Date": None})


def pct(a, b):
    return 100.0 * (a / b - 1.0)


def aggregate(runs):
    """One row per cell (label simulated (network))."""
    order = []
    by = {}
    for r in runs:
        if r["cell"] not in by:
            by[r["cell"]] = []
            order.append(r["cell"])
        by[r["cell"]].append(r)
    out = []
    for c in order:
        rs = by[c]
        done = [r for r in rs if r["completed"] == "1"]
        ts = [float(r["time_s"]) for r in done]
        m, sd, lo, hi = summarise(ts) if ts else (float("nan"),) * 4
        if len(ts) < MIN_FOR_CI:
            # Too few completed runs for a t interval: report none.
            lo = hi = float("nan")
            if len(ts) < 2:
                sd = float("nan")
        elif lo < 0.0:
            # A transfer time cannot be negative: truncate the interval at 0.
            lo = 0.0
        sent = sum(int(r["data_sent"]) for r in rs)
        enq = sum(int(r["mac_frames_enqueued_sender"]) for r in rs)
        segs = sum(int(r["segments"]) for r in rs)
        out.append({"label": SIM, "group": rs[0]["group"], "cell": c, "cause": rs[0]["cause"],
                    "value": rs[0]["value"], "hops": int(rs[0]["hops"]), "bg_nodes": int(rs[0]["bg_nodes"]),
                    "min_be": int(rs[0]["min_be"]), "max_be": int(rs[0]["max_be"]),
                    "max_backoffs": int(rs[0]["max_backoffs"]), "frame_retries": int(rs[0]["frame_retries"]),
                    "seg_bytes": int(rs[0]["seg_bytes"]), "runs": len(rs), "completed": len(done),
                    "time_mean_s": m, "time_sd_s": sd, "time_ci_lo_s": lo, "time_ci_hi_s": hi,
                    "time_min_s": min(ts) if ts else float("nan"), "time_max_s": max(ts) if ts else float("nan"),
                    "tx_per_segment": sent / float(segs), "frames_per_segment_sender": enq / float(sent),
                    "poll_resends": sum(int(r["poll_resends"]) for r in rs),
                    "runs_stuck_rx": sum(1 for r in rs if int(r["stuck_rx_nodes"]) > 0),
                    "mac_tx_drop": sum(int(r["mac_tx_drop"]) for r in rs),
                    "seed": rs[0]["seed"], "runs_first": rs[0]["run"], "runs_last": rs[-1]["run"]})
    return out


CELL_FIELDS = ["label", "group", "cell", "cause", "value", "hops", "bg_nodes", "min_be", "max_be", "max_backoffs",
               "frame_retries", "seg_bytes", "runs", "completed", "time_mean_s", "time_sd_s", "time_ci_lo_s",
               "time_ci_hi_s", "time_min_s", "time_max_s", "tx_per_segment", "frames_per_segment_sender",
               "poll_resends", "runs_stuck_rx", "mac_tx_drop", "seed", "runs_first", "runs_last"]


def verdict(ns3, model):
    in_pub = cells.PROSE_LOW_S <= ns3 <= cells.PROSE_HIGH_S
    agrees = abs(ns3 / model - 1.0) <= cells.MODEL_TOL
    if in_pub and agrees:
        return "both"
    if in_pub:
        return "published"
    if agrees:
        return "model"
    return "neither"


def gap_rows(agg, lk):
    lmap = {r["cell"]: r for r in lk}
    out = []
    for a in agg:
        l = lmap[a["cell"]]
        tl = float(l["time_s_linksim"])
        full = a["completed"] == a["runs"]
        out.append({"cell": a["cell"], "group": a["group"], "cause": a["cause"], "value": a["value"],
                    "time_mean_s_simulated_network": a["time_mean_s"],
                    "time_ci_lo_s_simulated_network": a["time_ci_lo_s"],
                    "time_ci_hi_s_simulated_network": a["time_ci_hi_s"],
                    "completed_simulated_network": "%d of %d" % (a["completed"], a["runs"]),
                    "stuck_runs_simulated_network": a["runs_stuck_rx"],
                    "time_s_modelled": tl, "range_low_s_published": cells.PROSE_LOW_S,
                    "range_high_s_published": cells.PROSE_HIGH_S,
                    "err_ns3_vs_low_pct": pct(a["time_mean_s"], cells.PROSE_LOW_S),
                    "err_model_vs_ns3_pct": pct(tl, a["time_mean_s"]),
                    "in_published_range": full and cells.PROSE_LOW_S <= a["time_mean_s"] <= cells.PROSE_HIGH_S,
                    "agrees_with": verdict(a["time_mean_s"], tl) if full else "incomplete runs",
                    "model_note": l["note"]})
    return out


GAP_FIELDS = ["cell", "group", "cause", "value", "time_mean_s_simulated_network", "time_ci_lo_s_simulated_network",
              "time_ci_hi_s_simulated_network", "completed_simulated_network", "stuck_runs_simulated_network",
              "time_s_modelled",
              "range_low_s_published", "range_high_s_published", "err_ns3_vs_low_pct", "err_model_vs_ns3_pct",
              "in_published_range", "agrees_with", "model_note"]


def smallest_single(gap):
    """For each cause of the one at a time sweep, the value nearest the
    baseline whose ns-3 mean lies in the published range (None if none)."""
    base = {"hops": 1, "neighbours": 0, "macMinBE": 3, "macMaxBE": 5, "macMaxCSMABackoffs": 4,
            "macMaxFrameRetries": 3}
    res = {}
    for cause, b in base.items():
        rows = [g for g in gap if g["group"] == "S2 one" and g["cause"] == cause]
        rows.sort(key=lambda g: abs(float(g["value"]) - b))
        hit = [g for g in rows if g["in_published_range"]]
        res[cause] = (hit[0] if hit else None, rows)
    return res


def lora_toa_compare(ns, lk):
    lmap = {(r["dr"], r["phy_payload_bytes"]): float(r["toa_s_linksim"]) for r in lk}
    out = []
    for r in ns:
        a = float(r["toa_s_ns3"])
        b = lmap[(r["dr"], r["phy_payload_bytes"])]
        out.append({"dr": int(r["dr"]), "phy_payload_bytes": int(r["phy_payload_bytes"]),
                    "toa_ms_simulated_network": 1000.0 * a, "toa_ms_modelled": 1000.0 * b,
                    "diff_ms": 1000.0 * (b - a), "err_model_vs_ns3_pct": pct(b, a)})
    return out


def lora_flights_compare(ns, lk):
    lmap = {(r["protocol"], r["dr"]): r for r in lk}
    out = []
    for r in ns:
        l = lmap[(r["protocol"], r["dr"])]
        a = float(r["handshake_s_ns3"])
        b = float(l["blast_s_linksim"])
        c = float(l["protocol_sim_s_linksim"])
        b9 = float(l["blast_9b_s_linksim"])
        out.append({"protocol": r["protocol"], "dr": int(r["dr"]), "fragments_simulated_network": int(r["fragments"]),
                    "fragments_modelled": int(l["fragments"]),
                    "handshake_s_simulated_network": a, "blast_s_modelled": b, "protocol_sim_s_modelled": c,
                    "blast_9b_s_modelled": b9, "err_blast_9b_vs_ns3_pct": pct(b9, a),
                    "err_blast_vs_ns3_pct": pct(b, a), "err_protocol_sim_vs_ns3_pct": pct(c, a)})
    return out


def fmt_t(s):
    if s != s:
        return "n/a"
    if s >= 3600:
        return "%.2f h" % (s / 3600.0)
    if s >= 60:
        return "%.1f min" % (s / 60.0)
    return "%.2f s" % s


def figures(agg, gap, toa_cmp):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    matplotlib.rcParams["svg.hashsalt"] = SVG_SALT
    amap = {a["cell"]: a for a in agg}
    gmap = {g["cell"]: g for g in gap}
    # Hop sweep
    full = lambda n: amap[n]["completed"] == amap[n]["runs"]
    allhops = [1] + [h for h in range(2, 7) if "hops_%d" % h in amap]
    allnames = ["base_frame"] + ["hops_%d" % h for h in allhops[1:]]
    hops = [h for h, n in zip(allhops, allnames) if full(n)]
    names = [n for n in allnames if full(n)]
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.axhspan(cells.PROSE_LOW_S, cells.PROSE_HIGH_S, color=BAND, alpha=0.6,
               label="published prose range (ePrint 2021/781 pp. 15 to 16)")
    m = [amap[n]["time_mean_s"] for n in names]
    lo = [amap[n]["time_mean_s"] - amap[n]["time_ci_lo_s"] for n in names]
    hi = [amap[n]["time_ci_hi_s"] - amap[n]["time_mean_s"] for n in names]
    ax.errorbar(hops, m, yerr=[lo, hi], color=PINK, marker="o", capsize=3,
                label="ns-3, mean and 95% interval, cells with every run completed (simulated (network))")
    ax.plot(allhops, [gmap[n]["time_s_modelled"] for n in allnames], color=GREY, marker="s", linestyle="--",
            label="linksim at the same hop count (modelled)")
    notes = ["%d hops: %d of %d ns-3 runs completed" % (h, amap[n]["completed"], amap[n]["runs"])
             for h, n in zip(allhops, allnames) if not full(n)]
    if notes:
        ax.text(0.98, 0.55, "\n".join(notes), transform=ax.transAxes, ha="right", va="bottom", fontsize=7,
                color=DARK)
    ax.set_xlabel("hops (line topology)")
    ax.set_ylabel("time for 50 kB, s")
    ax.set_title("IEEE 802.15.4 with 6LoWPAN, 50 kB, selective repeat", fontsize=10)
    ax.legend(fontsize=7, loc="upper left")
    fig.tight_layout()
    savefig(fig, "fig_netsim_hops.svg")
    plt.close(fig)
    # One at a time causes
    one = [a for a in agg if a["group"] in ("S1", "S2 one")]
    fig, ax = plt.subplots(figsize=(7, max(4, 0.22 * len(one))))
    ys = list(range(len(one)))
    ax.axvspan(cells.PROSE_LOW_S, cells.PROSE_HIGH_S, color=BAND, alpha=0.6, label="published prose range")
    ax.barh(ys, [a["time_mean_s"] for a in one], color=PINK, edgecolor=DARK,
            label="ns-3 mean (simulated (network))")
    ax.set_yticks(ys)
    ax.set_yticklabels(["%s = %s%s" % (a["cause"], a["value"],
                                      "" if a["completed"] == a["runs"] else
                                      " (%d of %d completed)" % (a["completed"], a["runs"])) for a in one], fontsize=6)
    ax.invert_yaxis()
    ax.set_xscale("log")
    ax.set_xlabel("time for 50 kB, s (log scale)")
    ax.set_title("One cause at a time from the 1 hop baseline (ns-3)", fontsize=10)
    ax.legend(fontsize=7, loc="lower right")
    fig.tight_layout()
    savefig(fig, "fig_netsim_causes.svg")
    plt.close(fig)
    # LoRa time on air
    fig, ax = plt.subplots(figsize=(7, 3.6))
    for dr, col in ((0, PINK), (5, GREY)):
        rr = [r for r in toa_cmp if r["dr"] == dr]
        ax.plot([r["phy_payload_bytes"] for r in rr], [r["diff_ms"] for r in rr], marker="o", color=col,
                label="DR%d" % dr)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_xlabel("PHY payload, bytes")
    ax.set_ylabel("linksim minus ns-3, ms")
    ax.set_title("LoRa time on air: linksim/lora.py (modelled) minus lorawan module (simulated (network))", fontsize=9)
    ax.legend(fontsize=8)
    fig.tight_layout()
    savefig(fig, "fig_netsim_lora_toa.svg")
    plt.close(fig)


def build():
    runs = read("lrwpan_runs.csv")
    lk = read("linksim_same_settings.csv")
    agg = aggregate(runs)
    write("lrwpan_cells.csv", agg, CELL_FIELDS)
    gap = gap_rows(agg, lk)
    write("gap_sweep.csv", gap, GAP_FIELDS)
    toa_cmp = lora_toa_compare(read("lora_toa.csv"), read("linksim_lora_toa.csv"))
    write("lora_toa_compare.csv", toa_cmp, ["dr", "phy_payload_bytes", "toa_ms_simulated_network",
                                            "toa_ms_modelled", "diff_ms", "err_model_vs_ns3_pct"])
    fl_cmp = lora_flights_compare(read("lora_flights.csv"), read("linksim_lora_flights.csv"))
    write("lora_flights_compare.csv", fl_cmp, ["protocol", "dr", "fragments_simulated_network",
                                               "fragments_modelled", "handshake_s_simulated_network",
                                               "blast_s_modelled", "protocol_sim_s_modelled",
                                               "blast_9b_s_modelled", "err_blast_9b_vs_ns3_pct",
                                               "err_blast_vs_ns3_pct", "err_protocol_sim_vs_ns3_pct"])
    sr = read("sr_closed_form.csv")
    val = validation_rows(agg, gap, toa_cmp, fl_cmp)
    write("validation.csv", val, VAL_FIELDS)
    figures(agg, gap, toa_cmp)
    doc = document(agg, gap, toa_cmp, fl_cmp, sr, val)
    with open(DOC, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(doc)
    return doc


VAL_FIELDS = ["figure", "unit", "value_published", "value_simulated_network", "value_modelled",
              "err_simulated_network_vs_published_pct", "err_modelled_vs_published_pct",
              "err_modelled_vs_simulated_network_pct", "note"]


def validation_rows(agg, gap, toa_cmp, fl_cmp):
    amap = {a["cell"]: a for a in agg}
    gmap = {g["cell"]: g for g in gap}
    out = []
    for cell, what in (("base_frame", "frame mode"), ("base_dgram", "datagram mode")):
        a, g = amap[cell], gmap[cell]
        for end, v in (("low end", cells.PROSE_LOW_S), ("high end", cells.PROSE_HIGH_S)):
            out.append({"figure": "50 kB over IEEE 802.15.4, 1 hop, ns-3 defaults, %s (%s)" % (what, end),
                        "unit": "s", "value_published": v, "value_simulated_network": a["time_mean_s"],
                        "value_modelled": g["time_s_modelled"],
                        "err_simulated_network_vs_published_pct": pct(a["time_mean_s"], v),
                        "err_modelled_vs_published_pct": pct(g["time_s_modelled"], v),
                        "err_modelled_vs_simulated_network_pct": pct(g["time_s_modelled"], a["time_mean_s"]),
                        "note": "published: ePrint 2021/781 pp. 15 to 16 prose range; cross check, not calibration"})
    # Published LoRa example with every LoRaWAN setting except CR and preamble
    # (linksim/results/validation_v4.csv, data/raw/S12_link_sources.md line 57).
    pub = [r for r in read_linksim("validation_v4.csv")
           if r["figure"].startswith("LoRa example C2.3") and r["model"].startswith("time on air formula")]
    ns13 = [r for r in toa_cmp if r["dr"] == 0 and r["phy_payload_bytes"] == 13]
    if pub and ns13:
        v = float(pub[0]["value_published"])
        m = float(pub[0]["value_modelled"])
        n = ns13[0]["toa_ms_simulated_network"]
        out.append({"figure": "LoRa example: 13 B header only frame at SF12 (DR0)", "unit": "ms", "value_published": v,
                    "value_simulated_network": n, "value_modelled": m,
                    "err_simulated_network_vs_published_pct": pct(n, v), "err_modelled_vs_published_pct": pct(m, v),
                    "err_modelled_vs_simulated_network_pct": pct(m, n),
                    "note": "published: data/raw/S12_link_sources.md:57 (rounded to 1.16 s); CR 4/5 and preamble 8 are ASSUMPTIONS in both"})
    for r in toa_cmp:
        out.append({"figure": "LoRa time on air, DR%d, %d B PHY payload" % (r["dr"], r["phy_payload_bytes"]),
                    "unit": "ms", "value_published": "", "value_simulated_network": r["toa_ms_simulated_network"],
                    "value_modelled": r["toa_ms_modelled"], "err_simulated_network_vs_published_pct": "",
                    "err_modelled_vs_published_pct": "", "err_modelled_vs_simulated_network_pct": r["err_model_vs_ns3_pct"],
                    "note": "no published value; implementation cross check"})
    for r in fl_cmp:
        out.append({"figure": "hybrid %s handshake over LoRaWAN EU868 DR%d, no loss" % (r["protocol"], r["dr"]),
                    "unit": "s", "value_published": "", "value_simulated_network": r["handshake_s_simulated_network"],
                    "value_modelled": r["blast_s_modelled"], "err_simulated_network_vs_published_pct": "",
                    "err_modelled_vs_published_pct": "", "err_modelled_vs_simulated_network_pct": r["err_blast_vs_ns3_pct"],
                    "note": "modelled value: linksim fragments back to back with the duty cycle, no acknowledgements; round 4 three flight handshake, superseded by F1"})
    return out


def nf(spec, *v):
    """Format, or n/a when a value is missing (no completed run)."""
    if any(x != x for x in v):
        return "n/a"
    return spec % v


BASIS = {"hops": "hop count is an ASSUMPTION (the paper gives none)",
         "neighbours": "background load is an ASSUMPTION (the paper gives none)",
         "macMinBE": "inside the cited range (N1.1, N2.1) with macMaxBE 8 (N1.2)",
         "macMaxBE": "cited range N1.2, N2.1", "macMaxCSMABackoffs": "cited range N1.3, N2.1",
         "macMaxFrameRetries": "cited range N1.4"}


def _turnaround():
    from linksim import model
    return model.load_params()["turnaround_s"]


def table(header, rows):
    L = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    for r in rows:
        L.append("| " + " | ".join(str(x) for x in r) + " |")
    return L


def document(agg, gap, toa_cmp, fl_cmp, sr, val):
    amap = {a["cell"]: a for a in agg}
    gmap = {g["cell"]: g for g in gap}
    L = []
    a = L.append
    nruns = sum(x["runs"] for x in agg)
    a("# Network simulator check (fifth round)")
    a("")
    a("Author: Huda Mueen. Generated by `python3 -m netsim.make_study` from the committed result files in "
      "`netsim/results/`; do not edit by hand. Network simulator output is labelled **simulated (network)** "
      "(ns-3 at tag ns-3.48 with the lorawan module at v0.3.7, pinned in `netsim/fetch_build.sh`); linksim values "
      "are labelled **modelled**; the figure of ePrint 2021/781 is labelled **published**. The three never share a "
      "column. ns-3 runs: %d in %d cells, global seed %s, one block of run numbers per cell (stored in "
      "`netsim/results/lrwpan_runs.csv`). Sources: `netsim/SOURCES.md` (N1 to N7)." % (nruns, len(agg), cells.SEED))
    a("")
    a("## 1. Settings of the 802.15.4 transfer")
    a("")
    a("The paper states only the object size, the radio family and that the time depends on link quality and "
      "network load (N6.1). Every other setting is an ns-3 default, a value of `linksim/params.csv`, or an "
      "ASSUMPTION, as listed.")
    a("")
    L.extend(table(["setting", "value", "source"], [s for s in cells.SETTINGS]))
    a("")
    a("Transfer protocol: application level selective repeat over UDP, the closest ns-3 equivalent of "
      "`linksim/sim.py` selective_repeat: the sender sends a window of %d segments, the last one asks for a block "
      "acknowledgement with a bitmap, a timeout resends the last segment as a poll, and unacknowledged segments "
      "return to the pending list. The timeout is %g times the smoothed round trip of a window (linksim derives "
      "it from known air times instead) and doubles after each expiry until a new sample (timer details in the table). MAC acknowledgements and retries run underneath, as in a real stack, "
      "while linksim counts one MAC acknowledgement per frame without retries." % (cells.WINDOW, cells.RTO_FACTOR))
    a("")
    b, d = amap["base_frame"], amap["base_dgram"]
    a("## 2. Scenario 1: one hop, ns-3 defaults")
    a("")
    L.extend(table(["mode", "runs", "time mean s (simulated (network))", "95% interval s", "min to max s",
                    "frames per segment at the sender", "linksim s (modelled)", "published range s"],
                   [[x["value"], "%d (%d completed)" % (x["runs"], x["completed"]), "%.2f" % x["time_mean_s"],
                     "%.2f to %.2f" % (x["time_ci_lo_s"], x["time_ci_hi_s"]),
                     "%.2f to %.2f" % (x["time_min_s"], x["time_max_s"]), "%.2f" % x["frames_per_segment_sender"],
                     "%.2f" % gmap[x["cell"]]["time_s_modelled"], "%g to %g" % (cells.PROSE_LOW_S, cells.PROSE_HIGH_S)]
                    for x in (b, d)]))
    a("")
    a("## 3. Validation table (errors per figure)")
    a("")
    a("Error = value / reference minus 1. The 802.15.4 rows are a cross check against a prose range, never a "
      "calibration. LoRa rows have no published value and compare two implementations.")
    a("")
    def f(v, spec=None):
        if v == "":
            return ""
        if spec is None:
            spec = "%.1f" if abs(v) >= 1000 else "%.4g"
        return spec % v
    L.extend(table(["figure", "unit", "published", "simulated (network)", "modelled",
                    "error simulated vs published", "error modelled vs published", "error modelled vs simulated"],
                   [[v["figure"], v["unit"], f(v["value_published"]), f(v["value_simulated_network"]),
                     f(v["value_modelled"]), f(v["err_simulated_network_vs_published_pct"], "%+.1f%%"),
                     f(v["err_modelled_vs_published_pct"], "%+.1f%%"),
                     f(v["err_modelled_vs_simulated_network_pct"], "%+.1f%%")] for v in val]))
    a("")
    a("## 4. Scenario 2: the gap sweep")
    a("")
    a("One cause at a time from the one hop baseline, then combined. Agreement with the model means the ns-3 "
      "mean lies within %d percent of linksim at the same setting (threshold fixed before the sweep); agreement "
      "with the published figure means the ns-3 mean lies in 30 to 60 s. Ranges of the CSMA parameters: N1 and "
      "N2. Each linksim value reruns the diagnosis of `docs/LINKSIM_STUDY.md` Section 4.4 (steps 1 to 6) at the "
      "same setting. macMinBE values above 5 are run with macMaxBE 8, since macMinBE may not exceed macMaxBE (N1.1). "
      "linksim includes a receiver turnaround of %g s before each block acknowledgement (`linksim/params.csv` "
      "turnaround_s, an ASSUMPTION) that the ns-3 transfer does not have." % (int(100 * cells.MODEL_TOL), _turnaround()))
    a("")
    for grp, title in (("S2 one", "One cause at a time"), ("S2 combined", "Combined causes")):
        a("### %s" % title)
        a("")
        rows = [g for g in gap if g["group"] == grp]
        L.extend(table(["cause", "value", "ns-3 mean s (simulated (network))", "95% interval s", "completed",
                        "runs with a stuck receiver", "linksim s (modelled)", "ns-3 vs 30 s", "in 30 to 60 s", "agrees with", "model note"],
                       [[g["cause"], g["value"], nf("%.2f", g["time_mean_s_simulated_network"]),
                         nf("%.2f to %.2f", g["time_ci_lo_s_simulated_network"], g["time_ci_hi_s_simulated_network"]),
                         g["completed_simulated_network"], g["stuck_runs_simulated_network"],
                         "%.2f" % g["time_s_modelled"],
                         nf("%+.1f%%", g["err_ns3_vs_low_pct"]), "yes" if g["in_published_range"] else "no",
                         g["agrees_with"], g["model_note"]] for g in rows]))
        a("")
    nfail = sum(x["runs"] - x["completed"] for x in agg)
    nstuck = sum(x["runs_stuck_rx"] for x in agg)
    a("Runs that did not complete (poll limit reached or simulation cap of 3600 s): %d of %d. In %d of them a node on the line kept its "
      "receiver in the BUSY_RX state for more than 1 s up to the end of the run, far longer than any frame, so a "
      "reception never ended and the route was blocked. The cause was not established: no ns-3 issue, code path "
      "or diagnostic run was traced, so these runs may show a defect of the simulator at the pinned version or a "
      "real collapse of the multi hop transfer under load, and this study does not decide between the two. "
      "Means and intervals use completed runs only; a cell with fewer completed runs "
      "than runs is reported with that count and is not used for the gap verdict. An interval is printed as n/a "
      "when fewer than %d runs completed, and a lower bound below 0 s is truncated at 0 s." % (
          nfail, nruns, nstuck, MIN_FOR_CI))
    a("")
    stuck_cells = [x for x in agg if x["runs_stuck_rx"] > 0 or x["completed"] < x["runs"]]
    if stuck_cells:
        a("Share of runs per cell that did not complete or had a stuck receiver (a result in itself; these cells "
          "lie at 4 or more hops, or combine hops with load or datagram mode):")
        a("")
        L.extend(table(["cell", "runs", "not completed", "with a stuck receiver", "share stuck"],
                       [[x["value"] if x["group"] != "S2 one" else "%s = %s" % (x["cause"], x["value"]), x["runs"],
                         x["runs"] - x["completed"], x["runs_stuck_rx"],
                         "%.0f%%" % (100.0 * x["runs_stuck_rx"] / x["runs"])] for x in stuck_cells]))
        a("")
    a("Figures: `netsim/results/fig_netsim_hops.svg` (hop sweep, ns-3 against linksim) and "
      "`netsim/results/fig_netsim_causes.svg` (one cause at a time).")
    a("")
    a("### Per cause verdict")
    a("")
    ss = smallest_single(gap)
    vrows = []
    for cause, (hit, rows) in ss.items():
        kinds = sorted(set(g["agrees_with"] for g in rows))
        vrows.append([cause, ("%s (ns-3 mean %.2f s)" % (hit["value"], hit["time_mean_s_simulated_network"])) if hit
                      else "none in the swept range", ", ".join(kinds)])
    L.extend(table(["cause", "smallest change from the baseline landing in 30 to 60 s",
                    "agreement found across its values"], vrows))
    a("")
    comb = [g for g in gap if g["group"] == "S2 combined" and g["in_published_range"]]
    a("Combined cells landing in 30 to 60 s: %s." % (
        ", ".join("%s (%.2f s)" % (g["value"], g["time_mean_s_simulated_network"]) for g in comb) if comb else "none"))
    a("")
    fol = [g for g in gap if g["group"] == "S3 follow up"]
    if fol:
        a("Follow up (added after the sweep, so not part of the pre set design): %d more runs in new run blocks "
          "for each one at a time cell that landed in the range." % amap[fol[0]["cell"]]["runs"])
        a("")
        L.extend(table(["cause", "value", "ns-3 mean s (simulated (network))", "95% interval s", "completed",
                        "in 30 to 60 s", "agrees with"],
                       [[g["cause"], g["value"], nf("%.2f", g["time_mean_s_simulated_network"]),
                         nf("%.2f to %.2f", g["time_ci_lo_s_simulated_network"], g["time_ci_hi_s_simulated_network"]),
                         g["completed_simulated_network"], "yes" if g["in_published_range"] else "no",
                         g["agrees_with"]] for g in fol]))
        a("")
    a("### Gap verdict")
    a("")
    hits = [(c, h) for c, (h, _) in ss.items() if h]
    base = b["time_mean_s"]
    a("At one hop with ns-3 defaults the transfer takes %.2f s in ns-3 (simulated (network)), against %.2f s in "
      "linksim (modelled) and 30 to 60 s in the paper (published); ns-3 is %+.1f%% from the low end of the "
      "published range." % (base, gmap["base_frame"]["time_s_modelled"], pct(base, cells.PROSE_LOW_S)))
    a("")
    if hits:
        caveats = []
        for c, h in hits:
            lo_c, hi_c = h["time_ci_lo_s_simulated_network"], h["time_ci_hi_s_simulated_network"]
            if lo_c < cells.PROSE_LOW_S or hi_c > cells.PROSE_HIGH_S:
                fu = [g for g in fol if g["cause"] == c]
                txt = ("%s = %s reaches the range on the mean only: its 95 percent interval (%.2f to %.2f s) crosses "
                       "the edge of the range" % (c, h["value"], lo_c, hi_c))
                if fu:
                    txt += (", and so does the follow up interval (%.2f to %.2f s)" % (
                        fu[0]["time_ci_lo_s_simulated_network"], fu[0]["time_ci_hi_s_simulated_network"])
                        if (fu[0]["time_ci_lo_s_simulated_network"] < cells.PROSE_LOW_S
                            or fu[0]["time_ci_hi_s_simulated_network"] > cells.PROSE_HIGH_S)
                        else ", although the follow up interval (%.2f to %.2f s) lies inside it" % (
                            fu[0]["time_ci_lo_s_simulated_network"], fu[0]["time_ci_hi_s_simulated_network"]))
                caveats.append(txt + ", so part of the plausible range lies outside 30 to 60 s.")
            if c == "macMinBE":
                caveats.append("The backoff cause is not a single setting: macMinBE %s is only allowed with "
                               "macMaxBE raised from 5 to 8, so this cause sets both to 8 together." % h["value"])
        a("Single causes that bring the ns-3 time into the published range: %s. Each is sufficient in simulation; "
          "the paper states none of these settings (N6.1), so the simulation shows which causes can explain the "
          "gap, not which one applied in the paper. %s" % ("; ".join(
              "%s = %s (ns-3 mean %.2f s, 95%% interval %.2f to %.2f s; %s)" % (
                  c, h["value"], h["time_mean_s_simulated_network"], h["time_ci_lo_s_simulated_network"],
                  h["time_ci_hi_s_simulated_network"], BASIS[c]) for c, h in hits),
              ("Causes tied to a cited setting: %s; the others rest on ASSUMPTIONS." % ", ".join(
                  c for c, _ in hits if c not in ("hops", "neighbours")))
              if any(c not in ("hops", "neighbours") for c, _ in hits)
              else "None of them is tied to a cited setting; all rest on ASSUMPTIONS."))
        if caveats:
            a("")
            a(" ".join(caveats))
    else:
        a("Negative result: no single cause within the swept ranges brings the ns-3 time into 30 to 60 s.")
    if comb:
        a("")
        a("Combined cells in the range (listed above) keep every CSMA parameter inside its cited range; their hop "
          "counts, spacing and loads are ASSUMPTIONS.")
    elif not hits:
        a("No combined cell lands in the range either; the sweep is exhausted for these causes.")
    a("")
    hm = [(h, gmap["hops_%d" % h]) for h in (2, 3) if "hops_%d" % h in gmap]
    a("Multi hop forwarding in ns-3 costs more than the store and forward ASSUMPTION of linksim: %s. The window "
      "of segments is forwarded while the sender keeps sending on the same channel, so frames of different hops "
      "contend and collide (MAC drops in `netsim/results/lrwpan_cells.csv`), which linksim does not model." % "; ".join(
          "at %d hops ns-3 %.2f s against linksim %.2f s" % (h, g["time_mean_s_simulated_network"], g["time_s_modelled"])
          for h, g in hm))
    a("")
    a("## 5. LoRaWAN")
    a("")
    a("### Time on air")
    a("")
    a("ns-3 value: `LoraPhy::GetTimeOnAir` with the parameters the class A MAC uses (N3.1, N3.2). linksim value: "
      "`linksim/lora.py` with `linksim/params.csv` (CR 4/5 and 8 preamble symbols are ASSUMPTIONS there). Both "
      "implement the same published formula, so this checks the implementation, not the physics.")
    a("")
    L.extend(table(["DR", "PHY payload B", "ns-3 ms (simulated (network))", "linksim ms (modelled)",
                    "linksim minus ns-3 ms", "error"],
                   [[r["dr"], r["phy_payload_bytes"], "%.3f" % r["toa_ms_simulated_network"],
                     "%.3f" % r["toa_ms_modelled"], "%+.3f" % r["diff_ms"], "%+.2f%%" % r["err_model_vs_ns3_pct"]]
                    for r in toa_cmp]))
    a("")
    a("Figure: `netsim/results/fig_netsim_lora_toa.svg`.")
    a("")
    a("### Hybrid handshake under the EU868 duty cycle")
    a("")
    a("Flights of the hybrid handshake of each protocol profile (`netsim/results/ns3_handshake_flights.csv`, a "
      "frozen copy of `linksim/results/protocols_flights.csv` as it was when the ns-3 runs were made, without the "
      "command sent after the handshake), fragmented at 51 B (DR0) or 222 B (DR5), sent as "
      "unconfirmed uplinks by two class A end devices, one per side; the module's MAC enforces the duty cycle and "
      "the receive windows. No acknowledgement is simulated. The module adds a 9 B frame overhead (no message "
      "integrity code, N3.3) where linksim adds 13 B. linksim columns (`netsim/results/linksim_lora_flights.csv`, "
      "written by `python3 -m netsim.compare` on the same frozen flights): the same fragments back to back under "
      "the duty cycle (blast), and the protocol simulation with selective repeat acknowledgements at zero loss.")
    a("")
    a("**Superseded handshake.** These rows use the round 4 three flight handshake. Design change F1 of "
      "`docs/FORMAL_VERIFICATION.md` later added a fourth flight (the vehicle signature), and "
      "`linksim/results/protocols_flights.csv` and `linksim/results/protocols_grid.csv` now hold that four flight "
      "handshake of the reference design, so their values differ from this table. The ns-3 runs were not repeated "
      "on the four flight handshake; the rows below check the implementation of the duty cycle and fragmentation "
      "and are not the handshake times of the reference design.")
    a("")
    L.extend(table(["protocol", "DR", "fragments", "ns-3 (simulated (network))", "linksim blast (modelled)",
                    "linksim blast with the module's %d B overhead (modelled)" % cells.NS3_LORAWAN_OVERHEAD_BYTES,
                    "linksim protocol simulation (modelled)", "blast vs ns-3", "blast with %d B vs ns-3" % cells.NS3_LORAWAN_OVERHEAD_BYTES,
                    "protocol simulation vs ns-3"],
                   [[r["protocol"], r["dr"], r["fragments_simulated_network"], fmt_t(r["handshake_s_simulated_network"]),
                     fmt_t(r["blast_s_modelled"]), fmt_t(r["blast_9b_s_modelled"]), fmt_t(r["protocol_sim_s_modelled"]),
                     "%+.1f%%" % r["err_blast_vs_ns3_pct"], "%+.2f%%" % r["err_blast_9b_vs_ns3_pct"],
                     "%+.1f%%" % r["err_protocol_sim_vs_ns3_pct"]]
                    for r in fl_cmp]))
    a("")
    a("## 6. Selective repeat closed form check")
    a("")
    a("Closed form (N4.1, also N5.1): with a frame lost independently with probability P and error free "
      "acknowledgements, the expected number of transmissions per frame is 1 / (1 - P). `linksim/checks.py` "
      "sr_check_rows runs `linksim/sim.py` selective_repeat unchanged; two wrappers make the acknowledgements "
      "error free for the pre set rows. Each loss rate has its own seed block. Label modelled; 95 percent "
      "interval of the mean (normal approximation); 50 frames per trial on the 802.15.4 link of linksim.")
    a("")
    L.extend(table(["role", "loss", "trials", "mean transmissions per frame", "95% interval", "1/(1-P)",
                    "inside", "1/(1-P)^2", "seeds"],
                   [[r["role"], r["loss"], r["trials_completed"], "%.5f" % float(r["mean_tx"]),
                     "%.5f to %.5f" % (float(r["ci_lo"]), float(r["ci_hi"])), "%.5f" % float(r["closed_form"]),
                     "yes" if r["inside"] == "True" else "no", "%.5f" % float(r["upper_bound"]),
                     "%s to %s" % (r["seed_first"], r["seed_last"])] for r in sr]))
    a("")
    pre = [r for r in sr if r["role"] == "pre set check"]
    nin = sum(1 for r in pre if r["inside"] == "True")
    asrun = [r for r in sr if r["role"].startswith("studies as run")]
    nb = sum(1 for r in asrun if r["inside_bounds"] == "True")
    pooled = [r for r in sr if r["role"] == "follow up pooled"]
    chance = 1.0 - 0.95 ** len(pre)
    a("Pre set rows: %d of %d inside their 95 percent interval. At least one miss among %d independent 95 percent "
      "intervals has probability %.2f by chance; the follow up rows (ten more independent seed blocks at the rate that missed, "
      "added after the first run and labelled as such) %s." % (
          nin, len(pre), len(pre), chance,
          ("have a pooled mean inside its interval" if pooled and pooled[0]["inside"] == "True"
           else "do not resolve the miss")))
    a("")
    a("Rows marked studies as run use the simulation as the protocol and mission studies do, with "
      "acknowledgements lost at the same rate. Then the poll that recovers a lost acknowledgement resends a data "
      "frame, so the mean exceeds 1 / (1 - P); it stays below the bound 1 / (1 - P)^2 at %d of %d rates. That "
      "excess is a property of linksim's protocol, not a defect of the closed form." % (nb, len(asrun)))
    a("")
    a("ns-3: the selective repeat of the ns-3 transfer runs over MAC retries, so its loss probability is not an "
      "input and the closed form cannot be applied to it; the ns-3 transmissions per segment are reported in "
      "`netsim/results/lrwpan_cells.csv` (tx_per_segment) for reference only.")
    a("")
    a("## 7. Limits")
    a("")
    a("- ns-3 is a simulator: its output is not a radio measurement, and its PHY error, propagation and CSMA models "
      "are those of the pinned version.")
    a("- The published figure is a prose range without settings; a cause that lands in the range is sufficient in "
      "simulation, not shown to be the cause in the paper.")
    a("- Hop count, node spacing, background traffic and the segment size are ASSUMPTIONS of this study.")
    a("- The paper's own transfer used CoAP from a repository (N6.2); it is not simulated.")
    a("- The lorawan module omits the 4 B message integrity code (N3.3) and models class A receive windows; "
      "linksim adds 13 B and models none.")
    a("")
    a("_simulated (network) values are output of ns-3, not measurements_")
    return "\n".join(L) + "\n"


def main():
    build()
    print("wrote docs/NETSIM_STUDY.md and netsim/results summaries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
