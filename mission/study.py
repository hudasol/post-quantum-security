"""Mission study driver: base runs, sweeps, low rate profile, envelope, Morris screening (label: estimated).

Seed 20261020 for every random step; each configuration has its own generator derived from the seed
and a CRC32 of its key (see sim.rng_for). Results go to mission/results/.
"""
import json
import math
import os
from multiprocessing import Pool

import numpy as np
import pandas as pd

from . import model, sim

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, 'results')
DEADLINES = [0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0]
METRICS = ['avail', 'added_latency_ms', 'latency_ms', 'utilisation', 'utilisation_down', 'compute_share', 'ttra_s',
           'first_session_s']

SWEEPS = {
    'frame_loss': [0.0, 0.01, 0.05, 0.1, 0.2],
    'rekey_interval_s': [60.0, 900.0, math.inf],
    'outage_rate_per_h': [0.0, 2.0, 20.0, 60.0],
    'outage_mean_s': [2.0, 30.0],
    'clock_hz': [480e6],
    'wait_state_factor': [1.5],
    'mac_cycles': [2000.0, 50000.0],
}
SWEEP_LINKS = ['sik', 'ieee802154', 'lora_dr5']
LOWRATE = dict(cmd_rate=1 / 60.0, tel_scale=0.0)


def boot_ci(x, stat=np.median, B=2000, key='boot'):
    """Bootstrap 95 percent percentile interval of stat(x); NaNs dropped. Returns (point, lo, hi)."""
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    if len(x) == 0:
        return (float('nan'),) * 3
    rng = sim.rng_for(key)
    idx = rng.integers(0, len(x), size=(B, len(x)))
    if stat is np.median:
        bs = np.median(x[idx], axis=1)
    elif stat is np.mean:
        bs = x[idx].mean(axis=1)
    else:
        bs = np.apply_along_axis(stat, 1, x[idx])
    return float(stat(x)), float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))


def _job(args):
    vehicle, arch, link, runs, over, tag = args
    key = tag + '|' + json.dumps(over, sort_keys=True, default=str)
    res, cfg = sim.run_config(vehicle, arch, link, runs, DEADLINES, key_extra=key, **over)
    df = pd.DataFrame(res)
    dl = cfg['deadline']
    out = dict(vehicle=vehicle, arch=arch, link=link, tag=tag, runs=runs, seed=sim.SEED, config_key=key,
               deadline_s=dl, label='estimated')
    out.update({f'over_{k}': v for k, v in over.items()})
    for m in METRICS:
        if m not in df:
            continue
        pt, lo, hi = boot_ci(df[m].values, key='boot|' + key + '|' + m)
        out[f'{m}_median'] = pt
        out[f'{m}_lo'] = lo
        out[f'{m}_hi'] = hi
    out['avail_mean'], out['avail_mean_lo'], out['avail_mean_hi'] = boot_ci(df['avail'].values, stat=np.mean,
                                                                            key='bootmean|' + key)
    for d in DEADLINES:
        out[f'avail_med_{d:g}'] = float(df[f'avail_{d:g}'].median())
        out[f'avail_mean_{d:g}'] = float(df[f'avail_{d:g}'].mean())
        out[f'avail_base_mean_{d:g}'] = float(df[f'avail_base_{d:g}'].mean())
    out['teardowns_per_run_mean'] = float(df['n_teardowns'].mean())
    out['handshakes_per_run_mean'] = float(df['n_handshakes'].mean())
    out['share_runs_with_teardown'] = float((df['n_teardowns'] > 0).mean())
    return out


def run_jobs(jobs, procs=2):
    with Pool(procs) as pool:
        return pd.DataFrame(pool.map(_job, jobs))


def base_jobs(runs):
    return [(v, a, l, runs, {}, 'base') for v in ['drone', 'robot'] for l in model.LINKS for a in model.ARCHS]


def sweep_jobs(runs):
    jobs = []
    for par, vals in SWEEPS.items():
        for val in vals:
            for l in SWEEP_LINKS:
                for a in model.ARCHS:
                    if par in ('rekey_interval_s',) and a in ('C', 'D'):
                        continue
                    jobs.append(('drone', a, l, runs, {par: val}, 'sweep:' + par))
    return jobs


def lowrate_jobs(runs):
    return [(v, a, l, runs, dict(LOWRATE), 'lowrate') for v in ['drone'] for l in model.LINKS for a in model.ARCHS]


def envelope(base, threshold):
    """Feasible when mean availability at the deadline is at least threshold and median utilisation at most 1."""
    rows = []
    for _, r in base.iterrows():
        for d in DEADLINES:
            av = r[f'avail_mean_{d:g}']
            util = r['utilisation_median']
            util_d = r.get('utilisation_down_median', float('nan'))
            over = util > 1 or (not np.isnan(util_d) and util_d > 1)
            if av >= threshold and not over:
                why = 'feasible'
            elif over:
                why = 'link overloaded'
            elif r['arch'] in ('A', 'B') and r['first_session_s_median'] > 60:
                why = 'session not established in preflight'
            else:
                why = 'deadline missed or link loss'
            rows.append(dict(vehicle=r['vehicle'], link=r['link'], arch=r['arch'], tag=r['tag'], deadline_s=d,
                             avail_mean=av, utilisation_median=util, feasible=why == 'feasible', reason=why,
                             label='estimated'))
    return pd.DataFrame(rows)


def compute_latency_table():
    """Vehicle side compute time per operation at the reference clocks (label: derived from published)."""
    a = model.load_assumptions()
    cyc = model.cycle_table()
    rows = []
    for arch in model.ARCHS:
        ap = model.arch_profile(arch)
        for what, c in [('handshake or rekey', ap['hs_cycles']), ('per command check', ap['cmd_cycles']),
                        ('boot verify', ap['boot_cycles'])]:
            if c == 0:
                continue
            rows.append(dict(arch=arch, operation=what, cycles=c,
                             ms_at_168MHz=c * a['wait_state_factor'] / a['clock_hz'] * 1e3,
                             ms_at_480MHz=c / a['clock_alt_hz'] * 1e3, label='derived from published'))
    src = pd.DataFrame([dict(operation=k, cycles=v[0], label=v[1], source=v[2]) for k, v in cyc.items()])
    return pd.DataFrame(rows), src


def link_crosscheck():
    """No loss handshake time of the mission transfer model against linksim's published table (model to model)."""
    linksim_sr = {'sik': 0.8986, 'ieee802154': 0.5008}  # docs/LINK_REFERENCE_DESIGN.md section 7.2, provisioned key
    rows = []
    for l, ref in linksim_sr.items():
        cfg = sim.build_config('drone', 'B', l, frame_loss=0.0, clock_hz=1e30)
        rng = sim.rng_for('crosscheck|' + l)
        t, air = sim.sample_handshake(rng, cfg)
        rows.append(dict(link=l, mission_model_s=t, linksim_selective_repeat_s=ref,
                         relative_difference=(t - ref) / ref, air_s=air['up'] + air['down'], label='estimated',
                         note='model to model comparison of two estimates, not a validation against measurement'))
    return pd.DataFrame(rows)


def morris(runs=200, r=10, seed=sim.SEED):
    """Morris elementary effects on mean availability (drone, SiK) for architectures A, B and C."""
    from SALib.sample import morris as ms
    from SALib.analyze import morris as ma
    problem = dict(num_vars=7, names=['frame_loss', 'outage_rate_per_h', 'outage_mean_s', 'rekey_interval_s',
                                      'mac_cycles', 'wait_state_factor', 'deadline_s'],
                   bounds=[[0, 0.2], [0, 30], [1, 30], [60, 1800], [2000, 50000], [1, 1.5], [0.1, 2.0]])
    X = ms.sample(problem, N=r, num_levels=4, seed=seed)
    out = []
    for arch in ['A', 'B', 'C']:
        jobs = [('drone', arch, 'sik', runs, dict(zip(problem['names'], map(float, x))), 'morris') for x in X]
        df = run_jobs(jobs)
        Y = df['avail_mean'].values
        S = ma.analyze(problem, X, Y, num_levels=4, seed=seed)
        for i, n in enumerate(problem['names']):
            out.append(dict(arch=arch, input=n, mu_star=S['mu_star'][i], sigma=S['sigma'][i],
                            mu_star_conf=S['mu_star_conf'][i], runs_per_point=runs, trajectories=r, seed=seed,
                            label='estimated'))
    return pd.DataFrame(out), X


def _stage(name, jobs, resume):
    path = os.path.join(RES, name)
    if resume and os.path.exists(path):
        return pd.read_csv(path)
    df = run_jobs(jobs)
    df.to_csv(path, index=False)
    return df


def main(runs=1000, morris_runs=200, resume=False):
    """Run every stage; with resume=True, stages whose result file exists are read instead of rerun."""
    os.makedirs(RES, exist_ok=True)
    a = model.load_assumptions()
    base = _stage('base.csv', base_jobs(runs), resume)
    sweeps = _stage('sweeps.csv', sweep_jobs(runs), resume)
    low = _stage('lowrate.csv', lowrate_jobs(runs), resume)
    env = pd.concat([envelope(base, a['feasible_availability']), envelope(low, a['feasible_availability'])])
    env.to_csv(os.path.join(RES, 'envelope.csv'), index=False)
    comp, src = compute_latency_table()
    comp.to_csv(os.path.join(RES, 'compute_latency.csv'), index=False)
    src.to_csv(os.path.join(RES, 'cycle_sources.csv'), index=False)
    link_crosscheck().to_csv(os.path.join(RES, 'link_crosscheck.csv'), index=False)
    mo, _ = morris(morris_runs)
    mo.to_csv(os.path.join(RES, 'morris.csv'), index=False)
    with open(os.path.join(RES, 'config.json'), 'w') as f:
        json.dump(dict(seed=sim.SEED, runs=runs, morris_runs_per_point=morris_runs, deadlines=DEADLINES,
                       sweeps={k: [str(x) for x in v] for k, v in SWEEPS.items()}, sweep_links=SWEEP_LINKS,
                       lowrate=LOWRATE, assumptions=a), f, indent=1)
    return base, sweeps, low, env


if __name__ == '__main__':
    import sys
    main(resume='--resume' in sys.argv[1:])
