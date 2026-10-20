#!/usr/bin/env bash
# Clone Ibex, mlkem-native and mldsa-native at pinned commits into WORK_DIR
# (outside the repository) and verify the checked out commits.
# Author: Huda Mueen.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/config.sh"
mkdir -p "$WORK_DIR"

fetch() {
  local url="$1" dir="$2" commit="$3"
  if [ ! -d "$dir/.git" ]; then
    git clone -q "$url" "$dir"
  fi
  git -C "$dir" checkout -q "$commit"
  local got
  got="$(git -C "$dir" rev-parse HEAD)"
  if [ "$got" != "$commit" ]; then
    echo "commit mismatch in $dir: $got" >&2
    exit 1
  fi
  echo "$dir $got"
}

fetch "$IBEX_URL" "$WORK_DIR/ibex" "$IBEX_COMMIT"
fetch "$MLKEM_URL" "$WORK_DIR/mlkem-native" "$MLKEM_COMMIT"
fetch "$MLDSA_URL" "$WORK_DIR/mldsa-native" "$MLDSA_COMMIT"
