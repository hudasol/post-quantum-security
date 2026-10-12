# Fleet planner rules

These rules turn `docs/DECISION_FRAMEWORK.md` into a deterministic classification. They support planning. They are not a security guarantee. Every threshold below is tagged **[assumption]** (my choice, editable on the command line) or **[derived]** (arithmetic on a published row of `data/evidence.csv`).

## Inputs

Required columns (a blank, `unknown` or unparseable value in any of them gives UNKNOWN):

| Column | Meaning |
|---|---|
| `device_id` | label |
| `ram_kb` | total RAM |
| `flash_kb` | total flash |
| `bootrom_verifier_updatable` | `yes` or `no`: can the immutable boot ROM verifier or fused trust anchor be changed after shipping |
| `link_bandwidth_bps` | effective link rate in bit/s (must be greater than 0) |
| `service_life_remaining_years` | years the device stays in service |
| `data_lifetime_years` | years its data must stay confidential |

Optional columns (a blank means "not known"):

| Column | Meaning |
|---|---|
| `free_flash_kb`, `free_ram_kb` | headroom after the current firmware |
| `updatable_bootloader_stage` | `yes` or `no`: a second boot stage that can be replaced by a firmware update and can verify a PQ signature |
| `core`, `notes` | free text, never used for a decision |

Lines starting with `#` are comments. The example inventory is labelled SYNTHETIC.

## Parameters

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

Both exposures combined need `SIG_FLASH_KB + KEM_FLASH_KB = 45` kB flash and `KEM_RAM_KB = 9` kB RAM (the two run one after the other).

## Algorithm

1. **Missing required field**: UNKNOWN, listing the fields.
2. `sig_exposed = service_life_remaining_years > SIG_YEARS`. `conf_exposed = data_lifetime_years > CONF_YEARS`. Strictly greater: exactly equal is not exposed.
3. Neither exposed: **NO_ACTION_BEFORE_RETIREMENT** (a fifth class I added; flagged deviation from the four requested classes).
4. Needs: flash and RAM per the exposure (signature only, KEM only, or both).
5. **Headroom test.** If `free_*` is known, compare it to the need. If it is unknown: when total `flash_kb` or `ram_kb` is already below the need, the need cannot be met (insufficient); otherwise the answer is UNKNOWN naming the missing `free_*` column. Never guess.
6. If `sig_exposed`:
   - `bootrom_verifier_updatable = yes`: enough headroom gives **FIRMWARE_UPDATE**, insufficient gives **HARDWARE_REPLACEMENT**.
   - `bootrom_verifier_updatable = no`: look at `updatable_bootloader_stage`. `yes` and enough headroom gives **HYBRID** (classical root stays, the PQ verifier in the updatable stage, accept an image only if both verify). `yes` with insufficient headroom, or `no`, gives **HARDWARE_REPLACEMENT**. Blank gives UNKNOWN.
7. If only `conf_exposed`: enough headroom for the KEM gives **FIRMWARE_UPDATE**; insufficient gives **HARDWARE_REPLACEMENT**. If handshake time `HS_BYTES * 8 / link_bandwidth_bps` exceeds `HS_BUDGET_S`, a FIRMWARE_UPDATE result becomes **HYBRID** (terminate the PQ session at a gateway, keep the classical hop on the device) and the reason says so.
8. Every result carries a reason string and the estimated handshake time labelled "estimated from published sizes, not measured".
