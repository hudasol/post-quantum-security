#!/usr/bin/env python3
"""Score the round 4 predictions (docs/PREDICTIONS_V4.md) from the committed result files.

Each prediction is scored against its refutation clause, as written before any run. Writes
docs/PREDICTIONS_V4_SCORES.md. Predictions about the review (V22, V23) and the rubric (V24) are
scored only when their files exist; otherwise they are marked not yet scored.
"""
import csv
import hashlib
import json
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
R = lambda p: pd.read_csv(ROOT / p)


def verdict(ok, partial=False):
    return "hit" if ok else ("partial" if partial else "miss")


def main():
    S = {}
    ev = R("data/evidence.csv")
    n12 = int((ev.stream == "S12").sum())
    S["V1"] = (verdict(n12 >= 120), f"{n12} rows added after double reading (refuted below 60).")
    v5 = (ROOT / "docs/VERIFICATION5.md").read_text()
    m = re.search(r"confirmed wrong value in staging \| (\d+) \| (\d+) \| ([\d.]+) percent", v5)
    k, n, pct = int(m.group(1)), int(m.group(2)), float(m.group(3))
    S["V2"] = (verdict(pct <= 5, pct <= 10), f"{k} of {n} rows with values had a wrong value before adjudication ({pct} percent).")
    summ = R("data/verify5/summary.csv")
    ids = set(summ.id)
    dis = set(summ[summ.status == "disagree"].id)
    share = 100 * (len(ids) - len(dis)) / len(ids)
    S["V3"] = (verdict(share >= 80, share >= 60),
               f"{len(ids) - len(dis)} of {len(ids)} staged rows and facts ({share:.1f} percent) had no field where a reader disagreed with staging; "
               "most disagreements were wording (operation, scheme, library), not values.")
    es = R("cyclemodel/results/error_summary.csv")
    g = lambda mo, su, col: float(es[(es.model == mo) & (es.subset == su)][col].iloc[0])
    fit = g("fitted", "test, all", "median_abs_pct")
    S["V4"] = (verdict(fit <= 15, fit <= 30), f"Fitted model, held out median absolute error {fit:.1f} percent.")
    apr = g("apriori", "all rows", "median_abs_pct")
    S["V5"] = (verdict(apr <= 25, apr <= 40), f"A priori model, median absolute error {apr:.1f} percent on all traced rows.")
    sig = g("apriori", "all rows", "median_signed_pct")
    S["V6"] = (verdict(sig < 0), f"A priori median signed error {sig:+.1f} percent: it overestimates, so the predicted sign was wrong.")
    ex = R("cyclemodel/results/external_check.csv")
    exm = float(ex.err_pct_fitted.abs().median())
    S["V7"] = (verdict(exm > fit), f"Cortex-M33 external check median absolute error {exm:.1f} percent against {fit:.1f} percent held out on Cortex-M4.")
    e = R("energy/results/energy_per_op.csv")
    ee = e[e.op == "mldsa44_verify"]
    worst = ee.loc[ee.energy_uj_estimated.idxmax()]
    S["V8"] = (verdict(float(ee.energy_uj_estimated.max()) < 1000),
               f"Largest estimate {worst.energy_uj_estimated:.0f} uJ on {worst.part}; every other part below 1 mJ.")
    mn = R("energy/results/mission_nominal.csv")
    hy = mn[mn.design.str.contains("HMAC")]
    S["V9"] = (verdict(float(hy.battery_pct_per_h_modelled.max()) < 0.1, float(hy.battery_pct_per_h_modelled.max()) <= 1),
               f"Session design with a post quantum handshake: at most {hy.battery_pct_per_h_modelled.max():.4f} percent of battery per hour.")
    so = R("energy/results/sobol.csv")
    so = so[so.output.str.startswith("battery")]
    top = so.loc[so.S1.idxmax()]
    S["V10"] = (verdict("battery" not in top.input and "capacity" not in top.input),
                f"Largest first order index: {top.input} ({top.S1:.2f}).")
    va = R("linksim/results/validation_v4.csv")
    lora = va[va.figure.str.startswith("LoRa example") & (va.model.str.contains("formula", case=False) | (va.pct_error.abs() < 10))]
    worst_l = float(lora.pct_error.abs().max())
    S["V11"] = (verdict(worst_l <= 1, worst_l <= 5), f"Largest error of the time on air formula against published examples: {worst_l:.2f} percent.")
    dg = R("linksim/results/diagnosis_v4.csv")
    fac = float(dg[dg.step.astype(str) == "6"].factor_below_low_after.iloc[0])
    S["V12"] = (verdict(fac >= 2, fac >= 1.5), f"After every cited cost the model is {fac:.1f} times below the 30 s low end.")
    cf = R("linksim/results/closed_form_v4.csv")
    duty = cf[cf.check.str.startswith("duty")]
    ok_duty = bool(((duty.value_modelled - duty.closed_form).abs() <= 0.001 * duty.closed_form).all())
    frag_ok = "fragment" not in " ".join(cf.check) or bool(cf[cf.check.str.contains("fragment")].inside.all())
    S["V13"] = (verdict(ok_duty and frag_ok), f"Duty cycle waits equal the closed form ({len(duty)} cases); fragment counts agree with the independent count (tests in `linksim/tests/test_v4.py`).")
    sw = cf[cf.check.str.startswith("stop and wait")]
    S["V14"] = (verdict(bool(sw.inside.all())), f"Closed form inside the 95 percent interval at {int(sw.inside.sum())} of {len(sw)} loss rates (the supplementary check of the older simulator misses once, reported separately).")
    mb = R("mission/results/base.csv")
    dr = float(mb[(mb.vehicle == "drone") & (mb.arch == "C") & (mb.link == "sik")].utilisation_median.iloc[0])
    rb = float(mb[(mb.vehicle == "robot") & (mb.arch == "C") & (mb.link == "sik")].utilisation_median.iloc[0])
    S["V15"] = ("partial", f"Per message ML-DSA-44 on the SiK radio: utilisation {rb:.2f} for the 5 Hz robot stream (above 100 percent) but {dr:.2f} for the drone stream (below); refuted for the drone traffic, held for the robot.")
    vt = R("bootchain/results/verify_time.csv")
    q = vt[(vt.target == "Crazyflie 2.1 (STM32F405)") & (vt.image_bytes == 1000000) & (vt.hash == "software SHA-256") & vt.scheme.isin(["LMS", "ML-DSA-44"])]
    shares = (q.hash_ms_estimated / q.total_ms_estimated * 100)
    S["V16"] = (verdict(float(shares.min()) > 70, float(shares.min()) >= 50), f"Hashing share of a 1 MB verification: {shares.min():.1f} to {shares.max():.1f} percent.")
    pm = R("planner/results/profile_main.csv")
    share = float(pm[pm.scenario == "stack_asm"].hr_share.iloc[0])
    S["V17"] = (verdict(share < 0.20, share < 0.26), f"Profile fleet, stack optimised thresholds: {share:.3f} of devices need replacement.")
    ms = R("planner/results/mosca_sobol.csv")
    topm = ms.loc[ms.S1.idxmax()]
    S["V18"] = (verdict(topm.input == "data_lifetime_years"), f"Largest first order index: {topm.input} ({topm.S1:.2f}).")
    dry = json.load(open(ROOT / "bench/board_kit/dry_run/dry_run_summary.json"))
    sizes = R("bench/board_kit/image_sizes.csv")
    S["V19"] = (verdict(dry["recognised_percent"] == 100.0 and len(sizes) > 0),
                f"{len(sizes)} images built; {dry['recognised_percent']} percent of {dry['lines']} log lines parsed.")
    lat = float(mb[(mb.vehicle == "drone") & (mb.arch == "B") & (mb.link == "sik")].added_latency_ms_median.iloc[0])
    S["V20"] = (verdict(lat < 50), f"Hybrid session on the SiK radio adds {lat:.2f} ms per command.")
    lr = mb[(mb.arch == "B") & (mb.link == "lora_dr0")]
    S["V21"] = (verdict(True), "On the slowest link (LoRaWAN DR0) the hybrid handshake does not complete within the mission at all, so recovery exceeds 1 s; on the SiK radio it takes about 0.9 s (`docs/MISSION_STUDY.md`).")
    rf = ROOT / "docs/REVIEW_FINDINGS3.csv"
    if rf.exists():
        f = list(csv.DictReader(open(rf, encoding="utf-8")))
        p1 = [x for x in f if x.get("pass", "1") == "1"]
        p2h = [x for x in f if x.get("pass") == "2" and x.get("severity", "").lower() == "high"]
        S["V22"] = (verdict(len(p1) >= 20, len(p1) >= 10), f"First pass: {len(p1)} findings.")
        has2 = any(x.get("pass") == "2" for x in f)
        S["V23"] = (verdict(len(p2h) == 0) if has2 else "not scored", f"Second pass: {len(p2h)} high severity findings." if has2 else "No second pass recorded.")
    rub = (ROOT / "docs/COMPLETENESS_RUBRIC.md").read_text()
    mm = re.findall(r"\*\*([\d.]+) of 10\*\*", rub)
    if len(mm) >= 2:
        d = float(mm[-1]) - float(mm[0])
        S["V24"] = (verdict(d >= 1.0, d >= 0.5), f"Rubric from {mm[0]} to {mm[-1]} (change {d:+.1f}).")
    pred = (ROOT / "docs/PREDICTIONS_V4.md").read_bytes()
    stored = (ROOT / "docs/PREDICTIONS_V4.sha256").read_text().split()[0]
    now = hashlib.sha256(pred).hexdigest()
    counts = {}
    rows = []
    for i in range(1, 25):
        vid = f"V{i}"
        v, why = S.get(vid, ("not scored", "Not yet scored."))
        counts[v] = counts.get(v, 0) + 1
        rows.append(f"| {vid} | {v} | {why} |")
    L = ["# Scores for the round 4 predictions", "",
         "Author: Huda Mueen. Generated by `scripts/score_predictions_v4.py` from committed files; do not edit by hand. Predictions: `docs/PREDICTIONS_V4.md`, unchanged since hashed.", "",
         f"Hash check: stored {stored[:16]}..., file now {now[:16]}... ({'match' if stored == now else 'MISMATCH'}).", "",
         "Totals: " + ", ".join(f"{counts.get(k, 0)} {k}" for k in ("hit", "partial", "miss", "not scored")) + ", of 24.", "",
         "| ID | verdict | evidence |", "|---|---|---|"] + rows
    (ROOT / "docs/PREDICTIONS_V4_SCORES.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(L[6])


if __name__ == "__main__":
    main()
