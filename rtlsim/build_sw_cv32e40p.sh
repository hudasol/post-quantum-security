#!/usr/bin/env bash
# Build one bare metal RV32IMC ELF and hex file per parameter set for the CV32E40P example
# testbench. The benchmark program (sw/bench.c, sw/bench_rng.c), the libraries, the compiler and
# every compiler flag are the ones of build_sw.sh for Ibex; only the start up code (crt0.S and
# vectors.S of example_tb/core/custom at the pinned commit), its link script (stack enlarged to
# CV32E40P_STACK_SIZE with --defsym) and the output functions (sw/cv32e40p/) differ.
# Output: WORK_DIR/cv32e40p_sw/<set>.elf and <set>.hex. Author: Huda Mueen.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/config.sh"

CC="${CROSS}gcc"
OUT="$WORK_DIR/cv32e40p_sw"
CUST="$WORK_DIR/cv32e40p/example_tb/core/custom"
SHIM="$HERE/sw/cv32e40p"
mkdir -p "$OUT"

CFLAGS="$ARCH_FLAGS $OPT_FLAGS $COMMON_CFLAGS -isystem $PICOLIBC_DIR/include"
LIBC="$PICOLIBC_DIR/lib/$PICOLIBC_MULTILIB/libc.a"
LIBGCC="$($CC -march=rv32im -mabi=ilp32 -print-libgcc-file-name)"
[ -f "$LIBC" ] && [ -f "$LIBGCC" ]

$CC $ARCH_FLAGS -Os $COMMON_CFLAGS -c "$CUST/crt0.S" -o "$OUT/crt0.o"
$CC $ARCH_FLAGS -Os $COMMON_CFLAGS -c "$CUST/vectors.S" -o "$OUT/vectors.o"
$CC $ARCH_FLAGS -Os $COMMON_CFLAGS -I"$SHIM" -c "$SHIM/cv32e40p_common.c" -o "$OUT/common.o"
$CC $CFLAGS -c "$HERE/sw/bench_rng.c" -o "$OUT/bench_rng.o"

link() {
  local name="$1"; shift
  $CC $ARCH_FLAGS -static -nostdlib -nostartfiles -T "$CUST/link.ld" \
    -Wl,--defsym=__stack_size=$CV32E40P_STACK_SIZE \
    "$OUT/crt0.o" "$OUT/vectors.o" "$OUT/common.o" "$OUT/bench_rng.o" "$@" \
    "$LIBC" "$LIBGCC" -o "$OUT/$name.elf"
  ${CROSS}size "$OUT/$name.elf"
  ${CROSS}objcopy -O verilog "$OUT/$name.elf" "$OUT/$name.hex"
}

MLKEM="$WORK_DIR/mlkem-native/mlkem"
for p in 512 768 1024; do
  $CC $CFLAGS -DMLK_CONFIG_PARAMETER_SET=$p -I"$MLKEM" \
    -c "$MLKEM/mlkem_native.c" -o "$OUT/mlkem$p.o"
  $CC $CFLAGS -DMLK_CONFIG_PARAMETER_SET=$p -DBENCH_KEM=$p -DBENCH_RUNS=$BENCH_RUNS \
    -I"$MLKEM" -I"$SHIM" -c "$HERE/sw/bench.c" -o "$OUT/bench_kem$p.o"
  link "ML-KEM-$p" "$OUT/bench_kem$p.o" "$OUT/mlkem$p.o"
done

MLDSA="$WORK_DIR/mldsa-native/mldsa"
for p in 44 65 87; do
  $CC $CFLAGS -DMLD_CONFIG_PARAMETER_SET=$p -I"$MLDSA" \
    -c "$MLDSA/mldsa_native.c" -o "$OUT/mldsa$p.o"
  $CC $CFLAGS -DMLD_CONFIG_PARAMETER_SET=$p -DBENCH_DSA=$p -DBENCH_RUNS=$BENCH_RUNS \
    -I"$MLDSA" -I"$SHIM" -c "$HERE/sw/bench.c" -o "$OUT/bench_dsa$p.o"
  link "ML-DSA-$p" "$OUT/bench_dsa$p.o" "$OUT/mldsa$p.o"
done

{
  echo "compiler=$($CC --version | head -1)"
  echo "cflags=$CFLAGS"
  echo "startup=example_tb/core/custom crt0.S vectors.S link.ld at $CV32E40P_COMMIT"
  echo "stack_size=$CV32E40P_STACK_SIZE"
  echo "libc=$LIBC"
  echo "libgcc=$LIBGCC"
} > "$OUT/build_info.txt"
cat "$OUT/build_info.txt"
