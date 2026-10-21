#!/usr/bin/env python3
"""Compute the round 5 (stream S13) PRISMA style flow counts from the search files.

Inputs: data/raw/S13_search_log.csv (one row per query), data/raw/S13_screening.csv (one row
per record assessed beyond its title), data/raw/S13_staged.csv and, when present,
data/raw/S13_verified.csv. Writes data/raw/S13_prisma.csv (stage, count, how it is counted);
scripts/build_search_protocol.py turns it into the flow table and diagram.
"""
import csv
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"


def rows(name):
    p = RAW / name
    if not p.exists():
        return []
    with open(p, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def flow():
    log, scr = rows("S13_search_log.csv"), rows("S13_screening.csv")
    staged, verified = rows("S13_staged.csv"), rows("S13_verified.csv")
    n = lambda col: sum(int(r[col] or 0) for r in log)
    full = [r for r in scr if r["stage_reached"] == "full text"]
    inc = [r for r in scr if r["decision"] == "included"]
    out = [
        ("queries and sources searched", len(log), "rows of S13_search_log.csv"),
        ("identified", n("records_returned"), "sum of records_returned over queries; a record found by several queries counts once per query"),
        ("screened on title and snippet", n("records_screened"), "sum of records_screened over queries"),
        ("eligible (abstract or full text assessed)", len(scr), "distinct records in S13_screening.csv"),
        ("not retrieved", sum(r["stage_reached"] == "not retrieved" for r in scr), "records whose full text could not be retrieved"),
        ("full text assessed", len(full), "stage_reached = full text"),
        ("excluded after abstract or full text", sum(r["decision"] == "excluded" for r in scr), "decision = excluded, any stage"),
        ("included sources", len(inc), "decision = included"),
        ("staged rows", len(staged), "rows of S13_staged.csv"),
        ("rows confirmed by two readers and promoted", len(verified), "rows of S13_verified.csv"),
        ("included sources that contribute promoted rows", len({r["source_url"] for r in verified}),
         "distinct source_url of S13_verified.csv; an included source can contribute none when all its rows are unconfirmed or demoted"),
    ]
    reasons = Counter(r["exclusion_reason"] for r in scr if r["decision"] == "excluded")
    return out, reasons


def main():
    out, reasons = flow()
    with open(RAW / "S13_prisma.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["stage", "count", "how_counted", "label"])
        for s, c, h in out:
            # counts of this repository's own search records, made on a PC; not values from a source
            w.writerow([s, c, f"count of this repository's records: {h}", "host measured"])
        for why, c in sorted(reasons.items(), key=lambda x: (-x[1], x[0])):
            w.writerow([f"excluded: {why}", c, "count of this repository's records: S13_screening.csv exclusion_reason", "host measured"])
    for s, c, _ in out:
        print(f"{s}: {c}")


if __name__ == "__main__":
    main()
