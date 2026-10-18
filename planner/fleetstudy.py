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
SEED_DRAWS = 5      # extra 1000 device fleets to show seed to seed variation
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
    ("sig_flash_kb", "param", Fraction(30, 2), Fraction(90, 2)),
    ("sig_ram_kb", "param", Fraction(7, 2), Fraction(21, 2)),
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
        if kind == "param" and name not in ("sig_horizon_year", "conf_horizon_year"):
            # minus and plus 50 percent of the value in force, so each scenario is varied around its own value
            lo, hi = Fraction(getattr(p0, name)) / 2, Fraction(getattr(p0, name)) * 3 / 2
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


HEADER = 4840        # wolfBoot ML-DSA-44 example image header (data/raw/S4_migration.md line 85)
SIG_BUFFERS = 3732   # ML-DSA-44 public key 1,312 B plus signature 2,420 B held by the verifier


def portable_c_params():
    """Thresholds from this repository's own emulated portable C build instead of the stack optimised pqm4
    rows (label: emulated inputs, estimated thresholds). Same derivation as docs/PLANNER_RULES.md: signature
    flash = ML-DSA-44 image text plus the 4,840 B ML-DSA-44 header, signature RAM = ML-DSA-44 verify stack plus the
    1,312 B public key and 2,420 B signature buffers, KEM flash =
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
    return Parameters(sig_flash_kb=kb(tx[("mldsa", "44")] + HEADER), sig_ram_kb=kb(st[("ML-DSA-44", "verify")] + SIG_BUFFERS),
                      kem_flash_kb=kb(tx[("mlkem", "768")]), kem_ram_kb=kb(st[("ML-KEM-768", "decaps")] + 6004))


def published_params(ids):
    """Thresholds from published pqm4 rows of data/evidence.csv (label: published inputs, estimated thresholds),
    with the derivation of docs/PLANNER_RULES.md: signature flash = ML-DSA-44 code size plus the 4,840 B header,
    signature RAM = ML-DSA-44 verify stack, KEM flash = ML-KEM-768 code size, KEM RAM = ML-KEM-768 decaps stack
    plus 6,004 B of buffers; kB = 1000 B, rounded up. pqm4 code sizes exclude hashing and libc."""
    import math
    with open(os.path.join(ROOT, "data", "evidence.csv"), newline="", encoding="utf-8") as fh:
        ev = {r["id"]: r for r in csv.DictReader(fh)}
    sig_v, kem_d = ev[ids["sig_verify"]], ev[ids["kem_decaps"]]
    assert sig_v["parameter_set"] == "ML-DSA-44" and sig_v["operation"] == "verify"
    assert kem_d["parameter_set"] == "ML-KEM-768" and kem_d["operation"] == "decaps"
    kb = lambda b: Fraction(math.ceil(b / 1000))  # noqa: E731
    return Parameters(sig_flash_kb=kb(int(sig_v["flash_or_code_bytes"]) + HEADER),
                      sig_ram_kb=kb(int(sig_v["stack_bytes"]) + SIG_BUFFERS),
                      kem_flash_kb=kb(int(kem_d["flash_or_code_bytes"])),
                      kem_ram_kb=kb(int(kem_d["stack_bytes"]) + 6004))


def scenarios():
    """(key, label, basis, Parameters) for the four threshold scenarios."""
    return [
        ("stack_asm", "stack optimised assembly (pqm4 m4fstack, published)", "S2-0036, S2-0027",
         published_params({"sig_verify": "S2-0036", "kem_decaps": "S2-0027"})),
        ("speed_asm", "speed optimised assembly (pqm4 m4f and m4fspeed, published; middle case)",
         "S2-0033, S2-0024", published_params({"sig_verify": "S2-0033", "kem_decaps": "S2-0024"})),
        ("portable_c", "portable C (repository build, emulated)", "bench/mcu/qemu_results",
         portable_c_params()),
        ("reference_c", "reference C (pqm4 clean, published)", "S2-0030, S2-0021",
         published_params({"sig_verify": "S2-0030", "kem_decaps": "S2-0021"})),
    ]


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
    stg = staged(fleets[1000])
    _write("staged.csv", stg, ["year", "in_wave"] + list(CLASSES)
           + ["migrated_this_wave", "migrated_total"])
    sc = scenarios()
    scen, tor_all, changed = [], [], []
    for n in SIZES:
        per = {}
        for key, label, basis, p in sc:
            res = classify_devices(fleets[n], p)
            per[key] = [r.cls for r in res]
            scen.append({"devices": n, "scenario": key, "label": label, "basis": basis,
                         "sig_flash_kb": p.sig_flash_kb, "sig_ram_kb": p.sig_ram_kb, "kem_flash_kb": p.kem_flash_kb,
                         "kem_ram_kb": p.kem_ram_kb, "violations": len(violations(fleets[n], res, p)), **counts(res)})
            for r in tornado(fleets[n], p):
                tor_all.append({"devices": n, "scenario": key, **r})
        hr = {k: v.count(HARDWARE_REPLACEMENT) for k, v in per.items()}
        lo_k = min(hr, key=lambda k: (hr[k], k))
        hi_k = max(hr, key=lambda k: (hr[k], k))
        diff = sum(1 for a, b in zip(per[lo_k], per[hi_k]) if a != b)
        changed.append({"devices": n, "lowest": lo_k, "highest": hi_k, "hr_low": hr[lo_k], "hr_high": hr[hi_k],
                        "changed": diff, "share_changed": diff / n})
    _write("scenarios.csv", scen, ["devices", "scenario", "label", "basis", "sig_flash_kb", "sig_ram_kb",
                                   "kem_flash_kb", "kem_ram_kb", "violations"] + list(CLASSES))
    _write("scenario_range.csv", changed, ["devices", "lowest", "highest", "hr_low", "hr_high", "changed",
                                           "share_changed"])
    _write("tornado.csv", tor_all, ["devices", "scenario", "input", "kind", "low", "high", "changed_low",
                                    "share_low", "changed_high", "share_high", "swing"])
    seedvar = []
    for k in range(SEED_DRAWS):
        devs = make_fleet(1000, seed=BASE_SEED + 1000 + k)
        for key, _, _, p in sc:
            seedvar.append({"seed": BASE_SEED + 1000 + k, "scenario": key,
                            "hr": counts(classify_devices(devs, p))[HARDWARE_REPLACEMENT]})
    _write("seed_variation.csv", seedvar, ["seed", "scenario", "hr"])
    hw_rows = [{"class": h, "core": v[0], "ram_kb": " ".join(map(str, v[1])),
                "flash_kb": " ".join(map(str, v[2])), "share": dict(MIX)[h]} for h, v in HW.items()]
    _write("hardware_classes.csv", hw_rows, ["class", "core", "ram_kb", "flash_kb", "share"])
    r1000 = [c for c in changed if c["devices"] == 1000][0]
    label = {k: lab for k, lab, _, _ in sc}

    L = ["# Planner study on synthetic fleets", "",
         "Author: Huda Mueen. Generated by `cd planner && python fleetstudy.py`; do not edit by hand. "
         "Label: **estimated**. Every fleet is **SYNTHETIC**: invented devices from five invented hardware "
         "classes (`planner/results/hardware_classes.csv`), seed %d plus the fleet size. Not a real fleet, "
         "not measured. The planner supports planning; it is not a security guarantee." % BASE_SEED, "",
         "**Headline.** How many devices need new hardware depends on which implementation the memory thresholds "
         "assume. On the 1000 device fleet it ranges from %d (%s) to %d (%s); %d devices (%.1f percent) change "
         "class between those two scenarios. The answer is the range, not one figure." % (
             r1000["hr_low"], label[r1000["lowest"]], r1000["hr_high"], label[r1000["highest"]], r1000["changed"],
             100 * r1000["share_changed"]), "",
         "## 1. Threshold scenarios", "",
         "Each scenario takes the four memory thresholds from one implementation, derived as in "
         "`docs/PLANNER_RULES.md`. Three come from published pqm4 rows of `data/evidence.csv` (stack optimised "
         "assembly, speed optimised assembly as the middle case, reference C); one from this repository's own "
         "portable C build as run in the emulator. The violation count is an internal consistency check against "
         "the thresholds in force, not evidence that code fits a real device.", "",
         "| devices | scenario | basis | sig flash kB | sig RAM kB | KEM flash kB | KEM RAM kB | violations | "
         + " | ".join(CLASSES) + " |", "|---|---|---|---|---|---|---|---|" + "---|" * len(CLASSES)]
    for s_ in scen:
        L.append("| %d | %s | %s | %s | %s | %s | %s | %d | %s |" % (
            s_["devices"], s_["label"], s_["basis"], s_["sig_flash_kb"], s_["sig_ram_kb"], s_["kem_flash_kb"],
            s_["kem_ram_kb"], s_["violations"], " | ".join(str(s_[c]) for c in CLASSES)))
    L += ["", "Range of hardware replacements, and devices that change class between the scenario with the fewest "
          "and the scenario with the most replacements:", "",
          "| devices | fewest | most | hardware replacements | devices that change class |", "|---|---|---|---|---|"]
    for c in changed:
        L.append("| %d | %s | %s | %d to %d | %d (%.1f%%) |" % (c["devices"], c["lowest"], c["highest"], c["hr_low"],
                                                             c["hr_high"], c["changed"], 100 * c["share_changed"]))
    L += ["", "Seed to seed variation: %d fleets of 1000 devices (seeds %d to %d; the first is the fleet above), "
          "hardware replacements per scenario (`planner/results/seed_variation.csv`):" % (SEED_DRAWS, BASE_SEED + 1000,
                                                                BASE_SEED + 1000 + SEED_DRAWS - 1), "",
          "| scenario | lowest | highest |", "|---|---|---|"]
    for key, _, _, _ in sc:
        v = [r["hr"] for r in seedvar if r["scenario"] == key]
        L.append("| %s | %d | %d |" % (key, min(v), max(v)))
    rng_ = {key: (min(r["hr"] for r in seedvar if r["scenario"] == key),
                  max(r["hr"] for r in seedvar if r["scenario"] == key)) for key, _, _, _ in sc}
    keys = [k for k, _, _, _ in sc]
    over = [f"{a} and {b}" for a, b in zip(keys, keys[1:]) if rng_[a][1] >= rng_[b][0]]
    ext = rng_[keys[0]][1] < rng_[keys[-1]][0]
    L += ["", ("Neighbouring scenarios overlap between draws (" + "; ".join(over) + "), so their order is not "
               "settled by one fleet; " if over else "No neighbouring scenarios overlap between draws; ")
          + ("the two extremes do not overlap." if ext else "even the two extremes overlap.")]
    L += ["", "## 2. Tornado sensitivity per scenario and fleet size", "",
          "Share of devices whose class changes when one input moves to its low or high value with the other inputs "
          "at the scenario's values. Rule parameters move by minus and plus 50 percent (horizon years by 2 years); "
          "device fields are scaled or shifted across the whole fleet. Full table: `planner/results/tornado.csv`. "
          "Shown: the three inputs with the largest swing.", "",
          "| devices | scenario | first | second | third |", "|---|---|---|---|---|"]
    for n in SIZES:
        for key, _, _, _ in sc:
            top = [r for r in tor_all if r["devices"] == n and r["scenario"] == key][:3]
            L.append("| %d | %s | %s |" % (n, key, " | ".join("%s %.1f%%" % (r["input"], 100 * r["swing"])
                                                             for r in top)))
    L += ["", "## 3. Scale and the memory limit property (stack optimised thresholds)", "",
          "| devices | seed | classify time (s) | violations | " + " | ".join(CLASSES) + " |",
          "|---|---|---|---|" + "---|" * len(CLASSES)]
    for s in scale:
        L.append("| %d | %d | %.3f | %d | %s |" % (s["devices"], s["seed"], s["seconds"], s["violations"],
                                                    " | ".join(str(s[c]) for c in CLASSES)))
    L += ["", "Times are host wall time of the classifier on this machine.", "",
          "## 4. Staged migration (1000 device fleet, stack optimised thresholds, waves 2026 to 2030)", "",
          "Each wave classifies the devices not yet migrated with the wave year as the planning year and "
          "remaining service life reduced by the years elapsed. FIRMWARE_UPDATE and HYBRID devices are "
          "migrated in that wave, HARDWARE_REPLACEMENT devices are replaced, and the rest carry over.", "",
          "| year | devices in wave | " + " | ".join(CLASSES) + " | migrated in wave | migrated total |",
          "|---|---|" + "---|" * len(CLASSES) + "---|---|"]
    for s in stg:
        L.append("| %d | %d | %s | %d | %d |" % (s["year"], s["in_wave"], " | ".join(str(s[c]) for c in CLASSES),
                                                s["migrated_this_wave"], s["migrated_total"]))
    L += ["", "## Limits", "",
          "1. The hardware classes, their shares and every distribution are invented; every count here depends on "
          "them. A real inventory would change every number.",
          "2. The tornado moves one input at a time; interactions are not explored.",
          "3. The thresholds use one parameter set per family (ML-DSA-44, ML-KEM-768); a fleet that must use "
          "ML-DSA-87 or ML-KEM-1024 needs more.",
          "4. The staged model assumes every action in a wave succeeds and that replaced hardware leaves "
          "the fleet; it does not model budgets, downtime or partial rollouts.",
          "5. Each fleet is one draw from invented distributions; the seed table in section 1 shows how far the "
          "counts move between draws.", "",
          "_This tool supports planning. It is not a security guarantee._", ""]
    with open(DOC, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(L))
    print("wrote planner/results/ and docs/PLANNER_STUDY.md in %.1f s" % (time.time() - t_all))


if __name__ == "__main__":
    main()
