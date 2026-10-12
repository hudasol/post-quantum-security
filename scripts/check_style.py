#!/usr/bin/env python3
"""Style lint for published text: no em dashes, no emojis except the allowed set, no university affiliation.
Applies to .md, .py, .csv, .txt, .yml, .sh files that are not licence texts. Exit 1 on any hit."""
import os, re, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALLOWED_EMOJI = set('\U0001F337\U0001F338\U0001F34B\U0001F33F')
EXT = {'.md', '.py', '.csv', '.txt', '.yml', '.yaml', '.sh', '.tex', '.dot'}
SKIP = {'scripts/check_style.py'}
EMOJI = re.compile('[\U0001F300-\U0001FAFF☀-➿⭐⬆✅❌]')
def files(root):
    try:
        out = subprocess.run(['git','ls-files','-co','--exclude-standard','-z'], cwd=root, capture_output=True, check=True).stdout
        return [p for p in out.decode().split('\0') if p]
    except Exception:
        return [os.path.relpath(os.path.join(d, f), root) for d, _, fs in os.walk(root) if '.git' not in d.split(os.sep) for f in fs]
def check(root):
    hits = []
    for rel in files(root):
        if rel in SKIP or os.path.splitext(rel)[1] not in EXT or rel.startswith('bench/mcu/ext/'): continue
        p = os.path.join(root, rel)
        if not os.path.isfile(p): continue
        for n, line in enumerate(open(p, encoding='utf-8', errors='replace'), 1):
            if '—' in line: hits.append(f'{rel}:{n}: em dash')
            if re.search(r'stirling', line, re.I): hits.append(f'{rel}:{n}: university affiliation')
            for ch in EMOJI.findall(line):
                if ch not in ALLOWED_EMOJI: hits.append(f'{rel}:{n}: emoji {ch!r}')
    return hits
if __name__ == '__main__':
    h = check(sys.argv[1] if len(sys.argv) > 1 else ROOT)
    for x in h: print('STYLE', x)
    print(f'{len(h)} finding(s)')
    sys.exit(1 if h else 0)
