# Cross check: second run against this repository

Second run rows: 582. This repository: 523 rows (stream S8 left out, see the script). Matching is by value and source (see `scripts/crosscheck_second_run.py`).

| Result | Rows |
|---|---|
| MATCHED | 299 |
| ONLY_SECOND | 245 |
| NO_NUMBER | 38 |

| Source family | MATCHED | ONLY_SECOND | NO_NUMBER |
|---|---|---|---|
| arxiv | 54 | 62 | 7 |
| eprint | 3 | 46 | 4 |
| nist | 32 | 7 | 0 |
| other | 0 | 62 | 20 |
| pqm4 | 210 | 28 | 0 |
| rfc | 0 | 40 | 7 |
