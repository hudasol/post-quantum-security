#!/usr/bin/env python3
"""Make blank check sheets for the round 5 double reading (verification 6, stream S13).

Same design as scripts/verify5_sheets.py: for every staged S13 row (data/raw/S13_staged.csv)
the sheet gives only what a reader needs to find the value: id, source title, source URL and
location in the source. The values to check are left blank, so a reader cannot copy them.
Both readers get the same sheet and the reading rules in data/verify6/READING_RULES.md;
neither sees the staged values or the other reader's work.

Writes data/verify6/sheet_rows.csv.
"""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "verify6"
ROW_FIELDS = ["scheme", "parameter_set", "operation", "device", "core", "clock_mhz", "library", "cycles",
              "ram_bytes", "stack_bytes", "flash_or_code_bytes", "energy_uj", "key_or_sig_size_bytes"]


def staged():
    with open(RAW / "S13_staged.csv", newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def write(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "source_title", "source_url", "location_in_source"] + ROW_FIELDS + ["reader_note"])
        for r in rows:
            w.writerow([r["id"], r["source_title"], r["source_url"], r["location_in_source"]] + [""] * len(ROW_FIELDS) + [""])


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = staged()
    write(OUT / "sheet_rows.csv", rows)
    print(f"sheet: {len(rows)} rows")


if __name__ == "__main__":
    main()
