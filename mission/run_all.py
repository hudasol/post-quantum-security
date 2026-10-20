"""Run the mission study and generate docs/MISSION_STUDY.md and docs/REFERENCE_ARCHITECTURE.md.

Usage:
    python3 -m mission.run_all            # full run (seed 20261020, 1000 runs per configuration)
    python3 -m mission.run_all --reuse    # regenerate figures and documents from mission/results/
Every number in the two documents is read from the result files written by mission/study.py.
"""
import json
import math
import os
import sys

import numpy as np
import pandas as pd

from . import model, study

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RES = os.path.join(HERE, 'results')
FIG = os.path.join(HERE, '..', 'docs', 'figures', 'mission')
DOC_STUDY = os.path.join(ROOT, 'docs', 'MISSION_STUDY.md')
DOC_ARCH = os.path.join(ROOT, 'docs', 'REFERENCE_ARCHITECTURE.md')
PINK = ['#d63384', '#ad1457', '#f48fb1', '#880e4f', '#f8bbd0']
LABEL = '_estimated (modelled from published sizes and cycle counts plus labelled assumptions; not measured); seed 20261020_'


def fmt(x, nd=3):
    """Format a number for a table; NaN becomes 'n/a'."""
    if x is None or (isinstance(x, float) and (math.isnan(x))):
        return 'n/a'
    if isinstance(x, (int, np.integer)):
        return str(int(x))
    if x == math.inf:
        return 'inf'
    ax = abs(x)
    if ax != 0 and (ax < 10 ** (-nd) or ax >= 1e5):
        return f'{x:.2e}'
    return f'{x:.{nd}f}'


def md_table(df, cols, headers=None):
    """Markdown table from selected DataFrame columns."""
    headers = headers or cols
    out = ['| ' + ' | '.join(headers) + ' |', '|' + '---|' * len(cols)]
    for _, r in df.iterrows():
        out.append('| ' + ' | '.join(fmt(r[c]) if isinstance(r[c], (float, int, np.floating, np.integer))
                                     and not isinstance(r[c], bool) else str(r[c]) for c in cols) + ' |')
    return '\n'.join(out)


def ci(r, m, nd=3):
    return f"{fmt(r[m + '_median'], nd)} [{fmt(r[m + '_lo'], nd)}, {fmt(r[m + '_hi'], nd)}]"


def cim(r, nd=4):
    """Mean availability with its bootstrap 95 percent interval."""
    return f"{fmt(r['avail_mean'], nd)} [{fmt(r['avail_mean_lo'], nd)}, {fmt(r['avail_mean_hi'], nd)}]"


def load():
    base = pd.read_csv(os.path.join(RES, 'base.csv'))
    sweeps = pd.read_csv(os.path.join(RES, 'sweeps.csv'))
    low = pd.read_csv(os.path.join(RES, 'lowrate.csv'))
    env = pd.read_csv(os.path.join(RES, 'envelope.csv'))
    comp = pd.read_csv(os.path.join(RES, 'compute_latency.csv'))
    src = pd.read_csv(os.path.join(RES, 'cycle_sources.csv'))
    cross = pd.read_csv(os.path.join(RES, 'link_crosscheck.csv'))
    mo = pd.read_csv(os.path.join(RES, 'morris.csv'))
    with open(os.path.join(RES, 'config.json')) as f:
        cfg = json.load(f)
    return dict(base=base, sweeps=sweeps, low=low, env=env, comp=comp, src=src, cross=cross, mo=mo, cfg=cfg)


# ------------------------------------------------------------------ figures

def figures(d):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    os.makedirs(FIG, exist_ok=True)
    base = d['base']
    paths = {}
    # 1. availability against deadline
    fig, axs = plt.subplots(1, 2, figsize=(10, 4), sharey=True)
    for ax, link in zip(axs, ['sik', 'ieee802154']):
        for i, arch in enumerate(model.ARCHS):
            r = base[(base.vehicle == 'drone') & (base.link == link) & (base.arch == arch)].iloc[0]
            ax.plot(study.DEADLINES, [r[f'avail_mean_{x:g}'] for x in study.DEADLINES], marker='o', color=PINK[i],
                    label=arch)
        ax.set_xscale('log')
        ax.set_title(model.LINK_NAMES[link])
        ax.set_xlabel('command deadline (s)')
        ax.grid(alpha=0.3)
    axs[0].set_ylabel('control availability (mean of 1000 runs)')
    axs[0].legend()
    fig.suptitle('Drone, availability against deadline (estimated, seed 20261020, base assumptions)')
    fig.tight_layout()
    paths['deadline'] = os.path.join(FIG, 'mission_availability_deadline.png')
    fig.savefig(paths['deadline'], dpi=120)
    plt.close(fig)
    # 2. availability and recovery against frame loss
    sw = d['sweeps']
    fl = sw[sw.tag == 'sweep:frame_loss']
    fig, axs = plt.subplots(1, 2, figsize=(10, 4))
    for i, arch in enumerate(model.ARCHS):
        s = fl[(fl.link == 'sik') & (fl.arch == arch)].sort_values('over_frame_loss')
        axs[0].plot(s.over_frame_loss, s.avail_mean, marker='o', color=PINK[i], label=arch)
        if arch in ('A', 'B'):
            for j, link in enumerate(['sik', 'ieee802154']):
                s2 = fl[(fl.link == link) & (fl.arch == arch)].sort_values('over_frame_loss')
                axs[1].plot(s2.over_frame_loss, s2.ttra_s_median, marker='os'[j], color=PINK[i + 2 * j],
                            label=f'{arch} {model.LINK_NAMES[link]}')
    axs[0].set_title('SiK, availability at 0.5 s deadline')
    axs[0].set_xlabel('frame loss probability')
    axs[0].set_ylabel('mean availability')
    axs[1].set_title('time to recover authentication after teardown')
    axs[1].set_xlabel('frame loss probability')
    axs[1].set_ylabel('median seconds')
    for ax in axs:
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8)
    fig.suptitle('Drone, frame loss sweep (estimated, seed 20261020)')
    fig.tight_layout()
    paths['loss'] = os.path.join(FIG, 'mission_loss_sweep.png')
    fig.savefig(paths['loss'], dpi=120)
    plt.close(fig)
    # 3. envelope at 0.5 s deadline
    env = d['env']
    e = env[(env.deadline_s == 0.5)]
    rows = [(t, v, l) for t in ['base', 'lowrate'] for v in ['drone', 'robot'] for l in model.LINKS
            if len(e[(e.tag == t) & (e.vehicle == v) & (e.link == l)])]
    M = np.array([[e[(e.tag == t) & (e.vehicle == v) & (e.link == l) & (e.arch == a)].avail_mean.iloc[0]
                   for a in model.ARCHS] for t, v, l in rows])
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list('pink', ['#fce4ec', '#f48fb1', '#d63384', '#880e4f'])
    fig, ax = plt.subplots(figsize=(7, 0.45 * len(rows) + 1.5))
    ax.imshow(M, cmap=cmap, vmin=0, vmax=1, aspect='auto')
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            ax.text(j, i, f'{M[i, j]:.3f}', ha='center', va='center', color='white' if M[i, j] > 0.6 else '#880e4f',
                    fontsize=8)
    ax.set_xticks(range(4))
    ax.set_xticklabels(model.ARCHS)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([f'{t} {v} {model.LINK_NAMES[l]}' for t, v, l in rows], fontsize=8)
    ax.set_title('Mean control availability, 0.5 s deadline\n(estimated, seed 20261020, 1000 runs each)', fontsize=9)
    fig.tight_layout()
    paths['envelope'] = os.path.join(FIG, 'mission_envelope.png')
    fig.savefig(paths['envelope'], dpi=120)
    plt.close(fig)
    return paths


# ------------------------------------------------------------------ documents

def _row(df, **kw):
    s = df
    for k, v in kw.items():
        s = s[s[k] == v]
    return s.iloc[0]


def feasible_set(env, tag, vehicle, deadline):
    e = env[(env.tag == tag) & (env.vehicle == vehicle) & (env.deadline_s == deadline) & env.feasible]
    return {(r.link, r.arch) for r in e.itertuples()}


def study_doc(d, paths):
    base, sw, low, env, comp, src, cross, mo, cfg = (d[k] for k in
                                                     ['base', 'sweeps', 'low', 'env', 'comp', 'src', 'cross', 'mo', 'cfg'])
    a = cfg['assumptions']
    L = []
    w = L.append
    w('# Mission Study: Authenticated Command Channel for a Drone and a Ground Robot\n')
    w('Author: Huda Mueen\n')
    w('Status: **estimated**. A seeded discrete event simulation built on published message sizes, published cycle counts, cited link parameters and labelled assumptions. Nothing was measured on a radio or a flight controller and nothing cryptographic was implemented. The link model has only weak validation (Section 8). Generated by `python3 -m mission.run_all`; do not edit by hand.\n')
    w(f"Seed {cfg['seed']}; {cfg['runs']} runs per configuration; availability is reported as the mean over runs and other metrics as the median over runs, each with a bootstrap 95 percent percentile interval (2000 resamples).\n")
    w('## 1. Question\n')
    w('Which of four authentication architectures can keep an authenticated command channel available on four narrow links during a whole mission (preflight, takeoff, cruise, link loss and recovery, landing), and where does each one stop working?\n')
    w('## 2. Architectures\n')
    rows = []
    for arch in model.ARCHS:
        ap = model.arch_profile(arch)
        rows.append(dict(arch=model.ARCH_NAMES[arch], hs=int(model.handshake_bytes(arch)), tag=int(ap['tag_bytes']),
                         extra=int(ap['cmd_extra_bytes']), qs='yes' if ap['quantum_safe'] else 'no'))
    w(md_table(pd.DataFrame(rows), ['arch', 'hs', 'tag', 'extra', 'qs'],
               ['architecture', 'handshake bytes on air', 'tag bytes per message', 'extra bytes per command',
                'resists a future quantum adversary (design intent, not analysed)']))
    w('\nA: handshake flights 32 B, 32 B and 80 B (Ed25519 signature 64 B plus 16 B confirmation), then MAVLink 2 signing. B: flights 1216 B, 1120 B and 2436 B as in `docs/MAVLINK_PQ_SKETCH.md` (ground signs the transcript with ML-DSA-44, the vehicle verifies against a pinned key), then the same 13 B field. C: no session; each command carries a 2420 B ML-DSA-44 signature, carried in file transfer style chunks of 239 B. D: firmware verified at boot with LMS; session keys are provisioned over a wired link before flight and renewed locally, so nothing about keys crosses the radio. Sizes come from `linksim/params.csv` (cited rows).\n')
    w('## 3. Inputs\n')
    w('### 3.1 Traffic\n')
    p = model.load_link_params()
    pl = model.load_payloads()
    tr = model.load_traffic()
    bps = sum(float(r['rate_hz']) * model.mav_frame_bytes(pl[r['message']], p['mav_sig_field_bytes'], p)
              for r in tr if r['vehicle'] == 'drone' and r['direction'] == 'down')
    w('Message payload lengths are host measured from pymavlink 2.4.50 (`mission/payload_lengths.csv`); rates are in `mission/traffic.csv`: HEARTBEAT at 1 Hz is published, the other stream rates are assumptions because the retrieved ArduPilot and PX4 pages do not state defaults (`data/raw/S12_traffic_sources.md`). The drone command probe is SET_POSITION_TARGET_GLOBAL_INT at 1 Hz; the robot probe is SET_POSITION_TARGET_LOCAL_NED at 5 Hz. The PX4 TELEM1 default budget of 1200 B/s (published) is a cross check: '
      + f'the assumed drone downlink with 13 B signing fields is {bps:.0f} B/s (derived), inside that budget.\n')
    w('### 3.2 Compute\n')
    w('Reference board: STM32F405 class flight controller at 168 MHz (Cortex-M4F, the same core family as the pqm4 rows; `data/raw/S5_benchmark_plan_facts.md` line 77). A 480 MHz Cortex-M7 board (Pixhawk 6C, line 75) is a sensitivity case only, because M4 cycle counts do not transfer directly to an M7. Published rows use zero flash wait states; a wait state factor is swept.\n')
    w(md_table(src, ['operation', 'cycles', 'range_min_cycles', 'range_max_cycles', 'label', 'source'],
               ['operation', 'cycles used', 'published range min', 'published range max', 'label', 'source']))
    w('\n')
    w(md_table(comp, ['arch', 'operation', 'cycles', 'ms_at_168MHz', 'ms_at_480MHz', 'label']))
    w('\nClassical rows: X25519 uses S12A-325 (Fujii and Aranha, STM32F401 at 84 MHz), chosen because it is an STM32F4 part with board and clock stated and the highest stated clock among the Cortex-M4 rows; it is counted twice (key generation and shared secret), which is conservative because a fixed base key generation can be faster. Ed25519 verify uses S12A-328 from the same table and board. The published range over all double read rows is shown beside each value (X25519 S12A-317, S12A-321, S12A-325, S12A-332, S12A-333; Ed25519 verify S12A-320, S12A-324, S12A-328, S12A-331). An earlier version of this study used an ECDH secp256r1 proxy for X25519 and a value derived from a time for Ed25519; both are replaced. The largest median compute share in any base configuration is ' + fmt(base.compute_share_median.max(), 4) + ' of the cycle budget.\n')
    w('### 3.3 Assumptions\n')
    keys = ['frame_loss', 'outage_rate_per_h', 'outage_mean_s', 'session_timeout_s', 'rekey_interval_s', 'grace_s',
            'deadline_s', 'mac_cycles', 'wait_state_factor', 'feasible_availability']
    w(md_table(pd.DataFrame([dict(name=k, value=a[k]) for k in keys]), ['name', 'value']))
    w('\nAll are labelled `assumption` in `mission/assumptions.csv` and swept where they matter. Outages are a Poisson process with exponential durations; an outage longer than the session timeout tears the session down and forces a new handshake after the link returns.\n')
    w('## 4. Base results (estimated)\n')
    w('Control availability is the share of commands issued in flight that reach the vehicle authenticated within the deadline (0.5 s), over an unbroken link, with a valid key. Added latency is the median extra delivery time against the same command without authentication (same random draws). Utilisation is the share of air time on the shared channel (SiK, 802.15.4) or the share of the ground transmitter duty cycle budget (LoRaWAN; above 1 means overloaded). Compute share is vehicle cycles spent on authentication over the mission divided by available cycles at 168 MHz. Time to recover is from link return to a new valid session after a teardown (A and B only).\n')
    for veh in ['drone', 'robot']:
        w(f'### 4.{1 if veh == "drone" else 2} {veh.capitalize()}\n')
        b = base[base.vehicle == veh].copy()
        b['Link'] = b.link.map(model.LINK_NAMES)
        b['availability'] = b.apply(lambda r: cim(r), axis=1)
        b['unauthenticated'] = b['avail_base_mean_0.5'].map(lambda x: fmt(x, 4))
        b['added ms'] = b.apply(lambda r: ci(r, 'added_latency_ms', 2), axis=1)
        b['utilisation'] = b.apply(lambda r: ci(r, 'utilisation'), axis=1)
        b['compute share'] = b.apply(lambda r: ci(r, 'compute_share', 4), axis=1)
        b['recover s'] = b.apply(lambda r: ci(r, 'ttra_s', 2), axis=1)
        b['first session s'] = b.apply(lambda r: ci(r, 'first_session_s', 1), axis=1)
        w(md_table(b, ['Link', 'arch', 'availability', 'unauthenticated', 'added ms', 'utilisation', 'compute share',
                       'recover s', 'first session s']))
        w('\n' + LABEL + '\n')
    w('"unauthenticated" is the mean availability of the same command stream with no authentication bytes or compute, which isolates the share lost to the link itself. n/a means no run produced a value (for example no teardown, or no delivered command).\n')
    w(f"![Availability against deadline](figures/mission/{os.path.basename(paths['deadline'])})\n")
    w('_Figure 1. Drone, mean availability against deadline. Estimated, seed 20261020, base assumptions, 1000 runs per point._\n')
    # sweeps
    w('## 5. Sensitivity (estimated)\n')
    w('One factor at a time around the base, drone, links SiK, 802.15.4 and LoRaWAN DR5, 1000 runs per point. Values are mean availability at the 0.5 s deadline.\n')
    for par in study.SWEEPS:
        s = sw[sw.tag == 'sweep:' + par].copy()
        if not len(s):
            continue
        s['val'] = s['over_' + par]
        piv = s.pivot_table(index=['link', 'val'], columns='arch', values='avail_mean').reset_index()
        piv['link'] = piv.link.map(model.LINK_NAMES)
        cols = ['link', 'val'] + [c for c in model.ARCHS if c in piv]
        w(f'### {par}\n')
        w(f"Base value {a.get(par, 'n/a')}.\n")
        w(md_table(piv, cols, ['link', par] + cols[2:]))
        if par in ('frame_loss', 'outage_mean_s', 'rekey_interval_s'):
            t = s[s.arch.isin(['A', 'B'])].pivot_table(index=['link', 'val'], columns='arch',
                                                        values='ttra_s_median').reset_index()
            t['link'] = t.link.map(model.LINK_NAMES)
            w('\nMedian time to recover authentication after a teardown (s):\n')
            w(md_table(t, ['link', 'val'] + [c for c in ['A', 'B'] if c in t], ['link', par] +
                       [c for c in ['A', 'B'] if c in t]))
        if par in ('clock_hz', 'wait_state_factor', 'mac_cycles'):
            t = s.pivot_table(index=['link', 'val'], columns='arch', values='compute_share_median').reset_index()
            t['link'] = t.link.map(model.LINK_NAMES)
            w('\nMedian compute share:\n')
            w(md_table(t, ['link', 'val'] + model.ARCHS, ['link', par] + model.ARCHS))
        w('\n' + LABEL + '\n')
    w(f"![Loss sweep](figures/mission/{os.path.basename(paths['loss'])})\n")
    w('_Figure 2. Drone, frame loss sweep: availability on SiK (left) and recovery time after teardown (right). Estimated, seed 20261020._\n')
    w('### Morris screening\n')
    w(f"Elementary effects (SALib Morris, {int(mo.trajectories.iloc[0])} trajectories, 4 levels, {int(mo.runs_per_point.iloc[0])} runs per point, seed 20261020) on mean availability, drone on SiK. Inputs and ranges: frame loss 0 to 0.2, outage rate 0 to 30 per hour, outage mean 1 to 30 s, rekey interval 60 to 1800 s, tag cycles 2000 to 50000, wait state factor 1 to 1.5, deadline 0.1 to 2 s.\n")
    w(md_table(mo.sort_values(['arch', 'mu_star'], ascending=[True, False]),
               ['arch', 'input', 'mu_star', 'sigma', 'mu_star_conf']))
    w('\n' + LABEL + '\n')
    # rekey interplay
    w('## 6. Rekey and link loss interplay\n')
    rk = sw[(sw.tag == 'sweep:rekey_interval_s') & (sw.link == 'sik')]
    w('A rekey that is interrupted by an outage keeps the old key for the grace period; if the transfer does not finish within it, commands are refused until it does. A long outage tears the session down regardless of rekeying. Handshakes per run and runs with at least one teardown (drone, SiK):\n')
    t = pd.concat([rk, base[(base.vehicle == 'drone') & (base.link == 'sik') & base.arch.isin(['A', 'B'])].assign(
        over_rekey_interval_s=a['rekey_interval_s'])])
    w(md_table(t.sort_values(['arch', 'over_rekey_interval_s']),
               ['arch', 'over_rekey_interval_s', 'handshakes_per_run_mean', 'share_runs_with_teardown', 'avail_mean'],
               ['arch', 'rekey interval s', 'handshakes per run', 'share of runs with a teardown', 'mean availability']))
    w('\n' + LABEL + '\n')
    spread = t.groupby('arch').avail_mean.agg(lambda v: v.max() - v.min())
    w(f"Null result: across rekey intervals from 60 s to once per arming, mean availability changes by at most {fmt(spread.max(), 4)} (A {fmt(spread.get('A'), 4)}, B {fmt(spread.get('B'), 4)}), while the number of handshakes per mission changes by an order of magnitude. With a {a['grace_s']:g} s grace period, rekeying and link loss do not interact strongly in this model; teardowns from outages longer than the {a['session_timeout_s']:g} s session timeout dominate.\n")
    # low rate
    w('## 7. Design envelope\n')
    w(f"Feasible means mean availability at least {a['feasible_availability']} and utilisation at most 1 (assumption). Base traffic profile:\n")
    e = env[env.tag == 'base']
    for veh in ['drone', 'robot']:
        piv = e[e.vehicle == veh].pivot_table(index=['link', 'arch'], columns='deadline_s', values='reason',
                                              aggfunc='first').reset_index()
        piv['link'] = piv.link.map(model.LINK_NAMES)
        dcols = [c for c in piv.columns if c not in ('link', 'arch')]
        w(f'**{veh}**\n')
        w(md_table(piv, ['link', 'arch'] + dcols, ['link', 'arch'] + [f'{c:g} s' for c in dcols]))
        w('\n')
    w('Low rate profile (one command per 60 s, telemetry off), drone, to show what LoRaWAN can carry at all:\n')
    lw = low.copy()
    lw['Link'] = lw.link.map(model.LINK_NAMES)
    lw['availability 5 s'] = lw['avail_mean_5'].map(fmt)
    lw['availability 10 s'] = lw['avail_mean_10'].map(fmt)
    lw['utilisation'] = lw.apply(lambda r: ci(r, 'utilisation'), axis=1)
    lw['first session s'] = lw.apply(lambda r: ci(r, 'first_session_s', 1), axis=1)
    w(md_table(lw, ['Link', 'arch', 'availability 5 s', 'availability 10 s', 'utilisation', 'first session s']))
    w('\n' + LABEL + '\n')
    w(f"![Envelope](figures/mission/{os.path.basename(paths['envelope'])})\n")
    w('_Figure 3. Mean availability at the 0.5 s deadline for every configuration. Estimated, seed 20261020, 1000 runs each._\n')
    # validation
    w('## 8. Validation and limits\n')
    w('There is no measured mission, radio trace or flight controller timing to calibrate against, so no calibration and validation split was possible; this is a null result for validation and is stated as such. The only check is a model to model comparison of the no loss handshake time of the mission transfer model against the earlier `linksim` table (`docs/LINK_REFERENCE_DESIGN.md` section 7.2, provisioned key variant). Both are estimates built from the same cited link parameters, so agreement shows consistency, not accuracy.\n')
    w(md_table(cross, ['link', 'mission_model_s', 'linksim_selective_repeat_s', 'relative_difference', 'label']))
    w('\nThe difference arises because this model acknowledges each flight once, while `linksim` acknowledges every 16 fragments. Further limits:\n')
    w('- Loss is independent per frame; real loss is bursty. Outages are Poisson with exponential durations; both rates are assumptions.\n- LoRaWAN PHY and MAC overhead is ignored (understates air time) and class A receive windows are not modelled; the 1 percent duty cycle is applied per transmitter.\n- The robot uses MAVLink framing; ROS 2 DDS Security per message overhead could not be verified (`data/raw/S12_traffic_sources.md`).\n- X25519 and Ed25519 cycles come from Cortex-M4 boards at 84 MHz or less and are applied at 168 MHz with the wait state factor; the per message tag cost (10000 cycles) has no published row and is swept.\n- Ground station compute is ignored. One vehicle, one ground station, no contention from other users of the band.\n- Security properties are design intent; nothing was analysed formally.\n- The software in the loop step was skipped: no Docker daemon is available and building a PX4 or ArduPilot simulator from source did not fit the 30 minute time box on this two core host, so message counts come from the traffic table, not from a simulator.\n')
    w('## 9. Reproduction\n')
    w('```\n/home/claude/work/venv_mav/bin/python mission/measure_payloads.py   # optional, needs pymavlink outside the repository\npython3 -m mission.run_all\npython3 -m unittest discover -s mission/tests -t .\n```\n')
    return '\n'.join(L)


def recommend(d):
    """Derive the recommendation statements from the envelope; returns a dict of facts used in the text."""
    env, base, sw, low = d['env'], d['base'], d['sweeps'], d['low']
    f = {}
    for veh in ['drone', 'robot']:
        f[veh] = feasible_set(env, 'base', veh, 0.5)
    f['low'] = feasible_set(env, 'lowrate', 'drone', 5.0)
    fl = sw[(sw.tag == 'sweep:frame_loss')]
    f['loss_B_fail'] = {}
    for link in ['sik', 'ieee802154']:
        s = fl[(fl.link == link) & (fl.arch == 'B')].sort_values('over_frame_loss')
        bad = s[s.avail_mean < d['cfg']['assumptions']['feasible_availability']]
        f['loss_B_fail'][link] = float(bad.over_frame_loss.iloc[0]) if len(bad) else None
    return f


def arch_doc(d, paths):
    base, sw, low, env, comp, cfg = (d[k] for k in ['base', 'sweeps', 'low', 'env', 'comp', 'cfg'])
    a = cfg['assumptions']
    f = recommend(d)
    L = []
    w = L.append
    w('# Reference Architecture: Post Quantum Command Authentication for a Drone and a Ground Robot\n')
    w('Author: Huda Mueen\n')
    w('Status: **design level, estimated**. Every figure below is read from `mission/results/` (seed 20261020, 1000 runs per configuration) and is an estimate from published sizes and cycle counts, cited link parameters and labelled assumptions. The link model has only weak validation (a model to model check, `docs/MISSION_STUDY.md` section 8). Nothing cryptographic is implemented. Generated by `python3 -m mission.run_all`.\n')
    w('## 1. Recommendation\n')
    w('A layered design:\n')
    w('1. **Boot:** firmware signed with LMS and verified by the bootloader (the firmware half of architecture D). Verification costs ' +
      fmt(_row(comp, arch='D', operation='boot verify').ms_at_168MHz, 1) + ' ms at 168 MHz (derived from published cycles) and uses no radio time.\n')
    w('2. **Session start on links of SiK class or faster:** hybrid key establishment X25519 plus ML-KEM-768 with an ML-DSA-44 transcript signature from the ground station, verified against a pinned key (architecture B), then the existing 13 B MAVLink 2 signing field on every message.\n')
    w('3. **Provisioned session keys as the fallback** (the session half of D) for links where the B handshake cannot finish in preflight (LoRaWAN class links, where only low rate command traffic is possible at all), and as the recovery path when establishing a new session would take longer than the vehicle safety case allows.\n')
    w('4. **No per command ML-DSA-44 signatures on streamed commands** (architecture C). They remain an option for rare, high value commands such as a mission upload, where seconds of delay are acceptable.\n')
    checks = [
        ('B feasible on SiK and IEEE 802.15.4 for drone and robot at 0.5 s',
         all((l, 'B') in f[v] for v in ['drone', 'robot'] for l in ['sik', 'ieee802154'])),
        ('D feasible wherever B is feasible', all((l, 'D') in f[v] for v in ['drone', 'robot'] for l, a_ in f[v] if a_ == 'B')),
        ('C infeasible for the 5 Hz robot stream on every link', not any(a_ == 'C' for _, a_ in f['robot'])),
        ('B not feasible on any LoRaWAN link in the low rate profile', not any(a_ == 'B' and l.startswith('lora') for l, a_ in f['low'])),
        ('D within 0.005 of the unauthenticated stream on LoRaWAN DR5 in the low rate profile',
         abs(_row(low, link='lora_dr5', arch='D')['avail_mean_5'] - _row(low, link='lora_dr5', arch='D')['avail_base_mean_5']) < 0.005),
    ]
    w('Checks of this recommendation against the result files (computed by `mission/run_all.py`):\n')
    for text, ok in checks:
        w(f"- {text}: {'holds' if ok else 'DOES NOT HOLD; revise the recommendation'}")
    w('\n')
    w('## 2. Evidence for the recommendation (estimated)\n')
    rows = []
    for veh in ['drone', 'robot']:
        for link in ['sik', 'ieee802154', 'lora_dr5']:
            for arch in model.ARCHS:
                r = _row(base, vehicle=veh, link=link, arch=arch)
                rows.append(dict(vehicle=veh, link=model.LINK_NAMES[link], arch=arch, avail=cim(r),
                                 added=ci(r, 'added_latency_ms', 2), util=fmt(r.utilisation_median),
                                 comp=fmt(r.compute_share_median, 4), rec=fmt(r.ttra_s_median, 2),
                                 feas='yes' if (r.link, arch) in f[veh] else 'no'))
    w(md_table(pd.DataFrame(rows), ['vehicle', 'link', 'arch', 'avail', 'added', 'util', 'comp', 'rec', 'feas'],
               ['vehicle', 'link', 'arch', 'mean availability at 0.5 s [95% CI]', 'added latency ms [95% CI]',
                'utilisation', 'compute share', 'recovery s after teardown', 'feasible']))
    w('\n' + LABEL + '\n')
    def names(s, veh):
        return ', '.join(sorted(f'{a} on {model.LINK_NAMES[l]}' for l, a in s)) or 'none'
    w(f"Feasible at the 0.5 s deadline (base assumptions): drone: {names(f['drone'], 'drone')}; robot: {names(f['robot'], 'robot')}. Low rate profile (one command per minute, 5 s deadline, drone): {names(f['low'], 'drone')}.\n")
    bS = _row(base, vehicle='drone', link='sik', arch='B')
    aS = _row(base, vehicle='drone', link='sik', arch='A')
    cS = _row(base, vehicle='drone', link='sik', arch='C')
    cR = _row(base, vehicle='robot', link='sik', arch='C')
    bD5 = _row(low, link='lora_dr5', arch='B')
    w('## 3. Quantified trade offs (estimated)\n')
    w(f"- **B against A on SiK (drone):** availability {cim(bS)} against {cim(aS)}; the per message cost is identical (same 13 B field), so the difference is only the session start: first session after {fmt(bS.first_session_s_median, 2)} s against {fmt(aS.first_session_s_median, 2)} s, and recovery after a teardown {fmt(bS.ttra_s_median, 2)} s against {fmt(aS.ttra_s_median, 2)} s. Handshake air bytes 4772 against 144.\n")
    w(f"- **C on SiK:** added latency {ci(cS, 'added_latency_ms', 1)} ms per command and availability {cim(cS)} for the 1 Hz drone stream; for the 5 Hz robot stream utilisation reaches {fmt(cR.utilisation_median)} and availability {cim(cR)}.\n")
    lora_base = base[base.link.str.startswith('lora')]
    p = model.load_link_params()
    dr0 = model.link_profile('lora_dr0', p)
    a_dr0, _ = model.command_frames('drone', 'A', dr0, p=p)
    w(f"- **LoRaWAN:** under the 1 percent duty cycle the base command streams are not carried by any architecture: the highest mean availability on either LoRaWAN link is {fmt(lora_base.avail_mean.max(), 4)}, and the same stream without authentication reaches at most {fmt(lora_base['avail_base_mean_0.5'].max(), 4)}, so the link, not the authentication, rules it out. In the low rate profile (one command per minute, 5 s deadline) the B handshake on DR5 needs a median {fmt(bD5.first_session_s_median, 1)} s against a 60 s preflight; feasible there: {names(f['low'], 'drone')}. On DR0 one signed setpoint needs {len(a_dr0)} link frames, and each frame is followed by the duty cycle silence.\n")
    cmp_rows = comp.copy()
    abd = base[base.arch.isin(['A', 'B', 'D'])]
    w('- **Compute:** the largest median compute share of A, B and D in any base configuration is ' + fmt(abd.compute_share_median.max(), 4) + ' of the 168 MHz cycle budget; C costs ' +
      fmt(_row(comp, arch='C', operation='per command check').ms_at_168MHz, 2) + ' ms of verification per command (derived from published cycles), which matters only at high command rates.\n')
    w('\n' + md_table(cmp_rows, ['arch', 'operation', 'cycles', 'ms_at_168MHz', 'ms_at_480MHz', 'label']) + '\n')
    w('## 4. Conditions under which the recommendation changes\n')
    lb = f['loss_B_fail']
    thr = d['cfg']['assumptions']['feasible_availability']
    for link, v in lb.items():
        if v is None:
            w(f"- Frame loss on {model.LINK_NAMES[link]}: B stays at or above the {thr} threshold up to the highest swept frame loss ({max(study.SWEEPS['frame_loss']):g}), because retransmissions fit inside the 0.5 s deadline; frame loss does not change the recommendation in the swept range (a null result). C, by contrast, drops to {fmt(_row(sw[sw.tag == 'sweep:frame_loss'], link=link, arch='C', over_frame_loss=max(study.SWEEPS['frame_loss'])).avail_mean, 4)} at that loss.")
        else:
            w(f"- Frame loss on {model.LINK_NAMES[link]}: B falls below the {thr} threshold at a frame loss of {v:g}.")
        w('\n')
    orr = sw[(sw.tag == 'sweep:outage_rate_per_h') & (sw.link == 'sik')]
    for rate in sorted(orr.over_outage_rate_per_h.unique()):
        x = orr[orr.over_outage_rate_per_h == rate].set_index('arch').avail_mean
        if all(x[a_] < thr for a_ in ['A', 'B', 'D']):
            w(f"- Link loss events: at {rate:g} outages per hour (mean 5 s) A, B and D all fall below the threshold on SiK (A {fmt(x['A'], 4)}, B {fmt(x['B'], 4)}, D {fmt(x['D'], 4)}). The three differ by at most {fmt(max(x[a_] for a_ in 'ABD') - min(x[a_] for a_ in 'ABD'), 4)}, so at this rate the link, not the choice of authentication, sets availability and the recommendation does not change; the remedy is a more reliable link, not a different scheme.\n")
            break
    rk = sw[(sw.tag == 'sweep:rekey_interval_s') & (sw.link == 'sik')]
    if len(rk):
        span = rk.groupby('arch').avail_mean.agg(lambda v: v.max() - v.min())
        w(f"- Rekey interval (60 s to once per arming): the spread of mean availability across the swept intervals is {fmt(span.get('A', float('nan')), 4)} for A and {fmt(span.get('B', float('nan')), 4)} for B on SiK, comparable to the run to run noise; in this model the rekey interval does not change the recommendation (a null result), because the old key stays valid for the {d['cfg']['assumptions']['grace_s']:g} s grace period while a rekey is in progress.\n")
    lw = d['low']
    dD = _row(lw, link='lora_dr5', arch='D')
    dA = _row(lw, link='lora_dr5', arch='A')
    w(f"- LoRaWAN DR5, low rate profile: D reaches a mean availability of {fmt(dD['avail_mean_5'], 4)} and A {fmt(dA['avail_mean_5'], 4)} at a 5 s deadline, against {fmt(dD['avail_base_mean_5'], 4)} for the same stream without authentication, so authentication costs almost nothing there, but the link itself stays below the {thr} threshold (a lost frame waits out the duty cycle silence before it can be sent again). B reaches {fmt(_row(lw, link='lora_dr5', arch='B')['avail_mean_5'], 4)} because its handshake does not finish within the mission.\n")
    w('- If the link cannot complete the B handshake inside preflight (LoRaWAN class links in this study), use provisioned keys (D) and accept the key management burden: keys must be loaded over a wire before each mission and a captured vehicle exposes them until they expire.\n')
    fl = sw[(sw.tag == 'sweep:frame_loss') & (sw.link == 'sik') & (sw.arch == 'B')].sort_values('over_frame_loss')
    w(f"- If the safety case requires renewed authentication within a bound shorter than the B recovery time after a teardown (median {fmt(fl.ttra_s_median.iloc[0], 2)} s at no frame loss and {fmt(fl.ttra_s_median.iloc[-1], 2)} s at a frame loss of {fl.over_frame_loss.iloc[-1]:g} on SiK), keep the session alive through outages (longer session timeout) or fall back to D keys.\n")
    c_low = sorted(model.LINK_NAMES[l] for l, a_ in f['low'] if a_ == 'C')
    w(f"- If command streams are rare (one per minute in the low rate profile) and each command is high value, C is feasible on: {', '.join(c_low) or 'no link'} at a 5 s deadline, because its per command delay no longer competes with a stream.\n")
    ck = sw[(sw.tag == 'sweep:clock_hz') & (sw.link == 'sik')]
    if len(ck):
        w(f"- If the flight controller is a Cortex-M7 at 480 MHz (sensitivity case; M4 cycles are not directly comparable to M7), the largest median compute share on SiK becomes {fmt(ck.compute_share_median.max(), 4)}; compute is not the limiting resource in any configuration studied.\n")
    cs = d['src'].set_index('operation')
    lo_a = cs.loc['x25519_two_mults', 'range_min_cycles'] + cs.loc['ed25519_verify', 'range_min_cycles']
    hi_a = cs.loc['x25519_two_mults', 'range_max_cycles'] + cs.loc['ed25519_verify', 'range_max_cycles']
    w(f"- Across the published range of X25519 and Ed25519 rows, the A handshake compute spans {fmt(lo_a / a['clock_hz'] * 1e3, 1)} to {fmt(hi_a / a['clock_hz'] * 1e3, 1)} ms at 168 MHz (derived from published); compute is not the limiting resource at either end, so the choice of row does not change any verdict.\n")
    w('## 5. Components and interfaces (design level)\n')
    w('| component | role | where it runs |\n|---|---|---|\n| LMS verifier in the bootloader | verifies the firmware image before start | flight controller or robot MCU |\n| Pinned ML-DSA-44 ground key | authenticates the ground station during session start | vehicle, provisioned over a wire |\n| Hybrid key establishment (X25519 plus ML-KEM-768) | derives a 32 B signing key per session | ground station and vehicle (or a companion computer gateway) |\n| MAVLink 2 signing (13 B field, 6 B tag) | per message authentication | unchanged on both sides |\n| Provisioned key store | fallback session keys, rotated locally | vehicle |\n| Link supervisor | session timeout, rekey timing, fallback decision | vehicle |\n')
    w('## 6. Limits\n')
    w('- Estimated throughout; no radio, flight controller or cryptographic library was run. The link model is only checked against another model.\n- Assumed traffic rates, outage process, timeouts and deadlines drive the verdicts; they are swept, but real values for a given vehicle may lie outside the swept ranges.\n- No formal security analysis of the handshake or of the fallback logic. Specialists in protocol security would need to review any real design.\n- Draft and standards status: ML-KEM (FIPS 203) and ML-DSA (FIPS 204) are final; MAVLink has no post quantum extension and the sketch in `docs/MAVLINK_PQ_SKETCH.md` is not a proposal to any project.\n')
    return '\n'.join(L)


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if '--reuse' not in argv:
        study.main()
    else:
        # cheap deterministic tables are always regenerated from the current inputs
        comp, src = study.compute_latency_table()
        comp.to_csv(os.path.join(RES, 'compute_latency.csv'), index=False)
        src.to_csv(os.path.join(RES, 'cycle_sources.csv'), index=False)
        study.link_crosscheck().to_csv(os.path.join(RES, 'link_crosscheck.csv'), index=False)
    d = load()
    paths = figures(d)
    with open(DOC_STUDY, 'w') as f:
        f.write(study_doc(d, paths))
    with open(DOC_ARCH, 'w') as f:
        f.write(arch_doc(d, paths))
    print('wrote', DOC_STUDY, DOC_ARCH)


if __name__ == '__main__':
    main()
