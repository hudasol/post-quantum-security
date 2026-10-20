# Protocol for round 5

Author: Huda Mueen. Written 2026-10-21 before any experiment of the round. Predictions: `docs/PREDICTIONS_V5.md` (hashed in `docs/PREDICTIONS_V5.md.sha256`). Completeness rubric: `docs/COMPLETENESS_RUBRIC.md`. Round 4 ended at commit `256d7c5`.

## Aim

Move the study from modelled to evidenced where free tools allow it. Round 4 ended at 5.7 of 10, with hardware evidence at 2, model validation at 4 and external validity at 5. This round tests the models against independent tools and real artefacts: memory use of real flight stack builds, a flight stack running in software in the loop, a network simulator, a formal protocol verifier and two more open cores. It also prepares a board session that can refute the cycle model. Nothing is measured on a microcontroller in this round.

## Research questions

The six questions of `docs/PROTOCOL_V4.md` are unchanged. RQ1 compute cost and its prediction; RQ2 energy and CPU headroom; RQ3 links and protocols; RQ4 signed boot and update; RQ5 fleet migration; RQ6 a feasible architecture and the follow on robotics project it justifies.

## Labels

Seven labels from round 4: published, host measured, emulated, estimated, modelled, RTL simulated, planned. Two labels are added in this round and defined here before first use:

| Label | Meaning | Never |
|---|---|---|
| simulated (network) | output of an established network simulator (ns-3 or Cooja) run by a script in this repository at a pinned version, with its configuration and seeds stored | presented as a measurement of a radio, or placed in one column with modelled values of `linksim/` |
| SITL measured | a timing or count taken from a flight stack running in software in the loop on the host, with the link emulated, at a pinned flight stack version | presented as a timing on flight hardware |

Board measured stays reserved for a session on a real board. Every result file of this round carries a `label` column, and files that hold several labels list a label for every column in `data/column_labels.csv`.

## Seeds

Round 5 uses seed `20261021` for every split, sample and Monte Carlo draw unless a script states another. Independent checks use separate seed blocks, stated per row.

## Work packages and acceptance tests

| Package | Output | Acceptance test |
|---|---|---|
| WP0 protocol, predictions, rubric start | this file, `docs/PREDICTIONS_V5.md`, rubric start block | committed and hashed before any experiment |
| WP1 flight stack memory and real workloads | `flightstack/`, `data/flightstack_memory.csv`, planner rerun, traffic from public flight logs | at least 5 board classes with measured free memory; planner rerun regenerates in CI; traffic statistics carry their flight count and a source per flight |
| WP2 software in the loop | `sitl/`, `docs/SITL_STUDY.md` | four configurations, at least 20 scripted missions each, seeds stored; error against the mission study stated |
| WP3 network simulator check | `netsim/`, `docs/NETSIM_STUDY.md` | validation table with errors per figure; the 802.15.4 gap explained by a simulated, cited cause or reported as a negative result; selective repeat closed form check with independent seed blocks |
| WP4 formal verification | `formal/`, `docs/FORMAL_VERIFICATION.md` | every listed property proved or a documented counterexample with the design change that removes it; tool versions pinned |
| WP5 statistics | `cyclemodel/` additions, `stats/`, `docs/STATISTICS_V5.md` | every interval in the paper recomputed with the cluster method; the paper states which conclusions change |
| WP6 systematic literature | `data/raw/S13_*`, `docs/SEARCH_PROTOCOL.md`, `docs/VERIFICATION6.md` | at least 150 new double read rows or a written account of why the literature does not hold them; flow diagram and query log regenerate; bibliography check passes |
| WP7 open cores and board kit | `rtlsim/` additions, `bench/board_kit/` additions | kit builds images for both boards; dry run parses 100 percent of emulator log lines for both cache passes; a test proves the cache off option is compiled in |
| WP8 shared inputs and reruns | `data/shared_inputs.csv`, reruns of every study | one parameter, one value, one source, enforced by a test; every document regenerates in CI |
| WP9 paper | `docs/PAPER.md`, `docs/PAPER.pdf` | every number in the claims register; a fresh reader finds no unsupported claim in the abstract |
| WP10 proposal pack | `docs/PROPOSAL_ROBOTICS*.md`, one page brief | every number traced to a claim; entity facts only by id |
| WP11 review | `docs/REVIEW_FINDINGS5.csv` | high and medium findings fixed or explained; up to three passes |
| WP12 close | scores, rubric, run log, PDFs, tag `round5` | CI green on the final commit |

## Cut order

From the first to cut to the last: the WP2 screen recording; Tamarin in WP4; VexRiscv in WP7; the hierarchical meta analysis in WP5 (the cluster bootstrap stays); the WP6 snowballing round. WP0, the WP1 memory measurement, the WP3 ns-3 check of the 802.15.4 gap, WP4 with ProVerif, the WP7 cache off option, WP8, WP11 and WP12 are never cut.

## Environment constraints known at the start

The run uses a Linux host with two cores and about 7 GB of memory. Builds of PX4, ArduPilot, ns-3 and the open cores are serialised so that at most two heavy jobs run at once. Third party code is fetched at pinned commits by scripts and never committed.
