/* bench_falcon.c - round 7 functional check of padded Falcon-512 (signature per command) on an emulated Cortex-M4.
 *
 * Author: Huda Mueen. Label: emulated. QEMU gives correctness, stack high water marks and image size only, no
 * cycle counts (see qemu_results/LIMITS.md); this check never replaces or adjusts an RTL simulated number.
 * Library: the padded Falcon-512 folder of liboqs tag 0.16.0 (integer emulated floating point), SHAKE256 of
 * mldsa-native through rtlsim/proto/sw/falcon_shim/fips202.h, as in the RTL image. The message is a 44 B buffer of
 * the length of the COMMAND_LONG frame of the RTL image. Randomness: bench_rng.c, deterministic and INSECURE.
 */
#include "api.h"
#include "bench_common.h"
#include "stack_paint.h"

#define PARAM "Falcon-512 (padded)"
static uint8_t pk[PQCLEAN_FALCONPADDED512_CLEAN_CRYPTO_PUBLICKEYBYTES];
static uint8_t sk[PQCLEAN_FALCONPADDED512_CLEAN_CRYPTO_SECRETKEYBYTES];
static uint8_t sig[PQCLEAN_FALCONPADDED512_CLEAN_CRYPTO_BYTES];
static size_t siglen;
static uint8_t msg[44];

static int sign_msg(void)
{
  int rc = PQCLEAN_FALCONPADDED512_CLEAN_crypto_sign_signature(sig, &siglen, msg, sizeof msg, sk);
  return (rc == 0 && siglen == sizeof sig) ? 0 : 1;
}

static int verify_msg(void)
{
  return PQCLEAN_FALCONPADDED512_CLEAN_crypto_sign_verify(sig, siglen, msg, sizeof msg, pk);
}

int main(void)
{
  uint32_t st = 0x2468ace1u;
  unsigned ok = 0, fail = 0, rej_ok = 0, rej_fail = 0;
  long stack_kg = -1, stack_sign = -1, stack_ver = -1;
  int rc = 0;

  cyc_init();
  bench_meta_common();
  bench_meta("alg", "Falcon");
  bench_meta("param", PARAM);
  bench_meta("lib", "liboqs 0.16.0 (commit 5a1a854b0dc9f2141bdc771c555ee60c37950183) pqclean_falcon-padded-512_clean");

  STACK_MEASURE(stack_kg, rc = PQCLEAN_FALCONPADDED512_CLEAN_crypto_sign_keypair(pk, sk));
  if (rc != 0) fail++; else ok++;
  for (unsigned i = 0; i < BENCH_ITERS; i++)
  {
    bench_fill(msg, sizeof msg, &st);
    if (i == 0)
    {
      STACK_MEASURE(stack_sign, rc = sign_msg());
    }
    else
    {
      rc = sign_msg();
    }
    if (rc != 0) fail++; else ok++;
    if (i == 0)
    {
      STACK_MEASURE(stack_ver, rc = verify_msg());
    }
    else
    {
      rc = verify_msg();
    }
    if (rc == 0) ok++; else fail++;
    msg[12] ^= 1u;
    if (verify_msg() != 0) rej_ok++; else rej_fail++;
    msg[12] ^= 1u;
    sig[100] ^= 1u;
    if (verify_msg() != 0) rej_ok++; else rej_fail++;
    sig[100] ^= 1u;
  }
  printf("STACK,Falcon,%s,keygen,%ld\n", PARAM, stack_kg);
  printf("STACK,Falcon,%s,sign,%ld\n", PARAM, stack_sign);
  printf("STACK,Falcon,%s,verify,%ld\n", PARAM, stack_ver);
  printf("CHECK,Falcon,%s,keygen_sign_verify,%u,%u\n", PARAM, ok, fail);
  printf("CHECK,Falcon,%s,reject_modified_message_or_signature,%u,%u\n", PARAM, rej_ok, rej_fail);
  return (fail || rej_fail) ? 1 : 0;
}
