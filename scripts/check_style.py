#!/usr/bin/env python3
"""Style lint for published text: no em dashes, no emojis, no banned affiliation and no tool or vendor names (matched by word hash), no local machine paths.
Applies to .md, .py, .csv, .txt, .yml, .sh files that are not licence texts. Exit 1 on any hit."""
import hashlib, os, re, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALLOWED_EMOJI = set()
# SHA-256 of each banned word (lower case), so the lint does not itself name the banned affiliation.
BANNED_SHA256 = {'4011393f356a69582a25dfd73603b974b88e7df6fec0b75793c6155c365e691c'}
# SHA-256 of tool and product names that must not appear in repository text (names of the tools used to fetch and
# search, and of the vendor), matched by word hash for the same reason. docs/PREDICTIONS_V3.md was hashed before
# round 3 and cannot change, so it is exempt.
TOOL_SHA256 = {'32ed3a37e22652f5262701eec81dc4f24ffa10cc030845cfa04ed67ca7c82f18', 'c4ef3e6214a4b8dd3c18ee795af15676419af881472ed20ec7adc94ba67c0751', 'c857d09db23e6822e3600bc06ad8d58f92ed62bc8efd81c753f77048662cb97d', 'c70eca6b0f88f44d81a41311647e50fda1ac454ec04ffd442b0eb4743a993131', '94a168d2da574b00ec6c787377278465271cf2b97e68af076fc3eee87eba8664', 'd298391b07433318a02bd922ed5b90112a4302606c4928b54e3fb1c18130d92e'}
TOOL_EXEMPT = {'docs/PREDICTIONS_V3.md'}
WORD = re.compile(r'[a-z]+')
EXT = {'.md', '.py', '.csv', '.txt', '.yml', '.yaml', '.sh', '.tex', '.dot'}
SKIP = {'scripts/check_style.py'}
# Hyphenated compounds that reviews found in prose; written as separate words in this repository.
COMPOUNDS = re.compile(r'\b(HSM-backed|PQ-capable|hardware-fault-safe|re-opened|re-run|Host-measured|time-management|PQC-specific|hybrid-protected|long-lived-secret)\b')
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
            if re.search(r'/home/[a-z]', line): hits.append(f'{rel}:{n}: local machine path')
            if rel.endswith('.md') and not rel.startswith('data/raw/'):
                for m in COMPOUNDS.findall(line): hits.append(f'{rel}:{n}: hyphenated compound {m!r}')
            if any(hashlib.sha256(w.encode()).hexdigest() in BANNED_SHA256 for w in WORD.findall(line.lower())):
                hits.append(f'{rel}:{n}: banned affiliation')
            if rel not in TOOL_EXEMPT and any(hashlib.sha256(w.encode()).hexdigest() in TOOL_SHA256 for w in WORD.findall(line.lower())):
                hits.append(f'{rel}:{n}: tool or vendor name')
            for ch in EMOJI.findall(line):
                if ch not in ALLOWED_EMOJI: hits.append(f'{rel}:{n}: emoji {ch!r}')
    return hits
if __name__ == '__main__':
    h = check(sys.argv[1] if len(sys.argv) > 1 else ROOT)
    for x in h: print('STYLE', x)
    print(f'{len(h)} finding(s)')
    sys.exit(1 if h else 0)
