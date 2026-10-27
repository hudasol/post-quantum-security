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
  docs/figures/rtl_baselines_vehicle.png   vehicle side cycles per design and core
  docs/RTL_BASELINES.md
Usage: python3 rtlsim/proto/make_doc.py
"""
import csv
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
IMAGES = ["primitives", "classical", "pq_only", "hybrid_f1", "per_command_mldsa44", "mavlink_tag"]
SESSION_DESIGNS = ["classical", "pq_only", "hybrid_f1"]
DESIGN_NAME = {
    "classical": "Classical session (X25519, Ed25519 by both sides, key confirmation)",
    "pq_only": "Post quantum only session (ML-KEM-768, ML-DSA-44 by both sides, key confirmation)",
    "hybrid_f1": "Hybrid session with F1 (X25519 plus ML-KEM-768, ML-DSA-44 by both sides, key confirmation)",
    "per_command_mldsa44": "ML-DSA-44 signature per command",
    "mavlink_tag": "MAVLink 2 signing tag per message",
}
CLOCKS_MHZ = [64, 168]
PRIM_ORDER = ["x25519_keygen", "x25519_shared", "ed25519_keygen", "ed25519_sign", "ed25519_verify",
              "sha256_60B", "mavlink_tag_frame60", "shake256_kdf", "shake256_confirm_tag",
              "shake256_transcript_hybrid", "mlkem768_keygen", "mlkem768_encaps", "mlkem768_decaps",
              "mldsa44_keygen", "mldsa44_sign", "mldsa44_verify"]
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
                    })
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
    names = ["classical\nsession", "post quantum\nonly session", "hybrid\nwith F1",
             "ML-DSA-44\nper command", "MAVLink 2 tag\nper message"]
    fig, ax = plt.subplots(figsize=(7.5, 3.8))
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


def write_doc(logs, prims, sessions, sizes, times):
    L = []
    a = L.append
    info = {c: read_build_info(c) for c in CORES}
    bi = info["ibex"] or info["cv32e40p"]
    runs = bi.get("runs", "")
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
    a(f"- Runs and seeds: {runs} runs per image; run r reseeds the test generator with {seed} + r "
      f"(seed block {seed} to {int(seed) + int(runs) - 1 if seed and runs else ''}). The generator "
      "(`rtlsim/sw/bench_rng.c`, splitmix64) is a deterministic test generator and is NOT a secure random "
      "number generator. Medians with a bootstrap 95 percent interval of the median (10,000 resamples, "
      f"seed {pp.SEED}); with five runs the interval is coarse.")
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
      "MAVLink frame and a modified payload are rejected.")
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
      "command design, one message for the tag. Source: `rtlsim/results/proto_sessions.csv`. Message "
      "bytes are the sizes of the buffers the program built (`MSG` lines of the logs).")
    a("")
    a("| Design | Unit | Side | Ibex median cycles | CV32E40P median cycles | Peak stack Ibex / CV32E40P (B) | "
      "Bytes on air per unit | Runs correct Ibex / CV32E40P |")
    a("|---|---|---|---|---|---|---|---|")
    for design in pp.DESIGNS:
        for unit, _ in pp.UNITS[design]:
            for side in ("vehicle", "ground"):
                ri = get(sessions, core="ibex", design=design, unit=unit, side=side)
                rc = get(sessions, core="cv32e40p", design=design, unit=unit, side=side)
                if not ri and not rc:
                    continue
                r0 = ri or rc
                a(f"| {DESIGN_NAME[design]} | {unit} | {side} | "
                  f"{fmt_int(ri['cycles_median']) if ri else 'not run'} | "
                  f"{fmt_int(rc['cycles_median']) if rc else 'not run'} | "
                  f"{ri['peak_stack_bytes'] if ri else ''} / {rc['peak_stack_bytes'] if rc else ''} | "
                  f"{r0['bytes_total']} | "
                  f"{(str(ri['runs_correct']) + '/' + str(ri['n_runs'])) if ri else ''} / "
                  f"{(str(rc['runs_correct']) + '/' + str(rc['n_runs'])) if rc else ''} |")
    a("")
    a("Bytes per flight (from the logs): " + "; ".join(
        f"{d}: {get(sessions, design=d)['bytes_per_flight']}" for d in pp.DESIGNS if get(sessions, design=d)) + ".")
    a("")

    # Ratios
    a("## Ratios (label: RTL simulated, derived from the medians)")
    a("")
    a("| Ratio | Side | Ibex | CV32E40P |")
    a("|---|---|---|---|")
    pairs = [("hybrid_f1", "classical"), ("pq_only", "classical"), ("hybrid_f1", "pq_only")]
    ratios = {}
    for num, den in pairs:
        for side in ("vehicle", "ground"):
            vals = []
            for core in CORES:
                n = get(sessions, core=core, design=num, side=side)
                d = get(sessions, core=core, design=den, side=side)
                v = n["cycles_median"] / d["cycles_median"] if n and d else None
                ratios[(num, den, side, core)] = v
                vals.append(fmt_ratio(v) if v else "not available")
            a(f"| {num} over {den} | {side} | {vals[0]} | {vals[1]} |")
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

    # Per command against session
    a("### Signature per command against a session with a tag per message")
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
    a("| Image | Ibex text | Ibex data | Ibex bss | CV32E40P text | CV32E40P bss | Ibex text, unused sections removed |")
    a("|---|---|---|---|---|---|---|")
    for img in IMAGES:
        si = get(sizes, core="ibex", image=img, variant="timing")
        sc = get(sizes, core="cv32e40p", image=img, variant="timing")
        sg = get(sizes, core="ibex", image=img, variant="gc")
        if not si and not sc:
            continue
        a(f"| {img} | {fmt_int(si['text_bytes']) if si else ''} | {si['data_bytes'] if si else ''} | "
          f"{fmt_int(si['bss_bytes']) if si else ''} | {fmt_int(sc['text_bytes']) if sc else ''} | "
          f"{fmt_int(sc['bss_bytes']) if sc else ''} | {fmt_int(sg['text_bytes']) if sg else ''} |")
    a("")
    for variant, what in (("timing", "simulated images"), ("gc", "size only build with unused sections removed")):
        h = get(sizes, core="ibex", image="hybrid_f1", variant=variant)
        c = get(sizes, core="ibex", image="classical", variant=variant)
        p = get(sizes, core="ibex", image="pq_only", variant=variant)
        if h and c and p:
            a(f"- Ibex, {what}: hybrid over classical text {h['text_bytes'] / c['text_bytes']:.2f}; post quantum "
              f"only over classical {p['text_bytes'] / c['text_bytes']:.2f}.")
    a("")
    a("The simulated classical image links the whole Monocypher object, which also holds functions the "
      "protocol never calls (for example Argon2, BLAKE2b, ChaCha20 and Poly1305), so its text is large "
      "beside the post quantum only image; the size only build removes them.")
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
    a("- Five runs per image; intervals of the median are coarse. Signing with ML-DSA-44 has a data "
      "dependent number of rejection rounds, so its runs vary more than the other operations.")
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
    a("bash rtlsim/proto/run.sh ibex && bash rtlsim/proto/run.sh cv32e40p")
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
    res = RTL / "results"
    write_csv(res / "proto_primitives.csv", prims)
    write_csv(res / "proto_sessions.csv", sessions)
    write_csv(res / "proto_sizes.csv", sizes)
    write_csv(res / "proto_time_estimated.csv", times)
    if sessions:
        make_figure(sessions, ROOT / "docs" / "figures" / "rtl_baselines_vehicle.png")
    write_doc(logs, prims, sessions, sizes, times)
    print(f"logs {len(logs)}, primitive rows {len(prims)}, session rows {len(sessions)}")


if __name__ == "__main__":
    main()
