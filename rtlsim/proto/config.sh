# Settings of the round 6 protocol baselines (rtlsim/proto). Author: Huda Mueen.
# Sourced by the other rtlsim/proto scripts after rtlsim/config.sh, whose compiler, flags, picolibc,
# library pins and memory settings are reused unchanged (same as round 5).
#
# Locations outside the repository (set them in the environment to rerun elsewhere):
#   WORK_DIR       round 5 work folder with ibex/, mlkem-native/, mldsa-native/ (rtlsim/config.sh)
#   CV32_WORK_DIR  folder with cv32e40p/ and cv32e40p_build/obj/Vtb_top (default WORK_DIR)
#   PROTO_TP       folder for the classical library and the MAVLink C library fetched by fetch.sh
#   PROTO_BUILD    folder for the protocol images
CV32_WORK_DIR="${CV32_WORK_DIR:-$WORK_DIR}"
PROTO_TP="${PROTO_TP:-$WORK_DIR/rtl6_third_party}"
PROTO_BUILD="${PROTO_BUILD:-$WORK_DIR/rtl6_proto_build}"

# Classical library: Monocypher (X25519, Ed25519 with SHA-512 from its optional module), release tag 4.0.3.
# Licence: dual BSD-2-Clause or CC0-1.0 (LICENCE.md at the tag).
MONO_URL="https://github.com/LoupVaillant/Monocypher.git"
MONO_COMMIT="ab2b16dd619ad5f6979a4fbe69cfa324a6fcc35f"   # tag 4.0.3, committed 2026-06-15

# MAVLink 2 C library (generated headers): signing helpers and the SHA-256 they use (mavlink_sha256.h).
# Licence: MIT for the generated C library (mavlink.io/en/ introduction); mavlink_sha256.h carries a
# BSD-3-Clause notice (Heimdal, Kungliga Tekniska Hogskolan). Master at the time of the run.
MAVLINK_URL="https://github.com/mavlink/c_library_v2.git"
MAVLINK_COMMIT="6b4243f0e54b42ddb1e65df7a3a5e8c99d15ec1f"   # master, committed 2026-10-25

# Images: one per design. The primitives image times each operation alone.
PROTO_IMAGES="primitives classical pq_only hybrid_f1 kem_auth per_command_mldsa44 mavlink_tag"
# Runs per image. Round 6 first ran 5 runs per image (seed block 20261021 to 20261025); after the review,
# the session designs, the per command design and the primitives run 15 runs (seed block 20261021 to
# 20261035, which extends the first block, so runs 0 to 4 repeat the first runs seed for seed). The tag
# image has no data dependent operation and stays at 5 runs.
PROTO_RUNS="${PROTO_RUNS:-15}"
PROTO_RUNS_TAG="${PROTO_RUNS_TAG:-5}"
PROTO_SEED="20261021"          # run r uses seed PROTO_SEED + r

# Runs of one image (mavlink_tag: PROTO_RUNS_TAG; every other image: PROTO_RUNS).
proto_runs_for() {
  if [ "$1" = mavlink_tag ]; then echo "$PROTO_RUNS_TAG"; else echo "$PROTO_RUNS"; fi
}
STACK_PAINT_BYTES="0x30000"    # 192 kB painted below the caller of each timed step (stack is 256 kB)

# Round 7: Falcon-512 per command. Padded Falcon-512 (fixed 666 B signatures), clean implementation with integer
# emulated floating point, from the liboqs release tag 0.16.0, folder src/sig/falcon/pqclean_falcon-padded-512_clean
# (a copy of PQClean; identical to PQClean master of 2026-08-04, commit 0586a824, apart from build files).
# Licence of the Falcon folder: MIT (LICENSE in that folder); liboqs: MIT. Only that folder is compiled.
LIBOQS_URL="https://github.com/open-quantum-safe/liboqs.git"
LIBOQS_TAG="0.16.0"
LIBOQS_COMMIT="5a1a854b0dc9f2141bdc771c555ee60c37950183"   # tag 0.16.0, committed 2026-07-09
FALCON_SUBDIR="src/sig/falcon/pqclean_falcon-padded-512_clean"
PROTO_IMAGES_R7="per_command_falcon512"
