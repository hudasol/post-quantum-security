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


def main():
    ev = rows("data/evidence.csv")
    s10 = [r for r in ev if r["stream"] == "S10"]
    v3 = {r["set"]: r for r in rows("data/verify3/summary.csv")}["all"]
    txt = subprocess.run(["git", "show", "1060a1d:bench/mcu/qemu_results/stack.csv"], cwd=ROOT,
                         capture_output=True, text=True, check=True).stdout
    emu = [int(l.split(",")[3]) for l in txt.splitlines() if l.startswith("ML-DSA,ML-DSA-44,sign,")][0]
    mem = min((float(r["stack_bytes"] or r["ram_bytes"]), r["id"]) for r in s10 if r["operation"] == "sign"
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
        "date": "2026-10-16",
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
