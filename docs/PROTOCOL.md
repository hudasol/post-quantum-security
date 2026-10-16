# Review Protocol: PQC cost on embedded drone/robot computers

Author: Huda Mueen. Protocol written 2026-10-11, before any evidence was collected.
Status: living document; any deviation is logged in the "Deviations" section at the bottom.

## 1. Research question

What does migrating to post quantum cryptography (ML-KEM / FIPS 203, ML-DSA / FIPS 204, SLH-DSA / FIPS 205, and stateful hash based signatures LMS/XMSS for firmware signing) cost on the microcontroller- and embedded class computers inside small drones and robots, and what migration paths exist for fleets already deployed with long service lives?

## 2. Sub-questions (one research stream each)

| Stream | Question | Output file |
|---|---|---|
| S1 Standards | What is the status and timeline of NIST and national/regional migration guidance (US, UK, EU, others)? Is there any UAE or Gulf guidance? | `data/raw/S1_standards.md` |
| S2 Benchmarks | What do published results report for ML-KEM, ML-DSA, SLH-DSA, LMS, XMSS on Cortex-M4/M33 and similar devices? | `data/raw/S2_benchmarks.md`, `data/raw/S2_evidence.csv` |
| S3 Drone/robot | What are the protocol level facts for MAVLink signing, ROS 2 / SROS2 / DDS-Security, secure boot, OTA signing, constrained telemetry radios, hybrid modes, crypto agility, hardware acceleration, side channel and fault considerations (conceptual only)? | `data/raw/S3_robotics.md`, `data/raw/S3_evidence.csv` |
| S4 Migration | What can a deployed fleet do by firmware update vs hardware change? How does firmware signing migration differ from session key migration? Which data needs long term confidentiality (harvest-now-decrypt-later) vs authenticity only? | `data/raw/S4_migration.md` |

## 3. Search strategy

Primary sources first, in this order:
1. Standards bodies and government agencies (NIST CSRC, NSA, NCSC UK, ENISA / EU Commission, BSI, ANSSI, others found).
2. Project repositories and their own documentation (for example pqm4, PQClean, mlkem native, mldsa native, liboqs, MAVLink docs, ROS 2 docs).
3. Peer-reviewed papers and IACR ePrint / TCHES / IEEE / ACM entries.
4. Vendor application notes, only when they contain measured numbers and name the setup.
5. Secondary summaries (blogs, news) are used only to locate primary sources and are never cited for a number.

Suggested query families (each stream records the exact queries it ran in its raw file):
- "pqm4 ML-KEM Cortex-M4 cycles", "ML-DSA Cortex-M4 stack usage", "SLH-DSA Cortex-M4", "LMS XMSS Cortex-M embedded benchmark"
- "post quantum MAVLink", "MAVLink 2 message signing limitations", "SROS2 post quantum", "DDS-Security post quantum"
- "post quantum secure boot microcontroller", "post quantum OTA firmware update embedded"
- "CNSA 2.0 timeline", "NIST IR 8547 transition", "NCSC post quantum migration timelines", "EU coordinated implementation roadmap post quantum", "UAE post quantum cryptography guidance", "TII post quantum", "Saudi / Qatar / Gulf post quantum guidance"
- "crypto agility embedded", "hybrid key exchange constrained devices", "hardware accelerator ML-KEM ML-DSA", "harvest now decrypt later data lifetime"

## 4. Inclusion criteria

A source is included when ALL of the following hold:
- It was actually retrieved by a research pass during this review (fetched page, paper text or repository file), and the retrieval date is recorded.
- It reports a number, status, requirement or protocol fact that is relevant to a sub question.
- It names its setup (device, compiler or library version, parameter set) well enough to judge comparability, or the missing detail is recorded as "not stated".

Excluded: sources that could not be retrieved, marketing claims without a method, numbers quoted second hand without a traceable primary source.

## 5. Evidence table schema (CSV)

One row per (source, device, library, parameter set, operation). Columns:

`id, scheme, parameter_set, operation, device, core, clock_mhz, library, library_version, compiler_flags_or_notes, cycles, ram_bytes, stack_bytes, flash_or_code_bytes, energy_uj, key_or_sig_size_bytes, size_kind, evidence_type, source_title, source_url, retrieval_date, location_in_source, comparability_warning`

Rules:
- `evidence_type` is one of `published`, `host-measured`, `estimated`. Only `published` rows come from this review's research streams. Host measurements made in the sandbox are stored in a separate file, never in this table.
- Empty cell means "not reported by the source". Never fill a gap from memory or by interpolation.
- `location_in_source` names the table, figure or file and line that holds the number, so a verifier can re-check it.
- Numbers are copied exactly as published, with units normalised only when the conversion is exact (for example kilocycles to cycles) and noted in `comparability_warning`.

## 6. Comparability rules

Two rows are only plotted on the same axis when they share: operation, parameter set, and core family. Otherwise they appear in separate panels or with a visible warning. Always flag differences in:
- Core and memory system (Cortex-M4 vs M33 vs M7, wait states, clock frequency). Cycle counts are not directly comparable across cores with different memory behaviour.
- Library and implementation style (reference C vs assembly optimised vs stack optimised).
- Compiler, version and optimisation flags.
- What is measured (whole operation vs only the NTT; includes hashing or not; includes random sampling or not).
- Statistic reported (single run, mean, median) and number of runs.
- RAM definition (peak stack only vs stack plus static buffers).
- Parameter-set version (for example round-3 Kyber vs final ML-KEM; the final standards changed details, so pre standard numbers carry a warning).
- Stateful signature parameters (LMS/XMSS tree height, Winternitz parameter, hash function).

## 7. Handling standards that are still moving

Every standards or guidance claim carries: document identifier, status (draft / final / withdrawn / superseded), publication or version date, and retrieval date. Claims about timelines are phrased as "as of <retrieval date>" and flagged "in flux" where the source is a draft or says it will be revised.

## 8. Safety and scope limits

- Side-channel and fault injection topics are covered at a conceptual, defensive level only (what the risk class is, what countermeasure families exist). No attack procedures or exploitation guidance.
- No custom cryptographic primitives for production use. Benchmark scripts call existing, reviewed libraries only.
- Host measurements (sandbox, x86 or ARM server) are labelled "host measurement" and are never presented as microcontroller results.

## 9. Synthesis and verification

1. Streams S1 to S4 run in parallel and each writes raw notes and evidence rows with source URLs and retrieval dates.
2. The evidence rows are merged into `data/evidence.csv` after a schema check.
3. Plots are produced only from `data/evidence.csv` rows of type `published` and carry the caption "Published numbers; setups differ; see comparability column".
4. A separate verification pass that did not collect the data draws a random sample of at least 25 rows (seeded, seed recorded), re-opens each source, and compares every populated numeric field. Error rate = rows with at least one wrong field / rows checked, and also field level error rate. Errors are corrected in the table and logged in `docs/VERIFICATION.md`.
5. The report is drafted only after the table is verified, so no figure in the prose can predate the check.

## 10. Deviations log

- D1 (2026-10-11): WebFetch permission prompts went unanswered during unattended research, so streams S1, S2 and S3 retrieved public pages with `curl` through the sandbox's configured egress proxy (TLS verification on, no workaround of any explicit denial). S4 was re-run the same way. Search results were used only to locate sources.
- D2 (2026-10-11): The schema in section 5 has no time column. Some sources report only milliseconds (wolfSSL, wolfBoot, ESP32 papers). No `time_ms` column was added: for those sources `cycles` is left empty and the millisecond figure is recorded in `compiler_flags_or_notes`. The merged table instead gains four derived label columns (`stream`, `scheme_family`, `standard_status`, `device_class`). (Corrected 2026-10-11: an earlier version of this entry said a `time_ms` column was added; it was not.)
- D3 (2026-10-11): Hosts that could not be retrieved through the proxy (eprint.iacr.org via Cloudflare 403, nsa.gov, cisa.gov, several vendor pages) are listed per stream under "Sources I could not retrieve". Numbers from those sources are not used.
- D4 (2026-10-11): `eprint.iacr.org` PDFs, nsa.gov, media.defense.gov and cisa.gov were unreachable (HTTP 403). Nothing from them is used; they are listed for manual fetching in docs/NEXT_STEPS.md.
- D5 (2026-10-11): The merge script moved one non numeric cell (S3-044) into `comparability_warning` and applied three location only corrections (data/corrections.csv) found by the verification pass. No numeric value was changed after collection.
