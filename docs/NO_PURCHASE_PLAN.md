# Hardware experiments without buying anything

Author: Huda Mueen. Written 2026-10-12. Tags: **[retrieved]** means read from a page on 2026-10-12 (URL given); **[inference]** is my reasoning.

No purchase is required for any step of this project. The plan has three tiers. Use the first tier that answers your question.

## Tier 1. Emulator: correctness, flash size and stack size checks (free)

- QEMU documents Arm development boards that include `mps2-an386` (Cortex-M4) and `mps2-an505` (Cortex-M33) [retrieved: https://www.qemu.org/docs/master/system/arm/mps2.html].
- Renode lists supported boards that include the STM32F4 Discovery (Cortex-M4F) [retrieved: https://renode.readthedocs.io/en/latest/introduction/supported-boards.html].
- What this tier can answer: does the pinned ML-KEM and ML-DSA code build for the target core and give the known answer test result (correctness); what is the linked flash size; what is the peak stack with stack painting.
- What this tier cannot answer: **real cycle counts, wait states, cache effects or energy**. [inference] An emulator executes instructions but does not model the flash accelerator, bus contention or the power rail of a real chip, so its timing must not be quoted as a microcontroller measurement. Label any emulator output "emulated, not hardware".

## Tier 2. Borrowed lab hardware: real cycle counts (free)

Ask for a few hours on a bench that already has a Cortex-M4F or M33 board and a USB cable. Candidates in your own network: a university robotics or embedded systems lab, a hackathon teammate who owns a Nucleo or Discovery board, or a research institute lab if you are invited. Bring the prepared firmware (`bench/mcu/`), so the session is only flash, run and copy the output. Record the board, core, clock, flash wait states and toolchain in the `META` line, as the harness does.

A draft message for a lab is in `docs/supplier/README.md` (section "Lab loan request").

## Tier 3. Existing boards you already own

Check first whether you or a teammate already own an STM32 board, a Raspberry Pi Pico (Cortex-M0+, no cycle counter; the RP2040 paper in the evidence table used a timer) or an ESP32. The Cortex-M4F cycle counter (DWT CYCCNT) is the preferred method; M0+ boards need a timer instead and are reported in a separate panel.

## What the first hardware experiment becomes

E1, ML-DSA-44 verify and ML-KEM-768 decapsulation with pinned mlkem-native and mldsa-native v2.0.0, three power cycles. Step 1 runs in an emulator for correctness and sizes today, at no cost. Step 2 repeats on borrowed hardware for cycles. Both are reported in separate columns; emulated numbers never enter the cycle table.
