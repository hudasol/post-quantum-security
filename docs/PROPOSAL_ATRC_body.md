# Proposal: the real cost of post quantum cryptography on drone and robot microcontrollers

Author: Huda Mueen. Draft of {{date}}. Generated from `docs/PROPOSAL_ATRC_body.md` by `scripts/build_proposal.py`; every number below is read from a file in this repository.

## 1. Problem

Drones and robots authenticate commands, firmware and telemetry with classical public key cryptography on microcontroller class flight computers and narrow radio links. The replacements are standardised (ML-KEM and ML-DSA, FIPS 203 and 204; `docs/REPORT.md`), and some buyers now set dates: the NSA CNSA 2.0 FAQ expects new national security system acquisitions to comply from 1 January 2027 and fielded equipment that cannot comply to be phased out by 31 December 2030 (`data/raw/S10_cnsa_faq.md`, rows 24 and 25; US guidance, not binding elsewhere). An operator cannot yet answer three plain questions from evidence: what the new algorithms cost on the actual flight controller, what they cost on the actual link, and which devices in a fleet can be migrated by a firmware update.

## 2. Gap found in the evidence

The repository holds {{n_rows}} published rows with source, location and comparability warning (`data/evidence.csv`), {{n_s10}} of them added in this round from six papers and each rechecked by a fresh reader (`docs/VERIFICATION3.md`). Four gaps remain:

1. **No cycle count for one fixed firmware on one recorded board.** Published counts mix libraries, clocks and statistics; even the pqm4 benchmark clock is unresolved in the project's own files (`data/raw/S6_pqm4_config.md`).
2. **Memory varies by an order of magnitude.** ML-DSA-44 signing needs {{emu_sign}} B of stack in the portable C build run in the emulator, against {{min_sign}} B in the smallest published signing memory figure ({{min_sign_id}}), a factor of {{sign_ratio}} (`docs/PREDICTIONS_V2_SCORES.md`, Q1.5). Which one a flight controller can afford is a design decision, not a footnote.
3. **Link costs are estimated, not measured.** Only one published link timing is in the table: a TLS handshake over an emulated 57.6 kbps link on a PC (ePrint 2026/2343, Table 5).
4. **No real fleet profile.** The planner has been tested only on invented fleets (`docs/PLANNER_STUDY.md`).

## 3. Research questions

RQ1. What are the cycle counts and stack of ML-KEM-768 and ML-DSA-44 on a Cortex-M4F and a Cortex-M33 for one pinned firmware, and how far are they from the published figures?
RQ2. How long do a hybrid handshake and a signed firmware update take on drone radio links, and how well does a size based model predict a measured link?
RQ3. For a representative flight controller, which migration class (firmware update, hybrid, hardware replacement) follows, and which input decides it?
RQ4. Which reporting rules make such numbers comparable across studies (starting from the recommendations of ePrint 2026/1333, rows S10C in `data/evidence.csv`)?

## 4. Method

Predictions are written and hashed before every run, then scored with misses kept (`docs/PREDICTIONS_V2.md`, `docs/PREDICTIONS_V2_SCORES.md`). Evidence enters the table only through staging, a fresh reader check and a merge script. Five labels are never mixed: published, host measured, emulated, estimated, planned. Board runs follow `docs/BOARD_RUN_PROTOCOL.md`: reproduce pqm4 first, then the repository harness, three power cycles, clock and flash wait states read back at run time.

## 5. Work plan (six months, part time)

| Month | Milestone | Output |
|---|---|---|
| 1 | Board session B0 and B1 on a borrowed Cortex-M4F | first board measured cycle and stack table; pqm4 clock question settled for that board |
| 2 | Cortex-M33 board and stack optimised variants | second panel; memory against speed trade off |
| 3 | Link measurement on a borrowed telemetry radio pair | measured handshake times to validate the duty cycle, fragmentation and loss parts of the link model |
| 4 | Flight controller case study with the planner | migration class and sensitivity for one real profile |
| 5 to 6 | Report, reporting checklist, paper draft | updated report and an open method note |

## 6. Already done in this repository

1. Evidence: {{n_rows}} rows; fresh reader check of the {{n_s10}} new rows found 0 transcription errors (rule of three upper bound {{rule3}} percent) but {{v3_any}} rows needing a column or warning fix ({{v3_rate}} percent) (`docs/VERIFICATION3.md`).
2. Emulation: {{emu_builds}} builds (two cores, three optimisation levels) pass every correctness check; Cortex-M33 and Cortex-M4 stack marks agree (largest difference {{m33_diff}} percent) (`bench/mcu/qemu_results/ANALYSIS.md`).
3. Link model: {{trials}} seeded trials per cell. With no loss, the hybrid handshake takes {{sik_s}} s on a SiK radio and {{lora_h}} h on LoRaWAN EU868 DR0 (`docs/LINKSIM_STUDY.md`). Against the one published link figure the model underestimates absolute time by {{val_lo}} to {{val_hi}} percent but predicts the post quantum minus classical difference within {{val_diff}} percent.
4. Planner: 0 memory limit violations on synthetic fleets of up to 1000 devices; the inputs that move the most devices are {{tornado_inputs}} ({{tornado}} percent of the fleet) (`docs/PLANNER_STUDY.md`).
5. Host baseline: rank order agrees with published counts (Spearman {{rho}}), but run medians drift by up to {{cv}} percent, so host times are used for nothing else (`bench/host/native/RESULTS.md`).
6. Predictions: {{p_hit}} hit, {{p_partial}} partial, {{p_miss}} miss of {{p_total}} (`docs/PREDICTIONS_V2_SCORES.md`).

## 7. Risks

Board access may slip (mitigation: the firmware is built and emulator tested, so a session takes half a day). pqm4 is announced for archiving after January 2027 (mitigation: clone at the pinned commit now). Standards are moving: as read on 2026-10-11, FIPS 206 for FN-DSA was not published and the HQC standard was pending (`data/raw/S1_standards.md`, rows 5 and 7 to 8). The fresh reader check used one reader per set. The link model is validated on one bandwidth bound link only.

## 8. The ask

1. **Supervision** by a researcher in embedded security or communications, about one hour a fortnight.
2. **A borrowed STM32 board** (Cortex-M4F, ideally NUCLEO-L4R5ZI, and if possible a Cortex-M33 board) for half a day per month (`docs/NEEDS_FROM_AUTHOR.md`).
3. **Access to one representative flight controller profile**: core, clock, free RAM and flash after the flight stack, link type and rate.

## 9. Limits, stated plainly

Nothing in this repository has yet been measured on a real microcontroller. Emulated figures give stack and size, never cycles. Host timings on this laptop were unstable. Fleets are synthetic. The link model ignores TCP behaviour and assumes independent frame loss.
