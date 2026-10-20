#!/usr/bin/env python3
"""Check every registered claim against its data file (claims register, round 4).

data/claims_register.csv has one row per number stated in the paper or a proposal:
  claim_id, document, text_in_document, value, source_file, column, query, aggregate,
  tolerance_rel, label, note
The script recomputes the value from source_file (a CSV): rows are selected with the pandas
query in `query` (empty selects all), the column is aggregated (value, median, mean, min, max,
sum, count, nunique), and the result must equal `value` within `tolerance_rel` (default 0.005).
The document must contain `text_in_document` verbatim. Any mismatch fails the build, so a
document cannot drift from its data.
"""
import csv
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REG = ROOT / "data" / "claims_register.csv"


def compute(source, column, query, aggregate):
    d = pd.read_csv(ROOT / source)
    if query:
        d = d.query(query, engine="python")
    s = d[column] if column else d.iloc[:, 0]
    if aggregate == "value":
        if len(s) != 1:
            raise ValueError(f"query selects {len(s)} rows, expected 1")
        return float(s.iloc[0])
    if aggregate == "count":
        return float(len(s))
    if aggregate == "nunique":
        return float(s.nunique())
    return float(getattr(pd.to_numeric(s, errors="coerce"), aggregate)())


def main():
    if not REG.exists():
        print("no claims register yet")
        return 0
    problems, n = [], 0
    docs = {}
    with open(REG, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            n += 1
            cid = r["claim_id"]
            try:
                got = compute(r["source_file"], r["column"], r["query"], r["aggregate"] or "value")
            except Exception as exc:  # noqa: BLE001
                problems.append(f"{cid}: cannot compute ({exc})")
                continue
            want = float(r["value"])
            tol = float(r["tolerance_rel"] or 0.005)
            if abs(got - want) > tol * max(abs(want), 1e-12):
                problems.append(f"{cid}: data gives {got:g}, register says {want:g}")
            doc = r["document"]
            if doc not in docs:
                p = ROOT / doc
                docs[doc] = p.read_text(encoding="utf-8") if p.exists() else None
            if docs[doc] is None:
                problems.append(f"{cid}: document {doc} missing")
            elif r["text_in_document"] not in docs[doc]:
                problems.append(f"{cid}: text not found in {doc}: {r['text_in_document']!r}")
    for p in problems:
        print(p)
    print(f"{n} claims checked, {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
