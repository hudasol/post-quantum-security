# Fleet migration planner

Author: Huda Mueen

## Purpose

The planner reads an inventory of devices and assigns each one a migration class for post quantum cryptography. It implements `docs/PLANNER_RULES.md` exactly, using the reasoning of `docs/DECISION_FRAMEWORK.md`. It states UNKNOWN whenever required information is missing or unparseable, and it never guesses.

**It supports planning. It is not a security guarantee.**

The flash and RAM thresholds are lower bounds from published stack optimised pqm4 rows, excluding hashing and libc. A device that passes these thresholds may still lack the room it needs in practice, and a handshake time is an estimate from published sizes, not a measurement.

## Install and run

Python 3 and the standard library only. There is nothing to install. Run from the `planner` directory:

```
python -m fleetplan examples/synthetic_inventory.csv
python -m fleetplan INVENTORY.csv --format csv -o plan.csv
python -m fleetplan INVENTORY.csv --format json --explain
python -m fleetplan INVENTORY.csv --format md --today-year 2027 --hs-budget-s 120
```

Options:

| Option | Meaning |
|---|---|
| `--format table\|csv\|json\|md` | output format, default `table` |
| `--explain` | print every reason on its own line and the parameters with their tag and basis |
| `-o OUT` | write to a file instead of standard output |
| `--today-year N`, `--sig-horizon-year N`, `--conf-horizon-year N`, `--hs-budget-s N` | override the assumptions |
| `--sig-flash-kb`, `--sig-ram-kb`, `--kem-flash-kb`, `--kem-ram-kb`, `--hs-bytes` | override the derived constants |

The exit code is 0 on success and 2 for an unreadable or structurally invalid inventory or an invalid option.

Run the tests with `python -m unittest` from the `planner` directory.

## Input columns

Lines starting with `#` are comments. A comment line or a `notes` value containing SYNTHETIC marks the input as synthetic.

| Column | Required | Meaning |
|---|---|---|
| `device_id` | yes | label, must be unique and not blank |
| `ram_kb` | yes | total RAM, number not below 0 |
| `flash_kb` | yes | total flash, number not below 0 |
| `bootrom_verifier_updatable` | yes | `yes` or `no`: can the boot ROM verifier or fused trust anchor be changed after shipping |
| `link_bandwidth_bps` | yes | effective link rate in bit/s, must be greater than 0 |
| `service_life_remaining_years` | yes | years the device stays in service, number not below 0 |
| `data_lifetime_years` | yes | years its data must stay confidential, number not below 0 |
| `free_flash_kb`, `free_ram_kb` | no | headroom after the current firmware, must not exceed the total |
| `updatable_bootloader_stage` | no | `yes` or `no`: a replaceable second boot stage that can verify a PQ signature |
| `core`, `notes` | no | free text, never used for a decision |

A blank or `unknown` value is treated as not known. A value that is not a plain number (for example `abc`, `1e3`, `1,000`), a negative number, a zero bandwidth, or a yes/no field holding anything else is treated as unparseable. A free headroom figure larger than the matching total is contradictory and is treated as unparseable. The loader reports structural faults (missing required column, duplicate or blank `device_id`, wrong field count) with the line number and stops.

## Classes

| Class | Meaning |
|---|---|
| `FIRMWARE_UPDATE` | a firmware update can carry the PQ signature verifier and/or the hybrid KEM |
| `HYBRID` | signature: the classical root stays, the PQ verifier sits in the updatable bootloader stage, and an image is accepted only if both signatures verify. Confidentiality: the PQ session ends at a gateway and the classical hop stays on the device |
| `HARDWARE_REPLACEMENT` | headroom is insufficient, or the verifier cannot be changed at any stage |
| `NO_ACTION_BEFORE_RETIREMENT` | neither exposure applies before the device retires. This is a fifth class, a flagged deviation from the four requested classes (flag `FIFTH_CLASS_DEVIATION`) |
| `UNKNOWN` | required information is missing or unparseable. The fields are named in `missing_fields` |

## Output

The CSV columns are `device_id, class, reasons, missing_fields, handshake_s_estimate, flags`. In CSV and table output the reasons are joined with ` | ` and lists with `;`. In JSON they are arrays. The CSV also carries `#` comment lines for the banner, the summary counts, the notes and the footer, so skip lines starting with `#` when reading it with another tool.

Flags: `FIFTH_CLASS_DEVIATION`, `GATEWAY_REQUIRED` (HYBRID from rule 7), `HS_OVER_BUDGET` (the estimate exceeds the budget and the gateway conversion did not apply, so review by hand), `INVALID_OPTIONAL:<column>` (an optional value was present but unparseable and was not used).

Every output carries a `SYNTHETIC` banner when the input is marked, the summary count per class, the handshake label, the lower bound note, and the footer: "This tool supports planning. It is not a security guarantee."

## How decisions are explained

Every device has a list of reason strings. The first one is the deciding reason. Each string starts with the rule number it applies, for example `Rule 6: signature exposed, bootrom_verifier_updatable = no, updatable_bootloader_stage = yes and headroom is enough, so HYBRID ...`. The later reasons give the supporting facts: the exposure test (Rule 2), the need (Rule 4), the headroom test (Rule 5), and the handshake estimate (Rule 8), which is always labelled "estimated from published sizes, not measured". The table format prints the first reason, and `--explain` prints all of them.

## Rules in brief

1. A missing or unparseable required field gives UNKNOWN.
2. Signature exposed if `service_life_remaining_years` is strictly greater than SIG_YEARS. Confidentiality exposed if `data_lifetime_years` is strictly greater than CONF_YEARS. Equal is not exposed.
3. Neither exposed gives NO_ACTION_BEFORE_RETIREMENT.
4. The need is 31 kB flash and 3 kB RAM (signature), 14 kB and 9 kB (KEM), or 45 kB and 9 kB (both).
5. Headroom: a known `free_*` value is compared with the need (equal is enough). If it is not known and the total is already below the need, the need cannot be met. Otherwise the answer is UNKNOWN naming the `free_*` column.
6. Signature exposed: see the class table. A fixed boot ROM verifier with a blank `updatable_bootloader_stage` gives UNKNOWN.
7. Only confidentiality exposed: enough headroom gives FIRMWARE_UPDATE, otherwise HARDWARE_REPLACEMENT. A FIRMWARE_UPDATE whose handshake time `HS_BYTES * 8 / link_bandwidth_bps` exceeds `HS_BUDGET_S` becomes HYBRID.
8. Every result carries a reason and the labelled handshake estimate.

Two small points where the rules leave room: when both exposures apply, the gateway conversion of rule 7 is not applied (the rule covers only the confidentiality case), and the device is flagged `HS_OVER_BUDGET` instead. For the combined need, RAM is the larger of the two RAM figures, because the two verifications run one after the other. With the defaults this is 9 kB, the same as the rules.

## Assumptions

Copied from `docs/PLANNER_RULES.md`. A tag [assumption] marks a choice of mine that is editable on the command line. A tag [derived] marks arithmetic on a published row of `data/evidence.csv`.

| Name | Default | Tag | Basis |
|---|---|---|---|
| `today_year` | 2026 | [assumption] | date of this work |
| `sig_horizon_year` | 2030 | [assumption] | EU roadmap v1.1: products with market life beyond 2030 should have PQ signed firmware updates (data/raw/S1 row 39) |
| `conf_horizon_year` | 2035 | [assumption] | NCSC, EU, IR 8547 draft end dates (S1 rows 15, 33, 37) |
| `SIG_YEARS` | sig_horizon_year - today_year = 4 | [derived] | |
| `CONF_YEARS` | conf_horizon_year - today_year = 9 | [derived] | |
| `SIG_FLASH_KB` | 31 | [derived] | ML-DSA-44 verify code 24,844 B (S2-0036) plus 5,288 B wolfBoot example header (S3 4.2) = 30,132 B, rounded up. Excludes hashing and libc. Lower bound. |
| `SIG_RAM_KB` | 3 | [derived] | ML-DSA-44 verify stack 2,712 B (S2-0036), rounded up |
| `KEM_FLASH_KB` | 14 | [derived] | ML-KEM-768 code 13,320 B (S2-0027), rounded up |
| `KEM_RAM_KB` | 9 | [derived] | ML-KEM-768 decaps stack 2,844 B (S2-0027) plus buffers 6,004 B (FIPS sizes: 1184 + 1088 + 1312 + 2420) = 8,848 B, rounded up |
| `HS_BYTES` | 6068 | [derived] | hybrid handshake bytes: 2 x 32 B X25519 + 1184 + 1088 + 1312 + 2420 |
| `HS_BUDGET_S` | 300 | [assumption] | longest tolerable in band handshake |

Both exposures combined need `SIG_FLASH_KB + KEM_FLASH_KB = 45` kB flash and `KEM_RAM_KB = 9` kB RAM.

## Limits

- The thresholds are lower bounds from published stack optimised pqm4 rows, excluding hashing and libc. Real needs are higher.
- The handshake time is estimated from published sizes, not measured. It ignores latency, retransmission, processing time and link protocol overhead.
- The planner reads only the columns above. It does not know about secure elements with fixed algorithm sets, supply chain constraints, signer state management, or any property of the device not in the inventory.
- Dates and horizons are assumptions that follow standards that were still in flux when the rules were written. Change them on the command line when the guidance changes.
- The bundled example is SYNTHETIC. It is invented for testing and is not a real fleet.
- The CSV reader handles one record per line and does not accept quoted line breaks.

## Statement

This tool supports planning. It is not a security guarantee.
