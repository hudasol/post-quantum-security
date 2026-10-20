"""Fourth round validation and diagnosis of the link simulator.

Author: Huda Mueen.

Run from the repository root:  python -m linksim.validate_v4
Writes linksim/results/validation_v4.csv, validation_v4.md, diagnosis_v4.csv,
closed_form_v4.csv and fig_diagnosis_v4.svg. Sources of every published value
are in data/raw/S12_link_sources.md and data/evidence.csv. Size and timing
arithmetic only; no cryptographic operation. Seed 20261020.
"""
import csv
import os

from . import checks, lora, mac802154, model, sim, validate

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "linksim", "results")
SEED = 20261020
PROSE = validate.PROSE_802154

# One model change per cause, applied cumulatively in this order. Each entry:
# (step id, cause, flag added or None, source of the change).
DIAG_STEPS = [
    ("0", "baseline (third round model)", None, "linksim/validate.py crosscheck_802154"),
    ("1", "PHY header (SHR and PHR)", "phy", "data/raw/S12_link_sources.md:38"),
    ("2", "6LoWPAN fragment headers and 8 octet alignment", "frag",
     "data/raw/S12_link_sources.md:8-11 (datagram size ASSUMPTION 1280 B)"),
    ("3", "MAC acknowledgement frame and turnaround before it", "mac_ack",
     "data/raw/S12_link_sources.md:22,25,35"),
    ("4", "inter frame spacing (LIFS or SIFS)", "ifs", "data/raw/S12_link_sources.md:24"),
    ("5", "CCA and mean initial backoff", "csma", "data/raw/S12_link_sources.md:26,29,32"),
    ("6", "RX to TX turnaround after CCA", "turnaround", "data/raw/S12_link_sources.md:25"),
    ("7", "per fragment processing", None,
     "no retrieved source gives a per fragment processing time; not applied"),
    ("8", "effective rate", None,
     "250 kbps with 16 microsecond symbols is consistent (data/raw/S12_link_sources.md:28,42); no change"),
    ("9", "multi hop forwarding", None,
     "ePrint 2021/781 pages 15 to 16 give no hop count; not applied, shown only as a sweep"),
]
HOPS = (1, 2, 3, 4)


def _w(name, rows, fields):
    os.makedirs(RES, exist_ok=True)
    with open(os.path.join(RES, name), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: ("%.6g" % r[k]) if isinstance(r.get(k), float) else r.get(k, "")
                        for k in fields})


def pct(model_v, pub):
    return 100.0 * (model_v / pub - 1.0)


def wall_802154(p, flags, nbytes=PROSE["bytes"], loss=0.0, seed=SEED, proto="sr"):
    link = mac802154.build(p, flags)
    return sim._run_flights(link, [("A", "object", nbytes)], proto, loss, seed, p).wall_s


def diagnosis(p=None):
    """Rows of diagnosis_v4.csv: model time for 50 kB after each cumulative
    change, with the error against the low (30 s) and high (60 s) ends of
    the prose range before and after the change."""
    p = p or model.load_params()
    flags = []
    rows = []
    prev = None
    for sid, cause, flag, src in DIAG_STEPS:
        if flag:
            flags.append(flag)
        t = wall_802154(p, flags)
        frames = len(mac802154.build(p, flags).fragment_wire_sizes(PROSE["bytes"]))
        before = prev if prev is not None else t
        rows.append({"label": "modelled", "step": sid, "cause": cause,
                     "applied": "yes" if flag else ("baseline" if sid == "0" else "no"),
                     "flags": "+".join(flags) or "none", "source": src, "frames": frames,
                     "time_s_modelled_before": before, "time_s_modelled_after": t,
                     "err_low_pct_before": pct(before, PROSE["low_s"]),
                     "err_low_pct_after": pct(t, PROSE["low_s"]),
                     "err_high_pct_after": pct(t, PROSE["high_s"]),
                     "factor_below_low_after": PROSE["low_s"] / t, "seed": SEED})
        prev = t
    full = prev
    for h in HOPS:
        t = mac802154.multihop_wall_s(full, h)
        rows.append({"label": "assumption", "step": "9 sweep", "cause": "multi hop, %d hops" % h,
                     "applied": "sweep only", "flags": "+".join(flags),
                     "source": "ASSUMPTION store and forward on one channel, no spatial reuse",
                     "frames": "", "time_s_modelled_before": full, "time_s_modelled_after": t,
                     "err_low_pct_before": pct(full, PROSE["low_s"]),
                     "err_low_pct_after": pct(t, PROSE["low_s"]),
                     "err_high_pct_after": pct(t, PROSE["high_s"]),
                     "factor_below_low_after": PROSE["low_s"] / t, "seed": SEED})
    return rows


# Published LoRa time on air examples (data/raw/S12_link_sources.md lines 50 to 52, 57).
# params: (pl, sf, bw, cr, n_preamble, crc, ih, de); 'stated' says which were in the source.
LORA_EXAMPLES = [
    ("C1.5 SF7 CR4/8 11 B CRC on explicit header", "payload symbols", 40.0,
     (11, 7, 125000, 4, 8, 1, 0, 0), "SF, BW, CR, PL, CRC, header stated; DE off at SF7", "data/raw/S12_link_sources.md:51"),
    ("C1.4 SF7 CR4/8 11 B", "payload symbols", 32.0,
     (11, 7, 125000, 4, 8, 0, 1, 0), "CRC and header not stated; CRC off and implicit header reproduce it", "data/raw/S12_link_sources.md:50"),
    ("C1.6 SF12 CR4/6 6 preamble 11 B", "time on air ms", 794.624,
     (11, 12, 125000, 2, 6, 0, 1, 0), "CRC, header, DE not stated; CRC off, implicit header, DE off reproduce it", "data/raw/S12_link_sources.md:52"),
    ("C2.3 SF12 13 B LoRaWAN header only", "time on air ms", 1160.0,
     (13, 12, 125000, 1, 8, 1, 0, 1), "published value rounded to 1.16 s; CR 4/5 and preamble 8 are ASSUMPTIONS, CRC on, explicit header, DE on per line 56", "data/raw/S12_link_sources.md:57"),
]


def lora_value(kind, prm):
    pl, sf, bw, cr, npre, crc, ih, de = prm
    if kind == "payload symbols":
        return float(lora.payload_symbols(pl, sf, cr, crc, ih, de))
    return 1000.0 * lora.time_on_air_s(pl, sf, bw, cr, npre, crc, ih, de)


def validation(p=None):
    """Rows of validation_v4.csv."""
    p = p or model.load_params()
    rows = []
    ho = {r["group"]: r for r in validate.held_out(p)}
    for r in validate.run(p):
        rows.append({"label": "modelled", "figure": "ePrint 2026/2343 Table 5, %s, UAV profile handshake" % r["group"],
                     "source": "data/evidence.csv:" + r["ids"].replace(" ", ";"), "unit": "ms",
                     "value_published": r["uav_ms"], "value_modelled": r["pred_plain"],
                     "abs_error": r["pred_plain"] - r["uav_ms"], "pct_error": pct(r["pred_plain"], r["uav_ms"]),
                     "model": "third round bytes over rate plus 2 round trips (uncalibrated)", "role": "validation"})
        h = ho.get(r["group"])
        if h:
            rows.append({"label": "modelled", "figure": "ePrint 2026/2343 Table 5, %s, UAV profile handshake" % r["group"],
                         "source": "data/evidence.csv:" + r["ids"].replace(" ", ";"), "unit": "ms",
                         "value_published": h["uav_ms"], "value_modelled": h["pred_cal_ms"],
                         "abs_error": h["pred_cal_ms"] - h["uav_ms"], "pct_error": pct(h["pred_cal_ms"], h["uav_ms"]),
                         "model": "calibrated constant, %s split" % h["split"], "role": "validation" if h["split"] == "test" else "calibration"})
    diag = diagnosis(p)
    for tag, d in (("third round model", diag[0]), ("fourth round frame model (steps 1 to 6)", diag[len(DIAG_STEPS) - 1])):
        for end, v in (("low end", PROSE["low_s"]), ("high end", PROSE["high_s"])):
            t = d["time_s_modelled_after"]
            rows.append({"label": "modelled", "figure": "ePrint 2021/781 pp. 15 to 16 prose, 50 kB over IEEE 802.15.4 (%s)" % end,
                         "source": PROSE["source"], "unit": "s", "value_published": v, "value_modelled": t,
                         "abs_error": t - v, "pct_error": pct(t, v), "model": tag, "role": "cross check only"})
    for name, kind, pub, prm, note, src in LORA_EXAMPLES:
        v = lora_value(kind, prm)
        rows.append({"label": "modelled", "figure": "LoRa example " + name, "source": src,
                     "unit": "symbols" if kind == "payload symbols" else "ms",
                     "value_published": pub, "value_modelled": v, "abs_error": v - pub,
                     "pct_error": pct(v, pub), "model": "time on air formula; " + note, "role": "validation"})
    # Existing bytes over bit rate model for the same 13 B LoRaWAN frame at DR0.
    v = 1000.0 * 8.0 * 13 / p["lorawan_dr0_bitrate_bps"]
    rows.append({"label": "modelled", "figure": "LoRa example C2.3 SF12 13 B LoRaWAN header only", "source": "data/raw/S12_link_sources.md:57",
                 "unit": "ms", "value_published": 1160.0, "value_modelled": v, "abs_error": v - 1160.0,
                 "pct_error": pct(v, 1160.0), "model": "third round LoRaWAN model (8 x bytes / 250 bit/s, no PHY or MAC overhead)",
                 "role": "validation"})
    return rows


SIM_TRIALS = 8000


def closed_form_rows(p=None):
    """Duty cycle and Monte Carlo closed form checks (also unit tests)."""
    p = p or model.load_params()
    rows = []
    L = model.build_links(p)["lorawan"]
    for nb in (11, 51):
        air = L.air_s(L.wire_bytes(nb))
        rows.append({"label": "modelled", "check": "duty cycle wait, %d B at DR0, 1 percent" % nb,
                     "value_modelled": L.off_s(air), "closed_form": 99.0 * air,
                     "inside": abs(L.off_s(air) - 99.0 * air) < 1e-9, "trials": "", "seed": ""})
    for q in (0.01, 0.05, 0.1, 0.2, 0.3):
        r = checks.check_row(q, checks.sw_transmissions_data_loss(q, 2000, SEED), 1.0 / (1.0 - q))
        rows.append({"label": "modelled", "check": "stop and wait transmissions per fragment, data loss %g" % q,
                     "value_modelled": r["mean_tx"], "ci_lo": r["ci_lo"], "ci_hi": r["ci_hi"],
                     "closed_form": r["closed_form"], "inside": r["inside"], "trials": 2000, "seed": SEED})
    # Each loss rate gets its own seed block, so the five checks are independent of each other.
    for k, q in enumerate((0.01, 0.05, 0.1, 0.2, 0.3)):
        s0 = SEED + 100000 * (k + 1)
        r = checks.check_row(q, checks.sw_transmissions_sim("sik", q, SIM_TRIALS, s0, p), 1.0 / (1.0 - q) ** 2)
        rows.append({"label": "modelled", "check": "supplementary: existing sim.stop_and_wait, data and ack loss %g, closed form 1/(1-p)^2" % q,
                     "value_modelled": r["mean_tx"], "ci_lo": r["ci_lo"], "ci_hi": r["ci_hi"],
                     "closed_form": r["closed_form"], "inside": r["inside"], "trials": SIM_TRIALS,
                     "seed": "%d to %d" % (s0, s0 + SIM_TRIALS - 1)})
    return rows


VAL_FIELDS = ["label", "figure", "source", "unit", "value_published", "value_modelled", "abs_error",
              "pct_error", "model", "role"]
DIAG_FIELDS = ["label", "step", "cause", "applied", "flags", "source", "frames", "time_s_modelled_before",
               "time_s_modelled_after", "err_low_pct_before", "err_low_pct_after", "err_high_pct_after",
               "factor_below_low_after", "seed"]
CF_FIELDS = ["label", "check", "value_modelled", "ci_lo", "ci_hi", "closed_form", "inside", "trials", "seed"]


def markdown(val, diag, cf):
    L = []
    a = L.append
    a("Validation table (each published value labelled published, each model value labelled modelled; "
      "error = modelled minus published, and modelled / published minus 1).")
    a("")
    a("| figure | source | unit | published | modelled | absolute error | percent error | model | role |")
    a("|---|---|---|---|---|---|---|---|---|")
    for r in val:
        a("| %s | %s | %s | %.6g | %.6g | %+.4g | %+.1f%% | %s | %s |" % (
            r["figure"], r["source"], r["unit"], r["value_published"], r["value_modelled"],
            r["abs_error"], r["pct_error"], r["model"], r["role"]))
    a("")
    a("Diagnosis of the IEEE 802.15.4 gap, one cause at a time, cumulative (50 kB, no loss, selective "
      "repeat, seed %d; error against the prose range of ePrint 2021/781 pages 15 to 16; label modelled, "
      "multi hop rows are an ASSUMPTION sweep and are not applied)." % SEED)
    a("")
    a("| step | cause | applied | frames | time before s (modelled) | time after s (modelled) | error vs 30 s before | error vs 30 s after | factor below 30 s | source |")
    a("|---|---|---|---|---|---|---|---|---|---|")
    for r in diag:
        a("| %s | %s | %s | %s | %.3f | %.3f | %+.1f%% | %+.1f%% | %.2f | %s |" % (
            r["step"], r["cause"], r["applied"], r["frames"], r["time_s_modelled_before"],
            r["time_s_modelled_after"], r["err_low_pct_before"], r["err_low_pct_after"],
            r["factor_below_low_after"], r["source"]))
    a("")
    a("Closed form checks (label modelled; 95 percent interval of the mean, normal approximation).")
    a("")
    a("| check | modelled | 95% interval | closed form | inside |")
    a("|---|---|---|---|---|")
    for r in cf:
        ci = ("%.4f to %.4f" % (r["ci_lo"], r["ci_hi"])) if "ci_lo" in r else "n/a"
        a("| %s | %.6g | %s | %.6g | %s |" % (r["check"], r["value_modelled"], ci, r["closed_form"],
                                             "yes" if r["inside"] else "no"))
    return "\n".join(L) + "\n"


def plot_diagnosis(diag, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    rows = [r for r in diag if r["step"] != "9 sweep"]
    fig, ax = plt.subplots(figsize=(8, 4.2))
    xs = list(range(len(rows)))
    ax.bar(xs, [r["time_s_modelled_after"] for r in rows], color="#d63384", edgecolor="#880e4f")
    ax.axhspan(PROSE["low_s"], PROSE["high_s"], color="#f8bbd0", alpha=0.6,
               label="published prose range 30 to 60 s (ePrint 2021/781 pp. 15 to 16)")
    ax.set_xticks(xs)
    ax.set_xticklabels([r["step"] for r in rows])
    ax.set_xlabel("cumulative diagnosis step (see diagnosis_v4.csv)")
    ax.set_ylabel("time for 50 kB, s")
    ax.set_title("IEEE 802.15.4, 50 kB: modelled time after each cause\n(modelled, no loss, seed %d)" % SEED,
                 fontsize=10)
    ax.legend(fontsize=8, loc="upper left")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def main():
    p = model.load_params()
    val = validation(p)
    diag = diagnosis(p)
    cf = closed_form_rows(p)
    _w("validation_v4.csv", val, VAL_FIELDS)
    _w("diagnosis_v4.csv", diag, DIAG_FIELDS)
    _w("closed_form_v4.csv", cf, CF_FIELDS)
    with open(os.path.join(RES, "validation_v4.md"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("# Fourth round validation tables\n\nAuthor: Huda Mueen. Generated by "
                 "`python -m linksim.validate_v4`; seed %d.\n\n" % SEED + markdown(val, diag, cf))
    plot_diagnosis(diag, os.path.join(RES, "fig_diagnosis_v4.svg"))
    print("seed=%d wrote validation_v4.csv diagnosis_v4.csv closed_form_v4.csv validation_v4.md fig_diagnosis_v4.svg" % SEED)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
