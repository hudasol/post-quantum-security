"""Inputs and deterministic arithmetic for the mission study (label: estimated).

Reads data/shared_inputs.csv (every parameter shared with another study: cycles, clock, sizes, link
parameters), linksim/params.csv (link parameters only the link studies use), data/evidence.csv (range rows),
mission/traffic.csv, mission/payload_lengths.csv and mission/assumptions.csv.
No code from linksim/ is imported; only its parameter file is read.
Nothing cryptographic is implemented: sizes and cycle counts are bookkeeping values.
"""
import csv
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from shared import inputs as shared_inputs  # noqa: E402



def _read_csv(path):
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def load_link_params(path=os.path.join(ROOT, 'linksim', 'params.csv')):
    """Return {name: float} from linksim/params.csv plus every value of data/shared_inputs.csv."""
    p = {r['name']: float(r['value']) for r in _read_csv(path)}
    sh = shared_inputs.values()
    dup = set(p) & set(sh)
    if dup:
        raise ValueError(f'defined twice: {sorted(dup)}')
    p.update(sh)
    return p


# Mission names of shared parameters: mission name -> (shared parameter, multiplier).
SHARED_ASSUMPTIONS = {
    'clock_hz': ('clock_m4_ref_mhz', 1e6),
    'mac_cycles': ('mac_cycles_per_message', 1.0),
    'ftp_header_bytes': ('mav_ftp_header_bytes', 1.0),
    'chunk_data_bytes': ('mav_ftp_data_bytes', 1.0),
}


def load_assumptions(path=os.path.join(HERE, 'assumptions.csv')):
    """Return {name: float} from mission/assumptions.csv plus the shared values under their mission names."""
    a = {r['name']: float(r['value']) for r in _read_csv(path)}
    sh = shared_inputs.values()
    for name, (sname, mult) in SHARED_ASSUMPTIONS.items():
        if name in a:
            raise ValueError(f'{name} is shared (data/shared_inputs.csv {sname}); remove it from {path}')
        a[name] = sh[sname] * mult
    return a


def load_payloads(path=os.path.join(HERE, 'payload_lengths.csv')):
    """Return {message: max payload bytes} (host measured)."""
    return {r['message']: int(r['max_payload_bytes']) for r in _read_csv(path)}


def load_traffic(path=os.path.join(HERE, 'traffic.csv')):
    return _read_csv(path)


def evidence_cycles(ids, path=os.path.join(ROOT, 'data', 'evidence.csv')):
    """Return {id: cycles} for the requested evidence ids (published rows)."""
    want = set(ids)
    out = {}
    for r in _read_csv(path):
        if r['id'] in want and r['cycles']:
            out[r['id']] = float(r['cycles'])
    missing = want - set(out)
    if missing:
        raise KeyError(f'evidence rows without cycles: {sorted(missing)}')
    return out


# The chosen row of every operation comes from data/shared_inputs.csv (one value, one source); the range rows
# below are mission only. Classical rows (stream S12, published, double read), the same rows as the energy study:
# X25519: S12A-332, Emill X25519-Cortex-M4 README, integer only version, 548,873 cycles per scalar
#   multiplication (board and clock not stated). The vehicle does two scalar multiplications per handshake
#   (ephemeral key generation and shared secret), so the row is counted twice (conservative, since a fixed base
#   key generation can be faster).
# Ed25519 verify: S12A-331, Owens et al., STM32F407 at 24 MHz, 722,000 cycles.
# Ranges over all S12A rows for the same operation are carried beside the chosen value.
#
# Flash wait states: the wait state factor (mission/assumptions.csv) is applied only to rows measured under
# zero wait state conditions (zero_ws True below). pqm4 rows: zero wait states derived from the pqm4 code
# (comparability warning of the rows). S12A-331: measured at 24 MHz and treated as zero wait state conditions,
# as in the energy study; the row itself does not state the wait state setting. Rows whose clock or wait state
# setting is not stated (S12A-332, S8-026) are used as published without the factor.
CYCLE_SOURCES = {
    # name: (shared parameter, times counted, note, ids spanning the range for one operation, range multiplier, zero_ws)
    'x25519_two_mults': ('x25519_scalarmult_cycles_m4', 2,
                         'X25519, two scalar multiplications (key generation plus shared secret), Emill integer version, board and clock not stated',
                         ['S12A-317', 'S12A-321', 'S12A-325', 'S12A-332', 'S12A-333'], 2, False),
    'ed25519_verify': ('ed25519_verify_cycles_m4', 1, 'Ed25519 verify, Owens et al., STM32F407 at 24 MHz',
                       ['S12A-320', 'S12A-324', 'S12A-328', 'S12A-331'], 1, True),
    'ed25519_sign': ('ed25519_sign_cycles_m4', 1, 'Ed25519 sign, Owens et al., STM32F407 at 24 MHz',
                     ['S12A-319', 'S12A-323', 'S12A-327', 'S12A-330'], 1, True),
    'mlkem768_encaps': ('mlkem768_encaps_cycles_m4', 1, 'ML-KEM-768 encaps, pqm4 m4fspeed', ['S2-0023'], 1, True),
    'mldsa44_verify': ('mldsa44_verify_cycles_m4', 1, 'ML-DSA-44 verify, pqm4 m4f', ['S2-0033'], 1, True),
    'mldsa44_sign': ('mldsa44_sign_cycles_m4', 1, 'ML-DSA-44 sign, pqm4 m4f (mean of a variable signing time)',
                     ['S2-0032'], 1, True),
    'lms_verify': ('lms_verify_cycles_m4', 1,
                   'LMS w=16 h=10 SHA-256 verify, Cortex-M4 (Campos et al.), clock not stated', ['S8-026'], 1, False),
}


def cycle_table():
    """Return {operation: (cycles, label, source, range_min, range_max, range_ids, zero_ws)}.

    The chosen value is the shared value (data/shared_inputs.csv) times the count; the range is the minimum and
    maximum over the listed published rows for the same operation, times the multiplier (two scalar
    multiplications for X25519). zero_ws marks rows measured at zero flash wait states.
    """
    ids = sorted(set(sum((v[3] for v in CYCLE_SOURCES.values()), [])))
    ev = evidence_cycles(ids)
    sh = shared_inputs.values()
    t = {}
    for name, (sname, count, note, rng_ids, mult, zws) in CYCLE_SOURCES.items():
        vals = [ev[i] * mult for i in rng_ids]
        eid = shared_inputs.evidence_id(sname)
        label = 'published' if count == 1 else 'derived from published'
        t[name] = (sh[sname] * count, label, '+'.join([eid] * count) + '; ' + note, min(vals), max(vals),
                   ' '.join(rng_ids), zws)
    return t


def effective_cycles(parts, ws, cyc=None):
    """Sum cycles of the named operations, applying the wait state factor only to zero wait state rows."""
    cyc = cyc or cycle_table()
    return sum(cyc[n][0] * (ws if cyc[n][6] else 1.0) for n in parts)


# ---------------------------------------------------------------- links

LINKS = ['sik', 'ieee802154', 'lora_dr5', 'lora_dr0']
LINK_NAMES = {'sik': 'SiK 64 kbit/s', 'ieee802154': 'IEEE 802.15.4', 'lora_dr5': 'LoRaWAN DR5', 'lora_dr0': 'LoRaWAN DR0'}


def link_profile(name, p=None):
    """Return a dict describing a link: data rate, frame capacity, frame wire bytes, duty cycle, turnaround.

    sik: byte stream at air rate x usable fraction (cited); MAVLink frames are sent whole (one link frame each).
    ieee802154: 81 B of data per 127 B PHY frame at 250 kbit/s (cited, worst case with link security).
    lora_dr5 / lora_dr0: EU868 application payload 222 B / 51 B at 5470 / 250 bit/s, 1 percent duty cycle (cited);
    the 13 B LoRaWAN frame overhead (shared value, cited) is added to each frame; the PHY preamble and header are
    not counted (the nominal bit rate model), which understates air time.
    """
    p = p or load_link_params()
    if name == 'sik':
        return dict(name=name, rate=p['sik_air_rate_bps'] * p['sik_usable_fraction'], cap=None, wire_extra=0,
                    duty=1.0, turnaround=p['turnaround_s'], shared=True)
    if name == 'ieee802154':
        return dict(name=name, rate=p['ieee802154_rate_bps'], cap=int(p['ieee802154_data_bytes']),
                    wire_extra=int(p['ieee802154_phy_max_bytes'] - p['ieee802154_data_bytes']), duty=1.0,
                    turnaround=p['turnaround_s'], shared=True)
    if name == 'lora_dr5':
        return dict(name=name, rate=p['lorawan_dr5_bitrate_bps'], cap=int(p['lorawan_dr5_payload_bytes']),
                    wire_extra=int(p['lorawan_frame_overhead_bytes']), duty=p['lorawan_duty_cycle'],
                    turnaround=p['turnaround_lorawan_s'], shared=False)
    if name == 'lora_dr0':
        return dict(name=name, rate=p['lorawan_dr0_bitrate_bps'], cap=int(p['lorawan_dr0_payload_bytes']),
                    wire_extra=int(p['lorawan_frame_overhead_bytes']), duty=p['lorawan_duty_cycle'],
                    turnaround=p['turnaround_lorawan_s'], shared=False)
    raise ValueError(name)


def link_frames(mav_frame_bytes, link):
    """Air times (s) of the link frames that carry one MAVLink frame of the given size."""
    if link['cap'] is None:
        return [mav_frame_bytes * 8.0 / link['rate']]
    n = math.ceil(mav_frame_bytes / link['cap'])
    out = []
    left = mav_frame_bytes
    for _ in range(n):
        d = min(left, link['cap'])
        left -= d
        if link['wire_extra'] and link['name'] == 'ieee802154':
            wire = link['cap'] + link['wire_extra']  # full PHY frame per fragment
        else:
            wire = d + link['wire_extra']
        out.append(wire * 8.0 / link['rate'])
    return out


def mav_frame_bytes(payload, auth_bytes, p=None):
    """MAVLink 2 frame size: header + payload + checksum + per frame authentication field."""
    p = p or load_link_params()
    return int(p['mav_header_bytes'] + payload + p['mav_checksum_bytes'] + auth_bytes)


def object_frames(nbytes, link, a=None, p=None):
    """Air times of all link frames needed to carry an object of nbytes in file transfer style chunks."""
    p = p or load_link_params()
    a = a or load_assumptions()
    chunk = int(a['chunk_data_bytes'])
    out = []
    left = int(nbytes)
    while left > 0:
        d = min(left, chunk)
        left -= d
        out += link_frames(mav_frame_bytes(a['ftp_header_bytes'] + d, 0, p), link)
    return out


# ---------------------------------------------------------------- architectures

ARCHS = ['A', 'B', 'C', 'D']
ARCH_NAMES = {
    'A': 'A classical (X25519 + Ed25519, MAVLink 2 signing)',
    'B': 'B hybrid (X25519 + ML-KEM-768, ML-DSA-44 transcript signatures of both sides, symmetric tag)',
    'C': 'C ML-DSA-44 signature on every command',
    'D': 'D LMS signed firmware plus provisioned session keys',
}


def arch_profile(arch, p=None, cyc=None):
    """Bytes on the air and vehicle side cycles for one architecture.

    flights: handshake flights as (direction, bytes); direction 'up' is ground to vehicle.
    tag_bytes: per message authentication field (13 B MAVLink 2 signing field, cited).
    cmd_extra_bytes: extra bytes carried with every command (C only).
    hs_cycles: vehicle cycles per handshake or rekey; cmd_cycles: per command check; boot_cycles: once.
    """
    p = p or load_link_params()
    cyc = cyc or cycle_table()
    x = p['x25519_share_bytes']
    tag = p['mav_sig_field_bytes']
    # Design change F1 (docs/FORMAL_VERIFICATION.md): the ground station signs the transcript and sends its key
    # confirmation tag (flight 3, up); the vehicle then signs the transcript with its own pinned key and sends its
    # tag (flight 4, down). Vehicle cycles: key exchange, verification of the ground signature, one signature.
    # Architecture A gets the same structure with Ed25519 so that A and B stay comparable.
    if arch == 'A':
        flights = [('up', x), ('down', x), ('up', p['ed25519_sig_bytes'] + p['confirm_bytes']),
                   ('down', p['ed25519_sig_bytes'] + p['confirm_bytes'])]
        parts = ['x25519_two_mults', 'ed25519_verify', 'ed25519_sign']
        hs = sum(cyc[n][0] for n in parts)
        return dict(flights=flights, tag_bytes=tag, cmd_extra_bytes=0, hs_cycles=hs, cmd_cycles=0.0, boot_cycles=0.0,
                    hs_parts=parts, cmd_parts=[], boot_parts=[], session=True, quantum_safe=False)
    if arch == 'B':
        flights = [('up', x + p['mlkem768_ek_bytes']), ('down', x + p['mlkem768_ct_bytes']),
                   ('up', p['mldsa44_sig_bytes'] + p['confirm_bytes']),
                   ('down', p['mldsa44_sig_bytes'] + p['confirm_bytes'])]
        parts = ['x25519_two_mults', 'mlkem768_encaps', 'mldsa44_verify', 'mldsa44_sign']
        hs = sum(cyc[n][0] for n in parts)
        return dict(flights=flights, tag_bytes=tag, cmd_extra_bytes=0, hs_cycles=hs, cmd_cycles=0.0, boot_cycles=0.0,
                    hs_parts=parts, cmd_parts=[], boot_parts=[], session=True, quantum_safe=True)
    if arch == 'C':
        return dict(flights=[], tag_bytes=0, cmd_extra_bytes=p['mldsa44_sig_bytes'], hs_cycles=0.0,
                    cmd_cycles=cyc['mldsa44_verify'][0], boot_cycles=0.0, hs_parts=[], cmd_parts=['mldsa44_verify'],
                    boot_parts=[], session=False, quantum_safe=True)
    if arch == 'D':
        return dict(flights=[], tag_bytes=tag, cmd_extra_bytes=0, hs_cycles=0.0, cmd_cycles=0.0,
                    boot_cycles=cyc['lms_verify'][0], hs_parts=[], cmd_parts=[], boot_parts=['lms_verify'],
                    session=False, quantum_safe=True)
    raise ValueError(arch)


def handshake_bytes(arch):
    return sum(b for _, b in arch_profile(arch)['flights'])


def command_frames(vehicle, arch, link, payloads=None, traffic=None, p=None, a=None):
    """Air times of the link frames for one authenticated command, and for the same command unauthenticated."""
    payloads = payloads or load_payloads()
    traffic = traffic or load_traffic()
    cmd = [r for r in traffic if r['vehicle'] == vehicle and r['role'] == 'command'][0]
    pl = payloads[cmd['message']]
    ap = arch_profile(arch, p)
    base = link_frames(mav_frame_bytes(pl, 0, p), link)
    if ap['cmd_extra_bytes']:
        auth = object_frames(pl + ap['cmd_extra_bytes'], link, a, p)
    else:
        auth = link_frames(mav_frame_bytes(pl, ap['tag_bytes'], p), link)
    return auth, base


def command_rate(vehicle, traffic=None):
    traffic = traffic or load_traffic()
    return float([r for r in traffic if r['vehicle'] == vehicle and r['role'] == 'command'][0]['rate_hz'])


def telemetry_load(vehicle, arch, link, payloads=None, traffic=None, p=None):
    """Return (air seconds per second, messages per second, mean frame air time) for non command traffic.

    Down and up directions are summed (shared half duplex channel for SiK and 802.15.4).
    For LoRaWAN the result is split by transmitter in telemetry_load_by_dir.
    """
    payloads = payloads or load_payloads()
    traffic = traffic or load_traffic()
    ap = arch_profile(arch, p)
    air = 0.0
    msgs = 0.0
    nfr = 0.0
    for r in traffic:
        if r['vehicle'] != vehicle or r['role'] not in ('telemetry', 'ack'):
            continue
        rate = float(r['rate_hz'])
        fr = link_frames(mav_frame_bytes(payloads[r['message']], ap['tag_bytes'], p), link)
        air += rate * sum(fr)
        msgs += rate
        nfr += rate * len(fr)
    return air, msgs, (air / nfr if nfr else 0.0)


def telemetry_load_by_dir(vehicle, arch, link, payloads=None, traffic=None, p=None):
    """Return {'up': air s/s, 'down': air s/s} for non command traffic."""
    payloads = payloads or load_payloads()
    traffic = traffic or load_traffic()
    ap = arch_profile(arch, p)
    out = {'up': 0.0, 'down': 0.0}
    for r in traffic:
        if r['vehicle'] != vehicle or r['role'] not in ('telemetry', 'ack'):
            continue
        fr = link_frames(mav_frame_bytes(payloads[r['message']], ap['tag_bytes'], p), link)
        out[r['direction']] += float(r['rate_hz']) * sum(fr)
    return out


def mission_phases(vehicle, a=None):
    """Return list of (phase, start, end) in seconds."""
    a = a or load_assumptions()
    if vehicle == 'drone':
        names = ['preflight', 'takeoff', 'cruise', 'landing']
        d = [a['drone_preflight_s'], a['drone_takeoff_s'], a['drone_cruise_s'], a['drone_landing_s']]
    else:
        names = ['preflight', 'drive']
        d = [a['robot_preflight_s'], a['robot_drive_s']]
    out, t = [], 0.0
    for n, x in zip(names, d):
        out.append((n, t, t + x))
        t += x
    return out
