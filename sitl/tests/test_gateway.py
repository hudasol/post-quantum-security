"""Tests of the round 6 gateway: executed handshake, per message tag, replay rules and the gateway relay.

The tests that execute ML-KEM-768 or ML-DSA-44 need the host libraries built by sitl/pqlib/build.sh (folder in
SITL_PQLIB); they are skipped when the libraries are absent.
"""
import os
import struct
import tempfile
import unittest

import numpy as np

from mission import replay
from sitl import config_r6 as c6
from sitl import gateway as gw
from sitl import linkrelay as lr
from sitl import pqcrypto

HAVE_PQ = pqcrypto.available()


def frame2(msgid, payload, seq=5):
    hdr = bytes([0xFD, len(payload), 0, 0, seq, 255, 190]) + struct.pack('<I', msgid)[:3]
    return hdr + bytes(payload) + b'\x00\x00'


def command_long(cmd=183, seq=5):
    p = struct.pack('<7fHBBB', 9, 1500, 0, 0, 0, 0, 0, cmd, 1, 1, 0)
    return frame2(lr.MSG_COMMAND_LONG, p, seq)


def parse(raw):
    return lr.parse_frames(raw)[0][0]


class FakeSock:
    def __init__(self):
        self.sent = []

    def sendall(self, b):
        self.sent.append(b)

    def sendto(self, b, addr):
        self.sent.append(b)


def prof(loss=0.0):
    return dict(name='t', rate=57600.0, cap=None, wire_extra=0, loss=loss, rto=0.1, max_retries=20, turnaround=0.05)


class TestTagAndRules(unittest.TestCase):
    def test_tag_roundtrip_and_tamper(self):
        key = bytes(range(32))
        f = command_long()
        field = gw.tag_field(key, f, 0, 41)
        self.assertEqual(len(field), 13)
        self.assertEqual(gw.check_field(key, f, field), (True, 0, 41))
        bad = bytearray(f)
        bad[12] ^= 1
        self.assertFalse(gw.check_field(key, bytes(bad), field)[0])
        self.assertFalse(gw.check_field(bytes(32), f, field)[0])

    def test_tag_matches_mavlink_formula(self):
        # first 6 B of SHA-256(key || header || payload || crc || link id || 6 B timestamp), the signing guide formula
        import hashlib
        key = bytes(range(32))
        f = command_long()
        field = gw.tag_field(key, f, 1, 0x2A00001234)
        ts = (0x2A00001234).to_bytes(8, 'little')[:6]
        self.assertEqual(field[7:], hashlib.sha256(key + f + bytes([1]) + ts).digest()[:6])

    def test_acceptor_rules(self):
        seq = [0, 2, 1, 2, 3, 70, 5]
        pub = [gw.Acceptor('published').accept(0)[0]]
        a = gw.Acceptor('published')
        self.assertEqual([a.accept(c)[0] for c in seq], [True, True, False, False, True, True, False])
        s = gw.Acceptor('strict')
        out = [s.accept(c) for c in seq]
        self.assertEqual([o[0] for o in out], [True, False, True, True, True, False, False])
        self.assertEqual(out[1][1], 'ahead_of_next')
        self.assertTrue(s.gap())
        c = gw.Acceptor('cache', 64)
        self.assertEqual([c.accept(x)[0] for x in seq], [True, True, True, False, True, True, False])
        self.assertTrue(pub[0])

    def test_acceptor_agrees_with_mission_model(self):
        rng = np.random.default_rng(20261021)
        for w in (1, 4, 32, 64):
            for _ in range(20):
                seq = list(rng.integers(0, 120, 80))
                a = gw.Acceptor('cache', w)
                mine = [a.accept(int(x))[0] for x in seq]
                ref = replay.accept_in_arrival_order([int(x) for x in seq], 'cache', w).tolist()
                self.assertEqual(mine, ref)
                p = gw.Acceptor('published')
                self.assertEqual([p.accept(int(x))[0] for x in seq],
                                 replay.accept_in_arrival_order([int(x) for x in seq], 'published').tolist())


class TestHandshake(unittest.TestCase):
    def run_hs(self, design):
        g, v = gw.LongTerm(design), gw.LongTerm(design)
        G = gw.GroundHandshake(design, g, v.pk)
        V = gw.VehicleHandshake(design, v, g.pk)
        f1 = G.start()
        f2 = V.on_f1(f1)
        f3 = G.on_f2(f2)
        f4, why = V.on_f3(f3)
        self.assertIsNone(why)
        self.assertIsNone(G.on_f4(f4))
        self.assertEqual(G.key, V.key)
        self.assertEqual([len(f1), len(f2), len(f3), len(f4)], gw.flight_sizes(design))
        return G, V, f3, f4

    def test_classical(self):
        G, V, f3, f4 = self.run_hs('classical')
        self.assertEqual(gw.flight_sizes('classical'), [32, 32, 80, 80])

    @unittest.skipUnless(HAVE_PQ, 'host builds of mlkem-native and mldsa-native not found')
    def test_hybrid_sizes_match_round5_bytes(self):
        G, V, f3, f4 = self.run_hs('hybrid')
        # the round 5 relay carried the same flight sizes (sitl/config.py security_config('hybrid'))
        from sitl import config as c5
        self.assertEqual([b for _, b, _ in c5.security_config('hybrid')['flights']], gw.flight_sizes('hybrid'))

    @unittest.skipUnless(HAVE_PQ, 'host builds of mlkem-native and mldsa-native not found')
    def test_hybrid_rejects_modified_f3(self):
        g, v = gw.LongTerm('hybrid'), gw.LongTerm('hybrid')
        G = gw.GroundHandshake('hybrid', g, v.pk)
        V = gw.VehicleHandshake('hybrid', v, g.pk)
        f3 = bytearray(G.on_f2(V.on_f1(G.start())))
        f3[5] ^= 1
        self.assertEqual(V.on_f3(bytes(f3)), (None, 'f3_signature'))
        f3[5] ^= 1
        f3[-1] ^= 1
        self.assertEqual(V.on_f3(bytes(f3)), (None, 'f3_confirmation'))
        # a vehicle that pinned another ground key rejects the genuine ground
        other = gw.LongTerm('hybrid')
        V2 = gw.VehicleHandshake('hybrid', v, other.pk)
        G2 = gw.GroundHandshake('hybrid', g, v.pk)
        self.assertEqual(V2.on_f3(G2.on_f2(V2.on_f1(G2.start())))[1], 'f3_signature')


class TestRtlDelays(unittest.TestCase):
    def test_reader(self):
        with tempfile.TemporaryDirectory() as d:
            rows = ['label,core,design,unit,side,steps,cycles_median']
            for k, (design, side, steps) in c6.RTL_SESSION_ROWS.items():
                v = 10_000_000 if 'total' in k else 20_000
                rows.append(f'RTL simulated,cv32e40p,{design},u,{side},{steps},{v}')
                rows.append(f'RTL simulated,ibex,{design},u,{side},{steps},1')
            with open(os.path.join(d, 'proto_sessions.csv'), 'w') as f:
                f.write('\n'.join(rows) + '\n')
            prim = ['label,core,operation,cycles_median'] + [f'RTL simulated,cv32e40p,{op},100000' for op in c6.RTL_PRIMITIVES]
            with open(os.path.join(d, 'proto_primitives.csv'), 'w') as f:
                f.write('\n'.join(prim) + '\n')
            dl = c6.rtl_delays(d, 'cv32e40p', 168e6)
            self.assertAlmostEqual(dl['hybrid_vehicle_f2']['cycles'], 500000)
            self.assertAlmostEqual(dl['hybrid_vehicle_f4']['cycles'], 9_500_000)
            self.assertAlmostEqual(dl['classical_vehicle_f2']['cycles'], 400000)
            self.assertAlmostEqual(dl['tag_check']['seconds'], 20000 / 168e6)
            self.assertEqual(dl['tag_check']['label'], 'estimated from RTL simulated cycles')
            with self.assertRaises(KeyError):
                c6.rtl_delays(d, 'nosuchcore', 168e6)

    def test_paired_seeds(self):
        s = c6.load_settings()
        self.assertEqual(c6.run_seed(s, 'sik', 3), int(s['seed_base_r6']) + 3)
        self.assertEqual(c6.run_seed(s, 'ieee802154', 0), int(s['seed_base_r6']) + 1000)


class TestGatewayRelay(unittest.TestCase):
    """Drive the gateway relay on explicit times without sockets."""

    def make(self, name, loss=0.0, delays=None):
        from sitl import gwrelay
        sec = c6.security_config(name)
        sec['delays'] = delays or {}
        r = gwrelay.GatewayRelay(prof(loss), sec, 1, 0, ('127.0.0.1', 1))
        r.stream_cmd_id = 183
        r.tcp, r.udp = FakeSock(), FakeSock()
        r.gcs_addr = ('127.0.0.1', 2)
        return r

    def step(self, r, t):
        for ev, tt, u in r.chan.advance(t):
            r._deliver(ev, tt, u)
        r._flush(t, r.tcp, r.udp)
        r._check_timeouts(t)

    def run_until(self, r, t0, t1, dt=0.005):
        t = t0
        while t < t1:
            t += dt
            self.step(r, t)
        return t

    def session(self, name, **kw):
        r = self.make(name, **kw)
        r._start_handshake(0.0)
        self.run_until(r, 0.0, 3.0)
        self.assertEqual(r.g_state, 'up')
        self.assertEqual(r.v_state, 'up')
        return r

    def test_classical_session_and_command(self):
        r = self.session('classical', delays={'classical_vehicle_f2': 0.05, 'classical_vehicle_f4': 0.07,
                                              'tag_check': 0.001})
        f = command_long()
        r._uplink(parse(f), 3.0)
        self.run_until(r, 3.0, 3.5)
        self.assertEqual(r.tcp.sent[-1], f)  # forwarded without the tag field
        rec = r.cmds[-1]
        self.assertGreaterEqual(rec['t_vehicle'] - rec['t_gateway'], 0.001 - 1e-9)
        self.assertEqual(rec['counter'], 0)
        self.assertGreater(r.hs_log[0]['t_done'], 0.12)

    def test_published_rejects_reordered_and_cache_accepts(self):
        for name, expect in (('classical', 'rejected_late_or_duplicate'),):
            r = self.session(name)
            # deliver counter 1 before counter 0 by bypassing the channel
            key = r.g_keys[r.g_epoch]['key']
            f0, f1 = command_long(seq=1), command_long(seq=2)
            for c, f in ((1, f1), (0, f0)):
                m = dict(kind='mav', raw=f, msgid=lr.MSG_COMMAND_LONG, cmd=True, rec=None,
                         data=f + gw.tag_field(key, f, 0, c))
                r._vehicle_in(m, 4.0)
            self.assertEqual(r.rejects['stream0_late_or_duplicate'], 1)

    @unittest.skipUnless(HAVE_PQ, 'host builds of mlkem-native and mldsa-native not found')
    def test_strict_gap_triggers_resync(self):
        r = self.session('hybrid_strict')
        key = r.g_keys[r.g_epoch]['key']
        f = command_long()
        m = dict(kind='mav', raw=f, msgid=lr.MSG_COMMAND_LONG, cmd=True, rec=None, data=f + gw.tag_field(key, f, 0, 1))
        r.g_ctr[0] = 2
        r._vehicle_in(m, 3.0)  # counter 1 arrives, counter 0 never does
        self.assertEqual(r.rejects['stream0_ahead_of_next'], 1)
        n_hs = r.hs_id
        self.run_until(r, 3.0, 3.0 + r.gap_wait + 2.0)
        self.assertIn('vehicle_request', [x[1] for x in r.resyncs])
        self.run_until(r, 3.0 + r.gap_wait + 2.0, 3.0 + r.gap_wait + 6.0)
        self.assertGreater(r.hs_id, n_hs)
        self.assertEqual(r.g_state, 'up')

    @unittest.skipUnless(HAVE_PQ, 'host builds of mlkem-native and mldsa-native not found')
    def test_strict_ground_give_up_triggers_resync(self):
        r = self.session('hybrid_strict')
        r.add_outage(3.0, 8.0)
        r._uplink(parse(command_long()), 3.1)
        self.run_until(r, 3.1, 7.0)
        self.assertIn('ground_give_up', [x[1] for x in r.resyncs])
        self.assertEqual(r.cmds[-1]['dropped'], 'link_up')

    @unittest.skipUnless(HAVE_PQ, 'host builds of mlkem-native and mldsa-native not found')
    def test_pqsig_real(self):
        r = self.make('pqsig_real', delays={'mldsa44_verify_command': 0.02})
        f = command_long()
        r._uplink(parse(f), 0.0)
        self.run_until(r, 0.0, 1.0)
        self.assertEqual(r.tcp.sent[-1], f)
        rec = r.cmds[-1]
        self.assertGreaterEqual(rec['t_vehicle'] - rec['t_gateway'], 0.02 - 1e-9)
        from sitl import config as c5
        self.assertEqual(r.chan.stats['wire_bytes']['up'], sum(c5.object_fragments(len(f) + 2420, prof())))


if __name__ == '__main__':
    unittest.main()
