# Run log, second study round (2026-10-16)

Author: Huda Mueen. One line per decision, stop or deviation, in time order. Predictions for this round were hashed and committed before any run (`docs/PREDICTIONS_V2.md`, commit `59bd903`).

| # | Package | Event | Decision |
|---|---|---|---|
| 1 | setup | The remote `main` was ahead of the local copy by seven commits (second run cross check). | Fast forwarded before any work; no local changes were pending. |
| 2 | setup | Every commit made before this round carries an author name and address that are not the author's own. | Rewriting history is not allowed in this round. Recorded in `docs/NEEDS_FROM_AUTHOR.md` item 2 for the author to decide. New commits carry the author's name. |
| 3 | WP1 | `scripts/merge_evidence.py` regenerated `data/evidence.csv` byte for byte (568 rows); README, report and CSV agreed on 568; CI green. | Gate passed; no change needed. |
| 4 | WP5 | A Windows checkout turned the shell scripts into CRLF line endings, which bash under WSL cannot run. | Added `.gitattributes` (LF for scripts and C build files). The stored files were already LF. |
| 5 | WP5 | No administrator rights in the Linux environment, so QEMU could not be installed with the package manager. | Downloaded the Ubuntu archive packages of QEMU 10.2.1 and its libraries and unpacked them in a user folder. Free, no account. |
| 6 | WP2 | The paper ePrint 2021/781 reports signing cost in KiloTicks; the extraction converted them to cycles. The fresh reader found the paper does not establish that a tick is one CPU cycle. | 38 rows keep the ticks verbatim in the warning with an empty cycles cell (`scripts/promote_s10.py`). Counted as errors in `docs/VERIFICATION3.md`. |
| 7 | WP2 | Three RISQrypt warnings misdescribed what a Table 9 figure covers. | Sentences replaced by `scripts/promote_s10.py`; counted as errors. |
| 8 | WP3 | The new end to end simulator test draws figures, and the CI test job had no plotting library. | CI installs matplotlib in the test job; fixed before CI reported a failure. |
| 9 | WP4 | The first run of the new monotonicity property test failed: the test raised free memory above total memory, which the loader correctly rejects as invalid. | The test was wrong, not the planner. The test now raises free memory up to the device total. |
| 10 | WP5 | Renode has no platform description for the MPS2 boards used here. | Not tried; porting belongs with the real board run. Recorded in `docs/EMULATOR_RESULTS.md`. |
| 11 | WP3, WP4 | Regenerating the first round figures in `plots/` changed only the PNG bytes (a different plotting library build), not the rows behind them. | Not committed, to avoid churn; the row lists in `plots/*_rows.csv` are unchanged. |
| 12 | WP8 | The report changed (971 rows), but pandoc and XeLaTeX are not installed and the TeX packages need administrator rights to install and configure. | PDFs not rebuilt; the README says they show the earlier 568 row version. Listed in `docs/NEEDS_FROM_AUTHOR.md` item 5. |
| 13 | WP6 | Host run medians drifted by up to 37.5 percent between runs on the laptop's Linux virtual machine. | Reported as measured (prediction Q5.1 missed). A within run ratio check was added after seeing the data and is labelled post hoc; host numbers are used for rank order only. |
| 14 | review | A fresh reviewer that had seen only the repository listed 38 findings (4 high, 17 medium, 17 low; `docs/REVIEW_FINDINGS.csv`). | 32 fixed, 2 partly fixed, 3 left with a reason, 1 open for the author. |
| 15 | WP2, stop | **Stop condition met:** rows S10C-001 to S10C-036 (ePrint 2026/1333) give ML-DSA cycles on a Cortex-M33 and contradict the report headline that none were published. | The report and brief were corrected and the correction is marked in the report (commit `4a0b857`). Prediction Q1.4, whose first scoring rule could not fail, was rescored as a miss. |
| 16 | review | Public notes described work as done by subagents or a drafting agent, and one note held a local scratch path. | Reworded (commit `ba88503`). One word in the hashed `docs/PREDICTIONS.md` changed; its stored hash still verifies the text committed on 2026-10-11. The earlier commit author field remains open (item 2 of `docs/NEEDS_FROM_AUTHOR.md`). |
| 17 | WP4 | The reviewer showed that the planner's default thresholds assume stack optimised assembly. | Added a portable C threshold scenario: hardware replacements in the 1000 device fleet rise from 246 to 351 (`docs/PLANNER_STUDY.md` section 4). |
| 18 | round 3 | Third round predictions written and hashed before any run (`docs/PREDICTIONS_V3.md`, commit `efd8765`). | Scored by `scripts/score_predictions_v3.py`. |
| 19 | A | Three files still said or implied that no Cortex-M33 cycles were published (benchmark plan, playbook, board notes). | Corrected with dated notes; `scripts/check_claims.py` now fails CI if a retracted claim reappears without a correction marker. |
| 20 | G | The first run of the improved host script failed: the repository path contains spaces and the binary list was split on them. | Fixed with relative paths and rerun; only the second run is recorded. |
| 21 | G | The improved host method steadied the medians, but every operation still had runs about twice as slow (spread up to 120.8 percent). | Reported as measured; the spread prediction R11 is a miss. |
| 22 | B | The column lint first matched the word SysTick and missed table lists such as "Tables 4 and 5". | Rules refined before review; all 40 flags of the refined lint reviewed by hand, 21 real (S8 warnings), fixed through `data/corrections.csv`. |
| 23 | F | pandoc 3.6 emits a macro the repository template does not define. | PDFs built with the `pandoc/latex:3.1` image instead of editing the template. |
| 24 | H | The ASD pages timed out again on 2026-10-18 (two WebFetch attempts). | Left open and in flux; no other route used. |
| 25 | H | Renode cannot parse paths with spaces, and in the background its monitor stopped the machine at end of input. | Files staged in a folder without spaces; the monitor input is kept open for the run. |
| 26 | D | The only published link figure outside Table 5 is a prose statement in ePrint 2021/781, not a table. | Used only as a cross check in `docs/LINKSIM_STUDY.md` 4.2; it does not enter `data/evidence.csv`. |
| 27 | E | `docs/AUTHOR_DECISIONS.md` was written for the author and, as instructed, not committed. | Nothing acted on. |

