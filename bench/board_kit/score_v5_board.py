#!/usr/bin/env python3
"""Score the registered round 5 board predictions (docs/PREDICTIONS_V5_BOARD.md) from a board CSV.

Author: Huda Mueen. Inputs:
  one or more result CSVs from parse.py (only rows labelled 'board measured' are used),
  the checks CSV from parse.py (--checks), needed for refutation rule 3,
  bench/board_kit/predictions_v5_board.csv (the rows of the hashed prediction file; label modelled).
The hashed file docs/PREDICTIONS_V5_BOARD.md is read only to confirm its SHA-256; it is never
changed. The rules applied are those registered in that file:
  verdict per row: hit if the board mean of all iterations of all power cycles of the caches off
      image lies inside the registered interval, miss otherwise;
  rule 3: a row counts only if its logs show cache_pass,off (check
      cache_pass_off:image_matches_firmware), cache_off_applied,1 (check
      cache_pass_off:writes_applied_at_zero_wait_states) and flash_ws,0 (result rows); a log
      that fails any of them is left out, and if no row of a board can be measured that way the
      rules are not applied for that board (check of conditions only);
  rule 1: refuted for a board if more than a third of its registered rows miss (more than 6 of 18);
  rule 2: refuted for a board if more than four fifths of the signed errors (board mean minus
      prediction) share one sign (more than 14 of 18);
  rule 4: a refutation on NUCLEO-L552ZE-Q means the Cortex-M4 model does not transfer to that
      Cortex-M33 board; it is reported separately and does not refute the model on the Cortex-M4
      board.
The thresholds are the registered counts (6 and 14 of 18); when fewer rows can be scored the counts
are still compared with them, and the board summary says how many rows were scored.
With no board measured rows (for example the emulated dry run) every row is 'not scored'.

Output CSV (--out): one row per prediction row, then one summary row per board. Value columns
carry their label as a suffix (cycles_modelled, cycles_board_measured_mean); verdict columns are
derived from both and say so.
"""
import argparse
import csv
import hashlib
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import kit_config as K  # noqa: E402

PREDICTIONS = os.path.join(HERE, "predictions_v5_board.csv")
REGISTERED = os.path.join(REPO, "docs", "PREDICTIONS_V5_BOARD.md")
MISS_LIMIT = 6  # rule 1: more than 6 of 18 misses refutes
SIGN_LIMIT = 14  # rule 2: more than 14 of 18 errors of one sign refutes
RULE3_CHECKS = ("cache_pass_off:image_matches_firmware",
                "cache_pass_off:writes_applied_at_zero_wait_states")
COLUMNS = ["kind", "id", "board", "platform", "parameter_set", "operation", "cycles_modelled",
           "interval_lo_modelled", "interval_hi_modelled", "n_logs_board_measured",
           "n_logs_excluded_rule3", "n_values_board_measured", "cycles_board_measured_mean",
           "cycles_board_measured_median", "cycles_board_measured_sd",
           "signed_error_board_measured_minus_modelled", "verdict", "rows_registered",
           "rows_scored", "misses", "errors_positive", "errors_negative", "rule1", "rule2",
           "rule3", "rule4", "board_verdict"]


def read_csv(path):
    with open(path, newline="") as fh:
        return list(csv.DictReader(fh))


def file_sha256(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def registered_hash_ok(md=REGISTERED):
    """True if docs/PREDICTIONS_V5_BOARD.md matches its committed hash file."""
    try:
        with open(md + ".sha256") as fh:
            want = fh.read().split()[0]
    except OSError:
        return False
    return file_sha256(md) == want


def rule3_logs(checks):
    """source_log names whose caches off checks all passed (rule 3, from the checks CSV)."""
    seen, bad = {}, set()
    for c in checks:
        if c.get("check") in RULE3_CHECKS:
            seen.setdefault(c["source_log"], set()).add(c["check"])
            if int(c.get("fail") or 0) or not int(c.get("ok") or 0):
                bad.add(c["source_log"])
    return {log for log, got in seen.items() if set(RULE3_CHECKS) <= got and log not in bad}


def score_rows(results, checks, predictions):
    good_logs = rule3_logs(checks)
    out = []
    for p in predictions:
        plat = p["platform"]
        cand = [r for r in results if r.get("label") == "board measured"
                and K.board_platform(r.get("board")) == plat
                and (r.get("cache_pass") or "on") == "off"
                and r.get("scheme", "").upper() == p["parameter_set"].upper()
                and r.get("operation") == p["operation"] and r.get("cycles") not in ("", None)]
        logs = {r["source_log"] for r in cand}
        ok = [r for r in cand if r["source_log"] in good_logs and str(r.get("flash_ws")) == "0"]
        ok_logs = {r["source_log"] for r in ok}
        row = dict.fromkeys(COLUMNS, "")
        row.update(kind="prediction", id=p["id"], board=p["board"], platform=plat,
                   parameter_set=p["parameter_set"], operation=p["operation"],
                   cycles_modelled=p["cycles_modelled"], interval_lo_modelled=p["interval_lo_modelled"],
                   interval_hi_modelled=p["interval_hi_modelled"], n_logs_board_measured=len(ok_logs),
                   n_logs_excluded_rule3=len(logs - ok_logs), n_values_board_measured=len(ok))
        if p.get("counts_toward_refutation") != "yes":
            row["verdict"] = "not counted (registered as not counting)"
        elif not ok:
            row["verdict"] = ("not scored: no board measured caches off values" if not cand
                              else "not scored: no log meets rule 3")
        else:
            v = [float(r["cycles"]) for r in ok]
            mean = statistics.fmean(v)
            lo, hi = float(p["interval_lo_modelled"]), float(p["interval_hi_modelled"])
            row.update(cycles_board_measured_mean=f"{mean:.0f}",
                       cycles_board_measured_median=f"{statistics.median(v):.0f}",
                       cycles_board_measured_sd=f"{statistics.stdev(v):.0f}" if len(v) > 1 else "",
                       signed_error_board_measured_minus_modelled=f"{mean - float(p['cycles_modelled']):.0f}",
                       verdict="hit" if lo <= mean <= hi else "miss")
        out.append(row)
    return out


def board_summaries(rows):
    out = []
    for plat in [pl for pl in K.PLATFORMS if any(r["platform"] == pl for r in rows)]:
        br = [r for r in rows if r["platform"] == plat]
        counted = [r for r in br if not r["verdict"].startswith("not counted")]
        scored = [r for r in counted if r["verdict"] in ("hit", "miss")]
        miss = sum(1 for r in scored if r["verdict"] == "miss")
        errs = [float(r["signed_error_board_measured_minus_modelled"]) for r in scored]
        pos, neg = sum(1 for e in errs if e > 0), sum(1 for e in errs if e < 0)
        s = dict.fromkeys(COLUMNS, "")
        s.update(kind="board summary", board=br[0]["board"], platform=plat,
                 rows_registered=len(counted), rows_scored=len(scored))
        if not scored:
            s.update(rule3="not applied: no row measured with caches off at zero wait states",
                     board_verdict="not scored (check of conditions only)")
            out.append(s)
            continue
        r1 = miss > MISS_LIMIT
        r2 = max(pos, neg) > SIGN_LIMIT
        s.update(misses=miss, errors_positive=pos, errors_negative=neg,
                 rule1=f"{'refuted' if r1 else 'not refuted'}: {miss} misses (limit more than {MISS_LIMIT})",
                 rule2=(f"{'refuted' if r2 else 'not refuted'}: {max(pos, neg)} errors of one sign "
                        f"(limit more than {SIGN_LIMIT})"),
                 rule3=f"applied: {len(scored)} of {len(counted)} rows scored")
        refuted = r1 or r2
        if plat == K.M33_PLATFORM:
            s["rule4"] = ("Cortex-M33 board: a refutation here means the Cortex-M4 model does not "
                          "transfer to this board; it does not refute the model on the Cortex-M4 board")
            s["board_verdict"] = ("Cortex-M4 model does not transfer" if refuted
                                  else "transfer not refuted")
        else:
            s["board_verdict"] = "model refuted" if refuted else "model not refuted"
        if len(scored) < len(counted):
            s["board_verdict"] += f" (partial: {len(scored)} of {len(counted)} rows scored)"
        out.append(s)
    return out


def score(results, checks, predictions):
    rows = score_rows(results, checks, predictions)
    return rows + board_summaries(rows)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("results", nargs="+", help="result CSV files from parse.py")
    ap.add_argument("--checks", action="append", default=[], help="checks CSV from parse.py")
    ap.add_argument("--predictions", default=PREDICTIONS)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    if not registered_hash_ok():
        print("warning: docs/PREDICTIONS_V5_BOARD.md does not match its .sha256 file", file=sys.stderr)
    results = [r for p in a.results for r in read_csv(p)]
    checks = [c for p in a.checks for c in read_csv(p)]
    rows = score(results, checks, read_csv(a.predictions))
    with open(a.out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    for s in (r for r in rows if r["kind"] == "board summary"):
        print(f"{s['platform']}: {s['board_verdict']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
