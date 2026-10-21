#!/usr/bin/env bash
# Add the CV32E40P commit, tag, licence and simulator version to rtlsim/results/environment.txt
# (replacing earlier cv32e40p_ lines; the Ibex lines are kept). Author: Huda Mueen.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/config.sh"
OUT="$HERE/results/environment.txt"
D="$WORK_DIR/cv32e40p"
tmp="$(mktemp)"
grep -v '^cv32e40p_' "$OUT" > "$tmp" || true
{
  cat "$tmp"
  echo "cv32e40p_commit=$(git -C "$D" rev-parse HEAD)"
  echo "cv32e40p_describe=tag cv32e40p_v1.8.3"
  echo "cv32e40p_licence=$(head -1 "$D/LICENSE" | sed 's/^ *//')"
  echo "cv32e40p_verilator=$(verilator --version)"
  echo "cv32e40p_stack_size=$CV32E40P_STACK_SIZE"
} > "$OUT"
rm -f "$tmp"
grep '^cv32e40p_' "$OUT"
