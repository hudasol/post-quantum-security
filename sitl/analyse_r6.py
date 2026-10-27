"""Summarise the round 6 software in the loop runs (executed cryptography) and compare them with the mission model.

Reads sitl/raw_r6/, writes sitl/results_r6/: commands.csv, missions.csv, summary.csv, paired.csv, rejections.csv,
reorder.csv, delays.csv, host_compute.csv, comparison.csv, environment.json and SVG figures.
Labels: round trips through the flight stack and mission completion are SITL measured; handshake time, one way
delivery and channel figures are emulated (the emulated link with executed cryptography, vehicle side delays
estimated from RTL simulated cycles); the delays themselves are estimated (from RTL simulated cycles); ground
side compute times are host measured; mission model values are estimated.
Intervals: 95 percent cluster bootstrap over missions (2000 resamples); differences between configurations are
paired by mission index (the same seed in every configuration). Bootstrap seeds: 20311021 + 5000 + offsets.
"""
import glob
import json
import os
import sys

import numpy as np
import pandas as pd

from mission import model, sim
from . import analyse as a5
from . import config_r6 as c6

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RAW = os.path.join(HERE, 'raw_r6')
RES = os.path.join(HERE, 'results_r6')
BOOT = 2000
PAIRS = [('hybrid_strict', 'hybrid_published'), ('hybrid_cache', 'hybrid_published'),
         ('hybrid_strict', 'hybrid_cache'), ('hybrid_published', 'classical'), ('classical', 'signing'),
         ('hybrid_published', 'none'), ('pqsig_real', 'hybrid_published')]


def load_raw(raw=RAW):
    cmds, mis, runs, arr = [], [], [], []
    for f in sorted(glob.glob(os.path.join(raw, '*_missions.csv'))):
        tag = os.path.basename(f)[:-len('_missions.csv')]
        mis.append(pd.read_csv(f))
        cmds.append(pd.read_csv(os.path.join(raw, f'{tag}_commands.csv')))
        with open(os.path.join(raw, f'{tag}_run.json')) as fh:
            info = json.load(fh)
        info['_tag'] = tag
        runs.append(info)
        ap = os.path.join(raw, f'{tag}_arrivals.csv')
        if os.path.exists(ap):
            x = pd.read_csv(ap)
            x['profile'], x['config'] = info['profile'], info['config']
            arr.append(x)
    if not mis:
        return None, None, [], None
    return (pd.concat(cmds, ignore_index=True), pd.concat(mis, ignore_index=True), runs,
            pd.concat(arr, ignore_index=True) if arr else pd.DataFrame())


def reason_of(d):
    """Category of a command that was not acknowledged within the deadline."""
    if not isinstance(d, str) or d == '':
        return ''
    return d


def prepare(cmds, mis, deadline):
    c, m = a5.prepare(cmds, mis, deadline)
    # rematch keeps the dropped label only for undelivered commands; restore gateway rejections
    orig = cmds.set_index(['profile', 'config', 'idx'])['dropped']
    key = list(zip(c.profile, c.config, c.idx))
    c['dropped_gateway'] = [orig.get(k, np.nan) for k in key]
    c['dropped'] = np.where(c['dropped'].isna() & c['dropped_gateway'].astype(str).str.startswith('rejected'),
                            c['dropped_gateway'], c['dropped'])
    return c, m


def share(col):
    return lambda d: float(d[col].mean()) if len(d) else np.nan


def paired_boot(a, b, fn, seed, n=BOOT):
    """fn(a) - fn(b) with the same mission indices resampled for both (paired by mission)."""
    ids = sorted(set(a.mission) & set(b.mission))
    ga = {i: g for i, g in a.groupby('mission')}
    gb = {i: g for i, g in b.groupby('mission')}
    if not ids:
        return np.nan, np.nan, np.nan, 0
    point = fn(pd.concat([ga[i] for i in ids])) - fn(pd.concat([gb[i] for i in ids]))
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(n):
        pick = rng.choice(ids, len(ids))
        v = fn(pd.concat([ga[i] for i in pick])) - fn(pd.concat([gb[i] for i in pick]))
        if v == v:
            vals.append(v)
    return point, float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5)), len(ids)


def handshake_boot(gm, seed):
    hs = gm[['mission', 'handshake_s']].dropna()
    if len(hs) == 0:
        return np.nan, np.nan, np.nan
    x = hs.handshake_s.values
    rng = np.random.default_rng(seed)
    bs = [np.median(rng.choice(x, len(x))) for _ in range(BOOT)]
    return float(np.median(x)), float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))


def mission_model_value(profile, config, deadline_col='avail_mean_0.5', rate=60.0):
    """Mission model availability at the 0.5 s deadline at the outage rate of the scripted missions (estimated)."""
    arch, rule = c6.STUDY[config]
    if rule is None:
        sw = pd.read_csv(os.path.join(ROOT, 'mission', 'results', 'sweeps.csv'))
        o = sw[(sw.tag == 'sweep:outage_rate_per_h') & (sw.vehicle == 'drone') & (sw.link == profile)
               & (sw.arch == arch) & (sw.over_outage_rate_per_h == rate)]
        col = 'avail_base_mean_0.5' if config == 'none' else deadline_col
        rule_name = {'none': 'none', 'signing': 'published', 'pqsig_real': 'no rule'}[config]
        return arch, rule_name, float(o[col].iloc[0])
    ro = pd.read_csv(os.path.join(ROOT, 'mission', 'results', 'replay_outage_sweep.csv'))
    r = ro[(ro.link == profile) & (ro.arch == arch) & (ro.over_outage_rate_per_h == rate) & (ro.replay_rule == rule)]
    if rule == 'cache':
        r = r[r.base_window == 1]
    return arch, rule, float(r[deadline_col].iloc[0])


def handshake_model(profile, delays, design='hybrid', runs=1000, seed=20311021 + 7000):
    """Mission model handshake transfer applied to the executed flight sizes and the RTL delays (estimated)."""
    from . import gateway as gw
    cfg = sim.build_config('drone', 'B' if design == 'hybrid' else 'A', profile)
    sizes = gw.flight_sizes(design)
    cfg = dict(cfg)
    cfg['ap'] = dict(cfg['ap'], flights=list(zip(['up', 'down', 'up', 'down'], sizes)))
    cfg['hs_eff'] = (delays[f'{design}_vehicle_f2']['seconds'] + delays[f'{design}_vehicle_f4']['seconds']) * cfg['clock']
    rng = np.random.default_rng(seed)
    return float(np.median([sim.sample_handshake(rng, cfg)[0] for _ in range(runs)]))


def reorder_stats(arr):
    """Per configuration: stream 0 arrivals at the vehicle gateway that came after a higher counter of the same key."""
    rows = []
    if arr is None or len(arr) == 0:
        return pd.DataFrame(rows)
    for (p, k), g in arr.groupby(['profile', 'config']):
        late, depth = 0, []
        for _, e in g.groupby('epoch', sort=False):
            mx = -1
            for cnt in e.counter.values:
                if cnt < mx:
                    late += 1
                    depth.append(mx - cnt)
                mx = max(mx, cnt)
        rows.append(dict(profile=p, config=k, arrivals=len(g), arrivals_after_higher_counter=late,
                         max_reorder_depth=int(max(depth)) if depth else 0, label='emulated'))
    return pd.DataFrame(rows)


def analyse(raw=RAW, res=RES):
    a = model.load_assumptions()
    s = c6.load_settings()
    deadline = a['deadline_s']
    cmds, mis, runs, arr = load_raw(raw)
    if cmds is None:
        print('no raw runs found')
        return 1
    os.makedirs(res, exist_ok=True)
    c, m = prepare(cmds, mis, deadline)
    seed0 = int(s['seed_base_r6']) + 5000
    out_c = c[['profile', 'config', 'mission', 'seed', 'idx', 't_send', 'rt_s', 'ow_s', 'result', 'dropped',
               'accepted_rt', 'delivered_ow', 'in_outage']].rename(columns={'ow_s': 'ow_s_emulated'})
    out_c['label'] = 'SITL measured'
    out_c.to_csv(os.path.join(res, 'commands.csv'), index=False, float_format='%.6f')
    mm = m[['profile', 'config', 'mission', 'seed', 'outage_start_after_arm_s', 'outage_duration_s', 'completed',
            'upload_ok', 'arm_ok']].rename(columns={'outage_start_after_arm_s': 'outage_start_after_arm_s_assumption',
                                                    'outage_duration_s': 'outage_duration_s_assumption'})
    mm['flight_s'] = m['t_disarm'] - m['t_arm']
    mm['handshake_s_emulated'] = m['handshake_s']
    mm['label'] = 'SITL measured'
    mm.to_csv(os.path.join(res, 'missions.csv'), index=False, float_format='%.6f')
    # delays and host compute
    delays = runs[0]['rtl_delays']
    drows = []
    for used, dd in [(1, delays)] + [(0, v) for _, v in sorted(runs[0].get('rtl_delays_other_cores', {}).items())]:
        drows += [dict(name=k, core=v['core'], used_in_runs=used, cycles=v['cycles'], clock_hz=a['clock_hz'],
                       delay_ms=v['seconds'] * 1e3, source=v['source'], label='estimated',
                       label_note='estimated from RTL simulated cycles') for k, v in sorted(dd.items())]
    pd.DataFrame(drows).to_csv(os.path.join(res, 'delays.csv'), index=False)
    hc = []
    for info in runs:
        for op, h in info['gateway']['host'].items():
            hc.append(dict(profile=info['profile'], config=info['config'], operation=op, count=h['n'],
                           host_mean_ms=h['host_s'] / h['n'] * 1e3 if h['n'] else np.nan, host_max_ms=h['host_max_s'] * 1e3,
                           delay_ms_estimated=h['rtl_s'] * 1e3, host_exceeds_rtl_delay=h['exceeds'],
                           side='vehicle' if op.startswith('vehicle') else 'ground', label='host measured'))
    pd.DataFrame(hc).to_csv(os.path.join(res, 'host_compute.csv'), index=False, float_format='%.6g')
    rows = []

    def add(p, k, metric, val, lo, hi, n, unit, label):
        rows.append(dict(profile=p, config=k, metric=metric, value=val, ci_lo=lo, ci_hi=hi, n=n, unit=unit, label=label))
    for p in c6.PROFILES:
        for ki, k in enumerate(c6.CONFIGS):
            g = c[(c.profile == p) & (c.config == k)]
            if len(g) == 0:
                continue
            gm = m[(m.profile == p) & (m.config == k)]
            sd = seed0 + 100 * c6.PROFILES.index(p) + 10 * ki
            up = g[~g.in_outage]
            acc_up = up[up.acked & (up.result == 0)]
            add(p, k, 'missions', len(gm), np.nan, np.nan, len(gm), 'count', 'SITL measured')
            add(p, k, 'missions_completed', int(gm.completed.sum()), np.nan, np.nan, len(gm), 'count', 'SITL measured')
            add(p, k, 'commands', len(g), np.nan, np.nan, len(gm), 'count', 'SITL measured')
            for name, df, fn, unit, lab in [
                    ('availability_rt_all', g, share('accepted_rt'), 'ratio', 'SITL measured'),
                    ('availability_rt_link_up', up, share('accepted_rt'), 'ratio', 'SITL measured'),
                    ('latency_rt_median_ms', acc_up, a5.med_ms('rt_s'), 'ms', 'SITL measured'),
                    ('latency_rt_p95_ms', acc_up, a5.p95_ms('rt_s'), 'ms', 'SITL measured'),
                    ('availability_ow_all', g, share('delivered_ow'), 'ratio', 'emulated'),
                    ('latency_ow_median_ms', up, a5.med_ms('ow_s'), 'ms', 'emulated')]:
                v, lo, hi = a5.cluster_boot(df, fn, sd + len(rows))
                add(p, k, name, v, lo, hi, len(gm), unit, lab)
            if k != 'none':
                b = c[(c.profile == p) & (c.config == 'none')]
                if len(b):
                    bu = b[~b.in_outage]
                    bacc = bu[bu.acked & (bu.result == 0)]
                    v, lo, hi, n = paired_boot(acc_up, bacc, a5.med_ms('rt_s'), sd + 50)
                    add(p, k, 'added_latency_rt_ms', v, lo, hi, n, 'ms', 'SITL measured')
            if c6.STUDY[k][1] is not None:
                v, lo, hi = handshake_boot(gm, sd + 60)
                add(p, k, 'handshake_median_s', v, lo, hi, int(gm.handshake_s.notna().sum()), 's', 'emulated')
    summ = pd.DataFrame(rows)
    summ.to_csv(os.path.join(res, 'summary.csv'), index=False, float_format='%.6g')
    # paired differences between configurations
    pr = []
    for p in c6.PROFILES:
        for j, (x, y) in enumerate(PAIRS):
            gx = c[(c.profile == p) & (c.config == x)]
            gy = c[(c.profile == p) & (c.config == y)]
            if len(gx) == 0 or len(gy) == 0:
                continue
            v, lo, hi, n = paired_boot(gx, gy, share('accepted_rt'), seed0 + 900 + 10 * j)
            pr.append(dict(profile=p, config=x, minus_config=y, metric='availability_rt_all', difference=v,
                           ci_lo=lo, ci_hi=hi, missions_paired=n, label='SITL measured'))
    pr = pd.DataFrame(pr, columns=['profile', 'config', 'minus_config', 'metric', 'difference', 'ci_lo', 'ci_hi',
                                   'missions_paired', 'label'])
    pr.to_csv(os.path.join(res, 'paired.csv'), index=False, float_format='%.6g')
    # rejections by reason: stream commands (commands.csv) and all stream 0 frames (gateway counters)
    rj = []
    for (p, k), g in c.groupby(['profile', 'config']):
        not_ok = g[~g.accepted_rt]
        for why, n in not_ok.dropped.fillna('acknowledged late or rejected by the flight stack').value_counts().items():
            rj.append(dict(profile=p, config=k, scope='stream commands not acknowledged within 0.5 s', reason=why,
                           count=int(n), label='SITL measured'))
    for info in runs:
        for why, n in sorted(info['gateway']['rejects'].items()):
            rj.append(dict(profile=info['profile'], config=info['config'], scope='uplink frames rejected by the vehicle side gateway',
                           reason=why, count=int(n), label='emulated'))
        for why, n in sorted(info['gateway']['down_rejects'].items()):
            rj.append(dict(profile=info['profile'], config=info['config'], scope='downlink frames rejected by the ground side gateway',
                           reason=why, count=int(n), label='emulated'))
        for why, n in sorted(info['relay_drops'].items()):
            rj.append(dict(profile=info['profile'], config=info['config'], scope='frames dropped by a gateway without a session',
                           reason=why, count=int(n), label='emulated'))
        rj.append(dict(profile=info['profile'], config=info['config'], scope='resynchronisations (strict rule)',
                       reason='all triggers', count=len(info['gateway']['resyncs']), label='emulated'))
        for trig in sorted({t for _, t in info['gateway']['resyncs']}):
            rj.append(dict(profile=info['profile'], config=info['config'], scope='resynchronisations (strict rule)',
                           reason=trig, count=sum(1 for _, t in info['gateway']['resyncs'] if t == trig), label='emulated'))
    pd.DataFrame(rj).to_csv(os.path.join(res, 'rejections.csv'), index=False)
    reorder_stats(arr).reindex(columns=['profile', 'config', 'arrivals', 'arrivals_after_higher_counter',
                                        'max_reorder_depth', 'label']).to_csv(os.path.join(res, 'reorder.csv'), index=False)
    # comparison with the mission model per rule
    comp = []
    for p in c6.PROFILES:
        for k in c6.CONFIGS:
            sv = summ[(summ.profile == p) & (summ.config == k) & (summ.metric == 'availability_rt_all')]
            if len(sv) == 0:
                continue
            r = sv.iloc[0]
            arch, rule, est = mission_model_value(p, k)
            verdict = 'consistent' if r.ci_lo <= est <= r.ci_hi else ('model higher' if est > r.ci_hi else 'model lower')
            comp.append(dict(profile=p, config=k, mission_arch=arch, mission_rule=rule,
                             quantity='share acknowledged within 0.5 s, outages included', value=r.value, ci_lo=r.ci_lo,
                             ci_hi=r.ci_hi, mission_model_estimated=est, error=r.value - est, verdict=verdict,
                             label='SITL measured'))
        for k, design in (('hybrid_published', 'hybrid'), ('classical', 'classical')):
            sv = summ[(summ.profile == p) & (summ.config == k) & (summ.metric == 'handshake_median_s')]
            if len(sv) == 0:
                continue
            r = sv.iloc[0]
            est = handshake_model(p, delays, design)
            verdict = 'consistent' if r.ci_lo <= est <= r.ci_hi else ('model higher' if est > r.ci_hi else 'model lower')
            comp.append(dict(profile=p, config=k, mission_arch='B' if design == 'hybrid' else 'A', mission_rule='',
                             quantity='median handshake s (mission transfer model with the executed flight sizes and RTL delays)',
                             value=r.value, ci_lo=r.ci_lo, ci_hi=r.ci_hi, mission_model_estimated=est,
                             error=r.value - est, verdict=verdict, label='emulated'))
    pd.DataFrame(comp).to_csv(os.path.join(res, 'comparison.csv'), index=False, float_format='%.6g')
    write_environment(runs, res)
    from . import plots_r6
    plots_r6.all_figures(c, summ, pr, m, res, deadline)
    print('wrote', res)
    return 0


def write_environment(runs, res):
    import platform
    import subprocess
    try:
        cpu = [l.split(':', 1)[1].strip() for l in subprocess.run(['lscpu'], capture_output=True, text=True).stdout.splitlines()
               if l.startswith('Model name')][0]
    except Exception:
        cpu = 'unknown'
    r0 = runs[0]
    env = dict(flight_stack=r0.get('flight_stack'), flight_stack_commit='fb773567896014da007bca58358704d4a0d8516f (tag Copter-4.7.2)',
               pymavlink=r0.get('pymavlink'), python=r0.get('python'), libraries=r0.get('libraries'),
               host=f'{cpu}, {os.cpu_count()} logical cores, Linux {platform.release()}',
               rtl_core=c6.load_settings()['rtl_core'], clock_hz=model.load_assumptions()['clock_hz'])
    old = os.path.join(res, 'environment.json')
    if os.path.exists(old):
        with open(old) as fh:
            prev = json.load(fh)
        if prev.get('host'):
            env['host'] = prev['host']
    with open(old, 'w') as fh:
        json.dump(env, fh, indent=1)


if __name__ == '__main__':
    sys.exit(analyse())
