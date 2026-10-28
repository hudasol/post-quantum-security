#!/usr/bin/env python3
"""Score the round 6 predictions (docs/PREDICTIONS_V6.md) from the committed result files.

Each prediction is scored against its refutation clause as registered. Verdicts: hit, miss, between (neither the
expectation nor the refutation clause holds), not scored (metric not computable as registered). When a metric can be
read two ways, both are computed and the less favourable verdict is kept. Writes docs/PREDICTIONS_V6_SCORES.md.
"""
import hashlib
import subprocess
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ORDER = {"hit": 0, "between": 1, "miss": 2}


def verdict(hit, not_refuted):
    return "hit" if hit else ("between" if not_refuted else "miss")


def worst(vs):
    return max(vs, key=lambda v: ORDER[v])


def R(p):
    return pd.read_csv(ROOT / p)


def score():
    S = {}
    ses, prim, sizes = R("rtlsim/results/proto_sessions.csv"), R("rtlsim/results/proto_primitives.csv"), R("rtlsim/results/proto_sizes.csv")

    def cyc(core, d, side, unit="session start"):
        return float(ses[(ses.core == core) & (ses.design == d) & (ses.side == side) & (ses.unit == unit)].cycles_median.iloc[0])

    def op(core, o):
        return float(prim[(prim.core == core) & (prim.operation == o)].cycles_median.iloc[0])
    r1 = op("cv32e40p", "x25519_shared") / op("cv32e40p", "mlkem768_encaps")
    S["Q1"] = (verdict(r1 >= 1, r1 >= 0.5), f"X25519 shared secret over ML-KEM-768 encaps on CV32E40P: {r1:.2f}.")
    h = cyc("cv32e40p", "hybrid_f1", "vehicle")
    S["Q2"] = (verdict(12e6 <= h <= 35e6, 6e6 <= h <= 70e6), f"Vehicle side hybrid handshake on CV32E40P: {h:,.0f} cycles.")
    r3 = h / cyc("cv32e40p", "classical", "vehicle")
    S["Q3"] = (verdict(r3 <= 4, r3 <= 8), f"Hybrid over classical, vehicle side, CV32E40P: {r3:.2f}.")
    r4 = cyc("ibex", "hybrid_f1", "vehicle") / h
    S["Q4"] = (verdict(1.2 <= r4 <= 1.6, 1.0 <= r4 <= 2.0), f"Ibex over CV32E40P, vehicle side hybrid: {r4:.2f}.")
    tags = [cyc("cv32e40p", "mavlink_tag", side, "per message, tag alone, 60 B frame") for side in ("vehicle", "ground")]
    t = max(tags)
    S["Q5"] = (verdict(t < 20e3, t <= 100e3), f"MAVLink 2 signing tag over a 60 B frame on CV32E40P: generation {tags[1]:,.0f}, check {tags[0]:,.0f} cycles; the larger is scored.")
    st = float(ses[(ses.design == "hybrid_f1") & (ses.side == "vehicle") & (ses.unit == "session start")].peak_stack_bytes.max())
    S["Q6"] = (verdict(st < 100e3, st <= 150e3), f"Peak stack of the vehicle side hybrid handshake (larger of the two cores): {st:,.0f} B.")
    vs, txt = [], []
    for variant in ("timing", "gc"):
        z = sizes[(sizes.core == "ibex") & (sizes.variant == variant)]
        r7 = float(z[z.image == "hybrid_f1"].text_bytes.iloc[0]) / float(z[z.image == "classical"].text_bytes.iloc[0])
        vs.append(verdict(r7 >= 2, r7 >= 1.2))
        txt.append(f"{variant} build {r7:.2f}")
    S["Q7"] = (worst(vs), "Hybrid over classical text size, Ibex: " + "; ".join(txt) + ". The less favourable reading is kept.")
    sm = R("sitl/results_r6/summary.csv")
    hs = float(sm[(sm.profile == "sik") & (sm.config == "hybrid_published") & (sm.metric == "handshake_median_s")].value.iloc[0])
    dev = hs / 1.28 - 1
    S["Q8"] = (verdict(abs(dev) <= 0.30, abs(dev) <= 0.50), f"Hybrid handshake with executed cryptography {hs:.3f} s against 1.28 s registered ({100 * dev:+.1f} percent).")
    pr = R("sitl/results_r6/paired.csv")

    def pdiff(a, b):
        return float(pr[(pr.profile == "sik") & (pr.config == a) & (pr.minus_config == b) & (pr.metric == "availability_rt_all")].difference.iloc[0])
    d9 = -pdiff("hybrid_strict", "hybrid_published")
    S["Q9"] = (verdict(d9 <= 0.05, d9 <= 0.10), f"Drop of the acknowledged share, strict against published, paired: {d9:.4f}.")
    d10 = abs(pdiff("hybrid_cache", "hybrid_published"))
    S["Q10"] = (verdict(d10 <= 0.02, d10 <= 0.05), f"Absolute difference, replay cache against published, paired: {d10:.4f}.")
    mb = R("mission/results/replay_base.csv")
    d11 = -float(mb[(mb.vehicle == "drone") & (mb.arch == "B") & (mb.link == "sik") & (mb.tag == "base") & (mb.replay_rule == "strict")].diff_vs_published_mean.iloc[0])
    S["Q11"] = (verdict(d11 <= 0.02, d11 <= 0.05), f"Mission model drop, strict against published, drone, SiK, B: {d11:.4f}.")
    pv = R("formal/results/proverif_results.csv")
    # The registered metric names "a seen counter table". Three encodings exist: a restriction that makes check and
    # insert one step (proved), a ProVerif table read sequentially (cannot be proved) and a table read by concurrent
    # branches (counterexample). The less favourable reading counts all of them.
    enc = ["session_replay_cache", "session_replay_cache_fresh_counters", "session_replay_cache_table_sequential",
           "session_replay_cache_table_concurrent"]
    c1 = pv[(pv.model.isin(enc)) & (pv.property_id == "C1")]
    per = [("hit" if r == "proved" else ("miss" if r == "counterexample" else "between")) for r in c1.result]
    S["Q12"] = (worst(per), "Injective agreement (C1) per encoding of the seen counter table: " + "; ".join(c1.model + " " + c1.result)
                + ". Check and insert as one step is proved; a table that concurrent branches read before either inserts gives a counterexample, so the cache must check and record atomically. The less favourable reading is kept.")
    sc = R("data/raw/S14_screening.csv")
    n1 = int((sc.seen_round5_screening == "no").sum())
    n2 = int((sc.new_record == "yes").sum())
    S["Q13"] = (worst([verdict(n1 >= 5, n1 > 0), verdict(n2 >= 5, n2 > 0)]),
                f"Records passing title screening not seen in round 5: {n1}; also new to the repository: {n2}. The index was reached through a web search limited to dblp.org, not its API (refused).")
    pdf = ROOT / "docs/conference/paper.pdf"
    if pdf.exists():
        out = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True).stdout
        pages = int([l for l in out.splitlines() if l.startswith("Pages:")][0].split()[1])
        S["Q14"] = (verdict(pages <= 6, pages <= 7), f"Compiled paper: {pages} pages including references (the less favourable reading of 'without references').")
    else:
        S["Q14"] = ("not scored", "docs/conference/paper.pdf not built.")
    return S


def main():
    S = score()
    stored = (ROOT / "docs/PREDICTIONS_V6.md.sha256").read_text().split()[0]
    now = hashlib.sha256((ROOT / "docs/PREDICTIONS_V6.md").read_bytes()).hexdigest()
    counts = {}
    for v, _ in S.values():
        counts[v] = counts.get(v, 0) + 1
    L = ["# Scores for the round 6 predictions", "",
         "Author: Huda Mueen. Generated by `scripts/score_predictions_v6.py` from committed files; do not edit by hand. Predictions: `docs/PREDICTIONS_V6.md`, unchanged since hashed.", "",
         f"Hash check: stored {stored[:16]}..., file now {now[:16]}... ({'match' if stored == now else 'MISMATCH'}).", "",
         "Verdicts: hit when the expectation holds; miss when the refutation clause is met; between when neither holds; not scored when the metric could not be computed as registered. When a metric reads two ways, the less favourable verdict is kept and named.", "",
         "Totals: " + ", ".join(f"{counts.get(k, 0)} {k}" for k in ("hit", "between", "miss", "not scored")) + f", of {len(S)}.", "",
         "| ID | verdict | evidence |", "|---|---|---|"] + [f"| {k} | {v} | {e} |" for k, (v, e) in S.items()]
    (ROOT / "docs/PREDICTIONS_V6_SCORES.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    pd.DataFrame([{"id": k, "verdict": v, "evidence": e, "label": "host measured"} for k, (v, e) in S.items()]).to_csv(
        ROOT / "data/predictions_v6_scores.csv", index=False, lineterminator="\n")
    print(L[8])


if __name__ == "__main__":
    main()
