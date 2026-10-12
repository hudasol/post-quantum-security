# Verification of data/evidence.csv (independent re-check)

Date: 2026-10-11. Verifier: independent subagent that did not collect the data. Protocol reference: docs/PROTOCOL.md sections 5, 6, 9 (and D1, D3).

## Method

- Sample: `data/verification_sample.csv`, 50 rows drawn at random from `data/evidence.csv` with seed **20261011** (drawn by `scripts/draw_verification_sample.py`, not re-run here).
- Retrieval: every distinct `source_url` (17 URLs) re-fetched by me with `curl -L` through the sandbox egress proxy (TLS verification on, proxy not unset, no mirrors, caches or archives). All 17 returned HTTP 200. PDFs were read with `pdftotext -layout`; HTML was stripped to text. Downloads were kept in a fresh scratch directory and treated as data only (python run with `-I`).
- pqm4 `benchmarks.csv` as retrieved on 2026-10-11: 573 lines, sha256 `4e4ca381d5deecb0ee845a6fa26047818e913d3422dc3adecf716e2ca4fc59f6`. The README was fetched from raw.githubusercontent.com for clock, compiler and board statements.
- For each row I located the cited table, line or slide and compared every populated field among cycles, ram_bytes, stack_bytes, flash_or_code_bytes, energy_uj, key_or_sig_size_bytes, clock_mhz, scheme, parameter_set, operation, device, core, library, library_version, compiler_flags_or_notes (numeric claims inside it), and whether `comparability_warning` is contradicted. I checked that numbers sit in the correct row and column (operation, parameter set, implementation), the units (k, M, kcc, mJ vs uJ) and, for pqm4, line numbers plus min/max and execution counts.
- Unit conversions (thousand-cycles, 10^6 clk, M-cycles, mJ) are recorded as `unit-conversion-ok` when the claimed value equals the published number times the exact factor.
- One field-level line per (row, field) is in `data/verification_results.csv` (518 lines). Nothing in `data/evidence.csv` was changed.

## Per-row summary

Columns: fields checked | match | unit-conversion-ok | mismatch | not-in-source | unverifiable-source-unreachable.

| id | fields checked | match | unit-conv-ok | mismatch | not-in-source | unreachable | result |
|---|---|---|---|---|---|---|---|
| S2-0251 | 11 | 10 | 1 | 0 | 0 | 0 | all checkable fields agree |
| S2-0086 | 12 | 11 | 0 | 0 | 0 | 1 | 11 fields agree; 1 unverifiable |
| S2-0158 | 12 | 11 | 1 | 0 | 0 | 0 | all checkable fields agree |
| S2-0149 | 12 | 11 | 1 | 0 | 0 | 0 | all checkable fields agree |
| S2-0179 | 13 | 12 | 1 | 0 | 0 | 0 | all checkable fields agree |
| S2-0229 | 11 | 10 | 1 | 0 | 0 | 0 | all checkable fields agree |
| S2-0390 | 11 | 10 | 1 | 0 | 0 | 0 | all checkable fields agree |
| S2-0028 | 12 | 11 | 0 | 0 | 0 | 1 | 11 fields agree; 1 unverifiable |
| S2-0019 | 12 | 11 | 0 | 0 | 0 | 1 | 11 fields agree; 1 unverifiable |
| S2-0127 | 11 | 10 | 1 | 0 | 0 | 0 | all checkable fields agree |
| S3-023 | 6 | 6 | 0 | 0 | 0 | 0 | all checkable fields agree |
| S2-0327 | 10 | 10 | 0 | 0 | 0 | 0 | all checkable fields agree |
| S2-0091 | 11 | 10 | 1 | 0 | 0 | 0 | all checkable fields agree |
| S2-0282 | 11 | 11 | 0 | 0 | 0 | 0 | all checkable fields agree |
| S2-0173 | 13 | 12 | 1 | 0 | 0 | 0 | all checkable fields agree |
| S2-0348 | 11 | 11 | 0 | 0 | 0 | 0 | all checkable fields agree |
| S2-0107 | 11 | 10 | 1 | 0 | 0 | 0 | all checkable fields agree |
| S2-0409 | 6 | 6 | 0 | 0 | 0 | 0 | all checkable fields agree |
| S2-0007 | 12 | 11 | 0 | 0 | 0 | 1 | 11 fields agree; 1 unverifiable |
| S2-0228 | 11 | 10 | 1 | 0 | 0 | 0 | all checkable fields agree |
| S2-0324 | 10 | 10 | 0 | 0 | 0 | 0 | all checkable fields agree |
| S2-0213 | 13 | 11 | 2 | 0 | 0 | 0 | all checkable fields agree |
| S2-0399 | 6 | 6 | 0 | 0 | 0 | 0 | all checkable fields agree |
| S2-0332 | 10 | 10 | 0 | 0 | 0 | 0 | all checkable fields agree |
| S2-0032 | 12 | 11 | 0 | 0 | 0 | 1 | 11 fields agree; 1 unverifiable |
| S3-012 | 9 | 4 | 1 | 0 | 0 | 4 | 5 fields agree; 4 unverifiable |
| S2-0212 | 13 | 11 | 2 | 0 | 0 | 0 | all checkable fields agree |
| S2-0296 | 11 | 11 | 0 | 0 | 0 | 0 | all checkable fields agree |
| S2-0223 | 11 | 9 | 2 | 0 | 0 | 0 | all checkable fields agree |
| S2-0326 | 10 | 10 | 0 | 0 | 0 | 0 | all checkable fields agree |
| S3-037 | 5 | 5 | 0 | 0 | 0 | 0 | all checkable fields agree |
| S2-0428 | 6 | 6 | 0 | 0 | 0 | 0 | all checkable fields agree |
| S2-0397 | 6 | 6 | 0 | 0 | 0 | 0 | all checkable fields agree |
| S2-0202 | 13 | 11 | 2 | 0 | 0 | 0 | all checkable fields agree |
| S2-0063 | 12 | 11 | 0 | 0 | 0 | 1 | 11 fields agree; 1 unverifiable |
| S3-014 | 8 | 8 | 0 | 0 | 0 | 0 | all checkable fields agree |
| S2-0193 | 13 | 11 | 2 | 0 | 0 | 0 | all checkable fields agree |
| S2-0302 | 11 | 11 | 0 | 0 | 0 | 0 | all checkable fields agree |
| S2-0385 | 11 | 10 | 1 | 0 | 0 | 0 | all checkable fields agree |
| S2-0123 | 11 | 10 | 1 | 0 | 0 | 0 | all checkable fields agree |
| S2-0059 | 12 | 11 | 0 | 0 | 0 | 1 | 11 fields agree; 1 unverifiable |
| S3-029 | 5 | 5 | 0 | 0 | 0 | 0 | all checkable fields agree |
| S2-0225 | 11 | 10 | 1 | 0 | 0 | 0 | all checkable fields agree |
| S2-0152 | 12 | 11 | 1 | 0 | 0 | 0 | all checkable fields agree |
| S2-0026 | 12 | 11 | 0 | 0 | 0 | 1 | 11 fields agree; 1 unverifiable |
| S3-007 | 9 | 0 | 0 | 0 | 0 | 9 | not verifiable (Table 8 unreachable) |
| S2-0033 | 12 | 11 | 0 | 0 | 0 | 1 | 11 fields agree; 1 unverifiable |
| S3-005 | 9 | 0 | 0 | 0 | 0 | 9 | not verifiable (Table 8 unreachable) |
| S2-0239 | 11 | 10 | 1 | 0 | 0 | 0 | all checkable fields agree |
| S3-034 | 5 | 5 | 0 | 0 | 0 | 0 | all checkable fields agree |

## Results (counts, unrounded)

- Rows sampled: 50. Rows verifiable: 48. Rows not verifiable: 2 (S3-005, S3-007; see below).
- Rows with at least one mismatch or not-in-source: 0 of 48. **Row-level error rate = 0/48.**
- Field lines recorded: 518 = 460 match + 27 unit-conversion-ok + 0 mismatch + 0 not-in-source + 31 unverifiable-source-unreachable.
- Fields verifiable: 487 (460 + 27). **Field-level error rate = 0/487.**
- Zero corrections are required to the values in the sample.

Caveat on the zero: the sample contains 50 rows of a larger table. A 0/48 row result does not bound the population error rate tightly (a one-sided 95% upper bound is roughly 6%, rule of three). The sample is also dominated by pqm4 (9 rows), arXiv 2603.19340 (6) and standards sizes (8).

## Unverifiable rows and fields

| id | what | why |
|---|---|---|
| S3-005 | all fields (Kyber768 KeyGen, claimed 23000 cycles) | Value only in Table 8 of eprint 2026/312 PDF. `eprint.iacr.org/2026/312.pdf` returns HTTP 403 (Cloudflare challenge, consistent with D3). The abstract page (HTTP 200) does not contain it. No mirror used. |
| S3-007 | all fields (Kyber768 Dec, claimed 35000 cycles) | Same as S3-005. |
| S3-012 | device, core, library, compiler_flags_or_notes | Cycles (1230K, masked Dilithium3 signing) is confirmed by the abstract text; Table 8 and the FPGA/toolchain details are not reachable. |
| 9 pqm4 rows (S2-0086, 0028, 0019, 0007, 0032, 0033, 0063, 0059, 0026) | commit hashes inside `library_version` (HEAD 5e5cc76d0b07, 2026-09-04; file last changed 90bfb630e536, 2025-05-22) | Not in the file; GitHub API from this session returns 403 ("access not enabled"). The compiler (gcc 11.3.1 20220712), 24 MHz and board statements in the README did match. |

## Observations that are not value errors

1. S2-0390 and S2-0385: `location_in_source` lists three candidate tables. The correct ones are Table 2 (S2-0390, XMSSMT row) and Table 3 (S2-0385, LMS/HSS row). PROTOCOL section 5 wants the exact location.
2. S3-023: the sentence giving the server key_share size (1665 bytes, 1568 + 97) is in Section 4.2 (Server Share), not 4.1. The value is right. The client share is also 1665 bytes.
3. arXiv 2603.19340 rows (S2-0228, 0229, 0225, 0223, 0239): the cycles are the paper's published kilocycle figures times 1000 (for example 3,148 kc). The mean in ms times 125 differs slightly because of the paper's rounding (25.18 ms x 125 = 3,147,500). The claimed value equals the published figure, so I recorded it as unit-conversion-ok.
4. S2-0251: the energy figure 48.87 mJ is in the appendix text; the discussion section rounds it to 48.9 mJ. The claim matches the appendix. It is a constant-power estimate, as the row's note states.
5. S2-0348: the core field is blank, and the row warning says to confirm the core from the ST datasheet. The wolfSSL page does not state the core, so I could not confirm it from the cited source.
6. pqm4 rows give core as Cortex-M4F. The pqm4 README says only "Cortex-M4"; M4F for the Nucleo-L4R5ZI is stated in arXiv 2604.15868 (p.17).
7. The pqm4 file can change after 2026-10-11; the values above refer to the sha256 given.

## Corrections needed

None. No (id, field) pair in the sample differs from its source.

Suggested documentation fixes (not value corrections): items 1 and 2 above.


## Second pass: prose claims in the report (2026-10-11)
A separate subagent (not the data collector nor the report author) checked 54 non-table claims in REPORT.md, 26 against live primary sources (NIST, NCSC, EU roadmap, IETF, mavlink.io, PX4, wolfBoot, TF-M, GRI, arXiv) and the rest against the research notes; 1 was unverifiable (ASD page unreachable). It found 6 defects in 53 gradable claims (about 11%), one substantive (CVE number: 49601 should be 49600), the rest precision or labelling (IR 8547 deprecation applies to 112-bit strength only; ArduPilot's bootloader algorithm is not stated in the docs read; "some vendor parts ship PQ verification" overstated vendor claims; 36x should be 36.5x; two untagged inferences). All were corrected in REPORT_body.md; the CVE number was also corrected in data/raw/S3_robotics.md. It also flagged that the wolfBoot blog's 320 MHz for the STM32H563 exceeds the 250 MHz maximum Zephyr lists for the NUCLEO-H563ZI; the report now says so. No invented facts were found. Table-row verification (0/48) is reported above; this second figure covers prose, not table rows.
