#!/usr/bin/env bash
# Round 7: run the Falcon-512 per command image of one core on its Verilator model (the models of rounds 5 and 6,
# unchanged; see run.sh). Logs go to rtlsim/results/logs/proto_r7/<core>/per_command_falcon512.log with a
# .simstats.txt beside them. Author: Huda Mueen. Usage: run_falcon.sh ibex|cv32e40p
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/../config.sh"
source "$HERE/config.sh"
CORE="${1:?usage: run_falcon.sh ibex|cv32e40p}"
PROTO_BUILD_R7="${PROTO_BUILD_R7:-$WORK_DIR/rtl7_proto_build}"
LOG_DIR="$HERE/../results/logs/proto_r7/$CORE"
ELF_DIR="$PROTO_BUILD_R7/$CORE/timing"
RUN_DIR="$PROTO_BUILD_R7/runs_$CORE"
mkdir -p "$LOG_DIR" "$RUN_DIR"
img=per_command_falcon512
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
  nice -n 10 "$SIM" +firmware="$ELF_DIR/$img.hex" 2>&1 | sed "s|$CV32_WORK_DIR|\$CV32_WORK_DIR|g" \
    > "$LOG_DIR/$img.log" || true
  : > "$LOG_DIR/$img.simstats.txt"
else
  echo "unknown core $CORE" >&2; exit 2
fi
end=$(date +%s)
echo "wall_seconds=$((end - start))" >> "$LOG_DIR/$img.simstats.txt"
echo "finished $CORE $img ($((end - start)) s)"
