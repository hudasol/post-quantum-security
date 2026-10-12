#!/usr/bin/env python3
"""Small secrets scan for tracked and untracked files (not ignored). Exit 1 if a pattern matches.
Patterns: private key blocks, GitHub and Slack tokens, AWS access key ids, Google API keys, bearer tokens, generic key or password assignments with long values.
A line containing the marker  secretscan:allow  is skipped (use for documented examples)."""
import os, re, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATTERNS = {
 'private key block': re.compile(r'-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY'),
 'github token': re.compile(r'\b(?:ghp|gho|ghu|ghs|ghr|github_pat)_[A-Za-z0-9_]{20,}'),
 'slack token': re.compile(r'\bxox[abprs]-[A-Za-z0-9-]{10,}'),
 'aws access key id': re.compile(r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b'),
 'google api key': re.compile(r'\bAIza[0-9A-Za-z_\-]{35}\b'),
 'anthropic or openai style key': re.compile(r'\bsk-(?:ant-)?[A-Za-z0-9_\-]{30,}'),
 'bearer token': re.compile(r'[Bb]earer\s+[A-Za-z0-9_\-\.=]{30,}'),
 'generic secret assignment': re.compile(r'(?i)\b(?:api[_-]?key|secret|passwd|password|token)\b\s*[:=]\s*["\'][A-Za-z0-9_\-/+=]{20,}["\']'),
}
def files(root):
    try:
        out = subprocess.run(['git','ls-files','-co','--exclude-standard','-z'], cwd=root, capture_output=True, check=True).stdout
        return [p for p in out.decode().split('\0') if p]
    except Exception:
        return [os.path.relpath(os.path.join(d, f), root) for d, _, fs in os.walk(root) if '.git' not in d.split(os.sep) for f in fs]
def scan(root):
    hits = []
    for rel in files(root):
        p = os.path.join(root, rel)
        if not os.path.isfile(p) or os.path.getsize(p) > 5*1024*1024: continue
        data = open(p, 'rb').read()
        if b'\0' in data[:8192]: continue
        for n, line in enumerate(data.decode('utf-8', 'replace').splitlines(), 1):
            if 'secretscan:allow' in line: continue
            for name, rx in PATTERNS.items():
                if rx.search(line): hits.append(f'{rel}:{n}: {name}')
    return hits
if __name__ == '__main__':
    root = sys.argv[1] if len(sys.argv) > 1 else ROOT
    h = scan(root)
    for x in h: print('FOUND', x)
    print(f'{len(h)} finding(s)')
    sys.exit(1 if h else 0)
