# Licence proposal (for the author to confirm)

Author: Huda Mueen. Proposed 2026-10-12. Nothing is final until you confirm.

| Part | Proposed licence | Short reason | Alternative |
|---|---|---|---|
| Code: `scripts/`, `bench/` (own files only), `linksim/`, `planner/`, `.github/` | Apache License 2.0 (`LICENSE`) | Permissive, so labs and companies can reuse the planner and simulator; includes an explicit patent grant, which matters near cryptography; compatible with the Apache, MIT and ISC licensed libraries the benchmarks call. | MIT (shorter, no patent clause) |
| Documents, data, plots: `docs/`, `data/`, `plots/` | Creative Commons Attribution 4.0 (`LICENSE-DOCS`) | Anyone may reuse and adapt the text and tables if they credit you, which suits a citable review. | CC0 for data only, if you prefer no attribution on the tables |

Points to know before you confirm:

1. The numbers in `data/evidence.csv` are facts copied from third party sources, each with its URL. CC BY 4.0 covers your selection, structure, notes and labels, not the underlying papers. The papers themselves are not in this repository.
2. The two PDFs in `docs/` are generated from your own text and are covered by CC BY 4.0.
3. Third party libraries are never committed; they are downloaded by script. Two of them (wolfSSL, wolfBoot) are GPL-3.0, which is another reason to keep them out of this repository. See `docs/LICENSES.md`.
4. A licence file only helps if the copyright holder is right. The notice names Huda Mueen as author; change it if a co author should be named.
