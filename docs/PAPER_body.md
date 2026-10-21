# The cost of post quantum cryptography on drone and robot microcontrollers: evidence, models and a migration path

Author: Huda Mueen. Draft of {{date}}. Generated from `docs/PAPER_body.md` by `scripts/build_paper.py`; every number below is read from a file in this repository, and `scripts/check_numbers.py` fails the build when a stated number drifts from its file. Licence: all rights reserved (`LICENSE`).

Target venue: a six page workshop paper with one additional page (PPT-PQC 2027, `data/raw/S13_venue.md`). Sections 1 to 6 and the references form the submission; the section marked Supplementary is for the repository version only. {{word_note}}

## Abstract

Drones and ground robots authenticate commands, telemetry and firmware with classical public key cryptography on microcontroller flight computers and narrow radio links. This paper asks what the standardised replacements (ML-KEM, ML-DSA, LMS) cost on such devices and links, how well that cost can be predicted before a board is measured, and which devices in a fleet can migrate in place. {{abstract_method}} {{abstract_results}} Nothing in this study was measured on a microcontroller; a board session that can refute the cycle model is prepared and its outcome registered in advance.

## 1. Introduction

A small multirotor or ground robot runs its flight stack on a microcontroller and talks to its operator over a telemetry radio, a mesh network or a cellular link. Public key cryptography protects its command channel, its update channel and sometimes its data. A future quantum computer threatens these differently: recorded data is exposed today if it stays valuable longer than the migration takes; command authentication is exposed from the day forgery becomes possible; and a boot chain whose root of trust is fixed in read only memory cannot be fixed at all.

The replacements are standardised: ML-KEM for key establishment [@nist_nistpubs_fips_nist_fips_203], ML-DSA and SLH-DSA for signatures [@nist_nistpubs_fips_nist_fips_204] [@nist_nistpubs_fips_nist_fips_205], and stateful hash based schemes for firmware [@rfc-editor_rfc_rfc8391]. What an operator cannot yet say from evidence is what they cost on its own flight controller, over its own link, across its own fleet. Published microcontroller measurements are many but uneven: most come from one core, from libraries tuned for a benchmark framework [@iacr_2019_844], under clock, cache and counter settings that differ from paper to paper [@iacr_2026_1333].

The study answers six research questions. RQ1: what the algorithms cost in cycles and memory on microcontroller cores, and how well cycles can be predicted without a board. RQ2: what they cost in energy and CPU headroom. RQ3: how handshake, command and update traffic behave over the radios such vehicles use. RQ4: what signed boot and update cost. RQ5: which devices of a fleet built from real board classes can migrate in place. RQ6: which command and update architecture is feasible.

Contributions. (1) A provenance controlled evidence table whose rows were checked against their sources by readers who worked separately from the staging and from each other (every row of the last two rounds by two readers), with measured reading error rates. (2) Models whose errors are measured on held out data, including leave one group out tests that expose where they do not transfer. (3) Checks of those models by independent tools: real flight stack builds, a network simulator, a protocol verifier and two open core simulations. (4) A reference architecture for an authenticated command and update channel, with three design changes found by formal verification. (5) A pre registered board experiment that can refute the cycle model.

## 2. Related work

The pqm4 framework set the common method for Cortex-M4 measurements [@iacr_2019_844] [@githubusercontent_mupq_pqm4_master_benchmarks_csv]; later work moved optimised code to the Cortex-M7 [@iacr_2025_366], reduced memory for ML-DSA [@iacr_2022_323], and measured small cores such as the Cortex-M0+ [@arxiv_pdf_2603_19340]. A recent methodology paper shows that results move with library configuration, caches and statistics and proposes reporting rules [@iacr_2026_1333]. LMS and XMSS have been compared on the Cortex-M4 [@iacr_2020_470], post quantum secure boot has been built and measured [@date-conference_proceedings_archive_2020_pdf_0438], open bootloaders document post quantum options [@githubusercontent_wolfssl_wolfboot_master_docs_pq_md], and post quantum signed updates over constrained networks have been measured [@iacr_2021_781]. MAVLink 2 signs messages with a shared secret [@mavlink_en_guide_message_signing]; post quantum command authentication for unmanned systems has been studied under real time limits [@iacr_2026_2343], and constrained nodes have been integrated with ROS 2 security [@ipp_docs_secure_integration_of_extremely_resource_constraine]. This paper adds the combination: one verified table across these strands, models validated against it and against independent tools, and fleet and mission consequences derived from it, each with its uncertainty and evidence label.

## 3. Method

Evidence labels. Every number carries one label, never mixed in one column: published (copied from a retrieved source), host measured, emulated, estimated (arithmetic from published values), modelled (with its validation error), RTL simulated (cycle accurate simulation of an open core design), simulated (network) (ns-3 output) and planned. Board measured is reserved for a session on a real board.

Evidence table. Rows enter `data/evidence.csv` only through staging files and a merge script that changes no value. {{method_reading}}

Models and independent checks. A trace driven cycle model counts executed instructions by class in the pinned pqm4 code and maps them to cycles with costs fitted on half of the matched published rows. An energy model multiplies cycles by datasheet currents; a link and protocol simulator uses cited radio parameters with Monte Carlo intervals; a boot model adds hashing and verification; a fleet planner classifies devices of nine real board classes against published memory footprints; a mission simulation compares four security architectures. Each was checked this round by a tool that does not share its code: the memory of real flight stack builds for the planner, ns-3 for the link model, ProVerif for the protocol design, and a second open core for the RTL results. Statistics use a cluster bootstrap by binary and leave one group out validation; one chain propagates published ranges end to end with Sobol indices.

Pre registration. Predictions with refutation clauses were hashed before each round and are scored by script; misses stay in the record (`docs/PREDICTIONS_V5.md`, `docs/PREDICTIONS_V5_BOARD.md`). Scores of this round are in `docs/PREDICTIONS_V5_SCORES.md` and stay partial until the round closes.

## 4. Results

Each answer states its uncertainty and its evidence label. Detailed results per study are in the Supplementary section and the study documents.

{{rq_results}}

## 5. Threats to validity

{{threats}}

## 6. Conclusion

{{conclusion}}

## References

Keys refer to `data/bibliography.bib`, generated from the evidence table and the source notes.

<!-- end of main paper -->

## Supplementary material (repository version only; not part of the six page submission)

### S1. Detailed results by research question

{{results}}

### S2. Discussion

{{discussion}}

### S3. Reproducibility: one command per figure and table

{{repro}}

### S4. Earlier verification and review

Earlier rounds verified rows by independent readers on random and headline samples ({{v2_rate_sentence}}) and rechecked {{n_s10}} rows from supplied papers in full; in round 4 every new row was read by two readers ({{v5_sentence}}). Predictions of earlier rounds: {{pred_sentence}}. Each round was reviewed by fresh reviewers working from a clean copy of the repository only; they belong to this project, not to an outside body, and no external reviewer has checked the study. Findings and resolutions are logged in `docs/REVIEW_FINDINGS*.csv`.
