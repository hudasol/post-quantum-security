#!/usr/bin/env python3
"""Write README.md. Counts are read from the data files, so the README cannot drift from them."""
import csv, collections, json
ev = list(csv.DictReader(open('data/evidence.csv')))
host = list(csv.DictReader(open('bench/host/host_measurements.csv')))
S = {r['set']: r for r in csv.DictReader(open('data/verify2/summary.csv'))}
v3 = {r['set']: r for r in csv.DictReader(open('data/verify3/summary.csv'))}['all']
c = S['combined']; ver = int(c['rows']) - int(c['unverifiable'])
n_pub = sum(1 for r in ev if r['evidence_type'] == 'published')
n_s2 = sum(1 for r in ev if r['stream'] == 'S2'); n_s3 = sum(1 for r in ev if r['stream'] == 'S3'); n_s7 = sum(1 for r in ev if r['stream'] == 'S7'); n_s8 = sum(1 for r in ev if r['stream'] == 'S8'); n_s10 = sum(1 for r in ev if r['stream'] == 'S10')
n_pq = sum(1 for r in ev if 'mupq/pqm4' in r['source_url'])
hk = len(host)
import re as _re
n_cross = _re.search(r'This repository: (\d+) rows', open('data/crosscheck/SUMMARY.md').read()).group(1)
n_ren = sum(1 for r in csv.DictReader(open('bench/mcu/renode_results/checks.csv')) if r['fail'] == '0')
_v4 = [r for x in 'ABCDEF' for r in csv.DictReader(open(f'data/verify4/S10{x}_results.csv'))]
v4_bad = sum(1 for r in _v4 if any(r[k].strip().lower() != 'yes' for k in ('value_ok', 'location_ok', 'row_ok', 'other_fields_ok', 'warning_ok')))
lint_true = sum(1 for r in csv.DictReader(open('data/verify4/lint_review.csv')) if r['verdict'] == 'true')
_rng = {r['devices']: r for r in csv.DictReader(open('planner/results/scenario_range.csv'))}['1000']
import io, subprocess
_pdf_commit = subprocess.run(['git', 'log', '-1', '--format=%H', '--', 'docs/REPORT.pdf'], capture_output=True, text=True).stdout.strip()
_pdf_date = subprocess.run(['git', 'log', '-1', '--format=%cs', '--', 'docs/REPORT.pdf'], capture_output=True, text=True).stdout.strip()
n_pdf = len(list(csv.DictReader(io.StringIO(subprocess.run(['git', 'show', _pdf_commit + ':data/evidence.csv'], capture_output=True, text=True).stdout))))
emu = list(csv.DictReader(open('bench/mcu/qemu_results/checks.csv'))); n_emu = len(emu); n_emu_ok = sum(1 for r in emu if r['fail'] == '0')
_same_text = subprocess.run(['git', 'show', _pdf_commit + ':docs/REPORT.md'], capture_output=True, text=True,
                            encoding='utf-8').stdout.replace('\r\n', '\n') == open('docs/REPORT.md', encoding='utf-8').read().replace('\r\n', '\n')
pdf_note = (f"The PDFs were built on {_pdf_date} from the current `docs/REPORT.md` "
            "(`scripts/build_pdfs.sh`, or `scripts/build_pdfs_docker.sh` without a local pandoc and XeLaTeX)."
            if _same_text else
            f"The PDFs were last built on {_pdf_date} from an earlier text of `docs/REPORT.md` ({n_pdf} rows then, "
            f"{n_pub} now). Rebuild with `scripts/build_pdfs.sh` or `scripts/build_pdfs_docker.sh`.")
n_s12 = sum(1 for r in ev if r['stream'] == 'S12')
import pandas as _pd, os as _os
_es = _pd.read_csv('cyclemodel/results/error_summary.csv')
_cm = _es[(_es.model == 'fitted') & (_es.subset == 'test, all')].iloc[0]
_rtl_n = len(_pd.read_csv('rtlsim/results/ibex_cycles.csv').query('statistic == "median"')) if _os.path.exists('rtlsim/results/ibex_cycles.csv') else 0
_v5 = _re.search(r'confirmed wrong value in staging \| (\d+) \| (\d+) \| ([\d.]+) percent \| ([\d.]+) to ([\d.]+)', open('docs/VERIFICATION5.md').read())
txt = f"""# Post quantum cryptography on drone and robot computers

A sourced study of what post quantum cryptography costs on microcontroller class computers in drones and robots: a provenance controlled evidence table, a trace driven cycle model, a cycle accurate simulation of an open source core, energy, link, protocol, boot, fleet and mission models with their validation errors, and a ready to run board experiment whose outcome is registered in advance. Author: Huda Mueen. Evidence retrieved 2026-10-11, 2026-10-12 and 2026-10-20; supplied papers read 2026-10-16 and 2026-10-20.

**For a research director:** `docs/PAPER.md` (the study, every number checked against its data file), `docs/PROPOSAL_ROBOTICS.md` (follow on robotics project, with short variants `docs/PROPOSAL_ROBOTICS_ATRC.md`, `_EDGE.md`, `_ADEO.md`) and `docs/PROPOSAL_ATRC.md` (2 pages). Progress against a stated definition of a complete study: `docs/COMPLETENESS_RUBRIC.md`.

**Start here:** `docs/EXECUTIVE_BRIEF.pdf` (2 pages), then `docs/REPORT.pdf` (`docs/REPORT.md`). {pdf_note}

## What is published, host measured, emulated, estimated, modelled, RTL simulated and planned

Every number in this repository carries one of seven labels (emulated was added in phase 2; modelled and RTL simulated in round 4; board measured is reserved for `docs/BOARD_RUN_PROTOCOL.md`). Round 4 result files carry a `label` column checked by `scripts/check_labels.py`. Five earlier result files that hold several labels have a label for every column in `data/column_labels.csv`, checked by a test. Labels are never mixed in one table or axis without a label on each column; the deliberate comparisons are the model validation in `docs/LINKSIM_STUDY.md` section 4, the ratio tables in `bench/host/native/RESULTS.md` and `bench/host/native_v3/RESULTS.md`, prediction Q1.5, the stack range in `docs/PROPOSAL_ATRC.md` (published against emulated) and the portable C planner scenario, whose thresholds come from emulated figures.

| Label | Meaning | Where it lives | Count or status |
|---|---|---|---|
| **Published** | Copied from a source that was actually retrieved, with URL, retrieval date and location in the source | `data/evidence.csv` | {n_pub} rows ({n_s2} benchmark and size rows, {n_s3} protocol and size rows, {n_s7} benchmark and size rows read from author supplied PDFs in phase 2, {n_s8} cycle and stack rows from the LMS and XMSS paper found by the second run and rechecked against the PDF, {n_s10} rows read on 2026-10-16 from six more author supplied PDFs and rechecked in full by a fresh reader, {n_s12} rows added on 2026-10-20 after two independent readers); {n_pq} come from the pqm4 project |
| **Host measured** | Run on a PC or server, never on a microcontroller | `bench/host/` | {hk} liboqs timing records; native timings of the emulated code in `bench/host/native/` and, with an interleaved method, `bench/host/native_v3/` (ratios and rank order only) |
| **Estimated** | Arithmetic from published sizes or rates, formula shown, "estimated from published sizes, not measured" | `linksim/`, `docs/link_tables.md`, `docs/LINKSIM_STUDY.md` (Monte Carlo, sweeps, validation), `docs/LINK_REFERENCE_DESIGN.md`, `docs/PLANNER_RULES.md` thresholds, `docs/PLANNER_STUDY.md` (synthetic fleets; hardware replacements in 1000 devices range from {_rng['hr_low']} to {_rng['hr_high']} by implementation), derived times in the report | all derived |
| **Emulated** | Run on emulated Cortex-M4 and Cortex-M33 models (QEMU), cross checked in Renode. Correctness, stack and image size only; no cycle counts | `docs/EMULATOR_RESULTS.md`, `bench/mcu/qemu_results/` | {n_emu} builds (Cortex-M4 and Cortex-M33, three optimisation levels), {n_emu_ok} passed every check; {n_ren} Renode builds give the same stack to the byte |
| **Modelled** | Trace driven or fitted model; its validation error is shown beside every value | `cyclemodel/`, `docs/CYCLE_MODEL.md`, calibrated parts of `energy/` and `bootchain/` | cycle model: median held out error {_cm['median_abs_pct']:.1f} percent on {int(_cm['n'])} published rows, worst {_cm['worst_abs_pct']:.1f} percent (signing) |
| **RTL simulated** | Cycle accurate simulation of an open source core design (Ibex RV32IMC), never presented as Arm silicon | `rtlsim/`, `docs/RTL_SIM_RESULTS.md` | {_rtl_n} operations |
| **Planned** | An experiment that has not been run | `docs/BENCHMARK_PLAN.md` (E1 to E5), `docs/BOARD_RUN_PROTOCOL.md` (B0, B1), `bench/board_kit/`, `docs/PREDICTIONS_V4_BOARD.md`, `docs/NO_PURCHASE_PLAN.md`, `bench/mcu/` | nothing has been measured on a real microcontroller; 30 board predictions are registered |

No purchase is needed for any planned step: an emulator (QEMU or Renode) checks correctness and sizes, and borrowed lab hardware gives real cycle counts (`docs/NO_PURCHASE_PLAN.md`).

## Verification

Separate verification passes that did not collect the data reopened the sources; no external reviewer has checked the table. Phase 1 sampled 50 rows. Phase 2 checked all {S['headline']['rows']} rows behind a headline number and a seeded stratified random sample of {S['random']['rows']} further rows. Phase 2 combined (headline plus random) strict row error rate: {int(c['error'])} of {ver} verifiable rows ({100*int(c['error'])/ver:.1f} percent), with {c['wrong_fields']} wrong value in {c['populated']} compared fields; the other {c['missing_only_rows']} were rounded KB figures that the table left empty and now records verbatim. {c['unverifiable']} rows could not be verified because the source stayed blocked. The {n_s7} + {n_s8} rows added later from author supplied PDFs were each checked by finding the value in the named table, not by the independent verifiers, and are outside these rates. Details: `docs/VERIFICATION.md` (phase 1) and `docs/VERIFICATION2.md` (phase 2). The {n_s10} S10 rows were each rechecked by a fresh reader: 0 transcription errors, and {v3['any']} of {v3['rows']} rows needed a fix to a column mapping or a warning (`docs/VERIFICATION3.md`). A second reading by three new readers then checked a seeded stratified sample of {len(_v4)} of those rows field by field and found {v4_bad} errors (approximate 95 percent upper bound {100*3/len(_v4):.1f} percent), and a column lint over all rows found {lint_true} warning errors, now fixed (same file). In round 4 every one of {_v5.group(2)} new rows with values was read by two independent readers and every value disagreement got a third look: {_v5.group(1)} had a wrong value in staging ({_v5.group(3)} percent, Wilson interval {_v5.group(4)} to {_v5.group(5)} percent), all corrected; rows that only one reader could confirm stay out of the table (`docs/VERIFICATION5.md`). The pqm4 benchmark clock is unresolved in the project's own files and is stated as such (`data/raw/S6_pqm4_config.md`). A second, independent run of the same brief was merged in: its 582 rows are kept as raw input in `data/second_run/` and compared with the {n_cross} row version of this table in `docs/CROSSCHECK.md`.

Predictions were written before the phase 2 runs and are scored in `docs/PREDICTIONS.md`. Round 3 and round 4 predictions are hashed in `docs/PREDICTIONS_V3.md` and `docs/PREDICTIONS_V4.md`. The second round predictions were hashed before any run (`docs/PREDICTIONS_V2.md`) and are scored by script in `docs/PREDICTIONS_V2_SCORES.md`; decisions and deviations are in `docs/RUN_LOG.md`, and what only the author can supply is in `docs/NEEDS_FROM_AUTHOR.md`.

## Contents

| Path | What |
|---|---|
| `docs/PAPER.md`, `data/claims_register.csv` | the study as a paper; every number is registered and recomputed by `scripts/check_numbers.py` |
| `docs/PROPOSAL_ROBOTICS*.md`, `docs/CONTEXT_ENTITIES.md` | follow on robotics proposal and short variants; public facts only |
| `docs/PROPOSAL_ATRC.md` | two page research proposal, numbers filled from the result files by `scripts/build_proposal.py` |
| `docs/META_ANALYSIS.md`, `docs/SEARCH_PROTOCOL.md`, `data/bibliography.bib`, `docs/DATA_DICTIONARY.md` | spread of published cycle counts, search log and flow, generated bibliography, column meanings |
| `cyclemodel/`, `rtlsim/` | trace driven cycle model; Ibex RTL simulation |
| `energy/`, `bootchain/`, `mission/` | energy and CPU headroom, signed boot and update, mission simulation (`docs/ENERGY_STUDY.md`, `docs/BOOT_UPDATE_STUDY.md`, `docs/MISSION_STUDY.md`, `docs/REFERENCE_ARCHITECTURE.md`) |
| `linksim/protocols.py`, `docs/PROTOCOL_SIM.md` | protocol simulation (DTLS 1.3, EDHOC with OSCORE, MAVLink 2 style, DDS Security style) |
| `data/reference_profiles.csv`, `docs/POLICY_TIMELINE.md` | real flight controller classes; dated policy milestones from primary texts |
| `bench/board_kit/` | build, capture, parse and compare scripts for a borrowed board session |
| `docs/REPORT.md`, `docs/REPORT.pdf` | full review |
| `docs/EXECUTIVE_BRIEF.md`, `.pdf` | 2 page brief |
| `docs/DECISION_FRAMEWORK.md`, `docs/MIGRATION_PLAYBOOK.md` | decision flow and phased playbook |
| `docs/LINK_REFERENCE_DESIGN.md`, `linksim/` | constrained link reference design and its simulator (size and timing arithmetic only, no cryptography) |
| `planner/`, `docs/PLANNER_RULES.md` | fleet migration planner (supports planning, not a security guarantee); SYNTHETIC example inventory |
| `docs/upstream/` | drafts of questions to MAVLink, SROS2 or DDS Security, and MCUboot (drafts only, nothing filed) |
| `docs/supplier/` | neutral supplier email template and response tracker |
| `docs/MAVLINK_PQ_SKETCH.md` | design sketch, not a proposal to any project |
| `docs/BENCHMARK_PLAN.md`, `docs/NEXT_STEPS.md`, `docs/SOURCES_TO_UPLOAD.md` | experiments, first steps, sources to fetch |
| `data/` | evidence table, corrections, verification inputs and results, research notes in `data/raw/` |
| `plots/` | figures from published rows, with the row ids behind each |
| `bench/` | harness for on device tests (run on a PC and in two emulators, not yet on a board), statistics and power analysis, host measurements |
| `scripts/`, `tests/`, `.github/workflows/ci.yml` | build, checks and continuous integration |

## Checks that run on every push

`scripts/check_repo_policy.py` fails if a paper, a PDF outside a three file allowlist, an archive, a saved web page or a vendored library is committed. `scripts/scan_secrets.py` is a secrets scan. `scripts/check_style.py` is a text lint. `scripts/check_citations.py`, `scripts/check_numbers.py` and `scripts/check_labels.py` check the bibliography, every registered claim and the label columns. Generated files (evidence table, report markdown, verification summary) are regenerated in CI and must match the committed copies.

## Rebuild

```
pip install -r requirements.txt         # free packages, versions as used in round 4
python3 scripts/merge_evidence.py      # evidence table from raw notes, corrections and the pqm4 rule
python3 scripts/build_report.py         # report markdown; numbers come from the table
python3 scripts/build_paper.py          # paper, proposals and claims register
./scripts/build_pdfs.sh                 # needs pandoc and xelatex
python3 -m unittest discover -s tests -t .
python3 -m unittest discover -s linksim/tests -t .
for d in energy bootchain mission cyclemodel rtlsim; do python3 -m unittest discover -s $d -t .; done
python3 -m unittest discover -s bench/board_kit/tests
cd planner && python3 -m unittest
```

## Licences

All rights reserved by Huda Mueen. This is not open source. Please contact the author through https://github.com/hudasol before you use, copy, modify, distribute or sell any part of it (`LICENSE`, `docs/LICENCE_DECISION.md`). Third party libraries are never committed; their licences are recorded in `docs/LICENSES.md`. No paper is redistributed.

## Safety

Defensive and conceptual only. No attack code, no side channel guidance, no cryptographic primitive is implemented here. The benchmark harness random generator is insecure and exists for timing only.
"""
open('README.md', 'w').write(txt)
print(len(txt.split()), 'words')
