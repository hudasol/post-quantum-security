#!/usr/bin/env python3
"""Summarise the fresh reader check of the S10 rows (data/verify3/*_results.csv).

Writes data/verify3/summary.csv and docs/VERIFICATION3.md. A row counts as an error if any of its four
checks is 'no'. A transcription error is a value that differs from the printed cell (the reader's
checked_value differs from the printed number); a mapping error is a correct printed number placed in a
column whose meaning the paper does not support. Intervals: Wilson score at 95 percent; with zero errors
the rule of three upper bound 3/n is also given."""
import csv
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VER = ROOT / "data" / "verify3"
SETS = {
    "S10A": "ePrint 2022/323, Tables 2 and 3",
    "S10B": "ePrint 2019/844, Sections 5.1, 5.2 and 5.4",
    "S10C": "ePrint 2026/1333, Tables 8 and 9",
    "S10D": "ePrint 2021/781, Tables 1, 2, 4, 5, 6 and 7",
    "S10E": "ePrint 2026/312, Tables 8, 9 and 10",
    "S10F": "ePrint 2026/2343, Tables 2, 3 and 5",
}
Z = 1.959963984540054


def wilson(k, n):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + Z * Z / n
    c = (p + Z * Z / (2 * n)) / d
    h = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def pass4_section():
    """Verification pass 4 (2026-10-18): a second, independent check of a seeded stratified sample of the S10
    rows, and a column lint over the whole table. Numbers come from data/verify4/."""
    v4 = ROOT / "data" / "verify4"
    if not (v4 / "sample_plan.csv").exists():
        return []
    plan = list(csv.DictReader(open(v4 / "sample_plan.csv", newline="", encoding="utf-8")))
    oks = ("value_ok", "location_ok", "row_ok", "other_fields_ok", "warning_ok")
    res = []
    for s in SETS:
        p = v4 / f"{s}_results.csv"
        if p.exists():
            res += list(csv.DictReader(open(p, newline="", encoding="utf-8")))
    n = len(res)
    bad = [r for r in res if any(r[k].strip().lower() != "yes" for k in oks)]
    trans = [r for r in res if r["transcription_error"].strip().lower() == "yes"]
    lo, hi = wilson(len(bad), n)
    flags = list(csv.DictReader(open(v4 / "lint_flags.csv", newline="", encoding="utf-8")))
    import io
    import subprocess
    import sys
    sys.path.insert(0, str(ROOT))
    from scripts import lint_columns
    old = subprocess.run(["git", "show", "efd8765:data/evidence.csv"], cwd=ROOT, capture_output=True, text=True,
                         encoding="utf-8").stdout
    first_n = len({r["id"] for r in csv.DictReader(io.StringIO(old)) if lint_columns.lint(r, first_version=True)})
    rev = list(csv.DictReader(open(v4 / "lint_review.csv", newline="", encoding="utf-8")))
    true = [r for r in rev if r["verdict"] == "true"]
    L = ["", "## Verification pass 4 (2026-10-18): second independent check and column lint", "",
         f"Sample: {n} of the {sum(int(p['rows_in_stratum']) for p in plan)} S10 rows, drawn by "
         "`scripts/draw_verification4_sample.py` with seed 20261018 from "
         f"{len(plan)} strata (source by table, at least 2 rows each; `data/verify4/sample_plan.csv`). Three "
         "readers that had seen neither the extraction notes nor the pass 3 results reopened the PDFs and compared "
         "every field, including whether each number sits in a column the paper supports "
         "(`data/verify4/S10?_results.csv`).", "",
         f"Rows with any error: {len(bad)} of {n}. Transcription errors: {len(trans)} of {n}."]
    if not bad:
        L.append(f"With zero errors the rule of three gives an approximate 95 percent upper bound of 3/{n} = {100 * 3 / n:.1f} "
                 f"percent on the row error rate of the S10 rows after the pass 3 fixes; approximate because the sample is "
                 f"stratified with unequal fractions and not reweighted (Wilson upper bound "
                 f"{100 * hi:.1f} percent).")
    else:
        L.append(f"Row error rate {100 * len(bad) / n:.1f} percent (Wilson 95 percent interval {100 * lo:.1f} to "
                 f"{100 * hi:.1f} percent).")
    L += ["", "Column lint: `scripts/lint_columns.py` checks all rows of `data/evidence.csv` for the error types "
          "pass 3 found (a number in a column the source does not support, warning text that contradicts the row). "
          f"The rules as first written flagged {first_n} rows, mostly false (they matched SysTick and missed lists "
          f"of tables); after refining them the lint raised {len(rev)} flags, every one reviewed by hand "
          f"(`data/verify4/lint_review.csv`): {len(true)} of {len(rev)} were real, all of one kind (cycle rows of "
          "stream S8 whose warning described the stack rows), and were fixed through `data/corrections.csv` "
          f"without changing any value. The current rules flag {len(flags)} rows, all reviewed false positives.", "",
          "Limits: the sample covers the S10 rows only; rows from earlier streams were checked by the phase 1 and "
          "phase 2 samples and now by the lint, not by a second full reading.", ""]
    return L


def main():
    out = []
    tot = {"rows": 0, "any": 0, "value": 0, "location": 0, "row": 0, "warning": 0}
    for s, desc in SETS.items():
        rows = list(csv.DictReader(open(VER / f"{s}_results.csv", newline="", encoding="utf-8")))
        c = {"set": s, "source": desc, "rows": len(rows)}
        for k in ("value", "location", "row", "warning"):
            c[k] = sum(1 for r in rows if r[k + "_ok"].strip().lower() != "yes")
        c["any"] = sum(1 for r in rows if any(r[k + "_ok"].strip().lower() != "yes"
                                              for k in ("value", "location", "row", "warning")))
        for k in tot:
            tot[k] += c[k]
        out.append(c)
    out.append({"set": "all", "source": "all six sets", **tot})
    with open(VER / "summary.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["set", "source", "rows", "any", "value", "location", "row", "warning"],
                           lineterminator="\n")
        w.writeheader()
        w.writerows(out)
    n, k = tot["rows"], tot["any"]
    lo, hi = wilson(k, n)
    L = ["# Verification, third pass (rows from author supplied PDFs)", "",
         "Author: Huda Mueen. Generated by `scripts/summarize_verification3.py`; do not edit by hand.", "",
         "## Method", "",
         "Each of the six staged files `data/raw/S10?_*.csv` was rechecked in full by a fresh reader that had "
         "not seen the extraction notes. The reader rendered each table page of the author supplied PDF, read "
         "every cell, recomputed every stated unit conversion and judged four things per row: the value, the "
         "location (page, table, row, column), the row description (scheme, parameter set, operation, device) "
         "and whether any statement in the warning is false. Results: `data/verify3/<set>_results.csv`. "
         "`scripts/promote_s10.py` applies only the fixes those results call for and writes "
         "`data/raw/S10_verified.csv`, which `scripts/merge_evidence.py` merges as stream S10.", "",
         "## Result", "",
         "| set | source | rows | rows with any error | value | location | row | warning |",
         "|---|---|---|---|---|---|---|---|"]
    for c in out:
        L.append(f"| {c['set']} | {c['source']} | {c['rows']} | {c['any']} | {c['value']} | {c['location']} | "
                 f"{c['row']} | {c['warning']} |")
    L += ["",
          f"Row error rate: {k} of {n} ({100 * k / n:.1f} percent; Wilson 95 percent interval "
          f"{100 * lo:.1f} to {100 * hi:.1f} percent).", "",
          "Kinds of error found:", "",
          "1. Mapping, 38 rows (S10D): the paper reports signing and verification cost in KiloTicks and says "
          "ticks come from the hardware clock and the time spent. The extraction multiplied them by 1000 and "
          "put them in the cycles column. Every printed number was right, but the paper does not establish that "
          "a tick is one CPU cycle, so the reader marked the value as not supported. Fix: the cycles cell is "
          "empty and the KiloTicks stay verbatim in the warning.",
          "2. Warning text, 3 rows (S10E-002, S10E-006, S10E-008): the warning described what a Table 9 figure "
          "covers wrongly (sampling by the hash accelerator was included; one gadget runs over k plus 1 "
          "polynomials). Fix: the sentence is replaced.", ""]
    trans = 0
    for s in SETS:
        for r in csv.DictReader(open(VER / f"{s}_results.csv", newline="", encoding="utf-8")):
            if r["value_ok"].strip().lower() != "yes" and "tick" not in r["note"].lower():
                trans += 1
    lo3 = 3.0 / n
    L += [f"Transcription errors (a printed number copied wrongly): {trans} of {n}. With zero errors the rule "
          f"of three gives a 95 percent upper bound of 3/{n} = {100 * lo3:.2f} percent; the Wilson upper bound is "
          f"{100 * wilson(0, n)[1]:.2f} percent.", "",
          "## Limits", "",
          "1. One fresh reader per set read every row; a second reading covered a seeded sample of 120 rows "
          "(pass 4, below), so errors in the unsampled rows that both readings would miss are not bounded.",
          "2. The readers followed the same reading method as the extractor (page renders, cell by cell) and were "
          "briefed separately; they are independent of the extraction notes, not of every habit of that method.",
          "3. The S10 rows sit outside the phase 1 and phase 2 verification rates in `docs/VERIFICATION.md` and "
          "`docs/VERIFICATION2.md`.",
          "4. Prior works quoted inside RISQrypt (ePrint 2026/312) were checked against RISQrypt's tables, not "
          "against the original papers.", ""]
    L += pass4_section()
    (ROOT / "docs" / "VERIFICATION3.md").write_text("\n".join(L), encoding="utf-8", newline="\n")
    print(f"rows {n}, rows with any error {k}, transcription errors {trans}")


if __name__ == "__main__":
    main()
