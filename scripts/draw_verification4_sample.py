#!/usr/bin/env python3
"""Draw the seeded stratified sample for the second independent check of the S10 rows (verification pass 4).

Strata: source set (S10A to S10F) by table or section named in location_in_source. Each stratum gets
max(2, round(share x N)) rows, capped at its size, where N = 120; a few extra rows may result from the
minimum of 2. Rows are taken from data/evidence.csv as merged (after the fixes of verification pass 3), so the
check covers what the table now says. Writes data/verify4/sample_<set>.csv and data/verify4/sample_plan.csv.
Seed: 20261018 (printed)."""
import csv
import random
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEED = 20261018
N = 120
OUT = ROOT / "data" / "verify4"
BASE = ["id", "scheme", "parameter_set", "operation", "device", "core", "clock_mhz", "library", "library_version",
        "compiler_flags_or_notes", "cycles", "ram_bytes", "stack_bytes", "flash_or_code_bytes", "energy_uj",
        "key_or_sig_size_bytes", "size_kind", "evidence_type", "source_title", "source_url", "retrieval_date",
        "location_in_source", "comparability_warning"]


def stratum(r):
    m = re.search(r"Table\s+(\d+)", r["location_in_source"])
    if m:
        return f"Table {m.group(1)}"
    m = re.search(r"Section\s+([\d.]+)", r["location_in_source"])
    return f"Section {m.group(1)}" if m else "other"


def main():
    rows = [r for r in csv.DictReader(open(ROOT / "data" / "evidence.csv", newline="", encoding="utf-8"))
            if r["stream"] == "S10"]
    groups = defaultdict(list)
    for r in rows:
        groups[(r["id"][:4], stratum(r))].append(r)
    rng = random.Random(SEED)
    plan, picked = [], defaultdict(list)
    for key in sorted(groups):
        g = sorted(groups[key], key=lambda r: r["id"])
        k = min(len(g), max(2, round(N * len(g) / len(rows))))
        sel = sorted(rng.sample(g, k), key=lambda r: r["id"])
        picked[key[0]].extend(sel)
        plan.append({"set": key[0], "stratum": key[1], "rows_in_stratum": len(g), "sampled": k})
    OUT.mkdir(parents=True, exist_ok=True)
    for s, sel in picked.items():
        with open(OUT / f"sample_{s}.csv", "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=BASE, lineterminator="\n", extrasaction="ignore")
            w.writeheader()
            w.writerows(sel)
    with open(OUT / "sample_plan.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["set", "stratum", "rows_in_stratum", "sampled"], lineterminator="\n")
        w.writeheader()
        w.writerows(plan)
    print(f"seed {SEED}; {sum(p['sampled'] for p in plan)} rows sampled from {len(rows)} in {len(plan)} strata")
    for s in sorted(picked):
        print(s, len(picked[s]))


if __name__ == "__main__":
    main()
