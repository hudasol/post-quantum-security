#!/usr/bin/env bash
# Fetch and PIN the benchmark libraries. Fails if a tag does not resolve to the commit recorded
# in docs/BENCHMARK_PLAN.md (commits read on 2026-10-11, see data/raw/S5_benchmark_plan_facts.md).
# Downloaded code is untrusted data: review before flashing, never run it as root on a machine you care about.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
EXT="$HERE/ext"
mkdir -p "$EXT"

fetch() { # name url tag expected_commit
  local name=$1 url=$2 tag=$3 want=$4
  if [ ! -d "$EXT/$name/.git" ]; then
    git clone --quiet --depth 1 --branch "$tag" "$url" "$EXT/$name"
  fi
  local got
  got="$(git -C "$EXT/$name" rev-parse HEAD)"
  if [ "$got" != "$want" ]; then
    echo "COMMIT MISMATCH for $name $tag: expected $want, got $got" >&2
    exit 1
  fi
  echo "ok  $name $tag $got"
}

# Experiment E1 (ML-KEM / ML-DSA)
fetch mlkem-native https://github.com/pq-code-package/mlkem-native v2.0.0 d1b2fe782888bdb761a50336012923180be7f502
fetch mldsa-native https://github.com/pq-code-package/mldsa-native v2.0.0 834a90d5e846ffa1e1611bd24e160bb2e9b86d35

# Experiment E2 (hash-based firmware signature verification) - optional: ./fetch_libs.sh e2
if [ "${1:-}" = "e2" ]; then
  fetch wolfssl https://github.com/wolfSSL/wolfssl v5.9.4-stable 3c5eead44904df64e6a5a1f4ebdce377d35a849a
  fetch wolfboot https://github.com/wolfSSL/wolfBoot v2.10.0 eb710fe1656f20addb736b5c205f18bf53fa2998
  fetch tf-psa-crypto https://github.com/Mbed-TLS/TF-PSA-Crypto v1.2.0 73c5da561c8e5253db7b1fb440eda86fde8d8024
fi
