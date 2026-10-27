#!/usr/bin/env bash
# Build the round 6 protocol images for one core (ibex or cv32e40p). Compiler, flags, picolibc, the
# pinned mlkem-native and mldsa-native sources and the start up code are those of round 5
# (rtlsim/build_sw.sh, rtlsim/build_sw_cv32e40p.sh); the classical library and the MAVLink C library come
# from fetch.sh. One ELF per design (config.sh PROTO_IMAGES).
#
# Two variants are linked:
#   timing  the images that are simulated: round 5 flags, whole library objects linked (as round 5)
#   gc      size only, never simulated: the same sources with -ffunction-sections -fdata-sections and
#           --gc-sections, so that library code the design never calls (for example the parts of the
#           classical library that the protocol does not use) is not counted
# text, data and bss of every ELF and of every library object are written to rtlsim/results/logs/proto/.
# Author: Huda Mueen. Usage: build.sh ibex|cv32e40p
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/../config.sh"
source "$HERE/config.sh"
CORE="${1:?usage: build.sh ibex|cv32e40p}"

CC="${CROSS}gcc"
SIZE="${CROSS}size"
CFLAGS="$ARCH_FLAGS $OPT_FLAGS $COMMON_CFLAGS -isystem $PICOLIBC_DIR/include"
LIBC="$PICOLIBC_DIR/lib/$PICOLIBC_MULTILIB/libc.a"
LIBGCC="$($CC -march=rv32im -mabi=ilp32 -print-libgcc-file-name)"
[ -f "$LIBC" ] && [ -f "$LIBGCC" ]

MLKEM="$WORK_DIR/mlkem-native/mlkem"
MLDSA="$WORK_DIR/mldsa-native/mldsa"
MONO="$PROTO_TP/monocypher/src"
MAV="$PROTO_TP/mavlink_c"
[ "$(git -C "$WORK_DIR/mlkem-native" rev-parse HEAD)" = "$MLKEM_COMMIT" ]
[ "$(git -C "$WORK_DIR/mldsa-native" rev-parse HEAD)" = "$MLDSA_COMMIT" ]
[ "$(git -C "$PROTO_TP/monocypher" rev-parse HEAD)" = "$MONO_COMMIT" ]
[ "$(git -C "$PROTO_TP/mavlink_c" rev-parse HEAD)" = "$MAVLINK_COMMIT" ]

LOGS="$HERE/../results/logs/proto"
mkdir -p "$LOGS/$CORE" "$PROTO_BUILD/kat"
python3 "$HERE/gen_kat.py" "$PROTO_BUILD/kat/kat.h"

# Core start up code and link arguments (as round 5).
OUTC="$PROTO_BUILD/$CORE"
mkdir -p "$OUTC"
if [ "$CORE" = ibex ]; then
  COMMON="$WORK_DIR/ibex/examples/sw/simple_system/common"
  sed -e "s|ram         : ORIGIN = 0x00100000, LENGTH = 0x30000|ram         : ORIGIN = 0x00100000, LENGTH = $RAM_LENGTH|" \
      -e "s|stack       : ORIGIN = 0x00130000, LENGTH = 0x8000|stack       : ORIGIN = $STACK_ORIGIN, LENGTH = $STACK_LENGTH|" \
      "$COMMON/link.ld" > "$OUTC/link.ld"
  grep -q "LENGTH = $RAM_LENGTH" "$OUTC/link.ld"
  $CC $ARCH_FLAGS -Os $COMMON_CFLAGS -I"$COMMON" -c "$COMMON/crt0.S" -o "$OUTC/crt0.o"
  $CC $ARCH_FLAGS -Os $COMMON_CFLAGS -I"$COMMON" -c "$COMMON/simple_system_common.c" -o "$OUTC/common.o"
  START=("$OUTC/crt0.o" "$OUTC/common.o")
  LDARGS=(-T "$OUTC/link.ld")
  INC="$COMMON"
elif [ "$CORE" = cv32e40p ]; then
  CUST="$CV32_WORK_DIR/cv32e40p/example_tb/core/custom"
  SHIM="$HERE/../sw/cv32e40p"
  [ "$(git -C "$CV32_WORK_DIR/cv32e40p" rev-parse HEAD)" = "$CV32E40P_COMMIT" ]
  $CC $ARCH_FLAGS -Os $COMMON_CFLAGS -c "$CUST/crt0.S" -o "$OUTC/crt0.o"
  $CC $ARCH_FLAGS -Os $COMMON_CFLAGS -c "$CUST/vectors.S" -o "$OUTC/vectors.o"
  $CC $ARCH_FLAGS -Os $COMMON_CFLAGS -I"$SHIM" -c "$SHIM/cv32e40p_common.c" -o "$OUTC/common.o"
  START=("$OUTC/crt0.o" "$OUTC/vectors.o" "$OUTC/common.o")
  LDARGS=(-T "$CUST/link.ld" -Wl,--defsym=__stack_size=$CV32E40P_STACK_SIZE)
  INC="$SHIM"
else
  echo "unknown core $CORE" >&2; exit 2
fi

LIBOBJS="mlkem768 mldsa44 mld_fips202 mld_keccakf1600 monocypher monocypher_ed25519 proto_hash bench_rng"

build_variant() {
  local variant="$1" vflags="$2" vld="$3"
  local OBJ="$PROTO_BUILD/obj_$variant" OUT="$OUTC/$variant"
  local F="$CFLAGS $vflags"
  mkdir -p "$OBJ" "$OUT"
  # Library objects (portable C backends, as in round 5), built once for both cores.
  if [ ! -f "$OBJ/done" ]; then
    $CC $F -DMLK_CONFIG_PARAMETER_SET=768 -I"$MLKEM" -c "$MLKEM/mlkem_native.c" -o "$OBJ/mlkem768.o"
    $CC $F -DMLD_CONFIG_PARAMETER_SET=44 -I"$MLDSA" -c "$MLDSA/mldsa_native.c" -o "$OBJ/mldsa44.o"
    # The FIPS 202 part of mldsa-native alone, for the classical image (no ML-DSA in it).
    $CC $F -DMLD_CONFIG_PARAMETER_SET=44 -I"$MLDSA" -c "$MLDSA/src/fips202/fips202.c" -o "$OBJ/mld_fips202.o"
    $CC $F -DMLD_CONFIG_PARAMETER_SET=44 -I"$MLDSA" -c "$MLDSA/src/fips202/keccakf1600.c" -o "$OBJ/mld_keccakf1600.o"
    $CC $F -I"$MONO" -c "$MONO/monocypher.c" -o "$OBJ/monocypher.o"
    $CC $F -I"$MONO" -I"$MONO/optional" -c "$MONO/optional/monocypher-ed25519.c" -o "$OBJ/monocypher_ed25519.o"
    $CC $F -DMLD_CONFIG_PARAMETER_SET=44 -I"$MLDSA" -I"$HERE/sw" -c "$HERE/sw/proto_hash.c" -o "$OBJ/proto_hash.o"
    $CC $F -c "$HERE/../sw/bench_rng.c" -o "$OBJ/bench_rng.o"
    touch "$OBJ/done"
  fi
  if [ "$variant" = timing ]; then
    ( cd "$OBJ" && $SIZE $(for l in $LIBOBJS; do echo "$l.o"; done) ) > "$LOGS/object_sizes.txt"
  fi

  local PF="$F -DMLK_CONFIG_PARAMETER_SET=768 -DMLD_CONFIG_PARAMETER_SET=44 -DPROTO_RUNS=$PROTO_RUNS \
    -DPROTO_SEED=${PROTO_SEED}u -DSTACK_PAINT_BYTES=$STACK_PAINT_BYTES -I$INC -I$HERE/sw \
    -I$PROTO_BUILD/kat -I$MLKEM -I$MLDSA -I$MONO -I$MAV"
  $CC $PF -c "$HERE/sw/proto_util.c" -o "$OUT/proto_util.o"

  local sizes="$LOGS/$CORE/sizes_$variant.txt"
  printf '   text\t   data\t    bss\t    dec\t    hex\tfilename\n' > "$sizes"
  local sizes_a="$LOGS/$CORE/sections_$variant.txt"
  : > "$sizes_a"
  : > "$OUT/link_objects.txt"
  for img in $PROTO_IMAGES; do
    local macro="PROTO_DESIGN_$(echo "$img" | tr a-z A-Z)"
    [ "$img" = per_command_mldsa44 ] && macro=PROTO_DESIGN_PER_COMMAND
    # -Wno-address-of-packed-member silences warnings from the MAVLink headers; it does not change code.
    $CC $PF -Wno-address-of-packed-member -D"$macro" -c "$HERE/sw/proto_bench.c" -o "$OUT/proto_$img.o"
    local libs
    case "$img" in
      primitives)          libs="monocypher monocypher_ed25519 mlkem768 mldsa44 proto_hash" ;;
      classical)           libs="monocypher monocypher_ed25519 proto_hash mld_fips202 mld_keccakf1600" ;;
      pq_only)             libs="mlkem768 mldsa44 proto_hash" ;;
      hybrid_f1)           libs="monocypher mlkem768 mldsa44 proto_hash" ;;
      per_command_mldsa44) libs="mldsa44" ;;
      mavlink_tag)         libs="" ;;
    esac
    local objs=()
    for l in $libs; do objs+=("$OBJ/$l.o"); done
    $CC $ARCH_FLAGS -static -nostdlib -nostartfiles $vld "${LDARGS[@]}" "${START[@]}" "$OBJ/bench_rng.o" \
      "$OUT/proto_util.o" "$OUT/proto_$img.o" "${objs[@]}" "$LIBC" "$LIBGCC" -o "$OUT/$img.elf" \
      2> >(grep -v "RWX permissions" >&2)
    ( cd "$OUT" && $SIZE "$img.elf" ) | tail -1 >> "$sizes"
    ( cd "$OUT" && $SIZE -A "$img.elf" ) | grep -v '^\.debug\|^\.comment\|^\.riscv' >> "$sizes_a"
    if [ "$CORE" = cv32e40p ] && [ "$variant" = timing ]; then
      ${CROSS}objcopy -O verilog "$OUT/$img.elf" "$OUT/$img.hex"
    fi
    echo "$img: ${libs:-none}" >> "$OUT/link_objects.txt"
  done
  cp "$OUT/link_objects.txt" "$LOGS/$CORE/link_objects.txt"
  cat "$sizes"
}

build_variant timing "" ""
build_variant gc "-ffunction-sections -fdata-sections" "-Wl,--gc-sections"

{
  echo "core=$CORE"
  echo "compiler=$($CC --version | head -1)"
  echo "cflags=$CFLAGS"
  echo "gc_variant_extra_cflags=-ffunction-sections -fdata-sections; ldflags=-Wl,--gc-sections (size only)"
  echo "mlkem_commit=$MLKEM_COMMIT"
  echo "mldsa_commit=$MLDSA_COMMIT"
  echo "monocypher_commit=$MONO_COMMIT"
  echo "mavlink_c_commit=$MAVLINK_COMMIT"
  echo "runs=$PROTO_RUNS"
  echo "seed_first=$PROTO_SEED"
  echo "stack_paint_bytes=$STACK_PAINT_BYTES"
  if [ "$CORE" = cv32e40p ]; then echo "cv32e40p_commit=$CV32E40P_COMMIT stack_size=$CV32E40P_STACK_SIZE"; fi
  if [ "$CORE" = ibex ]; then echo "ibex_commit=$IBEX_COMMIT ram_length=$RAM_LENGTH stack_length=$STACK_LENGTH"; fi
} > "$LOGS/$CORE/build_info.txt"
