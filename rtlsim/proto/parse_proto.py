#!/usr/bin/env python3
"""Parser and aggregation for the logs of the round 6 protocol benchmark (rtlsim/proto/sw/proto_bench.c).
Author: Huda Mueen.

Log line formats (see rtlsim/proto/sw/proto_util.h):
  CFG,<key>,<value>
  RES,<set>,<operation>,<run>,<cycles>,<ok|fail>
  STK,<set>,<operation>,<run>,<bytes>,<ok|sat>
  CHK,<set>,<check>,<run>,<ok|fail>
  MSG,<set>,<flight>,<direction>,<bytes>
  DONE,<set>,<number of failed checks>
Lines of any other form (simulator messages) are ignored. A log without a DONE line is incomplete.
"""
import os
import statistics
import sys
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import parse_log  # noqa: E402  (round 5 parser: bootstrap interval of the median)

SEED = 20261021

# Steps that make up each side of one unit of work, per design. Session designs: one session start.
SESSION_STEPS = {"vehicle": ["vehicle_f2", "vehicle_f4"],
                 "ground": ["ground_f1", "ground_f3", "ground_accept"]}
UNITS = {
    "classical": [("session start", SESSION_STEPS)],
    "pq_only": [("session start", SESSION_STEPS)],
    "hybrid_f1": [("session start", SESSION_STEPS)],
    "per_command_mldsa44": [("per command, ML-DSA-44 signature",
                             {"vehicle": ["vehicle_verify_command"], "ground": ["ground_sign_command"]})],
    "mavlink_tag": [
        ("per message, tag alone, 60 B frame",
         {"vehicle": ["vehicle_tag_check_frame60"], "ground": ["ground_tag_frame60"]}),
        ("per message, tag alone, COMMAND_LONG",
         {"vehicle": ["vehicle_tag_check_command_long"], "ground": ["ground_tag_command_long"]}),
        ("per message, full path, 60 B frame",
         {"vehicle": ["vehicle_receive_frame60"], "ground": ["ground_pack_signed_frame60"]}),
        ("per message, full path, COMMAND_LONG",
         {"vehicle": ["vehicle_receive_command_long"], "ground": ["ground_pack_signed_command_long"]}),
    ],
}
DESIGNS = ["classical", "pq_only", "hybrid_f1", "per_command_mldsa44", "mavlink_tag"]


@dataclass
class ProtoLog:
    config: dict = field(default_factory=dict)
    res: list = field(default_factory=list)   # (set, op, run, cycles, ok)
    stk: list = field(default_factory=list)   # (set, op, run, bytes, saturated)
    chk: list = field(default_factory=list)   # (set, check, run, ok)
    msg: list = field(default_factory=list)   # (set, flight, direction, bytes)
    done: bool = False
    failures_reported: int = -1


def parse_lines(lines):
    """Parse log lines into a ProtoLog. Raises ValueError on a malformed tagged line."""
    out = ProtoLog()
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        p = line.split(",")
        tag = p[0]
        if tag == "CFG" and len(p) == 3:
            out.config[p[1]] = p[2]
        elif tag == "RES":
            if len(p) != 6 or p[5] not in ("ok", "fail"):
                raise ValueError(f"malformed RES line: {line!r}")
            out.res.append((p[1], p[2], int(p[3]), int(p[4]), p[5] == "ok"))
        elif tag == "STK":
            if len(p) != 6 or p[5] not in ("ok", "sat"):
                raise ValueError(f"malformed STK line: {line!r}")
            out.stk.append((p[1], p[2], int(p[3]), int(p[4]), p[5] == "sat"))
        elif tag == "CHK":
            if len(p) != 5 or p[4] not in ("ok", "fail"):
                raise ValueError(f"malformed CHK line: {line!r}")
            out.chk.append((p[1], p[2], int(p[3]), p[4] == "ok"))
        elif tag == "MSG":
            if len(p) != 5:
                raise ValueError(f"malformed MSG line: {line!r}")
            out.msg.append((p[1], p[2], p[3], int(p[4])))
        elif tag == "DONE":
            if len(p) != 3:
                raise ValueError(f"malformed DONE line: {line!r}")
            out.done = True
            out.failures_reported = int(p[2])
    return out


def parse_file(path):
    with open(path, encoding="ascii", errors="replace") as fh:
        return parse_lines(fh)


def op_summary(log, seed=SEED):
    """One dict per (set, operation): n, min, median, max, bootstrap 95 percent interval of the median,
    passed calls, largest peak stack and whether the painted area was used up in any run."""
    groups, stacks = {}, {}
    for s, op, run, cyc, ok in log.res:
        groups.setdefault((s, op), []).append((run, cyc, ok))
    for s, op, run, b, sat in log.stk:
        stacks.setdefault((s, op), []).append((b, sat))
    rows = []
    for (s, op), recs in groups.items():
        cyc = [c for _, c, _ in recs]
        lo, hi = parse_log.bootstrap_median_ci(cyc, seed=seed)
        st = stacks.get((s, op), [])
        rows.append({"set": s, "operation": op, "n": len(cyc), "min": min(cyc),
                     "median": statistics.median(cyc), "max": max(cyc), "ci_low": lo, "ci_high": hi,
                     "ok": sum(ok for _, _, ok in recs),
                     "stack_max": max((b for b, _ in st), default=None),
                     "stack_saturated": any(sat for _, sat in st)})
    return rows


def checks_for(log, set_name, run=None):
    """(passed, total) of the CHK lines of a set, for one run or for all runs."""
    c = [ok for s, _, r, ok in log.chk if s == set_name and (run is None or r == run)]
    return sum(c), len(c)


def unit_totals(log, set_name, steps, seed=SEED):
    """Sum the cycles of the steps of one side for every run and summarise across runs.

    Returns a dict with per run totals, n, median, interval, min, max, the peak stack over the steps and
    runs, the number of runs whose steps all succeeded and whose checks all passed, and the run count."""
    by_run = {}
    for s, op, run, cyc, ok in log.res:
        if s == set_name and op in steps:
            by_run.setdefault(run, {})[op] = (cyc, ok)
    stack = {}
    for s, op, run, b, sat in log.stk:
        if s == set_name and op in steps:
            stack.setdefault(run, []).append((b, sat))
    totals, good = [], 0
    for run in sorted(by_run):
        d = by_run[run]
        if set(d) != set(steps):
            continue  # incomplete run (log cut off); not counted
        totals.append(sum(c for c, _ in d.values()))
        passed, n = checks_for(log, set_name, run)
        if all(ok for _, ok in d.values()) and passed == n:
            good += 1
    if not totals:
        return None
    lo, hi = parse_log.bootstrap_median_ci(totals, seed=seed)
    all_st = [b for v in stack.values() for b, _ in v]
    return {"totals": totals, "n": len(totals), "median": statistics.median(totals), "min": min(totals),
            "max": max(totals), "ci_low": lo, "ci_high": hi, "stack_max": max(all_st) if all_st else None,
            "stack_saturated": any(sat for v in stack.values() for _, sat in v), "runs_correct": good}


def flights(log, set_name):
    """[(flight, direction, bytes)] of a set, in log order."""
    return [(f, d, b) for s, f, d, b in log.msg if s == set_name]


def read_size_sections(path):
    """Parse a concatenation of `size -A` outputs into {image: {section: size}}."""
    out, cur = {}, None
    with open(path) as fh:
        for line in fh:
            line = line.rstrip()
            if line.endswith(":") and ".elf" in line:
                cur = line.split(".elf")[0].strip()
                out[cur] = {}
            elif cur and line.startswith(".") and len(line.split()) >= 2:
                name, size = line.split()[:2]
                out[cur][name] = int(size)
    return out


TEXT_SECTIONS = (".vectors", ".init", ".text", ".rodata", ".eh_frame", ".init_array")
DATA_SECTIONS = (".data", ".sdata")
BSS_SECTIONS = (".bss", ".sbss")


def image_sizes(sections):
    """text (code and read only data), data and bss of one image, excluding the stack and heap
    reservations of the link scripts, so that both cores are counted the same way."""
    return {"text": sum(sections.get(s, 0) for s in TEXT_SECTIONS),
            "data": sum(sections.get(s, 0) for s in DATA_SECTIONS),
            "bss": sum(sections.get(s, 0) for s in BSS_SECTIONS)}
