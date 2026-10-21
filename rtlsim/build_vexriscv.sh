#!/usr/bin/env bash
# Generate the VexRiscv core (rtlsim/vexriscv/GenRtlsimVex.scala) with sbt at the pinned VexRiscv
# commit and build a Verilator model with the small C++ testbench rtlsim/vexriscv/tb_vex.cpp.
# sbt (free, Apache-2.0) is fetched at a pinned release; it downloads Scala and SpinalHDL from
# Maven Central. Everything lands in WORK_DIR, outside the repository. Author: Huda Mueen.
# STATUS (2026-10-21): not run. The sbt launcher could not retrieve sbt 1.6.0 (the version in
# VexRiscv project/build.properties): Maven Central answered HTTP 429 to its requests, and
# no mirror was used. VexRiscv was cut (first in the round 5 cut order); this file was never
# built or run.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/config.sh"
V="$WORK_DIR/vex"
mkdir -p "$V"
cd "$V"
if [ ! -x sbt/bin/sbt ]; then
  curl -sSL -o "sbt-$SBT_VERSION.tgz" "https://github.com/sbt/sbt/releases/download/v$SBT_VERSION/sbt-$SBT_VERSION.tgz"
  echo "$SBT_SHA256  sbt-$SBT_VERSION.tgz" | sha256sum -c -
  tar xzf "sbt-$SBT_VERSION.tgz"
fi
[ -d VexRiscv/.git ] || git clone -q "$VEX_URL" VexRiscv
git -C VexRiscv checkout -q "$VEX_COMMIT"
[ "$(git -C VexRiscv rev-parse HEAD)" = "$VEX_COMMIT" ]
cp "$HERE/vexriscv/GenRtlsimVex.scala" VexRiscv/src/main/scala/vexriscv/demo/
( cd VexRiscv && nice -n 10 ../sbt/bin/sbt -batch "runMain vexriscv.demo.GenRtlsimVex" > "$V/sbt.log" 2>&1 ) \
  || { tail -30 "$V/sbt.log" >&2; exit 1; }
mkdir -p build
nice -n 10 verilator --cc --exe --build -j 1 -O3 -Wno-fatal -Wno-lint -Wno-style \
  --top-module VexRiscv -Mdir build/obj VexRiscv/VexRiscv.v "$HERE/vexriscv/tb_vex.cpp" \
  > build/verilator.log 2>&1 || { tail -30 build/verilator.log >&2; exit 1; }
ls -l build/obj/VVexRiscv
