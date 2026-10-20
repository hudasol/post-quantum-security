#!/usr/bin/env python3
"""Fail if the bibliography is stale, a cited key is missing, or an entry is used by nothing.

Citations in documents are written as [@key]. Every key cited in docs/*.md must exist in
data/bibliography.bib, and every entry must be cited by at least one evidence row or be used
by a round 4 source note or parameter file (the bibliography records which).
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIB = ROOT / "data" / "bibliography.bib"


def main():
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "build_bibliography.py"), "--check"],
                       capture_output=True, text=True)
    problems = []
    if r.returncode:
        problems.append(r.stderr.strip() or r.stdout.strip())
    text = BIB.read_text(encoding="utf-8") if BIB.exists() else ""
    entries = re.findall(r"^@misc\{([^,]+),(.*?)^\}", text, re.M | re.S)
    keys = {k for k, _ in entries}
    for k, body in entries:
        if "Cited by" not in body and "Used by" not in body:
            problems.append(f"entry {k} is used by no row and no source note")
    for doc in sorted((ROOT / "docs").glob("*.md")):
        for k in re.findall(r"\[@([A-Za-z0-9_]+)\]", doc.read_text(encoding="utf-8")):
            if k not in keys:
                problems.append(f"{doc.relative_to(ROOT)} cites missing key {k}")
    for p in problems:
        print(p)
    print(f"{len(problems)} problem(s); {len(keys)} entries")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
