/*
 * Timing, stack painting and log output for the round 6 protocol benchmark (research benchmark code).
 * Author: Huda Mueen. SPDX-License-Identifier: Apache-2.0
 * The cycle counter is read exactly as in rtlsim/sw/bench.c (mcycle and mcycleh, round 5).
 */
#include "proto_util.h"

uint64_t pu_overhead;
int pu_fails;

uint64_t pu_mcycle(void)
{
  uint32_t hi, lo, hi2;
  do
  {
    __asm__ volatile("csrr %0, mcycleh" : "=r"(hi));
    __asm__ volatile("csrr %0, mcycle" : "=r"(lo));
    __asm__ volatile("csrr %0, mcycleh" : "=r"(hi2));
  } while (hi != hi2);
  return ((uint64_t)hi << 32) | lo;
}

void pu_measure_overhead(void)
{
  uint64_t best = UINT64_MAX;
  for (int i = 0; i < 8; i++)
  {
    uint64_t a = pu_mcycle();
    uint64_t b = pu_mcycle();
    if (b - a < best)
    {
      best = b - a;
    }
  }
  pu_overhead = best;
}

void pu_put_u64(uint64_t v)
{
  char buf[24];
  int i = 0;
  if (v == 0)
  {
    putchar('0');
    return;
  }
  while (v > 0)
  {
    buf[i++] = (char)('0' + (v % 10u));
    v /= 10u;
  }
  while (i > 0)
  {
    putchar(buf[--i]);
  }
}

static void head(const char *tag, const char *set, const char *op)
{
  puts(tag);
  putchar(',');
  puts(set);
  putchar(',');
  puts(op);
  putchar(',');
}

void pu_res(const char *set, const char *op, int run, uint64_t cyc, int ok)
{
  head("RES", set, op);
  pu_put_u64((uint64_t)run);
  putchar(',');
  pu_put_u64(cyc);
  putchar(',');
  puts(ok ? "ok" : "fail");
  putchar('\n');
}

void pu_stk(const char *set, const char *op, int run, uint32_t bytes, int saturated)
{
  head("STK", set, op);
  pu_put_u64((uint64_t)run);
  putchar(',');
  pu_put_u64(bytes);
  putchar(',');
  puts(saturated ? "sat" : "ok");
  putchar('\n');
}

void pu_chk(const char *set, const char *check, int run, int ok)
{
  head("CHK", set, check);
  pu_put_u64((uint64_t)run);
  putchar(',');
  puts(ok ? "ok" : "fail");
  putchar('\n');
  pu_fails += !ok;
}

void pu_msg(const char *set, const char *flight, const char *dir, size_t bytes)
{
  head("MSG", set, flight);
  puts(dir);
  putchar(',');
  pu_put_u64((uint64_t)bytes);
  putchar('\n');
}

void pu_cfg(const char *key, uint64_t v)
{
  puts("CFG,");
  puts(key);
  putchar(',');
  pu_put_u64(v);
  putchar('\n');
}

void pu_cfg_s(const char *key, const char *v)
{
  puts("CFG,");
  puts(key);
  putchar(',');
  puts(v);
  putchar('\n');
}

void pu_done(const char *set)
{
  puts("DONE,");
  puts(set);
  putchar(',');
  pu_put_u64((uint64_t)pu_fails);
  putchar('\n');
}

#define PAINT_WORD 0x5AC3A55Au
#define PAINT_GAP 256u

static uintptr_t paint_ref;    /* stack pointer of the caller of the timed step */
static uintptr_t paint_bottom; /* lowest painted address */
static uintptr_t paint_top;    /* one past the highest painted address */

__attribute__((noinline)) void pu_stack_paint(void)
{
  uintptr_t sp;
  __asm__ volatile("mv %0, sp" : "=r"(sp));
  paint_ref = sp;
  paint_top = (sp - PAINT_GAP) & ~(uintptr_t)3u;
  paint_bottom = paint_top - STACK_PAINT_BYTES;
  for (volatile uint32_t *p = (volatile uint32_t *)paint_bottom; (uintptr_t)p < paint_top; p++)
  {
    *p = PAINT_WORD;
  }
}

__attribute__((noinline)) uint32_t pu_stack_peak(int *saturated)
{
  volatile uint32_t *p = (volatile uint32_t *)paint_bottom;
  while ((uintptr_t)p < paint_top && *p == PAINT_WORD)
  {
    p++;
  }
  *saturated = ((uintptr_t)p == paint_bottom);
  if ((uintptr_t)p >= paint_top)
  {
    return PAINT_GAP; /* nothing below the gap was touched: at most the gap */
  }
  return (uint32_t)(paint_ref - (uintptr_t)p);
}
