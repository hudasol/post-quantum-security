/*
 * Wrappers around the incremental SHAKE256 of mldsa-native (src/fips202/fips202.h at the pinned commit).
 * Compiled with -I<mldsa-native>/mldsa -DMLD_CONFIG_PARAMETER_SET=44 so that the namespaced symbols are
 * those of the ML-DSA-44 build. Research benchmark code; no hash function is implemented here.
 * Author: Huda Mueen. SPDX-License-Identifier: Apache-2.0
 */
#include "proto_hash.h"

#include "src/fips202/fips202.h"

_Static_assert(sizeof(ph_ctx) == sizeof(mld_shake256ctx), "context layout");

void ph_init(ph_ctx *c) { mld_shake256_init((mld_shake256ctx *)c); }

void ph_absorb(ph_ctx *c, const uint8_t *in, size_t len)
{
  mld_shake256_absorb((mld_shake256ctx *)c, in, len);
}

void ph_squeeze(ph_ctx *c, uint8_t *out, size_t len)
{
  mld_shake256_finalize((mld_shake256ctx *)c);
  mld_shake256_squeeze(out, len, (mld_shake256ctx *)c);
  mld_shake256_release((mld_shake256ctx *)c);
}
