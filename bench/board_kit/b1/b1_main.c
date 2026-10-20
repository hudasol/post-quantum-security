/* b1_main.c - glue between the repository harness (bench/mcu/src) and the pqm4 platform layer.
 *
 * Author: Huda Mueen. Board support only; no cryptography is implemented here.
 *
 * Start up, clock set up and UART all come from pqm4 (common/hal-opencm3.c with libopencm3 on
 * nucleo-l4r5zi; common/hal-mps2.c with startup_MPS2.S on mps2-an386) at the pinned commit. This
 * file only:
 *   1. calls hal_setup(CLOCK_BENCHMARK), the same clock mode pqm4 uses for its speed binaries;
 *   2. reads back and prints the clock, flash wait states and cache and prefetch bits (META lines);
 *   3. runs a counter check: one loop timed by the DWT cycle counter and by pqm4's SysTick timer;
 *   4. routes the harness printf output to hal_send_str, one line at a time;
 *   5. runs the unchanged harness main (renamed bench_harness_main at compile time).
 * STATUS: built for nucleo-l4r5zi and run in QEMU (mps2-an386) only; not yet run on a real board.
 */
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "hal.h"
#include "cyc.h"

#if defined(BENCH_BOARD_OPENCM3)
#include <libopencm3/stm32/rcc.h>
#include <libopencm3/stm32/flash.h>
#endif

#ifndef BENCH_COUNTER_LOOP
#define BENCH_COUNTER_LOOP 1000000u
#endif

int bench_harness_main(void);

/* printf replacement for the harness: pqm4 wraps _write to a stub, so text goes out through
 * hal_send_str, which appends its own newline. Lines longer than the buffer are split. */
int bench_printf(const char *fmt, ...)
{
  static char line[200];
  static size_t used;
  char buf[200];
  va_list ap;
  va_start(ap, fmt);
  int len = vsnprintf(buf, sizeof buf, fmt, ap);
  va_end(ap);
  for (const char *c = buf; *c; c++) {
    if (*c == '\n' || used == sizeof line - 1) {
      line[used] = '\0';
      hal_send_str(line);
      used = 0;
      if (*c == '\n') continue;
    }
    line[used++] = *c;
  }
  return len;
}

static void meta_u(const char *k, unsigned long v) { bench_printf("META,%s,%lu\n", k, v); }

static void print_board_state(void)
{
#if defined(BENCH_BOARD_OPENCM3)
  uint32_t acr = FLASH_ACR;
  uint32_t cfgr = RCC_CFGR;
  uint32_t pll = RCC_PLLCFGR;
  unsigned long src = (pll >> RCC_PLLCFGR_PLLSRC_SHIFT) & RCC_PLLCFGR_PLLSRC_MASK;
  unsigned long m = ((pll >> RCC_PLLCFGR_PLLM_SHIFT) & RCC_PLLCFGR_PLLM_MASK) + 1u;
  unsigned long n = (pll >> RCC_PLLCFGR_PLLN_SHIFT) & RCC_PLLCFGR_PLLN_MASK;
  unsigned long r = (((pll >> RCC_PLLCFGR_PLLR_SHIFT) & RCC_PLLCFGR_PLLR_MASK) + 1u) * 2u;
  unsigned long sws = (cfgr >> RCC_CFGR_SWS_SHIFT) & RCC_CFGR_SWS_MASK;
  unsigned long hpre = (cfgr >> RCC_CFGR_HPRE_SHIFT) & RCC_CFGR_HPRE_MASK;
  bench_printf("META,platform,nucleo-l4r5zi (pqm4 hal-opencm3, libopencm3)\n");
  meta_u("clock_hz_hal", (unsigned long)rcc_ahb_frequency); /* value pqm4 set, not a measurement */
  bench_printf("META,rcc_cfgr,0x%08lx\n", (unsigned long)cfgr);
  bench_printf("META,rcc_pllcfgr,0x%08lx\n", (unsigned long)pll);
  /* Clock from the RCC fields, valid when SWS selects the PLL fed by HSI16 and HPRE does not divide. */
  if (sws == RCC_CFGR_SWS_PLL && src == RCC_PLLCFGR_PLLSRC_HSI16 && hpre < 8u)
    meta_u("clock_hz_rcc", 16000000ul / m * n / r);
  else
    bench_printf("META,clock_hz_rcc,unknown (sws=%lu src=%lu hpre=%lu)\n", sws, src, hpre);
  bench_printf("META,flash_acr,0x%08lx\n", (unsigned long)acr);
  meta_u("flash_ws", (unsigned long)((acr >> FLASH_ACR_LATENCY_SHIFT) & FLASH_ACR_LATENCY_MASK));
  bench_printf("META,cache,icache=%d dcache=%d prefetch=%d\n", (acr & FLASH_ACR_ICEN) ? 1 : 0,
               (acr & FLASH_ACR_DCEN) ? 1 : 0, (acr & FLASH_ACR_PRFTEN) ? 1 : 0);
#else
  bench_printf("META,platform,mps2-an386 (pqm4 hal-mps2, QEMU; emulated)\n");
  bench_printf("META,clock_hz_rcc,emulated\n");
  bench_printf("META,flash_ws,emulated\n");
  bench_printf("META,cache,emulated\n");
#endif
}

/* Counter check: the same loop timed by DWT CYCCNT and by pqm4's SysTick based hal_get_time.
 * On a real core both count core clock cycles, so the two values should agree closely. */
static void counter_check(void)
{
  volatile uint32_t k = 0;
  cyc_init();
  uint64_t s0 = hal_get_time();
  uint32_t d0 = cyc_now();
  for (uint32_t i = 0; i < BENCH_COUNTER_LOOP; i++) k += i;
  uint32_t d1 = cyc_now();
  uint64_t s1 = hal_get_time();
  meta_u("counter_loop_iters", (unsigned long)BENCH_COUNTER_LOOP);
  meta_u("counter_dwt_cycles", (unsigned long)(d1 - d0));
  meta_u("counter_systick_cycles", (unsigned long)(s1 - s0));
}

int main(void)
{
  hal_setup(CLOCK_BENCHMARK);
  hal_send_str("==========================");
  print_board_state();
  counter_check();
  int rc = bench_harness_main();
  bench_printf("META,harness_rc,%d\n", rc);
  hal_send_str("#");
  return rc;
}
