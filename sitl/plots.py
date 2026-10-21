"""SVG figures of the software in the loop study (one per configuration, plus two overview figures)."""
import os

import matplotlib
matplotlib.rcParams['svg.hashsalt'] = 'sitl'
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from . import config as cfgmod  # noqa: E402

COLORS = {'none': '#7a6f8f', 'signing': '#d98cb3', 'hybrid': '#b0476f', 'pqsig': '#4f6d8f'}
SHORT = {'none': '1 none', 'signing': '2 signing', 'hybrid': '3 hybrid', 'pqsig': '4 ML-DSA-44'}


def _style(ax):
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(alpha=0.3)


def latency_cdf(c, profile, res, deadline):
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    for k in cfgmod.CONFIGS:
        g = c[(c.profile == profile) & (c.config == k) & (~c.in_outage) & c.acked]
        if len(g) == 0:
            continue
        x = np.sort(g.rt_s.values * 1e3)
        ax.step(x, np.arange(1, len(x) + 1) / len(x), where='post', color=COLORS[k], label=SHORT[k])
    ax.axvline(deadline * 1e3, color='k', ls='--', lw=1, label=f'deadline {deadline:g} s')
    ax.set_xscale('log')
    ax.set_xlabel('command to COMMAND_ACK round trip, ms (log scale)')
    ax.set_ylabel('share of acknowledged commands')
    ax.set_title(f'SITL measured, {cfgmod.PROFILE_NAMES[profile]}, link up')
    _style(ax)
    ax.legend(fontsize=8, frameon=False)
    fig.tight_layout()
    fig.savefig(os.path.join(res, f'fig_latency_cdf_{profile}.svg'), metadata={'Date': None})
    plt.close(fig)


def availability(comp, profile, res):
    d = comp[(comp.profile == profile) & (comp.metric.isin(['availability_rt_link_up', 'availability_ow_link_up']))]
    if len(d) == 0:
        return
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    ks = [k for k in cfgmod.CONFIGS if k in set(d.config)]
    x = np.arange(len(ks))
    for j, (metric, lab, hatch) in enumerate([('availability_rt_link_up', 'SITL measured (ACK round trip)', ''),
                                             ('availability_ow_link_up', 'emulated (one way to vehicle)', '//')]):
        dd = d[d.metric == metric].set_index('config').reindex(ks)
        err = np.vstack([dd.value - dd.ci_lo, dd.ci_hi - dd.value])
        ax.bar(x + (j - 1) * 0.27, dd.value, 0.27, yerr=err, color=[COLORS[k] for k in ks], hatch=hatch,
               edgecolor='k', lw=0.5, label=lab, capsize=2)
    st = d[d.metric == 'availability_ow_link_up'].set_index('config').reindex(ks)
    ax.bar(x + 0.27, st.study_estimated, 0.27, color='white', edgecolor='k', lw=0.8, label='mission study (estimated)')
    ax.set_xticks(x)
    ax.set_xticklabels([SHORT[k] for k in ks])
    ax.set_ylabel('commands within 0.5 s, link up')
    ax.set_ylim(0, 1.05)
    ax.set_title(f'Availability, {cfgmod.PROFILE_NAMES[profile]}')
    _style(ax)
    ax.legend(fontsize=7, frameon=False, loc='lower left')
    fig.tight_layout()
    fig.savefig(os.path.join(res, f'fig_availability_{profile}.svg'), metadata={'Date': None})
    plt.close(fig)


def timeline(c, m, profile, config, res, deadline):
    g = c[(c.profile == profile) & (c.config == config)]
    mm = m[(m.profile == profile) & (m.config == config)]
    if len(g) == 0 or len(mm) == 0:
        return
    # the mission with the longest outage shows recovery most clearly
    r = mm.loc[mm.outage_duration_s.idxmax()]
    gg = g[g.mission == r['mission']]
    t0 = r['t_arm']
    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    ax.axvspan(r['o_s'] - t0, r['o_e'] - t0, color='#f3c6d8', alpha=0.7, label='link outage')
    ok = gg[gg.acked & (gg.result == 0)]
    ax.plot(ok.t_send - t0, ok.rt_s * 1e3, 'o', ms=3, color=COLORS[config], label='acknowledged command')
    lost = gg[~(gg.acked & (gg.result == 0))]
    ax.plot(lost.t_send - t0, np.full(len(lost), deadline * 1e3 * 1.8), 'x', color='k', ms=4,
            label='not acknowledged')
    ax.axhline(deadline * 1e3, color='k', ls='--', lw=1)
    ax.set_yscale('log')
    ax.set_xlabel('time after arming, s')
    ax.set_ylabel('round trip, ms (log scale)')
    ax.set_title(f'{SHORT[config]}, {cfgmod.PROFILE_NAMES[profile]}, mission {int(r["mission"])} (SITL measured)')
    _style(ax)
    ax.legend(fontsize=7, frameon=False, loc='upper left')
    fig.tight_layout()
    fig.savefig(os.path.join(res, f'fig_timeline_{profile}_{config}.svg'), metadata={'Date': None})
    plt.close(fig)


def make_all(c, m, summ, comp, res, deadline):
    for p in cfgmod.PROFILES:
        if len(c[c.profile == p]) == 0:
            continue
        latency_cdf(c, p, res, deadline)
        if len(comp):
            availability(comp, p, res)
        for k in cfgmod.CONFIGS:
            timeline(c, m, p, k, res, deadline)
