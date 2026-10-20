"""Unit tests for the pipeline helpers (image lists, document helpers, split writer, configuration)."""
import os
import sys
import tempfile
import unittest

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from cyclemodel import analyse, make_doc, run_all, trace_all  # noqa: E402
from cyclemodel import model as M  # noqa: E402


class Images(unittest.TestCase):
    def test_pqm4_images(self):
        imgs = trace_all.pqm4_images()
        self.assertEqual(len(imgs), 18)
        kem = [i for i in imgs if i['parameter_set'].startswith('ML-KEM')]
        dsa = [i for i in imgs if i['parameter_set'].startswith('ML-DSA')]
        self.assertEqual(len(kem), 9)
        self.assertEqual(len(dsa), 9)
        for i in kem:
            self.assertEqual(set(i['targets']), {'keygen', 'encaps', 'decaps'})
        for i in dsa:
            self.assertEqual(set(i['targets']), {'keygen', 'sign', 'verify'})
        clean = [i for i in imgs if i['implementation'] == 'clean']
        self.assertTrue(all(i['targets']['keygen'].startswith('PQCLEAN_') for i in clean))

    def test_harness_and_external(self):
        self.assertEqual(len(trace_all.harness_images()), 6)
        ext = trace_all.external_images()
        self.assertEqual([e['parameter_set'] for e in ext], ['ML-DSA-44', 'ML-DSA-87'])


class DocHelpers(unittest.TestCase):
    def test_table(self):
        t = make_doc.table(['a', 'b'], [[1, 2]])
        self.assertEqual(t.splitlines(), ['| a | b |', '|---|---|', '| 1 | 2 |'])

    def test_numbers(self):
        self.assertEqual(make_doc.big(1234567.4), '1 234 567')
        self.assertEqual(make_doc.f1(2.345), '2.3')


class SplitWriter(unittest.TestCase):
    def test_build_split_writes_disjoint_halves(self):
        rows = []
        for b in [('ML-KEM-512', 'clean'), ('ML-KEM-768', 'clean'), ('ML-KEM-1024', 'clean'),
                  ('ML-DSA-44', 'm4f'), ('ML-DSA-65', 'm4f'), ('ML-DSA-87', 'm4f')]:
            for op in ('keygen', 'sign'):
                rows.append(dict(id=f'{b[0]}-{b[1]}-{op}', parameter_set=b[0], implementation=b[1], operation=op))
        df = pd.DataFrame(rows)
        old = analyse.RES
        with tempfile.TemporaryDirectory() as d:
            analyse.RES = d
            try:
                out = analyse.build_split(df)
            finally:
                analyse.RES = old
            s = pd.read_csv(os.path.join(d, 'split.csv'))
        self.assertEqual(len(s), len(df))
        per_bin = out.groupby(['parameter_set', 'implementation'])['half'].nunique()
        self.assertTrue((per_bin == 1).all())
        self.assertEqual(set(s['label']), {'assumption'})


class Config(unittest.TestCase):
    def test_git_head_missing(self):
        self.assertEqual(run_all.git_head('/nonexistent/path'), 'not present')

    def test_seed(self):
        self.assertEqual(M.SEED, 20261020)


if __name__ == '__main__':
    unittest.main()
