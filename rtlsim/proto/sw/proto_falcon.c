/*
 * Round 7: Falcon-512 signature per command on open RISC-V cores in RTL simulation (research benchmark code).
 * Author: Huda Mueen. SPDX-License-Identifier: Apache-2.0
 *
 * BENCHMARK CODE ONLY, NOT FOR USE. This file is timing code around the pinned padded Falcon-512 sources of the
 * library recorded in rtlsim/proto/config.sh (FALCON_*) and the MAVLink 2 C library. It implements no
 * cryptographic primitive. The Falcon sources use integer emulated floating point (their fpr type is a 64 bit
 * integer), so they run on the RV32IMC cores, which have no floating point unit. SHAKE256 comes from mldsa-native
 * through rtlsim/proto/sw/falcon_shim/fips202.h. Randomness comes from rtlsim/sw/bench_rng.c, a fixed seed test
 * generator that is NOT a secure random number generator.
 *
 * Design (the per command design of round 6, PROTO_DESIGN_PER_COMMAND in proto_bench.c, with Falcon-512 in place of
 * ML-DSA-44): the ground signs each COMMAND_LONG frame and the vehicle verifies it. One difference from the ML-DSA-44
 * image: Falcon-512 key generation is far more expensive than ML-DSA-44 key generation, so the key pair is
 * generated once (seed PROTO_SEED, timed as one run of provisioning_keypair) instead of once per run; each of the
 * PROTO_RUNS runs reseeds the generator with PROTO_SEED + r and signs and verifies command r, as in round 6.
 */
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#include "api.h"
#include "proto_util.h"

#include "common/mavlink.h"

#define SET "per_command_falcon512"
#define FAL_PK PQCLEAN_FALCONPADDED512_CLEAN_CRYPTO_PUBLICKEYBYTES
#define FAL_SK PQCLEAN_FALCONPADDED512_CLEAN_CRYPTO_SECRETKEYBYTES
#define FAL_SIG PQCLEAN_FALCONPADDED512_CLEAN_CRYPTO_BYTES

#ifndef PROTO_RUNS
#define PROTO_RUNS 15
#endif
#ifndef PROTO_SEED
#define PROTO_SEED 20261021u
#endif

void bench_rng_seed(uint64_t seed);

static uint8_t skG[FAL_SK], pkG[FAL_PK], sig[FAL_SIG];
static size_t siglen;
static uint8_t frame[MAVLINK_MAX_PACKET_LEN];
static uint16_t frame_len;

/* Unsigned MAVLink 2 COMMAND_LONG frame built with the MAVLink C library (untimed), as in proto_bench.c. */
static void build_command(int r)
{
  mavlink_message_t msg;
  mavlink_get_channel_status(MAVLINK_COMM_0)->signing = NULL;
  mavlink_msg_command_long_pack(1, 1, &msg, 1, 1, (uint16_t)(400 + r), 0, 1.0f, 2.0f + (float)r, 3.0f,
                                4.0f, 5.0f, 6.0f, 7.0f);
  frame_len = mavlink_msg_to_send_buffer(frame, &msg);
}

static int sign_cmd(void)
{
  siglen = 0;
  int rc = PQCLEAN_FALCONPADDED512_CLEAN_crypto_sign_signature(sig, &siglen, frame, frame_len, skG);
  return (rc == 0 && siglen == FAL_SIG) ? 0 : 1;
}

static int verify_cmd(void)
{
  return PQCLEAN_FALCONPADDED512_CLEAN_crypto_sign_verify(sig, siglen, frame, frame_len, pkG);
}

static void run_design(void)
{
  build_command(0);
  pu_msg(SET, "command_frame", "ground_to_vehicle", frame_len);
  pu_msg(SET, "command_signature", "ground_to_vehicle", FAL_SIG);
  bench_rng_seed((uint64_t)PROTO_SEED);
  PU_STEP(SET, "provisioning_keypair", 0, PQCLEAN_FALCONPADDED512_CLEAN_crypto_sign_keypair(pkG, skG));
  for (int r = 0; r < PROTO_RUNS; r++)
  {
    bench_rng_seed((uint64_t)PROTO_SEED + (uint64_t)r);
    build_command(r);
    PU_STEP(SET, "ground_sign_command", r, sign_cmd());
    PU_STEP(SET, "vehicle_verify_command", r, verify_cmd());
    if (r == 0)
    {
      frame[12] ^= 1u;
      pu_chk(SET, "vehicle_rejects_modified_command", r, verify_cmd() != 0);
      frame[12] ^= 1u;
      sig[100] ^= 1u;
      pu_chk(SET, "vehicle_rejects_modified_signature", r, verify_cmd() != 0);
      sig[100] ^= 1u;
    }
  }
}

int main(void)
{
  pcount_enable(1);
  pu_measure_overhead();
  pu_cfg_s("set", SET);
  pu_cfg("seed_first", PROTO_SEED);
  pu_cfg("runs", PROTO_RUNS);
  pu_cfg("timer_overhead_cycles", pu_overhead);
  pu_cfg("stack_paint_bytes", STACK_PAINT_BYTES);
  pu_fails = 0;
  run_design();
  pu_done(SET);
  return 0;
}
