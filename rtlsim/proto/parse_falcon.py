#!/usr/bin/env python3
"""Round 7: summarise the Falcon-512 per command runs on Ibex and CV32E40P and compare them with ML-DSA-44 per command.

Reads rtlsim/results/logs/proto_r7/<core>/ (logs, size files, build information) and, for the comparison, the round 6
logs of the ML-DSA-44 per command image (rtlsim/results/logs/proto/<core>/per_command_mldsa44.log), which are not
changed. Writes:
  rtlsim/results/proto_falcon.csv          one row per core and operation (label RTL simulated; sizes host measured)
  rtlsim/results/proto_falcon_ratios.csv   Falcon-512 over ML-DSA-44 per command and Ibex over CV32E40P, medians with
                                           bootstrap intervals (label RTL simulated)
  docs/RTL_FALCON_R7.md                    the study section
The Falcon-512 key pair is made once per image (one run of provisioning_keypair); signing and verification run
PROTO_RUNS times with the round 6 seed block. Author: Huda Mueen.
"""
import csv
import os
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import parse_proto as pp  # noqa: E402

CORES = ["ibex", "cv32e40p"]
CORE_NAME = {"ibex": "Ibex (small)", "cv32e40p": "CV32E40P"}
SET = "per_command_falcon512"
MLDSA_SET = "per_command_mldsa44"
LOGS7 = ROOT / "rtlsim" / "results" / "logs" / "proto_r7"
LOGS6 = ROOT / "rtlsim" / "results" / "logs" / "proto"
RES = ROOT / "rtlsim" / "results"
OPS = [("provisioning_keypair", "ground", "key pair, made once per image"),
       ("ground_sign_command", "ground", "sign one COMMAND_LONG frame (44 B)"),
       ("vehicle_verify_command", "vehicle", "verify one COMMAND_LONG frame (44 B)")]
LABEL = "RTL simulated"


def build_info(core):
    out = {}
    p = LOGS7 / core / "build_info.txt"
    if p.exists():
        for line in p.read_text().splitlines():
            k, _, v = line.partition("=")
            out[k] = v
    return out


def sizes(core, variant):
    sec = pp.read_size_sections(LOGS7 / core / f"sections_{variant}.txt")
    return pp.image_sizes(sec.get(SET, {}))


def mldsa_sizes(core, variant):
    sec = pp.read_size_sections(LOGS6 / core / f"sections_{variant}.txt")
    return pp.image_sizes(sec.get(MLDSA_SET, {}))


def mldsa_bytes():
    with open(RES / "proto_sessions.csv", newline="", encoding="utf-8") as fh:
        r = next(x for x in csv.DictReader(fh) if x["design"] == MLDSA_SET and x["side"] == "vehicle")
    sig = r["bytes_per_flight"].split(";")[1].split()[-1]
    return f"{r['bytes_total']} B ({sig} B signature)"


def load():
    logs, ml = {}, {}
    for core in CORES:
        p = LOGS7 / core / f"{SET}.log"
        if p.exists() and p.stat().st_size:
            logs[core] = pp.parse_file(p)
        q = LOGS6 / core / f"{MLDSA_SET}.log"
        if q.exists():
            ml[core] = pp.parse_file(q)
    return logs, ml


def rows_falcon(logs, ml):
    rows = []
    for core in CORES:
        lg = logs.get(core)
        if lg is None:
            continue
        summ = {r["operation"]: r for r in pp.op_summary(lg)}
        ms = {r["operation"]: r for r in pp.op_summary(ml[core])} if core in ml else {}
        passed, total = pp.checks_for(lg, SET)
        fl = pp.flights(lg, SET)
        st, sg = sizes(core, "timing"), sizes(core, "gc")
        for op, side, what in OPS:
            if op not in summ:
                continue
            s = summ[op]
            m = ms.get(op if op != "provisioning_keypair" else "", None)
            rows.append({
                "label": LABEL, "core": core, "design": SET, "operation": op, "side": side, "what": what,
                "cycles_median": s["median"], "cycles_ci95_low": s["ci_low"], "cycles_ci95_high": s["ci_high"],
                "cycles_min": s["min"], "cycles_max": s["max"], "n_runs": s["n"],
                "peak_stack_bytes": s["stack_max"], "stack_saturated": s["stack_saturated"],
                "calls_succeeded": s["ok"], "checks_passed": passed, "checks_total": total,
                "log_complete": lg.done, "seed_first": lg.config.get("seed_first", ""),
                "bytes_per_command": sum(b for _, _, b in fl),
                "signature_bytes": next((b for f, _, b in fl if f == "command_signature"), ""),
                "text_bytes_host_measured": st["text"], "data_bytes_host_measured": st["data"],
                "bss_bytes_host_measured": st["bss"], "text_bytes_gc_host_measured": sg["text"],
                "mldsa44_cycles_median": m["median"] if m else "",
                "mldsa44_peak_stack_bytes": m["stack_max"] if m else "",
            })
    return rows


def ratio(a, b):
    lo, hi = pp.bootstrap_ratio_ci(a, b)
    return statistics.median(a) / statistics.median(b), lo, hi


def rows_ratios(logs, ml):
    out = []
    for core in CORES:
        if core not in logs or core not in ml:
            continue
        for op in ("ground_sign_command", "vehicle_verify_command"):
            a = list(pp.run_values(logs[core], SET, op).values())
            b = list(pp.run_values(ml[core], MLDSA_SET, op).values())
            if a and b:
                v, lo, hi = ratio(a, b)
                out.append({"label": LABEL, "comparison": "Falcon-512 over ML-DSA-44 per command", "core": core,
                            "operation": op, "ratio": round(v, 4), "ci95_low": round(lo, 4), "ci95_high": round(hi, 4),
                            "n_numerator": len(a), "n_denominator": len(b)})
    if all(c in logs for c in CORES):
        for op in ("ground_sign_command", "vehicle_verify_command"):
            a = list(pp.run_values(logs["ibex"], SET, op).values())
            b = list(pp.run_values(logs["cv32e40p"], SET, op).values())
            if a and b:
                v, lo, hi = ratio(a, b)
                out.append({"label": LABEL, "comparison": "Ibex over CV32E40P, Falcon-512", "core": "ibex/cv32e40p",
                            "operation": op, "ratio": round(v, 4), "ci95_low": round(lo, 4), "ci95_high": round(hi, 4),
                            "n_numerator": len(a), "n_denominator": len(b)})
    return out


def write_csv(path, rows):
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def fi(x):
    return f"{int(round(float(x))):,}"


def write_doc(rows, ratios, logs):
    bi = build_info("ibex")
    L = ["# Falcon-512 per command on the RTL cores (round 7)", "",
         "Author: Huda Mueen. Generated by `rtlsim/proto/parse_falcon.py` from the logs in "
         "`rtlsim/results/logs/proto_r7/`; do not edit by hand. Label: RTL simulated (cycle accurate Verilator "
         "simulation of open RISC-V cores, never Arm silicon); sizes are host measured.", "",
         "## What was run", "",
         "The per command design of round 6 (`docs/RTL_BASELINES.md`) with the padded Falcon-512 signature (fixed "
         "666 B) in place of ML-DSA-44: the ground signs each MAVLink 2 COMMAND_LONG frame and the vehicle verifies it. "
         f"Library: the padded Falcon-512 folder of liboqs tag {bi.get('liboqs_tag', '').split()[0] if bi.get('liboqs_tag') else '0.16.0'} "
         "(`rtlsim/proto/config.sh`), a copy of PQClean that is identical to PQClean master of 2026-08-04 apart from "
         "build files. Both cores are RV32IMC without a floating point unit. Falcon signing and key generation need "
         "floating point arithmetic; the pinned clean implementation emulates it with 64 bit integer arithmetic "
         "(its `fpr` type), which is the build used here; no hardware floating point build was possible on these "
         "cores. SHAKE256 comes from mldsa-native, as for the other designs; "
         "`rtlsim/proto/check_falcon_shim.sh` shows that one key pair and five signatures are byte identical to "
         "those made with the SHAKE256 that PQClean ships "
         "(`rtlsim/results/logs/proto_r7/falcon_shim_check.txt`). Compiler, flags, start up code, stack size and "
         "the stack painting are those of round 6. The key pair is made once per image (one run), because Falcon "
         "key generation is far more expensive than signing; signing and verification run "
         f"{rows[0]['n_runs'] if rows else ''} times with the round 6 seed block, and run 0 also checks that a "
         "modified command and a modified signature are rejected.", "",
         "## Cycles, stack and size", "",
         "| core | operation | cycles (median) | 95 percent interval | min to max | runs | peak stack (B) | "
         "ML-DSA-44 cycles (round 6) | ML-DSA-44 stack (B) |",
         "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        L.append(f"| {CORE_NAME[r['core']]} | {r['operation']} | {fi(r['cycles_median'])} | "
                 f"{fi(r['cycles_ci95_low'])} to {fi(r['cycles_ci95_high'])} | {fi(r['cycles_min'])} to "
                 f"{fi(r['cycles_max'])} | {r['n_runs']} | {fi(r['peak_stack_bytes'])} | "
                 f"{fi(r['mldsa44_cycles_median']) if r['mldsa44_cycles_median'] != '' else 'not applicable'} | "
                 f"{fi(r['mldsa44_peak_stack_bytes']) if r['mldsa44_peak_stack_bytes'] != '' else 'not applicable'} |")
    L += ["", "Correctness: " + "; ".join(
        f"{CORE_NAME[c]}: calls succeeded in every run "
        f"{'yes' if all(r['calls_succeeded'] == r['n_runs'] for r in rows if r['core'] == c) else 'no'}, "
        f"checks passed {next(r['checks_passed'] for r in rows if r['core'] == c)} of "
        f"{next(r['checks_total'] for r in rows if r['core'] == c)}, log complete "
        f"{next(r['log_complete'] for r in rows if r['core'] == c)}" for c in CORES if any(r['core'] == c for r in rows))
        + ".", "",
        "Bytes per command on the link: " + ", ".join(sorted({f"{r['bytes_per_command']} B (44 B frame and "
                                                               f"{r['signature_bytes']} B signature)" for r in rows}))
        + f"; ML-DSA-44 per command needs {mldsa_bytes()} (`rtlsim/results/proto_sessions.csv`).", "",
        "Image size (host measured, text including read only data): " + "; ".join(
            f"{CORE_NAME[c]} {fi(r['text_bytes_host_measured'])} B, {fi(r['text_bytes_gc_host_measured'])} B "
            "with unused code removed" for c in CORES for r in rows[:len(rows)] if r['core'] == c
            and r['operation'] == 'vehicle_verify_command') + ". The image holds key generation, signing and "
        "verification; a vehicle image needs verification only, which this study did not build separately.", "",
        "## Ratios", "",
        "| comparison | core | operation | ratio of medians | 95 percent interval | runs |", "|---|---|---|---|---|---|"]
    for r in ratios:
        L.append(f"| {r['comparison']} | {r['core']} | {r['operation']} | {r['ratio']:.3f} | {r['ci95_low']:.3f} to "
                 f"{r['ci95_high']:.3f} | {r['n_numerator']} and {r['n_denominator']} |")
    L += ["", "Intervals: percentile bootstrap of the ratio of two medians, the two samples resampled independently "
          "(`rtlsim/proto/parse_proto.py`).", ""]
    (ROOT / "docs" / "RTL_FALCON_R7.md").write_text("\n".join(L), encoding="utf-8")


def main():
    logs, ml = load()
    rows = rows_falcon(logs, ml)
    ratios = rows_ratios(logs, ml)
    write_csv(RES / "proto_falcon.csv", rows)
    write_csv(RES / "proto_falcon_ratios.csv", ratios)
    if rows:
        write_doc(rows, ratios, logs)
    print(f"{len(rows)} rows, {len(ratios)} ratios")
    return 0 if rows else 1


if __name__ == "__main__":
    sys.exit(main())
