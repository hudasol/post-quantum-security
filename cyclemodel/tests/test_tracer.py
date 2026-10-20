"""Unit tests for the instruction class tracer, including the hand validated function."""
import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import capstone  # noqa: E402
from cyclemodel import tracer  # noqa: E402
from cyclemodel.tracer import CLASSES, IDX, classify, run_function  # noqa: E402

# Hand assembled with arm-none-eabi-as -mcpu=cortex-m4 -mthumb:
#   push {r4, lr}; movs r2, #0
# 1: ldr r3, [r0], #4; mla r2, r3, r3, r2; subs r1, #1; bne 1b
#   mov r0, r2; pop {r4, pc}
SUMSQ = bytes.fromhex('10b5002250f8043b03fb03220139f9d1104610bd')


def _cs():
    return capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB | capstone.CS_MODE_MCLASS)


class HandValidation(unittest.TestCase):
    def test_sum_of_squares_counts(self):
        """Expected counts derived by hand for n = 3 loop iterations."""
        data = struct.pack('<3I', 2, 3, 4)
        r0, vec = run_function(SUMSQ, (0x20000000, 3), data=data)
        self.assertEqual(r0, 4 + 9 + 16)
        got = dict(zip(CLASSES, vec))
        expected = dict.fromkeys(CLASSES, 0)
        expected.update(stm_insn=1, stm_regs=2, alu=1 + 3 + 1, load=3, mac=3, branch_cond_taken=2,
                        branch_cond_not_taken=1, ldm_insn=1, ldm_regs=2, pc_write=1)
        self.assertEqual(got, expected)

    def test_one_iteration(self):
        r0, vec = run_function(SUMSQ, (0x20000000, 1), data=struct.pack('<I', 7))
        self.assertEqual(r0, 49)
        self.assertEqual(vec[IDX['branch_cond_taken']], 0)
        self.assertEqual(vec[IDX['branch_cond_not_taken']], 1)


class Classify(unittest.TestCase):
    def one(self, hexcode):
        return classify(next(_cs().disasm(bytes.fromhex(hexcode), 0)))

    def test_classes(self):
        self.assertEqual(self.one('0022')[0], 'alu')            # movs r2, r4 (lsls)
        self.assertEqual(self.one('03fb0322')[0], 'mac')        # mla
        self.assertEqual(self.one('f9d1')[0], 'branch_cond')    # bne
        self.assertEqual(self.one('10bd'), ('ldm', 2, False, True))  # pop {r4, pc}
        self.assertEqual(self.one('10b5'), ('stm', 2, False, False))  # push {r4, lr}
        self.assertEqual(self.one('4ff0000c')[0], 'alu')        # mov.w ip, #0
        self.assertEqual(self.one('91fbf2f0')[0], 'div')        # sdiv r0, r1, r2

    def test_register_ranges(self):
        # push {r4-r11, lr} : 9 registers
        self.assertEqual(self.one('2de9f04f')[:2], ('stm', 9))


class ElfReader(unittest.TestCase):
    def test_rejects_non_elf(self):
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_not_elf.bin')
        with open(p, 'wb') as f:
            f.write(b'abcd' * 8)
        try:
            with self.assertRaises(ValueError):
                tracer.ElfImage(p)
        finally:
            os.remove(p)


if __name__ == '__main__':
    unittest.main()
