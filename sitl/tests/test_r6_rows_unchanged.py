"""The rows of the round 6 result files that existed before a configuration was added stay unchanged.

FINGERPRINTS were computed from the committed files before the kem_auth runs were added: for each file, the
number of lines (header and the rows of the first seven configurations) and the SHA-256 of those lines. After
kem_auth, the files hold the same lines first and the kem_auth rows after them. FINGERPRINTS_K were computed from
the committed files with kem_auth, before hybrid_strict_inband and pqsig_counter were added; the files hold those
lines first and the rows of the two added configurations after them. delays.csv gains no rows (the two added
configurations use the delays of the first seven). The review of the paired differences added new files
(missed_per_mission.csv, paired_missed.csv, session_restarts.csv) and changed no existing row
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
# file: (lines including the header, SHA-256 of those lines), with kem_auth, before the two added configurations
FINGERPRINTS_K = {
    'summary.csv': (85, '11d9e160d6c1965f82bf928f1069dfd396ef906fbe13831cc1c7c2a43f2b2bc3'),
    'paired.csv': (10, '2e9d8bd599ff48e4a68e1684de51a2d0dfcd64510a4f1a633e21a857484f2881'),
    'rejections.csv': (71, 'f446ff5472c280a0ea90b5bdfdc11d4385f12f6fd11008b6c5caf3900de41b67'),
    'host_compute.csv': (47, 'bc38953e79df190669bbd745dde81ea54e91a8e72592059b140d89bec6163504'),
    'deadline_sweep.csv': (49, '7bc8b39b737c8dea858916bc2b7a9bb54e10955c987f7aaf5d1afd870c179a52'),
    'comparison.csv': (11, '0f01799c23c8267de0c79c432f53b4e21f2ad01201c4b132be689c1405ad60b7'),
    'reorder.csv': (6, '4d978c8d0d572b489cdeb7411177c3fd8619138da8473c46f489216d48a5c8d0'),
    'missions.csv': (161, '4924b99a0aafe6d3260808daeda386c2994085a16922c249297a2cf7c864de78'),
    'commands.csv': (7731, '9504714b4412c547e773edbe5ad9e4b9de8bccc364acb683de322cf55081470f'),
    'delays.csv': (25, '0763e78f68a77a3abe48b3830086a45be3dc8875a8adf83f4a908e5a6cd85ea1'),
}
LATER = {'hybrid_strict_inband', 'pqsig_counter'}
NEW_FILES = ('missed_per_mission.csv', 'paired_missed.csv', 'session_restarts.csv')
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
            nk = FINGERPRINTS_K[name][0]
            with open(os.path.join(RES, name), newline='') as f:
                rows = list(csv.DictReader(f))
            self.assertTrue(all(r['config'] in FIRST_SEVEN for r in rows[:n - 1]), name)
            self.assertTrue(all(r['config'] == 'kem_auth' for r in rows[n - 1:nk - 1]), name)

    def test_rows_with_kem_auth_unchanged(self):
        for name, (n, digest) in FINGERPRINTS_K.items():
            with open(os.path.join(RES, name), 'rb') as f:
                lines = f.read().splitlines(keepends=True)
            self.assertGreaterEqual(len(lines), n, name)
            self.assertEqual(hashlib.sha256(b''.join(lines[:n])).hexdigest(), digest, name)
            if name == 'delays.csv':
                self.assertEqual(len(lines), n, name)

    def test_rows_after_kem_auth_are_the_added_configurations(self):
        for name, (n, _) in FINGERPRINTS_K.items():
            if name == 'delays.csv':
                continue
            with open(os.path.join(RES, name), newline='') as f:
                rows = list(csv.DictReader(f))
            self.assertTrue(all(r['config'] not in LATER for r in rows[:n - 1]), name)
            later = rows[n - 1:]
            self.assertTrue(later and all(r['config'] in LATER for r in later), name)
            self.assertEqual({r['config'] for r in later}, LATER, name)

    def test_added_configuration_rows_with_the_labels_of_their_kind(self):
        def rows(name):
            with open(os.path.join(RES, name), newline='') as f:
                return list(csv.DictReader(f))
        summ = rows('summary.csv')
        ref = {'hybrid_strict_inband': 'hybrid_strict', 'pqsig_counter': 'pqsig_real'}
        for k, old in ref.items():
            self.assertEqual({r['metric']: r['label'] for r in summ if r['config'] == k},
                             {r['metric']: r['label'] for r in summ if r['config'] == old}, k)
        paired = [(r['config'], r['minus_config']) for r in rows('paired.csv') if r['config'] in LATER]
        self.assertEqual(paired, [('hybrid_strict_inband', 'hybrid_published'), ('hybrid_strict_inband', 'hybrid_strict'),
                                  ('pqsig_counter', 'pqsig_real'), ('pqsig_counter', 'hybrid_published')])
        self.assertTrue(all(r['label'] == 'SITL measured' and r['missions_paired'] == '20'
                            for r in rows('paired.csv') if r['config'] in LATER))
        for k in LATER:
            self.assertTrue(all(r['label'] == 'host measured' for r in rows('host_compute.csv') if r['config'] == k))
            sweep = [r for r in rows('deadline_sweep.csv') if r['config'] == k]
            self.assertEqual(len(sweep), 6)
            self.assertTrue(all(r['label'] == 'SITL measured' for r in sweep))
            comp = [r for r in rows('comparison.csv') if r['config'] == k]
            self.assertEqual(len(comp), 1)
            self.assertEqual((comp[0]['mission_model_estimated'], comp[0]['error'], comp[0]['label']), ('', '', 'SITL measured'))
            self.assertIn('no architecture for', comp[0]['verdict'])
        labels = {r['scope']: r['label'] for r in rows('rejections.csv') if r['config'] not in LATER}
        rej = [r for r in rows('rejections.csv') if r['config'] in LATER]
        self.assertTrue(rej and all(labels.get(r['scope']) == r['label'] for r in rej))

    def test_new_files_of_the_review(self):
        def rows(name):
            with open(os.path.join(RES, name), newline='') as f:
                return list(csv.DictReader(f))
        mpm = rows('missed_per_mission.csv')
        self.assertTrue(all(r['label'] == 'SITL measured' for r in mpm))
        self.assertTrue(all(int(r['missed']) == int(r['commands']) - int(r['acknowledged']) for r in mpm))
        configs = {r['config'] for r in mpm}
        self.assertEqual(configs, FIRST_SEVEN | {'kem_auth'} | LATER)
        # the commands per mission add up to the commands of summary.csv
        summ = {r['config']: r for r in rows('summary.csv') if r['metric'] == 'commands'}
        for k in configs:
            self.assertEqual(sum(int(r['commands']) for r in mpm if r['config'] == k), int(float(summ[k]['value'])), k)
        pm = rows('paired_missed.csv')
        self.assertTrue(all(r['label'] == 'SITL measured' and r['metric'] == 'missed_per_mission' for r in pm))
        self.assertEqual([(r['config'], r['minus_config']) for r in pm],
                         [(r['config'], r['minus_config']) for r in rows('paired.csv')])
        sr = rows('session_restarts.csv')
        self.assertTrue(all(r['label'] == 'emulated' for r in sr))
        self.assertEqual({r['config'] for r in sr}, configs)

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
