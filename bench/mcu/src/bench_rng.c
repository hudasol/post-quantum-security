/* bench_rng.c - deterministic stand-in for randombytes(), FOR BENCHMARKING ONLY.
 *
 * mlkem-native and mldsa-native expect the integrator to supply `int randombytes(uint8_t*, size_t)`.
 * This one is a xorshift generator: it is NOT secure and must never be used to generate real keys.
 * Its purpose is reproducible timing without a hardware RNG in the timed region. Report the cost
 * of your board's real TRNG separately (see README, "what to report").
 */
#include <stddef.h>
#include <stdint.h>

static uint64_t bench_rng_state = 0x9e3779b97f4a7c15ull;

int randombytes(uint8_t *out, size_t outlen)
{
  for (size_t i = 0; i < outlen; i++)
  {
    uint64_t x = bench_rng_state;
    x ^= x << 13;
    x ^= x >> 7;
    x ^= x << 17;
    bench_rng_state = x;
    out[i] = (uint8_t)(x >> 24);
  }
  return 0;
}
