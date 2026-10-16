# Predictions for the second study round (written before any run)

Author: Huda Mueen. Written 2026-10-16, before any experiment of this round was run. The SHA-256 of this file as committed is stored in `docs/PREDICTIONS_V2.sha256`; the hash covers the prediction text only. Scores are written in a separate file, `docs/PREDICTIONS_V2_SCORES.md`, so this file is never edited after the hash is taken. Misses stay recorded.

What I already knew when writing: the committed outputs of the first round (`docs/link_tables.md`, `docs/EMULATOR_RESULTS.md`, `bench/mcu/host_selftest/`, the planner tests) and the text of Table 5 of ePrint 2026/2343 (two node handshake times), which I read while listing the tables of the supplied papers. Predictions that lean on those are marked "informed".

Labels: every prediction names the evidence label of the result it concerns (published, host measured, emulated, estimated, planned).

Seeds: Monte Carlo trial i of a cell uses seed `20261016 + i`. Planner fleets use seed `20261016` plus the fleet size. Every output file stores its seeds and configuration.

## Q1. More verified data (WP2, label published)

Sources: ePrint 2022/323, 2026/1333, 2021/781, 2026/312, 2026/2343, 2019/844 and the NSA CNSA 2.0 FAQ, as supplied by the author.

| ID | Question | Metric | Method | Prediction | Refuted if |
|---|---|---|---|---|---|
| Q1.1 | How many new rows can be taken from tables in these sources? | new rows merged into `data/evidence.csv` | extraction into `data/raw/` staging, then `scripts/merge_evidence.py` | at least 60 | fewer than 30 |
| Q1.2 | How accurate is the extraction? | row error rate found by a fresh reader (value, row, column or table wrong) | every new row rechecked against the PDF by a reader that has not seen the extraction notes | at most 5 percent | more than 10 percent |
| Q1.3 | Does the CNSA 2.0 FAQ give benchmark rows? | rows in the evidence schema | reading the FAQ | none; it gives dates and an algorithm list, which go into a research note | it contains a device measurement table |
| Q1.4 | Do the new rows contradict a headline number in the report? | contradictions found | compare each new row with the headline numbers it touches | none | any contradiction (this would trigger a report correction) |
| Q1.5 | How small can ML-DSA signing memory get? | ratio of the emulated portable C ML-DSA-44 sign stack (50,008 B, first round) to the smallest published Dilithium2 or ML-DSA-44 signing memory figure in the new rows | arithmetic on rows | ratio at least 5 (informed by the purpose of the 2022/323 paper) | ratio below 2 |

## Q2. Link simulator (WP3, label estimated)

| ID | Question | Metric | Method | Prediction | Refuted if |
|---|---|---|---|---|---|
| Q2.1 | Which inputs move the handshake time most? | relative change of hybrid handshake wall time per sweep step | one at a time sweeps of payload per fragment, rate, loss, retry limit and timeout factor | rate and payload per fragment have the largest effect; at zero loss the retry limit and the timeout factor change wall time by exactly 0 | any retry setting changes the zero loss wall time |
| Q2.2 | How much does 5 percent loss inflate a selective repeat handshake on SiK? | mean wall time at 5 percent loss divided by mean at 0 percent, 1000 trials | Monte Carlo | between 1.05 and 1.40, with the 95 percent interval of the mean narrower than plus or minus 2 percent of the mean | outside 1.05 to 1.40, or interval wider than 2 percent |
| Q2.3 | Is the LoRaWAN EU868 DR0 handshake an hours scale cost? | median and 95th percentile wall time, key sent | Monte Carlo, 1000 trials | median above 4 h at 0 percent loss and 95th percentile above 5 h at 10 percent loss (informed by first round tables) | either bound not met |
| Q2.4 | What does a fragment header cost on the slowest link? | fragments of the key sent handshake with a 4 B header per fragment versus none, LoRaWAN DR0 | fragmentation model | at least 8 percent more fragments | under 5 percent more |
| Q2.5 | Where does a short retry limit break? | completion rate, BLE, stop and wait, retry limit 3, 20 percent loss | Monte Carlo, 1000 trials | below 50 percent of handshakes complete | at least 50 percent complete |
| Q2.6 | How does the faster LoRaWAN data rate compare? | wall time ratio DR0 over DR5 (EU868, 1 percent duty) for the key sent handshake | fragmentation and duty cycle model | DR5 under 10 minutes, ratio above 20 | DR5 at least 10 minutes or ratio at most 20 |
| Q2.7 | Does the size based model agree with a published link figure? | error against Table 5 of ePrint 2026/2343 (UAV profile, 57.6 kbps, 40 ms delay) | bytes over rate plus a round trip term | the absolute times are underestimated by 15 to 50 percent, but the ML-KEM-768 minus P-256 difference is predicted within 15 percent (informed: Table 5 was read before writing) | difference error above 25 percent |

## Q3. Fleet planner (WP4, synthetic inputs, label estimated)

| ID | Question | Metric | Method | Prediction | Refuted if |
|---|---|---|---|---|---|
| Q3.1 | Is the planner monotone? | violations in property tests | more free RAM or flash, a newer updatable stage, or a shorter service life never yields a worse class | 0 violations | any violation |
| Q3.2 | Does it ever recommend an update that does not fit? | devices given FIRMWARE_UPDATE or HYBRID whose free RAM or free flash is below the stated need | property tests and fleets of 10, 100 and 1000 devices in five hardware classes | 0 | any |
| Q3.3 | Which input moves the fleet most? | share of the 1000 device fleet that changes class when one parameter moves by plus or minus 50 percent (years: plus or minus 2) | tornado sensitivity | a horizon year moves more devices than any memory threshold; the largest single swing is between 10 and 40 percent of the fleet | a memory threshold leads, or the largest swing is outside 10 to 40 percent |
| Q3.4 | What happens in a staged migration? | class counts per wave as the planning year moves from 2026 to 2030 and devices age | staged runs | UNKNOWN stays constant across waves; NO_ACTION_BEFORE_RETIREMENT never decreases | either fails |
| Q3.5 | Does it scale? | wall time to classify 1000 devices on the host | timing | under 2 s | 2 s or more |

## Q4. Emulated measurements (WP5, label emulated)

| ID | Question | Metric | Method | Prediction | Refuted if |
|---|---|---|---|---|---|
| Q4.1 | Does the code run on the Cortex-M33 model? | correctness checks on `mps2-an505` | QEMU, all six parameter sets | all pass | any failure |
| Q4.2 | Does the core change stack use? | stack high water mark, M33 versus M4, same compiler and flags | QEMU sweep | within plus or minus 10 percent for every operation | any operation outside 10 percent |
| Q4.3 | Does a newer compiler change the first round figures? | M4 stack and text size, current toolchain versus the committed 2026-10-12 results (gcc 13.2.1) | QEMU rerun | both within plus or minus 10 percent | any value outside 10 percent |
| Q4.4 | Does stack grow with the parameter set? | ordering of stack per operation | QEMU sweep | strictly increasing 512, 768, 1024 and 44, 65, 87 for every operation and both cores | any exception |
| Q4.5 | What does optimisation level do? | text size and stack at -Os and -O3 versus -O2 | QEMU sweep | -Os gives smaller text than -O2 for every image; stack changes by less than 15 percent | either fails |
| Q4.6 | Does a second emulator agree? | stack of the same ELF in Renode versus QEMU | Renode, one subset, only if it installs without a purchase | identical (0 B difference) | any difference |

## Q5. Host measured baseline (WP6, label host measured)

| ID | Question | Metric | Method | Prediction | Refuted if |
|---|---|---|---|---|---|
| Q5.1 | Is the host timing stable? | coefficient of variation of the per run median across 5 runs | warm up, then 5 runs of at least 200 iterations, median per run | below 3 percent for every operation | any operation at 3 percent or more |
| Q5.2 | How much dearer is signing than key exchange? | host median of ML-DSA-44 sign over ML-KEM-768 encaps | ratio of medians | between 5 and 30 | outside |
| Q5.3 | Do host ratios transfer to a microcontroller? | rank correlation of host medians with published pqm4 Cortex-M4 cycles for matching operations; largest relative difference between a host ratio and the matching pqm4 ratio | ratios only | ranks agree (Spearman at least 0.9) but at least one ratio differs by more than 30 percent | ranks disagree, or every ratio within 30 percent |

## Q6. Review

| ID | Question | Metric | Method | Prediction | Refuted if |
|---|---|---|---|---|---|
| Q6.1 | Are there unsupported claims left? | findings from a fresh reviewer that sees only the repository | review before the final push | at least 3 findings that need a fix or a recorded limit | fewer than 3 |
