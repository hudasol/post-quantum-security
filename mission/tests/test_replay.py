"""Tests of the replay acceptance rules of the mission model (python3 -m unittest discover -s mission -t .)."""
import os
import unittest

import numpy as np
import pandas as pd

from mission import replay, sim

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(os.path.dirname(HERE), 'results')


class TestAcceptance(unittest.TestCase):
    def test_published_rejects_late_and_duplicate(self):
        acc = replay.accept_in_arrival_order([0, 2, 1, 2, 3], 'published')
        self.assertEqual(acc.tolist(), [True, True, False, False, True])

    def test_cache_accepts_late_inside_window(self):
        acc = replay.accept_in_arrival_order([0, 2, 1, 2, 3], 'cache', 4)
        self.assertEqual(acc.tolist(), [True, True, True, False, True])
        # outside the window: highest 10, window 4 accepts only counters above 6
        acc = replay.accept_in_arrival_order([10, 6, 7], 'cache', 4)
        self.assertEqual(acc.tolist(), [True, False, True])

    def test_cache_window_one_equals_published(self):
        rng = np.random.default_rng(1)
        seq = rng.permutation(50).tolist() + [3, 7]
        a = replay.accept_in_arrival_order(seq, 'cache', 1)
        b = replay.accept_in_arrival_order(seq, 'published')
        self.assertEqual(a.tolist(), b.tolist())

    def test_given_up_needs_outage(self):
        start = np.array([0.0, 10.0])
        att = np.array([[1], [1]])
        gu, t_gu = replay.given_up(start, att, 0.1, 20, np.array([9.9]), np.array([20.0]))
        self.assertEqual(gu.tolist(), [False, True])
        self.assertAlmostEqual(t_gu[1], 10.0 + 21 * 0.1)

    def test_strict_stall_until_resync(self):
        t = np.arange(10.0)
        sent = np.ones(10, bool)
        gu = np.zeros(10, bool)
        gu[3] = True
        t_gu = t + 2.0
        rej, n, stall = replay.strict_rejections(t, sent, gu, t_gu, np.zeros(0), np.zeros(0), np.zeros(0),
                                                 np.zeros(0), lambda: 1.5)
        # stall from t=3 to 3 + 2 + 1.5 = 6.5: commands 4, 5, 6 rejected
        self.assertEqual(np.flatnonzero(rej).tolist(), [4, 5, 6])
        self.assertEqual(n, 1)
        self.assertAlmostEqual(stall, 3.5)

    def test_strict_teardown_handshake_ends_stall_earlier(self):
        t = np.arange(10.0)
        gu = np.zeros(10, bool)
        gu[1] = True
        rej, n, _ = replay.strict_rejections(t, np.ones(10, bool), gu, t + 2.0, np.zeros(0), np.zeros(0),
                                             np.array([2.5]), np.array([4.2]), lambda: 10.0)
        self.assertEqual(np.flatnonzero(rej).tolist(), [2, 3, 4])


class TestPairedRuns(unittest.TestCase):
    def test_published_rule_unchanged_and_paired(self):
        res0, _ = sim.run_config('drone', 'B', 'sik', 30, [0.5], key_extra='test')
        res1, _ = sim.run_config('drone', 'B', 'sik', 30, [0.5], key_extra='test', replay_rule='published')
        res2, _ = sim.run_config('drone', 'B', 'sik', 30, [0.5], key_extra='test', replay_rule='strict')
        for a, b, c in zip(res0, res1, res2):
            self.assertEqual(a['avail'], b['avail'])
            self.assertEqual(a['avail'], b['avail_rule_published'])
            self.assertEqual(b['avail_rule_cache_W64'], b['avail_rule_published'])
            self.assertEqual(c['avail'], b['avail_rule_strict'])
            self.assertLessEqual(c['avail'], a['avail'])
            self.assertEqual(a['n_outages'], c['n_outages'])

    def test_rule_keys(self):
        self.assertEqual(replay.rule_key('cache', 8), 'cache_W8')
        self.assertEqual(replay.rule_key('strict'), 'strict')
        with self.assertRaises(ValueError):
            replay.rule_key('other')

    def test_result_files(self):
        path = os.path.join(RES, 'replay_regeneration_check.csv')
        if not os.path.exists(path):
            self.skipTest('replay results not generated')
        chk = pd.read_csv(path)
        self.assertTrue(chk.identical.all())
        rb = pd.read_csv(os.path.join(RES, 'replay_base.csv'))
        self.assertEqual(set(rb.replay_rule), {'published', 'strict', 'cache'})
        self.assertTrue((rb.label == 'estimated').all())
        s = rb[(rb.replay_rule == 'strict')]
        self.assertTrue((s.diff_vs_published_mean <= 0).all())


if __name__ == '__main__':
    unittest.main()
