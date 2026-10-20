#!/usr/bin/env bash
# Build one bare metal RV32IMC ELF per parameter set for the Ibex simple system.
# Libraries are compiled from the pinned clones in WORK_DIR with their portable
# C backends (no native backend options set). The simple system crt0.S and
# simple_system_common.c are used from the Ibex clone; the link script is
# generated from the Ibex clone's link.ld with wider memory regions.
# Output: WORK_DIR/rtlsim_build/<set>.elf. Author: Huda Mueen.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/config.sh"

CC="${CROSS}gcc"
OUT="$WORK_DIR/rtlsim_build"
COMMON="$WORK_DIR/ibex/examples/sw/simple_system/common"
mkdir -p "$OUT"

# Link script: same sections as the stock script, wider ram and stack regions.
sed -e "s|ram         : ORIGIN = 0x00100000, LENGTH = 0x30000|ram         : ORIGIN = 0x00100000, LENGTH = $RAM_LENGTH|" \
    -e "s|stack       : ORIGIN = 0x00130000, LENGTH = 0x8000|stack       : ORIGIN = $STACK_ORIGIN, LENGTH = $STACK_LENGTH|" \
    "$COMMON/link.ld" > "$OUT/link.ld"
grep -q "LENGTH = $RAM_LENGTH" "$OUT/link.ld"
grep -q "LENGTH = $STACK_LENGTH" "$OUT/link.ld"

CFLAGS="$ARCH_FLAGS $OPT_FLAGS $COMMON_CFLAGS -isystem $PICOLIBC_DIR/include"
LIBC="$PICOLIBC_DIR/lib/$PICOLIBC_MULTILIB/libc.a"
LIBGCC="$($CC -march=rv32im -mabi=ilp32 -print-libgcc-file-name)"
[ -f "$LIBC" ] && [ -f "$LIBGCC" ]

# Support objects shared by every ELF. The stock common code is built with -Os
# as in Ibex common.mk; it is not inside any timed interval except putchar.
$CC $ARCH_FLAGS -Os $COMMON_CFLAGS -I"$COMMON" -c "$COMMON/crt0.S" -o "$OUT/crt0.o"
$CC $ARCH_FLAGS -Os $COMMON_CFLAGS -I"$COMMON" -c "$COMMON/simple_system_common.c" -o "$OUT/common.o"
$CC $CFLAGS -c "$HERE/sw/bench_rng.c" -o "$OUT/bench_rng.o"

link() {
  local name="$1"; shift
  $CC $ARCH_FLAGS -static -nostdlib -nostartfiles -T "$OUT/link.ld" \
    "$OUT/crt0.o" "$OUT/common.o" "$OUT/bench_rng.o" "$@" \
    "$LIBC" "$LIBGCC" -o "$OUT/$name.elf"
  ${CROSS}size "$OUT/$name.elf"
}

MLKEM="$WORK_DIR/mlkem-native/mlkem"
for p in 512 768 1024; do
  $CC $CFLAGS -DMLK_CONFIG_PARAMETER_SET=$p -I"$MLKEM" \
    -c "$MLKEM/mlkem_native.c" -o "$OUT/mlkem$p.o"
  $CC $CFLAGS -DMLK_CONFIG_PARAMETER_SET=$p -DBENCH_KEM=$p -DBENCH_RUNS=$BENCH_RUNS \
    -I"$MLKEM" -I"$COMMON" -c "$HERE/sw/bench.c" -o "$OUT/bench_kem$p.o"
  link "ML-KEM-$p" "$OUT/bench_kem$p.o" "$OUT/mlkem$p.o"
done

MLDSA="$WORK_DIR/mldsa-native/mldsa"
for p in 44 65 87; do
  $CC $CFLAGS -DMLD_CONFIG_PARAMETER_SET=$p -I"$MLDSA" \
    -c "$MLDSA/mldsa_native.c" -o "$OUT/mldsa$p.o"
  $CC $CFLAGS -DMLD_CONFIG_PARAMETER_SET=$p -DBENCH_DSA=$p -DBENCH_RUNS=$BENCH_RUNS \
    -I"$MLDSA" -I"$COMMON" -c "$HERE/sw/bench.c" -o "$OUT/bench_dsa$p.o"
  link "ML-DSA-$p" "$OUT/bench_dsa$p.o" "$OUT/mldsa$p.o"
done

{
  echo "compiler=$($CC --version | head -1)"
  echo "cflags=$CFLAGS"
  echo "libc=$LIBC"
  echo "libgcc=$LIBGCC"
} > "$OUT/build_info.txt"
cat "$OUT/build_info.txt"
