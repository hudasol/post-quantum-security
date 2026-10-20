"""Regenerate every cycle model result file, figure and docs/CYCLE_MODEL.md.

Steps: build images outside the repository (cyclemodel/build_images.sh), trace them, run the tracer
checks, fit and validate the models, draw the figures, write the configuration record and the document.
Option --reuse-traces skips building and tracing when results/traces.csv and traces_external.csv exist.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from cyclemodel import analyse, figures, make_doc, trace_all, validate_tracer  # noqa: E402
from cyclemodel import model as M  # noqa: E402

WORK = os.environ.get('CM_WORK', '/home/claude/work')


def tool_version(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout.splitlines()[0].strip()
    except Exception as e:  # pragma: no cover
        return f'unavailable ({e.__class__.__name__})'


def git_head(path):
    try:
        return subprocess.run(['git', '-C', path, 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return 'not present'


def write_config():
    import capstone
    import unicorn
    rows = [
        ('seed', str(M.SEED)),
        ('bootstrap_resamples', str(M.N_BOOT)),
        ('toolchain_used', tool_version(['arm-none-eabi-gcc', '--version'])),
        ('toolchain_published_pqm4', 'arm-none-eabi-gcc 11.3.1 20220712 (Arm GNU Toolchain 11.3.Rel1), per pqm4 README (data/raw/S6_pqm4_config.md)'),
        ('pqm4_commit', git_head(os.path.join(WORK, 'pqm4_cm'))),
        ('pqm4_build', 'PLATFORM=mps2-an386, MUPQ_ITERATIONS=10 for ML-KEM and 50 for ML-DSA, pqm4 default flags (-O3 -g3, -mcpu=cortex-m4 -mfloat-abi=hard -mfpu=fpv4-sp-d16)'),
        ('mlkem_native_commit', git_head(os.path.join(WORK, 'harness_libs', 'mlkem-native'))),
        ('mldsa_native_commit', git_head(os.path.join(WORK, 'harness_libs', 'mldsa-native'))),
        ('harness_build', 'bench/mcu Makefile target arm, ARM_OPT=-O2, ITERS=10, board/qemu link.ld and startup.c'),
        ('dilithium_lowram_commit', git_head(os.path.join(WORK, 'ext_check', 'dilithium-lowram'))),
        ('unicorn_version', unicorn.__version__),
        ('capstone_version', capstone.__version__),
        ('memory_map', 'mps2-an386 layout: 0x00000000 4 MB code, 0x20000000 8 MB data, 0x40000000 and 0xE0000000 1 MB each as RAM reading zero'),
        ('randomness', 'pqm4 mps2 build: fixed seed surf generator in common/randombytes.c (deterministic); harness: fixed xorshift32 state; external: fixed seed bytes'),
        ('licences', 'pqm4: repository code Apache-2.0 or CC0-1.0 per README, PQClean clean implementations public domain (CC0) per their LICENSE files, m4f variants carry no separate LICENSE file; mlkem-native and mldsa-native Apache-2.0 or ISC or MIT per LICENSE; dilithium-lowram CC0 or Apache-2.0 per LICENSE'),
        ('refused_fetch', 'https://developer.arm.com/documentation/100166/0001/Programmers-Model/Instruction-set-summary/Cortex-M4-instructions (2026-10-20, permission not granted in time; not retried)'),
    ]
    # label: configuration record of this run (the published toolchain row is derived from published text)
    M.write_csv(os.path.join(M.RES, 'config.csv'),
                [dict(label='derived from published' if k == 'toolchain_published_pqm4' else 'assumption', key=k, value=v)
                 for k, v in rows])


def main():
    reuse = '--reuse-traces' in sys.argv
    have = all(os.path.exists(os.path.join(M.RES, f)) for f in ('traces.csv', 'traces_external.csv'))
    if not (reuse and have):
        subprocess.run(['bash', os.path.join(HERE, 'build_images.sh')], check=True)
        trace_all.main(('main', 'external'))
    validate_tracer.main()
    analyse.main()
    figures.main()
    write_config()
    make_doc.main()


if __name__ == '__main__':
    main()
