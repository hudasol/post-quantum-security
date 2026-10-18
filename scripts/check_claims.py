#!/usr/bin/env python3
"""Fail if a retracted claim reappears in tracked text.

Each entry in RETRACTED is a pattern for a statement that the evidence table contradicts. A line that matches is
allowed only if it is itself marked as a correction (it contains 'orrection' or 'earlier versions said' or
'earlier said'), or if the file is a log that quotes the history (ALLOW). Exit 1 on any other hit."""
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RETRACTED = [
    # Retracted 2026-10-16: rows S10C-001 to S10C-036 give ML-DSA cycles on a Cortex-M33 (STM32U5A5).
    (r"no published ML-KEM[,/ ]+ML-DSA(?:[,/ ]+(?:or )?SLH-DSA)? cycle", "no published PQC cycles on a Cortex-M33"),
    (r"no published ML-KEM/ML-DSA cycles exist", "no published PQC cycles on a Cortex-M33"),
    (r"any Cortex-M33 result", "no Cortex-M33 result at all"),
    (r"\bno M33\b", "no M33 numbers"),
    (r"nothing from a flight controller part", "no Cortex-M7 numbers at all"),
]
MARKERS = ("orrection", "earlier versions said", "earlier said", "earlier versions")
ALLOW = {"docs/RUN_LOG.md", "docs/REVIEW_FINDINGS.csv", "docs/REVIEW_FINDINGS2.csv", "scripts/check_claims.py",
         "tests/test_claims.py", "docs/PREDICTIONS_V2_SCORES.md", "docs/PREDICTIONS_V3.md"}
EXT = {".md", ".py", ".csv", ".txt", ".dot", ".tex"}


def tracked(root):
    out = subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True, check=True).stdout
    return [p for p in out.decode().split("\0") if p]


def scan_text(text, path=""):
    hits = []
    for n, line in enumerate(text.splitlines(), 1):
        for pat, what in RETRACTED:
            if re.search(pat, line, re.I) and not any(m in line for m in MARKERS):
                hits.append(f"{path}:{n}: retracted claim ({what})")
    return hits


def check(root):
    hits = []
    for rel in tracked(root):
        if rel in ALLOW or os.path.splitext(rel)[1] not in EXT or rel.startswith(("data/raw/", "data/second_run/")):
            continue
        p = os.path.join(root, rel)
        if os.path.isfile(p):
            hits += scan_text(open(p, encoding="utf-8", errors="replace").read(), rel)
    return hits


if __name__ == "__main__":
    h = check(ROOT)
    for x in h:
        print("CLAIM", x)
    print(f"{len(h)} retracted claim(s) found")
    sys.exit(1 if h else 0)
