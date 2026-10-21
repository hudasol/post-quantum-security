"""Link profiles and the four security configurations of the software in the loop study.

Every number is read from linksim/params.csv (cited link parameters and labelled assumptions),
mission/assumptions.csv (mission study assumptions), data/evidence.csv (published cycle counts)
or from this file's own run settings, which are stated as assumptions of this study in
sitl/settings.csv. Nothing cryptographic is implemented: the hybrid session and the per command
signature are emulated by their bytes on the emulated link and by the published vehicle side
cycle cost as a delay.
"""
import csv
import math
import os

from mission import model

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

CONFIGS = ['none', 'signing', 'hybrid', 'pqsig']
CONFIG_NAMES = {
    'none': '1 no authentication',
    'signing': '2 MAVLink 2 signing as shipped (flight stack)',
    'hybrid': '3 hybrid session with change F1 and per message tag (emulated relay pair)',
    'pqsig': '4 ML-DSA-44 signature per command (emulated relay pair)',
}
# Mission study architecture used for the comparison of each configuration.
# none: the unauthenticated stream of the same study (avail_base columns); signing: D (provisioned key,
# 13 B field, no handshake); hybrid: B (handshake plus 13 B field); pqsig: C.
STUDY_ARCH = {'none': 'A', 'signing': 'D', 'hybrid': 'B', 'pqsig': 'C'}

PROFILES = ['sik', 'ieee802154']
PROFILE_NAMES = {'sik': 'SiK class 64 kbit/s', 'ieee802154': 'IEEE 802.15.4 class 250 kbit/s'}


def load_settings(path=os.path.join(HERE, 'settings.csv')):
    """Return {name: float or str} from sitl/settings.csv (run settings of this study)."""
    out = {}
    with open(path, newline='', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            v = r['value']
            try:
                out[r['name']] = float(v)
            except ValueError:
                out[r['name']] = v
    return out


def link_profile(name, p=None, a=None):
    """Emulated link profile: rate, fragment capacity, wire bytes per fragment, loss, retransmission timeout.

    The fragmentation and rate rules are those of mission/model.py (link_profile and link_frames).
    """
    p = p or model.load_link_params()
    a = a or model.load_assumptions()
    lk = model.link_profile(name, p)
    ack_air = sum(model.link_frames(model.mav_frame_bytes(p['ack_payload_bytes'], 0, p), lk))
    rto = p['rto_factor'] * (lk['turnaround'] + ack_air)
    return dict(name=name, rate=lk['rate'], cap=lk['cap'], wire_extra=lk['wire_extra'],
                loss=a['frame_loss'], rto=rto, max_retries=int(p['max_retries']), turnaround=lk['turnaround'])


def fragments(nbytes, prof):
    """Wire sizes in bytes of the link frames that carry one unit of nbytes (model.link_frames rule)."""
    if prof['cap'] is None:
        return [int(nbytes)]
    n = int(math.ceil(nbytes / prof['cap']))
    return [int(prof['cap'] + prof['wire_extra'])] * n


def object_fragments(nbytes, prof, p=None, a=None):
    """Wire sizes of the link frames for a large object sent in file transfer style chunks (model.object_frames)."""
    p = p or model.load_link_params()
    a = a or model.load_assumptions()
    chunk = int(a['chunk_data_bytes'])
    out = []
    left = int(nbytes)
    while left > 0:
        d = min(left, chunk)
        left -= d
        out += fragments(model.mav_frame_bytes(a['ftp_header_bytes'] + d, 0, p), prof)
    return out


def air_time(wire_bytes, prof):
    return wire_bytes * 8.0 / prof['rate']


def security_config(name, p=None, a=None):
    """Bytes and vehicle side delays of one configuration.

    tag_bytes: bytes added by the relay pair to every MAVLink frame on the air (hybrid only; the
    architecture's 13 B MAVLink 2 signing field). The signing configuration carries the real 13 B
    field that the flight stack and the ground station add, so the relay adds nothing.
    cmd_extra_bytes: bytes added to every command frame (pqsig: one ML-DSA-44 signature).
    cmd_delay_s: vehicle side delay per command (published cycles at the mission study clock).
    flights: handshake flights (direction, bytes, vehicle delay before sending it), hybrid only, with F1.
    """
    p = p or model.load_link_params()
    a = a or model.load_assumptions()
    cyc = model.cycle_table()
    clock = a['clock_hz']
    ws = a['wait_state_factor']
    if name in ('none', 'signing'):
        return dict(name=name, tag_bytes=0, cmd_extra_bytes=0, cmd_delay_s=0.0, flights=[], session=False)
    if name == 'hybrid':
        x = p['x25519_share_bytes']
        sig = p['mldsa44_sig_bytes']
        conf = p['confirm_bytes']
        sign_cycles = model.evidence_cycles(['S2-0032'])['S2-0032'] * ws  # ML-DSA-44 sign, pqm4 m4f, zero wait states
        d2 = model.effective_cycles(['x25519_two_mults', 'mlkem768_encaps'], ws, cyc) / clock
        d4 = (model.effective_cycles(['mldsa44_verify'], ws, cyc) + sign_cycles) / clock
        flights = [('up', int(x + p['mlkem768_ek_bytes']), 0.0),
                   ('down', int(x + p['mlkem768_ct_bytes']), d2),
                   ('up', int(sig + conf), 0.0),
                   ('down', int(sig + conf), d4)]
        return dict(name=name, tag_bytes=int(p['mav_sig_field_bytes']), cmd_extra_bytes=0,
                    cmd_delay_s=a['mac_cycles'] / clock, flights=flights, session=True,
                    timeout_s=a['session_timeout_s'], rekey_s=a['rekey_interval_s'], grace_s=a['grace_s'])
    if name == 'pqsig':
        return dict(name=name, tag_bytes=0, cmd_extra_bytes=int(p['mldsa44_sig_bytes']),
                    cmd_delay_s=model.effective_cycles(['mldsa44_verify'], ws, cyc) / clock, flights=[], session=False)
    raise ValueError(name)


def handshake_compute_s(sc):
    return sum(f[2] for f in sc['flights'])
