#!/usr/bin/env python3
"""Parse raw capture logs (capture.py format) into the board kit result CSV and a checks CSV.

Author: Huda Mueen. Two firmware output formats are understood:
  B0, pqm4 binaries (speed, stack, test): "keypair cycles:" then a value line, "+" between
      iterations, "#" at the end; "keypair stack usage:" then a value line; OK and ERROR lines.
  B1, repository harness through the pqm4 platform layer: META, BENCH, STACK and CHECK lines
      (bench/mcu/README.md), plus the glue META lines from b1/b1_main.c.
Every line of every log is classified. A line that is not a known record or known framing is
counted as unrecognised; parse_log returns the counts so a caller can require 100 percent.

Result CSV schema (RESULT_COLUMNS, one row per measurement; documented in RESULT_TEMPLATE.csv):
  experiment   B0 or B1
  label        evidence label from the capture header: board measured or emulated
  date_utc     capture start time
  board        board name from the capture header
  clock_hz     core clock in Hz read back at the board (B1: META clock_hz_rcc; B0: --clock-hz)
  flash_ws     flash wait states read back at the board
  cache        cache and prefetch bits read back at the board
  cache_pass   on (state left by the clock set up) or off (BENCH_CACHE_OFF image); from the image
               name, checked against the META cache_pass line of B1 images (a mismatch is a
               failed check). B0 pqm4 images are always the on pass.
  toolchain    arm-none-eabi-gcc version line
  commit       pqm4 commit (B0) or library commit (B1)
  library      pqm4, mlkem-native or mldsa-native
  scheme       ML-KEM-768, ML-DSA-44, ...
  variant      pqm4 implementation (clean, m4fspeed, m4f, m4fstack) or portable_c for B1
  operation    keygen, encaps, decaps, sign, verify
  run          power cycle number (capture header)
  iter         iteration index within the run (0 based); empty for stack rows
  cycles       cycles for one operation (B0: SysTick via hal_get_time; B1: DWT CYCCNT)
  stack_bytes  stack high water mark for the operation (one row per operation and run)
  unit         cycles or bytes
  source_log   file name of the raw log
"""
import argparse
import csv
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kit_config as K  # noqa: E402

RESULT_COLUMNS = ["experiment", "label", "date_utc", "board", "clock_hz", "flash_ws", "cache",
                  "cache_pass", "toolchain", "commit", "library", "scheme", "variant", "operation", "run", "iter",
                  "cycles", "stack_bytes", "unit", "source_log"]
CHECK_COLUMNS = ["experiment", "label", "board", "commit", "scheme", "variant", "run", "check", "ok",
                 "fail", "source_log"]
META_COLUMNS = ["source_log", "key", "value"]

OP_MAP = {"keypair": "keygen", "encaps": "encaps", "decaps": "decaps", "sign": "sign",
          "verify": "verify"}
IMG_RE = re.compile(r"(?:mupq_pqclean_|mupq_)?crypto_(kem|sign)_([a-z0-9-]+)_([a-z0-9]+)_"
                    r"(test|speed|stack|hashing|testvectors)(?:\.(?:elf|bin|hex))?$")
B1_RE = re.compile(r"b1_(mlkem|mldsa)_(\d+)(_cacheoff)?")
TS_LINE = re.compile(r"^(\d{4}-\d\d-\d\dT[0-9:.]+Z)\t(.*)$")
FRAMING = {"", "==========================", "+", "#"}
# Known pqm4 status lines (test, speed and stack binaries at the pinned commit).
PQM4_OK = {
    "OK KEYS": "roundtrip", "OK invalid sk_a": "invalid_sk_rejected",
    "OK invalid ciphertext": "invalid_ct_rejected",
    "OK Signature did verify correctly!": "sign_verify",
    "OK Signature did not verify correctly under wrong public key!": "wrong_pk_rejected",
    "Signature valid!": "sign_verify",
}
PQM4_ERR = {
    "ERROR KEYS": "roundtrip", "ERROR invalid sk_a": "invalid_sk_rejected",
    "ERROR invalid ciphertext": "invalid_ct_rejected",
    "ERROR Signature did not verify correctly!": "sign_verify",
    "ERROR Signature did verify correctly under wrong public key!": "wrong_pk_rejected",
    "ERROR canary overwritten": "canary",
}
PQM4_PROGRESS = {"DONE key pair generation!", "DONE encapsulation!", "DONE decapsulation!",
                 "crypto_sign_keypair DONE.", "crypto_sign DONE.", "crypto_sign_open DONE."}


def read_capture(path):
    """Return (header dict, list of (timestamp, line)) from a capture.py raw log."""
    header, lines = {}, []
    with open(path, encoding="ascii", errors="replace") as fh:
        for raw in fh:
            raw = raw.rstrip("\n")
            if raw.startswith("# capture,"):
                _, k, v = raw.split(",", 2)
                header[k] = v
                continue
            m = TS_LINE.match(raw)
            if not m:
                raise ValueError(f"{path}: line is not in capture format: {raw[:60]!r}")
            lines.append((m.group(1), m.group(2)))
    return header, lines


def image_info(image):
    """Map a pqm4 image name to (kind, scheme, variant, binary type) or a B1 image to its set."""
    m = IMG_RE.search(image)
    if m:
        return {"experiment": "B0", "scheme": m.group(2).upper(), "variant": m.group(3), "kind": m.group(4),
                "library": "pqm4", "cache_pass": "on"}
    m = B1_RE.search(image)
    if m:
        lib = "mlkem-native" if m.group(1) == "mlkem" else "mldsa-native"
        return {"experiment": "B1", "scheme": None, "variant": "portable_c", "kind": "harness",
                "library": lib, "cache_pass": "off" if m.group(3) else "on"}
    raise ValueError(f"unknown image name: {image}")


def _base(header, info, ctx, path):
    return {"experiment": info["experiment"], "label": header.get("label", ""),
            "date_utc": header.get("start_utc", ""), "board": header.get("board", ""),
            "clock_hz": ctx.get("clock_hz", ""), "flash_ws": ctx.get("flash_ws", ""),
            "cache": ctx.get("cache", ""), "cache_pass": info.get("cache_pass", "on"),
            "toolchain": ctx.get("toolchain", ""),
            "commit": ctx.get("commit", ""), "library": info["library"],
            "scheme": info["scheme"] or "", "variant": info["variant"], "run": header.get("run", ""),
            "source_log": os.path.basename(path)}


def parse_pqm4(lines, header, info, ctx, path):
    rows, checks, unknown = [], {}, []
    it = 0
    pending = None  # (operation, 'cycles'|'stack')
    base = _base(header, info, ctx, path)
    for _, line in lines:
        s = line.strip()
        if pending is not None:
            if not s.isdigit():
                unknown.append(line)
                pending = None
                continue
            op, what = pending
            row = dict(base, operation=op, iter="", cycles="", stack_bytes="")
            if what == "cycles":
                row.update(iter=str(it), cycles=s, unit="cycles")
            else:
                row.update(stack_bytes=s, unit="bytes")
            rows.append(row)
            pending = None
            continue
        m = re.match(r"^(keypair|encaps|decaps|sign|verify) (cycles|stack usage):$", s)
        if m:
            pending = (OP_MAP[m.group(1)], "cycles" if m.group(2) == "cycles" else "stack")
            continue
        if s == "+":
            if info["kind"] == "speed":
                it += 1
            continue
        if s in FRAMING or s in PQM4_PROGRESS:
            continue
        if s in PQM4_OK:
            checks.setdefault(PQM4_OK[s], [0, 0])[0] += 1
            continue
        if s in PQM4_ERR:
            checks.setdefault(PQM4_ERR[s], [0, 0])[1] += 1
            continue
        unknown.append(line)
    chk = [dict(experiment=base["experiment"], label=base["label"], board=base["board"],
                commit=base["commit"], scheme=base["scheme"], variant=base["variant"],
                run=base["run"], check=f"{info['kind']}:{k}", ok=v[0], fail=v[1],
                source_log=base["source_log"]) for k, v in sorted(checks.items())]
    return rows, chk, unknown, {}


def board_check(header, meta, base, rows):
    """Check that the board named in the capture header is the one the firmware reports.

    B1 images print META,platform,<platform> (b1/b1_main.c). A header board of another platform
    is a failed check, so a Cortex-M33 log captured under the Cortex-M4 board name (or the
    reverse) cannot pass parse.py --require-all."""
    fw = (meta.get("platform") or "").split(" ")[0]
    if fw not in K.PLATFORMS:
        return []
    same = K.board_platform(header.get("board", "")) == fw
    return [dict(experiment="B1", label=base["label"], board=base["board"], commit=base["commit"],
                 scheme=rows[0]["scheme"] if rows else "", variant=base["variant"], run=base["run"],
                 check=f"board:header_matches_firmware_{fw}", ok=int(same), fail=int(not same),
                 source_log=base["source_log"])]


def parse_b1(lines, header, info, ctx, path):
    rows, chk, unknown, meta = [], [], [], {}
    for _, line in lines:
        s = line.strip()
        if s in FRAMING:
            continue
        f = s.split(",")
        if f[0] == "META" and len(f) >= 3:
            meta[f[1]] = ",".join(f[2:])
            continue
        if f[0] in ("BENCH", "STACK", "CHECK"):
            continue  # second pass, once META is known
        unknown.append(line)
    c2 = dict(ctx)
    if meta.get("clock_hz_rcc", "").isdigit():
        c2.setdefault("clock_hz", meta["clock_hz_rcc"])
    elif "clock_hz_rcc" in meta:
        c2.setdefault("clock_hz", meta["clock_hz_rcc"])
    for k in ("flash_ws", "cache"):
        if k in meta:
            c2.setdefault(k, meta[k])
    if "compiler" in meta:
        c2.setdefault("toolchain", "arm-none-eabi-gcc " + meta["compiler"])
    if "lib" in meta:
        mm = re.search(r"commit ([0-9a-f]{40})", meta["lib"])
        if mm:
            c2.setdefault("commit", mm.group(1))
    base = _base(header, info, c2, path)
    for _, line in lines:
        f = line.strip().split(",")
        if f[0] == "BENCH" and len(f) == 8:
            _, alg, param, op, _rid, it, val, unit = f
            if unit != "cycles":
                unknown.append(line)
                continue
            rows.append(dict(base, scheme=param, operation=op, iter=it, cycles=val,
                             stack_bytes="", unit="cycles"))
        elif f[0] == "STACK" and len(f) == 5:
            _, alg, param, op, b = f
            rows.append(dict(base, scheme=param, operation=op, iter="", cycles="",
                             stack_bytes=b, unit="bytes"))
        elif f[0] == "CHECK" and len(f) == 6:
            _, alg, param, what, ok, fail = f
            chk.append(dict(experiment="B1", label=base["label"], board=base["board"],
                            commit=base["commit"], scheme=param, variant=base["variant"],
                            run=base["run"], check=f"harness:{what}", ok=int(ok), fail=int(fail),
                            source_log=base["source_log"]))
        elif f[0] in ("BENCH", "STACK", "CHECK"):
            unknown.append(line)
    if "cache_pass" in meta:
        same = meta["cache_pass"] == info.get("cache_pass")
        chk.append(dict(experiment="B1", label=base["label"], board=base["board"],
                        commit=base["commit"], scheme=rows[0]["scheme"] if rows else "",
                        variant=base["variant"], run=base["run"],
                        check=f"cache_pass_{info.get('cache_pass')}:image_matches_firmware",
                        ok=int(same), fail=int(not same), source_log=base["source_log"]))
    if info.get("cache_pass") == "off" and base["label"] != "emulated":
        applied = meta.get("cache_off_applied") == "1"
        chk.append(dict(experiment="B1", label=base["label"], board=base["board"],
                        commit=base["commit"], scheme=rows[0]["scheme"] if rows else "",
                        variant=base["variant"], run=base["run"],
                        check="cache_pass_off:writes_applied_at_zero_wait_states",
                        ok=int(applied), fail=int(not applied), source_log=base["source_log"]))
    chk += board_check(header, meta, base, rows)
    return rows, chk, unknown, meta


def parse_log(path, ctx=None):
    """Parse one raw log. Returns dict with rows, checks, meta, n_lines, n_unrecognised."""
    header, lines = read_capture(path)
    if not header.get("board"):
        raise ValueError(f"{path}: capture header has no board; capture again with capture.py --board")
    info = image_info(header.get("image", ""))
    ctx = dict(ctx or {})
    if header.get("label") == "emulated":
        for k in ("clock_hz", "flash_ws", "cache"):
            ctx.setdefault(k, "emulated")
    fn = parse_pqm4 if info["experiment"] == "B0" else parse_b1
    rows, chk, unknown, meta = fn(lines, header, info, ctx, path)
    return {"rows": rows, "checks": chk, "meta": meta, "header": header, "n_lines": len(lines),
            "n_unrecognised": len(unknown), "unrecognised": unknown[:20]}


def write_csv(path, columns, rows):
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


TEMPLATE_ROW = {
    "experiment": "<B0|B1>", "label": "planned", "date_utc": "<capture start, UTC>",
    "board": "<board name and chip marking>", "clock_hz": "<read back, Hz>",
    "flash_ws": "<FLASH_ACR latency read back>", "cache": "<icache dcache prefetch bits>",
    "cache_pass": "<on|off>",
    "toolchain": "<arm-none-eabi-gcc --version first line>",
    "commit": "<pqm4 or library commit>", "library": "<pqm4|mlkem-native|mldsa-native>",
    "scheme": "<ML-KEM-768|ML-DSA-44|...>", "variant": "<clean|m4fspeed|m4f|portable_c>",
    "operation": "<keygen|encaps|decaps|sign|verify>", "run": "<power cycle 1..3>",
    "iter": "<iteration, 0 based; empty for stack>", "cycles": "<cycles; empty for stack>",
    "stack_bytes": "<bytes; empty for cycles>", "unit": "<cycles|bytes>",
    "source_log": "<raw log file name>"}


def write_template(path):
    """Result template: the header plus one placeholder row labelled planned (no data)."""
    write_csv(path, RESULT_COLUMNS, [TEMPLATE_ROW])


# Energy measurements (docs/BOARD_RUN_PROTOCOL.md section 10). One row per operation phase,
# written by hand or by a power analyzer export at the bench. Inputs are board measured.
ENERGY_COLUMNS = ["label", "date_utc", "board", "platform", "image", "cache_pass", "run", "scheme",
                  "operation", "method", "instrument", "jumper", "supply_v", "current_ma_mean",
                  "current_ma_idle", "charge_uc", "n_ops", "window_s", "note"]
ENERGY_OUT_COLUMNS = ENERGY_COLUMNS + [
    "cycles_board_measured_mean", "clock_hz", "time_s_per_op_board_measured",
    "energy_uj_per_op_board_measured", "energy_uj_per_op_net_of_idle_board_measured",
    "energy_source"]
ENERGY_METHODS = ("multimeter_phase", "analyzer_gpio_window")


def read_energy(path):
    """Read an energy CSV; check the header and the method of every row."""
    with open(path, newline="") as fh:
        rd = csv.DictReader(fh)
        missing = [c for c in ENERGY_COLUMNS if c not in (rd.fieldnames or [])]
        if missing:
            raise ValueError(f"{path}: missing energy columns {missing}")
        rows = list(rd)
    for r in rows:
        if r["method"] not in ENERGY_METHODS:
            raise ValueError(f"{path}: unknown method {r['method']!r}")
    return rows


def _f(x):
    return float(x) if x not in ("", None) else None


def energy_rows(energy, results):
    """Derive energy per operation.

    analyzer_gpio_window: the analyzer integrates charge over the window in which the firmware
        holds a GPIO marker high around n_ops operations: E = V x charge / n_ops.
    multimeter_phase: the meter's average current over one operation phase of a harness image (the
        phase is delimited by the BENCH line timestamps in the capture log). The time per operation
        is the board measured mean cycles of that image, scheme, operation and cache pass divided by
        the clock read back: E = V x I_mean x cycles / clock. The value net of idle subtracts the
        idle current measured with the board held in reset at the same supply.
    """
    cyc = {}
    clock = {}
    for r in results:
        if r.get("cycles") in ("", None):
            continue
        k = (r["board"], r.get("cache_pass", "on"), r["scheme"].upper(), r["operation"])
        cyc.setdefault(k, []).append(float(r["cycles"]))
        if str(r.get("clock_hz", "")).isdigit():
            clock[k] = float(r["clock_hz"])
    out = []
    for e in energy:
        row = dict.fromkeys(ENERGY_OUT_COLUMNS, "")
        row.update(e)
        v = _f(e["supply_v"])
        if e["method"] == "analyzer_gpio_window":
            q, n = _f(e["charge_uc"]), _f(e["n_ops"])
            if v is not None and q is not None and n:
                row["energy_uj_per_op_board_measured"] = f"{v * q / n:.3f}"
                if _f(e["window_s"]) is not None:
                    row["time_s_per_op_board_measured"] = f"{_f(e['window_s']) / n:.6f}"
                row["energy_source"] = "supply_v x charge_uc / n_ops"
        else:
            k = (e["board"], e["cache_pass"], e["scheme"].upper(), e["operation"])
            i_mean, i_idle = _f(e["current_ma_mean"]), _f(e["current_ma_idle"])
            if k in cyc and k in clock and v is not None and i_mean is not None:
                c = sum(cyc[k]) / len(cyc[k])
                t = c / clock[k]
                row.update(cycles_board_measured_mean=f"{c:.0f}", clock_hz=f"{clock[k]:.0f}",
                           time_s_per_op_board_measured=f"{t:.6f}",
                           energy_uj_per_op_board_measured=f"{v * i_mean * 1e-3 * t * 1e6:.3f}",
                           energy_source="supply_v x current_ma_mean x cycles / clock_hz")
                if i_idle is not None:
                    row["energy_uj_per_op_net_of_idle_board_measured"] = \
                        f"{v * (i_mean - i_idle) * 1e-3 * t * 1e6:.3f}"
            else:
                row["energy_source"] = "no matching board measured cycles; energy not derived"
        out.append(row)
    return out


def write_energy_template(path):
    write_csv(path, ENERGY_COLUMNS, [{
        "label": "planned", "date_utc": "<UTC>", "board": "<board name as in the capture header>",
        "platform": "<nucleo-l4r5zi|nucleo-l552ze-q>", "image": "<image name>",
        "cache_pass": "<on|off>", "run": "<power cycle>", "scheme": "<ML-KEM-768|...>",
        "operation": "<keygen|encaps|decaps|sign|verify>",
        "method": "<multimeter_phase|analyzer_gpio_window>",
        "instrument": "<make, model, range>", "jumper": "<IDD jumper name from the board manual>",
        "supply_v": "<V at the jumper>", "current_ma_mean": "<mA, meter average over the phase>",
        "current_ma_idle": "<mA, board held in reset>", "charge_uc": "<uC over the window (analyzer)>",
        "n_ops": "<operations inside the window (analyzer)>", "window_s": "<s (analyzer)>",
        "note": ""}])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("logs", nargs="+")
    ap.add_argument("--out", required=True, help="result CSV")
    ap.add_argument("--checks-out", required=True)
    ap.add_argument("--meta-out", default=None)
    ap.add_argument("--clock-hz", default="", help="B0: core clock read back at the board")
    ap.add_argument("--flash-ws", default="", help="B0: FLASH_ACR latency read back at the board")
    ap.add_argument("--cache", default="", help="B0: cache and prefetch bits read back")
    ap.add_argument("--toolchain", default="")
    ap.add_argument("--commit", default="", help="B0: pqm4 commit")
    ap.add_argument("--energy", default=None, help="energy CSV (ENERGY_TEMPLATE.csv format)")
    ap.add_argument("--energy-out", default=None, help="energy per operation CSV")
    ap.add_argument("--require-all", action="store_true",
                    help="exit 1 if any line is unrecognised or a check failed")
    a = ap.parse_args(argv)
    ctx = {k: v for k, v in (("clock_hz", a.clock_hz), ("flash_ws", a.flash_ws),
                             ("cache", a.cache), ("toolchain", a.toolchain),
                             ("commit", a.commit)) if v}
    rows, checks, metas, bad, total = [], [], [], 0, 0
    for p in a.logs:
        r = parse_log(p, ctx)
        rows += r["rows"]
        checks += r["checks"]
        metas += [{"source_log": os.path.basename(p), "key": k, "value": v}
                  for k, v in r["meta"].items()]
        total += r["n_lines"]
        bad += r["n_unrecognised"]
        for u in r["unrecognised"]:
            print(f"UNRECOGNISED {os.path.basename(p)}: {u!r}", file=sys.stderr)
    write_csv(a.out, RESULT_COLUMNS, rows)
    write_csv(a.checks_out, CHECK_COLUMNS, checks)
    if a.meta_out:
        write_csv(a.meta_out, META_COLUMNS, metas)
    if a.energy:
        er = energy_rows(read_energy(a.energy), rows)
        write_csv(a.energy_out or os.path.splitext(a.out)[0] + "_energy.csv", ENERGY_OUT_COLUMNS,
                  er)
        print(f"energy rows={len(er)} derived="
              f"{sum(1 for r in er if r['energy_uj_per_op_board_measured'])}")
    failed = sum(int(c["fail"]) for c in checks)
    print(f"logs={len(a.logs)} lines={total} unrecognised={bad} rows={len(rows)} "
          f"checks={len(checks)} failed_checks={failed}")
    return 1 if a.require_all and (bad or failed) else 0


if __name__ == "__main__":
    sys.exit(main())
