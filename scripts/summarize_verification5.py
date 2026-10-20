#!/usr/bin/env python3
"""Compare two independent readers with the staged round 4 rows and report error rates.

Inputs: data/raw/S12*_staged.csv and S12*_link_facts.csv (staged values); data/verify5/
reader1_rows.csv, reader2_rows.csv, reader1_facts.csv, reader2_facts.csv (filled blank sheets);
data/verify5/adjudication.csv (third look: id, field, verdict in staged_right, reader_right,
both_wrong, not_in_source, ambiguous_source; correct_value; note).

Rules, fixed before the comparison was run on the real sheets:
  * A field is compared only when a reader filled it. A blank reader field means the reader
    found no value at the stated location (status not_at_location), for example a clock stated
    only in the body text; it is not counted as a disagreement.
  * Value fields (numbers) agree within a relative 0.5 percent; ranges written "a to b" and
    "a-b" are the same; a value field agrees when the same set of numbers appears.
  * Text fields agree after lower casing and dropping punctuation if one contains the other or
    their word sets overlap by at least half.
  * A row is confirmed when every staged value field was read as the same number by BOTH
    readers. Value disagreements all get a third look. Text disagreements are counted per field;
    a seeded sample of them (seed 20261020) gets a third look to estimate the mapping error rate.

Writes data/verify5/summary.csv, data/verify5/row_status.csv and docs/VERIFICATION5.md.
"""
import csv
import math
import random
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
V = ROOT / "data" / "verify5"
SEED = 20261020
ROW_FIELDS = ["scheme", "parameter_set", "operation", "device", "core", "clock_mhz", "library", "cycles",
              "ram_bytes", "stack_bytes", "flash_or_code_bytes", "energy_uj", "key_or_sig_size_bytes"]
FACT_FIELDS = ["quantity", "value", "unit", "conditions"]
VALUE_FIELDS = {"cycles", "ram_bytes", "stack_bytes", "flash_or_code_bytes", "energy_uj", "key_or_sig_size_bytes", "value"}
NUM = VALUE_FIELDS | {"clock_mhz"}
TEXT_SAMPLE = 60


def read(path):
    if not path.exists():
        return {}
    with open(path, newline="", encoding="utf-8") as fh:
        return {r["id"]: r for r in csv.DictReader(fh)}


def staged(pattern):
    out = {}
    for p in sorted(RAW.glob(pattern)):
        out.update(read(p))
    return out


def num(x):
    try:
        return float(re.sub(r"[,\s]", "", str(x)))
    except ValueError:
        return None


def numbers(s):
    return sorted(float(m.replace(",", "")) for m in re.findall(r"\d[\d,]*\.?\d*", s))


def same(field, a, b):
    a, b = (a or "").strip(), (b or "").strip()
    if not a and not b:
        return True
    if field in NUM:
        x, y = num(a), num(b)
        if x is not None and y is not None:
            return abs(x - y) <= 0.005 * max(abs(x), abs(y), 1e-12)
        na, nb = numbers(a), numbers(b)
        return bool(na) and na == nb
    norm = lambda s: re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()
    x, y = norm(a), norm(b)
    if x == y or (x and y and (x in y or y in x)):
        return True
    tx, ty = set(x.split()), set(y.split())
    return bool(tx and ty) and len(tx & ty) / len(tx | ty) >= 0.5


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def compare(stage, r1, r2, fields):
    out = []
    for rid, s in stage.items():
        for name, r in (("reader1", r1.get(rid)), ("reader2", r2.get(rid))):
            for f in fields:
                sv = s.get(f, "")
                if r is None:
                    out.append((rid, f, name, sv, None, "missing_sheet"))
                    continue
                rv = r.get(f, "")
                if not sv.strip() and not rv.strip():
                    continue
                if not rv.strip():
                    status = "not_at_location"
                elif not sv.strip():
                    status = "reader_extra"
                else:
                    status = "agree" if same(f, sv, rv) else "disagree"
                out.append((rid, f, name, sv, rv, status))
    return out


def adjudications():
    if not (V / "adjudication.csv").exists():
        return {}
    with open(V / "adjudication.csv", newline="", encoding="utf-8") as fh:
        return {(r["id"], r["field"]): r for r in csv.DictReader(fh)}


def row_status(stage, res, adj, fields):
    """Per row: confirmed, corrected, single_reader, blocked, with the reason."""
    by = {}
    for rid, f, rd, sv, rv, st in res:
        by.setdefault(rid, []).append((f, rd, sv, rv, st))
    out = {}
    for rid, s in stage.items():
        items = by.get(rid, [])
        vals = [f for f in fields if f in VALUE_FIELDS and (s.get(f) or "").strip()]
        status, reason = "confirmed", ""
        if any(st == "missing_sheet" for _, _, _, _, st in items):
            status, reason = "blocked", "missing from a reader sheet"
        for f in vals:
            sts = {rd: st for ff, rd, _, _, st in items if ff == f}
            if "disagree" in sts.values():
                a = adj.get((rid, f))
                if a is None:
                    status, reason = "blocked", f"open value disagreement on {f}"
                    break
                if a["verdict"] in ("not_in_source", "ambiguous_source"):
                    status, reason = "blocked", f"{f}: {a['verdict']}"
                    break
                if a["verdict"] in ("reader_right", "both_wrong"):
                    status = "corrected"
            elif list(sts.values()).count("agree") < 2 and status == "confirmed":
                status, reason = "single_reader", f"{f} confirmed by fewer than two readers"
        if not vals and status == "confirmed":
            status, reason = "single_reader", "no value field to confirm"
        out[rid] = (status, reason)
    return out


def rate_line(label, k, n):
    if not n:
        return f"| {label} | {k} | 0 | n/a | n/a |"
    lo, hi = wilson(k, n)
    extra = f"; rule of three upper bound {300 / n:.1f} percent" if k == 0 else ""
    return f"| {label} | {k} | {n} | {100 * k / n:.1f} percent | {100 * lo:.1f} to {100 * hi:.1f} percent{extra} |"


def text_sample(res):
    keys = sorted({(rid, f) for rid, f, _, _, _, st in res if st == "disagree" and f not in VALUE_FIELDS})
    rnd = random.Random(SEED)
    return sorted(rnd.sample(keys, min(TEXT_SAMPLE, len(keys))))


def main():
    rows_s, facts_s = staged("S12*_staged.csv"), staged("S12*_link_facts.csv")
    res_rows = compare(rows_s, read(V / "reader1_rows.csv"), read(V / "reader2_rows.csv"), ROW_FIELDS)
    res_facts = compare(facts_s, read(V / "reader1_facts.csv"), read(V / "reader2_facts.csv"), FACT_FIELDS)
    res = res_rows + res_facts
    adj = adjudications()
    st_rows = row_status(rows_s, res_rows, adj, ROW_FIELDS)
    st_facts = row_status(facts_s, res_facts, adj, FACT_FIELDS)
    V.mkdir(parents=True, exist_ok=True)
    with open(V / "summary.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "field", "reader", "staged", "read", "status"])
        w.writerows(res)
    with open(V / "row_status.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "kind", "status", "reason"])
        for k, d in (("row", st_rows), ("fact", st_facts)):
            for rid, (s, r) in sorted(d.items()):
                w.writerow([rid, k, s, r])
    val_dis = sorted({(rid, f) for rid, f, _, _, _, st in res if st == "disagree" and f in VALUE_FIELDS})
    txt_dis = sorted({(rid, f) for rid, f, _, _, _, st in res if st == "disagree" and f not in VALUE_FIELDS})
    sample = text_sample(res)
    with open(V / "third_look_queue.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "field", "why"])
        w.writerows([(i, f, "value disagreement") for i, f in val_dis] + [(i, f, "seeded text sample") for i, f in sample])
    val_wrong = {k[0] for k in val_dis if adj.get(k, {}).get("verdict") in ("reader_right", "both_wrong", "not_in_source")}
    txt_judged = [k for k in sample if k in adj]
    txt_wrong = [k for k in txt_judged if adj[k]["verdict"] in ("reader_right", "both_wrong", "not_in_source")]
    field_counts = Counter(f for _, f in txt_dis)
    cs = Counter(s for s, _ in st_rows.values())
    cf = Counter(s for s, _ in st_facts.values())
    n_rows, n_val_rows = len(rows_s), sum(1 for s in rows_s.values() if any((s.get(f) or "").strip() for f in VALUE_FIELDS))
    lines = [
        "# Verification 5: two independent readers for every round 4 row", "",
        "Author: Huda Mueen. Generated by `scripts/summarize_verification5.py`; do not edit by hand.", "",
        f"Round 4 staged {n_rows} evidence rows and {len(facts_s)} link and timing facts. Each was read against its source by two readers "
        "who saw neither the staged values nor each other's sheets (blank sheets from `scripts/verify5_sheets.py`). "
        "Disagreements on values all got a third look; a seeded sample of wording disagreements got one too (`data/verify5/adjudication.csv`). "
        "The comparison rules are in the script header and were fixed before the comparison ran.", "",
        f"Limits. Only {len(txt_judged)} of {len(txt_dis)} wording disagreements (operation, scheme, library, conditions and similar fields) got a third look, "
        f"and staging was wrong in {len(txt_wrong)} of them. If that share holds for the rest, roughly "
        f"{round(len(txt_wrong) / max(len(txt_judged), 1) * (len(txt_dis) - len(txt_judged)))} wording fields of the promoted rows are still wrong; "
        "values are not affected, but groupings that use these fields (the meta analysis) may be. Two readers also wrote helper scripts "
        "to the same scratch path by accident (`docs/RUN_LOG.md` entry 35); each sheet came from its own fetches, but shared tooling cannot be excluded.", "",
        "## Outcome per evidence row", "",
        "| status | rows | meaning |", "|---|---|---|",
        f"| confirmed | {cs['confirmed']} | every value read as the same number by both readers |",
        f"| corrected | {cs['corrected']} | a value was wrong in staging and is corrected from the third look |",
        f"| single reader | {cs['single_reader']} | only one reader could confirm the value (for example a page one reader could not retrieve), or the row holds no value field; not promoted |",
        f"| blocked | {cs['blocked']} | open disagreement, value not in the source, or the source is ambiguous; not promoted |", "",
        f"Facts (not merged into the evidence table): confirmed {cf['confirmed']}, corrected {cf['corrected']}, single reader {cf['single_reader']}, blocked {cf['blocked']}.", "",
        "## Error rates", "",
        "| measure | rows | of | rate | Wilson 95 percent interval |", "|---|---|---|---|---|",
        rate_line("evidence rows with a confirmed wrong value in staging", len({r for r in val_wrong if r in rows_s}), n_val_rows),
        rate_line("evidence rows with any value disagreement between staging and a reader", len({k[0] for k in val_dis if k[0] in rows_s}), n_val_rows),
        rate_line("sampled wording disagreements where staging was wrong after a third look", len(txt_wrong), len(txt_judged)), "",
        f"Wording disagreements by field (before the third look; most are differences of phrasing such as \"sign\" and \"Sign (average)\"): "
        + ", ".join(f"{f} {n}" for f, n in field_counts.most_common()) + ".", "",
        "Fields a reader left blank because the source states them away from the cited location (for example a clock given in the body text) "
        f"are counted as not at location, not as errors: {sum(1 for x in res if x[5] == 'not_at_location')} field readings.", "",
        "Only confirmed and corrected rows enter `data/raw/S12_verified.csv` (`scripts/promote_s12.py`); single reader and blocked rows stay in staging with their reason in `data/verify5/row_status.csv`.", "",
    ]
    (ROOT / "docs" / "VERIFICATION5.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines[8:22]))


if __name__ == "__main__":
    main()
