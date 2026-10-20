"""Monte Carlo and Sobol analysis of the mission security workload. Author: Huda Mueen.

Inputs are the ranges in energy/workload_assumptions.csv (all labelled assumption).
Monte Carlo draws from triangular(low, nominal, high); Sobol indices use uniform
(low, high) bounds through SALib. Seed 20261020. Output label: modelled (estimated
inputs, no validation data exists for these mission shares).
"""
import numpy as np
from SALib.analyze import sobol as sobol_analyze
from SALib.sample import sobol as sobol_sample

from energy import model

INPUTS = ["handshakes_per_h", "rekeys_per_h", "commands_per_s", "boots_per_h", "image_mb",
          "ua_per_mhz", "proxy_factor", "vdd_v", "impl_factor", "crazyflie_cell_v", "command_msg_bytes"]


def evaluate(samples, names, cyc, platform, design):
    """Vectorised battery share (percent per hour) and CPU share (percent) for sample rows.

    samples: array (n, len(names)). cyc: dict op -> nominal cycles (msg of 64 B for HMAC).
    platform: platforms.csv row. design: see model.workload_cycles_per_h.
    """
    s = {n: samples[:, i] for i, n in enumerate(names)}
    c = dict(cyc)
    # HMAC cycles scale with the bytes processed for the sampled message length.
    base_bytes = model.hmac_sha256_bytes(64)
    msg = s["command_msg_bytes"]
    hmac_bytes = 64 * (np.ceil((64 + msg + 9) / 64) + 2)
    c["hmac_sha256_msg"] = cyc["hmac_sha256_msg"] * hmac_bytes / base_bytes
    cyc_h = model.workload_cycles_per_h(c, s, design) * s["impl_factor"]
    clock = float(platform["clock_mhz"])
    cpu_pct = 100.0 * cyc_h / 3600.0 / (clock * 1e6)
    energy_j_h = model.energy_uj(cyc_h, s["ua_per_mhz"] * s["proxy_factor"], s["vdd_v"]) * 1e-6
    if platform["battery_wh"]:
        bwh = float(platform["battery_wh"]) * np.ones_like(cyc_h)
    else:
        bwh = model.battery_wh(float(platform["battery_mah"]), s["crazyflie_cell_v"])
    power_w = bwh / float(platform["run_time_h"])
    batt_pct = 100.0 * energy_j_h / (power_w * 3600.0)
    return batt_pct, cpu_pct


def triangular_samples(assume, n, seed=model.SEED):
    rng = np.random.default_rng(seed)
    cols = []
    for name in INPUTS:
        a = assume[name]
        if a["low"] == a["high"]:
            cols.append(np.full(n, a["nominal"]))
        else:
            cols.append(rng.triangular(a["low"], a["nominal"], a["high"], size=n))
    return np.column_stack(cols)


def nominal_row(assume):
    return np.array([[assume[n]["nominal"] for n in INPUTS]])


def sobol_indices(assume, cyc, platform, design, n_base=1024, seed=model.SEED, which=0):
    """First order and total Sobol indices for battery share (which=0) or CPU share (which=1)."""
    problem = {"num_vars": len(INPUTS), "names": INPUTS,
               "bounds": [[assume[n]["low"], assume[n]["high"]] for n in INPUTS]}
    X = sobol_sample.sample(problem, n_base, calc_second_order=False, seed=seed)
    Y = evaluate(X, INPUTS, cyc, platform, design)[which]
    res = sobol_analyze.analyze(problem, Y, calc_second_order=False, seed=seed)
    return [{"input": n, "S1": float(res["S1"][i]), "S1_conf": float(res["S1_conf"][i]),
             "ST": float(res["ST"][i]), "ST_conf": float(res["ST_conf"][i])} for i, n in enumerate(INPUTS)]
