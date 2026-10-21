#!/usr/bin/env python3
"""Hierarchical (variance component) model of published microcontroller cycle counts.

Replaces the max over min spread of scripts/meta_analysis.py as the measure of how far a published cycle count
can sit from another count for the same operation, parameter set and core class.

Data: the rows that scripts/meta_analysis.py uses (data/evidence.csv, label published, microcontroller rows with
a cycle count and a plain operation). Response: natural log of cycles. A cell is one (parameter set, operation,
core class); only cells with two or more rows carry information on the spread and are used.

Model (linear mixed model, REML):
    log cycles = cell mean (fixed) + a[variant] + b[statistic] + c[compiler] + d[source] + residual
with crossed random effects. Factors, all read from the row text:
  * variant: the implementation as the row states it (the `library` field, verbatim).
  * statistic: mean, median, min or other (single execution, worst case, not stated), read from the notes.
  * compiler: compiler family and major version where the notes state it (for example "gcc 11"), else "not stated".
  * source: the source URL.
The residual is the spread left between rows of one cell that share variant, statistic, compiler and source,
that is, repeated measurements of one implementation. A sensitivity fit replaces the verbatim variant by a coarse
class (portable C, stack optimised, assembly or optimised, other).

Weights. If data/source_quality.csv exists, the model is fitted twice, unweighted and weighted. Weighted: the
residual variance of a row is divided by the weight of its source; the weight is the column `weight` if present,
otherwise (score + 1) / 6 from the column `score` (0 to 5); sources missing from the file get weight 1. Without the
file only the unweighted fit runs, and the outputs say so. Column `weighting` of every output names the fit.

Fitting. The REML criterion is maximised with scipy (own implementation, which handles the weights); the unweighted
fit is cross checked against statsmodels MixedLM (crossed variance components in a single group). Intervals for the
variance shares come from a parametric bootstrap (seed 20261021, N_BOOT refits).

Writes data/meta/hierarchical_variance.csv, data/meta/hierarchical_residual.csv, data/meta/hierarchical_rows.csv
and data/meta/hierarchical_config.csv (every file has a label column).
"""
import os
import re

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.linalg import cho_factor, cho_solve
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import meta_analysis as MA  # noqa: E402

SEED = 20261021
N_BOOT = 100
FACTORS = ["variant", "statistic", "compiler", "source"]
OUT = ROOT / "data" / "meta"
WEIGHT_FILE = ROOT / "data" / "source_quality.csv"


def statistic_of(notes, warning=""):
    """mean, median, min or other, read from the notes first and the comparability warning second."""
    for t in (str(notes), str(warning)):
        s = t.lower()
        m = re.search(r"statistic:\s*([a-z ]+)", s)
        if m:
            w = m.group(1)
            if "median" in w:
                return "median"
            if "mean" in w or "average" in w:
                return "mean"
            if "minimum" in w or w.startswith("min") or "best" in w:
                return "min"
            return "other"
        if re.search(r"\bmedian\b", s):
            return "median"
        if re.search(r"\b(mean|average|avg)\b", s):
            return "mean"
        if re.search(r"\b(minimum|best) (of|over|observed)\b|\bmin of\b|\bminimum cycle", s):
            return "min"
    return "other"


def compiler_of(notes):
    s = str(notes).lower()
    m = re.search(r"\bgcc\b[^0-9;]{0,60}?(\d{1,2})\.\d", s)
    if m:
        return f"gcc {int(m.group(1))}"
    for k in ("clang", "armclang", "iar", "keil", "armcc"):
        if re.search(rf"\b{k}\b", s):
            return k
    if re.search(r"\bgcc\b", s):
        return "gcc, version not stated"
    return "not stated"


def variant_class(library):
    s = str(library).lower()
    if "stack" in s or "lowram" in s or "memory constrained" in s:
        return "stack or memory optimised"
    if re.search(r"clean|reference|portable|pqclean|\bref\b", s):
        return "portable C or reference"
    if re.search(r"m4f|asm|assembly|slothy|optimi|m4-ct|\bm4\b|m7", s):
        return "assembly or optimised"
    return "other or not stated"


def load_rows():
    d = MA.load().copy()
    d["cell"] = d["param"] + " | " + d["op_class"] + " | " + d["core_class"]
    d["y"] = np.log(d["cycles"].astype(float))
    d["variant"] = d["library"].astype(str)
    d["variant_class"] = d["library"].map(variant_class)
    d["statistic"] = [statistic_of(n, w) for n, w in zip(d["compiler_flags_or_notes"], d["comparability_warning"])]
    d["compiler"] = d["compiler_flags_or_notes"].map(compiler_of)
    d["source"] = d["source_url"].astype(str)
    n = d.groupby("cell")["y"].transform("size")
    return d[n >= 2].reset_index(drop=True), d


def load_weights(d):
    if not WEIGHT_FILE.exists():
        return np.ones(len(d)), "unweighted (data/source_quality.csv not present)"
    q = pd.read_csv(WEIGHT_FILE)
    key = "source_url" if "source_url" in q.columns else q.columns[0]
    if "weight" in q.columns:
        m = dict(zip(q[key].astype(str), q["weight"].astype(float)))
        rule = "column weight"
    else:
        # score 0 to 5 (data/source_quality.csv): weight (score + 1) / 6, so a score of 0 keeps a small positive weight
        m = dict(zip(q[key].astype(str), (q["score"].astype(float) + 1.0) / 6.0))
        rule = "weight (score + 1) / 6"
    w = d["source"].map(lambda s: m.get(s, 1.0)).to_numpy(float)
    if (w <= 0).any():
        raise SystemExit("weights must be positive")
    missing = int((~d["source"].isin(list(m))).sum())
    return w, f"weighted by data/source_quality.csv, {rule}; {len(m)} sources listed, {missing} rows from unlisted sources at weight 1"


def design(d, factors):
    cells = sorted(d["cell"].unique())
    X = (d["cell"].to_numpy()[:, None] == np.array(cells)[None, :]).astype(float)
    Z = []
    for f in factors:
        lev = sorted(d[f].unique())
        Z.append((d[f].to_numpy()[:, None] == np.array(lev)[None, :]).astype(float))
    return X, Z


def contrasts(X):
    """Orthonormal basis K of the null space of X' (error contrasts for REML)."""
    q, _ = np.linalg.qr(X, mode="complete")
    return q[:, np.linalg.matrix_rank(X):]


class Reml:
    """REML criterion on error contrasts: y* = K'y ~ N(0, K'VK), V = sum s_k Z_k Z_k' + s_e W^-1."""

    def __init__(self, X, Z, w):
        self.K = contrasts(X)
        self.A = [self.K.T @ M for M in Z]
        self.AA = [a @ a.T for a in self.A]
        self.R = (self.K.T * (1.0 / w)) @ self.K

    def neg(self, theta, ys):
        s = np.exp(theta)
        V = s[-1] * self.R
        for k, M in enumerate(self.AA):
            V = V + s[k] * M
        try:
            c = cho_factor(V, lower=True, check_finite=False)
        except np.linalg.LinAlgError:
            return 1e12
        return 0.5 * (2 * np.log(np.diag(c[0])).sum() + ys @ cho_solve(c, ys, check_finite=False))


def fit(y, X, Z, w, start=None, reml=None):
    reml = reml or Reml(X, Z, w)
    ys = reml.K.T @ y
    k = len(Z) + 1
    best = None
    v = float(ys @ ys / len(ys))
    starts = [start] if start is not None else []
    starts += [np.full(k, np.log(max(v, 1e-6) / k)), np.full(k, np.log(max(v, 1e-6))), np.full(k, -6.0)]
    for s0 in starts:
        r = minimize(reml.neg, s0, args=(ys,), method="L-BFGS-B", bounds=[(-25, 5)] * k)
        if best is None or r.fun < best.fun:
            best = r
    return np.exp(best.x), -best.fun


def shares(var):
    tot = var.sum()
    return var / tot if tot > 0 else var * np.nan


def simulate(rng, X, beta, Z, var, w):
    y = X @ beta
    for k, M in enumerate(Z):
        y = y + M @ rng.normal(0, np.sqrt(var[k]), M.shape[1])
    return y + rng.normal(0, np.sqrt(var[-1] / w))


def gls_beta(y, X, Z, var, w):
    V = np.diag(var[-1] / w) + sum(var[k] * (M @ M.T) for k, M in enumerate(Z))
    Vi = np.linalg.inv(V)
    return np.linalg.solve(X.T @ Vi @ X, X.T @ Vi @ y)


def statsmodels_check(d, factors):
    """Unweighted crossed variance component fit with statsmodels MixedLM (cell as fixed effect)."""
    import statsmodels.formula.api as smf
    dd = d.copy()
    dd["one"] = 1
    for f in factors:
        dd[f + "_c"] = pd.Categorical(dd[f]).codes
    vc = {f: f"0 + C({f}_c)" for f in factors}
    m = smf.mixedlm("y ~ 0 + C(cell)", dd, groups="one", vc_formula=vc, re_formula="0")
    r = m.fit(reml=True, method=["lbfgs"])
    names = list(r.model.exog_vc.names)
    out = {n: float(v) for n, v in zip(names, r.vcomp)}
    out["residual"] = float(r.scale)
    return out


def run(d, factors, w, n_boot, seed):
    y = d["y"].to_numpy(float)
    X, Z = design(d, factors)
    reml = Reml(X, Z, w)
    var, ll = fit(y, X, Z, w, reml=reml)
    beta = gls_beta(y, X, Z, var, w)
    rng = np.random.default_rng(seed)
    boot = []
    for _ in range(n_boot):
        ys = simulate(rng, X, beta, Z, var, w)
        vb, _ = fit(ys, X, Z, w, start=np.log(np.maximum(var, 1e-10)), reml=reml)
        boot.append(vb)
    return var, ll, np.array(boot), X, Z


def analyse(d, w, wnote, mode, n_boot):
    var, ll, boot, X, Z = run(d, FACTORS, w, n_boot, SEED)
    names = FACTORS + ["residual"]
    sh, bsh = shares(var), np.array([shares(b) for b in boot])
    q = lambda a, p: float(np.percentile(a, p)) if n_boot else np.nan  # noqa: E731
    rows = []
    for i, n in enumerate(names):
        rows.append(dict(label="modelled", weighting=mode, fit="main (variant as stated)", component=n,
                         levels=int(Z[i].shape[1]) if i < len(Z) else len(d),
                         variance_log=float(var[i]), sd_log=float(np.sqrt(var[i])),
                         factor_1sd=float(np.exp(np.sqrt(var[i]))), share_within_cell=float(sh[i]),
                         share_ci_lo=q(bsh[:, i], 2.5) if n_boot else np.nan,
                         share_ci_hi=q(bsh[:, i], 97.5) if n_boot else np.nan,
                         sd_ci_lo=q(np.sqrt(boot[:, i]), 2.5) if n_boot else np.nan,
                         sd_ci_hi=q(np.sqrt(boot[:, i]), 97.5) if n_boot else np.nan,
                         weighting_note=wnote, seed=SEED, n_boot=n_boot))
    f2 = ["variant_class", "statistic", "compiler", "source"]
    var2, _, _, _, Z2 = run(d, f2, w, 0, SEED)
    sh2 = shares(var2)
    for i, n in enumerate(f2 + ["residual"]):
        rows.append(dict(label="modelled", weighting=mode, fit="sensitivity (variant class)", component=n,
                         levels=int(Z2[i].shape[1]) if i < len(Z2) else len(d), variance_log=float(var2[i]),
                         sd_log=float(np.sqrt(var2[i])), factor_1sd=float(np.exp(np.sqrt(var2[i]))),
                         share_within_cell=float(sh2[i]), share_ci_lo=np.nan, share_ci_hi=np.nan,
                         sd_ci_lo=np.nan, sd_ci_hi=np.nan, weighting_note=wnote, seed=SEED, n_boot=0))
    sm_note = "not run (weighted fit)"
    if np.all(w == 1.0):
        try:
            sm = statsmodels_check(d, FACTORS)
            diffs = [abs(sm.get(n, np.nan) - var[i]) for i, n in enumerate(names)]
            sm_note = "statsmodels MixedLM variances: " + "; ".join(f"{n} {sm.get(n, float('nan')):.4g}" for n in names) \
                + f"; max absolute difference to own REML {max(diffs):.2g}"
        except Exception as e:  # pragma: no cover
            sm_note = f"statsmodels check failed: {type(e).__name__}"
    res = [dict(label="modelled", weighting=mode, measure="residual sd of the hierarchical model (log cycles)",
                value=float(np.sqrt(var[-1])), factor=float(np.exp(np.sqrt(var[-1]))),
                ci_lo=q(np.sqrt(boot[:, -1]), 2.5) if n_boot else np.nan,
                ci_hi=q(np.sqrt(boot[:, -1]), 97.5) if n_boot else np.nan,
                n_rows=len(d), n_groups=d["cell"].nunique()),
           dict(label="modelled", weighting=mode, measure="total within cell sd of the hierarchical model (log cycles)",
                value=float(np.sqrt(var.sum())), factor=float(np.exp(np.sqrt(var.sum()))),
                ci_lo=q(np.sqrt(boot.sum(axis=1)), 2.5) if n_boot else np.nan,
                ci_hi=q(np.sqrt(boot.sum(axis=1)), 97.5) if n_boot else np.nan,
                n_rows=len(d), n_groups=d["cell"].nunique())]
    return rows, res, sm_note


def main(n_boot=N_BOOT):
    t0 = time.time()
    d, d_all = load_rows()
    w, wnote = load_weights(d)
    modes = [("unweighted", np.ones(len(d)), "unweighted")]
    if WEIGHT_FILE.exists():
        modes.append(("weighted", w, wnote))
    else:
        modes[0] = ("unweighted", np.ones(len(d)), "unweighted (data/source_quality.csv not present)")
    rows, res, notes = [], [], {}
    for mode, ww, note in modes:
        r1, r2, sm = analyse(d, ww, note, mode, n_boot)
        rows += r1
        res += r2
        notes[mode] = (note, sm)
    # sensitivity: rows that report a worst observed value (the slowest of many runs) removed
    worst = d.apply(lambda r: bool(re.search(r"worst", f"{r['compiler_flags_or_notes']} {r['location_in_source']}", re.I)),
                    axis=1).to_numpy()
    if worst.any():
        dn = d[~worst].reset_index(drop=True)
        cn = dn.groupby("cell")["y"].transform("size") >= 2
        dn = dn[cn].reset_index(drop=True)
        r1, r2, _ = analyse(dn, np.ones(len(dn)), "unweighted", "unweighted", 0)
        for r in r1:
            r["fit"] = "worst observed rows excluded: " + r["fit"]
        for r in r2:
            r["measure"] = "worst observed rows excluded: " + r["measure"]
        rows += r1
        res += r2
    key = d["cell"] + " || " + d["variant"]
    g = d.assign(key=key).groupby("key")["y"]
    rep = g.transform("size") >= 2
    dev = (d["y"] - g.transform("mean"))[rep]
    dof = int(rep.sum() - (g.size() >= 2).sum())
    pooled_sd = float(np.sqrt((dev ** 2).sum() / dof)) if dof > 0 else float("nan")
    res.append(dict(label="published", weighting="unweighted",
                    measure="pooled within sd of log cycles, same cell and same stated variant",
                    value=pooled_sd, factor=float(np.exp(pooled_sd)), ci_lo=np.nan, ci_hi=np.nan,
                    n_rows=int(rep.sum()), n_groups=int((g.size() >= 2).sum())))
    pd.DataFrame(rows).to_csv(OUT / "hierarchical_variance.csv", index=False, float_format="%.6g")
    pd.DataFrame(res).to_csv(OUT / "hierarchical_residual.csv", index=False, float_format="%.6g")
    d.assign(label="published", weight=w)[["label", "id", "cell", "variant", "variant_class", "statistic",
                                           "compiler", "source", "cycles", "weight"]].to_csv(
        OUT / "hierarchical_rows.csv", index=False)
    cfg = [("seed", SEED), ("n_boot", n_boot), ("rows_used", len(d)), ("rows_in_meta_analysis", len(d_all)),
           ("cells_used", d["cell"].nunique()), ("worst_observed_rows", int(worst.sum())), ("weightings", ", ".join(m for m, _, _ in modes)),
           ("weighting", notes.get("weighted", notes["unweighted"])[0]),
           ("response", "natural log of cycles"), ("method", "REML, crossed random effects, cell as fixed effect"),
           ("statsmodels_check", notes["unweighted"][1]),
           ("statistic_levels", "; ".join(f"{k} {v}" for k, v in d["statistic"].value_counts().items())),
           ("compiler_levels", "; ".join(f"{k} {v}" for k, v in d["compiler"].value_counts().items())),
           ("runtime_s", f"{time.time() - t0:.0f}")]
    pd.DataFrame([dict(label="assumption", key=k, value=v) for k, v in cfg]).to_csv(
        OUT / "hierarchical_config.csv", index=False)
    print(pd.DataFrame(rows)[["weighting", "fit", "component", "levels", "sd_log", "share_within_cell", "share_ci_lo",
                              "share_ci_hi"]].to_string())
    print(pd.DataFrame(res)[["weighting", "measure", "value", "factor"]].to_string())
    print(notes, f"{time.time() - t0:.0f} s")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else N_BOOT)
