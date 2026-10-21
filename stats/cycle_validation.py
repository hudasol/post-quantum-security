#!/usr/bin/env python3
"""Added validation of the round 4 cycle model (no change to the fitted model).

Inputs (all committed): cyclemodel/results/traces.csv (emulated class counts), cyclemodel/results/split.csv
(round 4 binary split, seed 20261020), data/evidence.csv (published pqm4 rows), cyclemodel/model.py (features,
NNLS fit, error and interval helpers).

Analyses (label of every result: modelled)
1. Reproduction. The round 4 fitted and reduced models are refitted on the round 4 training half exactly as in
   cyclemodel/analyse.py; the held out errors must equal cyclemodel/results/matched_rows.csv.
2. Cluster bootstrap. The held out errors are resampled by binary (parameter set and implementation): each
   resample draws binaries with replacement and keeps all rows of a drawn binary together. 10000 resamples,
   seed 20261021. For every subset of cyclemodel/results/error_summary.csv the 95 percent interval of the median
   absolute and the median signed error is reported, together with the interval of the 2.5 and 97.5 percentiles
   of the held out errors, which are the bounds of the prediction interval of cyclemodel/model.py.
3. Leave one group out. The model is refitted on all matched rows outside one group and predicts the rows of the
   group: leave one implementation family out (clean, m4f, m4fspeed, m4fstack as the pqm4 binaries define them),
   leave one parameter set out, leave one scheme out, and leave one binary out. Median and worst absolute error
   per left out group, for the full (12 feature) and the reduced (4 feature) model.
4. Board predictions with a cluster aware prediction interval: the round 4 point predictions with the outer
   limits of the cluster bootstrap intervals of the two error percentiles as a wider interval.
5. Harness check. Whether published cycle rows exist for exactly the mlkem-native and mldsa-native harness code.

Writes stats/results/cycle_cluster_bootstrap.csv, cycle_lofo.csv, cycle_lofo_summary.csv,
cycle_board_predictions_cluster.csv, cycle_harness_check.csv and cycle_config.csv.
"""
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from cyclemodel import model as M  # noqa: E402

SEED = 20261021
N_BOOT = 10000
OUT = os.path.join(ROOT, 'stats', 'results')
ROUND4_ROW_CI = (0.669738, 1.72035)  # read again from error_summary.csv in main(); kept for the test


def load_rows():
    tr = pd.read_csv(os.path.join(M.RES, 'traces.csv'))
    agg = M.aggregate_traces(tr)
    pub = M.published_pqm4()
    rows = pub.merge(agg[agg['source'] == 'pqm4'], on=['parameter_set', 'implementation', 'operation'], how='left')
    split = pd.read_csv(os.path.join(M.RES, 'split.csv'))[['id', 'half']]
    rows = rows.merge(split, on='id', how='left')
    if rows['half'].isna().any() or rows['instructions'].isna().any():
        raise SystemExit('matched rows without split or trace')
    rows['binary'] = rows['parameter_set'] + ' ' + rows['implementation']
    rows['family'] = rows['keccak_share'].map(M.family_of)
    rows['impl_kind'] = np.where(rows['implementation'].map(M.is_assembly), 'assembly (m4f variants)', 'clean C')
    return agg, rows.sort_values('id').reset_index(drop=True)


def fit_both(X, y):
    G = M.reduced_matrix()
    return M.fit_nnls(X, y), G @ M.fit_nnls(X @ G, y)


def round4_errors(rows):
    X = rows[M.FEATURE_NAMES].to_numpy(float)
    y = rows['cycles'].to_numpy(float)
    tr = (rows['half'] == 'train').to_numpy()
    c_fit, c_red = fit_both(X[tr], y[tr])
    out = rows.copy()
    out['err_pct_fitted'] = M.pct_error(X @ c_fit, y)
    out['err_pct_reduced'] = M.pct_error(X @ c_red, y)
    return out, c_fit, c_red, X[tr]


def subsets(rows):
    t = rows['half'] == 'test'
    s = [('test, all', t), ('test, excluding sign', t & (rows['operation'] != 'sign')), ('train, all', rows['half'] == 'train')]
    for fam in ('NTT heavy', 'hash heavy'):
        s.append((f'test, {fam}', t & (rows['family'] == fam)))
    for k in ('clean C', 'assembly (m4f variants)'):
        s.append((f'test, {k}', t & (rows['impl_kind'] == k)))
    for op in ('keygen', 'encaps', 'decaps', 'sign', 'verify'):
        s.append((f'test, {op}', t & (rows['operation'] == op)))
    return s


def cluster_bootstrap(errors, clusters, n=N_BOOT, seed=SEED):
    """Resample clusters with replacement; return arrays of statistics per resample.
    Statistics: median absolute, median signed, 2.5 and 97.5 percentiles of the errors."""
    e = np.asarray(errors, float)
    cl = np.asarray(clusters)
    labels = sorted(set(cl))
    members = [np.flatnonzero(cl == c) for c in labels]
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(labels), size=(n, len(labels)))
    res = np.empty((n, 4))
    for i, d in enumerate(draws):
        v = e[np.concatenate([members[j] for j in d])]
        res[i] = (np.median(np.abs(v)), np.median(v), np.percentile(v, 2.5), np.percentile(v, 97.5))
    return res


def row_bootstrap(errors, n=N_BOOT, seed=SEED):
    e = np.asarray(errors, float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(e), size=(n, len(e)))
    v = e[idx]
    return np.column_stack([np.median(np.abs(v), axis=1), np.median(v, axis=1),
                            np.percentile(v, 2.5, axis=1), np.percentile(v, 97.5, axis=1)])


def ci(a):
    return float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5))


def bootstrap_table(rows):
    out = []
    for model in ('fitted', 'reduced'):
        for name, mask in subsets(rows):
            sub = rows[mask]
            e = sub[f'err_pct_{model}'].to_numpy()
            cb = cluster_bootstrap(e, sub['binary'].to_numpy())
            rb = row_bootstrap(e)
            r = dict(label='modelled', model=model, subset=name, n_rows=len(e), n_binaries=sub['binary'].nunique(),
                     seed=SEED, n_boot=N_BOOT, median_abs_pct=float(np.median(np.abs(e))),
                     median_signed_pct=float(np.median(e)), worst_abs_pct=float(np.abs(e).max()),
                     err_p025_pct=float(np.percentile(e, 2.5)), err_p975_pct=float(np.percentile(e, 97.5)))
            for tag, b in (('cluster', cb), ('row', rb)):
                r[f'median_abs_{tag}_ci_lo'], r[f'median_abs_{tag}_ci_hi'] = ci(b[:, 0])
                r[f'median_signed_{tag}_ci_lo'], r[f'median_signed_{tag}_ci_hi'] = ci(b[:, 1])
                r[f'err_p025_{tag}_ci_lo'], r[f'err_p025_{tag}_ci_hi'] = ci(b[:, 2])
                r[f'err_p975_{tag}_ci_lo'], r[f'err_p975_{tag}_ci_hi'] = ci(b[:, 3])
            out.append(r)
    return pd.DataFrame(out)


LOFO_KEYS = {'implementation family': 'implementation', 'parameter set': 'parameter_set', 'scheme': 'scheme',
             'binary': 'binary'}


def lofo(rows):
    X = rows[M.FEATURE_NAMES].to_numpy(float)
    y = rows['cycles'].to_numpy(float)
    per_row, summ = [], []
    for kind, col in LOFO_KEYS.items():
        for g in sorted(rows[col].unique()):
            held = (rows[col] == g).to_numpy()
            c_fit, c_red = fit_both(X[~held], y[~held])
            for model, c in (('fitted', c_fit), ('reduced', c_red)):
                e = M.pct_error(X[held] @ c, y[held])
                sub = rows[held]
                for (_, r), ev in zip(sub.iterrows(), e):
                    per_row.append(dict(label='modelled', left_out_by=kind, group=g, model=model, id=r['id'],
                                        binary=r['binary'], operation=r['operation'], cycles_published=r['cycles'],
                                        cycles_modelled=float(X[held][list(sub.index).index(r.name)] @ c),
                                        err_pct=float(ev), seed=SEED))
                ns = (sub['operation'] != 'sign').to_numpy()
                a = np.abs(e)
                summ.append(dict(label='modelled', left_out_by=kind, group=g, model=model, n_rows=int(held.sum()),
                                 n_train_rows=int((~held).sum()), median_abs_pct=float(np.median(a)),
                                 worst_abs_pct=float(a.max()), median_signed_pct=float(np.median(e)),
                                 median_abs_excl_sign_pct=float(np.median(a[ns])) if ns.any() else float('nan'),
                                 worst_abs_excl_sign_pct=float(a[ns].max()) if ns.any() else float('nan')))
    return pd.DataFrame(per_row), pd.DataFrame(summ)


def lofo_pooled(per_row):
    """Pooled error over all rows for each leave out scheme (each row predicted once without its group)."""
    out = []
    for (kind, model), g in per_row.groupby(['left_out_by', 'model']):
        e = g['err_pct'].to_numpy()
        ns = (g['operation'] != 'sign').to_numpy()
        cb = cluster_bootstrap(e, g['binary'].to_numpy())
        lo, hi = ci(cb[:, 0])
        out.append(dict(label='modelled', left_out_by=kind, group='all groups pooled', model=model, n_rows=len(e),
                        n_train_rows=float('nan'), median_abs_pct=float(np.median(np.abs(e))),
                        worst_abs_pct=float(np.abs(e).max()), median_signed_pct=float(np.median(e)),
                        median_abs_excl_sign_pct=float(np.median(np.abs(e[ns]))),
                        worst_abs_excl_sign_pct=float(np.abs(e[ns]).max()),
                        median_abs_cluster_ci_lo=lo, median_abs_cluster_ci_hi=hi,
                        err_p025_pct=float(np.percentile(e, 2.5)), err_p975_pct=float(np.percentile(e, 97.5))))
    return pd.DataFrame(out)


def board_cluster(boot):
    """Round 4 board predictions with the point prediction interval and a cluster aware wider interval."""
    bp = pd.read_csv(os.path.join(M.RES, 'board_predictions.csv'))
    r = boot[(boot['model'] == 'fitted') & (boot['subset'] == 'test, all')].iloc[0]
    q_lo, q_hi = r['err_p025_pct'] / 100, r['err_p975_pct'] / 100
    w_lo, w_hi = r['err_p025_cluster_ci_lo'] / 100, r['err_p975_cluster_ci_hi'] / 100
    out = []
    for _, b in bp.iterrows():
        p = float(b['cycles_modelled'])
        out.append(dict(label='modelled', target=b['target'], parameter_set=b['parameter_set'],
                        implementation=b['implementation'], operation=b['operation'], cycles_modelled=round(p),
                        pi95_lo_round4=int(b['pi95_lo_modelled']), pi95_hi_round4=int(b['pi95_hi_modelled']),
                        pi95_lo_recomputed=round(p / (1 + q_hi)), pi95_hi_recomputed=round(p / (1 + q_lo)),
                        pi95_lo_cluster_outer=round(p / (1 + w_hi)), pi95_hi_cluster_outer=round(p / (1 + w_lo)),
                        width_ratio_cluster_to_round4=(p / (1 + w_lo) - p / (1 + w_hi))
                        / (float(b['pi95_hi_modelled']) - float(b['pi95_lo_modelled'])),
                        extrapolation_flags=b['extrapolation_flags'], seed=SEED))
    return pd.DataFrame(out)


def harness_check():
    ev = pd.read_csv(os.path.join(ROOT, 'data', 'evidence.csv'))
    pat = 'mlkem-native|mldsa-native|PQ Code Package|mlkem_native|mldsa_native'
    hit = ev[ev.apply(lambda r: r.astype(str).str.contains(pat, case=False).any(), axis=1)]
    m4 = hit[hit['core'].astype(str).str.contains('M4', case=False) & hit['cycles'].notna()]
    rows = [dict(label='published', id=r['id'], core=r['core'], library=r['library'], parameter_set=r['parameter_set'],
                 operation=r['operation'], cycles=r['cycles'], usable_for_harness_test=False,
                 reason='different core and build (not the bench/mcu harness at -O2 on a Cortex-M4)')
            for _, r in hit.iterrows()]
    verdict = ('possible' if len(m4) else 'not possible: no published cycle row for the mlkem-native or mldsa-native '
               'harness code on a Cortex-M4; the test waits for the board')
    rows.append(dict(label='published', id='summary', core='', library='', parameter_set='', operation='', cycles='',
                     usable_for_harness_test=bool(len(m4)), reason=verdict))
    return pd.DataFrame(rows), verdict, len(hit)


def main():
    os.makedirs(OUT, exist_ok=True)
    agg, rows = load_rows()
    rows, c_fit, c_red, _ = round4_errors(rows)
    mr = pd.read_csv(os.path.join(M.RES, 'matched_rows.csv'))[['id', 'err_pct_fitted', 'err_pct_reduced']]
    chk = rows.merge(mr, on='id', suffixes=('', '_r4'))
    dev = float(max((chk['err_pct_fitted'] - chk['err_pct_fitted_r4']).abs().max(),
                    (chk['err_pct_reduced'] - chk['err_pct_reduced_r4']).abs().max()))
    if dev > 1e-3:
        raise SystemExit(f'round 4 errors not reproduced (max difference {dev})')
    boot = bootstrap_table(rows)
    es = pd.read_csv(os.path.join(M.RES, 'error_summary.csv'))
    r4 = es.set_index(['model', 'subset'])
    boot['median_abs_round4_row_ci_lo'] = [r4.loc[(m, s), 'median_abs_ci_lo'] for m, s in zip(boot.model, boot.subset)]
    boot['median_abs_round4_row_ci_hi'] = [r4.loc[(m, s), 'median_abs_ci_hi'] for m, s in zip(boot.model, boot.subset)]
    boot.to_csv(os.path.join(OUT, 'cycle_cluster_bootstrap.csv'), index=False, float_format='%.6g')
    per_row, summ = lofo(rows)
    summ = pd.concat([summ, lofo_pooled(per_row)], ignore_index=True)
    per_row.to_csv(os.path.join(OUT, 'cycle_lofo.csv'), index=False, float_format='%.6g')
    summ.to_csv(os.path.join(OUT, 'cycle_lofo_summary.csv'), index=False, float_format='%.6g')
    board_cluster(boot).to_csv(os.path.join(OUT, 'cycle_board_predictions_cluster.csv'), index=False, float_format='%.6g')
    hc, verdict, n_hit = harness_check()
    hc.to_csv(os.path.join(OUT, 'cycle_harness_check.csv'), index=False)
    cfg = [('seed', SEED), ('n_boot', N_BOOT), ('cluster', 'binary (parameter set and implementation)'),
           ('round4_reproduction_max_abs_difference_pct', f'{dev:.3g}'), ('round4_seed', M.SEED),
           ('harness_rows_found', n_hit), ('harness_verdict', verdict),
           ('lofo_training', 'all matched rows outside the left out group (both round 4 halves)')]
    pd.DataFrame([dict(label='assumption', key=k, value=v) for k, v in cfg]).to_csv(
        os.path.join(OUT, 'cycle_config.csv'), index=False)
    t = boot[(boot.model == 'fitted') & (boot.subset == 'test, all')].iloc[0]
    print(f"test, all: median abs {t.median_abs_pct:.2f}; cluster CI {t.median_abs_cluster_ci_lo:.2f} to "
          f"{t.median_abs_cluster_ci_hi:.2f}; row CI {t.median_abs_row_ci_lo:.2f} to {t.median_abs_row_ci_hi:.2f}")
    print(summ[summ.model == 'fitted'][['left_out_by', 'group', 'n_rows', 'median_abs_pct', 'worst_abs_pct',
                                        'median_abs_excl_sign_pct']].to_string())
    print(verdict)


if __name__ == '__main__':
    main()
