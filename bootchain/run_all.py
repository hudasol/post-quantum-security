"""Build every boot and update chain result, figure and docs/BOOT_UPDATE_STUDY.md. Author: Huda Mueen.

Run from the repository root:  python3 -m bootchain.run_all
Seed 20261020 for every random step. Outputs: bootchain/results/*.csv, docs/figures/bootchain/boot_*.png,
docs/BOOT_UPDATE_STUDY.md. Verification and transfer times are estimated; comparisons with
published boot measurements report the error beside each modelled value.
"""
import csv
import os
import statistics

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from SALib.analyze import sobol as sobol_analyze
from SALib.sample import sobol as sobol_sample

from bootchain import model as bm
from energy import model as em

OUT = os.path.join(bm.HERE, "results")
FIG = os.path.join(bm.HERE, "..", "docs", "figures", "bootchain")
DOC = os.path.join(bm.ROOT, "docs", "BOOT_UPDATE_STUDY.md")
PINK = ["#d63384", "#f48fb1", "#ad1457", "#f8bbd0", "#880e4f", "#fce4ec"]
IMAGES = [100000, 250000, 500000, 1000000, 2000000]
TARGETS = [("Crazyflie 2.1 (STM32F405)", "Cortex-M4", 168.0), ("STM32H563", "Cortex-M33", 250.0),
           ("TurtleBot3 Burger board", "Cortex-M7", 216.0)]
MC_N = 20000


def write_csv(name, rows):
    with open(os.path.join(OUT, name), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def f3(x):
    return f"{x:,.0f}" if abs(x) >= 100 else f"{x:.3g}"


def build():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(FIG, exist_ok=True)
    ev = em.load_evidence()
    bench = em.load_local("retrieved_benchmarks.csv")
    cmap = em.load_local("cycle_map.csv")
    inp = bm.load_inputs()
    schemes = bm.load_schemes()
    params = em.read_csv(os.path.join(bm.ROOT, "linksim", "params.csv"))
    cpb_sw_all = em.sha256_cpb(bench, "sw")
    cpb_hw_all = em.sha256_cpb(bench, "hw")
    cpb_sw, cpb_hw = statistics.median(cpb_sw_all), statistics.median(cpb_hw_all)
    R = {"cpb_sw": cpb_sw, "cpb_hw": cpb_hw, "cpb_sw_rng": (min(cpb_sw_all), max(cpb_sw_all)),
         "cpb_hw_rng": (min(cpb_hw_all), max(cpb_hw_all))}
    sig = {s["scheme"]: s for s in schemes}

    def sigcyc(s, core):
        if not sig[s]["verify_op"]:
            return None
        return em.cycles_for(sig[s]["verify_op"], core, ev, bench, cmap)

    # 1. verification time
    vt = []
    for tname, core, clk in TARGETS:
        for s in sig:
            c = sigcyc(s, core)
            if c is None:
                continue
            for img in IMAGES:
                for kind, cpb in (("software SHA-256", cpb_sw), ("hardware HASH", cpb_hw)):
                    vt.append({"target": tname, "core_class": core, "clock_mhz": clk, "scheme": s, "image_bytes": img,
                               "hash": kind, "cycles_per_byte_derived": round(cpb, 2),
                               "sig_cycles": round(c["cycles"]), "cycle_source_label": c["cycle_label"],
                               "cycle_source": c["source"],
                               "hash_ms_estimated": round(1e3 * bm.hash_time_s(img, cpb, clk), 3),
                               "sig_ms_estimated": round(1e3 * c["cycles"] / (clk * 1e6), 3),
                               "total_ms_estimated": round(1e3 * bm.verify_time_s(img, cpb, c["cycles"], clk), 3),
                               "label": "estimated"})
    write_csv("verify_time.csv", vt)
    R["vt"] = vt

    # 2a. comparison with wolfBoot published boot times
    img = bm.inval(inp, "wolfboot_app_image_bytes")
    clk = bm.inval(inp, "wolfboot_clock_mhz")
    base_ms = em.parse_time_ms(ev["S2-0347"]["compiler_flags_or_notes"])
    comp = []
    for rid in ["S2-%04d" % i for i in range(347, 358)]:
        e = ev[rid]
        pub = em.parse_time_ms(e["compiler_flags_or_notes"])
        s = next((k for k, v in sig.items() if v["boot_row"] == rid), None)
        if rid == "S2-0347":
            pred = 1e3 * bm.hash_time_s(img, cpb_sw, clk)
            src = "hash only"
        elif s:
            c = sigcyc(s, "Cortex-M33")
            pred = 1e3 * bm.verify_time_s(img, cpb_sw, c["cycles"], clk)
            src = c["cycle_label"] + " " + c["source"]
        else:
            pred, src = None, "no published verify cycles for this configuration"
        comp.append({"id": rid, "configuration": e["parameter_set"], "boot_ms_published": pub,
                     "verify_ms_modelled": round(pred, 3) if pred is not None else "",
                     "error_pct_modelled": round(bm.pct_increase(pub, pred), 1) if pred is not None else "",
                     "increment_over_hash_only_ms_published": round(pub - base_ms, 3),
                     "sig_ms_modelled": round(pred - 1e3 * bm.hash_time_s(img, cpb_sw, clk), 3) if pred is not None and rid != "S2-0347" else "",
                     "cycle_source": src, "label": "modelled"})
    # seeded calibration and validation split on rows with a prediction
    usable = [r for r in comp if r["sig_ms_modelled"] != ""]
    rng = np.random.default_rng(bm.SEED)
    order = rng.permutation(len(usable))
    cal_ids = {usable[i]["id"] for i in order[: (len(usable) + 1) // 2]}
    ratios = [r["increment_over_hash_only_ms_published"] / r["sig_ms_modelled"] for r in usable if r["id"] in cal_ids]
    k = float(np.median(ratios))
    overhead = base_ms - 1e3 * bm.hash_time_s(img, cpb_sw, clk)
    for r in comp:
        r["set"] = "calibration" if r["id"] in cal_ids else ("validation" if r in usable else "not predicted")
        if r["sig_ms_modelled"] != "" or r["id"] == "S2-0347":
            sm = r["sig_ms_modelled"] if r["sig_ms_modelled"] != "" else 0.0
            cal_pred = base_ms + k * sm
            r["boot_ms_modelled_calibrated"] = round(cal_pred, 3)
            r["error_pct_calibrated"] = round(bm.pct_increase(r["boot_ms_published"], cal_pred), 1)
        else:
            r["boot_ms_modelled_calibrated"] = ""
            r["error_pct_calibrated"] = ""
        r["seed"] = bm.SEED
    write_csv("wolfboot_comparison.csv", comp)
    val_err = [abs(r["error_pct_calibrated"]) for r in comp if r["set"] == "validation"]
    raw_err = [abs(r["error_pct_modelled"]) for r in comp if r["error_pct_modelled"] != ""]
    R.update(comp=comp, k=k, overhead=overhead, base_ms=base_ms, val_err=val_err, raw_err=raw_err,
             raw_ci=em.bootstrap_median_ci(raw_err), val_ci=em.bootstrap_median_ci(val_err) if val_err else None)

    # 2b. comparison with 2021/781 Table 8 (transfer and flash increments)
    ed_sig = float(ev["S10D-013"]["key_or_sig_size_bytes"])
    ed_libs = [float(ev[i]["flash_or_code_bytes"]) for i in sig["Ed25519"]["suit_lib_flash_ref"].split("|")]
    dhash = bm.inval(inp, "sha3_compact_flash_bytes") - bm.inval(inp, "sha256_riot_flash_bytes")
    t8 = []
    for s, key in (("Falcon-512", "falcon"), ("LMS", "lms"), ("ML-DSA-44", "dilithium")):
        sb = float(ev[sig[s]["suit_sig_bytes_ref"]]["key_or_sig_size_bytes"])
        libs = [float(ev[i]["flash_or_code_bytes"]) for i in sig[s]["suit_lib_flash_ref"].split("|")]
        u2 = 100 * (sb - ed_sig) / bm.inval(inp, "suit_u2_base_transfer_bytes")
        u3 = [100 * (sb - ed_sig + lib - el + dhash) / bm.inval(inp, "suit_u3_base_transfer_bytes")
              for lib in libs for el in ed_libs]
        pu2 = bm.inval(inp, f"suit_u2_{key}_increase_pct")
        pu3 = bm.inval(inp, f"suit_u3_{key}_increase_pct")
        t8.append({"scheme_in_paper": sig[s]["suit_name"], "u2_pct_published": pu2, "u2_pct_modelled": round(u2, 2),
                   "u2_error_points": round(u2 - pu2, 2), "u3_pct_published": pu3,
                   "u3_pct_modelled_low": round(min(u3), 1), "u3_pct_modelled_high": round(max(u3), 1),
                   "u3_published_inside_range": min(u3) <= pu3 <= max(u3), "label": "modelled"})
    write_csv("suit_table8_comparison.csv", t8)
    R["t8"] = t8

    # 3. verifier flash and RAM from published rows
    vf = []
    for s, v in sig.items():
        if v["boot_row"]:
            e = ev[v["boot_row"]]
            vf.append({"scheme": s, "id": v["boot_row"], "bootloader_flash_bytes_published": e["flash_or_code_bytes"],
                       "stack_bytes_published": e["stack_bytes"], "source": "wolfBoot on STM32H563", "label": "published"})
    for rid in ("S2-0033", "S2-0036", "S8-027", "S8-039", "S2-0060"):
        e = ev[rid]
        vf.append({"scheme": e["parameter_set"] + " verify (" + e["library"][:40] + ")", "id": rid,
                   "bootloader_flash_bytes_published": e["flash_or_code_bytes"], "stack_bytes_published": e["stack_bytes"],
                   "source": "library row (code size excludes common code where stated)", "label": "published"})
    write_csv("verifier_memory.csv", vf)
    R["vf"] = vf

    # 4. A and B slot overhead
    swap = bm.inval(inp, "ab_swap_sector_bytes")
    ab = []
    for s, v in sig.items():
        if not v["boot_row"]:
            continue
        boot_flash = float(ev[v["boot_row"]]["flash_or_code_bytes"])
        hdr = bm.inval(inp, "pq_image_header_bytes") if s not in ("Ed25519", "ECDSA P-256") else 256.0 + float(
            ev[v["sig_bytes_ref"]]["key_or_sig_size_bytes"])
        for fl_name in ("fmuv2_flash_limit_bytes", "fmuv3_flash_bytes"):
            fl = bm.inval(inp, fl_name)
            mx = bm.max_image_ab(fl, hdr, boot_flash, swap)
            ab.append({"scheme": s, "flash": fl_name, "flash_bytes": fl, "bootloader_bytes_published": boot_flash,
                       "header_bytes": hdr, "max_image_bytes_ab_estimated": round(mx),
                       "overhead_fraction_of_flash_estimated": round(1 - 2 * mx / fl, 4), "label": "estimated"})
    write_csv("ab_overhead.csv", ab)
    R["ab"] = ab

    # 5. transfer time per link
    rates = bm.link_rates(params)
    tr = []
    for lname, (rate, tag) in rates.items():
        for s in ("Ed25519", "ML-DSA-44", "ML-DSA-87", "LMS", "XMSS", "SLH-DSA-128s", "SLH-DSA-128f"):
            sb = float(ev[sig[s]["sig_bytes_ref"]]["key_or_sig_size_bytes"])
            for img in (100000, 1000000):
                tr.append({"link": lname, "rate_tag": tag, "effective_bps": rate, "scheme": s, "image_bytes": img,
                           "sig_bytes_published": sb, "transfer_s_estimated": round(bm.transfer_time_s(img + sb, rate), 2),
                           "signature_share_pct_estimated": round(100 * sb / (img + sb), 3), "label": "estimated"})
    write_csv("transfer_time.csv", tr)
    R["tr"] = tr

    # 6. Monte Carlo intervals and Sobol sensitivity for 1 MB on Cortex-M4 at 168 MHz
    names = ["image_bytes", "cycles_per_byte", "impl_factor", "clock_mhz"]
    bounds = [[250000, 2000000], list(R["cpb_sw_rng"]), [1.0, 2.3], [168.0, 250.0]]
    rng = np.random.default_rng(bm.SEED)
    mcr, sob = [], {}
    for s in ("Ed25519", "ML-DSA-44", "ML-DSA-87", "LMS", "XMSS", "SLH-DSA-128s"):
        cyc = sigcyc(s, "Cortex-M4")["cycles"]
        X = np.column_stack([rng.uniform(lo, hi, MC_N) for lo, hi in bounds])
        t = 1e3 * bm.verify_time_s(X[:, 0], X[:, 1], cyc * X[:, 2], X[:, 3])
        mcr.append({"scheme": s, "boot_ms_p2_5": round(float(np.percentile(t, 2.5)), 2),
                    "boot_ms_median": round(float(np.median(t)), 2), "boot_ms_p97_5": round(float(np.percentile(t, 97.5)), 2),
                    "sig_share_median_pct": round(float(np.median(100 * cyc * X[:, 2] / (X[:, 3] * 1e6) * 1e3 / t)), 2),
                    "n": MC_N, "seed": bm.SEED, "label": "modelled"})
        prob = {"num_vars": 4, "names": names, "bounds": bounds}
        Xs = sobol_sample.sample(prob, 1024, calc_second_order=False, seed=bm.SEED)
        Y = 1e3 * bm.verify_time_s(Xs[:, 0], Xs[:, 1], cyc * Xs[:, 2], Xs[:, 3])
        a = sobol_analyze.analyze(prob, Y, calc_second_order=False, seed=bm.SEED)
        sob[s] = [{"scheme": s, "input": n, "S1": round(float(a["S1"][i]), 4), "ST": round(float(a["ST"][i]), 4),
                   "ST_conf": round(float(a["ST_conf"][i]), 4), "seed": bm.SEED, "label": "modelled"}
                  for i, n in enumerate(names)]
    write_csv("boot_mc.csv", mcr)
    write_csv("boot_sobol.csv", [r for v in sob.values() for r in v])
    R.update(mc=mcr, sob=sob, bounds=bounds)
    figures(R)
    write_doc(R, inp)
    return R


def figures(R):
    plt.rcParams.update({"axes.edgecolor": "#880e4f", "axes.labelcolor": "#880e4f", "xtick.color": "#880e4f",
                         "ytick.color": "#880e4f", "axes.titlecolor": "#880e4f"})
    sel = [r for r in R["vt"] if r["target"].startswith("Crazyflie") and r["image_bytes"] == 1000000
           and r["hash"] == "software SHA-256"]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    x = np.arange(len(sel))
    ax.bar(x, [r["hash_ms_estimated"] for r in sel], color=PINK[1], label="SHA-256 over 1 MB image")
    ax.bar(x, [r["sig_ms_estimated"] for r in sel], bottom=[r["hash_ms_estimated"] for r in sel], color=PINK[0],
           label="signature verification")
    ax.set_xticks(x)
    ax.set_xticklabels([r["scheme"] for r in sel], rotation=30, ha="right", fontsize=8)
    ax.set_ylabel("ms")
    ax.set_title("Estimated boot verification time, 1 MB image, Cortex-M4 at 168 MHz, software hash\n"
                 "(label: estimated; published or derived cycles; no random step)", fontsize=9)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "boot_verify_time.png"), dpi=130)
    plt.close(fig)
    pts = [r for r in R["comp"] if r["verify_ms_modelled"] != ""]
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.scatter([r["boot_ms_published"] for r in pts], [r["verify_ms_modelled"] for r in pts], color=PINK[0],
               label="uncalibrated model")
    ax.scatter([r["boot_ms_published"] for r in pts], [r["boot_ms_modelled_calibrated"] for r in pts], color=PINK[4],
               marker="s", label="calibrated (seeded split)")
    for r in pts:
        ax.annotate(r["id"], (r["boot_ms_published"], r["verify_ms_modelled"]), fontsize=6, color="#880e4f")
    lim = [10, 3000]
    ax.plot(lim, lim, color=PINK[1], lw=1)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("published wolfBoot boot time (ms)")
    ax.set_ylabel("modelled (ms)")
    ax.set_title("Modelled versus published boot time, STM32H563 rows\n(label: modelled; seed 20261020)", fontsize=9)
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "boot_validation.png"), dpi=130)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(8, 4))
    sch = list(R["sob"].keys())
    names = [r["input"] for r in R["sob"][sch[0]]]
    w = 0.8 / len(names)
    for i, n in enumerate(names):
        ax.bar(np.arange(len(sch)) + i * w, [next(r["ST"] for r in R["sob"][s] if r["input"] == n) for s in sch], w,
               label=n, color=PINK[i])
    ax.set_xticks(np.arange(len(sch)) + 0.4 - w / 2)
    ax.set_xticklabels(sch, fontsize=8)
    ax.set_ylabel("total Sobol index")
    ax.set_title("Sobol total indices for boot verification time\n(label: modelled; SALib N=1024; seed 20261020)",
                 fontsize=9)
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "boot_sobol.png"), dpi=130)
    plt.close(fig)


def write_doc(R, inp):
    L = []
    L.append("# Signed boot and update chain study\n")
    L.append("Author: Huda Mueen. Generated by `bootchain/run_all.py` (run `python3 -m bootchain.run_all` from the repository "
             "root). Seed 20261020. Do not edit by hand.\n")
    L.append("## Labels and model\n")
    L.append("Verification time = SHA-256 over the image (cycles per byte x bytes / clock) + one signature verification "
             "(cycles / clock). Signature cycles are `published` rows of `data/evidence.csv` or `derived from published` "
             "times; cycles per byte are `derived from published` throughput. Times are `estimated`. Comparisons with "
             "published boot measurements are `modelled` with the error stated beside them. Where a core has no row the "
             "Cortex-M4 row is used and marked `proxy`. Sources: `data/raw/S12_boot_sources.md`.\n")
    lo, hi = R["cpb_sw_rng"]
    L.append(f"SHA-256 cycles per byte: software median {R['cpb_sw']:.1f} (range {lo:.1f} to {hi:.1f}, three Cortex-M4 "
             f"boards); hardware HASH median {R['cpb_hw']:.2f} (range {R['cpb_hw_rng'][0]:.2f} to {R['cpb_hw_rng'][1]:.2f}). "
             "No vendor reference manual was retrieved; the hardware figure comes from benchmark pages.\n")
    L.append("Caveat on the hardware HASH rows: the STM32F405 of the Crazyflie 2.1 has no hash peripheral; parts of the same "
             "family with a cryptographic block have one. The hardware HASH rows for that target are a what if for such a part "
             "at the same clock, not a property of the Crazyflie.\n")
    L.append("Naming: the SLH-DSA-128s and SLH-DSA-128f rows use pqm4 rows of SPHINCS+ (round 3, sha2, simple), the pre standard "
             "design that SLH-DSA was derived from; they stand in for SLH-DSA, for which the evidence table holds sizes but no cycle rows.\n")
    L.append("Image size: no retrieved source states a PX4 or ArduPilot binary size. The cited limits are 1 MB (early FMUv2 "
             "flash) and 2 MB (FMUv3), and the Crazyflie MCU has 1 MB of flash. Image sizes of 0.1 to 2 MB are therefore "
             "assumptions bounded by cited limits (`unverified`).\n")
    L.append("## 1. Verification time (estimated)\n")
    L.append("| Target | Scheme | Image | Hash | Hash ms | Signature ms | Total ms | Cycle source label |")
    L.append("|---|---|---|---|---|---|---|---|")
    for r in R["vt"]:
        if r["image_bytes"] == 1000000 and r["target"].startswith(("Crazyflie", "STM32H563")):
            L.append(f"| {r['target']} | {r['scheme']} | 1 MB | {r['hash']} | {f3(r['hash_ms_estimated'])} | "
                     f"{f3(r['sig_ms_estimated'])} | {f3(r['total_ms_estimated'])} | {r['cycle_source_label']} ({r['cycle_source']}) |")
    cf = [r for r in R["vt"] if r["target"].startswith("Crazyflie") and r["image_bytes"] == 1000000]
    sw_sig_dom = sorted({r["scheme"] for r in cf if r["hash"] == "software SHA-256" and r["sig_ms_estimated"] > r["hash_ms_estimated"]})
    hw_sig_dom = sorted({r["scheme"] for r in cf if r["hash"] == "hardware HASH" and r["sig_ms_estimated"] > r["hash_ms_estimated"]})
    L.append("\nAll sizes and targets: `bootchain/results/verify_time.csv`. On the Cortex-M4 at 168 MHz with a 1 MB image, "
             "schemes whose signature term exceeds the software hash term: "
             f"{', '.join(sw_sig_dom) if sw_sig_dom else 'none'}. With the hardware HASH figure: "
             f"{', '.join(hw_sig_dom) if hw_sig_dom else 'none'}. With a software hash the hash path, not the signature "
             "choice, sets most of the boot verification time.\n")
    L.append("## 2. Comparison with published boot and update measurements\n")
    L.append(f"### wolfBoot total boot time (rows S2-0347 to S2-0357, STM32H563, about 100 KB image)\n")
    L.append("The published figure is total boot time from reset to a GPIO signal, not verification alone. The uncalibrated "
             "model uses Cortex-M4 cycle rows (proxy for the Cortex-M33) and the recorded 320 MHz clock (the product page "
             "states 250 MHz maximum).\n")
    L.append("| Row | Configuration | Published ms | Modelled ms (uncalibrated) | Error percent | Calibrated ms | Error percent (calibrated) | Set |")
    L.append("|---|---|---|---|---|---|---|---|")
    for r in R["comp"]:
        L.append(f"| {r['id']} | {r['configuration']} | {r['boot_ms_published']} | {r['verify_ms_modelled']} | "
                 f"{r['error_pct_modelled']} | {r['boot_ms_modelled_calibrated']} | {r['error_pct_calibrated']} | {r['set']} |")
    rc = R["raw_ci"]
    L.append(f"\nUncalibrated median absolute error {statistics.median(R['raw_err']):.0f} percent over {len(R['raw_err'])} rows "
             f"(bootstrap 95 percent interval {rc[0]:.0f} to {rc[1]:.0f}). This is a negative result: the model built from "
             "library cycle counts underestimates wolfBoot boot time strongly, because the published hash only "
             f"row exceeds the modelled hash by about {R['overhead']:.0f} ms (fixed boot work, a slower hash, or both), and because the wolfCrypt "
             "implementations and parameter sets differ from the library rows (for example the boot row uses LMS with "
             "Winternitz 8 while the cycle row uses w=16, and the ML-DSA rows differ by implementation). "
             f"Calibration (seeded half split, seed {bm.SEED}): fixed term = published hash only time, signature term "
             f"multiplied by k = {R['k']:.2f} (median ratio on the calibration rows). The published Ed25519 row (S2-0350, about 1.6 s) is far slower than the other classical rows and pulls the calibration; it is kept as published.")
    if R["val_err"]:
        vc = R["val_ci"]
        L.append(f"On the {len(R['val_err'])} validation rows the median absolute error is {statistics.median(R['val_err']):.0f} "
                 f"percent (interval {vc[0]:.0f} to {vc[1]:.0f}, maximum {max(R['val_err']):.0f}). With so few rows and one "
                 "scale factor across unlike implementations, this validation is weak. Split: "
                 "`bootchain/results/wolfboot_comparison.csv`.\n")
    L.append("### 2021/781 SUIT update costs (supplied PDF, Table 8, page 15)\n")
    L.append("Modelled transfer increase for U2 = (post quantum signature bytes minus 64) / 47 kB. Modelled U3 increase "
             "adds the change in signature library flash (Table 5) and hash flash (Table 1), with a range over the two "
             "Ed25519 libraries.\n")
    L.append("| Scheme (paper) | U2 published percent | U2 modelled | Error (points) | U3 published percent | U3 modelled range | Published inside range |")
    L.append("|---|---|---|---|---|---|---|")
    for r in R["t8"]:
        L.append(f"| {r['scheme_in_paper']} | {r['u2_pct_published']} | {r['u2_pct_modelled']} | {r['u2_error_points']} | "
                 f"{r['u3_pct_published']} | {r['u3_pct_modelled_low']} to {r['u3_pct_modelled_high']} | "
                 f"{r['u3_published_inside_range']} |")
    L.append("\nThe paper does not state how U3 composes the library change, so a mismatch in U3 is reported rather than "
             "tuned away. The 2021/781 tables contain no end to end boot or update time measurement, so no time comparison "
             "with this paper is possible (null result).\n")
    L.append("## 3. Verifier flash and RAM (published)\n")
    L.append("| Scheme | Row | Flash bytes | Stack bytes | Source |")
    L.append("|---|---|---|---|---|")
    for r in R["vf"]:
        L.append(f"| {r['scheme']} | {r['id']} | {r['bootloader_flash_bytes_published']} | {r['stack_bytes_published']} | {r['source']} |")
    L.append("")
    L.append("## 4. A and B slot flash overhead (estimated)\n")
    L.append("Largest image that fits two slots = (flash - bootloader - swap sector) / 2 - header. Bootloader size from "
             "the wolfBoot rows; header 5288 B (cited wolfBoot LMS example) for post quantum schemes and an assumed 256 B "
             "plus the signature for classical schemes; swap sector 4096 B is an assumption.\n")
    L.append("| Scheme | Flash | Bootloader bytes | Max image per slot (bytes) | Share of flash not usable for one image |")
    L.append("|---|---|---|---|---|")
    for r in R["ab"]:
        L.append(f"| {r['scheme']} | {r['flash_bytes']:,.0f} | {r['bootloader_bytes_published']:,.0f} | "
                 f"{r['max_image_bytes_ab_estimated']:,} | {r['overhead_fraction_of_flash_estimated']} |")
    bl = [r["bootloader_bytes_published"] for r in R["ab"]]
    L.append("\nThe A and B layout, not the signature, is the dominant flash cost: it halves the space for the image. The "
             f"published bootloader sizes range from {min(bl):,.0f} to {max(bl):,.0f} bytes across the schemes.\n")
    L.append("## 5. Transfer time per link (estimated)\n")
    L.append("Simple bytes over rate using `linksim/params.csv`. No loss, retries, framing or acknowledgement. The link "
             "model's own validation is weak (see `docs/LINKSIM_STUDY.md`), and this simplest form ignores even what that "
             "model includes.\n")
    L.append("| Link | Scheme | Image | Transfer s | Signature share of bytes, percent |")
    L.append("|---|---|---|---|---|")
    for r in R["tr"]:
        if r["image_bytes"] == 1000000 and r["scheme"] in ("Ed25519", "ML-DSA-44", "LMS", "SLH-DSA-128f"):
            L.append(f"| {r['link']} ({r['rate_tag']}) | {r['scheme']} | 1 MB | {f3(r['transfer_s_estimated'])} | "
                     f"{r['signature_share_pct_estimated']} |")
    mx = max(r["signature_share_pct_estimated"] for r in R["tr"] if r["image_bytes"] == 1000000)
    mx100 = max(r["signature_share_pct_estimated"] for r in R["tr"] if r["image_bytes"] == 100000)
    mxs = sorted({r["scheme"] for r in R["tr"] if r["signature_share_pct_estimated"] in (mx, mx100)})
    L.append(f"\nThe largest signature share is {mx} percent of the bytes for a 1 MB image and {mx100} percent for a 100 kB "
             f"image ({', '.join(mxs)}), so the link cost of a post quantum signature on a full image is small; it matters "
             "for small module updates, and on low rate links such as LoRaWAN any full image transfer is impractical.\n")
    L.append("## 6. Where an immutable root of trust forces replacement\n")
    L.append("- Boot code in ROM cannot be changed, so its signature algorithm must outlive the device; RFC 9019 recommends "
             "post quantum (for example hash based) signatures for such code (`data/raw/S4_migration.md`, RFC 9019 entry).")
    L.append("- Functions built into an integrated circuit cannot change, so a chip must be replaced if its algorithm must "
             "change (NIST CSWP 39 section 4.5, in `data/raw/S4_migration.md`).")
    L.append("- A firmware update can add a software post quantum verifier or a parallel post quantum identity chain, but "
             "cannot make a ROM rooted classical chain quantum safe (Caliptra example, `data/raw/S4_migration.md`).")
    L.append("- The STM32H563 product page lists ECDSA signature verification and a HASH accelerator; the STM32U5A5 page lists "
             "a PKA. Neither page states post quantum support (`unverified`). If the immutable first stage of such a part "
             "verifies with a fixed classical block and its key hash is fused, the classification above applies; whether "
             "the first stage is replaceable was not checked.\n")
    L.append("## 7. Sensitivity and intervals (modelled)\n")
    b = R["bounds"]
    L.append(f"Uniform inputs: image {b[0][0]:,} to {b[0][1]:,} B (assumption), cycles per byte {b[1][0]:.1f} to "
             f"{b[1][1]:.1f} (derived), implementation factor 1 to 2.3 (assumption), clock 168 to 250 MHz (cited clocks). "
             f"{MC_N} draws, seed {bm.SEED}.\n")
    L.append("| Scheme | Boot ms median (2.5 to 97.5 percentile) | Signature share of time, median percent | Dominant input (total Sobol index) |")
    L.append("|---|---|---|---|")
    for r in R["mc"]:
        top = max(R["sob"][r["scheme"]], key=lambda x: x["ST"])
        L.append(f"| {r['scheme']} | {f3(r['boot_ms_median'])} ({f3(r['boot_ms_p2_5'])} to {f3(r['boot_ms_p97_5'])}) | "
                 f"{r['sig_share_median_pct']} | {top['input']} ({top['ST']:.2f}) |")
    L.append("\n## Figures\n")
    L.append("- `docs/figures/bootchain/boot_verify_time.png`: estimated verification time split, 1 MB, Cortex-M4 at 168 MHz.")
    L.append("- `docs/figures/bootchain/boot_validation.png`: modelled versus published wolfBoot boot time, seed 20261020.")
    L.append("- `docs/figures/bootchain/boot_sobol.png`: Sobol total indices, modelled, seed 20261020.\n")
    with open(DOC, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")


if __name__ == "__main__":
    build()
    print("seed", bm.SEED, "wrote", DOC)
