#!/usr/bin/env python3
"""Build docs/PROPOSAL_ATRC.md from docs/PROPOSAL_ATRC_body.md, filling every {{placeholder}} from the
committed result files, so that no number in the proposal is typed by hand. Fails on an unfilled placeholder."""
import csv
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def rows(rel):
    with open(ROOT / rel, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def min_stack():
    """Lowest published ML-DSA-44 (or Dilithium2) stack figure that covers signing, over the whole table."""
    ev = rows("data/evidence.csv")
    c = [(float(r["stack_bytes"]), r["id"]) for r in ev if r["stack_bytes"] and "sign" in r["operation"]
         and any(t in r["parameter_set"] for t in ("ML-DSA-44", "Dilithium2", "Dilithium-2"))]
    v, i = min(c)
    return {"min_any": f"{v:,.0f}", "min_any_id": i}


def round3():
    """Third round figures: second check, lint, Renode, held out validation, cross check, host baseline."""
    v4 = []
    for x in "ABCDEF":
        p = ROOT / "data" / "verify4" / f"S10{x}_results.csv"
        if p.exists():
            v4 += rows(f"data/verify4/S10{x}_results.csv")
    oks = ("value_ok", "location_ok", "row_ok", "other_fields_ok", "warning_ok")
    bad = sum(1 for r in v4 if any(r[k].strip().lower() != "yes" for k in oks))
    lint = rows("data/verify4/lint_review.csv")
    ren = rows("bench/mcu/renode_results/checks.csv")
    ho = [r for r in rows("linksim/results/validation_heldout.csv") if r["split"] == "test"]
    xc = rows("linksim/results/validation_crosscheck.csv")[0]
    hs = rows("bench/host/native_v3/summary.csv")
    xs, ys = [float(r["median_ns"]) for r in hs], [float(r["pqm4_clean_cycles"]) for r in hs]
    rk = lambda v: [sorted(v).index(x) + 1 for x in v]  # noqa: E731
    n = len(xs)
    rho = 1 - 6 * sum((a - b) ** 2 for a, b in zip(rk(xs), rk(ys))) / (n * (n * n - 1))
    return {
        "v4_n": str(len(v4)), "v4_bad": str(bad),
        "v4_bound": f"{100 * 3 / len(v4):.1f}" if bad == 0 else "n/a",
        "lint_true": str(sum(1 for r in lint if r["verdict"] == "true")),
        "renode_n": str(sum(1 for r in ren if r["fail"] == "0")),
        "val_ho": f"{max(abs(100 * float(r['err_cal'])) for r in ho):.2f}",
        "val_unc_lo": f"{min(-100 * float(r['err_plain']) for r in rows('linksim/results/validation.csv')):.0f}",
        "val_unc_hi": f"{max(-100 * float(r['err_plain']) for r in rows('linksim/results/validation.csv')):.0f}",
        "spread3": f"{max(100 * float(r['spread']) for r in hs):.0f}",
        **min_stack(),
        "xc_factor": f"{float(xc['factor_below_low']):.1f}",
        "xc_factor4": f"{float([r for r in rows('linksim/results/diagnosis_v4.csv') if r['step'] == '6'][0]['factor_below_low_after']):.1f}",
        "rho3": f"{rho:.3f}",
        "ratio3": f"{max(abs(100 * float(r['ratio_diff'])) for r in hs):.1f}",
    }


def main():
    ev = rows("data/evidence.csv")
    s10 = [r for r in ev if r["stream"] == "S10"]
    v3 = {r["set"]: r for r in rows("data/verify3/summary.csv")}["all"]
    emu = [int(r["stack_bytes"]) for r in rows("bench/mcu/qemu_results/stack.csv") if r["board"] == "an386"
           and r["opt"] == "-O2" and r["param"] == "ML-DSA-44" and r["op"] == "sign"][0]
    mem = min((float(r["stack_bytes"] or r["ram_bytes"]), r["id"]) for r in ev if r["operation"] == "sign"
              and (r["stack_bytes"] or r["ram_bytes"])
              and any(t in r["parameter_set"] for t in ("Dilithium-2", "Dilithium2", "ML-DSA-44")))
    ck = rows("bench/mcu/qemu_results/checks.csv")
    stk = {(r["board"], r["opt"], r["param"], r["op"]): int(r["stack_bytes"]) for r in rows("bench/mcu/qemu_results/stack.csv")}
    m33 = max(abs(stk[("an505", o, p, op)] / v - 1) for (b, o, p, op), v in stk.items() if b == "an386")
    g = rows("linksim/results/mc_grid.csv")
    cell = lambda l, loss: [r for r in g if r["link"] == l and r["proto"] == "sr" and r["variant"] == "hybrid"  # noqa: E731
                            and float(r["loss"]) == loss and float(r["max_retries"]) == 20][0]
    val = rows("linksim/results/validation.csv")
    errs = [100 * float(r["err_plain"]) for r in val]
    diffs = [abs(100 * float(r["diff_err_plain"])) for r in val if r["diff_err_plain"] not in ("", "nan")]
    tor = rows("planner/results/tornado.csv")
    hs = rows("bench/host/native/summary.csv")
    xs, ys = [float(r["median_ns"]) for r in hs], [float(r["pqm4_clean_cycles"]) for r in hs]
    rk = lambda v: [sorted(v).index(x) + 1 for x in v]  # noqa: E731
    n = len(xs)
    rho = 1 - 6 * sum((a - b) ** 2 for a, b in zip(rk(xs), rk(ys))) / (n * (n * n - 1))
    sc = (ROOT / "docs" / "PREDICTIONS_V2_SCORES.md").read_text(encoding="utf-8")
    m = re.search(r"Totals: (\d+) hit, (\d+) partial, (\d+) miss, (\d+) not scored, of (\d+)", sc)
    cfg = {r["key"]: r["value"] for r in rows("linksim/results/config.csv")}
    vals = {
        "date": subprocess.run(["git", "log", "-1", "--format=%cs", "--", "data/evidence.csv"], cwd=ROOT,
                               capture_output=True, text=True).stdout.strip() or "undated",
        "n_rows": f"{len(ev):,}", "n_s10": str(len(s10)),
        "emu_sign": f"{emu:,}", "min_sign": f"{mem[0]:,.0f}", "min_sign_id": mem[1],
        "sign_ratio": f"{emu / mem[0]:.1f}",
        "rule3": f"{100 * 3 / int(v3['rows']):.2f}", "v3_any": v3["any"],
        "v3_rate": f"{100 * int(v3['any']) / int(v3['rows']):.1f}",
        "emu_builds": str(len(ck)) if all(r["fail"] == "0" for r in ck) else "NOT ALL",
        "m33_diff": f"{100 * m33:.1f}",
        "trials": cfg["trials_per_cell"],
        "sik_s": f"{float(cell('sik', 0.0)['median']):.2f}",
        "lora_h": f"{float(cell('lorawan', 0.0)['median']) / 3600:.2f}",
        "val_lo": f"{-max(errs):.0f}", "val_hi": f"{-min(errs):.0f}", "val_diff": f"{max(diffs):.0f}",
        "tornado": f"{100 * float(tor[0]['swing']):.1f}",
        "tornado_inputs": " and ".join(r["input"].replace("_", " ") for r in tor if r["swing"] == tor[0]["swing"]),
        "rho": f"{rho:.3f}", "cv": f"{100 * max(float(r['cv_of_run_medians']) for r in hs):.0f}",
        "p_ns": m.group(4),
        **round3(),
        "hr_default": [r["hr_low"] for r in rows("planner/results/scenario_range.csv") if r["devices"] == "1000"][0],
        "hr_portable": [r["hr_high"] for r in rows("planner/results/scenario_range.csv") if r["devices"] == "1000"][0],
        "p_hit": m.group(1), "p_partial": m.group(2), "p_miss": m.group(3), "p_total": m.group(5),
    }
    body = (ROOT / "docs" / "PROPOSAL_ATRC_body.md").read_text(encoding="utf-8")
    body = body.replace("Generated from `docs/PROPOSAL_ATRC_body.md` by `scripts/build_proposal.py`; every number",
                        "Generated from `docs/PROPOSAL_ATRC_body.md` by `scripts/build_proposal.py` (do not edit by hand); every number")
    for k, v in vals.items():
        body = body.replace("{{" + k + "}}", v)
    left = re.findall(r"\{\{\w+\}\}", body)
    if left:
        raise SystemExit(f"unfilled placeholders: {left}")
    (ROOT / "docs" / "PROPOSAL_ATRC.md").write_text(body, encoding="utf-8", newline="\n")
    print(f"wrote docs/PROPOSAL_ATRC.md, {len(body.split())} words")


if __name__ == "__main__":
    main()
