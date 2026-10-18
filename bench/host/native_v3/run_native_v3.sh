#!/usr/bin/env bash
# Host measured baseline, third round (label: HOST MEASURED). Same harness and library commits as the emulated
# runs (bench/mcu, -DBENCH_HOST, ns timer). Method changes against bench/host/native/ (round two), where run
# medians drifted by up to 37.5 percent:
#   1. RUNS separate processes per binary (default 15) instead of 5;
#   2. the run order of all binaries is interleaved and shuffled with a fixed seed, so slow periods of the
#      machine fall on every algorithm alike instead of on one block of runs;
#   3. every process is pinned to one CPU with taskset; ITERS iterations per operation (default 420), of which
#      analyze_native_v3.py drops the first DROP as in process warm up;
#   4. one discarded warm up pass over all binaries first;
#   5. machine state (load average, reported CPU MHz) is logged before every run.
# Use these numbers only for ratios between algorithms; they do not transfer to a microcontroller.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
MCU="$HERE/../../mcu"
RUNS=${RUNS:-15}; ITERS=${ITERS:-420}; CPU=${CPU:-2}; SEED=${SEED:-20261018}
OUT="$HERE/raw"; rm -rf "$OUT"; mkdir -p "$OUT"
make -s -C "$MCU" clean >/dev/null
make -s -C "$MCU" host ITERS="$ITERS"
cd "$MCU"   # relative binary names: the repository path may contain spaces
BINS=$(ls build/host/bench_*)
{
  echo "key,value"
  echo "label,host measured"
  echo "date_utc,$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "cpu_model,$(grep -m1 'model name' /proc/cpuinfo | cut -d: -f2 | sed 's/^ //' | tr ',' ' ')"
  echo "logical_cpus,$(nproc)"
  echo "kernel,$(uname -sr)"
  echo "environment,Linux virtual machine (WSL2) on a laptop; CPU frequency governor not controllable without administrator rights"
  echo "compiler,$(gcc --version | head -1 | tr ',' ' ')"
  echo "flags,-std=c99 -O2 -DBENCH_HOST (bench/mcu/Makefile host target)"
  echo "mlkem_native,$(git -C ext/mlkem-native rev-parse HEAD)"
  echo "mldsa_native,$(git -C ext/mldsa-native rev-parse HEAD)"
  echo "runs_per_binary,$RUNS"
  echo "iterations_per_operation_per_run,$ITERS"
  echo "pinned_cpu,$CPU"
  echo "order_seed,$SEED"
  echo "warm_up,one discarded pass over all binaries, then the first iterations of each run are dropped in analysis"
} > "$HERE/config.csv"
for b in $BINS; do taskset -c "$CPU" "./$b" > /dev/null; done
ORDER=$(python3 -c "
import random,sys
bins=sys.argv[1].split(); runs=int(sys.argv[2]); rng=random.Random(int(sys.argv[3]))
jobs=[(r,b) for r in range(1,runs+1) for b in bins]; rng.shuffle(jobs)
print(' '.join(f'{r}:{b}' for r,b in jobs))" "$BINS" "$RUNS" "$SEED")
echo "seq,run,binary,loadavg_1min,cpu_mhz" > "$HERE/state.csv"
i=0
for job in $ORDER; do
  i=$((i+1)); run=${job%%:*}; b=${job#*:}
  mhz=$(grep -m1 'cpu MHz' /proc/cpuinfo | cut -d: -f2 | tr -d ' ')
  echo "$i,$run,$(basename "$b"),$(cut -d' ' -f1 /proc/loadavg),$mhz" >> "$HERE/state.csv"
  taskset -c "$CPU" "./$b" > "$OUT/run${run}_$(basename "$b").csv"
done
python3 "$HERE/analyze_native_v3.py"
