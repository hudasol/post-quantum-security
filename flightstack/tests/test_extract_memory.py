"""Tests of flightstack/extract_memory.py and of the committed memory files.

Author: Huda Mueen
"""

import csv
import os
import tempfile
import unittest

from flightstack import extract_memory as em

ROOT = em.ROOT

OBJDUMP = """
Sections:
Idx Name          Size      VMA       LMA       File off  Algn
  0 .vectors      00000400  08020000  08020000  00010000  2**7
                  CONTENTS, ALLOC, LOAD, READONLY, CODE
  1 .text         00010000  08020400  08020400  00010400  2**4
                  CONTENTS, ALLOC, LOAD, READONLY, CODE
  2 .data         00000200  24000000  08030400  00030000  2**2
                  CONTENTS, ALLOC, LOAD, DATA
  3 .bss          00001000  24000200  08030600  00030200  2**2
                  ALLOC
  4 .main_stack   00000800  20000000  20000000  00000000  2**3
                  ALLOC
  5 .ramfunc      00000100  00000000  08030600  00040000  2**2
                  CONTENTS, ALLOC, LOAD, CODE
  6 .heap         00004000  24001200  08030700  00000000  2**0
                  ALLOC
  7 .crash_log    00002000  081f0000  081f0000  00000000  2**0
                  ALLOC
  8 .debug_info   00100000  00000000  00000000  00050000  2**0
                  CONTENTS, READONLY, DEBUGGING
"""

PX4_BLOCK = """MEMORY
{
	ITCM_RAM  (rwx) : ORIGIN = 0x00000000, LENGTH =   64K
	FLASH      (rx) : ORIGIN = 0x08020000, LENGTH = 1920K
	DTCM1_RAM (rwx) : ORIGIN = 0x20000000, LENGTH =   64K
	AXI_SRAM  (rwx) : ORIGIN = 0x24000000, LENGTH =  512K /* D1 domain AXI bus */
	BKPRAM    (rwx) : ORIGIN = 0x38800000, LENGTH =    4K
}
"""

AP_BLOCK = """/* generated ldscript.ld */
MEMORY
{
    flash : org = 0x08010000, len = 960K
    ram0  : org = 0x20000000, len = 131072
}
"""
AP_HAL = "#define HAL_MEMORY_REGIONS {(void*)0x20000000, 0x00020000, 0x01 }, {(void*)0x10000000, 0x00010000, 0x02 }\n"


class TestParsers(unittest.TestCase):
    def test_memory_block_px4(self):
        r = dict((n, (o, ln)) for n, o, ln in em.parse_memory_block(PX4_BLOCK))
        self.assertEqual(r["FLASH"], (0x08020000, 1920 * 1024))
        self.assertEqual(r["AXI_SRAM"], (0x24000000, 512 * 1024))
        self.assertEqual(len(r), 5)

    def test_memory_block_ardupilot(self):
        r = dict((n, (o, ln)) for n, o, ln in em.parse_memory_block(AP_BLOCK))
        self.assertEqual(r["flash"], (0x08010000, 960 * 1024))
        self.assertEqual(r["ram0"], (0x20000000, 131072))

    def test_objdump(self):
        s = em.parse_objdump(OBJDUMP)
        self.assertEqual(len(s), 9)
        self.assertEqual(s[2][0], ".data")
        self.assertIn("LOAD", s[2][4])
        self.assertNotIn("LOAD", s[3][4])

    def test_hal_regions(self):
        self.assertEqual(em.parse_hal_regions(AP_HAL), [(0x20000000, 0x20000, 1), (0x10000000, 0x10000, 2)])


class TestAnalyse(unittest.TestCase):
    def test_px4_accounting(self):
        summary, rows = em.analyse("px4", em.parse_memory_block(PX4_BLOCK), em.parse_objdump(OBJDUMP))
        # flash: vectors, text, data load image, ramfunc load image; bss and stacks are not loaded
        self.assertEqual(summary["flash_used_bytes"], 0x400 + 0x10000 + 0x200 + 0x100)
        self.assertEqual(summary["flash_capacity_bytes"], 1920 * 1024)
        self.assertEqual(summary["ram_data_bss_bytes"], 0x200 + 0x1000)
        self.assertEqual(summary["ram_reserved_stack_bytes"], 0x800)
        # the heap section is the allocator pool, not static use; the crash log area is reserved flash
        self.assertEqual(summary["flash_reserved_bytes"], 0)
        self.assertEqual(summary["flash_crash_log_bytes"], 0x2000)
        self.assertEqual(summary["flash_free_bytes"], 1920 * 1024 - summary["flash_used_bytes"])
        self.assertEqual(summary["itcm_used_bytes"], 0x100)
        # capacity excludes ITCM and backup RAM
        self.assertEqual(summary["ram_capacity_bytes"], (64 + 512) * 1024)
        self.assertEqual(summary["ram_free_static_bytes"], (64 + 512) * 1024 - 0x1200 - 0x800)
        self.assertAlmostEqual(summary["flash_free_share"] + summary["flash_used_bytes"] / (1920 * 1024), 1.0)
        counted = {r["region"]: r["counted_in_capacity"] for r in rows}
        self.assertEqual(counted["ITCM_RAM"], "no")
        self.assertEqual(counted["BKPRAM"], "no")
        self.assertEqual(counted["AXI_SRAM"], "yes")

    def test_ardupilot_capacity_from_allocator_regions(self):
        sections = [(".data", 0x100, 0x20000000, 0x08010000, {"ALLOC", "LOAD", "CONTENTS"}),
                    (".bss", 0x900, 0x20000100, 0x08010100, {"ALLOC"}),
                    (".text", 0x1000, 0x08010200, 0x08010200, {"ALLOC", "LOAD", "CODE"})]
        summary, rows = em.analyse("ardupilot", em.parse_memory_block(AP_BLOCK), sections,
                                   em.parse_hal_regions(AP_HAL))
        self.assertEqual(summary["ram_capacity_bytes"], 0x30000)
        self.assertEqual(summary["ram_static_used_bytes"], 0xA00)
        self.assertEqual(summary["flash_used_bytes"], 0x1100)
        self.assertTrue(any(r["region"].startswith("allocator region 0x10000000") for r in rows))


class TestBuildRows(unittest.TestCase):
    def test_failed_and_missing(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "px4_t1"))
            with open(os.path.join(d, "px4_t1", "build_status.txt"), "w") as fh:
                fh.write("exit_code=2\ncommit=abc\n")
            mapping = [{"stack": "px4", "target": "t1", "board": "B", "flash_capacity_source": "x",
                        "ram_capacity_source": "y", "source_repo": "z", "failure_note": ""},
                       {"stack": "px4", "target": "t2", "board": "C", "flash_capacity_source": "x",
                        "ram_capacity_source": "y", "source_repo": "z", "failure_note": ""}]
            pins = {"PX4-Autopilot": {"version": "v0"}, "ArduPilot": {"version": "a0"}}
            rows, regions = em.build_rows(d, mapping, pins)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["build_status"], "failed")
            self.assertIn("exit code 2", rows[0]["failure_reason"])
            self.assertEqual(regions, [])


class TestCommittedFiles(unittest.TestCase):
    """The committed result regenerates from the committed raw artefacts."""

    def test_regenerates(self):
        if not os.path.exists(em.OUT):
            self.skipTest("no committed memory file")
        rows, _ = em.build_rows()
        with open(em.OUT, newline="", encoding="utf-8") as fh:
            committed = list(csv.DictReader(fh))
        self.assertEqual(len(rows), len(committed))
        for a, b in zip(rows, committed):
            self.assertEqual(a["target"], b["target"])
            if a["build_status"] == "built":
                self.assertEqual(str(a["flash_used_bytes"]), b["flash_used_bytes"])
                self.assertEqual(str(a["ram_static_used_bytes"]), b["ram_static_used_bytes"])

    def test_labels_and_boards(self):
        if not os.path.exists(em.OUT):
            self.skipTest("no committed memory file")
        with open(os.path.join(ROOT, "data", "reference_profiles.csv"), newline="", encoding="utf-8") as fh:
            boards = {r["board"] for r in csv.DictReader(fh)}
        with open(em.OUT, newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        for r in rows:
            self.assertEqual(r["label"], "host measured")
            self.assertIn(r["board"], boards)
            if r["build_status"] == "built":
                self.assertLess(int(r["flash_used_bytes"]), int(r["flash_capacity_bytes"]))
                self.assertTrue(r["flash_capacity_source"] and r["ram_capacity_source"])
                self.assertRegex(r["commit"], "^[0-9a-f]{40}$")

    def test_flash_matches_linker_report(self):
        """Independent check: the linker's own memory usage report (PX4 prints it) gives the same flash use."""
        import re
        if not os.path.exists(em.OUT):
            self.skipTest("no committed memory file")
        with open(em.OUT, newline="", encoding="utf-8") as fh:
            rows = [r for r in csv.DictReader(fh) if r["build_status"] == "built"]
        checked = 0
        for r in rows:
            path = os.path.join(em.RAW, "%s_%s" % (r["stack"], r["target"]), "memory_usage_lines.txt")
            if not os.path.exists(path):
                continue
            with open(path, encoding="utf-8") as fh:
                for line in fh:
                    m = re.match(r"\s*FLASH\w*:\s+([0-9.]+)\s+(B|KB|MB)\s", line)
                    if m and float(m.group(1)) > 0:
                        mult = {"B": 1, "KB": 1024, "MB": 1024 * 1024}[m.group(2)]
                        self.assertLessEqual(abs(float(m.group(1)) * mult - int(r["flash_used_bytes"])), mult)
                        checked += 1
        if not checked:
            self.skipTest("no linker memory report among the builds")

    def test_flightlog_access_record(self):
        with open(os.path.join(ROOT, "flightstack", "flightlog_access.csv"), newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        self.assertTrue(rows)
        for r in rows:
            self.assertTrue(r["url"].startswith("https://"))
            self.assertTrue(r["decision"])


if __name__ == "__main__":
    unittest.main()
