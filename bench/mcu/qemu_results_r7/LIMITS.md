# What this emulated Falcon-512 check can and cannot show

Label: **emulated**. Produced by `bench/mcu/run_qemu_falcon.sh`; configuration in `config.csv`. A functional check on
an emulated Cortex-M4 (QEMU mps2-an386): it shows that the pinned padded Falcon-512 code builds for the instruction set,
signs, verifies and rejects a modified message and a modified signature, with its stack high water marks and image
size. It is NOT cycle accurate and gives no cycle count or time; QEMU models no cycle counter, caches or flash wait
states. It does not replace or adjust any RTL simulated number. A real Cortex-M board with a real radio remains future
work.
