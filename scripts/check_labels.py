#!/usr/bin/env python3
"""Fail if a round 4 result file mixes evidence labels or uses a label outside the vocabulary.

Scope: CSV files under the round 4 result folders (see ROUND4_DIRS). Each such file must have a
`label` column whose values are in LABELS. A column that carries values of a second label must
say so with a suffix (for example `cycles_published`); a column suffix that names a label not
in the vocabulary fails. data/evidence.csv must hold only published or derived from published
rows. The README defines the labels.
"""
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LABELS = {"published", "host measured", "emulated", "estimated", "planned", "modelled", "rtl simulated",
          "derived from published", "assumption", "synthetic", "board measured", "cited",
          "simulated (network)", "sitl measured"}
SUFFIXES = {"published", "host_measured", "emulated", "estimated", "planned", "modelled", "rtl_simulated",
            "derived", "assumption", "synthetic", "board_measured",
            "simulated_network", "sitl_measured"}
ROUND4_DIRS = ["cyclemodel/results", "rtlsim/results", "energy/results", "bootchain/results", "mission/results",
               "bench/board_kit/dry_run", "formal/results"]
# round 4 files inside folders that also hold earlier files (whose label column has other meanings)
ROUND4_FILES = ["linksim/results/validation_v4.csv", "linksim/results/diagnosis_v4.csv", "linksim/results/closed_form_v4.csv",
                "linksim/results/protocols_*.csv", "planner/results/profile_*.csv", "planner/results/mosca_*.csv",
                "bench/board_kit/image_sizes.csv", "data/reference_profiles.csv"]
LABELISH = re.compile(r"_(published|measured|emulated|estimated|planned|modelled|modeled|simulated|derived|synthetic)$")


def check_file(path):
    problems = []
    if Path(path).name.endswith("config.csv"):
        return []  # run configuration records, not results
    with open(ROOT / path, newline="", encoding="utf-8") as fh:
        rd = csv.DictReader(fh)
        cols = rd.fieldnames or []
        if "label" not in cols:
            return [f"{path}: no label column"]
        for c in cols:
            m = LABELISH.search(c)
            if m and not any(c.endswith("_" + s) for s in SUFFIXES):
                problems.append(f"{path}: column {c} names an unknown label")
        for i, r in enumerate(rd, start=2):
            v = (r.get("label") or "").strip().lower()
            if v not in LABELS:
                problems.append(f"{path} line {i}: label {v!r} not in the vocabulary")
                break
    return problems


def main():
    problems = []
    for d in ROUND4_DIRS:
        for p in sorted((ROOT / d).rglob("*.csv")) if (ROOT / d).exists() else []:
            problems += check_file(p.relative_to(ROOT))
    for pat in ROUND4_FILES:
        for p in sorted(ROOT.glob(pat)):
            problems += check_file(p.relative_to(ROOT))
    with open(ROOT / "data" / "evidence.csv", newline="", encoding="utf-8") as fh:
        bad = {r["evidence_type"] for r in csv.DictReader(fh)} - {"published", "derived-from-published"}
    if bad:
        problems.append(f"data/evidence.csv holds evidence types {sorted(bad)}")
    for p in problems:
        print(p)
    print(f"{len(problems)} label problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
