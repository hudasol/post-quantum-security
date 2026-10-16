#!/usr/bin/env bash
# Emulator sweep (free). Builds the six benchmark images for two emulated cores and three optimisation
# levels and runs each one in QEMU:
#   mps2-an386  Cortex-M4   -mfpu=fpv4-sp-d16  board/qemu/link.ld
#   mps2-an505  Cortex-M33  -mfpu=fpv5-sp-d16  board/qemu_an505/link.ld (UART0 secure alias)
#   optimisation -O2, -Os, -O3
# Label: EMULATED. Gives correctness checks, stack high water marks and image size only. It gives NO cycle
# counts: QEMU does not model the DWT cycle counter, caches or flash wait states, so BENCH rows print 0 and
# are discarded here. Real cycles need a real board (docs/BOARD_RUN_PROTOCOL.md).
# Needs: qemu-system-arm (or QEMU=<path>), arm-none-eabi-gcc, and ./fetch_libs.sh already run.
# Regenerates every file in qemu_results/ in one go.
set -euo pipefail
cd "$(dirname "$0")"
QEMU=${QEMU:-qemu-system-arm}
OUT=qemu_results; rm -rf "$OUT"; mkdir -p "$OUT" build/arm
ITERS=${ITERS:-3}; SPAN=${SPAN:-131072}
OPTS=${OPTS:-"-O2 -Os -O3"}
BOARDS=${BOARDS:-"an386 an505"}

{
  echo "key,value"
  echo "label,emulated"
  echo "date_utc,$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "qemu,$("$QEMU" --version | head -1 | tr ',' ' ')"
  echo "compiler,$(arm-none-eabi-gcc --version | head -1 | tr ',' ' ')"
  echo "mlkem_native,$(git -C ext/mlkem-native rev-parse HEAD)"
  echo "mldsa_native,$(git -C ext/mldsa-native rev-parse HEAD)"
  echo "iterations_per_operation,$ITERS"
  echo "stack_paint_span_bytes,$SPAN"
  echo "optimisation_levels,$OPTS"
  echo "boards,$BOARDS"
  echo "common_flags,-mthumb -mfloat-abi=hard -ffunction-sections -fdata-sections -std=c99 -DBENCH_DISABLE_IRQ; link -Wl --gc-sections --specs=nano.specs --specs=nosys.specs"
  echo "random_inputs,deterministic xorshift32 from src/bench_rng.c (insecure; benchmark inputs only); no seed argument"
} > "$OUT/config.csv"

echo "board,cpu,opt,alg,param,check,ok,fail" > "$OUT/checks.csv"
echo "board,cpu,opt,alg,param,op,stack_bytes" > "$OUT/stack.csv"
echo "board,cpu,opt,alg,param,text_bytes,data_bytes,bss_bytes,note" > "$OUT/image_size.csv"

for board in $BOARDS; do
  case $board in
    an386) cpu=cortex-m4;  fpu=fpv4-sp-d16; ld=board/qemu/link.ld;       extra="" ;;
    an505) cpu=cortex-m33; fpu=fpv5-sp-d16; ld=board/qemu_an505/link.ld; extra="-DBENCH_UART_BASE=0x50200000u" ;;
    *) echo "unknown board $board"; exit 2 ;;
  esac
  for opt in $OPTS; do
    for cfg in mlkem:512 mlkem:768 mlkem:1024 mldsa:44 mldsa:65 mldsa:87; do
      alg=${cfg%%:*}; set=${cfg##*:}
      make -s arm CPU=$cpu FPU=$fpu ALG=$alg SET=$set ITERS=$ITERS STACK_SPAN=$SPAN ARM_OPT=$opt \
           ARM_EXTRA="$extra" LDSCRIPT=$ld STARTUP=board/qemu/startup.c >/dev/null 2>&1 \
        || { echo "BUILD FAILED $board $opt $cfg"; exit 1; }
      elf=build/arm/${alg}_${set}.elf
      log=build/arm/${board}_${opt}_${alg}_${set}.log
      timeout 900 "$QEMU" -M mps2-$board -cpu $cpu -nographic -semihosting -kernel "$elf" > "$log" \
        || { echo "RUN FAILED $board $opt $cfg"; exit 1; }
      pre="$board,$cpu,$opt"
      grep '^CHECK' "$log" | sed "s/^CHECK,/$pre,/" | tr -d '\r' >> "$OUT/checks.csv"
      grep '^STACK' "$log" | sed "s/^STACK,/$pre,/" | tr -d '\r' >> "$OUT/stack.csv"
      arm-none-eabi-size "$elf" | awk -v p="$pre" -v a=$alg -v s=$set \
        'NR==2{print p","a","s","$1","$2","$3",image includes harness and C library; baseline not subtracted"}' >> "$OUT/image_size.csv"
      echo "done $board $opt $cfg"
    done
  done
done

cat > "$OUT/LIMITS.md" <<'EOF'
# What these emulated results can and cannot show

Label: **emulated**. Produced by `bench/mcu/run_qemu.sh`; configuration in `config.csv`.

| Question | Can QEMU answer it? |
|---|---|
| Does the code build for the instruction set and run correctly? | Yes (`checks.csv`). |
| Stack high water mark of each operation | Yes, by stack painting (`stack.csv`). Deterministic for one binary; it includes the harness frames above the library call, so it slightly overstates the library alone. |
| Image size | Yes (`image_size.csv`). It includes the harness and the C library; no baseline is subtracted, so it is an upper bound for the library's flash cost. |
| Cycle counts | **No.** QEMU does not model the DWT cycle counter; the BENCH rows print 0 and are discarded. |
| Instruction cache, data cache, ART accelerator, prefetch | **No.** QEMU does not model them. |
| Flash wait states and bus contention | **No.** Memory accesses take no modelled time. |
| Energy | **No.** |
| Timing of any kind, including host wall time of the emulator | **No.** Emulator run time depends on the host and must never be presented as device time or cycles. |
| Behaviour of a specific microcontroller (clock tree, memory map, peripherals) | **No.** The MPS2 boards are FPGA reference designs, not a product. |

Real cycle counts need a real board; the procedure is in `docs/BOARD_RUN_PROTOCOL.md`.
EOF
python3 analyze_qemu.py
echo "results in $OUT/"
