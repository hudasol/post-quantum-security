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
