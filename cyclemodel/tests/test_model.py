"""Unit tests for the model helpers (split, fit, errors, intervals)."""
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from cyclemodel import model as M  # noqa: E402


def binaries():
    out = []
    for p in ('ML-KEM-512', 'ML-KEM-768', 'ML-KEM-1024'):
        out += [(p, 'clean'), (p, 'm4fspeed'), (p, 'm4fstack')]
    for p in ('ML-DSA-44', 'ML-DSA-65', 'ML-DSA-87'):
        out += [(p, 'clean'), (p, 'm4f'), (p, 'm4fstack')]
    return out


class Split(unittest.TestCase):
    def test_half_and_disjoint(self):
        s = M.make_split(binaries())
        self.assertEqual(sorted(s), sorted(binaries()))
        self.assertEqual(sum(v == 'train' for v in s.values()), 9)
        self.assertEqual(sum(v == 'test' for v in s.values()), 9)

    def test_every_stratum_in_both_halves(self):
        s = M.make_split(binaries())
        for impl in ('clean', 'm4fspeed', 'm4fstack', 'm4f'):
            for scheme in ('ML-KEM', 'ML-DSA'):
                vals = {v for (p, i), v in s.items() if i == impl and p.startswith(scheme)}
                if vals:
                    self.assertEqual(vals, {'train', 'test'})

    def test_deterministic(self):
        self.assertEqual(M.make_split(binaries()), M.make_split(binaries()))


class Fit(unittest.TestCase):
    def test_recovers_known_costs(self):
        rng = np.random.default_rng(1)
        X = rng.uniform(1e4, 1e6, size=(30, 4))
        c = np.array([1.0, 2.0, 0.0, 3.0])
        y = X @ c
        got = M.fit_nnls(X, y)
        np.testing.assert_allclose(got, c, atol=1e-6)

    def test_non_negative(self):
        X = np.array([[1.0, 1.0], [2.0, 1.0], [3.0, 1.0]])
        y = np.array([1.0, 1.0, 1.0])
        self.assertTrue((M.fit_nnls(X, y) >= 0).all())


class Errors(unittest.TestCase):
    def test_pct_error(self):
        self.assertAlmostEqual(float(M.pct_error(110, 100)), 10.0)
        self.assertAlmostEqual(float(M.pct_error(90, 100)), -10.0)

    def test_summary(self):
        s = M.summarise([-10.0, 5.0, 20.0])
        self.assertEqual(s['n'], 3)
        self.assertAlmostEqual(s['median_abs_pct'], 10.0)
        self.assertAlmostEqual(s['worst_abs_pct'], 20.0)
        self.assertAlmostEqual(s['median_signed_pct'], 5.0)
        self.assertLessEqual(s['median_abs_ci_lo'], s['median_abs_pct'])
        self.assertGreaterEqual(s['median_abs_ci_hi'], s['median_abs_pct'])

    def test_bootstrap_single(self):
        self.assertEqual(M.bootstrap_ci([3.0], np.median), (3.0, 3.0))

    def test_prediction_interval(self):
        lo, hi = M.prediction_interval(100.0, [0.0, 0.0, 0.0])
        self.assertAlmostEqual(lo, 100.0)
        self.assertAlmostEqual(hi, 100.0)
        lo, hi = M.prediction_interval(100.0, np.linspace(-10, 10, 101))
        self.assertLess(lo, 100.0)
        self.assertGreater(hi, 100.0)


class Reduced(unittest.TestCase):
    def test_matrix_maps_each_feature_once(self):
        G = M.reduced_matrix()
        self.assertEqual(G.shape, (len(M.FEATURE_NAMES), len(M.REDUCED)))
        np.testing.assert_array_equal(G.sum(axis=1), np.ones(len(M.FEATURE_NAMES)))

    def test_extrapolation_flags(self):
        Xt = np.array([[1.0, 1.0], [2.0, 1.0]])
        self.assertEqual(M.extrapolation_flags([1.5, 1.0], Xt, ['a', 'b']), [])
        self.assertEqual(M.extrapolation_flags([1.0, 3.0], Xt, ['a', 'b']), ['a', 'b'])


class Labels(unittest.TestCase):
    def test_implementation_of(self):
        self.assertEqual(M.implementation_of("pqm4 implementation 'm4fspeed (Cortex-M4F)'"), 'm4fspeed')
        self.assertEqual(M.implementation_of("pqm4 implementation 'm4f (Cortex-M4F)'"), 'm4f')
        self.assertEqual(M.implementation_of("pqm4 implementation 'clean (PQClean)'"), 'clean')
        self.assertIsNone(M.implementation_of('other'))

    def test_family(self):
        self.assertEqual(M.family_of(0.7), 'hash heavy')
        self.assertEqual(M.family_of(0.2), 'NTT heavy')

    def test_assembly(self):
        self.assertTrue(M.is_assembly('m4fstack'))
        self.assertFalse(M.is_assembly('clean'))

    def test_a_priori_covers_features(self):
        self.assertEqual(set(M.A_PRIORI), set(M.FEATURE_NAMES))


if __name__ == '__main__':
    unittest.main()
