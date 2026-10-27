"""Replay acceptance rules of the vehicle in the mission model, and their paired runs (label: estimated).

Three rules decide whether the vehicle accepts an authenticated command that arrives with a valid tag:

- published: the counter (MAVLink 2 timestamp) is greater than the last accepted one; gaps are allowed. This is
  the rule of every earlier mission study result, which regenerate identically with it.
- strict: only the next counter is accepted (the rule of the proofs C1 and C2 in docs/FORMAL_VERIFICATION.md).
  A frame that the link layer retransmits is waited for (the mission model link layer delivers in order, so the
  stall behind a retransmission is already part of the latency). A command that the link layer gives up leaves
  a gap: every later command is rejected until a resynchronisation, modelled explicitly as a new handshake of
  the architecture (the same four flights and vehicle compute as a rekey of the mission model, which resets both
  counters). The ground station starts it when its link layer reports the give up; the handshake pauses during
  outages (sim.transfer_through_outages). When a teardown handshake of the session timeline ends earlier, that
  handshake ends the stall instead. Commands issued from the gap until the new key is in use are not available.
- cache: any counter not yet seen inside a window of W counters below the highest accepted one is accepted
  (a replay cache); W is an assumption (mission/replay_assumptions.csv) and is swept.

Give up: the link layer of the mission model makes at most max_retries + 1 attempts per frame
(linksim/params.csv), one every (frame air time + retransmission timeout) from the start of the command. A
command is given up when fewer attempt instants fall outside outages than the attempts its frame loss draws
need. All three rules are evaluated on the same draws of each run; the strict rule draws its resynchronisation
handshakes from a separate generator, so the published rule results stay as they were.
"""
import csv
import json
import math
import os
from multiprocessing import Pool

import numpy as np

from . import model, sim

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, 'results')
RULES = ['published', 'strict', 'cache']
RULE_NAMES = {'published': 'published (counter greater than the last accepted, gaps allowed)',
              'strict': 'strict (next counter only; resynchronisation by a new handshake after a give up)',
              'cache': 'replay cache (unseen counter inside a window of W counters)'}
DEADLINES = [0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0]
LOSS_SWEEP = [0.0, 0.01, 0.05, 0.1, 0.2]


def load_replay_assumptions(path=os.path.join(HERE, 'replay_assumptions.csv')):
    """Return {name: value}; the window sweep is a list of integers."""
    out = {}
    with open(path, newline='', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            v = r['value']
            out[r['name']] = [int(x) for x in v.split()] if ' ' in v else float(v)
    return out


def rule_key(rule, window=None):
    """Column key of a rule: published, strict, or cache_W<window>."""
    if rule == 'cache':
        if window is None:
            window = int(load_replay_assumptions()['replay_window_counters'])
        return f'cache_W{int(window)}'
    if rule in ('published', 'strict'):
        return rule
    raise ValueError(rule)


def accept_in_arrival_order(counters, rule, window=1):
    """Generic acceptance of counters in arrival order without resynchronisation (published and cache rules).

    Returns a boolean array aligned with the input order. published: counter greater than the highest accepted.
    cache: counter above the highest accepted, or not yet seen and greater than highest minus window.
    """
    acc = np.zeros(len(counters), bool)
    hi = -math.inf
    seen = set()
    for i, c in enumerate(counters):
        if rule == 'published':
            ok = c > hi
        elif rule == 'cache':
            ok = c not in seen and c > hi - window
        else:
            raise ValueError(rule)
        if ok:
            acc[i] = True
            seen.add(c)
            hi = max(hi, c)
    return acc


def given_up(start, att, attempt_period, max_retries, o_s, o_e):
    """Boolean array: the link layer gives the command up (module docstring), and the give up time."""
    n = len(start)
    k = np.arange(int(max_retries) + 1)
    inst = start[:, None] + k[None, :] * attempt_period  # attempt instants
    if len(o_s):
        idx = np.searchsorted(o_s, inst, side='right') - 1
        down = (idx >= 0) & (o_e[np.clip(idx, 0, None)] > inst)
    else:
        down = np.zeros(inst.shape, bool)
    free = (~down).sum(axis=1)
    need = att.max(axis=1) if att.ndim == 2 else att
    gu = free < need
    t_gu = inst[:, -1] + attempt_period if n else np.zeros(0)
    return gu, t_gu


def strict_rejections(t, sent, gu, t_gu, o_s, o_e, inv_s, inv_e, draw_handshake):
    """Strict rule with resynchronisation: returns (rejected mask, number of resynchronisations, stall seconds).

    Commands are processed in issue order (in order delivery). A given up command starts a stall that ends when
    the resynchronisation handshake (draw_handshake() seconds, paused in outages) or an earlier teardown
    handshake of the session timeline completes.
    """
    rej = np.zeros(len(t), bool)
    stall_end = -math.inf
    n_rs = 0
    stall_s = 0.0
    for k in np.flatnonzero(sent):
        if t[k] < stall_end:
            rej[k] = True
            continue
        if gu[k]:
            end = sim.transfer_through_outages(float(t_gu[k]), draw_handshake(), o_s, o_e)
            for s, e in zip(inv_s, inv_e):
                if t[k] <= s < end:
                    end = min(end, e)
                    break
            n_rs += 1
            stall_s += end - t[k]
            stall_end = end
    return rej, n_rs, stall_s


def rule_outcomes(cfg, x, deadlines):
    """Per run availability under every rule (keys avail_rule_<rule>[_<deadline>]) and rule counters."""
    a = load_replay_assumptions()
    windows = sorted(set(a['replay_window_sweep'] + [int(a['replay_window_counters'])]))
    if cfg.get('replay_window') is not None:
        windows = sorted(set(windows + [int(cfg['replay_window'])]))
    if not cfg['ap']['session']:
        raise ValueError('replay rules are modelled for the session architectures A and B')
    t, start, att = x['t'], x['start'], x['att']
    n = len(t)
    frames = np.asarray(cfg['cmd_auth'], float)
    rto = cfg['p']['rto_factor'] * (cfg['link']['turnaround'] + cfg['ack_air'])
    period = frames.sum() / cfg['link']['duty'] + rto
    gu, t_gu = given_up(start, att, period, cfg['p']['max_retries'], x['o_s'], x['o_e'])
    sent = x['valid']  # commands issued with a valid session key carry a counter
    arrival = start + x['air'] + x['extra'] + x['comp']
    order = np.argsort(np.where(gu, np.inf, arrival), kind='stable')
    arrived = sent & ~gu
    idx_arr = [i for i in order if arrived[i]]
    cnt = np.cumsum(sent) - 1  # counter of each sent command, in issue order
    acc = {}
    acc['published'] = np.zeros(n, bool)
    acc['published'][idx_arr] = accept_in_arrival_order(cnt[idx_arr], 'published')
    for w in windows:
        m = np.zeros(n, bool)
        m[idx_arr] = accept_in_arrival_order(cnt[idx_arr], 'cache', w)
        acc[f'cache_W{w}'] = m
    rng = cfg['rng_replay']
    rej, n_rs, stall_s = strict_rejections(t, sent, gu, t_gu, x['o_s'], x['o_e'], x['inv_s'], x['inv_e'],
                                           lambda: sim.sample_handshake(rng, cfg)[0])
    acc['strict'] = arrived & ~rej
    out = {'n_sent': int(sent.sum()), 'n_given_up': int((sent & gu).sum()), 'n_resync_strict': n_rs,
           'stall_s_strict': stall_s}
    for key, m in acc.items():
        out[f'n_rejected_{key}'] = int((arrived & ~m).sum())
        for d in deadlines:
            ok = x['valid'] & x['link_ok'] & (x['lat'] <= d) & m
            out[f'avail_rule_{key}_{d:g}'] = ok.mean() if n else float('nan')
        ok = x['ok'] & m
        out[f'avail_rule_{key}'] = ok.mean() if n else float('nan')
    return out


# ---------------------------------------------------------------- paired runs

def paired_ci(diff, key, B=2000):
    """Mean of paired differences with a bootstrap 95 percent percentile interval over runs."""
    return sim_boot(diff, key, B)


def sim_boot(x, key, B=2000):
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    if len(x) == 0:
        return (float('nan'),) * 3
    rng = sim.rng_for(key)
    idx = rng.integers(0, len(x), size=(B, len(x)))
    bs = x[idx].mean(axis=1)
    return float(x.mean()), float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))


def _job(args):
    """One configuration under the replay rule report; the key equals the key of the earlier study rows."""
    import pandas as pd
    vehicle, arch, link, runs, over, tag = args
    key = tag + '|' + json.dumps(over, sort_keys=True, default=str)
    res, cfg = sim.run_config(vehicle, arch, link, runs, DEADLINES, key_extra=key, replay_rule='published', **over)
    df = pd.DataFrame(res)
    ra = load_replay_assumptions()
    base_w = int(ra['replay_window_counters'])
    keys = ['published', 'strict'] + [f'cache_W{w}' for w in sorted(set(ra['replay_window_sweep'] + [base_w]))]
    rows = []
    for k in keys:
        rule = 'cache' if k.startswith('cache') else k
        w = int(k.split('W')[1]) if rule == 'cache' else float('nan')
        m, lo, hi = sim_boot(df[f'avail_rule_{k}'].values, 'replaymean|' + key + '|' + k)
        d, dlo, dhi = paired_ci(df[f'avail_rule_{k}'].values - df['avail_rule_published'].values,
                                'replaydiff|' + key + '|' + k)
        r = dict(vehicle=vehicle, arch=arch, link=link, tag=tag, config_key=key, runs=runs, seed=sim.SEED,
                 replay_rule=rule, replay_window=w, base_window=int(w == base_w) if rule == 'cache' else 1,
                 deadline_s=cfg['deadline'], avail_mean=m, avail_mean_lo=lo, avail_mean_hi=hi,
                 avail_median=float(df[f'avail_rule_{k}'].median()),
                 diff_vs_published_mean=d, diff_vs_published_lo=dlo, diff_vs_published_hi=dhi,
                 share_runs_lower_than_published=float((df[f'avail_rule_{k}'] < df['avail_rule_published']).mean()),
                 rejected_per_run_mean=float(df[f'n_rejected_{k}'].mean()),
                 given_up_per_run_mean=float(df['n_given_up'].mean()),
                 resync_per_run_mean=float(df['n_resync_strict'].mean()) if rule == 'strict' else 0.0,
                 stall_s_per_run_mean=float(df['stall_s_strict'].mean()) if rule == 'strict' else 0.0,
                 commands_per_run_mean=float(df['n_sent'].mean()), label='estimated')
        for over_k, v in over.items():
            r[f'over_{over_k}'] = v
        for dl in DEADLINES:
            r[f'avail_mean_{dl:g}'] = float(df[f'avail_rule_{k}_{dl:g}'].mean())
        rows.append(r)
    return rows


def base_jobs(runs):
    return [('drone', a, l, runs, {}, 'base') for l in model.LINKS for a in ['A', 'B']]


def loss_jobs(runs):
    return [('drone', 'B', 'sik', runs, {'frame_loss': v}, 'sweep:frame_loss') for v in LOSS_SWEEP]


def outage_jobs(runs):
    """Outage rate sweep (the points of the study sweep), drone, A and B, SiK and IEEE 802.15.4; used by the
    comparison with the software in the loop runs, whose scripted outages match the 60 per hour point."""
    from . import study
    return [('drone', a, l, runs, {'outage_rate_per_h': v}, 'sweep:outage_rate_per_h')
            for v in study.SWEEPS['outage_rate_per_h'] for l in ['sik', 'ieee802154'] for a in ['A', 'B']]


def run(jobs, procs=2):
    import pandas as pd
    with Pool(procs) as pool:
        parts = pool.map(_job, jobs)
    return pd.DataFrame([r for p in parts for r in p])


def regeneration_check(rep, earlier):
    """Published rule rows against the earlier study rows with the same key (mean availability, exact)."""
    import pandas as pd
    rows = []
    pub = rep[rep.replay_rule == 'published']
    for _, r in pub.iterrows():
        e = earlier[(earlier.vehicle == r.vehicle) & (earlier.arch == r.arch) & (earlier.link == r.link)
                    & (earlier.config_key == r.config_key)]
        val = float(e.avail_mean.iloc[0]) if len(e) == 1 else float('nan')
        rows.append(dict(vehicle=r.vehicle, arch=r.arch, link=r.link, config_key=r.config_key,
                         replay_avail_mean=r.avail_mean, earlier_avail_mean=val,
                         identical=bool(len(e) == 1 and abs(val - r.avail_mean) <= 1e-12), label='estimated'))
    return pd.DataFrame(rows)


def main(runs=None):
    import pandas as pd
    a = model.load_assumptions()
    runs = int(runs or a['runs'])
    base = run(base_jobs(runs))
    base.to_csv(os.path.join(RES, 'replay_base.csv'), index=False)
    loss = run(loss_jobs(runs))
    loss.to_csv(os.path.join(RES, 'replay_loss_sweep.csv'), index=False)
    outage = run(outage_jobs(runs))
    outage.to_csv(os.path.join(RES, 'replay_outage_sweep.csv'), index=False)
    sweeps = pd.read_csv(os.path.join(RES, 'sweeps.csv'))
    chk = pd.concat([regeneration_check(base, pd.read_csv(os.path.join(RES, 'base.csv'))),
                     regeneration_check(loss, sweeps), regeneration_check(outage, sweeps)])
    chk.to_csv(os.path.join(RES, 'replay_regeneration_check.csv'), index=False)
    return base, loss, chk


if __name__ == '__main__':
    main()
