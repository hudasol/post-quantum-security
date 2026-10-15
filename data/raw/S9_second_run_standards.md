<!-- Raw notes from the second run (phase 1), retrieved 2026-10-11. Kept unedited except this line and the path mentions. Not independently verified except where data/crosscheck says so. -->
# Standards status, timelines and government guidance (PQC migration for MCU-class devices)

Retrieval date for every row: 2026-10-11. Source IDs (S01...) refer to ./data/sources_standards.csv.
"In flux?" = Y means the status or dates could plausibly change before a thesis or paper is finalised.
Sources marked SECONDARY were not confirmed against a primary document and should not carry a headline claim alone.

## 1. NIST standards and guidance

| Item | Status | Key dates | Source | Retrieved | In flux? |
|---|---|---|---|---|---|
| FIPS 203 (ML-KEM-512/768/1024) | Final | Published 2024-08-13 (draft 2023-08-24). Planning note 2025-11-17: an issue will be corrected in a future revision; errata spreadsheet lists potential updates | S01 https://csrc.nist.gov/pubs/fips/203/final | 2026-10-11 | Y (revision pending) |
| FIPS 204 (ML-DSA) | Final | Published 2024-08-13. Planning note 2026-07-31: several minor issues to be corrected in a future revision | S02 https://csrc.nist.gov/pubs/fips/204/final | 2026-10-11 | Y (revision pending) |
| FIPS 205 (SLH-DSA) | Final | Published 2024-08-13. Page lists SP 800-230 (draft) as related | S03 https://csrc.nist.gov/pubs/fips/205/final | 2026-10-11 | N (but see SP 800-230) |
| FIPS 206 (FN-DSA / Falcon) | Not found as a published draft or final. NIST project pages (updated 2026-08-05) say Falcon is selected and FIPS 206 is "in development". A guessed CSRC URL for a FIPS 206 draft returned 404 (weak negative evidence) | 2025 NIST talk: initial public draft "basically written, awaiting approval". A secondary vendor page (S53, unverified) says the draft was submitted for approval 2025-08-28 | S08, S09, S13, S18, S53 | 2026-10-11 | Y |
| HQC (KEM) | Selected 2025-03-11. A NIST presentation titled "FIPS 207: HQC-KEM" is dated 2025-09-25. I could not confirm that a draft FIPS has been published | NIST said (March 2025) it would draft the standard, take comment, and finalise in roughly two years | S10, S11, S12, S18 | 2026-10-11 | Y |
| SP 800-208 (LMS/HSS, XMSS/XMSS-MT) | Final | Draft 2019-12-11; final 2020-10-29. No revision found | S06 https://csrc.nist.gov/pubs/sp/800/208/final | 2026-10-11 | N |
| SP 800-227 (KEM recommendations) | Final | Draft 2025-01-07; final 2025-09-18. NIST slides say it contains some hybrid key-establishment guidance and NIST does not intend to recommend for or against hybrids | S07, S14 | 2026-10-11 | N |
| NIST IR 8547 (transition) | Only the initial public draft was found on CSRC | IPD 2024-11-12; comments closed 2025-01-10. Draft table: RSA and ECDSA at 112-bit strength deprecated after 2030 and disallowed after 2035; 128-bit and above (RSA, ECDSA, EdDSA, DH/ECDH) disallowed after 2035. NSM-10 target of 2035 quoted. CSRC PQC page (updated 2026-08-05) still cites the IR 8547 timeline | S04, S05, S08 | 2026-10-11 | Y (draft; final may change dates) |
| SP 800-230 ipd (extra SLH-DSA parameter sets for limited-signature use) | Initial public draft | Published 2026-04-13; comments closed 2026-06-12. Six parameter sets, levels 1/3/5, capped at 2^24 signatures per key, aimed at software, firmware and certificate signing; not for general use | S15 https://csrc.nist.gov/pubs/sp/800/230/ipd | 2026-10-11 | Y |
| NIST additional signatures on-ramp | Round 3 | Round 3 announced 2026-05-14 with 9 candidates; round-2 report is IR 8610 | S16, S17 | 2026-10-11 | Y |

Notes
- NIST IR 8547 values above come from the November 2024 draft PDF. If the final is published, dates must be rechecked.
- The NIST "MPTS 2026" Moody slide deck (S14) has inconsistent internal dates (cover 2023, footer March 2025). I used it only for NIST's hybrid stance. It lists LMS and XMSS among PQC standards in the IR 8547 summary.
- Parameter names used here follow the FIPS (ML-KEM-512/768/1024), not round-3 Kyber names.

## 2. IETF status

Status is from the RFC Editor index and datatracker pages. Draft-to-RFC mappings were confirmed on each datatracker page.

| Item | Status | Key dates | Source | Retrieved | In flux? |
|---|---|---|---|---|---|
| RFC 8554 (LMS) | Published, Informational (CFRG) | April 2019 | S19 | 2026-10-11 | N |
| RFC 8391 (XMSS) | Published, Informational | May 2018 | S19 | 2026-10-11 | N |
| RFC 9858 (extra HSS/LMS parameter sets, smaller signatures) | Published, Informational (IRTF) | October 2025 | S21 | 2026-10-11 | N |
| RFC 9708 (HSS/LMS in CMS; obsoletes RFC 8708) | Published, Proposed Standard | January 2025 | S19 | 2026-10-11 | N |
| RFC 8778 (HSS/LMS in COSE) | Published, Proposed Standard | April 2020 | S19 | 2026-10-11 | N |
| RFC 9802 (HSS and XMSS in X.509) | Published, Proposed Standard | June 2025 | S19 | 2026-10-11 | N |
| RFC 9881 (ML-DSA in X.509 / algorithm identifiers) | Published, Proposed Standard (was draft-ietf-lamps-dilithium-certificates) | October 2025 | S19, S29 | 2026-10-11 | N |
| RFC 9882 (ML-DSA in CMS) | Published, Proposed Standard | October 2025 | S19, S29 | 2026-10-11 | N |
| RFC 9935 (ML-KEM in X.509) | Published, Proposed Standard | March 2026 | S19, S29 | 2026-10-11 | N |
| RFC 9936 (ML-KEM in CMS) | Published, Proposed Standard | March 2026 | S19, S29 | 2026-10-11 | N |
| RFC 9909 (SLH-DSA in X.509) | Published, Proposed Standard | December 2025 | S19, S29 | 2026-10-11 | N |
| RFC 9814 (SLH-DSA in CMS) | Published, Proposed Standard | July 2025 | S19, S29 | 2026-10-11 | N |
| RFC 9964 (ML-DSA in JOSE and COSE) | Published, Proposed Standard (was draft-ietf-cose-dilithium) | May 2026 | S19, S29 | 2026-10-11 | N |
| RFC 10024 (hybrid key agreement in TLS 1.3: X25519MLKEM768, SecP256r1MLKEM768, SecP384r1MLKEM1024) | Published, Standards Track (was draft-ietf-tls-ecdhe-mlkem) | August 2026 | S20 | 2026-10-11 | N |
| RFC 9954 (Hybrid key exchange framework in TLS 1.3) | Published, Informational | July 2026 | S19 | 2026-10-11 | N |
| RFC 9794 (PQ/T hybrid terminology) | Published, Informational | June 2025 | S19 | 2026-10-11 | N |
| RFC 9958 (PQC for Engineers) | Published, Informational | June 2026 | S19, S29 | 2026-10-11 | N |
| RFC 10042 (hybrid ML-KEM key exchange in SSH) | Published, Informational | August 2026 | S19 | 2026-10-11 | N |
| draft-ietf-tls-mlkem (pure ML-KEM in TLS 1.3) | Active Internet-Draft, intended Informational, rev 11 | Updated 2026-10-05 | S22 | 2026-10-11 | Y |
| draft-ietf-tls-mldsa (ML-DSA in TLS 1.3) | Active Internet-Draft, intended Informational, rev 06 | Updated 2026-10-05 | S23 | 2026-10-11 | Y |
| draft-ietf-cose-sphincs-plus (SLH-DSA in JOSE/COSE) | Active Internet-Draft, Proposed Standard intended, rev 10 | Updated 2026-08-24 | S24 | 2026-10-11 | Y |
| draft-ietf-cose-falcon (FN-DSA in JOSE/COSE) | Expired, rev 04 | Last revised 2026-09-16 | S25 | 2026-10-11 | Y |
| draft-ietf-lamps-fn-dsa-certificates and cms-fn-dsa | Active, rev 00 | May 2026; depend on FIPS 206 | S26 | 2026-10-11 | Y |
| draft-ietf-lamps-pq-composite-sigs (rev 19) and -kem (rev 22) | Active, Proposed Standard intended | Updated 2026-10-02 and 2026-10-10 | S27, S30 | 2026-10-11 | Y |
| draft-ietf-uta-pqc-app (PQC recommendations for TLS-based applications) | Active, rev 03 | Updated 2026-07-04 | S28 | 2026-10-11 | Y |

I did not retrieve datatracker status for CoAP, OSCORE, EDHOC or DTLS-specific PQC drafts. That gap belongs to the protocol-cost subagent or a follow-up search.

## 3. Government migration guidance

| Item | Status | Key dates | Source | Retrieved | In flux? |
|---|---|---|---|---|---|
| NSA CNSA 2.0 (SECONDARY ONLY) | NSA documents were not accessible (HTTP 403). The following comes from a single blog summarising FAQ v2.1 | Software and firmware signing: support and prefer by 2025, exclusive use by 2030. Networking equipment: prefer 2026, exclusive 2030. Web, cloud, OS: exclusive by 2033. Niche and constrained equipment: prefer by 2030, exclusive 2033. Procurement gate 2027-01-01. Algorithms: ML-KEM-1024, ML-DSA-87; LMS and XMSS single-tree only for firmware (no HSS multi-tree); SLH-DSA not approved; FN-DSA not planned. Blog is dated 2024-12-29; newer NSA versions may exist (a May 2025 advisory URL exists but was not readable) | S40, S51 | 2026-10-11 | Y |
| CISA PQC product categories list | Not retrieved (HTTP 403). Existence of a January 2026 publication inferred from search titles only. No content used | n/a | S52 | 2026-10-11 | Y |
| UK NCSC | Published | Guidance v1.0 dated 2025-03-20. Milestones: by 2028 define goals, discover estate, initial plan; by 2031 early priority migration and refined roadmap; by 2035 complete migration. Names IoT/ICS and in-field sensors in scope and notes constrained, non-upgradeable devices are hard. Says some rarely used technologies may miss 2035 | S31 | 2026-10-11 | N |
| EU coordinated roadmap | Published by Member States with the Commission | 2025-06-23. Start by end of 2026; critical infrastructure by end of 2030 (EC page). The 2035 target appears via BSI's reference to the EU roadmap, not on the EC page I read. Roadmap PDF body was not read. Survey feedback posted 2026-09-02. Earlier 2024-04-11 Recommendation encourages hybrid schemes | S32, S33, S34, S35 | 2026-10-11 | Y |
| Germany BSI TR-02102-1 v2026-01 (PRIMARY) | Current | As of 2026-01-23. Recommends PQ mechanisms only in hybrid form. Classical key agreement alone recommended until end 2031 (end 2030 for very high protection needs); classical signatures until end 2035. Accepts ML-KEM, FrodoKEM, Classic McEliece; intends to add HQC after its standard. Signatures: ML-DSA and SLH-DSA (hedged), plus LMS/HSS and XMSS/XMSS-MT only where state management can be guaranteed, with firmware and software update signing named as such a case. Strongly recommends products with lifetime beyond 2030 get a PQ upgrade path including firmware-update signature verification. Joint statement with 17 other European states, Nov 2024 | S35, S36 | 2026-10-11 | Y |
| France ANSSI | 2022 paper (primary) proposed three phases: hybrid defence-in-depth now; hybrid with PQ assurance not earlier than 2025; optional standalone PQC probably not before 2030. 2023-10-11 follow-up paper exists; its content here is from a secondary blog: strongly recommends hybrid for KEMs and signatures for products protecting beyond 2030, accepts ML-KEM and FrodoKEM, ML-DSA and SLH-DSA, and does not promise to match NIST's set exactly | 2022-01-04; 2023-10-11 | S37, S38, S39 | 2026-10-11 | Y |
| UAE: National Encryption Policy and executive regulation (SECONDARY) | Reported approved 2025-11-27 by the UAE Cybersecurity Council. Applies to government entities: approved transition plans from RSA/ECC to PQC, automated crypto inventory, crypto-agility by design, priority for data needing 10 to 20 years of confidentiality. No submission deadline found publicly. Primary WAM article could not be read (JavaScript page) | 2025-11-27 | S46, S47, S50 | 2026-10-11 | Y |
| UAE: national PQC programmes and TII libraries | UAE Cyber Security Council signed an agreement with ATRC entities (VentureOne, TII, QuantumGate) for a national PQC migration plan. TII develops national cryptographic libraries covering classical and PQ algorithms; TII Security Laboratory does compliance testing; UAE National Cryptography Center sets requirements for the Crypto Discovery Tool. Three programmes named (secondary): National Information Assurance Program, National Cybersecurity Index Platform, National Post-Quantum Migration Program | Media-office page undated in text; CyberQ event 2025-11-26/27 (secondary) | S45, S48 | 2026-10-11 | Y |
| UAE: Abu Dhabi government (news) | Abu Dhabi DGE and TII speaking about sovereign, agile encryption and first cryptographic inventories | 2026-10-06 | S49 | 2026-10-11 | Y |
| Saudi NCA National Cryptographic Standards NCS-1:2020 (PRIMARY) | Version 1.0, July 2020. Section 7.2 says no international PQC standards exist yet and PQC will be considered in later versions. Landing page last updated 2025-05-16 and I found no newer NCS version | July 2020 | S42, S43 | 2026-10-11 | Y |
| Qatar, Kuwait, Oman | No national PQC guidance found | n/a | S44 (no Qatar entry) | 2026-10-11 | n/a |
| Bahrain | Search results only (not fetched): a government partnership with SandboxAQ announced December 2025. Not guidance | Dec 2025 | none retrieved | 2026-10-11 | n/a |
| UAE Central Bank (CBUAE), TDRA, DESC | No PQC-specific guidance found | n/a | none | 2026-10-11 | n/a |

### Gulf search log (so the negative result is auditable)
Queries run: "UAE Cyber Security Council post-quantum cryptography national policy guidance"; "Saudi National Cybersecurity Authority NCA post-quantum cryptography standard migration"; "TII Abu Dhabi OR Central Bank of the UAE OR TDRA OR Dubai Electronic Security Center post-quantum cryptography migration roadmap 2030"; "Qatar National Cyber Security Agency post-quantum cryptography guidance OR Bahrain OR Oman OR Kuwait quantum-safe"; "Central Bank of the UAE CBUAE quantum post-quantum cryptography guidance financial institutions"; "Saudi Arabia NCA post-quantum cryptography national cryptographic standards NCS-1:2020 update quantum-safe roadmap".
Finding: only the UAE has PQC-specific national policy (government entities). I found no UAE or Gulf guidance specific to microcontrollers, IoT, drones or sensors, and no UAE statement on which algorithm parameter sets are mandated or on firmware-signing deadlines. Saudi NCS-1:2020 predates the NIST standards. No Central Bank, TDRA, DESC or Qatar document was found.

## 4. Points that matter for MCU-class migration

1. Firmware signing is the earliest, best-defined target. CNSA 2.0 (secondary source) puts exclusive use by 2030 and prefers single-tree LMS or XMSS; BSI lists LMS/HSS and XMSS for firmware updates provided state is managed safely. This makes LMS/XMSS and, if finalised, SP 800-230 the relevant near-term options for secure boot.
2. FN-DSA is not yet published as a FIPS, so MCU plans that rely on Falcon-class signature sizes cannot cite a final standard. NIST's own 2025 slides stress floating-point use in key generation and signing and say verification needs none.
3. The IETF has a published hybrid TLS 1.3 key agreement (RFC 10024) and published certificate, CMS and COSE profiles for ML-KEM, ML-DSA, SLH-DSA, LMS and XMSS. Pure ML-KEM and ML-DSA in TLS are still drafts. COSE support for SLH-DSA is a draft and for FN-DSA the draft expired.
4. Government positions differ on hybrids: BSI recommends hybrid, ANSSI strongly recommends hybrid (secondary), NIST takes no side, and CNSA 2.0 favours exclusive PQC by its dates. A migration design for deployed devices should record which regime it targets.
5. NCSC explicitly lists field sensors and non-upgradeable devices as a difficult class, which supports planning an upgrade path now.
