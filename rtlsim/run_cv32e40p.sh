#!/usr/bin/env bash
# Run each benchmark on the CV32E40P Verilator model. The testbench prints the program output
# on standard output and ends at the exit write ("EXIT SUCCESS" or "EXIT FAILURE").
# Usage: run_cv32e40p.sh [set ...]  (default: all six parameter sets)
# Logs go to rtlsim/results/logs/cv32e40p/<set>.log. Author: Huda Mueen.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/config.sh"
SIM="$WORK_DIR/cv32e40p_build/obj/Vtb_top"
SW="$WORK_DIR/cv32e40p_sw"
LOG_DIR="$HERE/results/logs/cv32e40p"
mkdir -p "$LOG_DIR"
SETS=("$@")
if [ ${#SETS[@]} -eq 0 ]; then
  SETS=(ML-KEM-512 ML-KEM-768 ML-KEM-1024 ML-DSA-44 ML-DSA-65 ML-DSA-87)
fi
for s in "${SETS[@]}"; do
  start=$(date +%s)
  # the testbench prints its own source path on $finish; the work directory is masked
  nice -n 10 "$SIM" +firmware="$SW/$s.hex" 2>&1 | sed "s|$WORK_DIR|\$WORK_DIR|g" > "$LOG_DIR/$s.log" || true
  end=$(date +%s)
  echo "wall_seconds=$((end - start))" > "$LOG_DIR/$s.simstats.txt"
  echo "finished $s ($((end - start)) s)"
done
