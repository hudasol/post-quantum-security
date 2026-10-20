#!/usr/bin/env python3
"""Dry run of the whole board kit pipeline on emulator output (label: emulated).

Author: Huda Mueen. Runs every mps2-an386 image built by build_b0.py and build_b1.py in
qemu-system-arm, streams its output through capture.py (the same code path as a serial capture),
parses every log with parse.py, requires that 100 percent of lines are recognised and no check
fails, runs compare.py, and writes DRY_RUN.md plus small summary CSVs into bench/board_kit/dry_run/.
Raw logs and the full per iteration result CSV stay outside the repository (OUT_DIR/dry_run/).
QEMU cycle values are meaningless: they are labelled emulated and compare.py excludes them from
every cycle comparison. This run only proves the pipeline.
"""
import argparse
import csv
import datetime as dt
import glob
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kit_config as K  # noqa: E402
import capture  # noqa: E402
import parse  # noqa: E402
import compare  # noqa: E402

QEMU = ["qemu-system-arm", "-M", "mps2-an386", "-nographic", "-semihosting", "-kernel"]


def run_image(elf, run_id, experiment, logdir, timeout=900):
    name = os.path.splitext(os.path.basename(elf))[0]
    out = os.path.join(logdir, f"run{run_id}_{name}.log")
    meta = {"version": "1", "source": "qemu-system-arm mps2-an386 (stdout pipe)",
            "start_utc": capture.utc_now(), "experiment": experiment, "image": name,
            "run": run_id, "label": "emulated", "board": "QEMU mps2-an386", "note": "dry run"}
    p = subprocess.Popen(QEMU + [elf], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    with open(out, "w") as fh:
        n, reason = capture.capture_lines(p.stdout, fh, meta)
    try:
        rc = p.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        p.kill()
        rc = "timeout"
    return out, n, reason, rc


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--out", default=os.path.join(K.OUT_DIR, "dry_run"))
    ap.add_argument("--summary", default=os.path.join(HERE, "dry_run"))
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    os.makedirs(a.summary, exist_ok=True)
    for f in glob.glob(os.path.join(a.out, "*.log")):
        os.remove(f)
    base = os.path.join(K.OUT_DIR, "mps2-an386")
    images = [(e, "B0") for e in sorted(glob.glob(os.path.join(base, "b0", "*.elf")))]
    images += [(e, "B1") for e in sorted(glob.glob(os.path.join(base, "b1", "b1_*.elf")))]
    started = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    caps = []
    for run_id in range(1, a.runs + 1):
        for elf, exp in images:
            log, n, reason, rc = run_image(elf, run_id, exp, a.out)
            caps.append({"log": os.path.basename(log), "experiment": exp, "run": run_id,
                         "lines": n, "end": reason, "qemu_rc": rc})
    rows, checks, total, bad = [], [], 0, 0
    per_log = []
    for c in caps:
        r = parse.parse_log(os.path.join(a.out, c["log"]))
        rows += r["rows"]
        checks += r["checks"]
        total += r["n_lines"]
        bad += r["n_unrecognised"]
        per_log.append(dict(c, parsed_lines=r["n_lines"], unrecognised=r["n_unrecognised"],
                            rows=len(r["rows"])))
    full = os.path.join(a.out, "dry_run_results.csv")
    parse.write_csv(full, parse.RESULT_COLUMNS, rows)
    parse.write_csv(os.path.join(a.summary, "dry_run_checks.csv"), parse.CHECK_COLUMNS, checks)
    cmp_rows = compare.compare(rows, compare.read_csv(compare.EVIDENCE),
                               compare.optional_rows(compare.PREDICTIONS, "modelled"),
                               compare.optional_rows(compare.find_rtl(None), "RTL simulated"))
    with open(os.path.join(a.summary, "dry_run_compare.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=compare.COLUMNS)
        w.writeheader()
        w.writerows(cmp_rows)
    with open(os.path.join(a.summary, "dry_run_logs.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["label"] + list(per_log[0].keys()))
        w.writeheader()
        w.writerows([dict(p, label="emulated") for p in per_log])
    qemu_v = subprocess.run(["qemu-system-arm", "--version"], capture_output=True,
                            text=True).stdout.splitlines()[0]
    summary = {"started_utc": started, "qemu": qemu_v, "runs": a.runs, "images": len(images),
               "logs": len(caps), "lines": total, "unrecognised": bad,
               "recognised_percent": 100.0 * (total - bad) / total if total else 0.0,
               "result_rows": len(rows), "check_rows": len(checks),
               "failed_checks": sum(int(c["fail"]) for c in checks),
               "ok_checks": sum(int(c["ok"]) for c in checks),
               "ends": sorted({c["end"] for c in caps}),
               "qemu_rc": sorted({str(c["qemu_rc"]) for c in caps}),
               "compare_groups": len(cmp_rows),
               "cycles_compared": sum(1 for r in cmp_rows if r["cycles_status"] == "compared"),
               "cycles_excluded": sum(1 for r in cmp_rows
                                      if r["cycles_status"].startswith("excluded")),
               "published_matched": sum(1 for r in cmp_rows if r["published_id"]),
               "predictions_file": os.path.exists(compare.PREDICTIONS)}
    with open(os.path.join(a.summary, "dry_run_summary.json"), "w") as fh:
        json.dump(summary, fh, indent=1)
    write_md(os.path.join(HERE, "DRY_RUN.md"), summary, cmp_rows)
    print(json.dumps(summary, indent=1))
    ok = bad == 0 and summary["failed_checks"] == 0 and summary["ends"] == ["marker"]
    return 0 if ok else 1


def previous_harness_stack():
    path = os.path.join(os.path.dirname(os.path.dirname(HERE)), "bench", "mcu", "qemu_results",
                        "stack.csv")
    out = {}
    if os.path.exists(path):
        for r in compare.read_csv(path):
            if r["board"] == "an386" and r["opt"] == "-O2":
                out[(r["param"], r["op"])] = r["stack_bytes"]
    return out


def write_md(path, s, cmp_rows):
    stack = [r for r in cmp_rows if r["experiment"] == "B0" and r["stack_emulated"] != ""]
    b1stack = [r for r in cmp_rows if r["experiment"] == "B1" and r["stack_emulated"] != ""]
    L = ["# Board kit dry run on emulator output", "",
         "Author: Huda Mueen. Generated by `bench/board_kit/run_dry_run.py`; do not edit by hand.",
         f"Label of every number in this file: **emulated** (QEMU mps2-an386), except columns "
         f"marked published. Run started {s['started_utc']}; {s['qemu']}; seed for the bootstrap in "
         f"compare.py: {compare.SEED} (not used here because no cycles are compared).", "",
         "## Purpose", "",
         "This run proves that the board session pipeline works end to end before a board is "
         "borrowed: build (pqm4 images and the harness through pqm4's platform layer), run, "
         "capture, parse, compare. It proves nothing about cycle counts. QEMU does not model the "
         "core clock, flash wait states or caches; its SysTick and DWT values are not cycle counts. "
         "They are labelled emulated and compare.py excludes them from every cycle comparison.", "",
         "## Pipeline result", "",
         "| Item | Value |", "|---|---|",
         f"| Images run (B0 pqm4 test, speed and stack; B1 harness) | {s['images']} |",
         f"| Runs per image (stand in for power cycles) | {s['runs']} |",
         f"| Raw logs captured | {s['logs']} |",
         f"| Capture end reasons | {', '.join(s['ends'])} |",
         f"| QEMU exit codes | {', '.join(s['qemu_rc'])} |",
         f"| Output lines parsed | {s['lines']} |",
         f"| Unrecognised lines | {s['unrecognised']} |",
         f"| Lines recognised | {s['recognised_percent']:.1f} percent |",
         f"| Result rows written | {s['result_rows']} |",
         f"| Correctness checks passed / failed | {s['ok_checks']} / {s['failed_checks']} |",
         f"| Comparison groups | {s['compare_groups']} |",
         f"| Groups with cycles compared | {s['cycles_compared']} |",
         f"| Groups with emulated cycles excluded | {s['cycles_excluded']} |",
         f"| Groups matched to a published evidence row | {s['published_matched']} |",
         f"| Modelled predictions file present | {'yes' if s['predictions_file'] else 'no'} |",
         "",
         "## Stack: B0 emulated against published (stack is not a cycle count)", "",
         "| Scheme | Variant | Operation | stack_emulated (bytes) | stack_published (bytes) | "
         "Evidence id |", "|---|---|---|---|---|---|"]
    for r in stack:
        L.append(f"| {r['scheme']} | {r['variant']} | {r['operation']} | {r['stack_emulated']} | "
                 f"{r['stack_published']} | {r['published_id']} |")
    same = sum(1 for r in stack if str(r["stack_emulated"]) == str(r["stack_published"]))
    diff = [r for r in stack if str(r["stack_emulated"]) != str(r["stack_published"])]
    L += ["", f"{same} of {len(stack)} B0 stack values from QEMU equal the published pqm4 value "
          "byte for byte. This checks that the same pqm4 code and stack method were built; it says "
          "nothing about cycles. The toolchain differs from the one pqm4 names for its results "
          "(see build_log.md)."]
    for r in diff:
        L.append(f"Difference: {r['scheme']} {r['variant']} {r['operation']}: "
                 f"{int(r['stack_emulated']) - int(r['stack_published'])} bytes (emulated minus "
                 f"published, {r['published_id']}); a compiler version effect is the likely "
                 "reason but was not tested.")
    prev = previous_harness_stack()
    L += ["", "## Stack: B1 harness through the pqm4 platform layer (emulated)", "",
          "The last column is the earlier emulated run with the repository's own QEMU start up "
          "files (`bench/mcu/qemu_results/stack.csv`, an386, -O2). Small differences are expected: "
          "the kit build uses pqm4's flags (gnu99, -g3, pqm4 HAL) instead.", "",
          "| Scheme | Operation | stack_emulated, kit (bytes) | stack_emulated, earlier run (bytes) |",
          "|---|---|---|---|"]
    for r in b1stack:
        L.append(f"| {r['scheme']} | {r['operation']} | {r['stack_emulated']} | "
                 f"{prev.get((r['scheme'], r['operation']), 'not found')} |")
    L += ["", "## Files", "",
          "- `dry_run/dry_run_summary.json`: the numbers in the first table.",
          "- `dry_run/dry_run_logs.csv`: one row per raw log (lines, end reason, rows).",
          "- `dry_run/dry_run_checks.csv`: correctness checks per log.",
          "- `dry_run/dry_run_compare.csv`: compare.py output (emulated cycles excluded).",
          "- Raw logs and the per iteration CSV stay outside the repository under the work "
          "directory (`board_kit_out/dry_run/`).", ""]
    with open(path, "w") as fh:
        fh.write("\n".join(L))


if __name__ == "__main__":
    sys.exit(main())
