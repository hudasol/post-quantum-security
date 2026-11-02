"""Summarise the round 7 gateway emulation runs (sitl/raw_r7/<set>/) beside the round 6 runs, which are read, never
changed (sitl/raw_r6/).

Writes sitl/results_r7/:
  missed_per_mission.csv  one row per set, configuration and mission (the round 6 definition: stream commands not
                          acknowledged within 0.5 s, outages included)
  summary.csv             per set and configuration: missions, commands, shares acknowledged within 0.5 s and 1 s,
                          round trip median, added round trip against no authentication, missed commands per
                          mission, handshake median
  paired_missed.csv       paired differences of missed commands per mission between configurations of a set
  loss_change.csv         per configuration: burst loss minus independent loss, paired by seed, and the difference
                          of that change between two configurations
  burst_loss.csv          per burst loss run: frames sent, frames lost to the loss process, to outages, and in the
                          bad state
  rerun_check.csv         larger set, missions 0 to 19, against round 6 (or the falcon20 set) on the same seeds
  host_compute.csv        ground and vehicle side compute of the gateways on the host (host measured)
  delays.csv              vehicle side delays used (estimated from RTL simulated cycles)
Reference runs under independent loss on seeds 0 to 19: the round 6 runs for the round 6 configurations and the
falcon20 set for Falcon-512. A run split over two lanes (large100 hybrid_strict, missions 0 to 49 and 50 to 99) is
prepared per part and then merged; its seeds are those of missions 0 to 99 either way.
Labels: as round 6 (sitl/analyse_r6.py): round trips, shares and missed commands are SITL measured; channel counts
are emulated; delays estimated; host compute host measured. Intervals: 95 percent bootstrap over missions (2000
resamples), paired by mission seed for differences. Bootstrap seeds: 20311021 + 9000 + offsets. Author: Huda Mueen.
"""
import glob
import json
import os
import sys

import numpy as np
import pandas as pd

from mission import model
from . import analyse as a5
from . import analyse_r6 as a6
from . import config_r6 as c6
from . import config_r7 as c7

HERE = os.path.dirname(os.path.abspath(__file__))
RAW7 = os.path.join(HERE, 'raw_r7')
RES7 = os.path.join(HERE, 'results_r7')
SETS = ['falcon20', 'burst20', 'large100']
SEED0 = 20311021 + 9000
PAIRS = {
    'falcon20': [('pqsig_falcon', 'pqsig_real'), ('pqsig_falcon', 'hybrid_published'), ('pqsig_falcon', 'none'),
                 ('pqsig_falcon_counter', 'pqsig_falcon'), ('pqsig_falcon_counter', 'pqsig_counter')],
    'burst20': None, 'large100': None,
}
KEY_PAIRS = [('hybrid_strict', 'hybrid_published'), ('hybrid_strict_inband', 'hybrid_published'),
             ('hybrid_cache', 'hybrid_published'), ('hybrid_strict', 'hybrid_cache'),
             ('hybrid_published', 'classical'), ('hybrid_published', 'none'), ('kem_auth', 'hybrid_published'),
             ('pqsig_real', 'hybrid_published'), ('pqsig_falcon', 'hybrid_published'), ('pqsig_falcon', 'pqsig_real')]
PAIRS['burst20'] = PAIRS['large100'] = KEY_PAIRS
# configurations whose change from independent to burst loss is compared (R7.13)
CHANGE_PAIRS = [('pqsig_real', 'hybrid_published'), ('pqsig_falcon', 'hybrid_published'),
                ('hybrid_strict', 'hybrid_published'), ('hybrid_cache', 'hybrid_published')]


def load_folder(raw):
    """(commands, missions, runs) of the runs in one folder; the configuration of a part that does not start at
    mission 0 carries the suffix @<first mission> until it is merged."""
    cmds, mis, runs = [], [], []
    for f in sorted(glob.glob(os.path.join(raw, '*_missions.csv'))):
        tag = os.path.basename(f)[:-len('_missions.csv')]
        with open(os.path.join(raw, f'{tag}_run.json')) as fh:
            info = json.load(fh)
        first = int(info.get('first_mission', 0) or 0)
        key = info['config'] + (f'@{first}' if first else '')
        mi = pd.read_csv(f)
        cm = pd.read_csv(os.path.join(raw, f'{tag}_commands.csv'))
        mi['config'] = key
        cm['config'] = key
        info['_config'] = info['config']
        info['config'] = key
        info['_tag'] = tag
        info['_events'] = pd.read_csv(os.path.join(raw, f'{tag}_events.csv'))
        cmds.append(cm)
        mis.append(mi)
        runs.append(info)
    if not mis:
        return None, None, []
    return pd.concat(cmds, ignore_index=True), pd.concat(mis, ignore_index=True), runs


def merged(df):
    if df is None or 'config' not in df:
        return df
    df = df.copy()
    df['config'] = df['config'].astype(str).str.split('@').str[0]
    return df


def prepared(cmds, mis, runs, deadline):
    c, m = a6.prepare(cmds, mis, deadline)
    mpm = a6.missed_per_mission(c, mis, runs)
    return merged(c), merged(m), merged(mpm)


def load_round6(deadline):
    cmds, mis, runs, _ = a6.load_raw(a6.RAW)
    return prepared(cmds, mis, runs, deadline), runs


def summary_rows(set_name, c, c1, m, mpm, base_c, k, sd):
    rows = []

    def add(metric, v, lo, hi, n, unit, label):
        rows.append(dict(set=set_name, profile='sik', config=k, metric=metric, value=v, ci_lo=lo, ci_hi=hi, n=n,
                         unit=unit, label=label))
    g = c[c.config == k]
    g1 = c1[c1.config == k]
    gm = m[m.config == k]
    gp = mpm[mpm.config == k]
    if len(g) == 0:
        return rows
    up = g[~g.in_outage]
    acc_up = up[up.acked & (up.result == 0)]
    add('missions', len(gm), np.nan, np.nan, len(gm), 'count', 'SITL measured')
    add('missions_completed', int(gm.completed.sum()), np.nan, np.nan, len(gm), 'count', 'SITL measured')
    add('commands', len(g), np.nan, np.nan, len(gm), 'count', 'SITL measured')
    for name, df, fn, unit in [('availability_rt_all', g, a6.share('accepted_rt'), 'ratio'),
                               ('availability_rt_all_1s', g1, a6.share('accepted_rt'), 'ratio'),
                               ('latency_rt_median_ms', acc_up, a5.med_ms('rt_s'), 'ms')]:
        v, lo, hi = a5.cluster_boot(df, fn, sd + len(rows))
        add(name, v, lo, hi, len(gm), unit, 'SITL measured')
    v, lo, hi = a5.cluster_boot(gp, lambda d: float(d.missed.mean()), sd + 40)
    add('missed_per_mission', v, lo, hi, len(gp), 'count', 'SITL measured')
    if k != 'none' and base_c is not None and len(base_c):
        bu = base_c[~base_c.in_outage]
        bacc = bu[bu.acked & (bu.result == 0)]
        v, lo, hi, n = a6.paired_boot(acc_up, bacc, a5.med_ms('rt_s'), sd + 50)
        add('added_latency_rt_ms', v, lo, hi, n, 'ms', 'SITL measured')
    if k in c6.SESSION:
        v, lo, hi = a6.handshake_boot(gm, sd + 60)
        add('handshake_median_s', v, lo, hi, int(gm.handshake_s.notna().sum()), 's', 'emulated')
    return rows


def paired_rows(set_name, mpm, pairs, seed):
    out = []
    for j, (x, y) in enumerate(pairs):
        gx, gy = mpm[mpm.config == x], mpm[mpm.config == y]
        if len(gx) == 0 or len(gy) == 0:
            continue
        v, lo, hi, n = a6.paired_boot(gx, gy, lambda d: float(d.missed.mean()), seed + 10 * j)
        jx, jy = gx.set_index('mission'), gy.set_index('mission')
        ids = sorted(set(jx.index) & set(jy.index))
        dm = jx.loc[ids, 'missed'] - jy.loc[ids, 'missed']
        out.append(dict(set=set_name, profile='sik', config=x, minus_config=y, metric='missed_per_mission',
                        difference=v, ci_lo=lo, ci_hi=hi, missions_paired=n, missions_differing=int((dm != 0).sum()),
                        label='SITL measured'))
    return out


def change_frame(burst, indep, k):
    """Per mission: missed under burst loss minus missed under independent loss for configuration k."""
    b = burst[burst.config == k].set_index('mission')
    i = indep[indep.config == k].set_index('mission')
    ids = sorted(set(b.index) & set(i.index))
    return pd.DataFrame(dict(mission=ids, missed=(b.loc[ids, 'missed'] - i.loc[ids, 'missed']).values))


def analyse(raw=RAW7, res=RES7):
    a = model.load_assumptions()
    deadline = a['deadline_s']
    os.makedirs(res, exist_ok=True)
    (c6c, c6m, c6p), runs6 = load_round6(deadline)
    (c6c1, _, _), _ = load_round6(1.0)
    sets = {}
    for s in SETS:
        cm, mi, runs = load_folder(os.path.join(raw, s))
        if cm is None:
            continue
        c, m, mpm = prepared(cm, mi, runs, deadline)
        c1 = prepared(cm, mi, runs, 1.0)[0]
        sets[s] = dict(c=c, c1=c1, m=m, mpm=mpm, runs=runs)
    if not sets:
        print('no round 7 runs found')
        return 1
    # independent loss reference on seeds 0 to 19: round 6 runs, and falcon20 for Falcon-512
    ref = dict(c=c6c, c1=c6c1, m=c6m, mpm=c6p)
    if 'falcon20' in sets:
        for x in ('c', 'c1', 'm', 'mpm'):
            ref[x] = pd.concat([ref[x], sets['falcon20'][x]], ignore_index=True)
    mpm_all, summ, pairs, change, bl, rr, hc, dl = [], [], [], [], [], [], [], []
    for si, s in enumerate(SETS):
        if s not in sets:
            continue
        d = sets[s]
        mp = d['mpm'].copy()
        mp.insert(0, 'set', s)
        mpm_all.append(mp)
        if s == 'falcon20':
            # Falcon-512 against the round 6 runs on the same seeds and loss model
            c, c1, m, mpm = ref['c'], ref['c1'], ref['m'], ref['mpm']
            confs = c7.CONFIGS
        else:
            c, c1, m, mpm = d['c'], d['c1'], d['m'], d['mpm']
            confs = c7.SETS[s]['configs']
        base = c[c.config == 'none']
        for ki, k in enumerate(confs):
            summ += summary_rows(s, c, c1, m, mpm, base, k, SEED0 + 1000 * si + 100 * ki)
        pairs += paired_rows(s, mpm, PAIRS[s], SEED0 + 1000 * si + 900)
        for info in d['runs']:
            st = info['channel_stats']
            if 'burst_lost_frames' in st:
                bl.append(dict(set=s, profile=info['profile'], config=info['_config'], part=info['config'],
                               missions=info.get('missions_run'), frames=st['frames'], lost_frames=st['lost_frames'],
                               burst_lost_frames=st['burst_lost_frames'], outage_lost_frames=st['outage_lost_frames'],
                               bad_state_frames=st['bad_state_frames'],
                               mean_loss_assumption=info['link_profile']['burst']['mean_loss'],
                               mean_burst_frames_assumption=info['link_profile']['burst']['mean_burst_frames'],
                               label='emulated'))
            for op, h in info['gateway']['host'].items():
                hc.append(dict(set=s, profile=info['profile'], config=info['_config'], part=info['config'],
                               operation=op, count=h['n'],
                               host_mean_ms=h['host_s'] / h['n'] * 1e3 if h['n'] else np.nan,
                               host_max_ms=h['host_max_s'] * 1e3, delay_ms_estimated=h['rtl_s'] * 1e3,
                               host_exceeds_rtl_delay=h['exceeds'],
                               side='vehicle' if op.startswith('vehicle') else 'ground', label='host measured'))
            if info['_config'] in c7.CONFIGS and s == 'falcon20':
                for used, dd in [(1, info['rtl_delays'])] + [(0, v) for _, v in sorted(info.get('rtl_delays_other_cores', {}).items())]:
                    dl += [dict(set=s, name=kk, core=v['core'], used_in_runs=used, cycles=v['cycles'],
                                clock_hz=a['clock_hz'], delay_ms=v['seconds'] * 1e3, source=v['source'],
                                label='estimated', label_note='estimated from RTL simulated cycles')
                           for kk, v in sorted(dd.items()) if kk.startswith('falcon512')]
    # change from independent to burst loss, paired by seed
    if 'burst20' in sets:
        b = sets['burst20']['mpm']
        for ki, k in enumerate(c7.BURST_SET):
            f = change_frame(b, ref['mpm'], k)
            if len(f) == 0:
                continue
            v, lo, hi = a5.cluster_boot(f, lambda d: float(d.missed.mean()), SEED0 + 5000 + 10 * ki)
            change.append(dict(config=k, minus_config='', metric='missed_per_mission burst minus independent',
                               difference=v, ci_lo=lo, ci_hi=hi, missions_paired=len(f), label='SITL measured'))
        for j, (x, y) in enumerate(CHANGE_PAIRS):
            fx, fy = change_frame(b, ref['mpm'], x), change_frame(b, ref['mpm'], y)
            if len(fx) == 0 or len(fy) == 0:
                continue
            v, lo, hi, n = a6.paired_boot(fx, fy, lambda d: float(d.missed.mean()), SEED0 + 5500 + 10 * j)
            change.append(dict(config=x, minus_config=y,
                               metric='change of missed_per_mission from independent to burst loss, difference',
                               difference=v, ci_lo=lo, ci_hi=hi, missions_paired=n, label='SITL measured'))
    # larger set, missions 0 to 19, against the reference runs on the same seeds
    if 'large100' in sets:
        L = sets['large100']['mpm']
        for ki, k in enumerate(c7.BURST_SET):
            x = L[(L.config == k) & (L.mission < 20)]
            y = ref['mpm'][ref['mpm'].config == k]
            if len(x) == 0 or len(y) == 0:
                continue
            v, lo, hi, n = a6.paired_boot(x, y, lambda d: float(d.missed.mean()), SEED0 + 6000 + 10 * ki)
            rr.append(dict(config=k, metric='missed_per_mission, larger set missions 0 to 19 minus reference run',
                           larger_set_mean=float(x.missed.mean()), reference_mean=float(y.missed.mean()),
                           difference=v, ci_lo=lo, ci_hi=hi, missions_paired=n,
                           reference='falcon20' if k in c7.CONFIGS else 'round 6', label='SITL measured'))
    out = [('missed_per_mission.csv', pd.concat(mpm_all, ignore_index=True)), ('summary.csv', pd.DataFrame(summ)),
           ('paired_missed.csv', pd.DataFrame(pairs)), ('loss_change.csv', pd.DataFrame(change)),
           ('burst_loss.csv', pd.DataFrame(bl)), ('rerun_check.csv', pd.DataFrame(rr)),
           ('host_compute.csv', pd.DataFrame(hc)), ('delays.csv', pd.DataFrame(dl))]
    for name, df in out:
        if len(df):
            df.to_csv(os.path.join(res, name), index=False, float_format='%.6g')
    print('wrote', res)
    return 0


if __name__ == '__main__':
    sys.exit(analyse())
