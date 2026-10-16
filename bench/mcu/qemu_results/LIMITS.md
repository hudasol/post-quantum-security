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
