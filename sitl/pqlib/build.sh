#!/bin/sh
# Build mlkem-native (ML-KEM-768) and mldsa-native (ML-DSA-44) as host shared libraries for the software in
# the loop gateway of round 6, from the commits pinned by rtlsim/config.sh (tag v2.0.0 of each project),
# portable C back end, outside the repository. Nothing built here is committed.
# Licences: mlkem-native and mldsa-native, Apache-2.0 OR ISC OR MIT (LICENSE of each project).
# Usage: sh sitl/pqlib/build.sh [source folder with mlkem-native/ and mldsa-native/] [output folder]
# Author: Huda Mueen.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
SRC=${1:-../third_party/wp7_work/rtl}
OUT=${2:-../third_party/sitl6_pqlib}
MLKEM_COMMIT=d1b2fe782888bdb761a50336012923180be7f502
MLDSA_COMMIT=834a90d5e846ffa1e1611bd24e160bb2e9b86d35
if [ ! -d "$SRC/mlkem-native/.git" ]; then
  git clone -q https://github.com/pq-code-package/mlkem-native.git "$SRC/mlkem-native"
  git -C "$SRC/mlkem-native" checkout -q $MLKEM_COMMIT
fi
if [ ! -d "$SRC/mldsa-native/.git" ]; then
  git clone -q https://github.com/pq-code-package/mldsa-native.git "$SRC/mldsa-native"
  git -C "$SRC/mldsa-native" checkout -q $MLDSA_COMMIT
fi
test "$(git -C "$SRC/mlkem-native" rev-parse HEAD)" = "$MLKEM_COMMIT" || { echo "unexpected mlkem-native commit"; exit 1; }
test "$(git -C "$SRC/mldsa-native" rev-parse HEAD)" = "$MLDSA_COMMIT" || { echo "unexpected mldsa-native commit"; exit 1; }
mkdir -p "$OUT"
CC=${CC:-gcc}
CFLAGS="-O2 -fPIC -shared -std=c99 -D_GNU_SOURCE"
nice -n 10 $CC $CFLAGS -DMLK_CONFIG_PARAMETER_SET=768 -I"$SRC/mlkem-native/mlkem" \
  "$SRC/mlkem-native/mlkem/mlkem_native.c" "$HERE/randombytes.c" -o "$OUT/libmlkem768.so"
nice -n 10 $CC $CFLAGS -DMLD_CONFIG_PARAMETER_SET=44 -I"$SRC/mldsa-native/mldsa" \
  "$SRC/mldsa-native/mldsa/mldsa_native.c" "$HERE/randombytes.c" -o "$OUT/libmldsa44.so"
{
  echo "mlkem_commit=$MLKEM_COMMIT"
  echo "mldsa_commit=$MLDSA_COMMIT"
  echo "compiler=$($CC --version | head -1)"
  echo "cflags=$CFLAGS"
} > "$OUT/build_info.txt"
ls -l "$OUT"
