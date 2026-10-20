# Pinned third party sources and settings for the RTL simulation runs.
# Author: Huda Mueen. Sourced by the other rtlsim scripts.
# Third party code is cloned OUTSIDE the repository into WORK_DIR and is never
# copied into the repository.

WORK_DIR="${WORK_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/work}"  # outside the repository

IBEX_URL="https://github.com/lowRISC/ibex.git"
# Ibex master at the time of the run (no release tag newer than v2.1.0 exists;
# this commit is v2.1.0-242-g1b29dae8, committed 2026-10-19).
IBEX_COMMIT="1b29dae8866e6c0f0a3cd9dead53a77b4f45e357"
IBEX_CONFIG="small"

MLKEM_URL="https://github.com/pq-code-package/mlkem-native.git"
MLKEM_COMMIT="d1b2fe782888bdb761a50336012923180be7f502"   # tag v2.0.0
MLDSA_URL="https://github.com/pq-code-package/mldsa-native.git"
MLDSA_COMMIT="834a90d5e846ffa1e1611bd24e160bb2e9b86d35"   # tag v2.0.0

FUSESOC_VERSION="2.4.3"

CROSS="${CROSS:-riscv64-unknown-elf-}"
ARCH_FLAGS="-march=rv32imc_zicsr -mabi=ilp32"
OPT_FLAGS="-O3 -fomit-frame-pointer"
COMMON_CFLAGS="-static -mcmodel=medany -ffreestanding -fno-builtin-printf -std=gnu99"
PICOLIBC_DIR="/usr/lib/picolibc/riscv64-unknown-elf"
# picolibc ships no rv32imc multilib; the rv32im ilp32 build is ABI compatible.
PICOLIBC_MULTILIB="rv32im/ilp32"

# Simple system memory map used by the generated link script. The RTL RAM is
# 1 MB at 0x100000 (ibex_simple_system.sv, Depth 1024*1024/4); the stock link
# script uses only 224 kB of it, so the generated script widens both regions.
RAM_LENGTH="0xC0000"      # 768 kB code and data at 0x100000
STACK_ORIGIN="0x1C0000"
STACK_LENGTH="0x40000"    # 256 kB stack

BENCH_RUNS="${BENCH_RUNS:-5}"
SEED="20261020"
