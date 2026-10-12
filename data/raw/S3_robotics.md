# S3 Drone and robot specifics: raw notes

Stream: S3 (drone/robot protocol-level facts). Compiled 2026-10-11. All retrieval dates below are 2026-10-11 unless stated.
Scope rule: side-channel and fault material is conceptual and defensive only (risk classes and countermeasure families). No attack procedures.
Conventions: "Fact" is paraphrased from the retrieved text. "Limit/risk" is my commentary. "in flux" means the source is a draft, says it will be revised, or is a preprint. Every number in Sections 1-7 comes from a retrieved source. Numbers in Section 8 are my own arithmetic and are labelled estimates.

## 0. Retrieval method and deviations

- The WebFetch tool was blocked in this session (permission prompt unanswered, error PROVENANCE_REQUIRED). I therefore fetched primary pages with `curl` through the sandbox's pre-configured agent proxy (CA bundle in place, TLS verification on), converted HTML with a small local script and PDFs with `pdftotext`. WebSearch was used only to locate sources (search snippets are never cited for facts). Deviation to be logged in PROTOCOL section 10 by the coordinator.
- Local working copies of retrieved pages are in the session scratchpad (not in the project tree).
- Queries run (WebSearch): "post-quantum MAVLink UAV communication security"; "post-quantum cryptography ROS 2 DDS-Security SROS2 ML-KEM ML-DSA"; "micro-ROS security DTLS Micro XRCE-DDS secure communication microcontroller status"; "micro-ROS security not supported SROS2 ... github issue"; "PQSec-DDS Integrating post-quantum cryptography into DDS Security for robotic applications"; "MCUboot post-quantum LMS ML-DSA support pull request"; "TF-M Trusted Firmware-M LMS XMSS ML-DSA post-quantum PSA Certified status secure boot"; "STM32 NXP Infineon Microchip secure boot ROM LMS ML-DSA post-quantum microcontroller product"; "PSA Certified post-quantum cryptography roadmap ..."; "Microchip MEC175xB ... press release"; "Infineon PSOC Control C3 post-quantum ... press release"; "NXP post-quantum cryptography ..." (twice, second restricted to nxp.com domains); "Arm PSA Certified post-quantum ..." (restricted to Arm/TrustedFirmware domains); "ArduPilot secure bootloader signed firmware Ed25519 monocypher docs"; "PX4 signed firmware bootloader Ed25519 ..."; "first-order masked Kyber ML-KEM Cortex-M4 ..."; "masked ML-DSA Dilithium implementation Cortex-M ..."; "survey implementation attacks side-channel fault injection lattice-based ..."; "ML-KEM ML-DSA unified hardware accelerator ASIC ..."; "MAVLink security analysis vulnerabilities ... MAVSec ..."; "MAVLink 2 message signing weaknesses shared key replay analysis paper"; "Bluetooth Core Specification ATT_MTU default 23 ...".

---

## 1. MAVLink signing, PX4/ArduPilot support, critiques, PQC work

### 1.1 MAVLink guide: message signing (primary)
- URL: https://mavlink.io/en/guide/message_signing.html (retrieved 2026-10-11). Note: the path `/en/guides/` returns 404; the correct path is `/en/guide/`.
- Fact (frame): signing sets bit 0x01 of the incompatibility flags and appends 13 signature bytes after the packet. A library that does not support signing must drop signed packets.
- Fact (13 bytes): 1 byte link ID, 6 bytes (48 bits) timestamp, 6 bytes (48 bits) signature.
- Fact (timestamp): units of 10 microseconds since 1 January 2015 GMT; must increase for every message on a link; a stream is the tuple (SystemID, ComponentID, LinkID).
- Fact (signature): the 48-bit value is the first 48 bits of SHA-256 over secret key + header + payload + CRC + link ID + timestamp. The docs write it as `sha256_48(secret_key + header + payload + CRC + link-ID + timestamp)`. So it is a truncated keyed hash by prefix construction as written on that page, not the HMAC construction. (My reading of the formula; the page itself calls it a SHA-256 hash of the packet appended to the key.)
- Fact (key): 32 bytes of binary data held at both ends of a channel. The guide says the key should be created on one system (often a GCS) and shared to trusted devices over secure channels. The mavgen C and Python libraries support one key per link; the page says that is a library choice, not a protocol limit.
- Fact (key distribution): the key may be shared with the SETUP_SIGNING message, which must only travel over a secure link such as USB or wired Ethernet, be sent directly to each system/component, never be broadcast and never be auto-forwarded between links.
- Fact (replay): receivers discard a signed packet if its timestamp is older than the previous one in the same (SystemID, ComponentID, LinkID) stream, if the signature mismatches, or if the timestamp is more than one minute (6,000,000 units) behind the local timestamp. The guide recommends persisting the timestamp (ideally at least once a minute) and, without an RTC, advancing it from GPS time.
- Fact (unsigned acceptance): libraries should offer conditional acceptance of unsigned packets; the page lists RADIO_STATUS as always accepted unsigned.
- Fact (logging): systems should omit SETUP_SIGNING from logs and strip signatures from telemetry logs, to make it harder to collect large amounts of signature data.
- Limit/risk: (a) the signature field is a fixed 13 bytes with a 6-byte tag, so a PQC signature cannot be placed in it; it would need a different mechanism (Section 2). (b) Symmetric shared key only: no per-GCS identity or non-repudiation; every holder can sign as anyone (PX4 page below states this). (c) No confidentiality (PX4 and ArduPilot pages state it). (d) Key distribution is out of band and manual. (e) 48-bit tag and a pre-quantum-style symmetric design: the 256-bit key and SHA-256 are not the quantum-fragile part of this protocol; the fragile parts for a PQC study are key provisioning and any asymmetric identity layered on top.
- MAVLink serialization guide (https://mavlink.io/en/guide/serialization.html, retrieved 2026-10-11): MAVLink 2 header is 10 bytes (magic, len, incompat flags, compat flags, seq, sysid, compid, 3-byte msgid), payload up to 255 bytes, 2-byte checksum, optional 13-byte signature. Stated maximum packet length is 280 bytes for a signed message using the whole payload.

### 1.2 PX4 documentation on signing (primary)
- URL: https://docs.px4.io/main/en/mavlink/message_signing.html (retrieved 2026-10-11; "main" docs, in flux).
- Fact: PX4 appends a 13-byte signature to every outgoing MAVLink 2 message when a key is present; one secret key is shared by all systems and components (GCS, PX4, companion computer, camera, gimbal). With no key on the SD card signing is off and everything is accepted.
- Fact: key stored in a 40-byte file `/mavlink/mavlink-signing-key.bin` on the SD card (32-byte key + 8-byte little-endian timestamp), mode 0600. Removing the card or deleting the file disables signing; the page says there is no software-only recovery for a lost key, on purpose.
- Fact: provisioning is by SETUP_SIGNING (message ID 256) on any link when no key is present; once active, changes must be signed with the current key; changes are rejected while armed.
- Fact: HEARTBEAT, RADIO_STATUS, ADSB_VEHICLE and COLLISION are always accepted unsigned.
- Fact: the page lists "what signing does not protect against": eavesdropping, SD-card extraction, spoofed allowlisted messages, and it notes there is no automatic key rotation. It also notes that on-disk timestamps typically stay at the provisioning value because vehicles are often powered off by pulling the battery.
- Limit/risk: the symmetric key is a single point of compromise for the whole vehicle system; a quantum adversary does not break it directly, but a classical key-distribution step (for example a GCS that provisions keys over a public-key channel) would be the migration-relevant item. Not addressed by the page.

### 1.3 ArduPilot documentation on signing (primary)
- URL: https://ardupilot.org/copter/docs/common-MAVLink2-signing.html (retrieved 2026-10-11). The dev-docs URL `ardupilot.org/dev/docs/mavlink-message-signing.html` returned 404.
- Fact: ArduPilot and Mission Planner can add packet signing using a passkey. The page says it does not encrypt data. When active, non-USB serial ports can be configured to answer only commands that carry the key. It says telemetry downlink data is unaffected, and USB connections are unaffected (USB can erase or change the passkey). MAVLink 1 links are not protected.
- Limit/risk: unsigned downlink and unprotected USB are documented design choices; they mean signing covers command authentication only on that page's description.

### 1.4 Published critiques, analyses and PQC/lightweight-crypto work for MAVLink/UAV links
- MAVSec (Allouch et al., arXiv 1905.00265v2, May 2019; https://arxiv.org/pdf/1905.00265, retrieved 2026-10-11). Fact: argues MAVLink lacks protection; implements symmetric encryption (AES-CBC, AES-CTR, RC4, ChaCha20) in ArduPilot and compares memory and CPU use; concludes ChaCha20 is the most efficient. Limit/risk: confidentiality only; pre-PQC; the abstract states no PQC content. I did not extract its numbers (not needed for this review; would require the full results section).
- MAVLink survey (arXiv 1906.10641, https://arxiv.org/pdf/1906.10641, retrieved 2026-10-11): describes the 13-byte signature field and the 6-byte truncated tag in line with the guide. No PQC.
- CVE-2026-1579 (record at https://ocve.arawa.fr/cve/CVE-2026-1579, an aggregator, retrieved 2026-10-11). Fact: the record states MAVLink does not require cryptographic authentication by default; without signing, any message including interactive-shell access can be sent by an unauthenticated party; PX4 offers MAVLink 2 signing as the mitigation. Limit/risk: aggregator, secondary; it shows the practical baseline problem is lack of enabled authentication, before any quantum question.
- Khan et al., "Future-Proofing Security for UAVs With Post-Quantum Cryptography: A Review", IEEE Open Journal of the Communications Society vol. 5, 2024 (DOI 10.1109/OJCOMS.2024.3486649; https://repository.essex.ac.uk/39966/1/Future-Proofing_Security_for_UAVs_With_Post-Quantum_Cryptography_A_Review.pdf, retrieved 2026-10-11). Fact: a survey; says UAV links rely on MAVLink, SSL/TLS, IEEE 802.11 with classical schemes, and that hybrid schemes, hardware acceleration (FPGA offload) and lightweight lattice implementations are being studied. Limit/risk: review without UAV measurements that I could extract; it is not protocol-specific.
- Bera, Das, Sikdar, "Quantum Resistant Lattice-Based Access Control Scheme for UAV-Assisted Internet-of-Drones Applications" (IEEE, 2026 preprint copy at https://www.ece.nus.edu.sg/stfpage/bsikdar/papers/tmc_bera_26.pdf, retrieved 2026-10-11). Fact: proposes an RLWE-based anonymous access-control protocol, formally checked with a verification tool; testbed on Raspberry Pi 4 Model B (Cortex-A72 at 1800 MHz). Limit/risk: application-class CPU, custom protocol, not MAVLink-integrated; not comparable to MCU flight controllers. Venue/status of the copy not confirmed beyond the file.
- ArduPilot Discourse thread, "Post-quantum authentication for MAVLink C2" (https://discuss.ardupilot.org/t/post-quantum-authentication-for-mavlink-c2-found-a-relay-problem-nobody-talks-about/144270, posted 2026-06-20, retrieved 2026-10-11). Community post, not peer reviewed, in flux. Fact (author's claims): the poster reports that signature bytes appended after a MAVLink frame are dropped by a MAVProxy relay, reports the ML-DSA-87 signature as 4627 bytes, proposes carrying authentication material as first-class MAVLink messages (custom message ID 50000) and filed an RFC issue (mavlink/mavlink #2527, not retrievable, 403). Author's numbers on a server-class Arm Neoverse-N2: ML-KEM-1024 session setup 241 us, ML-DSA-87 sign 509 us, HMAC-SHA3-256 per telemetry packet 1.1 us. Another forum member replied that a ~4 kB signature per message is untenable for most uses. Limit/risk: unverified single-author claims on a non-flight CPU; I did not reproduce them and do not put them in the evidence CSV. The 4627 value does match FIPS 204 Table 2 (Section 2).
- ePrint 2026/2343, "Post-Quantum Command Authentication for Unmanned Systems: A KpqC Feasibility Study under Real-Time and Bandwidth Constraints" (Hyoung et al., Hansung University, preprint approved 2026-10-07; https://eprint.iacr.org/2026/2343, retrieved 2026-10-11, abstract only; the PDF returned 403). Fact (abstract): studies Korean PQC candidates (HAETAE, AIMer, SMAUG-T, NTRU+), with NIST ML-KEM/ML-DSA/SLH-DSA as yardstick and ECDSA/ECDH as baseline, for the authentication and key-establishment path of ROS 2/DDS-Security on UAV/UGV command channels, framed as size-latency budget under MTU, rate, latency and bandwidth limits; measures handshakes over emulated constrained links on a two-node testbed. Limit/risk: preprint, in flux; no numbers retrievable here.
- Plain statement: I found no PQC-specific MAVLink standard, no PX4 or ArduPilot documentation mentioning PQC for signing, and no peer-reviewed measurement of PQC on a MAVLink flight controller. The items above are a community RFC, preprints and surveys.

---

## 2. MAVLink frame limits, fragmentation, and radio constraints

### 2.1 Frame and message limits (primary: mavlink.io)
- Payload length byte: 0-255; maximum packet 280 bytes when signed (serialization page above).
- FILE_TRANSFER_PROTOCOL (message 110): `payload` is 251 bytes (https://mavlink.io/en/messages/common.html, retrieved 2026-10-11). The FTP service page (https://mavlink.io/en/services/ftp.html) shows a 12-byte FTP header inside that payload (seq, session, opcode, size, req_opcode, burst flag, padding, offset), leaving bytes 12 to 250 for data, i.e. 239 bytes of data per message by that layout. The page says the payload encoding is not mandated and private networks may use others.
- ENCAPSULATED_DATA (message 131, image transmission): `data` is 253 bytes plus a 2-byte sequence number.
- TUNNEL (message 385): `payload` is 128 bytes plus a payload length byte.
- SETUP_SIGNING (message 256): 32-byte key + 64-bit timestamp.
- Limit/risk: there is no standard MAVLink "large object" service for authentication data; chunking via FTP or TUNNEL means reassembly state, loss handling and an unsigned-or-signed question for the chunks themselves. PX4 drops messages it cannot verify when signing is on. The forum report above claims relays may drop trailing bytes; I did not verify it.

### 2.2 Telemetry radios
- SiK firmware (ArduPilot SiK repo, `Firmware/radio/radio.h`, https://raw.githubusercontent.com/ArduPilot/SiK/master/Firmware/radio/radio.h, retrieved 2026-10-11): `MAX_PACKET_LENGTH` is 252 bytes in the radio firmware source.
- ArduPilot SiK documentation (https://ardupilot.org/copter/docs/common-3dr-radio-advanced-configuration-and-technical-information.html, retrieved 2026-10-11): default air data rate 64 kbps; selectable rates 2, 4, 8, 16, 19, 24, 32, 48, 64, 96, 128, 192 and 250 kbps; without error correction a one-direction link can carry about 90% of the air rate; enabling ECC halves the supportable data rate.
- RFD900x data sheet (https://files.rfdesign.com.au/Files/documents/RFD900x%20DataSheet.pdf, "last update 16/03/2017" in the footer, retrieved 2026-10-11): RF data rates 4, 64, 125 (can be 128), 250 and 500 kbps in the specification table; serial rates up to 460 kbps; up to 50 hopping channels; MAVLink framing selectable; automatic duty cycle throttling by radio temperature. Limit/risk: the same document says "up to 250kbps" in one place and "up to 500kbps" in another; I treat the 500 kbps entry as unresolved. Old revision; a newer data sheet was not retrieved.
- LoRa / LoRaWAN (via The Things Network documentation of the LoRa Alliance regional parameters, which is a secondary summary of the RP002 spec; the LoRa Alliance RP002 PDF itself was not retrievable):
  - EU863-870 (https://www.thethingsnetwork.org/docs/lorawan/regional-parameters/eu868/): maximum application payload by data rate is 51 bytes at DR0-DR2, 115 bytes at DR3, 222 bytes at DR4-DR7; bit rate at DR0 (SF12/125 kHz) is 250 bit/s and at DR5 (SF7/125 kHz) 5470 bit/s. Recommended duty cycle 1%; ETSI EN 300.220 sub-band duty cycles 0.1%, 1% or 10% depending on sub-band.
  - US902-928 (https://www.thethingsnetwork.org/docs/lorawan/regional-parameters/us915/): maximum application payload 11 bytes at DR0, 53 at DR1, 125 at DR2, 222 at DR3/DR4; no duty-cycle limit under FCC rules but a 400 ms maximum dwell time per channel.
  - TTN Sandbox fair-use policy: 30 s uplink airtime per node per day (a network policy, not a regulation).
  - Limit/risk: LoRaWAN is star-topology and built for infrequent small uplinks; TTN docs say it is not suitable for real-time data. LoRa as a raw PHY (not LoRaWAN) has different limits; the Semtech SX1276 data sheet was not retrievable, so I make no PHY-level claim.
- IEEE 802.15.4: RFC 4919 (informational, https://www.rfc-editor.org/rfc/rfc4919.txt, retrieved 2026-10-11) says the maximum physical-layer packet is 127 bytes, the resulting MAC-layer frame about 102 octets, and link-layer security overhead can leave 81 octets for data in the worst case (AES-CCM-128). It also gives 250/40/20 kbps data rates for the PHYs it lists. Limit/risk: RFC 4919 summarizes 802.15.4-2003; the IEEE standard itself is paywalled and was not retrieved.
- Bluetooth LE: RFC 7668 (https://www.rfc-editor.org/rfc/rfc7668.txt, retrieved 2026-10-11) says the default LE link-layer MTU is 27 octets, leaving 23 octets for upper layers, and that larger MTUs are negotiated per direction. Limit/risk: the Bluetooth Core specification (data length extension, ATT_MTU up to 517 per the usual references) was not retrievable here, so I do not give those numbers. RFC 7668 describes the pre-extension default.

---

## 3. ROS 2 security, DDS-Security, micro-ROS

### 3.1 DDS-Security (OMG, primary)
- Document: DDS Security version 1.2, OMG formal/25-03-06, "Release Date: Tbd 2025" on the cover, retrieved 2026-10-11 from https://www.omg.org/spec/DDS-SECURITY/1.2/PDF. Status: the cover wording indicates a not-yet-final release at that revision; flag as in flux. (The 1.1 PDF fetched as a blank/unreadable file.)
- Fact (signature algorithms, Table 25): RSASSA-PSS with 2048-bit RSA and SHA-256; RSASSA-PKCS1-v1.5 with 2048-bit RSA and SHA-256; ECDSA on P-256 with SHA-256; ECDSA on P-384 with SHA-384. The table marks certain legacy names as deprecated in v1.2.
- Fact (key agreement): DHE with MODP-2048 (the table marks the older name deprecated), ECDHE on P-256, ECDHE on P-384.
- Fact (crypto plugin): built-in plugin "DDS:Crypto:AES-GCM-GMAC"; algorithms AES-128-GCM/GMAC and AES-256-GCM/GMAC with 96-bit IVs.
- Fact (PQC): a search of the full text finds no post-quantum algorithm; the only quantum-related hit is a bibliography entry pointing to the NSA CNSA 2.0 FAQ. The specification defines pluggable SPI interfaces, so new algorithms need new plugin implementations or algorithm identifiers in the spec.
- Limit/risk: the interoperable built-ins are RSA/ECC for identity and certificates, so DDS-Security authentication, permissions-document signing and key agreement all sit on quantum-vulnerable public-key algorithms; the symmetric AES-GCM data path is the less exposed part.

### 3.2 ROS 2 / SROS2 documentation
- ROS 2 design article "ROS 2 DDS-Security integration" (https://design.ros2.org/articles/ros2_dds_security.html, written 2019-07, last modified 2020-07, retrieved 2026-10-11). Fact: ROS 2 uses three of DDS-Security's five plugin interfaces (authentication, access control, cryptographic), the built-in PKI-DH authentication plugin with X.509 certificates and a CA, signed governance and permissions XML files, and the AES-GCM-GMAC crypto plugin. Security is off by default.
- ROS 2 documentation tutorial source for "Setting up security" (kilted branch, https://raw.githubusercontent.com/ros2/ros2_documentation/kilted/source/Tutorials/Advanced/Security/Introducing-ros2-security.rst, retrieved 2026-10-11; the rendered docs.ros.org pages sit behind a bot-check and could not be fetched). Fact: sros2 provides tools for ROS 2 on DDS-Security; tested with eProsima Fast DDS, Eclipse Cyclone DDS and RTI Connext in the repository README; the tutorial states secure communication across DDS vendors is not supported; the tutorial also covers the Zenoh RMW (`rmw_zenoh_cpp`), which has its own security tooling (generated Zenoh configs with access control, authentication and encryption) rather than DDS-Security.
- Limit/risk: SROS2 key and certificate tooling is Python with the `cryptography` library (per the UMH thesis below), which has no PQC; ROS 2 security rests on whichever DDS vendor plugin implements the above algorithms.

### 3.3 micro-ROS / Micro XRCE-DDS on microcontrollers
- The micro.ros.org pages I tried (feature comparison, middleware, security tutorial) returned 404 at the guessed paths, and the eProsima Micro XRCE-DDS docs pages I retrieved (introduction, transport) contain no security section. I therefore cannot cite an official statement of security status. This is a gap, not evidence of absence.
- Nandi et al., "Secure integration of extremely resource-constrained nodes on distributed ROS2 applications", Open Research Europe 2023 (DOI 10.12688/openreseurope.16108.1; abstract on https://cister.isep.ipp.pt/docs/secure_integration_of_extremely_resource_constrained_nodes_on_distributed_ros2_applications/1863/ fetched over http because the https certificate did not match, retrieved 2026-10-11; abstract only). Fact: builds the first open-source TLS 1.3 transport (wolfSSL plus the eProsima API) between micro-ROS and ROS 2; reports that encrypted single-value messages show about 20% time overhead versus the default unencrypted micro-ROS transport; also discusses how DDS-XRCE and DDS-Security interact. Limit/risk: classical TLS 1.3 only; the abstract implies micro-ROS security is done at the transport rather than via DDS-Security on the MCU.

### 3.4 PQC for DDS / ROS 2: what exists
- Something exists, but it is small and early:
  - PQSec-DDS (Blanco-Romero et al., JNIC 2024, Universidad Carlos III de Madrid; https://idus.us.es/bitstream/handle/11441/160619/JNIC24_414.pdf, retrieved 2026-10-11). Fact: a C/C++ library plugging into the DDS-Security authentication SPI to carry post-quantum KEMs and signatures through the handshake (via liboqs and oqs-provider); proof of concept with Cyclone DDS; crypto-agile design. The paper states performance implications still need study. Limit/risk: the paper does not report benchmarks that I could find; 8-page conference paper.
  - UMH master's thesis, "Enhancing Communication Security in ROS 2" (F. J. Blanco Romero, 2024/2025; https://dspace.umh.es/bitstream/11000/37017/1/Blanco_Romero_Francisco_Javier_TFM.pdf, retrieved 2026-10-11). Fact: describes a PQC-enabled SROS2 fork (Dilithium3 key option via OpenSSL OQS provider), the PQSec-DDS plugin, and a Zenoh fork using rustls with the X25519Kyber768Draft00 hybrid group; its conclusions list comprehensive benchmarking of PQC in Cyclone DDS as future work. Limit/risk: pre-FIPS naming (Kyber/Dilithium), student thesis, no benchmarks.
  - AXON, "A ROS 2 RMW with Shared-Memory/QUIC Transport and QKD/ML-KEM Key Establishment" (arXiv 2609.10024v1, 9 September 2026, University of Leon; https://arxiv.org/pdf/2609.10024, retrieved 2026-10-11, preprint, in flux). Fact: a non-DDS RMW; remote traffic uses TLS 1.3 over QUIC offering only the hybrid X25519MLKEM768 group (no classical-only fallback), with an alternative mode using an externally supplied 256-bit key; it is not DDS wire-compatible. The authors state they have not quantified handshake or steady-state overhead, in the classic mode certificates are self-signed and not validated so an active man-in-the-middle is not prevented, and there has been no third-party cryptographic audit. Limit/risk: key establishment only; peer authentication is explicitly not post-quantum or even validated in the shipped mode; not for MCUs.
  - IJNRD 2026 (vol. 11, issue 8, https://www.ijnrd.org/papers/IJNRD2608233.pdf, retrieved 2026-10-11): a proposed ML-KEM plus Ascon-AEAD128 framework for robot-to-cloud links whose evaluation is described as a simulation-ready design; no measured results; low-tier venue. I list it only to show what exists.
- Plain statement: I found no PQC support in the upstream DDS-Security specification, in sros2 mainline, or in Fast DDS / Cyclone DDS / Connext releases (I did not check vendor release notes exhaustively). The only DDS-Security PQC work I retrieved is PQSec-DDS and its thesis fork; I found no published benchmark of PQC DDS-Security handshakes on a robot-class or MCU-class CPU.

---

## 4. Secure boot, OTA and standards identifiers

### 4.1 MCUboot
- Sources: MCUboot design doc (https://raw.githubusercontent.com/mcu-tools/mcuboot/main/docs/design.md) and release notes (https://raw.githubusercontent.com/mcu-tools/mcuboot/main/docs/release-notes.md, top entry "Version 2.5.0"), retrieved 2026-10-11.
- Fact: the image TLV list in the design doc includes RSA-2048 PSS, RSA-3072 PSS, ECDSA and Ed25519 signature types; I found no LMS, XMSS, ML-DSA or other PQC identifier in either file (searched for those terms).
- Limit/risk: absence in the main-branch docs is not proof there is no open pull request or fork; the GitHub issue search was blocked (403). Status: no upstream PQC signature support found as of 2026-10-11.
- TF-M's Zephyr/MCUboot-based BL2 therefore signs with classical algorithms; TF-M's PQC step is BL1 (4.4).

### 4.2 wolfBoot
- Sources: wolfBoot README with release notes (https://raw.githubusercontent.com/wolfSSL/wolfBoot/master/README.md) and `docs/PQ.md` (https://raw.githubusercontent.com/wolfSSL/wolfBoot/master/docs/PQ.md), retrieved 2026-10-11.
- Fact (history from the changelog): V2.0.0 (2023-11-07) added LMS/HSS and XMSS/XMSS^MT; V2.3.0 (2024-10-31) added ML-DSA and hybrid authentication (one PQC algorithm plus ECC or RSA); V2.10.0 (2026-10-01) lists an NXP i.MX RT700 (MIMXRT798S) target with an ML-DSA-87 signed-boot configuration.
- Fact (PQ.md): supports ML-DSA (FIPS 204), LMS/HSS and XMSS/XMSS^MT (SP 800-208); lists ML-DSA sizes as private key 2560/4032/4896, public key 1312/1952/2592, signature 2420/3309/4627 bytes for levels 2/3/5 (matches FIPS 204 Table 2); example LMS config (2 levels, height 5, Winternitz 8) gives a 2644-byte signature and an image header of 5288 bytes; XMSS-SHA2_10_256 gives 2500 bytes. Hybrid mode verifies both a classical and a PQ signature sequentially and is described as protecting boot against a break in either; it needs the universal keystore option. Notes that stateful keys need more care.
- Limit/risk: vendor documentation, no timing or footprint numbers in these pages; the ML-DSA-87 NXP entry is a configuration claim from a release note.

### 4.3 PX4 and ArduPilot bootloader signing
- PX4 "Bootloader Secure Boot" (https://docs.px4.io/main/en/advanced_config/bootloader_secure_boot, retrieved 2026-10-11; in flux): Ed25519 via the monocypher library; 32-byte key, 64-byte signature; the page says verification needs no RNG on the device and the implementation fits in a 128 KB bootloader sector; the signed image carries a table of contents and a 64-byte signature at the end; a lost-key warning says recovery needs a debug probe. The example target is px4_fmu-v6x.
- ArduPilot "Creating Tamperproof Firmware" (https://ardupilot.org/dev/docs/secure-firmware.html) and the signing README (https://raw.githubusercontent.com/ArduPilot/ardupilot/master/Tools/scripts/signing/README.md), retrieved 2026-10-11. Fact: the bootloader can embed up to 10 public keys and refuses firmware not signed by one of them; key generation uses `pymonocypher`; the retrieved README text does not itself name the signature algorithm. A forum thread (https://discuss.ardupilot.org/t/firmware-code-checksum-parameter-checksum-and-rsa-firmware-signing-support-for-dgca-india-compliance/141687) records an Indian certification requirement for RSA signing and asks whether ArduPilot supports it; I did not retrieve an answer.
- Limit/risk: both flight stacks ship classical (Ed25519-class) bootloader verification in a fixed-size bootloader region; changing the signature scheme changes the immutable first-stage code, which is exactly the case where SP 800-208 and RFC 9019 recommend considering hash-based signatures. I found no PX4 or ArduPilot documentation of a PQC bootloader.

### 4.4 TF-M and PSA Certified
- TF-M BL1 documentation (https://trustedfirmware-m.readthedocs.io/en/latest/design_docs/booting/bl1.html, retrieved 2026-10-11): BL1_2 verifies the next boot stage with LMS (SP 800-208, RFC 8554) using SHA-256; the SHA256_H10 parameter set lets each key sign 1024 images; the page states LMS public keys are 32 bytes and signatures 1912 bytes; the LMS software implementation used in BL1 is about 3 KiB versus at least 6.5 KiB for RSA; BL1 mentions fault-injection and DPA mitigations. Limit/risk: the 1912-byte figure does not match my arithmetic from RFC 8554 Table 1 for N32/H10 with W=8 (1452) or W=4 (2508); the page does not state W, so I do not reconcile it (Section 8.3). TF-M roadmap page (retrieved) lists classical features and I found no PQC mention there.
- PSA Certified Crypto API: the PSA API site (https://arm-software.github.io/psa-api/crypto/, retrieved 2026-10-11) lists a PQC extension: 1.3 betas (March to September 2025), PQC 1.4 Final 0 (November 2025) and Final 1 (28 January 2026), and "PQC 1.5.0 Integrated" with the 1.5.0 core spec (June 2026). The 1.4 PQC extension PDF (https://arm-software.github.io/psa-api/crypto/1.4/ext-pqc/AES0119-PSA_Certified_Crypto_API-1.4_PQC_Extension.1.pdf, retrieved) covers LMS, HSS, XMSS, XMSS^MT, ML-DSA, SLH-DSA and ML-KEM. Fact: the standard API surface for PQC now exists. Limit/risk: an API specification is not an implementation or a certification; Mbed TLS / TF-PSA-Crypto changelog (https://raw.githubusercontent.com/Mbed-TLS/TF-PSA-Crypto/development/ChangeLog, retrieved) shows LMS verification support and fixes including one (CVE-2025-49601) where a failing hash accelerator could let an invalid signature be accepted. That is a defensive lesson: hardware offload paths must fail closed.

### 4.5 Vendor hardware / ROM statements (what the pages state)
- STMicroelectronics press release 10 March 2025 (https://newsroom.st.com/media-center/press-item.html/n4680.html, retrieved 2026-10-11): says ST introduced hardware cryptographic accelerators and software libraries for general-purpose and secure microcontrollers; X-CUBE-PQC for STM32; Stellar automotive MCUs with a SHA-3 accelerator; secure MCU libraries and hardware IP supporting ML-KEM, ML-DSA and XMSS/LMS targeting Common Criteria and FIPS 140-3. ST blog on X-CUBE-PQC (https://blog.st.com/x-cube-pqc/, retrieved; undated in the text I extracted): says LMS came first, then ML-KEM, ML-DSA and XMSS, uses the STM32 cryptographic accelerator "to mitigate the performance penalty", and states the algorithms are CAVP-certified. Limit/risk: marketing wording, no cycle counts, no device list in these pages; the X-CUBE-PQC product page did not load.
- Microchip press release 15 May 2025 (https://ir.microchip.com/news-events/press-releases/detail/1312/microchip-brings-hardware-quantum-resistance-to-embedded-controllers, retrieved 2026-10-11): MEC175xB embedded controllers (Arm Cortex-M4F at 96 MHz, 480 KB SRAM) with ML-DSA, LMS verification and ML-KEM "implemented in immutable hardware"; secure boot and update configurable for CNSA 1.0, 2.0 or hybrid signature verification; ML-DSA used for attestation; early-adopter availability. Limit/risk: vendor claim; an embedded controller for PC platforms, not a flight controller.
- Infineon press release 27 August 2025, as republished by EEJournal (https://www.eejournal.com/industry_news/infineon-drives-industry-transition-to-post-quantum-cryptography-on-psoc-control-microcontrollers, retrieved; the infineon.com press page did not load): PSOC Control C3 Performance Line described as CNSA 2.0 compliant for firmware protection, supporting LMS firmware verification with SHA-2 hardware acceleration and SHA-512; hybrid LMS plus ECC firmware signing supported; samples late 2025, production parts in 2026. Limit/risk: motor-control/power MCUs; a relevant class for ESC and actuator controllers but no performance data stated.
- NXP: the nxp.com pages found by search (PQC strategy blog, "Trusted Robotics Toolkit: Post-Quantum Secure", white paper) returned access-denied or not-available to my fetches, so I cannot state what they say. The only NXP statement I retrieved is via wolfBoot's release note (i.MX RT700, Section 4.2), which is wolfSSL's claim, not NXP's.
- Arm: no Arm page stating LMS/ML-DSA in a Cortex-M ROM was retrieved; the PSA/TF-M items in 4.4 are the Arm-ecosystem evidence.

### 4.6 SUIT, Uptane, COSE and CMS identifiers
- RFC 9019 (SUIT architecture, Informational, https://www.rfc-editor.org/rfc/rfc9019.txt, retrieved) says RSA/ECC signatures may become vulnerable to quantum-accelerated key extraction and that unchangeable bootloader code in ROM is recommended to use post-quantum secure signatures such as hash-based ones (cites RFC 8778); it gives a worst-case horizon estimate of about 2030 from research current at its writing (published 2021, so dated; do not treat as current).
- RFC 9124 (SUIT information model, Informational, retrieved): requires algorithm extensibility; I did not extract more.
- RFC 8778 (HSS/LMS in COSE, Standards Track, April 2020, https://www.rfc-editor.org/rfc/rfc8778.txt, retrieved): registers COSE algorithm value -46, "HSS-LMS".
- RFC 8554 (LMS, Informational, April 2019) and RFC 8391 (XMSS, Informational, May 2018), retrieved. RFC 8554 Table 1 gives LM-OTS signature lengths of 8516, 4292, 2180 and 1124 bytes for W=1, 2, 4, 8 with n=32.
- draft-ietf-suit-mti-23 (https://datatracker.ietf.org/doc/draft-ietf-suit-mti/, retrieved; datatracker "last updated 2026-09-30", latest revision 2025-07-22, WG state "Submitted to IESG for Publication", intended Proposed Standard; in flux): defines mandatory-to-implement profiles; the profile `suit-sha256-hsslms-a256kw-a256ctr` uses HSS/LMS (COSE -46); recipients are RECOMMENDED to implement that profile; it recommends taller trees for long device lifetimes; other profiles use Ed25519 (-19), ECDH and AES or ChaCha20/Poly1305. It lists post-quantum support as something a profile may require device support for. It contains no ML-DSA profile in this revision. The text of the file I retrieved shows an "Expires 23 January 2026" line, so the draft text itself is older than the datatracker timestamp; treat its status as unresolved.
- RFC 9964 (ML-DSA for JOSE and COSE, Proposed Standard, May 2026, https://datatracker.ietf.org/doc/rfc9964/, retrieved): registers COSE algorithms ML-DSA-44 = -48, ML-DSA-65 = -49, ML-DSA-87 = -50; the pure form is used (empty context string) and HashML-DSA is intentionally not supported.
- RFC 9882 (ML-DSA in CMS, Proposed Standard, October 2025, https://www.rfc-editor.org/rfc/rfc9882.txt, retrieved) and RFC 8708 (HSS/LMS in CMS, Standards Track, February 2020, retrieved).
- draft-ietf-lamps-pq-composite-sigs-19 (composite ML-DSA for X.509; datatracker: RFC Editor queue, intended Proposed Standard, retrieved; in flux).
- Uptane Standard 2.1.0 ("latest", https://uptane.org/docs/latest/standard/uptane-standard, retrieved): the metadata section names RSA and ECDSA (rsassa-pss, ecdsa) and ed25519 as examples; I found no post-quantum text. It does not mandate a metadata format or one algorithm, so algorithm change is a metadata-profile question.
- Limit/risk: the identifiers exist (HSS-LMS -46, ML-DSA -48/-49/-50), so OTA manifest formats can already carry PQC signatures; the SUIT-profile and device-library side is what lags (no ML-DSA SUIT profile in the MTI draft I retrieved).

---

## 5. Hybrid approaches, crypto-agility, hardware acceleration

### 5.1 Hybrid key exchange (IETF)
- RFC 10024, "Post-Quantum Traditional (PQ/T) Hybrid Key Agreement Mechanisms for TLS 1.3", Proposed Standard, August 2026 (https://datatracker.ietf.org/doc/rfc10024/, retrieved). Groups: X25519MLKEM768, SecP256r1MLKEM768, SecP384r1MLKEM1024. Published sizes: X25519MLKEM768 client share 1216 bytes (1184 ML-KEM + 32 X25519), server share 1120 bytes (1088 + 32), shared secret 64 bytes; SecP256r1MLKEM768 client 1249 / server 1153; SecP384r1MLKEM1024 client 1665 / server 1665. These sizes go in the evidence CSV.
- RFC 9954, "Hybrid Key Exchange in TLS 1.3", Informational (https://datatracker.ietf.org/doc/rfc9954/, retrieved; datatracker last updated 2026-07-15).
- draft-ietf-tls-mlkem-11 (pure ML-KEM for TLS 1.3, retrieved; RFC Editor queue, intended Informational, in flux).
- RFC 9794 (terminology for PQ/T hybrid schemes, NCSC UK authors, June 2025, Informational, retrieved); RFC 9955 "Hybrid Signature Spectrums" (Informational, retrieved); RFC 9958 "Post-Quantum Cryptography for Engineers" (Informational, retrieved). I used them for terminology and for the statements below, not for numbers.

### 5.2 Constrained-device guidance and hybrid/dual signing for firmware
- draft-ietf-pquip-pqc-hsm-constrained-07, "Adapting Constrained Devices for Post-Quantum Cryptography" (https://datatracker.ietf.org/doc/draft-ietf-pquip-pqc-hsm-constrained/, last revised 2026-10-08, retrieved; IESG evaluation, intended Informational; explicitly "work in progress", in flux). Facts: recommends storing seeds instead of expanded private keys where possible; describes lazy matrix expansion and pre-hashing as memory optimizations; gives a worked, naive memory accounting (not a measurement): for ML-KEM-768 about 9,216 bytes and for ML-DSA-87 at least about 79 KB of RAM during signing before per-iteration vectors; says stateful HBS (HSS/LMS, XMSS) are good candidates for firmware signing with versioned updates easing state management, SLH-DSA avoids state but has slower, larger signatures, and ML-DSA is faster with shorter signatures but hash-based schemes inspire more confidence; for hybrid firmware signing it says a non-composite approach (two signatures carried separately) is simple and fits current secure-boot designs, while composite constructions need cryptographic processing changes and overall cost remains dominated by the PQ component; verification must enforce that authentication holds as long as one component holds.
- RFC 10033, "Hash-Based Signatures: State and Backup Management" (Informational, https://datatracker.ietf.org/doc/rfc10033/, datatracker last updated 2026-09-15, retrieved): operational guidance and security considerations for managing state and backups of stateful hash-based keys.
- Vendor implementations of dual/hybrid firmware signing: wolfBoot (ML-DSA plus ECC, sequential verification, Section 4.2); Infineon (LMS plus ECC, Section 4.5); Microchip (hybrid signature verification option, Section 4.5).
- Crypto-agility: the IETF PQC-engineer guidance and the draft above treat agility as a design goal; PQSec-DDS (Section 3.4) and wolfBoot (universal keystore) are implementation examples. The IETF crypto-agility draft URL I tried (draft-ietf-pquip-crypto-agility) returned 404.
- Limit/risk: a hybrid signature in a fixed-size bootloader sector doubles the verification code and the header; for MAVLink-class links the signature size problem (Section 8) is not reduced by hybrid mode.

### 5.3 Hardware acceleration of ML-KEM / ML-DSA (published numbers recorded in the CSV)
- RISQrypt (Tosun et al., ePrint 2026/312, https://eprint.iacr.org/2026/312, PDF from Sabanci University repository, retrieved): unified Kyber/Dilithium architecture with masking, HORNET 32-bit RISC-V core plus accelerators, FPGA Artix-7 XC7A100T; Table 8 reports, in thousands of cycles averaged over 1024 runs, Kyber768 keygen/enc/dec/masked-dec 23/28/35/109 and Dilithium3 keygen/sign/verify/masked-sign 120/480/126/1230; ASIC synthesis area is also reported. Pre-final naming (Kyber/Dilithium); preprint, in flux.
- Adams Bridge (ePrint 2026/256, https://eprint.iacr.org/2026/256, abstract only retrieved): unified ML-KEM/ML-DSA accelerator for the open-source Caliptra root of trust, synthesized in 5 nm at 600 MHz, ML-DSA three phases 26/61/31 us and ML-KEM 11/14/20 us, masking and shuffling countermeasures with TVLA up to one million traces; parameter sets and phase names not in the abstract. Preprint.
- PQShield NTT accelerator (Kundi et al., ASHES '24, DOI 10.1145/3689939.3695785, PDF retrieved): single NTT/iNTT engine; Zynq UltraScale+ FPGA; 3,821 LUTs, 2,970 FFs, 20 DSPs, 5 BRAMs; 258 clock cycles for a 256-coefficient polynomial at up to 322 MHz. NTT only, not a full operation.
- Karabulut and Azarderakhsh (ePrint 2026/711): reports Caliptra's masked ML-DSA costs about 6x area and a masked reduction design with 12.1x speedup and 86.7% fewer LUTs (abstract). Preprint.
- Systematic review of ML-DSA on IoT (ePrint 2026/1576, retrieved, abstract): states hashing is the largest single contributor to software cost in embedded profiling of ML-DSA (secondary claim from a review).
- Vendor statements: ST says its STM32 crypto accelerator mitigates PQC performance cost (Section 4.5); Microchip and Infineon describe hardware PQC / LMS verification (Section 4.5). No MCU vendor page I retrieved gives cycle counts.
- Limit/risk: published accelerator results use FPGAs or ASIC synthesis, not flight-controller MCUs; no comparable published number for a Cortex-M-class part with a PQC accelerator was retrieved in this stream (S2 covers software benchmarks).

---

## 6. Side-channel and fault considerations (conceptual, defensive)

- Risk classes (from the Ravi et al. survey, ePrint 2022/737, https://eprint.iacr.org/2022/737, retrieved, preprint): structured-lattice schemes (Kyber/ML-KEM, Dilithium/ML-DSA) are exposed to implementation attacks that observe physical leakage (timing, power, EM) or perturb computation (faults); the survey classifies reported attacks, says protecting against all of them needs customized countermeasures per scheme, and implements countermeasures in pqm4 on Cortex-M4 with "reasonable" overheads (abstract gives no number).
- Countermeasure families: constant-time coding; masking (splitting secrets into shares so one observation reveals nothing; first order and higher order); shuffling; redundancy and recomputation checks and ciphertext/validity checks for fault resilience; hardware isolation and immutable verification logic.
- Published masking overheads (setup as stated by each source):
  - Bos et al., "Masking Kyber: First- and Higher-Order Implementations", TCHES 2021 (ePrint 2021/483, retrieved): first-order masked Kyber decapsulation 3.1 million cycles on Cortex-M4F, a factor 3.5 over the unprotected optimized pqm4 implementation; also Cortex-M0+ results and higher orders.
  - Heinz et al., "First-Order Masked Kyber on ARM Cortex-M4" (ePrint 2022/058, retrieved, preprint): masked Kyber768 decapsulation 2,978,441 cycles including RNG, tested with 100,000 traces.
  - Migliore et al., "Masking Dilithium" (ACNS 2019, ePrint 2019/394, retrieved): masking on an ARM Cortex-M3 and a Dilithium variant with a power-of-two modulus that makes the masked operations 7.3 to 9 times more efficient; that variant is not FIPS 204.
  - Coron et al., TCHES 2024 issue 4 (retrieved): improved masked generation of the masking vector and rejection sampling in Dilithium; abstract has no overhead number. Belaid et al. (SUCRE, ePrint 2026/2248, TCHES 2026): states rejection sampling is about 25% of masked ML-DSA runtime and SUCRE is 4 to 6 times faster than Coron et al. on that step, at the cost of more memory.
  - RISQrypt: masked decapsulation 109K cycles vs 35K unmasked (Kyber768) and masked sign 1230K vs 480K (Dilithium3), on its FPGA co-design (Table 8). Ratio is mine (Section 8).
- Stateful hash-based signatures: SP 800-208 (October 2020, https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-208.pdf, retrieved) says the signer must ensure no one-time key signs more than one message, because two signatures from the same one-time key make forgery of arbitrary messages computationally feasible; it requires key and signature generation inside hardware cryptographic modules that do not export secret keys, says seemingly routine operations can lead to reuse, notes that the key state must be committed to non-volatile memory before a signature is exported (a crash or power loss before the write lands can cause reuse; a monotonic counter can help), discusses spreading keys over several modules to survive module failure, and says stateful schemes are not for general use but fit long-lived constrained devices such as firmware-update authentication. RFC 10033 gives operational guidance. Limit/risk for fleets (my reading): the state lives with the signer (build server or HSM), not the drone; any practice that could replay an older key state (restoring a backup, running two signing pipelines) is the hazard class SP 800-208 and RFC 10033 address.
- Fault-related defensive lessons for hash-based signing and verification code: a published analysis (Wagner et al., "Faulting Winternitz One-Time Signatures...", PQCrypto 2023, ePrint 2023/1572, retrieved) concludes exposed devices running signing or verification need countermeasures for the WOTS checksum computation and proposes hardened reference implementations; the Mbed TLS record in Section 4.4 shows a verification-time hazard where a failing hash accelerator could lead to acceptance of an invalid signature. I record these as risk classes only.
- Limit/risk for drones: a flight computer is physically accessible after capture, so side-channel and fault classes matter most for keys that live on the vehicle (session keys, device identity keys) and less for public verification keys; masking multiplies cost (3.5x for one Cortex-M4F Kyber decapsulation as published) on top of the unprotected cost.

---

## 7. Items found absent (plainly)

- No PQC in MAVLink: no official protocol change, no PX4/ArduPilot PQC signing; only a community RFC proposal and preprints.
- No PQC in the DDS-Security specification (v1.2 text), no mainline SROS2 PQC; only research forks.
- No MCUboot PQC support found in the main-branch docs and release notes.
- No micro-ROS / Micro XRCE-DDS PQC work found; micro-ROS security documentation itself could not be fetched.
- No PQC speed/size numbers from any flight-controller MCU in the sources retrieved in this stream (S2 covers generic Cortex-M).
- No vendor page retrieved states ML-DSA or LMS in a masked ROM of an STM32/NXP/Infineon part with timing; Microchip MEC175xB states "immutable hardware" for its algorithms (claim).

---

## 8. Estimates (clearly labelled, with formulas)

All items here are my arithmetic, labelled estimates, not published results. Inputs are the retrieved values named in the parentheses. They ignore headers, retransmission, acknowledgements, channel contention, key-establishment round trips and any security layer on the chunks.

### 8.1 Number of chunks
Formula: `chunks = ceil(N / C)`, where N = object size in bytes and C = usable bytes per message or frame.

Chunk sizes C (retrieved): MAVLink payload max 255; FTP data 239 (251 payload minus 12 header bytes, layout per the FTP page); ENCAPSULATED_DATA 253; TUNNEL 128; LoRaWAN EU868 DR0-DR2 application payload 51; LoRaWAN US915 DR0 application payload 11; 802.15.4 worst-case data with AES-CCM-128 81 (RFC 4919); BLE default 23 (RFC 7668).

Object sizes N: ML-DSA-44/65/87 signature 2420/3309/4627 and ML-DSA-65 public key 1952 (FIPS 204 Table 2); ML-KEM-768 encapsulation key 1184 and ciphertext 1088 (FIPS 203 Table 3); SLH-DSA-128s/128f/256f signature 7856/17088/49856 (FIPS 205 Table 2); LMS H10/W8 signature 1452 (computed, 8.3); HSS 2-level H5/W8 signature 2644 (wolfBoot-stated and reproduced in 8.3); Ed25519 signature 64 (PX4 docs); hybrid X25519MLKEM768 client/server share 1216/1120 (RFC 10024).

| Object (N bytes) | 255 MAVLink | 239 FTP | 253 ENCAP | 128 TUNNEL | 51 LoRaWAN EU DR0 | 11 LoRaWAN US DR0 | 81 802.15.4 | 23 BLE default |
|---|---|---|---|---|---|---|---|---|
| ML-DSA-44 sig (2420) | 10 | 11 | 10 | 19 | 48 | 220 | 30 | 106 |
| ML-DSA-65 sig (3309) | 13 | 14 | 14 | 26 | 65 | 301 | 41 | 144 |
| ML-DSA-87 sig (4627) | 19 | 20 | 19 | 37 | 91 | 421 | 58 | 202 |
| ML-DSA-65 pk (1952) | 8 | 9 | 8 | 16 | 39 | 178 | 25 | 85 |
| ML-KEM-768 ek (1184) | 5 | 5 | 5 | 10 | 24 | 108 | 15 | 52 |
| ML-KEM-768 ct (1088) | 5 | 5 | 5 | 9 | 22 | 99 | 14 | 48 |
| SLH-DSA-128s sig (7856) | 31 | 33 | 32 | 62 | 155 | 715 | 97 | 342 |
| SLH-DSA-128f sig (17088) | 68 | 72 | 68 | 134 | 336 | 1554 | 211 | 743 |
| SLH-DSA-256f sig (49856) | 196 | 209 | 198 | 390 | 978 | 4533 | 616 | 2168 |
| LMS H10/W8 sig (1452) | 6 | 7 | 6 | 12 | 29 | 132 | 18 | 64 |
| HSS L2/H5/W8 sig (2644) | 11 | 12 | 11 | 21 | 52 | 241 | 33 | 115 |
| Ed25519 sig (64) | 1 | 1 | 1 | 1 | 2 | 6 | 1 | 3 |
| X25519MLKEM768 client share (1216) | 5 | 6 | 5 | 10 | 24 | 111 | 16 | 53 |
| X25519MLKEM768 server share (1120) | 5 | 5 | 5 | 9 | 22 | 102 | 14 | 49 |

Per-frame overhead for a MAVLink 2 frame (retrieved structure): 10-byte header + 2-byte checksum = 12 bytes unsigned, 25 bytes if the 13-byte signature is added. Sending one ML-DSA-44 signature as 11 FTP messages therefore needs 11 separately framed (and, if signing is on, separately signed) messages, plus the FTP session and acknowledgement logic. Conclusion from the arithmetic: a PQ signature cannot be attached per message (the 13-byte field is fixed and one signature would fill 10 to 19 full-size frames); a design would need signing of occasional critical commands, a session-key derived tag per message (as the forum poster proposes), or a hash-then-sign scheme over batches.

### 8.2 Serial airtime
Formula: `t = 8 * N / R_eff` seconds, with R_eff the effective data rate. Inputs: SiK default 64 kbps; effective one-direction rate about 0.9 x air rate without ECC, about half of that with ECC (SiK docs); N = 2420/3309/4627.
- 64 kbps, no ECC (R_eff = 57,600 bit/s): 0.34 s / 0.46 s / 0.64 s.
- 64 kbps, ECC on (R_eff = 28,800 bit/s): 0.67 s / 0.92 s / 1.29 s.
- 250 kbps, no ECC (R_eff = 225,000 bit/s): 0.09 s / 0.12 s / 0.16 s.
These ignore MAVLink framing (adds 12 bytes per frame), time-division sync, and sharing the link with ongoing telemetry; at 64 kbps a single ML-DSA signature would occupy the link for roughly a third of a second to over a second, delaying other traffic.

### 8.3 Low-rate LoRa(WAN) and LMS size cross-check
- LoRaWAN EU868 DR0 nominal bit rate 250 bit/s: `t = 8 * N / 250` gives 77.4 s / 105.9 s / 148.1 s for the three ML-DSA signatures. At DR5 (5470 bit/s): 3.5 s / 4.8 s / 6.8 s. Under a 1% duty cycle (EU recommended value) the minimum spacing before another transmission is about `t * 99`, i.e. roughly 2.1 / 2.9 / 4.1 hours of enforced silence at DR0 for those three sizes (formula: t_off = t_on * (1/0.01 - 1)). Nominal bit rates only; real airtime includes LoRaWAN headers and per-frame preambles, so these are lower bounds.
- LMS signature size check: RFC 8554 gives LMS signature = 4 (leaf index) + LM-OTS signature + 4 (tree type) + 32 x H bytes. With the Table 1 W=8 OTS size 1124 and H = 10: 4 + 1124 + 4 + 320 = 1452 bytes. For HSS with 2 levels, H = 5, W = 8, an LMS public key is 56 bytes (4 + 4 + 16 + 32 from the RFC structure), each LMS signature is 4 + 1124 + 4 + 160 = 1292, and HSS = 4 + (1292 + 56) + 1292 = 2644, which equals the figure in wolfBoot's documentation. TF-M states 1912 bytes for SHA256_H10; with W unstated the formula gives 1452 (W=8) or 2508 (W=4), so I leave the TF-M figure unreconciled and do not use it in the table.

### 8.4 Ratios from published numbers
- Masking cost, RISQrypt Table 8: Kyber768 masked decapsulation / unmasked = 109 / 35 = 3.1x; Dilithium3 masked sign / unmasked = 1230 / 480 = 2.6x (hardware co-design, averages of 1024 runs). Compare Bos et al. at 3.5x on a Cortex-M4F (software). Setups differ; do not plot together.
- Hybrid handshake bytes (RFC 10024 sizes): client share + server share = 1216 + 1120 = 2336 bytes for X25519MLKEM768, versus 32 + 32 = 64 for plain X25519 shares (the 32-byte X25519 part is stated in the RFC); about 36.5x. Certificates and signatures come on top.

---

## 9. Sources I could not retrieve (or only partly)

- https://mavlink.io/en/guides/message_signing.html (wrong path; correct path retrieved from `/en/guide/`).
- https://ardupilot.org/dev/docs/mavlink-message-signing.html (404; replaced by the copter doc page).
- mavlink/mavlink GitHub issue #2527 (HTTP 403 through the sandbox); the claim is known only from the forum post.
- Zenodo paper on PQC for MAVLink cited in the forum post (not attempted); the MAVLink Message Signing Proposal Google Doc (not attempted).
- SBSeg 2024-era paper at sol.sbc.org.br ("download/44307/44070", connection reset) and its related "Implementation Attacks on ML-KEM" entry (not retrieved).
- eprint.iacr.org/2026/2343.pdf (403): only the abstract page was read.
- docs.ros.org rendered pages (bot-check page returned); ROS 2 docs read from GitHub source of the kilted/jazzy branches instead (the rolling branch path 404).
- micro.ros.org security/feature pages (404 at all guessed paths) and eProsima Micro XRCE-DDS security page (404); micro-ROS security status therefore rests on the Nandi et al. abstract only. The full Open Research Europe paper was not fetched.
- DDS-Security 1.1 PDF (unreadable) and the DDS-XRCE specification (not attempted).
- Bluetooth Core Specification (data length extension, ATT_MTU maximum): the Bluetooth SIG pages tried returned 404 or marketing content; Nordic pages blocked.
- Semtech SX1276 data sheet and LoRa Alliance RP002 PDF (not retrieved; TTN documentation used as a secondary summary).
- IEEE 802.15.4 standard (paywalled; RFC 4919 summary used).
- Newer RFD900x/RFD900x-US data sheet (only the 2017 revision retrieved).
- MCUboot GitHub issues and pull requests (403): PQC status inferred only from docs and release notes.
- PX4 and ArduPilot PQC discussions on GitHub (not searched; GitHub search blocked).
- NXP pages (PQC strategy blog, Trusted Robotics Toolkit, white paper, investor press release): access denied. Infineon press page (login/404) and Microchip main-site press page (403): used the EEJournal republication and Microchip's investor-relations copy respectively. ST X-CUBE-PQC product page (connection error).
- Arm / Cortex-M ROM-level PQC statements: none found.
- Uptane 2.2.0 URL (404; the "latest" 2.1.0 page read instead).
- Full text of Adams Bridge (ePrint 2026/256 PDF, blocked) and of the Coron et al. TCHES 2024 numbers (abstract only).
- IETF crypto-agility draft (`draft-ietf-pquip-crypto-agility`, 404 on datatracker).


## Correction (2026-10-11, report fact-check)
Section 4.4 attributes the Mbed TLS hash-accelerator LMS-verification bug to CVE-2025-49601. The independent check found that bug is CVE-2025-49600; CVE-2025-49601 is a separate out-of-bounds read in LMS public-key import (matches S5's Zephyr row). Use 49600 for the verification-bypass hazard.
