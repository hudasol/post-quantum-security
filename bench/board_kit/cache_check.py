#!/usr/bin/env python3
"""Static check that a B1 image carries the caches off register writes (or does not).

Author: Huda Mueen. Board support only. The check reads the image with the free binutils
(arm-none-eabi-nm and arm-none-eabi-objdump) and needs no board:
  1. the compile time flag symbol bench_cache_off_compiled is present in a caches off image and
     absent from a caches on image;
  2. in the disassembly of bench_cache_configure (b1/b1_main.c) a register is loaded with the
     address of the cache control register of the part, its value is cleared with a bic of the
     expected mask, and the result is stored back through that register.
Expected writes per platform (register addresses and bits from the pinned CMSIS headers named in
kit_config.py and b1/b1_main.c):
  nucleo-l4r5zi    FLASH_ACR 0x40022000, clear PRFTEN, ICEN, DCEN (bits 8, 9, 10: mask 0x700)
  nucleo-l552ze-q  ICACHE_CR 0x40030400, clear EN (bit 0: mask 0x1)
Usage: python3 cache_check.py <elf> --platform <platform> --expect off|on
"""
import argparse
import re
import subprocess
import sys

HERE_FLAG = "bench_cache_off_compiled"
EXPECTED = {"nucleo-l4r5zi": (0x40022000, 0x700), "nucleo-l552ze-q": (0x40030400, 0x1)}

LDR_LIT = re.compile(r"\bldr(?:\.w)?\s+(r\d+|ip|lr), \[pc, #-?\d+\]\s+@ \(([0-9a-f]+) ")
WORD = re.compile(r"^\s*([0-9a-f]+):\s+([0-9a-f]{8})\s+\.word\s+0x([0-9a-f]+)")
BIC = re.compile(r"\bbic(?:s)?(?:\.w)?\s+(r\d+), (r\d+), #(\d+)")
STR = re.compile(r"\bstr(?:\.w)?\s+(r\d+), \[(r\d+)(?:, #0)?\]")


def symbols(elf):
    out = subprocess.run(["arm-none-eabi-nm", elf], capture_output=True, text=True, check=True)
    return {ln.split()[-1] for ln in out.stdout.splitlines() if ln.strip()}


def disassemble(elf, func="bench_cache_configure"):
    out = subprocess.run(["arm-none-eabi-objdump", "-d", f"--disassemble={func}", elf],
                         capture_output=True, text=True, check=True)
    return out.stdout


def find_clear_writes(text):
    """Return a list of (address, mask) for every load, bic, store sequence in the disassembly."""
    lines = text.splitlines()
    words = {}
    for ln in lines:
        m = WORD.match(ln)
        if m:
            words[int(m.group(1), 16)] = int(m.group(3), 16)
    regs = {}
    pending = {}  # register holding a cleared value -> mask
    found = []
    for ln in lines:
        m = LDR_LIT.search(ln)
        if m:
            regs[m.group(1)] = words.get(int(m.group(2), 16))
            pending.pop(m.group(1), None)
            continue
        m = BIC.search(ln)
        if m:
            pending[m.group(1)] = int(m.group(3))
            continue
        m = STR.search(ln)
        if m and m.group(1) in pending and regs.get(m.group(2)) is not None:
            found.append((regs[m.group(2)], pending.pop(m.group(1))))
    return found


def check(elf, platform, expect):
    """Return (ok, details). expect is 'off' (writes required) or 'on' (writes absent)."""
    addr, mask = EXPECTED[platform]
    has_flag = HERE_FLAG in symbols(elf)
    writes = find_clear_writes(disassemble(elf))
    clears = any(a == addr and (m & mask) == mask for a, m in writes)
    if expect == "off":
        ok = has_flag and clears
    else:
        ok = (not has_flag) and not clears
    return ok, {"flag_symbol": has_flag, "clear_writes": [(hex(a), hex(m)) for a, m in writes],
                "expected": (hex(addr), hex(mask))}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("elf")
    ap.add_argument("--platform", choices=sorted(EXPECTED), required=True)
    ap.add_argument("--expect", choices=("off", "on"), required=True)
    a = ap.parse_args(argv)
    ok, d = check(a.elf, a.platform, a.expect)
    print(("PASS" if ok else "FAIL"), a.elf, d)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
