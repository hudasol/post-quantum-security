/*
 * Support code for running rtlsim/sw/bench.c on the CV32E40P example testbench.
 * Author: Huda Mueen. SPDX-License-Identifier: Apache-2.0
 *
 * 1. putchar and puts write to the testbench print address (no newline is added by puts,
 *    as in the Ibex simple system).
 * 2. _exit writes the exit value to the testbench exit address (crt0.S of the example testbench
 *    calls exit after main).
 * 3. The cycle counter is also enabled before main (bench.c then calls pcount_enable(1), as on
 *    Ibex): the CV32E40P user manual at the pinned commit
 *    (docs/source/control_status_registers.rst, mcountinhibit at CSR 0x320) gives the reset value
 *    0x0000_000D, which inhibits mcycle (bit 0) out of reset. Bit 0 is cleared here; bench.c then
 *    reads mcycle and mcycleh exactly as on Ibex.
 */
#include "simple_system_common.h"

int putchar(int c)
{
  *(volatile uint32_t *)CV32_STDOUT_REG = (unsigned char)c;
  return c;
}

int puts(const char *str)
{
  while (*str) putchar(*str++);
  return 0;
}

void _exit(int status)
{
  *(volatile uint32_t *)CV32_EXIT_REG = (uint32_t)status;
  for (;;) { }
}

__attribute__((constructor)) static void cv32_enable_mcycle(void)
{
  __asm__ volatile("csrci 0x320, 1");
}
