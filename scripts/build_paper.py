#!/usr/bin/env python3
"""Build docs/PAPER.md (six page main part plus a supplementary section) and the proposals from the result files, and write the claims register.

Every number placed in the paper comes from a call to `claim()`, which reads it from a result file
with a pandas query and an aggregate, formats it, and records one row in data/claims_register.csv
(document, the formatted text, the value, the file, the column, the query, the aggregate). The
build fails on an unfilled placeholder. scripts/check_numbers.py then recomputes every row, so the
paper cannot drift from its data.
"""
import csv
import datetime as dt
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DOC = "docs/PAPER.md"
CLAIMS = []
BY_KEY = {}  # marker number -> claim row
WORDS_PER_PAGE = 900  # two column IEEE style page including figures (estimate used for the page budget)


def claim(cid, source, column, query="", aggregate="value", fmt="{:,.0f}", scale=1.0, label="", doc=DOC):
    d = pd.read_csv(ROOT / source)
    if query:
        d = d.query(query, engine="python")
    s = d[column]
    if aggregate == "value":
        if len(s) != 1:
            sys.exit(f"{cid}: query selects {len(s)} rows in {source}")
        v = float(s.iloc[0])
    elif aggregate == "count":
        v = float(len(s))
    elif aggregate == "nunique":
        v = float(s.nunique())
    else:
        v = float(getattr(pd.to_numeric(s, errors="coerce"), aggregate)())
    text = fmt.format(v * scale)
    CLAIMS.append({"claim_id": cid, "document": doc, "text_in_document": text, "value": v, "source_file": source,
                   "column": column, "query": query, "aggregate": aggregate, "tolerance_rel": "0.005",
                   "label": label, "note": f"displayed as {fmt} x {scale}" if scale != 1.0 else "", "context": ""})
    BY_KEY[len(BY_KEY)] = CLAIMS[-1]
    # invisible markers locate the number in the finished document, so that short integers get a context (anchor())
    return f"\u2063{len(BY_KEY) - 1}\u2064{text}"


MARK = re.compile("\u2063(\\d+)\u2064")


def anchor(text):
    """Remove the claim markers from a finished document. For every short integer claim (one or two digits, no
    decimal point) record as context the number with the words that follow it, so that scripts/check_numbers.py
    checks the number where it stands rather than anywhere in the document."""
    out, pos = [], 0
    marks = []
    for m in MARK.finditer(text):
        out.append(text[pos:m.start()])
        marks.append((int(m.group(1)), sum(len(x) for x in out)))
        pos = m.end()
    out.append(text[pos:])
    clean = "".join(out)
    for i, at in marks:
        c = BY_KEY[i]
        c["_used"] = True
        t = c["text_in_document"]
        if re.fullmatch(r"\d{1,2}", t) and clean[at:at + len(t)] == t:
            words = re.match(r"\S*(?:\s+\S+){0,2}", clean[at:at + 80]).group(0)
            c["context"] = words.rstrip(".,;:)|") if len(words) > len(t) else ""
    return clean


def exists(p):
    return (ROOT / p).exists()


def results_text():
    ev = "data/evidence.csv"
    L = []
    # RQ1 compute
    L.append("#### S1.1 RQ1: compute cost, and how well it can be predicted\n")
    L.append(
        f"Evidence. The table holds {claim('n_rows', ev, 'id', aggregate='count', label='published')} rows; "
        f"{claim('n_mcu_cycles', ev, 'cycles', 'device_class == \"mcu\" and cycles == cycles', 'count', label='published')} are microcontroller rows with a cycle count, "
        f"on {claim('n_cores', ev, 'core', 'device_class == \"mcu\" and cycles == cycles', 'nunique', label='published')} core labels as the sources print them (Cortex-M4 and Cortex-M4F are counted apart, and one label is 'not stated'). "
        f"Inside groups of the same parameter set, operation and core class that have rows from two or more sources, the largest published value is "
        f"{claim('meta_spread', 'data/meta/cycle_groups.csv', 'max_over_min', 'sources >= 2', 'median', '{:.2f}', label='estimated')} times the smallest at the median group "
        f"(up to {claim('meta_spread_max', 'data/meta/cycle_groups.csv', 'max_over_min', 'sources >= 2', 'max', '{:.2f}', label='estimated')}; ratios computed from published rows; `docs/META_ANALYSIS.md`). "
        "Part of this spread is deliberate: a group can hold speed and stack optimised variants of one scheme and both means and medians, so it measures how far a "
        "published figure can sit from the deployed code when the variant and conditions are not known, not the measurement error of one implementation. "
        "Library, optimisation, toolchain, cache and statistic all move it.\n")
    if exists("cyclemodel/results/error_summary.csv"):
        L.append("{{cycle_model_text}}\n")
    if exists("rtlsim/results/ibex_cycles.csv"):
        L.append("{{rtl_text}}\n")
    # RQ2 energy
    er = "energy/results/max_rates.csv"
    L.append("#### S1.2 RQ2: energy and CPU headroom\n")
    L.append(
        "Energy per operation was estimated from published cycles and cited run currents of five parts and checked against published energy rows: "
        f"uncalibrated, the estimate is low by a median of {claim('en_uncal', 'energy/results/validation_split.csv', 'abs_pct_error_uncalibrated', 'set == \"validation\"', 'median', '{:.1f}', label='modelled')} percent on the held out rows; "
        f"after one scale factor fitted on the other half, the median error is {claim('en_cal', 'energy/results/validation_split.csv', 'abs_pct_error_calibrated', 'set == \"validation\"', 'median', '{:.1f}', label='modelled')} percent "
        "(`docs/ENERGY_STUDY.md`). The check uses one board and one source, so it calibrates a factor rather than validating the model in general, and the energy figures elsewhere in this paper are uncalibrated; on that board the published energy is "
        f"{claim('en_k', 'energy/results/validation_split.csv', 'ratio_published_over_estimated', 'set == \"calibration\"', 'median', '{:.2f}', label='modelled')} times the estimate, so they are likely low by a similar factor; the message rates below depend only on cycles and are unaffected. "
        f"At 20 percent CPU headroom a 168 MHz Cortex-M4 flight controller can verify about {claim('rate_mldsa', er, 'msgs_per_s_at_20pct_estimated', 'target == \"Crazyflie 2.1\" and design == \"ML-DSA-44\"', fmt='{:.1f}', label='estimated')} ML-DSA-44 signatures per second, "
        f"{claim('rate_ed', er, 'msgs_per_s_at_20pct_estimated', 'target == \"Crazyflie 2.1\" and design == \"Ed25519\"', fmt='{:.1f}', label='estimated')} Ed25519 signatures and "
        f"{claim('rate_lms', er, 'msgs_per_s_at_20pct_estimated', 'target == \"Crazyflie 2.1\" and design == \"LMS\"', fmt='{:.1f}', label='estimated')} LMS signatures, against about "
        f"{claim('rate_mac', er, 'msgs_per_s_at_20pct_estimated', 'target == \"Crazyflie 2.1\" and design == \"HMAC-SHA256 session\"', fmt='{:,.0f}', label='estimated')} messages under a symmetric MAC session (estimated). "
        "Energy per hour is small for every design; CPU time, not battery, is the binding budget, and the command rate is the input that matters most (Sobol indices in `energy/results/sobol.csv`).\n")
    # RQ3 links
    dg = "linksim/results/diagnosis_v4.csv"
    L.append("#### S1.3 RQ3: links and protocols\n")
    L.append(
        "The link model was repaired one cited cause at a time and checked against published figures and closed forms (`docs/LINKSIM_STUDY.md` section 4.4). "
        "The LoRa time on air formula reproduces the published examples, but this is a weak check: only one of the four examples states every parameter, and for the other three the unstated settings were chosen after the fact because they reproduce the published value. Fragment counts agree with an independent count and the duty cycle wait equals its formula, an arithmetic check; stop and wait retransmissions in the event simulation agree with their closed form within Monte Carlo intervals; selective repeat, which the protocol and mission studies use, was checked against its closed form in round 5, with the outcome in section 4.3. "
        "For IEEE 802.15.4, adding every cited cost (PHY header, 6LoWPAN fragment headers and alignment, acknowledgements, inter frame spacing, clear channel assessment and backoff, turnaround) "
        f"takes a 50 kB transfer from {claim('d_base', dg, 'time_s_modelled_after', 'step == \"0\"', fmt='{:.1f}', label='modelled')} s to "
        f"{claim('d_final', dg, 'time_s_modelled_after', 'step == \"6\"', fmt='{:.1f}', label='modelled')} s, which is still "
        f"{claim('d_factor', dg, 'factor_below_low_after', 'step == \"6\"', fmt='{:.1f}', label='modelled')} times faster than the published 30 to 60 s. "
        "Most of that gap is unexplained by single hop costs in the link model; the round 5 ns-3 runs (section 4.3) find settings that close it, none of which the source states, so the model is reported as optimistic on 802.15.4 networks. "
        "The rate part was checked against one published table of handshakes over an emulated link, with one constant fitted on two of its rows; that is a weak test on one testbed.\n")
    pg = "linksim/results/protocols_grid.csv"
    if exists(pg):
        L.append("The protocol simulation (1000 seeded trials per cell, `docs/PROTOCOL_SIM.md`) gives the time to the first authenticated message. "
                 "On a telemetry radio and on 802.15.4, a hybrid session handshake completes in about one to two seconds; on LoRaWAN it takes minutes at DR5 and hours at DR0, because of the duty cycle. "
                 "Per message post quantum signatures overload the slower links.\n")
    # RQ4 boot
    vt = "bootchain/results/verify_time.csv"
    q = 'target == "Crazyflie 2.1 (STM32F405)" and image_bytes == 1000000 and scheme == "{s}" and hash == "{h}"'
    L.append("#### S1.4 RQ4: signed boot and update\n")
    _vt = pd.read_csv(ROOT / vt)
    _h = _vt[(_vt.target == "Crazyflie 2.1 (STM32F405)") & (_vt.image_bytes == 1000000) & (_vt.hash == "hardware HASH")]
    _hs = sorted(set(_h[_h.hash_ms_estimated >= _h.sig_ms_estimated * 0.95].scheme))
    hash_still = ", ".join(_hs[:-1]) + " and " + _hs[-1] if len(_hs) > 1 else "".join(_hs)
    L.append(
        "For a 1 MB image on a 168 MHz Cortex-M4 (the STM32F405 class of a small drone flight controller) with software SHA-256, verification takes about "
        f"{claim('b_mldsa_sw', vt, 'total_ms_estimated', q.format(s='ML-DSA-44', h='software SHA-256'), fmt='{:.0f}', label='estimated')} ms with ML-DSA-44 and "
        f"{claim('b_lms_sw', vt, 'total_ms_estimated', q.format(s='LMS', h='software SHA-256'), fmt='{:.0f}', label='estimated')} ms with LMS, of which hashing the image is "
        f"{claim('b_hash_sw', vt, 'hash_ms_estimated', q.format(s='LMS', h='software SHA-256'), fmt='{:.0f}', label='estimated')} ms. "
        f"With a hash peripheral, which the STM32F405 itself lacks (the rows are a what if for a part of that class with one), the totals fall to {claim('b_mldsa_hw', vt, 'total_ms_estimated', q.format(s='ML-DSA-44', h='hardware HASH'), fmt='{:.0f}', label='estimated')} ms and "
        f"{claim('b_lms_hw', vt, 'total_ms_estimated', q.format(s='LMS', h='hardware HASH'), fmt='{:.0f}', label='estimated')} ms; the signature then becomes the larger part for the slower verifiers, while for {hash_still} hashing still costs about as much as the signature or more. "
        "The choice of signature scheme changes boot time far less than image size and hash hardware do (`docs/BOOT_UPDATE_STUDY.md`). "
        "Against published bootloader timings the uncalibrated model is far off and the calibrated check rests on three rows, so these are estimates of order, not predictions. "
        "A fixed first stage root of trust that verifies only a classical signature cannot be changed by any of this; such devices need hardware replacement for signing migration.\n")
    # RQ5 fleets
    pm = "planner/results/profile_mc_summary.csv"
    L.append("#### S1.5 RQ5: fleet migration\n")
    L.append(
        f"The round 3 synthetic fleet is reproduced exactly ({claim('syn_lo', pm, 'median', 'fleet == \"synthetic\" and thresholds == \"stack_asm\"', fmt='{:.3f}', label='estimated')} to "
        f"{claim('syn_hi', pm, 'median', 'fleet == \"synthetic\" and thresholds == \"reference_c\"', fmt='{:.3f}', label='estimated')} of devices need hardware replacement). "
        f"On fleets drawn from nine real board classes, with every memory threshold drawn from published rows, the median share is "
        f"{claim('prof_med', pm, 'median', 'fleet == \"profile\" and thresholds == \"uncertain\"', fmt='{:.3f}', label='estimated')} "
        f"(2.5 to 97.5 percentile {claim('prof_lo', pm, 'p2_5', 'fleet == \"profile\" and thresholds == \"uncertain\"', fmt='{:.3f}', label='estimated')} to "
        f"{claim('prof_hi', pm, 'p97_5', 'fleet == \"profile\" and thresholds == \"uncertain\"', fmt='{:.3f}', label='estimated')}). "
        "These round 4 figures assumed the free memory a flight stack leaves. Round 5 measured it for seven board classes from real flight stack builds, and the replacement share rose (section 4.5 and `docs/FLIGHTSTACK_STUDY.md`); the round 4 statement that the share is close to 0.20 no longer holds. "
        f"Under the Mosca inequality with stated ranges, data lifetime has the largest total Sobol index ({claim('mosca_st', 'planner/results/mosca_sobol.csv', 'ST', 'input == \"data_lifetime_years\"', fmt='{:.2f}', label='modelled')}), largely because its range is the widest. "
        "Policy dates come from primary texts (`docs/POLICY_TIMELINE.md`); the supplied UAE policy texts give no post quantum date.\n")
    # RQ6 mission
    mb = "mission/results/base.csv"
    qm = 'vehicle == "{v}" and arch == "{a}" and link == "{l}"'
    L.append("#### S1.6 RQ6: mission level design\n")
    L.append(
        "In the mission simulation (1000 runs per configuration, `docs/MISSION_STUDY.md`), a classical session, a hybrid session and hash signed firmware with session keys keep the drone's control link available "
        f"about as often as an unauthenticated stream on a telemetry radio (mean over runs {claim('m_b_sik', mb, 'avail_mean', qm.format(v='drone', a='B', l='sik'), fmt='{:.3f}', label='estimated')} for the hybrid session; estimated): within the assumed outage ranges, link outages rather than authentication set availability. "
        f"A post quantum signature on every command adds about {claim('m_c_lat', mb, 'added_latency_ms_median', qm.format(v='drone', a='C', l='sik'), fmt='{:.0f}', label='estimated')} ms per command on that radio (estimated), "
        f"lowers availability to {claim('m_c_sik', mb, 'avail_mean', qm.format(v='drone', a='C', l='sik'), fmt='{:.3f}', label='estimated')}, and overloads the link for a ground robot streaming commands at 5 Hz "
        f"(utilisation {claim('m_c_rob', mb, 'utilisation_median', qm.format(v='robot', a='C', l='sik'), fmt='{:.2f}', label='estimated')}). "
        "LoRaWAN carries none of the command streams within its duty cycle. The resulting reference architecture (`docs/REFERENCE_ARCHITECTURE.md`): hash based signatures (LMS) for firmware, "
        "a hybrid key establishment followed by a symmetric MAC session for commands on telemetry class links or faster, and no per command signatures on streamed commands.\n")
    return "\n".join(L)


def cycle_model_text():
    es = "cyclemodel/results/error_summary.csv"
    q = 'model == "{m}" and subset == "{s}"'
    ex = "cyclemodel/results/external_check.csv"
    return (
        "Prediction without a board. A trace driven model counts executed instructions by class in the pinned pqm4 code (emulated) and maps them to cycles (modelled; `docs/CYCLE_MODEL.md`). "
        "Fitted on half of the matched published rows and tested on the other half, split by binary so that no test row shares a binary with a training row, its median absolute error is "
        f"{claim('cm_med', es, 'median_abs_pct', q.format(m='fitted', s='test, all'), fmt='{:.1f}', label='modelled')} percent "
        f"(95 percent interval {claim('cm_lo', es, 'median_abs_ci_lo', q.format(m='fitted', s='test, all'), fmt='{:.1f}', label='modelled')} to "
        f"{claim('cm_hi', es, 'median_abs_ci_hi', q.format(m='fitted', s='test, all'), fmt='{:.1f}', label='modelled')}, a row bootstrap; the cluster bootstrap of round 5 gives almost the same interval, section 4.1) on "
        f"{claim('cm_n', es, 'n', q.format(m='fitted', s='test, all'), fmt='{:.0f}', label='modelled')} held out rows, and "
        f"{claim('cm_nosign', es, 'median_abs_pct', q.format(m='fitted', s='test, excluding sign'), fmt='{:.1f}', label='modelled')} percent without signing; "
        f"signing misses by up to {claim('cm_worst', es, 'worst_abs_pct', q.format(m='fitted', s='test, all'), fmt='{:.1f}', label='modelled')} percent because its cost varies from message to message. "
        "The two halves share algorithms and much code (for example the same parameter set in two assembly variants), so this is a test of interpolation within one code base, not of transfer to new code. "
        "Without fitting, a model built from assumed per instruction costs is "
        f"{claim('cm_apriori', es, 'median_signed_pct', q.format(m='apriori', s='test, all'), fmt='{:.1f}', label='modelled')} percent high at the median. "
        f"Applied without refitting to an independent low memory library, key generation lands {claim('cm_ext_lo', ex, 'err_pct_fitted', '', 'min', '{:.1f}', label='modelled')} to "
        f"{claim('cm_ext_hi', ex, 'err_pct_fitted', '', 'max', '{:.1f}', label='modelled')} percent above its published Cortex-M33 values, a weak check because core, memory system and compiler all differ. "
        "The model's predictions for the first board session are registered with intervals in `docs/PREDICTIONS_V4_BOARD.md`.")


def rtl_text():
    rt = "rtlsim/results/ibex_cycles.csv"
    q = 'statistic == "median" and parameter_set == "{p}" and operation == "{o}"'
    d = pd.read_csv(ROOT / rt)
    have = set(zip(d.parameter_set, d.operation))
    parts = []
    for ps, op in (("ML-KEM-768", "decaps"), ("ML-KEM-512", "decaps"), ("ML-DSA-44", "verify"), ("ML-DSA-44", "sign")):
        if (ps, op) in have:
            parts.append(f"{ps} {op} {claim('rtl_' + ps + op, rt, 'cycles', q.format(p=ps, o=op), label='RTL simulated')} cycles")
    return ("Cycle accurate simulation of an open source core. The portable C code of mlkem-native and mldsa-native was run on a cycle accurate simulation of the open source Ibex RV32IMC core (small configuration, memory without wait states; RTL simulated, `docs/RTL_SIM_RESULTS.md`): "
            + "; ".join(parts) + " (signing is the median of five messages and varies several fold). These are measurements of a core design in simulation, not of Arm silicon. "
            f"They are {claim('rtl_ratio_lo', 'rtlsim/results/ibex_vs_cortex_m4.csv', 'ratio_to_clean', '', 'min', '{:.2f}', label='RTL simulated')} to "
            f"{claim('rtl_ratio_hi', 'rtlsim/results/ibex_vs_cortex_m4.csv', 'ratio_to_clean', '', 'max', '{:.2f}', label='RTL simulated')} times the published portable C rows for the Cortex-M4 "
            "(different library, compiler, instruction set and statistic, so only the order of magnitude is compared) and give a microcontroller class reference that no vendor setting can change.")


def q(**kw):
    """Build a pandas query of equalities from keyword arguments (strings quoted, numbers bare)."""
    return " and ".join(f'{k} == "{v}"' if isinstance(v, str) else f"{k} == {v}" for k, v in kw.items())


def rq_text():
    """Short answer per research question for the six page main paper: answer, uncertainty, label."""
    L = []
    # RQ1 -------------------------------------------------------------------------------------
    cb, lo = "stats/results/cycle_cluster_bootstrap.csv", "stats/results/cycle_lofo_summary.csv"
    hv, cs = "data/meta/hierarchical_variance.csv", "rtlsim/results/core_spread.csv"
    held = q(model="fitted", subset="test, all")
    pooled = 'left_out_by == "{g}" and group == "all groups pooled" and model == "{m}"'
    main_fit = 'weighting == "unweighted" and fit == "main (variant as stated)" and component == "{c}"'
    worst_fit = 'weighting == "unweighted" and fit == "worst observed rows excluded: main (variant as stated)" and component == "{c}"'
    L.append("### 4.1 RQ1: compute cost and its prediction\n")
    L.append(
        "Answer. Within the pqm4 code base, cycles can be predicted without a board to within a few percent, but the fitted model does not transfer to a scheme it has not seen, and published figures for one operation spread with the statistic, compiler and implementation variant they report; compiler and statistic take most of the variance in the main fit, with intervals from zero to most of it, while without the few rows that report a worst observed value the compiler share falls and statistic and implementation variant take similar shares, so no single factor is established. "
        f"Fitted on half of the matched published rows and tested on the other half (split by binary), the cycle model's median absolute error is {claim('p_cm_med', cb, 'median_abs_pct', held, fmt='{:.1f}', label='modelled')} percent; "
        f"a cluster bootstrap by binary gives {claim('p_cm_lo', cb, 'median_abs_cluster_ci_lo', held, fmt='{:.1f}', label='modelled')} to {claim('p_cm_hi', cb, 'median_abs_cluster_ci_hi', held, fmt='{:.1f}', label='modelled')} percent, almost the round 4 interval, "
        f"but the board prediction intervals widen by a factor of {claim('p_cm_width', 'stats/results/cycle_board_predictions_cluster.csv', 'width_ratio_cluster_to_round4', '', 'median', '{:.2f}', label='modelled')} when computed by cluster; the registered board predictions keep the round 4 envelope intervals, and the cluster intervals are given for information only. "
        f"Leaving out a whole implementation family gives {claim('p_lofo_fam', lo, 'median_abs_pct', pooled.format(g='implementation family', m='fitted'), fmt='{:.1f}', label='modelled')} percent, and leaving out a whole scheme "
        f"{claim('p_lofo_scheme', lo, 'median_abs_pct', pooled.format(g='scheme', m='fitted'), fmt='{:.1f}', label='modelled')} percent (cluster interval {claim('p_lofo_scheme_lo', lo, 'median_abs_cluster_ci_lo', pooled.format(g='scheme', m='fitted'), fmt='{:.1f}', label='modelled')} to "
        f"{claim('p_lofo_scheme_hi', lo, 'median_abs_cluster_ci_hi', pooled.format(g='scheme', m='fitted'), fmt='{:.1f}', label='modelled')}, worst {claim('p_lofo_scheme_worst', lo, 'worst_abs_pct', pooled.format(g='scheme', m='fitted'), fmt='{:.1f}', label='modelled')}); "
        f"a reduced four feature model transfers better ({claim('p_lofo_scheme_red', lo, 'median_abs_pct', pooled.format(g='scheme', m='reduced'), fmt='{:.1f}', label='modelled')} percent). Figure 1 shows all five designs. "
        "Signing remains the hardest operation because its cost varies from message to message. Evidence: modelled, from emulated instruction traces and published cycle counts.\n")
    L.append("![Median absolute error of the cycle model on rows the fit did not see, by validation design, with cluster bootstrap 95 percent intervals (modelled). "
             "Source: `stats/results/cycle_cluster_bootstrap.csv` and `stats/results/cycle_lofo_summary.csv`.](figures/paper/fig1_cycle_model_errors.png){width=100%}\n")
    L.append(
        "A hierarchical model of the published cycle counts (crossed random effects for implementation variant, statistic, compiler and source) attributes "
        f"{claim('p_hm_stat', hv, 'share_within_cell', main_fit.format(c='statistic'), fmt='{:.1f}', scale=100, label='modelled')} percent of the within cell variance to the statistic and "
        f"{claim('p_hm_comp', hv, 'share_within_cell', main_fit.format(c='compiler'), fmt='{:.1f}', scale=100, label='modelled')} percent to the compiler, but both intervals are wide and the fit is driven by the few rows that report a worst observed signing value: without them, "
        f"the residual standard deviation falls from {claim('p_hm_res', hv, 'sd_log', main_fit.format(c='residual'), fmt='{:.2f}', label='modelled')} to "
        f"{claim('p_hm_res_x', hv, 'sd_log', worst_fit.format(c='residual'), fmt='{:.2f}', label='modelled')} in log cycles and the variant share rises from "
        f"{claim('p_hm_var', hv, 'share_within_cell', main_fit.format(c='variant'), fmt='{:.1f}', scale=100, label='modelled')} to "
        f"{claim('p_hm_var_x', hv, 'share_within_cell', worst_fit.format(c='variant'), fmt='{:.1f}', scale=100, label='modelled')} percent. Both fits are reported; neither is the single truth. "
        "As a reference that no vendor setting can change, the portable C code of mlkem-native and mldsa-native ran on cycle accurate simulations of two open RV32IMC cores (RTL simulated): "
        f"ML-KEM-768 decapsulation takes {claim('p_rtl_ibex', cs, 'cycles_median_ibex', q(parameter_set='ML-KEM-768', operation='decaps'), label='RTL simulated')} cycles on Ibex and "
        f"{claim('p_rtl_cv', cs, 'cycles_median_cv32e40p', q(parameter_set='ML-KEM-768', operation='decaps'), label='RTL simulated')} on CV32E40P, which is the faster core in "
        f"{claim('p_rtl_nfast', cs, 'fastest_core', 'fastest_core == \"cv32e40p\"', 'count', '{:.0f}', label='RTL simulated')} of {claim('p_rtl_n', cs, 'fastest_core', '', 'count', '{:.0f}', label='RTL simulated')} operations, by a factor of "
        f"{claim('p_rtl_lo', cs, 'max_over_min', '', 'min', '{:.2f}', label='RTL simulated')} to {claim('p_rtl_hi', cs, 'max_over_min', '', 'max', '{:.2f}', label='RTL simulated')}. "
        "These are simulations of core designs with memory without wait states, not measurements of silicon.\n")
    # RQ2 -------------------------------------------------------------------------------------
    er, e2 = "energy/results/max_rates.csv", "stats/results/e2e_mc_summary.csv"
    sob = "stats/results/e2e_sobol.csv"
    cf = 'target == "Crazyflie 2.1" and design == "{d}"'
    L.append("### 4.2 RQ2: energy and CPU headroom\n")
    L.append(
        "Answer. CPU time, not battery energy, is the binding budget. "
        f"At 20 percent CPU headroom a 168 MHz Cortex-M4 flight controller can verify about {claim('p_rate_mldsa', er, 'msgs_per_s_at_20pct_estimated', cf.format(d='ML-DSA-44'), fmt='{:.1f}', label='estimated')} ML-DSA-44 signatures per second against about "
        f"{claim('p_rate_mac', er, 'msgs_per_s_at_20pct_estimated', cf.format(d='HMAC-SHA256 session'), fmt='{:,.0f}', label='estimated')} messages under a symmetric MAC session (estimated). "
        f"Verifying a 1 MB firmware image costs a median of {claim('p_fw_mj', e2, 'median', 'output == \"firmware_verify_1mb_energy_mj\"', fmt='{:.1f}', label='modelled')} mJ "
        f"(2.5 to 97.5 percentile {claim('p_fw_mj_lo', e2, 'p2_5', 'output == \"firmware_verify_1mb_energy_mj\"', fmt='{:.1f}', label='modelled')} to {claim('p_fw_mj_hi', e2, 'p97_5', 'output == \"firmware_verify_1mb_energy_mj\"', fmt='{:.1f}', label='modelled')}) in the end to end chain, "
        f"and the datasheet current per MHz carries most of that range (total Sobol index {claim('p_sob_ua', sob, 'ST', 'output == \"firmware_verify_1mb_energy_mj\" and input == \"ua_per_mhz\"', fmt='{:.2f}', label='modelled')}). "
        f"Calibrated on one board and one source, published energy is {claim('p_en_k', 'energy/results/validation_split.csv', 'ratio_published_over_estimated', 'set == \"calibration\"', 'median', '{:.2f}', label='modelled')} times the uncalibrated estimate, so absolute energies are likely low by a similar factor; rates depend only on cycles. Evidence: estimated and modelled.\n")
    # RQ3 -------------------------------------------------------------------------------------
    gs, sr = "netsim/results/gap_sweep.csv", "netsim/results/sr_closed_form.csv"
    cell = 'cell == "{c}"'
    pg = "linksim/results/protocols_grid.csv"
    hs = 'scenario == "ttfam" and variant == "hybrid" and protocol == "mavlink2_pq" and loss == 0.0 and link == "{l}"'
    L.append("### 4.3 RQ3: links and protocols\n")
    L.append(
        "Answer. On telemetry class radios a hybrid handshake costs seconds once per session; on IEEE 802.15.4 meshes, transfer times depend on settings that published figures do not state, and our link model is optimistic there. "
        f"The protocol simulation (1000 seeded trials per cell) gives a median time to the first authenticated command of {claim('p_hs_sik', pg, 'wall_median', hs.format(l='sik'), fmt='{:.2f}', label='modelled')} s for the MAVLink style hybrid profile on a telemetry radio without loss, "
        f"{claim('p_hs_154', pg, 'wall_median', hs.format(l='ieee802154'), fmt='{:.2f}', label='modelled')} s on one 802.15.4 hop and {claim('p_hs_dr5', pg, 'wall_median', hs.format(l='lora_dr5'), fmt='{:,.0f}', label='modelled')} s on LoRaWAN DR5, where the duty cycle dominates (modelled). "
        f"For a 50 kB transfer over one 802.15.4 hop with ns-3 3.48 defaults, ns-3 gives {claim('p_ns_base', gs, 'time_mean_s_simulated_network', cell.format(c='base_frame'), fmt='{:.2f}', label='simulated (network)')} s (simulated (network)) and linksim "
        f"{claim('p_ls_base', gs, 'time_s_modelled', cell.format(c='base_frame'), fmt='{:.2f}', label='modelled')} s (modelled), against a published "
        f"{claim('p_pub_lo', gs, 'range_low_s_published', cell.format(c='base_frame'), fmt='{:.0f}', label='published')} to {claim('p_pub_hi', gs, 'range_high_s_published', cell.format(c='base_frame'), fmt='{:.0f}', label='published')} s. "
        f"Three changes each bring the ns-3 mean into that range (Figure 2): a minimum and maximum backoff exponent of 8, allowed by the cited standard ({claim('p_ns_be8', gs, 'time_mean_s_simulated_network', cell.format(c='minbe_8'), fmt='{:.1f}', label='simulated (network)')} s); "
        f"3 hops ({claim('p_ns_h3', gs, 'time_mean_s_simulated_network', cell.format(c='hops_3'), fmt='{:.1f}', label='simulated (network)')} s); or 16 neighbours sending, where only the mean reaches the range and its interval extends below it ({claim('p_ns_bg16', gs, 'time_mean_s_simulated_network', cell.format(c='bg_16'), fmt='{:.1f}', label='simulated (network)')} s). "
        "The source states none of these settings, so they are sufficient causes in simulation, not the proven cause. "
        f"ns-3 also shows that linksim's store and forward over hops is optimistic: at 3 hops linksim gives {claim('p_ls_h3', gs, 'time_s_modelled', cell.format(c='hops_3'), fmt='{:.1f}', label='modelled')} s against {claim('p_ns_h3b', gs, 'time_mean_s_simulated_network', cell.format(c='hops_3'), fmt='{:.1f}', label='simulated (network)')} s in ns-3, because frames of different hops contend, which linksim does not model. "
        f"Of {claim('p_ns_runs', 'netsim/results/lrwpan_runs.csv', 'completed', '', 'count', '{:.0f}', label='simulated (network)')} ns-3 runs, {claim('p_ns_stuck', 'netsim/results/lrwpan_runs.csv', 'completed', 'completed == 0', 'count', '{:.0f}', label='simulated (network)')} did not complete and are excluded from the verdict. "
        f"The selective repeat check against the closed form 1/(1-P), on its first registered run, placed {claim('p_sr_in', sr, 'inside', 'role == \"pre set check\" and inside == True', 'count', '{:.0f}', label='modelled')} of "
        f"{claim('p_sr_n', sr, 'inside', 'role == \"pre set check\"', 'count', '{:.0f}', label='modelled')} loss rates inside their 95 percent interval; the miss at P = 0.3 did not recur in ten follow up seed blocks added afterwards and labelled as such.\n")
    L.append("![Time to transfer 50 kB over IEEE 802.15.4 for one hop with defaults and for each single cause that reaches the published range: linksim (modelled) beside ns-3 (simulated (network), mean and 95 percent interval), with the published range shaded. "
             "Source: `netsim/results/gap_sweep.csv`.](figures/paper/fig2_lrwpan_causes.png){width=100%}\n")
    # RQ4 -------------------------------------------------------------------------------------
    vt = "bootchain/results/verify_time.csv"
    qb = 'target == "Crazyflie 2.1 (STM32F405)" and image_bytes == 1000000 and scheme == "{s}" and hash == "{h}"'
    L.append("### 4.4 RQ4: signed boot and update\n")
    L.append(
        "Answer. For firmware, the signature scheme matters less than image size and hash hardware, and a version counter is required. "
        f"For a 1 MB image on a 168 MHz Cortex-M4 with software SHA-256, verification takes about {claim('p_b_mldsa', vt, 'total_ms_estimated', qb.format(s='ML-DSA-44', h='software SHA-256'), fmt='{:.0f}', label='estimated')} ms with ML-DSA-44 and "
        f"{claim('p_b_lms', vt, 'total_ms_estimated', qb.format(s='LMS', h='software SHA-256'), fmt='{:.0f}', label='estimated')} ms with LMS, of which hashing is {claim('p_b_hash', vt, 'hash_ms_estimated', qb.format(s='LMS', h='software SHA-256'), fmt='{:.0f}', label='estimated')} ms (estimated). "
        f"Across the end to end ranges the median is {claim('p_fw_ms', e2, 'median', 'output == \"firmware_verify_1mb_ms\"', fmt='{:.0f}', label='modelled')} ms "
        f"({claim('p_fw_ms_lo', e2, 'p2_5', 'output == \"firmware_verify_1mb_ms\"', fmt='{:.0f}', label='modelled')} to {claim('p_fw_ms_hi', e2, 'p97_5', 'output == \"firmware_verify_1mb_ms\"', fmt='{:.0f}', label='modelled')}), "
        f"ranked by clock (total Sobol index {claim('p_sob_clk', sob, 'ST', 'output == \"firmware_verify_1mb_ms\" and input == \"clock_mhz\"', fmt='{:.2f}', label='modelled')}) and hash cost per byte "
        f"({claim('p_sob_cpb', sob, 'ST', 'output == \"firmware_verify_1mb_ms\" and input == \"sha256_cpb\"', fmt='{:.2f}', label='modelled')}); the implementation factor of the signature does not register. "
        "Against published bootloader timings the calibrated check rests on three rows, so these are estimates of order. Formal verification (Section 4.6) found that a signature without a signed version and a monotonic counter accepts a downgrade (F3). "
        "A fixed first stage that verifies only a classical signature cannot be migrated; such devices need hardware replacement for signing migration.\n")
    # RQ5 -------------------------------------------------------------------------------------
    fm, fs = "data/flightstack_memory.csv", "planner/results/flightstack_mc_summary.csv"
    L.append("### 4.5 RQ5: fleet migration\n")
    L.append(
        "Answer, a correction of round 4. With measured flight stack memory, a larger share of devices needs hardware replacement than round 4 reported. "
        f"Default builds of PX4 v1.17.0 and ArduPilot Copter-4.7.2 succeeded for {claim('p_fs_builds', fm, 'build_status', 'build_status == \"built\"', 'count', '{:.0f}', label='host measured')} targets on "
        f"{claim('p_fs_boards', fs, 'measured_boards', 'thresholds == \"uncertain\"', fmt='{:.0f}', label='estimated')} board classes (host measured from linker output); PX4 leaves as little as "
        f"{claim('p_fs_minfree', fm, 'flash_free_bytes', 'stack == \"px4\"', 'min', '{:,.0f}', label='host measured')} B of flash free. "
        f"With these values in place of the round 4 assumption, the median share needing hardware replacement rises from {claim('p_fl_a_stack', fs, 'assumed_median', 'thresholds == \"stack_asm\"', fmt='{:.3f}', label='estimated')} to "
        f"{claim('p_fl_m_stack', fs, 'measured_median', 'thresholds == \"stack_asm\"', fmt='{:.3f}', label='estimated')} under stack optimised thresholds and from "
        f"{claim('p_fl_a_unc', fs, 'assumed_median', 'thresholds == \"uncertain\"', fmt='{:.3f}', label='estimated')} to {claim('p_fl_m_unc', fs, 'measured_median', 'thresholds == \"uncertain\"', fmt='{:.3f}', label='estimated')} "
        f"(bootstrap interval of the median {claim('p_fl_m_unc_lo', fs, 'measured_ci_low', 'thresholds == \"uncertain\"', fmt='{:.3f}', label='estimated')} to {claim('p_fl_m_unc_hi', fs, 'measured_ci_high', 'thresholds == \"uncertain\"', fmt='{:.3f}', label='estimated')}; it describes the median, not the spread of the share across draws) "
        f"under thresholds drawn from published rows (Figure 3). Round 4's statement that the share stays near one fifth no longer holds. Using the larger of the two stacks' free memory per board, the uncertain scenario gives "
        f"{claim('p_fl_large', fs, 'larger_stack_median', 'thresholds == \"uncertain\"', fmt='{:.3f}', label='estimated')}. On the ArduPilot builds almost all of the flash counted as free is the crash log area that ArduPilot places in unused flash; code placed there removes crash logging. Counting that area as used raises the uncertain scenario to "
        f"{claim('p_fl_crash', fs, 'crash_log_used_median', 'thresholds == \"uncertain\"', fmt='{:.3f}', label='estimated')} and the stack optimised one to {claim('p_fl_crash_st', fs, 'crash_log_used_median', 'thresholds == \"stack_asm\"', fmt='{:.3f}', label='estimated')}, so the figures above are the smaller end of the correction. Free RAM is an upper bound because heap use at run time is not visible in a build. Evidence: estimated, from host measured memory.\n")
    L.append("![Share of fleet devices that need hardware replacement, median over 200 draws with a bootstrap interval of the median, under the round 4 assumed free memory and with measured flight stack memory for seven boards (estimated). "
             "Source: `planner/results/flightstack_mc_summary.csv`.](figures/paper/fig3_fleet_replacement.png){width=100%}\n")
    # RQ6 -------------------------------------------------------------------------------------
    pv, mb = "formal/results/proverif_results.csv", "mission/results/base.csv"
    qm = 'vehicle == "{v}" and arch == "{a}" and link == "{l}"'
    L.append("### 4.6 RQ6: a feasible architecture\n")
    L.append(
        "Answer. Hash based signatures (LMS) with a signed version and a monotonic counter for firmware; a hybrid key establishment in which both sides sign, followed by a symmetric MAC session, for commands on telemetry class links or faster; and no per command signatures on streamed commands. "
        f"In the mission simulation (1000 runs per configuration) the hybrid session keeps the drone's command link available about as often as an unauthenticated stream on a telemetry radio (mean {claim('p_m_b', mb, 'avail_mean', qm.format(v='drone', a='B', l='sik'), fmt='{:.3f}', label='estimated')} against "
        f"{claim('p_m_b_base', mb, 'avail_base_mean_0.5', qm.format(v='drone', a='B', l='sik'), fmt='{:.3f}', label='estimated')} without authentication, at a 0.5 s deadline), modelled under the published MAVLink replay rule with gaps allowed, not under the strict next sequence rule that the proofs use and the reference architecture adopts provisionally, whose availability is not modelled; "
        f"while a post quantum signature on every command adds about {claim('p_m_c_lat', mb, 'added_latency_ms_median', qm.format(v='drone', a='C', l='sik'), fmt='{:.0f}', label='estimated')} ms per command and lowers availability to "
        f"{claim('p_m_c', mb, 'avail_mean', qm.format(v='drone', a='C', l='sik'), fmt='{:.3f}', label='estimated')} (estimated). Across the end to end ranges the hybrid availability has median "
        f"{claim('p_e2e_av', e2, 'median', 'output == \"hybrid_availability_sik_drone\"', fmt='{:.3f}', label='modelled')} ({claim('p_e2e_av_lo', e2, 'p2_5', 'output == \"hybrid_availability_sik_drone\"', fmt='{:.3f}', label='modelled')} to "
        f"{claim('p_e2e_av_hi', e2, 'p97_5', 'output == \"hybrid_availability_sik_drone\"', fmt='{:.3f}', label='modelled')}), and the outage rate and mean outage length rank first and second (total Sobol indices "
        f"{claim('p_sob_or', sob, 'ST', 'output == \"hybrid_availability_sik_drone\" and input == \"outage_rate_per_h\"', fmt='{:.2f}', label='modelled')} and "
        f"{claim('p_sob_om', sob, 'ST', 'output == \"hybrid_availability_sik_drone\" and input == \"outage_mean_s\"', fmt='{:.2f}', label='modelled')}). Within the assumed outage ranges and with message sizes held fixed, outages rather than cryptography dominate the variation of availability; the ranking reflects those assumed ranges. Evidence: estimated (mission) and modelled (end to end chain).\n")
    L.append(
        f"ProVerif 2.05 checked {claim('p_pv_q', pv, 'property_id', '', 'count', '{:.0f}', label='modelled')} queries in {claim('p_pv_m', pv, 'model', '', 'nunique', '{:.0f}', label='modelled')} models of the stated designs, the changed designs and deliberate controls (Table 1). "
        "Three findings changed the design and were adopted in the reference architecture: in the stated session only the ground station signs, so the vehicle is not authenticated to it (F1; fixed by a vehicle ML-DSA-44 signature over the transcript and key confirmation, which adds a fourth flight to the handshake); "
        "the provisioned key fallback accepts a recorded command again after a power cycle (F2; fixed by deriving a session key from fresh nonces); and firmware without a signed version and counter accepts a downgrade (F3). "
        "The fallback's lack of forward secrecy is inherent and documented. These are results under the Dolev Yao model with abstract primitives, not statements about an implementation. Evidence: modelled.\n")
    L.append(formal_table() + "\n")
    L.append(
        "Board experiment. A board kit builds images for an STM32L4R5 (Cortex-M4) and an STM32L552 (Cortex-M33) board, now with an option that switches the caches off; "
        f"{claim('p_bk_n', 'bench/board_kit/predictions_v5_board.csv', 'id', 'cache_pass == \"off\"', 'count', '{:.0f}', label='modelled')} cycle predictions for the caches off pass were registered before any session, all out of sample (planned). "
        "The option is checked only by disassembly of the images and, for the L552, an emulator that logs the register write but does not model a cache, and the Cortex-M33 rows apply Cortex-M4 costs, an unsourced transfer assumption.\n")
    ss, sc, cm = "sitl/results/summary.csv", "sitl/results/comparison.csv", "sitl/results/commands.csv"
    qs = 'profile == "sik" and config == "{c}" and metric == "{m}"'
    qc = 'profile == "sik" and config == "{c}" and metric == "{m}"'
    L.append("### 4.7 Software in the loop\n")
    L.append(
        "ArduPilot Copter 4.7.2 ran in software in the loop with its built in vehicle model, behind a relay that emulates a SiK class link with frame loss and one outage per mission, and a ground station script that sent a stream of acknowledged commands (`docs/SITL_STUDY.md`). "
        "PX4 v1.17.0 was not used because its MAVLink module has no message signing to serve as the classical baseline. "
        f"Each of four configurations flew {claim('p_sitl_n', ss, 'value', qs.format(c='hybrid', m='missions_completed'), fmt='{:.0f}', label='SITL measured')} scripted missions with stored seeds. "
        f"With the link up, MAVLink 2 signing as the flight stack ships it added {claim('p_sitl_sig', ss, 'value', qs.format(c='signing', m='added_latency_rt_ms'), fmt='{:.1f}', label='SITL measured')} ms to the median command round trip and the hybrid session with design change F1 "
        f"{claim('p_sitl_hyb', ss, 'value', qs.format(c='hybrid', m='added_latency_rt_ms'), fmt='{:.1f}', label='SITL measured')} ms (SITL measured). The one way added latency of the hybrid session, "
        f"{claim('p_sitl_hyb_ow', ss, 'value', qs.format(c='hybrid', m='added_latency_ow_ms'), fmt='{:.2f}', label='emulated')} ms (emulated by the relay with the mission study's own inputs, so a consistency check of the relay, not a test of the model), equals the mission study's "
        f"{claim('p_sitl_hyb_st', sc, 'study_estimated', qc.format(c='hybrid', m='added_latency_ow_ms'), fmt='{:.2f}', label='estimated')} ms. "
        f"The emulated hybrid handshake of four flights took {claim('p_sitl_hs', ss, 'value', qs.format(c='hybrid', m='handshake_median_s'), fmt='{:.2f}', label='emulated')} s against "
        f"{claim('p_sitl_hs_st', sc, 'study_estimated', 'profile == \"sik\" and config == \"hybrid\" and study_arch == \"B with F1\" and metric == \"handshake_median_s\"', fmt='{:.2f}', label='estimated')} s when the mission handshake model is applied to the flight sizes and compute of this configuration (the mission study's own first session time is "
        f"{claim('p_sitl_hs_ms', sc, 'study_estimated', 'profile == "sik" and config == "hybrid" and study_arch == "B" and metric == "handshake_median_s"', fmt='{:.2f}', label='estimated')} s). "
        f"With outages, the share of commands acknowledged within 0.5 s was {claim('p_sitl_av_hyb', ss, 'value', qs.format(c='hybrid', m='availability_rt_all'), fmt='{:.3f}', label='SITL measured')} for the hybrid session against "
        f"{claim('p_sitl_av_hyb_st', sc, 'study_estimated', qc.format(c='hybrid', m='availability_rt_all'), fmt='{:.3f}', label='estimated')} in the mission study at the nearest point of its outage rate sweep; one outage per short flight is a higher rate than that point, and the share of flight time in outage differs between configurations because each draws its own outages, so differences between configurations of a few hundredths are not resolved. The relay of the hybrid configuration enforced no replay rule, so this figure is not the availability of the recommended design with its sequence rule. "
        f"A post quantum signature on every command added {claim('p_sitl_pq_ow', ss, 'value', qs.format(c='pqsig', m='added_latency_ow_ms'), fmt='{:.0f}', label='emulated')} ms one way (emulated), as the mission study predicts "
        f"({claim('p_sitl_pq_st', sc, 'study_estimated', qc.format(c='pqsig', m='added_latency_ow_ms'), fmt='{:.0f}', label='estimated')} ms), but "
        f"{claim('p_sitl_pq_rt', ss, 'value', qs.format(c='pqsig', m='added_latency_rt_ms'), fmt='{:.0f}', label='SITL measured')} ms on the round trip to the acknowledgement, and only "
        f"{claim('p_sitl_pq_av', ss, 'value', qs.format(c='pqsig', m='availability_rt_all'), fmt='{:.3f}', label='SITL measured')} of its commands were acknowledged within 0.5 s, against "
        f"{claim('p_sitl_pq_av_st', sc, 'study_estimated', qc.format(c='pqsig', m='availability_rt_all'), fmt='{:.3f}', label='estimated')} in the mission study, which counts one way delivery: the deadline falls in the tail of a delivery of several hundred milliseconds. "
        f"In the configuration with MAVLink 2 signing as shipped, the flight stack discarded {claim('p_sitl_drop', cm, 'dropped', 'config == \"signing\" and dropped == \"not_acknowledged_by_vehicle\"', 'count', '{:.0f}', label='SITL measured')} delivered signed commands, because the emulated link layer's retransmission let a frame arrive after a newer one and fail the signing timestamp rule, an effect the mission study does not model. The strict next sequence rule that the formal proofs use would reject such frames too, and every frame after a lost one, so a deployment needs in order delivery below the session layer or a replay window that the proofs do not yet cover; this is an open design question, not a result in favour of either rule. "
        "The hybrid session and the signature per command add the bytes and published compute delays on the link rather than executing cryptography, and the link is an emulation, not a radio. The added round trip latencies are about twice the emulated one way delays, because the flight stack handles the same frames in every configuration, so they too check the relay rather than the model; the parts that test the mission model are the acknowledged shares with outages and the discarded commands. Evidence: SITL measured for round trips through the flight stack; emulated for one way and handshake figures; against the mission study (estimated).\n")
    return "\n".join(L)


def formal_table():
    pv = "formal/results/proverif_results.csv"
    rows = [("proved", "property holds for every run the model allows: unbounded sessions for the command channel, one command per key before a rekey in the round 5 models and three or four per key in the replay rule models; the firmware model is bounded to three releases and three boots per device"),
            ("counterexample", f"attack trace found: {claim('p_pv_cx_reach', pv, 'result', 'result == \"counterexample\" and property_id.str.startswith(\"R\")', 'count', '{:.0f}', label='modelled')} reachability checks that must fail (a command or a session key can be accepted, and a window accepts commands out of order); "
             f"{claim('p_pv_cx_broken', pv, 'result', 'result == \"counterexample\" and not property_id.str.startswith(\"R\") and model.str.contains(\"broken|static_known\") and not model.str.startswith(\"session_replay\")', 'count', '{:.0f}', label='modelled')} in settings with a broken component (both components, ML-KEM alone for design K, ML-DSA-44, or the static keys of design K known); "
             f"{claim('p_pv_cx_stated', pv, 'result', 'result == \"counterexample\" and not property_id.str.startswith(\"R\") and model.str.contains(\"stated\") and not model.str.contains(\"broken\")', 'count', '{:.0f}', label='modelled')} in the stated designs (findings F1 to F3); "
             f"{claim('p_pv_cx_fs', pv, 'result', 'result == \"counterexample\" and model == \"fallback_d_fixed_fs_provisioned\"', 'count', '{:.0f}', label='modelled')} for forward secrecy of the provisioned key fallback (inherent, documented); "
             f"{claim('p_pv_cx_mid', pv, 'result', 'result == \"counterexample\" and model == \"firmware_counter_unsigned_version\"', 'count', '{:.0f}', label='modelled')} for an intermediate firmware design with a counter but an unsigned version; and "
             f"{claim('p_pv_cx_replay', pv, 'result', 'result == \"counterexample\" and model.str.startswith(\"session_replay\") and not property_id.str.startswith(\"R\")', 'count', '{:.0f}', label='modelled')} in the replay rule controls (no seen counter check, and a table read by concurrent branches)"),
            ("cannot be proved", "MAVLink timestamp rule with gaps, and the replay window and sequential table encodings without the tool help (their weaker non injective forms hold), and "
             f"{claim('p_pv_to', pv, 'result', 'result.str.startswith(\"cannot be proved (timeout\")', 'count', '{:.0f}', label='modelled')} queries that reached the time limit: authentication in the general design K model (also in a retry of three hours), three queries in each model of design K with its static keys known, and C1 with ML-DSA-44 and ML-KEM broken")]
    t = ["Table 1. ProVerif results by outcome (modelled). Source: `formal/results/proverif_results.csv`.\n", "| Outcome | Queries | Meaning |", "|---|---|---|"]
    for r, meaning in rows:
        t.append(f"| {r} | {claim('p_pv_' + r.replace(' ', '_'), pv, 'result', f'result.str.startswith(\"{r}\")', 'count', '{:.0f}', label='modelled')} | {meaning} |")
    return "\n".join(t)


def threats_text():
    return (
        "1. Nothing was measured on a microcontroller. Every cycle, energy and timing figure is published, emulated, RTL simulated, simulated (network), estimated or modelled.\n"
        "2. The board kit's caches off option is untested on silicon: the emulator logs the register write but does not model a cache, and no free emulator models the STM32L4R5.\n"
        "3. The Cortex-M33 board predictions apply Cortex-M4 instruction costs, a transfer assumption without a source.\n"
        "4. The cycle model is fitted and tested within one code base; it does not transfer to an unseen scheme (Figure 1), and its external check on another library and core rests on few rows.\n"
        "5. The hierarchical meta analysis is driven by the few rows that report a worst observed value; statistic and compiler are confounded with source and have wide intervals, so both fits are reported.\n"
        "6. Flight logs could not be used: the PX4 log sites disallow automated access in their robots rules and no reuse licence was found, so mission traffic is synthetic.\n"
        "7. Free RAM after a flight stack build is an upper bound, since heap use at run time is not visible; fleet counts are synthetic, and one board definition states more flash than the reference profile.\n"
        "8. The ns-3 causes of the 802.15.4 gap are sufficient in simulation, not proven: the published figure states no hop count, load or backoff setting. Hop count, spacing and background traffic are assumptions, and ns-3 is a simulator, not a radio.\n"
        "9. The committed ns-3 runs used the earlier three flight handshake; the round 3 link study and its design notes still describe three flights. The mission, protocol, energy and end to end studies use the four flight handshake of finding F1.\n"
        "10. Energy rests on datasheet currents and one calibration source; the end to end chain ran 20 missions per evaluation, not 1000.\n"
        "11. Formal results hold under the Dolev Yao model with abstract perfect primitives, one identity per side, without the rekey grace period or the LMS signer state; they say nothing about an implementation.\n"
        "12. The match rules for the third look at wording disagreements were written after a first literal comparison was seen; ambiguous lines stay unsettled and are listed for the author.\n"
        "13. IEEE Xplore and the ACM Digital Library could not be searched (their search pages could not be fetched), and Semantic Scholar refused; the systematic search under covers those indexes.\n"
        "14. The selective repeat follow up blocks and the extra ns-3 runs were added after the first results; predictions are scored on the first, registered runs only.\n"
        "15. Software in the loop used one flight stack (ArduPilot), one link profile (SiK class) and one outage per mission; the hybrid session and the per command signature were emulated by their bytes and published compute delays, not executed, and a first set of runs with a timing defect was replaced by a rerun with the same seeds.\n"
        f"16. {claim('p_s12_fetch', 'data/evidence.csv', 'id', 'stream == \"S12\" and comparability_warning.fillna(\"\").str.contains(\"Read with web fetch\")', 'count', '{:.0f}', label='published')} round 4 rows were read through a web fetch that returns a summary of the page rather than the page itself; round 5 excludes such values (inclusion 4), but the round 4 rows were not held to that rule. They include the Cortex-M4 X25519 and Ed25519 baseline rows that the mission and energy studies use, so those classical figures are less certain than their labels suggest until the full texts are read.")


def conclusion_text():
    return (
        "On the links small drones and ground robots use, the cost of post quantum authentication is a one time handshake if the design uses a session (availability modelled under the published MAVLink replay rule; the cost of the stricter rule the proofs need is not yet modelled); on telemetry radios and 802.15.4, per command signatures are the option that fails, and on LoRaWAN no command stream fits the duty cycle. "
        "For firmware, hashing dominates unless the device has hash hardware, and a signed version with a counter is required. The fleet answer is set by how much memory the flight stack leaves free, and measuring it raised the replacement share well above the round 4 estimate. "
        "A cycle model predicts within a code base but not across schemes, so migration decisions should rest on a measurement of the deployed code; the registered board session is the next step and can refute the model.")


def method_reading():
    ev, v6 = "data/evidence.csv", "data/verify6"
    tl = "data/verify5/third_look_summary.csv"
    r4 = 'measure == "round 4 sample of 60: staging wrong after a third look (round 4 rule, any difference from the source)"'
    r5 = 'measure == "staged text contradicts the source, all settled lines (automatic test and manual decisions)"'
    verb = 'measure == "staged text differs verbatim from the source among settled lines"'
    vf = 'status == "disagree" and field in ["cycles", "ram_bytes", "stack_bytes", "flash_or_code_bytes", "energy_uj", "key_or_sig_size_bytes", "value"]'
    return (
        f"In this round a systematic search staged {claim('p_s13_staged', 'data/raw/S13_staged.csv', 'id', '', 'count', '{:.0f}', label='host measured')} rows (stream S13); two readers who saw neither the staged values nor each other's sheet read every row, "
        f"{claim('p_s13_valdis', v6 + '/summary.csv', 'field', vf, 'count', '{:.0f}', label='host measured')} value fields disagreed with staging, all "
        f"{claim('p_s13_word', v6 + '/third_look_queue.csv', 'id', 'kind == \"wording\"', 'count', '{:.0f}', label='host measured')} wording disagreements got a third look, and "
        f"{claim('p_s13_prom', ev, 'id', 'stream == \"S13\"', 'count', '{:.0f}', label='host measured')} rows were promoted (`docs/VERIFICATION6.md`); of the others, "
        f"{claim('p_s13_dem', v6 + '/not_promoted.csv', 'id', 'reason.str.startswith("demoted")', 'count', '{:.0f}', label='host measured')} were demoted after review because they broke a written inclusion or exclusion rule (`data/raw/S13_demoted.csv`) and "
        f"{claim('p_s13_single', v6 + '/not_promoted.csv', 'id', 'reason.str.startswith("single_reader")', 'count', '{:.0f}', label='host measured')} had a value field that fewer than two readers confirmed (in this round, no reader; `docs/VERIFICATION6.md`). "
        f"The {claim('p_tl_lines', tl, 'of', 'measure == \"lines staging_right\"', fmt='{:.0f}', label='estimated')} wording disagreements that round 4 had left without a third look were all read again by blind readers; "
        f"the two rounds used different rules, so their rates are given apart: in the round 4 sample, where any difference from the source counted, staging was wrong in {claim('p_tl_r4', tl, 'count', r4, fmt='{:.0f}', label='estimated')} of {claim('p_tl_r4_n', tl, 'of', r4, fmt='{:.0f}', label='estimated')} "
        f"({claim('p_tl_r4_pct', tl, 'share', r4, fmt='{:.0f}', scale=100, label='estimated')} percent, Wilson interval {claim('p_tl_r4_lo', tl, 'wilson_lo', r4, fmt='{:.1f}', scale=100, label='estimated')} to {claim('p_tl_r4_hi', tl, 'wilson_hi', r4, fmt='{:.1f}', scale=100, label='estimated')}); "
        f"in this round, where only a contradiction of the source counted, staged text contradicted the source in {claim('p_tl_r5', tl, 'count', r5, fmt='{:.0f}', label='estimated')} of {claim('p_tl_r5_n', tl, 'of', r5, fmt='{:.0f}', label='estimated')} settled lines "
        f"(Wilson interval {claim('p_tl_r5_lo', tl, 'wilson_lo', r5, fmt='{:.2f}', scale=100, label='estimated')} to {claim('p_tl_r5_hi', tl, 'wilson_hi', r5, fmt='{:.1f}', scale=100, label='estimated')} percent), although the staged text differed verbatim from the source in "
        f"{claim('p_tl_verb', tl, 'count', verb, fmt='{:.0f}', label='estimated')} of them; {claim('p_tl_amb', tl, 'count', 'measure == \"lines ambiguous\"', fmt='{:.0f}', label='estimated')} lines stay ambiguous (`docs/STATISTICS_V5.md`).")


def parts_text(fill):
    fill["cycle_model_text"] = cycle_model_text() if exists("cyclemodel/results/error_summary.csv") else ""
    fill["rtl_text"] = rtl_text() if exists("rtlsim/results/ibex_cycles.csv") else ""
    cb = "stats/results/cycle_cluster_bootstrap.csv"
    lo = "stats/results/cycle_lofo_summary.csv"
    fs = "planner/results/flightstack_mc_summary.csv"
    gs = "netsim/results/gap_sweep.csv"
    pv = "formal/results/proverif_results.csv"
    fill["abstract_method"] = (
        f"It combines {fill['n_rows']} published rows from {fill['n_sources']} source URLs, the newest each read against its source in two separate reading passes, with a trace driven cycle model, energy, link, boot, fleet and mission models, "
        "and checks of those models by independent tools: memory of real flight stack builds, the ns-3 network simulator, the ProVerif protocol verifier and cycle accurate simulation of two open cores, plus software in the loop runs of a flight stack.")
    fill["abstract_results"] = (
        f"A cycle model fitted on part of the published rows of one code base predicts its held out rows with a median error of {claim('ab_cm', cb, 'median_abs_pct', 'model == \"fitted\" and subset == \"test, all\"', fmt='{:.1f}', label='modelled')} percent, "
        f"but {claim('ab_lofo', lo, 'median_abs_pct', 'left_out_by == \"scheme\" and group == \"all groups pooled\" and model == \"fitted\"', fmt='{:.1f}', label='modelled')} percent for a scheme left out of the fit. "
        f"Measured flight stack memory raises the estimated median share of fleet devices that need hardware replacement from {claim('ab_fl_as', fs, 'assumed_median', 'thresholds == \"stack_asm\"', fmt='{:.3f}', label='estimated')} to "
        f"{claim('ab_fl_ms', fs, 'measured_median', 'thresholds == \"stack_asm\"', fmt='{:.3f}', label='estimated')} under stack optimised thresholds and from {claim('ab_fl_a', fs, 'assumed_median', 'thresholds == \"uncertain\"', fmt='{:.3f}', label='estimated')} to "
        f"{claim('ab_fl_m', fs, 'measured_median', 'thresholds == \"uncertain\"', fmt='{:.3f}', label='estimated')} under thresholds drawn from published rows, a correction of our earlier estimate. "
        f"In ns-3, an IEEE 802.15.4 transfer that the link model puts at {claim('ab_ls', gs, 'time_s_modelled', 'cell == \"base_frame\"', fmt='{:.1f}', label='modelled')} s reaches the published 30 to 60 s, on average, with any one of three configurations the source does not state, so the published gap has sufficient causes but no proven one. "
        f"A protocol verifier checked {claim('ab_pv_n', pv, 'result', '', 'count', '{:.0f}', label='modelled')} queries, including deliberate controls built to fail, proved {claim('ab_pv_p', pv, 'result', 'result == \"proved\"', 'count', '{:.0f}', label='modelled')}, and found three design flaws whose fixes the reference architecture adopts. "
        "On telemetry class radios a hybrid key establishment followed by a symmetric session keeps command availability where it is without authentication, while a post quantum signature on every command does not; this availability is modelled under the published MAVLink replay rule, not the stricter rule the proofs need.")
    fill["method_reading"] = method_reading()
    fill["rq_results"] = rq_text()
    fill["threats"] = threats_text()
    fill["conclusion"] = conclusion_text()
    fill["discussion"] = (
        "Three results change what an engineer should do. First, a published cycle count is not a property of the algorithm alone: the implementation variant and the measurement conditions move the same operation on the same core class, so a migration decision should rest on a measurement of the deployed code, which the board kit makes cheap. "
        "Second, on the links drones and robots use, the cost of post quantum authentication is a one time handshake, not a per message burden, provided the design uses a session: on telemetry radios and 802.15.4, per message signatures are the option that fails, and on LoRaWAN no command stream fits the duty cycle. "
        "Third, the fleet answer depends on how much memory the flight stack leaves free; measured builds show less free flash than round 4 assumed, and operators can settle this from their own build output.\n\n"
        "Where the models overlap they are not independent: the mission model reads the link simulator's parameters through the shared inputs file, so their agreement on a single handshake is a consistency check, not a validation. "
        "The energy and mission studies both find CPU time, not energy, to be the binding budget. ns-3 now gives sufficient causes for the 802.15.4 gap and shows that the link model's multi hop assumption is optimistic; the link model was not tuned to the published figure.")
    fill["repro"] = repro_text()


def repro_text():
    rows = [
        ("Figure 1 (cycle model errors)", "python3 stats/cycle_validation.py && python3 scripts/make_paper_figures.py", "stats/results/cycle_cluster_bootstrap.csv, stats/results/cycle_lofo_summary.csv"),
        ("Figure 2 (802.15.4 transfer by cause)", "bash netsim/fetch_build.sh && python3 -m netsim.run_netsim && python3 -m netsim.make_study && python3 scripts/make_paper_figures.py", "netsim/results/gap_sweep.csv"),
        ("Figure 3 (fleet replacement share)", "python3 planner/flightstack_study.py && python3 scripts/make_paper_figures.py", "planner/results/flightstack_mc_summary.csv"),
        ("Table 1 (ProVerif results)", "sh formal/install.sh && python3 -m formal.build_models && python3 -m formal.run_all", "formal/results/proverif_results.csv"),
        ("Flight stack memory (RQ5)", "bash flightstack/fetch.sh && bash flightstack/build_all.sh && python3 flightstack/extract_memory.py", "data/flightstack_memory.csv"),
        ("Hierarchical meta analysis (RQ1)", "python3 stats/meta_hierarchical.py", "data/meta/hierarchical_variance.csv"),
        ("End to end chain and Sobol ranking", "python3 stats/end_to_end.py", "stats/results/e2e_mc_summary.csv, stats/results/e2e_sobol.csv"),
        ("Open core cycles (RQ1)", "bash rtlsim/run.sh && bash rtlsim/run_cv32e40p.sh && python3 rtlsim/report.py", "rtlsim/results/core_spread.csv"),
        ("Board predictions, caches off", "python3 bench/board_kit/predictions_v5.py", "bench/board_kit/predictions_v5_board.csv"),
        ("This paper and the claims register", "python3 scripts/build_paper.py && python3 scripts/check_numbers.py", "data/claims_register.csv"),
        ("PDF", "./scripts/build_pdfs.sh", "docs/PAPER.pdf"),
    ]
    t = ["| Item | Command | Result file |", "|---|---|---|"]
    for a, b, c in rows:
        t.append(f"| {a} | `{b}` | `{c}` |")
    return ("Each figure and table regenerates from committed scripts with stored seeds; third party code is fetched at pinned versions and never committed. "
            "Heavy steps (flight stack builds, ns-3, open core simulation) need the pinned toolchains listed in each study document.\n\n" + "\n".join(t))


def main_word_count(text):
    """Words of the six page main part: from the abstract to the end of the conclusion (references excluded)."""
    a = text.index("## Abstract")
    b = text.index("## References")
    body = re.sub(r"!\[[^\]]*\]\([^)]*\)\{[^}]*\}", " ", text[a:b])
    return len(body.split())


def main():
    body = (ROOT / "docs" / "PAPER_body.md").read_text(encoding="utf-8")
    ev = "data/evidence.csv"
    fill = {
        "date": __import__("subprocess").run(["git", "log", "-1", "--format=%cs", "--", "data/evidence.csv"], cwd=ROOT, capture_output=True, text=True).stdout.strip() or dt.date.today().isoformat(),
        "n_rows": claim("abs_rows", ev, "id", aggregate="count", label="published"),
        "n_sources": claim("abs_sources", ev, "source_url", aggregate="nunique", label="published"),
        "n_s10": claim("n_s10", ev, "id", 'stream == "S10"', "count", label="published"),
        "results": results_text(),
    }
    v5 = ROOT / "docs" / "VERIFICATION5.md"
    m = re.search(r"\| evidence rows with a confirmed wrong value in staging \| (\d+) \| (\d+) \| ([\d.]+) percent \| ([\d.]+) to ([\d.]+) percent", v5.read_text())
    fill["v5_sentence"] = (f"{m.group(1)} of {m.group(2)} staged rows with values had a wrong value before correction, {m.group(3)} percent, Wilson interval {m.group(4)} to {m.group(5)} percent; `docs/VERIFICATION5.md`"
                           if m else "see `docs/VERIFICATION5.md`")
    fill["v2_rate_sentence"] = "details in `docs/VERIFICATION.md`, `docs/VERIFICATION2.md` and `docs/VERIFICATION3.md`"
    fill["pred_sentence"] = "`docs/PREDICTIONS.md`, `docs/PREDICTIONS_V2.md`, `docs/PREDICTIONS_V3.md`, `docs/PREDICTIONS_V4.md`"
    fill["word_note"] = "{{word_note}}"
    parts_text(fill)
    text = body
    for _ in range(3):
        text = re.sub(r"\{\{(?!word_note)(\w+)\}\}", lambda mm: fill.get(mm.group(1), mm.group(0)), text)
    n_main = main_word_count(text)
    pages = n_main / WORDS_PER_PAGE
    text = text.replace("{{word_note}}", f"Length of the main part (abstract to conclusion, table included, figure captions and references excluded): {n_main} words, about {pages:.1f} pages at {WORDS_PER_PAGE} words per two column page, before the references and the three figures, each about a third of a column high.")
    left = re.findall(r"\{\{(\w+)\}\}", text)
    if left:
        sys.exit(f"unfilled placeholders: {sorted(set(left))}")
    text = anchor(text)
    (ROOT / DOC).write_text(text, encoding="utf-8")
    sys.path.insert(0, str(ROOT / "scripts"))
    import proposal_texts
    for pdoc, ptext in proposal_texts.all_docs(claim):
        ptext = anchor(ptext)
        (ROOT / pdoc).write_text(ptext, encoding="utf-8")
        # a number prepared for a document but not used in it is not a claim of that document
        CLAIMS[:] = [c for c in CLAIMS if c["document"] != pdoc or c.get("_used")]
    if (ROOT / "sitl/results_r6/summary.csv").exists():
        import conference_texts
        for cdoc, ctext in conference_texts.build(claim):
            ctext = anchor(ctext)
            (ROOT / cdoc).write_text(ctext, encoding="utf-8")
            CLAIMS[:] = [c for c in CLAIMS if c["document"] != cdoc or c.get("_used")]
    fields = ["claim_id", "document", "text_in_document", "value", "source_file", "column", "query", "aggregate", "tolerance_rel", "label", "note", "context"]
    with open(ROOT / "data" / "claims_register.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(CLAIMS)
    print(f"wrote {DOC} ({len(text.split())} words in all, {n_main} in the main part, about {pages:.1f} pages) and {len(CLAIMS)} claims")


if __name__ == "__main__":
    main()
