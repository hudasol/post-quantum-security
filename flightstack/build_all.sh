#!/usr/bin/env bash
# Build every target in turn (one at a time, two jobs, nice 10).
# Author: Huda Mueen.
HERE="$(cd "$(dirname "$0")" && pwd)"
TP="${1:-${THIRD_PARTY:?pass the third party folder or set THIRD_PARTY}}"
while IFS=, read -r stack target _; do
  [ "$stack" = stack ] && continue
  status="$HERE/../data/flightstack/raw/${stack}_${target}/build_status.txt"
  if [ -f "$status" ] && grep -q "^exit_code=0$" "$status" && [ "${REBUILD:-0}" != 1 ]; then
    echo "$stack $target already built, skipped (set REBUILD=1 to build again)"; continue
  fi
  bash "$HERE/build.sh" "$stack" "$target" "$TP"
done < "$HERE/targets.csv"
