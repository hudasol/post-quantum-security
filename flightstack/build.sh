#!/usr/bin/env bash
# Build one flight stack firmware target at a time, save the small text
# artefacts that the memory extraction needs into data/flightstack/raw/, and
# delete the build tree.
#
# Author: Huda Mueen.
#
# Usage: flightstack/build.sh px4|ardupilot TARGET [third_party_dir]
#   px4 targets:       px4_fmu-v6x_default, px4_fmu-v5_default, ...
#   ardupilot targets: CubeOrange, MatekF405-Wing, ... (vehicle: copter)
# Saved per target: objdump section headers (VMA, LMA, size, flags), the
# arm-none-eabi-size outputs, the MEMORY block of the linker script used, the
# linker memory usage lines, a build status file. Failures are recorded, not hidden.
set -uo pipefail
STACK="$1"; TARGET="$2"; TP="${3:-${THIRD_PARTY:?pass the third party folder or set THIRD_PARTY}}"
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$HERE")"
OUT="$ROOT/data/flightstack/raw/${STACK}_${TARGET}"
mkdir -p "$OUT"
export PATH="$TP/venv_flightstack/bin:$PATH"
LOG="$TP/build_${STACK}_${TARGET}.log"
start=$(date -u +%s)

memory_block () {  # linker script -> MEMORY block
  awk '/^[ \t]*MEMORY/{f=1} f{print} f&&/^[ \t]*}/{exit}' "$1"
}

if [ "$STACK" = px4 ]; then
  SRC="$TP/PX4-Autopilot"
  ( cd "$SRC" && nice -n 10 make "$TARGET" -j2 ) > "$LOG" 2>&1
  rc=$?
  BUILD="$SRC/build/$TARGET"
  ELF="$(ls "$BUILD"/*.elf 2>/dev/null | head -1)"
  board_dir="$(echo "$TARGET" | sed -E 's/_default$//; s/_/\//')"
  LD="$SRC/boards/$board_dir/nuttx-config/scripts/script.ld"
  LD_CITE="boards/$board_dir/nuttx-config/scripts/script.ld"
  COMMIT="$(git -C "$SRC" rev-parse HEAD)"
else
  SRC="$TP/ardupilot"
  rm -rf "$SRC/build"   # waf keeps one configuration for the whole build folder
  ( cd "$SRC" && nice -n 10 ./waf configure --board "$TARGET" && nice -n 10 ./waf copter -j2 ) > "$LOG" 2>&1
  rc=$?
  BUILD="$SRC/build/$TARGET"
  ELF="$BUILD/bin/arducopter"
  LD="$BUILD/ldscript.ld"
  LD_CITE="libraries/AP_HAL_ChibiOS/hwdef/$TARGET/hwdef.dat via build/$TARGET/ldscript.ld (generated)"
  COMMIT="$(git -C "$SRC" rev-parse HEAD)"
  [ -f "$BUILD/hwdef.h" ] && grep -E "#define (HAL_RAM0_START|HAL_MEMORY_REGIONS|HAL_RAM_RESERVE_START|BOARD_FLASH_SIZE|HAL_STORAGE_SIZE|APJ_BOARD_ID|STM32_FLASH_.*|HAL_EXPECTED_SYSID|HAL_CRASHDUMP|CH_CFG_ST_RESOLUTION|HAL_.*FLASH.*)\b" "$BUILD/hwdef.h" > "$OUT/hwdef_defines.txt"
fi
end=$(date -u +%s)
{
  echo "stack=$STACK"; echo "target=$TARGET"; echo "commit=$COMMIT"; echo "exit_code=$rc"
  echo "build_seconds=$((end-start))"; echo "jobs=2"; echo "nice=10"
  echo "toolchain=$(arm-none-eabi-gcc --version | head -1)"
  echo "linker_script=$LD_CITE"; echo "built_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} > "$OUT/build_status.txt"
grep -E "^ *(FLASH|ITCM|DTCM|AXI|SRAM|RAM|BKPRAM|CCM|ram|flash)[A-Za-z0-9_]*: +[0-9]" "$LOG" | tail -20 > "$OUT/memory_usage_lines.txt" || true
tail -40 "$LOG" | sed "s|$TP|<third_party>|g; s|$ROOT|<repo>|g" > "$OUT/build_log_tail.txt"
if [ "$rc" -eq 0 ] && [ -n "$ELF" ] && [ -f "$ELF" ]; then
  strip_paths () { sed "s|$TP|<third_party>|g; s|$ROOT|<repo>|g"; }
  arm-none-eabi-objdump -h "$ELF" | strip_paths > "$OUT/objdump_h.txt"
  arm-none-eabi-size "$ELF" | strip_paths > "$OUT/size_berkeley.txt"
  arm-none-eabi-size -A -x "$ELF" | strip_paths > "$OUT/size_sysv.txt"
  [ -f "$LD" ] && memory_block "$LD" > "$OUT/memory_block.ld"
  echo "elf=$(basename "$ELF")" >> "$OUT/build_status.txt"
  echo "elf_sha256=$(sha256sum "$ELF" | cut -d' ' -f1)" >> "$OUT/build_status.txt"
fi
# delete the build tree once the sizes are saved (disk is scarce)
if [ "$STACK" = px4 ]; then rm -rf "$BUILD"; else rm -rf "$SRC/build"; fi
echo "$STACK $TARGET exit $rc in $((end-start)) s"
