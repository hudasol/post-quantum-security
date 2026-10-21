#!/usr/bin/env bash
# Fetch ns-3 and the signetlabdei lorawan module at pinned versions and build
# only the modules this study needs, in optimized mode, under nice with -j2.
# Nothing fetched here is committed to the repository.
#
# Pins:
#   ns-3            tag ns-3.48 (github.com/nsnam/ns-3-dev-git)
#   lorawan module  tag v0.3.7, commit a13219eebab664729eeed2694fa1cedf89e9c8d8
#                   (its NS3-VERSION file states "release ns-3.48")
#
# Usage: netsim/fetch_build.sh [third_party_dir]
# The default third party folder is a sibling of the repository checkout.
set -euo pipefail

TP="${1:-$(cd "$(dirname "$0")/../.." && pwd)/third_party}"
NS3_TAG="ns-3.48"
LORAWAN_COMMIT="a13219eebab664729eeed2694fa1cedf89e9c8d8"
NS3_DIR="$TP/ns-3-dev"
JOBS="${NETSIM_JOBS:-2}"

mkdir -p "$TP"
if [ ! -d "$NS3_DIR/.git" ]; then
  git clone -q --depth 1 --branch "$NS3_TAG" https://github.com/nsnam/ns-3-dev-git "$NS3_DIR"
fi
if [ ! -d "$NS3_DIR/src/lorawan/.git" ]; then
  git clone -q https://github.com/signetlabdei/lorawan "$NS3_DIR/src/lorawan"
fi
git -C "$NS3_DIR/src/lorawan" checkout -q "$LORAWAN_COMMIT"
want="release $NS3_TAG"
have="$(tr -d '\n' < "$NS3_DIR/src/lorawan/NS3-VERSION")"
if [ "$have" != "$want" ]; then
  echo "lorawan NS3-VERSION is '$have', expected '$want'" >&2
  exit 1
fi

# Local build fix: at this pin some lorawan sources use NS_LOG macros without
# including ns3/log.h (they compile only with precompiled headers). Add the
# include to each such file; this changes no model behaviour.
for f in $(grep -l 'NS_LOG_COMPONENT_DEFINE' "$NS3_DIR"/src/lorawan/model/*.cc "$NS3_DIR"/src/lorawan/helper/*.cc); do
  if ! grep -q '#include "ns3/log.h"' "$f"; then
    sed -i '0,/^#include /s//#include "ns3\/log.h"\n#include /' "$f"
  fi
done

# Scenario programs live in netsim/scenarios and are copied into scratch/.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -d "$SCRIPT_DIR/scenarios" ]; then
  for f in "$SCRIPT_DIR"/scenarios/*.cc; do
    [ -e "$f" ] && cp "$f" "$NS3_DIR/scratch/netsim-$(basename "$f")"
  done
fi

cd "$NS3_DIR"
nice -n 10 ./ns3 configure --build-profile=optimized \
  --disable-tests --disable-examples --disable-python \
  --enable-modules="lr-wpan;sixlowpan;internet;applications;lorawan" \
  > "$TP/ns3_configure.log" 2>&1
nice -n 10 ./ns3 build -j "$JOBS" > "$TP/ns3_build.log" 2>&1
echo "ns-3 build finished: $NS3_DIR"
