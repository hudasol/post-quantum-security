#!/usr/bin/env python3
"""Promote round 5 staged rows (stream S13) to data/raw/S13_verified.csv after double reading.

Same rule as scripts/promote_s12.py: a staged row (data/raw/S13_staged.csv) is promoted only if
its status from scripts/summarize_verification6.py is confirmed (both readers read every value)
or corrected (a third look settled a value). Third look results are applied as follows:
  * value fields with verdict reader_right or both_wrong: the third reader's value replaces the
    staged value and the change is appended to the comparability warning;
  * wording fields with verdict reader_right or both_wrong: the staged label is kept (it uses the
    evidence table vocabulary) and the source wording read by the third reader is appended to the
    comparability warning, so the disagreement is settled in the record;
  * wording fields judged not_in_source or ambiguous_source: noted in the warning.
All other rows stay in staging and are listed with their reason in data/verify6/not_promoted.csv.
"""
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import summarize_verification6 as sv  # noqa: E402

RAW = ROOT / "data" / "raw"
V = ROOT / "data" / "verify6"
OUT = RAW / "S13_verified.csv"
DATE = "2026-10-21"


def main():
    stage, res, adj, status, have = sv.compare_all()
    with open(RAW / "S13_staged.csv", newline="", encoding="utf-8") as fh:
        header = csv.DictReader(fh).fieldnames
    blocked = {i: f"{s}: {why}" for i, (s, why) in status.items() if s not in ("confirmed", "corrected")}
    out = []
    for rid, r in stage.items():
        if rid in blocked:
            continue
        r = dict(r)
        notes = []
        for (aid, f), a in sorted(adj.items()):
            if aid != rid or f not in r:
                continue
            if f in sv.VALUE:
                if a["verdict"] in ("reader_right", "both_wrong"):
                    notes.append(f"{f} corrected from {r[f]!r} to {a['correct_value']!r} after double reading on {DATE}")
                    r[f] = a["correct_value"]
            elif a["verdict"] in ("reader_right", "both_wrong"):
                notes.append(f"source wording for {f} (third look, {DATE}): {a['correct_value']!r}")
            elif a["verdict"] in ("not_in_source", "ambiguous_source"):
                notes.append(f"third look on {DATE}: {f} {a['verdict'].replace('_', ' ')}")
        if notes:
            r["comparability_warning"] = (r.get("comparability_warning", "").rstrip() + " " + "; ".join(notes) + ".").strip()
        out.append(r)
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
