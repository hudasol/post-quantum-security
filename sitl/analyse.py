"""Summarise the software in the loop runs and compare them with the mission study.

Reads sitl/raw/<profile>_<config>_{commands,missions,events}.csv and _run.json, writes
sitl/results/commands.csv, missions.csv, runs.csv, summary.csv and comparison.csv, and SVG figures.
Labels: timings that include the flight stack's own acknowledgement (COMMAND_ACK round trip,
acceptance, mission completion) are SITL measured; quantities produced by the emulated link alone
(one way delivery to the vehicle port, handshake and session recovery over the relay pair, channel
utilisation) are emulated; mission study values are estimated.
Intervals: 95 percent cluster bootstrap over missions, 2000 resamples, seed 20261021 + 5000.
"""
import glob
import json
import os
import sys

import numpy as np
import pandas as pd

from mission import model, sim
from . import config as cfgmod

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RAW = os.path.join(HERE, 'raw')
RES = os.path.join(HERE, 'results')
BOOT = 2000


def load_raw(raw=RAW):
    cmds, mis, runs = [], [], []
    for f in sorted(glob.glob(os.path.join(raw, '*_missions.csv'))):
        tag = os.path.basename(f)[:-len('_missions.csv')]
        m = pd.read_csv(f)
        c = pd.read_csv(os.path.join(raw, f'{tag}_commands.csv'))
        with open(os.path.join(raw, f'{tag}_run.json')) as fh:
            info = json.load(fh)
        mis.append(m)
        cmds.append(c)
        runs.append(info)
    if not mis:
        return None, None, []
    return pd.concat(cmds, ignore_index=True), pd.concat(mis, ignore_index=True), runs


def rematch(cmds, window=0.3):
    """Reassign each flight stack acknowledgement to the command it answers.

    The relay of the recorded runs matched acknowledgements to delivered commands first in first out; when
    the flight stack silently discards a delivered command (seen with signing, where a frame retransmitted by
    the emulated link layer arrives after a newer one and fails the timestamp rule) that order shifts. Here
    each acknowledgement event (vehicle side time, ground side time, result) is assigned to the latest command
    of the same run delivered to the vehicle at most `window` seconds before it; delivered commands without
    an acknowledgement are marked not_acknowledged_by_vehicle.
    """
    out = []
    for _, g in cmds.groupby(['profile', 'config'], sort=False):
        g = g.sort_values('idx').copy()
        acks = g.loc[g.t_vehicle_ack.notna(), ['t_vehicle_ack', 't_ground_ack', 'result']].sort_values('t_vehicle_ack')
        for col in ('t_vehicle_ack', 't_ground_ack', 'result'):
            g[col] = np.nan
        g['dropped'] = g['dropped'].where(g['t_vehicle'].isna(), np.nan).astype(object)
        deliv = g[g.t_vehicle.notna()].sort_values('t_vehicle')
        tv = deliv.t_vehicle.values
        used = set()
        for a in acks.itertuples():
            j = np.searchsorted(tv, a.t_vehicle_ack, side='right') - 1
            while j >= 0 and deliv.index[j] in used:
                j -= 1
            if j >= 0 and a.t_vehicle_ack - tv[j] <= window:
                i = deliv.index[j]
                used.add(i)
                g.loc[i, ['t_vehicle_ack', 't_ground_ack', 'result']] = [a.t_vehicle_ack, a.t_ground_ack, a.result]
        miss = g.t_vehicle.notna() & g.t_vehicle_ack.isna()
        g.loc[miss, 'dropped'] = 'not_acknowledged_by_vehicle'
        out.append(g)
    return pd.concat(out, ignore_index=True)


def prepare(cmds, mis, deadline):
    """Join commands to their mission, mark outage windows and compute latencies and outcomes."""
    cmds = rematch(cmds)
    m = mis.copy()
    m['o_s'] = m['t_arm'] + m['outage_start_after_arm_s']
    m['o_e'] = m['o_s'] + m['outage_duration_s']
    c = cmds.merge(m[['profile', 'config', 'mission', 'o_s', 'o_e', 't_arm', 't_disarm', 'seed']],
                   on=['profile', 'config', 'mission'], how='left')
    c = c[(c['t_send'] >= c['t_arm']) & (c['t_send'] <= c['t_disarm'])].copy()
    c['rt_s'] = c['t_ground_ack'] - c['t_send']
    c['ow_s'] = c['t_vehicle'] - c['t_send']
    c['acked'] = c['t_ground_ack'].notna()
    c['accepted_rt'] = c['acked'] & (c['result'] == 0) & (c['rt_s'] <= deadline)
    c['delivered_ow'] = c['t_vehicle'].notna() & (c['ow_s'] <= deadline)
    c['in_outage'] = (c['t_send'] >= c['o_s'] - deadline) & (c['t_send'] < c['o_e'])
    return c, m


def cluster_boot(df, fn, seed, n=BOOT):
    """Point value and 95 percent interval of fn over missions resampled with replacement."""
    groups = [g for _, g in df.groupby('mission')]
    if not groups:
        return np.nan, np.nan, np.nan
    point = fn(df)
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(n):
        idx = rng.integers(0, len(groups), len(groups))
        v = fn(pd.concat([groups[i] for i in idx]))
        if v == v:
            vals.append(v)
    if not vals:
        return point, np.nan, np.nan
    return point, float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def boot_diff(a, b, fn, seed, n=BOOT):
    """Difference fn(a) - fn(b) with missions of a and b resampled independently."""
    ga = [g for _, g in a.groupby('mission')]
    gb = [g for _, g in b.groupby('mission')]
    point = fn(a) - fn(b)
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(n):
        ia = rng.integers(0, len(ga), len(ga))
        ib = rng.integers(0, len(gb), len(gb))
        v = fn(pd.concat([ga[i] for i in ia])) - fn(pd.concat([gb[i] for i in ib]))
        if v == v:
            vals.append(v)
    return point, float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def med_ms(col):
    def f(d):
        x = d[col].dropna()
        return float(np.median(x) * 1e3) if len(x) else np.nan
    return f


def p95_ms(col):
    def f(d):
        x = d[col].dropna()
        return float(np.percentile(x, 95) * 1e3) if len(x) else np.nan
    return f


def frac(col):
    return lambda d: float(d[col].mean()) if len(d) else np.nan


def session_recovery(events, mis):
    """Hybrid only: time from the end of each outage to the next completed handshake, when a teardown happened."""
    out = []
    ev = events
    for _, r in mis.iterrows():
        o_s = r['t_arm'] + r['outage_start_after_arm_s']
        o_e = o_s + r['outage_duration_s']
        td = ev[(ev.event == 'teardown_ground') & (ev.t >= o_s) & (ev.t <= o_e + 30)]
        if len(td) == 0:
            continue
        done = ev[(ev.event == 'hs_done') & (ev.t > o_e)]
        if len(done):
            out.append(dict(mission=r['mission'], recovery_s=float(done.t.min() - o_e), outage_s=r['outage_duration_s']))
    return pd.DataFrame(out)


def command_recovery(c):
    """Per mission: time from the outage end to the first accepted acknowledgement that arrives after it."""
    rows = []
    for (p, k, mi), g in c.groupby(['profile', 'config', 'mission']):
        o_e = g['o_e'].iloc[0]
        ok = g[(g['acked']) & (g['result'] == 0) & (g['t_ground_ack'] > o_e)]
        if len(ok):
            rows.append(dict(profile=p, config=k, mission=mi, cmd_recovery_s=float(ok['t_ground_ack'].min() - o_e)))
    return pd.DataFrame(rows)


def study_values(profile, config):
    """Mission study values (estimated) for the comparison."""
    base = pd.read_csv(os.path.join(ROOT, 'mission', 'results', 'base.csv'))
    sw = pd.read_csv(os.path.join(ROOT, 'mission', 'results', 'sweeps.csv'))
    arch = cfgmod.STUDY_ARCH[config]
    b = base[(base.vehicle == 'drone') & (base.link == profile) & (base.arch == arch)].iloc[0]
    o = sw[(sw.tag == 'sweep:outage_rate_per_h') & (sw.vehicle == 'drone') & (sw.link == profile) & (sw.arch == arch)]
    col = 'avail_base_mean_0.5' if config == 'none' else 'avail_mean_0.5'
    out = dict(arch=arch,
               avail_no_outage=float(o[o.over_outage_rate_per_h == 0.0][col].iloc[0]),
               avail_60_per_h=float(o[o.over_outage_rate_per_h == 60.0][col].iloc[0]),
               avail_base=float(b[col]),
               added_latency_ms=0.0 if config == 'none' else float(b['added_latency_ms_median']),
               first_session_s=float(b['first_session_s_median']) if config == 'hybrid' else np.nan,
               ttra_s=float(b['ttra_s_median']) if config == 'hybrid' else np.nan)
    return out


def f1_handshake_estimate(profile, runs=1000, seed=20261021 + 7000):
    """Mission study handshake model applied to the four flights of design change F1 (estimated)."""
    cfg = sim.build_config('drone', 'B', profile)
    sc = cfgmod.security_config('hybrid')
    cfg = dict(cfg)
    cfg['ap'] = dict(cfg['ap'], flights=[(d, b) for d, b, _ in sc['flights']])
    cfg['hs_eff'] = cfgmod.handshake_compute_s(sc) * cfg['clock']
    rng = np.random.default_rng(seed)
    return float(np.median([sim.sample_handshake(rng, cfg)[0] for _ in range(runs)]))


SCORING_NAMES = {'none': 'no_auth', 'signing': 'mavlink2_signing', 'hybrid': 'hybrid_session',
                 'pqsig': 'pq_signature_per_command'}
LINK_NAMES = {'sik': 'sik_64kbps', 'ieee802154': 'ieee802154_250kbps'}


def write_scoring_summary(summ, m, res):
    """One row per configuration and link: SITL measured values beside mission study values read at run time."""
    base = pd.read_csv(os.path.join(ROOT, 'mission', 'results', 'base.csv'))
    rows = []
    for p in cfgmod.PROFILES:
        cmp_path = os.path.join(res, 'comparison.csv')
        cmp_df = pd.read_csv(cmp_path) if os.path.exists(cmp_path) else None

        def study_av(prof, cfg, fallback):
            # The SITL availability counts the outages of the scripted missions, so it is compared with the
            # mission study at the matching outage rate (the comparison table's study value), not at no outage.
            if cmp_df is None:
                return fallback
            r = cmp_df[(cmp_df.profile == prof) & (cmp_df.config == cfg) & (cmp_df.metric == 'availability_rt_all')]
            return float(r.iloc[0]['study_estimated']) if len(r) else fallback
        for k in cfgmod.CONFIGS:
            sv = summ[(summ.profile == p) & (summ.config == k)]
            if len(sv) == 0:
                continue

            def get(metric):
                r = sv[sv.metric == metric]
                return float(r.iloc[0]['value']) if len(r) else np.nan
            arch = cfgmod.STUDY_ARCH[k]
            b = base[(base.vehicle == 'drone') & (base.link == p) & (base.arch == arch)].iloc[0]
            gm = m[(m.profile == p) & (m.config == k)]
            rows.append(dict(label='SITL measured', configuration=SCORING_NAMES[k], link=LINK_NAMES[p],
                             missions=len(gm), missions_completed=int(gm.completed.sum()),
                             added_latency_ms_median=np.nan if k == 'none' else get('added_latency_rt_ms'),
                             handshake_s_median=get('handshake_median_s') if k == 'hybrid' else np.nan,
                             availability=get('availability_rt_all'),
                             mission_study_architecture=arch if k != 'none' else 'A (unauthenticated stream columns)',
                             mission_study_added_latency_ms=np.nan if k == 'none' else float(b['added_latency_ms_median']),
                             mission_study_availability=study_av(p, k, float(b['avail_base_mean_0.5'] if k == 'none' else b['avail_mean_0.5'])),
                             seed_first=int(gm.seed.min()), seed_last=int(gm.seed.max()),
                             label_note=('label applies to the SITL columns; handshake_s_median is emulated (relay pair '
                                         'only); mission_study_* columns are estimated, read at run time from '
                                         'mission/results/base.csv (drone, same link, matching architecture); mission_study_availability is the '
                                         'study value at the outage rate of the scripted missions (comparison.csv)')))
    pd.DataFrame(rows).to_csv(os.path.join(res, 'sitl_summary.csv'), index=False, float_format='%.6g')


def write_environment(runs, res):
    """Record the flight stack, library versions and host of the runs (read from the run files and lscpu)."""
    import platform
    import subprocess
    try:
        cpu = [l.split(':', 1)[1].strip() for l in subprocess.run(['lscpu'], capture_output=True, text=True).stdout.splitlines()
               if l.startswith('Model name')][0]
    except Exception:
        cpu = 'unknown'
    env = dict(flight_stack=runs[0].get('flight_stack', 'unknown') if runs else 'unknown',
               flight_stack_commit='fb773567896014da007bca58358704d4a0d8516f (tag Copter-4.7.2)',
               pymavlink=next((r['pymavlink'] for r in runs if 'pymavlink' in r), '2.4.50'),
               python=next((r['python'] for r in runs if 'python' in r), platform.python_version()),
               host=f'{cpu}, {os.cpu_count()} logical cores, Linux {platform.release()}',
               px4_note=('PX4 v1.17.0 (the pinned PX4 checkout of this round) has no MAVLink 2 signing in its MAVLink module '
                         '(no SETUP_SIGNING handling in src/modules/mavlink), while its later documentation (v1.18) has a '
                         'page on message signing; to keep one baseline for all four configurations, all four run on '
                         'ArduPilot, whose documentation describes signing.'))
    with open(os.path.join(res, 'environment.json'), 'w') as fh:
        json.dump(env, fh, indent=1)


def analyse(raw=RAW, res=RES):
    a = model.load_assumptions()
    s = cfgmod.load_settings()
    deadline = a['deadline_s']
    cmds, mis, runs = load_raw(raw)
    if cmds is None:
        print('no raw runs found')
        return 1
    os.makedirs(res, exist_ok=True)
    c, m = prepare(cmds, mis, deadline)
    seed0 = int(s['seed']) + 5000
    out_c = c[['profile', 'config', 'mission', 'seed', 'idx', 't_send', 'rt_s', 'ow_s', 'result', 'dropped', 'accepted_rt',
               'delivered_ow', 'in_outage']].copy()
    out_c = out_c.rename(columns={'ow_s': 'ow_s_emulated'})
    out_c['label'] = 'SITL measured'
    out_c.to_csv(os.path.join(res, 'commands.csv'), index=False, float_format='%.6f')
    mm = m[['profile', 'config', 'mission', 'seed', 'outage_start_after_arm_s', 'outage_duration_s', 'completed',
            'upload_ok', 'arm_ok']].copy()
    mm['flight_s'] = m['t_disarm'] - m['t_arm']
    mm = mm.rename(columns={'outage_start_after_arm_s': 'outage_start_after_arm_s_assumption',
                            'outage_duration_s': 'outage_duration_s_assumption'})
    mm['handshake_s_emulated'] = m['handshake_s']
    mm['label'] = 'SITL measured'
    mm.to_csv(os.path.join(res, 'missions.csv'), index=False, float_format='%.6f')
    # per run channel statistics (emulated)
    rr = []
    for info in runs:
        st = info['channel_stats']
        dur = info['t_end'] - info['t_relay_start']
        rr.append(dict(profile=info['profile'], config=info['config'], base_seed=info['base_seed'],
                       duration_s=dur, utilisation=(st['air_s']['up'] + st['air_s']['down']) / dur,
                       wire_bytes_up=st['wire_bytes']['up'], wire_bytes_down=st['wire_bytes']['down'],
                       frames=st['frames'], lost_frames=st['lost_frames'], retransmissions=st['retransmissions'],
                       failed_units=st['failed_units'], buffer_drops=st['buffer_drops'],
                       commands_sent=info['commands_sent'], commands_seen_by_relay=info['commands_seen_by_relay'],
                       params_ok=int(all(info['params_ok'].values())), label='emulated'))
    pd.DataFrame(rr).to_csv(os.path.join(res, 'runs.csv'), index=False, float_format='%.6f')
    write_environment(runs, res)
    rows = []
    comp = []

    def add(p, k, metric, val, lo, hi, n, unit, label):
        rows.append(dict(profile=p, config=k, metric=metric, value=val, ci_lo=lo, ci_hi=hi, n=n, unit=unit, label=label))
    rec_all = command_recovery(c)
    for p in cfgmod.PROFILES:
        for ki, k in enumerate(cfgmod.CONFIGS):
            g = c[(c.profile == p) & (c.config == k)]
            if len(g) == 0:
                continue
            gm = m[(m.profile == p) & (m.config == k)]
            sd = seed0 + 100 * cfgmod.PROFILES.index(p) + 10 * ki
            up = g[~g.in_outage]
            acc_up = up[up.acked & (up.result == 0)]
            n_m = len(gm)
            add(p, k, 'missions', n_m, np.nan, np.nan, n_m, 'count', 'SITL measured')
            add(p, k, 'missions_completed', int(gm.completed.sum()), np.nan, np.nan, n_m, 'count', 'SITL measured')
            add(p, k, 'commands', len(g), np.nan, np.nan, n_m, 'count', 'SITL measured')
            for name, df, fn, unit, lab in [
                    ('availability_rt_all', g, frac('accepted_rt'), 'ratio', 'SITL measured'),
                    ('availability_rt_link_up', up, frac('accepted_rt'), 'ratio', 'SITL measured'),
                    ('latency_rt_median_ms', acc_up, med_ms('rt_s'), 'ms', 'SITL measured'),
                    ('latency_rt_p95_ms', acc_up, p95_ms('rt_s'), 'ms', 'SITL measured'),
                    ('availability_ow_all', g, frac('delivered_ow'), 'ratio', 'emulated'),
                    ('availability_ow_link_up', up, frac('delivered_ow'), 'ratio', 'emulated'),
                    ('latency_ow_median_ms', up, med_ms('ow_s'), 'ms', 'emulated')]:
                v, lo, hi = cluster_boot(df, fn, sd + len(rows))
                add(p, k, name, v, lo, hi, n_m, unit, lab)
            if k != 'none':
                b = c[(c.profile == p) & (c.config == 'none')]
                if len(b):
                    bu = b[~b.in_outage]
                    bacc = bu[bu.acked & (bu.result == 0)]
                    v, lo, hi = boot_diff(acc_up, bacc, med_ms('rt_s'), sd + 50)
                    add(p, k, 'added_latency_rt_ms', v, lo, hi, n_m, 'ms', 'SITL measured')
                    v, lo, hi = boot_diff(up, bu, med_ms('ow_s'), sd + 51)
                    add(p, k, 'added_latency_ow_ms', v, lo, hi, n_m, 'ms', 'emulated')
            rc = rec_all[(rec_all.profile == p) & (rec_all.config == k)] if len(rec_all) else rec_all
            if len(rc):
                add(p, k, 'command_recovery_median_s', float(rc.cmd_recovery_s.median()), float(rc.cmd_recovery_s.min()),
                    float(rc.cmd_recovery_s.max()), len(rc), 's (range in ci columns)', 'SITL measured')
            if k == 'hybrid':
                hs = gm['handshake_s'].dropna()
                if len(hs):
                    add(p, k, 'handshake_median_s', float(hs.median()), float(hs.min()), float(hs.max()), len(hs),
                        's (range in ci columns)', 'emulated')
                evf = os.path.join(raw, f'{p}_{k}_events.csv')
                ev = pd.read_csv(evf)
                sr = session_recovery(ev, gm)
                add(p, k, 'teardowns', len(sr), np.nan, np.nan, n_m, 'count', 'emulated')
                if len(sr):
                    add(p, k, 'session_recovery_median_s', float(sr.recovery_s.median()), float(sr.recovery_s.min()),
                        float(sr.recovery_s.max()), len(sr), 's (range in ci columns)', 'emulated')
    summ = pd.DataFrame(rows)
    summ.to_csv(os.path.join(res, 'summary.csv'), index=False, float_format='%.6g')
    # comparison with the mission study
    for p in cfgmod.PROFILES:
        cmp_path = os.path.join(res, 'comparison.csv')
        cmp_df = pd.read_csv(cmp_path) if os.path.exists(cmp_path) else None

        def study_av(prof, cfg, fallback):
            # The SITL availability counts the outages of the scripted missions, so it is compared with the
            # mission study at the matching outage rate (the comparison table's study value), not at no outage.
            if cmp_df is None:
                return fallback
            r = cmp_df[(cmp_df.profile == prof) & (cmp_df.config == cfg) & (cmp_df.metric == 'availability_rt_all')]
            return float(r.iloc[0]['study_estimated']) if len(r) else fallback
        for k in cfgmod.CONFIGS:
            sv = summ[(summ.profile == p) & (summ.config == k)]
            if len(sv) == 0:
                continue
            st = study_values(p, k)

            def get(metric):
                r = sv[sv.metric == metric]
                return r.iloc[0] if len(r) else None

            pairs = [('availability_ow_link_up', 'avail_no_outage', 'availability at 0.5 s, no outage'),
                     ('availability_rt_link_up', 'avail_no_outage', 'availability at 0.5 s, no outage'),
                     ('availability_ow_all', 'avail_60_per_h', 'availability at 0.5 s, outage rate 60 per h'),
                     ('availability_rt_all', 'avail_60_per_h', 'availability at 0.5 s, outage rate 60 per h')]
            if k != 'none':
                pairs += [('added_latency_ow_ms', 'added_latency_ms', 'added latency per command ms'),
                          ('added_latency_rt_ms', 'added_latency_ms', 'added latency per command ms')]
            if k == 'hybrid':
                pairs += [('handshake_median_s', 'first_session_s', 'first session s (study without F1)'),
                          ('session_recovery_median_s', 'ttra_s', 'recovery after teardown s')]
            for metric, skey, desc in pairs:
                r = get(metric)
                if r is None:
                    continue
                sval = st[skey]
                lo, hi = r['ci_lo'], r['ci_hi']
                if lo == lo and hi == hi and 'range' not in str(r['unit']):
                    verdict = 'consistent' if lo <= sval <= hi else ('study higher' if sval > hi else 'study lower')
                else:
                    verdict = 'no interval'
                comp.append(dict(profile=p, config=k, study_arch=st['arch'], metric=metric, study_quantity=desc,
                                 value=r['value'], ci_lo=r['ci_lo'], ci_hi=r['ci_hi'], study_estimated=sval,
                                 error=r['value'] - sval, verdict=verdict, label=r['label']))
            if k == 'hybrid':
                r = get('handshake_median_s')
                if r is not None:
                    e = f1_handshake_estimate(p)
                    comp.append(dict(profile=p, config=k, study_arch='B with F1', metric='handshake_median_s',
                                     study_quantity='first session s, study model with the F1 flights',
                                     value=r['value'], ci_lo=r['ci_lo'], ci_hi=r['ci_hi'], study_estimated=e,
                                     error=r['value'] - e, verdict='no interval', label=r['label']))
    pd.DataFrame(comp).to_csv(os.path.join(res, 'comparison.csv'), index=False, float_format='%.6g')
    write_scoring_summary(summ, m, res)
    from . import plots
    plots.make_all(c, m, summ, pd.DataFrame(comp), res, deadline)
    return 0


if __name__ == '__main__':
    sys.exit(analyse())
