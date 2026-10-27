# ProVerif 2.05 manual: statements used by the replay rule models

Author: Huda Mueen. Retrieval date: 2026-10-28. Values are paraphrased. Source: ProVerif 2.05 user manual and tutorial (B. Blanchet, B. Smyth, V. Cheval, M. Sylvestre, dated October 17, 2023), https://bblanche.gitlabpages.inria.fr/proverif/manual.pdf, SHA-256 of the retrieved file 4e738b31a3193bf3aefe651f2ff22a10bc190de7d7f9e0a406d85eed5d557034. The manual matches the ProVerif version pinned in `formal/install.sh`. The statements are used in `formal/make_doc.py` (section 9 of `docs/FORMAL_VERIFICATION.md`) to explain the encodings of `formal/build_models.py`.

| Statement | Location |
|---|---|
| Processes may insert records into a table and read them, but deleting a record is not possible; the attacker cannot access tables | section 4.1.5, page 41 |
| `get d(T) in P else Q` runs Q when no record matches; ProVerif considers every matching record when reasoning | section 4.1.5, page 41 |
| When restrictions are declared, ProVerif proves the main queries only on the traces of the process that satisfy the restrictions | section 6.2, page 91 |
| A restriction may not contain temporal variables (facts of the form F@t) | section 6.2, page 91 |
| ProVerif ignores how many times an action is repeated, because of the translation of processes into Horn clauses, which can yield false attacks | section 6.2, page 91 |
