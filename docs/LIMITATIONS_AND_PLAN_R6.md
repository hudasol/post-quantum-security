# Limitations after round 5 and the plan of round 6

Author: Huda Mueen. Written 2026-10-28, before any work of round 6. Sources of the list: the threats to validity of `docs/PAPER.md` (section 5), the end of round 5 scores of `docs/COMPLETENESS_RUBRIC.md`, the open items of `docs/NEEDS_FROM_AUTHOR.md` and the findings left open in `docs/REVIEW_FINDINGS5.csv`.

Aim of round 6: replace emulated or published figures with executed cryptography wherever free tools allow, compare the proposed design with real baselines measured under the same conditions, close the open replay rule question, and turn the study into a focused conference paper.

## 1. Limitations and what round 6 does about each

| # | Limitation after round 5 | Where it is stated | Round 6 action | What stays open |
|---|---|---|---|---|
| L1 | No cryptography was executed for the protocol. Handshake and per command costs are published cycle counts or emulated delays, and the classical baselines rest on rows read through a summarising fetch | threats 1, 15, 16 | Run the complete protocol code (classical baseline, post quantum only, hybrid session with F1, signature per command, MAVLink 2 signing tag) end to end on two open RISC-V core designs in cycle accurate RTL simulation, with correctness checks, cycles, stack and code size (label RTL simulated) | silicon measurement on a Cortex-M board (needs item 1) |
| L2 | The software in the loop configurations carried bytes and delays only, and enforced no replay rule | threat 15; rubric | A gateway in front of the flight stack executes the real handshake and per message tags with pinned libraries; compute delays come from the RTL cycles of L1 at a stated clock; strict next sequence rule, replay cache rule and the published rule run on paired seeds | real radio |
| L3 | Availability under the strict rule that the proofs use is not modelled | reference architecture; paper 4.6 | Add the strict rule and a replay cache rule to the mission model | none |
| L4 | Open design question: in order delivery or a replay window | paper 4.7 | Model a replay cache in ProVerif and check injective agreement | proofs stay abstract |
| L5 | Related work is a table of published rows, not a comparison of designs | rubric (evidence coverage) | Collect prior designs for post quantum authentication on drones, robots and constrained links with their reported numbers; compare in one table | numbers measured by others under other conditions |
| L6 | IEEE Xplore and ACM DL were not searched | threat 13 | Search the dblp index, which covers IEEE and ACM venues, with the round 5 queries | full text access |
| L7 | The paper is a six question study written as markdown, too broad for a six page venue | WP9 | A focused IEEE conference paper in LaTeX on the measured session layer, with an anonymised version and every number in the claims register | acceptance |
| L8 | Review passes did not converge, and every reader is internal | rubric (review depth) | A fourth pass of fresh reviewers on the round 6 work | external review |
| L9 | Nothing measured on a microcontroller or a radio | threats 1, 2, 3 | Not fixable without hardware; the board kit and predictions stay ready | needs items 1 and 6 |
| L10 | Flight logs, fleets and energy remain synthetic or datasheet based | threats 6, 7, 10 | Energy of the executed handshake is estimated from RTL cycles and cited currents, labelled estimated | measured energy |

## 2. Baselines

Every design is measured with the same code base, compiler, flags and core, so the comparison is fair inside this study:

1. **No authentication** (reference for latency and availability).
2. **MAVLink 2 signing as shipped**: a provisioned key and a SHA-256 based 6 B tag per message, no key exchange (the deployed classical baseline).
3. **Classical session**: X25519 key exchange with Ed25519 transcript signatures by both sides, then the same per message tag (a modern classical design of the same shape as the proposal).
4. **Post quantum only session**: ML-KEM-768 with ML-DSA-44 signatures by both sides.
5. **Hybrid session with F1 (proposed)**: X25519 plus ML-KEM-768, ML-DSA-44 signatures by both sides, key confirmation, then the same per message tag.
6. **ML-DSA-44 signature per command** (the obvious alternative that the study argues against).

Libraries are pinned and used as benchmark subjects only; no cryptographic primitive is written in this repository.

## 3. Order of work

1. Register the predictions of round 6 (`docs/PREDICTIONS_V6.md`, hashed) before any run.
2. RTL runs of the six baselines on Ibex and CV32E40P.
3. Mission model with the replay rules; ProVerif replay cache model; dblp search and related work, in parallel.
4. Software in the loop with executed cryptography, using the RTL cycles.
5. Conference paper, review pass, final checks.
