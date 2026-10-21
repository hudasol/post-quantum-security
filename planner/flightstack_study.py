"""Planner fleet study with measured flight stack memory.

Author: Huda Mueen

Run from planner/:  python flightstack_study.py
Reads data/flightstack_memory.csv (flash and static RAM use of flight stack
builds, host measured, with capacities from the pinned board definitions),
data/reference_profiles.csv and the inputs of profile_study.py. Writes
planner/results/flightstack_*.csv and docs/FLIGHTSTACK_STUDY.md.

The study repeats the Monte Carlo of profile_study.py (section 5 of
docs/PLANNER_STUDY.md) twice with the same seeds: once with the assumed free
share for every board (round 4 method), and once with the measured free flash
and free static RAM for the board classes that were built, keeping the
assumption for the rest. Draws are paired by seed. Where a board class was
built by both flight stacks, the smaller free value is used (the planner must
hold for either stack). Free static RAM is an upper bound on the RAM that new
code may use, because the build cannot show heap use and task stacks created
at run time.

Labels. Measured free memory: host measured (against published capacities
from the pinned board definitions). Fleet, mix, lifetimes and boot fields:
synthetic. Every count and share: estimated (modelled, no validation data).
Seeds: those of profile_study.py (20261020 and its blocks), so that the
assumed column reproduces planner/results/profile_mc_summary.csv; the
bootstrap of the paired difference uses seed 20261021.
"""

import csv
import os
import random
import sys
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import fleetstudy as fs  # noqa: E402
import profile_study as ps  # noqa: E402
from fleetplan.classify import CLASSES, HARDWARE_REPLACEMENT  # noqa: E402

ROOT = os.path.dirname(HERE)
RES = os.path.join(HERE, "results")
MEASURED = os.path.join(ROOT, "data", "flightstack_memory.csv")
DOC = os.path.join(ROOT, "docs", "FLIGHTSTACK_STUDY.md")
REGIONS = os.path.join(ROOT, "data", "flightstack_memory_regions.csv")
PINS = os.path.join(ROOT, "flightstack", "pins.csv")
FLIGHTLOG_STATUS = os.path.join(ROOT, "flightstack", "flightlog_access.csv")
DIFF_SEED = 20261021
THRESHOLDS = ("stack_asm", "speed_asm", "portable_c", "reference_c", "uncertain")
F405 = "Matek F405-Wing (F4 class)"


def load_measured(path=MEASURED):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def measured_free(rows, pick=min):
    """{board: (free_flash_bytes, free_ram_bytes, stacks)} using the smaller value over stacks
    (pick=max gives the larger value, for the sensitivity case)."""
    out = {}
    for r in rows:
        if r["build_status"] != "built":
            continue
        ff, fr = int(r["flash_free_bytes"]), int(r["ram_free_static_bytes"])
        if r["board"] in out:
            a, b, s = out[r["board"]]
            out[r["board"]] = (pick(a, ff), pick(b, fr), s + [r["stack"]])
        else:
            out[r["board"]] = (ff, fr, [r["stack"]])
    return out


def apply_measured(profiles, free):
    """Copy of the profiles with measured free flash and RAM (planner kB of 1000 B) where available."""
    out = []
    names = {p["board"] for p in profiles}
    for b in free:
        if b not in names:
            raise ValueError("measured board %r is not in data/reference_profiles.csv" % b)
    for p in profiles:
        q = dict(p)
        if p["board"] in free:
            ff, fr, _ = free[p["board"]]
            q["free_flash_kb"] = Fraction(max(ff, 0), 1000)
            q["free_ram_kb"] = Fraction(max(fr, 0), 1000)
        out.append(q)
    return out


def monte_carlo(base, profiles, ranges, scen, draws=ps.DRAWS):
    """hr_share per draw and threshold configuration, seeds as in profile_study.main()."""
    out = {k: [] for k in THRESHOLDS}
    rng_t = random.Random(ps.SEED + 1)
    for i in range(draws):
        p_unc = ps.draw_params(rng_t, ranges)
        fleet = ps.profile_fleet(base, profiles, random.Random(ps.SEED + 1000 + i), ps.FREE_RANGES[ps.FREE_MAIN])
        for k, _, _, p in scen:
            out[k].append(ps.hr(fleet, p) / ps.N)
        out["uncertain"].append(ps.hr(fleet, p_unc) / ps.N)
    return out


def paired_diff_ci(a, b, seed=DIFF_SEED, reps=2000):
    """Bootstrap 95 percent interval of median(b) minus median(a), resampling paired draws."""
    rng = random.Random(seed)
    n = len(a)
    d = []
    for _ in range(reps):
        idx = [rng.randrange(n) for _ in range(n)]
        d.append(ps.median([b[i] for i in idx]) - ps.median([a[i] for i in idx]))
    return ps.percentile(d, 0.025), ps.percentile(d, 0.975)


def board_classes(fleet, results, board):
    tag = "SYNTHETIC profile " + board.replace(",", " ")
    c = {k: 0 for k in CLASSES}
    for d, r in zip(fleet, results):
        if d["notes"] == tag:
            c[r.cls] += 1
    return c


def _write(name, rows, fields):
    os.makedirs(RES, exist_ok=True)
    with open(os.path.join(RES, name), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: ("%.4f" % r[k] if isinstance(r[k], float) else
                            (str(r[k]) if isinstance(r[k], Fraction) else r[k])) for k in fields})


def run(draws=ps.DRAWS, measured_path=MEASURED):
    rows = load_measured(measured_path)
    free = measured_free(rows)
    profiles = ps.load_profiles()
    prof_m = apply_measured(profiles, free)
    free_max = measured_free(rows, pick=max)
    prof_x = apply_measured(profiles, free_max)
    ranges = ps.threshold_ranges()
    scen = fs.scenarios()
    base = fs.make_fleet(ps.N)
    mc_a = monte_carlo(base, profiles, ranges, scen, draws)
    mc_m = monte_carlo(base, prof_m, ranges, scen, draws)
    mc_x = monte_carlo(base, prof_x, ranges, scen, draws)
    summary = []
    for k in THRESHOLDS:
        a, m, x = mc_a[k], mc_m[k], mc_x[k]
        xl, xh = ps.bootstrap_median_ci(x)
        dxl, dxh = paired_diff_ci(a, x)
        al, ah = ps.bootstrap_median_ci(a)
        ml, mh = ps.bootstrap_median_ci(m)
        dl, dh = paired_diff_ci(a, m)
        summary.append({"thresholds": k, "draws": len(a), "assumed_median": ps.median(a),
                        "assumed_ci_low": al, "assumed_ci_high": ah, "measured_median": ps.median(m),
                        "measured_ci_low": ml, "measured_ci_high": mh,
                        "change_median": ps.median(m) - ps.median(a), "change_ci_low": dl, "change_ci_high": dh,
                        "larger_stack_median": ps.median(x), "larger_stack_ci_low": xl,
                        "larger_stack_ci_high": xh, "larger_stack_change": ps.median(x) - ps.median(a),
                        "larger_stack_change_ci_low": dxl, "larger_stack_change_ci_high": dxh,
                        "measured_boards": len(free), "seed": ps.SEED, "diff_seed": DIFF_SEED, "label": "estimated"})
    # one seeded fleet, per board classes (planner decision per board class)
    fa = ps.profile_fleet(base, profiles, random.Random(ps.SEED), ps.FREE_RANGES[ps.FREE_MAIN])
    fm = ps.profile_fleet(base, prof_m, random.Random(ps.SEED), ps.FREE_RANGES[ps.FREE_MAIN])
    per_board = []
    for k, _, _, p in scen:
        ra, rm = fs.classify_devices(fa, p), fs.classify_devices(fm, p)
        for b in profiles:
            for name, fl, res in (("assumed", fa, ra), ("measured", fm, rm)):
                c = board_classes(fl, res, b["board"])
                per_board.append({"scenario": k, "free_memory": name, "board": b["board"],
                                  "measured": "yes" if b["board"] in free else "no",
                                  "devices": sum(c.values()), **c, "seed": ps.SEED, "label": "estimated"})
    thr = []
    for k, _, _, p in scen:
        thr.append({"scenario": k, "sig_flash_kb": p.sig_flash_kb, "sig_ram_kb": p.sig_ram_kb,
                    "kem_flash_kb": p.kem_flash_kb, "kem_ram_kb": p.kem_ram_kb, "label": "derived from published"})
    used = []
    for b in profiles:
        if b["board"] in free:
            ff, fr, stacks = free[b["board"]]
            used.append({"board": b["board"], "stacks": " ".join(sorted(stacks)), "free_flash_bytes": ff,
                         "free_ram_static_bytes": fr, "free_flash_kb": Fraction(ff, 1000),
                         "free_ram_kb": Fraction(fr, 1000), "label": "host measured"})
    for u in used:
        ff, fr, _ = free_max[u["board"]]
        u["free_flash_bytes_larger_stack"] = ff
        u["free_ram_static_bytes_larger_stack"] = fr
    return {"summary": summary, "per_board": per_board, "thresholds": thr, "free": used, "rows": rows,
            "mc_assumed": mc_a, "mc_measured": mc_m, "mc_larger": mc_x}


def write_outputs(out):
    _write("flightstack_mc_summary.csv", out["summary"], list(out["summary"][0].keys()))
    _write("flightstack_per_board.csv", out["per_board"], list(out["per_board"][0].keys()))
    _write("flightstack_free_used.csv", out["free"], ["board", "stacks", "free_flash_bytes", "free_ram_static_bytes",
                                                       "free_flash_kb", "free_ram_kb", "free_flash_bytes_larger_stack",
                                                       "free_ram_static_bytes_larger_stack", "label"])
    draws = []
    for k in THRESHOLDS:
        for i, (a, m) in enumerate(zip(out["mc_assumed"][k], out["mc_measured"][k])):
            draws.append({"draw": i, "seed": ps.SEED + 1000 + i, "thresholds": k, "hr_share_assumed_free": a,
                          "hr_share_measured_free": m, "hr_share_larger_stack_free": out["mc_larger"][k][i],
                          "label": "estimated"})
    _write("flightstack_mc_draws.csv", draws, ["draw", "seed", "thresholds", "hr_share_assumed_free",
                                               "hr_share_measured_free", "hr_share_larger_stack_free", "label"])


def _read(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def kib(n):
    return "%.1f" % (int(n) / 1024)


def document(out):
    rows = out["rows"]
    built = [r for r in rows if r["build_status"] == "built"]
    failed = [r for r in rows if r["build_status"] != "built"]
    pins = {r["component"]: r for r in _read(PINS)}
    regions = _read(REGIONS)
    access = _read(FLIGHTLOG_STATUS)
    L = ["# Flight stack memory and the fleet planner", "",
         "Author: Huda Mueen.", "",
         "Generated by `cd planner && python flightstack_study.py` from `data/flightstack_memory.csv`, "
         "`data/flightstack_memory_regions.csv` and the planner inputs. Do not edit by hand. The memory files are "
         "made by `flightstack/fetch.sh`, `flightstack/build_all.sh` and `flightstack/extract_memory.py`; the planner "
         "rerun needs only the committed files.", "",
         "Labels: memory use **host measured** (linker output of builds on the host, not a board); capacities "
         "**published** in the pinned board definitions; fleet, mix, lifetimes and boot fields **synthetic**; every "
         "count and share **estimated**.", "",
         "## 1. Builds", ""]
    L.append("Pinned versions (`flightstack/pins.csv`):")
    L.append("")
    L += ["| component | version | commit | label |", "|---|---|---|---|"]
    for r in pins.values():
        L.append("| %s | %s | %s | %s |" % (r["component"], r["version"], r["commit"] or "", r["label"]))
    L += ["", "Every target uses the default configuration of its board, built one at a time with two jobs. "
          "ArduPilot targets build the copter vehicle. %d builds were attempted, %d succeeded, covering %d board "
          "classes of `data/reference_profiles.csv`." % (len(rows), len(built), len({r["board"] for r in built})), ""]
    L += ["## 2. Flash and static RAM", "",
          "Flash used counts every loaded section at a load address in flash, including the initial values of "
          ".data. ArduPilot places a crash log area in the flash the image leaves unused (stated in its "
          "`common.ld`); that area is counted as free and listed in the column `flash_crash_log_bytes`. On every "
          "ArduPilot board built here the free flash is almost all crash log area (`data/flightstack_memory.csv`), "
          "so code added in that flash removes the space for crash dumps: the feature is lost, not merely moved. Static RAM "
          "counts sections allocated at run addresses in RAM: data plus bss, and sections the linker reserves for "
          "stacks. A heap section marks the pool the allocator manages and is not counted. Free static RAM is capacity minus both. It is an upper bound on "
          "the RAM that new code can use: the build cannot show the heap that the flight stack fills at start up "
          "(task stacks, message buffers, the logger buffer), so the RAM really left is smaller by an amount that "
          "only a run on the board can show. RAM capacity follows each stack's own linker description: the "
          "regions counted are listed in `data/flightstack_memory_regions.csv` (column counted_in_capacity), and "
          "the stacks do not count the same regions on the same chip (PX4 does not count ITCM RAM).", "",
          "Units: the tables of this section give KiB (1024 B); section 3 gives the planner's kB (1000 B), with "
          "three decimals, for the same quantities.", "",
          "| stack | target | board class | flash used (KiB) | flash capacity (KiB) | flash free share | data plus "
          "bss (KiB) | reserved stack sections (KiB) | RAM capacity (KiB) | static RAM free share |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for r in built:
        L.append("| %s | %s | %s | %s | %s | %.3f | %s | %s | %s | %.3f |" % (
            r["stack"], r["target"], r["board"], kib(r["flash_used_bytes"]), kib(r["flash_capacity_bytes"]),
            float(r["flash_free_share"]), kib(r["ram_data_bss_bytes"]), kib(r["ram_reserved_stack_bytes"]),
            kib(r["ram_capacity_bytes"]), float(r["ram_free_share"])))
    L += ["", "Capacity sources, per row, are in the columns `flash_capacity_source` and `ram_capacity_source` of "
          "`data/flightstack_memory.csv` (file path in the pinned checkout and commit). The flash capacity is the "
          "application region after the bootloader, not the whole chip. PX4 RAM capacity sums the RAM regions of "
          "the board linker script except instruction RAM and backup RAM; ArduPilot RAM capacity sums the regions "
          "the ChibiOS port hands to its allocator, which on the STM32H7 include instruction RAM.", ""]
    prof = {p["board"]: p for p in ps.load_profiles()}
    over = [r for r in built if int(r["flash_capacity_bytes"]) > int(prof[r["board"]]["flash_bytes"])]
    if over:
        L += ["Where a board definition declares more application flash than the total flash of the board profile "
              "(`data/reference_profiles.csv`), the profile total is a lower bound and the board definition is the "
              "more specific source:", "",
              "| stack | target | application flash in the board definition (B) | profile total flash (B) |",
              "|---|---|---|---|"]
        for r in over:
            L.append("| %s | %s | %s | %s |" % (r["stack"], r["target"], r["flash_capacity_bytes"],
                                                prof[r["board"]]["flash_bytes"]))
        L.append("")
    if failed:
        L += ["Builds that failed:", "", "| stack | target | reason |", "|---|---|---|"]
        for r in failed:
            L.append("| %s | %s | %s |" % (r["stack"], r["target"], r["failure_reason"]))
        L.append("")
    h7 = [g for g in regions if g["kind"] == "ram" and int(g["used_bytes"]) > 0]
    if h7:
        L += ["Regions holding static allocations (`data/flightstack_memory_regions.csv`; on the STM32H7 the "
              "tightly coupled DTCM, the AXI SRAM and the D2 and D3 SRAM banks are separate regions):", "",
              "| stack | target | region | length (KiB) | static use (KiB) | sections |", "|---|---|---|---|---|---|"]
        for g in h7:
            L.append("| %s | %s | %s | %s | %s | %s |" % (g["stack"], g["target"], g["region"], kib(g["length_bytes"]),
                                                          kib(g["used_bytes"]), g["sections"]))
        L.append("")
    L += ["## 3. Fleet planner with measured free memory", "",
          "The Monte Carlo of `docs/PLANNER_STUDY.md` section 5.4 is repeated with the same seeds (profile fleet "
          "seeds %d to %d, threshold seed %d) and %d draws. Column `assumed`: free memory is the total times a "
          "uniform share in %s for every board (round 4). Column `measured`: the boards built here use their "
          "measured free flash and free static RAM; where both stacks were built, the smaller value is taken for "
          "each resource separately, so a board can get the free flash of one stack and the free RAM of the other "
          "(column stacks), a combination no single build has. RAM never binds in this study (see the reading "
          "below), so this choice affects only the flash side; the other "
          "boards keep the assumption. The change is measured minus assumed, with a bootstrap 95 percent interval "
          "over the paired draws (seed %d)." % (ps.SEED + 1000, ps.SEED + 1000 + ps.DRAWS - 1, ps.SEED + 1, ps.DRAWS,
                                                 ps.FREE_RANGES[ps.FREE_MAIN], DIFF_SEED), "",
          "Free memory given to the planner (`planner/results/flightstack_free_used.csv`):", "",
          "| board class | stacks | free flash (kB) | free static RAM (kB) |", "|---|---|---|---|"]
    for f in out["free"]:
        L.append("| %s | %s | %s | %s |" % (f["board"], f["stacks"], ps.kb_text(f["free_flash_kb"]),
                                              ps.kb_text(f["free_ram_kb"])))
    L += ["", "Hardware replacement share of the fleet (`planner/results/flightstack_mc_summary.csv`):", "",
          "| thresholds | assumed median | assumed median 95% CI | measured median | measured median 95% CI | "
          "change of median | change 95% CI |", "|---|---|---|---|---|---|---|"]
    for s in out["summary"]:
        L.append("| %s | %.3f | %.3f to %.3f | %.3f | %.3f to %.3f | %+.3f | %+.3f to %+.3f |" % (
            s["thresholds"], s["assumed_median"], s["assumed_ci_low"], s["assumed_ci_high"], s["measured_median"],
            s["measured_ci_low"], s["measured_ci_high"], s["change_median"], s["change_ci_low"], s["change_ci_high"]))
    L += ["", "Sensitivity: where both stacks were built, the larger free value instead of the smaller one (a fleet "
          "that runs the stack with more room on each board):", "",
          "| thresholds | median | median 95% CI | change of median against assumed | change 95% CI |",
          "|---|---|---|---|---|"]
    for s in out["summary"]:
        L.append("| %s | %.3f | %.3f to %.3f | %+.3f | %+.3f to %+.3f |" % (
            s["thresholds"], s["larger_stack_median"], s["larger_stack_ci_low"], s["larger_stack_ci_high"],
            s["larger_stack_change"], s["larger_stack_change_ci_low"], s["larger_stack_change_ci_high"]))
    st = {s["thresholds"]: s for s in out["summary"]}
    px4_free = [int(r["flash_free_bytes"]) for r in built if r["stack"] == "px4"]
    thr = out["thresholds"]
    need_flash = [(t["scenario"], (t["sig_flash_kb"] + t["kem_flash_kb"]) * 1000) for t in thr]
    max_ram_need = max((t["sig_ram_kb"] + t["kem_ram_kb"]) * 1000 for t in thr)
    min_free_ram = min(int(f["free_ram_static_bytes"]) for f in out["free"])
    L += ["", "Reading. With the stack optimised thresholds the median hardware replacement share moves from %.3f "
          "(assumed free share) to %.3f (measured, smaller value over stacks) and %.3f (measured, larger value)." % (
              st["stack_asm"]["assumed_median"], st["stack_asm"]["measured_median"],
              st["stack_asm"]["larger_stack_median"])]
    if px4_free:
        below = ["%s (%s kB)" % (k, ps.kb_text(Fraction(int(n), 1000))) for k, n in need_flash
                 if sum(1 for f in px4_free if f < n) > 0]
        L[-1] += (" The default PX4 builds leave between %s and %s kB of application flash free on the boards built "
                  "here. Signature plus KEM flash need per scenario that exceeds the free flash of at least one PX4 "
                  "build: %s." % (ps.kb_text(Fraction(min(px4_free), 1000)), ps.kb_text(Fraction(max(px4_free), 1000)),
                                  ", ".join(below) if below else "none"))
    L[-1] += (" The smallest measured free static RAM is %s kB against a largest signature plus KEM RAM need of %s kB "
              "(an upper bound on free RAM, see section 2)." % (ps.kb_text(Fraction(min_free_ram, 1000)),
                                                                 ps.kb_text(Fraction(int(max_ram_need), 1000))))
    L += ["", "### 3.1 The STM32F405 class", "",
          "Planner classes of the devices given the Matek F405-Wing profile in the seeded fleet (seed %d), "
          "with the assumed and the measured free memory (`planner/results/flightstack_per_board.csv`):" % ps.SEED, "",
          "| scenario | free memory | devices | " + " | ".join(CLASSES) + " |", "|---|---|---|" + "---|" * len(CLASSES)]
    for r in out["per_board"]:
        if r["board"] == F405:
            L.append("| %s | %s | %d | %s |" % (r["scenario"], r["free_memory"], r["devices"],
                                                " | ".join(str(r[c]) for c in CLASSES)))
    L += ["", "Memory thresholds of each scenario in planner kB (`planner/results/flightstack_thresholds.csv`):", "",
          "| scenario | signature flash | signature RAM | KEM flash | KEM RAM |", "|---|---|---|---|---|"]
    for t in out["thresholds"]:
        L.append("| %s | %s | %s | %s | %s |" % (t["scenario"], ps.kb_text(t["sig_flash_kb"]), ps.kb_text(t["sig_ram_kb"]),
                                                 ps.kb_text(t["kem_flash_kb"]), ps.kb_text(t["kem_ram_kb"])))
    L += ["", "## 4. Traffic from public flight logs", ""]
    if access:
        L += ["| source | checked | finding | decision |", "|---|---|---|---|"]
        for a in access:
            L.append("| %s | %s | %s | %s |" % (a["url"], a["retrieved_utc"], a["finding"], a["decision"]))
        L += ["", "The site rules disallow automated access to every path below the root page and no licence for "
              "reuse of uploaded logs was found, so no log was downloaded (record: `flightstack/flightlog_access.csv`). "
              "No command rates or outage patterns from real flights exist in this repository, and the mission study "
              "keeps its synthetic traffic (`mission/traffic.csv`); it was not rerun. A source of flight logs released "
              "under a stated licence would be needed to close this gap.", ""]
    L += ["## 5. Limits", "",
          "1. Static RAM is not run time RAM. The free static RAM is an upper bound; heap use at run time is not "
          "visible in a build and is the next measurement to make on a board or in software in the loop.",
          "2. Default configurations only. Vendors and users enable or remove features, which moves flash use.",
          "3. Copter is the only ArduPilot vehicle built; plane and rover images differ in size.",
          "4. Board classes that were not built keep the assumed free share of round 4.",
          "5. The compiler is the distribution package named in `flightstack/pins.csv`, which may differ from the "
          "version each project uses for its release binaries, so sizes can differ from the published firmware "
          "files; that difference was not measured.", "",
          "_This tool supports planning. It is not a security guarantee._", ""]
    with open(DOC, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(L))


def main():
    out = run()
    write_outputs(out)
    _write("flightstack_thresholds.csv", out["thresholds"], ["scenario", "sig_flash_kb", "sig_ram_kb", "kem_flash_kb",
                                                             "kem_ram_kb", "label"])
    # The assumed column must reproduce the round 4 profile study.
    r4 = {r["thresholds"]: r for r in _read(os.path.join(RES, "profile_mc_summary.csv")) if r["fleet"] == "profile"}
    for s in out["summary"]:
        if s["thresholds"] in r4:
            assert abs(float(r4[s["thresholds"]]["median"]) - s["assumed_median"]) < 1e-4, (s, r4[s["thresholds"]])
    document(out)
    print("flightstack study written")


if __name__ == "__main__":
    main()
