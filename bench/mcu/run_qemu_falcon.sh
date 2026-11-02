#!/usr/bin/env bash
# Round 7, optional item: functional check of padded Falcon-512 on an emulated Cortex-M4 (QEMU mps2-an386), at -O2,
# -Os and -O3, with the harness, board files and flags of run_qemu.sh. Label: EMULATED. It gives correctness checks,
# stack high water marks and image size only, NO cycle counts, and is NOT cycle accurate: QEMU models no cycle
# counter, caches or flash wait states (qemu_results/LIMITS.md). It never replaces or adjusts an RTL simulated
# number. A real Cortex-M board with a real radio remains future work.
# Inputs outside the repository (nothing is committed): MLDSA_DIR, the mldsa-native/mldsa folder at the pinned commit
# (SHAKE256 only), and FALCON_DIR, the liboqs 0.16.0 folder src/sig/falcon/pqclean_falcon-padded-512_clean.
# Writes qemu_results_r7/. Author: Huda Mueen.
set -euo pipefail
cd "$(dirname "$0")"
QEMU=${QEMU:-qemu-system-arm}
MLDSA_DIR=${MLDSA_DIR:?set MLDSA_DIR}
FALCON_DIR=${FALCON_DIR:?set FALCON_DIR}
SHIM=../../rtlsim/proto/sw/falcon_shim
OUT=qemu_results_r7; rm -rf "$OUT"; mkdir -p "$OUT" build/arm_r7
ITERS=${ITERS:-3}; SPAN=${SPAN:-131072}
OPTS=${OPTS:-"-O2 -Os -O3"}
[ "$(git -C "$MLDSA_DIR/.." rev-parse HEAD)" = 834a90d5e846ffa1e1611bd24e160bb2e9b86d35 ]
[ "$(git -C "$FALCON_DIR" rev-parse HEAD)" = 5a1a854b0dc9f2141bdc771c555ee60c37950183 ]
{
  echo "key,value"
  echo "label,emulated"
  echo "date_utc,$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "qemu,$("$QEMU" --version | head -1 | tr ',' ' ')"
  echo "compiler,$(arm-none-eabi-gcc --version | head -1 | tr ',' ' ')"
  echo "falcon,liboqs 0.16.0 5a1a854b0dc9f2141bdc771c555ee60c37950183 src/sig/falcon/pqclean_falcon-padded-512_clean"
  echo "shake256,mldsa-native 834a90d5e846ffa1e1611bd24e160bb2e9b86d35 through rtlsim/proto/sw/falcon_shim/fips202.h"
  echo "iterations,$ITERS"
  echo "stack_paint_span_bytes,$SPAN"
  echo "optimisation_levels,$OPTS"
  echo "board,an386 (Cortex-M4 with single precision FPU; Falcon uses its integer emulated floating point)"
  echo "common_flags,-mcpu=cortex-m4 -mthumb -mfpu=fpv4-sp-d16 -mfloat-abi=hard -ffunction-sections -fdata-sections -std=c99 -DBENCH_DISABLE_IRQ; link -Wl --gc-sections --specs=nano.specs --specs=nosys.specs"
} > "$OUT/config.csv"
echo "board,cpu,opt,alg,param,check,ok,fail" > "$OUT/checks.csv"
echo "board,cpu,opt,alg,param,op,stack_bytes" > "$OUT/stack.csv"
echo "board,cpu,opt,alg,param,text_bytes,data_bytes,bss_bytes,note" > "$OUT/image_size.csv"
FSRC=$(for s in codec common fft fpr keygen pqclean rng sign vrfy; do echo "$FALCON_DIR/$s.c"; done)
for opt in $OPTS; do
  elf=build/arm_r7/falcon512_${opt#-}.elf
  log=build/arm_r7/an386_${opt}_falcon512.log
  arm-none-eabi-gcc -mcpu=cortex-m4 -mthumb -mfpu=fpv4-sp-d16 -mfloat-abi=hard -ffunction-sections -fdata-sections \
    $opt -std=c99 -DBENCH_ITERS=$ITERS -DBENCH_CLOCK_HZ=0 -DBENCH_RUN_ID=0 -DBENCH_STACK_SPAN=$SPAN -DBENCH_DISABLE_IRQ \
    -DBENCH_OPT_NOTE="\"$opt\"" -DMLD_CONFIG_PARAMETER_SET=44 -Isrc -I"$SHIM" -I"$MLDSA_DIR" -I"$FALCON_DIR" \
    src/bench_falcon.c $FSRC "$MLDSA_DIR/src/fips202/fips202.c" "$MLDSA_DIR/src/fips202/keccakf1600.c" src/bench_rng.c \
    board/qemu/startup.c -Tboard/qemu/link.ld -Wl,--gc-sections --specs=nano.specs --specs=nosys.specs -o "$elf" \
    2> >(grep -v "warning" >&2 || true)
  timeout 900 "$QEMU" -M mps2-an386 -cpu cortex-m4 -nographic -semihosting -kernel "$elf" > "$log"
  pre="an386,cortex-m4,$opt"
  grep '^CHECK' "$log" | sed "s/^CHECK,/$pre,/" | tr -d '\r' >> "$OUT/checks.csv"
  grep '^STACK' "$log" | sed "s/^STACK,/$pre,/" | tr -d '\r' >> "$OUT/stack.csv"
  arm-none-eabi-size "$elf" | awk -v p="$pre" \
    'NR==2{print p",Falcon,Falcon-512 (padded),"$1","$2","$3",image includes key generation, signing, verification, harness and C library"}' >> "$OUT/image_size.csv"
  echo "done an386 $opt falcon512"
done
cat > "$OUT/LIMITS.md" <<'EOM'
# What this emulated Falcon-512 check can and cannot show

Label: **emulated**. Produced by `bench/mcu/run_qemu_falcon.sh`; configuration in `config.csv`. A functional check on
an emulated Cortex-M4 (QEMU mps2-an386): it shows that the pinned padded Falcon-512 code builds for the instruction set,
signs, verifies and rejects a modified message and a modified signature, with its stack high water marks and image
size. It is NOT cycle accurate and gives no cycle count or time; QEMU models no cycle counter, caches or flash wait
states. It does not replace or adjust any RTL simulated number. A real Cortex-M board with a real radio remains future
work.
EOM
cat "$OUT/checks.csv" "$OUT/stack.csv" "$OUT/image_size.csv"
