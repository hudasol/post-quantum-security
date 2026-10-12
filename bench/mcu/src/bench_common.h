/* bench_common.h - shared helpers: deterministic inputs, CSV output, timed-region macro.
 *
 * Output format (one CSV line per measurement, over printf / UART):
 *   META,<key>,<value>
 *   BENCH,<alg>,<param>,<op>,<run_id>,<iter>,<value>,<unit>
 *   STACK,<alg>,<param>,<op>,<bytes_or_na>
 *   CHECK,<alg>,<param>,<what>,<ok_count>,<fail_count>
 * Analysis (medians, quantiles, bootstrap CI) is done off-device by bench/stats/analyze_runs.py.
 *
 * STATUS: compile-tested and run on a PC with -DBENCH_HOST (host measurement, ns).
 *         NOT tested on any microcontroller.
 */
#ifndef BENCH_COMMON_H
#define BENCH_COMMON_H

#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "cyc.h"

#ifndef BENCH_ITERS
#define BENCH_ITERS 100u
#endif
#ifndef BENCH_RUN_ID
#define BENCH_RUN_ID 0 /* set -DBENCH_RUN_ID=<n> per power cycle, or let the PC script do it */
#endif
#ifndef BENCH_MSG_LEN
#define BENCH_MSG_LEN 59u /* same message length pqm4 uses for signatures, for easier comparison */
#endif
#ifndef BENCH_CLOCK_HZ
#define BENCH_CLOCK_HZ 0 /* set to the real core clock in Hz; 0 = unknown (host) */
#endif

/* Deterministic input generator (xorshift32). NOT a cryptographic RNG. Benchmark inputs only. */
static inline uint32_t bench_xs32(uint32_t *s)
{
  uint32_t x = *s;
  x ^= x << 13;
  x ^= x >> 17;
  x ^= x << 5;
  return *s = x ? x : 0x1badb002u;
}
static inline void bench_fill(uint8_t *buf, size_t n, uint32_t *state)
{
  for (size_t i = 0; i < n; i++)
    buf[i] = (uint8_t)bench_xs32(state);
}

/* Timed region: `stmt` runs between two counter reads. Result stored in `out` (uint32_t). */
#define BENCH_TIME(out, stmt)                       \
  do                                                \
  {                                                 \
    uint32_t t0_, t1_;                              \
    irq_off();                                      \
    t0_ = cyc_now();                                \
    stmt;                                           \
    t1_ = cyc_now();                                \
    irq_on();                                       \
    (out) = (uint32_t)(t1_ - t0_);                  \
  } while (0)

static inline void bench_meta(const char *k, const char *v) { printf("META,%s,%s\n", k, v); }
static inline void bench_meta_u(const char *k, unsigned long v) { printf("META,%s,%lu\n", k, v); }
static inline void bench_row(const char *alg, const char *param, const char *op, unsigned iter, uint32_t v)
{
  printf("BENCH,%s,%s,%s,%d,%u,%lu,%s\n", alg, param, op, (int)BENCH_RUN_ID, iter, (unsigned long)v, CYC_UNIT);
}

static inline void bench_meta_common(void)
{
  bench_meta("harness_version", "0.1-untested-on-hardware");
#ifdef BENCH_HOST
  bench_meta("target", "HOST (not a microcontroller result)");
#else
  bench_meta("target", "MCU");
#endif
  bench_meta_u("clock_hz", (unsigned long)BENCH_CLOCK_HZ);
  bench_meta_u("iters", (unsigned long)BENCH_ITERS);
  bench_meta_u("msg_len", (unsigned long)BENCH_MSG_LEN);
  bench_meta("unit", CYC_UNIT);
#ifdef __VERSION__
  bench_meta("compiler", __VERSION__);
#endif
#ifdef BENCH_OPT_NOTE
  bench_meta("opt_note", BENCH_OPT_NOTE);
#endif
#ifdef BENCH_LIB_NOTE
  bench_meta("lib_note", BENCH_LIB_NOTE);
#endif
}

#endif /* BENCH_COMMON_H */
