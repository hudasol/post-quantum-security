/* hal_l552.c - minimal platform layer for the B1 harness on NUCLEO-L552ZE-Q (Cortex-M33).
 *
 * Author: Huda Mueen. Board support only; no cryptography is implemented here.
 *
 * pqm4 has no Cortex-M33 platform at the pinned commit (its mk/ directory lists cw308t-stm32f3,
 * cw308t-stm32f415, mps2-an386, nucleo-l476rg, nucleo-l4r5zi and stm32f4discovery; the same list
 * holds at pqm4 master e1146b1b), and the libopencm3 submodule at the pin has no STM32L5 family.
 * This file therefore implements the three pqm4 HAL calls that b1_main.c uses (hal_setup,
 * hal_send_str, hal_get_time, declared in pqm4 mupq/common/hal.h) with the vendor CMSIS device
 * header. Start up code, system file and linker script are the vendor files, used unchanged.
 *
 * Sources for every register and pin used here (all retrieved at pinned commits; see
 * bench/board_kit/kit_config.py and bench/board_kit/fetch_m33.sh):
 *   - register names and bit fields: STMicroelectronics/cmsis_device_l5 v1.0.7
 *     (e237398c0cbae890f4659f74fe6b64cae339b6a0), Include/stm32l552xx.h;
 *   - reset clock MSI 4 MHz: same repository, Source/Templates/system_stm32l5xx.c, header comment;
 *   - LPUART1 on PG7 (TX) and PG8 (RX) to the ST-LINK virtual COM port: board user manual UM2581
 *     (retrieved from www.st.com in this round);
 *   - alternate function AF8 for LPUART1 on PG7 and PG8: zephyrproject-rtos/hal_stm32
 *     c9550199186236d610092f4005f8c9bae2a6bfcf, dts/st/l5/stm32l552z(c-e)txq-pinctrl.dtsi;
 *   - LPUART baud divider 256 * f / baud, rounded: libopencm3 1f3abd43 (pqm4 submodule),
 *     lib/stm32/common/usart_common_all.c, usart_set_baudrate;
 *   - SysTick overflow counting: copied in method from pqm4 common/hal-opencm3.c (hal_get_time).
 * STATUS: built only. Not run on a board and not run in an emulator (no free model of this part
 * was run in this round).
 *
 * Clock: the core runs from the reset clock (MSI, 4 MHz per system_stm32l5xx.c) in both clock
 * modes, so the flash latency stays at its reset value; b1_main.c reads both back and prints them.
 */
#include <stdint.h>
#include <stddef.h>

#include "stm32l5xx.h"
#include "hal.h"

#define SERIAL_BAUD 38400u /* same rate as pqm4 SERIAL_BAUD */

static volatile unsigned long long overflowcnt = 0;

void SysTick_Handler(void) { ++overflowcnt; }

static void lpuart1_setup(uint32_t fck)
{
  RCC->APB1ENR1 |= RCC_APB1ENR1_PWREN;
  (void)RCC->APB1ENR1;
  PWR->CR2 |= PWR_CR2_IOSV; /* port G is supplied by VDDIO2 */
  RCC->AHB2ENR |= RCC_AHB2ENR_GPIOGEN;
  RCC->APB1ENR2 |= RCC_APB1ENR2_LPUART1EN;
  (void)RCC->APB1ENR2;
  /* PG7 and PG8: alternate function mode (MODER = 2), AF8 */
  GPIOG->MODER = (GPIOG->MODER & ~((3u << (7 * 2)) | (3u << (8 * 2)))) |
                 (2u << (7 * 2)) | (2u << (8 * 2));
  GPIOG->AFR[0] = (GPIOG->AFR[0] & ~(0xFu << (7 * 4))) | (8u << (7 * 4));
  GPIOG->AFR[1] = (GPIOG->AFR[1] & ~(0xFu << ((8 - 8) * 4))) | (8u << ((8 - 8) * 4));
  /* LPUART1 kernel clock: RCC_CCIPR1 LPUART1SEL left at its reset value (PCLK1 = HCLK here). */
  LPUART1->CR1 = 0;
  LPUART1->BRR = (fck / SERIAL_BAUD) * 256u + ((fck % SERIAL_BAUD) * 256u + SERIAL_BAUD / 2u) / SERIAL_BAUD;
  LPUART1->CR1 = USART_CR1_TE | USART_CR1_RE | USART_CR1_UE;
}

static void systick_setup(void)
{
  SysTick->LOAD = 0xFFFFFFu;
  SysTick->VAL = 0;
  SysTick->CTRL = SysTick_CTRL_CLKSOURCE_Msk | SysTick_CTRL_TICKINT_Msk | SysTick_CTRL_ENABLE_Msk;
}

void hal_setup(const enum clock_mode clock)
{
  (void)clock; /* both modes keep the reset clock; see the file header */
  SystemCoreClockUpdate();
  lpuart1_setup(SystemCoreClock);
  systick_setup();
  unsigned long long old = overflowcnt;
  while (old == overflowcnt) { } /* as pqm4: wait for the first SysTick overflow */
}

static void send_char(char c)
{
  while ((LPUART1->ISR & USART_ISR_TXE_TXFNF) == 0u) { }
  LPUART1->TDR = (uint8_t)c;
}

void hal_send_str(const char *in)
{
  for (const char *cur = in; *cur; cur++) send_char(*cur);
  send_char('\n');
}

uint64_t hal_get_time(void)
{
  while (1) {
    unsigned long long before = overflowcnt;
    unsigned long long result = (before + 1) * 16777216llu - SysTick->VAL;
    if (overflowcnt == before) return result;
  }
}
