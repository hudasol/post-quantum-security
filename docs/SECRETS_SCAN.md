# Secrets scan

Author: Huda Mueen. Run on 2026-10-12 over every tracked or not ignored file (the downloaded libraries under `bench/mcu/ext/` are ignored by git and were not committed).

| Scanner | Result |
|---|---|
| `scripts/scan_secrets.py` (private key blocks, GitHub, Slack, AWS, Google, API key style tokens, bearer tokens, generic secret assignments) | 0 findings |
| detect-secrets (pip package, all file plugins, binary files and the two generated PDFs excluded) | 8 findings, all false positives: the pinned git commit hashes in `scripts/fetch_licences.py` (hex strings of 40 characters) |
| GitHub secret scanning through the connector | not run: the connector disconnected in this session. GitHub's own push protection also applies on the remote. |

The CI job `policy` repeats the first scan on every push and pull request. No account name, token, key or personal email address is stored in the repository.
