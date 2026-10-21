#!/usr/bin/env python3
"""End to end uncertainty: published cycles through energy, link time, protocol time and mission availability.

One chain, one draw of every input per evaluation:
  published cycles (data/shared_inputs.csv: ML-DSA-44 verify S2-0033 and sign S2-0032, ML-KEM-768 encaps S2-0023;
  X25519 rows of mission/model.py) x implementation factor x wait state factor
  -> compute time at the drawn clock (mission/sim.py, bootchain/model.py)
  -> energy per firmware verification (energy/model.py energy_uj times the proxy factor)
  -> link and protocol time (mission/sim.py, which reads the cited link parameters of linksim/params.csv; the
     acknowledgement turnaround and retransmission timeout factor take the ranges of linksim/protocols.py)
  -> mission availability (mission/sim.py run_once).

Every input is drawn uniformly from the range already stated in a parameter file or script of the repository
(column `range_source` of stats/results/e2e_inputs.csv); inputs with a point value and no stated range are kept
fixed and listed in stats/results/e2e_fixed.csv. No range is invented here.

Outputs
  Y1 hybrid session availability, drone, SiK radio (architecture B of the mission study, with design change F1), mean over the runs of one
     evaluation, at the drawn command deadline;
  Y2 added latency per command with an ML-DSA-44 signature on every command (architecture C, drone, SiK), median
     over the commands of the mission minus the unprotected command, without the deadline condition;
  Y3 firmware verification time for a 1 MB image (SHA-256 in software plus one ML-DSA-44 verification);
  Y4 energy of that firmware verification (extra output that carries the energy link of the chain).

Monte Carlo: N_MC independent draws (seed 20261021) give the output intervals. Sobol: Saltelli sample of SALib with
N_SOBOL base points, first and total order indices with SALib's bootstrap intervals (seed 20261021). Each
evaluation runs RUNS missions per architecture with common random numbers (the same seed in every evaluation), so
an output is a deterministic function of the inputs and seed noise does not enter the indices.

Writes stats/results/e2e_inputs.csv, e2e_fixed.csv, e2e_mc.csv, e2e_mc_summary.csv, e2e_sobol.csv, e2e_config.csv.
Label of every output: modelled.
"""
import math
import os
import sys
import time

os.environ.setdefault("OMP_NUM_THREADS", "1")
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from energy import model as em  # noqa: E402
from mission import model as mm  # noqa: E402
from mission import sim  # noqa: E402

SEED = 20261021
RUNS = 20
N_MC = 1000
N_SOBOL = 512
IMAGE_BYTES = 1_000_000
OUT = os.path.join(ROOT, "stats", "results")


def cpb_range():
    v = em.sha256_cpb(em.load_local("retrieved_benchmarks.csv"), "sw")
    return float(min(v)), float(max(v))


def x25519_range():
    c = mm.cycle_table()["x25519_two_mults"]
    return float(c[3]), float(c[4])


def energy_range(name):
    for r in em.read_csv(os.path.join(ROOT, "energy", "workload_assumptions.csv")):
        if r["name"] == name:
            return float(r["low"]), float(r["high"])
    raise KeyError(name)


def inputs():
    """(name, low, high, unit, range_source)."""
    ms = "mission/study.py morris() bounds"
    ls = "linksim/protocols.py SOBOL_INPUTS"
    ew = "energy/workload_assumptions.csv low and high"
    lo_cpb, hi_cpb = cpb_range()
    lo_x, hi_x = x25519_range()
    return [
        ("impl_factor", *energy_range("impl_factor"), "ratio", ew + " (multiplier on published post quantum cycles)"),
        ("x25519_two_mults_cycles", lo_x, hi_x, "cycles",
         "mission/model.py cycle_table range over the published X25519 rows (two scalar multiplications)"),
        ("wait_state_factor", 1.0, 1.5, "ratio", ms),
        ("clock_mhz", 168.0, 250.0, "MHz", "bootchain/run_all.py Monte Carlo bounds"),
        ("mac_cycles", 2000.0, 50000.0, "cycles", ms),
        ("frame_loss", 0.0, 0.2, "ratio", ms),
        ("outage_rate_per_h", 0.0, 30.0, "1/h", ms),
        ("outage_mean_s", 1.0, 30.0, "s", ms),
        ("rekey_interval_s", 60.0, 1800.0, "s", ms),
        ("deadline_s", 0.1, 2.0, "s", ms),
        ("turnaround_s", 0.01, 0.1, "s", ls),
        ("rto_factor", 1.5, 4.0, "ratio", ls),
        ("sha256_cpb", lo_cpb, hi_cpb, "cycles per byte",
         "bootchain/run_all.py cpb_sw_rng (energy/retrieved_benchmarks.csv software SHA-256 rows)"),
        ("ua_per_mhz", *energy_range("ua_per_mhz"), "uA/MHz", ew),
        ("proxy_factor", *energy_range("proxy_factor"), "ratio", ew),
        ("vdd_v", *energy_range("vdd_v"), "V", ew),
    ]


FIXED = [
    ("mldsa44_verify_cycles", "published", "data/shared_inputs.csv mldsa44_verify_cycles_m4 (data/evidence.csv S2-0033, pqm4 m4f); varied only through impl_factor"),
    ("mldsa44_sign_cycles", "published", "data/shared_inputs.csv mldsa44_sign_cycles_m4 (data/evidence.csv S2-0032, pqm4 m4f; vehicle signature of design change F1); varied only through impl_factor"),
    ("mlkem768_encaps_cycles", "published", "data/shared_inputs.csv mlkem768_encaps_cycles_m4 (data/evidence.csv S2-0023, pqm4 m4fspeed); varied only through impl_factor"),
    ("image_bytes", "assumption", "1 MB as the output definition (bootchain/inputs.csv fmuv2_flash_limit_bytes)"),
    ("sik link rate and usable fraction", "cited", "data/shared_inputs.csv sik_air_rate_bps, sik_usable_fraction"),
    ("message, key and signature sizes", "cited", "data/shared_inputs.csv"),
    ("MAVLink payload lengths", "host measured", "mission/payload_lengths.csv"),
    ("traffic rates", "assumption", "mission/traffic.csv (two heartbeat rates published, the other rates assumptions)"),
    ("mission phase durations, session timeout, grace", "assumption", "mission/assumptions.csv (no stated range)"),
    ("max_retries", "assumption", "linksim/params.csv"),
    ("hash cost not scaled by the wait state factor", "assumption",
     "the SHA-256 rows do not state their wait state setting (mission/model.py convention)"),
]


class Chain:
    def __init__(self, runs=RUNS):
        self.runs = runs
        self.cfg = {a: sim.build_config("drone", a, "sik") for a in ("B", "C")}
        sh = mm.shared_inputs.values()  # data/shared_inputs.csv (one value, one source)
        self.mldsa = sh["mldsa44_verify_cycles_m4"]
        self.mldsa_sign = sh["mldsa44_sign_cycles_m4"]
        self.mlkem = sh["mlkem768_encaps_cycles_m4"]
        self.names = [i[0] for i in inputs()]

    def _cfg(self, arch, x):
        c = dict(self.cfg[arch])
        p = dict(c["p"], rto_factor=x["rto_factor"], turnaround_s=x["turnaround_s"])
        link = dict(c["link"], turnaround=x["turnaround_s"])
        clock = x["clock_mhz"] * 1e6
        pq = x["impl_factor"] * x["wait_state_factor"]
        if arch == "B":
            # vehicle side of the B handshake with design change F1 (mission/model.py arch_profile)
            hs = x["x25519_two_mults_cycles"] + (self.mlkem + self.mldsa + self.mldsa_sign) * pq
            cmd = 0.0
        else:
            hs = 0.0
            cmd = self.mldsa * pq
        c.update(p=p, link=link, clock=clock, ws=x["wait_state_factor"], mac=x["mac_cycles"], loss=x["frame_loss"],
                 outage_rate=x["outage_rate_per_h"], outage_mean=x["outage_mean_s"], rekey=x["rekey_interval_s"],
                 deadline=x["deadline_s"] if arch == "B" else 1e9, hs_eff=hs, cmd_eff=cmd)
        return c

    def __call__(self, xv):
        x = dict(zip(self.names, map(float, xv)))
        cb = self._cfg("B", x)
        rng = np.random.default_rng(SEED)
        y1 = float(np.mean([sim.run_once(rng, cb, [])["avail"] for _ in range(self.runs)]))
        cc = self._cfg("C", x)
        rng = np.random.default_rng(SEED + 1)
        lat = [sim.run_once(rng, cc, [])["added_latency_ms"] for _ in range(self.runs)]
        lat = [v for v in lat if not math.isnan(v)]
        y2 = float(np.median(lat)) if lat else float("nan")
        sig = self.mldsa * x["impl_factor"] * x["wait_state_factor"]
        cyc_fw = IMAGE_BYTES * x["sha256_cpb"] + sig
        y3 = 1e3 * cyc_fw / (x["clock_mhz"] * 1e6)
        y4 = em.energy_uj(cyc_fw, x["ua_per_mhz"] * x["proxy_factor"], x["vdd_v"]) / 1e3
        return [y1, y2, y3, y4]


OUTPUTS = [("hybrid_availability_sik_drone", "ratio"), ("added_latency_per_command_signature_ms", "ms"),
           ("firmware_verify_1mb_ms", "ms"), ("firmware_verify_1mb_energy_mj", "mJ")]


def _eval_block(args):
    X, runs = args
    ch = Chain(runs)
    return [ch(x) for x in X]


def evaluate(X, runs, procs):
    if procs <= 1:
        return np.array(_eval_block((X, runs)))
    from multiprocessing import Pool
    blocks = np.array_split(X, procs * 4)
    with Pool(procs) as pool:
        res = pool.map(_eval_block, [(b, runs) for b in blocks])
    return np.array([y for r in res for y in r])


def main(n_mc=N_MC, n_sobol=N_SOBOL, runs=RUNS, procs=2):
    from SALib.analyze import sobol as sob
    from SALib.sample import sobol as sobol_sample
    t0 = time.time()
    os.makedirs(OUT, exist_ok=True)
    inp = inputs()
    pd.DataFrame([dict(label="assumption", input=n, low=lo, high=hi, unit=u, distribution="uniform",
                       range_source=s) for n, lo, hi, u, s in inp]).to_csv(
        os.path.join(OUT, "e2e_inputs.csv"), index=False, float_format="%.6g")
    pd.DataFrame([dict(label=l, item=n, source=s) for n, l, s in FIXED]).to_csv(
        os.path.join(OUT, "e2e_fixed.csv"), index=False)
    names = [i[0] for i in inp]
    bounds = [[i[1], i[2]] for i in inp]
    rng = np.random.default_rng(SEED)
    Xmc = np.column_stack([rng.uniform(lo, hi, n_mc) for lo, hi in bounds])
    Ymc = evaluate(Xmc, runs, procs)
    mc = pd.DataFrame(Xmc, columns=names)
    for j, (o, _) in enumerate(OUTPUTS):
        mc[o] = Ymc[:, j]
    mc.insert(0, "label", "modelled")
    mc.to_csv(os.path.join(OUT, "e2e_mc.csv"), index=False, float_format="%.6g")
    summ = []
    for j, (o, u) in enumerate(OUTPUTS):
        y = Ymc[:, j]
        y = y[~np.isnan(y)]
        summ.append(dict(label="modelled", output=o, unit=u, n=len(y), n_nan=int(n_mc - len(y)),
                         p2_5=float(np.percentile(y, 2.5)), median=float(np.median(y)),
                         p97_5=float(np.percentile(y, 97.5)), mean=float(np.mean(y)), seed=SEED, runs_per_evaluation=runs))
    pd.DataFrame(summ).to_csv(os.path.join(OUT, "e2e_mc_summary.csv"), index=False, float_format="%.6g")
    t1 = time.time()
    problem = {"num_vars": len(names), "names": names, "bounds": bounds}
    Xs = sobol_sample.sample(problem, n_sobol, calc_second_order=False, seed=SEED)
    Ys = evaluate(Xs, runs, procs)
    rows = []
    for j, (o, _) in enumerate(OUTPUTS):
        y = Ys[:, j]
        nan = int(np.isnan(y).sum())
        if nan:
            y = np.where(np.isnan(y), np.nanmax(y), y)
        S = sob.analyze(problem, y, calc_second_order=False, seed=SEED, print_to_console=False)
        order = np.argsort(-S["ST"])
        for rank, k in enumerate(order, 1):
            rows.append(dict(label="modelled", output=o, input=names[k], rank_by_ST=rank, S1=float(S["S1"][k]),
                             S1_conf=float(S["S1_conf"][k]), ST=float(S["ST"][k]), ST_conf=float(S["ST_conf"][k]),
                             ST_lo=float(S["ST"][k] - S["ST_conf"][k]), ST_hi=float(S["ST"][k] + S["ST_conf"][k]),
                             N=n_sobol, samples=len(y), nan_set_to_max=nan, runs_per_evaluation=runs, seed=SEED))
    pd.DataFrame(rows).to_csv(os.path.join(OUT, "e2e_sobol.csv"), index=False, float_format="%.6g")
    cfg = [("seed", SEED), ("runs_per_evaluation", runs), ("n_mc", n_mc), ("n_sobol_base", n_sobol),
           ("sobol_evaluations", len(Xs)), ("processes", procs), ("mc_seconds", f"{t1 - t0:.0f}"),
           ("sobol_seconds", f"{time.time() - t1:.0f}"),
           ("y2_deadline", "added latency computed without the deadline condition (deadline set to 1e9 s)"),
           ("common_random_numbers", "seed 20261021 for architecture B and 20261022 for C in every evaluation")]
    pd.DataFrame([dict(label="assumption", key=k, value=v) for k, v in cfg]).to_csv(
        os.path.join(OUT, "e2e_config.csv"), index=False)
    print(pd.DataFrame(summ).to_string())
    print(pd.DataFrame(rows)[["output", "input", "rank_by_ST", "ST", "ST_conf"]].groupby("output").head(4).to_string())
    print(f"{time.time() - t0:.0f} s")


if __name__ == "__main__":
    a = sys.argv[1:]
    main(*(int(v) for v in a)) if a else main()
