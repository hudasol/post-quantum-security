/*
 * Fixed seed byte generator for cycle count runs only.
 * Author: Huda Mueen. SPDX-License-Identifier: Apache-2.0
 *
 * INSECURE: this is the splitmix64 sequence with a fixed seed. It exists so
 * that every simulation run sees the same inputs. It is predictable by design
 * and must never be used to generate keys or nonces for real use.
 */
#include <stddef.h>
#include <stdint.h>

static uint64_t state;

void bench_rng_seed(uint64_t seed);
int randombytes(uint8_t *out, size_t outlen);

void bench_rng_seed(uint64_t seed) { state = seed; }

static uint64_t next(void)
{
  uint64_t z = (state += 0x9E3779B97F4A7C15ull);
  z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ull;
  z = (z ^ (z >> 27)) * 0x94D049BB133111EBull;
  return z ^ (z >> 31);
}

int randombytes(uint8_t *out, size_t outlen)
{
  while (outlen > 0)
  {
    uint64_t v = next();
    for (int i = 0; i < 8 && outlen > 0; i++, outlen--)
    {
      *out++ = (uint8_t)(v >> (8 * i));
    }
  }
  return 0;
}
