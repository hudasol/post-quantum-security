"""Tests for the repository policy, secrets and style checks (run with: python -m unittest discover -s tests -t .)."""
import os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
import check_repo_policy as pol, scan_secrets as sec, check_style as sty

def make(tmp, rel, data=b'x'):
    p = os.path.join(tmp, rel); os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, 'wb').write(data)

class Policy(unittest.TestCase):
    def test_clean_repo_passes(self):
        with tempfile.TemporaryDirectory() as t:
            make(t, 'README.md', b'hello'); make(t, 'data/raw/S1.md', b'notes'); make(t, 'plots/a.png', b'\x89PNG\0\0')
            self.assertEqual(pol.check(t), [])
    def test_pdf_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            make(t, 'papers/x.pdf', b'%PDF-1.5 body')
            self.assertTrue(any('x.pdf' in p for p in pol.check(t)))
    def test_renamed_pdf_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            make(t, 'docs/notes.txt', b'%PDF-1.7 hidden')
            self.assertTrue(any('notes.txt' in p for p in pol.check(t)))
    def test_archive_and_html_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            make(t, 'data/raw/page.html', b'<html>'); make(t, 'dl/x.zip', b'PK')
            self.assertEqual(len(pol.check(t)), 4)  # page.html: extension, not md or csv in raw, looks like a page; x.zip: extension
    def test_raw_html_content_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            make(t, 'data/raw/S9.md', b'<!DOCTYPE html><p>saved page</p>')
            self.assertTrue(any('saved web page' in p for p in pol.check(t)))
    def test_third_party_dir_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            make(t, 'bench/mcu/ext/lib/a.c', b'int x;')
            self.assertTrue(any('third party' in p for p in pol.check(t)))
    def test_large_file_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            make(t, 'data/big.csv', b'a' * (5 * 1024 * 1024 + 1))
            self.assertTrue(any('5 MB' in p for p in pol.check(t)))
    def test_unexpected_binary_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            make(t, 'tools/blob.bin', b'\0\1\2')
            self.assertTrue(any('binary' in p for p in pol.check(t)))

class Secrets(unittest.TestCase):
    def test_detects_github_token_and_key_block(self):
        with tempfile.TemporaryDirectory() as t:
            make(t, 'a.txt', b'token = ghp_' + b'A' * 30)
            make(t, 'b.txt', b'-----BEGIN ' + b'PRIVATE KEY-----')
            self.assertEqual(len(sec.scan(t)), 2)
    def test_allow_marker_and_clean_text(self):
        with tempfile.TemporaryDirectory() as t:
            make(t, 'a.txt', b'example ghp_' + b'A' * 30 + b' secretscan:allow')
            make(t, 'b.txt', b'nothing here')
            self.assertEqual(sec.scan(t), [])

class Style(unittest.TestCase):
    def test_flags_em_dash_emoji_affiliation(self):
        with tempfile.TemporaryDirectory() as t:
            make(t, 'a.md', ('word ' + chr(0x2014) + ' word\n').encode())
            make(t, 'b.md', ('ok ' + chr(0x1F680) + '\n').encode())
            make(t, 'c.md', (b'University of Stir' + b'ling\n'))
            self.assertEqual(len(sty.check(t)), 3)
    def test_allowed_emoji_passes(self):
        with tempfile.TemporaryDirectory() as t:
            make(t, 'a.md', (chr(0x1F338) + ' sakura\n').encode())
            self.assertEqual(sty.check(t), [])

if __name__ == '__main__':
    unittest.main()
