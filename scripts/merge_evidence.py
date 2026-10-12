#!/usr/bin/env python3
"""Merge stream evidence CSVs into data/evidence.csv and run schema checks.

Only mechanical operations are done here:
  * repair rows split by an unquoted comma in location_in_source (24 fields -> 23),
  * add derived label columns (stream, scheme_family, standard_status, device_class)
    by explicit string rules, so that plots can filter without editing source values,
  * validate required fields.
No numeric value is changed, filled or interpolated.
"""
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "evidence.csv"

BASE_COLS = [
    "id", "scheme", "parameter_set", "operation", "device", "core", "clock_mhz",
    "library", "library_version", "compiler_flags_or_notes", "cycles", "ram_bytes",
    "stack_bytes", "flash_or_code_bytes", "energy_uj", "key_or_sig_size_bytes",
    "size_kind", "evidence_type", "source_title", "source_url", "retrieval_date",
    "location_in_source", "comparability_warning",
]
DERIVED = ["stream", "scheme_family", "standard_status", "device_class"]
NUMERIC = ["clock_mhz", "cycles", "ram_bytes", "stack_bytes", "flash_or_code_bytes",
           "energy_uj", "key_or_sig_size_bytes"]


def read_rows(path, stream):
    rows = []
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        header = next(reader)
        if header != BASE_COLS:
            sys.exit(f"{path.name}: header differs from protocol schema")
        for lineno, r in enumerate(reader, start=2):
            if len(r) == len(BASE_COLS) + 1:
                # known defect: unquoted comma inside location_in_source (index 21)
                r = r[:21] + [r[21] + "," + r[22]] + r[23:]
            if len(r) != len(BASE_COLS):
                sys.exit(f"{path.name} line {lineno}: {len(r)} fields, cannot repair")
            d = dict(zip(BASE_COLS, r))
            d["stream"] = stream
            rows.append(d)
    return rows


def scheme_family(s):
    t = s.lower()
    if t.startswith("pq/t hybrid"):
        return "hybrid-KEM"
    if "classical" in t or t.startswith(("ecdsa", "ecdh", "x25519", "ed25519", "rsa")):
        return "classical"
    if "ml-kem" in t or "kyber" in t:
        return "ML-KEM"
    if "ml-dsa" in t or "dilithium" in t:
        return "ML-DSA"
    if "slh-dsa" in t or "sphincs" in t:
        return "SLH-DSA"
    if "lms" in t or t.startswith("hss"):
        return "LMS"
    if "mavlink" in t:
        return "symmetric-MAC"
    if t.startswith("none"):
        return "hash-baseline"
    if "xmss" in t:
        return "XMSS"
    return "other"


def standard_status(s):
    t = s.lower()
    if "pre-standard" in t or "round" in t or "not fips" in t:
        return "pre-standard"
    if "published as" in t:
        return "check-source"  # source used old name for what may be final parameters
    if t.startswith(("ml-kem", "ml-dsa", "slh-dsa")):
        return "final-FIPS-name"
    if "kyber" in t or "dilithium" in t or "sphincs" in t:
        return "pre-standard"
    return "n/a"


def device_class(row):
    dev = row["device"].lower()
    core = row["core"].lower()
    if dev.startswith("n/a (standard)") or row["size_kind"] == "standard":
        return "standard-size"
    if dev.startswith("x86") or core.startswith("x86"):
        return "host-cpu"
    if any(k in dev + core for k in ("fpga", "5 nm", "zynq", "artix", "vexriscv", "ibex",
                                     "soc", "asic", "simulation")):
        return "fpga-asic-soft-core"
    if dev == "" and core == "":
        return "no-device"
    return "mcu"


def main():
    rows = (read_rows(RAW / "S2_evidence.csv", "S2") + read_rows(RAW / "S3_evidence.csv", "S3")
            + read_rows(RAW / "S7_verified.csv", "S7"))
    problems = []
    repaired = []
    seen = set()
    for r in rows:
        if r["id"] in seen:
            problems.append(f"duplicate id {r['id']}")
        seen.add(r["id"])
        if r["evidence_type"] != "published":
            problems.append(f"{r['id']}: evidence_type={r['evidence_type']!r}")
        for col in ("source_url", "retrieval_date", "location_in_source"):
            if not r[col].strip():
                problems.append(f"{r['id']}: empty {col}")
        if not re.match(r"^https?://", r["source_url"]):
            problems.append(f"{r['id']}: bad url")
        for col in NUMERIC:
            v = r[col].strip()
            if v and not re.match(r"^\d+(\.\d+)?$", v):
                # Mechanical, logged repair: a source that states an approximate/qualified
                # value in text keeps it verbatim in the warning column; numeric cell is blanked.
                r["comparability_warning"] = (
                    f"Source states {col} as text, not a number: '{v}'. "
                    + r["comparability_warning"]
                ).strip()
                r[col] = ""
                repaired.append(f"{r['id']}: {col} text moved to comparability_warning")
        r["scheme_family"] = scheme_family(r["scheme"])
        r["standard_status"] = standard_status(r["scheme"])
        r["device_class"] = device_class(r)
    # Apply logged corrections (data/corrections.csv); old_value must match exactly.
    by_id = {r["id"]: r for r in rows}
    corr_path = ROOT / "data" / "corrections.csv"
    if corr_path.exists():
        with open(corr_path, newline="", encoding="utf-8") as fh:
            for c in csv.DictReader(fh):
                r = by_id[c["id"]]
                if r[c["field"]] != c["old_value"]:
                    sys.exit(f"correction {c['id']}.{c['field']}: old_value does not match current cell")
                r[c["field"]] = c["new_value"]
                print(f"corrected: {c['id']}.{c['field']} ({c['reason'][:60]})")
    # pqm4 board and clock rule (data/pqm4_board_clock.csv, from data/raw/S6_pqm4_config.md).
    rule_path = ROOT / "data" / "pqm4_board_clock.csv"
    if rule_path.exists():
        with open(rule_path, newline="", encoding="utf-8") as fh:
            rule = {k["key"]: k["value"] for k in csv.DictReader(fh)}
        n_pq = 0
        for r in rows:
            if "mupq/pqm4" not in r["source_url"]:
                continue
            if rule["warning_old_clause"] not in r["comparability_warning"]:
                sys.exit(f"{r['id']}: pqm4 warning clause not found; rule file out of date")
            r["device"] = rule["device_new"]
            r["clock_mhz"] = rule["clock_mhz_new"]
            r["comparability_warning"] = r["comparability_warning"].replace(
                rule["warning_old_clause"], rule["warning_new_clause"], 1)
            r["compiler_flags_or_notes"] = (r["compiler_flags_or_notes"].rstrip("; ") + "; " + rule["note_suffix"]).strip()
            n_pq += 1
        print(f"pqm4 board and clock rule applied to {n_pq} rows")
    ambiguous = [r["id"] for r in rows if re.search(r"\bor Table\b", r["location_in_source"])]
    print(f"rows whose location_in_source still names alternative tables: {len(ambiguous)}")
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=BASE_COLS + DERIVED, quoting=csv.QUOTE_MINIMAL)
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {OUT} with {len(rows)} rows")
    from collections import Counter
    print("scheme_family:", Counter(r["scheme_family"] for r in rows))
    print("standard_status:", Counter(r["standard_status"] for r in rows))
    print("device_class:", Counter(r["device_class"] for r in rows))
    print("unmapped schemes:", sorted({r["scheme"] for r in rows if r["scheme_family"] == "other"}))
    print("check-source schemes:", sorted({r["scheme"] for r in rows if r["standard_status"] == "check-source"}))
    for msg in repaired:
        print("repaired:", msg)
    if problems:
        print(f"{len(problems)} schema problems:")
        for p in problems[:50]:
            print("  ", p)
        sys.exit(1)
    print("schema check passed")


if __name__ == "__main__":
    main()
