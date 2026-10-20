#!/usr/bin/env bash
# Run each benchmark ELF on the Ibex simple system Verilator model.
# The instruction trace is disabled (+ibex_tracer_enable=0, a plusarg of
# rtl/ibex_tracer.sv) because it grows by gigabytes per run; it does not change
# the simulated cycle counts. Each run uses its own directory because the model writes
# ibex_simple_system.log (ASCII port output) into the current directory.
# Usage: run.sh [set ...]   (default: all six parameter sets)
# Logs are copied to rtlsim/results/logs/<set>.log. Author: Huda Mueen.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/config.sh"

SIM="$WORK_DIR/ibex/build/lowrisc_ibex_ibex_simple_system_0/sim-verilator/Vibex_simple_system"
ELF_DIR="$WORK_DIR/rtlsim_build"
RUN_DIR="$WORK_DIR/rtlsim_runs"
LOG_DIR="$HERE/results/logs"
JOBS="${JOBS:-2}"
mkdir -p "$RUN_DIR" "$LOG_DIR"

SETS=("$@")
if [ ${#SETS[@]} -eq 0 ]; then
  SETS=(ML-KEM-512 ML-KEM-768 ML-KEM-1024 ML-DSA-44 ML-DSA-65 ML-DSA-87)
fi

run_one() {
  local s="$1"
  local d="$RUN_DIR/$s"
  rm -rf "$d"; mkdir -p "$d"
  ( cd "$d" && "$SIM" +ibex_tracer_enable=0 --meminit=ram,"$ELF_DIR/$s.elf" > stdout.txt 2>&1 )
  cp "$d/ibex_simple_system.log" "$LOG_DIR/$s.log"
  grep -E "Executed cycles|Simulation speed" "$d/stdout.txt" > "$LOG_DIR/$s.simstats.txt" || true
  echo "finished $s"
}

for s in "${SETS[@]}"; do
  while [ "$(jobs -rp | wc -l)" -ge "$JOBS" ]; do sleep 1; done
  run_one "$s" &
done
wait
