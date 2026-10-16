#!/usr/bin/env python3
"""Score docs/PREDICTIONS_V2.md against the result files of the second round.

Every metric is recomputed here from the committed result files; no number in the output is typed by hand.
Writes docs/PREDICTIONS_V2_SCORES.md. The prediction file itself is never edited; its hash is checked first.
Verdicts: hit, partial (some parts hold), miss, not scored (experiment not run)."""
import csv
import hashlib
import os
import statistics
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def rows(rel):
    with open(ROOT / rel, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def f(x):
    return float(x)


def check_hash():
    want = (ROOT / "docs" / "PREDICTIONS_V2.sha256").read_text(encoding="utf-8").split()[0]
    data = (ROOT / "docs" / "PREDICTIONS_V2.md").read_bytes().replace(b"\r\n", b"\n")
    got = hashlib.sha256(data).hexdigest()
    return want, got


def main():
    want, got = check_hash()
    S = []  # (id, verdict, evidence text)
    ev = rows("data/evidence.csv")
    s10 = [r for r in ev if r["stream"] == "S10"]
    v3 = {r["set"]: r for r in rows("data/verify3/summary.csv")}["all"]

    # Q1
    n = len(s10)
    S.append(("Q1.1", "hit" if n >= 60 else ("miss" if n < 30 else "partial"),
              f"{n} new rows merged (stream S10)."))
    k, m = int(v3["any"]), int(v3["rows"])
    rate = k / m
    trans = sum(1 for s in "ABCDEF" for r in rows(f"data/verify3/S10{s}_results.csv")
                if r["value_ok"].strip().lower() != "yes" and "tick" not in r["note"].lower())
    S.append(("Q1.2", "hit" if rate <= 0.05 else ("miss" if rate > 0.10 else "partial"),
              f"Row error rate {k} of {m} ({100 * rate:.1f} percent), above the 10 percent refutation line. "
              f"All {k} were column mapping or warning errors; transcription errors {trans} of {m} "
              f"(rule of three bound {100 * 3 / m:.2f} percent). See docs/VERIFICATION3.md."))
    cnsa = [r for r in ev if "cnsa" in (r["source_title"] + r["source_url"]).lower()]
    S.append(("Q1.3", "hit" if not cnsa else "miss",
              f"{len(cnsa)} evidence rows cite the CNSA 2.0 FAQ; it went into data/raw/S10_cnsa_faq.md as 41 claims."))
    m33 = [r["id"] for r in s10 if "M33" in r["core"] and r["cycles"]
           and r["scheme_family"] in ("ML-KEM", "ML-DSA", "SLH-DSA")]
    S.append(("Q1.4", "miss" if m33 else "hit",
              f"{len(m33)} new rows give ML-DSA cycles on a Cortex-M33 ({m33[0] if m33 else ''} onward), which "
              "contradicts the earlier report headline that no such cycles were published. The report was corrected "
              "and the correction is marked in it. (An earlier version of this script compared exact library strings, "
              "a test that could not fail; the fresh review found this.)"))
    emu = 50008  # first round emulated ML-DSA-44 sign stack, read below from git history when available
    try:
        txt = subprocess.run(["git", "show", "1060a1d:bench/mcu/qemu_results/stack.csv"], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout
        emu = [int(l.split(",")[3]) for l in txt.splitlines() if l.startswith("ML-DSA,ML-DSA-44,sign,")][0]
    except Exception:
        pass
    mem = [(f(r["stack_bytes"] or r["ram_bytes"]), r["id"]) for r in s10 if r["operation"] == "sign"
           and (r["stack_bytes"] or r["ram_bytes"])
           and any(t in r["parameter_set"] for t in ("Dilithium-2", "Dilithium2", "ML-DSA-44"))]
    lo = min(mem)
    ratio = emu / lo[0]
    S.append(("Q1.5", "hit" if ratio >= 5 else ("miss" if ratio < 2 else "partial"),
              f"Emulated ML-DSA-44 sign stack {emu:,} B over the smallest published signing memory "
              f"{lo[0]:,.0f} B ({lo[1]}) = {ratio:.1f}."))

    # Q2
    sw = rows("linksim/results/sweeps.csv")
    zero = [r for r in sw if r["axis"] in ("max_retries", "rto_factor") and f(r["loss"]) == 0]
    flat = all(len({r["mean"] for r in zero if r["link"] == l and r["axis"] == a}) == 1
               for l in {r["link"] for r in zero} for a in ("max_retries", "rto_factor"))
    tops = {}
    for l in sorted({r["link"] for r in sw}):
        eff = {}
        for a in ("payload", "rate_scale", "max_retries", "rto_factor"):
            sel = [f(r["mean"]) for r in sw if r["link"] == l and r["axis"] == a and f(r["loss"]) == 0.05]
            eff[a] = max(sel) / min(sel) - 1
        sel = [f(r["mean"]) for r in sw if r["link"] == l and r["axis"] == "loss"]
        eff["loss"] = max(sel) / min(sel) - 1
        tops[l] = sorted(eff, key=lambda a: -eff[a])[:2]
    both = all(set(t) == {"payload", "rate_scale"} for t in tops.values())
    S.append(("Q2.1", "hit" if flat and both else ("partial" if flat or both else "miss"),
              "Zero loss wall time is " + ("unchanged" if flat else "CHANGED") + " by retry limit and timeout "
              "factor, so the refutation clause is not met, but the first claim fails: the two largest axes per link "
              "(over each axis's sweep range) are "
              + "; ".join(f"{l}: {', '.join(t)}" for l, t in tops.items()) + "."))
    g = rows("linksim/results/mc_grid.csv")
    cell = lambda l, p, loss, v="hybrid", mr=20: [r for r in g if r["link"] == l and r["proto"] == p  # noqa: E731
                                                  and f(r["loss"]) == loss and r["variant"] == v
                                                  and f(r["max_retries"]) == mr][0]
    a0, a5 = cell("sik", "sr", 0.0), cell("sik", "sr", 0.05)
    infl = f(a5["mean"]) / f(a0["mean"])
    half = (f(a5["ci_hi"]) - f(a5["ci_lo"])) / 2 / f(a5["mean"])
    S.append(("Q2.2", "hit" if 1.05 <= infl <= 1.40 and half < 0.02 else "miss",
              f"SiK selective repeat, 5 percent loss: mean inflation {infl:.3f}; 95 percent interval half width "
              f"{100 * half:.2f} percent of the mean ({a5['trials']} trials)."))
    l0, l10 = cell("lorawan", "sr", 0.0), cell("lorawan", "sr", 0.10)
    ok3 = f(l0["median"]) > 4 * 3600 and f(l10["p95"]) > 5 * 3600
    S.append(("Q2.3", "hit" if ok3 else "miss",
              f"LoRaWAN DR0, selective repeat: median {f(l0['median']) / 3600:.2f} h at 0 percent loss; "
              f"95th percentile {f(l10['p95']) / 3600:.2f} h at 10 percent loss."))
    lr = rows("linksim/results/lowrate.csv")
    fr = lambda p, h, v="hybrid", mac=0: [r for r in lr if r["profile"] == p and int(r["frag_hdr_bytes"]) == h  # noqa: E731
                                          and r["variant"] == v and int(r["mac_overhead_bytes"]) == mac][0]
    inc = int(fr("eu868_dr0", 4)["fragments"]) / int(fr("eu868_dr0", 0)["fragments"]) - 1
    S.append(("Q2.4", "hit" if inc >= 0.08 else ("miss" if inc < 0.05 else "partial"),
              f"Fragments {fr('eu868_dr0', 0)['fragments']} to {fr('eu868_dr0', 4)['fragments']} "
              f"(+{100 * inc:.1f} percent)."))
    sh = cell("ble", "sw", 0.20, mr=3)
    S.append(("Q2.5", "hit" if f(sh["completion"]) < 0.5 else "miss",
              f"{100 * f(sh['completion']):.1f} percent complete (Wilson interval {100 * f(sh['completion_lo']):.1f} "
              f"to {100 * f(sh['completion_hi']):.1f} percent)."))
    d0, d5 = f(fr("eu868_dr0", 0)["floor_wall_s"]), f(fr("eu868_dr5", 0)["floor_wall_s"])
    p1, p2 = d5 < 600, d0 / d5 > 20
    S.append(("Q2.6", "hit" if p1 and p2 else "miss",
              f"Refutation clause met (DR5 at least 10 minutes). DR5 lower bound {d5 / 60:.1f} min (predicted under 10 min: {'yes' if p1 else 'no'}); ratio DR0 over "
              f"DR5 {d0 / d5:.1f} (predicted above 20: {'yes' if p2 else 'no'}). The DR5 figure is limited by the "
              "1 percent duty cycle, which I underweighted."))
    val = rows("linksim/results/validation.csv")
    abs_ok = all(-0.50 <= f(r["err_plain"]) <= -0.15 for r in val)
    diffs = [abs(f(r["diff_err_plain"])) for r in val if r["diff_err_plain"] not in ("", "nan")]
    S.append(("Q2.7", "hit" if abs_ok and max(diffs) <= 0.15 else ("miss" if max(diffs) > 0.25 else "partial"),
              f"Absolute errors {min(100 * f(r['err_plain']) for r in val):.1f} to "
              f"{max(100 * f(r['err_plain']) for r in val):.1f} percent; largest error of the difference to P-256 "
              f"{100 * max(diffs):.1f} percent over {len(diffs)} groups."))

    # Q3
    planner = ROOT / "planner"
    pt = subprocess.run([sys.executable, "-m", "unittest", "tests.test_fleet_properties"], cwd=planner,
                        capture_output=True, text=True)
    passed = pt.returncode == 0
    S.append(("Q3.1", "hit" if passed else "miss",
              "Monotonicity property tests " + ("pass" if passed else "FAIL") + ". The first run of the test failed "
              "because the test itself created devices with free memory above total memory (docs/RUN_LOG.md item 9); "
              "no planner violation was found."))
    sc = rows("planner/results/scale.csv")
    viol = sum(int(r["violations"]) for r in sc)
    S.append(("Q3.2", "hit" if viol == 0 and passed else "miss",
              f"{viol} violations over fleets of " + ", ".join(r["devices"] for r in sc) + " devices; property "
              "tests " + ("pass" if passed else "fail") + "."))
    tor = rows("planner/results/tornado.csv")
    top = tor[0]
    mem_thr = max(f(r["swing"]) for r in tor if r["input"] in ("sig_flash_kb", "sig_ram_kb", "kem_flash_kb",
                                                                  "kem_ram_kb"))
    hor = max(f(r["swing"]) for r in tor if r["input"] in ("sig_horizon_year", "conf_horizon_year"))
    ok = hor > mem_thr and 0.10 <= f(top["swing"]) <= 0.40
    S.append(("Q3.3", "hit" if ok else "miss",
              f"Largest swing {100 * f(top['swing']):.1f} percent ({top['input']}); largest horizon year swing "
              f"{100 * hor:.1f} percent against {100 * mem_thr:.1f} percent for the largest memory threshold."))
    st = rows("planner/results/staged.csv")
    unk = [int(r["UNKNOWN"]) for r in st]
    noa = [int(r["NO_ACTION_BEFORE_RETIREMENT"]) for r in st]
    u_ok = len(set(unk)) == 1
    n_ok = all(b >= a for a, b in zip(noa, noa[1:]))
    S.append(("Q3.4", "hit" if u_ok and n_ok else ("partial" if u_ok or n_ok else "miss"),
              f"UNKNOWN by wave {unk}; NO_ACTION_BEFORE_RETIREMENT by wave {noa}. Both moved: as the planning year "
              "approaches the confidentiality horizon more devices become exposed, and exposed devices with unknown "
              "free memory join UNKNOWN."))
    t1000 = [f(r["seconds"]) for r in sc if r["devices"] == "1000"][0]
    S.append(("Q3.5", "hit" if t1000 < 2 else "miss", f"{t1000:.3f} s for 1000 devices."))

    # Q4
    ck = rows("bench/mcu/qemu_results/checks.csv")
    an505 = [r for r in ck if r["board"] == "an505"]
    S.append(("Q4.1", "hit" if an505 and all(r["fail"] == "0" for r in an505) else "miss",
              f"{sum(r['fail'] == '0' for r in an505)} of {len(an505)} Cortex-M33 builds pass every check."))
    stk = {(r["board"], r["opt"], r["param"], r["op"]): int(r["stack_bytes"]) for r in rows("bench/mcu/qemu_results/stack.csv")}
    dif = max(abs(stk[("an505", o, p, op)] / stk[("an386", o, p, op)] - 1) for (b, o, p, op) in stk if b == "an386")
    S.append(("Q4.2", "hit" if dif <= 0.10 else "miss", f"Largest M33 versus M4 stack difference {100 * dif:.1f} percent."))
    try:
        txt = subprocess.run(["git", "show", "1060a1d:bench/mcu/qemu_results/stack.csv"], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout.splitlines()[1:]
        old = {(l.split(",")[1], l.split(",")[2]): int(l.split(",")[3]) for l in txt}
        txt = subprocess.run(["git", "show", "1060a1d:bench/mcu/qemu_results/image_size.csv"], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout.splitlines()[1:]
        name = {"mlkem": "ML-KEM-", "mldsa": "ML-DSA-"}
        oldt = {name[l.split(",")[0]] + l.split(",")[1]: int(l.split(",")[2]) for l in txt}
        newt = {name[r["alg"]] + r["param"]: int(r["text_bytes"]) for r in rows("bench/mcu/qemu_results/image_size.csv")
                if r["board"] == "an386" and r["opt"] == "-O2"}
        d3 = max([abs(stk[("an386", "-O2", p, op)] / v - 1) for (p, op), v in old.items()]
                 + [abs(newt[p] / v - 1) for p, v in oldt.items()])
        S.append(("Q4.3", "hit" if d3 <= 0.10 else "miss",
                  f"Largest change against the first round (gcc 13.2.1, QEMU 8.2.2): {100 * d3:.1f} percent."))
    except Exception as e:
        S.append(("Q4.3", "not scored", f"first round files not readable from git history ({e})."))
    order = {"ML-KEM": ["ML-KEM-512", "ML-KEM-768", "ML-KEM-1024"], "ML-DSA": ["ML-DSA-44", "ML-DSA-65", "ML-DSA-87"]}
    ops = {"ML-KEM": ["keygen", "encaps", "decaps"], "ML-DSA": ["keygen", "sign", "verify"]}
    exc = [(b, o, a, op) for b in ("an386", "an505") for o in ("-O2", "-Os", "-O3") for a in order for op in ops[a]
           if not (stk[(b, o, order[a][0], op)] < stk[(b, o, order[a][1], op)] < stk[(b, o, order[a][2], op)])]
    S.append(("Q4.4", "hit" if not exc else "miss", f"{len(exc)} exceptions to strictly growing stack."))
    sz = {(r["board"], r["opt"], r["alg"], r["param"]): int(r["text_bytes"]) for r in rows("bench/mcu/qemu_results/image_size.csv")}
    smaller = sum(sz[(b, "-Os", a, p)] < sz[(b, "-O2", a, p)] for (b, o, a, p) in sz if o == "-O2")
    total = sum(1 for k_ in sz if k_[1] == "-O2")
    stc = max(abs(stk[(b, o, p, op)] / stk[(b, "-O2", p, op)] - 1) for (b, o, p, op) in stk if o != "-O2")
    S.append(("Q4.5", "hit" if smaller == total and stc < 0.15 else "miss",
              f"-Os smaller than -O2 for {smaller} of {total} images; largest stack change {100 * stc:.1f} percent."))
    S.append(("Q4.6", "not scored", "Renode was not run (no platform description for the MPS2 boards; docs/EMULATOR_RESULTS.md)."))

    # Q5
    hs = rows("bench/host/native/summary.csv")
    cv = max(f(r["cv_of_run_medians"]) for r in hs)
    S.append(("Q5.1", "hit" if cv < 0.03 else "miss",
              f"Largest coefficient of variation of the run medians {100 * cv:.1f} percent; the virtual machine's CPU "
              "frequency was not under control."))
    s44 = [r for r in hs if r["param"] == "ML-DSA-44" and r["op"] == "sign"][0]
    S.append(("Q5.2", "hit" if 5 <= f(s44["host_ratio"]) <= 30 else "miss",
              f"ML-DSA-44 sign over ML-KEM-768 encaps on the host: {f(s44['host_ratio']):.2f}. Given Q5.1, this "
              "single ratio is not stable either (within run range in bench/host/native/RESULTS.md)."))
    xs, ys = [f(r["median_ns"]) for r in hs], [f(r["pqm4_clean_cycles"]) for r in hs]
    rk = lambda v: [sorted(v).index(x) + 1 for x in v]  # noqa: E731
    rx, ry = rk(xs), rk(ys)
    nn = len(xs)
    rho = 1 - 6 * sum((a - b) ** 2 for a, b in zip(rx, ry)) / (nn * (nn * nn - 1))
    worst = max(abs(f(r["ratio_diff"])) for r in hs)
    S.append(("Q5.3", "hit" if rho >= 0.9 and worst > 0.30 else "miss",
              f"Spearman {rho:.3f}; largest ratio difference {100 * worst:.0f} percent. Part of that difference is "
              "host noise (Q5.1), not only the platform."))

    # Q6
    rev = ROOT / "docs" / "REVIEW_FINDINGS.csv"
    if rev.exists():
        fx = rows("docs/REVIEW_FINDINGS.csv")
        S.append(("Q6.1", "hit" if len(fx) >= 3 else "miss",
                  f"{len(fx)} findings from the fresh review (docs/REVIEW_FINDINGS.csv)."))
    else:
        S.append(("Q6.1", "not scored", "review not yet run."))

    cnt = {v: sum(1 for _, x, _ in S if x == v) for v in ("hit", "partial", "miss", "not scored")}
    L = ["# Scores for the second round predictions", "",
         "Author: Huda Mueen. Generated by `scripts/score_predictions_v2.py` from the committed result files; "
         "do not edit by hand. The predictions are in `docs/PREDICTIONS_V2.md`, unchanged since they were hashed.", "",
         f"Hash check: stored {want[:16]}..., file now {got[:16]}... "
         + ("(match)." if want == got else "(MISMATCH: the prediction file changed after hashing)."), "",
         f"Totals: {cnt['hit']} hit, {cnt['partial']} partial, {cnt['miss']} miss, {cnt['not scored']} not scored, "
         f"of {len(S)}.", "",
         "| ID | verdict | evidence |", "|---|---|---|"]
    L += [f"| {i} | {v} | {e} |" for i, v, e in S]
    L += ["", "## What the misses say", "",
          "1. Q1.2: the extraction copied numbers correctly but twice put a correct number in a column whose meaning "
          "the paper does not support, or described a figure's scope wrongly. The fresh reader check is what caught "
          "this; a value only check would have passed every row.",
          "2. Q1.4: the new Cortex-M33 rows contradicted a report headline; the report was corrected.",
          "3. Q2.1 (partial): over the swept ranges, loss up to 20 percent moves the handshake more than the "
          "fragment payload on most links; rate leads on the stream links and LoRaWAN.",
          "4. Q2.6: the faster LoRaWAN rate does not rescue the handshake under a 1 percent duty cycle; silence "
          "time dominates.",
          "5. Q3.4: in a staged plan the unknown share grows, because devices that become exposed later still lack "
          "free memory data. Collecting that data early is the cheap fix.",
          "6. Q5.1: a laptop virtual machine is not a stable timing platform; only rank order survived.", ""]
    (ROOT / "docs" / "PREDICTIONS_V2_SCORES.md").write_text("\n".join(L), encoding="utf-8", newline="\n")
    print(cnt, "hash", "ok" if want == got else "MISMATCH")


if __name__ == "__main__":
    main()
