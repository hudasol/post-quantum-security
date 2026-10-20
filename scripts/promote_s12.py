#!/usr/bin/env python3
"""Promote round 4 staged rows to data/raw/S12_verified.csv after double reading.

A staged row (data/raw/S12*_staged.csv) is promoted only if its status from
scripts/summarize_verification5.py is confirmed (both readers read every value) or corrected
(a third look settled every value disagreement). Adjudicated corrections (verdict reader_right
or both_wrong, with correct_value) replace the staged value and the change is appended to the
comparability warning. All other rows stay in staging and are listed with their reason in
data/verify5/not_promoted.csv. No other value is changed.
"""
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import summarize_verification5 as sv  # noqa: E402

RAW = ROOT / "data" / "raw"
V = ROOT / "data" / "verify5"
OUT = RAW / "S12_verified.csv"


def main():
    stage = {}
    header = None
    for p in sorted(RAW.glob("S12*_staged.csv")):
        with open(p, newline="", encoding="utf-8") as fh:
            rd = csv.DictReader(fh)
            header = header or rd.fieldnames
            for r in rd:
                stage[r["id"]] = r
    rows_s = stage
    res = sv.compare(rows_s, sv.read(V / "reader1_rows.csv"), sv.read(V / "reader2_rows.csv"), sv.ROW_FIELDS)
    adj = sv.adjudications()
    status = sv.row_status(rows_s, res, adj, sv.ROW_FIELDS)
    blocked = {rid: f"{st}: {why}" for rid, (st, why) in status.items() if st not in ("confirmed", "corrected")}
    out = []
    for rid, r in stage.items():
        if rid in blocked:
            continue
        r = dict(r)
        notes = []
        for (aid, f), a in adj.items():
            if aid == rid and a["verdict"] in ("reader_right", "both_wrong") and f in r:
                notes.append(f"{f} corrected from {r[f]!r} to {a['correct_value']!r} after double reading on 2026-10-20")
                r[f] = a["correct_value"]
        if notes:
            r["comparability_warning"] = (r.get("comparability_warning", "") + " " + "; ".join(notes) + ".").strip()
        out.append(r)
    if header is None:
        sys.exit("no staged rows")
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=header)
        w.writeheader()
        w.writerows(out)
    with open(V / "not_promoted.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "reason"])
        w.writerows(sorted(blocked.items()))
    print(f"promoted {len(out)} of {len(stage)}; not promoted {len(blocked)}")


if __name__ == "__main__":
    main()
