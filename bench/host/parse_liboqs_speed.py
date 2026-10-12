#!/usr/bin/env python3
"""Parse liboqs speed_kem / speed_sig output into CSV rows.

HOST MEASUREMENT, not microcontroller result. Rows are labelled
evidence_type='host-measured' and must never be merged into data/evidence.csv.

Usage: parse_liboqs_speed.py RAW_DIR OUT_CSV
RAW_DIR holds files named <variant>_run<N>_<ALG>.txt (one speed_* invocation each).
"""
import csv, re, sys, pathlib

FIELDS = ["scheme", "parameter_set", "operation", "build_variant", "run_index",
          "iterations", "total_time_s", "mean_time_us", "stdev_time_us",
          "cycles_mean", "cycles_stdev", "evidence_type"]
NAME = re.compile(r"^(?P<v>[a-z]+)_run(?P<i>\d+)_(?P<alg>.+)\.txt$")

def scheme_of(alg):
    a = alg.upper()
    if a.startswith("ML-KEM"): return "ML-KEM", alg
    if a.startswith("ML-DSA"): return "ML-DSA", alg
    if a.startswith("SLH_DSA") or a.startswith("SLH-DSA"):
        return "SLH-DSA", alg.replace("SLH_DSA_PURE_", "SLH-DSA-").replace("_", "-")
    return alg, alg

def num(s):
    s = s.strip()
    return float(s) if s else None

def parse_file(path):
    m = NAME.match(path.name)
    if not m: return []
    scheme, pset = scheme_of(m["alg"])
    rows = []
    for line in path.read_text().splitlines():
        cells = [c.strip() for c in line.split("|")]
        if len(cells) < 7 or cells[0] in ("Operation", "") or set(cells[0]) <= set("-"):
            continue
        if cells[1] == "" and cells[2] == "":  # algorithm header row
            continue
        try:
            it = int(cells[1]); tot = float(cells[2]); mean = float(cells[3])
        except ValueError:
            continue
        rows.append(dict(scheme=scheme, parameter_set=pset, operation=cells[0],
                         build_variant=m["v"], run_index=int(m["i"]), iterations=it,
                         total_time_s=tot, mean_time_us=mean, stdev_time_us=num(cells[4]),
                         cycles_mean=num(cells[5]), cycles_stdev=num(cells[6]),
                         evidence_type="host-measured"))
    return rows

def main(raw_dir, out_csv):
    rows = []
    for p in sorted(pathlib.Path(raw_dir).glob("*.txt")):
        rows += parse_file(p)
    rows.sort(key=lambda r: (r["build_variant"], r["scheme"], r["parameter_set"],
                             r["operation"], r["run_index"]))
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, FIELDS); w.writeheader(); w.writerows(rows)
    print(f"wrote {len(rows)} rows to {out_csv}")

if __name__ == "__main__":
    if len(sys.argv) != 3: sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
