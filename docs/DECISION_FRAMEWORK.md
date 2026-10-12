# Decision framework

Tags: **[S1..S5, row]** = from the raw notes in `data/raw/` (each traces to a retrieved URL with retrieval date 2026-10-11); **[evidence S2-xxxx]** = row in `data/evidence.csv`; **[inference]** = my reasoning, not stated by a source. Standards marked *in flux* may have changed since 2026-10-11.

![Decision flowchart](figures/decision_flow.png)

(Source file `figures/decision_flow.dot`, also `decision_flow.svg`.)

## How to use it
Run the flowchart once per asset class, not once per fleet. A drone has at least five: the **firmware trust anchor** (ROM/OTP key and verifier), the **update path** (manifest, signer), the **command link**, the **data links** (video, telemetry, cloud uplink) and the **device identity**. They get different answers.

## The two questions that decide most outcomes
1. **Is the risk retroactive or prospective?** Secrecy has a harvest-now-decrypt-later (HNDL) problem: traffic recorded today can be read later. Authenticity does not: an authentication system stays secure as long as the algorithms and keys are secure when the authentication is performed [S4 A4, IR 8547 ipd 3.1.2]. The authenticity risk is *forgery after a break*, so it matters for keys that stay trusted for a long time, above all verification keys frozen in silicon [S4 A2 CSWP 39 s4.5; A8 RFC 9019; A5 SP 800-208 s1.1].
2. **Can the verifier be changed after shipping?** If the boot ROM or fused/OTP-hashed key and algorithm cannot be updated, the scheme there must stay secure for the device's whole life [S4 CSWP 39 s4.5], and NIST's draft IR 8547 says such devices should be designed to require quantum resistant signatures if they might still be in use when a cryptographically relevant quantum computer exists (draft, in flux) [S4 A4 s3.1.1].

## Choosing a firmware signature scheme (verify only device)

Sizes are standard values [evidence S2-0405..0413, S3-036..044]; cycle counts are *published, different setups, not comparable across rows* [evidence S2-0033, S2-0057, S2-0060, S2-0316, S2-0319]. Treat the cycle column as orientation, not a ranking.

| Criterion | LMS/HSS (SP 800-208) | XMSS/XMSS^MT (SP 800-208) | ML-DSA (FIPS 204) | SLH-DSA (FIPS 205) |
|---|---|---|---|---|
| State on signer | **Stateful**: signing a one time key twice allows forgery; key and signature generation only in FIPS 140 Level 3+ hardware modules per SP 800-208 s8.1 [S1 row 12, 13] | same | none | none |
| Signature size (bytes) | 1452 (1-level H10/W8, computed from RFC 8554 formula [S3 8.3]); 2644 (2-level H5/W8, wolfBoot docs) | 2500 (XMSS-SHA2_10_256, wolfBoot docs) | 2420 / 3309 / 4627 (-44/-65/-87) | 7856 (128s), 17088 (128f), 49856 (256f) |
| Public key | 56 B per LMS key (computed) | per RFC 8391 | 1312 / 1952 / 2592 | small (FIPS 205 Table 2) |
| Published verify cost on Cortex-M4 (setups differ) | 2,576,515 cycles LMS h5 SHA-256 (slides, S2-0316); 2,650,000 h10 (S2-0319) | 13,070,000 XMSS ROBUST h10 (S2-0322, slides) | 1,421,623 ML-DSA-44 (pqm4 m4f, mean, 24 MHz-labelled; S2-0033) | 7,471,794 for round-3 SPHINCS+ SHA2-128s-simple, **not final SLH-DSA** (S2-0060) |
| Standards / ecosystem | RFC 8554; COSE -46 (RFC 8778); SUIT MTI draft recommends an HSS/LMS profile (in flux) [S3 4.6]; TF-M BL1 uses LMS; wolfBoot, Mbed TLS (verify) | RFC 8391; wolfBoot | RFC 9964 gives COSE -48/-49/-50, **but the SUIT MTI draft -23 has no ML-DSA profile** [S3 4.6]; wolfBoot supports it | draft SP 800-230 (2026-04, in flux) proposes 2^24-signature variants for firmware; wolfCrypt, slhdsa-c (work in progress) |
| Hardware/ROM claims (vendor, unverified) | Infineon PSOC Control C3 LMS verify; Microchip MEC175xB | -- | Microchip MEC175xB ML-DSA | -- |
| Best when | one release authority with an HSM; long lived ROM-adjacent verifier; smallest code and signature | like LMS | many signers or no HSM state discipline; moderate sizes | most conservative assumption; can tolerate large signatures |

[inference] For a fleet whose releases come from one build pipeline, LMS/HSS fits best because the state problem sits in the vendor's HSM, not on the airframe. ML-DSA fits where stateful discipline cannot be guaranteed. SLH-DSA is the conservative stateless choice but the heaviest on bytes (and, from the round-3 rows, on cycles).

## Hybrid (dual) signatures: do it with two signatures, not one composite
NIST leaves hybrid use to each application and will accommodate hybrids in FIPS 140 validation [S1 row 20]; BSI and ANSSI favour hybrids, ASD does not recommend them [S1 rows 43, 47, 51]. For firmware, the IETF constrained device draft says carrying two separate signatures is simple and fits current secure boot designs, while overall cost stays dominated by the PQ part [S3 5.2; in flux]. wolfBoot implements it (sequential verification, larger headers) [S3 4.2]. Rule: accept an image only if **both** verify, so authenticity holds while either holds. NIST expects hybrids to be temporary, implying a second transition [S4 IR 8547 3.2].

## Link and command authentication
- MAVLink 2 signing is a 13-byte field holding a 6-byte truncated SHA-256 tag over a 32-byte shared key [S3 1.1]; an ML-DSA-44 signature is 2420 bytes, i.e. 10 full 255-byte payloads [S3 8.1, derived]. So per message PQ signatures are not feasible; the design space is a PQ/hybrid *session setup* plus a short symmetric tag per message [inference, consistent with a community proposal S3 1.4]. A shared symmetric key is not directly broken by Shor's algorithm [inference]; what is exposed is how the key reaches the vehicle (manual, over USB/wired link per the guide) and any public key step in provisioning.
- ROS 2 / DDS-Security 1.2 specifies RSA/ECDSA/ECDH and AES-GCM only; no PQC [S3 3.1]. Research forks exist (PQSec-DDS, a Dilithium3 SROS2 fork) without benchmarks [S3 3.4]. [inference] Until the spec changes, protect the robot-to-ground path with a hybrid TLS/IPsec tunnel at the gateway, and keep DDS-Security inside.

## What can be done by firmware update vs what needs hardware [inference, built on sourced constraints]
| By firmware update (if flash/RAM headroom and an updatable bootloader) | Likely needs hardware change or a gateway |
|---|---|
| Hybrid KEM in the application link layer | Boot ROM / fused key hash with classical only algorithm and nothing updatable before it |
| PQ verifier in an updatable second stage bootloader (wolfBoot-class); dual manifest signatures | Secure elements with a fixed algorithm set |
| Larger headers and certificate chains | Units with no flash headroom: published PQ code is 8-25 kB flash for ML-DSA [S2-0031..0036] and a 5 kB image header for LMS/ML-DSA in wolfBoot examples [S3 4.2] |
Worked example of the pattern: Caliptra 1.3 adds a software only ML-DSA-87 identity chain via runtime firmware without ROM changes, but the ROM-rooted classical chain remains and the PQ chain does not attest the ROM [S4 A19]. Not a drone part; shows what a firmware only fix can and cannot cover.
