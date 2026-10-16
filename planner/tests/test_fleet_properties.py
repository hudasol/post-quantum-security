"""Property tests of the planner on seeded SYNTHETIC fleets, and tests of the
fleet study functions.

Author: Huda Mueen

Each property is checked on several thousand invented devices drawn with
fixed seeds, under the default parameters and under randomly varied ones.
"""

import random
import unittest
from fractions import Fraction

from tests import helpers  # noqa: F401  (puts the planner root on sys.path)

import fleetstudy as fs  # noqa: E402
from fleetplan.classify import (FIRMWARE_UPDATE, HARDWARE_REPLACEMENT, HYBRID,  # noqa: E402
                                NO_ACTION, UNKNOWN)
from fleetplan.rules import Parameters  # noqa: E402

SEEDS = (1, 2, 3)
N = 700


def fleet(seed):
    return fs.make_fleet(N, seed=fs.BASE_SEED + 100000 + seed)


def random_params(rng):
    return Parameters(
        sig_horizon_year=rng.randint(2026, 2034),
        conf_horizon_year=rng.randint(2026, 2040),
        sig_flash_kb=Fraction(rng.randint(5, 80)), sig_ram_kb=Fraction(rng.randint(1, 20)),
        kem_flash_kb=Fraction(rng.randint(5, 40)), kem_ram_kb=Fraction(rng.randint(2, 30)),
        hs_budget_s=Fraction(rng.randint(10, 600)))


def param_sets():
    rng = random.Random(fs.BASE_SEED)
    return [Parameters()] + [random_params(rng) for _ in range(4)]


def classes(devices, p):
    return [r.cls for r in fs.classify_devices(devices, p)]


def with_fields(devices, **change):
    out = []
    for d in devices:
        e = dict(d)
        for k, f in change.items():
            e[k] = f(e[k])
        out.append(e)
    return out


class TestMemoryLimit(unittest.TestCase):
    def test_no_update_that_does_not_fit(self):
        for s in SEEDS:
            devs = fleet(s)
            for p in param_sets():
                res = fs.classify_devices(devs, p)
                self.assertEqual(fs.violations(devs, res, p), [], (s, p))

    def test_study_fleets(self):
        for n in fs.SIZES:
            devs = fs.make_fleet(n)
            self.assertEqual(fs.violations(devs, fs.classify_devices(devs)), [], n)


class TestMonotonicity(unittest.TestCase):
    def test_more_memory_never_worse(self):
        # Raise known free memory to the device total (the loader rejects free
        # memory above the total, so that is the largest valid value).
        for s in SEEDS:
            devs = fleet(s)
            richer = []
            for d in devs:
                e = dict(d)
                if e["free_ram_kb"] != "":
                    e["free_ram_kb"] = e["ram_kb"]
                if e["free_flash_kb"] != "":
                    e["free_flash_kb"] = e["flash_kb"]
                richer.append(e)
            for p in param_sets():
                for a, b in zip(classes(devs, p), classes(richer, p)):
                    if a in (FIRMWARE_UPDATE, HYBRID):
                        self.assertEqual(b, a)
                    if a != UNKNOWN:
                        self.assertNotEqual(b, UNKNOWN)
                    if b == HARDWARE_REPLACEMENT:
                        self.assertEqual(a, HARDWARE_REPLACEMENT)

    def test_updatable_stage_never_worse(self):
        for s in SEEDS:
            devs = fleet(s)
            no = with_fields(devs, updatable_bootloader_stage=lambda v: "no")
            yes = with_fields(devs, updatable_bootloader_stage=lambda v: "yes")
            for p in param_sets():
                for a, b in zip(classes(no, p), classes(yes, p)):
                    if a != HARDWARE_REPLACEMENT:
                        self.assertEqual(b, a)

    def test_shorter_life_never_adds_exposure(self):
        shorter = lambda v: str(max(0, int(v) - 3))  # noqa: E731
        for s in SEEDS:
            devs = fleet(s)
            short = with_fields(devs, service_life_remaining_years=shorter,
                                data_lifetime_years=shorter)
            for p in param_sets():
                for a, b in zip(classes(devs, p), classes(short, p)):
                    if a == NO_ACTION:
                        self.assertEqual(b, NO_ACTION)


class TestStudyFunctions(unittest.TestCase):
    def test_fleet_is_seeded_and_synthetic(self):
        a, b = fs.make_fleet(50), fs.make_fleet(50)
        self.assertEqual(a, b)
        self.assertNotEqual(a, fs.make_fleet(50, seed=1))
        self.assertTrue(all(d["notes"].startswith("SYNTHETIC H") for d in a))
        self.assertTrue(fs.to_csv(a).startswith("# SYNTHETIC"))

    def test_five_hardware_classes_appear(self):
        devs = fs.make_fleet(1000)
        self.assertEqual({d["notes"].split()[1] for d in devs}, set(fs.HW))

    def test_counts_and_need(self):
        devs = fs.make_fleet(100)
        res = fs.classify_devices(devs)
        self.assertEqual(sum(fs.counts(res).values()), 100)
        p = Parameters()
        for r in res:
            nd = fs.need(p, r)
            if r.cls in (FIRMWARE_UPDATE, HYBRID):
                self.assertIn(nd, ((p.both_flash_kb, p.both_ram_kb),
                                   (p.sig_flash_kb, p.sig_ram_kb),
                                   (p.kem_flash_kb, p.kem_ram_kb)))

    def test_violation_detected(self):
        devs = fs.make_fleet(100)
        res = fs.classify_devices(devs)
        idx = [i for i, r in enumerate(res) if r.cls == FIRMWARE_UPDATE][0]
        broken = [dict(d) for d in devs]
        broken[idx]["free_ram_kb"] = "0"
        self.assertEqual(fs.violations(broken, res), [devs[idx]["device_id"]])

    def test_tornado_rows(self):
        rows = fs.tornado(fs.make_fleet(100))
        self.assertEqual(len(rows), len(fs.TORNADO))
        self.assertEqual(rows, sorted(rows, key=lambda r: -r["swing"]))
        for r in rows:
            self.assertTrue(0 <= r["share_low"] <= 1 and 0 <= r["share_high"] <= 1)

    def test_staged_bookkeeping(self):
        out = fs.staged(fs.make_fleet(300))
        self.assertEqual(out[0]["in_wave"], 300)
        for prev, cur in zip(out, out[1:]):
            self.assertEqual(cur["in_wave"], prev[NO_ACTION] + prev[UNKNOWN])
            self.assertEqual(cur["migrated_total"],
                             prev["migrated_total"] + cur["migrated_this_wave"])


if __name__ == "__main__":
    unittest.main()
