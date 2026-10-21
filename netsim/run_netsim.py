"""Run the ns-3 scenarios of the network simulator check and write raw CSVs.

Author: Huda Mueen.

Run from the repository root after netsim/fetch_build.sh:
    python3 -m netsim.run_netsim [--ns3 ../third_party/ns-3-dev]
                                 [--only lrwpan|lora] [--quick]
Writes netsim/results/lrwpan_runs.csv, lora_toa.csv and lora_flights.csv,
labelled "simulated (network)". The study document is generated from these
committed files by python3 -m netsim.make_study, which needs no ns-3.

Only sizes and times are simulated. No cryptographic operation.
"""
import argparse
import csv
import glob
import os
import subprocess
import sys
import time

from . import cells

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "netsim", "results")
NS3_DEFAULT = os.path.join(os.path.dirname(ROOT), "third_party", "ns-3-dev")
LABEL = "simulated (network)"


def binary(ns3, name):
    hits = sorted(glob.glob(os.path.join(ns3, "build", "scratch", "*netsim-%s*" % name)))
    hits = [h for h in hits if os.access(h, os.X_OK) and os.path.isfile(h)]
    if not hits:
        raise SystemExit("ns-3 program %s not built under %s; run netsim/fetch_build.sh" % (name, ns3))
    return hits[0]


def run(ns3, exe, args):
    env = dict(os.environ)
    lib = os.path.join(ns3, "build", "lib")
    env["LD_LIBRARY_PATH"] = lib + (":" + env["LD_LIBRARY_PATH"] if env.get("LD_LIBRARY_PATH") else "")
    cmd = ["nice", "-n", "10", exe] + ["--%s=%s" % (k, v) for k, v in args]
    out = subprocess.run(cmd, env=env, capture_output=True, text=True, check=True)
    return out.stdout


def lrwpan(ns3, quick=False, only=()):
    exe = binary(ns3, "lrwpan_sr")
    hdr = run(ns3, exe, [("header", 1)]).strip().split(",")[1:]
    fields = ["label", "group", "cell", "cause", "value"] + hdr + ["wall_clock_s"]
    rows = []
    old = {}
    path = os.path.join(RES, "lrwpan_runs.csv")
    if only and os.path.exists(path):
        with open(path, newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                old.setdefault(r["cell"], []).append(r)
    for c in cells.lrwpan_cells():
        if only and c["cell"] not in only:
            rows.extend(old.get(c["cell"], []))
            continue
        runs = c["runs"][:2] if quick else c["runs"]
        for r in runs:
            args = list(c["args"].items()) + [("seed", cells.SEED), ("run", r), ("tag", c["cell"])]
            t0 = time.time()
            out = run(ns3, exe, args)
            line = [x for x in out.splitlines() if x.startswith("RESULT,")][0]
            vals = line.split(",")[1:]
            row = {"label": LABEL, "group": c["group"], "cell": c["cell"], "cause": c["cause"],
                   "value": c["value"], "wall_clock_s": "%.2f" % (time.time() - t0)}
            row.update(dict(zip(hdr, vals)))
            rows.append(row)
            print(c["cell"], r, row["completed"], row["time_s"], flush=True)
    write(os.path.join(RES, "lrwpan_runs.csv"), rows, fields)


def lora(ns3):
    exe = binary(ns3, "lora_flights")
    toa = []
    for dr in (0, 5):
        out = run(ns3, exe, [("mode", "toa"), ("dr", dr),
                             ("sizes", ",".join(str(s) for s in cells.LORA_TOA_SIZES))])
        for line in out.splitlines():
            if line.startswith("TOA,"):
                _, d, n, t = line.split(",")
                toa.append({"label": LABEL, "dr": int(d), "phy_payload_bytes": int(n),
                            "toa_s_ns3": float(t)})
    write(os.path.join(RES, "lora_toa.csv"), toa, ["label", "dr", "phy_payload_bytes", "toa_s_ns3"])
    fl = []
    frames = []
    for prot, flights in cells.lora_flights():
        for dr, cap in ((0, 51), (5, 222)):
            spec = ",".join("%s:%d" % (s, b) for s, b in flights)
            out = run(ns3, exe, [("mode", "flights"), ("dr", dr), ("cap", cap), ("flights", spec),
                                 ("seed", cells.SEED), ("run", 1), ("tag", prot)])
            for line in out.splitlines():
                if line.startswith("FRAME,"):
                    v = line.split(",")
                    frames.append({"label": LABEL, "protocol": v[1], "dr": int(v[2]), "index": int(v[3]),
                                   "flight": int(v[4]), "side": v[5], "app_bytes": int(v[6]),
                                   "phy_payload_bytes": int(v[7]), "start_s": float(v[8]),
                                   "toa_s": float(v[9])})
                if line.startswith("FLIGHTS,"):
                    v = line.split(",")
                    fl.append({"label": LABEL, "protocol": v[1], "dr": int(v[2]), "cap_bytes": int(v[3]),
                               "fragments": int(v[4]), "fragments_sent": int(v[5]),
                               "handshake_s_ns3": float(v[6]), "flights": spec,
                               "seed": cells.SEED, "run": 1})
            print(prot, dr, fl[-1]["handshake_s_ns3"], flush=True)
    write(os.path.join(RES, "lora_flights.csv"), fl,
          ["label", "protocol", "dr", "cap_bytes", "fragments", "fragments_sent", "handshake_s_ns3",
           "flights", "seed", "run"])
    write(os.path.join(RES, "lora_frames.csv"), frames,
          ["label", "protocol", "dr", "index", "flight", "side", "app_bytes", "phy_payload_bytes",
           "start_s", "toa_s"])


def write(path, rows, fields):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--ns3", default=os.environ.get("NS3_DIR", NS3_DEFAULT))
    ap.add_argument("--only", choices=("lrwpan", "lora"))
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--cells", default="", help="comma separated cell names to run; their rows replace those in lrwpan_runs.csv")
    a = ap.parse_args(argv)
    if a.only in (None, "lora"):
        lora(a.ns3)
    if a.only in (None, "lrwpan"):
        lrwpan(a.ns3, a.quick, [c for c in a.cells.split(",") if c])
    return 0


if __name__ == "__main__":
    sys.exit(main())
