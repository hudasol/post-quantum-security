# Proposal: the real cost of post quantum cryptography on drone and robot microcontrollers

Author: Huda Mueen. Draft of 2026-10-16. Generated from `docs/PROPOSAL_ATRC_body.md` by `scripts/build_proposal.py` (do not edit by hand); every number below is read from a file in this repository.

## 1. Problem

Drones and robots authenticate commands, firmware and telemetry with classical public key cryptography on microcontroller class flight computers and narrow radio links. The replacements are standardised (ML-KEM and ML-DSA, FIPS 203 and 204; `docs/REPORT.md`), and some buyers now set dates. The NSA CNSA 2.0 FAQ (Ver. 2.1, December 2024) expects new US national security system acquisitions to comply from 1 January 2027 and non compliant fielded equipment to be phased out by 31 December 2030, unless otherwise noted, and it requires the highest parameter sets (ML-KEM-1024, ML-DSA-87) plus LMS or XMSS for firmware signing (`data/raw/S10_cnsa_faq.md`, rows 4, 5, 7, 24 and 25). It binds only those US systems; it is cited here as an example of buyer pressure, not as a requirement for other operators. An operator cannot yet answer three plain questions from evidence: what the new algorithms cost on the actual flight controller, what they cost on the actual link, and which devices in a fleet can be migrated by a firmware update.

## 2. Gap found in the evidence

The repository holds 971 published rows with source, location and comparability warning (`data/evidence.csv`), 403 of them added in this round from six papers and each rechecked by a fresh reader (`docs/VERIFICATION3.md`). Four gaps remain:

1. **No cycle count for one fixed firmware on one recorded board.** Published counts mix libraries, clocks and statistics; even the pqm4 benchmark clock is unresolved in the project's own files (`data/raw/S6_pqm4_config.md`).
2. **Memory varies by an order of magnitude.** ML-DSA-44 signing needs 50,040 B of stack in the portable C build run in the emulator (*emulated*; the span includes harness frames), against 5,064 B for the smallest published ML-DSA-44 or Dilithium2 signing memory figure in the table (S2-0176, *published*; memory definitions differ between sources), a factor of about 9.9 (`bench/mcu/qemu_results/stack.csv`, `data/evidence.csv`). Which one a flight controller can afford is a design decision, not a footnote.
3. **Link costs are estimated, not measured.** Only one published link timing is in the table: a TLS handshake over an emulated 57.6 kbps link on a PC (ePrint 2026/2343, Table 5).
4. **No real fleet profile.** The planner has been tested only on invented fleets (`docs/PLANNER_STUDY.md`).

## 3. Research questions

RQ1. What are the cycle counts and stack of all six ML-KEM and ML-DSA parameter sets (including ML-KEM-1024 and ML-DSA-87, which CNSA 2.0 requires) on a Cortex-M4F and a Cortex-M33 for one pinned firmware, and how far are they from the published figures? Firmware signing with LMS is a second step (`docs/BENCHMARK_PLAN.md`, E2).
RQ2. How long do a hybrid handshake and a signed firmware update take on drone radio links, and how well does a size based model predict a measured link?
RQ3. For a representative flight controller, which migration class (firmware update, hybrid, hardware replacement) follows, and which input decides it?
RQ4. Which reporting rules make such numbers comparable across studies (starting from the recommendations of ePrint 2026/1333, rows S10C in `data/evidence.csv`)?

## 4. Method

Predictions are written and hashed before every run, then scored with misses kept (`docs/PREDICTIONS_V2.md`, `docs/PREDICTIONS_V2_SCORES.md`). From this round on, evidence enters the table only through staging, a fresh reader check of every row and a merge script; earlier rows were checked by sampling or by finding each value in its table (`README.md`, Verification). Five labels are never mixed: published, host measured, emulated, estimated, planned. Board runs follow `docs/BOARD_RUN_PROTOCOL.md`: reproduce pqm4 first, then the repository harness, three power cycles, clock and flash wait states read back at run time.

## 5. Work plan (six months, part time)

| Month | Milestone | Output |
|---|---|---|
| 1 | Board session B0 and B1 on a borrowed Cortex-M4F | first board measured cycle and stack table; pqm4 clock question settled for that board |
| 2 | Cortex-M33 board and stack optimised variants | second panel; memory against speed trade off |
| 3 | Link measurement on a borrowed telemetry radio pair | measured handshake times to validate the duty cycle, fragmentation and loss parts of the link model |
| 4 | Flight controller case study with the planner | migration class and sensitivity for one real profile |
| 5 to 6 | Report, reporting checklist, paper draft | updated report and an open method note |

## 6. Already done in this repository

1. Evidence: 971 rows; fresh reader check of the 403 new rows found 0 transcription errors (rule of three upper bound 0.74 percent) but 41 rows needing a column or warning fix (10.2 percent) (`docs/VERIFICATION3.md`).
2. Emulation (*emulated*): 36 builds (Cortex-M4 and Cortex-M33 models, three optimisation levels) pass every correctness check, with stack and image size recorded; no cycles (`bench/mcu/qemu_results/ANALYSIS.md`).
3. Link model (*estimated*, with stated assumptions such as a 1 s LoRaWAN turnaround, a 16 fragment window and no LoRaWAN MAC overhead; `linksim/params.csv`): 1000 seeded trials per lossy cell, zero loss cells are deterministic. With no loss, the hybrid handshake takes 1.16 s on a SiK radio and 5.36 h on LoRaWAN EU868 DR0 (`docs/LINKSIM_STUDY.md`). Against the one published link figure the model underestimates absolute time by 29 to 43 percent but predicts the post quantum minus classical difference within 7 percent.
4. Planner (*synthetic fleets*): property tests and fleets of up to 1000 devices show no recommendation that breaks the planner's own memory thresholds; under the default thresholds (stack optimised assembly) the inputs that move the most devices are sig horizon year and service life remaining years (11.2 percent of the fleet), and with portable C thresholds hardware replacements rise from 246 to 351 of 1000 (`docs/PLANNER_STUDY.md`).
5. Host baseline (*host measured*): rank order agrees with published counts across scheme families (Spearman 0.975) but not between ML-DSA-65 and ML-DSA-87, and the coefficient of variation of run medians reaches 38 percent, so host times are used for nothing else (`bench/host/native/RESULTS.md`).
6. Predictions: 20 hit, 1 partial, 5 miss, 1 not scored, of 27; one miss was a new row set contradicting a report headline, which was then corrected (`docs/PREDICTIONS_V2_SCORES.md`).

## 7. Risks

Board access may slip (mitigation: the firmware is built and emulator tested, so a session takes half a day). pqm4 is announced for archiving after January 2027 (mitigation: clone at the pinned commit now). Standards are moving: as read on 2026-10-11, FIPS 206 for FN-DSA was not published and the HQC standard was pending (`data/raw/S1_standards.md`, rows 5 and 7 to 8). The fresh reader check used one reader per set. The link model is validated on one bandwidth bound link only.

## 8. The ask

1. **Supervision** by a researcher in embedded security or communications, about one hour a fortnight.
2. **A borrowed STM32 board** (Cortex-M4F, ideally NUCLEO-L4R5ZI, and if possible a Cortex-M33 board) for half a day per month (`docs/NEEDS_FROM_AUTHOR.md`).
3. **Access to one representative flight controller profile**: core, clock, free RAM and flash after the flight stack, link type and rate.

## 9. Limits, stated plainly

Nothing in this repository has yet been measured on a real microcontroller. The earlier commits of the repository carry an author field that is not the author's own; correcting it is an open decision (`docs/NEEDS_FROM_AUTHOR.md`). Emulated figures give stack and size, never cycles. Host timings on this laptop were unstable. Fleets are synthetic. The link model ignores TCP behaviour and assumes independent frame loss.
