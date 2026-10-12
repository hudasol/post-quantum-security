/* bench_mldsa.c - ML-DSA keygen / sign / verify timing with mldsa-native v2.0.0.
 *
 * Build once per parameter set: -DMLD_CONFIG_PARAMETER_SET=44|65|87 (see Makefile).
 * Signing time is data-dependent (rejection sampling), so every iteration signs a DIFFERENT
 * message and every individual time is printed; analysis must use quantiles, not only a mean
 * (see docs/BENCHMARK_PLAN.md). Verification is timed on the signature just produced.
 *
 * Randomness: mldsa-native calls randombytes(); bench_rng.c supplies a deterministic,
 * INSECURE generator for reproducible timing only.
 *
 * STATUS: host-compiled and run with -DBENCH_HOST. NOT tested on hardware.
 */
#include <mldsa_native.h>
#include "bench_common.h"
#include "stack_paint.h"

#define STR_(x) #x
#define STR(x) STR_(x)
#define PARAM "ML-DSA-" STR(MLD_CONFIG_PARAMETER_SET)
#define PK_BYTES MLDSA_PUBLICKEYBYTES(MLD_CONFIG_PARAMETER_SET)
#define SK_BYTES MLDSA_SECRETKEYBYTES(MLD_CONFIG_PARAMETER_SET)
#define SIG_BYTES MLDSA_BYTES(MLD_CONFIG_PARAMETER_SET)

static uint8_t pk[PK_BYTES], sk[SK_BYTES], sig[SIG_BYTES];
static uint8_t msg[BENCH_MSG_LEN];
static const uint8_t ctx[1] = {0}; /* empty context string, length 0 */

int main(void)
{
  uint32_t st = 0x2468ace1u;
  unsigned ok = 0, fail = 0;
  long stack_kg = -1, stack_sign = -1, stack_ver = -1;
  int rc = 0;

  cyc_init();
  bench_meta_common();
  bench_meta("alg", "ML-DSA");
  bench_meta("param", PARAM);
  bench_meta("lib", "mldsa-native v2.0.0 (commit 834a90d5e846ffa1e1611bd24e160bb2e9b86d35)");

  for (unsigned i = 0; i < BENCH_ITERS; i++)
  {
    uint32_t t;
    BENCH_TIME(t, rc = mldsa_keypair(pk, sk));
    if (rc != 0) fail++; else ok++;
    bench_row("ML-DSA", PARAM, "keygen", i, t);
  }
  STACK_MEASURE(stack_kg, rc = mldsa_keypair(pk, sk));

  for (unsigned i = 0; i < BENCH_ITERS; i++)
  {
    uint32_t ts, tv;
    bench_fill(msg, sizeof msg, &st);
    BENCH_TIME(ts, rc = mldsa_signature(sig, msg, sizeof msg, ctx, 0, sk));
    if (rc != 0) fail++; else ok++;
    bench_row("ML-DSA", PARAM, "sign", i, ts);

    BENCH_TIME(tv, rc = mldsa_verify(sig, msg, sizeof msg, ctx, 0, pk));
    if (rc == 0) ok++; else fail++;
    bench_row("ML-DSA", PARAM, "verify", i, tv);
  }
  STACK_MEASURE(stack_sign, rc = mldsa_signature(sig, msg, sizeof msg, ctx, 0, sk));
  STACK_MEASURE(stack_ver, rc = mldsa_verify(sig, msg, sizeof msg, ctx, 0, pk));

  /* negative check (untimed): a corrupted signature must be rejected */
  sig[0] ^= 1u;
  if (mldsa_verify(sig, msg, sizeof msg, ctx, 0, pk) != 0) ok++; else fail++;

  printf("STACK,ML-DSA,%s,keygen,%ld\n", PARAM, stack_kg);
  printf("STACK,ML-DSA,%s,sign,%ld\n", PARAM, stack_sign);
  printf("STACK,ML-DSA,%s,verify,%ld\n", PARAM, stack_ver);
  printf("CHECK,ML-DSA,%s,sign_verify_and_reject,%u,%u\n", PARAM, ok, fail);
  return fail ? 1 : 0;
}
