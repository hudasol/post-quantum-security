/*
 * Random bytes for the pinned Falcon-512 sources (research benchmark glue, round 7). Author: Huda Mueen.
 * SPDX-License-Identifier: Apache-2.0
 * In the RTL images this is the fixed seed test generator of rtlsim/sw/bench_rng.c, which is NOT a secure random
 * number generator; on the host it is sitl/pqlib/randombytes.c.
 */
#ifndef PROTO_FALCON_SHIM_RANDOMBYTES_H
#define PROTO_FALCON_SHIM_RANDOMBYTES_H
#include <stddef.h>
#include <stdint.h>

int randombytes(uint8_t *out, size_t outlen);

#endif
