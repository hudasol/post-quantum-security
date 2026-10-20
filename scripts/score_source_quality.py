#!/usr/bin/env python3
"""Score every source of data/evidence.csv that has cycle rows against a fixed checklist.

The checklist (data/source_quality_checklist.csv) was written before any source was scored.
One point per item: method stated, platform stated, statistic stated, code available, cycle
counter described. A point is given only when the text recorded in the evidence rows of that
source (notes, comparability warning, location, device, clock, library, URL) states it; the
matched phrase is written as the reason. A missing point therefore means "not recorded in the
evidence table", which may understate a source whose text was not transcribed in full.

Writes data/source_quality.csv (one row per source URL). WP5 uses the score as a weight.
"""
import csv
import re
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "data" / "evidence.csv"
OUT = ROOT / "data" / "source_quality.csv"

RULES = OrderedDict([
    ("method_stated", re.compile(r"pqm4|benchmark|measured|framework|harness|test vectors|\bKAT|executions|iterations|\bruns\b", re.I)),
    ("statistic_stated", re.compile(r"\bmean\b|average|median|minimum|maximum|\bmin\b|\bmax\b|single execution|executions|iterations|runs\b", re.I)),
    ("code_available", re.compile(r"github|gitlab|repositor|open source|pqm4|PQClean|liboqs|commit", re.I)),
    ("cycle_counter_described", re.compile(r"DWT|CYCCNT|SysTick|cycle counter|\bPMU\b|mcycle|rdcycle|k_cycle_get|\btimer\b", re.I)),
])


def first(rx, texts):
    for t in texts:
        m = rx.search(t)
        if m:
            s = max(0, m.start() - 30)
            return " ".join(t[s:m.end() + 30].split())
    return ""


def score(rows):
    text = lambda cols: [r[c] for r in rows for c in cols if r.get(c)]
    out = OrderedDict()
    notes = text(["compiler_flags_or_notes", "comparability_warning", "location_in_source"])
    m = first(RULES["method_stated"], notes)
    out["method_stated"] = (1, f"recorded: '{m}'") if m else (0, "no method phrase in the recorded rows")
    devs = [r["device"] for r in rows if r["device"].strip() and "not stated" not in r["device"].lower()]
    clk = [r["clock_mhz"] for r in rows if r["clock_mhz"].strip()]
    mhz = first(re.compile(r"\d+(\.\d+)?\s*MHz", re.I), text(["compiler_flags_or_notes", "comparability_warning", "device"]))
    if devs and (clk or mhz):
        out["platform_stated"] = (1, f"device '{devs[0][:60]}'; clock {clk[0] + ' MHz' if clk else repr(mhz)}")
    else:
        out["platform_stated"] = (0, "device or clock not recorded" + (f" (device '{devs[0][:40]}')" if devs else ""))
    s = first(RULES["statistic_stated"], text(["compiler_flags_or_notes", "comparability_warning"]))
    stated_absent = first(re.compile(r"statistic not stated|statistic: not stated", re.I), text(["compiler_flags_or_notes", "comparability_warning"]))
    if s and not (stated_absent and not re.search(r"mean|average|median|single execution", s, re.I)):
        out["statistic_stated"] = (1, f"recorded: '{s}'")
    else:
        out["statistic_stated"] = (0, "recorded rows say the statistic is not stated" if stated_absent else "no statistic in the recorded rows")
    c = first(RULES["code_available"], text(["source_url", "library", "library_version", "compiler_flags_or_notes", "comparability_warning"]))
    out["code_available"] = (1, f"recorded: '{c}'") if c else (0, "no repository or open code named in the recorded rows")
    k = first(RULES["cycle_counter_described"], text(["compiler_flags_or_notes", "comparability_warning"]))
    out["cycle_counter_described"] = (1, f"recorded: '{k}'") if k else (0, "no cycle counter named in the recorded rows")
    return out


def main():
    by = OrderedDict()
    with open(EVIDENCE, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["cycles"].strip():
                by.setdefault(r["source_url"], []).append(r)
    items = ["method_stated", "platform_stated", "statistic_stated", "code_available", "cycle_counter_described"]
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["source_url", "source_title", "cycle_rows", "score"] + [x for i in items for x in (i, i + "_reason")] + ["label"])
        for url, rows in by.items():
            s = score(rows)
            w.writerow([url, rows[0]["source_title"][:200], len(rows), sum(v[0] for v in s.values())]
                       + [x for i in items for x in s[i]] + ["derived from published"])
    print(f"{len(by)} sources scored")


if __name__ == "__main__":
    main()
