/*
 * Timing, stack painting and log output for the round 6 protocol benchmark (research benchmark code).
 * Author: Huda Mueen. SPDX-License-Identifier: Apache-2.0
 *
 * Log lines (one per line, written through putchar and puts of the core's support code):
 *   CFG,<key>,<value>
 *   RES,<set>,<operation>,<run>,<cycles>,<ok|fail>      cycles of one timed call, timer overhead removed
 *   STK,<set>,<operation>,<run>,<bytes>,<ok|sat>        peak stack of that call (sat: painted area used up)
 *   CHK,<set>,<check>,<run>,<ok|fail>                   untimed correctness check
 *   MSG,<set>,<flight>,<direction>,<bytes>              bytes of one protocol message as built
 *   DONE,<set>,<number of failed checks>
 */
#ifndef PROTO_UTIL_H
#define PROTO_UTIL_H
#include <stddef.h>
#include <stdint.h>

#include "simple_system_common.h"

#ifndef STACK_PAINT_BYTES
#define STACK_PAINT_BYTES 0x30000u
#endif

extern uint64_t pu_overhead;
extern int pu_fails;

uint64_t pu_mcycle(void);
void pu_measure_overhead(void);
void pu_put_u64(uint64_t v);
void pu_res(const char *set, const char *op, int run, uint64_t cyc, int ok);
void pu_chk(const char *set, const char *check, int run, int ok);
void pu_msg(const char *set, const char *flight, const char *dir, size_t bytes);
void pu_cfg(const char *key, uint64_t v);
void pu_cfg_s(const char *key, const char *v);
void pu_done(const char *set);

/* Stack painting: pu_stack_paint fills STACK_PAINT_BYTES below the current stack pointer (minus a
 * 256 byte gap) with a pattern; pu_stack_peak returns the distance from that stack pointer to the
 * lowest word that no longer holds the pattern. Resolution: the result is at least 256 bytes. */
void pu_stack_paint(void);
uint32_t pu_stack_peak(int *saturated);
void pu_stk(const char *set, const char *op, int run, uint32_t bytes, int saturated);

/* Time one call, paint and read the stack around it, and log RES and STK lines. EXPR returns 0 on
 * success. */
#define PU_STEP(SET, OP, RUN, EXPR)                         \
  do                                                        \
  {                                                         \
    int sat_;                                               \
    pu_stack_paint();                                       \
    uint64_t t0_ = pu_mcycle();                             \
    int rc_ = (EXPR);                                       \
    uint64_t t1_ = pu_mcycle();                             \
    uint32_t pk_ = pu_stack_peak(&sat_);                    \
    pu_res((SET), (OP), (RUN), (t1_ - t0_) - pu_overhead, rc_ == 0); \
    pu_stk((SET), (OP), (RUN), pk_, sat_);                  \
    pu_fails += (rc_ != 0);                                 \
  } while (0)

#endif
