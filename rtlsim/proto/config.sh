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
PROTO_IMAGES="primitives classical pq_only hybrid_f1 per_command_mldsa44 mavlink_tag"
PROTO_RUNS="${PROTO_RUNS:-5}"
PROTO_SEED="20261021"          # run r uses seed PROTO_SEED + r (seed block 20261021 to 20261025 for 5 runs)
STACK_PAINT_BYTES="0x30000"    # 192 kB painted below the caller of each timed step (stack is 256 kB)
