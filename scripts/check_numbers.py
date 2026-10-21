#!/usr/bin/env python3
"""Check every registered claim against its data file (claims register, round 4).

data/claims_register.csv has one row per number stated in the paper or a proposal:
  claim_id, document, text_in_document, value, source_file, column, query, aggregate,
  tolerance_rel, label, note
The script recomputes the value from source_file (a CSV): rows are selected with the pandas
query in `query` (empty selects all), the column is aggregated (value, median, mean, min, max,
sum, count, nunique), and the result must equal `value` within `tolerance_rel` (default 0.005).
The document must contain `text_in_document` verbatim. Any mismatch fails the build, so a
document cannot drift from its data.

Location checks (review pass 1, round 5). A bare substring test lets a number drift in one
sentence while the same string survives elsewhere, so the text is checked at its own location:
  * whole token: the text must occur as a whole number, not inside a longer one ("1.36" does not
    match inside "21.36" or "1.365");
  * occurrence count: a text registered k times for one document must occur at least k times
    there as a whole token (two claims of 0.186 need two occurrences);
  * context: if a claim has a context string (column `context` of the register, or a row of the
    optional data/claims_context.csv with columns claim_id and context), the context must occur in
    the document and contain the text as a whole token, so the claim is pinned to its sentence;
  * short integers (one or two digits, no decimal point) without a context are too common to be
    located by count alone; they are reported as unanchored (a warning, not a failure) until a
    context is registered for them.
"""
import collections
import csv
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REG = ROOT / "data" / "claims_register.csv"
CONTEXT = ROOT / "data" / "claims_context.csv"
SHORT_INT = re.compile(r"^\d{1,2}$")


def token_pattern(text):
    """Regex for text as a whole token: no digit, letter or decimal part directly around it."""
    return re.compile(r"(?<![0-9A-Za-z])(?<![0-9][.,])" + re.escape(text) + r"(?![0-9A-Za-z])(?![.,][0-9])")


def count_tokens(text, doc):
    return len(token_pattern(text).findall(doc))


def load_contexts(rows, path=CONTEXT):
    ctx = {r["claim_id"]: r.get("context", "") for r in rows if r.get("context")}
    if path.exists():
        with open(path, newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                if r.get("context"):
                    ctx[r["claim_id"]] = r["context"]
    return ctx


def location_problems(rows, docs, contexts):
    """Problems and warnings of the location checks (see the module docstring)."""
    problems, warnings = [], []
    need = collections.Counter((r["document"], r["text_in_document"]) for r in rows)
    for (doc, text), k in sorted(need.items()):
        body = docs.get(doc)
        if body is None or not text:
            continue
        n = count_tokens(text, body)
        if SHORT_INT.match(text):
            continue  # handled per claim below (context or warning)
        if n < k:
            problems.append(f"{doc}: {text!r} occurs {n} time(s) as a whole number, registered {k} time(s)")
    for r in rows:
        body = docs.get(r["document"])
        if body is None:
            continue
        text, cid = r["text_in_document"], r["claim_id"]
        c = contexts.get(cid)
        if c:
            if c not in body:
                problems.append(f"{cid}: context not found in {r['document']}: {c!r}")
            elif count_tokens(text, c) == 0:
                problems.append(f"{cid}: context does not contain {text!r} as a whole number")
        elif SHORT_INT.match(text):
            warnings.append(f"{cid}: short integer {text!r} has no context (unanchored)")
    return problems, warnings


def compute(source, column, query, aggregate):
    d = pd.read_csv(ROOT / source)
    if query:
        d = d.query(query, engine="python")
    s = d[column] if column else d.iloc[:, 0]
    if aggregate == "value":
        if len(s) != 1:
            raise ValueError(f"query selects {len(s)} rows, expected 1")
        return float(s.iloc[0])
    if aggregate == "count":
        return float(len(s))
    if aggregate == "nunique":
        return float(s.nunique())
    return float(getattr(pd.to_numeric(s, errors="coerce"), aggregate)())


def main():
    if not REG.exists():
        print("no claims register yet")
        return 0
    problems, n = [], 0
    docs = {}
    with open(REG, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        n += 1
        cid = r["claim_id"]
        try:
            got = compute(r["source_file"], r["column"], r["query"], r["aggregate"] or "value")
        except Exception as exc:  # noqa: BLE001
            problems.append(f"{cid}: cannot compute ({exc})")
            continue
        want = float(r["value"])
        tol = float(r["tolerance_rel"] or 0.005)
        if abs(got - want) > tol * max(abs(want), 1e-12):
            problems.append(f"{cid}: data gives {got:g}, register says {want:g}")
        doc = r["document"]
        if doc not in docs:
            p = ROOT / doc
            docs[doc] = p.read_text(encoding="utf-8") if p.exists() else None
        if docs[doc] is None:
            problems.append(f"{cid}: document {doc} missing")
        elif r["text_in_document"] not in docs[doc]:
            problems.append(f"{cid}: text not found in {doc}: {r['text_in_document']!r}")
    loc, warnings = location_problems(rows, docs, load_contexts(rows))
    problems += loc
    for p in problems:
        print(p)
    if "--verbose" in sys.argv:
        for w in warnings:
            print("warning: " + w)
    print(f"{n} claims checked, {len(problems)} problem(s), {len(warnings)} unanchored short integer(s) "
          f"(--verbose lists them)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
