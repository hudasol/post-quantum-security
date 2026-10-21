---
title: "What does post quantum cryptography cost on drone and robot computers, and how do fielded fleets migrate?"
subtitle: "A sourced review with a reproducible hardware benchmark plan"
author: "Huda Mueen"
date: "Evidence retrieved 2026-10-11 to 2026-10-20 (Asia/Dubai)"
---

> **How to read the labels.** **Published** = a number or fact copied from a source that was actually retrieved during this review (source and retrieval date in `data/evidence.csv` and Appendix A). **Host measured** = run on a PC (the first round on an x86 server, the second round on a laptop virtual machine); never comparable to a microcontroller. **Emulated** = run in QEMU on a Cortex-M4 or Cortex-M33 model, cross checked in Renode on an STM32F4 model: correctness, stack and image size only, never cycles (`docs/EMULATOR_RESULTS.md`). **Estimated** (derived) = my arithmetic, formula shown. *Inference* is not a label for numbers: it marks a sentence that is my reasoning, not stated by a source. **Planned** = to be measured on your hardware. No number in this report was measured on a microcontroller, and no estimate is presented as a measurement. Standards and guidance marked *in flux* may have changed after 2026-10-11.

# 1. Summary

**The question.** What does it cost to move the computers inside small drones and robots (Cortex-M4/M33-class microcontrollers and similar) to post quantum cryptography (PQC), and how can fleets already in the field migrate?

**Headline findings** (each is developed and sourced below):

1. **The hard problem is signatures and the frozen trust anchor, not key exchange.** Secrecy is exposed retroactively (harvest now, decrypt later), but authenticity is exposed prospectively: a forged firmware image only matters once a capable quantum computer exists *and* devices still trust the classical key. Where the verification key and algorithm sit in an immutable boot ROM or fuses, the scheme must outlive the device (NIST CSWP 39, RFC 9019, draft IR 8547, SP 800-208).
2. **Compute cost on Cortex-M4F is moderate for ML-KEM and ML-DSA verification, large for ML-DSA signing and very large for SLH-DSA signing.** Published pqm4 figures (board and clock ambiguous, see 4.1): ML-KEM-768 decapsulation takes {{cyc:S2-0024}} cycles in the speed optimised M4F code (derived: {{ms:S2-0024}}) and ML-DSA-44 verification {{cyc:S2-0033}} cycles (derived: {{ms:S2-0033}}). ML-DSA-44 signing averages {{cyc:S2-0032}} cycles with a long tail. Round-3 SPHINCS+ SHA2-128s signing, the predecessor of SLH-DSA, takes {{cyc:S2-0059}} cycles (derived: {{ms:S2-0059}}).
3. **Memory and flash decide feasibility more than cycles.** ML-DSA-44 signing needs {{stack:S2-0032}} bytes of stack in the fast M4F code but {{stack:S2-0035}} bytes in the stack optimised code, which is {{cyc:S2-0035}} cycles. Verification can be done in {{stack:S2-0036}} bytes of stack. Code is {{code:S2-0031}} to {{code:S2-0034}} bytes for the M4F specific ML-DSA-44 variants.
4. **Sizes, not speed, break the radio links.** An ML-DSA-44 signature is {{size:S2-0407}} bytes; MAVLink 2's signature field is 13 bytes (6 B tag) and its largest payload is 255 bytes, so one ML-DSA-44 signature fills 10 full frames (derived). Per message PQ signatures on MAVLink-class telemetry are not workable; session key designs are.
5. **No upstream support in the drone/robot stack yet.** I found no PQC in MAVLink, PX4/ArduPilot signing, the DDS-Security specification, mainline SROS2 or upstream MCUboot. wolfBoot (ML-DSA, LMS/HSS, XMSS, hybrid) and TF-M BL1 (LMS) implement PQ verification, and some vendors claim PQ or LMS verification in parts (press statements, unverified, see 4.7); the PSA Crypto API has a PQC extension (1.4 final, January 2026).
6. **Planning dates already exist.** UK NCSC 2028/2031/2035; EU end-2026 first steps, end-2030 high risk use cases, 2035 broad, and an explicit EU roadmap line that products with a life beyond 2030 should be upgradable to PQC with a post quantum signature path for firmware updates; NIST's *draft* IR 8547 proposes deprecating 112 bit strength RSA/ECC after 2030 and disallowing all quantum vulnerable public key algorithms after 2035. **No UAE or Gulf algorithm level or embedded device level guidance was found**; the UAE National Encryption Policy (version 1.0, September 2025, Cyber Security Council) was read in full and its post quantum section (section 6 of the policy) names no algorithm, date or device class (this report, section 3.3).
7. **Big evidence holes remain** (section 6): Cortex-M33 cycle counts exist only for ML-DSA-44 and ML-DSA-87 key generation and signing, from one paper on an STM32U5A5 (rows S10C-001 to S10C-036); none for ML-KEM, ML-DSA verification or SLH-DSA. No final parameter SLH-DSA cycles on any MCU; no measured energy for the final standards on a Cortex-M; nothing from a flight controller running its flight stack. *Correction (2026-10-16): earlier versions said there were no published ML-KEM, ML-DSA or SLH-DSA cycles on a named Cortex-M33; the S10C rows added that day contradict this, so the statement was narrowed.* The benchmark plan (docs/BENCHMARK_PLAN.md) is built to fill exactly these.

**Recommendations in one paragraph.** Inventory every cryptographic use and each product's root of trust now; make signature algorithms and sizes configurable (crypto agility); put a PQ capable verifier (stateful hash based LMS/HSS if you can run an HSM backed single signer, otherwise ML-DSA) into the *updatable* stage of each bootloader and ship dual (classical plus PQ) signatures; move long secrecy links to hybrid ML-KEM key establishment; for MAVLink-class links authenticate sessions with a PQ/hybrid handshake and keep short symmetric tags per message; treat units with classical only immutable roots as a hardware replacement or gateway decision with a date; and measure before committing hardware.

# 2. Scope, method and evidence discipline

The protocol was written before any evidence was collected (`docs/PROTOCOL.md`). Four research streams (standards, benchmarks, drone/robot specifics, migration/HNDL) plus two supporting streams (benchmark plan facts, host measurement) were run as separate research passes. Primary sources were preferred; search results were used only to locate sources, and no number comes from a search snippet.

**Evidence table.** `data/evidence.csv` has {{nrows}} rows (431 benchmark and size rows from phase 1, 46 protocol and size rows, 46 benchmark and size rows added in phase 2 from the author supplied PDFs of ePrint 2025/366 and 2020/470, 45 cycle and stack rows from the 2020/470 PDF found by a second, independent run of the brief and rechecked against the PDF, and {{n_s10}} rows added on 2026-10-16 from the author supplied PDFs of ePrint 2022/323, 2019/844, 2026/1333, 2021/781, 2026/312 and 2026/2343, each rechecked by a fresh reader, `docs/VERIFICATION3.md`, and {{n_s12}} rows added on 2026-10-20 after two independent readers, `docs/VERIFICATION5.md`), each with source title, URL, retrieval date, location in the source, and a comparability warning. It is summarised in Appendices A and B. **Comparability rules**: rows share an axis only if operation, parameter set and core family agree; differences in library, compiler, statistic, RAM definition and pre standard versus final parameters are flagged.

**Second run.** The brief was run twice in separate sessions and the results merged here. Of the second run's 582 rows, 299 match a row in this table by value and source, 245 appear only in the second run, and 38 carry no number; the 210 comparable pqm4 rows all matched. Rows only in the second run are not used until their source is read (`docs/CROSSCHECK.md`).

**Verification.** A separate verification pass that did not collect the data drew 50 rows with a seeded random draw (seed 20261011) and reopened each source. Of the 50, 48 could be checked against their source and **0 had a wrong numeric field (0/48 rows; 0/487 fields)**; three location citations were corrected; two rows and 31 field lines could not be verified because the source was blocked from the work environment. With zero errors in 48 rows the upper 95% bound on the row error rate is about 6% (rule of three: 3/48), so this is evidence of good copying accuracy, not proof of none. Details: `docs/VERIFICATION.md`. Phase 2 checked all 157 rows behind a headline number and a stratified random sample of 120 more: 15 of 269 verifiable rows had an error, 1 a wrong value and 14 a rounded size the table had left empty (`docs/VERIFICATION2.md`). Phase 3 rechecked every one of the 403 rows added on 2026-10-16: 0 transcription errors, but 41 rows (10.2 percent) needed a column mapping or warning fix (`docs/VERIFICATION3.md`). A fourth pass on 2026-10-18 rechecked a seeded sample of those rows field by field with new readers and ran a column lint over the whole table; its results are in the same file.

**Deviations** (full log in PROTOCOL section 10): the research passes used `curl` through the configured network proxy because interactive fetch approvals went unanswered (TLS verification on, no workaround of any explicit denial); several hosts (eprint.iacr.org, nsa.gov, cisa.gov, some vendor pages) were unreachable and nothing from them is used; one non numeric cell was moved into the warning column and three location only fixes were applied.

**Safety scope.** Side channel and fault topics are conceptual and defensive. No attack procedures. No cryptographic primitive was implemented here; the benchmark harness calls pinned, reviewed libraries.

# 3. Standards status and timelines

*All rows retrieved 2026-10-11 unless a later date is given; the BSI, ASD, Canada and Singapore items were rechecked on 2026-10-17 (`data/raw/S11_standards_recheck.md`). "In flux" marks drafts or items moving at the date read.*

## 3.1 NIST and the United States

| Item | Status as retrieved | Notes |
|---|---|---|
| FIPS 203 (ML-KEM), 204 (ML-DSA), 205 (SLH-DSA) | Final, 2024-08-13; errata lists exist for 203 and 204 (**in flux**) | NIST says they "can and should be put into use now" |
| HQC | Selected 2025-03-11 as a backup KEM; no FIPS yet (**in flux**) | rationale in NIST IR 8545 |
| FN-DSA / FIPS 206 (Falcon) | **No draft published** as of a NIST post dated 2026-09-28 (**in flux**) | NIST still consulting on fixed point arithmetic for signing and key generation; verification does not need floating point |
| SP 800-208 (LMS/HSS, XMSS/XMSS^MT) | Final, October 2020 | names firmware authentication for long lived constrained devices as a use case; key and signature generation only in FIPS 140 Level 3+ hardware modules; "not suitable for general use" because of state management |
| Draft SP 800-230 | Initial public draft, 2026-04-13 (**in flux**) | extra SLH-DSA parameter sets limited to 2^24 signatures per key, aimed at firmware, software and certificate signing |
| NIST IR 8547 (transition) | Initial public draft, November 2024; still presented as a draft (**in flux**) | 112 bit classical signatures deprecated after 2030, all quantum vulnerable public key algorithms disallowed after 2035 |
| SP 800-227 (KEM recommendations) | Final, September 2025 | |
| CSWP 39 (crypto agility) | Final 2025-12-19; update 2026-06-29 | defines crypto agility; describes crypto gateways for legacy systems |
| NSM-10 / OMB M-23-02 | Final policy, 2022 | 2035 goal; prioritised cryptographic inventory |
| CISA PQC Initiative page (printed 2026-10-12, supplied by the author) | Read by OCR, 11 pages | The page describes CISA work since July 2022 on federal migration, a product category list, cryptographic discovery tools and a guidance document on post quantum considerations for operational technology; it states that NIST approved FIPS 203, 204 and 205 on 2024-08-13. It also cites a June 2026 executive order and OMB memorandum M-26-15; those cited documents were not read, so nothing is claimed about their content |
| NSA CNSA 2.0 | FAQ, Ver. 2.1 (December 2024), read 2026-10-16 (`data/raw/S10_cnsa_faq.md`); the separate algorithms advisory is missing | For US national security systems only: ML-KEM-1024, ML-DSA-87, LMS or XMSS for firmware signing, SLH-DSA not approved; new acquisitions compliant from 2027-01-01 and non compliant equipment phased out by 2030-12-31, unless otherwise noted (rows 4, 5, 7, 10, 24, 25); several points marked *in flux* in the note |

## 3.2 United Kingdom, European Union and others

- **UK NCSC** (v1.0, 2025-03-20): finish discovery and plan by **2028**, highest priority migration by **2031**, complete by **2035**. It flags industrial IoT as possibly resource constrained and non upgradeable, and notes some vendors already ship LMS/XMSS secure boot.
- **EU Coordinated Implementation Roadmap, Part 1 v1.1** (dated 2025-06-11; page updated 2026-09-03): national strategies and first steps by **end-2026**; high risk use cases by **end-2030**; as many systems as feasible by **2035**; hybrids "whenever feasible and suitable"; **products with an expected lifetime beyond 2030 should be upgradable to PQC, with post quantum signatures on the update mechanism, linked to the Cyber Resilience Act from December 2027**; a use case with transition effort above about 8 years and high impact (securing software updates is the example) is high risk. This is the single most relevant government statement found for drone and robot makers.
- **Germany BSI** (rechecked 2026-10-17, S11 rows 13 to 15): hybrid preferred; TR-02102 is still at version 2026-01; SecP256r1MLKEM768 and SecP384r1MLKEM1024 from RFC 10024 will be recommended in the next TR-02102-2, for which no date is given, and BSI says they may already be used in a TR compliant way in TLS 1.3, as may X25519MLKEM768 (*in flux*). **France ANSSI**: hybrid recommended; "not reasonable" to buy non-PQC products after 2030. **Australia ASD**: stop traditional asymmetric cryptography by end-2030, does not recommend hybrids (retrieved via summary on 2026-10-11; the 2026-10-17 recheck failed because every request to cyber.gov.au timed out, and search results show that the page has moved and that a September 2026 ISM edition exists, so this item may be stale; S11 row 16; *in flux*). **Canada** (rechecked 2026-10-17, S11 rows 1 to 5): the Cyber Centre roadmap is unchanged since June 2025, and a Treasury Board implementation notice effective 2025-10-09 makes it binding for federal departments: plans, annual reporting and PQC procurement clauses from 1 April 2026, plan updates by 1 April 2027 and 1 April 2028, transitions under way by 1 April 2028, high priority systems by end-2031 and the rest by end-2035. Neither source reports whether the April 2026 plans were delivered. **Japan**: government target about 2035 (interim report, Nov 2025). **Singapore** (rechecked 2026-10-17, S11 rows 6 to 12): Version 1 of the handbook and the readiness index (CSA, GovTech and IMDA, 16 July 2026) replaced the consultation drafts. It states milestones for CII owners (a migration plan to CSA by 31 March 2027, new systems quantum safe or quantum safe ready from 1 January 2028, migration complete by 31 December 2031), recommends ML-KEM, ML-DSA and SLH-DSA with LMS and XMSS for firmware signing only, and calls itself not mandatory; detailed guidance for the milestones is still being developed (*in flux*). **South Korea**: KpqC selected HAETAE and SMAUG-T (Jan 2025).
- **IETF**: RFC 10024 (hybrid TLS 1.3 groups X25519MLKEM768, SecP256r1MLKEM768, SecP384r1MLKEM1024; Proposed Standard, August 2026); draft-ietf-tls-mlkem in the RFC Editor queue (**in flux**); RFC 9881 (ML-DSA in X.509); RFC 9964 (ML-DSA in COSE: -48/-49/-50); RFC 8778 (HSS-LMS in COSE: -46); RFC 8554/8391 (LMS, XMSS; Informational); RFC 10033 (state management for stateful hash based signatures); draft SUIT mandatory-to-implement algorithms recommends an HSS/LMS profile and has no ML-DSA profile in the revision read (**in flux**).

## 3.3 UAE and the Gulf (stated plainly)

*Primary text read.* The author supplied the National Encryption Policy of the UAE Cyber Security Council (version 1.0, September 2025, 51 pages, classification Open) and a printed copy of its summary page on uaelegislation.gov.ae (published 17 September 2025). Section 6, "Post Quantum Cryptography", has one subsection of six statements. In paraphrase, an entity must: keep an inventory of systems and applications that use public key cryptography (6.1.1); test the new post quantum standard in a lab before production (6.1.2); plan the transition, including what the policy calls 'Independence analysis' (issues that may affect the order of system transition), decommissioning of unsupported technology, and validation of products (6.1.3); write acquisition policies for post quantum cryptography (6.1.4); alert IT departments and vendors (6.1.5); and train its workforce (6.1.6). The scope clause covers federal government entities and critical information infrastructure entities, with emirate level bodies handled by an emirate lead where an emirate programme exists. **The section names no algorithm, no deadline, no hybrid requirement and no rule for embedded or unmanned devices.** The earlier press reports (a policy and executive regulation approved in November 2025, overseen by the Cybersecurity Council) were not checked against this text and the executive regulation was not supplied [unverified].

*Other UAE items* (a national post quantum migration plan agreed in May 2026, a TII post quantum software library, QuantumGate) are listed with their public sources in `docs/CONTEXT_ENTITIES.md` (TII-03, TII-06, ADEO-02); they are not guidance for embedded devices.

*Rest of the Gulf:* a Saudi central bank (SAMA) circular with inventory deadlines (2026-12-31) and risk assessment deadlines (2027-03-31) is reported only by secondary sources and is **unverified**. For Qatar, Oman, Kuwait and Bahrain no migration guidance was found (Bahrain: a vendor press release about a tooling procurement only). CBUAE, ADGM, DIFC, Dubai Electronic Security Center and TDRA: nothing PQC specific found.
*Implication for you* [inference]: for UAE research and industry partners the practical anchors are the national policy (inventory, lab testing, plan, acquisition policy), the EU/UK dates when exporting, and the NIST algorithms; ask the UAE National Cryptography Center which algorithm profile applies to embedded and unmanned systems.

# 4. What the published numbers say

*Everything in this section is published (not measured here) unless it says derived. Setups differ; read the warnings before comparing.*

## 4.1 The comparability warning that matters most

The only maintained benchmark with the final ML-KEM/ML-DSA names on Cortex-M4F is **pqm4** (`benchmarks.csv`, last changed 2025-05-22). Its README says all cycle counts were taken at 24 MHz to avoid flash wait states, but its default board's (NUCLEO-L4R5ZI) benchmark clock path in code is 20 MHz and the CSV does not name the board; two other papers say the pqm4 reference numbers came from an L4R5ZI. **I therefore treat the pqm4 clock as unresolved**; every time figure here is derived at both candidate clocks (24 MHz from the README, 20 MHz from the code of the default board) and is not a claim about any particular board. The board and clock were checked in the project's own files (`data/raw/S6_pqm4_config.md`): the README default board is the NUCLEO-L4R5ZI, the benchmarks.py default platform is the STM32F4 Discovery, and the result files record neither. pqm4 itself carries a notice that it will be archived read only in or after January 2027. pqm4 times with SysTick, not the DWT counter. Its ML-DSA rows are means of 1000 runs and its KEM rows means of 10.

## 4.2 ML-KEM (FIPS 203) on Cortex-M4F

![ML-KEM cycles per operation (published, pqm4)](../plots/fig1_mlkem_cycles.png)

For ML-KEM-768 the reference-C ("clean") code needs {{cyc:S2-0019}} / {{cyc:S2-0020}} / {{cyc:S2-0021}} cycles for keygen / encaps / decaps with {{stack:S2-0021}} bytes of stack on decapsulation; the M4F specific speed optimised code needs {{cyc:S2-0022}} / {{cyc:S2-0023}} / {{cyc:S2-0024}} cycles ({{stack:S2-0024}} bytes stack, {{code:S2-0022}} bytes code), and the stack optimised variant {{cyc:S2-0025}} / {{cyc:S2-0026}} / {{cyc:S2-0027}} cycles in only {{stack:S2-0027}} bytes of stack. So the stack optimised variant costs about {{ratio:S2-0027/S2-0024}} the cycles of the speed variant for under half the stack. (ratio of published cycle counts, same benchmark.)

Other published context (different setups, never on one axis with pqm4): wolfCrypt on a Cortex-M4 NUCLEO-F439ZI at 168 MHz reports ML-KEM-768 decaps average {{note_ms:S2-0328}} ms (vendor blog, ML-KEM in assembly); the RP2040 (Cortex-M0+, 125 MHz, preprint) {{note_ms:S2-0226}} ms for decaps from a timer, with cycles derived as time x 125.

## 4.3 ML-DSA (FIPS 204) and firmware signature verification

![ML-DSA cycles per operation (published, pqm4)](../plots/fig2_mldsa_cycles.png)

For ML-DSA-44 verification, the operation a secure bootloader performs: {{cyc:S2-0030}} cycles in reference C, {{cyc:S2-0033}} in the M4F specific code ({{stack:S2-0033}} bytes of stack) and {{cyc:S2-0036}} in the stack optimised code ({{stack:S2-0036}} bytes). Signing is far costlier and variable: {{cyc:S2-0032}} cycles (mean) in the M4F code with {{stack:S2-0032}} bytes of stack; {{cyc:S2-0035}} cycles in {{stack:S2-0035}} bytes in the stack optimised code. ML-DSA-65 verification: {{cyc:S2-0042}} cycles (M4F code).

**The tail matters.** ML-DSA signing repeats until a candidate passes checks, so its time depends on the data. The RP2040 preprint reports a coefficient of variation near 66-73% for signing, and for its 10,000-run campaign p95 of 421.3 ms and max of 1156.79 ms against a mean of 182.7 ms for ML-DSA-44 (published, Cortex-M0+). A methodology paper (Riou et al., ePrint 2026/1333, full text read 2026-10-16) argues min/average/max are unsuitable for migration planning and reports best, average and worst observed cycles for three ML-DSA libraries on a Cortex-M33 (rows S10C-001 to S10C-036). [Inference] For a drone, signing on board therefore needs a worst case budget, not an average, and verification only designs avoid the problem. mldsa native ships a restartable signing example for bounding run time.

![Stack usage on Cortex-M4F (published, pqm4)](../plots/fig3_stack.png)

**Other published points.** wolfSSL's blog (Cortex-M4, 168 MHz): ML-DSA-44 verify average {{note_ms:S2-0334}} ms, sign {{note_ms:S2-0333}} ms. On the RP2040 (Cortex-M0+ at 125 MHz): ML-DSA-44 verify {{note_ms:S2-0234}} ms against ECDSA P-256 verify {{note_ms:S2-0244}} ms and RSA-2048 private operation {{note_ms:S2-0247}} ms (mbedTLS built with SDK defaults, not tuned, so the classical side is not a fair optimum). The CHERIoT blog (simulated Ibex RISC-V core) gives ML-DSA-44 verify {{cyc:S2-0363}} cycles.

## 4.4 SLH-DSA (FIPS 205) and stateful hash based signatures

![Hash based verification (published)](../plots/fig5_hash_verify.png)

*No final parameter SLH-DSA or LMS cycle count on any microcontroller was found.* What exists:

- **pqm4's SPHINCS+ rows are round-3 "simple" parameter sets, not FIPS 205**, reference C only. SHA2-128s: sign {{cyc:S2-0059}} cycles, verify {{cyc:S2-0060}}; SHA2-128f: sign {{cyc:S2-0056}}, verify {{cyc:S2-0057}}. Signatures are 7,856 (128s) and 17,088 (128f) bytes in FIPS 205 (published sizes). [Derived] verification takes {{ms:S2-0060}} (128s) and {{ms:S2-0057}} (128f); [inference] signing on-device is impractical.
- **LMS/XMSS on Cortex-M4** come from the full paper of Campos et al. (ePrint 2020/470, read from the supplied PDF; rows S7 and S8, SHA-256 variants) and from their conference *slides* (STM32F4DISCOVERY, clock not stated, pre-RFC-final variants). From the slides: LMS h5 SHA-256 verify {{cyc:S2-0316}} cycles with {{stack:S2-0316}} bytes of stack; LMS h10 verify {{cyc:S2-0319}}; XMSS ROBUST h10 verify {{cyc:S2-0322}}. The XMSS paper of Bos et al. (FRDM-K64F, 120 MHz) reports {{cyc:S2-0254}} cycles for reference XMSS-SHA2_10_256 verification and {{cyc:S2-0257}} with its speed-up techniques.
- **Boot time measurements** (wolfSSL blog, STM32H563 at 320 MHz, ~100 KB image, *total boot time, not verification only*; vendor, unverified): SHA2-only baseline {{note_ms:S2-0347}} ms; ECDSA P-256 {{note_ms:S2-0349}} ms; ML-DSA-44 {{note_ms:S2-0351}} ms; ML-DSA-87 {{note_ms:S2-0353}} ms; LMS 1-10-8 {{note_ms:S2-0354}} ms; XMSS-SHA2_10_256 {{note_ms:S2-0355}} ms; hybrid ECC+ML-DSA-65 {{note_ms:S2-0356}} ms. The blog gives 320 MHz for the STM32H563, above the 250 MHz maximum that Zephyr's board page lists for the NUCLEO-H563ZI, so the clock or part naming is doubtful. The same table lists Ed25519 at {{note_ms:S2-0350}} ms, which shows how much an unoptimised configuration can distort comparisons.
- **TF-M BL1** states its LMS software verifier is about 3 KiB versus at least 6.5 KiB for RSA (vendor documentation claim).

## 4.5 Sizes

![Key and signature sizes](../plots/fig4_sizes.png)

ML-DSA-44/65/87 signatures are {{size:S2-0407}} / {{size:S2-0410}} / {{size:S2-0413}} bytes and public keys {{size:S2-0406}} / {{size:S2-0409}} / {{size:S2-0412}} bytes (FIPS 204). ML-KEM-768 encapsulation key {{size:S2-0399}} and ciphertext {{size:S2-0401}} bytes (FIPS 203). Ed25519 signature: 64 bytes (PX4 docs). X25519MLKEM768 key shares: 1,216 (client) and 1,120 (server) bytes (RFC 10024).

## 4.6 Energy

Published *measured* energy exists only for **pre standard** Kyber/Dilithium on a Cortex-M4 at 96 MHz (Saarinen 2020) and on an ESP32 (2026 paper). Example on the Cortex-M4 (NUCLEO-F411RE, 96 MHz): Kyber768 decaps {{eng:S2-0195}} uJ; Dilithium2 verify {{eng:S2-0204}} uJ; Dilithium2 sign {{eng:S2-0203}} uJ; ECDSA P-256 verify {{eng:S2-0213}} uJ (same paper). On the ESP32 (240 MHz): Dilithium2 sign {{eng:S2-0218}} uJ. The RP2040 energy figures (for example {{eng:S2-0248}} uJ for ML-DSA-44 keygen+sign+verify) are **a datasheet model estimate, not a measurement**, by the source's own statement. **No measured energy for the final ML-KEM/ML-DSA/SLH-DSA on a Cortex-M was found.**

## 4.7 Hardware acceleration

Only FPGA and ASIC results were found (RISQrypt on an Artix-7 co-design: Kyber768 decaps 35 thousand cycles, 109 thousand masked; Dilithium3 verify 126 thousand cycles; Adams Bridge in 5 nm synthesis; a PQShield NTT block at 258 cycles per 256-point transform). Vendors claim PQC acceleration or verification in ST (X-CUBE-PQC with the STM32 crypto accelerator), Microchip (MEC175xB: ML-DSA, LMS verification and ML-KEM "in immutable hardware"; Cortex-M4F at 96 MHz) and Infineon (PSOC Control C3: LMS verification with SHA hardware). **None of these vendor pages gives cycle counts or a verifiable device list**; treat them as leads to ask suppliers about. A 2025 Mbed TLS vulnerability (CVE-2025-49600, an LMS-verification bug with unchecked hash return values) is a reminder that offload paths must fail closed: a failing hash accelerator could let an invalid LMS signature be accepted.

## 4.8 Classical baselines

Published classical numbers on matching devices exist (ECDSA/ECDH on the F411RE at 96 MHz; wolfCrypt RSA/ECC on the F439ZI; RP2040 mbedTLS). Round 4 added double read Cortex-M4 cycle rows for X25519 and Ed25519 (stream S12; for example S12A-330 to S12A-332 and S12A-317 to S12A-328), and pqm4 still has no classical baselines. Cross paper ratios are computed in `docs/ENERGY_STUDY.md`, with the published range shown beside each, and the same rows are combined in `docs/MISSION_STUDY.md` and `docs/REFERENCE_ARCHITECTURE.md`; setups differ between papers, so these ratios carry that caveat.

# 5. Drone and robot constraints

## 5.1 MAVLink signing

MAVLink 2 signing sets an incompatibility flag and appends **13 bytes**: 1 link ID, 6 B timestamp (10 microsecond units since 2015-01-01) and a 6 B tag, the first 48 bits of a SHA-256 over the secret key, header, payload, CRC, link ID and timestamp. The key is **32 bytes, shared by all parties**; provisioning is out of band or via `SETUP_SIGNING` over a secure link such as USB. Maximum payload 255 bytes; maximum signed packet 280 bytes. PX4 documents that signing gives no confidentiality, no per party identity, and no automatic key rotation, that a few messages (HEARTBEAT, RADIO_STATUS, ADSB_VEHICLE, COLLISION) are always accepted unsigned, and that without a key everything is accepted. ArduPilot's page says telemetry downlink and USB are unaffected by signing. A 2026 CVE record notes the baseline problem: MAVLink needs no authentication by default.
[Inference] A symmetric 256 bit key MAC is not what a quantum computer breaks directly; what is exposed is the **provisioning path** and any asymmetric steps around it, and the fact that nothing in the protocol can carry a PQ signature.
*Found absent:* no PQC specific MAVLink standard, no PX4/ArduPilot documentation of PQC signing, no peer reviewed measurement of PQC on a MAVLink flight controller. Community and preprint items exist (an ArduPilot forum RFC proposing authentication as first class messages and a KpqC feasibility preprint, ePrint 2026/2343, full text read 2026-10-16, rows S10F; its measurements are on a PC, not a flight controller); the forum author's numbers are unverified and are not used. Phase 2 addition: the MAVLink issue tracker records the maintainers' stated position. In mavlink/mavlink issue 2525 (closed 2026-06-30, https://github.com/mavlink/mavlink/issues/2525) a maintainer said there is no post quantum roadmap and the project does not think it needs one, that signatures recorded now are not a harvest risk, and that carrying about 4.6 kB per message is not acceptable; issue 2527 (closed 2026-06-24) was a third party wire format proposal that maintainers said falls outside the existing extension mechanisms. This is a project statement as read on 2026-10-12, not a standard.

## 5.2 Secure boot and OTA

- **PX4**: Ed25519 (monocypher), 32 B key, 64 B signature, fits a 128 KB bootloader sector; **ArduPilot**: bootloader can embed up to 10 public keys (the docs read do not name the algorithm; its tooling depends on monocypher, so an Ed25519-class scheme is likely, an inference). Both are classical signature checks in a fixed size bootloader region, which is the immutable-first-stage case.
- **MCUboot**: signature types listed are RSA, ECDSA and Ed25519; **no PQC identifier found** in the main branch design doc and release notes (issue and PR search was blocked, so absence is not proof).
- **wolfBoot** v2.0.0 added LMS/HSS and XMSS (2023-11-07), v2.3.0 ML-DSA and hybrid (2024-10-31), v2.10.0 (2026-10-01) lists an NXP i.MX RT700 ML-DSA-87 configuration; example headers: 4,840 bytes (ML-DSA-44), 5,288 bytes (2-level LMS). **TF-M BL1** verifies with LMS; **PSA Certified Crypto API** has a PQC extension (1.4 final, 2026-01-28) covering LMS, HSS, XMSS, ML-DSA, SLH-DSA and ML-KEM. **Zephyr 4.4.2** ships only experimental mldsa native (ML-DSA-87, internal) and Mbed TLS LMS verification.
- **SUIT/COSE/Uptane**: identifiers exist (HSS-LMS -46; ML-DSA -48/-49/-50); the SUIT mandatory-to-implement draft recommends an HSS/LMS profile; Uptane 2.1.0 (as read) shows RSA, ECDSA, Ed25519 and no PQC text.
- **Caliptra** (an open source silicon root of trust, datacenter oriented, used here only as a documented pattern): release 1.3 adds a software only ML-DSA-87 identity chain via runtime firmware without ROM change, while the ROM-rooted classical chain stays and the PQ chain does not attest the ROM.

## 5.3 ROS 2, DDS-Security, micro-ROS

DDS-Security 1.2 (cover marks it not yet final) specifies RSASSA-PSS/PKCS#1 v1.5 (2048 bit), ECDSA P-256/P-384, DHE MODP-2048 and ECDHE P-256/P-384 with AES-GCM/GMAC; a text search found **no post quantum algorithm**. ROS 2 uses it through SROS2 (security off by default; vendor interoperability of secure communication not supported per the tutorial). Research forks exist (PQSec-DDS plugin for Cyclone DDS; a Dilithium3 SROS2 fork and a hybrid Zenoh fork in a thesis; AXON, a non-DDS RMW with X25519MLKEM768 over QUIC whose own authors say peer authentication is not post quantum or even validated in the shipped mode) with **no benchmarks on robot or MCU hardware**. micro-ROS: official security pages could not be fetched; one paper built a classical TLS 1.3 transport (about 20% time overhead for single value messages). I found no PQC micro-ROS work.

## 5.4 Why sizes break links (derived estimates)

All figures here are **derived**: `chunks = ceil(N / C)`, `t = 8N / R_eff`, with N from published sizes and C, R from published link limits; they ignore headers, retransmission, acknowledgements and contention.

Chunk capacities (published): MAVLink payload 255 B; FTP data 239 B per message (251 B payload minus a 12 B header); ENCAPSULATED_DATA 253 B; TUNNEL 128 B; LoRaWAN EU868 DR0-DR2 51 B; US915 DR0 11 B; IEEE 802.15.4 about 81 B worst case with AES-CCM; BLE default 23 B.

| Object | Bytes | MAVLink 255 B | FTP 239 B | TUNNEL 128 B | LoRaWAN EU DR0 51 B | 802.15.4 81 B | BLE 23 B |
|---|---|---|---|---|---|---|---|
| ML-DSA-44 signature | 2420 | 10 | 11 | 19 | 48 | 30 | 106 |
| ML-DSA-65 signature | 3309 | 13 | 14 | 26 | 65 | 41 | 144 |
| ML-DSA-87 signature | 4627 | 19 | 20 | 37 | 91 | 58 | 202 |
| LMS H10/W8 signature (computed from RFC 8554) | 1452 | 6 | 7 | 12 | 29 | 18 | 64 |
| HSS 2x H5/W8 (wolfBoot docs) | 2644 | 11 | 12 | 21 | 52 | 33 | 115 |
| SLH-DSA-128s signature | 7856 | 31 | 33 | 62 | 155 | 97 | 342 |
| Ed25519 signature (reference) | 64 | 1 | 1 | 1 | 2 | 1 | 3 |

Serial airtime (SiK default 64 kbps; about 90% usable without error correction, about half with it): an ML-DSA-44 signature takes about 0.34 s, ML-DSA-65 0.46 s and ML-DSA-87 0.64 s with ECC off, double with ECC on; at LoRaWAN EU868 DR0 (250 bit/s nominal) the same signatures need about 77 s, 106 s and 148 s, and a 1% duty cycle then enforces hours of silence. Plot (derived, not measured):

![Chunks needed per object (derived estimate)](../plots/fig6_chunks_derived.png)

**Conclusion** [derived + inference]: per message PQ signatures are impossible in a 13 B field and wasteful elsewhere; occasional large objects (a firmware manifest signature, a certificate chain, a hybrid handshake of 2,336 bytes of key shares) can be chunked on slow links but need reassembly state and loss handling that MAVLink has no standard service for.

## 5.5 Side channel and fault considerations (conceptual, defensive)

Structured lattice schemes can leak through timing, power or EM and can be disturbed by faults; protecting an implementation needs scheme specific countermeasures (constant time coding, masking, shuffling, redundancy and validity checks, isolation) [Ravi et al. survey]. Published masking costs: first order masked Kyber decapsulation about 3.1 million cycles on Cortex-M4F, a factor 3.5 over the unprotected optimised code (Bos et al.); masked Kyber768 decaps 2,978,441 cycles including RNG (Heinz et al.); in an FPGA co-design masked Kyber768 decaps is 3.1x and masked Dilithium3 signing 2.6x the unmasked cost (RISQrypt Table 8, ratio derived). For stateful hash based signatures the danger is operational (reusing a one time key); SP 800-208 requires the state to be committed to non volatile memory before a signature is exported. [Inference] A captured drone is physically accessible, so these classes matter mainly for keys that live on the vehicle; a verify only device holding public keys has a smaller exposure than one that signs.

# 6. What is not known (and what that means)

| Gap | Consequence | Where addressed |
|---|---|---|
| Cortex-M33 cycles only for ML-DSA keygen and sign (S10C, STM32U5A5); none for ML-KEM, ML-DSA verify or SLH-DSA | cannot say what moving from M4F to M33 changes for key exchange or verification | E1 on NUCLEO-U575ZI-Q |
| No **final parameter SLH-DSA** cycles on any MCU; LMS and XMSS cycles come mainly from Campos et al. (ePrint 2020/470, rows S7, S8), plus the Bos et al. XMSS paper and conference slides (S2) | firmware signing choice rests on that paper, slides and round-3 data | E2 |
| No **measured energy** for final standards on a Cortex-M | battery impact unquantified | E3 |
| **pqm4 board/clock unresolved**; project to be archived | no stable maintained baseline | E1 reproduces pqm4 rows on the L4R5ZI |
| Cortex-M7 numbers exist on a Nucleo-F767ZI (rows S7-001 to S7-024) but none on a flight controller running its flight stack | | later E1 on a Pixhawk-class board |
| No PQC in MAVLink/DDS-Security/MCUboot upstream | migration needs wrappers or forks | playbook phases 2-3 |
| Vendor ROM/accelerator claims unverified | hardware replacement decisions need written vendor answers | playbook phase 0/4 |

# 7. Harvest-now-decrypt-later: what needs secrecy and what needs authenticity

**Sourced framing.** NIST draft IR 8547 and the CISA/NSA/NIST fact sheet describe harvest now, decrypt later for confidentiality; IR 8547 says authentication has no harvest analogue because it stays secure as long as the algorithms and keys are secure when authentication is performed; Banegas et al. state that a quantum breakthrough at time T does not affect signatures made before T but allows forging after T. The Mosca inequality (from GRI 2025 and IR 8547): trouble if shelf life X plus migration time Y exceeds the time Z to a cryptographically relevant quantum computer. The EU roadmap treats confidentiality needs beyond about 10 years as high risk. NCSC notes that for field OT sensors integrity is likely critical while confidentiality may not need strong protection.

**Timeline uncertainty (no date asserted).** The Global Risk Institute 2025 survey of 26 experts put a cryptographically relevant quantum computer as "quite possible (28-49%)" within 10 years and likely (51-70%) within 15 (expert opinion, broad bins). Resource estimates keep falling: Gidney 2025 estimates RSA-2048 factoring in under a week with under one million noisy qubits (under stated hardware assumptions); a 2026 Google whitepaper (abstract only) reports fewer than about 1,200 logical qubits for 256 bit ECDLP. These are engineering estimates, not forecasts; use agency dates (NCSC, EU, NIST draft) as planning deadlines.

**Classification of drone/robot data (inference; replace the lifetimes with your own).**

| Asset | Confidentiality lifetime | Authenticity lifetime | Priority |
|---|---|---|---|
| Telemetry (attitude, battery, position) | short; long if it reveals people or sensitive sites | short | low (secrecy), medium if tracks are sensitive |
| Video / imagery | medium to long (people, facilities, infrastructure) | short to medium (evidence needs provenance) | **high secrecy** |
| Mission plans, geofences | medium to long for sensitive operations | short per mission | medium |
| Maps / point clouds / site models | **long** | medium to long (poisoned maps) | **high** |
| Customer and site data | **long** (contractual, 10+ years) | medium to long | **high** |
| Firmware images | medium (low if public) | **very long**: the verification key outlives the device | **high authenticity** |
| Commands | short | short per command; key trusted for long | medium, via key provisioning |
| Long term keys and provisioning secrets | lifetime of what they protect | fleet lifetime | **high** |
| Logs | short to long | medium to long (forensics) | medium |
| Device identity / attestation certificates | low (public) | **very long** if ROM- or fuse rooted | **high authenticity** |

The practical rule: **move secrecy to hybrid KEM early because delay costs you retroactively; move authenticity where the trust anchor outlives the device, because that is where delay becomes unfixable.**

# 8. Hybrid, crypto agility and hardware acceleration in practice

- **Hybrid key exchange** is standardised for TLS 1.3 (RFC 10024) and IKEv2 (RFC 9370). Cost: X25519MLKEM768 key shares total 2,336 bytes versus 64 for X25519 (about 36.5x, derived). NIST leaves hybrid use to applications; BSI and ANSSI favour it; ASD does not.
- **Hybrid signatures for firmware**: carry two signatures and verify both (simple, fits current boot designs, cost dominated by the PQ part). wolfBoot, Infineon and Microchip describe this. NIST expects hybrids to be temporary, implying a second transition.
- **Crypto-agility** (NIST CSWP 39): the ability to replace algorithms in protocols, software, hardware and firmware while preserving operations; buffers and storage should not assume algorithm specific sizes; crypto gateways protect legacy components whose crypto cannot change; hardware functions cannot be changed in the field except in reconfigurable logic.
- **Hardware acceleration**: see 4.7; use it, but verify fail closed behaviour and ask vendors for numbers.

{{INCLUDE:DECISION_FRAMEWORK.md|# Decision framework|9. Decision framework}}

**Fleet planner result (estimated, synthetic fleets).** How many devices need new hardware depends on which implementation the planner's memory thresholds assume. On a synthetic fleet of 1000 devices it ranges from {{plan:hr_low:1000}} (thresholds from stack optimised assembly, published pqm4 rows) to {{plan:hr_high:1000}} (reference C, published pqm4 rows), and {{plan:changed:1000}} devices ({{plan:share_changed:1000}} percent) change class between the two; speed optimised assembly and this repository's portable C build fall in between (`docs/PLANNER_STUDY.md`). A plan should carry the range, not one of its ends. *Correction 2026-10-18: an earlier version of this paragraph gave 246 to 371; the signature memory thresholds were then corrected (ML-DSA-44 header size and the verifier's key and signature buffers, `docs/PLANNER_RULES.md`).*

{{INCLUDE:MIGRATION_PLAYBOOK.md|# Migration playbook for a deployed drone/robot fleet|10. Migration playbook}}

# 11. Benchmark plan (summary; full plan in docs/BENCHMARK_PLAN.md)

No purchase is required (emulator first, then borrowed lab hardware; `docs/NO_PURCHASE_PLAN.md`). Reference boards that a lab may already own (approximate single unit prices seen 2026-10-11, for reference only): NUCLEO-U575ZI-Q (Cortex-M33, $26.35), NUCLEO-L4R5ZI (Cortex-M4F, pqm4's default board, $33.61), optional Raspberry Pi Pico 2 (M33, about $6, needs an SWD probe), Nordic PPK2 for energy ($99.95). Software pinned by commit: mlkem native and mldsa native v2.0.0 (`d1b2fe7...`, `834a90d...`), wolfSSL v5.9.4-stable, wolfBoot v2.10.0, TF-PSA-Crypto v1.2.0. Method: DWT cycle counter at a fixed 0-wait state clock, stack painting, baseline subtracted code size, deterministic APIs so the RNG is outside the timed region; at least 3 power cycles, medians and percentiles with bootstrap CIs, ML-DSA signing reported as a distribution. Experiments: **E1** ML-KEM/ML-DSA cycles, stack and flash on M33 and M4F (first); **E2** hash based verification (specification only); **E3** energy; **E4** boot time impact in wolfBoot; **E5** link level transfer of signatures and handshakes over real radios.
**Status of the code**: the harness (`bench/mcu`) runs on a PC (*host measurement*) and in QEMU on Cortex-M4 and Cortex-M33 models (*emulated*: 36 builds pass their checks, stack and size in `bench/mcu/qemu_results/`, no cycles); its statistics script (`bench/stats`) was tested on that host output; the power script (`bench/power`) was tested on synthetic traces only. **None has been run on a microcontroller or a real power meter.** Host measured examples (x86 Xeon VM, liboqs 0.16.0, portable-C variant): ML-KEM-768 decaps about 62 microseconds (median of 5 runs) and ML-DSA-44 verify about 106 microseconds, versus millions of cycles on a Cortex-M; these say nothing about MCU ranking.

# 12. Limitations

- Evidence is only as good as retrieval: some hosts (NSA, several vendor pages) were unreachable from the work environment; the author supplied several of the papers and the CISA page by hand, and only what is read from those copies is used.
- Many MCU figures come from vendor blogs, preprints and conference slides. They are labelled as such in the table.
- The pqm4 board and clock are unresolved; pre standard Kyber/Dilithium rows are kept out of final standard comparisons.
- Government pages change; items marked *in flux* must be rechecked before relying on them.
- UAE coverage now rests on the policy text for section 6, plus press reports for everything else; the executive regulation was not supplied and Arabic sources were not searched.
- The decision framework and classifications tagged *inference* are my reasoning and need review by a cryptographer before a product decision.
- The verification results (phase 1: 0 of 48 rows wrong; phase 2: 15 of 269; phase 3: 41 of 403 needing a mapping or warning fix, 0 transcription errors; pass 4, a second sampled reading and a column lint: `docs/VERIFICATION3.md`) bound copying errors in the table, not the correctness of the sources themselves.

{{APPENDICES}}
