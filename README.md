# Post quantum cryptography on drone and robot computers

A sourced review of what post quantum cryptography costs on microcontroller class computers in drones and robots, with a link simulator, a fleet migration planner and a benchmark plan. Author: Huda Mueen. Evidence retrieved 2026-10-11 and 2026-10-12; supplied papers read 2026-10-16.

**For a research director:** `docs/PROPOSAL_ATRC.md` (2 pages: problem, gap, questions, plan, ask).

**Start here:** `docs/EXECUTIVE_BRIEF.pdf` (2 pages), then `docs/REPORT.pdf` (`docs/REPORT.md`). The PDFs were built on 2026-10-18 from the same 971 row table as `docs/REPORT.md` (`scripts/build_pdfs.sh`, or `scripts/build_pdfs_docker.sh` without a local pandoc and XeLaTeX).

## What is published, host measured, estimated and planned

Every number in this repository carries one of five labels (the fifth, emulated, was added in phase 2; a sixth, board measured, is reserved for `docs/BOARD_RUN_PROTOCOL.md`). Labels are never mixed in one table or axis without a label on each column; the deliberate comparisons are the model validation in `docs/LINKSIM_STUDY.md` section 4, the ratio table in `bench/host/native/RESULTS.md` and prediction Q1.5.

| Label | Meaning | Where it lives | Count or status |
|---|---|---|---|
| **Published** | Copied from a source that was actually retrieved, with URL, retrieval date and location in the source | `data/evidence.csv` | 971 rows (431 benchmark and size rows, 46 protocol and size rows, 46 benchmark and size rows read from author supplied PDFs in phase 2, 45 cycle and stack rows from the LMS and XMSS paper found by the second run and rechecked against the PDF, 403 rows read on 2026-10-16 from six more author supplied PDFs and rechecked in full by a fresh reader); 90 come from the pqm4 project |
| **Host measured** | Run on a PC or server, never on a microcontroller | `bench/host/` | 300 liboqs timing records; native timings of the emulated code in `bench/host/native/` and, with an interleaved method, `bench/host/native_v3/` (ratios and rank order only) |
| **Estimated** | Arithmetic from published sizes or rates, formula shown, "estimated from published sizes, not measured" | `linksim/`, `docs/link_tables.md`, `docs/LINKSIM_STUDY.md` (Monte Carlo, sweeps, validation), `docs/LINK_REFERENCE_DESIGN.md`, `docs/PLANNER_RULES.md` thresholds, `docs/PLANNER_STUDY.md` (synthetic fleets; hardware replacements in 1000 devices range from 260 to 382 by implementation), derived times in the report | all derived |
| **Emulated** | Run on emulated Cortex-M4 and Cortex-M33 models (QEMU), cross checked in Renode. Correctness, stack and image size only; no cycle counts | `docs/EMULATOR_RESULTS.md`, `bench/mcu/qemu_results/` | 36 builds (Cortex-M4 and Cortex-M33, three optimisation levels), 36 passed every check; 4 Renode builds give the same stack to the byte |
| **Planned** | An experiment that has not been run | `docs/BENCHMARK_PLAN.md` (E1 to E5), `docs/BOARD_RUN_PROTOCOL.md` (B0, B1), `docs/NO_PURCHASE_PLAN.md`, `bench/mcu/` | nothing has been measured on a real microcontroller |

No purchase is needed for any planned step: an emulator (QEMU or Renode) checks correctness and sizes, and borrowed lab hardware gives real cycle counts (`docs/NO_PURCHASE_PLAN.md`).

## Verification

Independent verifiers re-opened the sources. Phase 1 sampled 50 rows. Phase 2 checked all 157 rows behind a headline number and a seeded stratified random sample of 120 further rows. Phase 2 combined (headline plus random) strict row error rate: 15 of 269 verifiable rows (5.6 percent), with 1 wrong value in 655 compared fields; the other 14 were rounded KB figures that the table left empty and now records verbatim. 8 rows could not be verified because the source stayed blocked. The 46 + 45 rows added later from author supplied PDFs were each checked by finding the value in the named table, not by the independent verifiers, and are outside these rates. Details: `docs/VERIFICATION.md` (phase 1) and `docs/VERIFICATION2.md` (phase 2). The 403 S10 rows were each rechecked by a fresh reader: 0 transcription errors, and 41 of 403 rows needed a fix to a column mapping or a warning (`docs/VERIFICATION3.md`). A second reader then checked a seeded sample of 120 of those rows field by field and found 0 errors (95 percent upper bound 2.5 percent), and a column lint over all rows found 21 warning errors, now fixed (same file). The pqm4 benchmark clock is unresolved in the project's own files and is stated as such (`data/raw/S6_pqm4_config.md`). A second, independent run of the same brief was merged in: its 582 rows are kept as raw input in `data/second_run/` and compared with this table in `docs/CROSSCHECK.md`.

Predictions were written before the phase 2 runs and are scored in `docs/PREDICTIONS.md`. The second round predictions were hashed before any run (`docs/PREDICTIONS_V2.md`) and are scored by script in `docs/PREDICTIONS_V2_SCORES.md`; decisions and deviations are in `docs/RUN_LOG.md`, and what only the author can supply is in `docs/NEEDS_FROM_AUTHOR.md`.

## Contents

| Path | What |
|---|---|
| `docs/PROPOSAL_ATRC.md` | two page research proposal, numbers filled from the result files by `scripts/build_proposal.py` |
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
| `bench/` | harness for on device tests (host tested only), statistics and power analysis, host measurements |
| `scripts/`, `tests/`, `.github/workflows/ci.yml` | build, checks and continuous integration |

## Checks that run on every push

`scripts/check_repo_policy.py` fails if a paper, a PDF outside a two file allowlist, an archive, a saved web page or a vendored library is committed. `scripts/scan_secrets.py` is a secrets scan. `scripts/check_style.py` is a text lint. Generated files (evidence table, report markdown, verification summary) are regenerated in CI and must match the committed copies.

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
