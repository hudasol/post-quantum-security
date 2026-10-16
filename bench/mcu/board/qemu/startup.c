/* Minimal start up and C library glue for QEMU mps2-an386 (Cortex-M4) and mps2-an505 (Cortex-M33).
 * Board support only: no cryptography here.
 * Console is a CMSDK APB UART (DATA at +0x00, CTRL at +0x08, bit 0 = TX enable). UART0 sits at 0x40004000
 * on mps2-an386; on mps2-an505 the build passes -DBENCH_UART_BASE=0x50200000u (UART0, secure alias,
 * because the core starts in the secure state). */
#include <stdint.h>
#include <stddef.h>
#include <errno.h>

extern uint32_t _sidata, _sdata, _edata, _sbss, _ebss, _estack, _heap_start, _heap_end;
extern int main(void);

#ifndef BENCH_UART_BASE
#define BENCH_UART_BASE 0x40004000u
#endif
#define UART_DATA (*(volatile uint32_t *)(BENCH_UART_BASE + 0x0u))
#define UART_CTRL (*(volatile uint32_t *)(BENCH_UART_BASE + 0x8u))
#define CPACR (*(volatile uint32_t *)0xE000ED88u)

void Reset_Handler(void)
{
  CPACR |= (0xFu << 20); /* enable the FPU before any hard float code runs */
  __asm volatile("dsb; isb");
  for (uint32_t *s = &_sidata, *d = &_sdata; d < &_edata;) *d++ = *s++;
  for (uint32_t *d = &_sbss; d < &_ebss;) *d++ = 0;
  UART_CTRL = 1u;
  int rc = main();
  /* stop QEMU through ARM semihosting SYS_EXIT (needs -semihosting) */
  register uint32_t op __asm("r0") = 0x18u;
  register uint32_t arg __asm("r1") = (rc == 0) ? 0x20026u : 0x20023u;
  __asm volatile("bkpt 0xAB" :: "r"(op), "r"(arg) : "memory");
  for (;;) {}
}
void Default_Handler(void) { for (;;) {} }

__attribute__((section(".vectors"), used)) void (*const vectors[])(void) = {
  (void (*)(void))(&_estack), Reset_Handler,
  Default_Handler, Default_Handler, Default_Handler, Default_Handler, Default_Handler,
};

int _write(int fd, const char *buf, int len)
{
  (void)fd;
  for (int i = 0; i < len; i++) UART_DATA = (uint32_t)(unsigned char)buf[i];
  return len;
}
void *_sbrk(ptrdiff_t inc)
{
  static char *brk;
  if (!brk) brk = (char *)&_heap_start;
  if (brk + inc > (char *)&_heap_end) { errno = ENOMEM; return (void *)-1; }
  char *p = brk; brk += inc; return p;
}
