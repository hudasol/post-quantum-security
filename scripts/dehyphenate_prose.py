#!/usr/bin/env python3
"""Remove hyphens between lowercase words in prose (house style: "time management", not "time-management").
Leaves code spans, URLs, file names, macros, identifiers with capitals or digits, and fenced code untouched.
Usage: dehyphenate_prose.py FILE...   (edits in place; prints the number of changes per file)"""
import re, sys
WORD = re.compile(r'(?<![\w/\.\-\\])([a-z]{3,})-([a-z]{3,})(?![\w/\-\\])')
SKIP = re.compile(r'(`[^`]*`|https?://\S+|\{\{[^}]*\}\}|\[[^\]]*\]\([^)]*\)|<[^>]+>)')
KEEP = {'e-mail'}
def fix_line(line):
    parts = SKIP.split(line); out = []; n = 0
    for p in parts:
        if SKIP.fullmatch(p): out.append(p); continue
        def rep(m):
            nonlocal n
            if m.group(0) in KEEP: return m.group(0)
            n += 1; return m.group(1) + ' ' + m.group(2)
        # repeat to handle chains like long-term-risk
        prev = None
        while prev != p:
            prev = p; p = WORD.sub(rep, p)
        out.append(p)
    return ''.join(out), n
for f in sys.argv[1:]:
    fence = False; total = 0; res = []
    for line in open(f, encoding='utf-8'):
        if line.lstrip().startswith('```'): fence = not fence; res.append(line); continue
        if fence or line.startswith(('---', '|---')): res.append(line); continue
        new, n = fix_line(line); total += n; res.append(new)
    open(f, 'w', encoding='utf-8').write(''.join(res))
    print(f, total)
