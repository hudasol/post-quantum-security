"""Flash and static RAM use of flight stack firmware builds, from the small
text artefacts that flightstack/build.sh saves into data/flightstack/raw/.

Author: Huda Mueen.

Run from the repository root:  python3 flightstack/extract_memory.py
Reads, per build folder data/flightstack/raw/<stack>_<target>/:
  build_status.txt   exit code, commit, toolchain, linker script path
  objdump_h.txt      section headers of the ELF (size, VMA, LMA, flags)
  memory_block.ld    MEMORY block of the linker script used by the build
  hwdef_defines.txt  ArduPilot only: HAL_MEMORY_REGIONS and flash defines
and flightstack/targets_map.csv (target to board class and capacity source).
Writes data/flightstack_memory.csv (one row per stack and target) and
data/flightstack_memory_regions.csv (one row per memory region).

Method. Flash used: the sum of the sizes of all sections that are loaded
(LOAD flag) at a load address inside a flash region; this includes the
initial values of .data. Flash capacity: the length of the application flash
region of the linker script (the bootloader and any reserved sectors lie
outside it). Static RAM: sections with the ALLOC flag whose run address lies
inside a RAM region, split into data plus bss and sections the linker
reserves for stacks. A heap section only marks the pool the allocator
manages and is not counted. Flash space the linker reserves without loading
it is counted separately as reserved and is not free. ArduPilot places a
crash log area in the flash that the image leaves unused (its common.ld says
so); that area is reported in its own column and counted as free, because
it shrinks when the image grows. RAM capacity: for PX4, the sum of the RAM
regions of the board linker script except instruction RAM (ITCM) and backup
RAM; for ArduPilot, the sum of HAL_MEMORY_REGIONS, the RAM the ChibiOS port
hands to its allocator, generated from the board hwdef and the MCU table.
The build cannot show heap use, task stacks created at run time, or buffers
allocated at start up, so the free static RAM is an upper bound on the RAM
left for new code.
"""

import csv
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "flightstack", "raw")
MAP = os.path.join(ROOT, "flightstack", "targets_map.csv")
PINS = os.path.join(ROOT, "flightstack", "pins.csv")
OUT = os.path.join(ROOT, "data", "flightstack_memory.csv")
OUT_REGIONS = os.path.join(ROOT, "data", "flightstack_memory_regions.csv")

FIELDS = ["stack", "release", "commit", "target", "board", "build_status", "flash_used_bytes",
          "flash_reserved_bytes", "flash_crash_log_bytes", "flash_capacity_bytes", "flash_capacity_source", "flash_free_bytes", "flash_free_share",
          "ram_data_bss_bytes", "ram_reserved_stack_bytes", "ram_static_used_bytes", "ram_capacity_bytes",
          "ram_capacity_source", "ram_free_static_bytes", "ram_free_share", "itcm_used_bytes", "toolchain",
          "failure_reason", "label"]
REGION_FIELDS = ["stack", "target", "region", "kind", "origin", "length_bytes", "used_bytes", "free_bytes",
                 "counted_in_capacity", "sections", "label"]

REGION_RE = re.compile(r"^\s*(\w+)\s*(?:\([^)]*\))?\s*:\s*(?:ORIGIN|org|o)\s*=\s*(0x[0-9a-fA-F]+|\d+)\s*,\s*"
                       r"(?:LENGTH|len|l)\s*=\s*(0x[0-9a-fA-F]+|\d+)\s*([KM]?)", re.I)
SECTION_RE = re.compile(r"^\s*\d+\s+(\S+)\s+([0-9a-fA-F]{8})\s+([0-9a-fA-F]{8})\s+([0-9a-fA-F]{8})\s+[0-9a-fA-F]{8}\s+2\*\*\d+")
HAL_REGION_RE = re.compile(r"\{\s*\(void\s*\*\)\s*(0x[0-9a-fA-F]+)\s*,\s*(0x[0-9a-fA-F]+)\s*,\s*(0x[0-9a-fA-F]+)\s*\}")


def parse_int(text):
    return int(text, 16) if text.lower().startswith("0x") else int(text)


def parse_memory_block(text):
    """[(name, origin, length)] from a linker script MEMORY block."""
    out = []
    for line in text.splitlines():
        line = line.split("/*")[0]
        m = REGION_RE.match(line)
        if not m:
            continue
        mult = {"": 1, "K": 1024, "M": 1024 * 1024}[m.group(4).upper()]
        out.append((m.group(1), parse_int(m.group(2)), parse_int(m.group(3)) * mult))
    return out


def parse_objdump(text):
    """[(name, size, vma, lma, flags)] from objdump -h output."""
    out = []
    lines = text.splitlines()
    for i, line in enumerate(lines):
        m = SECTION_RE.match(line)
        if not m:
            continue
        flags = lines[i + 1].strip() if i + 1 < len(lines) else ""
        out.append((m.group(1), int(m.group(2), 16), int(m.group(3), 16), int(m.group(4), 16),
                    {f.strip() for f in flags.split(",")}))
    return out


def parse_hal_regions(text):
    """[(origin, length, flags)] from the HAL_MEMORY_REGIONS define of an ArduPilot hwdef.h."""
    for line in text.splitlines():
        if "HAL_MEMORY_REGIONS" in line:
            return [(int(a, 16), int(b, 16), int(c, 16)) for a, b, c in HAL_REGION_RE.findall(line)]
    return []


def read_kv(path):
    out = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if "=" in line:
                k, v = line.rstrip("\n").split("=", 1)
                out[k] = v
    return out


def is_flash(name):
    return "flash" in name.lower()


def is_excluded_ram(name):
    n = name.upper()
    return "ITCM" in n or "BKP" in n


def region_of(addr, regions):
    for name, origin, length in regions:
        if origin <= addr < origin + length:
            return name
    return None


def is_stack(section):
    return "stack" in section.lower()


def is_heap(section):
    return "heap" in section.lower()


def analyse(stack, regions, sections, hal_regions=None):
    """Memory use of one build. regions: linker MEMORY block; sections: objdump rows;
    hal_regions: ArduPilot allocator regions or None. Returns (summary dict, region rows)."""
    flash_regions = [r for r in regions if is_flash(r[0])]
    ram_regions = [r for r in regions if not is_flash(r[0])]
    used = {r[0]: 0 for r in regions}
    names = {r[0]: [] for r in regions}
    flash_used = flash_reserved = crash = 0
    data_bss = reserved = itcm = 0
    for name, size, vma, lma, flags in sections:
        if size == 0 or "ALLOC" not in flags:
            continue
        fv = region_of(vma, flash_regions)
        if fv and "LOAD" not in flags and "crash_log" in name:
            # ArduPilot common.ld: "The crash log uses the unused part of a flash section."
            crash += size
            names[fv].append(name + " (crash log in unused flash, counted as free)")
            continue
        if fv and "LOAD" not in flags:
            # space the linker reserves in flash without loading it (for example a crash log area)
            flash_reserved += size
            used[fv] += size
            names[fv].append(name + " (reserved)")
            continue
        if "LOAD" in flags:
            fr = region_of(lma, flash_regions)
            if fr:
                flash_used += size
                used[fr] += size
                names[fr].append(name)
        rr = region_of(vma, ram_regions)
        if rr:
            if is_heap(name):
                # the heap section marks the free pool the allocator manages; it is not static use
                names[rr].append(name + " (allocator pool, not counted)")
                continue
            used[rr] += size
            names[rr].append(name)
            if "ITCM" in rr.upper():
                itcm += size
            elif is_stack(name):
                reserved += size
            else:
                data_bss += size
    # Flash regions may alias one physical flash (PX4 FMUv5 maps it at an ITCM and an AXIM address).
    flash_capacity = max(length for _, _, length in flash_regions)
    if hal_regions:
        ram_capacity = sum(length for _, length, _ in hal_regions)
        counted = set()
        for name, origin, length in ram_regions:
            if any(origin <= o < origin + length or o <= origin < o + ln for o, ln, _ in hal_regions):
                counted.add(name)
    else:
        counted = {r[0] for r in ram_regions if not is_excluded_ram(r[0])}
        ram_capacity = sum(length for name, _, length in ram_regions if name in counted)
    rows = []
    for name, origin, length in regions:
        kind = "flash" if is_flash(name) else "ram"
        rows.append({"stack": stack, "region": name, "kind": kind, "origin": "0x%08x" % origin,
                     "length_bytes": length, "used_bytes": used[name], "free_bytes": length - used[name],
                     "counted_in_capacity": "yes" if (kind == "flash" or name in counted) else "no",
                     "sections": " ".join(names[name])})
    if hal_regions:
        for origin, length, fl in hal_regions:
            if region_of(origin, ram_regions) is None:
                rows.append({"stack": stack, "region": "allocator region 0x%08x (flags 0x%02x)" % (origin, fl),
                             "kind": "ram", "origin": "0x%08x" % origin, "length_bytes": length, "used_bytes": 0,
                             "free_bytes": length, "counted_in_capacity": "yes", "sections": ""})
    static = data_bss + reserved
    flash_free = flash_capacity - flash_used - flash_reserved
    summary = {"flash_used_bytes": flash_used, "flash_reserved_bytes": flash_reserved,
               "flash_crash_log_bytes": crash,
               "flash_capacity_bytes": flash_capacity, "flash_free_bytes": flash_free,
               "flash_free_share": flash_free / flash_capacity,
               "ram_data_bss_bytes": data_bss, "ram_reserved_stack_bytes": reserved,
               "ram_static_used_bytes": static, "ram_capacity_bytes": ram_capacity,
               "ram_free_static_bytes": ram_capacity - static, "ram_free_share": (ram_capacity - static) / ram_capacity,
               "itcm_used_bytes": itcm}
    return summary, rows


def load_map(path=MAP):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load_pins(path=PINS):
    with open(path, newline="", encoding="utf-8") as fh:
        return {r["component"]: r for r in csv.DictReader(fh)}


def build_rows(raw=RAW, mapping=None, pins=None):
    mapping = mapping if mapping is not None else load_map()
    pins = pins if pins is not None else load_pins()
    rows, region_rows = [], []
    for m in mapping:
        folder = os.path.join(raw, "%s_%s" % (m["stack"], m["target"]))
        status_path = os.path.join(folder, "build_status.txt")
        if not os.path.exists(status_path):
            continue  # not built in this run
        st = read_kv(status_path)
        comp = "PX4-Autopilot" if m["stack"] == "px4" else "ArduPilot"
        base = {"stack": m["stack"], "release": pins[comp]["version"], "commit": st.get("commit", ""),
                "target": m["target"], "board": m["board"], "toolchain": st.get("toolchain", ""),
                "flash_capacity_source": "", "ram_capacity_source": "", "failure_reason": "", "label": "host measured"}
        ok = st.get("exit_code") == "0" and os.path.exists(os.path.join(folder, "objdump_h.txt"))
        if not ok:
            base["build_status"] = "failed"
            base["failure_reason"] = m.get("failure_note") or "build exit code %s; see build_log_tail.txt" % st.get(
                "exit_code")
            rows.append(base)
            continue
        with open(os.path.join(folder, "memory_block.ld"), encoding="utf-8") as fh:
            regions = parse_memory_block(fh.read())
        with open(os.path.join(folder, "objdump_h.txt"), encoding="utf-8") as fh:
            sections = parse_objdump(fh.read())
        hal = None
        hw = os.path.join(folder, "hwdef_defines.txt")
        if m["stack"] == "ardupilot" and os.path.exists(hw):
            with open(hw, encoding="utf-8") as fh:
                hal = parse_hal_regions(fh.read())
        summary, rr = analyse(m["stack"], regions, sections, hal)
        base.update(summary)
        base["build_status"] = "built"
        base["flash_capacity_source"] = "%s at %s (%s)" % (m["flash_capacity_source"], base["commit"][:12],
                                                          m["source_repo"])
        base["ram_capacity_source"] = "%s at %s (%s)" % (m["ram_capacity_source"], base["commit"][:12],
                                                        m["source_repo"])
        rows.append(base)
        for r in rr:
            r["target"] = m["target"]
            r["label"] = "host measured"
            region_rows.append(r)
    return rows, region_rows


def write_csv(path, rows, fields):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: ("%.4f" % r[k] if isinstance(r.get(k), float) else r.get(k, "")) for k in fields})


def main():
    rows, region_rows = build_rows()
    write_csv(OUT, rows, FIELDS)
    write_csv(OUT_REGIONS, region_rows, REGION_FIELDS)
    built = [r for r in rows if r["build_status"] == "built"]
    print("%d builds, %d with measured memory, %d board classes" % (len(rows), len(built),
                                                                     len({r["board"] for r in built})))
    return 0


if __name__ == "__main__":
    sys.exit(main())
