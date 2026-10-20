#!/usr/bin/env python3
"""Compare two independent readers with the staged round 5 rows (stream S13) and report error rates.

Inputs: data/raw/S13_staged.csv (staged values); data/verify6/reader1_rows.csv and
reader2_rows.csv (filled blank sheets from scripts/verify6_sheets.py); data/verify6/third_look.csv
(third look: id, field, verdict in staged_right, reader_right, both_wrong, not_in_source,
ambiguous_source; correct_value; note).

The comparison rules are the round 4 rules of scripts/summarize_verification5.py, imported
unchanged (relative 0.5 percent for numbers, word overlap for text, a blank reader field is
"not at location"). One change, fixed before the comparison ran: EVERY value disagreement and
EVERY wording disagreement goes to the third look (round 4 sampled 60 wording disagreements).

Writes data/verify6/summary.csv, row_status.csv, third_look_queue.csv (id, field, source,
location only, so the third reader sees no staged or reader value) and docs/VERIFICATION6.md.
"""
import csv
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import summarize_verification5 as v5  # noqa: E402

RAW = ROOT / "data" / "raw"
V = ROOT / "data" / "verify6"
FIELDS = v5.ROW_FIELDS
VALUE = v5.VALUE_FIELDS
WRONG = ("reader_right", "both_wrong", "not_in_source")
# Wording synonyms, fixed before the third look answers were read: the staged operation labels
# use the evidence table vocabulary (keygen, encaps, decaps, sign, verify); a source label that
# names the same operation in other words is the same wording.
SYNONYMS = [(r"\bkey[\s-]*pair[\s-]*generation\b|\bkey[\s-]*generation\b|\bkey[\s-]*gen\b\.?|\bkeypair\b|\bkeygen\b", "keygen"),
            (r"\bdecapsulation\b|\bdecaps\b\.?|\bdec\b", "decaps"),
            (r"\bencapsulation\b|\bencaps\b\.?|\benc\b", "encaps"),
            (r"\bsignature generation\b|\bsigning\b", "sign"),
            (r"\bverification\b", "verify")]


def norm_words(s):
    s = (s or "").lower()
    for rx, rep in SYNONYMS:
        s = re.sub(rx, rep, s)
    return s


def same_wording(field, a, b):
    if field in VALUE or field == "clock_mhz":
        return v5.same(field, a, b)
    return v5.same(field, a, b) or v5.same(field, norm_words(a), norm_words(b))


def staged():
    return v5.read(RAW / "S13_staged.csv")


def third_look(stage=None, r1=None, r2=None):
    """Third look answers are blind: id, field, third_value, status (found, not_in_source,
    ambiguous_source), note. The verdict is derived here with the round 4 comparison rule:
    staged_right if the third value matches staging, reader_right if it matches a reader but not
    staging, both_wrong otherwise. correct_value is the third reader's value."""
    p = V / "third_look.csv"
    if not p.exists():
        return {}
    stage = stage if stage is not None else staged()
    r1 = r1 if r1 is not None else v5.read(V / "reader1_rows.csv")
    r2 = r2 if r2 is not None else v5.read(V / "reader2_rows.csv")
    out = {}
    with open(p, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            i, f, tv, st = r["id"], r["field"], (r.get("third_value") or "").strip(), (r.get("status") or "found").strip()
            if st in ("not_in_source", "ambiguous_source") or not tv:
                verdict = st if st in ("not_in_source", "ambiguous_source") else "not_in_source"
            elif same_wording(f, stage.get(i, {}).get(f, ""), tv):
                verdict = "staged_right"
            elif any(same_wording(f, (rd.get(i) or {}).get(f, ""), tv) for rd in (r1, r2) if (rd.get(i) or {}).get(f, "").strip()):
                verdict = "reader_right"
            else:
                verdict = "both_wrong"
            out[(i, f)] = {"id": i, "field": f, "verdict": verdict, "correct_value": tv, "note": r.get("note", "")}
    return out


def compare_all():
    stage = staged()
    r1, r2 = v5.read(V / "reader1_rows.csv"), v5.read(V / "reader2_rows.csv")
    res = v5.compare(stage, r1, r2, FIELDS) if (r1 and r2) else []
    adj = third_look(stage, r1, r2)
    status = v5.row_status(stage, res, adj, FIELDS) if res else {k: ("pending", "reader sheets missing") for k in stage}
    # third look on flagged value fields (both readers agreed but flagged the source): applied after the round 4 rule
    for (i, f), a in adj.items():
        if f not in VALUE or i not in status or status[i][0] not in ("confirmed", "corrected"):
            continue
        if a["verdict"] in ("not_in_source", "ambiguous_source"):
            status[i] = ("blocked", f"{f}: {a['verdict']} after third look")
        elif a["verdict"] in ("reader_right", "both_wrong"):
            status[i] = ("corrected", "")
    return stage, res, adj, status, bool(r1 and r2)


def owens_ratio():
    """Ratio of the Owens et al. 168 MHz Ed25519 verify row to its 24 MHz verify row, from data/evidence.csv."""
    ev = v5.read(ROOT / "data" / "evidence.csv")
    pick = lambda mhz: [r for r in ev.values() if "10507285" in r["source_url"] and r["operation"] == "verify"
                        and r["clock_mhz"] == mhz and r["cycles"].strip()]
    a, b = pick("168"), pick("24")
    if len(a) != 1 or len(b) != 1:
        return ["Owens et al. verify ratio: the 168 MHz and 24 MHz verify rows are not both in data/evidence.csv.", ""]
    ra, rb = a[0], b[0]
    return ["## Owens et al. Ed25519 verify at 168 MHz and 24 MHz", "",
            f"Row {ra['id']} (168 MHz, {int(float(ra['cycles']))} cycles) over row {rb['id']} (24 MHz, {int(float(rb['cycles']))} cycles): "
            f"ratio {float(ra['cycles']) / float(rb['cycles']):.3f}. Both values are printed in kilo cycles, so the ratio carries the "
            "rounding of the source (resolution 1000 cycles per value). The source does not state the flash wait states of the 168 MHz run.", ""]


def rate(label, k, n):
    return v5.rate_line(label, k, n)


def main():
    V.mkdir(parents=True, exist_ok=True)
    stage, res, adj, status, have = compare_all()
    with open(V / "summary.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "field", "reader", "staged", "read", "status"])
        w.writerows(res)
    with open(V / "row_status.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "status", "reason"])
        for rid, (s, why) in sorted(status.items()):
            w.writerow([rid, s, why])
    val_dis = sorted({(i, f) for i, f, _, _, _, st in res if st == "disagree" and f in VALUE})
    txt_dis = sorted({(i, f) for i, f, _, _, _, st in res if st == "disagree" and f not in VALUE})
    flagged = []
    if (V / "reader_flags.csv").exists():
        with open(V / "reader_flags.csv", newline="", encoding="utf-8") as fh:
            flagged = [(r["id"], r["field"]) for r in csv.DictReader(fh) if (r["id"], r["field"]) not in set(val_dis + txt_dis)]
    with open(V / "third_look_queue.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "field", "kind", "source_title", "source_url", "location_in_source"])
        for (i, f) in val_dis + txt_dis:
            s = stage[i]
            w.writerow([i, f, "value" if f in VALUE else "wording", s["source_title"], s["source_url"], s["location_in_source"]])
        for i, f in flagged:
            s = stage[i]
            w.writerow([i, f, "reader flag", s["source_title"], s["source_url"], s["location_in_source"]])
    n_rows = len(stage)
    val_rows = [i for i, s in stage.items() if any((s.get(f) or "").strip() for f in VALUE)]
    n_fields = sum(1 for i in val_rows for f in VALUE if (stage[i].get(f) or "").strip())
    dis_rows = {i for i, _ in val_dis}
    dis_fields = len(val_dis)
    judged_v = [k for k in val_dis if k in adj]
    judged_t = [k for k in txt_dis if k in adj]
    wrong_v = [k for k in judged_v if adj[k]["verdict"] in WRONG]
    wrong_t = [k for k in judged_t if adj[k]["verdict"] in WRONG]
    flag_j = [k for k in flagged if k in adj]
    cs = Counter(s for s, _ in status.values())
    field_counts = Counter(f for _, f in txt_dis)
    promoted = cs["confirmed"] + cs["corrected"]
    lines = ["# Verification 6: two independent readers for every round 5 row (stream S13)", "",
             "Author: Huda Mueen. Generated by `scripts/summarize_verification6.py`; do not edit by hand.", ""]
    if not have:
        lines += [f"Round 5 staged {n_rows} evidence rows (`data/raw/S13_staged.csv`). The reader sheets "
                  "(`data/verify6/reader1_rows.csv`, `reader2_rows.csv`) are not present, so no row is double read and none is promoted.", ""]
    else:
        lines += [
            f"Round 5 staged {n_rows} evidence rows from {len({s['source_url'] for s in stage.values()})} sources (`data/raw/S13_staged.csv`). "
            "Each row was read against its source by two readers who saw neither the staged values nor each other's sheets "
            "(blank sheets from `scripts/verify6_sheets.py`, rules in `data/verify6/READING_RULES.md`). "
            "Every value disagreement and every wording disagreement was sent to a third reader who saw only the row id, the field, "
            "the source and the location (`data/verify6/third_look_queue.csv`); verdicts are in `data/verify6/third_look.csv`. "
            "The comparison rules are those of round 4 (`scripts/summarize_verification5.py`).", "",
            "## Outcome per evidence row", "",
            "| status | rows | meaning |", "|---|---|---|",
            f"| confirmed | {cs['confirmed']} | every value read as the same number by both readers |",
            f"| corrected | {cs['corrected']} | a value was wrong in staging and is corrected from the third look |",
            f"| single reader | {cs['single_reader']} | only one reader confirmed a value, or the row holds no value field; not promoted |",
            f"| blocked | {cs['blocked']} | open disagreement, value not in the source, or the source is ambiguous; not promoted |", "",
            f"Rows double read and promoted to `data/raw/S13_verified.csv`: {promoted}.", "",
            "## Error rates", "",
            "| measure | count | of | rate | Wilson 95 percent interval |", "|---|---|---|---|---|",
            rate("staged value fields with a disagreement between staging and a reader, before adjudication", dis_fields, n_fields),
            rate("staged rows with a value disagreement, before adjudication", len(dis_rows), len(val_rows)),
            rate("staged rows with a value confirmed wrong by the third look", len({k[0] for k in wrong_v}), len(val_rows)),
            rate("value disagreements where staging was wrong after the third look", len(wrong_v), len(judged_v)),
            rate("wording disagreements where the source wording differs from the staged label after the third look", len(wrong_t), len(judged_t)), "",
            "A differing wording is not a wrong value: the staged label (evidence table vocabulary, such as keygen) is kept and the source wording "
            "read by the third reader is appended to the comparability warning by `scripts/promote_s13.py`; a field the third reader found "
            "ambiguous in the source is noted there as well.", "",
            f"Reader flagged values sent to the third look although both readers agreed with staging: {len(flag_j)}; the third reader read the same value in "
            f"{sum(1 for k in flag_j if adj[k]['verdict'] == 'staged_right')} of them.", "",
            f"Third look coverage: {len(judged_v)} of {len(val_dis)} value disagreements and {len(judged_t)} of {len(txt_dis)} wording disagreements.", "",
            "Wording disagreements by field before the third look: "
            + (", ".join(f"{f} {n}" for f, n in field_counts.most_common()) or "none") + ".", "",
            f"Fields a reader left blank because the source states them away from the cited location are counted as not at location, "
            f"not as errors: {sum(1 for x in res if x[5] == 'not_at_location')} field readings.", "",
        ]
    lines += owens_ratio()
    (ROOT / "docs" / "VERIFICATION6.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines[4:]))


if __name__ == "__main__":
    main()
