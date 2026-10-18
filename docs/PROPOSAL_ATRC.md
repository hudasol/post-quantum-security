# Proposal: the real cost of post quantum cryptography on drone and robot microcontrollers

Author: Huda Mueen. Draft of 2026-10-16. Generated from `docs/PROPOSAL_ATRC_body.md` by `scripts/build_proposal.py` (do not edit by hand); every number below is read from a file in this repository.

## 1. Problem

Drones and robots authenticate commands, firmware and telemetry with classical public key cryptography on microcontroller flight computers and narrow radio links. The replacements are standardised (ML-KEM and ML-DSA, FIPS 203 and 204; `docs/REPORT.md`), and buyers set dates: for US national security systems only, the CNSA 2.0 FAQ (Ver. 2.1, December 2024) expects compliant new acquisitions from 2027 and asks for ML-KEM-1024, ML-DSA-87 and LMS or XMSS for firmware (`data/raw/S10_cnsa_faq.md`, rows 4, 5, 7, 24). An operator still cannot say from evidence what the new algorithms cost on its flight controller, on its link, or across its fleet.

## 2. Gap in the evidence

`data/evidence.csv` holds 971 published rows, each with source, location and warning. Cortex-M33 cycles exist only for ML-DSA key generation and signing, from one paper (rows S10C); none for ML-KEM or verification. ML-DSA-44 signing memory spans a factor of about 9.9 between implementations (5,064 B published, S2-0176, against 50,040 B in this repository's emulated portable C build). Link costs rest on a model checked against one published link figure. No figure comes from a flight controller running its flight stack.

## 3. Research questions

RQ1. Cycles and stack of all six ML-KEM and ML-DSA parameter sets on a Cortex-M4F and a Cortex-M33 for one pinned firmware, against published figures.
RQ2. Handshake and signed update time on drone radios, with the duty cycle, fragmentation and loss parts of the model checked against a measured link.
RQ3. The migration class of each device for a real flight controller profile, as a range over implementations.
RQ4. Reporting rules that make such numbers comparable (from ePrint 2026/1333, rows S10C).

## 4. Method

Predictions are hashed before each run and scored by script against their refutation clauses; misses stay (`docs/PREDICTIONS_V3.md`). Rows enter the table through staging, a fresh reader check and a merge script. Five labels are kept apart: published, host measured, emulated, estimated, planned. Board runs follow `docs/BOARD_RUN_PROTOCOL.md`.

## 5. Work plan (six months, part time)

| Month | Milestone |
|---|---|
| 1 | Borrowed Cortex-M4F board: reproduce pqm4, then run the repository firmware (first board measured table) |
| 2 | Cortex-M33 board; stack against speed trade off |
| 3 | Borrowed telemetry radio pair: measured handshake times to check duty cycle, fragmentation and loss |
| 4 | Case study on [FLIGHT CONTROLLER PROFILE: to be supplied] |
| 5 to 6 | Report, reporting checklist, paper draft |

## 6. Already done

1. Evidence: 971 rows. A fresh reader rechecked all 403 rows added in October 2026 (0 numbers copied wrongly; 41 column or warning fixes), and a second reader found 0 errors in a seeded sample of 120 (95 percent upper bound 2.5 percent). A column lint over all rows found and fixed 21 more warning errors (`docs/VERIFICATION3.md`).
2. Emulated: 36 builds on Cortex-M4 and Cortex-M33 models pass every check; a second emulator (Renode) gives the same stack to the byte for 4 builds. No cycles (`bench/mcu/qemu_results/ANALYSIS.md`).
3. Estimated: the link model predicts the published rate bound handshakes within 0.7 percent on three held out groups after one constant is fitted on two others, but is 6.6 times faster than a published 802.15.4 transfer range; its duty cycle, fragmentation and loss parts are unvalidated (`docs/LINKSIM_STUDY.md`).
4. Estimated, synthetic fleet: hardware replacements in 1000 devices range from 260 to 382 depending on the implementation the thresholds assume (`docs/PLANNER_STUDY.md`).
5. Host measured: ranks agree with published cycle counts (Spearman 0.979), within run ratios lie within 22 percent of published ratios; used for ratios only (`bench/host/native_v3/RESULTS.md`).

## 7. What this study does not show

I have not measured anything on a microcontroller: every cycle count is someone else's, and the emulators give stack and size only. My link model is checked on one bandwidth bound link; on 802.15.4 it is several times too optimistic, and its duty cycle, fragmentation and loss parts have no published measurement behind them. My fleet results come from invented devices and swing by the implementation assumed. The table has had one full fresh reading and one sampled second reading for its newest rows; older rows were checked by sampling.

## 8. Risks

Board access may slip (the firmware is emulator tested, so a session takes half a day). pqm4 may be archived after January 2027 (clone the pinned commit now). Standards move (FN-DSA and HQC standards were pending when read; `data/raw/S1_standards.md`).

## 9. The ask

1. Supervision: [SUPERVISOR: to be named], about one hour a fortnight.
2. A borrowed STM32 Cortex-M4F board, and if possible a Cortex-M33 board, for half a day a month (`docs/NEEDS_FROM_AUTHOR.md`).
3. One representative flight controller profile: core, clock, free RAM and flash after the flight stack, link type and rate.
