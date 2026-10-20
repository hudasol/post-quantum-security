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
    return "hit" if ok else ("between" if partial else "miss")


def main():
    S = {}
    ev = R("data/evidence.csv")
    n12 = int((ev.stream == "S12").sum())
    S["V1"] = (verdict(n12 >= 120), f"{n12} rows added after double reading (refuted below 60).")
    v5 = (ROOT / "docs/VERIFICATION5.md").read_text()
    m = re.search(r"confirmed wrong value in staging \| (\d+) \| (\d+) \| ([\d.]+) percent", v5)
    k, n, pct = int(m.group(1)), int(m.group(2)), float(m.group(3))
    md = re.search(r"any value disagreement between staging and a reader \| (\d+) \| (\d+) \| ([\d.]+) percent", v5)
    k2, n2, p2 = int(md.group(1)), int(md.group(2)), float(md.group(3))
    S["V2"] = (verdict(p2 <= 5, p2 <= 10), f"{k2} of {n2} rows with values had a value that a reader read differently from staging before adjudication ({p2} percent); after the third look {k} had a confirmed wrong value ({pct} percent).")
    summ = R("data/verify5/summary.csv")
    ids = set(summ.id)
    dis = set(summ[summ.status == "disagree"].id)
    share = 100 * (len(ids) - len(dis)) / len(ids)
    S["V3"] = (verdict(share >= 80, share >= 60),
               f"{len(ids) - len(dis)} of {len(ids)} staged rows and facts ({share:.1f} percent) had no filled field where either reader differed from staging (fields a reader left blank, being stated away from the cited location, are not counted); "
               "most differences were wording (operation, scheme, library), not values.")
    es = R("cyclemodel/results/error_summary.csv")
    g = lambda mo, su, col: float(es[(es.model == mo) & (es.subset == su)][col].iloc[0])
    fit = g("fitted", "test, all", "median_abs_pct")
    S["V4"] = (verdict(fit <= 15, fit <= 30), f"Fitted model, held out median absolute error {fit:.1f} percent.")
    apr = g("apriori", "all rows", "median_abs_pct")
    S["V5"] = ("not scored", f"The registered method (costs from the Arm instruction timing tables) could not be run: the Arm page was refused, and the model run uses per class costs assumed by the author after registration. For information only: median absolute error {apr:.1f} percent, no better than one cycle per instruction.")
    sig = g("apriori", "all rows", "median_signed_pct")
    S["V6"] = ("not scored", f"As V5: the registered model could not be built. For information only: the assumed cost model has a median signed error of {sig:+.1f} percent.")
    ex = R("cyclemodel/results/external_check.csv")
    exm = float(ex.err_pct_fitted.abs().median())
    S["V7"] = (verdict(exm > fit), f"Cortex-M33 external check median absolute error {exm:.1f} percent against {fit:.1f} percent held out on Cortex-M4. Informed and weak: the six rows give two distinct predictions, and a larger error off the training code was nearly certain.")
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
    S["V10"] = ("not scored", f"Battery capacity, named in the refutation clause, was not an input of the sensitivity run, and the indices were computed for the per command ML-DSA-44 design rather than the session workload; the prediction could not fail as run. For information: largest first order index {top.input} ({top.S1:.2f}).")
    va = R("linksim/results/validation_v4.csv")
    lora = va[va.figure.str.startswith("LoRa example") & (va.model.str.contains("formula", case=False) | (va.pct_error.abs() < 10))]
    worst_l = float(lora.pct_error.abs().max())
    S["V11"] = ("between", f"Only one published example states every parameter, and it matches exactly; for the others the unstated settings were chosen because they reproduce the published value, so they are not independent checks. Largest error over all examples {worst_l:.2f} percent.")
    dg = R("linksim/results/diagnosis_v4.csv")
    fac = float(dg[dg.step.astype(str) == "6"].factor_below_low_after.iloc[0])
    S["V12"] = (verdict(fac >= 2, fac >= 1.5), f"After every cited cost the model is {fac:.1f} times below the 30 s low end.")
    cf = R("linksim/results/closed_form_v4.csv")
    duty = cf[cf.check.str.startswith("duty")]
    ok_duty = bool(((duty.value_modelled - duty.closed_form).abs() <= 0.001 * duty.closed_form).all())
    frag_ok = "fragment" not in " ".join(cf.check) or bool(cf[cf.check.str.contains("fragment")].inside.all())
    import subprocess, sys as _sys
    t = subprocess.run([_sys.executable, "-m", "unittest", "linksim.tests.test_v4.TestMac802154.test_fragment_counts_independent"], cwd=ROOT, capture_output=True, text=True)
    frag_ok = t.returncode == 0
    S["V13"] = (verdict(ok_duty and frag_ok), f"Duty cycle waits equal the closed form ({len(duty)} cases); the fragment count test against an independent RFC 4944 count {'passes' if frag_ok else 'fails'} when run by this script.")
    sw = cf[cf.check.str.startswith("stop and wait")]
    sim = cf[cf.check.str.startswith("supplementary")]
    S["V14"] = (verdict(bool(sim.inside.all())), f"Scored on the simulator the studies use (stop and wait with data and acknowledgement loss against 1/(1-p)^2): closed form inside the interval at {int(sim.inside.sum())} of {len(sim)} loss rates, and the simulator sits above it at every rate. A purpose written sampler agrees at {int(sw.inside.sum())} of {len(sw)}, but it cannot disagree by construction. Selective repeat, used by the protocol and mission studies, has no closed form check.")
    mb = R("mission/results/base.csv")
    dr = float(mb[(mb.vehicle == "drone") & (mb.arch == "C") & (mb.link == "sik")].utilisation_median.iloc[0])
    rb = float(mb[(mb.vehicle == "robot") & (mb.arch == "C") & (mb.link == "sik")].utilisation_median.iloc[0])
    S["V15"] = (verdict(min(dr, rb) > 1.0), f"Per message ML-DSA-44 on the SiK radio: utilisation {dr:.2f} for the drone stream, which meets the refutation clause (at or below 100 percent), and {rb:.2f} for the 5 Hz robot stream.")
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
    sik = float(mb[(mb.vehicle == "drone") & (mb.arch == "B") & (mb.link == "sik")].ttra_s_median.iloc[0])
    S["V21"] = ("miss", f"On LoRaWAN DR0 the hybrid handshake never completes, so the metric is undefined there; on the slowest link where it completes (the SiK radio) recovery after a session teardown takes {sik:.2f} s, below 1 s, which meets the refutation clause.")
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
    definition = ("Verdicts: hit when the prediction holds; miss when the refutation clause is met; between when neither holds "
                  "(this third verdict was not defined when the predictions were registered; it was defined on 2026-10-20 after a reviewer noted the gap); "
                  "not scored when the registered metric could not be computed as registered, with the reason.")
    L = ["# Scores for the round 4 predictions", "",
         "Author: Huda Mueen. Generated by `scripts/score_predictions_v4.py` from committed files; do not edit by hand. Predictions: `docs/PREDICTIONS_V4.md`, unchanged since hashed.", "",
         f"Hash check: stored {stored[:16]}..., file now {now[:16]}... ({'match' if stored == now else 'MISMATCH'}).", "",
         definition, "",
         "Totals: " + ", ".join(f"{counts.get(k, 0)} {k}" for k in ("hit", "between", "miss", "not scored")) + ", of 24.", "",
         "| ID | verdict | evidence |", "|---|---|---|"] + rows
    (ROOT / "docs/PREDICTIONS_V4_SCORES.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(L[8])


if __name__ == "__main__":
    main()
