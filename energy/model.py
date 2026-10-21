"""Energy and CPU headroom model. Author: Huda Mueen.

Arithmetic only: energy per operation = cycles x (current / frequency) x voltage.
Cycle counts come from data/evidence.csv rows (cited by id) or are derived from
published times (time x clock). No cryptographic code is run or implemented here.
"""
import csv
import math
import os
import re
import statistics

import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from shared import inputs as shared_inputs  # noqa: E402

SHARED_PREFIX = "shared:"
SEED = 20261020
NOMINAL_VDD_V = 3.3  # assumption, see workload_assumptions.csv (vdd_v nominal)


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_evidence():
    return {r["id"]: r for r in read_csv(os.path.join(ROOT, "data", "evidence.csv"))}


def resolve_shared(rows):
    """Replace every cell written as shared:<parameter> by the value of that parameter in data/shared_inputs.csv."""
    sh = shared_inputs.values()
    for r in rows:
        for k, v in r.items():
            if isinstance(v, str) and v.startswith(SHARED_PREFIX):
                r[k] = repr(sh[v[len(SHARED_PREFIX):]])
    return rows


def load_local(name):
    return resolve_shared(read_csv(os.path.join(HERE, name)))


def load_assumptions():
    out = {}
    for r in load_local("workload_assumptions.csv"):  # shared:<name> cells resolved by load_local
        out[r["name"]] = {k: float(r[k]) for k in ("low", "nominal", "high")}
    return out


_TIME_RE = re.compile(r"(?:reported time:|boot time|avg time)\s*([0-9]+(?:\.[0-9]+)?)\s*ms")


def parse_time_ms(notes):
    """Return the first published time in ms found in a notes cell, or None."""
    m = _TIME_RE.search(notes or "")
    return float(m.group(1)) if m else None


def cycles_from_time(ms, clock_mhz):
    """Derived cycles = time (ms) x clock (MHz) x 1000."""
    return ms * clock_mhz * 1000.0


def throughput_to_cpb(mb_per_s, clock_mhz):
    """Cycles per byte from a throughput in 10^6 B/s at a clock in MHz."""
    return clock_mhz / mb_per_s


def bench_values(bench, metric):
    return [(float(r["value"]), float(r["clock_mhz"]), r["board"]) for r in bench if r["metric"] == metric]


def sha256_cpb(bench, kind="sw"):
    """List of derived SHA-256 cycles per byte (one per board) for kind 'sw' or 'hw'."""
    return [throughput_to_cpb(v, c) for v, c, _ in bench_values(bench, f"sha256_{kind}_throughput")]


def hmac_sha256_bytes(msg_bytes):
    """Bytes passed through the SHA-256 compression for HMAC-SHA256 of one message.

    Inner hash: 64 B key block + message + 9 B minimum padding, rounded up to 64 B blocks.
    Outer hash: 64 B key block + 32 B inner digest + padding = 2 blocks.
    """
    inner_blocks = math.ceil((64 + msg_bytes + 9) / 64)
    return 64 * (inner_blocks + 2)


def cmap_evidence_id(r):
    """Evidence id behind a cycle_map.csv row (resolves method shared through data/shared_inputs.csv)."""
    if r["method"] == "shared":
        return shared_inputs.evidence_id(r["ref"])
    return r["ref"]


def cycles_for(op, core_class, ev, bench, cmap, msg_bytes=64):
    """Look up cycles for an operation on a core class.

    Returns dict(cycles, cycle_label, source, proxy). Falls back to the
    Cortex-M4 row (marked proxy) when no row exists for the core class.
    """
    rows = [r for r in cmap if r["op"] == op and r["core_class"] == core_class]
    proxy = False
    if not rows:
        rows = [r for r in cmap if r["op"] == op and r["core_class"] == "Cortex-M4"]
        proxy = core_class != "Cortex-M4"
    if not rows:
        raise KeyError(op)
    r = rows[0]
    if r["method"] == "shared":
        cyc = shared_inputs.value(r["ref"])
        src = (shared_inputs.evidence_id(r["ref"]) or r["ref"]) + " (data/shared_inputs.csv " + r["ref"] + ")"
    elif r["method"] == "evidence_cycles":
        cyc = float(ev[r["ref"]]["cycles"])
        src = r["ref"]
    elif r["method"] == "evidence_time":
        e = ev[r["ref"]]
        cyc = cycles_from_time(parse_time_ms(e["compiler_flags_or_notes"]), float(e["clock_mhz"]))
        src = r["ref"] + " (time x clock)"
    elif r["method"] == "benchmark_time":
        vals = [cycles_from_time(v, c) for v, c, _ in bench_values(bench, r["ref"])]
        cyc = statistics.median(vals)
        src = "energy/retrieved_benchmarks.csv " + r["ref"] + " (median of %d boards)" % len(vals)
    elif r["method"] == "hmac_estimate":
        cyc = hmac_sha256_bytes(msg_bytes) * shared_inputs.value("sha256_cpb_sw_m4")
        src = "SHA-256 software throughput median (data/shared_inputs.csv sha256_cpb_sw_m4)"
    else:
        raise ValueError(r["method"])
    label = r["cycle_label"]
    if proxy:
        label = label + "; proxy: Cortex-M4 row used for " + core_class
    return {"cycles": cyc, "cycle_label": label, "source": src, "proxy": proxy}


def energy_uj(cycles, ua_per_mhz, volts):
    """Energy in microjoules: cycles x (uA/MHz x 1e-12 A s per cycle) x V, expressed in uJ."""
    return cycles * ua_per_mhz * volts * 1e-6


def part_supply_options(part):
    """Return a list of (mode, ua_per_mhz, volts, volt_label) for one parts.csv row."""
    out = []
    if part["ua_per_mhz_ldo"]:
        out.append(("LDO", float(part["ua_per_mhz_ldo"]), NOMINAL_VDD_V, "assumption (VDD nominal)"))
    if part["ua_per_mhz_smps"]:
        out.append(("SMPS or stated", float(part["ua_per_mhz_smps"]), float(part["smps_voltage_v"]), "published"))
    if part["current_ma_at_freq"]:
        ua = float(part["current_ma_at_freq"]) * 1000.0 / float(part["freq_mhz_for_current"])
        out.append(("mA at stated MHz", ua, NOMINAL_VDD_V, "assumption (supply not stated in table)"))
    return out


def max_rate_per_s(cycles, clock_mhz, headroom):
    """Maximum sustained operations per second using a fraction `headroom` of the CPU."""
    return headroom * clock_mhz * 1e6 / cycles


def cpu_share(cycles_per_s, clock_mhz):
    return cycles_per_s / (clock_mhz * 1e6)


def workload_cycles_per_h(c, w, design):
    """Cycles per hour for a security workload.

    c: dict op -> cycles. w: dict of workload values. design: 'pq_sig' (ML-DSA-44 per
    command), 'classical' (Ed25519 per command), 'lms' (LMS verify per command, for
    comparison only) or 'mac' (HMAC-SHA256 per command after a post quantum handshake).
    Boot verification: SHA-256 over the image plus one ML-DSA-44 verify (classical: Ed25519).
    Vehicle side of the session handshake as in the mission study and the formal models with design change F1:
    two X25519 scalar multiplications, one ML-KEM-768 encapsulation (the vehicle answers the ground station's
    encapsulation key), one verification of the ground signature and one vehicle signature. A rekey repeats the
    key exchange without signatures (fresh X25519 shares and a fresh ML-KEM encapsulation).
    """
    if design == "classical":
        hs = 2 * c["x25519_shared"] + c["ed25519_verify"] + c["ed25519_sign"]
        rk = 2 * c["x25519_shared"]
        cmd = c["ed25519_verify"]
        bootsig = c["ed25519_verify"]
    else:
        hs = 2 * c["x25519_shared"] + c["mlkem768_encaps"] + c["mldsa44_verify"] + c["mldsa44_sign"]
        rk = 2 * c["x25519_shared"] + c["mlkem768_encaps"]
        cmd = {"pq_sig": c["mldsa44_verify"], "lms": c["lms_verify"], "mac": c["hmac_sha256_msg"]}[design]
        bootsig = c["mldsa44_verify"]
    boot = w["image_mb"] * 1e6 * c["sha256_cpb_sw"] + bootsig
    return (w["handshakes_per_h"] * hs + w["rekeys_per_h"] * rk
            + w["commands_per_s"] * 3600.0 * cmd + w["boots_per_h"] * boot)


def battery_wh(mah, volts):
    return mah * volts / 1000.0


def platform_power_w(battery_wh_value, run_time_h):
    """Average platform power implied by the stated battery energy and run time."""
    return battery_wh_value / run_time_h


def bootstrap_median_ci(values, n=10000, seed=SEED):
    """Bootstrap 95 percent interval for the median."""
    rng = np.random.default_rng(seed)
    v = np.asarray(values, dtype=float)
    if len(v) == 1:
        return float(v[0]), float(v[0])
    meds = np.median(rng.choice(v, size=(n, len(v)), replace=True), axis=1)
    return float(np.percentile(meds, 2.5)), float(np.percentile(meds, 97.5))
