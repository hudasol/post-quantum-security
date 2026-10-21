#!/usr/bin/env bash
# Clone CV32E40P at the pinned commit into WORK_DIR (outside the repository) and verify it.
# Author: Huda Mueen.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/config.sh"
mkdir -p "$WORK_DIR"
dir="$WORK_DIR/cv32e40p"
if [ ! -d "$dir/.git" ]; then
  git clone -q "$CV32E40P_URL" "$dir"
fi
git -C "$dir" checkout -q "$CV32E40P_COMMIT"
got="$(git -C "$dir" rev-parse HEAD)"
[ "$got" = "$CV32E40P_COMMIT" ] || { echo "commit mismatch in $dir: $got" >&2; exit 1; }
echo "$dir $got"
