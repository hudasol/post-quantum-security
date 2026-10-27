#!/usr/bin/env bash
# Fetch the classical library and the MAVLink C library at pinned commits into PROTO_TP, outside the
# repository. Nothing fetched here is committed. Author: Huda Mueen.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/../config.sh"
source "$HERE/config.sh"
mkdir -p "$PROTO_TP"

fetch() {
  local url="$1" commit="$2" dir="$3"
  if [ ! -d "$dir/.git" ]; then
    git clone -q "$url" "$dir"
  fi
  git -C "$dir" fetch -q origin "$commit" 2>/dev/null || true
  git -C "$dir" checkout -q "$commit"
  [ "$(git -C "$dir" rev-parse HEAD)" = "$commit" ]
  echo "$dir at $(git -C "$dir" rev-parse HEAD)"
}

fetch "$MONO_URL" "$MONO_COMMIT" "$PROTO_TP/monocypher"
fetch "$MAVLINK_URL" "$MAVLINK_COMMIT" "$PROTO_TP/mavlink_c"
# Licence files and notices that docs/LICENSES.md records.
head -5 "$PROTO_TP/monocypher/LICENCE.md"
sed -n 10,14p "$PROTO_TP/mavlink_c/mavlink_sha256.h"
