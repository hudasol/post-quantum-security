#!/usr/bin/env python3
"""Round 6 search of the dblp index (stream S14, question Q13): build the query log, the record
list and the screening list from the result file as retrieved.

Inputs (written when the searches were run, 2026-10-28):
  data/raw/S14_dblp_search_raw.csv   every result line as returned (query, rank, title, url)
  data/raw/S14_title_screen.csv      title screening decision per dblp record (round 5 rules)
Outputs:
  data/raw/S14_dblp_log.csv          one row per query or refused fetch, with counts
  data/raw/S14_dblp_records.csv      one row per distinct dblp record, with round 5 and repository matches
  data/raw/S14_screening.csv         records that pass title screening, for later full text reading

The dblp search API, the dblp search page and the dblp record pages were refused by the fetch
tool, so the searches ran through the web search tool restricted to the dblp.org domain. Counts
are therefore result counts of that search (at most ten per query), not dblp hit counts; venue
names, years and DOIs could not be read from the records. The venue stream and a year hint are
taken from the dblp key, and the hint is marked as such. Rerun: python3 relwork/build_s14_dblp.py
"""
import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
DATE = "2026-10-28"
TOOL = "web search restricted to the dblp.org domain"

# Fetches that were refused; recorded, not worked around (rule 3).
REFUSED = [
    ("R01", "https://dblp.org/search/publ/api?q=post-quantum%20microcontroller&format=json&h=100",
     "dblp search API (JSON)", "refused by the fetch tool: URL not on the allowlist of the session"),
    ("R02", "https://dblp.org/search?q=post-quantum%20microcontroller",
     "dblp search page (HTML)", "refused by the fetch tool: URL not on the allowlist of the session"),
    ("R03", "https://dblp.org/rec/journals/micro/MisoczkiGGDVF19.html",
     "dblp record page", "retrieved page was a bot protection notice without the record; record pages not read"),
]

# Files that recorded what round 5 screened (titles, URLs and arXiv ids).
ROUND5_FILES = ["S13_screening.csv", "S13_arxiv_hits.csv", "S13_search_log.csv", "S13_staged.csv"]
# Files that hold sources the repository already cites.
REPO_FILES = [ROOT / "data" / "bibliography.bib", ROOT / "data" / "evidence.csv"]


def norm(text):
    text = re.sub(r"<[^>]+>", "", text or "")
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def clean_title(t):
    t = re.sub(r"^dblp:\s*", "", t.strip())
    t = re.sub(r"<sup>\+</sup>", "+", t)
    return t.rstrip(".").strip()


def page_kind(url):
    if "/rec/" in url:
        return "record"
    if "/pid/" in url or "/pers/" in url:
        return "person page"
    if "/db/" in url:
        return "venue or volume page"
    return "other page"


def dblp_key(url):
    return url.split("/rec/", 1)[1].rsplit(".html", 1)[0]


def arxiv_id(key):
    m = re.match(r"journals/corr/abs-(\d{4})-(\d{4,5})$", key)
    return f"{m.group(1)}.{m.group(2)}" if m else ""


def year_from_key(key):
    """Year hint from the dblp key naming convention (not read from the record)."""
    a = arxiv_id(key)
    if a:
        return "20" + a[:2]
    last = key.rsplit("/", 1)[-1]
    m = re.search(r"(\d{4})$", last) or re.search(r"(\d{4})-\d$", last)
    if m and 1950 < int(m.group(1)) < 2100:
        return m.group(1)
    m = re.search(r"(\d{2})[a-z]?$", last)
    if m:
        yy = int(m.group(1))
        return str(2000 + yy if yy <= 30 else 1900 + yy)
    return ""


def read(name):
    with open(RAW / name, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def corpus(paths):
    return norm(" ".join(Path(p).read_text(encoding="utf-8", errors="replace") for p in paths if Path(p).exists()))


def match(title, aid, text):
    """Return how a record matches a corpus: by full normalised title or by arXiv id."""
    hows = []
    nt = norm(title)
    if len(nt.split()) >= 4 and nt in text:
        hows.append("title")
    if aid and norm(aid) in text:
        hows.append("arXiv id")
    return " and ".join(hows)


def build():
    raw = read("S14_dblp_search_raw.csv")
    screen = {r["dblp_key"]: r for r in read("S14_title_screen.csv")}
    r5_text = corpus([RAW / f for f in ROUND5_FILES])
    repo_text = corpus(REPO_FILES + sorted(p for p in RAW.glob("S1[0-3]*") if p.suffix in (".csv", ".md")))

    order, queries = [], {}
    records = {}
    for r in raw:
        q = queries.setdefault(r["query_id"], {"query": r["query"], "results": []})
        if r["query_id"] not in order:
            order.append(r["query_id"])
        q["results"].append(r)
        if page_kind(r["url"]) == "record":
            k = dblp_key(r["url"])
            rec = records.setdefault(k, {"title": clean_title(r["title_as_shown"]), "url": r["url"], "found_by": []})
            if r["query_id"] not in rec["found_by"]:
                rec["found_by"].append(r["query_id"])

    rec_rows = []
    for k, rec in records.items():
        aid = arxiv_id(k)
        s = screen[k]
        seen5 = match(rec["title"], aid, r5_text)
        inrepo = match(rec["title"], aid, repo_text)
        rec_rows.append({
            "dblp_key": k, "title": rec["title"], "venue_stream_from_key": k.rsplit("/", 1)[0],
            "year_from_key": year_from_key(k), "doi": "not retrieved (record page refused)",
            "url": rec["url"], "arxiv_id_from_key": aid, "found_by": " ".join(rec["found_by"]),
            "seen_round5_screening": "yes" if seen5 else "no", "round5_match": seen5,
            "in_repository_sources": "yes" if inrepo else "no", "repository_match": inrepo,
            "title_screen": s["decision"], "label": "published"})

    seen_before = set()
    log = []
    for qid in order:
        q = queries[qid]
        res = q["results"]
        keys = [dblp_key(r["url"]) for r in res if page_kind(r["url"]) == "record"]
        first = [k for k in keys if k not in seen_before]
        seen_before.update(keys)
        passing = [k for k in keys if screen[k]["decision"] == "pass"]
        log.append({
            "query_id": qid, "date": DATE, "tool": TOOL, "database": "dblp (through the search tool)", "query": q["query"],
            "results_returned": len(res), "record_pages": len(keys),
            "person_pages": sum(page_kind(r["url"]) == "person page" for r in res),
            "venue_or_volume_pages": sum(page_kind(r["url"]) == "venue or volume page" for r in res),
            "records_first_seen": len(first), "records_passing_title_screen": len(passing),
            "status": "run", "note": "result count of the search tool, not a dblp hit count", "label": "published"})
    for rid, url, db, why in REFUSED:
        log.append({"query_id": rid, "date": DATE, "tool": "web fetch", "database": db, "query": url,
                    "results_returned": 0, "record_pages": 0, "person_pages": 0, "venue_or_volume_pages": 0,
                    "records_first_seen": 0, "records_passing_title_screen": 0, "status": "refused",
                    "note": why + "; recorded, not worked around", "label": "published"})

    scr_rows = []
    for row in rec_rows:
        if row["title_screen"] != "pass":
            continue
        s = screen[row["dblp_key"]]
        new = row["seen_round5_screening"] == "no" and row["in_repository_sources"] == "no"
        scr_rows.append({
            "dblp_key": row["dblp_key"], "title": row["title"], "url": row["url"], "found_by": row["found_by"],
            "rule": s["rule"], "reason": s["reason"], "round5_gap_by_title": s["round5_gap_by_title"],
            "seen_round5_screening": row["seen_round5_screening"], "in_repository_sources": row["in_repository_sources"],
            "new_record": "yes" if new else "no",
            "next_step": "read the full text and apply inclusion 4 and the round 5 gap rule" if new else "already known; no action",
            "label": "published"})

    write("S14_dblp_log.csv", log)
    write("S14_dblp_records.csv", rec_rows)
    write("S14_screening.csv", scr_rows)
    return log, rec_rows, scr_rows


def write(name, rows):
    with open(RAW / name, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    log, recs, scr = build()
    print(f"{sum(1 for r in log if r['status'] == 'run')} queries, {sum(1 for r in log if r['status'] == 'refused')} refused fetches, "
          f"{len(recs)} distinct records, {len(scr)} pass title screening, "
          f"{sum(r['new_record'] == 'yes' for r in scr)} of them new")
