#!/usr/bin/env python3
"""Run the nucleo-l552ze-q B1 images (caches on and caches off) in Renode and record whether the
cache register writes reach the bus. Label of every value: emulated.

Author: Huda Mueen. Board support only. Renode (free, MIT licence) is fetched at a pinned release
by fetch_renode.sh, outside the repository; set RENODE_BIN to its renode launcher.
What this shows and what it does not:
  * Renode 1.16.1 ships platforms/cpus/stm32l552.repl (Cortex-M33). That description does not
    model the flash interface (0x40022000) or the ICACHE peripheral (0x40030400); Renode logs every
    access to them as an access to a non existing peripheral, with the program counter and value.
    The log therefore proves that the caches off image executes the store to ICACHE_CR with the
    EN bit cleared, and that the caches on image stores EN set, but no model of the cache acts on
    it, and no timing from Renode is a cycle count (its DWT is a tag that reads 0).
  * No free model of the STM32L4R5 was found: QEMU 8.2 lists no STM32L4 machine and Renode 1.16.1
    has no stm32l4 platform description. The nucleo-l4r5zi images are checked statically only
    (cache_check.py).
Usage: RENODE_BIN=<path to renode> python3 renode_check.py [--seconds 2] [--out <csv>]
"""
import argparse
import csv
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kit_config as K  # noqa: E402
import capture  # noqa: E402
import parse  # noqa: E402

RENODE_VERSION = "1.16.1"
REPL = "platforms/cpus/stm32l552.repl"
ACCESS = re.compile(r"\[cpu: 0x([0-9A-Fa-f]+)\]\s+(?:\(tag: '[^']*'\) )?(ReadDoubleWord|WriteDoubleWord) "
                    r"(?:from|to) non existing peripheral at 0x([0-9A-Fa-f]+)(?:, value 0x([0-9A-Fa-f]+))?")
COLUMNS = ["label", "tool", "platform_description", "image", "cache_pass", "register", "address",
           "writes", "last_write_value", "last_write_pc", "en_bit_after_last_write",
           "uart_cache_pass", "uart_cache_off_applied", "uart_cache_line", "uart_lines_parsed",
           "uart_lines_unrecognised", "note"]
REGS = {0x40030400: "ICACHE_CR", 0x40022000: "FLASH_ACR"}


def parse_log(text):
    """Return {address: [(pc, value), ...]} for writes to the cache related registers."""
    out = {a: [] for a in REGS}
    for m in ACCESS.finditer(text):
        addr = int(m.group(3), 16)
        if addr in out and m.group(2) == "WriteDoubleWord":
            out[addr].append((int(m.group(1), 16), int(m.group(4), 16)))
    return out


def parse_uart(text):
    meta = {}
    for line in text.splitlines():
        f = line.strip().split(",", 2)
        if len(f) == 3 and f[0] == "META":
            meta.setdefault(f[1], f[2])
    return meta


def parse_uart_lines(text, image, workdir):
    """Write the complete UART lines in capture format and parse them with parse.py.

    The run stops after a fixed emulated time, so the last line may be cut; it is dropped."""
    lines = text.split("\n")[:-1]
    path = os.path.join(workdir, image + "_capture.log")
    meta = {"version": "1", "source": f"Renode {RENODE_VERSION} lpuart1 file backend",
            "start_utc": capture.utc_now(), "experiment": "B1", "image": image, "run": 1,
            "label": "emulated", "board": "Renode stm32l552", "note": "renode_check"}
    with open(path, "w") as fh:
        capture.capture_lines([ln + "\n" for ln in lines], fh, meta)
    r = parse.parse_log(path)
    return r["n_lines"], r["n_unrecognised"]


def run_image(renode, elf, seconds, workdir):
    name = os.path.splitext(os.path.basename(elf))[0]
    uart = os.path.join(workdir, name + "_uart.txt")
    log = os.path.join(workdir, name + "_renode.log")
    root = os.path.dirname(os.path.realpath(renode))
    resc = os.path.join(workdir, name + ".resc")
    with open(resc, "w") as fh:
        fh.write(f'mach create "l552"\nmachine LoadPlatformDescription @{os.path.join(root, REPL)}\n'
                 f"sysbus LoadELF @{elf}\nsysbus.lpuart1 CreateFileBackend @{uart} true\n"
                 f"logFile @{log}\nemulation RunFor \"{seconds}\"\nquit\n")
    subprocess.run([renode, "--disable-gui", "--console", "-e", f"include @{resc}"],
                   capture_output=True, text=True, timeout=900)
    with open(log, errors="replace") as fh:
        ltxt = fh.read()
    utxt = open(uart, errors="replace").read() if os.path.exists(uart) else ""
    n, bad = parse_uart_lines(utxt, name, workdir)
    meta = parse_uart(utxt)
    meta["_lines"], meta["_bad"] = n, bad
    return parse_log(ltxt), meta


def rows_for(elf, cache_pass, writes, meta):
    rows = []
    for addr, name in REGS.items():
        w = writes[addr]
        last = w[-1] if w else None
        en = "" if (last is None or name != "ICACHE_CR") else str(last[1] & 1)
        rows.append({"label": "emulated", "tool": f"Renode {RENODE_VERSION}",
                     "platform_description": REPL, "image": os.path.basename(elf),
                     "cache_pass": cache_pass, "register": name, "address": hex(addr),
                     "writes": len(w), "last_write_value": hex(last[1]) if last else "",
                     "last_write_pc": hex(last[0]) if last else "",
                     "en_bit_after_last_write": en,
                     "uart_cache_pass": meta.get("cache_pass", ""),
                     "uart_cache_off_applied": meta.get("cache_off_applied", ""),
                     "uart_cache_line": meta.get("cache", ""),
                     "uart_lines_parsed": meta.get("_lines", ""),
                     "uart_lines_unrecognised": meta.get("_bad", ""),
                     "note": ("register not modelled by the platform description; the write is "
                              "logged on the bus and has no effect in the model, so the read back "
                              "cache line shows the model, not the write") if name == "ICACHE_CR"
                     else ("register not modelled; the image only reads it (latency check before "
                           "the caches off write), so no write is expected")})
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seconds", default="2", help="emulated seconds to run each image")
    ap.add_argument("--set", default="mlkem_512")
    ap.add_argument("--out", default=os.path.join(HERE, "dry_run", "renode_cache_check.csv"))
    a = ap.parse_args(argv)
    renode = os.environ.get("RENODE_BIN", "renode")
    base = os.path.join(K.OUT_DIR, K.M33_PLATFORM, "b1")
    rows = []
    with tempfile.TemporaryDirectory() as d:
        for cp in K.CACHE_PASSES:
            elf = os.path.join(base, f"b1_{a.set}{K.CACHE_SUFFIX[cp]}.elf")
            writes, meta = run_image(renode, elf, a.seconds, d)
            rows += rows_for(elf, cp, writes, meta)
    with open(a.out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    for r in rows:
        print(r["cache_pass"], r["register"], r["writes"], r["last_write_value"],
              r["uart_cache_line"], r["uart_lines_parsed"], r["uart_lines_unrecognised"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
