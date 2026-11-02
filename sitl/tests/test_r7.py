"""Tests of the round 7 additions: the two state loss process of the emulated link, the Falcon-512 per command
helpers of the gateway and the round 7 configurations. The Falcon-512 tests need the host build of
sitl/pqlib/build.sh (SITL_PQLIB); they are skipped when it is absent, and CI fails on any skip. Author: Huda Mueen."""
import random
import unittest

from sitl import config_r7 as c7
from sitl import gateway as gw
from sitl import linkrelay as lr
from sitl import pqcrypto

HAVE_FALCON = pqcrypto.falcon_available()


def prof(loss=0.02, burst=None):
    p = dict(name='t', rate=57600.0, cap=None, wire_extra=0, loss=loss, rto=0.1, max_retries=20, turnaround=0.05)
    if burst is not None:
        p['burst'] = burst
    return p


def lost_pattern(ch, n):
    for _ in range(n):
        ch.submit('down', [40], False, {}, 0.0)
    ev = ch.advance(1e9)
    ev.sort(key=lambda e: e[1])
    return [e == 'failed' for e, _, _ in ev]


class TestIndependentLossUnchanged(unittest.TestCase):
    def test_same_draws_as_round_6(self):
        # without a 'burst' entry every frame takes exactly one draw: lost when the draw is below the loss
        n, seed = 3000, 20311021
        got = lost_pattern(lr.Channel(prof(loss=0.2), seed), n)
        rng = random.Random(seed)
        self.assertEqual(got, [rng.random() < 0.2 for _ in range(n)])

    def test_no_burst_statistics(self):
        ch = lr.Channel(prof(), 1)
        self.assertNotIn('burst_lost_frames', ch.stats)
        ch.reset_burst_state()
        self.assertFalse(ch.bad)


class TestBurstLoss(unittest.TestCase):
    def test_parameters(self):
        b = c7.burst_params(0.02, 5)
        self.assertAlmostEqual(b['p_bg'], 0.2)
        self.assertAlmostEqual(b['p_gb'] / (b['p_gb'] + b['p_bg']), 0.02)

    def test_mean_loss_and_burst_length(self):
        b = c7.burst_params(0.02, 5)
        ch = lr.Channel(prof(burst=b), 20261021)
        ch.reset_burst_state()
        pat = lost_pattern(ch, 400000)
        loss = sum(pat) / len(pat)
        self.assertLess(abs(loss - 0.02), 0.003)
        runs, cur = [], 0
        for x in pat:
            if x:
                cur += 1
            elif cur:
                runs.append(cur)
                cur = 0
        self.assertLess(abs(sum(runs) / len(runs) - 5.0), 0.5)
        self.assertEqual(ch.stats['burst_lost_frames'], sum(pat))
        self.assertEqual(ch.stats['outage_lost_frames'], 0)

    def test_outage_frames_counted_apart(self):
        ch = lr.Channel(prof(burst=c7.burst_params(0.02, 5)), 3)
        ch.add_outage(0.0, 1e9)
        lost_pattern(ch, 100)
        self.assertEqual(ch.stats['outage_lost_frames'], 100)
        self.assertEqual(ch.stats['burst_lost_frames'], 0)

    def test_paired_by_seed(self):
        b = c7.burst_params(0.02, 5)
        a1, a2 = lr.Channel(prof(burst=b), 9), lr.Channel(prof(burst=b), 9)
        for ch in (a1, a2):
            ch.rng.seed(42)
            ch.reset_burst_state()
        self.assertEqual(lost_pattern(a1, 5000), lost_pattern(a2, 5000))

    def test_profile(self):
        p = prof()
        self.assertIs(c7.link_profile(p, 'independent'), p)
        self.assertAlmostEqual(c7.link_profile(p, 'burst')['burst']['mean_loss'], 0.02)
        with self.assertRaises(ValueError):
            c7.link_profile(p, 'other')


class TestRound7Configs(unittest.TestCase):
    def test_falcon_configs(self):
        d = {'falcon512_verify_command': dict(seconds=0.001)}
        s = c7.security_config('pqsig_falcon', d)
        self.assertTrue(s['pqsig'])
        self.assertEqual((s['pqsig_alg'], s['cmd_extra_bytes'], s['cmd_delay_s']), ('falcon512', 666, 0.001))
        s = c7.security_config('pqsig_falcon_counter', d)
        self.assertEqual((s['pq_counter'], s['rule'], s['cmd_extra_bytes']), (True, 'published', 672))

    def test_round6_configs_unchanged(self):
        from sitl import config_r6 as c6
        for k in c6.CONFIGS:
            self.assertEqual(c7.security_config(k), c6.security_config(k))

    def test_sets(self):
        self.assertEqual(c7.SETS['burst20']['configs'], c7.SETS['large100']['configs'])
        self.assertIn('pqsig_falcon', c7.BURST_SET)
        self.assertEqual(c7.load_settings()['missions_large_r7'], 100)


@unittest.skipUnless(HAVE_FALCON, 'host build of Falcon-512 not found')
class TestFalconGateway(unittest.TestCase):
    def test_sign_verify(self):
        pk, sk = pqcrypto.falcon512_keypair()
        sig = pqcrypto.falcon512_sign(b'command', sk)
        self.assertEqual(len(sig), 666)
        self.assertTrue(pqcrypto.falcon512_verify(sig, b'command', pk))
        self.assertFalse(pqcrypto.falcon512_verify(sig, b'commanD', pk))
        self.assertFalse(pqcrypto.falcon512_verify(sig[:-1], b'command', pk))

    def test_counter_seal_open(self):
        pk, sk = pqcrypto.falcon512_keypair()
        data = gw.pqsig_counter_seal(b'\xfd' + b'x' * 43, 77, sk, 'falcon512')
        self.assertEqual(len(data), 44 + 6 + 666)
        ok, frame, c = gw.pqsig_counter_open(data, pk, 'falcon512')
        self.assertEqual((ok, frame, c), (True, b'\xfd' + b'x' * 43, 77))
        bad = bytearray(data)
        bad[45] ^= 1
        self.assertFalse(gw.pqsig_counter_open(bytes(bad), pk, 'falcon512')[0])


if __name__ == '__main__':
    unittest.main()
