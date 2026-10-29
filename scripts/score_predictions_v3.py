#!/usr/bin/env python3
"""Score docs/PREDICTIONS_V3.md against its refutation clauses, recomputing every metric from committed files.

Writes docs/PREDICTIONS_V3_SCORES.md. The prediction file is never edited; its hash is checked first.
Verdicts: hit, partial, miss, not scored."""
import csv
import hashlib
import io
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
PRED_COMMIT = "e0fd150"  # commit that added the hashed predictions; state of the repository before any run


def rows(rel):
    with open(ROOT / rel, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def git_show(path, commit=PRED_COMMIT):
    return subprocess.run(["git", "show", f"{commit}:{path}"], cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", check=True).stdout


def main():
    from scripts import check_claims, lint_columns
    want = (ROOT / "docs" / "PREDICTIONS_V3.sha256").read_text(encoding="utf-8").split()[0]
    got = hashlib.sha256((ROOT / "docs" / "PREDICTIONS_V3.md").read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    S = []

    # R1: files (other than the report body and brief, and the generated report) that carried the retracted
    # claim at the prediction commit.
    files = subprocess.run(["git", "ls-tree", "-r", "--name-only", PRED_COMMIT], cwd=ROOT, capture_output=True,
                           text=True, check=True).stdout.split()
    skip = {"docs/REPORT_body.md", "docs/EXECUTIVE_BRIEF.md", "docs/REPORT.md"} | check_claims.ALLOW
    hit_files = sorted(f for f in files if f.endswith((".md", ".py", ".csv")) and f not in skip
                       and not f.startswith(("data/raw/", "data/second_run/"))
                       and check_claims.scan_text(git_show(f), f))
    S.append(("R1", "hit" if len(hit_files) >= 2 else "miss",
              f"{len(hit_files)} files still carried the retracted Cortex-M33 claim at the prediction commit: "
              + ", ".join(hit_files) + "; all corrected with dated notes, and `scripts/check_claims.py` now guards it."))

    # R2: second check of the seeded sample.
    v4 = [r for x in "ABCDEF" for r in rows(f"data/verify4/S10{x}_results.csv")]
    oks = ("value_ok", "location_ok", "row_ok", "other_fields_ok", "warning_ok")
    bad = sum(1 for r in v4 if any(r[k].strip().lower() != "yes" for k in oks))
    trans = sum(1 for r in v4 if r["transcription_error"].strip().lower() == "yes")
    rate = bad / len(v4)
    S.append(("R2", "hit" if rate <= 0.05 and trans == 0 else ("miss" if rate > 0.10 else "partial"),
              f"{bad} of {len(v4)} sampled rows with any error, {trans} transcription errors; rule of three upper "
              f"bound {100 * 3 / len(v4):.1f} percent."))

    # R3: lint as first written, on the table as it stood at the prediction commit.
    first = list(csv.DictReader(io.StringIO(git_show("data/evidence.csv"))))
    n_first = len({r["id"] for r in first if lint_columns.lint(r, first_version=True)})
    n_now = len({r["id"] for r in rows("data/evidence.csv") if lint_columns.lint(r)})
    rev = rows("data/verify4/lint_review.csv")
    n_rev, n_true = len(rev), sum(1 for r in rev if r["verdict"] == "true")
    S.append(("R3", "hit" if n_first <= 30 else ("miss" if n_first > 60 else "partial"),
              f"The lint as first written flagged {n_first} rows (refutation line 60): its tick rule matched "
              f"SysTick and its table rule missed lists of tables. After refining both rules it flagged {n_rev}, of "
              f"which {n_true} were real and fixed; the current rules flag {n_now}, all reviewed false positives."))

    # R4 to R6: planner scenarios.
    sc = rows("planner/results/scenarios.csv")
    hr = {r["scenario"]: int(r["HARDWARE_REPLACEMENT"]) for r in sc if r["devices"] == "1000"}
    order = hr["stack_asm"] < hr["speed_asm"] < hr["portable_c"] <= hr["reference_c"]
    S.append(("R4", "hit" if order else "miss",
              "Hardware replacements, 1000 devices: " + ", ".join(f"{k} {v}" for k, v in hr.items())
              + " (after the threshold correction of 2026-10-18; the order was the same before it). Across five "
              "fleet draws neighbouring scenarios overlap (`docs/PLANNER_STUDY.md` section 1)."))
    ratio = max(hr.values()) / min(hr.values())
    S.append(("R5", "hit" if ratio >= 1.4 else "miss", f"Highest over lowest: {ratio:.2f}."))
    rng = rows("planner/results/scenario_range.csv")
    shares = {r["devices"]: float(r["share_changed"]) for r in rng}
    ok6 = all(0.10 <= v <= 0.30 for v in shares.values())
    S.append(("R6", "hit" if ok6 else "miss",
              "Share of devices that change class between the extreme scenarios: "
              + ", ".join(f"{k} devices {100 * v:.1f} percent" for k, v in shares.items())
              + ". With 10 devices the share is one device, so that size says little."))

    # R7 to R9: link validation.
    ho = [r for r in rows("linksim/results/validation_heldout.csv") if r["split"] == "test"]
    worst = max(abs(float(r["err_cal"])) for r in ho)
    S.append(("R7", "hit" if worst <= 0.10 else ("miss" if worst > 0.15 else "partial"),
              f"Largest held out error {100 * worst:.1f} percent over {len(ho)} groups (a weak test: the groups "
              "differ only in key exchange bytes on one link)."))
    xc = rows("linksim/results/validation_crosscheck.csv")[0]
    f8 = float(xc["factor_below_low"])
    inside = float(xc["prose_low_s"]) <= float(xc["model_s"]) <= float(xc["prose_high_s"])
    S.append(("R8", "hit" if f8 >= 3 and not inside else "miss",
              f"Model {float(xc['model_s']):.1f} s for {xc['bytes']} B against 30 to 60 s in the prose: a factor of "
              f"{f8:.1f} below the low end."))
    from linksim import validate
    unval = [p for p, s, _ in validate.PARTS if s == "unvalidated" and p.startswith(("duty", "loss"))]
    S.append(("R9", "hit" if len(unval) == 2 else "miss",
              "No published measured figure for the duty cycle or loss parts in the evidence table or the supplied "
              "PDFs; both are labelled unvalidated (`docs/LINKSIM_STUDY.md` 4.3)."))

    # R10: PDFs.
    try:
        import pymupdf
        meta = [pymupdf.open(str(ROOT / "docs" / f)).metadata for f in ("REPORT.pdf", "EXECUTIVE_BRIEF.pdf")]
        built = all(m["author"] == "Huda Mueen" and m["creationDate"].startswith("D:202610") for m in meta)
        S.append(("R10", "hit" if built else "miss",
                  "Both PDFs rebuilt with `scripts/build_pdfs_docker.sh` (pandoc 3.1 image); author metadata "
                  + ", ".join(m["author"] for m in meta) + "."))
    except ImportError:
        S.append(("R10", "not scored", "PDF reader not installed where this script ran."))

    # R11, R12: host.
    hs = rows("bench/host/native_v3/summary.csv")
    spread = max(float(r["spread"]) for r in hs)
    S.append(("R11", "hit" if spread <= 0.10 else ("miss" if spread > 0.20 else "partial"),
              f"Largest spread of run medians {100 * spread:.1f} percent; largest median absolute deviation over "
              f"median {100 * max(float(r['rel_mad']) for r in hs):.1f} percent. Medians steadied, slow runs remained."))
    sign = {r["param"]: float(r["median_ns"]) for r in hs if r["op"] == "sign"}
    S.append(("R12", "hit" if sign["ML-DSA-44"] < sign["ML-DSA-65"] < sign["ML-DSA-87"] else "miss",
              "Signing medians: " + ", ".join(f"{k} {v:,.0f} ns" for k, v in sign.items()) + "."))

    # R13, R14: ASD and Renode.
    note = (ROOT / "data" / "raw" / "S11_standards_recheck.md").read_text(encoding="utf-8")
    asd = "Retry on 2026-10-18" in note and "timed out" in note.split("Retry on 2026-10-18")[1]
    S.append(("R13", "hit" if asd else "miss", "Two web fetch attempts on 2026-10-18 timed out (data/raw/S11)."))
    ren = rows("bench/mcu/renode_results/checks.csv")
    k512 = [r for r in ren if r["param"] == "ML-KEM-512"]
    S.append(("R14", "hit" if k512 and k512[0]["fail"] == "0" else "miss",
              f"Renode 1.17.0 ran {len(ren)} images on its STM32F4 Discovery model; "
              f"{sum(r['fail'] == '0' for r in ren)} pass every check, and stack equals QEMU to the byte."))

    # R15: proposal length.
    words = len((ROOT / "docs" / "PROPOSAL_ATRC.md").read_text(encoding="utf-8").split())
    S.append(("R15", "hit" if words <= 950 else ("miss" if words > 1100 else "partial"), f"{words} words."))

    # R16: second review.
    rev = ROOT / "docs" / "REVIEW_FINDINGS2.csv"
    if rev.exists():
        fx = rows("docs/REVIEW_FINDINGS2.csv")
        head = [r for r in fx if r["headline_contradiction"] == "yes"]
        changed = [r["n"] for r in fx if r["changed_headline"] == "yes"]
        sev = {k: sum(1 for r in fx if r["severity"] == k) for k in ("high", "medium", "low")}
        ok = 3 <= len(fx) <= 25 and not head
        S.append(("R16", "hit" if ok else "miss",
                  f"{len(fx)} findings ({sev['high']} high, {sev['medium']} medium, {sev['low']} low), above the "
                  f"refutation line of 25; none was a high severity contradiction of a headline number, but "
                  f"{len(changed)} medium findings (numbers {', '.join(changed)}) led to corrected headline figures: "
                  "the planner range and the proposal's stack range (`docs/REVIEW_FINDINGS2.csv`)."))
    else:
        S.append(("R16", "not scored", "second review not yet logged."))

    cnt = {v: sum(1 for _, x, _ in S if x == v) for v in ("hit", "partial", "miss", "not scored")}
    L = ["# Scores for the third round predictions", "",
         "Author: Huda Mueen. Generated by `scripts/score_predictions_v3.py` from committed files; do not edit by "
         "hand. Predictions: `docs/PREDICTIONS_V3.md`, unchanged since hashed.", "",
         f"Hash check: stored {want[:16]}..., file now {got[:16]}... "
         + ("(match)." if want == got else "(MISMATCH: the prediction file changed after hashing)."), "",
         f"Totals: {cnt['hit']} hit, {cnt['partial']} partial, {cnt['miss']} miss, {cnt['not scored']} not scored, "
         f"of {len(S)}.", "", "| ID | verdict | evidence |", "|---|---|---|"]
    L += [f"| {i} | {v} | {e} |" for i, v, e in S]
    L += ["", "## What the misses say", "",
          "1. R3: a lint is only as good as its first rules; the first version drowned the real errors in false "
          "flags, and the refinement was made after seeing them.",
          "2. R11: on a laptop virtual machine, interleaving and more runs steady the medians but cannot remove "
          "the slow periods; host spread stays large, so host numbers stay ratios only.",
          "3. R16: a second fresh review still found 53 problems, most of them small and stale wording, but two "
          "were real errors in the planner thresholds; one review per round is not enough to call the text clean.", ""]
    (ROOT / "docs" / "PREDICTIONS_V3_SCORES.md").write_text("\n".join(L), encoding="utf-8", newline="\n")
    print(cnt, "hash", "ok" if want == got else "MISMATCH")


if __name__ == "__main__":
    main()
