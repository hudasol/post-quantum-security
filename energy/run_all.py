"""Build every energy and CPU headroom result, figure and docs/ENERGY_STUDY.md. Author: Huda Mueen.

Run from the repository root:  python3 -m energy.run_all
Seed 20261020 for every random step. Outputs: energy/results/*.csv, docs/figures/energy/energy_*.png,
docs/ENERGY_STUDY.md. All energies are estimated (published or derived cycles times cited
current per MHz times a voltage); mission shares are modelled without validation data.
"""
import csv
import os
import statistics

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from energy import mc, model

OUT = os.path.join(model.HERE, "results")
FIG = os.path.join(model.HERE, "..", "docs", "figures", "energy")
DOC = os.path.join(model.ROOT, "docs", "ENERGY_STUDY.md")
PINK = ["#d63384", "#f48fb1", "#ad1457", "#f8bbd0", "#880e4f", "#fce4ec"]
CORES = ["Cortex-M4", "Cortex-M33", "Cortex-M7", "RISC-V"]
OPS = ["mldsa44_verify", "mldsa44_sign", "mldsa65_verify", "mldsa87_verify", "mlkem768_keygen",
       "mlkem768_encaps", "mlkem768_decaps", "lms_verify", "xmss_verify", "xmss_simple_verify",
       "slhdsa128s_verify", "slhdsa128f_verify", "ed25519_verify", "ed25519_sign", "ecdsa_p256_verify",
       "x25519_shared", "x25519_keygen", "hmac_sha256_msg"]
BASELINE = {"mldsa44_verify": "ed25519_verify", "mldsa65_verify": "ed25519_verify",
            "mldsa87_verify": "ed25519_verify", "lms_verify": "ed25519_verify", "xmss_verify": "ed25519_verify",
            "xmss_simple_verify": "ed25519_verify", "slhdsa128s_verify": "ed25519_verify",
            "slhdsa128f_verify": "ed25519_verify", "mldsa44_sign": "ed25519_sign",
            "mlkem768_keygen": "x25519_keygen", "mlkem768_encaps": "x25519_shared",
            "mlkem768_decaps": "x25519_shared", "hmac_sha256_msg": "ed25519_verify"}
RATE_OPS = [("Ed25519", "ed25519_verify"), ("ML-DSA-44", "mldsa44_verify"), ("LMS", "lms_verify"),
            ("HMAC-SHA256 session", "hmac_sha256_msg")]
HEADROOMS = [0.10, 0.20, 0.50]
MC_N = 20000


def write_csv(name, rows):
    path = os.path.join(OUT, name)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    return path


def fmt(x, nd=3):
    if x is None:
        return "n/a"
    if abs(x) >= 1000:
        return f"{x:,.0f}"
    return f"{x:.{nd}g}"


def build():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(FIG, exist_ok=True)
    ev = model.load_evidence()
    bench = model.load_local("retrieved_benchmarks.csv")
    cmap = model.load_local("cycle_map.csv")
    parts = model.load_local("parts.csv")
    plats = model.load_local("platforms.csv")
    assume = model.load_assumptions()
    res = {}

    # 1. cycles by core class
    cyc_rows, cyc = [], {}
    for core in CORES:
        cyc[core] = {}
        for op in OPS:
            r = model.cycles_for(op, core, ev, bench, cmap)
            cyc[core][op] = r["cycles"]
            cyc_rows.append({"core_class": core, "op": op, "cycles": round(r["cycles"]),
                             "label": r["cycle_label"].split(";")[0], "cycle_source_label": r["cycle_label"],
                             "source": r["source"]})
        cyc[core]["sha256_cpb_sw"] = statistics.median(model.sha256_cpb(bench, "sw"))
    write_csv("cycles_by_core.csv", cyc_rows)
    cpb_sw = model.sha256_cpb(bench, "sw")
    cpb_hw = model.sha256_cpb(bench, "hw")
    res["cpb_sw"] = (statistics.median(cpb_sw), min(cpb_sw), max(cpb_sw), model.bootstrap_median_ci(cpb_sw))
    res["cpb_hw"] = (statistics.median(cpb_hw), min(cpb_hw), max(cpb_hw), model.bootstrap_median_ci(cpb_hw))
    res["baselines"] = classical_baselines(ev, bench, cmap, cyc["Cortex-M4"])
    write_csv("sha256_cpb.csv", [{"board": b, "kind": k, "cycles_per_byte": round(model.throughput_to_cpb(v, c), 2),
                                  "label": "derived from published"}
                                 for k in ("sw", "hw") for v, c, b in model.bench_values(bench, f"sha256_{k}_throughput")])

    # 2. energy per operation for parts with a cited current
    e_rows = []
    for p in parts:
        for mode, ua, volts, vlabel in model.part_supply_options(p):
            core = p["core_class"]
            for op in OPS:
                r = model.cycles_for(op, core, ev, bench, cmap)
                e = model.energy_uj(r["cycles"], ua, volts)
                base = BASELINE.get(op)
                mult = None
                if base:
                    rb = model.cycles_for(base, core, ev, bench, cmap)
                    # A multiple is only stated when both rows come from the same core: a native row over a
                    # proxy row (or the reverse) would mix cores in one ratio.
                    if ("proxy" in r["cycle_label"]) == ("proxy" in rb["cycle_label"]):
                        mult = r["cycles"] / rb["cycles"]
                e_rows.append({"part": p["part"], "supply_mode": mode, "ua_per_mhz_published": round(ua, 2),
                               "volts": volts, "volts_label": vlabel, "op": op, "cycles": round(r["cycles"]),
                               "cycle_source_label": r["cycle_label"], "cycle_source": r["source"],
                               "energy_uj_estimated": round(e, 3), "baseline_op": base or "",
                               "multiple_of_baseline_estimated": round(mult, 3) if mult else "",
                               "label": "estimated"})
    write_csv("energy_per_op.csv", e_rows)
    res["energy_rows"] = e_rows
    res["parts_with_current"] = sorted({r["part"] for r in e_rows})
    res["parts_without"] = [p["part"] for p in parts if not model.part_supply_options(p)]

    # 3. maximum sustained verified messages per second
    rate_rows = []
    targets = [(pl["platform"], pl["core_class"], float(pl["clock_mhz"])) for pl in plats]
    targets += [(p["part"], p["core_class"], float(p["max_mhz"])) for p in parts if model.part_supply_options(p)]
    for name, core, clk in targets:
        for lab, op in RATE_OPS:
            r = model.cycles_for(op, core, ev, bench, cmap)
            row = {"target": name, "core_class": core, "clock_mhz": clk, "design": lab, "cycles": round(r["cycles"]),
                   "cycle_source_label": r["cycle_label"]}
            for h in HEADROOMS:
                row[f"msgs_per_s_at_{int(h*100)}pct_estimated"] = round(model.max_rate_per_s(r["cycles"], clk, h), 1)
            row["label"] = "estimated"
            rate_rows.append(row)
    write_csv("max_rates.csv", rate_rows)
    res["rates"] = rate_rows

    # 3b. validation against published energy rows (seeded calibration and validation split)
    res["val"] = validate(ev, parts)

    # 4. nominal mission workload and 5. Monte Carlo
    designs = [("pq_sig", "ML-DSA-44 per command"), ("mac", "HMAC-SHA256 per command after PQ handshake"),
               ("lms", "LMS verify per command"), ("classical", "Ed25519 and X25519 baseline")]
    nom, mcrows, sob = [], [], {}
    X = mc.triangular_samples(assume, MC_N)
    for pl in plats:
        c = cyc[pl["core_class"]]
        for d, dlab in designs:
            b0, c0 = mc.evaluate(mc.nominal_row(assume), mc.INPUTS, c, pl, d)
            nom.append({"platform": pl["platform"], "design": dlab, "battery_pct_per_h_modelled": round(float(b0[0]), 5),
                        "cpu_pct_modelled": round(float(c0[0]), 4), "label": "modelled"})
            b, cp = mc.evaluate(X, mc.INPUTS, c, pl, d)
            mcrows.append({"platform": pl["platform"], "design": dlab,
                           "battery_pct_p2_5": round(float(np.percentile(b, 2.5)), 5),
                           "battery_pct_median": round(float(np.median(b)), 5),
                           "battery_pct_p97_5": round(float(np.percentile(b, 97.5)), 5),
                           "cpu_pct_p2_5": round(float(np.percentile(cp, 2.5)), 4),
                           "cpu_pct_median": round(float(np.median(cp)), 4),
                           "cpu_pct_p97_5": round(float(np.percentile(cp, 97.5)), 4),
                           "cpu_over_100pct_fraction": round(float(np.mean(cp > 100)), 4),
                           "n": MC_N, "seed": model.SEED, "label": "modelled"})
        for which, tag in ((0, "battery"), (1, "cpu")):
            sob[(pl["platform"], tag)] = mc.sobol_indices(assume, c, pl, "pq_sig", which=which)
    write_csv("mission_nominal.csv", nom)
    write_csv("mission_mc.csv", mcrows)
    srows = [{"platform": k[0], "output": k[1] + " share, ML-DSA-44 per command", **r, "n_base": 1024,
              "seed": model.SEED, "label": "modelled"} for k, v in sob.items() for r in v]
    write_csv("sobol.csv", srows)
    res.update(nom=nom, mc=mcrows, sob=sob)
    figures(res, e_rows, rate_rows, sob)
    write_doc(res, assume, plats)
    return res


def classical_baselines(ev, bench, cmap, cm4):
    """Chosen Cortex-M4 classical baseline rows, the published alternatives and the resulting multiple range."""
    pq = {"ed25519_verify": "mldsa44_verify", "ed25519_sign": "mldsa44_sign", "x25519_shared": "mlkem768_decaps"}
    out = []
    for op, pq_op in pq.items():
        r = next(x for x in cmap if x["op"] == op and x["core_class"] == "Cortex-M4")
        ids = [r["ref"]] + [i for i in r.get("alternatives", "").split("|") if i]
        vals = [float(ev[i]["cycles"]) for i in ids]
        out.append({"op": op, "chosen_id": r["ref"], "cycles_published": round(vals[0]),
                    "alternative_ids": " ".join(ids[1:]), "range_low_published": round(min(vals)),
                    "range_high_published": round(max(vals)), "pq_op": pq_op,
                    "multiple_chosen_estimated": round(cm4[pq_op] / vals[0], 3),
                    "multiple_low_estimated": round(cm4[pq_op] / max(vals), 3),
                    "multiple_high_estimated": round(cm4[pq_op] / min(vals), 3),
                    "reason": r["note"], "label": "published"})
    old = [model.cycles_from_time(v, c) for v, c, _ in model.bench_values(bench, "ed25519_verify_time")]
    e = ev["S10D-031"]
    old.append(model.cycles_from_time(model.parse_time_ms(e["compiler_flags_or_notes"]), float(e["clock_mhz"])))
    write_csv("classical_baselines.csv", out)
    return {"rows": out, "derived_ed_verify": (min(old), max(old), len(old))}


VAL_IDS = ["S2-%04d" % i for i in range(190, 214)]


def validate(ev, parts):
    """Compare estimated energy (cycles x cited STM32L4R5 LDO current x 3.3 V) with published energy.

    Rows S2-0190 to S2-0213 (NUCLEO-F411RE at 96 MHz) carry published cycles and energy. A seeded
    half split calibrates one scale factor; the other half reports the error. The uncalibrated
    error over all rows is also reported. The F411 is not one of the cited parts, so this checks
    the order of magnitude of the method, not a part specific current.
    """
    ref = next(p for p in parts if p["part"] == "STM32L4R5")
    ua, volts = float(ref["ua_per_mhz_ldo"]), model.NOMINAL_VDD_V
    rows = [ev[i] for i in VAL_IDS if ev[i]["cycles"] and ev[i]["energy_uj"]]
    rng = np.random.default_rng(model.SEED)
    idx = rng.permutation(len(rows))
    cal = set(idx[: len(rows) // 2].tolist())
    out = []
    for k, r in enumerate(rows):
        pred = model.energy_uj(float(r["cycles"]), ua, volts)
        out.append({"id": r["id"], "set": "calibration" if k in cal else "validation",
                    "cycles_published": float(r["cycles"]), "energy_uj_published": float(r["energy_uj"]),
                    "energy_uj_estimated_uncalibrated": round(pred, 2),
                    "ratio_published_over_estimated": round(float(r["energy_uj"]) / pred, 4)})
    factor = float(np.median([o["ratio_published_over_estimated"] for o in out if o["set"] == "calibration"]))
    for o in out:
        o["energy_uj_modelled_calibrated"] = round(o["energy_uj_estimated_uncalibrated"] * factor, 2)
        o["abs_pct_error_calibrated"] = round(100 * abs(o["energy_uj_modelled_calibrated"] - o["energy_uj_published"])
                                              / o["energy_uj_published"], 2)
        o["abs_pct_error_uncalibrated"] = round(100 * abs(o["energy_uj_estimated_uncalibrated"] - o["energy_uj_published"])
                                                / o["energy_uj_published"], 2)
        o["seed"] = model.SEED
        o["label"] = "modelled"
    write_csv("validation_split.csv", out)
    v = [o["abs_pct_error_calibrated"] for o in out if o["set"] == "validation"]
    u = [o["abs_pct_error_uncalibrated"] for o in out]
    return {"n": len(out), "n_val": len(v), "factor": factor, "val_median": float(np.median(v)),
            "val_ci": model.bootstrap_median_ci(v), "val_max": max(v), "uncal_median": float(np.median(u)),
            "uncal_ci": model.bootstrap_median_ci(u),
            "ratio_range": (min(o["ratio_published_over_estimated"] for o in out),
                            max(o["ratio_published_over_estimated"] for o in out))}


def figures(res, e_rows, rate_rows, sob):
    plt.rcParams.update({"axes.edgecolor": "#880e4f", "axes.labelcolor": "#880e4f", "xtick.color": "#880e4f",
                         "ytick.color": "#880e4f", "axes.titlecolor": "#880e4f"})
    # energy per op on STM32L4R5 SMPS
    sel = [r for r in e_rows if r["part"] == "STM32L4R5" and r["supply_mode"] == "SMPS or stated"]
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.barh([r["op"] for r in sel], [r["energy_uj_estimated"] for r in sel], color=PINK[0])
    ax.set_xscale("log")
    ax.set_xlabel("energy per operation (uJ, log scale)")
    ax.set_title("Estimated energy per operation, STM32L4R5 at 43 uA/MHz, 3.3 V\n"
                 "(published or derived cycles; label: estimated; no random step)", fontsize=9)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "energy_per_op.png"), dpi=130)
    plt.close(fig)
    # rates at 20 percent headroom on platforms
    fig, ax = plt.subplots(figsize=(8, 4))
    plats = ["Crazyflie 2.1", "TurtleBot3 Burger"]
    labs = [d for d, _ in RATE_OPS]
    w = 0.38
    for i, pl in enumerate(plats):
        vals = [next(r for r in rate_rows if r["target"] == pl and r["design"] == d)["msgs_per_s_at_20pct_estimated"]
                for d in labs]
        ax.bar(np.arange(len(labs)) + i * w, vals, w, label=pl, color=PINK[2 * i])
    ax.set_yscale("log")
    ax.set_xticks(np.arange(len(labs)) + w / 2)
    ax.set_xticklabels(labs, fontsize=8)
    ax.set_ylabel("verified messages per second")
    ax.set_title("Estimated maximum verified messages per second at 20 percent CPU headroom\n"
                 "(label: estimated; cycles published or derived; no random step)", fontsize=9)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "energy_rates.png"), dpi=130)
    plt.close(fig)
    # Sobol
    fig, axs = plt.subplots(1, 2, figsize=(10, 4.5), sharey=True)
    for ax, pl in zip(axs, plats):
        s = sob[(pl, "battery")]
        names = [r["input"] for r in s]
        ax.barh(names, [r["ST"] for r in s], color=PINK[1], label="total ST")
        ax.barh(names, [r["S1"] for r in s], color=PINK[0], height=0.4, label="first order S1")
        ax.set_title(pl, fontsize=9)
        ax.set_xlabel("Sobol index")
    axs[0].legend(fontsize=8)
    fig.suptitle("Sobol indices for battery share per hour, ML-DSA-44 per command\n"
                 "(label: modelled; SALib, N=1024, seed 20261020)", fontsize=9)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "energy_sobol.png"), dpi=130)
    plt.close(fig)


def dominant(srows):
    top = max(srows, key=lambda r: r["ST"])
    return top["input"], top["ST"]


def write_doc(res, assume, plats):
    e = res["energy_rows"]

    def erow(part, mode, op):
        return next(r for r in e if r["part"] == part and r["supply_mode"] == mode and r["op"] == op)

    L = []
    L.append("# Energy and CPU headroom study\n")
    L.append("Author: Huda Mueen. Generated by `energy/run_all.py` (run `python3 -m energy.run_all` from the repository root). "
             "Seed 20261020. Do not edit by hand.\n")
    L.append("## Labels\n")
    L.append("Cycle counts are `published` (a row of `data/evidence.csv`, cited by id) or `derived from published` "
             "(a published time multiplied by the stated clock). Energy per operation is `estimated`: cycles multiplied by a "
             "cited run current per MHz and a voltage. Mission shares are `modelled` from labelled assumptions and have no "
             "validation data; no validation error can be reported for them. Where a core has no published row the Cortex-M4 "
             "row is used and the label says `proxy`.\n")
    L.append("## 1. Run current sources\n")
    L.append(f"Parts with a cited run current: {', '.join(res['parts_with_current'])}. "
             f"Parts searched but with no run current found: {', '.join(res['parts_without'])}. "
             "The six part target was not met for parts with values: five parts carry a cited figure. The product pages do not "
             "state temperature, code location, cache state or whether the figure is typical; these are `not stated` in "
             "`energy/parts.csv`. Sources and refused fetches are listed in `data/raw/S12_energy_sources.md`.\n")
    L.append("## 2. Energy per operation (estimated)\n")
    L.append("Energy = cycles x (current / frequency) x voltage. Multiple = cycles of the operation over cycles of the classical "
             "baseline on the same core (Ed25519 verify for verification, Ed25519 sign for signing, X25519 for key "
             "encapsulation). The multiple is left blank where one of the two rows is a proxy from another core and the other is native, "
             "because that ratio would mix cores. Full table: `energy/results/energy_per_op.csv`.\n")
    L.append("| Part, supply | Operation | Cycles | Cycle source label | Energy (uJ, estimated) | Multiple of baseline |")
    L.append("|---|---|---|---|---|---|")
    for part, mode in (("STM32L4R5", "SMPS or stated"), ("STM32U5A5", "SMPS or stated"), ("ESP32-C3", "mA at stated MHz")):
        for op in ("ed25519_verify", "ecdsa_p256_verify", "mldsa44_verify", "mldsa87_verify", "lms_verify",
                   "xmss_verify", "slhdsa128s_verify", "mlkem768_decaps", "x25519_shared", "hmac_sha256_msg"):
            r = erow(part, mode, op)
            L.append(f"| {part}, {r['ua_per_mhz_published']} uA/MHz at {r['volts']} V | {op} | {r['cycles']:,} | "
                     f"{r['cycle_source_label']} ({r['cycle_source']}) | {fmt(r['energy_uj_estimated'])} | "
                     f"{fmt(r['multiple_of_baseline_estimated']) if r['multiple_of_baseline_estimated'] != '' else ''} |")
    md, lo, hi, ci = res["cpb_sw"]
    L.append("")
    L.append(f"SHA-256 software cycles per byte (derived from published throughput, three Cortex-M4 boards): median {md:.1f}, "
             f"range {lo:.1f} to {hi:.1f}, bootstrap 95 percent interval of the median {ci[0]:.1f} to {ci[1]:.1f} (n = 3, so the "
             "interval is coarse). HMAC-SHA256 has no published cycles row in the evidence table; the HMAC figures are "
             "`estimated` from this SHA-256 throughput for a 64 byte message and are not published values.")
    L.append("")
    L.append("### Classical baselines on Cortex-M4\n")
    L.append("Ed25519 and X25519 cycles are published rows (ids S12A). Where several exist, the table gives the chosen row, "
             "the published range over all candidate rows, and the post quantum multiple over that range. Full table: "
             "`energy/results/classical_baselines.csv`.\n")
    L.append("| Operation | Chosen row | Cycles | Published range | Compared with | Multiple (chosen) | Multiple range | Why this row |")
    L.append("|---|---|---|---|---|---|---|---|")
    for b_ in res["baselines"]["rows"]:
        L.append(f"| {b_['op']} | {b_['chosen_id']} | {b_['cycles_published']:,} | {b_['range_low_published']:,} to "
                 f"{b_['range_high_published']:,} ({b_['chosen_id']} {b_['alternative_ids']}) | {b_['pq_op']} | "
                 f"{b_['multiple_chosen_estimated']} | {b_['multiple_low_estimated']} to {b_['multiple_high_estimated']} | "
                 f"{b_['reason']} |")
    a, b, n = res["baselines"]["derived_ed_verify"]
    L.append(f"\nEarlier passes used Ed25519 verify derived from published times (three CycloneCRYPTO boards and row S10D-031): "
             f"{a:,.0f} to {b:,.0f} cycles. Those time based values include unknown flash wait states and library choices and "
             "are no longer used. The Fujii and Aranha rows were run at 48 to 84 MHz, where wait states may apply, which is one "
             "reason the 24 MHz Owens et al. row was preferred. The C25519 library on the nRF52840 took far longer (row "
             "S10D-028), so the classical baseline still depends strongly on the library chosen.\n")
    v = res["val"]
    L.append("### Check against published energy\n")
    L.append(f"Rows S2-0190 to S2-0213 (NUCLEO-F411RE, 96 MHz) carry published cycles and published energy ({v['n']} rows). "
             "Estimating their energy with the cited STM32L4R5 LDO figure (110 uA/MHz) and 3.3 V gives a published over "
             f"estimated ratio of {v['ratio_range'][0]:.2f} to {v['ratio_range'][1]:.2f}; median absolute error without "
             f"calibration {v['uncal_median']:.1f} percent (bootstrap 95 percent interval {v['uncal_ci'][0]:.1f} to "
             f"{v['uncal_ci'][1]:.1f}). After calibrating one scale factor ({v['factor']:.2f}) on a seeded half "
             f"(seed {model.SEED}, split in `energy/results/validation_split.csv`), the median absolute error on the "
             f"{v['n_val']} validation rows is {v['val_median']:.1f} percent (interval {v['val_ci'][0]:.1f} to "
             f"{v['val_ci'][1]:.1f}, maximum {v['val_max']:.1f}). The low power part figure therefore underestimates a "
             "general purpose Cortex-M4 board by about the calibration factor; the proxy factor range of 1 to 3 used in "
             "section 4 covers it. The published energies are board level and the F411 is not a cited part, so this is a "
             "check of the method's order of magnitude only. The small calibrated error mostly reflects that the published energies are close to a constant board power times run time; the largest errors are on the elliptic curve rows, whose stated average power is lower. The uncalibrated energies in section 2 should be read with "
             "this error beside them.\n")
    L.append("## 3. Maximum sustained verified messages per second (estimated)\n")
    L.append("Rate = headroom x clock / cycles per verification. Platform clocks: Crazyflie 2.1 STM32F405 at 168 MHz; "
             "TurtleBot3 Burger Cortex-M7 board at 216 MHz (both cited). Full table: `energy/results/max_rates.csv`.\n")
    L.append("| Target | Design | Cycles per message | Cycle source label | 10 percent | 20 percent | 50 percent |")
    L.append("|---|---|---|---|---|---|---|")
    for r in res["rates"]:
        if r["target"] in ("Crazyflie 2.1", "TurtleBot3 Burger", "STM32U5A5"):
            L.append(f"| {r['target']} | {r['design']} | {r['cycles']:,} | {r['cycle_source_label']} | "
                     f"{fmt(r['msgs_per_s_at_10pct_estimated'])} | {fmt(r['msgs_per_s_at_20pct_estimated'])} | "
                     f"{fmt(r['msgs_per_s_at_50pct_estimated'])} |")
    L.append("\nThe symmetric MAC design row uses no published HMAC cycles (none exist in the evidence table); it is an estimate "
             "from published SHA-256 throughput. LMS and Ed25519 on the Cortex-M7 use the Cortex-M4 rows as a proxy.\n")
    L.append("## 4. Mission workloads (modelled)\n")
    L.append("Platforms (cited): Crazyflie 2.1, 250 mAh battery, 7 minute flight; TurtleBot3 Burger, 11.1 V 1800 mAh (19.98 Wh), "
             "2 h 30 min operating time. Battery share per hour = security energy per hour / (battery energy / run time "
             "x 1 h). Workload assumptions (all `assumption`, triangular low, nominal, high):\n")
    L.append("| Input | Low | Nominal | High | Unit |")
    L.append("|---|---|---|---|---|")
    units = {r["name"]: r["unit"] for r in model.load_local("workload_assumptions.csv")}
    for k in mc.INPUTS:
        a_ = assume[k]
        L.append(f"| {k} | {fmt(a_['low'])} | {fmt(a_['nominal'])} | {fmt(a_['high'])} | {units[k]} |")
    L.append("\nThe platform MCU run currents were not retrieved, so the current per MHz is a proxy range over the cited parts "
             "multiplied by an assumed proxy factor of 1 to 3 (`unverified`). The Crazyflie cell voltage is also an "
             "assumption.\n")
    L.append(f"| Platform | Design | Battery percent per hour, nominal | Monte Carlo median (2.5 to 97.5 percentile) | CPU percent nominal | CPU percent median (2.5 to 97.5) | Fraction of draws over 100 percent CPU |")
    L.append("|---|---|---|---|---|---|---|")
    for n_, m_ in zip(res["nom"], res["mc"]):
        L.append(f"| {n_['platform']} | {n_['design']} | {fmt(n_['battery_pct_per_h_modelled'])} | "
                 f"{fmt(m_['battery_pct_median'])} ({fmt(m_['battery_pct_p2_5'])} to {fmt(m_['battery_pct_p97_5'])}) | "
                 f"{fmt(n_['cpu_pct_modelled'])} | {fmt(m_['cpu_pct_median'])} ({fmt(m_['cpu_pct_p2_5'])} to "
                 f"{fmt(m_['cpu_pct_p97_5'])}) | {m_['cpu_over_100pct_fraction']} |")
    L.append(f"\nMonte Carlo: {MC_N} draws, seed {model.SEED}. These intervals reflect the assumed input ranges only, not "
             "measurement error.\n")
    L.append("## 5. Sensitivity (Sobol, modelled)\n")
    for pl in ("Crazyflie 2.1", "TurtleBot3 Burger"):
        for tag in ("battery", "cpu"):
            name, st = dominant(res["sob"][(pl, tag)])
            L.append(f"- {pl}, {tag} share, ML-DSA-44 per command: dominant input `{name}` (total index {st:.2f}).")
    L.append("\nFull indices with bootstrap confidence: `energy/results/sobol.csv`. Figure: `docs/figures/energy/energy_sobol.png`.\n")
    L.append("## 6. Findings, including null results\n")
    cf = next(r for r in res["nom"] if r["platform"] == "Crazyflie 2.1" and r["design"].startswith("ML-DSA"))
    cfc = next(r for r in res["nom"] if r["platform"] == "Crazyflie 2.1" and r["design"].startswith("Ed25519"))
    L.append(f"- Energy is not the binding constraint in this model: at the nominal workload the ML-DSA-44 design uses "
             f"{fmt(cf['battery_pct_per_h_modelled'])} percent of the Crazyflie battery energy per hour against "
             f"{fmt(cfc['battery_pct_per_h_modelled'])} percent for the Ed25519 baseline (modelled). CPU time is the tighter "
             "budget, and it is driven by the command rate.")
    m = {op: erow("STM32L4R5", "SMPS or stated", op)["multiple_of_baseline_estimated"]
         for op in ("mldsa44_verify", "mldsa87_verify", "lms_verify", "slhdsa128s_verify", "xmss_verify", "mldsa44_sign")}
    L.append(f"- On Cortex-M4, ML-DSA-44 verification takes {m['mldsa44_verify']} times the cycles of the Ed25519 verify row "
             f"used here ({'slower' if m['mldsa44_verify'] > 1 else 'faster'} than the classical baseline; range over the "
             f"published Ed25519 rows {res['baselines']['rows'][0]['multiple_low_estimated']} to "
             f"{res['baselines']['rows'][0]['multiple_high_estimated']}). Other multiples: "
             f"ML-DSA-87 {m['mldsa87_verify']}, LMS {m['lms_verify']}, SLH-DSA-128s (pre standard SPHINCS+ row) "
             f"{m['slhdsa128s_verify']}, XMSS {m['xmss_verify']}; ML-DSA-44 signing {m['mldsa44_sign']} times Ed25519 "
             "signing. The classical figure depends strongly on the library chosen (section 2).")
    L.append("- No published HMAC cycle counts exist in the evidence table; the symmetric session design is estimated only.")
    L.append(f"- The energy method was checked against {v['n']} published energy rows on one Cortex-M4 board; the "
             f"uncalibrated estimate is low by a factor near {v['factor']:.1f}. No energy check exists for the Cortex-M33, "
             "Cortex-M7 or RISC-V parts, and the mission shares have no validation data.\n")
    L.append("## Figures\n")
    L.append("- `docs/figures/energy/energy_per_op.png`: estimated energy per operation, STM32L4R5 at 43 uA/MHz and 3.3 V.")
    L.append("- `docs/figures/energy/energy_rates.png`: estimated maximum verified messages per second at 20 percent headroom.")
    L.append("- `docs/figures/energy/energy_sobol.png`: Sobol indices, modelled, seed 20261020.\n")
    with open(DOC, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")


if __name__ == "__main__":
    r = build()
    print("seed", model.SEED, "wrote", DOC)
