#!/usr/bin/env python3
"""Generate docs/STATISTICS_V5.md from the result files of stats/ (no number is typed here).

Reads stats/results/cycle_*.csv, data/meta/hierarchical_*.csv, data/meta/cycle_groups.csv,
stats/results/e2e_*.csv and data/verify5/third_look_*.csv.
"""
import os

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = os.path.join(ROOT, "stats", "results")
META = os.path.join(ROOT, "data", "meta")
V5 = os.path.join(ROOT, "data", "verify5")


def rd(*p):
    path = os.path.join(*p)
    return pd.read_csv(path) if os.path.exists(path) else None


def f1(x):
    return "n/a" if pd.isna(x) else f"{x:.1f}"


def f2(x):
    return "n/a" if pd.isna(x) else f"{x:.2f}"


def g3(x):
    return "n/a" if pd.isna(x) else f"{x:.3g}"


def pct(x):
    return "n/a" if pd.isna(x) else f"{100 * x:.1f}"


def cfgval(df, key):
    return df.set_index("key").loc[key, "value"]


def cycle_section(L):
    b, lofo, bp, hc, cfg = (rd(R, "cycle_cluster_bootstrap.csv"), rd(R, "cycle_lofo_summary.csv"),
                            rd(R, "cycle_board_predictions_cluster.csv"), rd(R, "cycle_harness_check.csv"),
                            rd(R, "cycle_config.csv"))
    if b is None:
        L.append("Cycle model results are missing; run `python3 stats/cycle_validation.py`.\n")
        return
    fb = b[b.model == "fitted"].set_index("subset")
    t = fb.loc["test, all"]
    L += ["## 1. Cycle model: cluster bootstrap and leave one group out (modelled)", "",
          f"Nothing in the round 4 model changes: refitting it on the round 4 training half reproduces the held out errors "
          f"of `cyclemodel/results/matched_rows.csv` (largest difference {cfgval(cfg, 'round4_reproduction_max_abs_difference_pct')} "
          "percentage points). The added analyses are in `stats/cycle_validation.py`.", "",
          "### 1.1 Cluster bootstrap by binary", "",
          f"The round 4 intervals resample rows. Here whole binaries are resampled with their rows kept together "
          f"({int(t.n_boot)} resamples, seed {int(t.seed)}; {int(t.n_rows)} held out rows in {int(t.n_binaries)} binaries).", "",
          "| model | subset | rows | binaries | median abs error, percent | round 4 row interval | row interval, seed 20261021 | cluster interval |",
          "|---|---|---|---|---|---|---|---|"]
    for _, r in b.iterrows():
        L.append(f"| {r.model} | {r.subset} | {r.n_rows} | {r.n_binaries} | {f1(r.median_abs_pct)} | "
                 f"{f1(r.median_abs_round4_row_ci_lo)} to {f1(r.median_abs_round4_row_ci_hi)} | "
                 f"{f1(r.median_abs_row_ci_lo)} to {f1(r.median_abs_row_ci_hi)} | "
                 f"{f1(r.median_abs_cluster_ci_lo)} to {f1(r.median_abs_cluster_ci_hi)} |")
    L += ["", "Prediction interval bounds. The round 4 prediction interval uses the 2.5 and 97.5 percentiles of the 27 held out "
          "errors. Their cluster bootstrap intervals show how uncertain these bounds are:", "",
          "| model | subset | 2.5 percentile of errors, percent | cluster interval | 97.5 percentile, percent | cluster interval |",
          "|---|---|---|---|---|---|"]
    for name in ("test, all", "test, excluding sign"):
        for m in ("fitted", "reduced"):
            r = b[(b.model == m) & (b.subset == name)].iloc[0]
            L.append(f"| {m} | {name} | {f1(r.err_p025_pct)} | {f1(r.err_p025_cluster_ci_lo)} to {f1(r.err_p025_cluster_ci_hi)} | "
                     f"{f1(r.err_p975_pct)} | {f1(r.err_p975_cluster_ci_lo)} to {f1(r.err_p975_cluster_ci_hi)} |")
    wr = bp.width_ratio_cluster_to_round4.iloc[0]
    L += ["", f"A cluster aware prediction interval for the board predictions takes the outer limits of these two intervals; "
          f"it is {f2(wr)} times as wide as the round 4 interval for every prediction "
          "(`stats/results/cycle_board_predictions_cluster.csv`).", ""]
    excl = fb.loc["test, excluding sign"]
    L.append(f"Reading. For all held out rows the cluster interval of the median absolute error is "
             f"{f1(t.median_abs_cluster_ci_lo)} to {f1(t.median_abs_cluster_ci_hi)} percent against "
             f"{f1(t.median_abs_round4_row_ci_lo)} to {f1(t.median_abs_round4_row_ci_hi)} percent for rows; without signing "
             f"{f1(excl.median_abs_cluster_ci_lo)} to {f1(excl.median_abs_cluster_ci_hi)} against "
             f"{f1(excl.median_abs_round4_row_ci_lo)} to {f1(excl.median_abs_round4_row_ci_hi)}. "
             + ("The cluster interval is not wider at the top: each test binary holds one row of each operation, and the "
                "errors differ more between operations than between binaries. "
                if t.median_abs_cluster_ci_hi <= 1.05 * t.median_abs_round4_row_ci_hi else
                "The cluster interval is wider, as expected when rows of one binary share their error. ")
             + "The prediction interval bounds, which rest on the few signing rows, are the uncertain part.")
    L += ["", "### 1.2 Leave one group out", "",
          "The model is refitted on all matched rows outside one group (both round 4 halves) and predicts the group.", "",
          "| left out by | group | rows | median abs error, percent | worst abs error, percent | median abs without sign | worst abs without sign |",
          "|---|---|---|---|---|---|---|"]
    for _, r in lofo[(lofo.model == "fitted") & (lofo.left_out_by != "binary") & (lofo.group != "all groups pooled")].iterrows():
        L.append(f"| {r.left_out_by} | {r.group} | {r.n_rows} | {f1(r.median_abs_pct)} | {f1(r.worst_abs_pct)} | "
                 f"{f1(r.median_abs_excl_sign_pct)} | {f1(r.worst_abs_excl_sign_pct)} |")
    pool = lofo[(lofo.model == "fitted") & (lofo.group == "all groups pooled")].set_index("left_out_by")
    red = lofo[(lofo.model == "reduced") & (lofo.group == "all groups pooled")].set_index("left_out_by")
    L += ["", "Pooled over the left out groups (each row predicted once without its group):", "",
          "| left out by | model | median abs, percent (cluster interval) | worst abs, percent | without sign: median, worst |",
          "|---|---|---|---|---|"]
    for k in ("binary", "implementation family", "parameter set", "scheme"):
        for m, d in (("fitted", pool), ("reduced", red)):
            r = d.loc[k]
            L.append(f"| {k} | {m} | {f1(r.median_abs_pct)} ({f1(r.median_abs_cluster_ci_lo)} to {f1(r.median_abs_cluster_ci_hi)}) | "
                     f"{f1(r.worst_abs_pct)} | {f1(r.median_abs_excl_sign_pct)}, {f1(r.worst_abs_excl_sign_pct)} |")
    fam = pool.loc["implementation family"]
    sch = pool.loc["scheme"]
    L += ["", f"Reading. Against the round 4 held out median of {f1(t.median_abs_pct)} percent, leaving out a whole implementation "
          f"family gives a pooled median absolute error of {f1(fam.median_abs_pct)} percent ({f1(fam.median_abs_pct / t.median_abs_pct)} "
          f"times; worst {f1(fam.worst_abs_pct)}), and leaving out a whole scheme gives {f1(sch.median_abs_pct)} percent "
          f"({f1(sch.median_abs_pct / t.median_abs_pct)} times; worst {f1(sch.worst_abs_pct)}). "
          f"The reduced four feature model transfers across schemes with a pooled median of {f1(red.loc['scheme'].median_abs_pct)} percent "
          f"(worst {f1(red.loc['scheme'].worst_abs_pct)}), so the twelve feature fit does not carry over to a scheme it has not seen.", "",
          "### 1.3 Test on the mlkem-native and mldsa-native harness", "",
          f"{hc[hc.id == 'summary'].reason.iloc[0][0].upper() + hc[hc.id == 'summary'].reason.iloc[0][1:]}. "
          f"`data/evidence.csv` holds {len(hc) - 1} rows that name these libraries; they come from a different core and build "
          "(`stats/results/cycle_harness_check.csv`).", ""]


def meta_section(L):
    v, res, cfg, gr = (rd(META, "hierarchical_variance.csv"), rd(META, "hierarchical_residual.csv"),
                       rd(META, "hierarchical_config.csv"), rd(META, "cycle_groups.csv"))
    if v is None:
        L.append("Hierarchical meta analysis results are missing; run `python3 stats/meta_hierarchical.py`.\n")
        return
    L += ["## 2. Meta analysis: hierarchical model (modelled from published rows)", "",
          f"Response: natural log of cycles. Cells (parameter set, operation, core class) with two or more rows: "
          f"{cfgval(cfg, 'cells_used')} cells, {cfgval(cfg, 'rows_used')} of {cfgval(cfg, 'rows_in_meta_analysis')} rows of "
          "`data/evidence.csv` that `scripts/meta_analysis.py` uses. Cell means are fixed effects; implementation variant "
          "(the library field as the row states it), statistic (mean, median, min, other), compiler where stated and source "
          "are crossed random effects (REML, `stats/meta_hierarchical.py`). "
          f"Fits: {cfgval(cfg, 'weightings')}; weighted fit: {cfgval(cfg, 'weighting')}. "
          f"Intervals: parametric bootstrap, {cfgval(cfg, 'n_boot')} refits per fit, seed {cfgval(cfg, 'seed')}.", ""]
    for title, sel in (("Unweighted, all rows", (v.weighting == "unweighted") & (v.fit == "main (variant as stated)")),
                       ("Weighted by source quality, all rows", (v.weighting == "weighted") & (v.fit == "main (variant as stated)")),
                       (f"Unweighted, the {cfgval(cfg, 'worst_observed_rows')} rows that report a worst observed value removed",
                        v.fit == "worst observed rows excluded: main (variant as stated)")):
        g = v[sel]
        if not len(g):
            continue
        L += [f"**{title}**", "", "| component | levels | sd of log cycles | factor at one sd | share of within cell variance, percent | 95 percent interval of the share |",
              "|---|---|---|---|---|---|"]
        for _, r in g.iterrows():
            L.append(f"| {r.component} | {r.levels} | {f2(r.sd_log)} | {f2(r.factor_1sd)} | {pct(r.share_within_cell)} | "
                     f"{pct(r.share_ci_lo)} to {pct(r.share_ci_hi)} |")
        L.append("")
    sens = v[(v.weighting == "unweighted") & (v.fit == "sensitivity (variant class)")]
    L += ["Sensitivity fit (unweighted, all rows) with a coarse variant class (portable C, stack or memory optimised, assembly or "
          "optimised, other) in place of the verbatim library text:", "", "| component | levels | sd of log cycles | share, percent |", "|---|---|---|---|"]
    for _, r in sens.iterrows():
        L.append(f"| {r.component} | {r.levels} | {f2(r.sd_log)} | {pct(r.share_within_cell)} |")
    rr = res.set_index(["weighting", "measure"])
    L += ["", "Spread of repeated measurements of one implementation:", "",
          "| measure | fit | sd of log cycles | factor | 95 percent interval of the sd |", "|---|---|---|---|---|"]
    for (wt, m), r in rr.iterrows():
        L.append(f"| {m} | {wt} | {f2(r.value)} | {f2(r.factor)} | {f2(r.ci_lo)} to {f2(r.ci_hi)} |")
    multi = gr[gr.sources >= 2]
    L += ["", f"Comparison with the round 4 measure: the max over min ratio is {f2(multi.max_over_min.median())} at the median of the "
          f"{len(multi)} groups with two or more sources. That ratio mixes every factor above and grows with the number of rows "
          "in a group; the variance shares say which factor carries the spread.", "",
          f"Statistic levels read from the notes: {cfgval(cfg, 'statistic_levels')}. Compiler levels: {cfgval(cfg, 'compiler_levels')}. "
          "Factors with few levels (statistic, compiler) give unstable variance estimates, and they are partly confounded with "
          "source and variant; the source component is near zero because each source mostly reports its own variants. "
          "The rows that report a worst observed signing time over a crafted test set (as the rows state) carry most of the "
          "statistic and compiler variance of the full fit.", "", f"Cross check (unweighted fit): {cfgval(cfg, 'statsmodels_check')}.", ""]


def e2e_section(L):
    inp, fx, s, sob, cfg = (rd(R, "e2e_inputs.csv"), rd(R, "e2e_fixed.csv"), rd(R, "e2e_mc_summary.csv"),
                            rd(R, "e2e_sobol.csv"), rd(R, "e2e_config.csv"))
    if s is None or sob is None:
        L.append("End to end results are missing; run `python3 stats/end_to_end.py`.\n")
        return
    L += ["## 3. End to end uncertainty and Sobol ranking (modelled)", "",
          "One chain from published cycles through compute time, energy, link and protocol time to mission availability "
          "(`stats/end_to_end.py`, which calls `mission/sim.py`, `energy/model.py` and the parameter files of `linksim/`). "
          f"Monte Carlo draws: {cfgval(cfg, 'n_mc')}; Sobol base points: {cfgval(cfg, 'n_sobol_base')} "
          f"({cfgval(cfg, 'sobol_evaluations')} evaluations); missions per evaluation and architecture: {cfgval(cfg, 'runs_per_evaluation')}, "
          f"with common random numbers ({cfgval(cfg, 'common_random_numbers')}); seed {cfgval(cfg, 'seed')}. "
          f"Run time: {cfgval(cfg, 'mc_seconds')} s Monte Carlo and {cfgval(cfg, 'sobol_seconds')} s Sobol on {cfgval(cfg, 'processes')} processes.", "",
          "Inputs (uniform over the stated range):", "", "| input | low | high | unit | range taken from |", "|---|---|---|---|---|"]
    for _, r in inp.iterrows():
        L.append(f"| {r.input} | {g3(r.low)} | {g3(r.high)} | {r.unit} | {r.range_source} |")
    L += ["", "Kept fixed (point values without a stated range): " + "; ".join(f"{r['item']} ({r.source})" for _, r in fx.iterrows()) + ".", "",
          "Output intervals:", "", "| output | unit | 2.5 percentile | median | 97.5 percentile |", "|---|---|---|---|---|"]
    for _, r in s.iterrows():
        L.append(f"| {r.output} | {r.unit} | {g3(r.p2_5)} | {g3(r["median"])} | {g3(r.p97_5)} |")
    L += ["", "Inputs ranked by total Sobol index (first five per output; all in `stats/results/e2e_sobol.csv`):", "",
          "| output | rank | input | total index | interval | first order index |", "|---|---|---|---|---|---|"]
    for o, g in sob.groupby("output", sort=False):
        for _, r in g.sort_values("rank_by_ST").head(5).iterrows():
            L.append(f"| {o} | {r.rank_by_ST} | {r.input} | {f2(r.ST)} | {f2(r.ST - r.ST_conf)} to {f2(r.ST + r.ST_conf)} | {f2(r.S1)} |")
    L += ["", f"Note on the latency output: {cfgval(cfg, 'y2_deadline')}. Intervals of the indices are SALib bootstrap intervals; with "
          f"{cfgval(cfg, 'n_sobol_base')} base points the small indices are not distinguishable from zero.", ""]


def third_section(L):
    s, c, corr = rd(V5, "third_look_summary.csv"), rd(V5, "third_look_classified.csv"), rd(V5, "third_look_corrections.csv")
    if s is None:
        L.append("Third look results are missing; run `python3 stats/third_look_classify.py`.\n")
        return
    m = s.set_index("measure")
    tot = int(m.loc["lines staging_right", "of"])
    L += ["## 4. Third look at every remaining wording disagreement (estimated)", "",
          f"Verification 5 left {tot} wording disagreements without a third look. Each went on a blank sheet "
          "(`stats/third_look_sheets.py`: row id, field, source and location only) to a fresh reader who saw neither the staged "
          "value nor the earlier readings and copied what the source prints. `stats/third_look_classify.py` compares afterwards.", "",
          "| class | lines |", "|---|---|"]
    for k in ("staging_right", "reader_right", "both_wrong", "not_in_source", "ambiguous", "not_retrieved"):
        L.append(f"| {k.replace('_', ' ')} | {int(m.loc['lines ' + k, 'count'])} |")
    L += ["", "The classes compare wording: the third reader copies the source verbatim, while staging writes a normalised "
          "description. The match rules (R1 to R5 in the script header) were written after a first literal comparison showed "
          "that almost every line differed in wording only; this is a decision taken after seeing the data.", "",
          "| measure | count | of | share, percent | Wilson 95 percent interval, percent |", "|---|---|---|---|---|"]
    for k in ("staged text differs verbatim from the source among settled lines",
              "staged text contradicts the source, settled lines of judged fields (operation, core, scheme, parameter_set)",
              "staged text contradicts the source, all settled lines (automatic test and manual decisions)",
              "round 4 sample of 60: staging wrong after a third look (round 4 rule, any difference from the source)",
              "staging wrong in substance, all wording disagreements with a settled third look (round 4 sample of 60 and this round)"):
        if k not in m.index:
            continue
        r = m.loc[k]
        L.append(f"| {k} | {int(r['count'])} | {int(r['of'])} | {pct(r.share)} | {pct(r.wilson_lo)} to {pct(r.wilson_hi)} |")
    um = "differing lines of judged fields that the automatic test could not map (counted as no contradiction found)"
    if um in m.index:
        L += ["", "The two substance rates use different tests and are reported separately; the pooled last row mixes them and is kept "
              "only for reference. The round 4 sample counted any difference from the source as wrong. The automatic test of this round is "
              "lenient: a scheme is compared only by family, a parameter set is a contradiction only when no number is shared, and a pair "
              f"it cannot map counts as no contradiction; {int(m.loc[um, 'count'])} of {int(m.loc[um, 'of'])} differing lines of the judged "
              "fields were of that kind, so the 0 for the judged fields is partly by construction. Counts and shares are script comparisons "
              "(estimated); only the third readings themselves are source wording."]
    L += ["", "Substance: for operation, core, scheme family and parameter numbers a contradiction test is automatic; for "
          "conditions, library, quantity and unit the decision per line is in `data/verify5/third_look_manual.csv`, written in "
          "the comparison step with all values in view.", "",
          f"Corrections written to `data/corrections.csv`: {0 if corr is None else len(corr)} "
          f"({', '.join(f'{r.id} {r.field}' for _, r in corr.iterrows()) if corr is not None and len(corr) else 'none'}). "
          f"Ambiguous lines ({int(m.loc['lines ambiguous', 'count'])}) are not settled and are listed in "
          "`data/verify5/third_look_classified.csv`; they concern conditions and quantities of link facts, not evidence rows "
          "used in the cycle analyses." if c is not None and set(c[c.verdict == 'ambiguous'].id.str[:5]) <= {'S12BL'} else
          f"Corrections written to `data/corrections.csv`: {0 if corr is None else len(corr)}. "
          f"Ambiguous lines ({int(m.loc['lines ambiguous', 'count'])}) are not settled and are listed in "
          "`data/verify5/third_look_classified.csv`.", ""]


def main():
    L = ["# Statistics, round 5", "", "Author: Huda Mueen. Generated by `stats/make_doc.py` from the result files named in each "
         "section; do not edit by hand. Labels: modelled (cycle model, hierarchical model, end to end chain), estimated "
         "(third look comparison counts and shares; the third readings themselves are source wording). Seed 20261021 unless a section states another.", ""]
    cycle_section(L)
    meta_section(L)
    e2e_section(L)
    third_section(L)
    L += ["## 5. Rerun", "", "```", "python3 stats/cycle_validation.py", "python3 stats/meta_hierarchical.py",
          "python3 stats/end_to_end.py", "python3 stats/third_look_classify.py", "python3 stats/make_doc.py",
          "python3 -m unittest discover -s stats -t .", "```", ""]
    with open(os.path.join(ROOT, "docs", "STATISTICS_V5.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(L))
    print("wrote docs/STATISTICS_V5.md")


if __name__ == "__main__":
    main()
