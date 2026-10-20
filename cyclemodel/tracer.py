"""Trace driven instruction class counter for Cortex-M4 ELF images (Unicorn plus Capstone).

Label of every output: emulated (instruction counts from functional emulation, not cycles).

How it works
* The ELF loadable segments are copied into Unicorn memory laid out like the QEMU mps2-an386 machine:
  code and read only data in SSRAM1 at 0x00000000, data in SSRAM2/3 at 0x20000000, peripheral space
  0x40000000 to 0x400FFFFF mapped as plain RAM (reads return zero unless written), the system control
  space 0xE0000000 to 0xE00FFFFF mapped as plain RAM. A UART status register that reads zero means
  "not full", so console output loops never stall. SysTick and DWT read zero, so timer reads inside the
  images return constants; nothing is timed by the emulator.
* Semihosting (BKPT 0xAB) and every other exception stop the run.
* The whole image runs from its reset vector. A basic block hook counts how often each translated
  block runs inside a measurement window. A window opens when a block starts at the entry address of a
  target function and closes when execution reaches the return address held in LR at entry with the
  stack pointer back at its entry value.
* Each distinct block is decoded once with Capstone and turned into a vector of instruction class
  counts. Conditional branch outcomes are taken from the address of the next block.

Assumptions (stated in docs/CYCLE_MODEL.md): instructions skipped by an IT block still count as
executed; exceptions and interrupts are absent; caches, flash wait states and bus contention are not
modelled at this level.
"""
import struct
from collections import defaultdict

import capstone
from capstone import arm as cs_arm
import unicorn
from unicorn import arm_const as uca

CLASSES = [
    'alu', 'mul', 'mac', 'div', 'load', 'store', 'ldm_insn', 'ldm_regs', 'stm_insn', 'stm_regs',
    'branch_uncond', 'branch_cond_taken', 'branch_cond_not_taken', 'it', 'fpu_move', 'fpu_ldst',
    'fpu_arith', 'other', 'pc_write', 'dual_extra',
]
# Columns that are not instruction counts: register totals and the PC write marker (an LDM, POP, LDR or
# MOV/ADD that writes PC is counted once in its own class and once in pc_write; dual_extra counts the
# second word of LDRD and STRD).
NON_INSN = ('ldm_regs', 'stm_regs', 'pc_write', 'dual_extra')
IDX = {c: i for i, c in enumerate(CLASSES)}

MUL_1 = {'mul', 'muls', 'smulbb', 'smulbt', 'smultb', 'smultt', 'smulwb', 'smulwt', 'smmul', 'smmulr',
         'smuad', 'smuadx', 'smusd', 'smusdx', 'smull', 'umull'}
MAC = {'mla', 'mls', 'smlal', 'umlal', 'umaal', 'smlabb', 'smlabt', 'smlatb', 'smlatt', 'smlawb',
       'smlawt', 'smlad', 'smladx', 'smlsd', 'smlsdx', 'smlald', 'smlaldx', 'smlsld', 'smlsldx',
       'smmla', 'smmlar', 'smmls', 'smmlsr', 'smlalbb', 'smlalbt', 'smlaltb', 'smlaltt', 'usada8'}
DIV = {'sdiv', 'udiv'}
COND_CODES = ('eq', 'ne', 'hs', 'cs', 'lo', 'cc', 'mi', 'pl', 'vs', 'vc', 'hi', 'ls', 'ge', 'lt', 'gt', 'le')


def _strip_width(m):
    for suf in ('.w', '.n'):
        if m.endswith(suf):
            return m[:-2]
    return m


def classify(insn):
    """Return (class name, register count or 0, is_conditional_branch, is_branch) for one Capstone insn."""
    m = _strip_width(insn.mnemonic.lower())
    ops = insn.op_str.lower()
    # Branches first
    if m in ('cbz', 'cbnz'):
        return 'branch_cond', 0, True, True
    if m in ('tbb', 'tbh'):
        return 'branch_uncond', 0, False, True
    if m == 'b' or m in ('bl', 'blx', 'bx'):
        return 'branch_uncond', 0, False, True
    if m.startswith('b') and len(m) == 3 and m[1:] in COND_CODES:
        return 'branch_cond', 0, True, True
    if m.startswith('it'):
        return 'it', 0, False, False
    if m.startswith('v'):
        base = m.split('.')[0]
        if base in ('vldr', 'vstr', 'vldm', 'vstm', 'vldmia', 'vstmia', 'vldmdb', 'vstmdb', 'vpush', 'vpop'):
            return 'fpu_ldst', 0, False, False
        if base in ('vmov', 'vmrs', 'vmsr'):
            return 'fpu_move', 0, False, False
        return 'fpu_arith', 0, False, False
    regs = 0
    if m in ('push', 'pop') or m.startswith('ldm') or m.startswith('stm'):
        inside = ops[ops.find('{') + 1: ops.find('}')] if '{' in ops else ''
        for part in inside.split(','):
            part = part.strip()
            if not part:
                continue
            if '-' in part:
                a, b = part.split('-')
                regs += int(b.strip().lstrip('r')) - int(a.strip().lstrip('r')) + 1
            else:
                regs += 1
        writes_pc = 'pc' in inside
        if m == 'pop' or m.startswith('ldm'):
            return ('ldm', regs, False, writes_pc)
        return ('stm', regs, False, False)
    # strip condition and flag suffixes for the remaining tests
    root = m
    if root in MUL_1 or root.rstrip('s') in MUL_1:
        return 'mul', 0, False, False
    if root in MAC:
        return 'mac', 0, False, False
    if root in DIV:
        return 'div', 0, False, False
    if root.startswith('ldr') or root.startswith('ldrex'):
        writes_pc = ops.startswith('pc')
        if root.startswith('ldrd'):
            return 'load', 2, False, writes_pc
        return 'load', 1, False, writes_pc
    if root.startswith('str'):
        if root.startswith('strd'):
            return 'store', 2, False, False
        return 'store', 1, False, False
    if root in ('nop', 'dmb', 'dsb', 'isb', 'bkpt', 'svc', 'wfi', 'wfe', 'cpsid', 'cpsie', 'mrs', 'msr', 'udf', 'sev', 'yield'):
        return 'other', 0, False, False
    if root.startswith('pld') or root.startswith('pli'):
        return 'other', 0, False, False
    writes_pc = ops.startswith('pc,') and root.startswith(('mov', 'add', 'sub'))
    return 'alu', 0, False, writes_pc


def block_vector(insns):
    """Class count vector for a list of decoded instructions; also returns whether the block ends in a
    conditional branch."""
    v = [0] * len(CLASSES)
    ends_cond = False
    n = len(insns)
    for k, insn in enumerate(insns):
        cls, regs, is_cond, is_branch = classify(insn)
        if cls == 'branch_cond':
            if k == n - 1:
                ends_cond = True
            else:  # should not happen inside a translated block; count as not taken
                v[IDX['branch_cond_not_taken']] += 1
        elif cls == 'ldm':
            v[IDX['ldm_insn']] += 1
            v[IDX['ldm_regs']] += regs
            if is_branch:  # POP or LDM that loads PC: marks a taken branch (pipeline refill)
                v[IDX['pc_write']] += 1
        elif cls == 'stm':
            v[IDX['stm_insn']] += 1
            v[IDX['stm_regs']] += regs
        elif cls in ('load', 'store'):
            v[IDX[cls]] += 1
            v[IDX['dual_extra']] += regs - 1
            if is_branch:  # LDR PC: marks a taken branch
                v[IDX['pc_write']] += 1
        else:
            v[IDX[cls]] += 1
            if cls == 'alu' and is_branch:  # MOV PC or ADD PC: marks a taken branch
                v[IDX['pc_write']] += 1
    return v, ends_cond


class ElfImage:
    """Minimal ELF32 little endian reader: loadable segments, entry point and symbol table."""

    def __init__(self, path):
        with open(path, 'rb') as f:
            self.data = f.read()
        d = self.data
        if d[:4] != b'\x7fELF' or d[4] != 1 or d[5] != 1:
            raise ValueError('not an ELF32 little endian file')
        (self.e_type, self.e_machine, _, self.entry, phoff, shoff, _, _, phentsize, phnum,
         shentsize, shnum, shstrndx) = struct.unpack_from('<HHIIIIIHHHHHH', d, 16)
        self.segments = []
        for i in range(phnum):
            p_type, p_off, p_vaddr, p_paddr, p_filesz, p_memsz, _, _ = struct.unpack_from('<IIIIIIII', d, phoff + i * phentsize)
            if p_type == 1 and p_filesz > 0:
                self.segments.append((p_paddr, d[p_off:p_off + p_filesz]))
        self.symbols = {}
        self.func_ranges = []  # (start, size, name)
        secs = [struct.unpack_from('<IIIIIIIIII', d, shoff + i * shentsize) for i in range(shnum)]
        for s in secs:
            if s[1] == 2:  # SHT_SYMTAB
                strtab = secs[s[6]]
                for j in range(s[5] // 16):
                    name_off, value, size, info, _, _ = struct.unpack_from('<IIIBBH', d, s[4] + j * 16)
                    if info & 0xF != 2:  # STT_FUNC only
                        continue
                    so = strtab[4] + name_off
                    name = d[so:d.index(b'\0', so)].decode()
                    self.symbols[name] = value & ~1
                    self.func_ranges.append((value & ~1, size, name))
        # Assembly functions often carry size 0: use the distance to the next function start instead.
        starts = sorted({a for a, _, _ in self.func_ranges})
        fixed = []
        for a, n, name in self.func_ranges:
            if n == 0:
                nxt = [x for x in starts if x > a]
                n = (nxt[0] - a) if nxt else 0
            fixed.append((a, n, name))
        self.func_ranges = fixed


MAP = [  # (base, size) regions of the mps2-an386 address map used here
    (0x00000000, 0x00400000),   # SSRAM1 (code)
    (0x20000000, 0x00800000),   # SSRAM2/3 (data)
    (0x40000000, 0x00100000),   # APB/AHB peripherals as RAM
    (0xE0000000, 0x00100000),   # system control space as RAM
    (0x00F00000, 0x00001000),   # stop pad for the return trap (inside nothing used by images)
]


class Tracer:
    def __init__(self, elf_path, targets, code_check=False):
        """targets: dict operation name -> function symbol name."""
        self.elf = ElfImage(elf_path)
        self.targets = {}
        for op, sym in targets.items():
            if sym not in self.elf.symbols:
                raise KeyError(f'symbol {sym} not in {elf_path}')
            self.targets[self.elf.symbols[sym]] = op
        self.uc = unicorn.Uc(unicorn.UC_ARCH_ARM, unicorn.UC_MODE_THUMB | unicorn.UC_MODE_MCLASS)
        try:
            self.uc.ctl_set_cpu_model(uca.UC_CPU_ARM_CORTEX_M4)
        except Exception:
            pass
        for base, size in MAP:
            self.uc.mem_map(base, size)
        for addr, blob in self.elf.segments:
            self.uc.mem_write(addr, blob)
        self.cs = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB | capstone.CS_MODE_MCLASS)
        self.cs.detail = False
        self.block_info = {}
        # Address ranges of Keccak functions, used to attribute executed instructions to hashing
        self.hash_ranges = [(a, a + n) for a, n, name in self.elf.func_ranges if 'keccak' in name.lower() and n > 0]
        self.hash_counts = []  # per window instructions executed inside Keccak functions
        self.windows = []  # list of (op, class vector)
        self.stop_reason = None
        self.code_check = code_check
        self.code_counts = []  # per window instruction counts from a per instruction hook (check only)

    def _decode(self, addr, size):
        code = bytes(self.uc.mem_read(addr, size))
        insns = list(self.cs.disasm(code, addr))
        vec, ends_cond = block_vector(insns)
        in_hash = any(lo <= addr < hi for lo, hi in self.hash_ranges)
        return vec, ends_cond, addr + size, len(insns), in_hash

    def run(self, timeout_s=0):
        uc = self.uc
        sp0 = struct.unpack('<I', bytes(uc.mem_read(0, 4)))[0]
        reset = struct.unpack('<I', bytes(uc.mem_read(4, 4)))[0]
        uc.reg_write(uca.UC_ARM_REG_SP, sp0)
        targets = self.targets
        counts = defaultdict(int)
        trans = {'t': 0, 'nt': 0}
        state = {'op': None, 'ret': None, 'sp': None, 'prev': None, 'icount': 0}
        condset = {}
        block_info = self.block_info
        windows = self.windows

        def close_window():
            vec = [0] * len(CLASSES)
            hash_n = 0
            for key, c in counts.items():
                info = block_info[key]
                bv = info[0]
                if info[4]:
                    hash_n += info[3] * c
                for i, x in enumerate(bv):
                    if x:
                        vec[i] += x * c
            vec[IDX['branch_cond_taken']] = trans['t']
            vec[IDX['branch_cond_not_taken']] += trans['nt']
            windows.append((state['op'], vec))
            self.code_counts.append(state['icount'])
            self.hash_counts.append(hash_n)
            state['icount'] = 0
            counts.clear()
            trans['t'] = trans['nt'] = 0
            state['op'] = None

        def hook_block(uc_, addr, size, _ud):
            key = (addr << 12) | size
            prev = state['prev']
            if state['op'] is not None:
                if addr == state['ret'] and uc_.reg_read(uca.UC_ARM_REG_SP) == state['sp']:
                    if prev in condset:
                        if addr == condset[prev]:
                            trans['nt'] += 1
                        else:
                            trans['t'] += 1
                    close_window()
                else:
                    if prev in condset:
                        if addr == condset[prev]:
                            trans['nt'] += 1
                        else:
                            trans['t'] += 1
            if key not in block_info:
                info = self._decode(addr, size)
                block_info[key] = info
                if info[1]:
                    condset[key] = info[2]
            if state['op'] is None and addr in targets:
                state['op'] = targets[addr]
                state['ret'] = uc_.reg_read(uca.UC_ARM_REG_LR) & ~1
                state['sp'] = uc_.reg_read(uca.UC_ARM_REG_SP)
                prev = None
            if state['op'] is not None:
                counts[key] += 1
                state['prev'] = key
            else:
                state['prev'] = None

        def hook_intr(uc_, intno, _ud):
            self.stop_reason = f'exception {intno} at pc 0x{uc_.reg_read(uca.UC_ARM_REG_PC):08x}'
            uc_.emu_stop()

        def hook_code(uc_, addr, size, _ud):
            if state['op'] is not None:
                state['icount'] += 1

        uc.hook_add(unicorn.UC_HOOK_BLOCK, hook_block)
        uc.hook_add(unicorn.UC_HOOK_INTR, hook_intr)
        if self.code_check:
            uc.hook_add(unicorn.UC_HOOK_CODE, hook_code)
        try:
            uc.emu_start(reset | 1, 0xFFFFFFFF, timeout=int(timeout_s * 1e6))
        except unicorn.UcError as e:
            self.stop_reason = f'UcError {e} at pc 0x{uc.reg_read(uca.UC_ARM_REG_PC):08x}'
        return self.windows

def run_function(code_bytes, args, data=b'', base=0x1000, max_steps=100000):
    """Run a raw Thumb code blob as a function with up to four integer arguments, with a block level
    class count. Used by the hand validation test. Returns (r0, class vector)."""
    uc = unicorn.Uc(unicorn.UC_ARCH_ARM, unicorn.UC_MODE_THUMB | unicorn.UC_MODE_MCLASS)
    uc.mem_map(0, 0x10000)
    uc.mem_map(0x20000000, 0x10000)
    uc.mem_write(base, code_bytes)
    if data:
        uc.mem_write(0x20000000, data)
    ret = 0x8000
    uc.mem_write(ret, b'\x00\xbf')  # nop pad
    for r, v in zip((uca.UC_ARM_REG_R0, uca.UC_ARM_REG_R1, uca.UC_ARM_REG_R2, uca.UC_ARM_REG_R3), args):
        uc.reg_write(r, v)
    uc.reg_write(uca.UC_ARM_REG_SP, 0x20008000)
    uc.reg_write(uca.UC_ARM_REG_LR, ret | 1)
    cs = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB | capstone.CS_MODE_MCLASS)
    vec = [0] * len(CLASSES)
    st = {'prev_fall': None}

    def hook_block(uc_, addr, size, _ud):
        if st['prev_fall'] is not None:
            vec[IDX['branch_cond_not_taken' if addr == st['prev_fall'] else 'branch_cond_taken']] += 1
            st['prev_fall'] = None
        if addr == ret:
            uc_.emu_stop()
            return
        insns = list(cs.disasm(bytes(uc_.mem_read(addr, size)), addr))
        bv, ends = block_vector(insns)
        for i, x in enumerate(bv):
            vec[i] += x
        if ends:
            st['prev_fall'] = addr + size

    uc.hook_add(unicorn.UC_HOOK_BLOCK, hook_block)
    uc.emu_start(base | 1, 0xFFFFFFFF, count=max_steps)
    return uc.reg_read(uca.UC_ARM_REG_R0), vec
