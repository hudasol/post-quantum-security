#!/usr/bin/env bash
# Build the Cortex-M4 images that the cycle model traces. Everything is built OUTSIDE the repository.
#   1. pqm4 at the pinned commit (with submodules) for PLATFORM=mps2-an386, speed binaries of
#      ML-KEM-512/768/1024 (clean, m4fspeed, m4fstack) and ML-DSA-44/65/87 (clean, m4f, m4fstack),
#      built with MUPQ_ITERATIONS=10 for ML-KEM and MUPQ_ITERATIONS=50 for ML-DSA (signing is variable
#      time, so more messages are needed for a stable mean), each iteration with different inputs.
#   2. The repository harness bench/mcu (mlkem-native v2.0.0, mldsa-native v2.0.0) for mps2-an386,
#      -O2, BENCH_ITERS=10, with the libraries cloned at the pins of bench/mcu/fetch_libs.sh.
#   3. pqcrystals lowram ML-DSA key expansion (external check against ePrint 2026/1333 rows).
# Benchmark subjects only. Licences: pqm4 Apache-2.0 or CC0-1.0 (per file; schemes carry their own),
# mlkem-native and mldsa-native Apache-2.0 or ISC or MIT (see their LICENSE files), dilithium-lowram CC0 or Apache-2.0 (its LICENSE file).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(dirname "$HERE")"
WORK=${WORK:-$(cd "$(dirname "$0")/../.." && pwd)/work}  # outside the repository
PQM4=$WORK/pqm4_cm
PQM4_PIN=5e5cc76d0b072ee7077e58afcbc619a1a67a53b4
mkdir -p "$WORK"
if [ ! -d "$PQM4/.git" ]; then
  git clone --quiet https://github.com/mupq/pqm4 "$PQM4"
  git -C "$PQM4" checkout --quiet $PQM4_PIN
  git -C "$PQM4" submodule update --init --recursive --depth 1
fi
test "$(git -C "$PQM4" rev-parse HEAD)" = "$PQM4_PIN" || { echo "pqm4 pin mismatch" >&2; exit 1; }

impls=""
for p in 512 768 1024; do impls="$impls crypto_kem/ml-kem-$p/m4fspeed crypto_kem/ml-kem-$p/m4fstack mupq/pqclean/crypto_kem/ml-kem-$p/clean"; done
for p in 44 65 87; do impls="$impls crypto_sign/ml-dsa-$p/m4f crypto_sign/ml-dsa-$p/m4fstack mupq/pqclean/crypto_sign/ml-dsa-$p/clean"; done
for i in $impls; do
  n=$(echo "$i" | sed 's#/#_#g')
  case "$i" in *crypto_sign*) its=${DSA_ITERS:-50};; *) its=10;; esac
  ( cd "$PQM4" && make -j2 PLATFORM=mps2-an386 MUPQ_ITERATIONS=$its IMPLEMENTATION_PATH="$i" "elf/${n}_speed.elf" >/dev/null 2>&1 ) \
    || { echo "build failed: $i" >&2; exit 1; }
  echo "built $n"
done

# Harness libraries at the pins named in bench/mcu/fetch_libs.sh (cloned outside the repository)
LIBS=$WORK/harness_libs
mkdir -p "$LIBS"
fetch() { local name=$1 url=$2 tag=$3 want=$4
  [ -d "$LIBS/$name/.git" ] || git clone --quiet --depth 1 --branch "$tag" "$url" "$LIBS/$name"
  test "$(git -C "$LIBS/$name" rev-parse HEAD)" = "$want" || { echo "pin mismatch $name" >&2; exit 1; }
}
fetch mlkem-native https://github.com/pq-code-package/mlkem-native v2.0.0 d1b2fe782888bdb761a50336012923180be7f502
fetch mldsa-native https://github.com/pq-code-package/mldsa-native v2.0.0 834a90d5e846ffa1e1611bd24e160bb2e9b86d35
HB=$WORK/harness_build
for alg in mlkem mldsa; do
  if [ $alg = mlkem ]; then sets="512 768 1024"; else sets="44 65 87"; fi
  for s in $sets; do
    make -s -C "$REPO/bench/mcu" arm EXT="$LIBS" BUILD="$HB" ALG=$alg SET=$s ITERS=10 ARM_OPT=-O2 \
      LDSCRIPT=board/qemu/link.ld STARTUP=board/qemu/startup.c >/dev/null
    echo "built harness $alg $s"
  done
done

# External check (ePrint 2026/1333): pqcrystals lowram ML-DSA at the tag named by the paper's
# crypto-benchmark manifest (crypto-benchmark-0.0.16), key expansion from a seed only, built for Cortex-M4
# with -Ofast (the Release setting of its CMake file; the paper does not state its flags).
EXTD=$WORK/ext_check
mkdir -p "$EXTD" "$WORK/ext_build"
LOWRAM_PIN=36139b4e9a9b895dc2b1f3e3599fedab25172a9d
[ -d "$EXTD/dilithium-lowram/.git" ] || git clone --quiet --depth 1 --branch crypto-benchmark-0.0.16 \
  https://github.com/sebastien-riou/dilithium-lowram "$EXTD/dilithium-lowram"
test "$(git -C "$EXTD/dilithium-lowram" rev-parse HEAD)" = "$LOWRAM_PIN" || { echo "pin mismatch dilithium-lowram" >&2; exit 1; }
SRC=$EXTD/dilithium-lowram/libpqcrystals-mldsa-lowram/source
for p in 44 87; do
  arm-none-eabi-gcc -mcpu=cortex-m4 -mthumb -mfpu=fpv4-sp-d16 -mfloat-abi=hard -Ofast -std=c99 -DMLDSA_PSET=$p \
    -I"$SRC" -I"$SRC/../include" \
    "$SRC"/{sign,packing,polyvec,poly,ntt,reduce,rounding,lowram,smallpoly,smallntt_3329,fips202,symmetric-shake,randombytes}.c \
    "$HERE/drivers/lowram_keyexp.c" "$REPO/bench/mcu/board/qemu/startup.c" -T"$REPO/bench/mcu/board/qemu/link.ld" \
    --specs=nano.specs --specs=nosys.specs -Wl,--gc-sections -o "$WORK/ext_build/lowram_keyexp_$p.elf" 2>/dev/null
  echo "built lowram key expansion $p"
done
arm-none-eabi-gcc --version | head -1
