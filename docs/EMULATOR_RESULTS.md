# Emulator results: ML-KEM and ML-DSA on an emulated Cortex-M4

Author: Huda Mueen. Run on 2026-10-12 in QEMU 8.2.2, machine `mps2-an386` (Cortex-M4). Label: **emulated**. These are not microcontroller measurements and they are not published numbers. They are kept apart from both.

## What was run

1. Libraries: mlkem-native v2.0.0 and mldsa-native v2.0.0, pinned commits in `bench/mcu/README.md`, portable C backend (no assembly).
2. Compiler: `arm-none-eabi-gcc` 13.2.1, `-O2 -mcpu=cortex-m4 -mthumb -mfpu=fpv4-sp-d16 -mfloat-abi=hard`, `--gc-sections`.
3. Harness: `bench/mcu/src/` with my own board files `bench/mcu/board/qemu/` (start up, linker script, UART output). 3 iterations per operation.
4. Command: `cd bench/mcu && ./fetch_libs.sh && ./run_qemu.sh`. Results: `bench/mcu/qemu_results/`.

## What the emulator can and cannot tell

| Question | Answer from QEMU |
|---|---|
| Does the code build and run on a Cortex-M4 instruction set? | Yes. All six builds ran. |
| Is it functionally correct? | Yes. ML-KEM round trips passed 12 of 12 for each of the three parameter sets; ML-DSA sign, verify and rejection of a corrupted signature passed 10 of 10 for each of the three parameter sets. |
| Stack use | Reported below (stack painting high water mark; deterministic for this binary and compiler). |
| Image size | Reported below. |
| Cycle counts | **No.** QEMU does not model the DWT cycle counter, so every BENCH row prints 0. Real cycles need a real board (`docs/NO_PURCHASE_PLAN.md`). |

## Stack high water marks (bytes, emulated, this build only)

| Parameter set | keygen | encaps or sign | decaps or verify |
|---|---|---|---|
| ML-KEM-512 | 9,432 | 12,072 | 12,888 |
| ML-KEM-768 | 13,784 | 16,944 | 18,080 |
| ML-KEM-1024 | 19,176 | 22,848 | 24,464 |
| ML-DSA-44 | 32,088 | 50,008 | 29,952 |
| ML-DSA-65 | 49,488 | 74,608 | 45,360 |
| ML-DSA-87 | 80,208 | 113,504 | 74,312 |

The span includes the harness frames above the library call, so it slightly overstates the library alone. Compare with published stack optimised figures only after checking library, compiler and counting method; the same warning rules as in `data/evidence.csv` apply. The practical reading: with the portable C backend, ML-DSA signing needs tens of kilobytes of stack, which is why the planner's RAM thresholds matter for small flight controllers and why stack optimised variants exist.

## Image size (bytes, emulated build)

| Image | text and rodata | data | bss |
|---|---|---|---|
| mlkem 512 | 19,408 | 92 | 69,132 |
| mlkem 768 | 19,376 | 92 | 70,604 |
| mlkem 1024 | 19,632 | 92 | 72,236 |
| mldsa 44 | 23,648 | 100 | 72,220 |
| mldsa 65 | 24,368 | 100 | 75,228 |
| mldsa 87 | 23,440 | 100 | 78,044 |

Each image includes the harness and the C library; the baseline image is not subtracted, so these are upper bounds for the library's flash cost. The bss figure is not interpreted here.

## Second round (2026-10-16): Cortex-M33 and an optimisation sweep

`bench/mcu/run_qemu.sh` now regenerates everything in `bench/mcu/qemu_results/` in one run: six parameter sets on `mps2-an386` (Cortex-M4) and `mps2-an505` (Cortex-M33, board files in `bench/mcu/board/qemu_an505/`), each at -O2, -Os and -O3, with QEMU 10.2.1 and arm-none-eabi-gcc 14.2.1 (`qemu_results/config.csv`). The tables above are the first round (QEMU 8.2.2, gcc 13.2.1) and are kept as they were. The comparison is generated in `qemu_results/ANALYSIS.md`; what the emulator cannot show is in `qemu_results/LIMITS.md`. In short:

1. All 36 builds pass every correctness check.
2. Stack high water marks are the same on the Cortex-M33 model as on the Cortex-M4 model for every operation (same C code and compiler; the emulator does not change stack use).
3. The newer toolchain changes the first round figures by at most a few percent (exact values in `ANALYSIS.md`).
4. Stack grows strictly with the parameter set for every operation, core and optimisation level; -Os gives the smallest text for every image.

Renode (third round, 2026-10-18): Renode 1.17.0, a free download, has an STM32F4 Discovery (Cortex-M4F) platform. With board files for that platform (`bench/mcu/board/renode_stm32f4/`, RAM limited to the 128 KB of contiguous SRAM of the real STM32F407) `bench/mcu/run_renode.sh` runs ML-KEM-512, 768 and 1024 and ML-DSA-44: every check passes and every stack high water mark equals the QEMU value at -O2 to the byte (`bench/mcu/renode_results/COMPARISON.md`). Renode does not model the DWT cycle counter either, so it adds no cycle figures.

## Not done

1. Real cycle counts, energy and flash wait state effects (a borrowed Cortex-M4F or M33 board is needed; see `docs/BOARD_RUN_PROTOCOL.md`).
2. Assembly backends of the libraries; only the portable C backend was built.
3. ML-DSA-65 and ML-DSA-87 in Renode: only a subset was run in this round; their signing stack (about 75 KB and 114 KB in QEMU) needs a larger paint span, and ML-DSA-87 may not fit the 128 KB of contiguous SRAM at all.

## One bug found on the way

The untested `arm` target in `bench/mcu/Makefile` defined `RUN_ID` after it was used, so the target could not compile. Fixed in its own commit.
