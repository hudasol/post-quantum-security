/* Minimal start up and C library glue for the STM32F4 Discovery as modelled by Renode. Board support only:
 * no cryptography here. Console is USART2 at 0x40004400 (SR at +0x00 with TXE in bit 7, DR at +0x04,
 * CR1 at +0x0C with UE in bit 13 and TE in bit 3). The clock tree is left at reset values; Renode does not
 * model timing, so no clock set up is needed for this emulated run. After main returns the core waits. */
#include <stdint.h>
#include <stddef.h>
#include <errno.h>

extern uint32_t _sidata, _sdata, _edata, _sbss, _ebss, _estack, _heap_start, _heap_end;
extern int main(void);

#define USART2_SR (*(volatile uint32_t *)0x40004400u)
#define USART2_DR (*(volatile uint32_t *)0x40004404u)
#define USART2_CR1 (*(volatile uint32_t *)0x4000440Cu)
#define CPACR (*(volatile uint32_t *)0xE000ED88u)

void Reset_Handler(void)
{
  CPACR |= (0xFu << 20); /* enable the FPU before any hard float code runs */
  __asm volatile("dsb; isb");
  for (uint32_t *s = &_sidata, *d = &_sdata; d < &_edata;) *d++ = *s++;
  for (uint32_t *d = &_sbss; d < &_ebss;) *d++ = 0;
  USART2_CR1 = (1u << 13) | (1u << 3);
  (void)main();
  for (;;) { __asm volatile("wfi"); }
}
void Default_Handler(void) { for (;;) {} }

__attribute__((section(".vectors"), used)) void (*const vectors[])(void) = {
  (void (*)(void))(&_estack), Reset_Handler,
  Default_Handler, Default_Handler, Default_Handler, Default_Handler, Default_Handler,
};

int _write(int fd, const char *buf, int len)
{
  (void)fd;
  for (int i = 0; i < len; i++) {
    while (!(USART2_SR & (1u << 7))) {}
    USART2_DR = (uint32_t)(unsigned char)buf[i];
  }
  return len;
}
void *_sbrk(ptrdiff_t inc)
{
  static char *brk;
  if (!brk) brk = (char *)&_heap_start;
  if (brk + inc > (char *)&_heap_end) { errno = ENOMEM; return (void *)-1; }
  char *p = brk; brk += inc; return p;
}
