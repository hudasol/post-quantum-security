# S12A: compute cost evidence, extraction notes

Author: Huda Mueen. Retrieval date for every row: 2026-10-20. Staged table: `data/raw/S12A_staged.csv` (443 rows, 23 column schema, all `evidence_type=published`). Search protocol: `data/raw/S12_search_log.csv`. These notes and both CSV files were written by one generator pass; every count below is computed from the staged CSV.

## Method

Rows were taken only from tables read in full text: the author supplied PDFs (text extracted with pdftotext, page by page, and parsed with regular expressions that stop on any unmatched row), or web fetch output where the tool was asked to reproduce table rows verbatim. Where the tool returned cells in its own layout, a second fetch was used to confirm cells, units and page numbers, and the row warning says so. Fetch output that the tool itself called approximate or ambiguous was not extracted (logged in the search log). Unit conversions (kilocycles, 10^3 cycles, 'k' suffixes) are multiplications by 1000 and are stated in each `comparability_warning`; millisecond and MB/s values are not converted to cycles and are kept in `compiler_flags_or_notes`. Before writing, each row was checked against `data/evidence.csv` for the same source and cell and for the same exact cycle count of the same operation in any source; 9 rows were skipped as duplicates (listed under the LMS vs XMSS source).

## Rows per source

| Source | Rows | Ids |
|---|---|---|
| pqm4: Testing and Benchmarking NIST PQC on ARM Cortex-M4 | 90 | S12A-001 to S12A-090 |
| Enabling Microarchitectural Agility: Taking ML-KEM & ML-DSA from Cortex-M4 to M7 with SLOTHY | 105 | S12A-091 to S12A-195 |
| Benchmarking and Analysing the NIST PQC Finalist Lattice-Based Signature Schemes on the ARM Cortex M7 | 50 | S12A-196 to S12A-245 |
| Accelerating SLH-DSA by Two Orders of Magnitude with a Single Hash Unit | 48 | S12A-269 to S12A-316 |
| LMS vs XMSS: Comparison of Stateful Hash-Based Signature Schemes on ARM Cortex-M4 | 45 | S12A-367 to S12A-411 |
| p256-m repository README | 20 | S12A-334 to S12A-353 |
| Fixslicing AES-like Ciphers | 17 | S12A-420 to S12A-436 |
| Yet another Improvement of Plantard Arithmetic for Faster Kyber on Low-end 32-bit IoT Devices | 15 | S12A-254 to S12A-268 |
| Crypto Benchmark on M5531 MCU | 13 | S12A-354 to S12A-366 |
| Efficient Curve25519 Implementation for ARM Microcontrollers | 12 | S12A-317 to S12A-328 |
| Falcon on ARM Cortex-M4: an Update | 8 | S12A-246 to S12A-253 |
| Post-Quantum Signatures on RISC-V with Hardware Acceleration | 8 | S12A-412 to S12A-419 |
| ChaCha20-Poly1305 Authenticated Encryption for High-Speed Embedded IoT Applications | 4 | S12A-437 to S12A-440 |
| Efficient and Side-Channel Resistant Ed25519 on ARM Cortex-M4 | 3 | S12A-329 to S12A-331 |
| Post-Quantum Cryptography on ESP32 | 3 | S12A-441 to S12A-443 |
| X25519-Cortex-M4 repository README | 2 | S12A-332 to S12A-333 |
| Total | 443 | |

## Rows per gap

| Scheme group | Rows |
|---|---|
| Falcon | 66 |
| LMS, HSS or XMSS | 45 |
| ML-DSA or Dilithium | 73 |
| ML-KEM or Kyber | 63 |
| SLH-DSA or SPHINCS+ | 114 |
| classical baseline | 82 |

| Core | Rows |
|---|---|
| CV32E40P RV32IMFC (software only) | 4 |
| CV32E40P RV32IMFC with keccak_f1600 instruction and other accelerators | 4 |
| Cortex-M0 | 10 |
| Cortex-M3 | 6 |
| Cortex-M4 | 133 |
| Cortex-M4F | 54 |
| Cortex-M55 | 13 |
| Cortex-M7 | 148 |
| RISC-V RV32IMAC (SiFive E31) | 20 |
| RISC-V RV32IMC control core plus SLotH hash accelerator (Keccak, SHA2-256, SHA2-512) | 48 |
| not stated in the article | 3 |

## Per source notes

### pqm4: Testing and Benchmarking NIST PQC on ARM Cortex-M4 (Kannwischer, Rijneveld, Schwabe, Stoffelen; ePrint 2019/844)

URL: https://eprint.iacr.org/2019/844.pdf  
Rows: 90 (S12A-001 to S12A-090)

- Read: Author supplied PDF, read in full text. Section 5.1 (speed) and Section 5.2 (stack) signature tables, pages 9, 10, 13 and 14 (page numbers from the PDF reader).
- Extracted: Rows: SPHINCS+ round 2 sha256 and shake256 'simple' parameter sets (clean), and Falcon round 2 falcon1024 m4-ct, falcon512-tree m4-ct, falcon1024 opt-ct, falcon512 opt-ct; cycles and stack as separate rows, as in the existing S10B rows.
- Licence or access: Open access ePrint; licence not checked.
- Ambiguities and checks: Section 5.1 states that SPHINCS+ (and SIKE) were measured in a single execution, not averaged over 100. The existing rows S10B-016 to S10B-018 (sphincs-sha256-128s-simple) say 'average of 100 executions' in their notes and warning; this looks like an error in those rows and is reported for the lead to check (not edited here). The sphincs-haraka-192s-robust row prints the same number for key generation and signing, so it was not used.

### Enabling Microarchitectural Agility: Taking ML-KEM & ML-DSA from Cortex-M4 to M7 with SLOTHY (Abdulrahman, Kannwischer, Lim; ASIA CCS 2025; ePrint 2025/366)

URL: https://eprint.iacr.org/2025/366.pdf  
Rows: 105 (S12A-091 to S12A-195)

- Read: Author supplied PDF, read in full text. Table 1 (Keccak-f[1600], page 10), Tables 2 and 3 (NTT and inverse NTT components, page 11), Table 5 (ML-DSA, page 15) and Table 6 (ML-KEM, page 16).
- Extracted: Rows: Keccak permutation on Cortex-M4 and Cortex-M7 for three implementations; NTT and inverse NTT for ML-DSA and ML-KEM before and after optimisation; all Cortex-M7 full scheme cells not already present (pqm4 and pqm4* for the speed variants, and every m4fstack cell).
- Licence or access: Open access ePrint; licence not checked.
- Ambiguities and checks: Device: the paper names the STM32F767ZI; the existing S7 rows call it Nucleo-F767ZI. Table 1 code size is printed in kilobytes without saying 1000 or 1024, so it was left out of the bytes column. Table 4 repeats the category 3 cells of Tables 5 and 6; the appendix tables are cited. 'M4 pqm4' rows are copied from pqm4 by the authors and were not taken; '[24]' rows were chased to the original paper.

### Benchmarking and Analysing the NIST PQC Finalist Lattice-Based Signature Schemes on the ARM Cortex M7 (Howe, Westerbaan; ePrint 2022/405)

URL: https://eprint.iacr.org/2022/405.pdf  
Rows: 50 (S12A-196 to S12A-245)

- Read: web fetch of the PDF with a request for verbatim rows. Tables 1 and 2 (Dilithium and Falcon cycles in kilocycles) and Tables 3 and 4 (stack).
- Extracted: Rows: average cycles (x1000) and stack for Dilithium-2, 3, 5 and Falcon-512 and 1024 (FPU and emulated builds, dynamic and tree signing).
- Licence or access: Open access ePrint; licence not checked.
- Ambiguities and checks: Citation chase from 2025-366 reference [24]. The Dilithium averages match the [24] rows printed in 2025-366 Table 5, which is an independent check of the fetch. Page numbers were not returned by the tool. Falcon stack values are identical for both degrees in most cells, copied as published. Clock 216 MHz, so not comparable with 24 MHz rows.

### Accelerating SLH-DSA by Two Orders of Magnitude with a Single Hash Unit (Saarinen; NIST Fifth PQC Standardization Conference, 2024)

URL: https://csrc.nist.gov/csrc/media/Events/2024/fifth-pqc-standardization-conference/documents/papers/accelerating-slh-dsa.pdf  
Rows: 48 (S12A-269 to S12A-316)

- Read: web fetch of the PDF, twice. Table 5 (page 12) and Table 6 (page 15).
- Extracted: Rows: end to end cycles of all 12 SLH-DSA parameter sets with the SLotH hash unit (SHAKE and SHA2), and key generation and signing with the masked Keccak unit.
- Licence or access: No licence stated in the fetched text; the source code is said to be freely available.
- Ambiguities and checks: The tool declined a verbatim table copy and returned the cells in its own layout with exact values; a second fetch confirmed two cells. The control core is RV32IMC on an FPGA or ASIC prototype, so these rows show accelerator potential, not a product MCU. The paper predates the final FIPS 205 text, so the scheme is labelled pre standard.

### LMS vs XMSS: Comparison of Stateful Hash-Based Signature Schemes on ARM Cortex-M4 (Campos, Kohlstadt, Reith, Stoettinger; ePrint 2020/470)

URL: https://eprint.iacr.org/2020/470.pdf  
Rows: 45 (S12A-367 to S12A-411)

- Read: Author supplied PDF, read in full text. Appendix A.1 Tables 9, 10 and 11.
- Extracted: Rows: SHA-256 w=256 and SHAKE256 single tree rows for h=5 and h=10, and the two layer XMSS^MT and HSS rows for SHA-256 and SHAKE256 not already present.
- Licence or access: Open access ePrint; licence not checked.
- Ambiguities and checks: Nine SHAKE256 h=5 cells carry exactly the values of the Africacrypt slide rows S2-0296 to S2-0304 and were skipped as duplicates of the same measurement. The paper does not state the clock. This source is Cortex-M4 only; it does not close the gap for LMS or XMSS on other cores.

### p256-m repository README (Manuel Pegourie-Gonnard)

URL: https://github.com/mpg/p256-m  
Rows: 20 (S12A-334 to S12A-353)

- Read: web fetch of the repository page (README). Performance, code size and stack tables.
- Extracted: Rows: P-256 key generation, ECDH, ECDSA sign and verify for p256-m and TinyCrypt on Cortex-M0 (STM32F091, 48 MHz) and Cortex-M4 (STM32F411, 100 MHz), with stack; code size rows per core and library.
- Licence or access: Licence: an apache-2.0.txt and a LICENSE file are listed; the page text does not name the licence, so it is recorded as unconfirmed. Commit not pinned.
- Ambiguities and checks: Only milliseconds are published. Following the convention of data/raw/S2_benchmarks.md section 3, cycles are left empty and the time is kept in compiler_flags_or_notes. The tool gave the tables in its own layout; the printed sums of the four operations match the rows.

### Fixslicing AES-like Ciphers (Adomnicai, Peyrin; TCHES 2021(1))

URL: https://icscm.ub.rub.de/index.php/TCHES/article/download/8739/8339/5469  
Rows: 17 (S12A-420 to S12A-436)

- Read: web fetch of the TCHES PDF, twice. Table 2 (page 414, Cortex-M3 and M4) and Table 3 (page 416, SiFive E31 on HiFive1 Rev B).
- Extracted: Rows: AES-128 encryption cycles per block, code size and stack for semi fixsliced, fully fixsliced and barrel shiftrows variants.
- Licence or access: TCHES open access; licence not checked.
- Ambiguities and checks: The paper marks unrolled and non unrolled variants by font, which the text extraction lost; variants are named by code size instead. Clock and compiler not stated in the fetched text.

### Yet another Improvement of Plantard Arithmetic for Faster Kyber on Low-end 32-bit IoT Devices (Huang et al.; arXiv 2309.00440)

URL: https://arxiv.org/pdf/2309.00440  
Rows: 15 (S12A-254 to S12A-268)

- Read: web fetch of the PDF, twice. Table II.
- Extracted: Rows: SiFive Freedom E310 (RV32IMAC) Kyber512, 768, 1024 cycles and stack for the stack and speed variants.
- Licence or access: arXiv preprint; licence line not present in the fetched text.
- Ambiguities and checks: The 'k' suffix is not defined in the caption and is read as thousands. The E310 clock is not stated. Cortex-M3 and simulator rows not taken.

### Crypto Benchmark on M5531 MCU (Oryx Embedded, CycloneCRYPTO 2.6.4)

URL: https://front.oryx-embedded.com/benchmark/nuvoton/crypto-m5531.html  
Rows: 13 (S12A-354 to S12A-366)

- Read: web fetch of the vendor page, twice (the tool declined a full copy and gave the requested cells).
- Extracted: Rows: Cortex-M55 (220 MHz) software AES-128 CTR, ChaCha20-Poly1305, SHA-256, SHA3-256, X25519, Ed25519, ECDSA P-256, and three hardware accelerated rows.
- Licence or access: Vendor page; terms not checked.
- Ambiguities and checks: Units are MB/s or ms, so cycles are empty and the value is in compiler_flags_or_notes. Ed25519 signing is printed slower than verification, which is unusual; copied as published. No ML-KEM or ML-DSA rows.

### Efficient Curve25519 Implementation for ARM Microcontrollers (Fujii, Aranha; SBSeg extended proceedings)

URL: https://sol.sbc.org.br/index.php/sbseg_estendido/article/download/4142/4071  
Rows: 12 (S12A-317 to S12A-328)

- Read: web fetch of the PDF, twice. Table 3.
- Extracted: Rows: X25519 and Ed25519 key generation, sign and verify in 10^3 cycles on Teensy 3.1 (48 and 72 MHz) and STM32F401C (84 MHz).
- Licence or access: Licence not stated in the fetched text.
- Ambiguities and checks: The caption unit '103 cycles' is the extraction of 10^3 cycles. Cited rows not taken.

### Falcon on ARM Cortex-M4: an Update (Pornin; ePrint 2025/123)

URL: https://eprint.iacr.org/2025/123.pdf  
Rows: 8 (S12A-246 to S12A-253)

- Read: web fetch of the PDF, twice. Table 1 on the first page.
- Extracted: Rows: Falcon-512 and 1024 key generation, signing, original and BUFF verification, with RAM split into work area and stack.
- Licence or access: Open access ePrint; licence not checked.
- Ambiguities and checks: Not FIPS 206 FN-DSA; the BUFF variant is described as a possible element of the coming standard.

### Post-Quantum Signatures on RISC-V with Hardware Acceleration (Karl, Schupp, Fritzmann, Sigl; slides, DOI 10.1145/3579092)

URL: https://www.ce.cit.tum.de/fileadmin/w00cgn/eisec/pdf/pq_signatures_riscv.pdf  
Rows: 8 (S12A-412 to S12A-419)

- Read: web fetch of the slides. Slide 10 cycle count table.
- Extracted: Rows: Dilithium2 key generation, signing and verification and Falcon-512 verification, base software and accelerated, on a CV32E40P PULPino SoC.
- Licence or access: Slides; licence not stated.
- Ambiguities and checks: Slides rather than the paper; the paper itself was not read. How cycles were obtained is not stated.

### ChaCha20-Poly1305 Authenticated Encryption for High-Speed Embedded IoT Applications (De Santis, Schauer, Sigl; DATE 2017)

URL: https://past.date-conference.com/proceedings-archive/2017/pdf/0591.pdf  
Rows: 4 (S12A-437 to S12A-440)

- Read: web fetch of the PDF. Table I.
- Extracted: Rows: this work rows for ChaCha20, Poly1305, Poly1305 with ChaCha20 and the AEAD on Cortex-M4.
- Licence or access: Conference proceedings archive; licence not checked.
- Ambiguities and checks: Two rows have merged speed and size cells in the extracted text; size left empty there. Clock not stated.

### Efficient and Side-Channel Resistant Ed25519 on ARM Cortex-M4 (Owens et al.; NSF PAR manuscript)

URL: https://par.nsf.gov/servlets/purl/10507285  
Rows: 3 (S12A-329 to S12A-331)

- Read: web fetch of the manuscript. Table II.
- Extracted: Rows: the 24 MHz row only (key generation, sign, verify in kilo cycles).
- Licence or access: NSF public access repository; licence not checked.
- Ambiguities and checks: The tool reported the row labels of the 168 MHz and scalar blinding rows as inferred, so those rows were not taken. Venue not stated.

### Post-Quantum Cryptography on ESP32 (Espressif developer blog, 14 October 2026)

URL: https://developer.espressif.com/blog/2026/10/esp32-post-quantum-cryptography/  
Rows: 3 (S12A-441 to S12A-443)

- Read: web fetch of the blog page. The single secure boot verification table.
- Extracted: Rows: ML-DSA-65 software verification, hardware SHA-256 and hardware RSA-PSS-3072 verification cycles on an ESP32-C5 at 80 MHz.
- Licence or access: Vendor blog; terms not checked.
- Ambiguities and checks: The core of the ESP32-C5 is not stated in the article and was left as not stated. Bootloader measurement, not a library best case.

### X25519-Cortex-M4 repository README (Emil Lenngren)

URL: https://github.com/Emill/X25519-Cortex-M4  
Rows: 2 (S12A-332 to S12A-333)

- Read: web fetch of the repository page; README sentences quoted by the tool.
- Extracted: Rows: X25519 scalar multiplication on Cortex-M4 (integer) and Cortex-M4F (FPU version).
- Licence or access: 2 clause BSD with an exception for Nordic Semiconductor and Dialog Semiconductor devices (as quoted). Commit not pinned.
- Ambiguities and checks: Board, clock and compiler not stated.

## Gaps that remain

- No ML-KEM or ML-DSA full scheme cycles on Cortex-M55, Cortex-M85 or a further Cortex-M0+ device were found; the Cortex-M55 rows are classical baselines from a vendor page (times only).
- ML-KEM on a silicon RISC-V MCU is covered only by pre standard Kyber on the SiFive E310; ML-DSA on RISC-V is covered by the ESP32-C5 vendor figure and by Dilithium round 3 on a PULPino SoC.
- LMS and XMSS verification on cores other than the Cortex-M4: the OpenTitan secure boot paper (ePrint 2022/1198) has such numbers, but the fetched table was ambiguous and was not extracted; it should be read from the PDF directly.
- Final FIPS 205 SLH-DSA on a Cortex-M core: still none; the new rows are round 2 SPHINCS+ on Cortex-M4 and draft era SLH-DSA on an accelerator prototype.
- Final FN-DSA: not standardised at retrieval; all Falcon rows are pre standard.
- SHA-256 and ChaCha20 cycle counts on Cortex-M are thin: ChaCha20 from DATE 2017 (Cortex-M4); SHA-256 only as throughput (Cortex-M55) or as a hardware accelerated boot step (ESP32-C5).

## Refused or blocked retrievals

- https://eprint.iacr.org/2016/714.pdf (AES on Cortex-M3 and M4): access to the site not granted in time; not retried.
- https://eprint.iacr.org/2023/773.pdf (Keccak on ARMv7-M, reference [4] of 2025-366): access to the site not granted in time; not retried.

## Observation for the existing dataset

- S10B-016 to S10B-018: the pqm4 paper (Section 5.1) measured SPHINCS+ in a single execution; those rows state an average of 100 executions.
- 2025-366 Table 1 Keccak rows give the permutation alone; do not compare with full hash throughput rows.

