# S2: Published embedded PQC benchmarks (raw notes)

Stream S2, protocol `docs/PROTOCOL.md` sections 4-6. Retrieval date for everything below: 2026-10-11.
Evidence table: `data/raw/S2_evidence.csv` (431 rows, 23 columns in the section 5 order, all `evidence_type=published`).
Every numeric cell was copied from a page, PDF or repository file retrieved in this session. An automated check confirmed that every cycles / stack / code-size / energy / size value in the CSV appears in the retrieved source text (486 values, 0 missing). This is only an occurrence check; the independent verification step of section 9 is still required.

## 1. Sources retrieved and used

| # | Source | Authors / owner | Venue / date | URL | Rows |
|---|---|---|---|---|---|
| 1 | pqm4 `benchmarks.csv` and `README.md` | mupq / pqm4 project (Kannwischer et al.) | GitHub, master HEAD `5e5cc76d0b07` (2026-09-04); `benchmarks.csv` last changed in `90bfb630e536` (2025-05-22) | https://raw.githubusercontent.com/mupq/pqm4/master/benchmarks.csv , .../README.md | 90 |
| 2 | Compact Dilithium Implementations on Cortex-M3 and Cortex-M4 | Greconici, Kannwischer, Sprenkels | IACR TCHES 2021(1):1-24 | https://tches.iacr.org/index.php/TCHES/article/download/8725/8325 | 36 |
| 3 | Revisiting Keccak and Dilithium Implementations on ARMv7-M | Huang, Adomnicai, Zhang, Dai, Liu, Cheung, Koc, Chen | IACR TCHES 2024(2):1-24 | https://bmt.ub.rub.de/index.php/TCHES/article/download/11419/10922/11688 | 45 |
| 4 | Low-Stack HAETAE for Memory-Constrained Microcontrollers (used only for its pqm4 ML-DSA reference columns) | Banegas, Kim, Seo, van Vredendaal | arXiv:2604.15868v1, 17 Apr 2026 (preprint) | https://arxiv.org/pdf/2604.15868 | 18 |
| 5 | Mobile Energy Requirements of the Upcoming NIST PQC Standards | Saarinen (PQShield) | arXiv:1912.00916v4, Apr 2020 | https://arxiv.org/pdf/1912.00916 | 24 |
| 6 | Simultaneous Integration of Kyber and Dilithium on Embedded Microcontrollers (ESP32) | Do, Dinh | ETASR 16(2), 2026, pp.33589-33595 | https://mail.etasr.com/index.php/ETASR/article/download/17148/6422/84641 | 6 |
| 7 | Benchmarking NIST-Standardised ML-KEM and ML-DSA on ARM Cortex-M0+ (RP2040) | Chhetri, Dhakal, Gautam | arXiv:2603.19340v6, 11 Aug 2026 (preprint) | https://arxiv.org/pdf/2603.19340 | 34 |
| 8 | Rapidly Verifiable XMSS Signatures | Bos, Huelsing, Renes, van Vredendaal | IACR TCHES 2021(1):137-168 | https://bmt.ub.rub.de/index.php/TCHES/article/download/8730/8330/5451 | 6 |
| 9 | LMS vs XMSS: Comparison of Stateful Hash-Based Signature Schemes on ARM Cortex-M4 (conference SLIDES, Africacrypt 2020) | Campos, Kohlstadt, Reith, Stoettinger | slides dated 19 Jul 2020 | https://www.sopmac.de/wp-content/uploads/2021/01/LMS_vs_XMSS.pdf | 63 |
| 10 | Updated Post-Quantum Benchmarks for ML-KEM and ML-DSA on STM32 | wolfSSL (vendor blog) | page dated 25 Jul / 8 Aug 2025 | https://www.wolfssl.com/updated-post-quantum-benchmarks-for-ml-kem-and-ml-dsa-on-stm32/ | 24 |
| 11 | wolfBoot Cipher and Hash Algorithm Benchmarks on STM32H5 | wolfSSL (vendor blog) | page dated 19 Mar / 7 Apr 2026 | https://www.wolfssl.com/wolfboot-cipher-and-hash-algorithm-benchmarks-on-stm32h5/ | 11 |
| 12 | Post-Quantum Cryptography on CHERIoT | D. Chisnall (CHERIoT Platform blog) | 12 Dec 2025 | https://cheriot.org/pqc/2025/12/12/pqc-on-cheriot.html | 6 |
| 13 | Post-Quantum Secure Boot | Kumar, Gupta, Chattopadhyay, Kasper, Krauss, Niederhagen | DATE 2020, pp.1583-1585 | https://www.date-conference.com/proceedings-archive/2020/pdf/0438.pdf | 4 |
| 14 | XMSS and Embedded Systems: XMSS Hardware Accelerators for RISC-V | Wang, Jungk, Waelde, Deng, Gupta, Szefer, Niederhagen | SAC 2019 (NSF PAR manuscript; ePrint 2018/1225) | https://par.nsf.gov//servlets/purl/10112210 | 9 |
| 15 | Stateful Hash-Based Signature (SHBS) Benchmark Data for XMSS and LMS | Romansky, Mazzuchi, Sarkani | arXiv:2502.06033v1, Feb 2025 | https://arxiv.org/pdf/2502.06033 | 19 (x86 host, flagged) |
| 16 | FIPS 203 / FIPS 204 / FIPS 205 (final, published 13 Aug 2024) | NIST | standards | https://nvlpubs.nist.gov/nistpubs/FIPS/NIST.FIPS.203.pdf (.204, .205) | 9 + 9 + 12 (`size_kind=standard`) |
| 17 | RFC 8391 (XMSS), Table 3 | IETF | May 2018 | https://www.rfc-editor.org/rfc/rfc8391.txt | 6 (`size_kind=standard`) |

## 2. Queries run (WebSearch, standard mode)

1. `ML-DSA Cortex-M4 cycles stack-optimised implementation eprint`
2. `post-quantum Cortex-M33 Dilithium Kyber benchmark`
3. `LMS XMSS Cortex-M benchmark verification time firmware signing`
4. `ML-KEM ML-DSA Cortex-M33 benchmark cycles STM32U5 OR nRF5340 OR RP2350 post-quantum`
5. `post-quantum secure boot Cortex-M LMS XMSS ML-DSA verification time measured microcontroller`
6. `post-quantum energy consumption microcontroller ML-KEM ML-DSA measured mJ nRF52840 OR ESP32 OR STM32`
7. `SLH-DSA SPHINCS+ Cortex-M4 optimized implementation cycles embedded 2025`
8. `LMS vs XMSS comparison of stateful hash-based signature schemes on ARM Cortex-M4 Campos Kohlstadt Reith Stöttinger`
9. `mlkem-native mldsa-native benchmarks Cortex-M cycles README`
10. `Dilithium Kyber ESP32 benchmark post-quantum microcontroller measured milliseconds`
11. `Helium MVE Cortex-M55 OR Cortex-M85 ML-KEM ML-DSA NTT implementation cycles`
12. `tches.iacr.org 2025 ML-DSA Cortex-M4 Cortex-M33 optimized implementation cycles Dilithium`
13. `Apples, Oranges, and Signatures: Pitfalls and Methodology in ML-DSA Benchmarking Riou`
14. `Kyber OR ML-KEM nRF5340 OR "Cortex-M33" benchmark cycles microcontroller TrustZone post-quantum`
15. `wolfBoot ML-DSA LMS XMSS STM32H5 OR STM32U5 OR nRF5340 boot time benchmark post-quantum secure boot`
16. `MCUboot LMS OR XMSS OR ML-DSA post-quantum signature verification embedded benchmark Zephyr`

The literal query `pqm4` was not run as a web search; pqm4 was retrieved directly from its repository (raw.githubusercontent.com worked; `api.github.com` returned 403 from the proxy, but the attached GitHub connector could read commit metadata, which is where the commit ids above come from).

## 3. How the setups differ (read before plotting)

| Group | Core / clock | Library | Notes |
|---|---|---|---|
| pqm4 benchmarks.csv | Cortex-M4F, 24 MHz (0 wait states) | `clean` = PQClean reference C; `m4fspeed`/`m4fstack`/`m4f` = M4F-specific code | Final ML-KEM/ML-DSA names. SPHINCS+ rows are round-3 "simple" parameter sets, NOT final SLH-DSA, and exist only as `clean`. gcc 11.3.1 per README. Means of 10 executions (KEM, SPHINCS+) or 1000 (ML-DSA). Stack excludes caller buffers. Code size excludes hashing/libc. |
| Greconici et al. | M4 at 24 MHz (STM32F407-DISCOVERY), M3 at 16 MHz (Arduino Due) | own asm | Pre-standard Dilithium2/3/4. Four stack strategies; mean of 10000. |
| Huang et al. | M4 24 MHz, M3 16 MHz | pqm4/pqm3 + new Keccak | Pre-standard Kyber/Dilithium; mean of 1000; gcc 10.2.1 -O3. |
| HAETAE paper (ML-DSA columns) | M4F (L4R5ZI) cycles at 20 MHz | pqm4 `m4f` / `m4fstack` | MEDIAN of 100, not mean, so not equal to the pqm4 CSV means. |
| Saarinen | M4 (F411RE) at 96 MHz | PQM4 code under Mbed OS | MEASURED energy; round-2 Kyber/Dilithium. |
| ETASR ESP32 | Xtensa LX6, 240 MHz | CRYSTALS reference C | Wall-clock ms and measured energy (shunt + scope); RAM is heap. |
| RP2040 paper | Cortex-M0+, 125 MHz | PQClean reference C | Cycles derived as t x 125. Energy is a datasheet-model ESTIMATE. Final parameter sets. Preprint. |
| wolfSSL STM32 blog | Cortex-M4 (NUCLEO-F439ZI), 168 MHz | wolfCrypt (ML-KEM asm, ML-DSA plain C) | Averages in ms only (stored in notes). Vendor post. |
| wolfBoot STM32H5 blog | STM32H563 at 320 MHz | wolfBoot + wolfCrypt | TOTAL BOOT TIME, not verify-only. Core not named on page. |
| LMS/XMSS Cortex-M4 | FRDM-K64F 120 MHz (Bos et al.); STM32F4DISCOVERY, clock not stated (Campos slides) | xmss-reference / hash-sigs | Different hashes and parameter variants; only compare like with like. |
| RISC-V rows | CHERIoT Ibex (Verilator sim), VexRiscv "Murax" and a hardware verifier on FPGA | various | Soft cores or simulation, not silicon MCUs. |

Fields not reported by a source are empty. In particular the schema has no wall-clock-time column. Where a source reports only milliseconds (wolfSSL, wolfBoot, ESP32) the time is written in `compiler_flags_or_notes` and `cycles` is left empty rather than converted. Suggest logging a schema deviation in PROTOCOL section 10 (e.g. add `time_ms`) before merging.

## 4. Data-quality flags and oddities noticed

- pqm4 board: the benchmark CSV itself does not name the board. The README lists `nucleo-l4r5zi` (STM32L4R5ZI) as default platform and `stm32f4discovery` as an alternative; it says all cycle counts were obtained at 24 MHz. Two papers retrieved (RP2040 paper Table X caption, HAETAE paper Sec. 5.2) state the pqm4 reference numbers come from a NUCLEO-L4R5ZI, but the pqm4 file does not say so. The brief's "STM32F4 Discovery" is therefore not confirmed for these tables; rows say "board not named".
- pqm4 HEAD commit `5e5cc76d0b07` (2026-09-04, author "vincentvbh-claude-public", message "new admin test") only inserts a "Maintenance Notice" heading into README.md; `benchmarks.csv` is unchanged since 2025-05-22. The README also carries a deprecation notice (pqm4 to be archived read-only in or after Jan 2027). Worth knowing before citing it as a living benchmark.
- Campos slides: slide 21 gives XMSS SIMPLE+PRE (Gimli-Hash, h=5) key generation as 35,652,023 cycles, about ten times lower than its neighbours; copied as published and flagged. Slide 18 and slide 19 disagree for XMSS SIMPLE h=10 verify (3.67 vs 3.57 M cycles), so only LMS and XMSS ROBUST h=10 (consistent on both) were included. The slide table of signature sizes is labelled "bits" but its values look like bytes, so it was not used for sizes.
- ETASR ESP32: Dilithium2 signing peak RAM of 20.2 KB (heap) is far below the stack figures other sources report for Dilithium2/ML-DSA-44 reference code (e.g. pqm4 `clean` 51,976 B). Treat the memory columns with caution.
- CHERIoT: ML-KEM key generation (5.14 M cycles) is slower than encapsulation (1.77 M), unexplained; ML-KEM parameter set not stated in the text read.
- RP2040 paper: its "mean" for ML-DSA signing at n=100 understates the tail; the paper's own n=10,000 -Os campaign gives a heavier tail (included as a separate row, not comparable to the -O3 rows).
- HAETAE paper vs pqm4 CSV: ML-DSA values differ (median vs mean, different pqm4 version, 20 vs 24 MHz). Both kept; do not mix them in one series.
- wolfBoot boot times: the SHA2-only baseline (55.662 ms) is a large share of every row. Do not read a row as pure verification time.
- RISC-V/FPGA hardware rows (DATE 2020, Murax HW accelerators) show hardware-offload potential only.

## 5. Gaps (nothing found / nothing retrievable)

- No ML-KEM / ML-DSA / SLH-DSA cycle counts on a named Cortex-M33 core. The only M33-class device is the STM32H563 in the wolfBoot post, and that page does not state the core (verifier should confirm from ST). No nRF5340 / nRF9160 / STM32U5 / RP2350 results found. The RP2040 paper lists RP2350 (Cortex-M33) as future work.
- No Helium/MVE (Cortex-M55/M85) or ARMv8-M-specific results retrieved. The TCHES Helium paper URL tried returned 404.
- No published energy numbers found for final ML-KEM/ML-DSA/SLH-DSA from a real measurement on Cortex-M4/M33. Measured energy exists only for pre-standard Kyber/Dilithium (Saarinen, M4) and for Kyber512/Dilithium2 on ESP32 (ETASR). RP2040 energy is a model estimate.
- No final SLH-DSA (FIPS 205) cycle counts on an MCU. Only pqm4 round-3 SPHINCS+ "simple" rows (reference C, Cortex-M4F) and x86 host verification cycles.
- No LMS/HSS numbers on an MCU with the final RFC 8554 parameters. LMS data on Cortex-M4 are from slides (Campos, hash-sigs, h=5 and h=10) and a vendor boot-time figure (wolfBoot LMS 1-10-8 on STM32H563: 207.703 ms total boot). The wolfSSL LMS-vs-XMSS-vs-SLH-DSA verification post (https://www.wolfssl.com/lms-versus-xmss-versus-slh-dsa-performance-data/, 21 May 2026) was retrieved but is EXCLUDED because it names no device or clock (inclusion criterion 3).
- LMS key/signature sizes from RFC 8554 / SP 800-208 are not in the CSV: the documents give formulas (e.g. LM-OTS signature 4 + n*(p+1) bytes, LMS public key 24 + n bytes in RFC 8554), not size tables, and deriving them was out of scope. Library-reported sizes are in the notes of the SHBS (x86) rows. XMSS sizes are from the RFC 8391 table.
- SLH-DSA secret-key sizes are not tabulated in FIPS 205 Table 2 and are left out.
- Classical baselines on the same device exist in: Saarinen (ECDH/ECDSA secp256r1 on M4), RP2040 paper (ECDSA, ECDH, RSA-2048 via mbedTLS), wolfSSL STM32 (ECC P-256, RSA-2048), wolfBoot (RSA-2048, ECDSA P-256, Ed25519 boot time). No X25519 or Ed25519 raw operation times found. pqm4 has no classical baselines.
- No ESP32 / nRF52 / RISC-V-MCU (PicoRV32, Ibex silicon) results for final standards. The HAETAE paper has nRF52840 and ESP32-C6 numbers, but for HAETAE, not ML-DSA, so they were not used.

## 6. Retrieved but not used

- arXiv 2609.23902 (PQC in lightweight virtualization, Puch et al., Sep 2026): Raspberry Pi 4 (Cortex-A72), not an MCU. Contains energy per operation; may matter for S3 companion computers.
- arXiv 2505.16614 (Patterson et al.): Raspberry Pi key-generation energy via OpenSSL, not an MCU.
- arXiv 2503.12952 (Demir et al.): desktop-class (AVX2) benchmarks.
- arXiv 2609.04058: FPGA accelerator case study; no MCU software numbers.
- TCHES 2026(2) artifact README for MSP430 Kyber/Dilithium (https://artifacts.iacr.org/tches/2026/a20/readme.html): only percentage speed-ups, no absolute cycle counts in the README; the paper text was not retrieved.
- mlkem-native and mldsa-native READMEs, PQC-OpenTitan README: no embedded cycle tables (mlkem-native/mldsa-native point to CI benchmark pages for 64-bit targets).
- krypteia-quantica docs (docs.rs) and other secondary summaries: appeared in search results, not opened (secondary).
- arXiv 2401.17538 (Liu et al. survey) was downloaded but only 4 pages were returned and it was not used.

## 7. Sources I could not retrieve (please fetch manually)

Cloudflare challenge ("Just a moment", HTTP 403) blocks **eprint.iacr.org** from this environment, including the web.archive.org route (connection reset). Affected, in priority order:
1. pqm4 paper, Kannwischer, Rijneveld, Schwabe, Stoffelen, ePrint 2019/844 (original round-2 M4 tables, board and clock).
2. Bos, Renes, Sprenkels, Dilithium for memory constrained devices, ePrint 2022/323 (the `m4fstack` strategy; also AFRICACRYPT 2022).
3. Abdulrahman, Kannwischer, Lim, SLOTHY: Cortex-M4 to M7 migration of ML-KEM/ML-DSA, ePrint 2025/366 (WebFetch of the abstract page gave only speed-up percentages: NTT 1.97x/1.69x, full schemes 11-33%; no cycle tables; full PDF not read).
4. Campos, Kohlstadt, Reith, Stoettinger, LMS vs XMSS full paper, ePrint 2020/470 (only the slides were obtained).
5. Banegas et al., Quantum-resistant security for software updates on low-power networked embedded devices, ePrint 2021/781 (RIOT/SUIT, hash-based signatures on Cortex-M).
6. Riou et al., Apples, Oranges, and Signatures: pitfalls in ML-DSA benchmarking, ePrint 2026/1333 (methodology; MAgiCS 2026).
7. Wang et al., XMSS and Embedded Systems, ePrint 2018/1225 (read via the NSF PAR manuscript instead).
8. Other IACR hits not opened: ePrint 2026/1576, 2025/2337, 2026/235, 2025/909, 2026/2352; TCHES article 9305 (Polynomial multiplication on embedded vector architectures, Helium; download URL tried returned 404).
Other failures:
- `api.github.com` (403 "GitHub access not enabled for this session"); worked around with the GitHub connector for commit metadata. `github.com` HTML pages were not needed.
- Nordic nRF Connect SDK ML-DSA sample page (nrfconnectdocs.nordicsemi.com, HTTP 403): may hold nRF54/nRF53 timing; fetch manually.
- ST product page for STM32H563 (WebFetch permission not granted): needed to confirm its core for the wolfBoot rows.
- Not attempted: Cortex-M33 vendor application notes (ST, NXP, Nordic, Renesas) for hardware PQC accelerators, and Zephyr/MCUboot PQ signature pull requests.
