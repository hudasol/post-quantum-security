"""Tests of the round 6 analysis helpers (python3 -m unittest discover -s sitl -t .)."""
import unittest

import numpy as np
import pandas as pd

from sitl import analyse_r6 as an
from sitl import config_r6 as c6


class TestAnalyseR6(unittest.TestCase):
    def test_paired_boot_identical_is_zero(self):
        rng = np.random.default_rng(1)
        d = pd.DataFrame(dict(mission=np.repeat(np.arange(10), 20), accepted_rt=rng.random(200) < 0.9))
        v, lo, hi, n = an.paired_boot(d, d, an.share('accepted_rt'), 5)
        self.assertEqual((v, lo, hi, n), (0.0, 0.0, 0.0, 10))

    def test_paired_boot_sign(self):
        a = pd.DataFrame(dict(mission=np.repeat(np.arange(8), 10), accepted_rt=True))
        b = a.copy()
        b.loc[b.index % 10 == 0, 'accepted_rt'] = False
        v, lo, hi, n = an.paired_boot(a, b, an.share('accepted_rt'), 5)
        self.assertAlmostEqual(v, 0.1)
        self.assertAlmostEqual(lo, 0.1)
        self.assertAlmostEqual(hi, 0.1)

    def test_reorder_stats(self):
        arr = pd.DataFrame(dict(profile='sik', config='hybrid_cache', epoch=[1, 1, 1, 1, 2, 2],
                                counter=[0, 2, 1, 3, 0, 1]))
        r = an.reorder_stats(arr).iloc[0]
        self.assertEqual(r.arrivals_after_higher_counter, 1)
        self.assertEqual(r.max_reorder_depth, 1)

    def test_mission_model_values_per_rule(self):
        vals = {k: an.mission_model_value('sik', k)[2] for k in c6.FIRST}
        self.assertLessEqual(vals['hybrid_strict'], vals['hybrid_published'])
        self.assertEqual(vals['hybrid_cache'], vals['hybrid_published'])
        for v in vals.values():
            self.assertTrue(0 <= v <= 1)

    def test_missed_per_mission_removes_the_length_artefact(self):
        # configuration b sends one more command per mission than a, and it is acknowledged: the share moves, the
        # count of missed commands per mission does not
        rows = []
        for k, extra in (('hybrid_published', 0), ('hybrid_cache', 1)):
            for i in range(6):
                for j in range(20 + extra):
                    rows.append(dict(profile='sik', config=k, mission=i, accepted_rt=j >= 2))
        c = pd.DataFrame(rows)
        mis = pd.DataFrame([dict(profile='sik', config=k, mission=i, seed=100 + i, t_mission_start=10.0 * i)
                            for k in ('hybrid_published', 'hybrid_cache') for i in range(6)])
        runs = [dict(profile='sik', config=k, _events=pd.DataFrame(dict(event=['teardown_ground'], t=[25.0])),
                     gateway=dict(handshakes=[dict(reason='initial', t_start=0.0), dict(reason='teardown', t_start=26.0)],
                                  resyncs=[])) for k in ('hybrid_published', 'hybrid_cache')]
        mpm = an.missed_per_mission(c, mis, runs)
        self.assertEqual(set(mpm.missed), {2})
        self.assertEqual(mpm[mpm.mission == 2][['teardowns_emulated', 'rehandshakes_emulated']].values.tolist(), [[1, 1]] * 2)
        self.assertEqual(int(mpm.teardowns_emulated.sum()), 2)
        v, lo, hi, n = an.paired_boot(c[c.config == 'hybrid_cache'], c[c.config == 'hybrid_published'],
                                      an.share('accepted_rt'), 5)
        self.assertGreater(v, 0)
        pm = an.paired_missed(mpm, 0)
        r = pm[(pm.config == 'hybrid_cache') & (pm.minus_config == 'hybrid_published')].iloc[0]
        self.assertEqual((r.difference, r.ci_lo, r.ci_hi, r.missions_differing), (0.0, 0.0, 0.0, 0))
        self.assertEqual((r.commands_difference, r.acknowledged_difference), (1.0, 1.0))
        self.assertEqual(r.missions_acknowledged_change_equals_sent_change, 6)
        sr = an.session_restarts(mpm)
        self.assertEqual(sr.missions_with_teardown_or_rehandshake.tolist(), [1, 1])

    def test_paired_missed_mean_and_sign(self):
        mk = lambda k, vals: pd.DataFrame(dict(profile='sik', config=k, mission=range(len(vals)), missed=vals,
                                               commands=50, acknowledged=[50 - v for v in vals]))
        mpm = pd.concat([mk('hybrid_strict', [3, 5, 4, 0]), mk('hybrid_published', [1, 1, 1, 0])], ignore_index=True)
        r = an.paired_missed(mpm, 0).iloc[0]
        self.assertEqual((r.config, r.minus_config), ('hybrid_strict', 'hybrid_published'))
        self.assertAlmostEqual(r.difference, 2.25)
        self.assertEqual(r.missions_differing, 3)
        self.assertTrue(r.ci_lo <= r.difference <= r.ci_hi)


if __name__ == '__main__':
    unittest.main()
