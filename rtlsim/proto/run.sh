#!/usr/bin/env bash
# Run the protocol images of one core on its Verilator model (models of round 5, unchanged):
#   ibex      Ibex simple system, small configuration (rtlsim/build_sim.sh); instruction trace off
#   cv32e40p  CV32E40P example testbench (rtlsim/build_sim_cv32e40p.sh)
# Logs go to rtlsim/results/logs/proto/<core>/<image>.log with a <image>.simstats.txt beside them.
# Usage: run.sh ibex|cv32e40p [image ...]   (default: every image of config.sh). Author: Huda Mueen.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/../config.sh"
source "$HERE/config.sh"
CORE="${1:?usage: run.sh ibex|cv32e40p [image ...]}"
shift
IMAGES=("$@")
if [ ${#IMAGES[@]} -eq 0 ]; then
  read -r -a IMAGES <<< "$PROTO_IMAGES"
fi
LOG_DIR="$HERE/../results/logs/proto/$CORE"
ELF_DIR="$PROTO_BUILD/$CORE/timing"
RUN_DIR="$PROTO_BUILD/runs_$CORE"
mkdir -p "$LOG_DIR" "$RUN_DIR"

for img in "${IMAGES[@]}"; do
  start=$(date +%s)
  if [ "$CORE" = ibex ]; then
    SIM="$WORK_DIR/ibex/build/lowrisc_ibex_ibex_simple_system_0/sim-verilator/Vibex_simple_system"
    d="$RUN_DIR/$img"
    rm -rf "$d"; mkdir -p "$d"
    ( cd "$d" && nice -n 10 "$SIM" +ibex_tracer_enable=0 --meminit=ram,"$ELF_DIR/$img.elf" > stdout.txt 2>&1 )
    cp "$d/ibex_simple_system.log" "$LOG_DIR/$img.log"
    grep -E "Executed cycles|Simulation speed" "$d/stdout.txt" > "$LOG_DIR/$img.simstats.txt" || true
  elif [ "$CORE" = cv32e40p ]; then
    SIM="$CV32_WORK_DIR/cv32e40p_build/obj/Vtb_top"
    # the testbench prints its own source path on $finish; the work directory is masked
    nice -n 10 "$SIM" +firmware="$ELF_DIR/$img.hex" 2>&1 | sed "s|$CV32_WORK_DIR|\$CV32_WORK_DIR|g" \
      > "$LOG_DIR/$img.log" || true
    : > "$LOG_DIR/$img.simstats.txt"
  else
    echo "unknown core $CORE" >&2; exit 2
  fi
  end=$(date +%s)
  echo "wall_seconds=$((end - start))" >> "$LOG_DIR/$img.simstats.txt"
  echo "finished $CORE $img ($((end - start)) s)"
done
