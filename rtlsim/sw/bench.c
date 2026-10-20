/*
 * Bare metal cycle count harness for the Ibex simple system (RV32IMC).
 * Author: Huda Mueen. SPDX-License-Identifier: Apache-2.0
 *
 * One ELF is built per parameter set. Exactly one of BENCH_KEM (512, 768,
 * 1024) or BENCH_DSA (44, 65, 87) is defined at compile time.
 *
 * Output lines written through the simple system ASCII port have the form
 *   RES,<parameter set>,<operation>,<run index>,<cycles>,<check>
 * where <check> is "ok" or "fail", and a final line
 *   DONE,<parameter set>,<number of failures>
 *
 * Randomness: bench_rng.c supplies a fixed seed generator for timing only.
 * It is NOT a secure random number generator and must never be used for keys.
 */
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#include "simple_system_common.h"

#ifndef BENCH_RUNS
#define BENCH_RUNS 5
#endif

void bench_rng_seed(uint64_t seed);

static inline uint64_t read_mcycle(void)
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

static void put_u64(uint64_t v)
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

static void report(const char *set, const char *op, int run, uint64_t cyc,
                   int ok)
{
  puts("RES,");
  puts(set);
  putchar(',');
  puts(op);
  putchar(',');
  put_u64((uint64_t)run);
  putchar(',');
  put_u64(cyc);
  putchar(',');
  puts(ok ? "ok" : "fail");
  putchar('\n');
}

/* Cost of two back to back counter reads; subtracted from every interval. */
static uint64_t overhead;

static void measure_overhead(void)
{
  uint64_t best = UINT64_MAX;
  for (int i = 0; i < 8; i++)
  {
    uint64_t a = read_mcycle();
    uint64_t b = read_mcycle();
    if (b - a < best)
    {
      best = b - a;
    }
  }
  overhead = best;
}

#define TIME_CALL(dst, expr)          \
  do                                  \
  {                                   \
    uint64_t t0_ = read_mcycle();     \
    rc = (expr);                      \
    uint64_t t1_ = read_mcycle();     \
    (dst) = (t1_ - t0_) - overhead;   \
  } while (0)

#define CAT_(a, b) a##b
#define CAT(a, b) CAT_(a, b)
#define STR_(a) #a
#define STR(a) STR_(a)

#if defined(BENCH_KEM)
#include "mlkem_native.h"

#define KEM_FN(x) CAT(CAT(CAT(PQCP_MLKEM_NATIVE_MLKEM, BENCH_KEM), _), x)
#define SET_NAME "ML-KEM-" STR(BENCH_KEM)

static uint8_t pk[MLKEM_PUBLICKEYBYTES(BENCH_KEM)];
static uint8_t sk[MLKEM_SECRETKEYBYTES(BENCH_KEM)];
static uint8_t ct[MLKEM_CIPHERTEXTBYTES(BENCH_KEM)];
static uint8_t ss_enc[MLKEM_BYTES];
static uint8_t ss_dec[MLKEM_BYTES];

static int run_bench(void)
{
  int fails = 0;
  int rc;
  uint64_t c;
  for (int r = 0; r < BENCH_RUNS; r++)
  {
    TIME_CALL(c, KEM_FN(keypair)(pk, sk));
    report(SET_NAME, "keygen", r, c, rc == 0);
    fails += (rc != 0);

    TIME_CALL(c, KEM_FN(enc)(ct, ss_enc, pk));
    report(SET_NAME, "encaps", r, c, rc == 0);
    fails += (rc != 0);

    memset(ss_dec, 0xA5, sizeof(ss_dec));
    TIME_CALL(c, KEM_FN(dec)(ss_dec, ct, sk));
    int ok = (rc == 0) && (memcmp(ss_enc, ss_dec, MLKEM_BYTES) == 0);
    report(SET_NAME, "decaps", r, c, ok);
    fails += !ok;
  }
  return fails;
}

#elif defined(BENCH_DSA)
#include "mldsa_native.h"

#define DSA_FN(x) CAT(CAT(CAT(PQCP_MLDSA_NATIVE_MLDSA, BENCH_DSA), _), x)
#define SET_NAME "ML-DSA-" STR(BENCH_DSA)

static uint8_t pk[MLDSA_PUBLICKEYBYTES(BENCH_DSA)];
static uint8_t sk[MLDSA_SECRETKEYBYTES(BENCH_DSA)];
static uint8_t sig[MLDSA_BYTES(BENCH_DSA)];
static uint8_t msg[64];

static int run_bench(void)
{
  int fails = 0;
  int rc;
  uint64_t c;
  static const uint8_t ctx[1] = {0};

  TIME_CALL(c, DSA_FN(keypair)(pk, sk));
  report(SET_NAME, "keygen", 0, c, rc == 0);
  fails += (rc != 0);

  for (int r = 0; r < BENCH_RUNS; r++)
  {
    /* Distinct message per run: byte i of message r is (r * 31 + i). */
    for (size_t i = 0; i < sizeof(msg); i++)
    {
      msg[i] = (uint8_t)(r * 31 + (int)i);
    }
    TIME_CALL(c, DSA_FN(signature)(sig, msg, sizeof(msg), ctx, 0, sk));
    report(SET_NAME, "sign", r, c, rc == 0);
    fails += (rc != 0);

    TIME_CALL(c, DSA_FN(verify)(sig, msg, sizeof(msg), ctx, 0, pk));
    report(SET_NAME, "verify", r, c, rc == 0);
    fails += (rc != 0);

    /* Negative check (not timed, first run only to save simulation time):
     * the signature must be rejected for a modified message. */
    if (r == 0)
    {
      msg[0] ^= 1u;
      rc = DSA_FN(verify)(sig, msg, sizeof(msg), ctx, 0, pk);
      report(SET_NAME, "verify_rejects_modified", r, 0, rc != 0);
      fails += (rc == 0);
    }
  }
  return fails;
}

#else
#error "Define BENCH_KEM or BENCH_DSA"
#endif

int main(void)
{
  pcount_enable(1);
  bench_rng_seed(20261020u);
  measure_overhead();
  puts("CFG,seed,20261020\n");
  puts("CFG,runs,");
  put_u64(BENCH_RUNS);
  putchar('\n');
  puts("CFG,timer_overhead_cycles,");
  put_u64(overhead);
  putchar('\n');
  int fails = run_bench();
  puts("DONE,");
  puts(SET_NAME);
  putchar(',');
  put_u64((uint64_t)fails);
  putchar('\n');
  return 0;
}
