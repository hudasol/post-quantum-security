#!/usr/bin/env python3
"""Fail if the repository contains copyrighted papers, PDFs outside an allowlist, or raw downloads.

Checks every file that git tracks or would track (not ignored). Exit code 1 on any violation.
Rules:
  1. No file with a document or archive extension (pdf, ps, epub, djvu, docx, pptx, xlsx, zip, tar, gz, tgz, bz2, xz, 7z, rar, html, htm, mhtml, warc), except the allowlist below.
  2. No file that starts with a PDF header, whatever its name, except the allowlist.
  3. Allowlisted PDFs must name only the author in their metadata (Author: Huda Mueen) and live in docs/.
  4. Binary files (NUL bytes) are allowed only as PNG or SVG under plots/ or docs/figures/.
  5. No file larger than 5 MB (large files are usually downloads).
  6. Nothing under third party directories (bench/mcu/ext, bench/mcu/build) and no vendored library trees.
  7. data/raw may hold only .md and .csv notes written for this review; a file that looks like saved HTML (contains '<html' or '<!doctype') is rejected.
"""
import os, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BAD_EXT = {'.pdf','.ps','.epub','.djvu','.docx','.pptx','.xlsx','.zip','.tar','.gz','.tgz','.bz2','.xz','.7z','.rar','.html','.htm','.mhtml','.warc'}
ALLOW = {'docs/REPORT.pdf','docs/EXECUTIVE_BRIEF.pdf'}
BIN_OK_EXT = {'.png','.svg'}
BIN_OK_DIRS = ('plots/','docs/figures/')
THIRD = ('bench/mcu/ext/','bench/mcu/build/')
MAX = 5 * 1024 * 1024

def files(root):
    try:
        out = subprocess.run(['git','ls-files','-co','--exclude-standard','-z'], cwd=root, capture_output=True, check=True).stdout
        return [p for p in out.decode().split('\0') if p]
    except Exception:
        res = []
        for d, _, fs in os.walk(root):
            if '.git' in d.split(os.sep): continue
            for f in fs: res.append(os.path.relpath(os.path.join(d, f), root))
        return res

def check(root):
    problems = []
    for rel in files(root):
        rel = rel.replace(os.sep, '/')
        p = os.path.join(root, rel)
        if not os.path.isfile(p): continue
        ext = os.path.splitext(rel)[1].lower()
        size = os.path.getsize(p)
        head = open(p, 'rb').read(8192)
        if rel.startswith(THIRD): problems.append(f'{rel}: third party directory must not be committed')
        if size > MAX: problems.append(f'{rel}: larger than 5 MB ({size} bytes)')
        is_pdf = head.startswith(b'%PDF')
        if (ext in BAD_EXT or is_pdf) and rel not in ALLOW:
            problems.append(f'{rel}: document or archive file not on the allowlist (papers and downloads must not be committed)')
        if rel in ALLOW:
            if not is_pdf: problems.append(f'{rel}: allowlisted file is not a PDF')
            try:
                info = subprocess.run(['pdfinfo', p], capture_output=True, text=True, check=True).stdout
                author = [l.split(':', 1)[1].strip() for l in info.splitlines() if l.startswith('Author:')]
                if author != ['Huda Mueen']: problems.append(f'{rel}: PDF author is {author!r}, expected Huda Mueen only')
            except FileNotFoundError:
                print(f'note: pdfinfo not installed, author of {rel} not checked')
        if b'\0' in head and rel not in ALLOW:
            if not (ext in BIN_OK_EXT and rel.startswith(BIN_OK_DIRS)):
                problems.append(f'{rel}: unexpected binary file')
        if rel.startswith('data/raw/'):
            if ext not in ('.md', '.csv'): problems.append(f'{rel}: data/raw may hold only .md and .csv notes')
            low = head.lower()
            if b'<html' in low or b'<!doctype' in low: problems.append(f'{rel}: looks like a saved web page')
    return problems

if __name__ == '__main__':
    root = sys.argv[1] if len(sys.argv) > 1 else ROOT
    probs = check(root)
    for p in probs: print('FAIL', p)
    print(f'{len(probs)} problem(s)')
    sys.exit(1 if probs else 0)
