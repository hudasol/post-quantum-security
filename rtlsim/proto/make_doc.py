#!/usr/bin/env python3
"""Build the round 6 protocol baseline results and docs/RTL_BASELINES.md from the simulation logs.

Author: Huda Mueen. Reads rtlsim/results/logs/proto/<core>/<image>.log, the section sizes written by
rtlsim/proto/build.sh, the round 5 cycle tables (rtlsim/results/<core>_cycles.csv) and
data/shared_inputs.csv. Writes:
  rtlsim/results/proto_primitives.csv      each primitive alone (label RTL simulated)
  rtlsim/results/proto_sessions.csv        per design and side (cycles, stack: RTL simulated; sizes: see
                                           data/column_labels.csv)
  rtlsim/results/proto_sizes.csv           text, data, bss of every image (label host measured)
  rtlsim/results/proto_time_estimated.csv  cycles divided by a stated clock (label estimated)
  rtlsim/results/proto_decomposition.csv   each session design and side against the sum of its primitive
                                           medians (label RTL simulated)
  rtlsim/results/proto_ratios.csv          ratios between session designs, from the session medians with a
                                           bootstrap interval and from the primitive sums (label RTL simulated)
and reads, without changing them, the frozen five run snapshots of round 6
(rtlsim/results/proto_sessions_runs5.csv, rtlsim/results/proto_primitives_runs5.csv).
  docs/figures/rtl_baselines_vehicle.png   vehicle side cycles per design and core
  docs/RTL_BASELINES.md
Usage: python3 rtlsim/proto/make_doc.py
"""
import csv
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RTL = HERE.parent
ROOT = RTL.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(RTL))
import parse_proto as pp  # noqa: E402

LABEL = "RTL simulated"
CORES = ["ibex", "cv32e40p"]
CORE_NAME = {"ibex": "Ibex (small)", "cv32e40p": "CV32E40P"}
IMAGES = ["primitives", "classical", "pq_only", "hybrid_f1", "kem_auth", "per_command_mldsa44", "mavlink_tag"]
SESSION_DESIGNS = ["classical", "pq_only", "hybrid_f1", "kem_auth"]
DESIGN_NAME = {
    "classical": "Classical session (X25519, Ed25519 by both sides, key confirmation)",
    "pq_only": "Post quantum only session (ML-KEM-768, ML-DSA-44 by both sides, key confirmation)",
    "hybrid_f1": "Hybrid session with F1 (X25519 plus ML-KEM-768, ML-DSA-44 by both sides, key confirmation)",
    "kem_auth": ("KEM authenticated session (X25519 plus ML-KEM-768, static ML-KEM-768 keys pinned at the "
                 "other side, no signatures, key confirmation)"),
    "per_command_mldsa44": "ML-DSA-44 signature per command",
    "mavlink_tag": "MAVLink 2 signing tag per message",
}
CLOCKS_MHZ = [64, 168]
PRIM_ORDER = ["x25519_keygen", "x25519_shared", "ed25519_keygen", "ed25519_sign", "ed25519_verify",
              "sha256_60B", "mavlink_tag_frame60", "shake256_kdf", "shake256_confirm_tag",
              "shake256_transcript_hybrid", "shake256_transcript_classical", "shake256_transcript_pq_only",
              "shake256_transcript_kem_auth", "shake256_kdf_kem_auth", "mlkem768_keygen", "mlkem768_encaps",
              "mlkem768_decaps", "mldsa44_keygen", "mldsa44_sign", "mldsa44_verify"]
PRIM_INFO = {
    "x25519_keygen": ("Monocypher", "public key from a 32 B secret (crypto_x25519_public_key)"),
    "x25519_shared": ("Monocypher", "shared secret, one scalar multiplication (crypto_x25519)"),
    "ed25519_keygen": ("Monocypher", "key pair from a 32 B seed (crypto_ed25519_key_pair)"),
    "ed25519_sign": ("Monocypher", "97 B input (crypto_ed25519_sign)"),
    "ed25519_verify": ("Monocypher", "97 B input (crypto_ed25519_check)"),
    "sha256_60B": ("MAVLink C library", "60 B input, 48 bit output (mavlink_sha256)"),
    "mavlink_tag_frame60": ("MAVLink C library", "mavlink_sign_packet over a 60 B frame, fixed fields"),
    "shake256_kdf": ("mldsa-native FIPS 202", "session key derivation over 3 x 32 B plus label"),
    "shake256_confirm_tag": ("mldsa-native FIPS 202", "16 B key confirmation tag"),
    "shake256_transcript_hybrid": ("mldsa-native FIPS 202", "transcript hash over F1 and F2 of the hybrid design (2,336 B)"),
    "shake256_transcript_classical": ("mldsa-native FIPS 202", "transcript hash over F1 and F2 of the classical design (64 B)"),
    "shake256_transcript_pq_only": ("mldsa-native FIPS 202", "transcript hash over F1 and F2 of the post quantum only design (2,272 B)"),
    "shake256_transcript_kem_auth": ("mldsa-native FIPS 202", "transcript hash over both identities, F1 and F2 without its tag, KEM authenticated design (4,576 B)"),
    "shake256_kdf_kem_auth": ("mldsa-native FIPS 202", "session key derivation over 5 x 32 B plus label (KEM authenticated design)"),
    "mlkem768_keygen": ("mlkem-native", "keypair"),
    "mlkem768_encaps": ("mlkem-native", "enc"),
    "mlkem768_decaps": ("mlkem-native", "dec"),
    "mldsa44_keygen": ("mldsa-native", "keypair"),
    "mldsa44_sign": ("mldsa-native", "97 B input, empty context"),
    "mldsa44_verify": ("mldsa-native", "97 B input, empty context"),
}
ROUND5 = {"mlkem768_keygen": ("ML-KEM-768", "keygen"), "mlkem768_encaps": ("ML-KEM-768", "encaps"),
          "mlkem768_decaps": ("ML-KEM-768", "decaps"), "mldsa44_keygen": ("ML-DSA-44", "keygen"),
          "mldsa44_sign": ("ML-DSA-44", "sign"), "mldsa44_verify": ("ML-DSA-44", "verify")}
# Primitive calls that make up each side of one session start (see rtlsim/proto/sw/proto_bench.c). Glue
# outside these calls (random bytes for the X25519 secrets, copies, comparisons, the signed input) is left
# in the residual. The signature primitives were timed over the 97 B signed input of the session designs.
DECOMP = {
    "classical": {
        "vehicle": [("x25519_keygen", 1), ("x25519_shared", 1), ("shake256_transcript_classical", 1),
                    ("shake256_kdf", 1), ("ed25519_verify", 1), ("shake256_confirm_tag", 2), ("ed25519_sign", 1)],
        "ground": [("x25519_keygen", 1), ("x25519_shared", 1), ("shake256_transcript_classical", 1),
                   ("shake256_kdf", 1), ("ed25519_sign", 1), ("shake256_confirm_tag", 2), ("ed25519_verify", 1)]},
    "pq_only": {
        "vehicle": [("mlkem768_encaps", 1), ("shake256_transcript_pq_only", 1), ("shake256_kdf", 1),
                    ("mldsa44_verify", 1), ("shake256_confirm_tag", 2), ("mldsa44_sign", 1)],
        "ground": [("mlkem768_keygen", 1), ("mlkem768_decaps", 1), ("shake256_transcript_pq_only", 1),
                   ("shake256_kdf", 1), ("mldsa44_sign", 1), ("shake256_confirm_tag", 2), ("mldsa44_verify", 1)]},
    "hybrid_f1": {
        "vehicle": [("x25519_keygen", 1), ("x25519_shared", 1), ("mlkem768_encaps", 1),
                    ("shake256_transcript_hybrid", 1), ("shake256_kdf", 1), ("mldsa44_verify", 1),
                    ("shake256_confirm_tag", 2), ("mldsa44_sign", 1)],
        "ground": [("x25519_keygen", 1), ("mlkem768_keygen", 1), ("x25519_shared", 1), ("mlkem768_decaps", 1),
                   ("shake256_transcript_hybrid", 1), ("shake256_kdf", 1), ("mldsa44_sign", 1),
                   ("shake256_confirm_tag", 2), ("mldsa44_verify", 1)]},
    "kem_auth": {
        "vehicle": [("x25519_keygen", 1), ("x25519_shared", 1), ("mlkem768_decaps", 1), ("mlkem768_encaps", 2),
                    ("shake256_transcript_kem_auth", 1), ("shake256_kdf_kem_auth", 1), ("shake256_confirm_tag", 2)],
        "ground": [("x25519_keygen", 1), ("mlkem768_keygen", 1), ("mlkem768_encaps", 1), ("x25519_shared", 1),
                   ("mlkem768_decaps", 2), ("shake256_transcript_kem_auth", 1), ("shake256_kdf_kem_auth", 1),
                   ("shake256_confirm_tag", 2)]},
}
RATIO_PAIRS = [("hybrid_f1", "classical"), ("pq_only", "classical"), ("hybrid_f1", "pq_only"),
               ("kem_auth", "classical"), ("kem_auth", "hybrid_f1"), ("kem_auth", "pq_only")]
SNAPSHOT_SESSIONS = "proto_sessions_runs5.csv"
SNAPSHOT_PRIMITIVES = "proto_primitives_runs5.csv"
FIRST_RUNS = 5   # runs 0 to 4 have the seeds of the round 6 five run snapshot
SESSION_SIDE_STEPS = {"vehicle": "F2 processing and F4 (vehicle_f2 plus vehicle_f4)",
                      "ground": "F1, F3 and acceptance (ground_f1 plus ground_f3 plus ground_accept)"}


def fmt_int(x):
    return f"{int(round(x)):,}"


def fmt_ratio(x, nd=2):
    return f"{x:.{nd}f}"


def log_path(core, image):
    return RTL / "results" / "logs" / "proto" / core / f"{image}.log"


def load_logs():
    logs = {}
    for core in CORES:
        for img in IMAGES:
            p = log_path(core, img)
            if p.exists():
                logs[(core, img)] = pp.parse_file(p)
    return logs


def load_sizes(core, variant):
    p = RTL / "results" / "logs" / "proto" / core / f"sections_{variant}.txt"
    if not p.exists():
        return {}
    return {img: pp.image_sizes(sec) for img, sec in pp.read_size_sections(p).items()}


def read_build_info(core):
    p = RTL / "results" / "logs" / "proto" / core / "build_info.txt"
    env = {}
    if p.exists():
        for line in p.read_text().splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                env[k] = v
    return env


def load_round5(core):
    p = RTL / "results" / f"{core}_cycles.csv"
    out = {}
    if p.exists():
        with open(p) as fh:
            for r in csv.DictReader(fh):
                if r["statistic"] == "median":
                    out[(r["parameter_set"], r["operation"])] = float(r["cycles"])
    return out


def shared_input(name):
    with open(ROOT / "data" / "shared_inputs.csv") as fh:
        for r in csv.DictReader(fh):
            if r["parameter"] == name:
                return r
    return None


def active_current_input():
    """An active current of a core in data/shared_inputs.csv, if any (unit mA)."""
    with open(ROOT / "data" / "shared_inputs.csv") as fh:
        for r in csv.DictReader(fh):
            if r["unit"].strip().lower() == "ma" and "current" in r["parameter"].lower():
                return r
    return None


def correctness_text(passed, total, step_ok, step_n):
    return f"steps succeeded {step_ok}/{step_n}; checks passed {passed}/{total}"


def build_primitives(logs):
    rows = []
    for core in CORES:
        lg = logs.get((core, "primitives"))
        if lg is None:
            continue
        r5 = load_round5(core)
        summ = {r["operation"]: r for r in pp.op_summary(lg)}
        for op in PRIM_ORDER:
            if op not in summ:
                continue
            s = summ[op]
            lib, inp = PRIM_INFO[op]
            chk = [ok for st, c, _, ok in lg.chk if st == "primitives" and c.startswith(op.split("_")[0])]
            r5v = r5.get(ROUND5.get(op, ("", "")), None)
            rows.append({
                "label": LABEL, "core": core, "operation": op, "library": lib, "input": inp,
                "cycles_median": s["median"], "cycles_ci95_low": s["ci_low"], "cycles_ci95_high": s["ci_high"],
                "cycles_min": s["min"], "cycles_max": s["max"], "n_runs": s["n"],
                "peak_stack_bytes": s["stack_max"], "stack_saturated": s["stack_saturated"],
                "correctness": (f"calls succeeded {s['ok']}/{s['n']}; related checks passed "
                                f"{sum(chk)}/{len(chk)}"),
                "log_complete": lg.done, "seed_first": lg.config.get("seed_first", ""),
                "round5_cycles_median": r5v if r5v is not None else "",
                "this_over_round5": round(s["median"] / r5v, 4) if r5v else "",
            })
    return rows


def build_sessions(logs):
    rows = []
    for core in CORES:
        sizes = load_sizes(core, "timing")
        sizes_gc = load_sizes(core, "gc")
        for design in pp.DESIGNS:
            lg = logs.get((core, design))
            if lg is None:
                continue
            fl = pp.flights(lg, design)
            fl_text = "; ".join(f"{f} {d} {b}" for f, d, b in fl)
            for unit, steps in pp.UNITS[design]:
                for side in ("vehicle", "ground"):
                    t = pp.unit_totals(lg, design, steps[side])
                    if t is None:
                        continue
                    t5 = pp.unit_totals(lg, design, steps[side], runs=range(FIRST_RUNS))
                    passed, total = pp.checks_for(lg, design)
                    sz = sizes.get(design, {})
                    szg = sizes_gc.get(design, {})
                    if design in SESSION_DESIGNS:
                        btot = sum(b for _, _, b in fl)
                    elif design == "per_command_mldsa44":
                        btot = sum(b for _, _, b in fl)
                    else:
                        btot = sum(b for f, _, b in fl if f == "signature_field")
                    rows.append({
                        "label": LABEL, "core": core, "design": design, "unit": unit, "side": side,
                        "steps": "+".join(steps[side]),
                        "cycles_median": t["median"], "cycles_ci95_low": t["ci_low"],
                        "cycles_ci95_high": t["ci_high"], "cycles_min": t["min"], "cycles_max": t["max"],
                        "n_runs": t["n"], "peak_stack_bytes": t["stack_max"],
                        "stack_saturated": t["stack_saturated"],
                        "text_bytes_host_measured": sz.get("text", ""),
                        "data_bytes_host_measured": sz.get("data", ""),
                        "bss_bytes_host_measured": sz.get("bss", ""),
                        "text_bytes_gc_host_measured": szg.get("text", ""),
                        "bytes_per_flight": fl_text, "bytes_total": btot,
                        "correctness": correctness_text(passed, total, t["runs_correct"], t["n"]),
                        "runs_correct": t["runs_correct"], "log_complete": lg.done,
                        "seed_first": lg.config.get("seed_first", ""),
                        "cycles_median_first5_runs": t5["median"] if t5 and t5["n"] == FIRST_RUNS else "",
                    })
    return rows


def load_snapshot(name):
    """Rows of a frozen round 6 five run snapshot (empty if absent)."""
    p = RTL / "results" / name
    if not p.exists():
        return []
    with open(p) as fh:
        return list(csv.DictReader(fh))


def snapshot_median(snap, **kw):
    r = [x for x in snap if all(x.get(k) == v for k, v in kw.items())]
    return float(r[0]["cycles_median"]) if r else None


def primitive_first_runs(logs, psnap):
    """[(core, operation, snapshot median, median of runs 0 to 4 of the primitives log)]."""
    out = []
    for r in psnap:
        lg = logs.get((r["core"], "primitives"))
        if lg is None:
            continue
        rv = pp.run_values(lg, "primitives", r["operation"])
        if all(k in rv for k in range(FIRST_RUNS)):
            out.append((r["core"], r["operation"], float(r["cycles_median"]),
                        float(statistics.median(rv[k] for k in range(FIRST_RUNS)))))
    return out


def prim_values(prims, core, field="cycles_median"):
    return {r["operation"]: float(r[field]) for r in prims if r["core"] == core}


def build_decomposition(prims, sessions):
    """Each session design and side against the sum of the medians of its primitive calls; also the sum
    with the ML-DSA-44 signing call at its smallest and largest run."""
    rows = []
    for core in CORES:
        med = prim_values(prims, core)
        if not med:
            continue
        lo, hi = dict(med), dict(med)
        lo.update({k: v for k, v in prim_values(prims, core, "cycles_min").items() if k == "mldsa44_sign"})
        hi.update({k: v for k, v in prim_values(prims, core, "cycles_max").items() if k == "mldsa44_sign"})
        for design in SESSION_DESIGNS:
            for side in ("vehicle", "ground"):
                s = get(sessions, core=core, design=design, side=side)
                if s is None:
                    continue
                parts = DECOMP[design][side]
                try:
                    total, comp = pp.decompose(med, parts)
                except KeyError:
                    continue
                tmin, _ = pp.decompose(lo, parts)
                tmax, _ = pp.decompose(hi, parts)
                rows.append({
                    "label": LABEL, "core": core, "design": design, "side": side,
                    "measured_cycles_median": s["cycles_median"], "measured_ci95_low": s["cycles_ci95_low"],
                    "measured_ci95_high": s["cycles_ci95_high"], "measured_min": s["cycles_min"],
                    "measured_max": s["cycles_max"], "primitive_sum_cycles": total,
                    "primitive_sum_sign_min": tmin, "primitive_sum_sign_max": tmax,
                    "residual_cycles": s["cycles_median"] - total,
                    "sum_over_measured_ratio": round(total / s["cycles_median"], 4),
                    "has_mldsa44_sign": any(op == "mldsa44_sign" for op, _ in parts),
                    "components": "; ".join(f"{op} x{n} = {int(sub)}" for op, n, _, sub in comp),
                })
    return rows


def build_ratios(logs, sessions, decomp):
    """Ratios of session designs per core and side: from the session medians (bootstrap interval of the
    ratio of medians over the runs) and from the primitive sums (point value with the ML-DSA-44 signing
    call at its median, and the values with signing at its smallest and largest run)."""
    rows = []
    for core in CORES:
        for num, den in RATIO_PAIRS:
            for side in ("vehicle", "ground"):
                ln, ld = logs.get((core, num)), logs.get((core, den))
                if ln is None or ld is None:
                    continue
                tn = pp.unit_totals(ln, num, pp.UNITS[num][0][1][side])
                td = pp.unit_totals(ld, den, pp.UNITS[den][0][1][side])
                if tn is None or td is None:
                    continue
                lo, hi = pp.bootstrap_ratio_ci(tn["totals"], td["totals"])
                rows.append({"label": LABEL, "core": core, "side": side, "numerator": num, "denominator": den,
                             "basis": "session medians", "ratio": round(tn["median"] / td["median"], 4),
                             "ci95_low": round(lo, 4), "ci95_high": round(hi, 4),
                             "n_runs_numerator": tn["n"], "n_runs_denominator": td["n"]})
                dn = get(decomp, core=core, design=num, side=side)
                dd = get(decomp, core=core, design=den, side=side)
                if dn and dd:
                    rows.append({"label": LABEL, "core": core, "side": side, "numerator": num,
                                 "denominator": den, "basis": "primitive sums",
                                 "ratio": round(dn["primitive_sum_cycles"] / dd["primitive_sum_cycles"], 4),
                                 "ci95_low": "", "ci95_high": "",
                                 "n_runs_numerator": "", "n_runs_denominator": ""})
                    for which in ("min", "max"):
                        rows.append({"label": LABEL, "core": core, "side": side, "numerator": num,
                                     "denominator": den, "basis": f"primitive sums, signing at its {which}",
                                     "ratio": round(dn[f"primitive_sum_sign_{which}"]
                                                    / dd[f"primitive_sum_sign_{which}"], 4),
                                     "ci95_low": "", "ci95_high": "",
                                     "n_runs_numerator": "", "n_runs_denominator": ""})
    return rows


def build_sizes():
    rows = []
    for core in CORES:
        for variant in ("timing", "gc"):
            for img, s in load_sizes(core, variant).items():
                rows.append({"label": "host measured", "core": core, "image": img, "variant": variant,
                             "text_bytes": s["text"], "data_bytes": s["data"], "bss_bytes": s["bss"]})
    return rows


def build_time(sessions):
    rows = []
    for r in sessions:
        for mhz in CLOCKS_MHZ:
            rows.append({"label": "estimated", "core": r["core"], "design": r["design"], "unit": r["unit"],
                         "side": r["side"], "clock_mhz": mhz,
                         "time_ms": round(r["cycles_median"] / (mhz * 1e3), 4),
                         "basis": "cycles_median of rtlsim/results/proto_sessions.csv divided by the clock; "
                                  "no wait states, no cache, open RISC-V core, not a Cortex-M"})
    return rows


def write_csv(path, rows):
    if not rows:
        return
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def make_figure(sessions, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    designs = SESSION_DESIGNS + ["per_command_mldsa44", "mavlink_tag"]
    names = ["classical\nsession", "post quantum\nonly session", "hybrid\nwith F1", "KEM\nauthenticated",
             "ML-DSA-44\nper command", "MAVLink 2 tag\nper message"]
    fig, ax = plt.subplots(figsize=(8.2, 3.8))
    width = 0.38
    for i, core in enumerate(CORES):
        vals = []
        for d in designs:
            unit = pp.UNITS[d][0][0]
            m = [r["cycles_median"] for r in sessions
                 if r["core"] == core and r["design"] == d and r["side"] == "vehicle" and r["unit"] == unit]
            vals.append(m[0] if m else 0)
        xs = [x + (i - 0.5) * width for x in range(len(designs))]
        ax.bar(xs, vals, width, label=CORE_NAME[core], color=["#4c72b0", "#dd8452"][i])
    ax.set_yscale("log")
    ax.set_xticks(range(len(designs)))
    ax.set_xticklabels(names, fontsize=8)
    ax.set_ylabel("vehicle side cycles (median, log scale)")
    ax.set_title("Vehicle side cost per design (label: RTL simulated)", fontsize=10)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=130, metadata={"Software": None})
    plt.close(fig)


def get(rows, **kw):
    out = [r for r in rows if all(r.get(k) == v for k, v in kw.items())]
    return out[0] if out else None


def write_doc(logs, prims, sessions, sizes, times, decomp=None, ratios_rows=None):
    decomp = decomp or []
    ratios_rows = ratios_rows or []
    L = []
    a = L.append
    info = {c: read_build_info(c) for c in CORES}
    bi = info["ibex"] or info["cv32e40p"]
    runs = bi.get("runs", "")
    runs_tag = bi.get("runs_mavlink_tag", runs)
    seed = bi.get("seed_first", "")
    a("# Executed protocol baselines on open RISC-V cores (RTL simulated)")
    a("")
    a("Author: Huda Mueen. Generated by `rtlsim/proto/make_doc.py`; do not edit by hand. Every number "
      "below is read by that script from `rtlsim/results/logs/proto/` (simulation logs and the section "
      "sizes written by `rtlsim/proto/build.sh`), `rtlsim/results/<core>_cycles.csv` (round 5) or "
      "`data/shared_inputs.csv`.")
    a("")
    a("## What this is, and what it is not")
    a("")
    a("This document closes limitation L1 of `docs/LIMITATIONS_AND_PLAN_R6.md` as far as free tools allow: "
      "the session protocols of `docs/REFERENCE_ARCHITECTURE.md` and `formal/models/session_b_fixed.pv` "
      "and the per message and per command alternatives were executed end to end with pinned libraries, "
      "with a correctness check in every run, on two open RISC-V core designs in cycle accurate "
      "simulation of their register transfer level descriptions (Verilator). Cycle counts and stack "
      "carry the label **RTL simulated**. They are not measurements of a Cortex-M microcontroller, of "
      "silicon or of a board. Both testbenches have no cache and no wait states, so a microcontroller "
      "that fetches from flash with wait states would take more cycles. Times at a clock are "
      "**estimated** (cycles divided by the clock). Code sizes come from the toolchain on the host "
      "(**host measured**).")
    a("")
    a("## Method")
    a("")
    a("- Cores and testbenches (unchanged from round 5, `docs/RTL_SIM_RESULTS.md`): Ibex, named "
      f"configuration small, commit `{info['ibex'].get('ibex_commit', '').split(' ')[0]}`, "
      "simple system with a single 1 MB RAM shared by instruction and data ports that answers in the "
      "next cycle (no wait states, no cache); CV32E40P, tag cv32e40p_v1.8.3, example testbench with a "
      "4 MB RAM (mm_ram and dp_ram), random stall and interrupt generators present but not enabled by "
      "the program (no wait states, no cache). Ibex runs with the instruction trace off.")
    a(f"- Compiler and flags (as round 5): `{bi.get('compiler', '')}`, `{bi.get('cflags', '')}`, "
      "picolibc for memcpy, memset and memcmp. The same object files of the libraries are linked for both "
      "cores; only the start up code and the output functions differ.")
    a(f"- Libraries, used as benchmark subjects only (no cryptographic primitive is written in this "
      f"repository): mlkem-native `{bi.get('mlkem_commit', '')}` (ML-KEM-768), mldsa-native "
      f"`{bi.get('mldsa_commit', '')}` (ML-DSA-44 and its SHAKE256), both with their portable C backends; "
      f"Monocypher `{bi.get('monocypher_commit', '')}` (tag 4.0.3; X25519, and Ed25519 with SHA-512 from "
      f"its optional module); the MAVLink 2 C library (generated headers, c_library_v2) "
      f"`{bi.get('mavlink_c_commit', '')}` for message signing and the SHA-256 it uses. Classical library "
      "and MAVLink library are fetched by `rtlsim/proto/fetch.sh` at these commits and never committed.")
    a("- Protocol glue (benchmark code, `rtlsim/proto/sw/proto_bench.c`): flights as in the formal model "
      "of design B with F1. F1 carries the ground X25519 share and the ML-KEM-768 encapsulation key; F2 "
      "the vehicle X25519 share and the ciphertext; F3 the ground signature over (flight 3, ground "
      "identity, vehicle identity, transcript hash) and a 16 B ground confirmation tag; F4 the vehicle "
      "signature over (flight 4, vehicle identity, ground identity, transcript hash) and a 16 B vehicle "
      "confirmation tag. The transcript hash is SHAKE256 over a label and the full bytes of F1 and F2; "
      "the session key is SHAKE256 over a label, the X25519 secret, the ML-KEM secret and the transcript "
      "hash; each confirmation tag is SHAKE256 over the session key, a label and the transcript hash; "
      "identities are SHAKE256 of the long term public keys, pinned at the other side. The signature "
      "input is therefore 97 B. The classical design drops the ML-KEM parts and signs with Ed25519; the "
      "post quantum only design drops the X25519 parts. The architecture names no concrete key "
      "derivation; SHAKE256 is used for every design so that the designs differ only in the parts under "
      "comparison. A rekey is not timed.")
    a("- KEM authenticated design (added after the review, in the spirit of post quantum WireGuard and of "
      "KEMTLS with pre distributed keys): each side holds a static ML-KEM-768 key pair whose encapsulation "
      "key is pinned at the other side; there are no signatures. F1 (ground to vehicle) carries the ground "
      "ephemeral X25519 share, a ground ephemeral ML-KEM-768 encapsulation key and a ciphertext "
      "encapsulated to the vehicle static key; F2 (vehicle to ground) carries the vehicle X25519 share, a "
      "ciphertext to the ground ephemeral key, a ciphertext to the ground static key and a 16 B vehicle "
      "confirmation tag; F3 (ground to vehicle) carries a 16 B ground confirmation tag. The session key is "
      "SHAKE256 over a label, the X25519 secret, the three ML-KEM secrets (vehicle static, ground "
      "ephemeral, ground static) and the transcript hash. The ground accepts after checking the vehicle "
      "tag, which only the holder of the vehicle static key can compute; the vehicle accepts after "
      "checking the ground tag, which only the holder of the ground static key can compute. One change "
      "against the flights first proposed: the transcript hash also covers both pinned identities, as the "
      "signed input of the signature designs does, so that each key is bound to the pair of parties and "
      "not only through the KEM secrets. No flaw was found in the proposed flights otherwise; as in every "
      "design here, the vehicle does its F2 work on an F1 it cannot yet authenticate, so an outsider can "
      "make it spend that work. Its formal model is in `docs/FORMAL_VERIFICATION.md` section 10. Its steps: "
      "ground F1; vehicle F2 processing; ground F2 check, acceptance and F3; vehicle F3 check and "
      "acceptance.")
    a("- Vehicle and ground are computed separately in one image per design: each step is timed on its "
      "own (ground F1; vehicle F2 processing; ground F3; vehicle F3 check and F4; ground acceptance), and "
      "a side's cost is the sum of its steps in that run. Long term keys and identities are provisioned "
      "untimed before each run.")
    a("- Per command design: the ground signs a MAVLink 2 COMMAND_LONG frame (built with the MAVLink C "
      "library) with ML-DSA-44 and the vehicle verifies it. Per message design: the MAVLink 2 signing tag "
      "of the shipped library, timed both alone (`mavlink_sign_packet` on the ground, "
      "`mavlink_signature_check` on the vehicle) and on the full path (pack with checksum and tag; "
      "byte parser with checksum, tag and timestamp check), for a COMMAND_LONG frame and for a frame of "
      "60 B before the signature field (10 B header, 48 B payload, 2 B checksum). The tag follows the "
      "MAVLink message signing guide (https://mavlink.io/en/guide/message_signing.html, read "
      "2026-10-28): the first 48 bits of SHA-256 over secret key, header, payload, checksum, link id and "
      "timestamp. A known answer test checks the library tag against that formula computed on the host.")
    a(f"- Runs and seeds: {runs} runs per image (the MAVLink tag image {runs_tag}, as it has no data "
      f"dependent operation); run r reseeds the test generator with {seed} + r (seed block {seed} to "
      f"{int(seed) + int(runs) - 1 if seed and runs else ''}). The generator "
      "(`rtlsim/sw/bench_rng.c`, splitmix64) is a deterministic test generator and is NOT a secure random "
      "number generator. Medians with a bootstrap 95 percent interval of the median (10,000 resamples, "
      f"seed {pp.SEED}), and the smallest and largest run.")
    a("- Cycles: `mcycle` read before and after each timed call, the cost of two back to back reads "
      "removed (as round 5). Peak stack: before each timed call the harness fills "
      f"{int(bi.get('stack_paint_bytes', '0'), 0) // 1024 if bi.get('stack_paint_bytes') else ''} kB "
      "below the caller's stack pointer (after a 256 B gap) with a pattern and afterwards finds the lowest "
      "overwritten word; the value is the distance from the caller's stack pointer, so it includes the "
      "glue frames, and its resolution floor is 256 B. Session state and messages are static (bss), "
      "not stack.")
    a("- Correctness in every run: both sides derive the same session key and transcript hash, both "
      "signatures verify, both confirmation tags match, both sides accept; known answer tests for "
      "SHA-256, the MAVLink tag and the key derivation; ML-KEM shared secrets equal; X25519 secrets "
      "agree. First run only (untimed): a modified F3 signature, a modified F3 tag and a modified F4 "
      "signature are rejected; a modified signed input is rejected by Ed25519 and ML-DSA-44; a replayed "
      "MAVLink frame and a modified payload are rejected. KEM authenticated design, first run only: a "
      "modified F3 tag, a modified F2 tag and a modified ciphertext to the ground static key are "
      "rejected, and the ground rejects F2 when the ciphertext to the vehicle static key in F1 was replaced "
      "in transit by an encapsulation of a third party.")
    a("- Code size: text (code plus read only data), data and bss of each image, excluding the stack and "
      "heap reservations of the link scripts. Two link variants: the simulated image (whole library "
      "objects, as round 5) and a size only build with `-ffunction-sections -fdata-sections` and "
      "`--gc-sections` that drops library code the design never calls. Each image holds both the "
      "vehicle and the ground code of its design, the harness and the C library parts it uses.")
    a("")

    # Correctness summary
    total_fail = 0
    lines = []
    for (core, img), lg in sorted(logs.items()):
        bad_steps = sum(1 for r in lg.res if not r[4])
        bad_chk = sum(1 for c in lg.chk if not c[3])
        total_fail += bad_steps + bad_chk + (0 if lg.done else 1)
        lines.append(f"{CORE_NAME[core]} {img}: {len(lg.res)} timed calls ({bad_steps} failed), "
                     f"{len(lg.chk)} checks ({bad_chk} failed), log {'complete' if lg.done else 'INCOMPLETE'}")
    sat = any(r["stack_saturated"] for r in prims + sessions)
    a("## Correctness")
    a("")
    for x in lines:
        a(f"- {x}.")
    a("")
    a(f"Failed calls, failed checks and incomplete logs in total: {total_fail}. Painted stack area used "
      f"up in any call: {'yes' if sat else 'no'}.")
    a("")

    # Primitives
    a("## Primitives alone (label: RTL simulated)")
    a("")
    a("Median cycles (bootstrap 95 percent interval of the median) and the largest peak stack over the "
      "runs. Source: `rtlsim/results/proto_primitives.csv`.")
    a("")
    a("| Operation | Library | Input | Ibex median | Ibex 95% CI | CV32E40P median | CV32E40P 95% CI | "
      "Peak stack Ibex / CV32E40P (B) |")
    a("|---|---|---|---|---|---|---|---|")
    for op in PRIM_ORDER:
        ri = get(prims, core="ibex", operation=op)
        rc = get(prims, core="cv32e40p", operation=op)
        if not ri and not rc:
            continue
        lib, inp = PRIM_INFO[op]

        def cell(r):
            if not r:
                return "not run", ""
            return fmt_int(r["cycles_median"]), f"{fmt_int(r['cycles_ci95_low'])} to {fmt_int(r['cycles_ci95_high'])}"
        mi, ci = cell(ri)
        mc, cc = cell(rc)
        st = f"{ri['peak_stack_bytes'] if ri else ''} / {rc['peak_stack_bytes'] if rc else ''}"
        a(f"| {op} | {lib} | {inp} | {mi} | {ci} | {mc} | {cc} | {st} |")
    a("")
    r5 = [r for r in prims if r["round5_cycles_median"] != ""]
    if r5:
        a("Consistency with round 5 (same libraries, compiler and flags; round 5 signed a 64 B message, "
          "this round a 97 B input, and the link layout differs): this round over round 5 median, "
          + "; ".join(f"{CORE_NAME[r['core']]} {r['operation']} {r['this_over_round5']:.3f}" for r in r5) + ".")
        a("")

    # Sessions
    a("## Designs, vehicle and ground side (label: RTL simulated)")
    a("")
    a("One unit of work per design: a session start for the session designs, one command for the per "
      "command design, one message for the tag. Each cell gives the median cycles, the bootstrap 95 percent "
      "interval of the median in brackets and the smallest to largest run after it. Source: "
      "`rtlsim/results/proto_sessions.csv`.")
    a("")
    a("| Design | Unit | Side | Ibex cycles: median [95% CI] (min to max) | CV32E40P cycles: median [95% CI] "
      "(min to max) | Runs correct Ibex / CV32E40P |")
    a("|---|---|---|---|---|---|")

    def cyc_cell(r):
        if not r:
            return "not run"
        return (f"{fmt_int(r['cycles_median'])} [{fmt_int(r['cycles_ci95_low'])} to "
                f"{fmt_int(r['cycles_ci95_high'])}] ({fmt_int(r['cycles_min'])} to {fmt_int(r['cycles_max'])})")
    for design in pp.DESIGNS:
        for unit, _ in pp.UNITS[design]:
            for side in ("vehicle", "ground"):
                ri = get(sessions, core="ibex", design=design, unit=unit, side=side)
                rc = get(sessions, core="cv32e40p", design=design, unit=unit, side=side)
                if not ri and not rc:
                    continue
                a(f"| {DESIGN_NAME[design]} | {unit} | {side} | {cyc_cell(ri)} | {cyc_cell(rc)} | "
                  f"{(str(ri['runs_correct']) + '/' + str(ri['n_runs'])) if ri else ''} / "
                  f"{(str(rc['runs_correct']) + '/' + str(rc['n_runs'])) if rc else ''} |")
    a("")
    a("| Design | Unit | Peak stack Ibex / CV32E40P (B) | Bytes on air per unit | Bytes per flight |")
    a("|---|---|---|---|---|")
    for design in pp.DESIGNS:
        for unit, _ in pp.UNITS[design]:
            ri = get(sessions, core="ibex", design=design, unit=unit, side="vehicle")
            rc = get(sessions, core="cv32e40p", design=design, unit=unit, side="vehicle")
            gi = get(sessions, core="ibex", design=design, unit=unit, side="ground")
            gc = get(sessions, core="cv32e40p", design=design, unit=unit, side="ground")
            r0 = ri or rc
            if not r0:
                continue

            def stk(*rs):
                v = [r["peak_stack_bytes"] for r in rs if r and r["peak_stack_bytes"] is not None]
                return str(max(v)) if v else ""
            a(f"| {design} | {unit} | {stk(ri, gi)} / {stk(rc, gc)} | {r0['bytes_total']} | "
              f"{r0['bytes_per_flight'] if design != 'mavlink_tag' else 'signature field ' + str(r0['bytes_total'])} |")
    a("")
    a("Peak stack is the larger of the vehicle and ground values. Message bytes are the sizes of the "
      "buffers the program built (`MSG` lines of the logs).")
    a("")

    # Rerun against the snapshot
    snap = load_snapshot(SNAPSHOT_SESSIONS)
    if snap:
        a("## The 15 run rerun and the five run snapshot of round 6")
        a("")
        a(f"The first runs of round 6 used {FIRST_RUNS} runs per image (seed block {seed} to "
          f"{int(seed) + FIRST_RUNS - 1 if seed else ''}). After the review the images were run again with "
          f"{runs} runs whose seed block extends the first one, and the 15 run values replace the five run "
          "values in `rtlsim/results/proto_sessions.csv` and `rtlsim/results/proto_primitives.csv`. The "
          "five run tables are kept unchanged as frozen snapshots, `rtlsim/results/"
          f"{SNAPSHOT_SESSIONS}` and `rtlsim/results/{SNAPSHOT_PRIMITIVES}`, because the software in the "
          "loop study of round 6 (`docs/SITL_STUDY_R6.md`) set its compute delays from the five run medians "
          "and recorded the SHA-256 of those two files in its raw outputs (`sitl/raw_r6/`); the snapshots "
          "are byte for byte the files it hashed. Their logs are those of the repository history before "
          "this rerun. Runs 0 to 4 of the rerun have the seeds of the snapshot, so the median of those five "
          "runs should reproduce it; the table checks this for the vehicle and ground totals.")
        a("")
        a("| Design | Side | Core | Five run snapshot median | Median of runs 0 to 4 of the rerun | Same | "
          "Median of all runs |")
        a("|---|---|---|---|---|---|---|")
        n_same = n_all = 0
        for design in pp.DESIGNS:
            if design == "mavlink_tag":
                continue
            unit = pp.UNITS[design][0][0]
            for side in ("vehicle", "ground"):
                for core in CORES:
                    r = get(sessions, core=core, design=design, unit=unit, side=side)
                    sm = snapshot_median(snap, core=core, design=design, unit=unit, side=side)
                    if not r or sm is None:
                        continue
                    f5 = r["cycles_median_first5_runs"]
                    same = f5 != "" and float(f5) == sm
                    n_same += same
                    n_all += 1
                    a(f"| {design} | {side} | {CORE_NAME[core]} | {fmt_int(sm)} | "
                      f"{fmt_int(f5) if f5 != '' else 'not available'} | {'yes' if same else 'no'} | "
                      f"{fmt_int(r['cycles_median'])} |")
        a("")
        a(f"Reproduced exactly: {n_same} of {n_all} rows. The KEM authenticated design is new and has no "
          "snapshot row.")
        a("")
        psnap = load_snapshot(SNAPSHOT_PRIMITIVES)
        cmp_ = primitive_first_runs(logs, psnap)
        if cmp_:
            same = sum(1 for _, _, sv, fv in cmp_ if sv == fv)
            maxd = max(abs(sv - fv) for _, _, sv, fv in cmp_)
            maxrel = max(abs(sv - fv) / sv for _, _, sv, fv in cmp_ if sv)
            a(f"Primitives image: {same} of {len(cmp_)} operation medians of runs 0 to 4 equal the snapshot; "
              f"the largest difference is {fmt_int(maxd)} cycles ({100 * maxrel:.4f} percent of that "
              "median). The primitives image gained the transcript hashes and the key derivation of the "
              "new design after the round 6 operations, which leaves their random stream, and so the "
              "ML-DSA-44 signing rounds per seed, unchanged but moves code in memory; we attribute the few cycles of "
              "difference per call to that layout change without having traced it further. The session images changed only in "
              "their run count.")
            a("")

    # Decomposition
    if decomp:
        a("## Where the cycles go: each side against its primitive costs (label: RTL simulated)")
        a("")
        a("Each side of a session start is a fixed list of calls to the pinned libraries plus glue. The "
          "tables list those calls, each costed at its median in the primitives image "
          "(`rtlsim/results/proto_primitives.csv`), and compare their sum with the measured median of the "
          "side; the residual is glue (random bytes for the X25519 secrets, copies, comparisons, the signed "
          "input) and the difference between a call in the session and the same call in the primitives "
          "image. ML-DSA-44 signing has a data dependent number of rounds (rejection sampling), so its "
          "cost differs from seed to seed and the session image signs other messages with other keys than "
          "the primitives image: for the designs that sign, the sum is also given with the signing call at "
          "its smallest and largest run. Source: `rtlsim/results/proto_decomposition.csv`.")
        a("")
        for side in ("vehicle", "ground"):
            a(f"### {side.capitalize()} side")
            a("")
            for design in SESSION_DESIGNS:
                di = get(decomp, core="ibex", design=design, side=side)
                dc = get(decomp, core="cv32e40p", design=design, side=side)
                if not di and not dc:
                    continue
                if side == "vehicle":
                    a(f"{DESIGN_NAME[design]}:")
                    a("")
                    a("| Call | Count | Ibex cycles | CV32E40P cycles | Share of the primitive sum, CV32E40P |")
                    a("|---|---|---|---|---|")
                    mi = prim_values(prims, "ibex")
                    mc = prim_values(prims, "cv32e40p")
                    for op, n in DECOMP[design][side]:
                        ci = n * mi[op] if op in mi else None
                        cc = n * mc[op] if op in mc else None
                        share = (f"{100 * cc / dc['primitive_sum_cycles']:.1f} %" if cc is not None and dc
                                 else "")
                        a(f"| {op} | {n} | {fmt_int(ci) if ci is not None else ''} | "
                          f"{fmt_int(cc) if cc is not None else ''} | {share} |")
                    a(f"| sum of primitive medians | | {fmt_int(di['primitive_sum_cycles']) if di else ''} | "
                      f"{fmt_int(dc['primitive_sum_cycles']) if dc else ''} | |")
                    a(f"| measured median of the side | | {fmt_int(di['measured_cycles_median']) if di else ''} | "
                      f"{fmt_int(dc['measured_cycles_median']) if dc else ''} | |")
                    a(f"| sum over measured | | {di['sum_over_measured_ratio']:.3f} | {dc['sum_over_measured_ratio']:.3f} | |"
                      if di and dc else "| sum over measured | | | | |")
                    a("")
            a(f"Summary, {side} side:")
            a("")
            a("| Design | Core | Sum of primitive medians | Sum, signing at its smallest / largest run | "
              "Measured median [95% CI] | Sum over measured |")
            a("|---|---|---|---|---|---|")
            for design in SESSION_DESIGNS:
                for core in CORES:
                    d = get(decomp, core=core, design=design, side=side)
                    if not d:
                        continue
                    rng = (f"{fmt_int(d['primitive_sum_sign_min'])} / {fmt_int(d['primitive_sum_sign_max'])}"
                           if d["has_mldsa44_sign"] else "no signing call")
                    a(f"| {design} | {CORE_NAME[core]} | {fmt_int(d['primitive_sum_cycles'])} | {rng} | "
                      f"{fmt_int(d['measured_cycles_median'])} [{fmt_int(d['measured_ci95_low'])} to "
                      f"{fmt_int(d['measured_ci95_high'])}] | {d['sum_over_measured_ratio']:.3f} |")
            a("")

    # Ratios
    a("## Ratios between designs (label: RTL simulated)")
    a("")
    a("Two readings of each ratio. From the session medians: the ratio of the two medians over the runs, "
      "with a bootstrap 95 percent interval of that ratio (the two designs run in separate images, so "
      "their runs are resampled independently). From the primitive sums: the ratio of the sums of the "
      "previous section, which does not depend on which seeds fell into which design but assumes the calls "
      "cost in the session what they cost alone; for designs that sign, the range uses the signing call "
      "at its smallest and at its largest run in both designs. ML-DSA-44 signing has a data dependent "
      "number of rounds, so ratios that involve a signing design move with the seeds; the KEM authenticated "
      "design has no data dependent call of that kind. Source: `rtlsim/results/proto_ratios.csv`.")
    a("")
    a("| Ratio | Side | Core | From session medians [95% CI] | From primitive sums (signing at smallest to "
      "largest) |")
    a("|---|---|---|---|---|")
    ratios = {}
    for num, den in RATIO_PAIRS:
        for side in ("vehicle", "ground"):
            for core in CORES:
                m = get(ratios_rows, core=core, side=side, numerator=num, denominator=den,
                        basis="session medians")
                ps = get(ratios_rows, core=core, side=side, numerator=num, denominator=den,
                         basis="primitive sums")
                pmin = get(ratios_rows, core=core, side=side, numerator=num, denominator=den,
                           basis="primitive sums, signing at its min")
                pmax = get(ratios_rows, core=core, side=side, numerator=num, denominator=den,
                           basis="primitive sums, signing at its max")
                if not m:
                    continue
                ratios[(num, den, side, core)] = m["ratio"]
                pcell = "not available"
                if ps:
                    lo_, hi_ = sorted((pmin["ratio"], pmax["ratio"]))
                    pcell = (f"{ps['ratio']:.2f} ({lo_:.2f} to {hi_:.2f})" if lo_ != hi_
                             else f"{ps['ratio']:.2f}")
                a(f"| {num} over {den} | {side} | {CORE_NAME[core]} | {m['ratio']:.2f} "
                  f"[{m['ci95_low']:.2f} to {m['ci95_high']:.2f}] | {pcell} |")
    a("")
    for core in CORES:
        h = get(decomp, core=core, design="hybrid_f1", side="vehicle")
        q = get(decomp, core=core, design="pq_only", side="vehicle")
        if h and q:
            diff = h["primitive_sum_cycles"] - q["primitive_sum_cycles"]
            a(f"- {CORE_NAME[core]}, vehicle side: the hybrid and the post quantum only designs differ by a "
              f"fixed set of calls, the X25519 key generation and shared secret and the longer transcript, "
              f"{fmt_int(diff)} cycles at the primitive medians; the signing call alone spans "
              f"{fmt_int(get(prims, core=core, operation='mldsa44_sign')['cycles_min'])} to "
              f"{fmt_int(get(prims, core=core, operation='mldsa44_sign')['cycles_max'])} cycles over its runs, "
              "so with few runs the ratio of session medians reflects the signing seeds as much as the "
              "designs.")
    a("")
    a("| Design | Unit | Side | Ibex over CV32E40P |")
    a("|---|---|---|---|")
    for design in pp.DESIGNS:
        for unit, _ in pp.UNITS[design]:
            for side in ("vehicle", "ground"):
                ri = get(sessions, core="ibex", design=design, unit=unit, side=side)
                rc = get(sessions, core="cv32e40p", design=design, unit=unit, side=side)
                if ri and rc:
                    a(f"| {design} | {unit} | {side} | {fmt_ratio(ri['cycles_median'] / rc['cycles_median'])} |")
    a("")

    # Classical baseline
    xs = get(prims, core="cv32e40p", operation="x25519_shared")
    xk = get(prims, core="cv32e40p", operation="x25519_keygen")
    ke = get(prims, core="cv32e40p", operation="mlkem768_encaps")
    a("## The classical baseline is one portable C library")
    a("")
    a("The classical designs use Monocypher, a library written in portable C for size and simplicity, "
      "with no assembly on either core; the post quantum libraries also run their portable C backends. "
      "Monocypher computes the ephemeral X25519 public key with the same variable base ladder as the "
      "shared secret, so key generation costs as much as a scalar multiplication"
      + (f" ({fmt_int(xk['cycles_median'])} against {fmt_int(xs['cycles_median'])} cycles on CV32E40P)"
         if xs and xk else "")
      + ". Every statement here that compares X25519 with ML-KEM-768"
      + (f" (for example one X25519 scalar multiplication at {fmt_int(xs['cycles_median'])} cycles against "
         f"{fmt_int(ke['cycles_median'])} for an ML-KEM-768 encapsulation on CV32E40P)" if xs and ke else "")
      + " therefore holds for portable C on these two cores only. A speed oriented X25519 (assembly, or a "
      "fixed base key generation) would make the X25519 parts cheaper, lower the classical session and "
      "raise the hybrid over classical ratio; no second classical implementation was measured.")
    a("")

    # Per command against session
    a("## Signature per command against a session with a tag per message (label: RTL simulated)")
    a("")
    for core in CORES:
        h = get(sessions, core=core, design="hybrid_f1", side="vehicle")
        v = get(sessions, core=core, design="per_command_mldsa44", side="vehicle")
        t = get(sessions, core=core, design="mavlink_tag", unit="per message, tag alone, COMMAND_LONG",
                side="vehicle")
        if h and v and t:
            n = h["cycles_median"] / (v["cycles_median"] - t["cycles_median"])
            a(f"- {CORE_NAME[core]}: one ML-DSA-44 verification per command costs "
              f"{fmt_int(v['cycles_median'])} cycles on the vehicle against {fmt_int(t['cycles_median'])} for "
              f"the tag check of the same COMMAND_LONG frame, a factor of "
              f"{v['cycles_median'] / t['cycles_median']:.0f}. The vehicle side of one hybrid session start "
              f"({fmt_int(h['cycles_median'])} cycles) equals the extra cost of signatures on {n:.1f} commands "
              "(hybrid session cycles divided by the difference between verification and tag check).")
    a("")

    # Time
    a("## Time at stated clocks (label: estimated)")
    a("")
    a("Median cycles divided by the clock, for the vehicle side; 64 MHz and 168 MHz are clocks of "
      "microcontroller classes used elsewhere in this study (168 MHz: `clock_m4_ref_mhz` in "
      "`data/shared_inputs.csv`). This assumes the cycle counts of these open cores without wait states "
      "and caches, which a Cortex-M flight controller does not share. Source: "
      "`rtlsim/results/proto_time_estimated.csv`.")
    a("")
    a("| Design | Unit | " + " | ".join(f"{CORE_NAME[c]} at {m} MHz (ms)" for c in CORES for m in CLOCKS_MHZ) + " |")
    a("|---|---|" + "---|" * (len(CORES) * len(CLOCKS_MHZ)))
    for design in pp.DESIGNS:
        for unit, _ in pp.UNITS[design]:
            cells = []
            for c in CORES:
                for m in CLOCKS_MHZ:
                    r = get(times, core=c, design=design, unit=unit, side="vehicle", clock_mhz=m)
                    cells.append(f"{r['time_ms']:.3f}" if r else "not run")
            a(f"| {design} | {unit} | " + " | ".join(cells) + " |")
    a("")
    cur = active_current_input()
    if cur is None:
        a("Energy: `data/shared_inputs.csv` holds no active current of a core, so no energy column is "
          "computed here (the plan asked for one only if such a current exists).")
    else:
        a(f"Energy input found: {cur['parameter']} = {cur['value']} {cur['unit']} ({cur['source']}).")
    a("")

    # Sizes
    a("## Code size (label: host measured)")
    a("")
    a("Bytes of each image; text includes read only data. Source: `rtlsim/results/proto_sizes.csv` and "
      "`rtlsim/results/logs/proto/object_sizes.txt` for the library objects.")
    a("")
    for variant, what in (("timing", "Simulated images (whole library objects linked)"),
                          ("gc", "Size only build with unused sections removed")):
        a(f"{what}:")
        a("")
        a("| Image | Ibex text | Ibex data | Ibex bss | CV32E40P text | CV32E40P data | CV32E40P bss |")
        a("|---|---|---|---|---|---|---|")
        for img in IMAGES:
            si = get(sizes, core="ibex", image=img, variant=variant)
            sc = get(sizes, core="cv32e40p", image=img, variant=variant)
            if not si and not sc:
                continue

            def tri(r):
                if not r:
                    return " | | "
                return f"{fmt_int(r['text_bytes'])} | {fmt_int(r['data_bytes'])} | {fmt_int(r['bss_bytes'])}"
            a(f"| {img} | {tri(si)} | {tri(sc)} |")
        a("")
    for variant, what in (("timing", "simulated images"), ("gc", "size only build with unused sections removed")):
        h = get(sizes, core="ibex", image="hybrid_f1", variant=variant)
        c = get(sizes, core="ibex", image="classical", variant=variant)
        p = get(sizes, core="ibex", image="pq_only", variant=variant)
        k = get(sizes, core="ibex", image="kem_auth", variant=variant)
        if h and c and p:
            a(f"- Ibex, {what}: hybrid over classical text {h['text_bytes'] / c['text_bytes']:.2f}; post quantum "
              f"only over classical {p['text_bytes'] / c['text_bytes']:.2f}"
              + (f"; KEM authenticated over classical {k['text_bytes'] / c['text_bytes']:.2f}, over hybrid "
                 f"{k['text_bytes'] / h['text_bytes']:.2f}" if k else "") + ".")
    a("")
    a("The simulated classical, hybrid and KEM authenticated images link the whole Monocypher object, "
      "which also holds functions the protocol never calls (for example Argon2, BLAKE2b, ChaCha20 and "
      "Poly1305), so their text is large beside the post quantum only image; the size only build removes "
      "them. The bss of the session images holds the static session state and messages; the KEM "
      "authenticated image also holds both static ML-KEM-768 key pairs.")
    a("")

    # Registered metrics
    a("## Values for the metrics registered before the runs")
    a("")
    a("Values only, computed from the files above; scoring against `docs/PREDICTIONS_V6.md` is left to "
      "the scoring script.")
    a("")
    a("| ID | Metric as registered | Value | Basis |")
    a("|---|---|---|---|")
    pc = lambda core, op: get(prims, core=core, operation=op)  # noqa: E731
    x = pc("cv32e40p", "x25519_shared")
    e = pc("cv32e40p", "mlkem768_encaps")
    if x and e:
        a(f"| Q1 | X25519 scalar multiplication over ML-KEM-768 encaps, CV32E40P | "
          f"{x['cycles_median'] / e['cycles_median']:.2f} | x25519_shared over mlkem768_encaps medians; "
          f"with x25519_keygen {pc('cv32e40p', 'x25519_keygen')['cycles_median'] / e['cycles_median']:.2f} |")
    h = get(sessions, core="cv32e40p", design="hybrid_f1", side="vehicle")
    if h:
        a(f"| Q2 | vehicle side hybrid handshake cycles, CV32E40P | {fmt_int(h['cycles_median'])} | "
          "median of the vehicle steps per run |")
    v = ratios.get(("hybrid_f1", "classical", "vehicle", "cv32e40p"))
    if v:
        a(f"| Q3 | vehicle hybrid over vehicle classical, CV32E40P | {v:.2f} | medians |")
    hi = get(sessions, core="ibex", design="hybrid_f1", side="vehicle")
    if hi and h:
        a(f"| Q4 | Ibex over CV32E40P, vehicle side hybrid | {hi['cycles_median'] / h['cycles_median']:.2f} | medians |")
    t = get(sessions, core="cv32e40p", design="mavlink_tag", unit="per message, tag alone, 60 B frame",
            side="ground")
    tv = get(sessions, core="cv32e40p", design="mavlink_tag", unit="per message, tag alone, 60 B frame",
             side="vehicle")
    if t and tv:
        a(f"| Q5 | one MAVLink 2 signing tag over a 60 B message, CV32E40P | {fmt_int(t['cycles_median'])} | "
          f"tag generation alone; tag check alone {fmt_int(tv['cycles_median'])} |")
    if h and hi:
        a(f"| Q6 | peak stack, vehicle side hybrid | {h['peak_stack_bytes']} B (CV32E40P), "
          f"{hi['peak_stack_bytes']} B (Ibex) | largest over steps and runs |")
    ht = get(sizes, core="ibex", image="hybrid_f1", variant="timing")
    ct = get(sizes, core="ibex", image="classical", variant="timing")
    hg = get(sizes, core="ibex", image="hybrid_f1", variant="gc")
    cg = get(sizes, core="ibex", image="classical", variant="gc")
    if ht and ct and hg and cg:
        a(f"| Q7 | text of the hybrid image over the classical image | {ht['text_bytes'] / ct['text_bytes']:.2f} "
          f"(simulated images); {hg['text_bytes'] / cg['text_bytes']:.2f} (unused sections removed) | Ibex; "
          "both readings given |")
    a("")

    a("![Vehicle side cycles per design](figures/rtl_baselines_vehicle.png)")
    a("")
    a("## Limits")
    a("")
    a("- Open RISC-V cores are not Cortex-M cores: instruction set, multiplier, pipeline and compiler "
      "back end differ, so these cycles do not transfer to a flight controller without a measurement "
      "there (`docs/BOARD_RUN_PROTOCOL.md`).")
    a("- No cache and no wait states in either testbench: Ibex reads a single RAM that answers in the "
      "next cycle; the CV32E40P example testbench RAM has no wait states unless its random stall "
      "generator is enabled, which the program does not do. Real flash wait states add cycles.")
    a("- Portable C backends only: no assembly backend of any library was used on either core; "
      "Monocypher is portable C by design.")
    a("- The X25519 secrets are not checked for the all zero output, nothing here is constant time "
      "reviewed, secrets are not wiped, and the random generator is a test generator: this is a cost "
      "benchmark, not an implementation for use.")
    a(f"- {runs} runs per image ({runs_tag} for the tag image); intervals of the median remain wide for "
      "every design that signs with ML-DSA-44, whose number of rejection rounds depends on the data, so its "
      "runs vary more than the other operations.")
    a("- The classical baseline is one portable C library (Monocypher); see the section on the classical "
      "baseline. The X25519 against ML-KEM-768 comparison holds for portable C on these cores only.")
    a("- The KEM authenticated design is executed here for cost and correctness; its security is checked "
      "in ProVerif in `docs/FORMAL_VERIFICATION.md` section 10 (keys not secret if ML-KEM is broken; authentication "
      "of the vehicle by the ground station proved only with typed static keys).")
    a("- Stack values include the benchmark glue frames and have a 256 B floor; the static session "
      "state (bss) is listed with the code size.")
    a("- The CV32E40P model was built with the BLKANDNBLK check of Verilator switched off for the counter "
      "registers (round 5); counts are checked only by repeatability and by the agreement with round 5 "
      "above.")
    a("")
    a("## Reproduce")
    a("")
    a("Set `WORK_DIR` (round 5 work folder with ibex, mlkem-native, mldsa-native), `CV32_WORK_DIR` "
      "(folder with cv32e40p and its Verilator build), `PROTO_TP` and `PROTO_BUILD` (folders outside the "
      "repository), then:")
    a("")
    a("```")
    a("bash rtlsim/proto/fetch.sh")
    a("bash rtlsim/proto/build.sh ibex && bash rtlsim/proto/build.sh cv32e40p")
    a("bash rtlsim/proto/run.sh ibex && bash rtlsim/proto/run.sh cv32e40p   # about 100 minutes per core")
    a("python3 rtlsim/proto/make_doc.py")
    a("python3 -m unittest discover -s rtlsim -t .")
    a("```")
    a("")
    a("## Sources and licences")
    a("")
    a("- MAVLink message signing guide, https://mavlink.io/en/guide/message_signing.html (read 2026-10-28): "
      "tag formula, 13 B signature field, timestamp rules.")
    a("- MAVLink developer guide introduction, https://mavlink.io/en/ (read 2026-10-28): the message "
      "definitions and the generated C library are MIT licensed. `mavlink_sha256.h` carries a BSD 3 clause "
      "notice (Heimdal, Royal Institute of Technology, Stockholm).")
    a("- Monocypher, https://github.com/LoupVaillant/Monocypher, tag 4.0.3: dual licence BSD-2-Clause or "
      "CC0-1.0 (LICENCE.md at the tag).")
    a("- mlkem-native and mldsa-native: Apache-2.0 OR ISC OR MIT (as round 5).")
    a("")
    (ROOT / "docs" / "RTL_BASELINES.md").write_text("\n".join(L))


def main():
    logs = load_logs()
    prims = build_primitives(logs)
    sessions = build_sessions(logs)
    sizes = build_sizes()
    times = build_time(sessions)
    decomp = build_decomposition(prims, sessions)
    ratios_rows = build_ratios(logs, sessions, decomp)
    res = RTL / "results"
    write_csv(res / "proto_primitives.csv", prims)
    write_csv(res / "proto_sessions.csv", sessions)
    write_csv(res / "proto_sizes.csv", sizes)
    write_csv(res / "proto_time_estimated.csv", times)
    write_csv(res / "proto_decomposition.csv", decomp)
    write_csv(res / "proto_ratios.csv", ratios_rows)
    if sessions:
        make_figure(sessions, ROOT / "docs" / "figures" / "rtl_baselines_vehicle.png")
    write_doc(logs, prims, sessions, sizes, times, decomp, ratios_rows)
    print(f"logs {len(logs)}, primitive rows {len(prims)}, session rows {len(sessions)}")


if __name__ == "__main__":
    main()
