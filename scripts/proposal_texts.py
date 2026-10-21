"""Texts of the robotics proposal (round 5), its three short variants and a one page brief. Author: Huda Mueen.

Every number goes through the `claim` function passed in by scripts/build_paper.py, so it is read
from a result file and recorded in data/claims_register.csv. Entity facts are cited by their id in
data/context_entities.csv; nothing else about any organisation is stated. Plan, milestone, risk,
equipment, data management, readiness and policy fit tables are rendered from data/proposal/*.csv.
The quoted policy terms come from the supplied UAE National Encryption Policy PDF, section 6.1.
"""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SEED_NOTE = ("This is a student research proposal and a seed for discussion. It is not a deployment, it has no "
             "relationship with or endorsement by any organisation named, and organisation facts come only from the "
             "public pages listed in `docs/CONTEXT_ENTITIES.md`, cited by their id.")

POLICY = ("UAE National Encryption Policy, Version 1.0, Cyber Security Council, section 6.1 \"General Requirements\" "
          "(supplied PDF; source note `data/raw/S12_policy_sources.md`, item 4; timeline row P24 of `data/policy_timeline.csv`)")

TRL_SOURCE = "Horizon 2020 Work Programme 2014-2015, General Annexes, G. Technology readiness levels (TRL)"

FORMAL = "formal/results/proverif_results.csv"
FLEET = "planner/results/flightstack_mc_summary.csv"
MEM = "data/flightstack_memory.csv"
GAP = "netsim/results/gap_sweep.csv"
LOFO = "stats/results/cycle_lofo_summary.csv"
CORES = "rtlsim/results/core_spread.csv"
V5B = "bench/board_kit/predictions_v5_board.csv"
PLAN = "bench/board_kit/session_plan.csv"
MB = "mission/results/base.csv"
PROP = "data/proposal/"


def rows(rel):
    with open(ROOT / rel, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def table(header, body):
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in body]
    return "\n".join(out)


def numbers(claim, doc):
    es = "cyclemodel/results/error_summary.csv"
    dg = "linksim/results/diagnosis_v4.csv"
    vt = "bootchain/results/verify_time.csv"
    qm = 'vehicle == "{v}" and arch == "{a}" and link == "{l}"'
    qb = 'target == "Crazyflie 2.1 (STM32F405)" and image_bytes == 1000000 and scheme == "LMS" and hash == "{h}"'
    lofo = 'left_out_by == "{b}" and group == "all groups pooled" and model == "{m}"'
    p = doc.replace("docs/", "").replace(".md", "").lower()
    c = lambda cid, *a, **k: claim(f"{p}_{cid}", *a, doc=doc, **k)  # noqa: E731
    return {
        "rows": c("rows", "data/evidence.csv", "id", aggregate="count", label="published"),
        "cm_med": c("cm_med", es, "median_abs_pct", 'model == "fitted" and subset == "test, all"', fmt="{:.1f}", label="modelled"),
        "cm_sign": c("cm_sign", es, "worst_abs_pct", 'model == "fitted" and subset == "test, all"', fmt="{:.0f}", label="modelled"),
        "lofo_fam": c("lofo_fam", LOFO, "median_abs_pct", lofo.format(b="implementation family", m="fitted"), fmt="{:.1f}", label="modelled"),
        "lofo_sch": c("lofo_sch", LOFO, "median_abs_pct", lofo.format(b="scheme", m="fitted"), fmt="{:.1f}", label="modelled"),
        "lofo_sch_red": c("lofo_sch_red", LOFO, "median_abs_pct", lofo.format(b="scheme", m="reduced"), fmt="{:.1f}", label="modelled"),
        "pi_wide": c("pi_wide", "stats/results/cycle_board_predictions_cluster.csv", "width_ratio_cluster_to_round4", aggregate="max", fmt="{:.2f}", label="modelled"),
        "core_lo": c("core_lo", CORES, "max_over_min", aggregate="min", fmt="{:.2f}", label="RTL simulated"),
        "core_hi": c("core_hi", CORES, "max_over_min", aggregate="max", fmt="{:.2f}", label="RTL simulated"),
        "core_sets": c("core_sets", CORES, "parameter_set", aggregate="nunique", label="RTL simulated"),
        "m_b": c("m_b", MB, "avail_mean", qm.format(v="drone", a="B", l="sik"), fmt="{:.3f}", label="estimated"),
        "m_c": c("m_c", MB, "avail_mean", qm.format(v="drone", a="C", l="sik"), fmt="{:.3f}", label="estimated"),
        "m_c_lat": c("m_c_lat", MB, "added_latency_ms_median", qm.format(v="drone", a="C", l="sik"), fmt="{:.0f}", label="estimated"),
        "m_b_lat": c("m_b_lat", MB, "added_latency_ms_median", qm.format(v="drone", a="B", l="sik"), fmt="{:.1f}", label="estimated"),
        "m_b_hs": c("m_b_hs", MB, "first_session_s_median", qm.format(v="drone", a="B", l="sik"), fmt="{:.2f}", label="estimated"),
        "deadline": c("deadline", MB, "deadline_s", qm.format(v="drone", a="B", l="sik"), fmt="{:.1f}", label="estimated"),
        "d_factor": c("d_factor", dg, "factor_below_low_after", 'step == "6"', fmt="{:.1f}", label="modelled"),
        "boot_sw": c("boot_sw", vt, "total_ms_estimated", qb.format(h="software SHA-256"), fmt="{:.0f}", label="estimated"),
        "boot_hw": c("boot_hw", vt, "total_ms_estimated", qb.format(h="hardware HASH"), fmt="{:.0f}", label="estimated"),
        "fs_builds": c("fs_builds", MEM, "target", 'build_status == "built"', "count", label="host measured"),
        "fs_boards": c("fs_boards", MEM, "board", 'build_status == "built"', "nunique", label="host measured"),
        "px4_flash_lo": c("px4_flash_lo", MEM, "flash_free_bytes", 'stack == "px4"', "min", fmt="{:.1f}", scale=0.001, label="host measured"),
        "px4_flash_hi": c("px4_flash_hi", MEM, "flash_free_bytes", 'stack == "px4"', "max", fmt="{:.1f}", scale=0.001, label="host measured"),
        "ram_lo": c("ram_lo", MEM, "ram_free_static_bytes", 'build_status == "built"', "min", fmt="{:.1f}", scale=0.001, label="host measured"),
        "hr_asm_a": c("hr_asm_a", FLEET, "assumed_median", 'thresholds == "stack_asm"', fmt="{:.3f}", label="estimated"),
        "hr_asm_m": c("hr_asm_m", FLEET, "measured_median", 'thresholds == "stack_asm"', fmt="{:.3f}", label="estimated"),
        "hr_unc_a": c("hr_unc_a", FLEET, "assumed_median", 'thresholds == "uncertain"', fmt="{:.3f}", label="estimated"),
        "hr_unc_m": c("hr_unc_m", FLEET, "measured_median", 'thresholds == "uncertain"', fmt="{:.3f}", label="estimated"),
        "ns_base": c("ns_base", GAP, "time_mean_s_simulated_network", 'cell == "base_frame"', fmt="{:.2f}", label="simulated (network)"),
        "ls_base": c("ls_base", GAP, "time_s_modelled", 'cell == "base_frame"', fmt="{:.2f}", label="modelled"),
        "pub_lo": c("pub_lo", GAP, "range_low_s_published", 'cell == "base_frame"', label="published"),
        "pub_hi": c("pub_hi", GAP, "range_high_s_published", 'cell == "base_frame"', label="published"),
        "ns_hops3": c("ns_hops3", GAP, "time_mean_s_simulated_network", 'cell == "hops_3"', fmt="{:.1f}", label="simulated (network)"),
        "ns_bg16": c("ns_bg16", GAP, "time_mean_s_simulated_network", 'cell == "bg_16"', fmt="{:.1f}", label="simulated (network)"),
        "ns_minbe8": c("ns_minbe8", GAP, "time_mean_s_simulated_network", 'cell == "minbe_8"', fmt="{:.1f}", label="simulated (network)"),
        "fv_q": c("fv_q", FORMAL, "query", aggregate="count", label="modelled"),
        "fv_models": c("fv_models", FORMAL, "model", aggregate="nunique", label="modelled"),
        "fv_proved": c("fv_proved", FORMAL, "query", 'result == "proved"', "count", label="modelled"),
        "fv_cex": c("fv_cex", FORMAL, "query", 'result == "counterexample"', "count", label="modelled"),
        "fv_cnp": c("fv_cnp", FORMAL, "query", 'result == "cannot be proved"', "count", label="modelled"),
        "v5b_rows": c("v5b_rows", V5B, "id", aggregate="count", label="modelled"),
        "v5b_per": c("v5b_per", V5B, "id", 'platform == "nucleo-l4r5zi"', "count", label="modelled"),
        "plan_min": c("plan_min", PLAN, "total_s", '~block.str.contains("B0")', "sum", fmt="{:.0f}", scale=1 / 60, label="estimated"),
        "clock": c("clock", vt, "clock_mhz", qb.format(h="software SHA-256"), label="published"),
        "img_mb": c("img_mb", vt, "image_bytes", qb.format(h="software SHA-256"), scale=1e-6, label="estimated"),
        "obj_kb": c("obj_kb", "netsim/results/lrwpan_runs.csv", "object_bytes", 'cell == "base_frame"', "max", scale=0.001, label="simulated (network)"),
        "hops": c("hops", GAP, "value", 'cell == "hops_3"', label="simulated (network)"),
        "bg": c("bg", GAP, "value", 'cell == "bg_16"', label="simulated (network)"),
        "minbe": c("minbe", GAP, "value", 'cell == "minbe_8"', label="simulated (network)"),
        "months": c("months", PROP + "plan.csv", "end_month", aggregate="max", label="planned"),
        "buy": c("buy", PROP + "equipment.csv", "purchase_count", aggregate="sum", label="planned"),
    }


def formal_table():
    """Property, result in the stated design, design change, result after the change; read from the ProVerif results."""
    r = {(x["model"], x["property_id"]): x for x in rows(FORMAL)}

    def res(model, pid):
        x = r[(model, pid)]
        return x["result"] + (f" ({x['weaker_form']})" if x["weaker_form"] else "")

    spec = [
        ("Ground station authenticates the vehicle (A2)", "session_b_stated", "A2", "F1: the vehicle signs the transcript; both sides confirm the key", "session_b_fixed", "A2"),
        ("Ground station session key stays secret (S2)", "session_b_stated", "S2", "F1", "session_b_fixed", "S2"),
        ("Ground station rekeyed key stays secret (S4)", "session_b_stated", "S4", "F1", "session_b_fixed", "S4"),
        ("Vehicle accepts each command once, only if sent (C1)", "session_b_stated", "C1", "none needed", "session_b_fixed", "C1"),
        ("Vehicle session key secret with one component broken (S1)", "session_b_fixed_classical_broken", "S1", "none needed (hybrid key derivation)", "session_b_fixed_kem_broken", "S1"),
        ("Provisioned key fallback: no replay after a power cycle (C1)", "fallback_d_stated", "C1", "F2: fresh nonces from both sides at every session start", "fallback_d_fixed", "C1"),
        ("Provisioned key fallback: earlier sessions secret after key theft (FS)", "fallback_d_fixed_fs_provisioned", "FS", "none possible without a key exchange; keys kept short lived", "fallback_d_fixed_fs_provisioned", "FS"),
        ("Firmware: no downgrade to an older signed image (D1)", "firmware_stated_no_counter", "D1", "F3: signed version and a monotonic counter in protected storage", "firmware_fixed_counter", "D1"),
        ("Published MAVLink timestamp rule with gaps (C1)", "session_timestamp_rule", "C1", "modelling limit, not a design finding; other models use the next sequence number", "session_timestamp_rule", "C1"),
    ]
    body = []
    for prop, m1, p1, change, m2, p2 in spec:
        after = "same as stated" if (m1, p1) == (m2, p2) else res(m2, p2)
        if m1 == "session_b_fixed_classical_broken":
            body.append([prop, "not run on the stated design", change,
                         f"{res(m1, p1)} with the classical part broken; {res(m2, p2)} with the KEM part broken"])
            continue
        body.append([prop, res(m1, p1), change, after])
    return table(["Property (model id)", "Stated design (modelled)", "Design change", "After the change (modelled)"], body)


def readiness(claim, doc, p):
    scale = {x["level"]: x["definition"] for x in rows(PROP + "trl_scale.csv")}
    body = []
    for x in rows(PROP + "readiness.csv"):
        q = f'id == "{x["id"]}"'
        now = claim(f"{p}_trl_now_{x['id'].lower()}", PROP + "readiness.csv", "trl_now", q, label="estimated", doc=doc)
        end = claim(f"{p}_trl_end_{x['id'].lower()}", PROP + "readiness.csv", "trl_end", q, label="estimated", doc=doc)
        body.append([x["component"], f"TRL {now} ({scale[x['trl_now']]})", x["evidence_now"], f"TRL {end} ({scale[x['trl_end']]})", x["evidence_end"]])
    return table(["Component", "Now (estimated)", "Evidence now", "End of project (planned)", "Evidence needed"], body)


def plan_tables():
    t = table(["Task", "Phase", "Work", "Months", "Deliverable"],
              [[x["id"], x["phase"], x["task"], x["start_month"] if x["start_month"] == x["end_month"] else f"{x['start_month']} to {x['end_month']}", x["deliverable"]]
               for x in rows(PROP + "plan.csv")])
    m = table(["Milestone", "Month", "What is shown", "Evidence file", "Decision gate"],
              [[x["id"], x["month"], x["milestone"], f"`{x['evidence_file'].split(' ')[0]}`", x["decision_gate"]] for x in rows(PROP + "milestones.csv")])
    r = table(["Id", "Risk", "Likelihood", "Impact", "Trigger", "Mitigation"],
              [[x["id"], x["risk"], x["likelihood"], x["impact"], x["trigger"], x["mitigation"]] for x in rows(PROP + "risks.csv")])
    return t, m, r


def resources_tables():
    e = table(["Item", "Quantity", "Source", "Purchases", "Used in"],
              [[x["item"], x["quantity"], x["source"], x["purchase_count"], x["used_in"]] for x in rows(PROP + "equipment.csv")])
    d = table(["Data", "What is stored", "Where", "Format", "Licence", "Retention", "Personal data"],
              [[x["item"], x["what_is_stored"], x["where"], x["format"], x["licence"], x["retention"], x["personal_data"]] for x in rows(PROP + "data_management.csv")])
    return e, d


def fit_table():
    return table(["Deliverable", "Policy section", "Policy term (quoted)", "Printed page", "Public entity facts (ids)", "Scope note"],
                 [[f"{x['id']}: {x['deliverable']}", x["policy_section_published"], f"\"{x['policy_term_published']}\"", x["policy_page_published"],
                   ", ".join(x["entity_fact_ids"].split()), x["note"]] for x in rows(PROP + "policy_fit.csv")])


def hypotheses(n):
    return table(["ID", "Hypothesis and measurable success criterion", "Refuted if", "Registered in"], [
        ["H1", f"On the Cortex-M4 board, caches off, the board mean of at least four fifths of the {n['v5b_per']} harness rows lies inside its registered interval, and the signed errors do not share one sign",
         "more than a third of the rows miss, or more than four fifths of the signed errors share one sign; only rows whose log shows the caches off conditions count; the Cortex-M33 board is scored apart and tests transfer only",
         "`docs/PREDICTIONS_V5_BOARD.md` (rules 1 to 4); round 4 rows under `docs/PREDICTIONS_V4_BOARD_NOTES.md` notes 5 to 9"],
        ["H2", f"On a borrowed SiK class radio pair at default settings, the median hybrid handshake (with design change F1) lies between half and twice the first session time of {n['m_b_hs']} s in the mission study (estimated; the protocol simulation gives a similar time for the same profile)",
         "the measured median lies outside that range", "this proposal; to be hashed before the radio session"],
        ["H3", f"With the session layer in software in the loop, the added latency per command stays near the modelled {n['m_b_lat']} ms and inside the {n['deadline']} s command deadline of the mission study",
         "the command stream misses its deadline more often with the session layer than without it", "this proposal; to be hashed before the software in the loop runs"],
        ["H4", f"Run time free RAM after the flight stack (heap included) stays above the signature plus KEM RAM thresholds of `planner/results/flightstack_thresholds.csv` on every built board class; the static upper bound is now {n['ram_lo']} kB at the smallest",
         "a built board class has less run time free RAM than a threshold; flash is already known to be short on default PX4 builds (section 2)", "this proposal; to be hashed before the runs"],
    ])


def robotics(claim):
    doc = "docs/PROPOSAL_ROBOTICS.md"
    p = "proposal_robotics"
    n = numbers(claim, doc)
    tasks, miles, risks = plan_tables()
    equip, dmp = resources_tables()
    text = f"""# Proposal: a post quantum ready command and update channel for drones and ground robots, from model to hardware in the loop

Author: Huda Mueen. Generated by `scripts/build_paper.py` from `scripts/proposal_texts.py` and `data/proposal/`; every number below is read from a result file and checked by `scripts/check_numbers.py`.

{SEED_NOTE}

## 1. Problem

Unmanned aircraft and ground robots accept commands and firmware over narrow radio links, authenticated today with classical public key cryptography on microcontroller flight computers. The post quantum replacements are standardised, and some buyers and national policies have set duties or dates (`docs/POLICY_TIMELINE.md`). An operator still cannot answer three practical questions from evidence: will the new algorithms fit and run fast enough on the flight controller it has; will the link carry the larger messages without hurting control; and which of its devices must be replaced rather than updated.

## 2. Preliminary results (this repository)

1. **Evidence.** A provenance controlled table of {n['rows']} published rows, every new row read by two independent readers (`docs/VERIFICATION5.md`, `docs/VERIFICATION6.md`).
2. **Flight stack memory and the corrected fleet answer.** {n['fs_builds']} default builds of PX4 and ArduPilot for {n['fs_boards']} board classes (host measured, linker output) leave {n['px4_flash_lo']} to {n['px4_flash_hi']} kB of application flash free in the PX4 builds; the smallest free static RAM is {n['ram_lo']} kB, an upper bound because run time heap is not visible in a build. With these measured values the fleet study's median hardware replacement share rises from {n['hr_asm_a']} to {n['hr_asm_m']} with stack optimised thresholds, and from {n['hr_unc_a']} to {n['hr_unc_m']} with uncertain thresholds (estimated; `docs/FLIGHTSTACK_STUDY.md`). The round 4 answer, which assumed free memory, was too optimistic.
3. **Causes of the 802.15.4 gap (ns-3).** A {n['obj_kb']} kB transfer over one hop with ns-3 defaults takes {n['ns_base']} s (simulated (network)) against {n['ls_base']} s in the link model (modelled) and a published {n['pub_lo']} to {n['pub_hi']} s. Each of these single causes brings ns-3 into the published range: {n['hops']} hops ({n['ns_hops3']} s), {n['bg']} loaded neighbours ({n['ns_bg16']} s) or a minimum backoff exponent of {n['minbe']}, a cited and allowed setting ({n['ns_minbe8']} s). The paper states none of these settings, so they are sufficient causes, not the proven cause; ns-3 also shows that the link model's multi hop forwarding is optimistic (`docs/NETSIM_STUDY.md`). Before this check the link model was {n['d_factor']} times too fast with no explanation.
4. **Formal verification.** ProVerif checked {n['fv_models']} model files with {n['fv_q']} queries: {n['fv_proved']} proved, {n['fv_cex']} counterexamples (stated designs and deliberate controls) and {n['fv_cnp']} that the tool could not prove (modelled; `docs/FORMAL_VERIFICATION.md`). Design findings F1 to F3 were each removed by a design change that was then proved; the reference architecture adopts them (section 2.1).
5. **Cycle model and its transfer limits.** The trace driven model predicts held out pqm4 Cortex-M4 rows with a median error of {n['cm_med']} percent (signing misses by up to {n['cm_sign']} percent), but leaving out a whole implementation family gives {n['lofo_fam']} percent and leaving out a whole scheme {n['lofo_sch']} percent ({n['lofo_sch_red']} percent for the reduced model), and a cluster aware prediction interval is {n['pi_wide']} times as wide as the registered one (modelled; `docs/STATISTICS_V5.md`). It is an interpolation within one code base, not a general predictor.
6. **Open core spread.** The same RV32IMC program takes {n['core_lo']} to {n['core_hi']} times as many cycles on one open core as on the other over {n['core_sets']} ML-KEM and ML-DSA parameter sets (RTL simulated; `docs/RTL_SIM_RESULTS.md`), so a figure for one core is not a figure for another of the same instruction set.
7. **Mission and boot.** A hybrid session keeps a drone's command availability on a telemetry radio at a mean of {n['m_b']}, while a post quantum signature on every command lowers it to {n['m_c']} and adds about {n['m_c_lat']} ms per command; verifying a {n['img_mb']} MB image with LMS takes about {n['boot_sw']} ms with a software hash and {n['boot_hw']} ms with hash hardware on a {n['clock']} MHz Cortex-M4 (estimated; `docs/MISSION_STUDY.md`, `docs/BOOT_UPDATE_STUDY.md`).
8. **Board kit ready, predictions registered.** The kit builds images for NUCLEO-L4R5ZI and NUCLEO-L552ZE-Q with an option that switches caches and prefetch off, checked so far only by disassembly of the images and an emulator that logs the register write but does not model a cache; {n['v5b_rows']} out of sample predictions for the caches off pass are hashed in `docs/PREDICTIONS_V5_BOARD.md`, and the bench plan keeps both boards within one afternoon of about {n['plan_min']} minutes (estimated; `bench/board_kit/ONE_AFTERNOON.md`). Nothing has yet been measured on a microcontroller.

### 2.1 Formal verification: properties, results and design changes

Read from `{FORMAL}` (label: modelled; abstract perfect primitives under a Dolev Yao attacker; not a test of any implementation).

{formal_table()}

### 2.2 Software in the loop comparison (to be filled by the lead)

Placeholder. This section will hold the comparison of the session layer in software in the loop (label: SITL measured) with the mission study (label: estimated): configurations, missions per configuration, seeds, added latency per command, handshake time and the error against the mission study. No number is stated here until the result files exist.

| Configuration | Missions | Added latency per command | Handshake time | Error against the mission study |
|---|---|---|---|---|
| to be filled | to be filled | to be filled | to be filled | to be filled |

## 3. Aim, hypotheses and measurable success criteria

Aim: test the models of this repository against measurements, turn them into a measured, reusable reference design for an authenticated command and update channel on a real flight controller, and publish the measurements with their provenance. Every hypothesis is hashed before its experiment, and misses stay.

{hypotheses(n)}

H1 follows the registered rules exactly; the four fifths criterion is a stricter success target stated here, not a change of the registered refutation rule. The round 4 board predictions are scored under their own notes and reported beside H1.

## 4. Readiness

Scale: {TRL_SOURCE}, retrieved on 2026-10-21 from the public European Commission page recorded in `data/proposal/trl_scale.csv`. The levels are the author's conservative reading of the evidence in each file named; no level rests on a measurement that has not been made.

{readiness(claim, doc, p)}

## 5. Plan

![Work plan by task and phase, with milestones (planned)](figures/proposal/gantt.png)

Figure generated by `scripts/make_gantt.py` from `data/proposal/plan.csv` and `data/proposal/milestones.csv` (label: planned).

{tasks}

### 5.1 Milestones and decision gates

{miles}

### 5.2 Risk register

{risks}

## 6. Resources

### 6.1 Borrowed equipment (purchases: {n['buy']})

{equip}

### 6.2 Data management plan

No personal data is collected: the measurements are cycle counts, currents, timings and memory figures of devices. Third party code is fetched at pinned versions by scripts and never committed; its licences are listed in `docs/LICENSES.md`.

{dmp}

## 7. Fit with section 6.1 of the national encryption policy and with public entity facts

Source of the quoted terms: {POLICY}. Section 6.1 places duties on entities; this project does not fulfil any entity's duty. It produces public inputs that an entity could use when it carries out its own duties. Entity facts are cited by id only; their wording and sources are in `docs/CONTEXT_ENTITIES.md`.

{fit_table()}

## 8. Deliverables

D1 to D6 as in section 7: a board measured table labelled apart from published values, a measured link timing dataset, a session and update design note with its formal model, an inventory template and planner rerun, an acquisition checklist, and a dataset release with a paper and a teaching note. Code and data stay with the author until a licence is agreed.

## 9. Ethics and safety

Defensive work only: no attack code and no side channel guidance; existing pinned libraries are benchmark subjects only. Flights, if any, follow the host lab's safety rules; hardware in the loop work needs no flight.

## 10. The ask

Supervision; a few hours of lab access to the two development boards, a multimeter and a telemetry radio pair (equipment list in section 6); and one representative flight controller profile from a partner (core, clock, free flash and RAM after the flight stack, link type), which replaces the largest remaining assumption in the fleet study. No purchase is required.
"""
    return doc, text


def variant(claim, org, doc, fit_lines):
    n = numbers(claim, doc)
    text = f"""# Proposal summary for {org}: post quantum ready command and update channels for drones and robots

Author: Huda Mueen. Two page summary of `docs/PROPOSAL_ROBOTICS.md`, generated by `scripts/build_paper.py`; every number is read from a result file.

{SEED_NOTE}

## Problem

Drones and robots authenticate commands and firmware on microcontroller flight computers over narrow links. The post quantum replacements are standardised, but their cost on such devices and links, and which devices must be replaced rather than updated, are not yet measured.

## Why this may be relevant (public facts only)

{fit_lines}

## What already exists

- {n['rows']} published rows with provenance, every new row read by two independent readers.
- Flight stack memory from {n['fs_builds']} real builds (host measured): default PX4 builds leave {n['px4_flash_lo']} to {n['px4_flash_hi']} kB of flash free, and the fleet's median hardware replacement share rises from {n['hr_unc_a']} to {n['hr_unc_m']} once measured memory replaces the assumption (estimated).
- ns-3 explains the 802.15.4 gap by sufficient causes: one hop takes {n['ns_base']} s in ns-3 against a published {n['pub_lo']} to {n['pub_hi']} s, and {n['hops']} hops, {n['bg']} loaded neighbours or a cited backoff setting each bring it into range (simulated (network)).
- Formal verification of the session and update design: {n['fv_proved']} of {n['fv_q']} queries proved, and design findings F1 to F3 (vehicle authentication, replay after a power cycle, firmware downgrade) fixed and proved (modelled).
- A cycle model with a median held out error of {n['cm_med']} percent within one code base, but {n['lofo_sch']} percent when a whole scheme is left out (modelled), and {n['v5b_rows']} board predictions for a caches off pass registered before any board session.
- A mission simulation: with a hybrid session, command availability on a telemetry radio stays at {n['m_b']}; a signature on every command lowers it to {n['m_c']} (estimated).

## Proposed next step

A one afternoon board session and a hardware in the loop study with a borrowed flight controller and telemetry radio, scored against predictions registered in this repository, followed by a reference design note for a session based command and update channel (`docs/REFERENCE_ARCHITECTURE.md`). Readiness, plan, risks and the policy fit are in `docs/PROPOSAL_ROBOTICS.md`.

## The ask

Supervision or a contact for feedback; a few hours of lab access to a development board and a radio pair; one representative flight controller profile. No purchase is required.
"""
    return doc, text


def brief(claim):
    doc = "docs/PROPOSAL_BRIEF.md"
    p = "proposal_brief"
    n = numbers(claim, doc)
    trl = {x["id"]: x for x in rows(PROP + "readiness.csv")}
    q = lambda i: f'id == "{i}"'  # noqa: E731
    c1_now = claim(f"{p}_trl_now_c1", PROP + "readiness.csv", "trl_now", q("C1"), label="estimated", doc=doc)
    c1_end = claim(f"{p}_trl_end_c1", PROP + "readiness.csv", "trl_end", q("C1"), label="estimated", doc=doc)
    ids = []
    for x in rows(PROP + "policy_fit.csv"):
        for i in x["entity_fact_ids"].split():
            if i not in ids:
                ids.append(i)
    sections = []
    for x in rows(PROP + "policy_fit.csv"):
        if x["policy_section_published"] not in sections:
            sections.append(x["policy_section_published"])
    text = f"""# Brief for a research director: post quantum command and update channels for drones and robots

Author: Huda Mueen. One page, generated by `scripts/build_paper.py` from `scripts/proposal_texts.py`; every number is read from a result file. Full proposal: `docs/PROPOSAL_ROBOTICS.md`.

{SEED_NOTE}

**Question.** Will standardised post quantum algorithms fit and run on the flight controllers and radio links that drones and robots use, and which devices must be replaced rather than updated?

**What the evidence shows now.**

- Real flight stack builds ({n['fs_builds']}, host measured) leave little flash: {n['px4_flash_lo']} to {n['px4_flash_hi']} kB free on default PX4 builds. With measured memory the estimated median share of a fleet needing new hardware rises from {n['hr_unc_a']} to {n['hr_unc_m']}.
- A hybrid session keeps command availability on a telemetry radio at {n['m_b']}; signing every command lowers it to {n['m_c']} (estimated).
- The session and update design was checked formally: {n['fv_proved']} of {n['fv_q']} queries proved, design flaws F1 to F3 found and fixed (modelled).
- The cycle model is accurate within one code base ({n['cm_med']} percent) but not across schemes ({n['lofo_sch']} percent); nothing is yet measured on a microcontroller.

**What is proposed.** {n['months']} months, part time: one afternoon on two borrowed boards scored against {n['v5b_rows']} registered predictions, software in the loop, a borrowed radio pair, a run time memory profile, and a design note with dataset release. Readiness of the command channel: TRL {c1_now} now, TRL {c1_end} planned at the end (lab only; scale in the full proposal).

**Fit.** Deliverables map to sections {", ".join(sorted(sections))} of the UAE National Encryption Policy (quoted terms and page in the full proposal, section 7) and to public facts {", ".join(ids)} in `docs/CONTEXT_ENTITIES.md`. The project does not fulfil any entity's duty and implies no endorsement.

**The ask.** Supervision; a few hours of lab access to two development boards, a multimeter and a telemetry radio pair; one representative flight controller profile. Purchases: {n['buy']}.
"""
    return doc, text


def all_docs(claim):
    facts = rows("data/context_entities.csv")

    def lines(org, ids):
        found = [f["fact_id"] for f in facts if f["organisation"] == org and f["fact_id"] in ids]
        note = " (EDGE-06 describes a challenge whose application window has closed.)" if "EDGE-06" in found else ""
        return ("Public facts that may make this work relevant are recorded, with their sources, only in `docs/CONTEXT_ENTITIES.md`: "
                + ", ".join(sorted(found)) + "." + note + " None of them implies any relationship with or endorsement by the organisation.")

    docs = [robotics(claim)]
    docs.append(variant(claim, "TII and ATRC", "docs/PROPOSAL_ROBOTICS_ATRC.md",
                        lines("TII and ATRC", {"TII-02", "TII-04", "TII-05", "TII-06", "TII-07"})))
    docs.append(variant(claim, "EDGE Group", "docs/PROPOSAL_ROBOTICS_EDGE.md",
                        lines("EDGE Group", {"EDGE-01", "EDGE-02", "EDGE-05", "EDGE-06"})))
    docs.append(variant(claim, "ADEO", "docs/PROPOSAL_ROBOTICS_ADEO.md",
                        lines("ADEO", {"ADEO-01", "ADEO-02", "ADEO-03", "ADEO-04"})
                        + "\n\nADEO publishes little on technology under its own name; the items above that do not name ADEO are Abu Dhabi government statements, as `docs/CONTEXT_ENTITIES.md` notes."))
    docs.append(brief(claim))
    return docs
