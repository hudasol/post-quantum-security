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


@unittest.skipUnless(HAVE_PQ, 'host builds of mlkem-native and mldsa-native not found')
class TestKemAuth(unittest.TestCase):
    """Design K (kem_auth) against the executed C reference (rtlsim/proto/sw/proto_bench.c)."""

    def run_hs(self):
        g, v = gw.LongTerm('kem_auth'), gw.LongTerm('kem_auth')
        G = gw.KemAuthGround(g, v.pk)
        V = gw.KemAuthVehicle(v, g.pk)
        f1 = G.start()
        f2 = V.on_f1(f1)
        f3, why = G.on_f2(f2)
        self.assertIsNone(why)
        self.assertIsNone(V.on_f3(f3))
        return g, v, G, V, f1, f2, f3

    def test_session_and_sizes_match_rtl(self):
        g, v, G, V, f1, f2, f3 = self.run_hs()
        self.assertEqual(G.key, V.key)
        self.assertEqual(G.th, V.th)
        self.assertTrue(G.accepted and V.accepted)
        self.assertEqual([len(f1), len(f2), len(f3)], gw.flight_sizes('kem_auth'))
        self.assertEqual(gw.flight_sizes('kem_auth'), [2304, 2224, 16])
        import csv
        with open(os.path.join(c6.ROOT, 'rtlsim', 'results', 'proto_sessions.csv'), newline='') as f:
            rows = [r for r in csv.DictReader(f) if r['design'] == 'kem_auth']
        self.assertTrue(rows)
        for r in rows:
            self.assertEqual(r['bytes_per_flight'], 'F1 ground_to_vehicle 2304; F2 vehicle_to_ground 2224; F3 ground_to_vehicle 16')

    def test_key_derivation_matches_known_answer(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('gen_kat', os.path.join(c6.ROOT, 'rtlsim', 'proto', 'gen_kat.py'))
        kat = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(kat)
        self.assertEqual(gw.ka_kdf(kat.KDF_SSX, kat.KDF_SSKEM, kat.KDF_SSKEM2, kat.KDF_SSKEM3, kat.KDF_TH),
                         kat.kdf4(kat.KDF_SSX, kat.KDF_SSKEM, kat.KDF_SSKEM2, kat.KDF_SSKEM3, kat.KDF_TH))
        self.assertEqual((gw.LABEL_TH, gw.LABEL_KDF, gw.LABEL_CG, gw.LABEL_CV, gw.LABEL_ID),
                         tuple(kat.LABELS[k] for k in ('LABEL_TH', 'LABEL_KDF', 'LABEL_CG', 'LABEL_CV', 'LABEL_ID')))

    def test_transcript_and_key_layout(self):
        g, v, G, V, f1, f2, f3 = self.run_hs()
        body = f2[:-16]
        self.assertEqual(G.th, gw.shake256(gw.LABEL_TH + g.id + v.id + f1 + body, 32))
        self.assertEqual(f2[-16:], gw.shake256(G.key + gw.LABEL_CV + G.th, 16))
        self.assertEqual(f3, gw.shake256(G.key + gw.LABEL_CG + G.th, 16))

    def test_negative_checks_of_the_reference(self):
        g, v, G, V, f1, f2, f3 = self.run_hs()
        bad = bytearray(f3)
        bad[0] ^= 1
        V2 = gw.KemAuthVehicle(v, g.pk)
        G2 = gw.KemAuthGround(g, v.pk)
        f2b = V2.on_f1(G2.start())
        self.assertEqual(V.on_f3(bytes(bad)), 'f3_confirmation')
        t = bytearray(f2b)
        t[gw.KA_F2_BODY] ^= 1
        self.assertEqual(G2.on_f2(bytes(t)), (None, 'f2_confirmation'))
        t = bytearray(f2b)
        t[32 + 1088 + 3] ^= 1  # ciphertext to the ground static key
        self.assertEqual(G2.on_f2(bytes(t)), (None, 'f2_confirmation'))
        self.assertIsNone(G2.on_f2(f2b)[1])
        # an F1 whose ciphertext to the vehicle static key was replaced by a third party
        G3 = gw.KemAuthGround(g, v.pk)
        f1c = G3.start()
        ct, _ = pqcrypto.mlkem768_enc(v.pk)
        V3 = gw.KemAuthVehicle(v, g.pk)
        f2c = V3.on_f1(f1c[:32 + 1184] + ct)
        self.assertEqual(G3.on_f2(f2c), (None, 'f2_confirmation'))
        # a vehicle that pinned another ground key does not derive the ground key
        other = gw.LongTerm('kem_auth')
        G4 = gw.KemAuthGround(g, v.pk)
        V4 = gw.KemAuthVehicle(v, other.pk)
        self.assertEqual(G4.on_f2(V4.on_f1(G4.start())), (None, 'f2_confirmation'))


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

    def test_kem_auth_delays_from_the_15_run_files(self):
        rtl = os.path.join(c6.ROOT, 'rtlsim', 'results')
        dl = c6.rtl_delays(rtl, 'ibex', 168e6, kem_auth=True)
        self.assertEqual(dl['kem_auth_vehicle_total']['cycles'], 17391267)
        self.assertAlmostEqual(dl['kem_auth_vehicle_f2']['cycles'] + dl['kem_auth_vehicle_accept']['cycles'], 17391267)
        # the accept step is one confirmation tag (42971 cycles) and its comparison
        self.assertTrue(42971 <= dl['kem_auth_vehicle_accept']['cycles'] < 50000)
        self.assertAlmostEqual(dl['kem_auth_vehicle_f2']['seconds'], dl['kem_auth_vehicle_f2']['cycles'] / 168e6)
        with tempfile.TemporaryDirectory() as d:
            for fn in ('proto_sessions', 'proto_primitives'):
                with open(os.path.join(rtl, fn + '_runs5.csv')) as f, open(os.path.join(d, fn + '.csv'), 'w') as g:
                    g.write(f.read())
            # the per message delays are the same in the five run snapshot and in the 15 run files
            d5 = c6.rtl_delays(d, 'ibex', 168e6)
            for k in ('tag_check', 'tag_make'):
                self.assertEqual(dl[k]['cycles'], d5[k]['cycles'])
            # the snapshot has no design K rows
            with self.assertRaises(KeyError):
                c6.rtl_delays(d, 'ibex', 168e6, kem_auth=True)

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
    def test_kem_auth_session_and_command(self):
        sec = c6.security_config('kem_auth')
        self.assertEqual((sec['design'], sec['rule'], sec['session'], sec['tag_bytes']), ('kem_auth', 'published', True, 13))
        r = self.session('kem_auth', delays={'kem_auth_vehicle_f2': 0.1, 'kem_auth_vehicle_accept': 0.01,
                                             'tag_check': 0.001})
        log = r.hs_log[0]
        self.assertIsNotNone(log['t_ground_accept'])
        self.assertGreater(log['t_done'], log['t_ground_accept'])
        self.assertEqual(r.hs_times[0][2], log['t_done'])
        self.assertGreaterEqual(r.chan.stats['wire_bytes']['down'], 2224)
        f = command_long()
        r._uplink(parse(f), 3.0)
        self.run_until(r, 3.0, 3.5)
        self.assertEqual(r.tcp.sent[-1], f)
        self.assertEqual(r.cmds[-1]['counter'], 0)
        self.assertEqual(set(r.host), {'ground_f1', 'vehicle_f2', 'ground_f3', 'vehicle_accept', 'ground_tag',
                                       'vehicle_tag_check'})

    @unittest.skipUnless(HAVE_PQ, 'host builds of mlkem-native and mldsa-native not found')
    def test_kem_auth_second_handshake_waits_for_the_vehicle(self):
        # the runner starts a new handshake per mission while the previous session is up; the session counts as
        # up again only when the vehicle has accepted the new F3, and that handshake time is recorded
        r = self.session('kem_auth', delays={'kem_auth_vehicle_f2': 0.1, 'kem_auth_vehicle_accept': 0.05})
        self.assertTrue(r.session_up())
        r._start_handshake(3.0)
        t = 3.0
        seen_ground_only = False
        while not r.session_up():
            t += 0.005
            self.step(r, t)
            seen_ground_only |= r.g_state == 'up' and r.v_state == 'up'
        self.assertTrue(seen_ground_only)
        self.assertEqual(len(r.hs_times), 2)
        self.assertEqual(r.hs_times[-1][0], r.hs_id)
        self.assertGreaterEqual(r.hs_times[-1][2] - r.hs_log[-1]['t_ground_accept'], 0.05 - 1e-9)

    @unittest.skipUnless(HAVE_PQ, 'host builds of mlkem-native and mldsa-native not found')
    def test_kem_auth_f3_give_up_restarts(self):
        r = self.make('kem_auth')
        r._start_handshake(0.0)
        # cut the link after F2 has reached the ground, so that F3 is given up
        t = 0.0
        while r.g_state != 'up':
            t += 0.005
            self.step(r, t)
        r.add_outage(t, t + 10.0)
        self.run_until(r, t, t + 9.0)
        self.assertIn('retry_after_give_up', [h['reason'] for h in r.hs_log])

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


class TestInbandMessages(unittest.TestCase):
    """Messages of the in band resynchronisation and the strict rule counter move (hybrid_strict_inband)."""

    def test_messages_roundtrip_and_forgeries(self):
        key, other = bytes(range(32)), bytes(32)
        for kind, make in (('set', gw.resync_set), ('ack', gw.resync_ack), ('request', gw.resync_request_msg)):
            msg = make(key, 41)
            self.assertEqual(len(msg), gw.RESYNC_BYTES)
            self.assertEqual(gw.open_resync(key, kind, msg), 41)
            self.assertIsNone(gw.open_resync(other, kind, msg))
            bad = bytearray(msg)
            bad[0] ^= 1  # counter changed, tag kept
            self.assertIsNone(gw.open_resync(key, kind, bytes(bad)))
            bad = bytearray(msg)
            bad[-1] ^= 1
            self.assertIsNone(gw.open_resync(key, kind, bytes(bad)))
        # the request has the layout of the strict rule request; a message of one kind is not valid as another
        self.assertEqual(gw.resync_request_msg(key, 7)[8:], gw.resync_request(key, 7))
        self.assertIsNone(gw.open_resync(key, 'ack', gw.resync_set(key, 41)))
        self.assertIsNone(gw.open_resync(key, 'set', gw.resync_ack(key, 41)))
        self.assertIsNone(gw.open_resync(key, 'set', gw.resync_request_msg(key, 41)))

    def test_set_next_moves_forward_only(self):
        a = gw.Acceptor('strict')
        self.assertEqual([a.accept(c)[0] for c in (0, 1, 3)], [True, True, False])
        self.assertTrue(a.gap())
        self.assertTrue(a.set_next(4))
        self.assertFalse(a.gap())
        self.assertEqual(a.accept(4), (True, None))
        self.assertFalse(a.set_next(2))  # an old set message does not reopen accepted counters
        self.assertEqual(a.accept(3), (False, 'behind_next'))
        self.assertEqual(a.accept(5), (True, None))

    def test_security_configs_of_the_added_designs(self):
        s = c6.security_config('hybrid_strict_inband')
        self.assertEqual((s['design'], s['rule'], s['session'], s['inband']), ('hybrid', 'strict', True, True))
        s = c6.security_config('pqsig_counter')
        self.assertEqual((s['pqsig'], s['pq_counter'], s['rule'], s['session']), (True, True, 'published', False))
        self.assertEqual(s['cmd_extra_bytes'], c6.security_config('pqsig_real')['cmd_extra_bytes'] + 6)
        self.assertNotIn('inband', c6.security_config('hybrid_strict'))


@unittest.skipUnless(HAVE_PQ, 'host builds of mlkem-native and mldsa-native not found')
class TestPqsigCounter(unittest.TestCase):
    def test_seal_open_and_tamper(self):
        pk, sk = pqcrypto.mldsa44_keypair()
        f = command_long()
        data = gw.pqsig_counter_seal(f, 300, sk)
        self.assertEqual(len(data), len(f) + 6 + pqcrypto.MLDSA44_SIG)
        self.assertEqual(gw.pqsig_counter_open(data, pk), (True, f, 300))
        bad = bytearray(data)
        bad[len(f)] ^= 1  # counter changed after signing
        self.assertFalse(gw.pqsig_counter_open(bytes(bad), pk)[0])


class TestAddedConfigsRelay(TestGatewayRelay):
    """Gateway relay with in band resynchronisation (hybrid_strict_inband) and ML-DSA-44 with a counter."""

    def command_with(self, r, key, c, seq=5):
        f = command_long(seq=seq)
        return dict(kind='mav', raw=f, msgid=lr.MSG_COMMAND_LONG, cmd=True, rec=None, data=f + gw.tag_field(key, f, 0, c))

    @unittest.skipUnless(HAVE_PQ, 'host builds of mlkem-native and mldsa-native not found')
    def test_inband_gap_resynchronises_without_a_handshake(self):
        r = self.session('hybrid_strict_inband', delays={'tag_check': 0.001, 'tag_make': 0.001})
        key = r.g_keys[r.g_epoch]['key']
        r.g_ctr[0] = 2
        r._vehicle_in(self.command_with(r, key, 1), 3.0)  # counter 1 arrives, counter 0 never does
        self.assertEqual(r.rejects['stream0_ahead_of_next'], 1)
        n_hs, n_epoch = r.hs_id, r.v_epoch
        self.run_until(r, 3.0, 3.0 + r.gap_wait + 2.0)
        self.assertEqual([x[1] for x in r.resyncs], ['vehicle_request'])
        self.assertEqual((r.hs_id, r.v_epoch), (n_hs, n_epoch))  # same session, same key
        acc = r.v_keys[r.v_epoch]['acc'][0]
        self.assertEqual(acc.hi, 1)  # next expected counter is 2, the next one the ground sends
        self.assertFalse(acc.gap())
        n_sent = len(r.tcp.sent)
        f = command_long(seq=9)
        r._uplink(parse(f), 6.0)
        self.run_until(r, 6.0, 6.5)
        self.assertEqual(r.tcp.sent[n_sent:][-1], f)
        self.assertEqual(r.cmds[-1]['counter'], 2)
        events = [e[0] for e in r.session_events]
        self.assertIn('resync_inband_applied', events)
        self.assertNotIn('resync_inband_acknowledged', events)  # the answer to a request is not acknowledged
        self.assertIn('vehicle_resync_tag', r.host)
        self.assertIn('vehicle_resync_check', r.host)

    @unittest.skipUnless(HAVE_PQ, 'host builds of mlkem-native and mldsa-native not found')
    def test_inband_ground_give_up_resynchronises_and_is_acknowledged(self):
        r = self.session('hybrid_strict_inband')
        n_hs = r.hs_id
        r.add_outage(3.0, 8.0)
        r._uplink(parse(command_long()), 3.1)
        self.run_until(r, 3.1, 9.5)
        self.assertIn('ground_give_up', [x[1] for x in r.resyncs])
        self.assertEqual(r.cmds[-1]['dropped'], 'link_up')
        self.assertEqual(r.hs_id, n_hs)
        self.assertIn('resync_inband_acknowledged', [e[0] for e in r.session_events])
        self.assertIsNone(r.g_set_out)
        # one set message at a time: the first is given up inside the outage and sent again once, no duplicates
        self.assertEqual([e[0] for e in r.session_events].count('resync_set_sent'), 2)
        self.assertEqual(r.rejects['bad_resync_set'], 0)
        f = command_long(seq=11)
        r._uplink(parse(f), 9.5)
        self.run_until(r, 9.5, 10.0)
        self.assertEqual(r.tcp.sent[-1], f)

    @unittest.skipUnless(HAVE_PQ, 'host builds of mlkem-native and mldsa-native not found')
    def test_inband_forged_messages_rejected(self):
        r = self.session('hybrid_strict_inband')
        key = r.v_keys[r.v_epoch]['key']
        acc = r.v_keys[r.v_epoch]['acc'][0]
        hi = acc.hi
        # a set message under another key, and a genuine one with the counter changed
        r._vehicle_set(dict(kind='rset', data=gw.resync_set(bytes(32), 50)), 3.0)
        bad = bytearray(gw.resync_set(key, 50))
        bad[0] ^= 3
        r._vehicle_set(dict(kind='rset', data=bytes(bad)), 3.0)
        self.run_until(r, 3.0, 3.2)
        self.assertEqual(r.rejects['bad_resync_set'], 2)
        self.assertEqual(acc.hi, hi)
        # a forged request and a forged acknowledgement at the ground start nothing
        r._on_resync_request(dict(kind='rs', data=gw.resync_request_msg(bytes(32), 0)), 3.2)
        r._ground_ack(dict(kind='rack', data=gw.resync_ack(bytes(32), 0)), 3.2)
        self.assertEqual(r.down_rejects['bad_resync_request'], 1)
        self.assertEqual(r.down_rejects['bad_resync_ack'], 1)
        self.assertEqual(r.resyncs, [])
        # a replayed (old) genuine set message does not lower the next expected counter
        r._vehicle_in(self.command_with(r, r.g_keys[r.g_epoch]['key'], 0), 3.3)
        r._vehicle_set(dict(kind='rset', data=gw.resync_set(key, 0)), 3.4)
        self.run_until(r, 3.4, 3.6)
        self.assertEqual(acc.hi, 0)
        self.assertEqual(r._vehicle_in(self.command_with(r, r.g_keys[r.g_epoch]['key'], 0), 3.6), None)
        self.assertEqual(r.rejects['stream0_behind_next'], 1)

    @unittest.skipUnless(HAVE_PQ, 'host builds of mlkem-native and mldsa-native not found')
    def test_inband_long_outage_still_forces_a_handshake(self):
        r = self.session('hybrid_strict_inband')
        r.auto_rehandshake = True
        r.last_rx = {'up': 3.0, 'down': 3.0}
        # the outage outlasts the session timeout; the new handshake starts inside it and completes after it
        r.add_outage(3.0, 3.0 + r.sec['timeout_s'] + 1.5)
        self.run_until(r, 3.0, 3.0 + r.sec['timeout_s'] + 6.0, dt=0.01)
        self.assertIn('teardown', [h['reason'] for h in r.hs_log])
        self.assertEqual(r.g_state, 'up')
        # a set message that reaches a vehicle without a key is counted as such, not as a forgery
        r.v_keys.clear()
        r._vehicle_set(dict(kind='rset', data=gw.resync_set(r.g_keys[r.g_epoch]['key'], 3)), 30.0)
        self.assertEqual((r.rejects['resync_set_no_session_vehicle'], r.rejects['bad_resync_set']), (1, 0))

    @unittest.skipUnless(HAVE_PQ, 'host builds of mlkem-native and mldsa-native not found')
    def test_pqsig_counter_forwards_and_rejects_a_replay(self):
        r = self.make('pqsig_counter', delays={'mldsa44_verify_command': 0.02})
        f = command_long()
        r._uplink(parse(f), 0.0)
        self.run_until(r, 0.0, 1.0)
        self.assertEqual(r.tcp.sent[-1], f)
        rec = r.cmds[-1]
        self.assertEqual(rec['counter'], 0)
        self.assertGreaterEqual(rec['t_vehicle'] - rec['t_gateway'], 0.02 - 1e-9)
        from sitl import config as c5
        self.assertEqual(r.chan.stats['wire_bytes']['up'], sum(c5.object_fragments(len(f) + 6 + 2420, prof())))
        # replay of the recorded command: valid signature, counter not greater than the last accepted one
        data = gw.pqsig_counter_seal(f, 0, r.pq_sk)
        n_sent = len(r.tcp.sent)
        r._vehicle_in(dict(kind='mav', raw=f, msgid=lr.MSG_COMMAND_LONG, cmd=True, rec=None, data=data), 1.0)
        self.run_until(r, 1.0, 1.5)
        self.assertEqual(r.rejects['counter_late_or_duplicate'], 1)
        self.assertEqual(len(r.tcp.sent), n_sent)
        # a counter raised by a third party breaks the signature
        bad = bytearray(data)
        bad[len(f)] = 9
        r._vehicle_in(dict(kind='mav', raw=f, msgid=lr.MSG_COMMAND_LONG, cmd=True, rec=None, data=bytes(bad)), 1.5)
        self.assertEqual(r.rejects['bad_signature'], 1)
        # pqsig_real accepts the same replay (no counter)
        q = self.make('pqsig_real')
        sig = pqcrypto.mldsa44_sign(f, q.pq_sk)
        for t in (0.0, 0.1):
            q._vehicle_in(dict(kind='mav', raw=f, msgid=lr.MSG_COMMAND_LONG, cmd=True, rec=None, data=f + sig), t)
        self.run_until(q, 0.1, 0.5)
        self.assertEqual(q.tcp.sent.count(f), 2)


if __name__ == '__main__':
    unittest.main()
