# On-device benchmark harness: ML-KEM and ML-DSA (experiment E1)

**STATUS (read first).** This harness has been compiled and run **on a PC only** (`make host`, output in ns, labelled *host measurement*).
**It has also been built and run in QEMU on an emulated Cortex-M4** (`./run_qemu.sh`, results in `docs/EMULATOR_RESULTS.md`): correctness, stack and size only, no cycle counts. **It has not been run on any real microcontroller.** The DWT cycle-counter code, the stack-painting macro and the ARM Makefile target are written from the
Arm CMSIS register layout and are untested on hardware. Expect to debug board bring-up. Nothing printed by a PC build may be quoted as an MCU result.

No cryptography is implemented here. The harness calls two pinned, reviewed libraries:

| Library | Pin (tag / commit, read 2026-10-11) | Licence |
|---|---|---|
| mlkem-native | `v2.0.0` / `d1b2fe782888bdb761a50336012923180be7f502` | Apache-2.0 OR ISC OR MIT |
| mldsa-native | `v2.0.0` / `834a90d5e846ffa1e1611bd24e160bb2e9b86d35` | Apache-2.0 OR ISC OR MIT |

`fetch_libs.sh` clones the tags and aborts if the commit differs from the pin. Downloaded code is untrusted: read it before flashing.

## What it measures

For each parameter set (ML-KEM-512/768/1024, ML-DSA-44/65/87), `ITERS` repetitions (default 100) of:
ML-KEM keygen / encaps / decaps (deterministic `*_derand` API, so no RNG inside the timed region); ML-DSA keygen / sign / verify (every sign uses a *different* message because sign time is data-dependent).
It also records stack high-water mark per operation by stack painting, and checks correctness (round trip; sign-verify; a corrupted signature must be rejected). A run with failed checks exits non-zero and `analyze_runs.py` warns.

The random source is `src/bench_rng.c`, a deterministic **insecure** xorshift generator used only so that timings are reproducible. Never use it for real keys. Measure your board's TRNG separately (BENCHMARK_PLAN section 5.4).

## Output format (printed over UART/semihosting/RTT)

```
META,<key>,<value>
BENCH,<alg>,<param>,<op>,<run_id>,<iter>,<value>,<unit>     unit = cycles (MCU) or ns_host (PC)
STACK,<alg>,<param>,<op>,<bytes>     -1 = not measured (PC), -2 = painted span too small
CHECK,<alg>,<param>,<what>,<ok>,<fail>
```

Capture one log file per power cycle and analyse with `../stats/analyze_runs.py` (medians, percentiles, bootstrap CI).

## PC self-test (works today)

```
./fetch_libs.sh
./run_host_selftest.sh                      # builds all six binaries, runs them, writes host_selftest/*.csv
python3 -I ../stats/analyze_runs.py host_selftest/run1/*.csv host_selftest/run2/*.csv host_selftest/run3/*.csv --out-csv s.csv --out-md s.md
```

## Emulator run (free, works today)

```
sudo apt install qemu-system-arm gcc-arm-none-eabi
./fetch_libs.sh && ./run_qemu.sh
```

Board files for QEMU `mps2-an386` are in `board/qemu/`. QEMU has no DWT cycle counter, so BENCH rows print 0.

## Board bring-up for real hardware (what you must supply; untested)

The `make arm` target needs your own `STARTUP=` file and `LDSCRIPT=`. Pick one route:

1. **STM32CubeIDE / CubeMX project** (simplest for NUCLEO boards): generate a bare project with a USART2/LPUART printf redirect, add `src/*.c` and the library's `mlkem_native.c` or `mldsa_native.c` (single-file build), add the `-D` flags shown in the Makefile `arm` rule.
2. **Zephyr** (both mlkem-native and mldsa-native document a Zephyr test platform): create an app that links the same sources; use `printk`/console for output.
3. **PlatformIO** with the `ststm32` platform (board ids `nucleo_l4r5zi`, `nucleo_u575zi_q` exist in platform-ststm32 v20.0.0).

Mandatory settings and checks, in this order:

1. **Fix the clock and say what it is.** Set `-DBENCH_CLOCK_HZ=<Hz>`. pqm4 benchmarks at a low clock to keep flash at zero wait states; for comparability run **one pass at that clock** (record the actual HCLK and flash latency in the log) and optionally a second "as-shipped" pass at full speed. Never mix the two in one table.
2. **Disable the cache question explicitly.** State whether instruction cache / ART accelerator / prefetch are on. Record it in `META`.
3. **Counter check.** Run the DWT self-check: time 1,000,000 iterations of a known `nop` loop and compare to the expected cycles; a mismatch means the counter is not counting core cycles. `CYCCNT` is 32-bit and wraps (about 36 s at 120 MHz); the timed operations here are far shorter, but do not add SLH-DSA signing (billions of cycles) without a 64-bit extension.
4. **Stack span.** `BENCH_STACK_SPAN` defaults to 16 KiB, which is too small for ML-DSA signing in reference-style code (published pqm4 figures for the reference implementation exceed 50 KB). Set it from your linker map and make sure it fits below the stack pointer without overwriting `.bss`/heap. A result of `-2` means the span was too small.
5. **Interrupts.** `-DBENCH_DISABLE_IRQ` is on in the ARM rule. If your UART needs interrupts, print only outside the timed region (the harness already does).
6. **Code size.** Build a baseline image with the harness but without the library call, then the real image; the `.text`+`.rodata` difference from `arm-none-eabi-size` (or the map file) is the library's flash cost. Use `-Wl,--gc-sections` as the Makefile does.
7. **Run at least 3 power cycles** (BENCHMARK_PLAN section 7) and pass the three logs to `analyze_runs.py`.

## Files

`src/` harness sources (`cyc.h` counter, `stack_paint.h`, `bench_common.h`, `bench_mlkem.c`, `bench_mldsa.c`, `bench_rng.c`), `Makefile`, `fetch_libs.sh`, `run_host_selftest.sh`, `host_selftest/` (PC output, **host measurement**), `board/NOTES.md`.
