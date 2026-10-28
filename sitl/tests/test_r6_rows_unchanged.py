"""The rows of the round 6 result files that existed before design K (kem_auth) was added stay unchanged.

The fingerprints were computed from the committed files before the kem_auth runs were added: for each file, the
number of lines (header and the rows of the first seven configurations) and the SHA-256 of those lines. After
kem_auth, the files hold the same lines first and the kem_auth rows after them
(python3 -m unittest discover -s sitl -t .).
"""
import csv
import hashlib
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(os.path.dirname(HERE), 'results_r6')

# file: (lines including the header, SHA-256 of those lines)
FINGERPRINTS = {
    'summary.csv': (74, '9b3a91c9b30fc339a6434293528e9fbbc8fb18b0955b4b0f5183e7a61a399f86'),
    'paired.csv': (8, '89f250a455d643949c61b7005da8d43251ed09f9b65b37a6ae1db903255d504e'),
    'rejections.csv': (58, '4d8fc2b0e09886cc6fabe91a8796444dc76132cfa527a8ff4b3c7680696591c5'),
    'host_compute.csv': (39, '167f69d191f461a32515b225f77c9be6f102b4f966e7c403fbd06851fe206162'),
    'deadline_sweep.csv': (43, '861f2b4a1ecd99807ffa1ca852c696151da4e28922dcdfc90d61f2ad64e568d3'),
    'comparison.csv': (10, 'ff885614c7d65a3820768fadd2f68dddd42c00cc97909a729e46f82eab4354f2'),
}
FIRST_SEVEN = {'none', 'signing', 'classical', 'hybrid_published', 'hybrid_strict', 'hybrid_cache', 'pqsig_real'}


class TestRoundSixRowsUnchanged(unittest.TestCase):
    def test_existing_rows_unchanged(self):
        for name, (n, digest) in FINGERPRINTS.items():
            with open(os.path.join(RES, name), 'rb') as f:
                lines = f.read().splitlines(keepends=True)
            self.assertGreaterEqual(len(lines), n, name)
            self.assertEqual(hashlib.sha256(b''.join(lines[:n])).hexdigest(), digest, name)

    def test_rows_after_the_existing_ones_are_kem_auth(self):
        for name, (n, _) in FINGERPRINTS.items():
            with open(os.path.join(RES, name), newline='') as f:
                rows = list(csv.DictReader(f))
            self.assertTrue(all(r['config'] in FIRST_SEVEN for r in rows[:n - 1]), name)
            self.assertTrue(all(r['config'] == 'kem_auth' for r in rows[n - 1:]), name)

    def test_kem_auth_rows_present_with_the_labels_of_their_kind(self):
        def rows(name):
            with open(os.path.join(RES, name), newline='') as f:
                return list(csv.DictReader(f))
        summ = rows('summary.csv')
        old = {r['metric']: r['label'] for r in summ if r['config'] == 'hybrid_published'}
        new = {r['metric']: r['label'] for r in summ if r['config'] == 'kem_auth'}
        self.assertEqual(new, old)
        paired = [r for r in rows('paired.csv') if r['config'] == 'kem_auth']
        self.assertEqual([r['minus_config'] for r in paired], ['hybrid_published', 'classical'])
        self.assertTrue(all(r['label'] == 'SITL measured' and r['missions_paired'] == '20' for r in paired))
        host = [r for r in rows('host_compute.csv') if r['config'] == 'kem_auth']
        self.assertTrue(host and all(r['label'] == 'host measured' for r in host))
        sweep = [r for r in rows('deadline_sweep.csv') if r['config'] == 'kem_auth']
        self.assertEqual(len(sweep), 6)
        self.assertTrue(all(r['label'] == 'SITL measured' for r in sweep))
        comp = [r for r in rows('comparison.csv') if r['config'] == 'kem_auth']
        self.assertEqual(len(comp), 1)
        self.assertEqual((comp[0]['mission_model_estimated'], comp[0]['error'], comp[0]['label']), ('', '', 'SITL measured'))
        self.assertIn('no architecture for design K', comp[0]['verdict'])
        rej = [r for r in rows('rejections.csv') if r['config'] == 'kem_auth']
        labels = {r['scope']: r['label'] for r in rows('rejections.csv') if r['config'] != 'kem_auth'}
        self.assertTrue(rej and all(labels[r['scope']] == r['label'] for r in rej))


if __name__ == '__main__':
    unittest.main()
