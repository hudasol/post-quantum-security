#!/usr/bin/env python3
"""Run the round 5 arXiv database queries (public arXiv API, no account) and store the hits.

Queries are listed in QUERIES (fixed in data/raw/S13_protocol.csv before screening). Writes
data/raw/S13_arxiv_hits.csv: query_id, query, arxiv_id, published, title. The title screen is
recorded separately in data/raw/S13_screening.csv. Rerun with network access; results can
grow as arXiv grows, so the retrieval date is stored per row.
"""
import csv
import datetime
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw" / "S13_arxiv_hits.csv"
API = "https://export.arxiv.org/api/query?search_query={}&max_results=50"
NS = {"a": "http://www.w3.org/2005/Atom"}
QUERIES = [
    ("AX1", 'all:"Cortex-M55" AND all:cryptography'),
    ("AX2", "all:post-quantum AND all:microcontroller"),
    ("AX3", 'all:"SLH-DSA"'),
    ("AX4", "all:HQC AND all:Cortex"),
    ("AX5", "all:ESP32 AND all:post-quantum"),
    ("AX6", "all:RISC-V AND all:Kyber"),
    ("AX7", "all:XMSS AND all:verification"),
    ("AX8", "all:Falcon AND all:Cortex-M4"),
    ("AX9", 'all:"Cortex-M33" AND all:post-quantum'),
    ("AX10", "all:masked AND all:Kyber AND all:Cortex"),
]


def run(q):
    url = API.format(urllib.parse.quote(q, safe=":"))
    with urllib.request.urlopen(url, timeout=60) as resp:
        root = ET.fromstring(resp.read())
    for e in root.findall("a:entry", NS):
        yield (e.find("a:id", NS).text.rsplit("/", 1)[-1], e.find("a:published", NS).text[:10],
               " ".join(e.find("a:title", NS).text.split()))


def main():
    today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    rows = []
    for qid, q in QUERIES:
        for aid, pub, title in run(q):
            rows.append([qid, q, aid, pub, title, today])
        time.sleep(3)
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["query_id", "query", "arxiv_id", "published", "title", "retrieval_date"])
        w.writerows(rows)
    print(f"{len(rows)} hits from {len(QUERIES)} queries")


if __name__ == "__main__":
    main()
