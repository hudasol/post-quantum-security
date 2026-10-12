# Next steps

## A. Fetch these sources yourself (the research environment could not reach them)
1. NSA CNSA 2.0 advisory and FAQ (nsa.gov / media.defense.gov) for the algorithm set, dates and LMS/XMSS firmware signing guidance. No CNSA 2.0 claim is made in the report.
2. CISA quantum pages (cisa.gov/quantum).
3. IACR ePrint PDFs (Cloudflare blocked the sandbox): 2019/844 (pqm4 paper: board and clock), 2026/1333 (ML-DSA benchmarking pitfalls), 2022/323 (stack optimised Dilithium), 2025/366 (SLOTHY), 2020/470 (LMS vs XMSS), 2021/781 (software updates), 2026/312 (RISQrypt), 2026/2343 (UAV command authentication).
4. UAE National Encryption Policy and executive regulation text (UAE Cybersecurity Council); ask the UAE National Cryptography Center for the algorithm profile for embedded and unmanned systems; search Arabic-language sources.
5. Vendor facts: written answers from your SoC suppliers on whether the boot-ROM verifier and key can change, and ST X-CUBE-PQC / Microchip MEC175xB / Infineon PSOC Control C3 / NXP PQC pages (blocked or claim only).
6. NIST CAVP/CMVP PQC validation search (JavaScript pages).

## B. Re-check before you rely on them (in flux on 2026-10-11)
FIPS 206 draft; NIST IR 8547 final; HQC FIPS; SP 800-230 final; FIPS 203/204 errata; draft-ietf-tls-mlkem RFC number; SUIT mandatory-to-implement draft (ML-DSA profile); BSI TR-02102-2; EU roadmap updates; Singapore and Japan roadmaps.

## C. Hardware work, in order
1. **E1** (first experiment; see below), then E3 (energy), E2 (hash based verification), E4 (boot time), E5 (radio transfer). All in `docs/BENCHMARK_PLAN.md`.
2. Add a Pixhawk-class (Cortex-M7) run only after E1 works.

## D. The first experiment (E1), exactly
Boards: **NUCLEO-U575ZI-Q** (Cortex-M33) and **NUCLEO-L4R5ZI** (Cortex-M4F). Libraries: mlkem native v2.0.0 and mldsa native v2.0.0 (pinned; `bench/mcu/fetch_libs.sh` verifies the commits). Measure **ML-DSA-44 verify and ML-KEM-768 decaps** first (cycles, stack, code size), then the other operations and parameter sets.
1. `cd bench/mcu && ./fetch_libs.sh && ./run_host_selftest.sh` (PC check that the harness builds).
2. Bring up a UART printf on each board (STM32CubeIDE, Zephyr or PlatformIO; see `bench/mcu/README.md`).
3. Run the DWT counter self check; set the core clock to a 0-wait-state value and record clock, flash latency and cache state.
4. Build with `make arm ...`; `-DBENCH_CLOCK_HZ=<Hz>`; set `BENCH_STACK_SPAN` from the linker map.
5. Run 3 power cycles x 100 iterations (1,000 for ML-DSA sign); save each UART log.
6. `python3 -I bench/stats/analyze_runs.py run1.csv run2.csv run3.csv --out-csv s.csv --out-md s.md`.
7. Subtract a baseline image to get code size; compare L4R5ZI results with published pqm4 rows S2-0022..0027 and S2-0031..0036 as a sanity check only (different library, counter, clock).
Approximate cost: about $60 for the two boards (prices seen 2026-10-11), plus a USB cable.

## E. Housekeeping
- The GitHub repository https://github.com/hudasol/post-quantum-security was empty and nothing has been pushed; the files are in the working directory. Say the word and I will commit them to a branch.
- The research subagents used `curl` via the sandbox's configured proxy (deviation D1).
