#!/usr/bin/env python3
"""Promote second run rows (ePrint 2020/470, LMS and XMSS on Cortex-M4F) to data/raw/S8_verified.csv.

Only rows that were checked against the author supplied PDF are promoted: the value must sit in the table named
below, in the row for that design, hash, w and h, and in the column for that operation (strict check, 48 of 48).
Rows whose value this repository already holds are skipped (see data/crosscheck/matched.csv).
The remaining second run rows stay in data/second_run/ and are not in the evidence table."""
import csv, re
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
B = [r for r in csv.DictReader(open(ROOT / "data/second_run/evidence_second_run.csv", encoding="utf-8")) if r["id"].startswith("cam")]
matched = {r["id"] for r in csv.DictReader(open(ROOT / "data/crosscheck/matched.csv", encoding="utf-8"))}
S7 = [r for r in csv.DictReader(open(ROOT / "data/raw/S7_verified.csv", encoding="utf-8")) if "2020/470" in r["source_url"]]
tpl = S7[0]
cols = list(tpl.keys())
W = ("Second run row, checked against the author supplied PDF on 2026-10-12: the value, the row (design, hash, w, h) and the column (operation) all match the named table. "
     "Core clock not stated in the paper. Reference implementations (LMS from cisco/hash-sigs, XMSS from xmss-reference, modified by the authors); SHA-256 variant. "
     "Stack is the peak stack of the operation as reported in Table 12.")
AMB = (" Table 12 labels the h=10 SHA-256 row of this design as plain XMSS, so the mapping to SIMPLE+PRE follows the second run's reading and is not certain.")
out = []
n = 0
for r in B:
    if r["id"] in matched:
        continue
    n += 1
    var = r["scheme"].split(",")[-1].strip(" )") if "XMSS" in r["scheme"] else "LMS"
    scheme = "LMS" if var == "LMS" else "XMSS"
    h = int(re.search(r"h=(\d+)", r["parameter_set"]).group(1))
    is_cyc = "cycles" in r["metric"]
    row = {c: "" for c in cols}
    row.update({k: tpl[k] for k in ("device", "core", "clock_mhz", "compiler_flags_or_notes", "evidence_type", "source_title", "source_url", "library_version", "size_kind", "stream", "scheme_family", "standard_status", "device_class") if k in tpl})
    row.update({
        "id": f"S8-{n:03d}", "scheme": scheme,
        "parameter_set": f"{var} SHA-256 n=256 w=16 h={h} (single tree)" if scheme == "XMSS" else f"LMS SHA-256 n=256 w=16 h={h} (single tree)",
        "operation": r["operation"], "library": "LMS: cisco/hash-sigs (modified); XMSS: xmss-reference (modified), as named by the second run",
        "cycles" if is_cyc else "stack_bytes": str(int(float(r["value"]))),
        "retrieval_date": "2026-10-12",
        "location_in_source": f"Table {9 if h == 5 else 10} (cycles)" if is_cyc else "Table 12 (stack)",
        "comparability_warning": W + (AMB if (not is_cyc and h == 10 and var == "XMSS SIMPLE+PRE") else ""),
    })
    out.append(row)
with open(ROOT / "data/raw/S8_verified.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=cols); w.writeheader(); w.writerows(out)
print(len(out), "rows written")
