#!/usr/bin/env python3
"""Compare planner output on the synthetic inventory with the hand written expectations in docs/PREDICTIONS_PLANNER.csv."""
import csv, subprocess, sys, io
out = subprocess.run([sys.executable, '-m', 'fleetplan', '../planner/examples/synthetic_inventory.csv' if False else 'examples/synthetic_inventory.csv', '--format', 'csv'],
                     cwd='planner', capture_output=True, text=True, check=True).stdout
rows = [l for l in out.splitlines() if not l.startswith('#')]
got = {r['device_id']: r['class'] for r in csv.DictReader(io.StringIO('\n'.join(rows)))}
exp = {r['device_id']: r['expected_class'] for r in csv.DictReader(open('docs/PREDICTIONS_PLANNER.csv'))}
hit = 0
for k in sorted(exp):
    ok = got.get(k) == exp[k]; hit += ok
    print(f"{k} expected {exp[k]:30s} got {got.get(k)} {'HIT' if ok else 'MISS'}")
print(f"{hit} of {len(exp)} agree")
