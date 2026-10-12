#!/usr/bin/env bash
# Build and run the harness on the PC. Output = HOST MEASUREMENT (nanoseconds), only a self-test
# of the harness and of bench/stats/analyze_runs.py. Never mix with microcontroller numbers.
set -euo pipefail
cd "$(dirname "$0")"
ITERS="${ITERS:-50}"
make -s host ITERS="$ITERS"
mkdir -p host_selftest
for b in build/host/bench_*; do
  n="$(basename "$b")"
  "$b" > "host_selftest/$n.csv"
  echo "$n: $(grep -c '^BENCH' host_selftest/$n.csv) rows, $(grep '^CHECK' host_selftest/$n.csv)"
done
