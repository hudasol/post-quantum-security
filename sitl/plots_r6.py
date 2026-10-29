"""SVG figures of the round 6 software in the loop study (deterministic: fixed hash salt, no date)."""
import os

import matplotlib
matplotlib.rcParams['svg.hashsalt'] = 'sitl_r6'
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from . import config_r6 as c6  # noqa: E402

COLORS = {'none': '#7a6f8f', 'signing': '#d98cb3', 'classical': '#8f9fb8', 'hybrid_published': '#b0476f',
          'hybrid_strict': '#7d2a4c', 'hybrid_cache': '#e7a1bf', 'pqsig_real': '#4f6d8f',
          'kem_auth': '#c9a227', 'hybrid_strict_inband': '#c46a8a', 'pqsig_counter': '#8fb0cf'}


def _style(ax):
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(alpha=0.3)


def _save(fig, path):
    fig.tight_layout()
    fig.savefig(path, metadata={'Date': None})
    plt.close(fig)


def availability(summ, comp, profile, res):
    d = summ[(summ.profile == profile) & (summ.metric == 'availability_rt_all')].set_index('config')
    ks = [k for k in c6.CONFIGS if k in d.index]
    if not ks:
        return
    d = d.reindex(ks)
    fig, ax = plt.subplots(figsize=(7.2, 3.9))
    x = np.arange(len(ks))
    ax.bar(x, d.value, 0.6, yerr=np.vstack([d.value - d.ci_lo, d.ci_hi - d.value]), capsize=3,
           color=[COLORS[k] for k in ks], edgecolor='k', lw=0.5, label='SITL measured [95% CI]')
    if comp is not None and len(comp):
        cm = comp[(comp.profile == profile) & comp.quantity.str.startswith('share')].set_index('config').reindex(ks)
        ax.scatter(x, cm.mission_model_estimated, marker='D', color='white', edgecolor='k', zorder=3,
                   label='mission model, same rule (estimated)')
    ax.set_xticks(x)
    ax.set_xticklabels([c6.SHORT[k] for k in ks], rotation=20, fontsize=8)
    ax.set_ylabel('commands acknowledged within 0.5 s\n(outages included)')
    lo = float(np.nanmin(d.ci_lo)) if len(d) else 0
    ax.set_ylim(max(0.0, lo - 0.1), 1.0)
    ax.set_title(f'{c6.cfgmod.PROFILE_NAMES[profile]}, executed cryptography')
    _style(ax)
    ax.legend(fontsize=7, frameon=False, loc='lower left')
    _save(fig, os.path.join(res, f'fig_r6_availability_{profile}.svg'))


def latency_cdf(c, profile, res, deadline):
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    n = 0
    for k in c6.CONFIGS:
        g = c[(c.profile == profile) & (c.config == k) & (~c.in_outage) & c.acked]
        if len(g) == 0:
            continue
        x = np.sort(g.rt_s.values * 1e3)
        ax.step(x, np.arange(1, len(x) + 1) / len(x), where='post', color=COLORS[k], label=c6.SHORT[k])
        n += 1
    if not n:
        plt.close(fig)
        return
    ax.axvline(deadline * 1e3, color='k', ls='--', lw=1, label=f'deadline {deadline:g} s')
    ax.set_xscale('log')
    ax.set_xlabel('command to COMMAND_ACK round trip, ms (log scale)')
    ax.set_ylabel('share of acknowledged commands')
    ax.set_title(f'SITL measured, {c6.cfgmod.PROFILE_NAMES[profile]}, link up')
    _style(ax)
    ax.legend(fontsize=7, frameon=False)
    _save(fig, os.path.join(res, f'fig_r6_latency_cdf_{profile}.svg'))


def paired(pr, profile, res):
    if len(pr) == 0:
        return
    d = pr[pr.profile == profile]
    if len(d) == 0:
        return
    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    y = np.arange(len(d))[::-1]
    ax.errorbar(d.difference, y, xerr=np.vstack([d.difference - d.ci_lo, d.ci_hi - d.difference]), fmt='o',
                color='#b0476f', ecolor='k', capsize=3)
    ax.axvline(0, color='k', lw=0.8)
    ax.set_yticks(y)
    ax.set_yticklabels([f'{c6.SHORT[a]} minus {c6.SHORT[b]}' for a, b in zip(d.config, d.minus_config)], fontsize=8)
    ax.set_xlabel('paired difference of the share acknowledged within 0.5 s')
    ax.set_title(f'SITL measured, paired by mission, {c6.cfgmod.PROFILE_NAMES[profile]}')
    _style(ax)
    _save(fig, os.path.join(res, f'fig_r6_paired_{profile}.svg'))


def handshakes(m, profile, res):
    ks = [k for k in c6.CONFIGS if k in c6.SESSION]
    d = m[(m.profile == profile) & m.config.isin(ks)]
    if len(d) == 0:
        return
    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    for i, k in enumerate(ks):
        v = d[d.config == k].handshake_s.dropna().values
        ax.scatter(np.full(len(v), i) + np.linspace(-0.15, 0.15, len(v)) if len(v) else [], v, s=12, color=COLORS[k])
    ax.set_xticks(range(len(ks)))
    ax.set_xticklabels([c6.SHORT[k] for k in ks], fontsize=8)
    ax.set_ylabel('handshake time per mission, s')
    ax.set_title(f'Emulated link, executed cryptography, {c6.cfgmod.PROFILE_NAMES[profile]}')
    _style(ax)
    _save(fig, os.path.join(res, f'fig_r6_handshake_{profile}.svg'))


def all_figures(c, summ, pr, m, res, deadline):
    import pandas as pd
    cp = os.path.join(res, 'comparison.csv')
    comp = pd.read_csv(cp) if os.path.exists(cp) else None
    for p in c6.PROFILES:
        availability(summ, comp, p, res)
        latency_cdf(c, p, res, deadline)
        paired(pr, p, res)
        handshakes(m, p, res)
