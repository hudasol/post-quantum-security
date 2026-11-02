#!/usr/bin/env bash
# Round 7: check that the SHAKE256 mapping of rtlsim/proto/sw/falcon_shim/fips202.h (SHAKE256 of mldsa-native)
# gives the same Falcon-512 output as the SHAKE256 that PQClean ships with Falcon. Both host builds compile the
# pinned Falcon folder with the same deterministic test generator (not a secure generator), make one key pair and
# sign five messages; the outputs (five signatures and the public key) must be byte identical. PQClean has no
# release tag; its master commit of 2026-08-04 is used, whose Falcon folder equals the pinned one apart from build
# files. Writes rtlsim/results/logs/proto_r7/falcon_shim_check.txt. Author: Huda Mueen.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/../config.sh"
source "$HERE/config.sh"
PQCLEAN_URL="https://github.com/PQClean/PQClean.git"
PQCLEAN_COMMIT="0586a824fc0d49df0b6b6e9179d8d15d06d0974f"
PQ="$PROTO_TP/pqclean"
if [ ! -d "$PQ/.git" ]; then git clone -q "$PQCLEAN_URL" "$PQ"; fi
git -C "$PQ" checkout -q "$PQCLEAN_COMMIT"
FAL="$PROTO_TP/liboqs/$FALCON_SUBDIR"
MLDSA="$WORK_DIR/mldsa-native/mldsa"
SHIM="$HERE/sw/falcon_shim"
T="$(mktemp -d)"
cat > "$T/rb.c" <<'C'
#include <stddef.h>
#include <stdint.h>
/* deterministic test generator for this check only, not a secure generator */
static uint64_t st = 20261021u;
int RB_NAME(uint8_t *o, size_t n)
{
  for (size_t i = 0; i < n; i++) { st = st * 6364136223846793005ULL + 1442695040888963407ULL; o[i] = (uint8_t)(st >> 56); }
  return 0;
}
C
cat > "$T/t.c" <<'C'
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include "api.h"
int main(void)
{
  static uint8_t pk[897], sk[1281], sig[666], m[44];
  size_t sl;
  memset(m, 7, sizeof m);
  if (PQCLEAN_FALCONPADDED512_CLEAN_crypto_sign_keypair(pk, sk)) return 1;
  for (int r = 0; r < 5; r++)
  {
    m[0] = (uint8_t)r;
    if (PQCLEAN_FALCONPADDED512_CLEAN_crypto_sign_signature(sig, &sl, m, sizeof m, sk)) return 2;
    if (PQCLEAN_FALCONPADDED512_CLEAN_crypto_sign_verify(sig, sl, m, sizeof m, pk)) return 3;
    fwrite(sig, 1, sl, stdout);
  }
  fwrite(pk, 1, sizeof pk, stdout);
  return 0;
}
C
SRC=$(for s in codec common fft fpr keygen pqclean rng sign vrfy; do echo "$FAL/$s.c"; done)
gcc -O2 -w -DRB_NAME=randombytes -DMLD_CONFIG_PARAMETER_SET=44 -I"$SHIM" -I"$MLDSA" -I"$FAL" "$T/t.c" "$T/rb.c" $SRC \
  "$MLDSA/src/fips202/fips202.c" "$MLDSA/src/fips202/keccakf1600.c" -o "$T/a"
gcc -O2 -w -DRB_NAME=PQCLEAN_randombytes -I"$PQ/common" -I"$FAL" "$T/t.c" "$T/rb.c" $SRC "$PQ/common/fips202.c" -o "$T/b"
"$T/a" > "$T/a.bin"
"$T/b" > "$T/b.bin"
OUT="$HERE/../results/logs/proto_r7/falcon_shim_check.txt"
{
  echo "liboqs_commit=$LIBOQS_COMMIT falcon_folder=$FALCON_SUBDIR"
  echo "pqclean_commit=$PQCLEAN_COMMIT (SHAKE256 of PQClean common/fips202.c)"
  echo "mldsa_commit=$MLDSA_COMMIT (SHAKE256 of mldsa-native through the shim)"
  echo "bytes_compared=$(wc -c < "$T/a.bin")"
  echo "sha256_shim=$(sha256sum "$T/a.bin" | cut -d' ' -f1)"
  echo "sha256_pqclean=$(sha256sum "$T/b.bin" | cut -d' ' -f1)"
  if cmp -s "$T/a.bin" "$T/b.bin"; then echo "result=identical"; else echo "result=different"; fi
} > "$OUT"
cat "$OUT"
rm -rf "$T"
