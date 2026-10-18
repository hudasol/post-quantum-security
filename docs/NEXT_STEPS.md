# Next steps

## A. Sources (status on 2026-10-12)
Received from the author (see `docs/SOURCES_TO_UPLOAD.md`): ePrint 2019/844, 2020/470, 2021/781, 2022/323, 2025/366, 2026/312, 2026/1333, 2026/2343; the NSA CNSA 2.0 FAQ; two UAE National Encryption Policy documents; a CISA quantum readiness document.
Done: 46 rows from 2025/366 and 2020/470 are in the table.
Still to do:
1. Read 2022/323 (stack figures), 2026/1333 (reporting rules), 2021/781 and 2026/2343 and add rows through `data/raw/` and `scripts/merge_evidence.py`.
2. Done: the CISA and uaelegislation.gov.ae files were read by OCR (English only). The executive regulation and the CISA cited orders are still unread.
3. The NSA CNSA 2.0 algorithms advisory (only the FAQ was supplied).
4. UAE National Cryptography Center algorithm profile for embedded and unmanned systems (ask them); Arabic language sources.
5. Vendor facts: written answers from SoC suppliers (`docs/supplier/README.md`, log in `docs/supplier/response_tracker.csv`).
6. NIST CAVP/CMVP PQC validation search (JavaScript pages).

## B. Re-check before you rely on them (in flux on 2026-10-11)
FIPS 206 draft; NIST IR 8547 final; HQC FIPS; SP 800-230 final; FIPS 203/204 errata; draft-ietf-tls-mlkem RFC number; SUIT mandatory-to-implement draft (ML-DSA profile); BSI TR-02102-2; EU roadmap updates; Singapore and Japan roadmaps.

## C. Hardware work, in order
1. **E1** (first experiment; see below), then E3 (energy), E2 (hash based verification), E4 (boot time), E5 (radio transfer). All in `docs/BENCHMARK_PLAN.md`.
2. Add a Pixhawk-class (Cortex-M7) run only after E1 works.

## D. The first experiment (E1), exactly
Targets: a Cortex-M33 board (for example NUCLEO-U575ZI-Q) and a Cortex-M4F board (for example NUCLEO-L4R5ZI), borrowed or already owned; emulator first. Libraries: mlkem native v2.0.0 and mldsa native v2.0.0 (pinned; `bench/mcu/fetch_libs.sh` verifies the commits). Measure **ML-DSA-44 verify and ML-KEM-768 decaps** first (cycles, stack, code size), then the other operations and parameter sets.
1. `cd bench/mcu && ./fetch_libs.sh && ./run_host_selftest.sh` (PC check that the harness builds).
2. Bring up a UART printf on each board (STM32CubeIDE, Zephyr or PlatformIO; see `bench/mcu/README.md`).
3. Run the DWT counter self check; set the core clock to a 0-wait-state value and record clock, flash latency and cache state.
4. Build with `make arm ...`; `-DBENCH_CLOCK_HZ=<Hz>`; set `BENCH_STACK_SPAN` from the linker map.
5. Run 3 power cycles x 100 iterations (1,000 for ML-DSA sign); save each UART log.
6. `python3 -I bench/stats/analyze_runs.py run1.csv run2.csv run3.csv --out-csv s.csv --out-md s.md`.
7. Subtract a baseline image to get code size; compare L4R5ZI results with published pqm4 rows S2-0022..0027 and S2-0031..0036 as a sanity check only (different library, counter, clock).
Cost: nothing. Do steps 1 to 2 and a build check in an emulator first (QEMU `mps2-an386` for Cortex-M4 and `mps2-an505` for Cortex-M33, or Renode), which gives correctness, flash size and stack size but no real cycle counts. For real cycles borrow a lab board for a few hours. See `docs/NO_PURCHASE_PLAN.md`.

## E. Housekeeping
- Licence decided: all rights reserved, permission on request (`LICENSE`, `docs/LICENCE_DECISION.md`). Release `v0.1.0` is published.
- Upstream duplicate checks (SROS2, MCUboot, ROS Discourse) are still to be done by hand; drafts are in `docs/upstream/` and nothing has been filed.
- The research passes used `curl` via the work environment's configured proxy in phase 1 (deviation D1).
