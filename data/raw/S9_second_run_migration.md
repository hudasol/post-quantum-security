<!-- Raw notes from the second run (phase 1), retrieved 2026-10-11. Kept unedited except this line and the path mentions. Not independently verified except where data/crosscheck says so. -->
# Migration, hybrids, crypto-agility, HNDL and side-channel/fault considerations

Scope: PQC for MCU-class deployed devices. Retrieval date for all sources: 2026-10-11. Source IDs refer to ./data/sources_migration.csv. Labels: [published] = stated in retrieved source; [derived] = my inference from sources. No numbers here are benchmark figures; sizes quoted are from specs.
Flag "IN FLUX" = guidance still moving or sources conflict.

## 1. Firmware-upgradable vs hardware replacement

- NIST CSWP 39 (Dec 2025) notes embedded algorithms are often fixed at compile time; fixed-function chips may need replacement; boot code with fixed public keys may not be updatable, so signatures must stay secure for device lifetime [published, M02]. IN FLUX: the fetch summary said the Dec 2025 version was withdrawn 2026-06-29 and replaced by CSWP 39-upd1 (M03 confirms upd1 published 2026-06-29; M04 shows the 2025 draft obsoleted by the final). I did not read upd1 text; re-check before citing CSWP 39 content.
- NIST IR 8547 draft: where devices cannot be updated, they should be designed to require quantum-resistant signatures, and verification code may be infeasible to update after manufacture [published, M11]. IR 8547 is the Nov 2024 initial public draft (M10); I did not verify whether a final exists. IN FLUX.
- NCSC UK: plan to identify long-lived hardware roots of trust that must migrate by 2028; ICS/IIoT devices may be resource-constrained, non-upgradeable, or hard to service [published, M01].
- EU roadmap deck: long-lived hard-to-upgrade devices (satellites, meters, vehicle sensors, ePassport chips); aims to make firmware/software upgrades quantum-safe by default by end 2030 [published, M05].
- ROM/immutable RoT example: TF-M BL1 splits ROM code (BL1_1, hash check against OTP) from BL1_2 (flash/OTP, LMS verification); BL1_2 has no upgrade logic and changes only at provisioning, because changing ROM after manufacture is expensive. OTP holds public key, BL1_2 hash and rollback counter; LMS signature 1912 bytes, 1024 signatures per key [published, M30]. Takeaway [derived]: a ROM that verifies only RSA/ECDSA cannot be fixed in the field; a design where ROM verifies a replaceable second stage via a hash gives a migration path only if that hash is in field-writable/provisionable storage.
- Secure elements/HSMs with fixed algorithms: no retrieved primary source on specific parts. Microchip press release body was not retrievable (M38); do not cite vendor features. Gap.
- Flash/RAM headroom: IETF PQUIP constrained-devices draft notes ML-DSA signing needs substantial RAM, with lazy expansion and external-mu hashing as mitigations; store seeds rather than expanded keys [published, M19]. Draft is Informational, in IESG evaluation as of fetch (IN FLUX).

## 2. Firmware-signing migration vs session/key-establishment migration

- NIST SP 800-208 (Oct 2020): LMS/HSS and XMSS/XMSS^MT; suited to long-lived systems such as firmware authentication on constrained devices; approved parameter sets use SHA-256 or SHAKE256 with 192- or 256-bit outputs [published, M12, M13]. Key/signature generation must be in hardware cryptographic modules (FIPS 140 level 3 per section 8.1 as summarised); verification modules just implement an approved parameter set. State: leaf index must be persisted in non-volatile storage before the signature is released; naive file writes can be lost [published, M13].
- Implication [derived]: on-device work is verification only (small code, no secret); state burden sits with the signing HSM, not the MCU. Session/key establishment is different: both endpoints must support it and handshake size/RAM change (ML-KEM-768 hybrid TLS key shares: 1216 B client / 1120 B server for X25519MLKEM768 [published, M14]).
- NSA CNSA 2.0 FAQ v2.1 (Dec 2024): recommends LMS/XMSS for firmware/software signing, prefers LMS SHA-256/192; HSS, XMSS^MT and SLH-DSA not approved; reason given: firmware roots of trust are locked for system life; signature generation needs CMVP-validated hardware, verification-only needs CAVP [published, M07]. ML-DSA approved, expected preferred for some uses later. A secondary summary reports "support and prefer by 2025, exclusive by 2030" for software signing (M06, secondary). Note the retrieved FAQ header says Dec 2024 v2.1; newer revisions not ruled out (IN FLUX).
- NCSC: signature-based secure boot using LMS/XMSS available from some vendors; PKI, IoT and ICS protocols will follow more slowly [published, M01].
- Academic: Wagner et al. present HW/SW co-design supporting LMS, XMSS and SPHINCS+ for embedded secure boot (abstract only, no figures retrieved) [published, M18].
- SUIT: draft-ietf-suit-mti-18 (June 2025) lists HSS-LMS as the only post-quantum profile ("future", recipients RECOMMENDED) and recommends taller trees for long-lived IoT [published, M33]. ML-DSA not in this revision; later revisions not checked (IN FLUX).

## 3. Hybrids and government stances

Terminology: RFC 9794 (June 2025, Informational) defines PQ/T hybrid, composite vs non-composite [published, M32].
- IETF TLS: hybrid groups X25519MLKEM768 (recommended), SecP256r1MLKEM768, SecP384r1MLKEM1024 with listed share sizes. Datatracker now shows RFC 10024, Proposed Standard, Aug 2026 [published as summarised from M14; verify RFC number on rfc-editor.org].
- IETF LAMPS composite ML-DSA: draft -19 (Apr 2026) in RFC Editor queue at fetch; one key, one signature; EUF-CMA but not SUF-CMA; cites BSI/ANSSI preference for hybrids as rationale [published, M15]. IN FLUX until RFC issued.
- NIST: IR 8547 draft says hybrids typically expected to be temporary, add complexity; plans to allow FIPS 203 secrets as a component in SP 800-56C and to accommodate dual/composite signatures in FIPS 140 validation [published, M11]. CSWP 39: hybrids may need two public keys, add complexity, may force a second transition [published, M02].
- NSA: hybrid not required; non-standardised hybrids not to be used on NSS mission systems; complexity warning [published, M07].
- NCSC UK: notes browsers use hybrid ML-KEM; exact mechanism not standardised industry-wide [published, M01]. Secondary claim "recommends hybrid where possible, no mandate" (M37) is not verified from primary.
- ANSSI/BSI: joint statement (30 Nov 2024) calls it urgent to deploy hybrid solutions [published, M08]. ANSSI follow-up paper full text not obtained; secondary says strongly recommends hybrid for products protecting data beyond 2030, including signatures (M36). BSI: secondary sources conflict - M37 says hybrid mandated, M35 (self-corrected 2026-10-10) says recommended, not mandated, and reports year-end 2030/2031/2035 milestones. BSI primary (TR-02102-1) NOT retrieved. IN FLUX; treat all BSI specifics as unverified.
- EU roadmap deck: hybrid "as long as one scheme is secure"; contributor note that Germany requires lattice signatures combined with classical ones (slide remark, unverified) [M05].
- Dual-signature secure boot: PQUIP constrained draft favours non-composite hybrid signatures for simplicity with existing update architectures [published, M19]. No retrieved MCU-class benchmarks of hybrid boot.
- ETSI TR 104 016: backwards-compatible hybrids can allow downgrade and are probably not an acceptable end state [published, M26].

## 4. Crypto-agility and inventories

- CSWP 39: asset-focused inventory (code, libraries, hardware, firmware, protocols), algorithm identifiers with integrity-protected negotiation, algorithm-agnostic APIs, modular crypto components, compensating controls for legacy [published, M02] (re-check against upd1, IN FLUX).
- CISA discovery/inventory strategy (Aug 2024, FCEB scope): prioritises data sensitive in 2035 and PKI; embedded crypto may not be discoverable by automated tools, so vendor information and manual tracking needed; no OT/IoT mention [published, M16].
- CISA/NSA/NIST factsheet: roadmap, inventory, supply chain, vendor engagement [published, M34]; date not shown on page.
- CBOM: CycloneDX (ECMA-424) lists CBOM among supported BOM types [published, M17]; version introducing crypto assets not confirmed.
- ETSI TR 104 016: repeatable inventory-dependency-risk-plan framework; keys embedded in hardware harder to migrate [published, M26]. Fetch truncated.
- UAE: vendor blog reports National Encryption Policy requiring government roadmaps, crypto-agile new systems, automated crypto discovery and focus on 10-20 year confidentiality data; no deadlines given [M28, vendor secondary, policy text not retrieved].

## 5. HNDL framing

- Mosca inequality: X (shelf life) + Y (migration time) > Z (time to CRQC) means trouble; secondary explainer [M23]. Primary paper not retrieved.
- HNDL concerns captured ciphertext, i.e. confidentiality. NIST IR 8547 says authentication may continue with quantum-vulnerable algorithms until a capable quantum computer exists [published, M11 sec 3.1.2]; NCSC says integrity likely critical for ICS even where confidentiality needs are lower [M01]. For firmware signing the risk is future forgery on devices that outlive classical roots and cannot be updated, not retroactive decryption [derived from M11 sec 3.1.1, M07]. Hence signing migration is driven by device lifetime, key-exchange migration by data shelf life.
- Telemetry examples [derived]: short-lived control telemetry (minutes-days) low HNDL value; flight logs, infrastructure survey data, health, location traces, credential/key material transported over the link may need 10+ years. UAE policy (M28) cites 10-20 year confidentiality data. CISA names data sensitive in 2035 [M16].
- Timelines: NIST deprecate after 2030 / disallow after 2035 (draft) [M11]; CNSA 2.0 dates [M07]; NCSC 2028/2031/2035 [M01]; EU 2026/2030/2035 [M05].

## 6. Side-channel and fault considerations (high level; published surveys only)

- Ravi, Chattopadhyay, D'Anvers, Baksi, ACM TECS 2024: survey of side-channel and fault attacks on Kyber and Dilithium, with countermeasures implemented in pqm4 (Cortex-M4) and liboqs; argues for custom countermeasures alongside masking [published, M24; abstract only, overheads not retrieved].
- Olaluwe et al. 2025 preprint: survey of side-channel attacks on PQC incl. ML-based profiling; no fault coverage [M22].
- Student overview of Kyber attacks: masking can cost roughly 2-3.5x in one cited case; shuffling, constant-time design, noise; fault countermeasures slow attacks without fully stopping them [M25; low-weight source].
- Individual papers show the threat class is real on Cortex-M targets: blind side-channel on Kyber on pqm4 [M20]; correction fault attacks on randomized Dilithium incl. bypass of shuffling and sign-then-verify, tested with clock glitches on an ARM MCU [M21]. Not a survey; recorded only as evidence of risk.
- PQUIP guidance: use hedged signing where side channels are a concern; seeds are critical parameters; erase ephemeral material [M19]. TF-M BL1 includes FI/DPA countermeasures in boot [M30].
- Interpretation [derived]: verification-only firmware checks hold no secret, so side-channel exposure is lower than for ML-KEM decapsulation or signing on-device; fault attacks on the verification result (skipping checks) remain a boot-security issue. Masked implementations carry substantial cost; no MCU overhead numbers retrieved here.

## 7. Case studies and sector guidance

- Automotive: ePrint 2026/2149 benchmarks PQC in TLS (Raspberry Pi 4B as ECU stand-in); concludes legacy 32-bit chips without accelerators are limited; compact signatures suggested for boot [published abstract, M27]. A Raspberry Pi is not MCU-class; comparability warning.
- UAV: IEEE OJ-COMS 2024 review; qualitative; suggests pilot tests, hybrid for non-critical traffic first; no MCU evaluation; internal inconsistency on overhead noted [M29].
- ICS/OT: NCSC ICS section [M01]; EU deck on OT [M05]. IEC 62443-specific PQC paper search returned candidates (TU Darmstadt thesis, vendor articles) but none retrieved.
- Telecom/satellite: GSMA PQ.03 and ESA/satellite documents were found in search but not fetched. Gap.
- Vendors: wolfBoot 2.0.0 (Nov 2023) claims LMS/XMSS firmware verification [M31, vendor].

## Gaps / inaccessible
NSA CNSA 2.0 algorithms advisory (May 2025 PDF), csrc CSWP 39 final page: fetch blocked (permission). ANSSI full PDF and BSI TR-02102-1: not obtained. Microchip body, GSMA PQ.03, ETSI TR 103 619, satellite and IEC 62443 papers: not read. No secure-element/HSM primary data. No MCU overhead figures for hybrids or masking.
