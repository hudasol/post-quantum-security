#!/usr/bin/env python3
"""Promote the staged S10 rows (author supplied PDFs read on 2026-10-16) to data/raw/S10_verified.csv.

Each staged file data/raw/S10?_*.csv was rechecked row by row by a fresh reader who had not seen the
extraction notes; the results are in data/verify3/<set>_results.csv. This script applies only the fixes
those results call for and stops if any other row failed a check:
  * S10D: 38 rows put the paper's KiloTicks, multiplied by 1000, in the cycles column. The paper does not
    establish that a tick is one CPU cycle, so the cycles cell is emptied and the printed KiloTicks stay
    verbatim in comparability_warning. The millisecond time stays in compiler_flags_or_notes.
  * S10E-002, S10E-006, S10E-008: the warning described the measured span wrongly; the sentence is replaced.
No number is changed; only cells are emptied or warnings corrected."""
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
VER = ROOT / "data" / "verify3"
SETS = ["S10A", "S10B", "S10C", "S10D", "S10E", "S10F"]
OK = ("value_ok", "location_ok", "row_ok", "warning_ok")

GADGET = "Cycles for one first order masked non linear gadget applied to a whole polynomial"
WARN_FIX = {
    "S10E-002": "Cycles for pseudo random sampling by the Keccak accelerator plus the first order masked CBD gadget on a whole polynomial (Section 7.2.2 below Table 9)",
    "S10E-008": "Cycles for pseudo random sampling by the Keccak accelerator plus the first order masked uniform sampling gadget on a whole polynomial (Section 7.2.2 below Table 9)",
    "S10E-006": "Cycles for the first order masked zero test over the full input vectors u and v, that is k plus 1 polynomials (Algorithm 5)",
}
TICKS = re.compile(r"Table gives ([0-9.]+) KiloTicks; converted x1000\. The authors describe ticks as computed "
                   r"from the hardware clock and the time spent, so this is a cycle equivalent derived from "
                   r"measured time rather than a cycle counter reading\.")


def main():
    out, fixes, cols = [], [], None
    for s in SETS:
        staged = sorted(RAW.glob(f"{s}_*.csv"))
        if len(staged) != 1:
            sys.exit(f"{s}: expected one staged file, found {len(staged)}")
        rows = list(csv.DictReader(open(staged[0], newline="", encoding="utf-8")))
        cols = cols or list(rows[0].keys())
        res = {r["id"]: r for r in csv.DictReader(open(VER / f"{s}_results.csv", newline="", encoding="utf-8"))}
        for r in rows:
            v = res.get(r["id"])
            if v is None:
                sys.exit(f"{r['id']}: no fresh reader result")
            bad = [k for k in OK if v[k].strip().lower() != "yes"]
            if not bad:
                out.append(r)
                continue
            if s == "S10D" and bad == ["value_ok"]:
                m = TICKS.search(r["comparability_warning"])
                if not m:
                    sys.exit(f"{r['id']}: tick sentence not found")
                r["comparability_warning"] = TICKS.sub(
                    f"Table gives {m.group(1)} KiloTicks (kept as printed). The paper says ticks are computed from the "
                    "hardware clock and the time spent but does not establish that a tick is one CPU cycle, so the "
                    "cycles cell is left empty (fresh reader check, data/verify3/S10D_results.csv).",
                    r["comparability_warning"])
                r["cycles"] = ""
                fixes.append(f"{r['id']}: cycles emptied, KiloTicks kept in warning")
            elif r["id"] in WARN_FIX and bad == ["warning_ok"]:
                if GADGET not in r["comparability_warning"]:
                    sys.exit(f"{r['id']}: warning sentence not found")
                r["comparability_warning"] = r["comparability_warning"].replace(GADGET, WARN_FIX[r["id"]])
                fixes.append(f"{r['id']}: warning corrected")
            else:
                sys.exit(f"{r['id']}: failed {bad} and no fix is defined; resolve before promoting")
            out.append(r)
    with open(RAW / "S10_verified.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(out)
    for f in fixes:
        print("fix:", f)
    print(f"{len(out)} rows written, {len(fixes)} fixed")


if __name__ == "__main__":
    main()
