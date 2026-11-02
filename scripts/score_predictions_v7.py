#!/usr/bin/env python3
"""Score docs/PREDICTIONS_V7.md against its refutation clauses, recomputing every metric from committed result files.

Writes docs/PREDICTIONS_V7_SCORES.md and data/predictions_v7_scores.csv. The prediction file is never edited; its
hash is checked first. Verdicts: hit, between, miss, not scored. Where a clause reads two ways the less favourable
reading is used and named in the evidence:
  kB in R7.4 and R7.5 is read as 1000 B (the lower bound of "below" and of "above" is then the stricter one);
  "either core" in R7.4 and R7.5 is the larger of the two cores;
  "configurations flown in both rounds" in R7.17 are the configurations of the larger set that round 6 flew
  (Falcon-512 was not flown in round 6).
Author: Huda Mueen."""
import hashlib
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RTL = ROOT / "rtlsim" / "results"
S7 = ROOT / "sitl" / "results_r7"
LABEL = {**{f"R7.{i}": "RTL simulated" for i in range(1, 6)}, **{f"R7.{i}": "SITL measured" for i in range(6, 18)}}
LABEL["R7.10"] = "emulated"


def csv(path):
    return pd.read_csv(path) if path.exists() else None


def verdict(hit, miss):
    return "hit" if hit else ("miss" if miss else "between")


def score():
    S = {}
    ratios, fal = csv(RTL / "proto_falcon_ratios.csv"), csv(RTL / "proto_falcon.csv")

    def ratio(comp, core, op):
        r = ratios[(ratios.comparison == comp) & (ratios.core == core) & (ratios.operation == op)]
        return None if len(r) == 0 else r.iloc[0]
    if ratios is None or fal is None:
        for i in range(1, 6):
            S[f"R7.{i}"] = ("not scored", "rtlsim/results/proto_falcon*.csv not present.")
    else:
        r = ratio("Falcon-512 over ML-DSA-44 per command", "cv32e40p", "vehicle_verify_command")
        S["R7.1"] = (verdict(r.ratio <= 0.5, r.ratio > 1.0),
                     f"Falcon-512 over ML-DSA-44 verify cycles, CV32E40P: {r.ratio:.3f} (interval {r.ci95_low:.3f} to "
                     f"{r.ci95_high:.3f}).") if r is not None else ("not scored", "no CV32E40P ratio row.")
        r = ratio("Ibex over CV32E40P, Falcon-512", "ibex/cv32e40p", "vehicle_verify_command")
        S["R7.2"] = (verdict(1.0 <= r.ratio <= 2.0, r.ratio < 0.8 or r.ratio > 3.0),
                     f"Ibex over CV32E40P, Falcon-512 verify: {r.ratio:.3f}.") if r is not None else ("not scored", "no row.")
        r = ratio("Falcon-512 over ML-DSA-44 per command", "cv32e40p", "ground_sign_command")
        S["R7.3"] = (verdict(r.ratio >= 3, r.ratio < 1),
                     f"Falcon-512 over ML-DSA-44 sign cycles, CV32E40P: {r.ratio:.3f} (interval {r.ci95_low:.3f} to "
                     f"{r.ci95_high:.3f}).") if r is not None else ("not scored", "no row.")
        for rid, op, lo_b, hi_b in (("R7.4", "ground_sign_command", 100000, 150000),
                                    ("R7.5", "vehicle_verify_command", 8000, 16000)):
            g = fal[fal.operation == op]
            mx = int(g.peak_stack_bytes.max())
            S[rid] = (verdict(mx < lo_b, mx > hi_b),
                      f"Largest peak stack over both cores: {mx:,} B (kB read as 1000 B, the less favourable reading).")
    summ, pm = csv(S7 / "summary.csv"), csv(S7 / "paired_missed.csv")

    def sval(st, k, metric):
        if summ is None:
            return None
        r = summ[(summ.set == st) & (summ.config == k) & (summ.metric == metric)]
        return None if len(r) == 0 else r.iloc[0]

    def pval(st, x, y):
        if pm is None:
            return None
        r = pm[(pm.set == st) & (pm.config == x) & (pm.minus_config == y)]
        return None if len(r) == 0 else r.iloc[0]

    def ns(rid, what):
        S[rid] = ("not scored", f"{what} not present in sitl/results_r7/.")
    r = sval("falcon20", "pqsig_falcon", "added_latency_rt_ms")
    if r is None:
        ns("R7.6", "falcon20 added round trip")
    else:
        S["R7.6"] = (verdict(70 <= r.value <= 250, r.value < 40 or r.value > 400),
                     f"Median added round trip, Falcon-512 per command: {r.value:.1f} ms (interval {r.ci_lo:.1f} to {r.ci_hi:.1f}).")
    r = sval("falcon20", "pqsig_falcon", "availability_rt_all")
    if r is None:
        ns("R7.7", "falcon20 share")
    else:
        S["R7.7"] = (verdict(0.80 <= r.value <= 0.93, r.value < 0.60),
                     f"Share acknowledged within 0.5 s, Falcon-512 per command: {r.value:.3f} (interval {r.ci_lo:.3f} to {r.ci_hi:.3f}).")
    r = pval("falcon20", "pqsig_falcon", "pqsig_real")
    if r is None:
        ns("R7.8", "falcon20 paired difference")
    else:
        S["R7.8"] = (verdict(r.difference <= -12, r.difference > -5),
                     f"Missed per mission, Falcon-512 minus ML-DSA-44 per command: {r.difference:+.2f} (interval {r.ci_lo:+.2f} to {r.ci_hi:+.2f}).")
    r = pval("falcon20", "pqsig_falcon_counter", "pqsig_falcon")
    if r is None:
        ns("R7.9", "falcon20 counter difference")
    else:
        S["R7.9"] = (verdict(-1.5 <= r.difference <= 1.5, not (-3 <= r.difference <= 3)),
                     f"Missed per mission, Falcon-512 with counter minus without: {r.difference:+.2f} (interval {r.ci_lo:+.2f} to {r.ci_hi:+.2f}).")
    bl = csv(S7 / "burst_loss.csv")
    if bl is None:
        ns("R7.10", "burst_loss.csv")
    else:
        v = bl.burst_lost_frames.sum() / bl.frames.sum()
        S["R7.10"] = (verdict(0.015 <= v <= 0.025, v < 0.01 or v > 0.03),
                      f"Frames lost to the burst process over frames sent, pooled over {len(bl)} runs: {v:.4f} "
                      f"({int(bl.burst_lost_frames.sum()):,} of {int(bl.frames.sum()):,}; outage losses excluded from the numerator).")
    r = pval("burst20", "hybrid_strict", "hybrid_published")
    if r is None:
        ns("R7.11", "burst20 strict difference")
    else:
        S["R7.11"] = (verdict(r.difference > 0 and r.ci_lo > 0, r.difference <= 0),
                      f"Burst loss, strict rule with a new handshake minus published rule: {r.difference:+.2f} (interval {r.ci_lo:+.2f} to {r.ci_hi:+.2f}).")
    r = pval("burst20", "hybrid_cache", "hybrid_published")
    if r is None:
        ns("R7.12", "burst20 cache difference")
    else:
        S["R7.12"] = (verdict(abs(r.difference) <= 0.25, abs(r.difference) > 1),
                      f"Burst loss, replay cache minus published rule: {r.difference:+.2f} (interval {r.ci_lo:+.2f} to {r.ci_hi:+.2f}).")
    lc = csv(S7 / "loss_change.csv")
    r = None if lc is None else lc[(lc.config == "pqsig_real") & (lc.minus_config == "hybrid_published")]
    if r is None or len(r) == 0:
        ns("R7.13", "loss change difference")
    else:
        r = r.iloc[0]
        S["R7.13"] = (verdict(r.difference > 0, r.difference < -2),
                      f"Change from independent to burst loss, ML-DSA-44 per command minus hybrid published: {r.difference:+.2f} (interval {r.ci_lo:+.2f} to {r.ci_hi:+.2f}).")
    r = pval("large100", "hybrid_strict", "hybrid_published")
    if r is None:
        ns("R7.14", "large100 strict difference")
    else:
        S["R7.14"] = (verdict(0.95 <= r.difference <= 2.25 and r.ci_lo > 0,
                              not (0.4 <= r.difference <= 3.0) or r.ci_lo <= 0),
                      f"Larger set, strict rule with a new handshake minus published rule: {r.difference:+.2f} (interval {r.ci_lo:+.2f} to {r.ci_hi:+.2f}, {int(r.missions_paired)} missions).")
    r = pval("large100", "hybrid_strict_inband", "hybrid_published")
    if r is None:
        ns("R7.15", "large100 in session difference")
    else:
        S["R7.15"] = (verdict(0.40 <= r.difference <= 1.55 and r.ci_lo > 0, r.ci_lo <= 0),
                      f"Larger set, strict rule in session minus published rule: {r.difference:+.2f} (interval {r.ci_lo:+.2f} to {r.ci_hi:+.2f}, {int(r.missions_paired)} missions).")
    r = pval("large100", "hybrid_cache", "hybrid_published")
    if r is None:
        ns("R7.16", "large100 cache difference")
    else:
        S["R7.16"] = (verdict(abs(r.difference) <= 0.2, abs(r.difference) > 0.5),
                      f"Larger set, replay cache minus published rule: {r.difference:+.2f} (interval {r.ci_lo:+.2f} to {r.ci_hi:+.2f}).")
    rr = csv(S7 / "rerun_check.csv")
    if rr is None:
        ns("R7.17", "rerun_check.csv")
    else:
        g = rr[rr.reference == "round 6"]
        i = g.difference.abs().idxmax()
        v = abs(g.difference[i])
        S["R7.17"] = (verdict(v <= 1.0, v > 2.5),
                      f"Largest absolute difference of mean missed per mission, missions 0 to 19, larger set against round 6, over "
                      f"{len(g)} configurations: {v:.2f} ({g.config[i]}); Falcon-512, not flown in round 6, is left out.")
    return dict(sorted(S.items(), key=lambda kv: int(kv[0].split(".")[1])))


def main():
    S = score()
    stored = (ROOT / "docs/PREDICTIONS_V7.md.sha256").read_text().split()[0]
    now = hashlib.sha256((ROOT / "docs/PREDICTIONS_V7.md").read_bytes()).hexdigest()
    counts = {}
    for v, _ in S.values():
        counts[v] = counts.get(v, 0) + 1
    L = ["# Scores for the round 7 predictions", "",
         "Author: Huda Mueen. Generated by `scripts/score_predictions_v7.py` from committed files; do not edit by hand. "
         "Predictions: `docs/PREDICTIONS_V7.md`, unchanged since hashed.", "",
         f"Hash check: stored {stored[:16]}..., file now {now[:16]}... ({'match' if stored == now else 'MISMATCH'}).", "",
         "Verdicts: hit when the expectation holds; miss when the refutation clause is met; between when neither holds; "
         "not scored when the metric could not be computed as registered. When a metric reads two ways, the less "
         "favourable verdict is kept and named.", "",
         "Totals: " + ", ".join(f"{counts.get(k, 0)} {k}" for k in ("hit", "between", "miss", "not scored")) + f", of {len(S)}.", "",
         "| ID | verdict | evidence | label of the evidence |", "|---|---|---|---|"] + [
        f"| {k} | {v} | {e} | {LABEL[k]} |" for k, (v, e) in S.items()]
    (ROOT / "docs/PREDICTIONS_V7_SCORES.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    pd.DataFrame([{"id": k, "verdict": v, "evidence": e, "label": LABEL[k]} for k, (v, e) in S.items()]).to_csv(
        ROOT / "data/predictions_v7_scores.csv", index=False, lineterminator="\n")
    print(L[8])
    return 0 if stored == now else 1


if __name__ == "__main__":
    sys.exit(main())
