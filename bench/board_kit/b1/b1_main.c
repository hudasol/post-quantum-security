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
 * Round 5 adds the cache pass option and a second board:
 *   BENCH_CACHE_OFF   after hal_setup, switch the instruction cache, data cache and prefetch off,
 *                     only if the flash latency read back is zero wait states, then read the bits
 *                     back (META cache_pass, cache_off_applied, cache). Without it the image is
 *                     the caches on pass and keeps the state pqm4's set up leaves.
 *   BENCH_BOARD_L552  NUCLEO-L552ZE-Q (Cortex-M33) with b1/m33/hal_l552.c and the vendor CMSIS
 *                     header. Its instruction cache is the ICACHE peripheral; the caches on pass
 *                     enables it, the caches off pass disables it.
 * Register sources (retrieved at pinned commits; docs/BOARD_RUN_PROTOCOL.md section 4):
 *   STM32L4R5: FLASH_ACR at FLASH_R_BASE = 0x40022000, LATENCY bits 3:0, PRFTEN bit 8, ICEN bit 9,
 *     DCEN bit 10 in STMicroelectronics/cmsis_device_l4 v1.7.5 (dc04e41a) Include/stm32l4r5xx.h;
 *     the same PRFTEN, ICEN and DCEN positions in libopencm3 1f3abd43 (pqm4 submodule)
 *     include/libopencm3/stm32/l4/flash.h and common/flash_common_idcache.h, which this file uses.
 *   STM32L552: ICACHE_CR EN bit 0 and ICACHE_SR BUSYF bit 0 at ICACHE_BASE_NS, FLASH_ACR LATENCY
 *     bits 3:0 (no prefetch or cache enable bits are defined for FLASH_ACR) in
 *     STMicroelectronics/cmsis_device_l5 v1.0.7 (e237398c) Include/stm32l552xx.h.
 * STATUS: built for nucleo-l4r5zi and nucleo-l552ze-q and run in QEMU (mps2-an386) only; not yet
 * run on a real board.
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
#elif defined(BENCH_BOARD_L552)
#include "stm32l5xx.h"
#endif

#if defined(BENCH_CACHE_OFF)
#define BENCH_CACHE_PASS "off"
/* Compile time flag symbol: the kit tests look for it with arm-none-eabi-nm. */
__attribute__((used)) const char bench_cache_off_compiled[] = "BENCH_CACHE_OFF";
#else
#define BENCH_CACHE_PASS "on"
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

/* Cache pass. Returns 1 if the caches off writes were made, 0 if not (caches on pass, emulator,
 * or flash latency not zero), and prints the reason. Kept out of line so that a test can find the
 * register writes in the disassembly of the caches off image. */
__attribute__((noinline, used)) int bench_cache_configure(void)
{
#if defined(BENCH_BOARD_OPENCM3)
#if defined(BENCH_CACHE_OFF)
  uint32_t ws = (FLASH_ACR >> FLASH_ACR_LATENCY_SHIFT) & FLASH_ACR_LATENCY_MASK;
  if (ws != 0u) {
    bench_printf("META,cache_off_refused,flash_ws=%lu\n", (unsigned long)ws);
    return 0;
  }
  FLASH_ACR &= ~(uint32_t)(FLASH_ACR_ICEN | FLASH_ACR_DCEN | FLASH_ACR_PRFTEN);
  __asm volatile("dsb\n\tisb" ::: "memory");
  return 1;
#else
  return 0; /* caches on pass: keep the bits pqm4's hal_setup(CLOCK_BENCHMARK) set */
#endif
#elif defined(BENCH_BOARD_L552)
  uint32_t ws = (FLASH->ACR & FLASH_ACR_LATENCY_Msk) >> FLASH_ACR_LATENCY_Pos;
#if defined(BENCH_CACHE_OFF)
  if (ws != 0u) {
    bench_printf("META,cache_off_refused,flash_ws=%lu\n", (unsigned long)ws);
    return 0;
  }
  ICACHE->CR &= ~ICACHE_CR_EN;
  for (uint32_t t = 0; (ICACHE->SR & ICACHE_SR_BUSYF) && t < 1000000u; t++) { }
  __asm volatile("dsb\n\tisb" ::: "memory");
  return 1;
#else
  (void)ws;
  for (uint32_t t = 0; (ICACHE->SR & ICACHE_SR_BUSYF) && t < 1000000u; t++) { }
  ICACHE->CR |= ICACHE_CR_EN;
  __asm volatile("dsb\n\tisb" ::: "memory");
  return 0;
#endif
#else
  return 0; /* emulator: no flash interface or cache to configure */
#endif
}

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
#elif defined(BENCH_BOARD_L552)
  SystemCoreClockUpdate();
  uint32_t acr = FLASH->ACR;
  uint32_t cfgr = RCC->CFGR;
  bench_printf("META,platform,nucleo-l552ze-q (kit hal_l552.c, CMSIS cmsis_device_l5)\n");
  meta_u("clock_hz_hal", (unsigned long)SystemCoreClock); /* CMSIS value from RCC registers */
  bench_printf("META,rcc_cfgr,0x%08lx\n", (unsigned long)cfgr);
  bench_printf("META,rcc_cr,0x%08lx\n", (unsigned long)RCC->CR);
  meta_u("clock_hz_rcc", (unsigned long)SystemCoreClock);
  bench_printf("META,flash_acr,0x%08lx\n", (unsigned long)acr);
  meta_u("flash_ws", (unsigned long)((acr & FLASH_ACR_LATENCY_Msk) >> FLASH_ACR_LATENCY_Pos));
  bench_printf("META,icache_cr,0x%08lx\n", (unsigned long)ICACHE->CR);
  bench_printf("META,cache,icache=%d dcache=none prefetch=none\n",
               (ICACHE->CR & ICACHE_CR_EN) ? 1 : 0);
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
  int applied = bench_cache_configure();
  hal_send_str("==========================");
  bench_printf("META,cache_pass,%s\n", BENCH_CACHE_PASS);
#if defined(BENCH_CACHE_OFF)
  bench_printf("META,cache_option,%s\n", bench_cache_off_compiled); /* keeps the flag symbol */
#endif
  meta_u("cache_off_applied", (unsigned long)applied);
  print_board_state();
  counter_check();
  int rc = bench_harness_main();
  bench_printf("META,harness_rc,%d\n", rc);
  hal_send_str("#");
  return rc;
}
