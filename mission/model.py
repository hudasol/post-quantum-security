"""Inputs and deterministic arithmetic for the mission study (label: estimated).

Reads linksim/params.csv (cited link parameters), data/evidence.csv (published cycles),
mission/traffic.csv, mission/payload_lengths.csv and mission/assumptions.csv.
No code from linksim/ is imported; only its parameter file is read.
Nothing cryptographic is implemented: sizes and cycle counts are bookkeeping values.
"""
import csv
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def _read_csv(path):
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def load_link_params(path=os.path.join(ROOT, 'linksim', 'params.csv')):
    """Return {name: float} from linksim/params.csv."""
    return {r['name']: float(r['value']) for r in _read_csv(path)}


def load_assumptions(path=os.path.join(HERE, 'assumptions.csv')):
    """Return {name: float} from mission/assumptions.csv."""
    return {r['name']: float(r['value']) for r in _read_csv(path)}


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


# Ed25519 verify has no cycle column in data/evidence.csv; S10D-031 reports 40 ms at 64 MHz
# (Monocypher on nRF52840, Cortex-M4F). Cycles are derived as time x clock.
ED25519_VERIFY_MS_S10D031 = 40.0
ED25519_CLOCK_MHZ_S10D031 = 64.0

CYCLE_SOURCES = {
    # name: (evidence ids, note)
    'ecdh_proxy': (['S2-0199', 'S2-0201'], 'X25519 has no cycle row; ECDH secp256r1 keygen plus shared secret (micro-ecc, Cortex-M4 at 96 MHz) used as a proxy'),
    'mlkem768_encaps': (['S2-0023'], 'ML-KEM-768 encaps, pqm4 m4fspeed'),
    'mldsa44_verify': (['S2-0033'], 'ML-DSA-44 verify, pqm4 m4f'),
    'lms_verify': (['S2-0316'], 'LMS w=16 h=5 SHA-256 verify, Cortex-M4 (slides)'),
}


def cycle_table():
    """Return {operation: (cycles, label, source)} for the vehicle side operations."""
    ids = sum((v[0] for v in CYCLE_SOURCES.values()), [])
    ev = evidence_cycles(ids)
    t = {}
    for name, (rows, note) in CYCLE_SOURCES.items():
        t[name] = (sum(ev[i] for i in rows), 'published', '+'.join(rows) + '; ' + note)
    ed = ED25519_VERIFY_MS_S10D031 * 1e-3 * ED25519_CLOCK_MHZ_S10D031 * 1e6
    t['ed25519_verify'] = (ed, 'derived from published', 'S10D-031: 40 ms x 64 MHz (Monocypher, nRF52840)')
    return t


# ---------------------------------------------------------------- links

LINKS = ['sik', 'ieee802154', 'lora_dr5', 'lora_dr0']
LINK_NAMES = {'sik': 'SiK 64 kbit/s', 'ieee802154': 'IEEE 802.15.4', 'lora_dr5': 'LoRaWAN DR5', 'lora_dr0': 'LoRaWAN DR0'}


def link_profile(name, p=None):
    """Return a dict describing a link: data rate, frame capacity, frame wire bytes, duty cycle, turnaround.

    sik: byte stream at air rate x usable fraction (cited); MAVLink frames are sent whole (one link frame each).
    ieee802154: 81 B of data per 127 B PHY frame at 250 kbit/s (cited, worst case with link security).
    lora_dr5 / lora_dr0: EU868 application payload 222 B / 51 B at 5470 / 250 bit/s, 1 percent duty cycle (cited);
    LoRaWAN PHY and MAC overhead ignored (not in the data files), which understates air time.
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
                    wire_extra=int(p['lorawan_phy_mac_overhead_bytes']), duty=p['lorawan_duty_cycle'],
                    turnaround=p['turnaround_lorawan_s'], shared=False)
    if name == 'lora_dr0':
        return dict(name=name, rate=p['lorawan_dr0_bitrate_bps'], cap=int(p['lorawan_dr0_payload_bytes']),
                    wire_extra=int(p['lorawan_phy_mac_overhead_bytes']), duty=p['lorawan_duty_cycle'],
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
    'B': 'B hybrid (X25519 + ML-KEM-768, ML-DSA-44 transcript signature, symmetric tag)',
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
    if arch == 'A':
        flights = [('up', x), ('down', x), ('up', p['ed25519_sig_bytes'] + p['confirm_bytes'])]
        hs = cyc['ecdh_proxy'][0] + cyc['ed25519_verify'][0]
        return dict(flights=flights, tag_bytes=tag, cmd_extra_bytes=0, hs_cycles=hs, cmd_cycles=0.0, boot_cycles=0.0,
                    session=True, quantum_safe=False)
    if arch == 'B':
        flights = [('up', x + p['mlkem768_ek_bytes']), ('down', x + p['mlkem768_ct_bytes']),
                   ('up', p['mldsa44_sig_bytes'] + p['confirm_bytes'])]
        hs = cyc['ecdh_proxy'][0] + cyc['mlkem768_encaps'][0] + cyc['mldsa44_verify'][0]
        return dict(flights=flights, tag_bytes=tag, cmd_extra_bytes=0, hs_cycles=hs, cmd_cycles=0.0, boot_cycles=0.0,
                    session=True, quantum_safe=True)
    if arch == 'C':
        return dict(flights=[], tag_bytes=0, cmd_extra_bytes=p['mldsa44_sig_bytes'], hs_cycles=0.0,
                    cmd_cycles=cyc['mldsa44_verify'][0], boot_cycles=0.0, session=False, quantum_safe=True)
    if arch == 'D':
        return dict(flights=[], tag_bytes=tag, cmd_extra_bytes=0, hs_cycles=0.0, cmd_cycles=0.0,
                    boot_cycles=cyc['lms_verify'][0], session=False, quantum_safe=True)
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
