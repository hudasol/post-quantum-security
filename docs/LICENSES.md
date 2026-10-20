# Third party licences

Author: Huda Mueen. Generated facts in `data/third_party_licences.csv` by `scripts/fetch_licences.py` (licence file read at the pinned commit on raw.githubusercontent.com, retrieved 2026-10-12). The 'as read' column is a keyword match, not legal advice. No third party code is stored in this repository.

| Component | Used for | Pinned commit | Licence file | Licence as read |
|---|---|---|---|---|
| mlkem native | E1 ML-KEM benchmark | `d1b2fe782888` | LICENSE | Apache-2.0; MIT; ISC |
| mldsa native | E1 ML-DSA benchmark | `834a90d5e846` | LICENSE | Apache-2.0; MIT; ISC |
| wolfSSL | E2 hash based signature verification | `3c5eead44904` | COPYING | GPL-3.0 |
| wolfBoot | E4 boot time | `eb710fe1656f` | LICENSE | GPL-3.0 |
| TF-PSA-Crypto | E2 comparison | `73c5da561c8e` | LICENSE | Apache-2.0; GPL-2.0 |
| pqm4 | reference rows only | `5e5cc76d0b07` | (none found at root) | not retrieved |
| slhdsa-c | SLH-DSA cross check | `174c02e42257` | LICENSE | Apache-2.0; MIT; ISC |
| liboqs | host measurements | `5a1a854b0dc9` | LICENSE.txt | MIT |
| ProVerif | WP4 formal verification of the session and update design (tool only, built outside the repository by `formal/install.sh`) | version 2.05, tarball SHA-256 in `formal/proverif.sha256` | LICENSE in the tarball | GPL-2.0 |

Notes:

- mlkem native, mldsa native and slhdsa-c carry a combined licence statement (Apache-2.0, MIT or ISC, as read). TF-PSA-Crypto offers Apache-2.0 or GPL-2.0 as read.
- wolfSSL and wolfBoot are GPL-3.0 as read. They are downloaded by `bench/mcu/fetch_libs.sh e2` for local experiments only. Do not redistribute builds without checking the licence.
- pqm4 has no licence file at the repository root at the pinned commit. Its licences are set per implementation directory. It is used only to read published benchmark rows and to read configuration files, never copied.
- liboqs is MIT as read (LICENSE.txt). Host measurements in `bench/host/` are labelled host measured.

## Datasets and documents used as sources

Every row of `data/evidence.csv` cites a source URL. The repository stores extracted numbers and short paraphrases, not the papers, slides or web pages. NIST publications (FIPS 203, 204, 205, SP 800-208) and IETF RFCs are cited for sizes and statements only. I have not verified the reuse terms of each paper; the numbers are factual values with attribution, and anything longer than a short phrase is paraphrased. If a rights holder objects to a row, remove it.

## Licence of this repository

All rights reserved by Huda Mueen. Permission is needed before use, copying, modification, distribution or sale; see `LICENSE` and `docs/LICENCE_DECISION.md`. The licences in the table above belong to third party libraries and are not changed by this.
