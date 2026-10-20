"""Tracer self checks written to cyclemodel/results/tracer_validation.csv (label: emulated).

1. Hand check: the hand assembled sum of squares function (see tests/test_tracer.py) with counts
   derived by hand.
2. Block versus instruction hook: for one real image (pqm4 ML-KEM-512 m4fspeed), the instruction total
   from block level class vectors must agree with a count from a per instruction hook in every window,
   within a relative tolerance of 1e-3.
3. The remaining differences are located: every address where the two counts differ lies inside an IT
   block (condition failed instructions, which the block count includes by assumption).
"""
import csv
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cyclemodel.tracer import CLASSES, NON_INSN, Tracer, run_function  # noqa: E402
from cyclemodel.trace_all import PQM4_ELF  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results', 'tracer_validation.csv')
TOL = 1e-3  # differences come from IT predicated instructions with a failed condition (check 3)
SUMSQ = bytes.fromhex('10b5002250f8043b03fb03220139f9d1104610bd')


def hand_check():
    r0, vec = run_function(SUMSQ, (0x20000000, 3), data=struct.pack('<3I', 2, 3, 4))
    got = dict(zip(CLASSES, vec))
    exp = dict.fromkeys(CLASSES, 0)
    exp.update(stm_insn=1, stm_regs=2, alu=5, load=3, mac=3, branch_cond_taken=2, branch_cond_not_taken=1,
               ldm_insn=1, ldm_regs=2, pc_write=1)
    return r0 == 29 and got == exp, f'r0={r0}; counts match hand derivation: {got == exp}'


def block_vs_code_check(elf=None):
    elf = elf or os.path.join(PQM4_ELF, 'crypto_kem_ml-kem-512_m4fspeed_speed.elf')
    t = Tracer(elf, {'keygen': 'crypto_kem_keypair', 'encaps': 'crypto_kem_enc', 'decaps': 'crypto_kem_dec'},
               code_check=True)
    w = t.run()
    rows = []
    for (op, vec), n_code in zip(w, t.code_counts):
        n_block = sum(v for c, v in zip(CLASSES, vec) if c not in NON_INSN)
        rows.append((op, n_block, n_code))
    return rows


def it_mismatch_check(elf=None, sym='crypto_kem_enc'):
    """Per address comparison for one window. Unicorn does not call the per instruction hook for an
    IT predicated instruction whose condition fails, while the block count includes it (the model
    assumption: such an instruction still occupies an issue slot). Returns (all mismatching addresses
    lie inside an IT block, number of mismatching addresses, block minus hook total)."""
    import capstone
    import unicorn
    from collections import Counter
    from unicorn import arm_const as uca
    elf = elf or os.path.join(PQM4_ELF, 'crypto_kem_ml-kem-512_m4fspeed_speed.elf')
    t = Tracer(elf, {'x': sym})
    uc = t.uc
    entry = t.elf.symbols[sym]
    cs = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB | capstone.CS_MODE_MCLASS)
    blk, code, st = Counter(), Counter(), {'on': False, 'ret': None}

    def hb(u, a, s, _):
        if a == entry and not st['on']:
            st['on'], st['ret'] = True, u.reg_read(uca.UC_ARM_REG_LR) & ~1
        elif st['on'] and a == st['ret']:
            st['on'] = False
            u.emu_stop()
        if st['on']:
            for i in cs.disasm(bytes(u.mem_read(a, s)), a):
                blk[i.address] += 1

    def hc(u, a, s, _):
        if st['on']:
            code[a] += 1
    uc.hook_add(unicorn.UC_HOOK_BLOCK, hb)
    uc.hook_add(unicorn.UC_HOOK_CODE, hc)
    uc.reg_write(uca.UC_ARM_REG_SP, struct.unpack('<I', bytes(uc.mem_read(0, 4)))[0])
    try:
        uc.emu_start(struct.unpack('<I', bytes(uc.mem_read(4, 4)))[0] | 1, 0xFFFFFFFF)
    except unicorn.UcError:
        pass
    bad = [a for a in set(blk) | set(code) if blk[a] != code[a]]

    def in_it(a):
        for back in (2, 4, 6, 8, 10, 12):
            ins = next(cs.disasm(bytes(uc.mem_read(a - back, 2)), a - back), None)
            if ins is not None and ins.mnemonic.startswith('it'):
                return True
        return False
    return all(in_it(a) for a in bad), len(bad), sum(blk.values()) - sum(code.values())


def main():
    ok, note = hand_check()
    out = [dict(label='emulated', check='hand derived counts, sum of squares, n=3', passed=ok, detail=note)]
    rows = block_vs_code_check()
    for k, (op, nb, nc) in enumerate(rows[:6]):
        out.append(dict(label='emulated', check=f'block total equals instruction hook total, ML-KEM-512 m4fspeed {op}, run {k // 3 + 1}',
                        passed=abs(nb - nc) <= TOL * nc,
                        detail=f'block={nb}; instruction_hook={nc}; relative difference={(nb - nc) / nc:.2e}; tolerance {TOL:g}'))
    ok_it, nbad, diff = it_mismatch_check()
    out.append(dict(label='emulated', check='every block versus hook difference lies in an IT block (ML-KEM-512 m4fspeed encaps)',
                    passed=ok_it, detail=f'mismatching addresses={nbad}; block minus hook={diff}; '
                    'Unicorn skips the instruction hook for IT predicated instructions whose condition fails'))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', newline='') as f:
        wr = csv.DictWriter(f, fieldnames=['label', 'check', 'passed', 'detail'])
        wr.writeheader()
        wr.writerows(out)
    print(out)


if __name__ == '__main__':
    main()
