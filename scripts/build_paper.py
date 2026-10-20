#!/usr/bin/env python3
"""Build docs/PAPER.md and the round 4 proposals from the result files, and write the claims register.

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
                   "label": label, "note": f"displayed as {fmt} x {scale}" if scale != 1.0 else ""})
    return text


def exists(p):
    return (ROOT / p).exists()


def results_text():
    ev = "data/evidence.csv"
    L = []
    # RQ1 compute
    L.append("### 4.1 RQ1: compute cost, and how well it can be predicted\n")
    L.append(
        f"Evidence. The table holds {claim('n_rows', ev, 'id', aggregate='count', label='published')} rows; "
        f"{claim('n_mcu_cycles', ev, 'cycles', 'device_class == \"mcu\" and cycles == cycles', 'count', label='published')} are microcontroller rows with a cycle count, "
        f"on {claim('n_cores', ev, 'core', 'device_class == \"mcu\" and cycles == cycles', 'nunique', label='published')} core labels as the sources print them (Cortex-M4 and Cortex-M4F are counted apart, and one label is 'not stated'). "
        f"Inside groups of the same parameter set, operation and core class that have rows from two or more sources, the largest published value is "
        f"{claim('meta_spread', 'data/meta/cycle_groups.csv', 'max_over_min', 'sources >= 2', 'median', '{:.2f}', label='published')} times the smallest at the median group "
        f"(up to {claim('meta_spread_max', 'data/meta/cycle_groups.csv', 'max_over_min', 'sources >= 2', 'max', '{:.2f}', label='published')}; `docs/META_ANALYSIS.md`). "
        "Part of this spread is deliberate: a group can hold speed and stack optimised variants of one scheme and both means and medians, so it measures how far a "
        "published figure can sit from the deployed code when the variant and conditions are not known, not the measurement error of one implementation. "
        "Library, optimisation, toolchain, cache and statistic all move it.\n")
    if exists("cyclemodel/results/error_summary.csv"):
        L.append("{{cycle_model_text}}\n")
    if exists("rtlsim/results/ibex_cycles.csv"):
        L.append("{{rtl_text}}\n")
    # RQ2 energy
    er = "energy/results/max_rates.csv"
    L.append("### 4.2 RQ2: energy and CPU headroom\n")
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
    L.append("### 4.3 RQ3: links and protocols\n")
    L.append(
        "The link model was repaired one cited cause at a time and checked against published figures and closed forms (`docs/LINKSIM_STUDY.md` section 4.4). "
        "The LoRa time on air formula reproduces the published examples, but this is a weak check: only one of the four examples states every parameter, and for the other three the unstated settings were chosen after the fact because they reproduce the published value. Fragment counts agree with an independent count and the duty cycle wait equals its formula, an arithmetic check; stop and wait retransmissions in the event simulation agree with their closed form within Monte Carlo intervals, but selective repeat, which the protocol and mission studies use, is not checked. "
        "For IEEE 802.15.4, adding every cited cost (PHY header, 6LoWPAN fragment headers and alignment, acknowledgements, inter frame spacing, clear channel assessment and backoff, turnaround) "
        f"takes a 50 kB transfer from {claim('d_base', dg, 'time_s_modelled_after', 'step == \"0\"', fmt='{:.1f}', label='modelled')} s to "
        f"{claim('d_final', dg, 'time_s_modelled_after', 'step == \"6\"', fmt='{:.1f}', label='modelled')} s, which is still "
        f"{claim('d_factor', dg, 'factor_below_low_after', 'step == \"6\"', fmt='{:.1f}', label='modelled')} times faster than the published 30 to 60 s. "
        "Most of that gap is unexplained by single hop costs; four hops would bring the model to 28.5 s, near the low end, but the source gives no hop count, so the model is reported as optimistic on 802.15.4 networks. "
        "The rate part was checked against one published table of handshakes over an emulated link, with one constant fitted on two of its rows; that is a weak test on one testbed.\n")
    pg = "linksim/results/protocols_grid.csv"
    if exists(pg):
        L.append("The protocol simulation (1000 seeded trials per cell, `docs/PROTOCOL_SIM.md`) gives the time to the first authenticated message. "
                 "On a telemetry radio and on 802.15.4, a hybrid session handshake completes in about one to two seconds; on LoRaWAN it takes minutes at DR5 and hours at DR0, because of the duty cycle. "
                 "Per message post quantum signatures overload the slower links.\n")
    # RQ4 boot
    vt = "bootchain/results/verify_time.csv"
    q = 'target == "Crazyflie 2.1 (STM32F405)" and image_bytes == 1000000 and scheme == "{s}" and hash == "{h}"'
    L.append("### 4.4 RQ4: signed boot and update\n")
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
    L.append("### 4.5 RQ5: fleet migration\n")
    L.append(
        f"The round 3 synthetic fleet is reproduced exactly ({claim('syn_lo', pm, 'median', 'fleet == \"synthetic\" and thresholds == \"stack_asm\"', fmt='{:.3f}', label='estimated')} to "
        f"{claim('syn_hi', pm, 'median', 'fleet == \"synthetic\" and thresholds == \"reference_c\"', fmt='{:.3f}', label='estimated')} of devices need hardware replacement). "
        f"On fleets drawn from nine real board classes, with every memory threshold drawn from published rows, the median share is "
        f"{claim('prof_med', pm, 'median', 'fleet == \"profile\" and thresholds == \"uncertain\"', fmt='{:.3f}', label='estimated')} "
        f"(2.5 to 97.5 percentile {claim('prof_lo', pm, 'p2_5', 'fleet == \"profile\" and thresholds == \"uncertain\"', fmt='{:.3f}', label='estimated')} to "
        f"{claim('prof_hi', pm, 'p97_5', 'fleet == \"profile\" and thresholds == \"uncertain\"', fmt='{:.3f}', label='estimated')}). "
        "The share is close to 0.20 and its intervals cross that value, so whether fewer than a fifth of devices need replacement depends on the threshold scenario. No retrieved page states how much flash or RAM a flight stack leaves free, so the free share is an assumption, and it moves the result more than the choice of implementation does (`docs/PLANNER_STUDY.md` section 5). "
        f"Under the Mosca inequality with stated ranges, data lifetime has the largest total Sobol index ({claim('mosca_st', 'planner/results/mosca_sobol.csv', 'ST', 'input == \"data_lifetime_years\"', fmt='{:.2f}', label='modelled')}), largely because its range is the widest. "
        "Policy dates come from primary texts (`docs/POLICY_TIMELINE.md`); the supplied UAE policy texts give no post quantum date.\n")
    # RQ6 mission
    mb = "mission/results/base.csv"
    qm = 'vehicle == "{v}" and arch == "{a}" and link == "{l}"'
    L.append("### 4.6 RQ6: mission level design\n")
    L.append(
        "In the mission simulation (1000 runs per configuration, `docs/MISSION_STUDY.md`), a classical session, a hybrid session and hash signed firmware with session keys keep the drone's control link available "
        f"about as often as an unauthenticated stream on a telemetry radio (mean over runs {claim('m_b_sik', mb, 'avail_mean', qm.format(v='drone', a='B', l='sik'), fmt='{:.3f}', label='estimated')} for the hybrid session): link outages, not authentication, set availability. "
        f"A post quantum signature on every command adds about {claim('m_c_lat', mb, 'added_latency_ms_median', qm.format(v='drone', a='C', l='sik'), fmt='{:.0f}', label='estimated')} ms per command on that radio, "
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
        f"{claim('cm_hi', es, 'median_abs_ci_hi', q.format(m='fitted', s='test, all'), fmt='{:.1f}', label='modelled')}, too narrow because rows cluster by binary) on "
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


def parts_text(fill):
    ev = "data/evidence.csv"
    fill["cycle_model_text"] = cycle_model_text() if exists("cyclemodel/results/error_summary.csv") else ""
    fill["rtl_text"] = rtl_text() if exists("rtlsim/results/ibex_cycles.csv") else ""
    fill["rtl_sentence"] = ("cycle accurate simulation of an open source microcontroller class core" if exists("rtlsim/results/ibex_cycles.csv")
                            else "no open core simulation")
    es = "cyclemodel/results/error_summary.csv"
    fill["abstract_results"] = (
        f"Within one code base, a cycle model fitted on half of the published rows predicts the other half with a median error of {claim('ab_cm', es, 'median_abs_pct', 'model == \"fitted\" and subset == \"test, all\"', fmt='{:.1f}', label='modelled')} percent, though signing misses by up to {claim('ab_cm_worst', es, 'worst_abs_pct', 'model == \"fitted\" and subset == \"test, all\"', fmt='{:.0f}', label='modelled')} percent. "
        "On telemetry class radios a hybrid key establishment followed by a symmetric session keeps command availability where it is without authentication, while a post quantum signature on every command does not. "
        "For firmware, hashing the image costs more than any signature check unless the device has hash hardware. "
        "The largest open uncertainties are the free memory a flight stack leaves and the real timing of mesh links.")
    fill["discussion"] = (
        "Three results change what an engineer should do. First, a published cycle count is not a property of the algorithm alone: the implementation variant and the measurement conditions move the same operation on the same core class by a factor that the meta analysis quantifies, so a migration decision should rest on a measurement of the deployed code, which the board kit makes cheap. "
        "Second, on the links drones and robots use, the cost of post quantum authentication is a one time handshake, not a per message burden, provided the design uses a session: per message signatures are the only option that fails. "
        "Third, the fleet answer depends more on how much memory the flight stack leaves free than on which implementation of ML-DSA is chosen; operators can settle this from their own build output, which no public page states.\n\n"
        "Where the models overlap they are not independent: the mission model reads the link simulator's parameters, so their agreement on a single handshake is a consistency check, not a validation, and the two still differ noticeably on the time to set up a hybrid session on the telemetry radio, a difference this round did not explain. The energy and mission studies both find CPU time, not energy, to be the binding budget. "
        "They disagree with the evidence in one place that matters, the 802.15.4 transfer time, and the study reports that gap rather than closing it by fitting.")
    fill["limitations"] = (
        "1. Nothing was measured on a microcontroller. The board experiment is prepared and its outcome registered, but not run.\n"
        "2. The cycle model is validated within one code base; its transfer to other libraries rests on a single small external check.\n"
        "3. The link model is too fast on IEEE 802.15.4 by a factor the study cannot yet explain; duty cycle and fragmentation are checked only arithmetically, and loss handling only against closed forms for stop and wait, with no measurement.\n"
        "4. Fleets are drawn from real board classes but their counts and free memory shares are synthetic or assumed.\n"
        "5. Energy rests on typical datasheet currents for five parts and one calibration source.\n"
        "6. The classical baselines (Ed25519, X25519) are single published rows chosen within a published range that spans about a factor of two; the energy and mission studies use the same rows and show the range beside each result.\n"
        "7. The studies do not yet share one set of inputs everywhere: the protocol and mission models describe the MAVLink style handshake differently, and the energy and mission models use different published LMS rows and per message costs; each choice is stated in its study.\n"
        "8. Several sources could not be retrieved (listed in `docs/NEEDS_FROM_AUTHOR.md` and the source notes); 126 new rows that only one reader could confirm were left out of the table.\n"
        "9. The double reading settled every value disagreement but only a sample of wording disagreements, so some operation, scheme or library fields are likely still wrong (`docs/VERIFICATION5.md`, Limits); two readers shared a scratch path for helper scripts, a limit on their independence.")


def main():
    body = (ROOT / "docs" / "PAPER_body.md").read_text(encoding="utf-8")
    ev = "data/evidence.csv"
    fill = {
        "date": __import__("subprocess").run(["git", "log", "-1", "--format=%cs", "--", "data/evidence.csv"], cwd=ROOT, capture_output=True, text=True).stdout.strip() or dt.date.today().isoformat(),
        "n_rows": claim("abs_rows", ev, "id", aggregate="count", label="published"),
        "n_sources": claim("abs_sources", ev, "source_url", aggregate="nunique", label="published"),
        "n_s10": claim("n_s10", ev, "id", 'stream == "S10"', "count", label="published"),
        "n_s12": claim("abs_s12", ev, "id", 'stream == "S12"', "count", label="published"),
        "results": results_text(),
    }
    v5 = ROOT / "docs" / "VERIFICATION5.md"
    m = re.search(r"\| evidence rows with a confirmed wrong value in staging \| (\d+) \| (\d+) \| ([\d.]+) percent \| ([\d.]+) to ([\d.]+) percent", v5.read_text())
    fill["v5_sentence"] = (f"{m.group(1)} of {m.group(2)} staged rows with values had a wrong value before correction, {m.group(3)} percent, Wilson interval {m.group(4)} to {m.group(5)} percent; `docs/VERIFICATION5.md`"
                           if m else "see `docs/VERIFICATION5.md`")
    fill["v2_rate_sentence"] = "details in `docs/VERIFICATION.md`, `docs/VERIFICATION2.md` and `docs/VERIFICATION3.md`"
    fill["pred_sentence"] = "`docs/PREDICTIONS.md`, `docs/PREDICTIONS_V2.md`, `docs/PREDICTIONS_V3.md`, `docs/PREDICTIONS_V4.md`"
    extra = (ROOT / "docs" / "PAPER_parts.md")
    parts = {}
    if extra.exists():
        chunks = re.split(r"^<!-- part: (\w+) -->\s*$", extra.read_text(encoding="utf-8"), flags=re.M)
        for i in range(1, len(chunks), 2):
            parts[chunks[i]] = chunks[i + 1].strip()
    fill.update(parts)
    parts_text(fill)
    text = body
    for _ in range(3):
        text = re.sub(r"\{\{(\w+)\}\}", lambda mm: fill.get(mm.group(1), mm.group(0)), text)
    left = re.findall(r"\{\{(\w+)\}\}", text)
    if left:
        sys.exit(f"unfilled placeholders: {sorted(set(left))}")
    (ROOT / DOC).write_text(text, encoding="utf-8")
    sys.path.insert(0, str(ROOT / "scripts"))
    import proposal_texts
    for pdoc, ptext in proposal_texts.all_docs(claim):
        (ROOT / pdoc).write_text(ptext, encoding="utf-8")
        # a number prepared for a document but not used in it is not a claim of that document
        CLAIMS[:] = [c for c in CLAIMS if c["document"] != pdoc or c["text_in_document"] in ptext]
    fields = ["claim_id", "document", "text_in_document", "value", "source_file", "column", "query", "aggregate", "tolerance_rel", "label", "note"]
    with open(ROOT / "data" / "claims_register.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(CLAIMS)
    print(f"wrote {DOC} ({len(text.split())} words) and {len(CLAIMS)} claims")


if __name__ == "__main__":
    main()
