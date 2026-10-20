# The cost of post quantum cryptography on drone and robot microcontrollers: evidence, models and a migration path

Author: Huda Mueen. Draft of {{date}}. Generated from `docs/PAPER_body.md` by `scripts/build_paper.py`; every number below is read from a file in this repository, and `scripts/check_numbers.py` fails the build when a stated number drifts from its file. Licence: all rights reserved (`LICENSE`).

## Abstract

Drones and ground robots authenticate commands, telemetry and firmware with classical public key cryptography on microcontroller flight computers and narrow radio links. NIST has standardised the replacements (ML-KEM, ML-DSA, SLH-DSA), and buyers have begun to set dates. This study asks what the replacements cost on such devices and links, how well that cost can be predicted before a board is measured, and which devices in a fleet can migrate in place. It combines {{n_rows}} published rows (measurements, sizes and protocol figures) read from {{n_sources}} sources and checked by independent readers, a trace driven cycle model checked on held out published rows of the same code base, {{rtl_sentence}}, an energy and CPU headroom model built from datasheet values, a link and protocol simulator checked against published timings and closed forms, a signed boot and update model, a fleet planner run on real flight controller classes, and a mission level simulation of four security architectures. {{abstract_results}} Nothing in this study was measured on a microcontroller; the board experiment that would test the model is prepared and its outcome predicted in advance.

## 1. Introduction

A small multirotor or ground robot runs its flight or motion stack on a microcontroller class processor and talks to its operator over a telemetry radio, a mesh network or a cellular link. Public key cryptography protects three things on such a device: the command channel (who may steer it), the update channel (which firmware it will run) and, sometimes, the confidentiality of its data. Each of these is threatened differently by a future quantum computer. Confidentiality is exposed today if recorded traffic stays valuable for longer than the time to migrate. Authentication of commands is exposed only from the day forgery becomes possible, but a device that cannot be updated by then cannot be fixed. A boot chain whose root of trust is fixed in read only memory cannot be fixed at all.

The replacement algorithms are standardised: ML-KEM for key establishment [@nist_nistpubs_fips_nist_fips_203], ML-DSA and SLH-DSA for signatures [@nist_nistpubs_fips_nist_fips_204] [@nist_nistpubs_fips_nist_fips_205], and the stateful hash based schemes LMS and XMSS for firmware signing [@rfc-editor_rfc_rfc8391]. What an operator cannot yet say from evidence is what they cost on its own flight controller, over its own link, across its own fleet. Published microcontroller measurements are many but uneven: most come from one core (the Cortex-M4), from libraries tuned for a benchmark framework [@iacr_2019_844], under clock, cache and counter settings that differ from paper to paper [@iacr_2026_1333].

This study answers six questions:

- RQ1 What do the standard algorithms cost in cycles, stack and flash on microcontroller cores, and how well can cycles be predicted without a board?
- RQ2 What do they cost in energy and CPU headroom, and what share of a vehicle's budget does a realistic security workload take?
- RQ3 How do handshake, rekey, signed command and update traffic behave over the radios such vehicles use?
- RQ4 What do signed boot and signed update cost, and where does a fixed root of trust force replacement?
- RQ5 For fleets built from real board classes, which devices can migrate in place, with what probability?
- RQ6 Which architecture for an authenticated command and update channel is feasible, and what follow on project does the evidence justify?

The contribution is not a new algorithm or implementation. It is an evidence base with its provenance, a set of models whose errors are measured rather than assumed, and a pre registered, ready to run experiment that will test those models on hardware.

## 2. Related work

Benchmark frameworks and optimised implementations. The pqm4 framework set the common method for Cortex-M4 measurements [@iacr_2019_844] and publishes a results table [@githubusercontent_mupq_pqm4_master_benchmarks_csv]. Later work moved optimised code to the Cortex-M7 [@iacr_2025_366], reduced memory for ML-DSA [@iacr_2022_323] [@iacr_index_php_tches_article_download_8725_8325], and revisited Keccak and Dilithium on ARMv7-M [@rub_index_php_tches_article_download_11419_10922_11688]. Measurements on small cores include the Cortex-M0+ of the RP2040 [@arxiv_pdf_2603_19340]. A recent methodology paper shows that results differ widely with library configuration, caches and statistics, and proposes reporting rules [@iacr_2026_1333]; its Cortex-M33 rows are used here as an independent check.

Hash based signatures and secure boot. LMS and XMSS have been compared on the Cortex-M4 [@iacr_2020_470], XMSS verification has been accelerated in hardware [@nsf_servlets_purl_10112210], and post quantum secure boot has been built and measured [@date-conference_proceedings_archive_2020_pdf_0438]. Open bootloaders document post quantum options [@githubusercontent_wolfssl_wolfboot_master_docs_pq_md] and immutable first stages [@readthedocs_en_latest_design_docs_booting_bl1]; a widely used autopilot documents its own secure boot [@px4_main_en_advanced_config_bootloader_secure_boot]. Software update over constrained networks with post quantum signatures has been measured on low power devices [@iacr_2021_781].

Protocols and robotics. Hybrid key agreement for TLS 1.3 is specified [@ietf_doc_rfc10024]. MAVLink 2 defines a message signing scheme with a shared secret [@mavlink_en_guide_message_signing]. Post quantum command authentication for unmanned systems has been studied under real time and bandwidth limits [@iacr_2026_2343], and resource constrained nodes have been integrated with ROS 2 security [@ipp_docs_secure_integration_of_extremely_resource_constraine]. Hardware and co design approaches appear in [@iacr_2026_312] and [@pqshield_wp_content_uploads_2024_10_high_performance_ntt_har].

What this study adds is the combination: one provenance controlled table across these strands, models fitted and validated against it, and fleet and mission level consequences derived from it, each with its uncertainty and its label.

## 3. Method

### 3.1 Evidence

Every number carries one of seven labels, kept apart in every table and figure: published (copied from a retrieved source with its location), host measured (run on a PC), emulated (run on QEMU or Renode models; correctness, stack and size only), estimated (arithmetic from published sizes or rates), modelled (trace driven or fitted model, with its validation error beside it), RTL simulated (cycle accurate simulation of an open source core design, not Arm silicon) and planned (not yet run). A board measured label is reserved for the board experiment.

Rows enter `data/evidence.csv` only through staging files and a merge script that changes no value. Earlier rounds verified rows by independent readers on random and headline samples ({{v2_rate_sentence}}) and rechecked {{n_s10}} rows from supplied papers in full. In this round every new row was read by two readers who saw neither the staged value nor each other's sheet; every disagreement on a value, and a seeded sample of disagreements on wording, was settled by a third look ({{v5_sentence}}). Searches are logged in `docs/SEARCH_PROTOCOL.md`.

### 3.2 Models and simulations

Where a model is fitted, the split is seeded and recorded and the error on the held out part is reported before any modelled value is used. Not every model could be validated: the cycle model is checked on held out rows of the same code base; the energy model is calibrated on one board and one source; the boot model rests on three held out rows; the link model's rate part is checked against one published table, its LoRa formula against published examples and its duty cycle and loss parts only against closed forms; the protocol, mission and fleet results have no measured data to be checked against and are estimates under stated assumptions. The cycle model counts executed instructions by class in a trace of the pinned benchmark code and maps them to cycles with either per class costs assumed by the author (the Arm timing tables could not be retrieved) or costs fitted on half of the matched published rows. The energy model multiplies cycles by datasheet run mode current and voltage. The link model and protocol simulator use cited radio parameters, closed form checks and Monte Carlo runs with intervals. The planner classifies devices against published memory footprints; the exposure model draws data lifetime, migration time and policy horizon from stated ranges. Variance based sensitivity indices name the input that matters most.

### 3.3 Pre registration and review

Predictions with refutation clauses were hashed before each round and are scored by script; misses stay ({{pred_sentence}}). Independent reviewers who saw only the repository reviewed each round; their findings and resolutions are logged.

## 4. Results

{{results}}

## 5. Discussion

{{discussion}}

## 6. Threats to validity

Internal validity. The cycle model is fitted to one framework's code and checked on its other half; every test binary has a sibling of the same implementation in training, so agreement there shows interpolation within one code base, not transfer to other libraries; its bootstrap intervals treat rows as independent although they cluster by binary, so they are too narrow; and its external check on a second core gives two distinct predictions. The fitted per class costs are not physical cycle costs. The link model's absolute times are checked against few published figures. Energy uses typical datasheet currents, not measured ones.

External validity. Published cycle counts come from development boards at benchmark clocks with caches and wait states set by each author; a flight controller running its flight stack has less free memory, interrupts and bus contention. Fleets in the planner are drawn from real board classes but their counts are synthetic.

Construct validity. Stack figures follow different definitions across sources; signing times are variable and summarised by different statistics.

Reliability. Every result regenerates from committed scripts with stored seeds; continuous integration fails when a document disagrees with its data.

## 7. Limitations

{{limitations}}

## 8. Reproducibility

Run `python3 scripts/merge_evidence.py`, then the `run_all.py` script of each model folder (`cyclemodel/`, `energy/`, `bootchain/`, `mission/`, `rtlsim/`), the link study scripts in `linksim/`, the planner study in `planner/`, and `python3 scripts/build_paper.py`. Third party libraries are fetched at pinned commits and never committed. Data dictionary: `docs/DATA_DICTIONARY.md`.

## References

Keys refer to `data/bibliography.bib`, generated from the evidence table and the source notes.
