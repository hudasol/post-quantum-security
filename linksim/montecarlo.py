"""Monte Carlo trials and one at a time parameter sweeps for the link simulator.

Author: Huda Mueen.

Each cell runs the seeded event simulation of sim.py many times with seeds
BASE_SEED, BASE_SEED + 1, ... and reports the mean with a 95 percent
interval, the median, the 5th and 95th percentiles and the completion rate
with a Wilson interval. Only sizes and times are simulated; no
cryptographic operation is performed. All results are estimated from
published sizes, not measured.
"""
import copy
import math

from . import model, sim

BASE_SEED = 20261016
TRIALS = 1000
Z95 = 1.959963984540054


def seed_list(trials=TRIALS, base=BASE_SEED):
    """Seeds used for a cell: base, base + 1, ..., base + trials - 1."""
    return [base + i for i in range(trials)]


def percentile(sorted_vals, q):
    """Linear interpolation percentile, q in [0, 1], of a sorted list."""
    if not sorted_vals:
        return float("nan")
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    pos = q * (len(sorted_vals) - 1)
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = pos - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


def summarise(values):
    """n, mean, sample standard deviation, 95 percent interval of the mean
    (normal approximation), median, p05 and p95."""
    n = len(values)
    if n == 0:
        nan = float("nan")
        return {"n": 0, "mean": nan, "sd": nan, "ci_lo": nan, "ci_hi": nan,
                "median": nan, "p05": nan, "p95": nan}
    mean = sum(values) / n
    sd = math.sqrt(sum((v - mean) ** 2 for v in values) / (n - 1)) if n > 1 else 0.0
    half = Z95 * sd / math.sqrt(n)
    s = sorted(values)
    return {"n": n, "mean": mean, "sd": sd, "ci_lo": mean - half,
            "ci_hi": mean + half, "median": percentile(s, 0.5),
            "p05": percentile(s, 0.05), "p95": percentile(s, 0.95)}


def wilson(k, n, z=Z95):
    """Wilson score interval for k successes in n trials."""
    if n == 0:
        return (float("nan"), float("nan"))
    ph = k / n
    den = 1 + z * z / n
    centre = (ph + z * z / (2 * n)) / den
    half = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / den
    return (max(0.0, centre - half), min(1.0, centre + half))


def link_variant(link, cap=None, rate_scale=1.0, overhead=None):
    """Copy of a Link with a different fragment payload, rate or overhead."""
    L = copy.copy(link)
    if cap is not None:
        if int(cap) < 1:
            raise ValueError("fragment payload must be at least 1 byte")
        L.cap = int(cap)
    if overhead is not None:
        L.overhead = int(overhead)
    L.rate_bps = link.rate_bps * float(rate_scale)
    return L


def mc_cell(link, flights, proto, loss, p, trials=TRIALS, base_seed=BASE_SEED):
    """Run one cell. Statistics of wall time cover completed runs only; the
    completion rate is reported separately. At zero loss the simulation is
    deterministic, so one run stands for all trials (stated in the output).
    """
    walls = []
    done = 0
    if loss == 0.0:
        st = sim._run_flights(link, flights, proto, loss, base_seed, p)
        walls = [st.wall_s] * trials if st.completed else []
        done = trials if st.completed else 0
        deterministic = True
    else:
        for s in seed_list(trials, base_seed):
            st = sim._run_flights(link, flights, proto, loss, s, p)
            if st.completed:
                done += 1
                walls.append(st.wall_s)
        deterministic = False
    res = summarise(walls)
    lo, hi = wilson(done, trials)
    res.update({"trials": trials, "completed": done,
                "completion": done / trials, "completion_lo": lo,
                "completion_hi": hi, "base_seed": base_seed,
                "deterministic": deterministic})
    return res


SWEEP_AXES = ("payload", "rate_scale", "loss", "max_retries", "rto_factor")


def sweep(link_key, axis, values, p=None, proto="sr", loss=0.05,
          variant="hybrid", trials=TRIALS, base_seed=BASE_SEED):
    """One at a time sweep of a single axis for one link. Returns a list of
    (value, result) pairs. Axes: payload (fragment data bytes), rate_scale
    (multiplier on the link rate), loss, max_retries, rto_factor."""
    if axis not in SWEEP_AXES:
        raise ValueError(axis)
    p = dict(p or model.load_params())
    base_link = model.build_links(p)[link_key]
    out = []
    for v in values:
        q = dict(p)
        L = base_link
        cell_loss = loss
        if axis == "payload":
            L = link_variant(base_link, cap=v)
        elif axis == "rate_scale":
            L = link_variant(base_link, rate_scale=v)
        elif axis == "loss":
            cell_loss = float(v)
        else:
            q[axis] = float(v)
        flights = model.handshake_flights(q, variant)
        out.append((v, mc_cell(L, flights, proto, cell_loss, q, trials,
                               base_seed)))
    return out


def relative_change(results, base_value):
    """Mean wall time of each sweep point divided by the mean at base_value,
    minus one. results is the output of sweep()."""
    base = dict(results)[base_value]["mean"]
    return [(v, r["mean"] / base - 1.0) for v, r in results]
