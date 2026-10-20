/* Driver for the external check of the cycle model: calls the key expansion from a seed of the
 * pqcrystals lowram ML-DSA library (dilithium-lowram, tag crypto-benchmark-0.0.16) three times with
 * fixed seeds. Benchmark subject only; no timing is done here (the image is traced by
 * cyclemodel/trace_all.py). Seeds are fixed byte patterns, not secrets. */
#include <stdint.h>
#include "sign.h"
#include "params.h"

static uint8_t pk[CRYPTO_PUBLICKEYBYTES];
static uint8_t sk[CRYPTO_SECRETKEYBYTES];

int main(void)
{
  uint8_t seed[32];
  int rc = 0;
  for (unsigned r = 0; r < 3; r++) {
    for (unsigned i = 0; i < sizeof seed; i++) seed[i] = (uint8_t)(i * 7u + r * 31u + 1u);
    rc |= crypto_sign_keypair_from_seed(seed, pk, sk);
  }
  return rc;
}
