#!/usr/bin/env bash
# Build a Verilator model of the CV32E40P example testbench (example_tb/core at the pinned
# commit): the RTL listed in cv32e40p_manifest.flist plus the testbench files, top tb_top, with
# Verilator's timing support for the testbench clock and reset. No RTL file is changed. The
# example testbench at this tag still passes the old parameter names PULP_XPULP and PULP_CLUSTER
# to cv32e40p_top, whose parameters are named COREV_PULP and COREV_CLUSTER at the same tag
# (rtl/cv32e40p_top.sv); a copy of cv32e40p_tb_subsystem.sv in the build directory renames these
# two port mappings (both values stay 0) and nothing else. Verilator 5.020 stops on BLKANDNBLK in
# cv32e40p_cs_registers.sv (per bit generate assignments to mhpmcounter_q, mhpmevent_q and
# mcountinhibit_q); the check is switched off with -Wno-BLKANDNBLK, so the counter CSRs are a
# known risk: the harness checks that mcycle counts and that results are correct and repeatable.
# Output: WORK_DIR/cv32e40p_build/obj/Vtb_top. Author: Huda Mueen.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/config.sh"
SRC="$WORK_DIR/cv32e40p"
OUT="$WORK_DIR/cv32e40p_build"
TB="$SRC/example_tb/core"
mkdir -p "$OUT"
sed "s#\${DESIGN_RTL_DIR}#$SRC/rtl#g" "$SRC/cv32e40p_manifest.flist" > "$OUT/manifest.f"
sed -e 's/\.PULP_XPULP      (PULP_XPULP)/.COREV_PULP      (PULP_XPULP)/' \
    -e 's/\.PULP_CLUSTER    (PULP_CLUSTER)/.COREV_CLUSTER   (PULP_CLUSTER)/' \
    "$TB/cv32e40p_tb_subsystem.sv" > "$OUT/cv32e40p_tb_subsystem.sv"
[ "$(diff "$TB/cv32e40p_tb_subsystem.sv" "$OUT/cv32e40p_tb_subsystem.sv" | grep -c '^>')" = 2 ]
nice -n 10 verilator --binary --timing -j 1 -O3 --x-assign fast --x-initial fast \
  -Wno-fatal -Wno-lint -Wno-style -Wno-MULTIDRIVEN -Wno-UNOPTFLAT -Wno-BLKANDNBLK \
  --top-module tb_top -Mdir "$OUT/obj" \
  -f "$OUT/manifest.f" +incdir+"$TB/include" \
  "$TB/include/perturbation_pkg.sv" "$TB/amo_shim.sv" "$TB/dp_ram.sv" \
  "$TB/riscv_rvalid_stall.sv" "$TB/riscv_gnt_stall.sv" \
  "$TB/cv32e40p_random_interrupt_generator.sv" "$TB/mm_ram.sv" \
  "$OUT/cv32e40p_tb_subsystem.sv" "$TB/tb_top.sv" > "$OUT/verilator.log" 2>&1 \
  || { tail -40 "$OUT/verilator.log" >&2; exit 1; }
ls -l "$OUT/obj/Vtb_top"
