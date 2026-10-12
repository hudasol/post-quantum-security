/* cyc.h - cycle counter abstraction for the PQC embedded benchmark harness.
 *
 * Target build (Cortex-M4 / M33 / M7): reads the DWT cycle counter CYCCNT (32-bit).
 *   - Cortex-M0+ has NO DWT cycle counter (RP2040): use a timer instead (see README).
 *   - Cortex-M7 needs the DWT lock register unlocked (done below).
 * Host build (-DBENCH_HOST): returns nanoseconds from clock_gettime. This exists ONLY so the
 *   harness logic can be compile-tested and run on a PC. Host numbers are "host measurement",
 *   never microcontroller results.
 *
 * STATUS: DWT path is UNTESTED ON HARDWARE (written from the Arm CMSIS register layout:
 * DEMCR 0xE000EDFC bit24 TRCENA, DWT_CTRL 0xE0001000 bit0 CYCCNTENA, CYCCNT 0xE0001004).
 */
#ifndef BENCH_CYC_H
#define BENCH_CYC_H

#include <stdint.h>

#ifdef BENCH_HOST
#include <time.h>
#define CYC_UNIT "ns_host"
static inline void cyc_init(void) {}
static inline uint32_t cyc_now(void)
{
  struct timespec ts;
  clock_gettime(CLOCK_MONOTONIC, &ts);
  return (uint32_t)((uint64_t)ts.tv_sec * 1000000000ull + (uint64_t)ts.tv_nsec);
}
static inline void irq_off(void) {}
static inline void irq_on(void) {}
#else
#define CYC_UNIT "cycles"
#define BENCH_DEMCR (*(volatile uint32_t *)0xE000EDFCu)
#define BENCH_DWT_CTRL (*(volatile uint32_t *)0xE0001000u)
#define BENCH_DWT_CYCCNT (*(volatile uint32_t *)0xE0001004u)
#define BENCH_DWT_LAR (*(volatile uint32_t *)0xE0001FB0u) /* present on Cortex-M7 */

static inline void cyc_init(void)
{
  BENCH_DEMCR |= (1u << 24);        /* TRCENA */
  BENCH_DWT_LAR = 0xC5ACCE55u;      /* unlock (needed on M7, ignored where absent) */
  BENCH_DWT_CYCCNT = 0;
  BENCH_DWT_CTRL |= 1u;             /* CYCCNTENA */
}
static inline uint32_t cyc_now(void) { return BENCH_DWT_CYCCNT; }
#ifdef BENCH_DISABLE_IRQ
static inline void irq_off(void) { __asm volatile("cpsid i" ::: "memory"); }
static inline void irq_on(void) { __asm volatile("cpsie i" ::: "memory"); }
#else
static inline void irq_off(void) {}
static inline void irq_on(void) {}
#endif
#endif

#endif /* BENCH_CYC_H */
