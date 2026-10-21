"""Pins and run settings shared by the board kit scripts (B0 and B1 of docs/BOARD_RUN_PROTOCOL.md).

Author: Huda Mueen. Board support only; no cryptography is implemented here.
Third party code is fetched at pinned commits outside the repository and is never committed.
"""
import os

PQM4_URL = "https://github.com/mupq/pqm4.git"
PQM4_COMMIT = "5e5cc76d0b072ee7077e58afcbc619a1a67a53b4"
# Submodule commits recorded at the pin (git submodule status after a recursive clone).
PQM4_SUBMODULES = {
    "libopencm3": "1f3abd43763fa39d23e737602b6d0011a45c70b2",
    "mupq": "ddcccedb2db9d0250856bd58ee5c46c61e506c5d",
    "mupq/pqclean": "c3e6861fbb0a0b2721d2599c0a68430061414f18",
}
MLKEM_NATIVE = ("https://github.com/pq-code-package/mlkem-native.git", "v2.0.0",
                "d1b2fe782888bdb761a50336012923180be7f502")
MLDSA_NATIVE = ("https://github.com/pq-code-package/mldsa-native.git", "v2.0.0",
                "834a90d5e846ffa1e1611bd24e160bb2e9b86d35")

# Work directory for clones and images: BOARD_KIT_WORK, or a directory named work next to the
# repository clone (so nothing third party ever lands inside the repository).
_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WORK = os.environ.get("BOARD_KIT_WORK", os.path.join(os.path.dirname(_REPO), "work"))
PQM4_DIR = os.path.join(WORK, "pqm4_kit")
OUT_DIR = os.path.join(WORK, "board_kit_out")
LIBS_DIR = os.path.join(WORK, "board_kit_libs")

# B0 variants: clean (PQClean reference C) and the fastest m4f variant per scheme in pqm4
# benchmarks.csv at the pin (ML-KEM-768: m4fspeed; ML-DSA-44: m4f). Optional extra: m4fstack.
# (scheme, variant, implementation path inside pqm4, MUPQ_NAMESPACE or "")
B0_VARIANTS = [
    ("ml-kem-768", "clean", "mupq/pqclean/crypto_kem/ml-kem-768/clean", "PQCLEAN_MLKEM768_CLEAN_"),
    ("ml-kem-768", "m4fspeed", "crypto_kem/ml-kem-768/m4fspeed", ""),
    ("ml-dsa-44", "clean", "mupq/pqclean/crypto_sign/ml-dsa-44/clean", "PQCLEAN_MLDSA44_CLEAN_"),
    ("ml-dsa-44", "m4f", "crypto_sign/ml-dsa-44/m4f", ""),
]
B0_OPTIONAL = [
    ("ml-kem-768", "m4fstack", "crypto_kem/ml-kem-768/m4fstack", ""),
    ("ml-dsa-44", "m4fstack", "crypto_sign/ml-dsa-44/m4fstack", ""),
]
B0_KINDS = ["test", "speed", "stack"]
# Iterations per power cycle (brief: 100, and 1000 for signing). pqm4 loops MUPQ_ITERATIONS times
# in speed.c; it is a retained make variable, so each value needs its own clean build.
ITERATIONS = {"ml-kem-768": 100, "ml-dsa-44": 1000}

B1_SETS = [("mlkem", 512), ("mlkem", 768), ("mlkem", 1024), ("mldsa", 44), ("mldsa", 65), ("mldsa", 87)]
B1_ITERS = {"mlkem": 100, "mldsa": 100}
B1_STACK_SPAN = 131072

PLATFORMS = ("nucleo-l4r5zi", "mps2-an386", "nucleo-l552ze-q")

# Cache passes (round 5). "on": the state pqm4's hal_setup(CLOCK_BENCHMARK) leaves (icache, dcache
# and prefetch on for nucleo-l4r5zi); "off": b1_main.c built with -DBENCH_CACHE_OFF clears them
# after the clock set up, at zero flash wait states only. Image names carry the pass.
CACHE_PASSES = ("on", "off")
CACHE_SUFFIX = {"on": "", "off": "_cacheoff"}

# Cortex-M33 board (round 5). pqm4 has no Cortex-M33 platform at PQM4_COMMIT (mk/ lists
# cw308t-stm32f3, cw308t-stm32f415, mps2-an386, nucleo-l476rg, nucleo-l4r5zi, stm32f4discovery;
# unchanged at pqm4 master e1146b1bc180c66689682f6ce63bd8f126a51ace, fetched 2026-10-20), and the
# pinned libopencm3 has no STM32L5 family. The kit therefore builds B1 for NUCLEO-L552ZE-Q with the
# vendor CMSIS files (start up, system file, linker script, device header), used unchanged, and a
# small platform file (b1/m33/hal_l552.c). B0 (pqm4 images) is not built for this board.
M33_PLATFORM = "nucleo-l552ze-q"
M33_DEVICE_DEFINE = "STM32L552xx"
CMSIS_DEVICE_L5 = ("https://github.com/STMicroelectronics/cmsis_device_l5.git", "v1.0.7",
                   "e237398c0cbae890f4659f74fe6b64cae339b6a0")
CMSIS_DEVICE_L4 = ("https://github.com/STMicroelectronics/cmsis_device_l4.git", "v1.7.5",
                   "dc04e41afbd7c204cd09f2fa5dd29658efbaff6c")  # register citation only
CMSIS_CORE = ("https://github.com/STMicroelectronics/cmsis_core.git", "v5.9.0_20250520",
              "b7487de1303e2eb77c402432e368691e9dcfb5f0")
HAL_STM32_PINCTRL = ("https://github.com/zephyrproject-rtos/hal_stm32.git",
                     "c9550199186236d610092f4005f8c9bae2a6bfcf",
                     "dts/st/l5/stm32l552z(c-e)txq-pinctrl.dtsi")  # AF8 citation only
M33_CFLAGS = ["-mcpu=cortex-m33", "-mthumb", "-mfloat-abi=hard", "-mfpu=fpv5-sp-d16",
              "-std=gnu99", "-O2", "-g3", "-Wall", "-Wextra", "-Wshadow", "-fno-common"]
M33_LDSCRIPT = "Source/Templates/gcc/linker/STM32L552xE_FLASH.ld"
M33_STARTUP = "Source/Templates/gcc/startup_stm32l552xx.s"
M33_SYSTEM = "Source/Templates/system_stm32l5xx.c"
# The M33 board runs at the reset clock (MSI 4 MHz), five times slower than the 20 MHz of
# nucleo-l4r5zi, so its B1 images loop fewer times to keep the session within one afternoon.
B1_ITERS_M33 = {"mlkem": 20, "mldsa": 20}

# Register addresses printed in the checklist for an optional OpenOCD cross check, computed from
# the pinned CMSIS headers (stm32l4r5xx.h: FLASH_R_BASE = PERIPH_BASE + 0x20000 + 0x2000;
# stm32l552xx.h: FLASH_R_BASE_NS = 0x40000000 + 0x20000 + 0x2000, ICACHE_BASE_NS = 0x40000000 +
# 0x20000 + 0x10400). Checked against the headers by session_plan.register_addresses_cmsis().
FLASH_ACR_ADDR = {"nucleo-l4r5zi": 0x40022000, "nucleo-l552ze-q": 0x40022000}
ICACHE_CR_ADDR = {"nucleo-l552ze-q": 0x40030400}


def image_base(alg, pset, cache_pass="on"):
    """B1 image name without extension, for example b1_mlkem_768 or b1_mldsa_44_cacheoff."""
    return f"b1_{alg}_{pset}{CACHE_SUFFIX[cache_pass]}"


def target_name(impl_path, kind, platform):
    """pqm4 binary name, as built by mupq.Implementation.get_binary_path."""
    ext = "bin" if platform == "mps2-an386" else "hex"
    return f"bin/{impl_path.replace('/', '_')}_{kind}.{ext}"


def elf_name(impl_path, kind):
    return f"elf/{impl_path.replace('/', '_')}_{kind}.elf"
