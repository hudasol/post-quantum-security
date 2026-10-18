# S7: retry of sources blocked in the earlier review

Method: web fetch and web search only, by design. No curl, wget, mirrors, caches or archives. Each item tried once or twice, including the abstract-page form where one exists. Retrieval date recorded as 2026-10-11 as instructed (the system clock reported 2026-10-12 partway through the session).

Important: most failures were NOT site blocks. web fetch returned a provenance error ("permission request for this URL was not answered in time"), meaning no one approved the fetch prompt. Those items are recorded as BLOCKED because nothing was retrieved, but they may succeed if the user approves the prompts or includes the URL in a message. The only site-side refusal seen was `ROBOTS_DISALLOWED` for the 2026/312 PDF.

All content below comes from the web fetch tool's summary of the page, not a verbatim read. Numbers should be re-checked against the PDF before they go into the report.

## Items

### 1. ePrint 2025/366, "Enabling Microarchitectural Agility: Taking ML-KEM & ML-DSA from Cortex-M4 to M7 with SLOTHY"
- URL: https://eprint.iacr.org/2025/366.pdf. Authors: Abdulrahman, Kannwischer, Lim. Venue: ACM ASIA CCS 2025.
- Status: RETRIEVED (full PDF). Date: 2026-10-11.
- Setup (Section 5): M7 = Nucleo-F767ZI (STM32F767ZI) at 24 MHz, chosen to avoid flash wait states (board supports up to 216 MHz). M4 = STM32F407-DISCOVERY for component counts, clock not stated; full-scheme M4 numbers taken from pqm4 tables.
- Component cycles on M7 (Tables 2, 3): ML-DSA NTT 8139 to 4141; iNTT 8207 to 4547; ML-KEM NTT 4011 to 2380; iNTT 4247 to 2586. Keccak-f1600 6691 to 5149 (Table 1).
- Full schemes on M7, ours versus pqm4 (cycles): ML-DSA-65 keygen/sign/verify 1,446,421 / 3,412,174 / 1,380,098 versus 1,808,627 / 4,489,455 / 1,753,730 (Table 4). ML-KEM-768 keygen/encaps/decaps 372,064 / 385,371 / 417,224 versus 462,147 / 469,808 / 511,840 (Table 4). ML-DSA-44 and ML-DSA-87 in Table 5; ML-KEM-512 and ML-KEM-1024 in Table 6 (all in the CSV).
- Stated speedups over pqm4 on M7: 11 to 33 percent (ML-DSA), 22 to 27 percent (ML-KEM). M7 versus M4 pqm4: 1.58 to 1.82 times fewer cycles (ML-DSA), 1.66 to 1.74 times (ML-KEM).
- Not extracted: stack, RAM, code size, compiler flags, library commit. These are the gaps for the PQC-on-MCU question and need a direct read of the PDF.
- Rows: S7-001 to S7-024.

### 2. ePrint 2020/470, "LMS vs XMSS: Comparison of Stateful Hash-Based Signature Schemes on ARM Cortex-M4"
- URL: https://eprint.iacr.org/2020/470.pdf. Authors: Campos, Kohlstadt, Reith, Stoettinger.
- Status: RETRIEVED (full PDF). Date: 2026-10-11.
- Device: STM32F4DISCOVERY (Cortex-M4F, 1 MB flash, 192 KB RAM). Compiler GNU Arm Embedded 9-2019-q4-major, `-O3 -mthumb -mcpu=cortex-m4 -mfloat-abi=hard -mfpu=fpv4-sp-d16`. Clock not stated; cycles only.
- SHA-256, n=256, w=16, h=10, in 10^6 cycles keygen / sign / verify (Table 6): LMS 3774.88 / 3791.15 / 2.65; XMSS ROBUST 23631.70 / 23642.03 / 13.07; XMSS SIMPLE 7792.23 / 7796.39 / 3.57; XMSS SIMPLE+PRE 7586.15 / 7596.24 / 4.20.
- LMS SHA-256 w=16 h=5 (Table 9): 117,988,963 / 126,516,806 / 2,576,515 cycles. HSS h=10, 2 layers (Table 11): 117,989,078 / 268,526,114 / 3,082,339.
- Hash share of time (Table 7): HSS 92 to 94 percent, XMSS^MT SIMPLE 85 percent.
- Signature sizes (Table 3, bits): LMS w=16 h=10 2512; w=256 h=10 1456; w=16 h=5 2352; w=256 h=5 1296. Several XMSS/HSS entries are not whole bytes and were not converted. No key sizes reported.
- Overlap warning: existing rows S2-0260 onward already cover this work from the Africacrypt slides (h=5, Gimli and Keccak hashes). The grep suggests some SHA-256 values may already be present (3 hits on the h=10 figures, 2 on the h=5/HSS figures), so deduplicate before merging.
- Rows: S7-025 to S7-046.

### 3. ePrint 2026/1333, "Apples, Oranges, and Signatures: Pitfalls and Methodology in ML-DSA Benchmarking"
- URL: https://eprint.iacr.org/2026/1333 (abstract page; the PDF form was refused for lack of approval).
- Status: RETRIEVED (abstract page only). Date: 2026-10-11.
- Authors: Riou, Park, Anwar, Poschmann, Hutter (PQShield; University of the Bundeswehr Munich).
- Facts: signing time varies because of rejection sampling and other data-dependent steps, so min/average/max is unsuitable for migration planning. Proposes a methodology with standardised input data sets and defined reporting metrics, aimed at worst-case execution time for real-time systems. No numbers on the page.
- Rows: none. The exact reporting recommendations still need the PDF.

### 4. ePrint 2021/781, "Quantum-Resistant Security for Software Updates on Low-power Networked Embedded Devices"
- URL: https://eprint.iacr.org/2021/781 (abstract page). Authors: Banegas, Zandberg, Herrmann, Baccelli, Smith.
- Status: RETRIEVED (abstract page only); PDF BLOCKED (permission unanswered). Date: 2026-10-11.
- Facts: uses RIOT's SUIT implementation; benchmarks LMS, Falcon and Dilithium against Ed25519 and ECDSA on Cortex-M, RISC-V and ESP32 hardware; estimates impact on update categories. First submitted 2021-06-10, last revised 2022-07-06. No numbers on the page.
- Rows: none.

### 5. ePrint 2026/312, "RISQrypt: Fast, Secure and Agile Hardware-Software Co-Design for Post-Quantum Cryptography"
- URL: https://eprint.iacr.org/2026/312 (abstract page). Authors: Tosun, Ay, Norga, Kundu, Yazici, Savas, Verbauwhede (Sabanci University; COSIC KU Leuven).
- Status: RETRIEVED (abstract page only); PDF refused with `ROBOTS_DISALLOWED`. Date: 2026-10-11.
- Facts: masked Kyber768 decapsulation about 109K cycles and masked Dilithium3 signing about 1230K cycles on average, stated as 11.3 times speedup over existing masked designs. Unprotected speedups: Kyber encaps 10.64 times, decaps 8.94 times; Dilithium sign 1.14 times, verify 2.23 times. Platform, clock and baseline not on the abstract.
- Rows: S7-047, S7-048 (device fields empty; hardware accelerator design, not a plain MCU result).

### 6. ePrint 2026/2343, "Post-Quantum Command Authentication for Unmanned Systems: A KpqC Feasibility Study under Real-Time and Bandwidth Constraints"
- URL: https://eprint.iacr.org/2026/2343 (abstract page). Authors: Hyoung, Lim, Bang, Park, Kim, Seo (Hansung University).
- Status: RETRIEVED (abstract page only); PDF BLOCKED (permission unanswered). Date: 2026-10-11.
- Facts: ROS2/DDS-Security setting; HAETAE, AIMer, SMAUG-T and NTRU+ compared with ML-KEM, ML-DSA, SLH-DSA and an ECDSA/ECDH baseline on a two-node testbed with emulated constrained links; outputs a feasibility envelope mapping algorithm to channel conditions. No latency or size numbers on the page. Page shows received 2026-10-05, approved 2026-10-07.
- Rows: none.

### 7. ePrint 2019/844, pqm4 paper (board and clock)
- URL: https://eprint.iacr.org/2019/844.pdf and https://eprint.iacr.org/2019/844.
- Status: BLOCKED (web fetch provenance error, tried PDF twice and abstract page once). Nothing retrieved.

### 8. ePrint 2022/323, Dilithium for memory-constrained devices (`m4fstack`)
- URL: https://eprint.iacr.org/2022/323.pdf and https://eprint.iacr.org/2022/323. A Springer URL guess (https://link.springer.com/chapter/10.1007/978-3-031-17433-9_1) was also tried and was not answered; the DOI there is an unverified guess.
- Status: BLOCKED (a provenance error). Nothing retrieved.

### 9. NSA CNSA 2.0 algorithms advisory and FAQ
- URLs tried: https://media.defense.gov/2022/Sep/07/2003071834/-1/-1/0/CSA_CNSA_2.0_ALGORITHMS_.PDF (twice), https://media.defense.gov/2022/Sep/07/2003071836/-1/-1/0/CSI_CNSA_2.0_FAQ_.PDF (once), and an nsa.gov news article URL (once). The two media.defense.gov paths and the nsa.gov article path are from memory, not verified.
- Status: BLOCKED (a provenance error). Nothing retrieved. A web search returned only secondary pages (encryptionconsulting.com, entrust.com, atsec.de, thalestct.com), which I did not treat as a substitute and did not fetch. No CNSA 2.0 claim should be made from this pass.

### 10. CISA quantum pages
- URLs tried: https://www.cisa.gov/quantum (twice), https://www.cisa.gov/resources-tools/resources/quantum-readiness-migration-post-quantum-cryptography (once; path from memory, unverified).
- Status: BLOCKED (a provenance error). Nothing retrieved.

### 11. UAE National Encryption Policy and executive regulation text
- URL tried: https://www.wam.ae/en/article/15w563h-uae-announces-approval-national-encryption-policy.
- Status: BLOCKED for the policy text. The fetch returned only the WAM homepage metadata, no article or policy text. A web search gave press and commentary links (WAM, Tribune India, Khaleej Times, MIT Sloan ME, postquantum.com, PQShield, Aletihad); none is the primary policy text and none was fetched, so no UAE requirement is recorded. Arabic-language and Cybersecurity Council / National Cryptography Center sources were not tried.

### Not retried in this pass
NIST CAVP/CMVP validation search, vendor pages (ST X-CUBE-PQC, Microchip, Infineon, NXP, Nordic, Arm), Bluetooth/LoRa/802.15.4 specs, micro-ROS docs, GitHub issues for MCUboot/PX4/ArduPilot, other jurisdictions (China, SAMA, NCA, TNO, ASD), Uptane, ISO/SAE 21434, Noise PQ, ePrint 2026/256. Reason: the fetch permission prompts were going unanswered, so further attempts would have repeated the same failure.

## Still inaccessible, for upload

| Title | DOI or URL |
|---|---|
| pqm4: Testing and Benchmarking NIST PQC on ARM Cortex-M4 | https://eprint.iacr.org/2019/844 |
| Dilithium for Memory Constrained Devices | https://eprint.iacr.org/2022/323 |
| Apples, Oranges, and Signatures (full PDF; only abstract read) | https://eprint.iacr.org/2026/1333.pdf |
| Quantum-Resistant Security for Software Updates on Low-power Networked Embedded Devices (full PDF; only abstract read) | https://eprint.iacr.org/2021/781.pdf |
| RISQrypt (full PDF; robots-disallowed; only abstract read) | https://eprint.iacr.org/2026/312.pdf |
| Post-Quantum Command Authentication for Unmanned Systems (full PDF; only abstract read) | https://eprint.iacr.org/2026/2343.pdf |
| NSA CNSA 2.0 algorithms advisory | https://media.defense.gov/2022/Sep/07/2003071834/-1/-1/0/CSA_CNSA_2.0_ALGORITHMS_.PDF (unverified path) |
| NSA CNSA 2.0 FAQ | https://media.defense.gov/2022/Sep/07/2003071836/-1/-1/0/CSI_CNSA_2.0_FAQ_.PDF (unverified path) |
| CISA quantum pages | https://www.cisa.gov/quantum |
| UAE National Encryption Policy and executive regulation (primary text) | no primary URL found; WAM press item https://www.wam.ae/en/article/15w563h-uae-announces-approval-national-encryption-policy returned no article text |
| Everything under "Not retried in this pass" | see list above |
