"""Tests of the emulated link: rate, loss, retransmission, outages, fragmentation and MAVLink framing."""
import math
import struct
import unittest

from sitl import config as cfgmod
from sitl import linkrelay as lr


def prof(rate=57600.0, loss=0.0, rto=0.1, retries=20, cap=None, extra=0):
    return dict(name='t', rate=rate, cap=cap, wire_extra=extra, loss=loss, rto=rto, max_retries=retries, turnaround=0.05)


class TestChannel(unittest.TestCase):
    def test_rate(self):
        p = prof()
        ch = lr.Channel(p, seed=1)
        for _ in range(100):
            ch.submit('up', [72], True, {}, 0.0)
        ev = ch.advance(100.0)
        self.assertEqual(len(ev), 100)
        last = max(t for _, t, _ in ev)
        self.assertAlmostEqual(last, 100 * 72 * 8 / 57600.0, places=9)
        self.assertAlmostEqual(ch.stats['air_s']['up'], last, places=9)

    def test_profile_rates_from_params(self):
        sik = cfgmod.link_profile('sik')
        self.assertAlmostEqual(sik['rate'], 64000 * 0.9)
        z = cfgmod.link_profile('ieee802154')
        self.assertEqual(z['rate'], 250000)
        self.assertEqual(cfgmod.fragments(100, z), [127, 127])
        self.assertEqual(cfgmod.fragments(100, sik), [100])

    def test_unreliable_loss_rate(self):
        p = prof(loss=0.2)
        ch = lr.Channel(p, seed=20261021)
        n = 5000
        for _ in range(n):
            ch.submit('down', [40], False, {}, 0.0)
        ev = ch.advance(1e6)
        ok = sum(1 for e, _, _ in ev if e == 'delivered')
        # binomial 4 sigma bound around 1 - p
        sd = math.sqrt(n * 0.2 * 0.8)
        self.assertLess(abs(ok - n * 0.8), 4 * sd)
        self.assertEqual(ch.stats['retransmissions'], 0)

    def test_reliable_retransmission(self):
        p = prof(loss=0.2, rto=0.1)
        ch = lr.Channel(p, seed=7)
        n = 2000
        for _ in range(n):
            ch.submit('up', [40], True, {}, 0.0)
        ev = ch.advance(1e6)
        self.assertEqual(sum(1 for e, _, _ in ev if e == 'delivered'), n)
        # expected attempts per frame 1 / (1 - p)
        ratio = ch.stats['retransmissions'] / n
        self.assertLess(abs(ratio - 0.25), 0.05)

    def test_single_retransmission_delay(self):
        # deterministic: loss 1 then retries exhausted gives failure after max_retries + 1 sends
        p = prof(loss=1.0, rto=0.1, retries=3)
        ch = lr.Channel(p, seed=1)
        ch.submit('up', [72], True, {}, 0.0)
        ev = ch.advance(10.0)
        self.assertEqual([e for e, _, _ in ev], ['failed'])
        air = 72 * 8 / 57600.0
        self.assertAlmostEqual(ev[0][1], 4 * air + 3 * 0.1, places=9)
        self.assertEqual(ch.stats['frames'], 4)

    def test_outage_drops(self):
        p = prof(loss=0.0)
        ch = lr.Channel(p, seed=1)
        ch.add_outage(1.0, 2.0)
        ch.submit('down', [72], False, {}, 0.5)
        ch.submit('down', [72], False, {}, 1.5)
        ch.submit('down', [72], False, {}, 2.5)
        ev = ch.advance(10.0)
        self.assertEqual([e for e, _, _ in ev], ['delivered', 'failed', 'delivered'])

    def test_reliable_survives_outage(self):
        p = prof(loss=0.0, rto=0.1, retries=20)
        ch = lr.Channel(p, seed=1)
        ch.add_outage(0.0, 1.0)
        ch.submit('up', [72], True, {}, 0.0)
        ev = ch.advance(10.0)
        self.assertEqual(ev[0][0], 'delivered')
        self.assertGreaterEqual(ev[0][1], 1.0)

    def test_buffer_limit(self):
        p = prof()
        ch = lr.Channel(p, seed=1, queue_limit_bytes=100)
        self.assertIsNotNone(ch.submit('down', [60], False, {}, 0.0))
        self.assertIsNone(ch.submit('down', [60], False, {}, 0.0))
        self.assertIsNotNone(ch.submit('up', [60], True, {}, 0.0))
        self.assertEqual(ch.stats['buffer_drops'], 1)

    def test_shared_fifo(self):
        p = prof()
        ch = lr.Channel(p, seed=1)
        ch.submit('down', [576], False, {'k': 1}, 0.0)
        ch.submit('up', [72], True, {'k': 2}, 0.0)
        ev = ch.advance(10.0)
        self.assertEqual([u.meta['k'] for _, _, u in ev], [1, 2])
        self.assertAlmostEqual(ev[1][1], (576 + 72) * 8 / 57600.0)


class TestSecurityConfigs(unittest.TestCase):
    def test_pqsig_object(self):
        sik = cfgmod.link_profile('sik')
        sc = cfgmod.security_config('pqsig')
        self.assertEqual(sc['cmd_extra_bytes'], 2420)
        fr = cfgmod.object_fragments(45 + 2420, sik)
        self.assertEqual(len(fr), math.ceil(2465 / 239))
        self.assertEqual(sum(fr), 2465 + 24 * len(fr))
        self.assertGreater(sc['cmd_delay_s'], 0.005)

    def test_hybrid_flights(self):
        sc = cfgmod.security_config('hybrid')
        self.assertEqual([f[0] for f in sc['flights']], ['up', 'down', 'up', 'down'])
        self.assertEqual(sum(f[1] for f in sc['flights']), 1216 + 1120 + 2436 + 2436)
        self.assertEqual(sc['tag_bytes'], 13)

    def test_plain(self):
        for c in ('none', 'signing'):
            sc = cfgmod.security_config(c)
            self.assertEqual((sc['tag_bytes'], sc['cmd_extra_bytes'], sc['cmd_delay_s']), (0, 0, 0.0))


class TestFraming(unittest.TestCase):
    def frame2(self, msgid, payload, seq=5, signed=False):
        hdr = bytes([0xFD, len(payload), 1 if signed else 0, 0, seq, 1, 1]) + struct.pack('<I', msgid)[:3]
        return hdr + payload + b'\x00\x00' + (bytes(13) if signed else b'')

    def test_parse(self):
        pl = struct.pack('<7fHBBB', 1, 8, -1, 0, 0, 0, 0, 178, 1, 1, 0)
        a = self.frame2(76, pl)
        b = self.frame2(77, struct.pack('<HB', 178, 0), signed=True)
        frs, rest = lr.parse_frames(b'\x11' + a + b + a[:5])
        self.assertEqual([f['msgid'] for f in frs], [76, 77])
        self.assertEqual(rest, a[:5])
        self.assertEqual(lr.command_long_id(frs[0]['payload']), 178)
        self.assertEqual(lr.command_ack_fields(frs[1]['payload']), (178, 0))
        self.assertTrue(frs[1]['signed'])
        self.assertEqual(len(frs[1]['raw']), 12 + 3 + 13)

    def test_parse_v1(self):
        raw = bytes([0xFE, 2, 9, 1, 1, 0]) + b'ab' + b'\x00\x00'
        frs, rest = lr.parse_frames(raw)
        self.assertEqual(frs[0]['msgid'], 0)
        self.assertEqual(rest, b'')


if __name__ == '__main__':
    unittest.main()
