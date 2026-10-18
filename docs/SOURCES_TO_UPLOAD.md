# Sources received and sources still open

Author: Huda Mueen. Status on 2026-10-12. Web fetch and web search were the only route used for blocked sites. The author supplied the PDFs below from her own computer. They are kept outside this repository. Nothing is cited for a number until the full text has been read and the row passes the normal correction and merge route.

## Received (12 files)

| Title | DOI or URL | Pages | Text layer | Earlier state | Next use |
|---|---|---|---|---|---|
| pqm4: Testing and Benchmarking NIST PQC on ARM Cortex-M4 | https://eprint.iacr.org/2019/844 | 22 | yes | blocked | background; check the board and clock wording against the project's own files |
| Dilithium for Memory Constrained Devices | https://eprint.iacr.org/2022/323 | 14 | yes | blocked | stack figures for the `m4fstack` variant |
| Pitfalls and Methodology in ML-DSA Benchmarking | https://eprint.iacr.org/2026/1333 | 20 | yes | abstract only | exact reporting recommendations |
| Quantum-Resistant Security for Software Updates on Low-power Networked Embedded Devices | https://eprint.iacr.org/2021/781 | 20 | yes | abstract only | update size and time tables |
| RISQrypt | https://eprint.iacr.org/2026/312 | 46 | yes | abstract only | accelerator numbers |
| Post-Quantum Command Authentication for Unmanned Systems | https://eprint.iacr.org/2026/2343 | 15 | yes | abstract only | UAV command authentication numbers |
| Enabling Microarchitectural Agility (SLOTHY, M4 to M7) | https://eprint.iacr.org/2025/366 | 16 | yes | fetch summary | cycle tables |
| LMS versus XMSS on Cortex-M4 | https://eprint.iacr.org/2020/470 | 20 | yes | fetch summary | full LMS and XMSS tables |
| NSA CNSA 2.0 FAQ | media.defense.gov (path not recorded) | 21 | yes | blocked | dates and algorithm set. This is the FAQ only; the separate algorithms advisory is not in the folder |
| CISA quantum readiness pages | https://www.cisa.gov/quantum | 11 | no (image only) | blocked | read by OCR on 2026-10-15; statements in section 3.1 only |
| Public Policy Document National Encryption Policy | uaelegislation.gov.ae | 7 | no (image only) | no primary text | read by OCR on 2026-10-15; English; summary page only, matches the policy scope |
| UAE National Encryption Policy (Cyber Security Council), version 1.0, September 2025 | Cyber Security Council | 51 | yes | no primary text | primary text for the UAE section |

## Still open

1. The NSA CNSA 2.0 algorithms advisory (separate from the FAQ).
2. The executive regulation of the UAE policy, and the documents cited on the CISA page.
3. Everything listed in Appendix C of `docs/REPORT.md` that is not in the table above.

## Rules

1. Do not commit these papers to this repository. Keep them in a local folder. The CI check rejects PDFs outside the two allowlisted generated reports.
2. A number from these files enters `data/evidence.csv` only through `data/corrections.csv` and `scripts/merge_evidence.py`, with the page and table named in `location_in_source`.
