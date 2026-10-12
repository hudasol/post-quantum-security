#!/usr/bin/env python3
"""Promote the staged S7 rows to data/raw/S7_verified.csv.

Each staged row was first taken from a fetch summary. On 2026-10-12 the author supplied the PDFs
(ePrint 2025/366 and 2020/470) and every value was found in the table named in location_in_source.
Two RISQrypt rows (S7-047, S7-048) duplicate S3-008 and S3-012 and are dropped.
Only the warning text and the retrieval date change; no number is edited."""
import csv
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
rows = list(csv.DictReader(open(ROOT / "data/raw/S7_new_rows.csv", newline="", encoding="utf-8")))
cols = list(rows[0].keys())[:23]
W = {
 "2025/366": ("Checked against the author supplied PDF on 2026-10-12: the value is in the table named in location_in_source. "
              "Cortex-M7 result. The paper states a 24 MHz core clock to avoid flash wait states (Section 5). "
              "Tables 4 and 5 give the mean of 5000 executions; Table 6 gives the mean of 1000 executions. "
              "Stack and code size not taken. Do not compare with Cortex-M4 rows without matching clock, library and statistic."),
 "2020/470": ("Checked against the author supplied PDF on 2026-10-12: the value is in the table named in location_in_source. "
              "The paper does not state the core clock. Cycle tables are in 10^6 cycles with two decimals, so converted figures carry about 10^4 cycles of rounding. "
              "SHA-256 rows from the full paper; the Africacrypt slide rows (S2-0260 onward) use other hash functions. Stack and code size not taken."),
}
SIZE = ("Checked against the author supplied PDF on 2026-10-12 (Table 3, signature size in bits; divided by 8, exact). "
        "Whether the figure includes any wire format header is not stated in the paper.")
out = []
for r in rows:
    if "2026/312" in r["source_url"]:
        continue
    key = "2025/366" if "2025/366" in r["source_url"] else "2020/470"
    r["comparability_warning"] = SIZE if r["operation"] == "size" else W[key]
    r["retrieval_date"] = "2026-10-12"
    out.append({c: r[c] for c in cols})
with open(ROOT / "data/raw/S7_verified.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=cols); w.writeheader(); w.writerows(out)
print(len(out), "rows written")
