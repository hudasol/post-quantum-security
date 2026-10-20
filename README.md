# Post quantum cryptography on drone and robot computers

A sourced study of what post quantum cryptography costs on microcontroller class computers in drones and robots: a provenance controlled evidence table, a trace driven cycle model, a cycle accurate simulation of an open source core, energy, link, protocol, boot, fleet and mission models with their validation errors, and a ready to run board experiment whose outcome is registered in advance. Author: Huda Mueen. Evidence retrieved 2026-10-11, 2026-10-12 and 2026-10-20; supplied papers read 2026-10-16 and 2026-10-20.

**For a research director:** `docs/PAPER.md` (the study, every number checked against its data file), `docs/PROPOSAL_ROBOTICS.md` (follow on robotics project, with short variants `docs/PROPOSAL_ROBOTICS_ATRC.md`, `_EDGE.md`, `_ADEO.md`) and `docs/PROPOSAL_ATRC.md` (2 pages). Progress against a stated definition of a complete study: `docs/COMPLETENESS_RUBRIC.md`.

**Start here:** `docs/EXECUTIVE_BRIEF.pdf` (2 pages), then `docs/REPORT.pdf` (`docs/REPORT.md`). The PDFs were last built on 2026-10-18 from an earlier text of `docs/REPORT.md` (971 rows then, 1328 now). Rebuild with `scripts/build_pdfs.sh` or `scripts/build_pdfs_docker.sh`.

## What is published, host measured, emulated, estimated, modelled, RTL simulated and planned

Every number in this repository carries one of seven labels (emulated was added in phase 2; modelled and RTL simulated in round 4; board measured is reserved for `docs/BOARD_RUN_PROTOCOL.md`). Round 4 result files carry a `label` column checked by `scripts/check_labels.py`. Labels are never mixed in one table or axis without a label on each column; the deliberate comparisons are the model validation in `docs/LINKSIM_STUDY.md` section 4, the ratio tables in `bench/host/native/RESULTS.md` and `bench/host/native_v3/RESULTS.md`, prediction Q1.5, the stack range in `docs/PROPOSAL_ATRC.md` (published against emulated) and the portable C planner scenario, whose thresholds come from emulated figures.

| Label | Meaning | Where it lives | Count or status |
|---|---|---|---|
| **Published** | Copied from a source that was actually retrieved, with URL, retrieval date and location in the source | `data/evidence.csv` | 1328 rows (431 benchmark and size rows, 46 protocol and size rows, 46 benchmark and size rows read from author supplied PDFs in phase 2, 45 cycle and stack rows from the LMS and XMSS paper found by the second run and rechecked against the PDF, 403 rows read on 2026-10-16 from six more author supplied PDFs and rechecked in full by a fresh reader, 357 rows added on 2026-10-20 after two independent readers); 90 come from the pqm4 project |
| **Host measured** | Run on a PC or server, never on a microcontroller | `bench/host/` | 300 liboqs timing records; native timings of the emulated code in `bench/host/native/` and, with an interleaved method, `bench/host/native_v3/` (ratios and rank order only) |
| **Estimated** | Arithmetic from published sizes or rates, formula shown, "estimated from published sizes, not measured" | `linksim/`, `docs/link_tables.md`, `docs/LINKSIM_STUDY.md` (Monte Carlo, sweeps, validation), `docs/LINK_REFERENCE_DESIGN.md`, `docs/PLANNER_RULES.md` thresholds, `docs/PLANNER_STUDY.md` (synthetic fleets; hardware replacements in 1000 devices range from 260 to 382 by implementation), derived times in the report | all derived |
| **Emulated** | Run on emulated Cortex-M4 and Cortex-M33 models (QEMU), cross checked in Renode. Correctness, stack and image size only; no cycle counts | `docs/EMULATOR_RESULTS.md`, `bench/mcu/qemu_results/` | 36 builds (Cortex-M4 and Cortex-M33, three optimisation levels), 36 passed every check; 4 Renode builds give the same stack to the byte |
| **Modelled** | Trace driven or fitted model; its validation error is shown beside every value | `cyclemodel/`, `docs/CYCLE_MODEL.md`, calibrated parts of `energy/` and `bootchain/` | cycle model: median held out error 1.0 percent on 27 published rows, worst 22.8 percent (signing) |
| **RTL simulated** | Cycle accurate simulation of an open source core design (Ibex RV32IMC), never presented as Arm silicon | `rtlsim/`, `docs/RTL_SIM_RESULTS.md` | 18 operations |
| **Planned** | An experiment that has not been run | `docs/BENCHMARK_PLAN.md` (E1 to E5), `docs/BOARD_RUN_PROTOCOL.md` (B0, B1), `bench/board_kit/`, `docs/PREDICTIONS_V4_BOARD.md`, `docs/NO_PURCHASE_PLAN.md`, `bench/mcu/` | nothing has been measured on a real microcontroller; 30 board predictions are registered |

No purchase is needed for any planned step: an emulator (QEMU or Renode) checks correctness and sizes, and borrowed lab hardware gives real cycle counts (`docs/NO_PURCHASE_PLAN.md`).

## Verification

Separate verification passes that did not collect the data reopened the sources; no external reviewer has checked the table. Phase 1 sampled 50 rows. Phase 2 checked all 157 rows behind a headline number and a seeded stratified random sample of 120 further rows. Phase 2 combined (headline plus random) strict row error rate: 15 of 269 verifiable rows (5.6 percent), with 1 wrong value in 655 compared fields; the other 14 were rounded KB figures that the table left empty and now records verbatim. 8 rows could not be verified because the source stayed blocked. The 46 + 45 rows added later from author supplied PDFs were each checked by finding the value in the named table, not by the independent verifiers, and are outside these rates. Details: `docs/VERIFICATION.md` (phase 1) and `docs/VERIFICATION2.md` (phase 2). The 403 S10 rows were each rechecked by a fresh reader: 0 transcription errors, and 41 of 403 rows needed a fix to a column mapping or a warning (`docs/VERIFICATION3.md`). A second reading by three new readers then checked a seeded stratified sample of 120 of those rows field by field and found 0 errors (approximate 95 percent upper bound 2.5 percent), and a column lint over all rows found 21 warning errors, now fixed (same file). In round 4 every one of 439 new rows with values was read by two independent readers and every value disagreement got a third look: 8 had a wrong value in staging (1.8 percent, Wilson interval 0.9 to 3.6 percent), all corrected; rows that only one reader could confirm stay out of the table (`docs/VERIFICATION5.md`). The pqm4 benchmark clock is unresolved in the project's own files and is stated as such (`data/raw/S6_pqm4_config.md`). A second, independent run of the same brief was merged in: its 582 rows are kept as raw input in `data/second_run/` and compared with the 523 row version of this table in `docs/CROSSCHECK.md`.

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

`scripts/check_repo_policy.py` fails if a paper, a PDF outside a two file allowlist, an archive, a saved web page or a vendored library is committed. `scripts/scan_secrets.py` is a secrets scan. `scripts/check_style.py` is a text lint. `scripts/check_citations.py`, `scripts/check_numbers.py` and `scripts/check_labels.py` check the bibliography, every registered claim and the label columns. Generated files (evidence table, report markdown, verification summary) are regenerated in CI and must match the committed copies.

## Rebuild

```
python3 scripts/merge_evidence.py      # evidence table from raw notes, corrections and the pqm4 rule
python3 scripts/build_report.py         # report markdown; numbers come from the table
./scripts/build_pdfs.sh                 # needs pandoc and xelatex
python3 -m unittest discover -s linksim/tests -t .
cd planner && python3 -m unittest
```

## Licences

All rights reserved by Huda Mueen. This is not open source. Please contact the author through https://github.com/hudasol before you use, copy, modify, distribute or sell any part of it (`LICENSE`, `docs/LICENCE_DECISION.md`). Third party libraries are never committed; their licences are recorded in `docs/LICENSES.md`. No paper is redistributed.

## Safety

Defensive and conceptual only. No attack code, no side channel guidance, no cryptographic primitive is implemented here. The benchmark harness random generator is insecure and exists for timing only.
