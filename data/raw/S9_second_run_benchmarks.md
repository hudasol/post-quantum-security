<!-- Raw notes from the second run (phase 1), retrieved 2026-10-11. Kept unedited except this line and the path mentions. Not independently verified except where data/crosscheck says so. -->
# Published implementation benchmarks for PQC on MCU-class devices

Retrieved 2026-10-11. Evidence table: `./data/evidence_benchmarks.csv` (476 rows). Source log: `./data/sources_benchmarks.csv`. All values are tagged `[published]` or `[derived-from-published]` in the notes column; nothing is estimated or host-measured.

## What the evidence covers

| Block | Rows | Device | Notes |
|---|---|---|---|
| pqm4 results (ML-KEM, ML-DSA, SPHINCS+ "simple", provisional FN-DSA) | 238 | Cortex-M4(F), 24 MHz | speed (mean cycles), stack, code size |
| pqm4 ML-DSA cross-check (HAETAE paper, Table 3) | 36 | NUCLEO-L4R5ZI, 20 MHz cycles / 120 MHz stack builds | median of 100 runs |
| RP2040 ML-KEM / ML-DSA (arXiv 2603.19340) | 57 | Cortex-M0+, 125 MHz | PQClean reference C, ms + cycles, stack, flash, classical baselines |
| LMS / XMSS on Cortex-M4 (Campos et al.) | 48 | STM32F4DISCOVERY | cycles and stack, SHA-256, h=5 and h=10 |
| XMSS verification (Bos et al., TCHES 2021) | 6 | FRDM-K64F, 120 MHz | verify cycles under several optimisations |
| SLH-DSA hardware acceleration (SLotH) | 24 | RISC-V control core + hash unit (FPGA/ASIC flow) | not an off-the-shelf MCU |
| BLE PQ key-establishment energy | 3 | nRF52840 + PPK2 | only 3 absolute numbers in text |
| Standard sizes: FIPS 203/204/205, RFC 8554 | 64 | n/a | normative sizes; LMS signature totals and SLH-DSA sk=4n are derived arithmetic |

## Key observations (all from the CSV; no cross-device normalisation)

- **ML-KEM is cheap on Cortex-M4.** pqm4 `m4fspeed` ML-KEM-768: 642,096 / 658,754 / 707,827 mean cycles for keygen / encaps / decaps (24 MHz); `m4fstack` keeps stack at 2,820 / 2,860 / 2,844 bytes versus 5,396 / 6,468 / 6,452 for `m4fspeed`. Portable `clean` C is about 1.5x slower in cycles but code size is smaller (5,120 B vs 16,016 B total for ML-KEM-768).
- **ML-DSA signing is the hard part.** Stack-optimised `m4fstack` ML-DSA-44 needs 4,408 / 5,080 / 2,712 bytes (keygen / sign / verify) versus 38,296 / 44,816 / 8,912 for `m4f`, but signing mean cycles rise from 3,943,121 to 12,134,284 (pqm4 table). The independent median figures in the HAETAE paper show the same trade (3,017 k to 10,330 k cycles). Signing time varies with rejection sampling (min/max in the pqm4 table span roughly 10x).
- **Portable-C ML-DSA on Cortex-M0+ is memory heavy.** Peak signing stack 50.6 KB (ML-DSA-44), 77.6 KB (-65), 119.6 KB (-87); ML-KEM decapsulation stack 9.4 / 14.2 / 20.0 KB (RP2040, PQClean reference C). ML-DSA-44 signing p99 584 ms (n=10,000, -Os).
- **SLH-DSA in software is very slow on M4 (`clean` C).** For example sphincs-sha2-128s-simple signing averages 7,657,558,168 cycles (about 319 s at 24 MHz by simple division, not tabulated), while verification is 7,471,794 cycles. Fast variants (`f`) sign in 368,575,228 cycles (128f-sha2). Hardware hash acceleration (SLotH) cut 128f-SHAKE signing to 4,903,978 cycles, but this is an FPGA/ASIC accelerator, not a stock MCU.
- **Stateful hash-based verification is cheap in time and stack.** Campos et al. (SHA-256, h=10): LMS verify 2,658,884 cycles with 1,044 B stack; XMSS ROBUST (RFC variant) 13,071,813 cycles with 3,896 B. Key generation is very costly (LMS h=10: 3.77 G cycles), which is why signing/keygen would typically happen off-device. Bos et al. brought XMSS-SHA2_10_256 verification from 13.85 M to 6.56 M cycles on a Cortex-M4 at 120 MHz, at the price of extra signer work.
- **Energy.** The only absolute figures extracted: ML-KEM key establishment over BLE on nRF52840 costs 721 to 2,633 uJ across configurations versus about 328 uJ for the classical ECDH P-256 pairing baseline; the paper argues radio/fragmentation cost often dominates. Per-operation computation energy was in figures only, not captured.

## Comparability warnings (apply to the whole table)

1. **Clocks differ**: pqm4 cycles at 24 MHz (README), HAETAE-paper pqm4 numbers at 20 MHz with median rather than mean; RP2040 at 125 MHz; K64F at 120 MHz. Cycles are the only fairly portable unit and even they depend on flash wait states and memory systems.
2. **Cores differ**: Cortex-M4F (hardware multiplier, DSP/SIMD) vs Cortex-M0+ (RP2040 single-cycle multiplier; authors warn results are optimistic for multi-cycle-multiplier M0+). No Cortex-M33, M7 or MCU RISC-V absolute numbers were obtained (see gaps).
3. **Implementation classes differ**: pqm4 `clean`/`ref` (portable C) vs `m4f*` (hand assembly) vs hardware-accelerated. `m4fstack` is a low-stack assembly variant, slower but with a much smaller stack.
4. **Stack/RAM definitions differ**: pqm4 stack excludes caller-allocated keys/ciphertexts/signatures; the RP2040 paper reports "peak stack" and a separate "total RAM" that adds key material; Campos et al. exclude key material and messages. ML-DSA-87 signing needs 17,667 B total including sk and signature when using the low-stack code (HAETAE paper text; not in CSV).
5. **Naming**: pqm4 SPHINCS+ rows use pre-standard "simple" names and FN-DSA rows are "fndsa_provisional" (draft); SLotH uses FIPS 205 initial-public-draft names. Verify parameter equivalence with the final FIPS 205 / FIPS 206 before citing as SLH-DSA / FN-DSA.
6. **Measurement methods**: mean of 100 (or 10, 1000) executions in pqm4; the number of executions is in the CSV warning field. Signing is non-constant-time in iterations. RP2040 uses a microsecond timer (cycles derived).
7. **pqm4 version**: the commit of the fetched results could not be retrieved (GitHub API access blocked for the session). A third-party paper cites `benchmarks.csv` at commit 90bfb630 (2025-05-22) measured on NUCLEO-L4R5ZI at 24 MHz with -O3, but that is a secondary statement and the master branch could have moved. pqm4 is now deprecated and planned to be archived in or after January 2027 (README).
8. **Hash-based schemes**: Campos et al. is a 2020 snapshot with older libraries; XMSS SIMPLE variants are optimisations, not RFC 8391 behaviour. The LMS signature sizes in the CSV are arithmetic from RFC 8554 field sizes.

## Excluded or partial sources

- **Excluded under protocol (no stated library version or non-MCU)**: wolfSSL STM32 ML-KEM/ML-DSA blog (Cortex-M4 168 MHz; version not stated; board naming inconsistent), wolfBoot KL26 LMS footprint post (Cortex-M0+ 48 MHz, LMS H20 W8: 14.9 KB code, 1.4 KB peak verify stack, 1,776 B signature; no verify time), and the SHBS benchmark arXiv paper (x86 timings). Details in `sources_benchmarks.csv` so they can be reconsidered as corroboration.
- **Abstract-only**: Compact Dilithium on Cortex-M3/M4 (TCHES 2021), SLOTHY M4-to-M7 (ePrint 2025/366, only relative speedups), Stateless hash-based signatures for security keys (ePrint 2025/298). eprint.iacr.org PDFs return HTTP 403 via curl; WebFetch gives abstract pages only.
- **Inaccessible**: ePrint 2022/323 (Dilithium for memory constrained devices): fetch permission went unanswered.

## Gaps for follow-up

- No absolute ML-KEM/ML-DSA numbers on **Cortex-M33 / M7 / M55** or on **MCU RISC-V (RV32)**; mlkem-native lists only Arm 64-bit, x86, RISC-V 64 and POWER backends and its README holds no embedded numbers; mldsa-native has a `MLD_CONFIG_REDUCE_RAM` option and restartable signing example but no published MCU cycles in its README. PQClean is reference code and its README carries no benchmarks.
- No peer-reviewed **SLH-DSA on stock MCU with hardware SHA** numbers retrieved beyond pqm4 portable C.
- No **energy per operation** numbers for ML-DSA/SLH-DSA/LMS on MCUs.
- XMSS sizes from RFC 8391 were fetched but not tabulated; FN-DSA/Falcon sizes were not collected (FIPS 206 not fetched).
- The pqm4 paper (ePrint 2019/844) PDF was not readable; it is a 2019 round-2 snapshot, so not useful for current standards anyway.
