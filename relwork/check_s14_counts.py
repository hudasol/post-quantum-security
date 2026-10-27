#!/usr/bin/env python3
"""Reproduce the counts of the round 6 dblp search (stream S14) from the logged files and fail on
any mismatch. Prints the measures of question Q13.

Checks:
  * results per query in data/raw/S14_dblp_log.csv equal the result lines in data/raw/S14_dblp_search_raw.csv;
  * record pages per query equal the records of data/raw/S14_dblp_records.csv whose found_by names the query;
  * the records passing title screening in S14_dblp_records.csv are exactly the rows of data/raw/S14_screening.csv;
  * the sum of records first seen per query equals the number of distinct records.
Rerun: python3 relwork/check_s14_counts.py
"""
import csv
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"


def read(name):
    with open(RAW / name, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def counts():
    log = read("S14_dblp_log.csv")
    raw = read("S14_dblp_search_raw.csv")
    recs = read("S14_dblp_records.csv")
    scr = read("S14_screening.csv")
    run = [r for r in log if r["status"] == "run"]
    passing = [r for r in recs if r["title_screen"] == "pass"]
    return {
        "queries_run": len(run),
        "fetches_refused": sum(r["status"] == "refused" for r in log),
        "results_returned": len(raw),
        "distinct_records": len(recs),
        "records_passing_title_screen": len(passing),
        "passing_not_seen_in_round5_screening": sum(r["seen_round5_screening"] == "no" for r in passing),
        "passing_new_to_repository": sum(r["new_record"] == "yes" for r in scr),
    }, log, raw, recs, scr


def problems():
    c, log, raw, recs, scr = counts()
    out = []
    per_query_raw = Counter(r["query_id"] for r in raw)
    per_query_rec = Counter(q for r in recs for q in r["found_by"].split())
    for r in log:
        if r["status"] != "run":
            continue
        q = r["query_id"]
        if int(r["results_returned"]) != per_query_raw[q]:
            out.append(f"{q}: results_returned {r['results_returned']} != {per_query_raw[q]} raw lines")
        if int(r["record_pages"]) != per_query_rec[q]:
            out.append(f"{q}: record_pages {r['record_pages']} != {per_query_rec[q]} records found by it")
    if sum(int(r["results_returned"]) for r in log) != len(raw):
        out.append("sum of results_returned differs from the raw lines")
    if sum(int(r["records_first_seen"]) for r in log) != len(recs):
        out.append("sum of records_first_seen differs from the distinct records")
    passing = {r["dblp_key"] for r in recs if r["title_screen"] == "pass"}
    if passing != {r["dblp_key"] for r in scr}:
        out.append("records passing title screening differ from data/raw/S14_screening.csv")
    return c, out


if __name__ == "__main__":
    c, out = problems()
    for k, v in c.items():
        print(f"{k}: {v}")
    for p in out:
        print("MISMATCH", p)
    sys.exit(1 if out else 0)
