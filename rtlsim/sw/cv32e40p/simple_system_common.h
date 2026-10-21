/*
 * Output and halt functions for the CV32E40P example testbench, with the names that
 * rtlsim/sw/bench.c uses from the Ibex simple system (putchar, puts).
 * Author: Huda Mueen. SPDX-License-Identifier: Apache-2.0
 *
 * Addresses from example_tb/core/mm_ram.sv at the pinned CV32E40P commit (rtlsim/config.sh):
 * a byte written to 0x1000_0000 is printed by the testbench, a word written to 0x2000_0004 ends
 * the simulation with that exit value.
 */
#ifndef CV32E40P_SIMPLE_SYSTEM_COMMON_H
#define CV32E40P_SIMPLE_SYSTEM_COMMON_H
#include <stdint.h>

#define CV32_STDOUT_REG 0x10000000u
#define CV32_EXIT_REG 0x20000004u

int putchar(int c);
int puts(const char *str);

/* Same semantics as pcount_enable in the Ibex simple system header, which bench.c calls:
 * write 0 to mcountinhibit (CSR 0x320) to enable the counters, all ones to inhibit them. */
static inline void pcount_enable(int enable)
{
  unsigned int inhibit_val = enable ? 0x0 : 0xFFFFFFFF;
  __asm__ volatile("csrw 0x320, %0" : : "r"(inhibit_val));
}

#endif
