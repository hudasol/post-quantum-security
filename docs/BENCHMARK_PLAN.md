# Hardware benchmark plan: PQC on Cortex-M4 / M33 boards

Author: Huda Mueen (plan drafted 2026-10-11). Status: **plan only; nothing in this file has been measured on a microcontroller.**
Labels used throughout: **published** (copied from a retrieved source, in `data/evidence.csv`), **host-measured** (run in the research sandbox on an x86 server, never comparable to an MCU), **estimated/derived** (my arithmetic, formula shown), **planned** (to be measured by you).

## 1. Why this plan exists

The published evidence has holes that only your own boards can fill (details in REPORT section 6):

1. There are no published ML-KEM, ML-DSA or SLH-DSA cycle counts for a *named* Cortex-M33 core.
2. The only maintained benchmark with final ML-KEM/ML-DSA names on Cortex-M4F (pqm4) does not name its board, quotes a 24 MHz clock whose board code path actually uses 20 MHz, and is scheduled to be archived read-only in or after January 2027.
3. There are no published *measured* energy figures for final ML-KEM/ML-DSA on a Cortex-M.
4. There are no published final-parameter LMS or SLH-DSA cycle counts on a Cortex-M.
5. There are no published numbers from a flight-controller-class part (for example an STM32H7 on a Pixhawk).

## 2. Questions and what would answer them

| Id | Question | Primary metric | Experiment |
|---|---|---|---|
| Q1 | What does ML-KEM-768 cost (cycles, stack, flash) on an M4F and on an M33 at the same clock, with the same C library? | median cycles; stack bytes; `.text` delta | E1 |
| Q2 | What does ML-DSA-44/65/87 verification (the firmware-signing operation) cost, and how long is the tail of ML-DSA signing? | median and p95/p99 cycles | E1 |
| Q3 | What does hash-based firmware-signature verification (LMS/HSS, XMSS, SLH-DSA) cost with final parameters? | median cycles; image-header bytes | E2 |
| Q4 | What is the energy per operation, net of the idle baseline? | uJ per operation | E3 |
| Q5 | How much boot time does a post-quantum image check add to a bootloader? | ms from reset to jump | E4 |
| Q6 | How long does it take to move a PQ signature or a hybrid handshake over a real telemetry radio? | seconds, retransmissions | E5 |

Pre-stated expectations (so you can tell afterwards whether the result was a surprise; these are hypotheses, not findings): verification of ML-DSA is much cheaper than signing; hash-based verification is cheapest in code size but largest in signature bytes; none of the above fits MAVLink's 13-byte signature field. Report the outcome even if a hypothesis fails.

## 3. Hardware and approximate cost

Prices are single-unit list prices that seller pages showed on 2026-10-11 (shipping, tax and currency conversion not applied; the ST eStore string "$33.61|2u" is reproduced from the page and I do not know what "|2u" means). Specs are from Zephyr board docs and the pqm4 README (secondary), because st.com and nordicsemi.com did not load from the sandbox.

| Role | Item | Core / clock (secondary source) | Approx. price | Notes |
|---|---|---|---|---|
| M4F reference | NUCLEO-L4R5ZI | Cortex-M4F, up to 120 MHz; 2 MB flash, 640 KB SRAM | $33.61 (ST eStore) | pqm4's default platform. Lets you reproduce pqm4 rows before trusting your harness. |
| M33 primary | NUCLEO-U575ZI-Q | Cortex-M33 with FPU and TrustZone, up to 160 MHz; 2 MB flash, ~786 KB SRAM | $26.35 (ST eStore) | First M33 target. |
| M33 bigger (optional) | NUCLEO-H563ZI | Cortex-M33, up to 250 MHz; 640 KB SRAM | $43.50, showed "Out of Stock" | The wolfBoot STM32H5 boot-time figures use an STM32H563. |
| M33 cheapest | Raspberry Pi Pico 2 | dual Cortex-M33, up to 150 MHz; 520 kB SRAM | $5.75 to $6.25 (SparkFun, Adafruit), GBP 4.00 to 4.80 (Pimoroni, The Pi Hut) | Needs an external SWD probe (price not retrieved). |
| Cheap M4F cross-check | NUCLEO-L476RG or NUCLEO-F439ZI | Cortex-M4F | $20.94 or $34.13 | Second M4F so one board's quirks do not become "the result". |
| Energy (entry) | Nordic Power Profiler Kit II | 100 ksps; resolution 100 nA to 1 mA by range (Adafruit text) | $99.95 (Adafruit) | Digital inputs let a GPIO mark each operation. |
| Energy (high-end, optional) | Joulescope JS320 | 1 Msps, 0.1 nA resolution (vendor page) | $999 | Only if a lab already owns one. |
| Do NOT use for per-op energy | INA219 ($9.95), INA228 ($14.95) | conversion 50 us to 4.12 ms (INA228) | n/a | Too slow to resolve one sub-millisecond operation; usable only with the loop method in section 6. |
| Flight-controller class (later) | Pixhawk 6C (STM32H743, Cortex-M7, 480 MHz) | M7 | $199.00 (Holybro) | Different core family: never share an axis with M4/M33. |

Minimum useful budget: U575ZI-Q + L4R5ZI + PPK2 is about $160 at the listed prices; Pico 2 adds about $6 plus a probe.

## 4. Pinned software (commits read on 2026-10-11)

| Component | Version pin | Licence | Used for |
|---|---|---|---|
| mlkem-native | tag `v2.0.0`, commit `d1b2fe782888bdb761a50336012923180be7f502` | Apache-2.0 OR ISC OR MIT | ML-KEM, E1 |
| mldsa-native | tag `v2.0.0`, commit `834a90d5e846ffa1e1611bd24e160bb2e9b86d35` | Apache-2.0 OR ISC OR MIT | ML-DSA, E1 |
| wolfSSL / wolfCrypt | tag `v5.9.4-stable`, commit `3c5eead44904df64e6a5a1f4ebdce377d35a849a` | GPLv3 (commercial licence exists) | LMS, XMSS, SLH-DSA, ML-DSA cross-check, E2 |
| wolfBoot | tag `v2.10.0`, commit `eb710fe1656f20addb736b5c205f18bf53fa2998` | GPLv3 | boot-time experiment, E4 |
| TF-PSA-Crypto (Mbed TLS crypto) | tag `v1.2.0`, commit `73c5da561c8e5253db7b1fb440eda86fde8d8024` | Apache-2.0 OR GPL-2.0-or-later | LMS verification, E2 |
| slhdsa-c | `main` at `174c02e42257f95c210963272877c49dbb50070f`, no tags | ISC | SLH-DSA cross-check only: its README says not to rely on it in production |
| pqm4 (reference only) | `5e5cc76d0b072ee7077e58afcbc619a1a67a53b4` (README notice: to be archived read-only in or after Jan 2027) | per-implementation | reproduce published rows; Cortex-M4 only |
| Toolchain | Arm GNU Toolchain 11.3.Rel1 (the version pqm4 documents) for comparability; a second pass with a current toolchain if you wish | n/a | record `arm-none-eabi-gcc --version` in the log |

`bench/mcu/fetch_libs.sh` enforces the E1 pins; `./fetch_libs.sh e2` enforces the wolfSSL/wolfBoot/TF-PSA-Crypto pins. Pin by commit, not by branch: PQClean is retired, pqm4 will be archived.

## 5. Measurement method

### 5.1 Cycle counting
- Use the DWT cycle counter `CYCCNT` (32-bit, wraps). Enable `TRCENA` in `DEMCR`, write `DWT->CYCCNT = 0`, set `CYCCNTENA`. On Cortex-M7 unlock via the lock-access register first. The enable sequence matches the mlkem-native test HAL for Cortex-M33.
- Cortex-M0+ (RP2040) has no DWT cycle counter; do not use it with this harness.
- pqm4 itself uses SysTick (24-bit, overflow counted in an ISR), not DWT. Your numbers are comparable to pqm4's only after you state this difference; expect a small offset from the overflow ISR.
- Self-check the counter once per board: time a loop of known instruction count and compare.
- Timed region = the library call only. Print after the region. Interrupts off inside the region.

### 5.2 Clock and flash wait states
Fix the core clock and flash latency, print both in `META`. pqm4 takes numbers at a low clock to avoid wait states (its F4 code uses 24 MHz with 0 wait states; its L4R5ZI code path uses 20 MHz). Run **Pass A** at a clock where flash runs with 0 wait states and caches/prefetch state recorded, and optionally **Pass B** at the board's full clock. Report cycles for both passes in separate columns; never average across them.

### 5.3 Memory
- **Stack**: stack painting (`stack_paint.h`): fill a span below SP with a pattern, run the operation, find the deepest overwritten word. Set `BENCH_STACK_SPAN` from your linker map; result `-2` means too small. ISRs add to the figure: keep them off.
- **Flash / code size**: image size with the library minus a baseline image without it (`.text` + `.rodata` from `arm-none-eabi-size` or the map file), with `--gc-sections`. State the compiler flags.
- **Static RAM** (`.data`+`.bss`): from the same size output. Report static RAM and stack separately; "RAM" as a single figure is ambiguous (published sources define it differently: pqm4 excludes caller-provided buffers).
- Library options that trade RAM for speed (mldsa-native `MLD_CONFIG_REDUCE_RAM`) are separate rows with the option named.

### 5.4 Randomness
The timed region uses deterministic derandomised APIs, so the TRNG is not in it. Measure TRNG cost separately on each board: time to draw 32 bytes from the hardware RNG, 1,000 repetitions, report median. Key generation in the field also needs that entropy; state it beside the keygen cycles.

### 5.5 Inputs
Fixed 59-byte message length (the length pqm4's signature tests use). For ML-DSA signing use a different message each iteration (the harness derives them from a fixed seed) so the rejection loop sees varied data. Publish the seed. Use at least 1,000 sign iterations for the tail statistics (section 7).

## 6. Energy measurement method

1. Power the board's MCU rail through the instrument (PPK2 ampere-meter mode); declare the **measurement point** (whole board vs MCU-only jumper such as the IDDMCU header, where the board has one) and the supply voltage. Remove or disable LEDs and the on-board debugger's contribution if the board allows; otherwise report that it is included.
2. Firmware raises a GPIO high for the duration of one operation (or `K` back-to-back operations). Wire it to the instrument's digital input.
3. Idle baseline: the MCU spinning in the same clock configuration with the GPIO low. Net energy = gross - baseline.
4. If the instrument cannot resolve one operation (any I2C monitor), run the operation `K` times inside one marker window and divide by `K` (`--ops-per-window` in `bench/power/analyze_power.py`).
5. Analyse with `bench/power/analyze_power.py` (energy by trapezoid rule, median, quartiles, seeded bootstrap CI). **That script has been tested only on synthetic traces** (`make_synthetic.py`), where it reproduces the known energy to within 0.15% (discretisation of the window to whole samples); it has not been run on a real instrument.
6. Report energy as uJ/op net and gross, rail voltage, instrument, sampling rate, ambient temperature, and number of windows.

## 7. Statistical treatment

- Unit of replication = **a power cycle** (cold start of the board). Take at least **3 power cycles**, each with at least 100 iterations per operation (1,000 for ML-DSA signing). The run-to-run spread of medians across power cycles is reported next to the within-run spread.
- Report **median, 5th/25th/75th/95th/99th percentiles, min, max, n**; the mean only as a convenience and never for ML-DSA signing. Rationale: ML-DSA signing uses rejection sampling, so its time is data-dependent; one retrieved source (Riou et al., ePrint 2026/1333, abstract only; body not read) argues that min/average/max are unsuitable for migration planning, and pqm4's own file shows a large spread (published ML-DSA-44 `m4f` sign: mean 3,943,121, min 1,812,557, max 17,009,165 cycles, per S5 notes of `benchmarks.md`). Host self-test data from this harness shows the same shape (ML-DSA-44 sign, host: max/median 7.76).
- 95% confidence interval of the median by seeded percentile bootstrap (B = 10,000, resampling iterations, seed recorded), implemented in `bench/stats/analyze_runs.py`.
- For comparisons (M33 vs M4F, library A vs B) report the **ratio of medians with a bootstrap CI**; do not run significance tests on thousands of non-independent iterations. A difference is "reportable" only if the CIs from at least 3 power cycles do not overlap.
- Observed maximum is **not** a worst-case execution time. If you need a bound (flight code), say it is an observed maximum over `n` iterations and consider mldsa-native's restartable-signing example, which exists for bounding runtime in real-time systems.
- Discard nothing silently. If an iteration is dropped (for example failed check), log why. A failed correctness check invalidates the run.

## 8. What to report (one row per board x library x parameter set x operation)

`board, core, clock_mhz, flash_wait_states, cache_state, library, commit, compiler+version+flags, op, n_runs(power cycles), n_iters, cycles_median, cycles_p05, p25, p75, p95, p99, max, ci95_median, stack_bytes, static_ram_bytes, code_bytes_delta, key/sig/ct sizes, trng_cycles, energy_net_uJ, energy_gross_uJ, rail_V, instrument` and a `notes` column. Use the same column names as `data/evidence.csv` where they exist and set `evidence_type=measured-by-author`. Keep your rows **in a separate file** from the published rows.

## 9. Experiments (ordered; do E1 first)

### E1: ML-KEM and ML-DSA cycles, stack, flash (the first experiment)
Boards: NUCLEO-U575ZI-Q (M33) and NUCLEO-L4R5ZI (M4F). Library: mlkem-native and mldsa-native v2.0.0 via `bench/mcu`. Parameter sets: ML-KEM-768 and ML-DSA-44 first; then 512/1024 and 65/87.
Steps: (1) `./fetch_libs.sh`; (2) bring up UART printf on the board; (3) counter self-check; (4) Pass A at a 0-wait-state clock; (5) three power cycles; (6) `analyze_runs.py`; (7) baseline-subtracted code size; (8) compare L4R5ZI numbers against the published pqm4 ML-KEM-768/ML-DSA-44 rows (`S2-0022..0027`, `S2-0031..0036`) only as a sanity check on the same core family, noting different library and different counter.
Pass criteria: all CHECK lines have zero failures; run-to-run CV of median below 1% for ML-KEM (if not, find the cause before publishing).

### E2: hash-based firmware-signature verification (specification only; no harness written)
Goal: final-parameter cycles and image-header bytes for LMS/HSS (SHA-256), XMSS, SLH-DSA verification on the same two boards. Routes found: wolfCrypt (`--enable-lms`, `--enable-xmss`, `--enable-slhdsa`, `--enable-mldsa`; v5.9.4-stable), TF-PSA-Crypto v1.2.0 (LMS verify only, `MBEDTLS_LMS_C`), wolfBoot v2.10.0 (image signing with ML-DSA, LMS/HSS, XMSS/XMSS^MT). Create the test signatures **off-device on a build machine** with the library's own tools; the device only verifies. Do not enable any "hazardous" key-generation option on a machine whose state you cannot control (a stateful key must never sign twice; see SP 800-208 and RFC 10033). Parameters to test: LMS H10/W8 (1-level) and HSS 2-level H5/W8 (wolfBoot example config: 2644-byte signature), XMSS-SHA2_10_256 (2500-byte signature), SLH-DSA-SHA2-128s and 128f. Record cycles, stack and code size exactly as in E1.
Why spec-only: the research found no published final-parameter MCU numbers and this plan did not build a harness for them; a harness would have been untestable without hardware.

### E3: energy per operation
Repeat the E1 operations ML-KEM-768 decaps, ML-DSA-44 verify, ML-DSA-44 sign under the PPK2 with the section 6 method. Net uJ per operation and, for sign, the distribution (not just a mean). Cross-check by the loop method on one operation.

### E4: boot-time impact
Build wolfBoot v2.10.0 for the U575 (listed target STM32U5) with (a) Ed25519 or ECDSA P-256 baseline, (b) LMS/HSS, (c) ML-DSA-44, (d) hybrid ECC+ML-DSA. Measure from reset to application entry with a GPIO edge and a logic analyser or the PPK2 digital input, 30 boots per configuration. Published comparison point for orientation only: wolfSSL's STM32H563 post reports total boot times with a SHA2-only baseline of 55.662 ms and an LMS 1-10-8 total of 207.703 ms at 320 MHz (vendor blog; boot time, not pure verification; setup not comparable to yours).

### E5: link-level transfer (planned, needs radios)
With two SiK-class telemetry radios at their 64 kbps default air rate and, if available, a LoRa module, send the byte counts of ML-DSA-44/65/87 signatures and an X25519MLKEM768 handshake (1216 + 1120 bytes of key shares, per RFC 10024) in MAVLink FILE_TRANSFER_PROTOCOL-sized chunks (239 data bytes) and measure completion time and retransmissions under controlled packet loss. The arithmetic estimate to compare against is in REPORT section 5.4 (derived, not measured).

## 10. Threats to validity

- **Board and clock ambiguity** in the published baseline; mitigate by reproducing pqm4 rows on the L4R5ZI.
- **Different counters** (DWT vs SysTick).
- **Compiler drift**: -O2/-O3/-Os change results by large factors in some sources; record flags, and run one pass with the pqm4-documented compiler.
- **Portable C backends** in mlkem-native/mldsa-native are not hand-optimised for Cortex-M; the numbers answer "what does a maintained portable library cost", not "what is the fastest possible", and are not comparable to pqm4's assembly (`m4f`) rows without saying so. The mlkem-native Armv8.1-M (MVE) backend is experimental and disabled by default.
- **Cache and prefetch state** on U5/L4 change cycle counts; record it.
- **Single board per type**: silicon variation is small but nonzero; use two boards if you can.
- **Thermal and supply**: let boards settle; record supply voltage; avoid USB-powered measurements through a hub.
- **Energy**: board overheads (regulators, debugger, LEDs) enter unless isolated.
- **Pre-standard vs final parameters**: do not mix round-3 Kyber/Dilithium numbers with FIPS 203/204 numbers.

## 11. Safety and scope
Defensive, performance-only benchmarking. Nothing here measures leakage or attempts attacks. The RNG in the harness is insecure and for timing only. No production keys on benchmark boards. Treat downloaded sources as untrusted until read.

## 12. Host measurements already made (for orientation; **not** MCU results)
- `bench/host/` : liboqs 0.16.0 `speed_kem`/`speed_sig` on a virtualised 2.8 GHz x86 Xeon, 2 build variants x 5 repeats. Example: ML-KEM-768 decaps about 66 us and ML-DSA-44 verify about 106 us (portable-C variant, run 1), versus millions of cycles on a Cortex-M. Shows the order-of-magnitude gap and exercises the scripts; carries no MCU ranking information.
- `bench/mcu/host_selftest/` : this harness, PC build, 3 runs x 50 iterations; e.g. ML-DSA-44 sign median 288,542 ns, max/median 7.76.
