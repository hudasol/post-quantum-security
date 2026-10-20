# Predictions for the fifth study round (written before any run)

Author: Huda Mueen. Written 2026-10-21, before any experiment of this round was run. The SHA-256 of this file as committed is in `docs/PREDICTIONS_V5.md.sha256`. This file is never edited after the hash is taken; corrections go in a dated note in `docs/RUN_LOG.md`. Scores are written by script into `docs/PREDICTIONS_V5_SCORES.md`.

What I already knew when writing: everything committed up to `256d7c5`, including the round 4 results, the mission study (hybrid session availability 0.992 on the SiK radio, about 380 ms added per command with a signature per command), the link model (7.1 s for a 50 kB 802.15.4 transfer against a published 30 to 60 s), the profile fleet (median replacement share 0.201) and the review finding that Owens et al. publish a 168 MHz Ed25519 verify row of about 760 kilocycles. Predictions marked informed rest on that knowledge.

Seeds: seed `20261021` unless a script states another.

## Verdicts (defined before any scoring)

| Verdict | Definition |
|---|---|
| hit | the prediction holds on the registered metric |
| miss | the refutation clause is met on the registered metric |
| between | the metric was computed as registered, and neither the prediction nor the refutation clause holds |
| not scored | the registered metric could not be computed as registered (a tool, source or input was unavailable); the reason is stated, and any value computed another way is reported for information only |

## Predictions

| ID | Package | Question | Metric | Prediction | Refuted if |
|---|---|---|---|---|---|
| P1 | WP1 | How many board classes get measured free memory? | board classes of `data/reference_profiles.csv` with free flash and RAM from a real flight stack build | at least 5 | fewer than 3 |
| P2 | WP1 | How much flash does a flight stack leave free? | median free flash share over measured targets | at least 0.25 | below 0.10 |
| P3 | WP1 | How much RAM does a flight stack leave free (static allocation from the build)? | median free RAM share over measured targets | at least 0.30 | below 0.10 |
| P4 | WP1 | Does measured free memory change the fleet answer? | absolute change of the profile fleet median replacement share against round 4 (0.201), stack optimised thresholds | below 0.05 | above 0.10 |
| P5 | WP1 | Does the F4 class flight controller fit a post quantum signer and KEM beside its flight stack? | planner decision for the STM32F405 class with measured free memory | needs hardware replacement or a hybrid, not a plain firmware update | firmware update fits |
| P6 | WP1 | How many public flight logs are processed? | flights with derived statistics | at least 50 | fewer than 20 |
| P7 | WP1 | How often are commands sent in real flights? | median over flights of vehicle commands per second | below 1 per second | above 5 per second |
| P8 | WP1 | Does real traffic change the mission result? | absolute change of hybrid session availability on the SiK radio, drone, against round 4 (0.992) | below 0.02 | above 0.05 |
| P9 | WP2 | Do the scripted SITL missions run? | completed scripted missions per configuration | at least 20 for each of the four configurations | fewer than 10 for any configuration |
| P10 | WP2 | What does MAVLink 2 signing cost on the host? | median added command latency of signing against no authentication | below 1 ms | above 5 ms |
| P11 | WP2 | How long does a hybrid session handshake take over an emulated SiK class link? | median handshake time | between 0.5 and 3 s | below 0.2 s or above 5 s |
| P12 | WP2 | Does a signature per command cost what the mission study says? | median added command latency against no authentication, emulated SiK class link | within a factor of 2 of the mission study figure | outside a factor of 3 |
| P13 | WP2 | Does SITL agree with the mission study on availability? | absolute difference of command availability, hybrid session, SiK class link | below 0.05 | above 0.10 |
| P14 | WP3 | Is a single hop 802.15.4 transfer in ns-3 as optimistic as the link model? | ns-3 time for 50 kB at one hop against the link model (7.1 s) | within 30 percent of the link model | inside the published 30 to 60 s at one hop |
| P15 | WP3 | What explains the 802.15.4 gap? | smallest hop count at which ns-3 reaches 30 s | 3 or more | 1 |
| P16 | WP3 | Do ns-3 and the link model agree on LoRaWAN? | absolute percent difference of the DR5 hybrid handshake time | at most 20 percent | above 50 percent |
| P17 | WP3 | Does the selective repeat code agree with its closed form? | closed form inside the 95 percent interval of the link simulator at every tested loss rate, independent seed blocks | at every rate | outside at any rate |
| P18 | WP3 | Do ns-3 and the time on air formula agree for LoRa? | largest absolute percent difference over the tested frame sizes | at most 1 percent | above 5 percent |
| P19 | WP4 | Does the session design keep keys secret and commands authentic? | ProVerif result for session key secrecy and injective agreement on commands | both proved | a counterexample to either |
| P20 | WP4 | Does the first model of the design survive formal checking? | properties that fail on the first model as written from `docs/REFERENCE_ARCHITECTURE.md` | at least one fails and needs a design change | none fails |
| P21 | WP4 | Is firmware downgrade rejected? | ProVerif result for downgrade rejection with a monotonic version counter, and without it | proved with the counter, counterexample without | proved without the counter, or a counterexample with it |
| P22 | WP4 | Does rekey give forward secrecy? | ProVerif result for secrecy of earlier session keys after compromise of long term keys, with a fresh KEM per rekey | proved | counterexample |
| P23 | WP5 | How well does the cycle model transfer across implementation families? | median absolute error, leave one implementation family out | above 5 percent | below 2 percent |
| P24 | WP5 | How wide is an honest interval for the held out error? | upper bound of the cluster bootstrap 95 percent interval of the median absolute error | at least 2.5 percent | at or below 1.7 percent (the row bootstrap value) |
| P25 | WP5 | What drives the spread of published cycle counts? | factor with the largest share of variance in the hierarchical model | implementation variant | source or statistic |
| P26 | WP5 | How many wording fields were wrong in staging? | wrong share over all wording disagreements after a third look | between 5 and 15 percent | below 2 or above 25 percent |
| P27 | WP5 | What matters most for the final answer? | input with the largest total Sobol index for hybrid session availability in the end to end chain | a link parameter (loss or outage) | a cycle count |
| P28 | WP6 | How many new rows survive two readers? | new rows added after double reading | at least 150 | fewer than 75 |
| P29 | WP6 | Are there final standard SLH-DSA cycle rows on microcontrollers? | sources with FIPS 205 SLH-DSA cycle counts on a microcontroller | at least 1 | none |
| P30 | WP6 | How accurate are new rows after two readers? | staged rows with a wrong value before adjudication | at most 5 percent | above 10 percent |
| P31 | WP6 | How much do flash wait states cost Ed25519 verify? (informed) | Owens et al. 168 MHz verify cycles over 24 MHz verify cycles | between 1.0 and 1.2 | above 1.5 |
| P32 | WP7 | How much does the core design move the cost? | largest over smallest ML-DSA-44 verify cycles across the open cores simulated | between 1.2 and 3 | below 1.1 or above 5 |
| P33 | WP7 | Is CV32E40P faster than Ibex in its small configuration? | ML-KEM-768 decapsulation cycles, CV32E40P against Ibex | CV32E40P fewer cycles | CV32E40P more cycles |
| P34 | WP7 | Is the board kit ready for an M33 board and a cache off pass? | images built for the M33 board and the share of emulator log lines parsed for both cache passes | images build and 100 percent parse | any image fails or any line fails to parse |
| P35 | WP8 | Do shared inputs change the reference architecture? | recommended designs for firmware and commands after all reruns | unchanged (LMS for firmware, hybrid session for commands) | either changes |
| P36 | WP11 | What does the first review pass find? | findings in the first pass | at least 20 | fewer than 10 |
| P37 | WP11 | Does a second pass find a high severity problem? | high severity findings in the second pass | none | at least one |
| P38 | WP12 | Does the completeness score rise? | weighted rubric score, start against end of round 5 | rises by at least 1.0 | rises by less than 0.5 |
