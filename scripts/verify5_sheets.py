#!/usr/bin/env python3
"""Make blank check sheets for the round 4 double reading (verification 5).

For every staged round 4 row (data/raw/S12*_staged.csv and data/raw/S12*_link_facts.csv)
the sheet gives only what a reader needs to find the value: id, source title, source URL and
location in the source. The values to check are left blank, so a reader cannot copy them.
Both readers get the same sheet; neither sees the staged values or the other reader's work.

Writes data/verify5/sheet_rows.csv and data/verify5/sheet_facts.csv.
"""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "verify5"
ROW_FIELDS = ["scheme", "parameter_set", "operation", "device", "core", "clock_mhz", "library", "cycles",
              "ram_bytes", "stack_bytes", "flash_or_code_bytes", "energy_uj", "key_or_sig_size_bytes"]
FACT_FIELDS = ["quantity", "value", "unit", "conditions"]


def staged(pattern):
    rows = []
    for p in sorted(RAW.glob(pattern)):
        with open(p, newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                r["_file"] = p.name
                rows.append(r)
    return rows


def write(path, rows, fields):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "source_title", "source_url", "location_in_source"] + fields + ["reader_note"])
        for r in rows:
            w.writerow([r["id"], r.get("source_title", ""), r.get("source_url", ""), r.get("location_in_source", "")]
                       + [""] * len(fields) + [""])


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = staged("S12*_staged.csv")
    facts = staged("S12*_link_facts.csv")
    write(OUT / "sheet_rows.csv", rows, ROW_FIELDS)
    write(OUT / "sheet_facts.csv", facts, FACT_FIELDS)
    print(f"sheets: {len(rows)} rows, {len(facts)} facts")


if __name__ == "__main__":
    main()
