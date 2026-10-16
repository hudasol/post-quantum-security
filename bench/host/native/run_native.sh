#!/usr/bin/env bash
# Host measured baseline (label: HOST MEASURED). Times the same mlkem-native and mldsa-native portable C code
# that runs in the emulator, natively on the PC, through the harness in bench/mcu (-DBENCH_HOST, ns timer).
# Method: build at -O2; one discarded warm up run of every binary; then RUNS runs of every binary, each pinned
# to one CPU with taskset, each doing ITERS iterations per operation. analyze_native.py drops the first
# DROP iterations of every run as in process warm up and reports the median of each run.
# These numbers are not transferable to a microcontroller. Use them only for ratios between algorithms.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
MCU="$HERE/../../mcu"
RUNS=${RUNS:-5}; ITERS=${ITERS:-220}; CPU=${CPU:-2}
OUT="$HERE/raw"; rm -rf "$OUT"; mkdir -p "$OUT"
make -s -C "$MCU" clean >/dev/null
make -s -C "$MCU" host ITERS="$ITERS"
{
  echo "key,value"
  echo "label,host measured"
  echo "date_utc,$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "cpu_model,$(grep -m1 'model name' /proc/cpuinfo | cut -d: -f2 | sed 's/^ //' | tr ',' ' ')"
  echo "kernel,$(uname -sr)"
  echo "compiler,$(gcc --version | head -1 | tr ',' ' ')"
  echo "flags,-std=c99 -O2 -DBENCH_HOST (bench/mcu/Makefile host target)"
  echo "mlkem_native,$(git -C "$MCU/ext/mlkem-native" rev-parse HEAD)"
  echo "mldsa_native,$(git -C "$MCU/ext/mldsa-native" rev-parse HEAD)"
  echo "runs,$RUNS"
  echo "iterations_per_operation_per_run,$ITERS"
  echo "pinned_cpu,$CPU"
  echo "warm_up,one discarded run of every binary before the measured runs"
  echo "inputs,deterministic xorshift32 from bench/mcu/src/bench_rng.c (insecure; benchmark inputs only)"
} > "$HERE/config.csv"
for b in "$MCU"/build/host/bench_*; do taskset -c "$CPU" "$b" > /dev/null; done
for run in $(seq 1 "$RUNS"); do
  for b in "$MCU"/build/host/bench_*; do
    taskset -c "$CPU" "$b" > "$OUT/run${run}_$(basename "$b").csv"
  done
done
python3 "$HERE/analyze_native.py"
