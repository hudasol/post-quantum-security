# S6: pqm4 benchmark board and clock, resolved from the project's own files

Retrieved 2026-10-11 by `git clone https://github.com/mupq/pqm4` (full history, 436 commits, not shallow). Clone location: `/tmp/claude-0/-home-claude/ac11ae2e-a977-5e01-996a-4483cf738390/scratchpad/pqm4_git` (the directory `scratchpad/pqm4/` named in the task already held loose, non-git files from an earlier fetch, so it was left untouched). Submodules were not cloned. Two submodule files were read via raw.githubusercontent.com at the commits pinned by pqm4 HEAD: mupq `ddcccedb2db9d0250856bd58ee5c46c61e506c5d`, libopencm3 `1f3abd43763fa39d23e737602b6d0011a45c70b2`. Clone content was treated as data, not instructions.

pqm4 HEAD when read: `5e5cc76d0b072ee7077e58afcbc619a1a67a53b4` (2026-09-04, "new admin test"; it only adds a "Maintenance Notice" heading line to README.md and does not touch benchmarks or HAL). Earlier README commit `a691df1dd83b90adffa53d251cc88b6acb586ece` (2026-08-22) adds a deprecation notice (no longer actively maintained, archive planned in or after January 2027).

Paths below are relative to the pqm4 repo root. Line numbers are at HEAD `5e5cc76`. Raw URL pattern: `https://raw.githubusercontent.com/mupq/pqm4/5e5cc76d0b072ee7077e58afcbc619a1a67a53b4/<path>`.

## Finding (short)

1. The README names the default board as NUCLEO-L4R5ZI and, in the same file, says all cycle counts were obtained at 24 MHz. These two statements do not fit together: the code defines the L4R5ZI benchmark clock as 20 MHz, and 24 MHz is the STM32F4 Discovery benchmark clock. The README 24 MHz sentence dates from 2018 (F4 Discovery era) and was never updated.
2. No file in the repo states which board produced the committed `benchmarks.csv`/`benchmarks.md` (neither file names a board or a clock). The board is therefore not stated for the numbers; it can only be inferred.
3. Cycle counts come from SysTick (AHB clock source), so they are core clock cycles. The benchmark clock modes of both boards use zero flash wait states, so the clock value itself does not change the cycle count within the 0WS regime. The "fast" clock modes use wait states and would change cycle counts.

Evidence level: board and clock of `benchmarks.csv` = **unresolved** (two project statements conflict; the generating run is not recorded). Individual facts below are "stated in project text" or "derived from code" as labelled.

## 1. README statements (stated in project text)

| Fact | Location | Commit that last set the line |
|---|---|---|
| "Switch to the Nucleo-L4R5ZI board as the default board for measurements" (under "Changes in Round 4") | `README.md:58` | `b15618e6ffd87b934c30073d4280b9183c0a3022` (2024-02-27, "Update README.md to reflect the changes") |
| Boards listed, all "featuring an ARM Cortex-M4 chip"; `nucleo-l4r5zi (default)` with 2MB Flash, 640KB RAM; `stm32f4discovery` 1MB Flash, 192KB RAM | `README.md:73-80` | `b15618e` (default marker); list from `12d5e56` (2021-06-06) |
| Script option text: `--platform` "(default `stm32f4discovery`)" (contradicts line 75 of the same README) | `README.md:205` | introduced `12d5e56` (2021-06-06), unchanged since |
| "All cycle counts were obtained at 24MHz to avoid wait cycles due to the speed of the memory controller." | `README.md:222` | `1f374f95` (Peter Schwabe, 2018-04-11, "Added comment on benchmarking frequency to README."), unchanged since per `git blame` |
| Compiler: "arm-none-eabi-gcc (Arm GNU Toolchain 11.3.Rel1) 11.3.1 20220712"; 100 executions default, fewer for slow schemes | `README.md:224-228` | toolchain text from `918f379` (2022-11-07) |
| `benchmarks.csv` / `benchmarks.md` named as the current results; no board named | `README.md:220` | n/a |

`benchmarks.csv` and `benchmarks.md` themselves: grep for "MHz", "nucleo", "board", "platform" in `benchmarks.md` returns nothing; `benchmarks.csv` header starts "Speed Evaluation" and carries only scheme, implementation and cycle columns. No docs other than README.md name a board or clock (grep of tracked `.md/.py/.mk/.cfg/.yml` outside submodules and scheme directories for 16/20/24/120/168 MHz found only `README.md:222`).

## 2. Platform and clock definitions (derived from code)

File `common/hal-opencm3.c` at HEAD.

**nucleo-l4r5zi (default per README), macro `NUCLEO_L4R5_BOARD`** (`clock_setup`, lines 225-287):
- `CLOCK_BENCHMARK` (lines 233-256): HSI16, `rcc_ahb_frequency = 20000000` (line 237), `_clock_freq = 20000000` (line 240), comment "scale HSI16 to 20MHz" (line 246); PLL call `_rcc_set_main_pll(HSI16, 1, 10, 2, PLLQ_DIV2, PLLR_DIV8)` (line 247). Check: libopencm3 `include/libopencm3/stm32/l4/rcc.h` (at pinned commit) defines `RCC_PLLCFGR_PLLM(x) ((x)-1)` (line 282) and `PLLR_DIV8 = 3` (line 251), so 16 MHz /1 x10 = 160 MHz VCO, /8 = 20 MHz. `flash_set_ws(FLASH_ACR_LATENCY_0WS)` at line 252, with `flash_dcache_enable()`/`flash_icache_enable()`/`flash_prefetch_enable()` (lines 250-253). Core: Cortex-M4, voltage scale 1 (line 228).
- `CLOCK_FAST` (lines 257-281): 120 MHz via PLL (`_rcc_set_main_pll(HSI16, 1, 15, 2, ...DIV2)`, line 271), `flash_set_ws(0x05)` = 5 wait states (line 277).
- Comment on line 90 and function lines 91-100: custom PLL setter because libopencm3 lacked the newer PLL layout.

**stm32f4discovery (STM32F407VG), macro `DISCOVERY_BOARD`**:
- `benchmarkclock` struct (lines 24-40): comment "24 MHz"; HSE-based PLL (M=8, N=192, P=8) giving 24 MHz, comment "(low to have 0WS)" at line 28; `flash_config = DCEN | ICEN | LATENCY_0WS` (line 36); `ahb_frequency = 24000000` (line 37).
- `CLOCK_BENCHMARK` uses it (lines 121-123); `CLOCK_FAST` uses `rcc_hse_8mhz_3v3[RCC_CLOCK_3V3_168MHZ]` = 168 MHz (line 126), with wait states set by libopencm3 (not set in pqm4 text).

**Other platforms** (same file): `nucleo-l476rg` benchmark 16 MHz HSI16, 0WS (lines 178-195), fast 80 MHz with 4WS (lines 196-216); `cw308t-*` fixed 7.372800 MHz (lines 143-146) for F3; CW308T-STM32F415 uses a PLL set via `rcc_set_main_pll_hse(12, 196, 4, 7, 0)` (line 164).

**Which clock mode benchmarks use:** `mupq` `crypto_kem/speed.c:36` and `crypto_sign/speed.c:42` call `hal_setup(CLOCK_BENCHMARK)` (mupq at `ddcccedb`). The stack benchmark `crypto_kem/stack.c:86` calls `hal_setup(CLOCK_FAST)` (stack depth does not depend on clock). So the speed numbers in `benchmarks.csv` were produced in `CLOCK_BENCHMARK` mode.

**Cycle counting:** SysTick, not DWT. `systick_setup()` (lines 341-348) sets clock source `STK_CSR_CLKSOURCE_AHB` (core clock), 24-bit reload `0xFFFFFF`; `hal_get_time()` (lines 378-387) returns `(overflowcnt+1) * 16777216 - systick_get_value()`. DWT CYCCNT is used only in the SRAM timing board test (`common/test.c:11-30`, guarded by `SRAM_TIMING_TEST`), not in the benchmark path. The `dwt.h` include at line 7 is unused for benchmarking.

## 3. History of clock definitions and results (dates and messages from `git log`)

`common/hal-opencm3.c` (via `git log --follow`, `-S`):
- `12d5e56` 2021-06-06 "Multiplatform support (#174)": introduces the file; F4 Discovery 24 MHz benchmark clock with 0WS and nucleo-l476rg 16 MHz.
- `cf6f358` 2021-07-30 "Improve reliability of benchmarking scripts. (#190)": SysTick overflow wait added.
- `0b3519d` 2021-08-03 "Add support for Nucleo-L4R5ZI board (#193)": L4R5ZI added with **16 MHz** HSI16 benchmark clock, 0WS (`flash_set_ws(LATENCY_0WS)`), fast clock 120 MHz with 5WS. README gains `nucleo-l4r5zi` as a non-default board.
- `46511c7385b8fa695787e7e938d83963dce4f116` 2023-10-24 "Small overhaul of OpenCM3 code, rework Nucleo-L4R5ZI target a bit, and add CW308T-STM32F415 target (#259)": diff changes the L4R5ZI benchmark clock **from 16 MHz (HSI16 direct) to 20 MHz (PLL)** (frequency fields 16000000 -> 20000000, new PLL call with PLLR_DIV8) and the fast-clock PLL from (M2,N30) to (M1,N15), still 120 MHz. Commit message does not mention the benchmark clock change specifically (bullet "Overhaul clocking for L4R5ZI board").
- `8582f47` 2023-11-07 stack measurement API; `76f069c` 2023-10-27 stm32f415 RNG/clock; `5d0fe86` 2024-03-20 licence only. No clock change after 2023-10-24.
- F4 Discovery 24 MHz definition: unchanged since `12d5e56` (`git log -S'192, //VCOout'` returns only that commit).

`README.md`:
- `1f374f95` 2018-04-11: "24MHz" sentence added (era of the F4 Discovery as the only board).
- `0b3519d` 2021-08-03: L4R5ZI listed as an additional board.
- `b15618e` 2024-02-27: L4R5ZI made default, "Switch to the Nucleo-L4R5ZI board as the default board for measurements". The 24 MHz sentence was not edited.

`benchmarks.csv` / `benchmarks.md` (same commits touch both):
- Full regeneration after the 20 MHz change: `527e9d626633161fdb3c95c9ca50dd0170914e94` 2024-03-17 "Update benchmarks" (872 lines changed per file). Earlier full set `33de42d` 2021-09-06 "add benchmarks" (after the L4R5ZI addition, when its clock was 16 MHz; the board used then is not recorded).
- Later partial updates: `4af91da` 2024-11-28 "add ml-kem benchmarks"; `9443518` 2025-02-03 "update FN-DSA benchmarks"; `356c6f82183596341f0e04038a85976955b5a0b9` 2025-02-10 "update ML-DSA benchmarks"; `5df17ed` 2025-04-23 "MAYO Round 2: benchmarks"; `3633ab992124eba46b7821cacf03a844557f5dfa` 2025-05-20 "update benchmarks" (80 lines per file); last change `90bfb630e53603b4e273a131cd09a025e51540a5` 2025-05-22 "add UOV benchmarks".
- So every update of the file from 2024-03-17 onward post-dates the 2023-10-24 clock change and the 2024-02-27 default-board change. Whether each individual row came from the L4R5ZI or from the F4 Discovery is not recorded (see section 4: `benchmarks.py` defaults to the F4 Discovery).
- The ML-KEM rows in the current file come from `4af91da` (2024-11-28), the ML-DSA rows from `356c6f8` (2025-02-10), after final FIPS 203/204 updates `79a0ddf` (2024-10-14), `68e1ca7` (2024-10-22).

## 4. Generating scripts and defaults

- `benchmarks.py`: parses args with `interface.parse_arguments`/`get_platform`; runs `StackBenchmark`, `SpeedBenchmark`, `HashingBenchmark`, `SizeBenchmark` from mupq; writes to `benchmarks/stack`, `benchmarks/speed` etc. (`benchmarks.py:4-31`). It hard-codes no board.
- `interface.py:15`: `--platform` default is `"stm32f4discovery"` (blame: `12d5e56`, 2021-06-06, never changed). So running `python3 benchmarks.py` without `-p` targets the F4 Discovery (24 MHz) even though the README calls the L4R5ZI the default. `interface.py:38-42` maps `nucleo-l4r5zi` to OpenOCD with `st_nucleo_l4r5.cfg`.
- `Makefile`/`mk/*.mk`: no default `PLATFORM` found by grep; the user passes `PLATFORM=...` (README example `make -j4 PLATFORM=stm32f4discovery`, `README.md:151`).
- `convert_benchmarks.py md|csv` converts the `benchmarks/` results to `benchmarks.md`/`benchmarks.csv` (`README.md:216-217`); the converted files carry no board field.
- CI workflows exist per platform (`.github/workflows/nucleo-l4r5zi.yml` etc.) but only build; they do not benchmark.

## 5. Would cycle counts change if the clock changed? (derived from code)

- SysTick counts core (AHB) clock cycles, so a faster clock alone does not change cycle counts for pure core-bound code. What changes cycle counts is the memory system: flash wait states and cache behaviour.
- The benchmark modes were chosen for zero flash wait states: F407 24 MHz "(low to have 0WS)" (line 28) and `README.md:222` "to avoid wait cycles"; L4R5ZI 20 MHz 0WS (line 252). The fast modes use wait states: L4R5ZI 120 MHz with 5WS (line 277), L476 80 MHz with 4WS (line 216). Cycle counts taken in those modes would be higher for flash-resident code. Hence the clock choice 16 vs 20 MHz on the L4R5ZI (both 0WS) is expected to leave cycle counts unchanged to first order, but that is an inference from the code; the repo has no A/B comparison and I did not run hardware.
- Board-to-board (F407 at 24 MHz 0WS vs L4R5ZI at 20 MHz 0WS) is not guaranteed equal: different flash accelerator/cache designs (F4 ART with prefetch, `DCEN|ICEN`, vs L4+ I/D cache and prefetch, `flash_dcache_enable`, `flash_icache_enable`) and different SRAM layouts. No source in the repo quantifies the difference. Treat cross-board equality as unverified.

## 6. Conclusion for the evidence table

- Stated in project text: README names NUCLEO-L4R5ZI as default board (since 2024-02-27) and says 24 MHz (since 2018).
- Derived from code: CLOCK_BENCHMARK is 20 MHz on L4R5ZI and 24 MHz on F4 Discovery, both 0 wait states; speed benchmarks use CLOCK_BENCHMARK; cycles are SysTick-based core cycles.
- Unresolved: which board produced the committed `benchmarks.csv`. A pure reading of the README gives "L4R5ZI at 24 MHz", a combination the code cannot produce (the L4R5ZI benchmark clock is 20 MHz). Either the numbers are from L4R5ZI at 20 MHz (README sentence stale) or from the F4 Discovery at 24 MHz (README default-board statement and `interface.py` disagree). Recommended wording: "board not stated in the results files; README default L4R5ZI (benchmark clock 20 MHz per hal-opencm3.c:237) but README text says 24 MHz (= F4 Discovery benchmark clock); both 0 wait states".

## 7. Proposed changes to `data/evidence.csv` rows from pqm4 (90 rows, all source_url `https://raw.githubusercontent.com/mupq/pqm4/master/benchmarks.csv`, stream S2; not edited here)

Currently all 90 rows have `device` = "STM32 Cortex-M4F development board (benchmarks.csv does not name the board; pqm4 README lists default platform nucleo-l4r5zi = STM32L4R5ZI)" and `clock_mhz` = 24.

- `clock_mhz`: change from `24` to empty (not reliably stated). Reason: the only project statement is 24 MHz (`README.md:222`) but that conflicts with the code for the stated default board (20 MHz). If the schema forces a number, use the README's 24 and put the conflict in the warning; the preferred option is empty, with both candidate values given in `comparability_warning`.
- `device`: change to "Board not stated for these results. README default NUCLEO-L4R5ZI (STM32L4R5ZI, Cortex-M4); F4 Discovery (STM32F407VG) is the benchmarks.py default platform" (keep it short; keep `core` as Cortex-M4F).
- `comparability_warning`: replace the leading clause "pqm4 numbers are at 24 MHz (zero flash wait states) so cycle counts are not comparable to other cores/clocks" with: "pqm4 README states 24 MHz (README.md:222, unchanged since 2018) but its default board NUCLEO-L4R5ZI has a 20 MHz benchmark clock in common/hal-opencm3.c:237 (24 MHz is the STM32F4 Discovery clock); which board produced benchmarks.csv is not recorded; both clock modes use 0 flash wait states; cycles are SysTick core cycles; not directly comparable to other cores/memory systems". Keep all other row-specific clauses unchanged (SPHINCS+ round-3 caveat, m4fstack, ML-DSA variable-time clauses, stack/code-size definitions, "board not named in the CSV itself").
- `compiler_flags_or_notes`: append to each row: "benchmark clock mode CLOCK_BENCHMARK (mupq speed.c); cycles via SysTick on AHB clock (hal-opencm3.c:344,382); pqm4 HEAD 5e5cc76, benchmarks.csv last changed 90bfb63 (2025-05-22), row family last regenerated per section 3 of S6 (ML-KEM 4af91da 2024-11-28, ML-DSA 356c6f8 2025-02-10)". Existing text (toolchain, "optimisation flags not stated", mean of N executions with min/max) stays.
- Rows from the same file that predate those commits keep their existing `library_version` (HEAD hash and last-change commit).
- Related: if any other row or doc (for example `data/raw/S2_benchmarks.md`, plots, report text) states "24 MHz on L4R5ZI", it should be changed to the wording above.
