#!/usr/bin/env python3
"""Build the B1 images: the repository harness (bench/mcu/src) with mlkem-native and mldsa-native
v2.0.0, linked against pqm4's platform layer (start up, clock, UART, linker script, libopencm3).

Author: Huda Mueen. Route A of the board kit: no new start up, clock or UART code. The only new C
file is b1/b1_main.c (glue: clock and flash read back, counter check, printf to hal_send_str).
Third party code is cloned at pinned commits under WORK (outside the repository) and nothing is
copied into the repository. pqm4 is cloned a second time (pqm4_b1) so that its retained make
variables do not clash with the B0 build tree.

Compiler flags are the ones pqm4 prints for the platform (pqm4_platform.mk kit-flags) with -O3
replaced by -O2 (the harness setting used for the emulator and host runs), plus
-ffunction-sections -fdata-sections and the harness defines of bench/mcu/Makefile.

Usage: python3 build_b1.py --platform nucleo-l4r5zi|mps2-an386 [--sets mlkem:768,mldsa:44]
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import kit_config as K  # noqa: E402
from build_b0 import run, parse_size  # noqa: E402

HARNESS = os.path.join(REPO, "bench", "mcu", "src")
GLUE = os.path.join(HERE, "b1", "b1_main.c")
PLATFORM_MK = os.path.join(HERE, "b1", "pqm4_platform.mk")
PQM4_B1 = os.path.join(K.WORK, "pqm4_b1")


def ensure_clone(url, dest, commit, log, tag=None, recursive=False):
    """Clone url into dest at the pinned commit (once) and verify HEAD."""
    if not os.path.isdir(os.path.join(dest, ".git")):
        if tag:
            run(["git", "clone", "--quiet", "--depth", "1", "--branch", tag, url, dest], K.WORK, log)
        else:
            run(["git", "clone", "--quiet", url, dest], K.WORK, log)
            run(["git", "checkout", "--quiet", commit], dest, log)
        if recursive:
            run(["git", "submodule", "update", "--init", "--recursive"], dest, log)
    head = run(["git", "rev-parse", "HEAD"], dest, log).stdout.strip()
    if head != commit:
        raise SystemExit(f"{dest}: HEAD {head} differs from pin {commit}")
    return head


def kit_flags(platform, log):
    for d in ("obj", "elf", "bin"):
        shutil.rmtree(os.path.join(PQM4_B1, d), ignore_errors=True)
    base = ["make", "-f", PLATFORM_MK, f"PLATFORM={platform}", "AIO=", "NO_RANDOMBYTES=1"]
    run(base + ["kit-prep"], PQM4_B1, log)
    out = run(base + ["kit-flags"], PQM4_B1, log).stdout
    flags = {}
    for line in out.splitlines():
        if line.startswith("KIT_"):
            k, v = line.split("=", 1)
            flags[k[4:]] = v.split()
    return flags


def harness_flags(alg, pset, iters, platform, mlk, mld):
    f = ["-ffunction-sections", "-fdata-sections", "-Wno-unused-parameter",
         f"-DBENCH_ITERS={iters}", "-DBENCH_CLOCK_HZ=0", "-DBENCH_RUN_ID=0",
         f"-DBENCH_STACK_SPAN={K.B1_STACK_SPAN}", "-DBENCH_DISABLE_IRQ",
         "-DBENCH_OPT_NOTE=\"-O2 pqm4 platform flags\"", "-Dmain=bench_harness_main",
         "-Dprintf=bench_printf", f"-I{HARNESS}"]
    if alg == "mlkem":
        f += ["-DMLK_CONFIG_NAMESPACE_PREFIX=mlkem", f"-DMLK_CONFIG_PARAMETER_SET={pset}",
              f"-I{os.path.join(mlk, 'mlkem')}"]
    else:
        f += ["-DMLD_CONFIG_NAMESPACE_PREFIX=mldsa", f"-DMLD_CONFIG_PARAMETER_SET={pset}",
              f"-I{os.path.join(mld, 'mldsa')}"]
    return f


def build(platform, sets, iters_override=None):
    log = []
    os.makedirs(K.WORK, exist_ok=True)
    pq = ensure_clone(K.PQM4_URL, PQM4_B1, K.PQM4_COMMIT, log, recursive=True)
    mlk = os.path.join(K.LIBS_DIR, "mlkem-native")
    mld = os.path.join(K.LIBS_DIR, "mldsa-native")
    os.makedirs(K.LIBS_DIR, exist_ok=True)
    ensure_clone(K.MLKEM_NATIVE[0], mlk, K.MLKEM_NATIVE[2], log, tag=K.MLKEM_NATIVE[1])
    ensure_clone(K.MLDSA_NATIVE[0], mld, K.MLDSA_NATIVE[2], log, tag=K.MLDSA_NATIVE[1])
    fl = kit_flags(platform, log)
    cflags = ["-O2" if x == "-O3" else x for x in fl["CFLAGS"]]
    # pqm4's CFLAGS carry -MMD; dependency files are not needed here.
    cflags = [x for x in cflags if x != "-MMD"]
    if platform == "nucleo-l4r5zi":
        cflags.append("-DBENCH_BOARD_OPENCM3")
    dest = os.path.join(K.OUT_DIR, platform, "b1")
    objdir = os.path.join(dest, "obj")
    os.makedirs(objdir, exist_ok=True)
    images = []
    for alg, pset in sets:
        iters = iters_override or K.B1_ITERS[alg]
        hf = harness_flags(alg, pset, iters, platform, mlk, mld)
        lib_src = os.path.join(mlk, "mlkem", "mlkem_native.c") if alg == "mlkem" else \
            os.path.join(mld, "mldsa", "mldsa_native.c")
        srcs = [os.path.join(HARNESS, f"bench_{alg}.c"), os.path.join(HARNESS, "bench_rng.c"),
                lib_src, GLUE]
        objs = []
        for s in srcs:
            o = os.path.join(objdir, f"{alg}{pset}_{os.path.basename(s)}.o")
            extra = [f"-I{HARNESS}"] if s == GLUE else hf  # glue keeps its own main and printf
            run([fl["CC"][0], "-c", "-o", o] + cflags + extra + [s], PQM4_B1, log)
            objs.append(o)
        name = f"b1_{alg}_{pset}"
        elf = os.path.join(dest, name + ".elf")
        run([fl["CC"][0]] + fl["LDFLAGS"] + ["-Wl,-Map=" + os.path.join(dest, name + ".map"),
                                             "-o", elf] + objs +
            ["-Wl,--start-group"] + fl["LDLIBS"] + ["-Wl,--end-group"], PQM4_B1, log)
        ext = "hex" if platform == "nucleo-l4r5zi" else "bin"
        img = os.path.join(dest, f"{name}.{ext}")
        run([fl["OBJCOPY"][0], "-Oihex" if ext == "hex" else "-Obinary", elf, img], PQM4_B1, log)
        size = parse_size(run(["arm-none-eabi-size", elf], PQM4_B1, log).stdout)
        images.append({"experiment": "B1", "platform": platform, "scheme": f"{alg}-{pset}",
                       "variant": "portable_c", "kind": "harness", "iterations": iters,
                       "elf": os.path.basename(elf), "image": os.path.basename(img), **size})
    gcc = run(["arm-none-eabi-gcc", "--version"], PQM4_B1, log).stdout.splitlines()[0]
    rec = {"experiment": "B1", "platform": platform, "pqm4_commit": pq,
           "mlkem_native": K.MLKEM_NATIVE[2], "mldsa_native": K.MLDSA_NATIVE[2],
           "toolchain": gcc, "cflags": cflags, "pqm4_flags": fl, "images": images,
           "commands": log, "out_dir": dest}
    with open(os.path.join(dest, "build_record.json"), "w") as fh:
        json.dump(rec, fh, indent=1)
    return rec


def parse_sets(text):
    out = []
    for item in text.split(","):
        alg, p = item.split(":")
        out.append((alg, int(p)))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--platform", choices=K.PLATFORMS, required=True)
    ap.add_argument("--sets", default=",".join(f"{a}:{p}" for a, p in K.B1_SETS))
    ap.add_argument("--iters", type=int, default=None, help="override iterations for all sets")
    a = ap.parse_args(argv)
    rec = build(a.platform, parse_sets(a.sets), a.iters)
    for im in rec["images"]:
        print(im["image"], im["text"], im["data"], im["bss"])
    print("record:", os.path.join(rec["out_dir"], "build_record.json"))


if __name__ == "__main__":
    main()
