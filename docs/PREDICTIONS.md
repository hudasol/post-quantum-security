# Predictions (written before any phase 2 run)

Author: Huda Mueen. Written 2026-10-11, before the verification subagents, the retrieval retries, the simulator, or the planner were run. The SHA-256 of the prediction text, taken at the moment of writing, is stored in `docs/PREDICTIONS.sha256`. Hits and misses are appended in the "Outcomes" section at the end only; the prediction text above it is not edited.

Confidence is my honest probability that the statement turns out true.

## P1. Verification

| ID | Prediction | Confidence |
|---|---|---|
| P1.1 | Field level error rate on the 157 headline rows is at most 2 percent; row level at most 3 percent. | 70% |
| P1.2 | Field level error rate on the further random sample (at least 100 rows) is at most 5 percent; row level at most 8 percent. | 65% |
| P1.3 | Most errors are location_in_source or comparability text, not the numeric value. | 70% |
| P1.4 | The pqm4 rows (cycles, stack, code size) match the pqm4 repository benchmark files exactly when diffed programmatically. | 85% |
| P1.5 | Combined row level error rate is below the 11 percent found in the earlier prose pass. | 80% |

## P2. pqm4 board and clock

| ID | Prediction | Confidence |
|---|---|---|
| P2.1 | The project's own benchmark configuration names the NUCLEO-L4R5ZI as the default board for the published results. | 75% |
| P2.2 | The clock in the current code for that board is 20 MHz, and the README statement of 24 MHz is stale or refers to the F4 path. | 60% |
| P2.3 | The repository history will not contain a single commit that states the board and clock together with the benchmarks.csv file; the answer will be inferred from code plus README, and I will say so. | 55% |
| P2.4 | If the clock is 20 MHz, the numbers of cycles do not change, only derived times in milliseconds (ms at 24 MHz in the report become ms at 20 MHz, about 1.2 times longer). | 90% |

## P3. Blocked sources (fetch tools only)

| ID | Prediction | Confidence |
|---|---|---|
| P3.1 | At least 70 percent of the listed eprint.iacr.org items stay blocked for the fetch tools. | 65% |
| P3.2 | nsa.gov and media.defense.gov (CNSA 2.0) stay blocked. | 70% |
| P3.3 | At least one source that curl could not reach is retrievable by the fetch tools (a non eprint host, for example a university or arXiv copy). | 60% |
| P3.4 | The UAE National Encryption Policy full text is not retrievable. | 80% |

## P4. Simulator (all values estimated from published sizes, not measured)

Assumptions: sizes from FIPS 203 and FIPS 204 (ML-KEM-768 public key 1184 B, ciphertext 1088 B; ML-DSA-44 public key 1312 B, signature 2420 B), X25519 32 B keys, MAVLink 2 frame limits (255 B payload), no packet loss unless stated.

| ID | Prediction | Confidence |
|---|---|---|
| P4.1 | A 1 MB firmware image over a 57.6 kbps effective link, no loss, no retransmission overhead beyond framing, takes between 130 and 170 s. | 85% |
| P4.2 | A hybrid handshake (X25519 plus ML-KEM-768, one ML-DSA-44 signature, one certificate sized public key) at 57.6 kbps effective takes under 1.5 s of air time. | 80% |
| P4.3 | The same handshake on LoRaWAN EU868 DR0 (250 bit/s, 51 B payload, 1 percent duty cycle) takes more than 60 s of air time and more than 100 times that in wall time under the duty cycle rule. | 75% |
| P4.4 | On 802.15.4 (about 81 B payload) the handshake needs between 60 and 90 fragments. | 60% |
| P4.5 | In the sensitivity check, the ranking of links (slowest to fastest) is unchanged across plus and minus 50 percent on every assumed parameter. | 80% |
| P4.6 | Loss of 10 percent with stop and wait retransmission increases the firmware time by between 8 and 25 percent for the fast link. | 55% |

## P5. Planner (hand written expected classes, before the planner exists)

Synthetic inventory of 12 devices. Expected class for each is written in `docs/PREDICTIONS_PLANNER.csv` (device id, expected class, reason). The planner developer does not read this file. Summary expectation:

| ID | Prediction | Confidence |
|---|---|---|
| P5.1 | The planner agrees with my hand classes on at least 10 of 12 rows. | 70% |
| P5.2 | Every row with a missing required field is classed UNKNOWN; no row with a missing field gets another class. | 90% |
| P5.3 | Disagreements, if any, come from threshold edge cases (free RAM near the ML-KEM-768 stack figure), not from logic bugs. | 60% |

## P6. Upstream issues

| ID | Prediction | Confidence |
|---|---|---|
| P6.1 | An existing issue or discussion about post quantum for MAVLink or MCUboot exists and will need linking. | 60% |
| P6.2 | There is no existing SROS2 post quantum issue, but a DDS-Security related one may exist in a different repository. | 55% |

## Outcomes

(Appended after the runs.)
