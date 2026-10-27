"""Configurations of the round 6 software in the loop study with executed cryptography.

Seven configurations on the same flight stack, missions, link profile and paired seeds:
  none                no authentication
  signing             MAVLink 2 signing as shipped (flight stack and ground station; key provisioned on a wire)
  classical           classical session: X25519 with Ed25519 transcript signatures by both sides, key
                      confirmation, then the 13 B per message tag (published replay rule)
  hybrid_published    hybrid session with change F1 (X25519 plus ML-KEM-768, ML-DSA-44 by both sides), then
                      the 13 B tag; published replay rule
  hybrid_strict       the same session; strict next counter rule with resynchronisation by a new handshake
  hybrid_cache        the same session; replay cache rule with a window of W counters
  pqsig_real          ML-DSA-44 signature on every command (ground signs, vehicle verifies); no session
The gateway pair executes the cryptography with pinned libraries (sitl/gateway.py). Vehicle side compute
delays come from RTL simulated cycles (rtlsim/results/proto_sessions.csv and proto_primitives.csv of the round 6
RTL runs) at the mission study clock and are labelled estimated from RTL simulated cycles.
"""
import csv
import os

from mission import model, replay

from . import config as cfgmod

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

CONFIGS = ['none', 'signing', 'classical', 'hybrid_published', 'hybrid_strict', 'hybrid_cache', 'pqsig_real']
CONFIG_NAMES = {
    'none': '1 no authentication',
    'signing': '2 MAVLink 2 signing as shipped',
    'classical': '3 classical session (X25519, Ed25519), published rule',
    'hybrid_published': '4 hybrid session with F1, published rule',
    'hybrid_strict': '5 hybrid session with F1, strict rule',
    'hybrid_cache': '6 hybrid session with F1, replay cache rule',
    'pqsig_real': '7 ML-DSA-44 signature per command',
}
SHORT = {'none': 'none', 'signing': 'signing', 'classical': 'classical', 'hybrid_published': 'hybrid pub',
         'hybrid_strict': 'hybrid strict', 'hybrid_cache': 'hybrid cache', 'pqsig_real': 'ML-DSA-44 cmd'}
# mission study architecture and replay rule used for the comparison of each configuration
STUDY = {'none': ('A', None), 'signing': ('D', None), 'classical': ('A', 'published'),
         'hybrid_published': ('B', 'published'), 'hybrid_strict': ('B', 'strict'), 'hybrid_cache': ('B', 'cache'),
         'pqsig_real': ('C', None)}
PROFILES = cfgmod.PROFILES

# Rows of the RTL result files used for the vehicle side delays. Sessions: (design, side, steps) of
# proto_sessions.csv; primitives: operation of proto_primitives.csv. cycles_median is used.
RTL_SESSION_ROWS = {
    'hybrid_vehicle_total': ('hybrid_f1', 'vehicle', 'vehicle_f2+vehicle_f4'),
    'classical_vehicle_total': ('classical', 'vehicle', 'vehicle_f2+vehicle_f4'),
    'tag_check': ('mavlink_tag', 'vehicle', 'vehicle_receive_command_long'),
    'tag_make': ('mavlink_tag', 'ground', 'ground_tag_frame60'),
    'mldsa44_verify_command': ('per_command_mldsa44', 'vehicle', 'vehicle_verify_command'),
}
RTL_PRIMITIVES = ['x25519_keygen', 'x25519_shared', 'mlkem768_encaps', 'shake256_transcript_hybrid', 'shake256_kdf']
# The session files give the vehicle total of a handshake (F2 and F4 steps together). The split between the step
# before F2 and the step before F4 is derived from the primitives: the F2 step is X25519 key generation, the
# X25519 shared secret, (hybrid) ML-KEM-768 encapsulation, the transcript hash and the key derivation; the F4 step
# is the rest of the total (signature verification, confirmation tags and signing). The classical transcript hash
# (77 B) is costed as shake256_kdf, since both absorb less than one SHAKE256 block of 136 B.
RTL_SPLIT = {
    'hybrid_vehicle_f2': ['x25519_keygen', 'x25519_shared', 'mlkem768_encaps', 'shake256_transcript_hybrid', 'shake256_kdf'],
    'classical_vehicle_f2': ['x25519_keygen', 'x25519_shared', 'shake256_kdf', 'shake256_kdf'],
}


def load_settings(path=os.path.join(HERE, 'settings_r6.csv')):
    out = {}
    with open(path, newline='', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            v = r['value']
            try:
                out[r['name']] = float(v)
            except ValueError:
                out[r['name']] = v
    return out


def run_seed(settings, profile, i):
    """Seed of mission i on a profile; the same for every configuration (paired outages and phases)."""
    return int(settings['seed_base_r6']) + 1000 * PROFILES.index(profile) + i


def _read(path):
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def rtl_delays(rtl_dir, core, clock_hz, statistic='median'):
    """Vehicle side delays {name: dict(seconds, cycles, source, core, label)} from the RTL result files."""
    if statistic != 'median':
        raise ValueError('only the median of the RTL runs is used')
    sess = _read(os.path.join(rtl_dir, 'proto_sessions.csv'))
    prim = _read(os.path.join(rtl_dir, 'proto_primitives.csv'))
    cyc, src = {}, {}
    for name, (design, side, steps) in RTL_SESSION_ROWS.items():
        m = [r for r in sess if r['core'].lower() == core.lower() and r['design'] == design and r['side'] == side
             and r['steps'] == steps]
        if len(m) != 1:
            raise KeyError(f'proto_sessions.csv row for {name}: {len(m)} matches (core {core})')
        cyc[name] = float(m[0]['cycles_median'])
        src[name] = f'proto_sessions.csv {design} {side} {steps}'
    pc = {}
    for op in RTL_PRIMITIVES:
        m = [r for r in prim if r['core'].lower() == core.lower() and r['operation'] == op]
        if len(m) != 1:
            raise KeyError(f'proto_primitives.csv row for {op}: {len(m)} matches (core {core})')
        pc[op] = float(m[0]['cycles_median'])
    for design in ('hybrid', 'classical'):
        f2 = sum(pc[op] for op in RTL_SPLIT[f'{design}_vehicle_f2'])
        tot = cyc[f'{design}_vehicle_total']
        if not 0 < f2 < tot:
            raise ValueError(f'{design}: F2 step from primitives ({f2}) outside the session total ({tot})')
        cyc[f'{design}_vehicle_f2'] = f2
        src[f'{design}_vehicle_f2'] = 'proto_primitives.csv ' + ' + '.join(RTL_SPLIT[f'{design}_vehicle_f2'])
        cyc[f'{design}_vehicle_f4'] = tot - f2
        src[f'{design}_vehicle_f4'] = f'{src[design + "_vehicle_total"]} minus the F2 step'
    return {k: dict(seconds=v / clock_hz, cycles=v, source=src[k], core=core,
                    label='estimated from RTL simulated cycles') for k, v in cyc.items()}


def security_config(name, delays=None):
    """Description of one configuration for the gateway relay; delays from rtl_delays (None in unit tests)."""
    ra = replay.load_replay_assumptions()
    p = model.load_link_params()
    a = model.load_assumptions()
    d = {k: v['seconds'] for k, v in (delays or {}).items()}
    base = dict(name=name, design=None, rule=None, window=int(ra['replay_window_counters']), pqsig=False,
                tag_bytes=0, cmd_extra_bytes=0, session=False, delays=d, timeout_s=a['session_timeout_s'],
                rekey_s=a['rekey_interval_s'], grace_s=a['grace_s'], cmd_delay_s=0.0, flights=[])
    if name in ('none', 'signing'):
        return base
    if name == 'pqsig_real':
        base.update(pqsig=True, cmd_extra_bytes=int(p['mldsa44_sig_bytes']), cmd_delay_s=d.get('mldsa44_verify_command', 0.0))
        return base
    design = 'classical' if name == 'classical' else 'hybrid'
    rule = 'published' if name in ('classical', 'hybrid_published') else name.split('_')[1]
    base.update(design=design, rule=rule, session=True, tag_bytes=int(p['mav_sig_field_bytes']),
                cmd_delay_s=d.get('tag_check', 0.0))
    return base
