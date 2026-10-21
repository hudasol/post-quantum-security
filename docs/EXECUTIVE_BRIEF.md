---
title: "Post quantum cryptography on drone and robot computers: two page brief"
author: "Huda Mueen"
date: "Evidence retrieved 2026-10-11 to 2026-10-20"
geometry: margin=1.8cm
fontsize: 10pt
---

**Update after round 5 (2026-10-21).** This brief summarises the evidence review. Since it was written, the free memory a flight stack leaves was measured from the linker output of real PX4 and ArduPilot builds (host measured, `docs/FLIGHTSTACK_STUDY.md`) and is smaller than the review assumed, so more devices need new hardware; the link model was checked with the ns-3 simulator, the session and update designs with the ProVerif verifier, and the command path with a flight stack in software in the loop. The current results, with their labels and limits, are in `docs/PAPER.md` and `docs/PROPOSAL_ROBOTICS.md`.

**Bottom line.** Published code and stack figures suggest that verify only post quantum designs fit Cortex-M class flight and robot computers that have that much memory free (not yet measured on a flight controller); per message post quantum signatures do not fit MAVLink class radio links; and the real deadline pressure is on **firmware signature trust anchors that cannot be changed after shipping**. Everything below is published or derived from retrieved sources; **nothing was measured on a microcontroller** (hardware plan included).

**What costs what** (published; pqm4 on Cortex-M4F; board and clock unresolved (README says 24 MHz, default board code says 20 MHz); setups differ)

| Operation | Cycles | Stack | Notes |
|---|---|---|---|
| ML-KEM-768 decaps (M4F code) | 707,827 | 6,452 B | stack optimised variant: 714,194 cycles in 2,844 B |
| ML-DSA-44 verify (M4F code) | 1,421,623 | 8,912 B | 2,712 B stack in the stack optimised variant (3.2 M cycles) |
| ML-DSA-44 sign (mean, M4F code) | 3,943,121 | 44,816 B | long tail from rejection sampling; 12.1 M cycles in 5,080 B stack variant |
| SPHINCS+ SHA2-128s sign (round 3, not final SLH-DSA) | 7.66 billion | 2,556 B | verify 7.47 M cycles |

Sizes: ML-DSA-44 signature 2,420 B (65: 3,309; 87: 4,627); ML-KEM-768 key 1,184 B, ciphertext 1,088 B; Ed25519 signature 64 B; MAVLink 2 signature field **13 bytes**. One ML-DSA-44 signature is about 10 full MAVLink payloads (derived), about 0.34 s of a 64 kbps SiK radio (derived).

**Headline findings**

1. *Authenticity risk is prospective, secrecy risk is retroactive.* Move long lived secret links (video, site maps, customer data) to hybrid ML-KEM key exchange early; move **firmware trust anchors** early too, because a classical key frozen in boot ROM or fuses must outlive the device.
2. *Planning dates exist:* UK NCSC 2028 / 2031 / 2035; EU end of 2026 / end of 2030 / 2035 and an explicit line that products living beyond 2030 should have a post quantum signature path for updates (Cyber Resilience Act link, Dec 2027); NIST IR 8547 draft: deprecate after 2030, disallow after 2035 (*in flux*). **No UAE algorithm level or embedded specific guidance found**; the UAE National Encryption Policy (v1.0, September 2025, read in full) asks entities for a public key inventory, lab testing, a transition plan, acquisition policies and training, with no algorithm, date or device rule.
3. *Upstream drone/robot software has no PQC yet:* none found in MAVLink, PX4/ArduPilot signing, DDS-Security 1.2, SROS2 or MCUboot. wolfBoot (ML-DSA, LMS/HSS, XMSS, hybrid), TF-M BL1 (LMS) and the PSA PQC API extension exist.
4. *Scheme choice for firmware:* LMS/HSS if one HSM backed signer can guard state (smallest code, 1.4 to 2.6 kB signatures); ML-DSA if not; SLH-DSA if conservative assumptions outweigh 7.9 kB+ signatures. Ship **dual** (classical + PQ) signatures, A/B slots, anti rollback.
5. *Fleet paths:* firmware update suffices only if there is an updatable stage before application code with flash/RAM headroom; classical only immutable ROM roots need replacement, a gateway, or a documented tolerated risk.

**Migration in five phases:** inventory (now) -> crypto agility groundwork -> post quantum capable verifier and dual signing in the updatable bootloader -> hybrid session keys and links -> procurement requirements and classical retirement. Each phase has exit criteria, risks and rollback in `docs/MIGRATION_PLAYBOOK.md`.

**What remains unmeasured:** Cortex-M33 cycles for ML-KEM and ML-DSA verification (published M33 figures for the standardised schemes cover only ML-DSA keygen and sign, from one paper; the other M33 rows are for RBLWE, which NIST did not select); final parameter SLH-DSA on any MCU; measured energy for the final standards; numbers from a flight controller running its flight stack (Cortex-M7 figures exist only on a Nucleo board); the harness itself on hardware (it has run only on a PC and in an emulator). Verification: phase 1 found 0 wrong values in 48 sampled rows; phase 2 found 15 of 269 rows with an error; phase 3 found 0 transcription errors but 41 of 403 new rows needing a mapping or warning fix (`docs/VERIFICATION3.md`).

**First experiment (E1):** ML-DSA-44 verify and ML-KEM-768 decaps cycles, stack and flash on a Cortex-M33 and a Cortex-M4F board (for example NUCLEO-L552ZE-Q and NUCLEO-L4R5ZI, the boards of `bench/board_kit/ONE_AFTERNOON.md`), pinned mlkem-native/mldsa-native v2.0.0, 3 power cycles, medians with bootstrap CIs. No purchase is needed: run it first in an emulator (QEMU or Renode) for correctness, flash and stack, then borrow a lab board for real cycle counts.
