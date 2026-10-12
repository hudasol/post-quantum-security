#!/usr/bin/env python3
"""Define the phase 2 verification sets from the data files.

Set A (headline): every row ID that supports a number in the report or brief.
  Sources of IDs: macros and plain mentions in docs/*.md (not REPORT.md, the
  expanded copy), plot row files, Appendix B list in scripts/build_report.py.
Set B (random): seeded, stratified by (device_class, library family),
  drawn from rows not in A and not in the earlier 50 row sample.
Output: data/verify2_headline.csv, data/verify2_random.csv, data/verify2_sets.json
"""
import csv, glob, json, random, re, sys
SEED = 20261012
N_RANDOM = 120
ids_all = {}
rows = list(csv.DictReader(open('data/evidence.csv')))
by_id = {r['id']: r for r in rows}

def ids_in(text):
    out = set()
    for m in re.finditer(r'S([23])-(\d{3,4})(?:\s*(?:\.\.|–|-|to)\s*(?:S[23]-)?(\d{3,4}))?', text):
        stream, a, b = m.group(1), m.group(2), m.group(3)
        w = max(len(a), 4 if stream == '2' else 3)
        def fmt(n): return f"S{stream}-{int(n):0{4 if stream=='2' else 3}d}"
        out.add(fmt(a))
        if b and int(b) > int(a) and int(b) - int(a) < 40:
            for n in range(int(a), int(b) + 1): out.add(fmt(n))
    return out

head = set()
src = {}
for f in ['docs/REPORT_body.md', 'docs/EXECUTIVE_BRIEF.md', 'docs/DECISION_FRAMEWORK.md',
          'docs/MIGRATION_PLAYBOOK.md', 'docs/BENCHMARK_PLAN.md', 'docs/GLOSSARY.md', 'docs/NEXT_STEPS.md']:
    s = ids_in(open(f).read())
    for i in s: src.setdefault(i, []).append(f)
    head |= s
for f in glob.glob('plots/*_rows.csv'):
    for r in csv.DictReader(open(f)):
        head.add(r['row_id']); src.setdefault(r['row_id'], []).append(f)
bt = open('scripts/build_report.py').read()
for i in ids_in(bt):
    head.add(i); src.setdefault(i, []).append('scripts/build_report.py (Appendix B)')
for i in open('data/appendix_b_ids.txt').read().split():
    head.add(i); src.setdefault(i, []).append('Appendix B')
head = {i for i in head if i in by_id}

prev = {r['id'] for r in csv.DictReader(open('data/verification_sample.csv'))}
pool = [r for r in rows if r['id'] not in head and r['id'] not in prev]

def libfam(r):
    l = r['library'].lower()
    for k in ['pqm4', 'liboqs', 'wolf', 'mbed', 'mlkem-native', 'mldsa-native', 'pqclean', 'openssl', 'botan', 'fips']:
        if k in l: return k
    return 'other'
strata = {}
for r in pool:
    strata.setdefault((r['device_class'], libfam(r)), []).append(r)
rng = random.Random(SEED)
total = len(pool)
alloc = {}
for k, v in strata.items():
    alloc[k] = max(1, round(N_RANDOM * len(v) / total))
# adjust to exactly N_RANDOM
keys = sorted(strata, key=lambda k: -len(strata[k]))
while sum(alloc.values()) > N_RANDOM:
    for k in keys:
        if alloc[k] > 1 and sum(alloc.values()) > N_RANDOM: alloc[k] -= 1
while sum(alloc.values()) < N_RANDOM:
    for k in keys:
        if alloc[k] < len(strata[k]) and sum(alloc.values()) < N_RANDOM: alloc[k] += 1
sample = []
for k in sorted(strata):
    v = sorted(strata[k], key=lambda r: r['id'])
    sample += rng.sample(v, min(alloc[k], len(v)))
sample.sort(key=lambda r: r['id'])
cols = list(rows[0].keys())
with open('data/verify2_headline.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, cols); w.writeheader()
    for i in sorted(head): w.writerow(by_id[i])
with open('data/verify2_random.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, cols); w.writeheader()
    for r in sample: w.writerow(r)
json.dump({'seed': SEED, 'n_headline': len(head), 'n_random': len(sample), 'pool': total,
           'strata': {f'{k[0]}|{k[1]}': [len(strata[k]), alloc[k]] for k in sorted(strata)}},
          open('data/verify2_sets.json', 'w'), indent=1)
print('headline', len(head), 'random', len(sample), 'pool', total)
for k in sorted(strata): print(k, len(strata[k]), alloc[k])
