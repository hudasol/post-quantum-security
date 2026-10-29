"""Configurations of the round 6 software in the loop study with executed cryptography.

Ten configurations on the same flight stack, missions, link profile and paired seeds:
  none                no authentication
  signing             MAVLink 2 signing as shipped (flight stack and ground station; key provisioned on a wire)
  classical           classical session: X25519 with Ed25519 transcript signatures by both sides, key
                      confirmation, then the 13 B per message tag (published replay rule)
  hybrid_published    hybrid session with change F1 (X25519 plus ML-KEM-768, ML-DSA-44 by both sides), then
                      the 13 B tag; published replay rule
  hybrid_strict       the same session; strict next counter rule with resynchronisation by a new handshake
  hybrid_cache        the same session; replay cache rule with a window of W counters
  pqsig_real          ML-DSA-44 signature on every command (ground signs, vehicle verifies); no session
  kem_auth            design K: KEM authentication with static ML-KEM-768 keys pinned on both sides, X25519 plus
                      ML-KEM-768 ephemeral exchange, no signatures, three flights, then the 13 B tag; published
                      replay rule (added after the first seven; its vehicle side delays come from the 15 run RTL
                      files, see rtl_delays)
  hybrid_strict_inband  the hybrid session with F1 and the strict rule, resynchronised inside the session (one
                      authenticated message each way under the session key) instead of by a new handshake; added
                      after kem_auth
  pqsig_counter       ML-DSA-44 signature per command over the frame and a 6 B counter, published rule at the
                      vehicle; added after kem_auth
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

CONFIGS = ['none', 'signing', 'classical', 'hybrid_published', 'hybrid_strict', 'hybrid_cache', 'pqsig_real',
           'kem_auth', 'hybrid_strict_inband', 'pqsig_counter']
# the configurations of the first round 6 runs, and the one added later (design K); analyse_r6 writes the rows of
# the added configuration after those of the first seven so that the earlier rows stay unchanged
FIRST = CONFIGS[:7]
ADDED = ['kem_auth']
# the two configurations added after kem_auth (in band resynchronisation, per command signature with a counter);
# their rows come after those of kem_auth in every output file
LATER = ['hybrid_strict_inband', 'pqsig_counter']
GROUPS = (FIRST, ADDED, LATER)
# configurations with a session (a handshake time per mission)
SESSION = ['classical', 'hybrid_published', 'hybrid_strict', 'hybrid_cache', 'kem_auth', 'hybrid_strict_inband']
CONFIG_NAMES = {
    'none': '1 no authentication',
    'signing': '2 MAVLink 2 signing as shipped',
    'classical': '3 classical session (X25519, Ed25519), published rule',
    'hybrid_published': '4 hybrid session with F1, published rule',
    'hybrid_strict': '5 hybrid session with F1, strict rule',
    'hybrid_cache': '6 hybrid session with F1, replay cache rule',
    'pqsig_real': '7 ML-DSA-44 signature per command',
    'kem_auth': '8 KEM authenticated session (design K), published rule',
    'hybrid_strict_inband': '9 hybrid session with F1, strict rule, in band resynchronisation',
    'pqsig_counter': '10 ML-DSA-44 signature per command with a counter, published rule',
}
SHORT = {'none': 'none', 'signing': 'signing', 'classical': 'classical', 'hybrid_published': 'hybrid pub',
         'hybrid_strict': 'hybrid strict', 'hybrid_cache': 'hybrid cache', 'pqsig_real': 'ML-DSA-44 cmd',
         'kem_auth': 'KEM auth', 'hybrid_strict_inband': 'strict in band', 'pqsig_counter': 'ML-DSA-44 ctr'}
# mission study architecture and replay rule used for the comparison of each configuration; the mission model has
# no architecture for design K, so kem_auth has none (its comparison row carries no model value)
STUDY = {'none': ('A', None), 'signing': ('D', None), 'classical': ('A', 'published'),
         'hybrid_published': ('B', 'published'), 'hybrid_strict': ('B', 'strict'), 'hybrid_cache': ('B', 'cache'),
         'pqsig_real': ('C', None), 'kem_auth': (None, 'published'), 'hybrid_strict_inband': (None, 'strict'),
         'pqsig_counter': (None, 'published')}
# why a configuration has no mission study architecture
NO_ARCH = {'kem_auth': 'design K',
           'hybrid_strict_inband': 'in band resynchronisation',
           'pqsig_counter': 'per command signature with a counter'}
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

# Design K (kem_auth): rows of the 15 run RTL files (rtlsim/results/proto_sessions.csv and proto_primitives.csv;
# the five run snapshots used for the first seven configurations have no design K rows). Design K has no signing
# rejection loop, so its cycles barely vary between runs. The vehicle total covers the F2 step and the accept step;
# the F2 step is costed from the primitives (X25519 key generation and shared secret, one ML-KEM-768
# decapsulation, two encapsulations, the transcript hash over both identities, F1 and F2, the key derivation over
# five inputs and the vehicle confirmation tag) and the accept step is the rest of the total (the ground
# confirmation tag and its comparison).
RTL_KEM_AUTH_ROW = ('kem_auth', 'vehicle', 'vehicle_f2+vehicle_accept')
RTL_KEM_AUTH_F2 = ['x25519_keygen', 'x25519_shared', 'mlkem768_decaps', 'mlkem768_encaps', 'mlkem768_encaps',
                   'shake256_transcript_kem_auth', 'shake256_kdf_kem_auth', 'shake256_confirm_tag']


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


def rtl_delays(rtl_dir, core, clock_hz, statistic='median', kem_auth=False):
    """Vehicle side delays {name: dict(seconds, cycles, source, core, label)} from the RTL result files.

    kem_auth=True adds the design K delays (kem_auth_vehicle_total, kem_auth_vehicle_f2, kem_auth_vehicle_accept),
    which need the design K rows of the 15 run files."""
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
    if kem_auth:
        design, side, steps = RTL_KEM_AUTH_ROW
        m = [r for r in sess if r['core'].lower() == core.lower() and r['design'] == design and r['side'] == side
             and r['steps'] == steps]
        if len(m) != 1:
            raise KeyError(f'proto_sessions.csv row for kem_auth_vehicle_total: {len(m)} matches (core {core})')
        tot = float(m[0]['cycles_median'])
        cyc['kem_auth_vehicle_total'] = tot
        src['kem_auth_vehicle_total'] = f'proto_sessions.csv {design} {side} {steps}'
        for op in sorted(set(RTL_KEM_AUTH_F2) - set(pc)):
            mm = [r for r in prim if r['core'].lower() == core.lower() and r['operation'] == op]
            if len(mm) != 1:
                raise KeyError(f'proto_primitives.csv row for {op}: {len(mm)} matches (core {core})')
            pc[op] = float(mm[0]['cycles_median'])
        f2 = sum(pc[op] for op in RTL_KEM_AUTH_F2)
        if not 0 < f2 < tot:
            raise ValueError(f'kem_auth: F2 step from primitives ({f2}) outside the session total ({tot})')
        cyc['kem_auth_vehicle_f2'] = f2
        src['kem_auth_vehicle_f2'] = 'proto_primitives.csv ' + ' + '.join(RTL_KEM_AUTH_F2)
        cyc['kem_auth_vehicle_accept'] = tot - f2
        src['kem_auth_vehicle_accept'] = f'{src["kem_auth_vehicle_total"]} minus the F2 step'
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
    if name == 'pqsig_counter':
        # the vehicle delay is that of the RTL row for the verification of a command (the 6 B counter is not costed)
        base.update(pqsig=True, pq_counter=True, rule='published', cmd_extra_bytes=int(p['mldsa44_sig_bytes']) + 6,
                    cmd_delay_s=d.get('mldsa44_verify_command', 0.0))
        return base
    design = {'classical': 'classical', 'kem_auth': 'kem_auth'}.get(name, 'hybrid')
    rule = 'published' if name in ('classical', 'hybrid_published', 'kem_auth') else name.split('_')[1]
    base.update(design=design, rule=rule, session=True, tag_bytes=int(p['mav_sig_field_bytes']),
                cmd_delay_s=d.get('tag_check', 0.0))
    if name == 'hybrid_strict_inband':
        base.update(inband=True)
    return base
