#!/usr/bin/env bash
# Emulator check (free): build the six benchmark images for a Cortex-M4 and run them in QEMU mps2-an386.
# Gives correctness checks, stack high water marks and image size. It gives NO cycle counts: QEMU does not model
# the DWT cycle counter, so BENCH rows print 0. Real cycles need a real board (docs/NO_PURCHASE_PLAN.md).
# Needs: qemu-system-arm, gcc-arm-none-eabi, and ./fetch_libs.sh already run.
set -euo pipefail
cd "$(dirname "$0")"
OUT=qemu_results; mkdir -p "$OUT" build/arm
ITERS=${ITERS:-3}; SPAN=${SPAN:-131072}
echo "alg,param,check,ok,fail" > "$OUT/checks.csv"; echo "alg,param,op,stack_bytes" > "$OUT/stack.csv"
echo "alg,param,text_bytes,data_bytes,bss_bytes,note" > "$OUT/image_size.csv"
for cfg in mlkem:512 mlkem:768 mlkem:1024 mldsa:44 mldsa:65 mldsa:87; do
  alg=${cfg%%:*}; set=${cfg##*:}
  make -s arm CPU=cortex-m4 FPU=fpv4-sp-d16 ALG=$alg SET=$set ITERS=$ITERS STACK_SPAN=$SPAN \
       LDSCRIPT=board/qemu/link.ld STARTUP=board/qemu/startup.c >/dev/null 2>&1
  elf=build/arm/${alg}_${set}.elf
  log="$OUT/${alg}_${set}.log"
  timeout 600 qemu-system-arm -M mps2-an386 -cpu cortex-m4 -nographic -semihosting -kernel "$elf" > "$log" || { echo "FAILED $cfg"; exit 1; }
  grep '^CHECK' "$log" | sed 's/^CHECK,//' >> "$OUT/checks.csv"
  grep '^STACK' "$log" | sed 's/^STACK,//' >> "$OUT/stack.csv"
  arm-none-eabi-size "$elf" | awk -v a=$alg -v p=$set 'NR==2{print a","p","$1","$2","$3",image includes harness and C library; baseline not subtracted"}' >> "$OUT/image_size.csv"
  rm -f "$log"
done
cat "$OUT/checks.csv" "$OUT/stack.csv" "$OUT/image_size.csv"
