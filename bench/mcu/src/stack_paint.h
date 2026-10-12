/* stack_paint.h - stack high-water-mark measurement by painting (target only).
 *
 * STACK_MEASURE(out, stmt): fills the free stack region below the current stack pointer with a
 * pattern, runs `stmt`, then finds how deep the pattern was overwritten. `out` receives the
 * bytes of stack used BY `stmt` (excluding the harness frame), or:
 *    -1 : not measured (host build)
 *    -2 : stack span too small (pattern fully overwritten); increase BENCH_STACK_SPAN
 *
 * DANGER: painting writes BENCH_STACK_SPAN bytes below SP. It must fit inside the free stack
 * area of YOUR linker script, or it will corrupt heap/.bss. Default span is deliberately small
 * (16 KiB); ML-DSA signing may need far more (published pqm4 numbers reach >100 KiB for the
 * reference code), so set -DBENCH_STACK_SPAN=<bytes> from your linker map and check it.
 *
 * Interrupt handlers that run during `stmt` also use this stack and inflate the result;
 * define BENCH_DISABLE_IRQ to avoid that (see cyc.h).
 *
 * STATUS: UNTESTED ON HARDWARE.
 */
#ifndef BENCH_STACK_PAINT_H
#define BENCH_STACK_PAINT_H
#include <stdint.h>

#ifdef BENCH_HOST
#define STACK_MEASURE(out, stmt) \
  do                             \
  {                              \
    stmt;                        \
    (out) = -1;                  \
  } while (0)
#else
#ifndef BENCH_STACK_SPAN
#define BENCH_STACK_SPAN 16384u
#endif
#define BENCH_STACK_PATTERN 0xA5A5A5A5u
#define BENCH_STACK_MARGIN 128u /* keep clear of the live frame */
#define STACK_MEASURE(out, stmt)                                                       \
  do                                                                                   \
  {                                                                                    \
    uintptr_t sp_;                                                                     \
    __asm volatile("mov %0, sp" : "=r"(sp_));                                          \
    volatile uint32_t *hi_ = (volatile uint32_t *)((sp_ - BENCH_STACK_MARGIN) & ~3u);   \
    volatile uint32_t *lo_ = (volatile uint32_t *)((sp_ - BENCH_STACK_SPAN) & ~3u);     \
    for (volatile uint32_t *p_ = lo_; p_ < hi_; p_++)                                  \
      *p_ = BENCH_STACK_PATTERN;                                                       \
    stmt;                                                                              \
    volatile uint32_t *q_ = lo_;                                                       \
    while (q_ < hi_ && *q_ == BENCH_STACK_PATTERN)                                     \
      q_++;                                                                            \
    if (q_ == lo_)                                                                     \
      (out) = -2;                                                                      \
    else                                                                               \
      (out) = (long)((uintptr_t)hi_ - (uintptr_t)q_) + (long)BENCH_STACK_MARGIN;        \
  } while (0)
#endif
#endif /* BENCH_STACK_PAINT_H */
