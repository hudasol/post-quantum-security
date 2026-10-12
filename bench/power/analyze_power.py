#!/usr/bin/env python3
"""Energy per operation from a current trace with a GPIO marker (stdlib only).

INPUT CSV (header required): time_s,current_a,marker
  time_s     sample time in seconds (monotonic; uniform or not - trapezoid rule is used)
  current_a  current drawn by the board's MCU supply rail, in amperes
  marker     0/1 digital level from a GPIO that the firmware raises for the duration of
             ONE measured window (see docs/BENCHMARK_PLAN.md section 6)
Typical sources: Nordic PPK2 export (100 ksps) or Joulescope CSV export, with the DUT GPIO wired
to the logic input. Re-map columns with --col-* if your exporter uses other names.

METHOD
  1. Windows = contiguous runs of marker==1.  window energy  E_w = V * integral(I dt).
  2. Idle baseline: median current over samples with marker==0 AND at least --guard-ms away
     from any window edge (so ramp-up/ramp-down does not leak in).  This is the MCU running
     its idle/busy-wait loop, not sleep, and is subtracted as  E_idle = V * I_base * duration.
     Net energy is reported as well as gross; the report must state which is used.
  3. --ops-per-window K: if each marker window covers K back-to-back operations (needed when the
     sampler is too slow to resolve one op), energy/op = E_w / K.
  4. Per-window values give median, quartiles, min, max, n.  95% CI of the median: seeded
     percentile bootstrap.

LIMITS (stated so nobody over-reads the output)
  * Only as good as the instrument: an INA219/INA228 (I2C monitors, conversion 50 us-4 ms) cannot
    resolve one sub-millisecond operation. Use --ops-per-window >> 1 with those.
  * Measures rail energy of whatever the probe sees (MCU + board regulators/LEDs). Declare the
    measurement point and the supply voltage; use --volts for the rail voltage.
  * STATUS: tested only on SYNTHETIC traces (make_synthetic.py). NOT tested on a real instrument.
"""
import argparse
import csv
import random
import statistics
import sys


def pct(sorted_vals, q):
    k = (len(sorted_vals) - 1) * q / 100.0
    lo = int(k)
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (k - lo)


def boot_ci(vals, seed, b=5000):
    if len(vals) < 2:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    n = len(vals)
    meds = sorted(pct(sorted(vals[rng.randrange(n)] for _ in range(n)), 50) for _ in range(b))
    return pct(meds, 2.5), pct(meds, 97.5)


def read_trace(path, ct, ci, cm):
    t, i, m = [], [], []
    with open(path, newline="") as fh:
        rd = csv.DictReader(fh)
        for row in rd:
            t.append(float(row[ct]))
            i.append(float(row[ci]))
            m.append(1 if float(row[cm]) > 0.5 else 0)
    if len(t) < 3:
        sys.exit("trace too short")
    if any(t[k + 1] <= t[k] for k in range(len(t) - 1)):
        sys.exit("time_s must be strictly increasing")
    return t, i, m


def windows(t, m):
    out, start = [], None
    for k, v in enumerate(m):
        if v and start is None:
            start = k
        if not v and start is not None:
            out.append((start, k - 1))
            start = None
    if start is not None:
        out.append((start, len(m) - 1))
    return out


def integrate(t, i, a, b):
    """trapezoid integral of i dt from sample a to sample b inclusive"""
    return sum(0.5 * (i[k] + i[k + 1]) * (t[k + 1] - t[k]) for k in range(a, b))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("trace")
    ap.add_argument("--volts", type=float, required=True, help="rail voltage in volts (declare it in the report)")
    ap.add_argument("--ops-per-window", type=int, default=1)
    ap.add_argument("--guard-ms", type=float, default=2.0)
    ap.add_argument("--label", default="unlabelled", help="e.g. ML-DSA-44/verify")
    ap.add_argument("--col-time", default="time_s")
    ap.add_argument("--col-current", default="current_a")
    ap.add_argument("--col-marker", default="marker")
    ap.add_argument("--seed", type=int, default=20261011)
    ap.add_argument("--out-csv", default=None, help="write per-window energies here")
    a = ap.parse_args()

    t, i, m = read_trace(a.trace, a.col_time, a.col_current, a.col_marker)
    wins = windows(t, m)
    if not wins:
        sys.exit("no marker windows found")
    guard = a.guard_ms / 1000.0
    edges = [(t[s], t[e]) for s, e in wins]
    base = []
    for k in range(len(t)):
        if m[k]:
            continue
        if all(t[k] < s - guard or t[k] > e + guard for s, e in edges):
            base.append(i[k])
    if not base:
        sys.exit("no idle samples outside guard bands: lengthen gaps between windows or lower --guard-ms")
    i_base = statistics.median(base)

    gross, net, dur = [], [], []
    for s, e in wins:
        d = t[e] - t[s]
        if d <= 0:
            continue
        eg = a.volts * integrate(t, i, s, e)
        gross.append(eg / a.ops_per_window * 1e6)                        # uJ per op
        net.append((eg - a.volts * i_base * d) / a.ops_per_window * 1e6)  # uJ per op
        dur.append(d / a.ops_per_window * 1e3)                           # ms per op
    def summ(x):
        s = sorted(x)
        lo, hi = boot_ci(s, a.seed)
        return dict(n=len(s), median=pct(s, 50), p25=pct(s, 25), p75=pct(s, 75), min=s[0], max=s[-1], ci_lo=lo, ci_hi=hi)
    print(f"label={a.label} volts={a.volts} ops_per_window={a.ops_per_window} windows={len(gross)} "
          f"idle_current_uA={i_base*1e6:.2f}")
    for name, x, unit in (("gross_energy", gross, "uJ/op"), ("net_energy", net, "uJ/op"), ("time", dur, "ms/op")):
        r = summ(x)
        print(f"{name}: median={r['median']:.3f} {unit}  IQR=[{r['p25']:.3f},{r['p75']:.3f}]  "
              f"min={r['min']:.3f} max={r['max']:.3f}  95%CI(median)=[{r['ci_lo']:.3f},{r['ci_hi']:.3f}]  n={r['n']}")
    if a.out_csv:
        with open(a.out_csv, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["window", "gross_uJ_per_op", "net_uJ_per_op", "ms_per_op"])
            for k, (g, n_, d) in enumerate(zip(gross, net, dur)):
                w.writerow([k, f"{g:.6f}", f"{n_:.6f}", f"{d:.6f}"])


if __name__ == "__main__":
    main()
