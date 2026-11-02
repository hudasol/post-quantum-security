/*
 * SHAKE256 for the pinned Falcon-512 sources (research benchmark glue, round 7). Author: Huda Mueen.
 * SPDX-License-Identifier: Apache-2.0
 *
 * The Falcon sources of the pinned library include "fips202.h" and call the incremental SHAKE256 interface of
 * PQClean (shake256_inc_init, _absorb, _finalize, _squeeze, _ctx_release). This header maps that interface onto
 * the SHAKE256 of the pinned mldsa-native (its src/fips202), the same Keccak code that the other round 6 designs
 * use, so that no further hash implementation enters the images. It implements no primitive itself.
 * Build with MLD_CONFIG_PARAMETER_SET=44 and the mldsa-native source folder on the include path.
 */
#ifndef PROTO_FALCON_SHIM_FIPS202_H
#define PROTO_FALCON_SHIM_FIPS202_H
#include <stddef.h>
#include <stdint.h>

#include "src/fips202/fips202.h"

typedef mld_shake256ctx shake256incctx;

static inline void shake256_inc_init(shake256incctx *s) { mld_shake256_init(s); }
static inline void shake256_inc_absorb(shake256incctx *s, const uint8_t *in, size_t inlen)
{
  mld_shake256_absorb(s, in, inlen);
}
static inline void shake256_inc_finalize(shake256incctx *s) { mld_shake256_finalize(s); }
static inline void shake256_inc_squeeze(uint8_t *out, size_t outlen, shake256incctx *s)
{
  mld_shake256_squeeze(out, outlen, s);
}
static inline void shake256_inc_ctx_release(shake256incctx *s) { mld_shake256_release(s); }

#endif
