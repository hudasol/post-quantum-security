<!-- Raw notes from the second run (phase 1), retrieved 2026-10-11. Kept unedited except this line and the path mentions. Not independently verified except where data/crosscheck says so. -->
# Protocol-level cost of PQC on constrained devices and links

Retrieval date for all sources: 2026-10-11. Source IDs (P01..P48) are in `./data/sources_protocols.csv`; every numeric claim below maps to a row in `./data/evidence_protocols.csv` (IDs E001..E106). Labels: `published` = figure appears in the retrieved source; `derived-from-published` = my arithmetic, formula shown. No `host-measured` values were produced in this pass.

## 0. Reading guide and comparability warnings (apply to everything below)

1. Mixed device classes. Rows span Cortex-M0+ (NXP KL26, RP2040), Cortex-M4 (nRF52840), Xtensa/RISC-V WiFi SoCs (ESP32, ESP32-S3, ESP32-C5), and x86 lab hosts. Timings, RAM and energy from these are NOT comparable with each other.
2. Several "measured" figures are vendor blog posts (wolfSSL, Espressif) with no stated compiler, flags or library commit. They fail the strict inclusion rule about stating compiler/library version and are marked as vendor claims in the CSV. Treat as indicative.
3. Handshake byte counts come from three different regimes: protocol-spec share sizes (exact), lab TLS stacks on x86 (OpenSSL/oqsprovider), and slide-deck proposals (PQ-EDHOC). They differ in what headers/credentials they count.
4. Frame-count figures I derived (802.15.4, LoRaWAN) are LOWER BOUNDS: payload bytes divided by link payload, ignoring IP/UDP/DTLS/6LoWPAN-fragment/SCHC headers, link-layer security, duty cycle and retransmission.
5. Draft status moves fast. As of 2026-10-11: ML-DSA in COSE is RFC 9964 (May 2026); HSS/LMS in COSE is RFC 8778 (2020); the hybrid ECDHE-MLKEM TLS draft is still an Internet-Draft (-05, 26 May 2026); ML-DSA in TLS 1.3 is draft-ietf-tls-mldsa-05; Merkle Tree Certificates is draft-ietf-plants-merkle-tree-certs-07 (7 Oct 2026). I did not verify RFC publication status beyond the pages I fetched.

## 1. TLS 1.3 / DTLS 1.3 handshake size

Published key-share sizes (draft-ietf-tls-ecdhe-mlkem-05, P01):

| Group | Client share | Server share |
|---|---|---|
| X25519MLKEM768 (codepoint 4588 / 0x11EC, DTLS-OK=Y, Recommended=Y) | 1216 B (1184 ML-KEM ek + 32) | 1120 B (1088 ML-KEM ct + 32) |
| SecP256r1MLKEM768 | 1249 B | 1153 B |
| SecP384r1MLKEM1024 | 1665 B | 1665 B |

Derived (formula: 1216 + 1120): 2336 B of key-share data for X25519MLKEM768 versus 64 B for X25519 alone, i.e. +2272 B before any certificate (E003). Chrome's reported extra bytes (about 1.1 kB server-to-client, 1.2 kB client-to-server, 4% handshake-time regression on the open Internet) match these deltas (P21, relayed second-hand).

An individual draft, draft-rosomakho-tls-ecdhe-mlkem512-01 (P41), proposes MLKEM512X25519 (0x11EA) and SecP256r1MLKEM512 (0x11E9), explicitly aimed at ClientHello size, fragmentation risk and constrained devices. It is non-WG and Recommended=N; ML-KEM-512 would shrink the client key share by roughly 384 B versus ML-KEM-768 (derived: 1184 - 800), but I did not retrieve a byte count from the draft itself.

Authentication cost dominates once certificates are involved:
- ML-DSA public key / signature sizes (P02): ML-DSA-44 1312 / 2420 B, ML-DSA-65 1952 / 3309 B, ML-DSA-87 2592 / 4627 B. TLS codepoints mldsa44/65/87 = 0x0904/05/06 (P15, draft, not yet "Recommended").
- Cloudflare accounting (P20): adding ML-DSA to a Web-PKI-style handshake adds about 14.7 kB (check: 2x1312 + 5x2420 = 14724 B, derived); ML-DSA for the handshake plus Falcon elsewhere about 7.3 kB; SLH-DSA about 39 kB. This models a public-Web chain with SCTs, which an MCU TLS client/server with a single private-PKI certificate would not normally have; treat as an upper-end reference, not an MCU estimate.
- Lab measurement, x86 + OpenSSL 3 + oqsprovider (P16): client-read handshake bytes 14,904 B (X25519, ML-DSA-65 root+leaf), 15,992 B (X25519MLKEM768, same chain), 50,969 B with an SLH-DSA-SHAKE-192s chain. The 1,088 B hybrid delta equals 1120 - 32 from the spec (derived consistency check). Hardware not stated, so I use bytes only, not the paper's timing.
- Internet-scale experiment (P21, relayed): in 2021 Cloudflare saw steeply rising client/middlebox failures beyond about 10 kB added to cert chains and about 15% handshake slowdown under 9 kB. This is not a constrained-link result.

DTLS 1.3 on a real constrained client (P17): ESP32-DevKitC V4 at 240 MHz, Zephyr 4.1.0, wolfSSL 5.8.2, libcoap 4.3.5, over WiFi to a Linux server. The ML-KEM-512 key share exceeded the 1400 B DTLS MTU cap in this build, so the firmware sends an empty first ClientHello to force a HelloRetryRequest (about 18 ms extra round trip) rather than enabling ClientHello fragmentation. Mean handshake + first CoAP request: ML-KEM-512 + ML-DSA-44 225 ms (249 ms with chain verification) versus ECDHE P-256 + ECDSA 479 ms (668 ms with chain verification). Caveats: the authors' ECDSA verify costs about 194 ms on this chip versus about 17 ms for ML-DSA-44, which says more about the ESP32's ECDSA path than about PQ being "faster"; X25519 (819 ms) being slower than P-256 (479 ms) also suggests hardware assistance or an unoptimised path for one curve. Do not read this as "PQ is faster than classical on MCUs" in general. Flash grows from 857 kB to 888 kB and peak heap from 66 kB to 97 kB of a 105 kB Zephyr heap (E-rows for P17).

Memory on ESP32-S3 (vendor article, P24): X25519MLKEM768 + ML-DSA-65 adds about 55.7 KB flash, about +30.5 KB transient handshake heap, and a transient working set of about 59 KB versus about 26 KB classical. Most is ML-DSA-65 verify scratch (about 31 KB) and ML-KEM-768 scratch (about 13 KB). This is the clearest RAM data point I found for a TLS stack; it is a vendor post without compiler details.

Fragmentation mechanics (conceptual): DTLS 1.3 fragments handshake messages and uses HelloRetryRequest/cookies (RFC 9147, P40). A draft on security of fragmenting PQC key material over 6LoWPAN/SCHC exists (P43, individual, low maturity).

## 2. Constrained links

- IEEE 802.15.4 / 6LoWPAN (RFC 4944, P11): 127-octet PHY packet, up to 25 octets frame overhead, so at most 102 octets MAC payload before link-layer security. Derived lower bounds (ceil(size/102)): ML-KEM-512 ek 800 B -> 8 frames; ML-KEM-768 ek 1184 B -> 12; ML-DSA-44 signature -> 24; ML-DSA-65 signature -> 33.
- LoRaWAN: RFC 8376 (P12, 2018) lists EU868 frame sizes 59-250 octets and US915 19-250, with up to 1% duty cycle in some bands. RFC 9011 (P13) uses 51-, 11- and 242-byte MTU examples. Derived lower bounds: ML-DSA-44 signature needs at least 48 uplinks at 51 B or 10 at 242 B; ML-KEM-512 ek at least 16 at 51 B. I could NOT retrieve the current LoRaWAN Regional Parameters payload table (the TTN page rendered without it), so current maxima per data rate are unverified. A LoRa Alliance talk (lpwan25) shows ECDH-based root-key agreement only; no PQ numbers.
- NB-IoT: RFC 8376 states 1600 B MTU (PDCP) with RLC segmentation, so single keys/signatures fit one SDU. An analytical model (P19, not measurement) assumes 200 B packets with 80 B overhead and estimates 46 packets and 10,688 mJ for an ML-DSA-44 + ML-KEM-512 certificate handshake versus 256 mJ for a P-256 ECDSA handshake; ML-DSA-87 + ML-KEM-1024 20,416 mJ. Model assumptions (1.25x protocol factor, 6x weak-signal factor, Cortex-M33 133 MHz) are the authors'.
- BLE (P18, measured on nRF52840 with PPK2, PQClean ML-KEM, Zephyr): communication is 57-63% of PQ key-establishment energy at small link-layer PDU sizes and 37% for ML-KEM-1024 once Data Length Extension is on; DLE cuts total PQKE energy by 25-34%. Table cells were not extractable, so only headline percentages are recorded.

## 3. CoAP / OSCORE / EDHOC

- Classical EDHOC baseline (RFC 9528, P10): total 101 B (static DH, kid) to 242 B (signature keys, x5t).
- PQ-EDHOC via PQ signatures: draft-spm-lake-pqsuites-01 (P06) defines suites with ML-KEM-512 + ML-DSA-44 (KEM ciphertext 768/1088/1568 B). Slide-deck byte analysis (P08, Papon & Onete) gives totals of 4794 / 7216 / 7224 / 5580 / 7984 B for five variants (assumes 8 B tags/MAC and 4-14 B kid credentials; the column-to-variant mapping is not explicit). Derived ratio of the cheapest PQ variant to RFC 9528 signature+kid: 4794 / 216 = 22.2x (cross-source, indicative only). Fraile et al. report about sevenfold message growth for a hybrid ML-KEM-512 EDHOC on Cortex-M4 (P36, abstract only).
- KEM-based authentication (draft-pocero-authkem-edhoc, adopted as draft-ietf-lake-authkem-edhoc per IETF 126 slides, P07, P09): removes signatures for one or both parties; the draft itself says PQ messages may need CoAP Block-wise fragmentation. IETF 126 hackathon (P09): both signature (method 0) and KEM (method 5) PQ-EDHOC ran on nRF52840 (Cortex-M4, pqm4 stack-optimised code); KEM-based authentication was faster on real boards and under 20% emulated loss versus ML-DSA, similar to Falcon. Results are charts only; no numbers extracted.
- Group OSCORE with PQ KEMs: draft-tiloca-core-group-oscore-kem-00 (P42), individual draft, no sizes read.
- MQTT-over-PQ-TLS: I found no peer-reviewed measurement of MQTT over PQ TLS on an MCU. A 2026 arXiv scoring paper (arXiv:2601.13423) came up in search but I did not extract usable numbers; recorded as a gap.

## 4. Secure boot and OTA signing

- Hash-based: wolfBoot on an NXP KL26 (Cortex-M0+ 48 MHz, 16 KB SRAM; P22): LMS L=1,H=20,W=8 signature 1776 B (H=10: 1456 B), bootloader code 14.9 KB versus 24.3 KB for ECDSA P-256, peak stack 1.4 KB versus 6.4 KB, static RAM 4.3 KB versus 1.3 KB. My arithmetic reproduces the sizes: single-level LMS sig = 4 + 1124 + 4 + 32h (RFC 8554), +4 B for the HSS level count gives 1776 and 1456 (consistency check; the +4 is my inference). Verify time was not published and H=20 key generation takes "multi-minute" (vendor). Stateful-key management risk is not captured by any size table.
- Lattice-based: Espressif ESP32-C5 prototype (P23): ML-DSA-65 software verify about 68 ms at about 80 MHz bootloader context versus about 7 ms for hardware-accelerated ECDSA; 8 KB flash block for the PQC signature; hybrid ECDSA + ML-DSA-65 design. Hosted on a pull-request preview site.
- MCUboot: the README and docs/design.md I retrieved (P45) contain no mention of LMS, ML-DSA or PQC. I could not search its issues/PRs (GitHub search API blocked), so "no upstream PQ support" is unconfirmed; treat as a gap, not a finding.
- SUIT/COSE: RFC 8778 (HSS/LMS, COSE alg -46) and RFC 9964 (ML-DSA-44/65/87 = -48/-49/-50; private key is a 32-byte seed only) are published. draft-ietf-suit-mti-23 (P05) defines only an HSS/LMS PQ profile (suit-sha256-hsslms-a256kw-a256ctr); no ML-DSA SUIT profile in the revision I read. CMS also has ML-DSA as RFC 9882 (title read only).
- Academic: Wagner et al. (P34, abstract) show hardware/software co-design for LMS/XMSS/SPHINCS+ secure boot; numbers not retrieved (PDF blocked).

## 5. Certificate-size reduction (conceptual)

- Raw public keys (RFC 7250, P38) remove the chain; certificate compression (RFC 8879, P39) is conceptually weak against high-entropy PQ keys/signatures (my inference; not tested).
- KEMTLS (P32, P33): replaces handshake signatures with KEM authentication. Embedded study on Cortex-M4 with wolfSSL: up to 38% shorter handshake and lower peak memory and traffic, but with pre-standard round-3 schemes (abstract only).
- Merkle Tree Certificates (P14): standalone inclusion proof about 384 B (12 hashes), landmark-relative about 736 B (23 hashes) with no signatures, versus 2420 B for one ML-DSA-44 signature; relying-party state 10,816 B in the draft's example. Requires up-to-date trust state, which is a large operational assumption for offline field devices.

## 6. Hardware and vendor support (claims, no performance numbers)

- STMicroelectronics (P25, P26): X-CUBE-PQC for STM32 with LMS, ML-KEM, ML-DSA, XMSS; hardware IP for secure MCUs. Infineon PSOC Control C3 (P28): LMS firmware verification with SHA-2 acceleration. Microchip MEC175xB (P27): ML-DSA, LMS, ML-KEM in immutable hardware (embedded controllers). TI AM263P4 (P31): no PQC in ROM; PQC secure boot planned for a secondary bootloader. NXP: only a wolfSSL FRDM-MCXN947 demo listing (P48); NXP's own pages not retrieved. Nordic CRACEN/nRF Connect SDK crypto pages blocked (HTTP 403 / Cloudflare challenge).
- Research accelerators: PQCUARK RISC-V ISA extension, up to 10.1x over NIST baseline, 2.3x over optimised software, on an RV64 core (P29, abstract only); Adams Bridge ML-KEM/ML-DSA accelerator at 5 nm (P30). Neither is MCU-class; neither gives MCU cycle counts.

## 7. Takeaways for the review

1. Bytes, not CPU, are the first-order protocol cost on constrained links: X25519MLKEM768 adds about 2.3 kB of key share; one ML-DSA-44 signature alone is 24+ 802.15.4 frames or 48+ LoRaWAN uplinks at 51 B (lower bounds).
2. Authentication (certificates/signatures), not key exchange, dominates handshake bytes (P16, P19, P20).
3. Verification is cheap, signing and RAM are not: ML-DSA verify scratch of about 31 KB (P24) matters more than verify time on 16-KB-SRAM parts; LMS verify is small (1.4 KB stack on M0+) but costs 1.5-1.8 KB per signature and adds state management (P22).
4. Signature-free designs (KEM-authenticated EDHOC, KEMTLS, Merkle Tree Certificates, PSK + ephemeral ML-KEM per P19) are the main protocol-level mitigations; all are drafts or research.
5. Public numbers on Cortex-M with stated clock, library commit and compiler at protocol level are scarce; most are vendor posts or abstracts.

## 8. Gaps and inaccessible sources

- Blocked (HTTP 403 / Cloudflare): Nordic nRF Connect SDK crypto docs and CRACEN pages; eprint.iacr.org PDF downloads (2022/1712, 2022/1198, 2025/2178, 2024/1192, 2026/666); GitHub discussions/search for MCUboot; All About Circuits (Infineon); the SNU Korean paper on PQ-EDHOC under MTU limits (TLS connection reset); ST X-CUBE-PQC product page (HTTP/2 error); NXP PQC blog (404).
- WebFetch tool required per-URL permission that was not granted; all retrieval was done via curl through the sandbox proxy.
- Not verified: current LoRaWAN Regional Parameters maximum payloads; MCUboot PQ roadmap; Zephyr/Mbed TLS PQ status; MQTT-over-PQ-TLS MCU measurements; KEMTLS embedded table numbers; IEEE Access PQ-EDHOC (P35) numeric results; draft-ietf-lake-authkem-edhoc and draft-ietf-lake-pqsuites current versions (only older/individual versions fetched).
- Excluded from the evidence table: wolfSSL LMS/XMSS/SLH-DSA verification table (P44, no device stated); arXiv:2609.21273 (P47, model-derived); arXiv:2607.03988 (Raspberry Pi 5 over 5G, not MCU-class; read abstract only).
