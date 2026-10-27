/*
 * Random bytes for the host builds of mlkem-native and mldsa-native used by the software in the loop gateway.
 * Research benchmark glue, not for use: it forwards to the operating system generator (getrandom) and
 * implements no cryptographic primitive. Author: Huda Mueen. SPDX-License-Identifier: Apache-2.0
 */
#include <stddef.h>
#include <stdint.h>
#include <sys/random.h>
#include <sys/types.h>

int randombytes(uint8_t *out, size_t outlen);

int randombytes(uint8_t *out, size_t outlen)
{
  size_t got = 0;
  while (got < outlen)
  {
    ssize_t r = getrandom(out + got, outlen - got, 0);
    if (r < 0)
    {
      return -1;
    }
    got += (size_t)r;
  }
  return 0;
}
