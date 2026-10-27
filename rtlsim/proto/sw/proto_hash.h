/*
 * Thin wrappers around the SHAKE256 functions of the pinned mldsa-native FIPS 202 code, used by the
 * protocol glue for the transcript hash, the key derivation and the key confirmation tags.
 * Research benchmark code; no hash function is implemented here.
 * Author: Huda Mueen. SPDX-License-Identifier: Apache-2.0
 */
#ifndef PROTO_HASH_H
#define PROTO_HASH_H
#include <stddef.h>
#include <stdint.h>

/* Same layout as mld_shake256ctx (checked with a static assertion in proto_hash.c). */
typedef struct
{
  uint64_t s[25];
  unsigned int pos;
} ph_ctx;

void ph_init(ph_ctx *c);
void ph_absorb(ph_ctx *c, const uint8_t *in, size_t len);
void ph_squeeze(ph_ctx *c, uint8_t *out, size_t len); /* finalizes, squeezes once, releases */

#endif
