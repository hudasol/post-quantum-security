#!/usr/bin/env python3
"""Cross check the second run's evidence table against data/evidence.csv.

The second run (an independent run of the same brief in a separate session, phase 1 only) wrote one value per row
(metric, value, unit). This repository writes one row per measurement with cycles, stack, code size and size in
separate columns. Matching is mechanical and value based:

  1. a second run row has a normalised source key (ePrint number, arXiv number, RFC number or URL path);
  2. its value counts as MATCHED if the same number appears in any cycles, stack, code or size column of a row
     here with the same source key (and, for pqm4 rows, the same parameter set and operation);
  3. otherwise it is ONLY_SECOND (no row here has that number for that source), and is listed for review.

No value is changed. Output: data/crosscheck/*.csv and data/crosscheck/SUMMARY.md."""
import csv, re, sys, collections
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
A_ALL = list(csv.DictReader(open(ROOT / "data/evidence.csv", encoding="utf-8")))
# Stream S8 rows were promoted from this very cross check, so they are left out to keep the result repeatable.
A = [r for r in A_ALL if r["stream"] != "S8"]
B = list(csv.DictReader(open(ROOT / "data/second_run/evidence_second_run.csv", encoding="utf-8")))
NUMCOLS = ["cycles", "stack_bytes", "flash_or_code_bytes", "key_or_sig_size_bytes", "ram_bytes", "energy_uj"]

def skey(url):
    u = url.lower().split(" ")[0]
    m = re.search(r"eprint\.iacr\.org/(\d{4}/\d+)", u)
    if m: return "eprint:" + m.group(1)
    m = re.search(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d+)", u)
    if m: return "arxiv:" + m.group(1)
    m = re.search(r"rfc-editor\.org/rfc/rfc(\d+)", u)
    if m: return "rfc:" + m.group(1)
    if "mupq/pqm4" in u: return "pqm4"
    m = re.search(r"nvlpubs\.nist\.gov/.*?(fips\.\d+|sp\.\d+-\d+\w*)", u)
    if m: return "nist:" + m.group(1)
    return re.sub(r"^https?://(www\.)?", "", u).rstrip("/").removesuffix(".pdf")

def fnum(x):
    try: return float(str(x).replace(",", ""))
    except ValueError: return None

def norm_param(p): return re.sub(r"[^a-z0-9]", "", p.lower())
def norm_op(o): return {"enc": "encaps", "dec": "decaps", "keygen": "keygen", "sign": "sign", "verify": "verify"}.get(o.lower(), o.lower())

idx = collections.defaultdict(set)          # source key -> numbers
pq = collections.defaultdict(set)           # (param, op) -> numbers (pqm4 only)
for r in A:
    k = skey(r["source_url"])
    for c in NUMCOLS:
        v = fnum(r[c])
        if v is None: continue
        idx[k].add(v)
        if k == "pqm4": pq[(norm_param(r["parameter_set"]), norm_op(r["operation"]))].add(v)

out = {"MATCHED": [], "ONLY_SECOND": [], "NO_NUMBER": []}
for r in B:
    v = fnum(r["value"])
    k = skey(r["source_url"])
    if v is None:
        out["NO_NUMBER"].append((r, k)); continue
    if k == "pqm4":
        ok = v in pq.get((norm_param(r["parameter_set"]), norm_op(r["operation"])), set()) or \
             (norm_op(r["operation"]).startswith("n/a") and v in idx[k])
    else:
        ok = v in idx[k]
    out["MATCHED" if ok else "ONLY_SECOND"].append((r, k))

d = ROOT / "data/crosscheck"; d.mkdir(exist_ok=True)
cols = ["id", "source_key", "scheme", "parameter_set", "operation", "metric", "value", "unit", "label", "source_url", "comparability_warning"]
for name, rows in out.items():
    with open(d / f"{name.lower()}.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh); w.writerow(cols)
        for r, k in rows:
            w.writerow([r["id"], k] + [r[c] for c in cols[2:]])
by = collections.defaultdict(collections.Counter)
for name, rows in out.items():
    for r, k in rows: by[k.split(":")[0] if ":" in k else (k if k == "pqm4" else "other")][name] += 1
L = ["# Cross check: second run against this repository", "",
     f"Second run rows: {len(B)}. This repository: {len(A)} rows (stream S8 left out, see the script). Matching is by value and source (see `scripts/crosscheck_second_run.py`).", "",
     "| Result | Rows |", "|---|---|"] + [f"| {k} | {len(v)} |" for k, v in out.items()] + ["", "| Source family | MATCHED | ONLY_SECOND | NO_NUMBER |", "|---|---|---|---|"]
for fam, c in sorted(by.items()): L.append(f"| {fam} | {c['MATCHED']} | {c['ONLY_SECOND']} | {c['NO_NUMBER']} |")
(d / "SUMMARY.md").write_text("\n".join(L) + "\n", encoding="utf-8")
print("\n".join(L))
