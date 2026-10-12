#!/usr/bin/env python3
"""Draw a seeded random sample of evidence rows for independent verification."""
import csv, random
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
SEED = 20261011
N = 50
rows = list(csv.DictReader(open(ROOT/"data/evidence.csv", newline="", encoding="utf-8")))
random.Random(SEED).shuffle(rows)
sample = rows[:N]
fields = list(sample[0].keys())
with open(ROOT/"data/verification_sample.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=fields); w.writeheader(); w.writerows(sample)
print(f"seed={SEED} n={N} of {len(rows)}")
from collections import Counter
print(Counter(r["stream"] for r in sample), Counter(r["device_class"] for r in sample))
