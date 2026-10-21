"""Tests for the round 5 statistics scripts (stats/)."""
import os
import sys
import unittest

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "stats"))

import cycle_validation as CV  # noqa: E402
import meta_hierarchical as MH  # noqa: E402
import third_look_classify as TL  # noqa: E402


class ClusterBootstrap(unittest.TestCase):
    def test_deterministic_and_covers(self):
        e = np.array([1.0, -2.0, 3.0, 0.5, -0.5, 4.0])
        cl = np.array(["a", "a", "b", "b", "c", "c"])
        b1 = CV.cluster_bootstrap(e, cl, n=500)
        b2 = CV.cluster_bootstrap(e, cl, n=500)
        np.testing.assert_array_equal(b1, b2)
        lo, hi = CV.ci(b1[:, 0])
        self.assertLessEqual(lo, np.median(np.abs(e)) + 1e-12)
        self.assertGreaterEqual(hi, np.median(np.abs(e)) - 1e-12)

    def test_whole_clusters_kept(self):
        # two clusters with constant errors: every resample median is one of the cluster values or their mean
        e = np.array([1.0, 1.0, 5.0, 5.0])
        b = CV.cluster_bootstrap(e, np.array(["x", "x", "y", "y"]), n=200)
        self.assertTrue(set(np.round(b[:, 1], 9)) <= {1.0, 3.0, 5.0})


class CycleResults(unittest.TestCase):
    def setUp(self):
        _, rows = CV.load_rows()
        self.rows, *_ = CV.round4_errors(rows)

    def test_round4_reproduced(self):
        mr = pd.read_csv(os.path.join(ROOT, "cyclemodel", "results", "matched_rows.csv"))
        m = self.rows.merge(mr, on="id", suffixes=("", "_r4"))
        self.assertEqual(len(m), 54)
        self.assertLess((m.err_pct_fitted - m.err_pct_fitted_r4).abs().max(), 1e-3)

    def test_lofo_partitions(self):
        per_row, summ = CV.lofo(self.rows)
        for kind in CV.LOFO_KEYS:
            g = per_row[(per_row.left_out_by == kind) & (per_row.model == "fitted")]
            self.assertEqual(len(g), 54)
            self.assertEqual(g.id.nunique(), 54)

    def test_board_interval_contains_round4(self):
        p = os.path.join(ROOT, "stats", "results", "cycle_board_predictions_cluster.csv")
        if not os.path.exists(p):
            self.skipTest("run stats/cycle_validation.py first")
        d = pd.read_csv(p)
        self.assertTrue((d.pi95_lo_cluster_outer <= d.pi95_lo_round4 + 1).all())
        self.assertTrue((d.pi95_hi_cluster_outer >= d.pi95_hi_round4 - 1).all())

    def test_harness_verdict(self):
        _, verdict, _ = CV.harness_check()
        self.assertTrue(verdict.startswith("not possible") or verdict == "possible")


class Meta(unittest.TestCase):
    def test_statistic_parser(self):
        self.assertEqual(MH.statistic_of("statistic: mean of 1000 executions"), "mean")
        self.assertEqual(MH.statistic_of("cycles -O3 median of 100 at 20 MHz"), "median")
        self.assertEqual(MH.statistic_of("cycles=mean of 10 executions (min 1, max 2)"), "mean")
        self.assertEqual(MH.statistic_of("statistic: minimum"), "min")
        self.assertEqual(MH.statistic_of("statistic: single execution"), "other")
        self.assertEqual(MH.statistic_of("nothing stated"), "other")

    def test_compiler_parser(self):
        self.assertEqual(MH.compiler_of("arm-none-eabi-gcc 12.2.1 -O3"), "gcc 12")
        self.assertEqual(MH.compiler_of("compiler and flags not stated"), "not stated")

    def _sim(self, seed=1):
        rng = np.random.default_rng(seed)
        n_cell, per = 40, 6
        cell = np.repeat(np.arange(n_cell), per)
        fa = rng.integers(0, 8, len(cell))
        fb = rng.integers(0, 6, len(cell))
        y = cell * 0.3 + rng.normal(0, 0.5, 8)[fa] + rng.normal(0, 0.2, 6)[fb] + rng.normal(0, 0.1, len(cell))
        d = pd.DataFrame(dict(cell=cell.astype(str), a=fa.astype(str), b=fb.astype(str), y=y))
        return d

    def test_reml_finite_and_ordered(self):
        d = self._sim()
        X, Z = MH.design(d, ["a", "b"])
        var, ll = MH.fit(d.y.to_numpy(), X, Z, np.ones(len(d)))
        self.assertTrue(np.isfinite(ll))
        self.assertGreater(var[0], var[2])  # factor a (sd 0.5) above the residual (sd 0.1)

    def test_matches_statsmodels(self):
        try:
            import statsmodels  # noqa: F401
        except ImportError:
            self.skipTest("statsmodels not installed")
        d = self._sim(2)
        X, Z = MH.design(d, ["a", "b"])
        var, _ = MH.fit(d.y.to_numpy(), X, Z, np.ones(len(d)))
        sm = MH.statsmodels_check(d, ["a", "b"])
        np.testing.assert_allclose(var, [sm["a"], sm["b"], sm["residual"]], rtol=0.05, atol=1e-3)

    def test_score_weights(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as t:
            f = Path(t) / "q.csv"
            pd.DataFrame(dict(source_url=["x", "y"], score=[0, 5])).to_csv(f, index=False)
            old = MH.WEIGHT_FILE
            MH.WEIGHT_FILE = f
            try:
                w, note = MH.load_weights(pd.DataFrame(dict(source=["x", "y", "z"])))
            finally:
                MH.WEIGHT_FILE = old
        np.testing.assert_allclose(w, [1 / 6, 1.0, 1.0])
        self.assertIn("(score + 1) / 6", note)

    def test_unweighted_without_file(self):
        d = pd.DataFrame(dict(source=["x", "y"]))
        if MH.WEIGHT_FILE.exists():
            self.skipTest("weight file present")
        w, note = MH.load_weights(d)
        self.assertTrue((w == 1).all())
        self.assertIn("unweighted", note)


class EndToEnd(unittest.TestCase):
    def test_ranges_from_files(self):
        import end_to_end as E
        inp = {n: (lo, hi, src) for n, lo, hi, _, src in E.inputs()}
        self.assertEqual(inp["impl_factor"][:2], E.energy_range("impl_factor"))
        self.assertEqual(inp["frame_loss"][:2], (0.0, 0.2))
        for n, (lo, hi, src) in inp.items():
            self.assertLess(lo, hi, n)
            self.assertTrue(src)

    def test_chain_deterministic_and_formula(self):
        import end_to_end as E
        ch = E.Chain(runs=2)
        x = [(lo + hi) / 2 for _, lo, hi, _, _ in E.inputs()]
        y1, y2 = ch(x), ch(x)
        self.assertEqual(y1, y2)
        d = dict(zip(ch.names, x))
        fw = 1e3 * (1e6 * d["sha256_cpb"] + ch.mldsa * d["impl_factor"] * d["wait_state_factor"]) / (d["clock_mhz"] * 1e6)
        self.assertAlmostEqual(y1[2], fw, places=6)
        self.assertTrue(0.0 <= y1[0] <= 1.0)


class ThirdLook(unittest.TestCase):
    def test_rules(self):
        same = TL._sv5().same
        self.assertEqual(TL.matches("operation", "keygen", "Key Generation", same), "R2")
        self.assertEqual(TL.matches("core", "Cortex-M4F", "32-bit ARM Cortex-M4 with FPU core", same), "R3")
        self.assertIsNone(TL.matches("operation", "keygen", "Verification", same))
        self.assertEqual(TL.contradiction("operation", "keygen", "sign"), "operation keygen against sign")
        self.assertEqual(TL.contradiction("parameter_set", "Kyber768", "KYBER512"), "parameter numbers disjoint")
        self.assertEqual(TL.contradiction("library", "a", "b"), "")

    def test_wilson(self):
        lo, hi = TL.wilson(0, 100)
        self.assertEqual(lo, 0.0)
        self.assertLess(hi, 0.05)

    def test_sheets_blind_and_disjoint(self):
        V = os.path.join(ROOT, "data", "verify5")
        sheets = [pd.read_csv(os.path.join(V, f"third_look_sheet_{i}.csv")) for i in (1, 2, 3)]
        cols = set(sheets[0].columns)
        self.assertEqual(cols, {"id", "field", "source_title", "source_url", "supplied_file", "location_in_source"})
        keys = [set(zip(s.id, s.field)) for s in sheets]
        self.assertFalse(keys[0] & keys[1] or keys[0] & keys[2] or keys[1] & keys[2])
        srcs = [set(s.source_url) for s in sheets]
        self.assertFalse(srcs[0] & srcs[1] or srcs[0] & srcs[2] or srcs[1] & srcs[2])


if __name__ == "__main__":
    unittest.main()
