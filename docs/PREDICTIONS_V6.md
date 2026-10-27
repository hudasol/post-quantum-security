# Predictions for round 6

Author: Huda Mueen. Written 2026-10-28, before any run of round 6, and hashed in `docs/PREDICTIONS_V6.md.sha256`. Scored by script after the runs; misses stay. Verdicts: hit when the prediction holds; miss when the refutation clause is met; between when neither holds; not scored when the metric could not be computed as registered, with the reason. When a clause is ambiguous the less favourable reading is used and named.

What I already knew when writing: everything committed up to `9cc1744`, including the round 5 RTL cycles of mlkem-native and mldsa-native on Ibex and CV32E40P (for example ML-DSA-44 sign about 9.4 million cycles and verify about 3.9 million on CV32E40P), the SITL results with emulated compute (hybrid handshake median 1.28 s; acknowledged share 0.914 with outages) and the mission study under the published replay rule.

"Vehicle side handshake" means all computation the vehicle performs in one session start of the design, measured in one RTL run with a correctness check that both sides derive the same key. "Core" means Ibex (small configuration) and CV32E40P as configured in round 5.

| ID | Package | Question | Metric | Expected | Refuted if |
|---|---|---|---|---|---|
| Q1 | RTL | How does one X25519 scalar multiplication compare with ML-KEM-768 encapsulation on the same core? | cycles of one X25519 scalar multiplication divided by cycles of ML-KEM-768 encaps, CV32E40P | at least 1 | below 0.5 |
| Q2 | RTL | What does the vehicle side of the hybrid handshake with F1 cost? | vehicle side handshake cycles, CV32E40P | 12 to 35 million | below 6 million or above 70 million |
| Q3 | RTL | How much more does the hybrid handshake cost than a classical session of the same shape? | vehicle side hybrid cycles divided by vehicle side classical (X25519 plus Ed25519) cycles, CV32E40P | at most 4 | above 8 |
| Q4 | RTL | Does the core order hold for whole handshakes? | Ibex cycles divided by CV32E40P cycles, vehicle side hybrid handshake | between 1.2 and 1.6 | below 1.0 or above 2.0 |
| Q5 | RTL | What does the per message tag cost? | cycles of one MAVLink 2 signing tag over a 60 byte message, CV32E40P | below 20 thousand | above 100 thousand |
| Q6 | RTL | What stack does the hybrid handshake need? | peak stack of the vehicle side hybrid handshake | below 100 kB | above 150 kB |
| Q7 | RTL | How large is the hybrid code? | text size of the hybrid image divided by the classical image | at least 2 | below 1.2 |
| Q8 | SITL | Does executing the cryptography change the handshake time? | median hybrid handshake time with executed cryptography against 1.28 s (round 5, emulated) | within 30 percent | outside 50 percent |
| Q9 | SITL | What does the strict next sequence rule cost? | drop of the hybrid share of commands acknowledged within 0.5 s, outages included, strict rule against the published rule on paired seeds | at most 0.05 | above 0.10 |
| Q10 | SITL | Does a replay cache recover what the strict rule loses? | absolute difference of that share, replay cache rule against the published rule on paired seeds | at most 0.02 | above 0.05 |
| Q11 | Mission | Does the strict rule lower modelled availability? | drop of mean availability, drone, SiK, architecture B, strict rule against the published rule | at most 0.02 | above 0.05 |
| Q12 | Formal | Is a replay cache rule safe in the model? | injective agreement on commands with a seen counter table in ProVerif | proved | counterexample |
| Q13 | Search | Does an index of IEEE and ACM venues add sources? | records from the dblp search not seen in the round 5 screening that pass title screening | at least 5 | none |
| Q14 | Paper | Does the focused paper fit the venue? | pages of the IEEE format paper without references, as compiled | at most 6 | above 7 |
