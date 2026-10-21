#!/usr/bin/env python3
"""Classify the third look of every remaining wording disagreement of verification 5.

Inputs: data/verify5/third_look_sheet_<n>.csv (blank sheets from stats/third_look_sheets.py), the answers
data/verify5/third_look_<n>.csv (id, field, value_as_in_source, location_found, note), the optional reread
data/verify5/third_look_3b.csv (replaces a line of sheet 3 that was not retrieved), the staged rows
(data/raw/S12*_staged.csv, S12*_link_facts.csv) and both reader sheets (data/verify5/reader*_*.csv).

The third reader saw only the source, the row id, the field and the location. The comparison is done here.

Comparison rule. The third reader copies the source verbatim, while staging and the first two readers wrote a
normalised description (for example "keygen" for the printed column "Key Generation", "Cortex-M4F" for
"32-bit ARM Cortex-M4 with FPU core"). A literal comparison would therefore count almost every line as a staging
error. Two texts are taken to state the same thing when any of these holds (rules written after the answers were
first compared literally, which is stated in docs/STATISTICS_V5.md):
  R1 the round 4 text rule of scripts/summarize_verification5.py (containment or word overlap of at least half);
  R2 operation fields: both map to the same canonical operation (keygen, encaps, decaps, sign, verify);
  R3 core fields: both name the same core (Cortex-M0+, M3, M4, M7, M33, M55, RISC-V), with or without FPU;
  R4 after normalisation (lower case; ^, |, =, commas, brackets and hyphens as spaces; "xmss mt" as "xmssmt";
     "sha 256" as "sha256"), every word of the shorter text appears in the longer one;
  R5 parameter_set fields: every number in the third reading appears in the staged text and they share at least
     one non numeric word.
Classes (per line): staging_right (staged text matches the third reading), reader_right (staged differs, at least
one reader matches), both_wrong (staged and both readers differ), not_in_source (third reader: not in source),
ambiguous (third reader marked the source ambiguous; not settled, reported apart), not_retrieved.

Substance. A wording difference is not by itself an error: staging writes normalised descriptions. For fields
with a canonical vocabulary (operation, core, scheme family, numbers of a parameter set) a contradiction test is
automatic. For the other fields (conditions, library, quantity, unit, device) the decision is read from
data/verify5/third_look_manual.csv (id, field, substance, reason), written in the comparison step after all values
were seen; lines missing there stay "field not judged".

Staging errors (contradictions) on rows that are in data/evidence.csv are written as corrections (data/corrections.csv format; the
old value is the current cell of data/evidence.csv). The new value is the canonical operation for operation
fields and the third reading verbatim otherwise.

Leniency of the automatic test: a scheme is compared only at family level, a parameter set is a contradiction only
when no number is shared, and a pair the test cannot map (for example an operation with no canonical name) counts
as "no contradiction found". The summary reports how many differing lines of judged fields could not be mapped,
and it reports the round 4 sample (judged under the round 4 rule: any difference from the source counts) and this
round separately before the pooled figure.

Labels: the summary counts and shares are script comparisons of readings against staged text, labelled estimated;
the third reading itself (column third of the classified file) is source wording.

Writes data/verify5/third_look_classified.csv, data/verify5/third_look_summary.csv and
data/verify5/third_look_corrections.csv; with --apply, appends the corrections to data/corrections.csv.
"""
import csv
import importlib.util
import math
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
V = ROOT / "data" / "verify5"
OPS = [("keygen", r"key ?gen|key generation|keypair|key pair|keygen"),
       ("encaps", r"encaps|encapsulat"),
       ("decaps", r"decaps|decapsulat"),
       ("sign", r"\bsign(ing|ature generation)?\b|\bsign\b"),
       ("verify", r"verif|signature validation|\bopen\b")]
CORES = [("Cortex-M0+", r"m0\+|m0 ?plus"), ("Cortex-M33", r"m33"), ("Cortex-M55", r"m55"), ("Cortex-M7", r"m7\b|m7f"),
         ("Cortex-M4", r"m4"), ("Cortex-M3", r"m3\b"), ("RISC-V", r"risc|rv32")]


def _sv5():
    spec = importlib.util.spec_from_file_location("sv5", ROOT / "scripts" / "summarize_verification5.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def canon_op(s):
    t = str(s).lower()
    hits = [k for k, p in OPS if re.search(p, t)]
    return hits[0] if len(hits) == 1 else None


def canon_core(s):
    t = str(s).lower()
    for k, p in CORES:
        if re.search(p, t):
            return k
    return None


def norm_words(s):
    t = str(s).lower()
    t = re.sub(r"xmss\s*\^?\s*mt", "xmssmt", t)
    t = re.sub(r"sha\s*-?\s*(\d)", r"sha\1", t)
    t = re.sub(r"shake\s*-?\s*(\d)", r"shake\1", t)
    t = re.sub(r"[\^|=,;:()\[\]/\-_'\"*+]", " ", t)
    return [w for w in t.split() if w not in {"the", "a", "an", "of", "and", "with", "in", "on", "for"}]


def numbers(s):
    return {float(x) for x in re.findall(r"\d+(?:\.\d+)?", str(s))}


def matches(field, staged, third, same):
    """Return the first rule under which the two texts state the same thing, else None."""
    if not str(staged).strip() or not str(third).strip():
        return None
    if same(field, staged, third):
        return "R1"
    if field == "operation" and canon_op(staged) and canon_op(staged) == canon_op(third):
        return "R2"
    if field == "core" and canon_core(staged) and canon_core(staged) == canon_core(third):
        return "R3"
    a, b = norm_words(staged), norm_words(third)
    if a and b:
        short, long_ = (a, b) if len(a) <= len(b) else (b, a)
        if set(short) <= set(long_):
            return "R4"
    if field == "parameter_set":
        nt, ns = numbers(third), numbers(staged)
        wt = {w for w in norm_words(third) if not re.fullmatch(r"\d+(\.\d+)?", w)}
        ws = {w for w in norm_words(staged) if not re.fullmatch(r"\d+(\.\d+)?", w)}
        if nt and nt <= ns and wt & ws:
            return "R5"
    return None


def _family(s):
    spec = importlib.util.spec_from_file_location("me", ROOT / "scripts" / "merge_evidence.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.scheme_family(str(s))


def contradiction(field, staged, third):
    """Substance test for a staged text that differs in wording: return the reason when the two name different
    things, else ''. Only fields with a canonical vocabulary are tested; other fields are not judged."""
    if field == "operation":
        a, b = canon_op(staged), canon_op(third)
        return f"operation {a} against {b}" if a and b and a != b else ""
    if field == "core":
        a, b = canon_core(staged), canon_core(third)
        return f"core {a} against {b}" if a and b and a != b else ""
    if field == "scheme":
        a, b = _family(staged), _family(third)
        return f"scheme family {a} against {b}" if a != "other" and b != "other" and a != b else ""
    if field == "parameter_set":
        a, b = numbers(staged), numbers(third)
        return "parameter numbers disjoint" if a and b and not (a & b) else ""
    return ""


JUDGED = {"operation", "core", "scheme", "parameter_set"}


def mappable(field, staged, third):
    """True when the automatic contradiction test can map both texts (canonical operation or core, a known scheme
    family, numbers in both parameter sets). An unmappable pair is reported as 'no contradiction found' by
    contradiction(); the summary counts such lines separately so the leniency is visible."""
    if field == "operation":
        return bool(canon_op(staged) and canon_op(third))
    if field == "core":
        return bool(canon_core(staged) and canon_core(third))
    if field == "scheme":
        return _family(staged) != "other" and _family(third) != "other"
    if field == "parameter_set":
        return bool(numbers(staged) and numbers(third))
    return False


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def load_answers():
    sheets = sorted(V.glob("third_look_sheet_[0-9].csv"))
    ans = []
    for sh in sheets:
        n = sh.stem.split("_")[-1]
        a = pd.read_csv(V / f"third_look_{n}.csv", dtype=str).fillna("")
        a["sheet"] = n
        ans.append(a)
    a = pd.concat(ans, ignore_index=True)
    b_path = V / "third_look_3b.csv"
    if b_path.exists():
        b = pd.read_csv(b_path, dtype=str).fillna("")
        for _, r in b.iterrows():
            m = (a["id"] == r["id"]) & (a["field"] == r["field"])
            if r["value_as_in_source"].strip() or r["note"].strip():
                a.loc[m, ["value_as_in_source", "location_found", "note"]] = [r["value_as_in_source"], r["location_found"], r["note"]]
                a.loc[m, "sheet"] = "3b"
    return a


def classify():
    m = _sv5()
    stage = {**m.staged("S12*_staged.csv"), **m.staged("S12*_link_facts.csv")}
    r1 = {**m.read(V / "reader1_rows.csv"), **m.read(V / "reader1_facts.csv")}
    r2 = {**m.read(V / "reader2_rows.csv"), **m.read(V / "reader2_facts.csv")}
    a = load_answers()
    out = []
    for _, r in a.iterrows():
        sv = stage[r["id"]].get(r["field"], "")
        v1 = r1.get(r["id"], {}).get(r["field"], "")
        v2 = r2.get(r["id"], {}).get(r["field"], "")
        tv, note = r["value_as_in_source"], r["note"].lower()
        rule = ""
        if "not retrieved" in note and not tv.strip():
            cls = "not_retrieved"
        elif "not in source" in note and not tv.strip():
            cls = "not_in_source"
        elif "ambiguous" in note:
            cls = "ambiguous"
        else:
            rule = matches(r["field"], sv, tv, m.same)
            if rule:
                cls = "staging_right"
            else:
                rr = [x for x in (matches(r["field"], v1, tv, m.same), matches(r["field"], v2, tv, m.same)) if x]
                cls = "reader_right" if rr else "both_wrong"
                rule = "readers: " + ",".join(rr) if rr else ""
        if cls == "staging_right":
            substance = "match"
        elif cls in ("reader_right", "both_wrong"):
            why = contradiction(r["field"], sv, tv)
            substance = ("contradiction: " + why) if why else (
                "wording only, no contradiction found" if r["field"] in JUDGED else "wording only, field not judged")
        else:
            substance = cls
        out.append(dict(label="published", id=r["id"], field=r["field"], sheet=r["sheet"], staged=sv,
                        reader1=v1, reader2=v2, third=tv, location_found=r["location_found"], note=r["note"],
                        verdict=cls, rule=rule, substance=substance))
    c = pd.DataFrame(out)
    man_path = V / "third_look_manual.csv"
    if man_path.exists():
        man = pd.read_csv(man_path, dtype=str).fillna("")
        mm = {(r["id"], r["field"]): r for _, r in man.iterrows()}
        for i, r in c.iterrows():
            k = (r["id"], r["field"])
            if r["substance"] == "wording only, field not judged" and k in mm:
                c.at[i, "substance"] = ("contradiction: " if mm[k]["substance"] == "contradiction" else "") \
                    + mm[k]["substance"] + " (manual: " + mm[k]["reason"] + ")"
    return c


def corrections(c):
    ev = pd.read_csv(ROOT / "data" / "evidence.csv", dtype=str).fillna("").set_index("id")
    wrong = c[c["verdict"].isin(["reader_right", "both_wrong"]) & c["substance"].str.startswith("contradiction")]
    out = []
    for _, r in wrong.iterrows():
        if r["id"] not in ev.index or r["field"] not in ev.columns:
            continue
        old = ev.loc[r["id"], r["field"]]
        new = canon_op(r["third"]) if r["field"] == "operation" and canon_op(r["third"]) else r["third"].strip()
        if not new or new == old:
            continue
        out.append(dict(id=r["id"], field=r["field"], old_value=old, new_value=new,
                        reason=f"Verification 5 third look (blind reader, sheet {r['sheet']}): source reads "
                               f"'{r['third'][:120]}' at {r['location_found'][:100] or 'the stated location'}; "
                               f"staged text did not match ({r['verdict']})"))
    return pd.DataFrame(out, columns=["id", "field", "old_value", "new_value", "reason"])


def main(apply=False):
    c = classify()
    c.to_csv(V / "third_look_classified.csv", index=False)
    settled = c[c["verdict"].isin(["staging_right", "reader_right", "both_wrong", "not_in_source"])]
    k = int(settled["verdict"].isin(["reader_right", "both_wrong", "not_in_source"]).sum())
    n = len(settled)
    lo, hi = wilson(k, n)
    rows = [dict(label="estimated", measure=f"lines {v}", count=int((c["verdict"] == v).sum()), of=len(c),
                 share=float((c["verdict"] == v).mean()), wilson_lo=float("nan"), wilson_hi=float("nan"))
            for v in ["staging_right", "reader_right", "both_wrong", "not_in_source", "ambiguous", "not_retrieved"]]
    rows.append(dict(label="estimated", measure="staged text differs verbatim from the source among settled lines", count=k, of=n,
                     share=k / n if n else float("nan"), wilson_lo=lo, wilson_hi=hi))
    # combined with the round 4 sample of 60 (adjudication.csv)
    adj = pd.read_csv(V / "adjudication.csv", dtype=str)
    m = _sv5()
    q = pd.read_csv(V / "third_look_queue.csv", dtype=str)
    samp = q[q["why"] == "seeded text sample"].merge(adj, on=["id", "field"])
    samp_set = samp[samp["verdict"].isin(["staged_right", "reader_right", "both_wrong", "not_in_source"])]
    k0 = int(samp_set["verdict"].isin(["reader_right", "both_wrong", "not_in_source"]).sum())
    n0 = len(samp_set)
    con = settled["substance"].str.startswith("contradiction")
    jud = settled[settled["field"].isin(JUDGED)]
    kc = int(jud["substance"].str.startswith("contradiction").sum())
    l4, h4 = wilson(kc, len(jud))
    rows.append(dict(label="estimated", measure="staged text contradicts the source, settled lines of judged fields "
                     "(operation, core, scheme, parameter_set)", count=kc, of=len(jud),
                     share=kc / len(jud) if len(jud) else float("nan"), wilson_lo=l4, wilson_hi=h4))
    ka = int(con.sum())
    l5, h5 = wilson(ka, n)
    rows.append(dict(label="estimated", measure="staged text contradicts the source, all settled lines "
                     "(automatic test and manual decisions)", count=ka, of=n, share=ka / n if n else float("nan"),
                     wilson_lo=l5, wilson_hi=h5))
    lo2, hi2 = wilson(ka + k0, n + n0)
    rows.append(dict(label="estimated", measure="staging wrong in substance, all wording disagreements with a settled "
                     "third look (round 4 sample of 60 and this round)", count=ka + k0, of=n + n0,
                     share=(ka + k0) / (n + n0) if n + n0 else float("nan"), wilson_lo=lo2, wilson_hi=hi2))
    rows.append(dict(label="estimated", measure="round 4 sample of 60: staging wrong after a third look (round 4 rule, any difference from the source)",
                     count=k0, of=n0, share=k0 / n0 if n0 else float("nan"), wilson_lo=wilson(k0, n0)[0], wilson_hi=wilson(k0, n0)[1]))
    dif_j = jud[jud["verdict"].isin(["reader_right", "both_wrong"])]
    unm = int(sum(not mappable(r["field"], r["staged"], r["third"]) for _, r in dif_j.iterrows()))
    rows.append(dict(label="estimated", measure="differing lines of judged fields that the automatic test could not map (counted as no contradiction found)",
                     count=unm, of=len(dif_j), share=unm / len(dif_j) if len(dif_j) else float("nan"),
                     wilson_lo=float("nan"), wilson_hi=float("nan")))
    rows.append(dict(label="estimated", measure="settled lines with wording that differs and no substance decision",
                     count=int((settled["substance"] == "wording only, field not judged").sum()), of=n,
                     share=float((settled["substance"] == "wording only, field not judged").mean()),
                     wilson_lo=float("nan"), wilson_hi=float("nan")))
    for f, g in settled.groupby("field"):
        kk = int(g["verdict"].isin(["reader_right", "both_wrong", "not_in_source"]).sum())
        l3, h3 = wilson(kk, len(g))
        rows.append(dict(label="estimated", measure=f"staged text differs verbatim among settled lines, field {f}", count=kk,
                         of=len(g), share=kk / len(g), wilson_lo=l3, wilson_hi=h3))
    for rule, g in c[c["verdict"] == "staging_right"].groupby("rule"):
        rows.append(dict(label="estimated", measure=f"staging right by rule {rule}", count=len(g), of=len(c),
                         share=len(g) / len(c), wilson_lo=float("nan"), wilson_hi=float("nan")))
    pd.DataFrame(rows).to_csv(V / "third_look_summary.csv", index=False, float_format="%.6g")
    corr = corrections(c)
    corr.to_csv(V / "third_look_corrections.csv", index=False)
    if apply and len(corr):
        cur = pd.read_csv(ROOT / "data" / "corrections.csv", dtype=str).fillna("")
        new = corr[~corr.set_index(["id", "field"]).index.isin(cur.set_index(["id", "field"]).index)]
        with open(ROOT / "data" / "corrections.csv", "a", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            for _, r in new.iterrows():
                w.writerow([r["id"], r["field"], r["old_value"], r["new_value"], r["reason"]])
        print(f"appended {len(new)} corrections")
    print(pd.DataFrame(rows)[["measure", "count", "of", "share", "wilson_lo", "wilson_hi"]].to_string())
    print(f"corrections for evidence rows: {len(corr)}")


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
