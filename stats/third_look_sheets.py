#!/usr/bin/env python3
"""Blank third look sheets for every wording disagreement of verification 5 not yet adjudicated.

A wording disagreement is a (row id, field) pair where a reader's text differed from the staged
text under the rules of scripts/summarize_verification5.py (fields other than the value fields).
Pairs already in data/verify5/adjudication.csv are skipped. Each sheet line gives only the row id,
the field name, the source title, the source URL, the supplied file name (when the source is in
the author supplied folder) and the location in the source. It never shows the staged value or
either reader's value.

Lines are split into up to three disjoint sheets; all fields of one source go to the same sheet so
that one reader opens each source once. The split is a greedy balance by line count over sources
sorted by name (deterministic, no random step).

Writes data/verify5/third_look_sheet_<n>.csv and data/verify5/third_look_rules.md.
"""
import csv
import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V = ROOT / "data" / "verify5"
N_SHEETS = 3
SUPPLIED = Path("/mnt/user-data/uploads/sources")


def _sv5():
    spec = importlib.util.spec_from_file_location("sv5", ROOT / "scripts" / "summarize_verification5.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def remaining_pairs():
    """Sorted list of (id, field) wording disagreements without an adjudication."""
    m = _sv5()
    rows_s, facts_s = m.staged("S12*_staged.csv"), m.staged("S12*_link_facts.csv")
    res = (m.compare(rows_s, m.read(V / "reader1_rows.csv"), m.read(V / "reader2_rows.csv"), m.ROW_FIELDS)
           + m.compare(facts_s, m.read(V / "reader1_facts.csv"), m.read(V / "reader2_facts.csv"), m.FACT_FIELDS))
    txt = sorted({(rid, f) for rid, f, _, _, _, st in res if st == "disagree" and f not in m.VALUE_FIELDS})
    adj = m.adjudications()
    return [k for k in txt if k not in adj], {**rows_s, **facts_s}, len(txt)


def supplied_file(url):
    """Name of the author supplied file whose name starts with the ePrint id of the URL, if any."""
    mm = re.search(r"eprint\.iacr\.org/(\d{4})/(\d+)", url or "")
    if not mm or not SUPPLIED.exists():
        return ""
    key = f"{mm.group(1)}-{mm.group(2)}"
    for p in sorted(SUPPLIED.iterdir()):
        if p.name.startswith(key + " ") or p.name.startswith(key + "\t") or p.name.split()[0] == key:
            return p.name
    return ""


def split(lines, n=N_SHEETS):
    by_src = {}
    for ln in lines:
        by_src.setdefault(ln["source_url"] or ln["source_title"], []).append(ln)
    sheets = [[] for _ in range(n)]
    for src in sorted(by_src, key=lambda s: (-len(by_src[s]), s)):
        i = min(range(n), key=lambda j: (len(sheets[j]), j))
        sheets[i].extend(by_src[src])
    return [sorted(s, key=lambda r: (r["source_url"], r["id"], r["field"])) for s in sheets]


RULES = """# Third look reading rules (verification 5, wording fields)

Author: Huda Mueen.

1. You see a row id, a field name, the source and a location. Open the source and go to the location.
2. Write in `value_as_in_source` what the source says for that field at that location, copied as printed
   (same words, same capitals, same symbols). Do not shorten, translate or normalise.
3. Field meanings: scheme (algorithm family named by the source), parameter_set (parameter set or
   variant name), operation (keygen, encaps, decaps, sign, verify or the operation name printed),
   device (board or chip), core (processor core), clock_mhz (clock in MHz), library (code base or
   implementation name), quantity (what a fact measures), unit, conditions (conditions printed with the value).
4. If the value is not at the stated location but elsewhere in the same source, copy it and write where
   in `location_found` (page, table, section). If it is nowhere in the source, leave `value_as_in_source`
   blank and write `not in source` in `note`. If the source is ambiguous, copy the candidates and write
   `ambiguous` in `note`.
5. Do not look at any other sheet, staging file or reader file of this repository. Use only the source.
6. If a source cannot be retrieved, leave the line blank and write `not retrieved` and the reason in `note`.
   Do not use mirrors, caches or archives.
7. Output: `third_look_<n>.csv` next to the sheet, columns id, field, value_as_in_source, location_found, note,
   one line per sheet line.
"""


def main():
    rem, stage, n_all = remaining_pairs()
    lines = []
    for rid, f in rem:
        s = stage[rid]
        lines.append(dict(id=rid, field=f, source_title=s.get("source_title", ""), source_url=s.get("source_url", ""),
                          supplied_file=supplied_file(s.get("source_url", "")),
                          location_in_source=s.get("location_in_source", "")))
    sheets = split(lines)
    cols = ["id", "field", "source_title", "source_url", "supplied_file", "location_in_source"]
    for i, sh in enumerate(sheets, 1):
        with open(V / f"third_look_sheet_{i}.csv", "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            w.writerows(sh)
    (V / "third_look_rules.md").write_text(RULES, encoding="utf-8")
    print(f"{n_all} wording disagreements, {len(rem)} without a third look; sheets: "
          + ", ".join(str(len(s)) for s in sheets))
    return 0


if __name__ == "__main__":
    sys.exit(main())
