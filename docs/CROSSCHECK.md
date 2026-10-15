# Cross check of two independent runs

Author: Huda Mueen. Date: 2026-10-15.

The same brief was run twice in separate sessions. To avoid two half versions, this repository is the single home. The second run's evidence table (582 rows) is kept unedited in `data/second_run/evidence_second_run.csv`, its four research notes are in `data/raw/S9_second_run_*.md`, and the comparison was produced by `scripts/crosscheck_second_run.py` (output in `data/crosscheck/`).

## Result

| Result | Rows | Meaning |
|---|---|---|
| Matched | 299 | same value and same source as a row here |
| Only in the second run | 245 | not in this table |
| No number | 38 | text claims, no value to compare |

By source family: pqm4 210 matched and 28 only in the second run (all 28 are FN-DSA rows); NIST 32 matched and 7 only second; arXiv 54 matched and 62 only second; ePrint 3 matched and 46 only second; RFC 0 matched and 40 only second; other 0 matched and 62 only second.

## What this tells us

1. **The two runs agree where they overlap.** All 210 comparable pqm4 rows matched. Independent agreement on a value is a consistency check, not proof that either run read the source correctly.
2. **The ePrint 2020/470 rows** (45 only in the second run at comparison time) were rechecked against the supplied PDF by finding each value in the named table, and promoted as stream S8 (`data/raw/S8_verified.csv`). They are outside the independent verification rates, as stated in the README.
3. **The other only in second rows are not promoted.** The second run checked only a sample of 30 rows at its first phase. The 62 arXiv, 40 RFC and 62 other rows stay unverified until each source is read. They are not in `data/evidence.csv` and must not be cited.
4. **pqm4 clock.** The project's own files leave the pqm4 benchmark clock unresolved (README wording and board code disagree). The second run states one value; that is a disagreement to resolve from the pqm4 repository at a pinned commit, not a result.

## Not yet merged

The second run's later work (protocol cost calculator, fleet planner, cross check tool, a 120 row verification and a 194 claim audit) lives in a bundle that is not on disk here. It will be reviewed and merged when the files are supplied. Until then nothing from it is used.
