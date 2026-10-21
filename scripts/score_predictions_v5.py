#!/usr/bin/env python3
"""Score the round 5 predictions (docs/PREDICTIONS_V5.md) strictly by their registered clauses.

Author: Huda Mueen. Writes docs/PREDICTIONS_V5_SCORES.md. Every verdict is computed from a result file;
where a registered metric could not be computed, the verdict is "not scored" with the reason. Where the
registered wording allows two readings, the reading less favourable to the prediction is used and named.
"""
import csv
import hashlib
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def R(p):
    return pd.read_csv(ROOT / p)


def verdict(ok, partial=False):
    return "hit" if ok else ("between" if partial else "miss")


def exists(p):
    return (ROOT / p).exists()


def score():
    S = {}
    # WP1 flight stack memory
    fm = R("data/flightstack_memory.csv")
    built = fm[fm.build_status == "built"]
    n_boards = built.board.nunique()
    S["P1"] = (verdict(n_boards >= 5, n_boards >= 3), f"{n_boards} board classes with measured free memory from {len(built)} builds.")
    mf = float(built.flash_free_share.median())
    S["P2"] = (verdict(mf >= 0.25, mf >= 0.10), f"Median free flash share over {len(built)} builds: {mf:.3f}.")
    mr = float(built.ram_free_share.median())
    S["P3"] = (verdict(mr >= 0.30, mr >= 0.10), f"Median free static RAM share over {len(built)} builds: {mr:.3f} (an upper bound: heap use at run time is not visible).")
    ms = R("planner/results/flightstack_mc_summary.csv")
    row = ms[ms.thresholds == "stack_asm"].iloc[0]
    ch = abs(float(row.change_median))
    S["P4"] = (verdict(ch < 0.05, ch <= 0.10), f"Profile fleet median replacement share, stack optimised thresholds (the registered scenario): {row.assumed_median:.3f} with assumed free memory against {row.measured_median:.3f} with measured free memory, change {row.change_median:+.3f}. The registration quoted 0.201, the round 4 median of the uncertain scenario; under that scenario the change is {float(ms[ms.thresholds == 'uncertain'].change_median.iloc[0]):+.3f}, which also meets the refutation clause.")
    pb = R("planner/results/flightstack_per_board.csv")
    f4 = pb[(pb.board.str.contains("F405")) & (pb.free_memory == "measured")]
    if len(f4):
        tot = f4[["FIRMWARE_UPDATE", "HYBRID", "HARDWARE_REPLACEMENT", "NO_ACTION_BEFORE_RETIREMENT", "UNKNOWN"]].sum()
        fits = int(tot.FIRMWARE_UPDATE) > 0
        S["P5"] = (verdict(not fits), f"STM32F405 class with measured memory, all scenarios: firmware update {int(tot.FIRMWARE_UPDATE)}, hybrid {int(tot.HYBRID)}, hardware replacement {int(tot.HARDWARE_REPLACEMENT)} device decisions. Memory is above every threshold; the replacements come from the missing updatable boot stage, not from memory.")
    else:
        S["P5"] = ("not scored", "No measured row for the STM32F405 class.")
    reason = "Public flight logs could not be used: the PX4 log sites disallow automated access and state no reuse licence (`flightstack/flightlog_access.csv`)."
    S["P6"] = ("miss", "Flights with derived statistics: 0, below the refutation threshold of 20. " + reason)
    S["P7"] = ("not scored", reason)
    S["P8"] = ("not scored", reason + " The mission study was not rerun with real traffic.")
    # WP2 software in the loop
    if exists("sitl/results/sitl_summary.csv"):
        ss = R("sitl/results/sitl_summary.csv")
        S.update(score_sitl(ss))
    else:
        for k in ("P9", "P10", "P11", "P12", "P13"):
            S[k] = ("not scored", "No software in the loop results committed.")
    # WP3 network simulator
    gs = R("netsim/results/gap_sweep.csv")
    b = gs[gs.cell == "base_frame"].iloc[0]
    d = float(b.time_mean_s_simulated_network) / float(b.time_s_modelled) - 1
    in_pub = 30 <= float(b.time_mean_s_simulated_network) <= 60
    S["P14"] = ("miss" if in_pub else verdict(abs(d) <= 0.30), f"ns-3 one hop 50 kB: {b.time_mean_s_simulated_network:.2f} s against the link model {b.time_s_modelled:.2f} s ({100 * d:+.1f} percent); published range 30 to 60 s.")
    hops = gs[gs.cell.str.match(r"^hops_\d+$")].copy()
    hops["h"] = hops.cell.str.extract(r"(\d+)").astype(int)
    reach = hops[(hops.time_mean_s_simulated_network >= 30)]
    hmin = int(reach.h.min()) if len(reach) else None
    base_reach = float(b.time_mean_s_simulated_network) >= 30
    hm = 1 if base_reach else hmin
    S["P15"] = ("not scored" if hm is None else verdict(hm >= 3, hm != 1), f"Smallest hop count at which ns-3 reaches 30 s: {hm} (first registered sweep).")
    lf = R("netsim/results/lora_flights_compare.csv")
    dr5 = lf[lf.dr == 5]
    worst5 = float(max(dr5.err_blast_vs_ns3_pct.abs().max(), dr5.err_protocol_sim_vs_ns3_pct.abs().max()))
    S["P16"] = (verdict(worst5 <= 20, worst5 <= 50), f"Largest absolute difference at DR5 between the link model (both its flight by flight calculation and its protocol simulation, the less favourable taken) and ns-3 over {len(dr5)} handshake profiles: {worst5:.2f} percent (computed on the round 4 three flight handshakes the ns-3 runs used).")
    sr = R("netsim/results/sr_closed_form.csv")
    pre = sr[sr.role == "pre set check"]
    n_in = int(pre.inside.astype(str).eq("True").sum())
    S["P17"] = (verdict(n_in == len(pre)), f"Selective repeat, registered first run: closed form inside the interval at {n_in} of {len(pre)} loss rates. Follow up seed blocks added after the first run are not scored.")
    lt = R("netsim/results/lora_toa_compare.csv")
    w = float(lt.err_model_vs_ns3_pct.abs().max())
    S["P18"] = (verdict(w <= 1, w <= 5), f"Largest difference between ns-3 and the time on air formula over {len(lt)} frame sizes: {w:.2f} percent (both implement the same formula).")
    # WP4 formal
    fr = R("formal/results/proverif_results.csv")
    st = fr[fr.model == "session_b_stated"].set_index("property_id").result
    keys_ok = all(st.get(k) == "proved" for k in ("S1", "S2", "S3", "S4"))
    cmd_ok = st.get("C1") == "proved"
    S["P19"] = (verdict(keys_ok and cmd_ok), f"Stated design (the reading the registered question names): command agreement (C1) {st.get('C1')}; secrecy of the vehicle's session keys (S1 {st.get('S1')}, S3 {st.get('S3')}); secrecy of the ground station's session keys (S2 {st.get('S2')}, S4 {st.get('S4')}), because the stated design does not let the ground station authenticate the vehicle. With design change F1 all eight properties are proved.")
    stated_models = [m for m in fr.model.unique() if "stated" in m and "fs" not in m]
    fails = fr[fr.model.isin(stated_models) & (fr.result == "counterexample")]
    S["P20"] = (verdict(len(fails) >= 1), f"Counterexamples in the first models as written: {len(fails)} ({', '.join(sorted(set(fails.model + ' ' + fails.property_id)))}).")
    fw = fr[fr.property_id == "D1"].set_index("model").result
    with_counter = [fw.get("firmware_fixed_counter"), fw.get("firmware_counter_unsigned_version")]
    S["P21"] = (verdict(fw.get("firmware_fixed_counter") == "proved" and fw.get("firmware_stated_no_counter") == "counterexample"),
                f"Registered pair: with a monotonic version counter (design F3, which also signs the version) {fw.get('firmware_fixed_counter')}; without a counter {fw.get('firmware_stated_no_counter')}. A variant written after registration, a counter with an unsigned version, gives {fw.get('firmware_counter_unsigned_version')}: the counter alone is not enough.")

    fs_stated = fr[fr.model == "session_b_stated_fs_longterm"].set_index("property_id").result
    fs_fixed = fr[fr.model == "session_b_fixed_fs_longterm"].set_index("property_id").result
    S["P22"] = (verdict(all(v == "proved" for v in fs_stated)), f"Stated design: earlier session keys after long term key compromise {', '.join(f'{k} {v}' for k, v in fs_stated.items())}; the counterexamples follow from the missing vehicle authentication (F1). With F1: {', '.join(f'{k} {v}' for k, v in fs_fixed.items())}.")
    # WP5 statistics
    lo = R("stats/results/cycle_lofo_summary.csv")
    fam = lo[(lo.left_out_by == "implementation family") & (lo.group == "all groups pooled") & (lo.model == "fitted")].iloc[0]
    v = float(fam.median_abs_pct)
    S["P23"] = (verdict(v > 5, v >= 2), f"Leave one implementation family out, pooled median absolute error {v:.1f} percent (scheme left out: {float(lo[(lo.left_out_by == 'scheme') & (lo.group == 'all groups pooled') & (lo.model == 'fitted')].iloc[0].median_abs_pct):.1f} percent).")
    cb = R("stats/results/cycle_cluster_bootstrap.csv")
    c = cb[(cb.model == "fitted") & (cb.subset == "test, all")].iloc[0]
    hi = float(c.median_abs_cluster_ci_hi)
    row_hi = float(c.median_abs_ci_hi) if "median_abs_ci_hi" in c.index and pd.notna(c.get("median_abs_ci_hi")) else float(R("cyclemodel/results/error_summary.csv").query('model == "fitted" and subset == "test, all"').median_abs_ci_hi.iloc[0])
    S["P24"] = (verdict(hi >= 2.5, hi > row_hi + 1e-9), f"Cluster bootstrap 95 percent interval of the median absolute error: {c.median_abs_cluster_ci_lo:.2f} to {hi:.2f} percent; the round 4 row bootstrap upper bound is {row_hi:.2f} percent, compared unrounded.")
    hv = R("data/meta/hierarchical_variance.csv")
    main = hv[(hv.weighting == "unweighted") & (hv.fit == "main (variant as stated)") & (hv.component != "residual")]
    top = main.loc[main.share_within_cell.idxmax()]
    alt = hv[(hv.weighting == "unweighted") & (hv.fit == "worst observed rows excluded: main (variant as stated)") & (hv.component != "residual")]
    alt_top = alt.loc[alt.share_within_cell.idxmax()] if len(alt) else None
    tops = {top.component} | ({alt_top.component} if alt_top is not None else set())
    S["P25"] = ("miss" if tops & {"source", "statistic"} else ("hit" if tops == {"variant"} else "between"),
                f"Main unweighted fit: largest share {top.component} ({100 * top.share_within_cell:.1f} percent), but compiler and statistic have overlapping intervals; " + (f"the fit without the worst observed rows ({alt_top.fit}) makes {alt_top.component} the largest ({100 * alt_top.share_within_cell:.1f} percent), which meets the refutation clause." if alt_top is not None else "no sensitivity fit."))

    tl = R("data/verify5/third_look_summary.csv")
    sub = tl[tl.measure.str.startswith("staging wrong in substance")].iloc[0]
    verb = tl[tl.measure.str.startswith("staged text differs verbatim from the source among settled")].iloc[0]
    s1, s2 = float(sub.share), float(verb.share)
    vs = [verdict(0.05 <= x <= 0.15, 0.02 <= x <= 0.25) for x in (s1, s2)]
    S["P26"] = ("miss" if "miss" in vs else ("between" if "between" in vs else "hit"),
                f"Two readings of the registered metric: wrong in substance {int(sub['count'])} of {int(sub['of'])} ({100 * s1:.1f} percent); differs verbatim {int(verb['count'])} of {int(verb['of'])} ({100 * s2:.1f} percent). Both meet the refutation clause.")
    so = R("stats/results/e2e_sobol.csv")
    y1 = so[so.output == "hybrid_availability_sik_drone"].sort_values("ST", ascending=False).iloc[0]
    link_like = any(k in y1.input for k in ("outage", "loss", "deadline", "turnaround", "rate"))
    cyc_like = "cycle" in y1.input or "impl_factor" in y1.input
    S["P27"] = ("miss" if cyc_like else verdict(link_like), f"Largest total Sobol index for hybrid availability: {y1.input} ({y1.ST:.2f}).")
    # WP6 literature
    ev = pd.read_csv(ROOT / "data/evidence.csv", dtype=str)
    n13 = int((ev.stream == "S13").sum())
    S["P28"] = (verdict(n13 >= 150, n13 >= 75), f"{n13} new rows after double reading.")
    final205 = ev[(ev.stream.isin(["S13"])) & ev.scheme.fillna("").str.contains("FIPS 205") & ~ev.scheme.fillna("").str.contains("draft")]
    S["P29"] = (verdict(len(final205) >= 1), f"Rows with final FIPS 205 SLH-DSA cycle counts on a microcontroller: {len(final205)} (the rows found are of the FIPS 205 initial public draft on an accelerated FPGA prototype, which the registered question, final standard, excludes).")
    rs = list(csv.DictReader(open(ROOT / "data/verify6/row_status.csv")))
    wrong = sum(1 for r in rs if r["status"] == "corrected")
    judged = [r for r in rs if r["status"] in ("confirmed", "corrected", "blocked")]
    unconf = len(rs) - len(judged)
    rate = wrong / len(judged) if judged else float("nan")
    S["P30"] = (verdict(rate <= 0.05, rate <= 0.10), f"Staged rows with a wrong value before adjudication: {wrong} of the {len(judged)} rows whose values two readers could judge; {unconf} more rows had a value that fewer than two readers confirmed, so whether they hold a wrong value is unknown. Counting all of those as wrong would give {(wrong + unconf) / len(rs):.3f}.")
    c24 = float(ev[ev.id == "S13-024"].cycles.iloc[0])
    c331 = float(ev[ev.id == "S12A-331"].cycles.iloc[0])
    ratio = c24 / c331
    S["P31"] = (verdict(1.0 <= ratio <= 1.2, ratio <= 1.5), f"Owens et al. Ed25519 verify at 168 MHz over 24 MHz: {c24:.0f} / {c331:.0f} = {ratio:.3f} (informed).")
    # WP7
    cs = R("rtlsim/results/core_spread.csv")
    v44 = cs[(cs.parameter_set == "ML-DSA-44") & (cs.operation == "verify")].iloc[0]
    m = float(v44.max_over_min)
    S["P32"] = (verdict(1.2 <= m <= 3, 1.1 <= m <= 5), f"ML-DSA-44 verify, largest over smallest across {int(v44.n_cores)} open cores ({v44.cores}): {m:.2f}. VexRiscv was not run.")
    k768 = cs[(cs.parameter_set == "ML-KEM-768") & (cs.operation == "decaps")].iloc[0]
    S["P33"] = (verdict(k768.fastest_core == "cv32e40p"), f"ML-KEM-768 decaps: CV32E40P {int(k768.cycles_median_cv32e40p)} cycles, Ibex {int(k768.cycles_median_ibex)}.")
    import json
    dry = json.load(open(ROOT / "bench/board_kit/dry_run/dry_run_summary.json"))
    sizes = R("bench/board_kit/image_sizes.csv")
    m33 = sizes.platform.astype(str).str.contains("l552").any()
    parsed = dry.get("recognised_percent")
    passes = dry.get("passes", {})
    allp = all(float(p.get("recognised_percent", 0)) == 100.0 for p in passes.values()) if passes else parsed == 100.0
    per_pass = ", ".join(str(k) + " " + str(v.get("recognised_percent")) for k, v in passes.items())
    S["P34"] = (verdict(m33 and allp), f"M33 images built: {'yes' if m33 else 'no'}; emulator log lines parsed: {parsed} percent overall; per cache pass: {per_pass}.")
    S["P35"] = ("miss", "The scheme families are unchanged (LMS for firmware, a hybrid session for commands, no per command signatures), but the designs changed in this round: the vehicle now signs the handshake (F1) and firmware needs a signed version and a monotonic counter (F3). Under the stricter reading, a change of either design meets the refutation clause (`docs/REFERENCE_ARCHITECTURE.md`; RUN_LOG entry 93).")

    # WP11 and WP12
    rf = ROOT / "docs/REVIEW_FINDINGS5.csv"
    if rf.exists():
        f = list(csv.DictReader(open(rf, encoding="utf-8")))
        p1 = [x for x in f if x.get("pass") == "1"]
        S["P36"] = (verdict(len(p1) >= 20, len(p1) >= 10), f"First pass: {len(p1)} findings.")
        has2 = any(x.get("pass") == "2" for x in f)
        p2h = [x for x in f if x.get("pass") == "2" and x.get("severity", "").lower() == "high"]
        S["P37"] = (verdict(len(p2h) == 0) if has2 else "not scored", f"Second pass: {len(p2h)} high severity findings." if has2 else "No second pass recorded.")
    rub = (ROOT / "docs/COMPLETENESS_RUBRIC.md").read_text()
    sec = rub.split("## Score at the start of round 5", 1)
    if len(sec) == 2:
        mm = re.findall(r"\*\*([\d.]+) of 10\*\*", sec[1])
        if len(mm) >= 2:
            dd = float(mm[1]) - float(mm[0])
            S["P38"] = (verdict(dd >= 1.0, dd >= 0.5), f"Rubric from {mm[0]} to {mm[1]} (change {dd:+.1f}).")
    return S


def score_sitl(ss):
    """Score P9 to P13 from sitl/results/sitl_summary.csv (one row per configuration and link profile)."""
    S = {}
    sik = ss[ss.link.str.contains("sik", case=False)]
    nmin = int(sik.missions_completed.min())
    S["P9"] = (verdict(nmin >= 20 and sik.configuration.nunique() >= 4, nmin >= 10), f"Fewest completed scripted missions in a configuration on the SiK class link: {nmin}; configurations: {sik.configuration.nunique()}.")
    def get(cfg, col):
        r = sik[sik.configuration == cfg]
        return float(r[col].iloc[0]) if len(r) and pd.notna(r[col].iloc[0]) else None
    a = get("mavlink2_signing", "added_latency_ms_median")
    S["P10"] = ("not scored" if a is None else verdict(a < 1, a <= 5), "Median added command latency of MAVLink 2 signing against no authentication: " + ("not available" if a is None else f"{a:.2f} ms") + ".")
    h = get("hybrid_session", "handshake_s_median")
    S["P11"] = ("not scored" if h is None else verdict(0.5 <= h <= 3, 0.2 <= h <= 5), "Median hybrid session handshake time: " + ("not available" if h is None else f"{h:.2f} s") + ".")
    c = get("pq_signature_per_command", "added_latency_ms_median")
    mref = get("pq_signature_per_command", "mission_study_added_latency_ms")
    if c is None or mref is None or mref == 0:
        S["P12"] = ("not scored", "Added latency per command with a signature per command, or its mission study value, not available.")
    else:
        f = c / mref
        S["P12"] = (verdict(0.5 <= f <= 2, 1 / 3 <= f <= 3), f"Signature per command: SITL {c:.0f} ms against the mission study {mref:.0f} ms (ratio {f:.2f}).")
    av = get("hybrid_session", "availability")
    aref = get("hybrid_session", "mission_study_availability")
    if av is None or aref is None:
        S["P13"] = ("not scored", "Availability or its mission study value not available.")
    else:
        dd = abs(av - aref)
        S["P13"] = (verdict(dd < 0.05, dd <= 0.10), f"Hybrid session availability: SITL {av:.3f} against the mission study {aref:.3f} (difference {dd:.3f}).")
    return S


def main():
    S = score()
    text = (ROOT / "docs/PREDICTIONS_V5.md").read_text(encoding="utf-8")
    ids = re.findall(r"^\| (P\d+) \|", text, re.M)
    stored = (ROOT / "docs/PREDICTIONS_V5.md.sha256").read_text().split()[0]
    now = hashlib.sha256((ROOT / "docs/PREDICTIONS_V5.md").read_bytes()).hexdigest()
    counts = {}
    L = ["# Scores of the round 5 predictions", "",
         "Author: Huda Mueen. Generated by `scripts/score_predictions_v5.py` from result files; do not edit by hand. "
         "Verdicts follow the vocabulary registered in `docs/PREDICTIONS_V5.md` before any run. Where a clause allows two readings, "
         "the reading less favourable to the prediction is used and named.", "",
         f"Hash check: the predictions file {'matches' if now == stored else 'DOES NOT match'} its registered SHA-256.", "",
         "| ID | Verdict | Evidence |", "|---|---|---|"]
    for i in ids:
        v, why = S.get(i, ("not scored", "Not yet scored."))
        counts[v] = counts.get(v, 0) + 1
        L.append(f"| {i} | {v} | {why} |")
    L += ["", "Totals: " + ", ".join(f"{counts.get(k, 0)} {k}" for k in ("hit", "between", "miss", "not scored")) + f", of {len(ids)}.", ""]
    (ROOT / "docs/PREDICTIONS_V5_SCORES.md").write_text("\n".join(L), encoding="utf-8")
    print(L[-2])


if __name__ == "__main__":
    main()
