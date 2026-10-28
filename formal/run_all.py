"""Run every ProVerif query of the formal verification study and record the results.

Author: Huda Mueen.

Run from the repository root:
    sh formal/install.sh                 (once; builds ProVerif 2.05 outside the repository)
    python3 -m formal.build_models       (renders formal/models/*.pv)
    python3 -m formal.run_all            (runs every model, writes the results)
    python3 -m formal.run_all --models a b --keep-existing
                                         (reruns models a and b one after the other, keeps the earlier
                                          rows and adds only rows of new queries)
    python3 -m formal.make_doc           (writes docs/FORMAL_VERIFICATION.md)

The ProVerif binary is taken from the environment variable PROVERIF, then from
PATH, then from third_party/proverif/proverif2.05/proverif next to the
repository. Writes formal/results/proverif_results.csv and one summary log per
model in formal/results/logs/. Label of every result: modelled (a formal proof
or counterexample under the Dolev Yao attacker model with abstract, perfect
primitives; not a statement about any implementation).
"""
import argparse
import csv
import os
import re
import shutil
import subprocess
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MODELS = os.path.join(HERE, "models")
RESULTS = os.path.join(HERE, "results")
CSV_PATH = os.path.join(RESULTS, "proverif_results.csv")
LOGS = os.path.join(RESULTS, "logs")
PINNED_VERSION = "2.05"
TIMEOUT_S = 1800
# Address space cap of one ProVerif run in MB (the run host has about 7 GB shared with other jobs).
MEM_LIMIT_MB = 4096
LABEL = "modelled"
NOTE = ("formal result of ProVerif under the Dolev Yao attacker model with abstract perfect primitives; "
        "unbounded sessions; not a statement about any implementation; the label applies to result and weaker_form, "
        "run_time_s_host_measured is the wall clock time of the whole model file on the run host")
FIELDS = ["model", "design", "attacker_setting", "property_id", "property", "query", "result",
          "weaker_form", "run_time_s_host_measured", "proverif_version", "label", "note"]

QUERY_RE = re.compile(r"\(\* ([A-Z][A-Z0-9]*): (.*?) \*\)\s*\n(query [^\n]*)")
HEAD_RE = re.compile(r"Design: (.*?)\n\s*Attacker setting: (.*?) \*\)", re.S)


def find_proverif():
    env = os.environ.get("PROVERIF")
    if env and os.path.isfile(env):
        return env
    p = shutil.which("proverif")
    if p:
        return p
    tp = os.environ.get("THIRD_PARTY", os.path.join(os.path.dirname(ROOT), "third_party"))
    cand = os.path.join(tp, "proverif", f"proverif{PINNED_VERSION}", "proverif")
    return cand if os.path.isfile(cand) else None


def proverif_version(binary):
    p = subprocess.run([binary, "-help"], capture_output=True, text=True)
    out = p.stdout + p.stderr
    m = re.search(r"Proverif (\d+\.\d+)", out)
    return m.group(1) if m else "unknown"


def parse_model(path):
    """Return (design, attacker setting, [(id, title, query text)]) from a model file."""
    text = open(path).read()
    h = HEAD_RE.search(text)
    design = " ".join(h.group(1).split()) if h else ""
    setting = " ".join(h.group(2).split()) if h else ""
    queries = [(m.group(1), m.group(2), m.group(3).strip()) for m in QUERY_RE.finditer(text)]
    return design, setting, queries


def classify(line):
    if line.endswith("is true."):
        return "proved"
    if line.endswith("is false."):
        return "counterexample"
    if line.endswith("cannot be proved."):
        return "cannot be proved"
    return "unparsed"


def parse_output(out):
    """Return a list of (main result, weaker form or '') in query order."""
    res = []
    for line in out.splitlines():
        line = line.strip()
        if not line.startswith("RESULT "):
            continue
        if line.startswith("RESULT (but") or line.startswith("RESULT (even"):
            if res:
                inner = line[len("RESULT ("):].rstrip(")")
                kind = "proved" if "is true" in inner else ("counterexample" if "is false" in inner else "cannot be proved")
                weak = "non injective form " + kind
                res[-1] = (res[-1][0], weak)
            continue
        res.append((classify(line), ""))
    return res


def summary_log(out):
    """Keep the verification summary and the tool's one line goal statements only. For a model with a
    restriction, ProVerif 2.05 prints its summary as 'Query(ies):' followed by ' - Query ...' lines; both
    forms are kept."""
    keep = [ln for ln in out.splitlines()
            if ln.startswith("goal reachable") or ln.startswith("RESULT") or ln.startswith("Query ")
            or ln.startswith("Query(ies):") or ln.startswith(" - Query ")]
    return "\n".join(keep) + "\n"


def _limit_memory(mb):
    """Return a function that caps the address space of the child process (None: no cap)."""
    if not mb:
        return None

    def apply():
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (mb * 1024 * 1024, mb * 1024 * 1024))
    return apply


def run_model(binary, path, timeout=TIMEOUT_S, mem_mb=MEM_LIMIT_MB):
    """Run one model; status is ok, timeout, or memory (the run stopped at the address space cap)."""
    t0 = time.time()
    try:
        p = subprocess.run(["nice", "-n", "10", binary, path], capture_output=True, text=True, timeout=timeout,
                           preexec_fn=_limit_memory(mem_mb))
        out, status = p.stdout + p.stderr, "ok"
        if p.returncode != 0 and ("out of memory" in out.lower() or p.returncode < 0):
            status = "memory"
    except subprocess.TimeoutExpired as e:
        out, status = (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or ""), "timeout"
    return out, status, time.time() - t0


def merge_rows(old_rows, new_rows):
    """Keep every earlier row and add only the rows of (model, property id) pairs that are new. An earlier row
    keeps its result, weaker form and run time; only its design and attacker setting columns follow the current
    model header (a documented header fix). Returns (rows, list of earlier pairs whose rerun result differs)."""
    old = {(r["model"], r["property_id"]): r for r in old_rows}
    merged, changed = [], []
    seen = set()
    for r in new_rows:
        key = (r["model"], r["property_id"])
        seen.add(key)
        if key in old:
            o = dict(old[key])
            if (o["result"], o["weaker_form"]) != (r["result"], r["weaker_form"]):
                changed.append((key, o["result"], r["result"]))
            o["design"], o["attacker_setting"] = r["design"], r["attacker_setting"]
            merged.append(o)
        else:
            merged.append(r)
    merged += [r for k, r in old.items() if k not in seen]
    return merged, changed


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="*", help="model names to run (default: all)")
    ap.add_argument("--timeout", type=int, default=TIMEOUT_S)
    ap.add_argument("--mem-mb", type=int, default=MEM_LIMIT_MB, help="address space cap per run in MB (0: none)")
    ap.add_argument("--keep-existing", action="store_true",
                    help="keep the earlier rows of the rerun models and add only rows of new queries")
    args = ap.parse_args(argv)
    binary = find_proverif()
    if not binary:
        raise SystemExit("ProVerif not found; run sh formal/install.sh or set PROVERIF")
    version = proverif_version(binary)
    os.makedirs(LOGS, exist_ok=True)
    names = sorted(f[:-3] for f in os.listdir(MODELS) if f.endswith(".pv"))
    if args.models:
        names = [n for n in names if n in args.models]
    old, earlier = [], []
    if os.path.exists(CSV_PATH) and (args.models or args.keep_existing):
        allrows = list(csv.DictReader(open(CSV_PATH)))
        old = [r for r in allrows if r["model"] not in names]
        earlier = [r for r in allrows if r["model"] in names]
    rows = list(old)
    fresh = []
    for name in names:
        path = os.path.join(MODELS, name + ".pv")
        design, setting, queries = parse_model(path)
        out, status, dt = run_model(binary, path, args.timeout, args.mem_mb)
        with open(os.path.join(LOGS, name + ".txt"), "w") as f:
            f.write(summary_log(out))
        results = parse_output(out)
        for i, (qid, title, qtext) in enumerate(queries):
            if status == "timeout" and i < len(results):
                res, weak = results[i]  # this query finished before the time limit
            elif status == "timeout":
                res, weak = f"cannot be proved (timeout {args.timeout} s)", ""
            elif status == "memory" and i >= len(results):
                res, weak = f"cannot be proved (memory cap {args.mem_mb} MB)", ""
            elif i < len(results):
                res, weak = results[i]
            else:
                res, weak = "error", ""
            fresh.append(dict(model=name, design=design, attacker_setting=setting, property_id=qid, property=title,
                             query=qtext, result=res, weaker_form=weak, run_time_s_host_measured=f"{dt:.1f}",
                             proverif_version=version, label=LABEL, note=NOTE))
        print(f"{name}: {len(queries)} queries, {dt:.1f} s, {status}, {[r[0] for r in results]}", flush=True)
    if args.keep_existing:
        merged, changed = merge_rows(earlier, fresh)
        for key, was, now in changed:
            print(f"WARNING {key}: earlier result {was!r}, rerun {now!r}; the earlier row is kept")
        rows += merged
    else:
        rows += fresh
    rows.sort(key=lambda r: (r["model"], r["property_id"]))
    with open(CSV_PATH, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {CSV_PATH} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
