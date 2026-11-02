#!/usr/bin/env bash
# Round 7: build the Falcon-512 per command image for one core (ibex or cv32e40p). Compiler, flags, picolibc, the
# start up code, the stack settings, the MAVLink C library and the SHAKE256 of mldsa-native are those of the round 6
# images (build.sh); the Falcon-512 sources come from fetch_falcon.sh. The round 6 images, their logs and their
# size files are not touched: everything goes to PROTO_BUILD_R7 and rtlsim/results/logs/proto_r7/<core>/.
# Two variants, as in build.sh: timing (simulated) and gc (size only, never simulated).
# Author: Huda Mueen. Usage: build_falcon.sh ibex|cv32e40p
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/../config.sh"
source "$HERE/config.sh"
CORE="${1:?usage: build_falcon.sh ibex|cv32e40p}"
PROTO_BUILD_R7="${PROTO_BUILD_R7:-$WORK_DIR/rtl7_proto_build}"

CC="${CROSS}gcc"
SIZE="${CROSS}size"
CFLAGS="$ARCH_FLAGS $OPT_FLAGS $COMMON_CFLAGS -isystem $PICOLIBC_DIR/include"
LIBC="$PICOLIBC_DIR/lib/$PICOLIBC_MULTILIB/libc.a"
LIBGCC="$($CC -march=rv32im -mabi=ilp32 -print-libgcc-file-name)"
[ -f "$LIBC" ] && [ -f "$LIBGCC" ]

MLDSA="$WORK_DIR/mldsa-native/mldsa"
MAV="$PROTO_TP/mavlink_c"
FAL="$PROTO_TP/liboqs/$FALCON_SUBDIR"
SHIM="$HERE/sw/falcon_shim"
[ "$(git -C "$WORK_DIR/mldsa-native" rev-parse HEAD)" = "$MLDSA_COMMIT" ]
[ "$(git -C "$PROTO_TP/mavlink_c" rev-parse HEAD)" = "$MAVLINK_COMMIT" ]
[ "$(git -C "$PROTO_TP/liboqs" rev-parse HEAD)" = "$LIBOQS_COMMIT" ]

LOGS="$HERE/../results/logs/proto_r7"
mkdir -p "$LOGS/$CORE"
OUTC="$PROTO_BUILD_R7/$CORE"
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
  CSHIM="$HERE/../sw/cv32e40p"
  [ "$(git -C "$CV32_WORK_DIR/cv32e40p" rev-parse HEAD)" = "$CV32E40P_COMMIT" ]
  $CC $ARCH_FLAGS -Os $COMMON_CFLAGS -c "$CUST/crt0.S" -o "$OUTC/crt0.o"
  $CC $ARCH_FLAGS -Os $COMMON_CFLAGS -c "$CUST/vectors.S" -o "$OUTC/vectors.o"
  $CC $ARCH_FLAGS -Os $COMMON_CFLAGS -I"$CSHIM" -c "$CSHIM/cv32e40p_common.c" -o "$OUTC/common.o"
  START=("$OUTC/crt0.o" "$OUTC/vectors.o" "$OUTC/common.o")
  LDARGS=(-T "$CUST/link.ld" -Wl,--defsym=__stack_size=$CV32E40P_STACK_SIZE)
  INC="$CSHIM"
else
  echo "unknown core $CORE" >&2; exit 2
fi

FALSRC="codec common fft fpr keygen pqclean rng sign vrfy"
LIBOBJS="falcon512 mld_fips202 mld_keccakf1600 bench_rng"

build_variant() {
  local variant="$1" vflags="$2" vld="$3"
  local OBJ="$PROTO_BUILD_R7/obj_$variant" OUT="$OUTC/$variant"
  local F="$CFLAGS $vflags"
  mkdir -p "$OBJ" "$OUT"
  if [ ! -f "$OBJ/done" ]; then
    local fobjs=()
    for s in $FALSRC; do
      $CC $F -DMLD_CONFIG_PARAMETER_SET=44 -I"$SHIM" -I"$MLDSA" -I"$FAL" -c "$FAL/$s.c" -o "$OBJ/falcon_$s.o"
      fobjs+=("$OBJ/falcon_$s.o")
    done
    ${CROSS}ld -m elf32lriscv -r "${fobjs[@]}" -o "$OBJ/falcon512.o"
    $CC $F -DMLD_CONFIG_PARAMETER_SET=44 -I"$MLDSA" -c "$MLDSA/src/fips202/fips202.c" -o "$OBJ/mld_fips202.o"
    $CC $F -DMLD_CONFIG_PARAMETER_SET=44 -I"$MLDSA" -c "$MLDSA/src/fips202/keccakf1600.c" -o "$OBJ/mld_keccakf1600.o"
    $CC $F -c "$HERE/../sw/bench_rng.c" -o "$OBJ/bench_rng.o"
    touch "$OBJ/done"
  fi
  if [ "$variant" = timing ]; then
    ( cd "$OBJ" && $SIZE $(for l in $LIBOBJS; do echo "$l.o"; done) ) > "$LOGS/object_sizes.txt"
  fi
  local PF="$F -DPROTO_SEED=${PROTO_SEED}u -DSTACK_PAINT_BYTES=$STACK_PAINT_BYTES -I$INC -I$HERE/sw -I$FAL -I$MAV"
  $CC $PF -c "$HERE/sw/proto_util.c" -o "$OUT/proto_util.o"
  local img=per_command_falcon512
  $CC $PF -DPROTO_RUNS="$PROTO_RUNS" -Wno-address-of-packed-member -c "$HERE/sw/proto_falcon.c" -o "$OUT/proto_$img.o"
  $CC $ARCH_FLAGS -static -nostdlib -nostartfiles $vld "${LDARGS[@]}" "${START[@]}" "$OBJ/bench_rng.o" \
    "$OUT/proto_util.o" "$OUT/proto_$img.o" "$OBJ/falcon512.o" "$OBJ/mld_fips202.o" "$OBJ/mld_keccakf1600.o" \
    "$LIBC" "$LIBGCC" -o "$OUT/$img.elf" 2> >(grep -v "RWX permissions" >&2)
  local sizes="$LOGS/$CORE/sizes_$variant.txt"
  printf '   text\t   data\t    bss\t    dec\t    hex\tfilename\n' > "$sizes"
  ( cd "$OUT" && $SIZE "$img.elf" ) | tail -1 >> "$sizes"
  ( cd "$OUT" && $SIZE -A "$img.elf" ) | grep -v '^\.debug\|^\.comment\|^\.riscv' > "$LOGS/$CORE/sections_$variant.txt"
  if [ "$CORE" = cv32e40p ] && [ "$variant" = timing ]; then
    ${CROSS}objcopy -O verilog "$OUT/$img.elf" "$OUT/$img.hex"
  fi
  echo "$img: falcon512 mld_fips202 mld_keccakf1600" > "$LOGS/$CORE/link_objects.txt"
  cat "$sizes"
}

build_variant timing "" ""
build_variant gc "-ffunction-sections -fdata-sections" "-Wl,--gc-sections"

{
  echo "core=$CORE"
  echo "compiler=$($CC --version | head -1)"
  echo "cflags=$CFLAGS"
  echo "gc_variant_extra_cflags=-ffunction-sections -fdata-sections; ldflags=-Wl,--gc-sections (size only)"
  echo "mldsa_commit=$MLDSA_COMMIT (SHAKE256 only)"
  echo "mavlink_c_commit=$MAVLINK_COMMIT"
  echo "liboqs_tag=$LIBOQS_TAG liboqs_commit=$LIBOQS_COMMIT falcon_folder=$FALCON_SUBDIR"
  echo "runs=$PROTO_RUNS"
  echo "seed_first=$PROTO_SEED"
  echo "stack_paint_bytes=$STACK_PAINT_BYTES"
  if [ "$CORE" = cv32e40p ]; then echo "cv32e40p_commit=$CV32E40P_COMMIT stack_size=$CV32E40P_STACK_SIZE"; fi
  if [ "$CORE" = ibex ]; then echo "ibex_commit=$IBEX_COMMIT ram_length=$RAM_LENGTH stack_length=$STACK_LENGTH"; fi
} > "$LOGS/$CORE/build_info.txt"
