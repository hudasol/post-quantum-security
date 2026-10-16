"""Synthetic fleet study for the planner: scale, tornado sensitivity and a
staged migration.

Author: Huda Mueen

Run from planner/:  python fleetstudy.py
Writes planner/results/*.csv and docs/PLANNER_STUDY.md.

Every fleet here is SYNTHETIC: invented devices drawn from five invented
hardware classes with a fixed seed. They are not a real fleet, not measured
and not from any supplier. The planner supports planning; it is not a
security guarantee. Label of every result: estimated.
"""

import csv
import os
import random
import sys
import time
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from fleetplan.classify import (CLASSES, FIRMWARE_UPDATE, HARDWARE_REPLACEMENT,  # noqa: E402
                                HYBRID, NO_ACTION, UNKNOWN, classify_all)
from fleetplan.loader import parse_text  # noqa: E402
from fleetplan.rules import Parameters  # noqa: E402

ROOT = os.path.dirname(HERE)
RES = os.path.join(HERE, "results")
DOC = os.path.join(ROOT, "docs", "PLANNER_STUDY.md")
BASE_SEED = 20261016
SIZES = (10, 100, 1000)
COLUMNS = ["device_id", "ram_kb", "flash_kb", "bootrom_verifier_updatable",
           "link_bandwidth_bps", "service_life_remaining_years", "data_lifetime_years",
           "free_flash_kb", "free_ram_kb", "updatable_bootloader_stage", "core", "notes"]

# Five invented hardware classes (SYNTHETIC). Fields: core, RAM choices (kB),
# flash choices (kB), free fraction range, P(bootrom verifier updatable),
# P(updatable bootloader stage), link rate choices (bit/s), service life
# range, data lifetime range.
HW = {
    "H1": ("Cortex-M0+", (8, 16, 32), (64, 128, 256), (0.05, 0.4), 0.2, 0.3,
           (250, 9600), (2, 12), (1, 10)),
    "H2": ("Cortex-M4", (64, 96, 128), (256, 512), (0.05, 0.5), 0.4, 0.5,
           (9600, 57600), (2, 12), (1, 15)),
    "H3": ("Cortex-M4", (192, 256), (1024,), (0.1, 0.6), 0.5, 0.6,
           (57600,), (3, 15), (1, 20)),
    "H4": ("Cortex-M33", (256, 512), (1024, 2048), (0.2, 0.7), 0.7, 0.8,
           (57600, 1000000), (5, 15), (1, 25)),
    "H5": ("Cortex-M7", (512, 1024), (2048,), (0.3, 0.8), 0.8, 0.9,
           (1000000,), (5, 15), (1, 25)),
}
MIX = (("H1", 0.15), ("H2", 0.30), ("H3", 0.25), ("H4", 0.20), ("H5", 0.10))
P_MISSING_FREE = 0.08   # share of devices whose free memory is not known


def _device(rng, i, hw):
    core, rams, flashes, (f_lo, f_hi), p_upd, p_stage, links, svc, dat = HW[hw]
    ram, flash = rng.choice(rams), rng.choice(flashes)
    missing = rng.random() < P_MISSING_FREE
    free_ram = "" if missing else str(int(ram * rng.uniform(f_lo, f_hi)))
    free_flash = "" if missing else str(int(flash * rng.uniform(f_lo, f_hi)))
    return {
        "device_id": f"F{i:05d}", "ram_kb": str(ram), "flash_kb": str(flash),
        "bootrom_verifier_updatable": "yes" if rng.random() < p_upd else "no",
        "link_bandwidth_bps": str(rng.choice(links)),
        "service_life_remaining_years": str(rng.randint(*svc)),
        "data_lifetime_years": str(rng.randint(*dat)),
        "free_flash_kb": free_flash, "free_ram_kb": free_ram,
        "updatable_bootloader_stage": "yes" if rng.random() < p_stage else "no",
        "core": core, "notes": f"SYNTHETIC {hw}",
    }


def make_fleet(n, seed=None):
    """List of n SYNTHETIC device dicts, seed BASE_SEED + n by default."""
    rng = random.Random(BASE_SEED + n if seed is None else seed)
    names = [h for h, _ in MIX]
    weights = [w for _, w in MIX]
    return [_device(rng, i, rng.choices(names, weights)[0]) for i in range(n)]


def to_csv(devices):
    lines = ["# SYNTHETIC: invented devices for testing. Not a real fleet, not measured.",
             ",".join(COLUMNS)]
    lines += [",".join(d[c] for c in COLUMNS) for d in devices]
    return "\n".join(lines) + "\n"


def classify_devices(devices, params=None):
    inv = parse_text(to_csv(devices), "<synthetic>")
    return classify_all(inv, params)


def counts(results):
    c = {k: 0 for k in CLASSES}
    for r in results:
        c[r.cls] += 1
    return c


def need(params, results_row):
    """(flash_kb, ram_kb) the planner required for a classified device, from
    its Rule 4 reason; None if Rule 4 was not reached."""
    for reason in results_row.reasons:
        if reason.startswith("Rule 4: need for "):
            if "signature and KEM" in reason:
                return params.both_flash_kb, params.both_ram_kb
            if "signature only" in reason:
                return params.sig_flash_kb, params.sig_ram_kb
            return params.kem_flash_kb, params.kem_ram_kb
    return None


def violations(devices, results, params=None):
    """Devices given FIRMWARE_UPDATE or HYBRID whose free RAM or free flash
    is below the need that applied to them."""
    p = params or Parameters()
    bad = []
    for d, r in zip(devices, results):
        if r.cls not in (FIRMWARE_UPDATE, HYBRID):
            continue
        nd = need(p, r)
        if nd is None or d["free_flash_kb"] == "" or d["free_ram_kb"] == "":
            bad.append(d["device_id"])
            continue
        if Fraction(d["free_flash_kb"]) < nd[0] or Fraction(d["free_ram_kb"]) < nd[1]:
            bad.append(d["device_id"])
    return bad


# Tornado: (name, kind, low, high). kind 'param' overrides a Parameters
# field; 'scale' multiplies a device field; 'shift' adds years to a field.
TORNADO = [
    ("sig_horizon_year", "param", 2028, 2032),
    ("conf_horizon_year", "param", 2033, 2037),
    ("sig_flash_kb", "param", Fraction(31, 2), Fraction(93, 2)),
    ("sig_ram_kb", "param", Fraction(3, 2), Fraction(9, 2)),
    ("kem_flash_kb", "param", Fraction(7), Fraction(21)),
    ("kem_ram_kb", "param", Fraction(9, 2), Fraction(27, 2)),
    ("hs_bytes", "param", 3034, 9102),
    ("hs_budget_s", "param", Fraction(150), Fraction(450)),
    ("free_ram_kb", "scale", Fraction(1, 2), Fraction(3, 2)),
    ("free_flash_kb", "scale", Fraction(1, 2), Fraction(3, 2)),
    ("service_life_remaining_years", "shift", -2, 2),
    ("data_lifetime_years", "shift", -2, 2),
]


def _vary(devices, field, kind, v):
    out = []
    for d in devices:
        e = dict(d)
        if e[field] != "":
            if kind == "scale":
                e[field] = str(int(Fraction(e[field]) * v))
            else:
                e[field] = str(max(0, int(e[field]) + v))
        out.append(e)
    return out


def tornado(devices, base_params=None):
    """For each input, the share of devices whose class changes at the low
    and the high value, sorted by the larger swing."""
    p0 = base_params or Parameters()
    base = [r.cls for r in classify_devices(devices, p0)]
    rows = []
    for name, kind, lo, hi in TORNADO:
        row = {"input": name, "kind": kind, "low": lo, "high": hi}
        for tag, v in (("low", lo), ("high", hi)):
            if kind == "param":
                res = classify_devices(devices, p0.override(**{name: v}))
            else:
                res = classify_devices(_vary(devices, name, kind, v), p0)
            changed = sum(1 for a, b in zip(base, res) if a != b.cls)
            row[f"changed_{tag}"] = changed
            row[f"share_{tag}"] = changed / len(devices)
        row["swing"] = max(row["share_low"], row["share_high"])
        rows.append(row)
    rows.sort(key=lambda r: -r["swing"])
    return rows


def staged(devices, years=(2026, 2027, 2028, 2029, 2030), replacement="H4"):
    """Staged migration. In each wave the planner runs on the devices not yet
    migrated, with today_year set to the wave year and every device aged by
    the years elapsed. FIRMWARE_UPDATE and HYBRID devices are migrated in
    that wave; HARDWARE_REPLACEMENT devices are replaced (counted as
    migrated); NO_ACTION and UNKNOWN devices carry over to the next wave."""
    remaining = [dict(d) for d in devices]
    t0 = years[0]
    out = []
    migrated = 0
    for y in years:
        aged = _vary(remaining, "service_life_remaining_years", "shift", -(y - t0))
        res = classify_devices(aged, Parameters(today_year=y)) if aged else []
        c = counts(res)
        moved = c[FIRMWARE_UPDATE] + c[HYBRID] + c[HARDWARE_REPLACEMENT]
        migrated += moved
        out.append({"year": y, "in_wave": len(aged), **c,
                    "migrated_this_wave": moved, "migrated_total": migrated})
        keep = {r.device_id for r in res if r.cls in (NO_ACTION, UNKNOWN)}
        remaining = [d for d in remaining if d["device_id"] in keep]
    return out


def portable_c_params():
    """Thresholds from this repository's own emulated portable C build instead of the stack optimised pqm4
    rows (label: emulated inputs, estimated thresholds). Same derivation as docs/PLANNER_RULES.md: signature
    flash = ML-DSA-44 image text plus the 5,288 B header, signature RAM = ML-DSA-44 verify stack, KEM flash =
    ML-KEM-768 image text, KEM RAM = ML-KEM-768 decaps stack plus 6,004 B of buffers; kB = 1000 B, rounded up.
    Image text includes the harness and the C library, so these are upper bounds."""
    import math
    qr = os.path.join(ROOT, "bench", "mcu", "qemu_results")
    with open(os.path.join(qr, "stack.csv"), newline="", encoding="utf-8") as fh:
        st = {(r["param"], r["op"]): int(r["stack_bytes"]) for r in csv.DictReader(fh)
              if r["board"] == "an386" and r["opt"] == "-O2"}
    with open(os.path.join(qr, "image_size.csv"), newline="", encoding="utf-8") as fh:
        tx = {(r["alg"], r["param"]): int(r["text_bytes"]) for r in csv.DictReader(fh)
              if r["board"] == "an386" and r["opt"] == "-O2"}
    kb = lambda b: Fraction(math.ceil(b / 1000))  # noqa: E731
    return Parameters(sig_flash_kb=kb(tx[("mldsa", "44")] + 5288), sig_ram_kb=kb(st[("ML-DSA-44", "verify")]),
                      kem_flash_kb=kb(tx[("mlkem", "768")]), kem_ram_kb=kb(st[("ML-KEM-768", "decaps")] + 6004))


def _write(name, rows, fields):
    os.makedirs(RES, exist_ok=True)
    with open(os.path.join(RES, name), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: (str(r[k]) if isinstance(r[k], Fraction) else
                            ("%.4f" % r[k] if isinstance(r[k], float) else r[k]))
                        for k in fields})


def main():
    t_all = time.time()
    scale = []
    fleets = {}
    for n in SIZES:
        devs = make_fleet(n)
        fleets[n] = devs
        t0 = time.perf_counter()
        res = classify_devices(devs)
        dt = time.perf_counter() - t0
        c = counts(res)
        scale.append({"devices": n, "seed": BASE_SEED + n, "seconds": dt,
                      "violations": len(violations(devs, res)), **c})
    _write("scale.csv", scale, ["devices", "seed", "seconds", "violations"] + list(CLASSES))
    tor = tornado(fleets[1000])
    _write("tornado.csv", tor, ["input", "kind", "low", "high", "changed_low", "share_low",
                                "changed_high", "share_high", "swing"])
    stg = staged(fleets[1000])
    _write("staged.csv", stg, ["year", "in_wave"] + list(CLASSES)
           + ["migrated_this_wave", "migrated_total"])
    pc = portable_c_params()
    scen = []
    for tag, p in (("stack optimised pqm4 rows (default)", Parameters()), ("portable C, emulated build", pc)):
        res = classify_devices(fleets[1000], p)
        scen.append({"thresholds": tag, "sig_flash_kb": p.sig_flash_kb, "sig_ram_kb": p.sig_ram_kb,
                     "kem_flash_kb": p.kem_flash_kb, "kem_ram_kb": p.kem_ram_kb,
                     "violations": len(violations(fleets[1000], res, p)), **counts(res)})
    _write("thresholds.csv", scen, ["thresholds", "sig_flash_kb", "sig_ram_kb", "kem_flash_kb", "kem_ram_kb",
                                    "violations"] + list(CLASSES))
    hw_rows = [{"class": h, "core": v[0], "ram_kb": " ".join(map(str, v[1])),
                "flash_kb": " ".join(map(str, v[2])), "share": dict(MIX)[h]} for h, v in HW.items()]
    _write("hardware_classes.csv", hw_rows, ["class", "core", "ram_kb", "flash_kb", "share"])

    L = ["# Planner study on synthetic fleets", "",
         "Author: Huda Mueen. Generated by `cd planner && python fleetstudy.py`; do not edit by hand. "
         "Label: **estimated**. Every fleet is **SYNTHETIC**: invented devices from five invented hardware "
         "classes (`planner/results/hardware_classes.csv`), seed %d plus the fleet size. Not a real fleet, "
         "not measured. The planner supports planning; it is not a security guarantee." % BASE_SEED, "",
         "## 1. Scale and the memory limit property", "",
         "| devices | seed | classify time (s) | violations | " + " | ".join(CLASSES) + " |",
         "|---|---|---|---|" + "---|" * len(CLASSES)]
    for s in scale:
        L.append("| %d | %d | %.3f | %d | %s |" % (s["devices"], s["seed"], s["seconds"], s["violations"],
                                                    " | ".join(str(s[c]) for c in CLASSES)))
    L += ["", "A violation is a FIRMWARE_UPDATE or HYBRID device whose free RAM or free flash is below the "
          "need that applied to it. Times are host wall time of the classifier on this machine.", "",
          "## 2. Tornado sensitivity (1000 device fleet)", "",
          "Share of devices whose class changes when one input moves to its low or high value; all other "
          "inputs at their defaults. Rule parameters move by minus and plus 50 percent (horizon years by "
          "2 years); device fields are scaled or shifted across the whole fleet.", "",
          "| input | low | high | changed at low | changed at high |", "|---|---|---|---|---|"]
    for r in tor:
        L.append("| %s | %s | %s | %.1f%% | %.1f%% |" % (r["input"], r["low"], r["high"],
                                                        100 * r["share_low"], 100 * r["share_high"]))
    L += ["", "## 3. Staged migration (1000 device fleet, waves 2026 to 2030)", "",
          "Each wave classifies the devices not yet migrated with the wave year as the planning year and "
          "remaining service life reduced by the years elapsed. FIRMWARE_UPDATE and HYBRID devices are "
          "migrated in that wave, HARDWARE_REPLACEMENT devices are replaced, and the rest carry over.", "",
          "| year | devices in wave | " + " | ".join(CLASSES) + " | migrated in wave | migrated total |",
          "|---|---|" + "---|" * len(CLASSES) + "---|---|"]
    for s in stg:
        L.append("| %d | %d | %s | %d | %d |" % (s["year"], s["in_wave"], " | ".join(str(s[c]) for c in CLASSES),
                                                s["migrated_this_wave"], s["migrated_total"]))
    L += ["", "## 4. Which implementation the thresholds assume (1000 device fleet)", "",
          "The default thresholds come from stack optimised pqm4 rows (hand written assembly; "
          "`docs/PLANNER_RULES.md`). The second line uses this repository's own portable C build as run in the "
          "emulator (`bench/mcu/qemu_results/`), which needs far more RAM. The violation count is an internal "
          "consistency check against the thresholds in force, not evidence that the code fits a real device.", "",
          "| thresholds | sig flash kB | sig RAM kB | KEM flash kB | KEM RAM kB | violations | " + " | ".join(CLASSES) + " |",
          "|---|---|---|---|---|---|" + "---|" * len(CLASSES)]
    for s_ in scen:
        L.append("| %s | %s | %s | %s | %s | %d | %s |" % (s_["thresholds"], s_["sig_flash_kb"], s_["sig_ram_kb"],
                 s_["kem_flash_kb"], s_["kem_ram_kb"], s_["violations"], " | ".join(str(s_[c]) for c in CLASSES)))
    L += ["", "## Limits", "",
          "1. The hardware classes, their shares and every distribution are invented; the tornado ranking "
          "depends on them. A real inventory would change every number here.",
          "2. The tornado moves one input at a time; interactions are not explored.",
          "3. The tornado and section 1 use the default thresholds, which assume stack optimised assembly; with "
          "portable C thresholds (section 4) the memory inputs matter far more, so the ranking above holds only for "
          "the default assumption.",
          "4. The staged model assumes every action in a wave succeeds and that replaced hardware leaves "
          "the fleet; it does not model budgets, downtime or partial rollouts.", "",
          "_This tool supports planning. It is not a security guarantee._", ""]
    with open(DOC, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(L))
    print("wrote planner/results/ and docs/PLANNER_STUDY.md in %.1f s" % (time.time() - t_all))


if __name__ == "__main__":
    main()
