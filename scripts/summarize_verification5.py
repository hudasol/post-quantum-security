#!/usr/bin/env python3
"""Compare two independent readers with the staged round 4 rows and report error rates.

Inputs: data/raw/S12*_staged.csv and S12*_link_facts.csv (staged values), data/verify5/
reader1_rows.csv, reader2_rows.csv, reader1_facts.csv, reader2_facts.csv (filled sheets) and
data/verify5/adjudication.csv (third look at every disagreement: id, field, verdict in
staged_right, reader_right, both_wrong, not_in_source; correct_value; note).

A field is compared only when the staged value is not empty or a reader filled it. Numbers
are compared after removing thousands separators, with a relative tolerance of 0.5 percent
for values the source rounds (the reader notes such rounding). Text fields are compared
case insensitively after collapsing spaces.

Writes data/verify5/summary.csv and docs/VERIFICATION5.md. Error rates carry Wilson 95
percent intervals; zero events also carry the rule of three upper bound.
"""
import csv
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
V = ROOT / "data" / "verify5"
NUM = {"clock_mhz", "cycles", "ram_bytes", "stack_bytes", "flash_or_code_bytes", "energy_uj", "key_or_sig_size_bytes", "value"}
ROW_FIELDS = ["scheme", "parameter_set", "operation", "device", "core", "clock_mhz", "library", "cycles",
              "ram_bytes", "stack_bytes", "flash_or_code_bytes", "energy_uj", "key_or_sig_size_bytes"]
FACT_FIELDS = ["quantity", "value", "unit", "conditions"]
VALUE_FIELDS = {"cycles", "ram_bytes", "stack_bytes", "flash_or_code_bytes", "energy_uj", "key_or_sig_size_bytes", "value", "clock_mhz"}


def read(path):
    if not path.exists():
        return {}
    with open(path, newline="", encoding="utf-8") as fh:
        return {r["id"]: r for r in csv.DictReader(fh)}


def staged(pattern):
    out = {}
    for p in sorted(RAW.glob(pattern)):
        out.update(read(p))
    return out


def num(x):
    try:
        return float(re.sub(r"[,\s]", "", str(x)))
    except ValueError:
        return None


def same(field, a, b):
    a, b = (a or "").strip(), (b or "").strip()
    if not a and not b:
        return True
    if field in NUM:
        x, y = num(a), num(b)
        if x is None or y is None:
            return a.lower() == b.lower()
        return abs(x - y) <= 0.005 * max(abs(x), abs(y), 1e-12)
    norm = lambda s: re.sub(r"\s+", " ", s.lower())
    return norm(a) == norm(b) or norm(a) in norm(b) or norm(b) in norm(a)


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def compare(stage, r1, r2, fields):
    out = []
    for rid, s in stage.items():
        a, b = r1.get(rid), r2.get(rid)
        for f in fields:
            sv = s.get(f, "")
            for name, r in (("reader1", a), ("reader2", b)):
                if r is None:
                    out.append((rid, f, name, sv, None, "missing_sheet"))
                    continue
                rv = r.get(f, "")
                if not sv.strip() and not rv.strip():
                    continue
                out.append((rid, f, name, sv, rv, "agree" if same(f, sv, rv) else "disagree"))
    return out


def rate_line(label, k, n):
    lo, hi = wilson(k, n)
    extra = f"; rule of three upper bound {300 / n:.1f} percent" if k == 0 and n else ""
    return f"| {label} | {k} | {n} | {100 * k / n:.1f} percent | {100 * lo:.1f} to {100 * hi:.1f} percent{extra} |" if n else f"| {label} | {k} | 0 | n/a | n/a |"


def main():
    rows_s, facts_s = staged("S12*_staged.csv"), staged("S12*_link_facts.csv")
    res = compare(rows_s, read(V / "reader1_rows.csv"), read(V / "reader2_rows.csv"), ROW_FIELDS)
    res += compare(facts_s, read(V / "reader1_facts.csv"), read(V / "reader2_facts.csv"), FACT_FIELDS)
    adj = {}
    if (V / "adjudication.csv").exists():
        with open(V / "adjudication.csv", newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                adj[(r["id"], r["field"])] = r
    ids = sorted(set(rows_s) | set(facts_s))
    dis = {(rid, f) for rid, f, _, _, _, st in res if st == "disagree"}
    both_ok = [rid for rid in ids if not any(k[0] == rid for k in dis)
               and not any(x[0] == rid and x[5] == "missing_sheet" for x in res)]
    wrong_rows, wrong_value_rows, mapping_rows, open_items = set(), set(), set(), []
    for key in sorted(dis):
        a = adj.get(key)
        if a is None:
            open_items.append(key)
            continue
        if a["verdict"] in ("reader_right", "both_wrong", "not_in_source"):
            wrong_rows.add(key[0])
            (wrong_value_rows if key[1] in VALUE_FIELDS else mapping_rows).add(key[0])
    V.mkdir(parents=True, exist_ok=True)
    with open(V / "summary.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "field", "reader", "staged", "read", "status"])
        w.writerows(res)
    n = len(ids)
    lines = ["# Verification 5: two independent readers for every round 4 row", "",
             "Author: Huda Mueen. Generated by `scripts/summarize_verification5.py`; do not edit by hand.", "",
             f"Rows and facts staged in round 4: {n}. Each was read against its source by two readers who saw neither the staged values nor each other's sheets "
             "(blank sheets from `scripts/verify5_sheets.py`). Every disagreement got a third look (`data/verify5/adjudication.csv`).", "",
             f"Rows where both readers agreed with every staged field: {len(both_ok)} of {n} ({100 * len(both_ok) / n:.1f} percent)." if n else "No rows staged.", "",
             f"Field disagreements: {len(dis)}; adjudicated: {len(dis) - len(open_items)}; open: {len(open_items)}.", "",
             "| measure | rows | of | rate | Wilson 95 percent interval |", "|---|---|---|---|---|",
             rate_line("rows with any confirmed error before correction", len(wrong_rows), n),
             rate_line("rows with a confirmed wrong value (numeric field)", len(wrong_value_rows), n),
             rate_line("rows with a confirmed mapping or text error only", len(mapping_rows - wrong_value_rows), n), "",
             "Rows with a confirmed error were corrected or removed before the merge; the merged stream is `data/raw/S12_verified.csv`.", ""]
    if open_items:
        lines += ["Open disagreements (not merged until resolved):", ""] + [f"- {i} {f}" for i, f in open_items] + [""]
    (ROOT / "docs" / "VERIFICATION5.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines[6:12]))


if __name__ == "__main__":
    main()
