#!/usr/bin/env bash
# Record the tool versions, pinned commits, licences and Ibex configuration
# used for the RTL simulation runs into rtlsim/results/environment.txt.
# Author: Huda Mueen.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/config.sh"
OUT="$HERE/results/environment.txt"
mkdir -p "$HERE/results"
{
  echo "ibex_commit=$(git -C "$WORK_DIR/ibex" rev-parse HEAD)"
  echo "ibex_describe=$(git -C "$WORK_DIR/ibex" describe --tags --always)"
  echo "ibex_licence=$(grep -m1 -o 'Apache License' "$WORK_DIR/ibex/LICENSE") $(grep -m1 -o 'Version 2.0' "$WORK_DIR/ibex/LICENSE")"
  echo "ibex_config_name=$IBEX_CONFIG"
  echo "ibex_fusesoc_opts=$(cd "$WORK_DIR/ibex" && "$WORK_DIR/ibexvenv/bin/python" util/ibex_config.py "$IBEX_CONFIG" fusesoc_opts)"
  echo "ibex_simple_system_ram=$(grep -m1 -o 'Depth(1024\*1024/4)' "$WORK_DIR/ibex/examples/simple_system/rtl/ibex_simple_system.sv") words of 32 bits"
  echo "ibex_instr_cycle_delay=0 (INSTR_CYCLE_DELAY default in ibex_simple_system.core)"
  echo "mlkem_commit=$(git -C "$WORK_DIR/mlkem-native" rev-parse HEAD) $(git -C "$WORK_DIR/mlkem-native" describe --tags --exact-match)"
  echo "mlkem_licence=Apache-2.0 OR ISC OR MIT (library sources, per LICENSE)"
  echo "mldsa_commit=$(git -C "$WORK_DIR/mldsa-native" rev-parse HEAD) $(git -C "$WORK_DIR/mldsa-native" describe --tags --exact-match)"
  echo "mldsa_licence=Apache-2.0 OR ISC OR MIT (library sources, per LICENSE)"
  echo "verilator=$(verilator --version)"
  echo "fusesoc=$("$WORK_DIR/ibexvenv/bin/fusesoc" --version)"
  echo "compiler=$(${CROSS}gcc --version | head -1)"
  echo "cflags=$ARCH_FLAGS $OPT_FLAGS $COMMON_CFLAGS"
  echo "libc=picolibc $PICOLIBC_MULTILIB ($(dpkg-query -W -f='${Version}' picolibc-riscv64-unknown-elf 2>/dev/null || echo unknown))"
  echo "link_ram=0x100000 length $RAM_LENGTH; stack 0x${STACK_ORIGIN#0x} length $STACK_LENGTH"
  echo "seed=$SEED"
  echo "bench_runs=$BENCH_RUNS"
} > "$OUT"
cat "$OUT"
