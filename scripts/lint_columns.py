#!/usr/bin/env python3
"""Column lint for data/evidence.csv: catches the kinds of error the third verification pass found (a correct
number in a column whose meaning the source does not support, and warning text that contradicts the row).

Rules (each flag is a candidate for review, not a verdict):
  T1 cycles filled while the row speaks of ticks (SysTick, the Cortex-M timer pqm4 reads, excluded)
  T2 cycles filled while the row reports a time, unless the warning says how the cycles were obtained
  S1 a size filled without size_kind, or size_kind without a size
  M1 stack_bytes filled while the warning calls the figure total memory and never stack
  W1 the warning names a table that differs from the table in location_in_source
  W2 device_class mcu while the warning says the platform is not a microcontroller
  W3 clock_mhz filled while the warning says the clock is not stated
  U1 implausible magnitude: cycles below 1000, or code size below 100 B
Writes data/verify4/lint_flags.csv (one line per flag) and prints a count per rule. Exit code 0: flags are
reviewed by hand in data/verify4/lint_review.csv."""
import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "verify4" / "lint_flags.csv"


def tables(text):
    """Table numbers named in text, including lists such as 'Tables 4 and 5' or 'Tables 8, 9 and 10'."""
    out = set(re.findall(r"\bTable\s+(\d+)\b", text))
    for grp in re.findall(r"\bTables\s+((?:\d+\s*(?:,|and)?\s*)+)", text):
        out |= set(re.findall(r"\d+", grp))
    return out


def lint(r):
    w = r["comparability_warning"].lower()
    notes = r["compiler_flags_or_notes"].lower()
    flags = []
    if r["cycles"] and re.search(r"(?<!sys)tick", w + " " + notes):
        flags.append(("T1", "cycles filled while the row speaks of ticks"))
    if r["cycles"] and "reported time:" in notes and not re.search(r"cycle|derived|x ?\d+|times the", w):
        flags.append(("T2", "cycles filled next to a reported time, with no stated derivation"))
    if r["key_or_sig_size_bytes"] and not r["size_kind"]:
        flags.append(("S1", "size without size_kind"))
    if r["size_kind"] and not r["key_or_sig_size_bytes"] and r["size_kind"] not in ("",):
        flags.append(("S1", "size_kind without size"))
    if r["stack_bytes"] and "total" in w and "memory" in w and "stack" not in w:
        flags.append(("M1", "stack_bytes holds a figure the warning calls total memory"))
    loc_t = tables(r["location_in_source"])
    warn_t = tables(r["comparability_warning"])
    if loc_t and warn_t and not (warn_t & loc_t):
        flags.append(("W1", f"warning names Table {sorted(warn_t)}, location names Table {sorted(loc_t)}"))
    if r["device_class"] == "mcu" and re.search(r"not a microcontroller|host cpu result|not microcontroller", w):
        flags.append(("W2", "device_class mcu but the warning says it is not a microcontroller"))
    if r["clock_mhz"] and re.search(r"clock (is )?not stated|does not state the (core )?clock|clock not given", w):
        flags.append(("W3", "clock filled but the warning says it is not stated"))
    if r["cycles"] and float(r["cycles"]) < 1000:
        flags.append(("U1", "cycles below 1000"))
    if r["flash_or_code_bytes"] and float(r["flash_or_code_bytes"]) < 100:
        flags.append(("U1", "code size below 100 B"))
    return flags


def main():
    rows = list(csv.DictReader(open(ROOT / "data" / "evidence.csv", newline="", encoding="utf-8")))
    out = []
    for r in rows:
        for rule, why in lint(r):
            out.append({"id": r["id"], "stream": r["stream"], "rule": rule, "why": why})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["id", "stream", "rule", "why"], lineterminator="\n")
        w.writeheader()
        w.writerows(out)
    by = {}
    for o in out:
        by[o["rule"]] = by.get(o["rule"], 0) + 1
    print(f"{len(rows)} rows linted; {len(out)} flags on {len({o['id'] for o in out})} rows; by rule {dict(sorted(by.items()))}")


if __name__ == "__main__":
    main()
