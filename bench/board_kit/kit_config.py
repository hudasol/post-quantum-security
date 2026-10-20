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

PLATFORMS = ("nucleo-l4r5zi", "mps2-an386")


def target_name(impl_path, kind, platform):
    """pqm4 binary name, as built by mupq.Implementation.get_binary_path."""
    ext = "hex" if platform == "nucleo-l4r5zi" else "bin"
    return f"bin/{impl_path.replace('/', '_')}_{kind}.{ext}"


def elf_name(impl_path, kind):
    return f"elf/{impl_path.replace('/', '_')}_{kind}.elf"
