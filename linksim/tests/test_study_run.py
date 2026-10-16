"""End to end test of the study runner and its figures on a tiny trial count.
Author: Huda Mueen. Estimated from published sizes, not measured.
"""
import os
import shutil
import tempfile
import unittest

from linksim import plot_study, study


class TestStudyRun(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.saved = (study.RES, study.DOC, plot_study.RES, plot_study.FIG)
        study.RES = os.path.join(self.tmp, "results")
        study.DOC = os.path.join(self.tmp, "STUDY.md")
        plot_study.RES = study.RES
        plot_study.FIG = os.path.join(self.tmp, "fig")

    def tearDown(self):
        study.RES, study.DOC, plot_study.RES, plot_study.FIG = self.saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_formatters(self):
        self.assertEqual(study.model_fmt(0.5), "500 ms")
        self.assertEqual(study.model_fmt(5), "5.00 s")
        self.assertEqual(study.model_fmt(600), "10.0 min")
        self.assertEqual(study.model_fmt(7200), "2.00 h")
        self.assertEqual(study.model_fmt(""), "n/a")
        self.assertEqual(study.model_fmt(float("nan")), "n/a")
        self.assertEqual(study._fmt(0.123456789), "0.123457")
        self.assertEqual(study._fmt("x"), "x")

    def test_end_to_end(self):
        self.assertEqual(study.main(["--trials", "2"]), 0)
        for f in ("mc_grid.csv", "sweeps.csv", "lowrate.csv", "validation.csv",
                  "config.csv"):
            self.assertTrue(os.path.exists(os.path.join(study.RES, f)), f)
        with open(study.DOC, encoding="utf-8") as fh:
            doc = fh.read()
        self.assertIn("Label: **estimated**", doc)
        self.assertIn("seeds 20261016 to 20261017", doc)
        # 6 links x 2 variants x 2 protocols x 5 loss levels + 1 short retry cell
        with open(os.path.join(study.RES, "mc_grid.csv"), encoding="utf-8") as fh:
            self.assertEqual(len(fh.read().strip().splitlines()) - 1, 121)
        plot_study.main()
        for f in ("linksim_mc_loss.png", "linksim_sweeps.png",
                  "linksim_lowrate.png"):
            self.assertTrue(os.path.exists(os.path.join(plot_study.FIG, f)), f)


if __name__ == "__main__":
    unittest.main()
