"""Trace every built image and write cyclemodel/results/traces.csv (one row per operation execution).

Label: emulated (instruction class counts from functional emulation of the images built by
cyclemodel/build_images.sh; no timing). Inputs are deterministic: pqm4 on mps2-an386 uses its fixed
seed surf generator (common/randombytes.c), and the harness uses its fixed xorshift32 state.
"""
import csv
import hashlib
import multiprocessing
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cyclemodel.tracer import CLASSES, NON_INSN, Tracer  # noqa: E402

WORK = os.environ.get('CM_WORK', '/home/claude/work')
PQM4_ELF = os.path.join(WORK, 'pqm4_cm', 'elf')
HARNESS_ELF = os.path.join(WORK, 'harness_build', 'arm')
EXT_ELF = os.path.join(WORK, 'ext_build')
RES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results')
OUT = os.path.join(RES, 'traces.csv')
OUT_EXT = os.path.join(RES, 'traces_external.csv')


def pqm4_images():
    out = []
    for p in (512, 768, 1024):
        for impl in ('clean', 'm4fspeed', 'm4fstack'):
            if impl == 'clean':
                f = f'mupq_pqclean_crypto_kem_ml-kem-{p}_clean_speed.elf'
                pre = f'PQCLEAN_MLKEM{p}_CLEAN_'
            else:
                f = f'crypto_kem_ml-kem-{p}_{impl}_speed.elf'
                pre = ''
            out.append(dict(source='pqm4', parameter_set=f'ML-KEM-{p}', implementation=impl, elf=os.path.join(PQM4_ELF, f),
                            targets={'keygen': pre + 'crypto_kem_keypair', 'encaps': pre + 'crypto_kem_enc',
                                     'decaps': pre + 'crypto_kem_dec'}))
    for p in (44, 65, 87):
        for impl in ('clean', 'm4f', 'm4fstack'):
            if impl == 'clean':
                f = f'mupq_pqclean_crypto_sign_ml-dsa-{p}_clean_speed.elf'
                pre = f'PQCLEAN_MLDSA{p}_CLEAN_'
            else:
                f = f'crypto_sign_ml-dsa-{p}_{impl}_speed.elf'
                pre = ''
            out.append(dict(source='pqm4', parameter_set=f'ML-DSA-{p}', implementation=impl, elf=os.path.join(PQM4_ELF, f),
                            targets={'keygen': pre + 'crypto_sign_keypair', 'sign': pre + 'crypto_sign_ctx',
                                     'verify': pre + 'crypto_sign_open_ctx'}))
    return out


def harness_images():
    out = []
    for p in (512, 768, 1024):
        out.append(dict(source='bench_mcu_harness', parameter_set=f'ML-KEM-{p}', implementation='mlkem-native v2.0.0 -O2',
                        elf=os.path.join(HARNESS_ELF, f'mlkem_{p}.elf'),
                        targets={'keygen': 'mlkem_keypair_derand', 'encaps': 'mlkem_enc_derand', 'decaps': 'mlkem_dec'}))
    for p in (44, 65, 87):
        out.append(dict(source='bench_mcu_harness', parameter_set=f'ML-DSA-{p}', implementation='mldsa-native v2.0.0 -O2',
                        elf=os.path.join(HARNESS_ELF, f'mldsa_{p}.elf'),
                        targets={'keygen': 'mldsa_keypair', 'sign': 'mldsa_signature', 'verify': 'mldsa_verify'}))
    return out


def external_images():
    """pqcrystals lowram ML-DSA (dilithium-lowram, tag crypto-benchmark-0.0.16), the library named
    pqcrystals-lowram in ePrint 2026/1333, built for Cortex-M4 here (the paper ran it on a Cortex-M33)."""
    out = []
    for p, mode in ((44, 2), (87, 5)):
        out.append(dict(source='external_check_2026_1333', parameter_set=f'ML-DSA-{p}', implementation='pqcrystals-lowram -Ofast',
                        elf=os.path.join(EXT_ELF, f'lowram_keyexp_{p}.elf'),
                        targets={'keygen': f'pqcrystals_dilithium{mode}_lowram_keypair_from_seed'}))
    return out


def trace_image(img):
    t = Tracer(img['elf'], img['targets'])
    windows = t.run()
    sha = hashlib.sha256(open(img['elf'], 'rb').read()).hexdigest()[:16]
    rows, seen = [], {}
    for (op, vec), hn in zip(windows, t.hash_counts):
        k = seen.get(op, 0)
        seen[op] = k + 1
        r = dict(label='emulated', source=img['source'], parameter_set=img['parameter_set'],
                 implementation=img['implementation'], operation=op, iteration=k,
                 elf=os.path.basename(img['elf']), elf_sha256_16=sha, stop_reason=t.stop_reason,
                 instructions=sum(v for c, v in zip(CLASSES, vec) if c not in NON_INSN))
        r['keccak_instructions'] = hn
        r.update(dict(zip(CLASSES, vec)))
        rows.append(r)
    return rows


def write(rows, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print('wrote', path, len(rows), 'rows')


def main(groups=('main', 'external')):
    if 'external' in groups:
        rows = []
        for img in external_images():
            rows.extend(trace_image(img))
        write(rows, OUT_EXT)
    if 'main' not in groups:
        return
    imgs = pqm4_images() + harness_images()
    # Largest images first so that the two worker processes finish at about the same time
    imgs.sort(key=lambda i: -os.path.getsize(i['elf']) if 'sign' in i['targets'] else 0)
    with multiprocessing.Pool(int(os.environ.get('CM_PROCS', '2'))) as pool:
        results = pool.map(trace_image, imgs, chunksize=1)
    rows = []
    for img, r in zip(imgs, results):
        print(img['source'], img['parameter_set'], img['implementation'], len(r), 'windows', flush=True)
        rows.extend(r)
    rows.sort(key=lambda r: (r['source'], r['parameter_set'], r['implementation'], r['operation'], r['iteration']))
    write(rows, OUT)


if __name__ == '__main__':
    main(tuple(sys.argv[1:]) or ('main', 'external'))
