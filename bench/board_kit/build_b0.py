#!/usr/bin/env python3
"""Build the B0 images (pqm4 ML-KEM-768 and ML-DSA-44, clean and fastest m4f variant; test, speed and
stack binaries) for one pqm4 platform, using pqm4's own build system and platform layer.

Author: Huda Mueen. The make invocation copies what pqm4's benchmarks.py passes to make
(mupq/mupq.py run_make plus interface.py M4Settings at the pinned commit): IMPLEMENTATION_PATH,
MUPQ_NAMESPACE, PLATFORM, MUPQ_ITERATIONS, LTO= and AIO=1 (the defaults of benchmarks.py with
-o speed and no --lto). Outputs (images, never committed) go to OUT_DIR/<platform>/ outside the
repository. A JSON record of every command, the toolchain version and arm-none-eabi-size output is
written beside the images; make_build_log.py turns it into build_log.md and image_sizes.csv.

Usage:
  python3 build_b0.py --platform nucleo-l4r5zi [--optional] [--pqm4 DIR] [--out DIR]
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kit_config as K  # noqa: E402


def run(cmd, cwd, log, check=True):
    """Run a command, append it with its return code to the log list."""
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    log.append({"cwd": cwd, "cmd": cmd, "rc": p.returncode,
                "stderr_tail": p.stderr[-800:] if p.returncode else ""})
    if check and p.returncode != 0:
        sys.stderr.write(p.stdout[-3000:] + p.stderr[-3000:])
        raise SystemExit(f"command failed: {' '.join(cmd)}")
    return p


def parse_size(text):
    """Parse the Berkeley format output of arm-none-eabi-size for one file."""
    lines = [ln for ln in text.strip().splitlines() if ln.strip()]
    if len(lines) < 2:
        raise ValueError("unexpected size output")
    f = lines[1].split()
    return {"text": int(f[0]), "data": int(f[1]), "bss": int(f[2]), "dec": int(f[3])}


def make_args(platform, impl_path, namespace, iterations):
    args = ["make", f"IMPLEMENTATION_PATH={impl_path}"]
    if namespace:
        args.append(f"MUPQ_NAMESPACE={namespace}")
    args += [f"PLATFORM={platform}", f"MUPQ_ITERATIONS={iterations}", "LTO=", "AIO=1"]
    return args


def check_pin(pqm4, log):
    head = run(["git", "rev-parse", "HEAD"], pqm4, log).stdout.strip()
    if head != K.PQM4_COMMIT:
        raise SystemExit(f"pqm4 HEAD {head} differs from pin {K.PQM4_COMMIT}")
    subs = {}
    for line in run(["git", "submodule", "status", "--recursive"], pqm4, log).stdout.splitlines():
        parts = line.strip().lstrip("+-U").split()
        subs[parts[1]] = parts[0]
    for path, want in K.PQM4_SUBMODULES.items():
        if subs.get(path) != want:
            raise SystemExit(f"submodule {path} is {subs.get(path)}, pin is {want}")
    return head, subs


def build(platform, pqm4, out, optional=False):
    log = []
    head, subs = check_pin(pqm4, log)
    dest = os.path.join(out, platform, "b0")
    os.makedirs(dest, exist_ok=True)
    variants = K.B0_VARIANTS + (K.B0_OPTIONAL if optional else [])
    images = []
    by_iters = {}
    for v in variants:
        by_iters.setdefault(K.ITERATIONS[v[0]], []).append(v)
    for iters, group in sorted(by_iters.items()):
        # MUPQ_ITERATIONS and PLATFORM are retained make variables: start from an empty object tree
        # (pqm4 'make clean' minus libclean, so libopencm3 is not rebuilt each time).
        for d in ("obj", "elf", "bin", "bin-host"):
            shutil.rmtree(os.path.join(pqm4, d), ignore_errors=True)
        log.append({"cwd": pqm4, "cmd": ["rm", "-rf", "obj", "elf", "bin", "bin-host"], "rc": 0,
                    "stderr_tail": ""})
        for scheme, variant, path, ns in group:
            for kind in K.B0_KINDS:
                tgt = K.target_name(path, kind, platform)
                run(make_args(platform, path, ns, iters) + [tgt], pqm4, log)
                elf = K.elf_name(path, kind)
                size = parse_size(run(["arm-none-eabi-size", elf], pqm4, log).stdout)
                for f in (elf, tgt):
                    shutil.copy2(os.path.join(pqm4, f), os.path.join(dest, os.path.basename(f)))
                images.append({"experiment": "B0", "platform": platform, "scheme": scheme,
                               "variant": variant, "kind": kind, "iterations": iters,
                               "elf": os.path.basename(elf), "image": os.path.basename(tgt), **size})
    gcc = run(["arm-none-eabi-gcc", "--version"], pqm4, log).stdout.splitlines()[0]
    rec = {"experiment": "B0", "platform": platform, "pqm4_commit": head, "submodules": subs,
           "toolchain": gcc, "images": images, "commands": log, "out_dir": dest}
    with open(os.path.join(dest, "build_record.json"), "w") as fh:
        json.dump(rec, fh, indent=1)
    return rec


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--platform", choices=K.PLATFORMS, required=True)
    ap.add_argument("--pqm4", default=K.PQM4_DIR)
    ap.add_argument("--out", default=K.OUT_DIR)
    ap.add_argument("--optional", action="store_true", help="also build the m4fstack variants")
    a = ap.parse_args(argv)
    rec = build(a.platform, a.pqm4, a.out, a.optional)
    for im in rec["images"]:
        print(im["image"], im["text"], im["data"], im["bss"])
    print("record:", os.path.join(rec["out_dir"], "build_record.json"))


if __name__ == "__main__":
    main()
