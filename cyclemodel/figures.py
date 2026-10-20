"""Figures for the cycle model (label: modelled; validation error shown; seed 20261020).

Colours: #ad1457 (train) and #ec407a (test), checked for colour vision deficiency separation and contrast
against a white plot area; train and test also differ by marker shape, so colour is never the only cue.
"""
import os
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cyclemodel import model as M  # noqa: E402

FIG = os.path.join(M.HERE, '..', 'docs', 'figures', 'cyclemodel')
TRAIN, TEST, INK, GRID = '#ad1457', '#ec407a', '#3d0a24', '#f8bbd0'


def _style(ax):
    ax.set_facecolor('white')
    ax.grid(True, color=GRID, linewidth=0.6)
    for s in ('top', 'right'):
        ax.spines[s].set_visible(False)
    for s in ('left', 'bottom'):
        ax.spines[s].set_color(INK)
    ax.tick_params(colors=INK)


def predicted_vs_published(rows, summ):
    fig, ax = plt.subplots(figsize=(7, 6), facecolor='#fce4ec')
    _style(ax)
    for half, col, mk in (('train', TRAIN, 'o'), ('test', TEST, '^')):
        r = rows[rows['half'] == half]
        ax.scatter(r['cycles_published'], r['cycles_modelled_fitted'], s=46, color=col, marker=mk,
                   edgecolor='white', linewidth=1.0, label=f'{half} half (n={len(r)})', zorder=3)
    lo = min(rows['cycles_published'].min(), rows['cycles_modelled_fitted'].min()) * 0.8
    hi = max(rows['cycles_published'].max(), rows['cycles_modelled_fitted'].max()) * 1.25
    ax.plot([lo, hi], [lo, hi], color=INK, linewidth=1.0, linestyle='--', label='equal', zorder=2)
    ax.set_xscale('log')
    ax.set_yscale('log')
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)
    ax.set_xlabel('published pqm4 cycles (Cortex-M4, published)', color=INK)
    ax.set_ylabel('predicted cycles, fitted model (modelled)', color=INK)
    s = summ[(summ['model'] == 'fitted') & (summ['subset'] == 'test, all')].iloc[0]
    ax.set_title('Predicted against published cycles, pqm4 ML-KEM and ML-DSA\n'
                 f'modelled; validation error shown; seed {M.SEED}\n'
                 f'held out median |error| {s.median_abs_pct:.1f} percent '
                 f'(95% CI {s.median_abs_ci_lo:.1f} to {s.median_abs_ci_hi:.1f}), worst {s.worst_abs_pct:.1f} percent',
                 color=INK, fontsize=9)
    ax.legend(frameon=False, labelcolor=INK)
    fig.tight_layout()
    p = os.path.join(FIG, 'predicted_vs_published.png')
    fig.savefig(p, dpi=150)
    plt.close(fig)
    return p


def error_by_family(rows):
    fig, ax = plt.subplots(figsize=(8, 4.8), facecolor='#fce4ec')
    _style(ax)
    groups = [('NTT heavy', 'clean C'), ('NTT heavy', 'assembly (m4f variants)'),
              ('hash heavy', 'clean C'), ('hash heavy', 'assembly (m4f variants)')]
    labels = []
    for i, (fam, kind) in enumerate(groups):
        for half, col, mk, dx in (('train', TRAIN, 'o', -0.12), ('test', TEST, '^', 0.12)):
            r = rows[(rows['family'] == fam) & (rows['impl_kind'] == kind) & (rows['half'] == half)]
            jitter = np.linspace(-0.05, 0.05, max(len(r), 1))[:len(r)]
            ax.scatter(i + dx + jitter, r['err_pct_fitted'], color=col, marker=mk, s=40, edgecolor='white',
                       linewidth=1.0, label=f'{half} half' if i == 0 else None, zorder=3)
        n = len(rows[(rows['family'] == fam) & (rows['impl_kind'] == kind)])
        labels.append(f'{fam}\n{kind}\n(n={n})')
    ax.axhline(0, color=INK, linewidth=1.0)
    ax.set_xticks(range(len(groups)))
    ax.set_xticklabels(labels, fontsize=8, color=INK)
    ax.set_ylabel('percent error, fitted model (modelled)', color=INK)
    ax.set_title('Error of the fitted model by operation family and implementation kind\n'
                 f'modelled; validation error shown; family from traced Keccak share (>= 0.5 is hash heavy); seed {M.SEED}',
                 color=INK, fontsize=9)
    ax.legend(frameon=False, labelcolor=INK)
    fig.tight_layout()
    p = os.path.join(FIG, 'error_by_family.png')
    fig.savefig(p, dpi=150)
    plt.close(fig)
    return p


def main():
    os.makedirs(FIG, exist_ok=True)
    rows = pd.read_csv(os.path.join(M.RES, 'matched_rows.csv'))
    summ = pd.read_csv(os.path.join(M.RES, 'error_summary.csv'))
    print(predicted_vs_published(rows, summ))
    print(error_by_family(rows))


if __name__ == '__main__':
    main()
