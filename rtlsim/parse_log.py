#!/usr/bin/env python3
"""Parser for the ASCII output of the bare metal cycle count harness (rtlsim/sw/bench.c) run on the Ibex
simple system Verilator model. Author: Huda Mueen.

Log line formats:
  CFG,<key>,<value>
  RES,<parameter set>,<operation>,<run index>,<cycles>,<ok|fail>
  DONE,<parameter set>,<number of failures>
Lines of any other form are ignored. A log without a DONE line is reported as incomplete.
"""
import random
import statistics
from dataclasses import dataclass, field


@dataclass
class Record:
    parameter_set: str
    operation: str
    run: int
    cycles: int
    ok: bool


@dataclass
class ParsedLog:
    config: dict = field(default_factory=dict)
    records: list = field(default_factory=list)
    done: bool = False
    failures_reported: int = -1


def parse_lines(lines):
    """Parse an iterable of log lines into a ParsedLog. Raises ValueError on a malformed RES or DONE line."""
    out = ParsedLog()
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        parts = line.split(",")
        tag = parts[0]
        if tag == "CFG" and len(parts) == 3:
            out.config[parts[1]] = parts[2]
        elif tag == "RES":
            if len(parts) != 6 or parts[5] not in ("ok", "fail"):
                raise ValueError(f"malformed RES line: {line!r}")
            out.records.append(Record(parts[1], parts[2], int(parts[3]), int(parts[4]), parts[5] == "ok"))
        elif tag == "DONE":
            if len(parts) != 3:
                raise ValueError(f"malformed DONE line: {line!r}")
            out.done = True
            out.failures_reported = int(parts[2])
    return out


def parse_file(path):
    with open(path, encoding="ascii", errors="replace") as fh:
        return parse_lines(fh)


def bootstrap_median_ci(values, seed=20261020, n_boot=10000, alpha=0.05):
    """Percentile bootstrap interval for the median. With one value, or all values equal, the interval is
    that value (zero width)."""
    vals = list(values)
    if not vals:
        raise ValueError("no values")
    if len(set(vals)) == 1:
        return float(vals[0]), float(vals[0])
    rng = random.Random(seed)
    meds = sorted(statistics.median(rng.choices(vals, k=len(vals))) for _ in range(n_boot))
    lo = meds[int((alpha / 2) * n_boot)]
    hi = meds[min(n_boot - 1, int((1 - alpha / 2) * n_boot))]
    return float(lo), float(hi)


def summarise(records, seed=20261020):
    """Group timed records by (parameter set, operation) and return a list of dicts with n, min, median, max,
    bootstrap 95 percent interval of the median, and the count of passed checks. Records whose operation ends
    in '_rejects_modified' are correctness checks only (not timed); they are attached to the matching
    timed operation as 'negative_ok' and 'negative_n'."""
    timed, negative = {}, {}
    for r in records:
        if r.operation.endswith("_rejects_modified"):
            key = (r.parameter_set, r.operation[: -len("_rejects_modified")])
            negative.setdefault(key, []).append(r)
        else:
            timed.setdefault((r.parameter_set, r.operation), []).append(r)
    rows = []
    for (ps, op), recs in timed.items():
        cyc = [r.cycles for r in recs]
        lo, hi = bootstrap_median_ci(cyc, seed=seed)
        neg = negative.get((ps, op), [])
        rows.append({
            "parameter_set": ps, "operation": op, "n": len(cyc),
            "min": min(cyc), "median": statistics.median(cyc), "max": max(cyc),
            "median_ci95_low": lo, "median_ci95_high": hi,
            "ok": sum(r.ok for r in recs),
            "negative_ok": sum(r.ok for r in neg), "negative_n": len(neg),
        })
    return rows


def correctness_text(row):
    """Plain description of the correctness checks behind a summary row."""
    op = row["operation"]
    base = {
        "decaps": "decaps shared secret equals encaps shared secret",
        "verify": "verify accepts the signature",
        "sign": "sign returned success",
        "keygen": "keygen returned success",
        "encaps": "encaps returned success",
    }.get(op, "call returned success")
    txt = f"{base}: {row['ok']}/{row['n']} pass"
    if row.get("negative_n"):
        txt += f"; modified message rejected: {row['negative_ok']}/{row['negative_n']}"
    return txt
