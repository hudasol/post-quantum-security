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
        vals = {k: an.mission_model_value('sik', k)[2] for k in c6.CONFIGS}
        self.assertLessEqual(vals['hybrid_strict'], vals['hybrid_published'])
        self.assertEqual(vals['hybrid_cache'], vals['hybrid_published'])
        for v in vals.values():
            self.assertTrue(0 <= v <= 1)


if __name__ == '__main__':
    unittest.main()
