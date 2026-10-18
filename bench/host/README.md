# HOST MEASUREMENT, not microcontroller result

Second round (2026-10-16): `native/` times the same mlkem-native and mldsa-native code that runs in the emulator, natively on a laptop, with a stated method (warm up, five pinned runs, median per run). Results and limits: `native/RESULTS.md`. Third round (2026-10-18): `native_v3/` repeats it with 15 interleaved runs per binary in a seeded order and reports the median absolute deviation (`native_v3/RESULTS.md`). The rest of this file describes the first round liboqs timings.

Sandbox timings of liboqs 0.16.0 `speed_kem` / `speed_sig`. Labelled `evidence_type=host-measured`.
They exist to (a) exercise the analysis scripts and (b) show the order-of-magnitude gap between a
server-class x86 core and a Cortex-M. They must never go into `data/evidence.csv` or onto the
published-number plots.

**Comparability warning:** x86-64 Xeon (AVX2/AVX-512, ~2.8 GHz, KVM guest, 33 MiB L3) versus an in-order Cortex-M with tens of KB of RAM and flash wait states: cycle counts and microseconds here are not comparable to MCU numbers and carry no MCU-ranking information.

## Environment (2026-10-11)
- CPU: Intel(R) Xeon(R) Processor @ 2.80 GHz (`lscpu`), 2 vCPUs, 1 thread/core, Hypervisor: KVM. Shared VM: expect noise from other tenants; stdev columns are large for the fast operations.
- Compiler: gcc 13.3.0 (Ubuntu 13.3.0-6ubuntu2~24.04.1); cmake 3.28.3; ninja 1.11.1. Build type Release, no OpenSSL (`-DOQS_USE_OPENSSL=OFF`).
- liboqs tag `0.16.0`, `git clone --depth 1 --branch 0.16.0`; checked-out commit `5a1a854b0dc9f2141bdc771c555ee60c37950183` (matches the S5 expected tag commit; no mismatch).

## Builds (two variants, labelled in `build_variant`)
Common flags: `-G Ninja -DCMAKE_BUILD_TYPE=Release -DOQS_BUILD_ONLY_LIB=OFF -DOQS_ENABLE_TESTS=OFF -DOQS_USE_OPENSSL=OFF -DOQS_ENABLE_SIG_STFL_LMS=OFF -DOQS_ENABLE_SIG_STFL_XMSS=OFF`
and `-DOQS_MINIMAL_BUILD="KEM_ml_kem_512;KEM_ml_kem_768;KEM_ml_kem_1024;SIG_ml_dsa_44;SIG_ml_dsa_65;SIG_ml_dsa_87;SIG_slh_dsa_pure_sha2_128s;SIG_slh_dsa_pure_sha2_128f;SIG_slh_dsa_pure_shake_128s;SIG_slh_dsa_pure_shake_128f"`.

- `opt` ("optimised"): defaults. `OQS_DIST_BUILD=ON`, `OQS_OPT_TARGET=auto`; runtime dispatch; tool reported active extensions ADX AES AVX AVX2 AVX512 BMI1 BMI2 PCLMULQDQ POPCNT SSE SSE2 SSE3.
- `portable` ("portable C"): extra flags `-DOQS_DIST_BUILD=OFF -DOQS_OPT_TARGET=generic -DOQS_USE_AVX2_INSTRUCTIONS=OFF -DOQS_USE_AVX512_INSTRUCTIONS=OFF -DOQS_USE_BMI1_INSTRUCTIONS=OFF -DOQS_USE_BMI2_INSTRUCTIONS=OFF -DOQS_USE_POPCNT_INSTRUCTIONS=OFF -DOQS_USE_AES_INSTRUCTIONS=OFF -DOQS_USE_SSE3_INSTRUCTIONS=OFF -DOQS_USE_ADX_INSTRUCTIONS=OFF -DOQS_USE_PCLMULQDQ_INSTRUCTIONS=OFF`; tool reported compile-time extensions SSE SSE2 only (x86-64 baseline), AES/SHA-3 "C". This is "no wide-SIMD extensions", not a Cortex-M-like build; it is still compiled with gcc -O3-class Release flags and x86 baseline SSE2.

Notes: the ML-KEM/ML-DSA sources are those vendored in liboqs (mlkem-native, mldsa-native per liboqs README); the build flags line also shows `OQS_LIBJADE_BUILD`, which was not investigated. SLH-DSA (slhdsa-c) is portable C in both variants, so its `opt` and `portable` numbers are expected to match within noise (they do). Names are the liboqs `SLH_DSA_PURE_*` (FIPS 205 pure) variants, 128s/128f, SHA2 and SHAKE.

## Not done
- LMS/XMSS: not built. Benchmarking them needs `OQS_HAZARDOUS_EXPERIMENTAL_ENABLE_SIG_STFL_KEY_SIG_GEN` (otherwise verify only, with no way to generate test vectors via the tool). I did not enable it, so no hazardous flag was used anywhere.
- Falcon, other schemes: not built.

## Runs
- 2 variants x 5 whole-run repeats, each repeat a separate process invocation per algorithm, `-d 3` (about 3 s per operation); runs executed sequentially (2 vCPUs). 300 rows (2 x 5 x 30 operations).
- Caveat: SLH-DSA-128s `sign` completed only 3-4 iterations in 3 s, so its mean is from very few samples; treat as indicative only.
- `cycles_mean` is the TSC-based "CPU cycles" the tool prints; on a VM it is not a reliable core-cycle count.

## Files
- `raw/*.txt` raw tool output (`<variant>_run<N>_<ALG>.txt`), `host_measurements.csv`, `parse_liboqs_speed.py`.
- CSV columns: scheme, parameter_set, operation, build_variant, run_index, iterations, total_time_s, mean_time_us, stdev_time_us, cycles_mean, cycles_stdev, evidence_type.

## Reproduce
```
W=$(mktemp -d); cd $W
git clone --depth 1 --branch 0.16.0 https://github.com/open-quantum-safe/liboqs src
git -C src rev-parse HEAD     # expect 5a1a854b0dc9f2141bdc771c555ee60c37950183
MIN="<the OQS_MINIMAL_BUILD list above>"
cmake -S src -B opt -G Ninja -DCMAKE_BUILD_TYPE=Release -DOQS_BUILD_ONLY_LIB=OFF -DOQS_ENABLE_TESTS=OFF -DOQS_MINIMAL_BUILD="$MIN" -DOQS_USE_OPENSSL=OFF -DOQS_ENABLE_SIG_STFL_LMS=OFF -DOQS_ENABLE_SIG_STFL_XMSS=OFF
cmake -S src -B portable <same flags> <portable flags above>
ninja -C opt; ninja -C portable
mkdir raw
for v in opt portable; do for i in 1 2 3 4 5; do
  for k in ML-KEM-512 ML-KEM-768 ML-KEM-1024; do $v/tests/speed_kem -d 3 $k > raw/${v}_run${i}_$k.txt; done
  for s in ML-DSA-44 ML-DSA-65 ML-DSA-87 SLH_DSA_PURE_SHA2_128S SLH_DSA_PURE_SHA2_128F SLH_DSA_PURE_SHAKE_128S SLH_DSA_PURE_SHAKE_128F; do $v/tests/speed_sig -d 3 $s > raw/${v}_run${i}_$s.txt; done
done; done
python3 -I bench/host/parse_liboqs_speed.py raw bench/host/host_measurements.csv
```
Total wall time about 25 minutes.
