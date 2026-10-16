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
emu = list(csv.DictReader(open('bench/mcu/qemu_results/checks.csv'))); n_emu = len(emu); n_emu_ok = sum(1 for r in emu if r['fail'] == '0')
txt = f"""# Post quantum cryptography on drone and robot computers

A sourced review of what post quantum cryptography costs on microcontroller class computers in drones and robots, with a link simulator, a fleet migration planner and a benchmark plan. Author: Huda Mueen. Evidence retrieved 2026-10-11 and 2026-10-12; supplied papers read 2026-10-16.

**For a research director:** `docs/PROPOSAL_ATRC.md` (2 pages: problem, gap, questions, plan, ask).

**Start here:** `docs/EXECUTIVE_BRIEF.pdf` (2 pages), then `docs/REPORT.pdf` (`docs/REPORT.md`).

## What is published, host measured, estimated and planned

Every number in this repository carries one of five labels (the fifth, emulated, was added in phase 2). They are never mixed in one table or one axis.

| Label | Meaning | Where it lives | Count or status |
|---|---|---|---|
| **Published** | Copied from a source that was actually retrieved, with URL, retrieval date and location in the source | `data/evidence.csv` | {n_pub} rows ({n_s2} benchmark and size rows, {n_s3} protocol and size rows, {n_s7} benchmark and size rows read from author supplied PDFs in phase 2, {n_s8} cycle and stack rows from the LMS and XMSS paper found by the second run and rechecked against the PDF, {n_s10} rows read on 2026-10-16 from six more author supplied PDFs and rechecked in full by a fresh reader); {n_pq} come from the pqm4 project |
| **Host measured** | Run on a PC or server, never on a microcontroller | `bench/host/` | {hk} liboqs timing records; native timings of the emulated code in `bench/host/native/` (used for rank order only, see its limits) |
| **Estimated** | Arithmetic from published sizes or rates, formula shown, "estimated from published sizes, not measured" | `linksim/`, `docs/link_tables.md`, `docs/LINKSIM_STUDY.md` (Monte Carlo, sweeps, validation), `docs/LINK_REFERENCE_DESIGN.md`, `docs/PLANNER_RULES.md` thresholds, `docs/PLANNER_STUDY.md` (synthetic fleets), derived times in the report | all derived |
| **Emulated** | Run on an emulated Cortex-M4 (QEMU). Correctness, stack and image size only; no cycle counts | `docs/EMULATOR_RESULTS.md`, `bench/mcu/qemu_results/` | {n_emu} builds (Cortex-M4 and Cortex-M33, three optimisation levels), {n_emu_ok} passed every check |
| **Planned** | An experiment that has not been run | `docs/BENCHMARK_PLAN.md` (E1 to E5), `docs/BOARD_RUN_PROTOCOL.md` (B0, B1), `docs/NO_PURCHASE_PLAN.md`, `bench/mcu/` | nothing has been measured on a real microcontroller |

No purchase is needed for any planned step: an emulator (QEMU or Renode) checks correctness and sizes, and borrowed lab hardware gives real cycle counts (`docs/NO_PURCHASE_PLAN.md`).

## Verification

Independent verifiers re-opened the sources. Phase 1 sampled 50 rows. Phase 2 checked all {S['headline']['rows']} rows behind a headline number and a seeded stratified random sample of {S['random']['rows']} further rows. Combined strict row error rate: {int(c['error'])} of {ver} verifiable rows ({100*int(c['error'])/ver:.1f} percent), with {c['wrong_fields']} wrong value in {c['populated']} compared fields; the other {c['missing_only_rows']} were rounded KB figures that the table left empty and now records verbatim. {c['unverifiable']} rows could not be verified because the source stayed blocked. The {n_s7} + {n_s8} rows added later from author supplied PDFs were each checked by finding the value in the named table, not by the independent verifiers, and are outside these rates. Details: `docs/VERIFICATION.md` (phase 1) and `docs/VERIFICATION2.md` (phase 2). The {n_s10} S10 rows were each rechecked by a fresh reader: 0 transcription errors, and {v3['any']} of {v3['rows']} rows needed a fix to a column mapping or a warning (`docs/VERIFICATION3.md`). The pqm4 benchmark clock is unresolved in the project's own files and is stated as such (`data/raw/S6_pqm4_config.md`). A second, independent run of the same brief was merged in: its 582 rows are kept as raw input in `data/second_run/` and compared with this table in `docs/CROSSCHECK.md`.

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
"""
open('README.md', 'w').write(txt)
print(len(txt.split()), 'words')
