"""Fit, validate and apply the cycle models; write every result CSV under cyclemodel/results/.

Run after cyclemodel/trace_all.py. All random steps use seed 20261020.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cyclemodel import model as M  # noqa: E402

RES = M.RES


def load():
    tr = pd.read_csv(os.path.join(RES, 'traces.csv'))
    agg = M.aggregate_traces(tr)
    pub = M.published_pqm4()
    pq = agg[agg['source'] == 'pqm4']
    rows = pub.merge(pq, on=['parameter_set', 'implementation', 'operation'], how='left')
    return tr, agg, rows


def build_split(rows):
    binaries = sorted({(r.parameter_set, r.implementation) for r in rows.itertuples()})
    split = M.make_split(binaries)
    rows = rows.copy()
    rows['half'] = [split[(r.parameter_set, r.implementation)] for r in rows.itertuples()]
    out = [dict(label='assumption', id=r.id, parameter_set=r.parameter_set, implementation=r.implementation,
                operation=r.operation, binary=f'{r.parameter_set} {r.implementation}', half=r.half, seed=M.SEED)
           for r in rows.sort_values(['half', 'parameter_set', 'implementation', 'operation']).itertuples()]
    M.write_csv(os.path.join(RES, 'split.csv'), out)
    return rows


def evaluate(rows):
    X = rows[M.FEATURE_NAMES].to_numpy(float)
    y = rows['cycles'].to_numpy(float)
    tr = (rows['half'] == 'train').to_numpy()
    c_fit = M.fit_nnls(X[tr], y[tr])
    G = M.reduced_matrix()
    c_red4 = M.fit_nnls(X[tr] @ G, y[tr])
    c_red = G @ c_red4
    c_ap = np.array([M.A_PRIORI[f] for f in M.FEATURE_NAMES])
    rows = rows.copy()
    rows['cycles_modelled_baseline'] = rows['instructions']
    rows['cycles_modelled_apriori'] = M.predict(X, c_ap)
    rows['cycles_modelled_fitted'] = M.predict(X, c_fit)
    rows['cycles_modelled_reduced'] = M.predict(X, c_red)
    for m in ('baseline', 'apriori', 'fitted', 'reduced'):
        rows[f'err_pct_{m}'] = M.pct_error(rows[f'cycles_modelled_{m}'], y)
    rows['family'] = rows['keccak_share'].map(M.family_of)
    rows['impl_kind'] = np.where(rows['implementation'].map(M.is_assembly), 'assembly (m4f variants)', 'clean C')
    costs = [dict(label='modelled', feature=f, classes='+'.join(M.FEATURES[f]), cost_fitted_cycles=float(c),
                  cost_apriori_cycles_assumption=M.A_PRIORI[f], apriori_status='unverified (TRM fetch refused)')
             for f, c in zip(M.FEATURE_NAMES, c_fit)]
    costs += [dict(label='modelled', feature=f'reduced: {k}', classes='+'.join(v), cost_fitted_cycles=float(c),
                   cost_apriori_cycles_assumption='', apriori_status='reduced model, no a priori value')
              for (k, v), c in zip(M.REDUCED.items(), c_red4)]
    M.write_csv(os.path.join(RES, 'fitted_costs.csv'), costs)
    out = []
    for r in rows.sort_values(['scheme', 'parameter_set', 'implementation', 'operation']).itertuples():
        out.append(dict(label='modelled', id=r.id, parameter_set=r.parameter_set, implementation=r.implementation,
                        operation=r.operation, half=r.half, family=r.family, impl_kind=r.impl_kind,
                        keccak_share_emulated=r.keccak_share, n_runs_emulated=r.n_runs,
                        instructions_emulated=r.instructions, cycles_published=r.cycles,
                        cycles_modelled_baseline=r.cycles_modelled_baseline,
                        cycles_modelled_apriori=r.cycles_modelled_apriori, cycles_modelled_fitted=r.cycles_modelled_fitted,
                        err_pct_baseline=r.err_pct_baseline, err_pct_apriori=r.err_pct_apriori,
                        err_pct_fitted=r.err_pct_fitted, cycles_modelled_reduced=r.cycles_modelled_reduced,
                        err_pct_reduced=r.err_pct_reduced))
    M.write_csv(os.path.join(RES, 'matched_rows.csv'), out)
    rows.attrs['X_train'] = X[tr]
    return rows, c_fit, c_ap, c_red


def summaries(rows):
    out = []
    subsets = [('test, all', rows['half'] == 'test'),
               ('test, excluding sign', (rows['half'] == 'test') & (rows['operation'] != 'sign')),
               ('train, all', rows['half'] == 'train'),
               ('all rows', rows['half'].notna())]
    for fam in ('NTT heavy', 'hash heavy'):
        subsets.append((f'test, {fam}', (rows['half'] == 'test') & (rows['family'] == fam)))
    for k in ('clean C', 'assembly (m4f variants)'):
        subsets.append((f'test, {k}', (rows['half'] == 'test') & (rows['impl_kind'] == k)))
    for op in ('keygen', 'encaps', 'decaps', 'sign', 'verify'):
        subsets.append((f'test, {op}', (rows['half'] == 'test') & (rows['operation'] == op)))
    for model in ('fitted', 'reduced', 'apriori', 'baseline'):
        for name, mask in subsets:
            e = rows.loc[mask, f'err_pct_{model}']
            s = M.summarise(e)
            out.append(dict(label='modelled', model=model, subset=name, seed=M.SEED, n_boot=M.N_BOOT, **s))
    M.write_csv(os.path.join(RES, 'error_summary.csv'), out)
    return pd.DataFrame(out)


def sign_variability(tr, c_fit):
    t = tr[(tr['operation'] == 'sign')].copy()
    for f, cols in M.FEATURES.items():
        t[f] = t[cols].sum(axis=1)
    t['cycles_modelled_fitted'] = t[M.FEATURE_NAMES].to_numpy(float) @ c_fit
    out = []
    for (src, ps, impl), g in t.groupby(['source', 'parameter_set', 'implementation']):
        v = g['cycles_modelled_fitted'].to_numpy()
        out.append(dict(label='modelled', source=src, parameter_set=ps, implementation=impl, n_messages=len(v),
                        instructions_mean_emulated=float(g['instructions'].mean()),
                        instructions_min_emulated=int(g['instructions'].min()),
                        instructions_max_emulated=int(g['instructions'].max()),
                        cycles_modelled_mean=float(v.mean()), cycles_modelled_sd=float(v.std(ddof=1)),
                        cycles_modelled_min=float(v.min()), cycles_modelled_max=float(v.max()),
                        cv_pct=float(v.std(ddof=1) / v.mean() * 100)))
    M.write_csv(os.path.join(RES, 'sign_variability.csv'), out)


def external_check(c_fit, c_ap, test_err):
    p = os.path.join(RES, 'traces_external.csv')
    ev = pd.read_csv(os.path.join(M.REPO, 'data', 'evidence.csv'))
    s10 = ev[ev['id'].astype(str).str.startswith('S10C') & ev['cycles'].notna()]
    out = []
    if not os.path.exists(p):
        M.write_csv(os.path.join(RES, 'external_check.csv'), [dict(label='modelled', note='no external traces')])
        return
    tr = pd.read_csv(p)
    agg = M.aggregate_traces(tr)
    for r in agg.itertuples():
        x = np.array([getattr(r, f) for f in M.FEATURE_NAMES], float)
        pred = float(x @ c_fit)
        lo, hi = M.prediction_interval(pred, test_err)
        rows = s10[(s10['library'] == 'pqcrystals-lowram') & (s10['parameter_set'] == r.parameter_set)
                   & (s10['operation'] == 'keygen')].sort_values('id')
        stats = ['minimum', 'average', 'worst observed']
        for (_, pr), st in zip(rows.iterrows(), stats):
            out.append(dict(label='modelled', id=pr['id'], parameter_set=r.parameter_set, operation='keygen (key expansion from seed)',
                            statistic_published=st, core_published='Cortex-M33 (STM32U5A5, 160 MHz, caches on)',
                            core_modelled='Cortex-M4 (model fitted on pqm4 rows)', n_seeds_emulated=r.n_runs,
                            instructions_mean_emulated=r.instructions, cycles_published=float(pr['cycles']),
                            cycles_modelled_fitted=pred, cycles_modelled_apriori=float(x @ c_ap),
                            pi95_lo_modelled=lo, pi95_hi_modelled=hi,
                            err_pct_fitted=float(M.pct_error(pred, pr['cycles'])),
                            inside_pi95=bool(lo <= pr['cycles'] <= hi)))
    M.write_csv(os.path.join(RES, 'external_check.csv'), out)


def board_predictions(agg, c_fit, test_err, c_red, test_err_red, X_train):
    sel = []
    h = agg[agg['source'] == 'bench_mcu_harness']
    sel.extend(h.itertuples())
    b0 = agg[(agg['source'] == 'pqm4') & (((agg['parameter_set'] == 'ML-KEM-768') & agg['implementation'].isin(['clean', 'm4fspeed']))
                                          | ((agg['parameter_set'] == 'ML-DSA-44') & agg['implementation'].isin(['clean', 'm4f'])))]
    sel.extend(b0.itertuples())
    out = []
    for r in sel:
        x = np.array([getattr(r, f) for f in M.FEATURE_NAMES], float)
        pred = float(x @ c_fit)
        lo, hi = M.prediction_interval(pred, test_err)
        pr = float(x @ c_red)
        lo_r, hi_r = M.prediction_interval(pr, test_err_red)
        flags = M.extrapolation_flags(x, X_train)
        target = 'harness (bench/mcu)' if r.source == 'bench_mcu_harness' else 'pqm4 B0'
        out.append(dict(label='modelled', target=target, parameter_set=r.parameter_set, implementation=r.implementation,
                        operation=r.operation, board='Cortex-M4 at zero flash wait states (no cache, no contention)',
                        cycles_modelled=round(pred), pi95_lo_modelled=round(lo), pi95_hi_modelled=round(hi),
                        cycles_modelled_reduced=round(pr), pi95_lo_modelled_reduced=round(lo_r), pi95_hi_modelled_reduced=round(hi_r),
                        pi95_envelope_lo_modelled=round(min(lo, lo_r)), pi95_envelope_hi_modelled=round(max(hi, hi_r)),
                        cycles_modelled_baseline=round(r.instructions),
                        extrapolation_flags=';'.join(flags) if flags else 'none',
                        n_runs_emulated=r.n_runs, instructions_mean_emulated=r.instructions,
                        instructions_sd_emulated=r.instructions_sd, keccak_share_emulated=r.keccak_share,
                        model='fitted NNLS, seed 20261020', toolchain='arm-none-eabi-gcc 13.2.1 20231009'))
    M.write_csv(os.path.join(RES, 'board_predictions.csv'), out)
    return out


def main():
    tr, agg, rows = load()
    missing = rows['instructions'].isna().sum()
    if missing:
        raise SystemExit(f'{missing} published rows have no trace')
    rows = build_split(rows)
    rows, c_fit, c_ap, c_red = evaluate(rows)
    summaries(rows)
    test_err = rows.loc[rows['half'] == 'test', 'err_pct_fitted'].to_numpy()
    sign_variability(tr, c_fit)
    external_check(c_fit, c_ap, test_err)
    test_err_red = rows.loc[rows['half'] == 'test', 'err_pct_reduced'].to_numpy()
    board_predictions(agg, c_fit, test_err, c_red, test_err_red, rows.attrs['X_train'])
    print('analysis written to', RES)


if __name__ == '__main__':
    main()
