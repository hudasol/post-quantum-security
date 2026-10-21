# Board run protocol: real cycle counts on a borrowed STM32 board

Author: Huda Mueen. Written 2026-10-16. Status: **planned**. Nothing in this file has been run on a real board, and no number in it is a result. Every board number that will come from this protocol is labelled planned until the run happens, and then board measured, in its own table, never mixed with published, host measured, emulated or estimated numbers.

**Board kit (added 2026-10-20, status planned).** `bench/board_kit/` holds everything needed to run this protocol in one short session: build scripts for B0 (`build_b0.py`, pqm4's own build at the pin) and B1 (`build_b1.py`, the harness linked against pqm4's platform layer), UART capture (`capture.py`), parsing (`parse.py`), comparison with published, modelled and RTL simulated rows (`compare.py`), the result template (`RESULT_TEMPLATE.csv`), the one page session checklist with an estimated session length (`CHECKLIST.md`, from `session_plan.py`), the build log and image sizes (`build_log.md`, `image_sizes.csv`) and an emulator dry run of the whole pipeline (`DRY_RUN.md`, label emulated). The kit has not been used on a board: all board numbers remain planned.

## 1. Purpose

The repository has published cycle counts (pqm4 and papers), emulated stack and size (QEMU, no cycles) and host timings (not transferable). It has no cycle count of its own from a microcontroller. This protocol closes that gap in one bench session of about half a day, with no purchase: a borrowed board, free tools and the firmware already in `bench/mcu/`.

Two experiments, in this order:

| ID | What | Why |
|---|---|---|
| B0 | Reproduce published pqm4 numbers for ML-KEM-768 and ML-DSA-44 (`clean` and the fastest `m4f` variant) at the pinned pqm4 commit | checks the board, clock and counter against a published reference before trusting any new number |
| B1 | Run the repository harness (mlkem-native and mldsa-native v2.0.0, portable C) for all six parameter sets | the first cycle counts for the exact code that the emulator and host runs used |

## 2. What the author needs to borrow or supply

1. One STM32 board with a Cortex-M4F, preferably the **NUCLEO-L4R5ZI** (pqm4's default board per its README) or the **STM32F4 Discovery** (STM32F407VG). Optional second board with a Cortex-M33 (a NUCLEO board with an STM32L5 or U5 part) for a second panel.
2. The USB cable for the board's on board ST-LINK.
3. Lab access for about half a day, typically from a university embedded systems or robotics lab.
4. A laptop with: `arm-none-eabi-gcc` (record the exact version), `make`, `git`, Python 3, and OpenOCD or `st-flash` for flashing. These are free and need no account; avoid tools that need a vendor login.
5. Permission from the lab to flash the board (the firmware only computes and prints; it does not touch any other device).

## 3. Pinned software (clone before the session; pqm4 is announced for archiving)

| Item | Pin | Source of the pin |
|---|---|---|
| pqm4 | `5e5cc76d0b072ee7077e58afcbc619a1a67a53b4` (2026-09-04) | `data/raw/S6_pqm4_config.md`; the README carries a deprecation notice and an archive planned in or after January 2027, so clone it now |
| mlkem-native | `v2.0.0` / `d1b2fe782888bdb761a50336012923180be7f502` | `bench/mcu/fetch_libs.sh` (aborts on mismatch) |
| mldsa-native | `v2.0.0` / `834a90d5e846ffa1e1611bd24e160bb2e9b86d35` | `bench/mcu/fetch_libs.sh` |
| Harness | this repository at the commit used, recorded in the result file | `bench/mcu/src/` |

Clone pqm4 with its submodules at the pin and check `git rev-parse HEAD` before the session. For B0, follow the pqm4 README at that commit for the build and benchmark commands, and copy the exact commands used into the result file. Do not rely on memory for pqm4's options.

## 4. Clock, flash wait states and caches (record, do not assume)

The project's own reading of pqm4 (`data/raw/S6_pqm4_config.md`, from `common/hal-opencm3.c` at the pin) is:

| Board | pqm4 benchmark clock mode | Flash wait states | Caches and prefetch |
|---|---|---|---|
| NUCLEO-L4R5ZI | 20 MHz (HSI16 through the PLL) | 0 | data cache, instruction cache and prefetch enabled in that mode |
| STM32F4 Discovery | 24 MHz (HSE through the PLL) | 0 | data and instruction cache enabled |

The pqm4 README says 24 MHz for all results; the code says 20 MHz for the L4R5ZI. This disagreement is unresolved (`docs/CROSSCHECK.md`). B0 is the place to settle it for the borrowed board: record what the board actually runs.

Rules for both experiments:

1. Run at the benchmark clock with 0 wait states, so cycle counts are comparable with pqm4. Optionally add a second pass at full speed, in a separate table, never mixed.
2. Read back and print, at run time, the core clock in Hz, the flash latency field of the flash access control register, and the cache and prefetch enable bits. The harness prints `META` lines; add these three values as `META,clock_hz`, `META,flash_ws`, `META,cache` in the board start up file.
3. State interrupts: the harness builds with `-DBENCH_DISABLE_IRQ`; print only outside timed regions.
4. The registered cycle predictions assume no cache and no prefetch. Where the board allows it, add one pass of the B1 images with instruction cache, data cache and prefetch switched off at zero wait states, in its own table. Only rows from that pass count toward the refutation rule of `docs/PREDICTIONS_V4_BOARD_NOTES.md` (note 7); rows measured with caches on are reported beside their verdicts. Round 4 noted that the kit could not yet switch caches off (`docs/PREDICTIONS_V4_BOARD_NOTES.md` note 8); the round 5 update below adds and tests that option, and the round 5 refutation rules are those of `docs/PREDICTIONS_V5_BOARD.md`.

**Round 5 update (2026-10-21, status planned): caches off option and a Cortex-M33 board.** The kit now has the option (`bench/board_kit/build_b1.py --cache both`). `b1/b1_main.c` built with `-DBENCH_CACHE_OFF` reads the flash latency after pqm4's `hal_setup(CLOCK_BENCHMARK)` and, only if it is zero wait states, clears the instruction cache, data cache and prefetch enable bits and prints the read back register (`META,cache_pass`, `META,cache_off_applied`, `META,cache`). Register sources, all retrieved at pinned commits because the reference manual fetched from www.st.com (RM0432) returned only its table of contents, without the bit fields:

| Part | Register and bits | Source |
|---|---|---|
| STM32L4R5 | FLASH_ACR at FLASH_R_BASE (AHB1 base plus 0x2000); LATENCY bits 3:0, PRFTEN bit 8, ICEN bit 9, DCEN bit 10 | STMicroelectronics/cmsis_device_l4 v1.7.5 (`dc04e41afbd7c204cd09f2fa5dd29658efbaff6c`), `Include/stm32l4r5xx.h`; same PRFTEN, ICEN and DCEN positions in libopencm3 `1f3abd43763fa39d23e737602b6d0011a45c70b2` (pqm4 submodule), `include/libopencm3/stm32/l4/flash.h` and `include/libopencm3/stm32/common/flash_common_idcache.h`, which the image uses. libopencm3 masks LATENCY with 0x07, the CMSIS header with 0xF; both read zero at zero wait states |
| STM32L552 | ICACHE_CR EN bit 0 and ICACHE_SR BUSYF bit 0 at ICACHE_BASE_NS (AHB1 base plus 0x10400); FLASH_ACR LATENCY bits 3:0, with no prefetch or cache enable bit defined for FLASH_ACR | STMicroelectronics/cmsis_device_l5 v1.0.7 (`e237398c0cbae890f4659f74fe6b64cae339b6a0`), `Include/stm32l552xx.h` |

pqm4 has no Cortex-M33 platform at the pinned commit or at its master branch (`e1146b1bc180c66689682f6ce63bd8f126a51ace`, fetched 2026-10-20), so B1 for NUCLEO-L552ZE-Q uses the vendor CMSIS start up file, system file and linker script unchanged, with a small platform file (`bench/board_kit/b1/m33/hal_l552.c`). It runs at the 4 MHz reset clock (MSI, per `system_stm32l5xx.c` of the same release) and prints on LPUART1 (PG7 and PG8, the ST-LINK virtual COM port in the board user manual UM2581, retrieved from www.st.com in round 5; alternate function 8 from zephyrproject-rtos/hal_stm32 `c9550199186236d610092f4005f8c9bae2a6bfcf`, `dts/st/l5/stm32l552z(c-e)txq-pinctrl.dtsi`). B0 is not built for this board. The caches on pass of this board enables its ICACHE; the caches off pass disables it.

Tests: `bench/board_kit/cache_check.py` proves from the disassembly that each caches off image loads the register address, clears the bits and stores the result, and that each caches on image does not; `bench/board_kit/renode_check.py` runs the NUCLEO-L552ZE-Q images in Renode 1.16.1, whose `stm32l552` description does not model the ICACHE or the flash interface, so the store is seen on the bus but has no effect in the model. No free model of the STM32L4R5 was found (QEMU 8.2 lists no STM32L4 machine; Renode 1.16.1 has no STM32L4 description). The predictions for the caches off pass are registered in `docs/PREDICTIONS_V5_BOARD.md`.

## 5. Firmware build (B1)

**Kit route (preferred, no new start up, clock or UART code).** `python3 bench/board_kit/build_b1.py --platform nucleo-l4r5zi` builds all six images with pqm4's start up (libopencm3 vector table and reset handler), clock set up (`hal_setup(CLOCK_BENCHMARK)`), LPUART1 output and linker script at the pinned commit. The only new file is `bench/board_kit/b1/b1_main.c`, which reads back the clock, flash wait states and cache bits as META lines and runs the counter check. The run id comes from `capture.py --run`, so one image serves all power cycles. The manual route below remains as a fallback.


From `bench/mcu/`:

```
./fetch_libs.sh
make arm CPU=cortex-m4 FPU=fpv4-sp-d16 ALG=mlkem SET=768 ITERS=100 \
     CLOCK_HZ=<measured Hz> STACK_SPAN=131072 ARM_OPT=-O2 RUN_ID=<power cycle number> \
     LDSCRIPT=<board linker script> STARTUP=<board start up file>
```

Repeat for `ALG=mlkem SET=512|768|1024` and `ALG=mldsa SET=44|65|87`. For a Cortex-M33 board use `CPU=cortex-m33 FPU=fpv5-sp-d16`. The board start up and linker files are the only new code; `bench/mcu/board/qemu/` is a working template (vector table, data copy, UART output) that needs the board's memory map, UART and clock set up. `bench/mcu/README.md` lists three routes (STM32CubeMX project, Zephyr, PlatformIO) and the mandatory checks. The span must fit below the stack pointer; the emulated ML-DSA-87 signing stack is about 113 KB (`bench/mcu/qemu_results/stack.csv`), so the F4 Discovery (192 KB RAM) can run it only if the linker script leaves enough room, and the L4R5ZI (640 KB RAM) has room. Set `STACK_SPAN` per board and per parameter set from the linker map, and check that the stack, the painted span and `.bss` fit in the one contiguous RAM region that holds the stack: a chip's total RAM may be split into separate regions.

## 6. Session steps

1. Before the session: build every image at home, run the kit dry run (`bench/board_kit/run_dry_run.py`, or `./run_qemu.sh` for the manual route) to confirm correctness, write the board prediction file (section 9) and hash it. Follow `bench/board_kit/CHECKLIST.md` at the board.
2. Connect the board; record board name, chip marking, core, and the ST-LINK firmware version.
3. Counter check: time 1,000,000 iterations of a known loop with the DWT cycle counter and compare with the expected count. A mismatch stops the session: the counter is not counting core cycles.
4. B0: build and run pqm4 for ML-KEM-768 and ML-DSA-44 at the pin; save the raw output.
5. B1: flash and run each of the six images; capture the UART output of each run to a file.
6. Power cycle the board and repeat steps 4 and 5 twice more (three power cycles in total, as in `docs/BENCHMARK_PLAN.md`).
7. Copy every raw log, the exact commands and the toolchain version into `bench/mcu/board_results/<date>/`.

## 7. Result template (CSV, one row per measurement)

The kit writes its own documented schema (`bench/board_kit/RESULT_TEMPLATE.csv`, columns described in `bench/board_kit/parse.py`); it carries the same information as the template below, with `label` set from the capture header.

```
date,board,chip,core,clock_hz,flash_ws,cache,toolchain,flags,library,library_commit,alg,param,op,run_id,iter,cycles,stack_bytes,label
```

`label` is always `board measured`. Analysis: `bench/stats/analyze_runs.py` over the three power cycle logs (median, percentiles, bootstrap interval). B0 is reported as the ratio of the board median to the published pqm4 value for the same scheme, implementation and operation (ML-KEM-768: rows S2-0019 to S2-0027; ML-DSA-44: rows S2-0028 to S2-0036 of `data/evidence.csv`, covering `clean`, `m4fspeed`, `m4f` and `m4fstack`).

## 8. What this protocol will and will not show

It will show real core cycle counts and stack for the two boards of the round 5 plan (NUCLEO-L4R5ZI and NUCLEO-L552ZE-Q), each at one clock and one toolchain, kept apart by board in every table. With an ammeter or a power analyser it will also show energy per operation by the method of section 10 (added in round 5); without one it shows no energy. It will not show behaviour on a production flight controller with its scheduler and interrupts running, or numbers for other boards.

## 9. Predictions before the run

Write them in a new hashed file before the session, as was done for each round (latest: `docs/PREDICTIONS_V5_BOARD.md`, rows for the two boards with refutation rules 1 to 4, scored by `python3 bench/board_kit/score_v5_board.py`). Suggested questions: does B0 reproduce the published pqm4 cycle counts within a stated tolerance; does the B1 stack match the emulated stack within a stated tolerance; how do B1 cycle counts compare with the pqm4 `clean` rows for the same parameter set.

## 10. Energy per operation (added in round 5, status planned)

Energy is measured, not modelled, only if the borrowed board session has time left (`bench/board_kit/ONE_AFTERNOON.md` places it after the caches off and caches on passes of the Cortex-M4 board). Free instruments only: a borrowed digital multimeter with a mA range, or a lab power analyzer if the lab has one.

**Where to measure.** Both NUCLEO-144 boards have a jumper, JP5 marked IDD, that carries the microcontroller supply: removing it and connecting an ammeter in its place measures the microcontroller current, and without the ammeter the microcontroller is not powered (board user manuals UM2179 Rev 10, section 7.8, for the NUCLEO-L4R5ZI board, and UM2581, section 6.7, for the NUCLEO-L552ZE-Q board, both retrieved from www.st.com in round 5). UM2581 adds that JP5 measures only at 3V3 and that JP4, which selects the microcontroller supply of 3V3 or 1V8 (section 6.8), can serve as the measurement point for both, with a reading that includes the supply pin of a level shifter. Keep both boards at 3V3 and measure at JP5; check the jumper and the supply voltage on the day against the manual of the exact board revision, and record what was used.

**What to record (one row per operation phase, `bench/board_kit/ENERGY_TEMPLATE.csv`).** Date, board and chip marking, platform, image, cache pass, run, scheme, operation, method, instrument make, model and range, jumper, supply voltage measured at the jumper, mean current over the phase, idle current with the board held in reset (the method of `bench/board_kit/ONE_AFTERNOON.md`: hold the reset button down while the meter averages for 10 s), and for an analyzer the charge over the marked window, the number of operations inside it and the window length. Never edit a row after the session; a repeated reading is a new row.

**Two methods.**

1. `multimeter_phase`: the harness runs each operation many times in a row (one phase per operation, delimited in the capture log by the timestamps of the first and last BENCH line of that operation). Read the meter's average (or its min, max and average function) over the phase and write it down with the phase name. parse.py derives the time per operation from the board measured mean cycles of the same board, cache pass, scheme and operation and the clock read back: energy per operation = supply voltage x mean current x cycles / clock; the value net of idle subtracts the idle current. UART output inside a phase is included in the mean current; state this beside every result.
2. `analyzer_gpio_window`: an analyzer that logs current against time and has a digital input integrates the charge while a GPIO marker is high around N operations; energy per operation = supply voltage x charge / N. The kit's images do not yet drive a GPIO marker (a planned change to `b1/b1_main.c`, to be tested at home before use); until then use method 1.

**Ingest.** `python3 bench/board_kit/parse.py <logs> --out board.csv --checks-out checks.csv --energy energy.csv --energy-out energy_per_op.csv`. The output keeps every input column and adds `cycles_board_measured_mean`, `clock_hz`, `time_s_per_op_board_measured`, `energy_uj_per_op_board_measured`, `energy_uj_per_op_net_of_idle_board_measured` and `energy_source` (the formula used). Energy values are board measured and never enter a column with the modelled values of `energy/`.

