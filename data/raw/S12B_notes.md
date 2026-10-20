# Extraction notes: energy, boot and update, handshakes and link timing

Author: Huda Mueen. Retrieval date for every item: 2026-10-20.

Outputs of this pass: `S12B_staged.csv` (40 rows in the 23 column evidence schema, all `published`),
`S12B_link_facts.csv` (63 link and timing facts), and `S12_search_log_B.csv` (87 log entries:
36 web searches, 49 page retrievals, and local checks). Nothing here has been promoted into `data/evidence.csv`;
the merge script reads only verified files, so these rows wait for an independent second reading.

Extraction rule followed: values were taken only from tables or explicit statements read in full text, either from the
supplied PDFs or from page retrievals that were asked to reproduce the table rows or sentences exactly. Where an
output looked summarised, inconsistent or structurally ambiguous, nothing was extracted and the reason is in the log.
Every staged row and fact was checked against `data/evidence.csv` for the same source and cell; no duplicates were
found.

## Main finding on the first priority topic (energy per operation)

No new measured per operation energy on a microcontroller was found that passed the extraction rule. This is a null
result and is reported as such. The candidates found fell into four groups: Raspberry Pi or laptop platforms
(arXiv 2505.16614, Cryptography 10(4) 55, arXiv 2609.23902, arXiv 2507.08312); energy computed from a cycle model or
datasheet current rather than measured (arXiv 2411.01380, arXiv 1903.07786); handshake level energy whose table was
inconsistent (Sensors 22 2484 Table A1, arXiv 2011.12035 Table IV); and one directly relevant paper whose retrieval was
blocked (arXiv 2106.11710, quantum resistant signatures for low power IoT). The existing energy rows in the evidence
table (arXiv 1912.00916, arXiv 2603.19340, ETASR 17148) remain the only microcontroller energy evidence.

## Per source notes

### eprint 2021/1553, Tasopoulos et al., post quantum TLS 1.3 on a Cortex-M4 (27 staged rows, 0 link facts)
- Read: eprint PDF through three retrievals (numeric rows of Table 2; notation and protocol details; device roles).
  The first retrieval declined to reproduce the table; a second retrieval asking for the numeric row values returned
  the full table. Values were checked against ratios stated in the same output (communication size about 6 times and
  about 3 times the ECDSA baseline for the Dilithium and Falcon combinations) and agree.
- Tables: PDF page 14, Table 2 (client and server average handshake time, communication size). Notation from Table 1.
- Licence: CC BY 4.0 (eprint page).
- Ambiguities: the paper does not state outright which device is client in each column; page 14 wording suggests
  the board was measured in both roles with the PC as peer. Algorithms are round 3 versions, not FIPS final.
  Static and .bss memory columns were not extracted (outside this topic). Round 4 rows were left out (SIKE is
  withdrawn; BIKE and HQC rows are available in the same table if needed later).

### Sensors 2022, 22, 2484, Schoeffel et al., PQC TLS on an nRF52840 over BLE (8 staged rows, 0 link facts)
- Read: publisher PDF through three retrievals (tables; table structure; caption, certificates and measurement point).
- Tables: Appendix A, Table A1 (handshake time mean and standard deviation for KEMs with ECDSA certificates).
- Licence: CC BY 4.0.
- Ambiguities: Table A1 prints one energy value per row below 1 mJ, which disagrees with the Figure 8 axis, so energy
  was not extracted. Table A2 (signature combinations with energy in mJ) was not extracted because the row grouping of
  server and client schemes is ambiguous in the extracted text. The internal check that handshake time minus the
  communication overhead column is constant across rows held for the extracted rows. The Cortex-M4 clock is not stated.
  Page is 19 by running header (first reading said 20).

### Espressif developer blog, hybrid secure boot on ESP32-C5 (5 staged rows, 0 link facts)
- Read: page through two retrievals; the second asked for exact phrases, which carry an approximation sign.
- Sections: Section 8 (bootloader verify path and the application benchmark table).
- Licence: not stated; vendor page served under a preview path, so it may change.
- Ambiguities: core, compiler, image size and total boot time are not stated; ECDSA curve not stated on the page as
  read here (an earlier pass recorded P-256). The same figures appear in `data/second_run/evidence_second_run.csv`
  (E080 to E082) but not in `data/evidence.csv`; these staged rows are a schema conformant reading.

### Supplied PDF 2021-781, Banegas et al., quantum resistant software updates (0 staged rows, 9 link facts)
- Read: supplied PDF text, Sections 3.1, 6.2 to 6.4 and Table 8 (PDF page 15).
- Licence: supplied PDF of the eprint version; licence as recorded by earlier passes for the same source.
- Ambiguities: the 30 to 60 s figure for 50 kB over IEEE 802.15.4 is a reference statement without a described method.
  Table 8 data transfer values are relative percentages against the Ed25519 base, kept as printed. Flash and stack
  columns of Table 8 were not extracted (memory, not link timing).

### Supplied PDF 2026-2343, Hyoung et al., KpqC command authentication (0 staged rows, 14 link facts)
- Read: supplied PDF text, Section 4.1 (netem profiles, PDF page 7) and Table 4 (PDF page 10).
- Ambiguities: Table 4 values are budget parameters taken from specifications, one marked as an estimate; they are
  not measurements. The ROS2 wired channel row was left out (not a constrained link). Handshake times from Table 5
  were already in the evidence table.

### arXiv 2011.12035, Restuccia, Tschofenig and Baccelli, DTLS and TLS 1.3 on RIOT (0 staged rows, 6 link facts)
- Read: arXiv PDF; Table III (bytes over the air) and Table IV (energy).
- Licence: not stated.
- Ambiguities: Table III units are not printed and the text does not say whether the counts are handshake only; the
  link was 6LoWPAN over Ethernet over serial, not a radio. Table IV was not extracted: the caption gives millicoulomb
  while the text gives the same values in microcoulomb, and charge is not energy.

### arXiv 2309.03338, Sabanci and Cebe, PQC TLS over NB-IoT (0 staged rows, 5 link facts)
- Read: arXiv PDF; Table 2 (PDF page 7) and Table 3 (PDF page 8).
- Licence: not stated.
- Ambiguities: NB-IoT is simulated in ns-3; byte totals are traffic counts in that setup, not radio measurements.
  Handshake times appear only in figures and were not extracted.

### arXiv 2505.13764, De Simone, Turvani and Riente, incremental FUOTA over LoRaWAN (0 staged rows, 9 link facts)
- Read: arXiv HTML v2; Section 2 statement, Section 5 Table 3 and Table 4 first row.
- Licence: not stated for the paper.
- Ambiguities: Table 4 times match fragment count multiplied by the 530 per hour downlink limit, so they are derived;
  energy is in mAh and scaled from measured per fragment current. Table 4 does not give delta sizes in bytes.

### arXiv 1507.05810, Vucinic et al., DTLS in duty cycled networks (0 staged rows, 7 link facts)
- Read: arXiv PDF; Sections III-A, III-B, VI.
- Licence: not stated.
- Ambiguities: Section III-A results are emulated (Cooja); Section III-B results are measured on hardware. The TSCH
  values of Section III-C were not extracted: they are analytical and the conclusion values disagree with Table I.

### Trinity College Dublin dissertation 2018-082, O'Sullivan, LoRa firmware transfer (0 staged rows, 2 link facts)
- Read: PDF; Summary and Abstract statements only (Table 5.1 rows were not in the extracted text).
- Licence: no open licence; facts paraphrased.
- Ambiguities: tests used a 5000 byte delta while the stated times refer to 7000 bytes; the derivation is not given in
  the extracted text.

### Seoul National University paper on post quantum EDHOC under MTU limits (0 staged rows, 11 link facts)
- Read: Korean language PDF, translated during retrieval; Table 1 only.
- Licence: not shown; venue and year not shown.
- Ambiguities: sizes are example payload sizes for ML-KEM-512 based EDHOC variants (Internet Drafts, in flux), not
  device measurements; message directions were inferred from the EDHOC message order because the arrows were garbled.

## Sources read but not extracted (see the log for each reason)
arXiv 1912.12257 (TLS 1.3 PQ KEM handshakes between two Raspberry Pi 3B+; signature not stated; Frodo total differs
between Table XII and Table XIII), arXiv 2508.10588 (LoRaWAN multicast simulation), arXiv 2607.23007 (analytical
model), wolfSSL LMS, XMSS and SLH-DSA verify table (no hardware stated), Politecnico di Torino thesis 37907 (Zynq SoC),
Waterloo thesis by Ganyu Xu (Raspberry Pi Pico 2 W client; result chapter not in the retrieved text), TU Delft thesis
(model based firmware transfer energy), EnGenius BLE throughput report (inconsistent rows), SECRYPT 2025 ESP32 paper
(no energy; rows missing from retrieved text), and several Raspberry Pi studies.

## Refused or blocked retrievals
- https://eprint.iacr.org/2022/1712.pdf (KEMTLS against TLS 1.3 on a Cortex-M4): refused by the site robots rule.
- https://arxiv.org/pdf/2106.11710 (quantum resistant signatures for low power IoT): blocked, permission not granted.
- https://www.mdpi.com/1424-8220/21/6/2192 (Sensors 21 2192): blocked, permission not granted.
None of these was retried and no other copy was sought.

## Items that remain unverified
Every staged row and fact rests on a single reading in this pass. The Espressif values carry an approximation sign
in the source. The board role per column in eprint 2021/1553 is inferred. The 7000 byte LoRa transfer times in the
Trinity College Dublin dissertation could not be traced to a table.
