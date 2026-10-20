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

RESULT_COLUMNS = ["experiment", "label", "date_utc", "board", "clock_hz", "flash_ws", "cache",
                  "toolchain", "commit", "library", "scheme", "variant", "operation", "run", "iter",
                  "cycles", "stack_bytes", "unit", "source_log"]
CHECK_COLUMNS = ["experiment", "label", "board", "commit", "scheme", "variant", "run", "check", "ok",
                 "fail", "source_log"]
META_COLUMNS = ["source_log", "key", "value"]

OP_MAP = {"keypair": "keygen", "encaps": "encaps", "decaps": "decaps", "sign": "sign",
          "verify": "verify"}
IMG_RE = re.compile(r"(?:mupq_pqclean_|mupq_)?crypto_(kem|sign)_([a-z0-9-]+)_([a-z0-9]+)_"
                    r"(test|speed|stack|hashing|testvectors)(?:\.(?:elf|bin|hex))?$")
B1_RE = re.compile(r"b1_(mlkem|mldsa)_(\d+)")
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
                "library": "pqm4"}
    m = B1_RE.search(image)
    if m:
        lib = "mlkem-native" if m.group(1) == "mlkem" else "mldsa-native"
        return {"experiment": "B1", "scheme": None, "variant": "portable_c", "kind": "harness",
                "library": lib}
    raise ValueError(f"unknown image name: {image}")


def _base(header, info, ctx, path):
    return {"experiment": info["experiment"], "label": header.get("label", ""),
            "date_utc": header.get("start_utc", ""), "board": header.get("board", ""),
            "clock_hz": ctx.get("clock_hz", ""), "flash_ws": ctx.get("flash_ws", ""),
            "cache": ctx.get("cache", ""), "toolchain": ctx.get("toolchain", ""),
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
    return rows, chk, unknown, meta


def parse_log(path, ctx=None):
    """Parse one raw log. Returns dict with rows, checks, meta, n_lines, n_unrecognised."""
    header, lines = read_capture(path)
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
    failed = sum(int(c["fail"]) for c in checks)
    print(f"logs={len(a.logs)} lines={total} unrecognised={bad} rows={len(rows)} "
          f"checks={len(checks)} failed_checks={failed}")
    return 1 if a.require_all and (bad or failed) else 0


if __name__ == "__main__":
    sys.exit(main())
