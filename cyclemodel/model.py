"""Timing models on top of the traced instruction class counts.

Inputs
* cyclemodel/results/traces.csv and traces_external.csv (emulated instruction class counts).
* data/evidence.csv: published pqm4 rows (S2-*) for ML-KEM and ML-DSA, and the ePrint 2026/1333 rows (S10C-*).

Models (label of every predicted value: modelled)
* baseline: cycles = instructions (one cycle per instruction).
* a priori: per class costs written in A_PRIORI below. The Arm Cortex-M4 Technical Reference Manual could
  not be retrieved (fetch refused), so every cost there is an assumption marked unverified.
* fitted: non negative least squares on a seeded half of the matched published rows, with each row scaled
  by 1/published so that the fit minimises relative error.

Errors are percent errors (predicted minus published, divided by published). Intervals are bootstrap 95
percent intervals over rows (10000 resamples, seed 20261020).
"""
import csv
import os
import re

import numpy as np
import pandas as pd
from scipy.optimize import nnls

SEED = 20261020
N_BOOT = 10000
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RES = os.path.join(HERE, 'results')

# Feature groups built from the tracer classes
FEATURES = {
    'single_issue': ['alu', 'it', 'other'],
    'mul_mac': ['mul', 'mac'],
    'div': ['div'],
    'load': ['load'],
    'store': ['store'],
    'dual_extra': ['dual_extra'],
    'ldm_stm_insn': ['ldm_insn', 'stm_insn'],
    'ldm_stm_regs': ['ldm_regs', 'stm_regs'],
    'branch_taken': ['branch_uncond', 'branch_cond_taken'],
    'pc_write': ['pc_write'],
    'branch_not_taken': ['branch_cond_not_taken'],
    'fpu': ['fpu_move', 'fpu_ldst', 'fpu_arith'],
}
FEATURE_NAMES = list(FEATURES)

# Reduced feature set (sensitivity check, fixed before seeing test errors of the full set would be the
# ideal; it was added after the full fit showed physically implausible costs, which is stated in the doc).
REDUCED = {
    'alu_like': ['single_issue', 'div', 'fpu', 'branch_not_taken'],
    'mul_mac': ['mul_mac'],
    'memory': ['load', 'store', 'dual_extra', 'ldm_stm_insn', 'ldm_stm_regs'],
    'taken_branch': ['branch_taken', 'pc_write'],
}

# A priori per feature costs in cycles. UNVERIFIED: the Cortex-M4 TRM instruction timing page could not
# be retrieved on 2026-10-20 (fetch refused), so these are assumptions of the author, not sourced values.
A_PRIORI = {
    'single_issue': 1.0,   # one cycle data processing; IT counted as one cycle (often folded on the core)
    'mul_mac': 1.0,        # single cycle 32 bit multiply and multiply accumulate assumed
    'div': 7.0,            # divide is data dependent; middle of an assumed 2 to 12 cycle range
    'load': 2.0,           # single load, no pipelining with neighbours assumed
    'store': 1.0,          # single store, write buffer assumed
    'dual_extra': 1.0,     # second word of LDRD or STRD
    'ldm_stm_insn': 1.0,   # load or store multiple: one plus one per register
    'ldm_stm_regs': 1.0,
    'branch_taken': 3.0,   # one plus an assumed pipeline refill of two
    'pc_write': 2.0,       # refill after POP {pc}, LDR pc or MOV pc (instruction itself counted in its class)
    'branch_not_taken': 1.0,
    'fpu': 1.0,            # FPU register moves and single precision operations
}


def implementation_of(library):
    s = str(library)
    for key in ('m4fspeed', 'm4fstack', 'm4f', 'clean'):
        if f"'{key}" in s:
            return key
    return None


def published_pqm4(evidence_path=None):
    """Matched published pqm4 rows for ML-KEM and ML-DSA with their implementation variant."""
    d = pd.read_csv(evidence_path or os.path.join(REPO, 'data', 'evidence.csv'))
    m = d[d['library'].astype(str).str.startswith('pqm4 implementation') & d['scheme'].isin(['ML-KEM', 'ML-DSA'])
          & d['cycles'].notna()].copy()
    m['implementation'] = m['library'].map(implementation_of)
    m = m[m['implementation'].notna()]
    return m[['id', 'scheme', 'parameter_set', 'implementation', 'operation', 'cycles', 'compiler_flags_or_notes']]


def aggregate_traces(traces):
    """Mean, standard deviation, min and max of the class counts per (source, set, implementation, operation)."""
    t = traces.copy()
    for f, cols in FEATURES.items():
        t[f] = t[cols].sum(axis=1)
    keys = ['source', 'parameter_set', 'implementation', 'operation']
    g = t.groupby(keys)
    out = g[FEATURE_NAMES + ['instructions', 'keccak_instructions']].mean()
    out['n_runs'] = g.size()
    out['instructions_sd'] = g['instructions'].std(ddof=1).fillna(0.0)
    out['instructions_min'] = g['instructions'].min()
    out['instructions_max'] = g['instructions'].max()
    out['keccak_share'] = out['keccak_instructions'] / out['instructions']
    return out.reset_index()


def family_of(keccak_share):
    """Operation family from the traced share of instructions inside Keccak functions."""
    return 'hash heavy' if keccak_share >= 0.5 else 'NTT heavy'


def make_split(binaries, seed=SEED):
    """Binary level split. Strata are (scheme, implementation kind); each stratum has three parameter sets.
    Strata take two or one binaries for training in a seeded order so that train and test have nine each.
    Returns dict binary -> 'train' or 'test'. No binary appears in both halves."""
    rng = np.random.default_rng(seed)
    strata = {}
    for b in sorted(binaries):
        strata.setdefault((b[0].split('-')[0] + '-' + b[0].split('-')[1], b[1]), []).append(b)
    keys = sorted(strata)
    order = rng.permutation(len(keys))
    n_train_total = len(binaries) // 2
    take = {}
    for rank, i in enumerate(order):
        take[keys[i]] = 2 if rank % 2 == 0 else 1
    # adjust so totals match exactly
    while sum(take.values()) > n_train_total:
        for k in keys:
            if take[k] == 2 and sum(take.values()) > n_train_total:
                take[k] = 1
    split = {}
    for k in keys:
        members = strata[k]
        perm = rng.permutation(len(members))
        for j, idx in enumerate(perm):
            split[members[idx]] = 'train' if j < take[k] else 'test'
    return split


def reduced_matrix():
    """Matrix G (12 x 4) with X_reduced = X @ G; a reduced cost vector c4 maps back as G @ c4."""
    G = np.zeros((len(FEATURE_NAMES), len(REDUCED)))
    for j, (_, members) in enumerate(REDUCED.items()):
        for f in members:
            G[FEATURE_NAMES.index(f), j] = 1.0
    return G


def extrapolation_flags(x, X_train, names=None):
    """Features whose share of the feature total in x lies outside the range seen in the training rows."""
    names = names or FEATURE_NAMES
    x = np.asarray(x, float)
    Xt = np.asarray(X_train, float)
    share = x / x.sum()
    st = Xt / Xt.sum(axis=1, keepdims=True)
    lo, hi = st.min(axis=0), st.max(axis=0)
    return [n for n, s, a, b in zip(names, share, lo, hi) if s < a - 1e-12 or s > b + 1e-12]


def predict(X, costs):
    return X @ np.asarray(costs, dtype=float)


def fit_nnls(X, y):
    """Non negative least squares on relative residuals: minimise sum ((X c - y) / y)^2 with c >= 0."""
    w = 1.0 / y
    c, _ = nnls(X * w[:, None], np.ones_like(y))
    return c


def pct_error(pred, pub):
    return (np.asarray(pred, float) - np.asarray(pub, float)) / np.asarray(pub, float) * 100.0


def bootstrap_ci(values, stat, n=N_BOOT, seed=SEED):
    v = np.asarray(values, float)
    if len(v) == 0:
        return (float('nan'), float('nan'))
    if len(v) == 1:
        return (float(v[0]), float(v[0]))
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(v), size=(n, len(v)))
    s = np.array([stat(v[i]) for i in idx])
    return (float(np.percentile(s, 2.5)), float(np.percentile(s, 97.5)))


def summarise(errors):
    """Median absolute, worst absolute and median signed percent error with bootstrap intervals."""
    e = np.asarray(errors, float)
    a = np.abs(e)
    lo1, hi1 = bootstrap_ci(a, np.median)
    lo2, hi2 = bootstrap_ci(e, np.median)
    return dict(n=len(e), median_abs_pct=float(np.median(a)) if len(e) else float('nan'), median_abs_ci_lo=lo1,
                median_abs_ci_hi=hi1, worst_abs_pct=float(a.max()) if len(e) else float('nan'),
                median_signed_pct=float(np.median(e)) if len(e) else float('nan'), median_signed_ci_lo=lo2,
                median_signed_ci_hi=hi2)


def prediction_interval(pred, test_errors_pct):
    """95 percent prediction interval for a true value given a prediction and held out errors.
    With e = (pred - true) / true, true = pred / (1 + e); quantiles 2.5 and 97.5 of e give the bounds."""
    e = np.asarray(test_errors_pct, float) / 100.0
    q_lo, q_hi = np.percentile(e, [2.5, 97.5])
    return pred / (1.0 + q_hi), pred / (1.0 + q_lo)


def write_csv(path, rows, fields=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fields = fields or list(rows[0].keys())
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: (f'{v:.6g}' if isinstance(v, float) else v) for k, v in r.items()})


def is_assembly(impl):
    return bool(re.match(r'm4', str(impl)))
