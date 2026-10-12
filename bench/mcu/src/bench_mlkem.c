/* bench_mlkem.c - ML-KEM keygen / encaps / decaps timing with mlkem-native v2.0.0.
 *
 * Build once per parameter set: -DMLK_CONFIG_PARAMETER_SET=512|768|1024 (see Makefile).
 * Uses the deterministic API (keypair_derand / enc_derand) so no RNG cost is inside the timed
 * region; report your board's TRNG cost separately.
 *
 * STATUS: host-compiled and run with -DBENCH_HOST. NOT tested on hardware.
 */
#include <mlkem_native.h>
#include "bench_common.h"
#include "stack_paint.h"

#define STR_(x) #x
#define STR(x) STR_(x)
#define PARAM "ML-KEM-" STR(MLK_CONFIG_PARAMETER_SET)
#define PK_BYTES MLKEM_PUBLICKEYBYTES(MLK_CONFIG_PARAMETER_SET)
#define SK_BYTES MLKEM_SECRETKEYBYTES(MLK_CONFIG_PARAMETER_SET)
#define CT_BYTES MLKEM_CIPHERTEXTBYTES(MLK_CONFIG_PARAMETER_SET)

static uint8_t pk[PK_BYTES], sk[SK_BYTES], ct[CT_BYTES];
static uint8_t ss_a[MLKEM_BYTES], ss_b[MLKEM_BYTES];

int main(void)
{
  uint32_t st = 0x12345678u;
  uint8_t coins[2 * MLKEM_SYMBYTES];
  uint8_t m[MLKEM_SYMBYTES];
  unsigned ok = 0, fail = 0;
  long stack_kg = -1, stack_enc = -1, stack_dec = -1;
  int rc = 0;

  cyc_init();
  bench_meta_common();
  bench_meta("alg", "ML-KEM");
  bench_meta("param", PARAM);
  bench_meta("lib", "mlkem-native v2.0.0 (commit d1b2fe782888bdb761a50336012923180be7f502)");

  /* keygen */
  for (unsigned i = 0; i < BENCH_ITERS; i++)
  {
    uint32_t t;
    bench_fill(coins, sizeof coins, &st);
    BENCH_TIME(t, rc = mlkem_keypair_derand(pk, sk, coins));
    if (rc != 0) fail++; else ok++;
    bench_row("ML-KEM", PARAM, "keygen", i, t);
  }
  bench_fill(coins, sizeof coins, &st);
  STACK_MEASURE(stack_kg, rc = mlkem_keypair_derand(pk, sk, coins));

  /* encaps (each iteration: fresh message m, fixed public key) */
  for (unsigned i = 0; i < BENCH_ITERS; i++)
  {
    uint32_t t;
    bench_fill(m, sizeof m, &st);
    BENCH_TIME(t, rc = mlkem_enc_derand(ct, ss_a, pk, m));
    if (rc != 0) fail++; else ok++;
    bench_row("ML-KEM", PARAM, "encaps", i, t);

    /* untimed correctness check: decaps must give the same shared secret */
    rc = mlkem_dec(ss_b, ct, sk);
    if (rc == 0 && memcmp(ss_a, ss_b, MLKEM_BYTES) == 0) ok++; else fail++;
  }
  bench_fill(m, sizeof m, &st);
  STACK_MEASURE(stack_enc, rc = mlkem_enc_derand(ct, ss_a, pk, m));

  /* decaps (timed on the last ciphertext) */
  for (unsigned i = 0; i < BENCH_ITERS; i++)
  {
    uint32_t t;
    BENCH_TIME(t, rc = mlkem_dec(ss_b, ct, sk));
    if (rc == 0 && memcmp(ss_a, ss_b, MLKEM_BYTES) == 0) ok++; else fail++;
    bench_row("ML-KEM", PARAM, "decaps", i, t);
  }
  STACK_MEASURE(stack_dec, rc = mlkem_dec(ss_b, ct, sk));

  printf("STACK,ML-KEM,%s,keygen,%ld\n", PARAM, stack_kg);
  printf("STACK,ML-KEM,%s,encaps,%ld\n", PARAM, stack_enc);
  printf("STACK,ML-KEM,%s,decaps,%ld\n", PARAM, stack_dec);
  printf("CHECK,ML-KEM,%s,roundtrip,%u,%u\n", PARAM, ok, fail);
  return fail ? 1 : 0;
}
