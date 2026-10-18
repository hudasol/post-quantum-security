# Predictions for the third study round (written before any run)

Author: Huda Mueen. Written 2026-10-18, before any experiment of this round was run. The SHA-256 of this file as committed is in `docs/PREDICTIONS_V3.sha256`. This file is never edited after the hash is taken; corrections go in a dated note in `docs/RUN_LOG.md`. Scores are written by `scripts/score_predictions_v3.py` into `docs/PREDICTIONS_V3_SCORES.md`, each against its refutation clause. Misses stay.

What I already knew when writing: everything committed up to `d6ecbb5`, including the published pqm4 stack and code size rows for the `m4fstack`, `m4f`, `m4fspeed` and `clean` implementations (S2-0019 to S2-0036), the round two planner result (246 hardware replacements with stack optimised thresholds, 351 with portable C thresholds, 1000 device fleet), Table 5 of ePrint 2026/2343, and a prose statement in ePrint 2021/781 (page 16) on transfer time over IEEE 802.15.4. Predictions that lean on these are marked informed.

Seeds: the second check sample uses seed `20261018`; the host run order is shuffled with seed `20261018`; planner fleets keep seed `20261016` plus the fleet size. Every output stores its seeds.

| ID | Item | Question | Metric | Method | Prediction | Refuted if |
|---|---|---|---|---|---|---|
| R1 | A | Does the corrected Cortex-M33 claim survive elsewhere? | files outside `docs/REPORT_body.md` and `docs/EXECUTIVE_BRIEF.md` that still state or imply that no ML-KEM, ML-DSA or SLH-DSA cycles were published for a Cortex-M33 | text search over tracked files | at least 2 | none found |
| R2 | B | How accurate are the 403 S10 rows on a second, independent check? | row error rate in a seeded stratified sample of at least 120 rows (any field wrong) | a reader that has not seen any notes compares every field with the PDF | at most 5 percent, with 0 transcription errors | above 10 percent |
| R3 | B | Is a column lint useful on all 971 rows? | rows flagged by the lint | rule based lint for wrong column and wrong warning text | at most 30 rows flagged | more than 60 rows flagged |
| R4 | C | How do the threshold scenarios order? | hardware replacements in the 1000 device fleet | planner under four threshold sets | stack optimised assembly (246, informed) fewer than speed optimised assembly, fewer than portable C emulated (351, informed), at most reference C | any other order |
| R5 | C | How wide is the range? | highest over lowest hardware replacement count, 1000 devices | same | at least 1.4 | below 1.4 |
| R6 | C | How many devices change class between the lowest and the highest scenario? | share of devices, for fleets of 10, 100 and 1000 | same | between 10 and 30 percent for every fleet size | outside that range for any fleet size |
| R7 | D | Can a constant fitted on some Table 5 groups predict the others? | absolute error on held out groups after fitting one fixed overhead term on the training groups | split by name: train P-256 and SMAUG-T1, test ML-KEM-768, SMAUG-T3, NTRU+-768 | at most 10 percent on every held out group | above 15 percent on any held out group |
| R8 | D | Does the model match the 802.15.4 prose figure of ePrint 2021/781? | model time for 50 kB on the 802.15.4 profile against the published 30 to 60 s | prose cross check, not a calibration | model below 30 s by a factor of at least 3 | model inside 30 to 60 s, or below by less than a factor of 3 |
| R9 | D | Is there a published measured figure for the duty cycle or loss parts? | count of such figures in the evidence table and the supplied PDFs | search | 0, so those parts are labelled unvalidated | at least one found |
| R10 | F | Can the PDFs be rebuilt with free tools here? | build result and the PDF author metadata check | pandoc and XeLaTeX through Docker or WSL | build succeeds and the metadata check passes | build fails |
| R11 | G | Does a better host method remove the drift? | largest spread of run medians, (max minus min) over median, over all 18 operations | interleaved shuffled runs, pinned CPU, more repetitions, warm up discarded | at most 10 percent | above 20 percent |
| R12 | G | Is the ML-DSA ordering restored on the host? | order of ML-DSA-44, ML-DSA-65 and ML-DSA-87 signing medians | same | 44 below 65 below 87 | any inversion |
| R13 | H | Can the ASD page be fetched now? | WebFetch result | WebFetch only | still times out | page retrieved |
| R14 | H | Does a free Renode setup run the firmware on a Cortex-M4 target? | ML-KEM-512 image runs to completion with passing checks | Renode, if a free download and an STM32F4 platform exist | yes | no run |
| R15 | I | Does the proposal fit two pages? | words in `docs/PROPOSAL_ATRC.md` | word count by script | at most 950 | more than 1100 |
| R16 | J | What does a second fresh review find? | findings and their severity | reviewer that has seen only the repository | between 3 and 25 findings, none of them a high severity contradiction of a headline number | fewer than 3 findings, or a high severity headline contradiction |
