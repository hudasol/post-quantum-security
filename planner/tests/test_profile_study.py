"""Tests of planner/profile_study.py and planner/policy_timeline.py, and
property tests of the planner on fleets built from the published board
profiles in data/reference_profiles.csv.

Author: Huda Mueen

Properties: (1) no FIRMWARE_UPDATE or HYBRID device has free memory below the
need in force or above its published total; (2) raising a device's free memory
never gives a worse class. Both are checked under randomly drawn thresholds.
"""

import os
import random
import tempfile
import unittest
from fractions import Fraction

from tests import helpers  # noqa: F401  (puts the planner root on sys.path)

import fleetstudy as fs  # noqa: E402
import policy_timeline as pt  # noqa: E402
import profile_study as ps  # noqa: E402
from fleetplan.classify import (FIRMWARE_UPDATE, HARDWARE_REPLACEMENT, HYBRID,  # noqa: E402
                                NO_ACTION, UNKNOWN)

N = 400


def profile_devices(seed, free_range=(0.0, 1.0)):
    base = fs.make_fleet(N, seed=fs.BASE_SEED + 200000 + seed)
    return ps.profile_fleet(base, ps.load_profiles(), random.Random(seed), free_range)


class TestProfiles(unittest.TestCase):
    def test_load_profiles(self):
        profiles = ps.load_profiles()
        self.assertGreaterEqual(len(profiles), 8)
        for p in profiles:
            self.assertGreater(p["flash_kb"], 0)
            self.assertGreater(p["ram_kb"], 0)
            self.assertEqual(p["label"], "published")
            self.assertTrue(p["source_url"])
            self.assertEqual(p["retrieval_date"], "2026-10-20")
            if p["free_flash_kb"] is not None:
                self.assertLessEqual(p["free_flash_kb"], p["flash_kb"])
            if p["free_ram_kb"] is not None:
                self.assertLessEqual(p["free_ram_kb"], p["ram_kb"])

    def test_load_profiles_rejects_missing_total(self):
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as fh:
            fh.write("board,core,flash_bytes,ram_bytes,free_flash_bytes_derived,free_ram_bytes_derived\n"
                     "X,M4,,1000,,\n")
        try:
            with self.assertRaises(ValueError):
                ps.load_profiles(fh.name)
        finally:
            os.unlink(fh.name)

    def test_kb_text(self):
        self.assertEqual(ps.kb_text(Fraction(2097152, 1000)), "2097.152")
        self.assertEqual(ps.kb_text(Fraction(14)), "14")
        with self.assertRaises(ValueError):
            ps.kb_text(Fraction(1, 3))

    def test_profile_fleet_keeps_other_fields(self):
        base = fs.make_fleet(50, seed=7)
        out = ps.profile_fleet(base, ps.load_profiles(), random.Random(1), (0.05, 0.5))
        for a, b in zip(base, out):
            for k in ("device_id", "bootrom_verifier_updatable", "link_bandwidth_bps",
                      "service_life_remaining_years", "data_lifetime_years", "updatable_bootloader_stage"):
                self.assertEqual(a[k], b[k])
            if a["free_flash_kb"] == "":
                self.assertEqual(b["free_flash_kb"], "")
            else:
                self.assertLessEqual(Fraction(b["free_flash_kb"]), Fraction(b["flash_kb"]))
            self.assertTrue(b["notes"].startswith("SYNTHETIC"))

    def test_profile_fleet_unknown_free(self):
        out = ps.profile_fleet(fs.make_fleet(30, seed=3), ps.load_profiles(), random.Random(2), None)
        self.assertTrue(all(d["free_flash_kb"] == "" and d["free_ram_kb"] == "" for d in out))

    def test_profile_fleet_is_deterministic(self):
        base = fs.make_fleet(40, seed=5)
        a = ps.profile_fleet(base, ps.load_profiles(), random.Random(9), (0.1, 0.2))
        b = ps.profile_fleet(base, ps.load_profiles(), random.Random(9), (0.1, 0.2))
        self.assertEqual(a, b)


class TestThresholds(unittest.TestCase):
    def test_ranges_cover_published_scenarios(self):
        r = ps.threshold_ranges()
        self.assertEqual(r["sig_flash_kb"][:2], (8212 + 4840, 24844 + 4840))
        self.assertEqual(r["kem_ram_kb"][:2], (2844 + 6004, 14480 + 6004))
        for key, _, _, p in fs.scenarios():
            if key == "portable_c":
                continue
            for name, (lo, hi, _) in r.items():
                v = getattr(p, name)
                self.assertGreaterEqual(v, Fraction(lo // 1000))
                self.assertLessEqual(v, Fraction(-(-hi // 1000)))

    def test_draw_params_in_range(self):
        r = ps.threshold_ranges()
        rng = random.Random(4)
        for _ in range(50):
            p = ps.draw_params(rng, r)
            for name, (lo, hi, _) in r.items():
                self.assertGreaterEqual(getattr(p, name) * 1000, lo)
                self.assertLess(getattr(p, name) * 1000, hi + 1000)


class TestStatistics(unittest.TestCase):
    def test_percentile_and_median(self):
        self.assertEqual(ps.median([1, 2, 3]), 2)
        self.assertEqual(ps.percentile([0, 10], 0.25), 2.5)

    def test_bootstrap_contains_median(self):
        xs = [0.1, 0.2, 0.2, 0.3, 0.25, 0.22, 0.18]
        lo, hi = ps.bootstrap_median_ci(xs, reps=300)
        self.assertLessEqual(lo, ps.median(xs))
        self.assertGreaterEqual(hi, ps.median(xs))

    def test_wilson(self):
        lo, hi = ps.wilson(0, 10)
        self.assertEqual(lo, 0.0)
        self.assertAlmostEqual(hi, 0.2775, places=3)
        lo, hi = ps.wilson(50, 100)
        self.assertAlmostEqual(lo + hi, 1.0, places=9)


class TestMosca(unittest.TestCase):
    def test_exposed_boundary(self):
        self.assertFalse(ps.exposed(5, 4, 2035))   # 9 is not greater than 9
        self.assertTrue(ps.exposed(5.1, 4, 2035))

    def test_flip_lifetime(self):
        self.assertEqual(ps.flip_lifetime(0, 2035), 9)
        self.assertEqual(ps.flip_lifetime(4, 2030), 0)

    def test_probability_monotone_in_lifetime(self):
        hz = [2030, 2031, 2035]
        ps_ = [ps.mosca_probability(x, hz, random.Random(1), draws=2000) for x in (0, 5, 10, 20)]
        self.assertEqual(ps_, sorted(ps_))
        self.assertEqual(ps_[-1], 1.0)
        self.assertEqual(ps.mosca_probability(0, [2035], random.Random(1), draws=500, migration=(0, 1)), 0.0)

    def test_sobol_runs(self):
        rows, mean, n = ps.sobol(2030, 2036, n=64)
        self.assertEqual([r["input"] for r in rows], ["data_lifetime_years", "migration_years", "horizon_year"])
        self.assertTrue(0 < mean < 1)
        self.assertEqual(n, 64 * 5)


class TestSection(unittest.TestCase):
    def test_replace_section_appends_then_replaces(self):
        doc = "# Title\n\nbody\n"
        once = ps.replace_section(doc, "## 5. A\n")
        self.assertIn(ps.START, once)
        twice = ps.replace_section(once, "## 5. B\n")
        self.assertEqual(twice.count(ps.START), 1)
        self.assertIn("## 5. B", twice)
        self.assertNotIn("## 5. A", twice)
        self.assertTrue(twice.startswith("# Title"))

    def test_refresh_doc_without_section_file(self):
        self.assertFalse(ps.refresh_doc(doc="unused", section="/nonexistent/section.md"))


class TestPolicyTimeline(unittest.TestCase):
    def test_load_and_horizons(self):
        rows = pt.load()
        self.assertGreaterEqual(len(rows), 20)
        yrs = pt.completion_years(rows)
        self.assertTrue(all(2030 <= y <= 2035 for y in yrs))
        self.assertEqual(len(yrs), len(pt.horizon_rows(rows)))
        self.assertGreater(len(pt.completion_years(rows, include_unverified=True)), len(yrs))
        for r in rows:
            self.assertIn(r["status"], pt.STATUSES)
            self.assertTrue(r["url_or_file"])
            self.assertTrue(r["location"])

    def test_jurisdictions_present(self):
        names = " ".join(r["jurisdiction"] for r in pt.load())
        for j in ("United States", "European Union", "United Kingdom", "Germany", "France", "Canada",
                  "Singapore", "Australia", "United Arab Emirates"):
            self.assertIn(j, names)

    def test_load_rejects_bad_status(self):
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as fh:
            fh.write(",".join(pt.FIELDS) + "\n" + ",".join(
                ["X1", "A", "B", "2025", "maybe", "", "none", "m", "p", "u", "2026-10-20", "l", "e",
                 "published"]) + "\n")
        try:
            with self.assertRaises(ValueError):
                pt.load(fh.name)
        finally:
            os.unlink(fh.name)

    def test_render_mentions_every_row(self):
        rows = pt.load()
        text = pt.render(rows)
        for r in rows:
            self.assertIn("| " + r["row_id"] + " |", text)
        self.assertIn("unverified", text)


class TestPropertiesOnRealProfiles(unittest.TestCase):
    def test_no_recommendation_breaks_a_memory_limit(self):
        ranges = ps.threshold_ranges()
        rng = random.Random(11)
        for seed in (1, 2, 3):
            devs = profile_devices(seed)
            for _ in range(3):
                p = ps.draw_params(rng, ranges)
                res = fs.classify_devices(devs, p)
                self.assertEqual(ps.limit_violations(devs, res, p), [])
        for key, _, _, p in fs.scenarios():
            devs = profile_devices(4, (0.0, 0.3))
            self.assertEqual(ps.limit_violations(devs, fs.classify_devices(devs, p), p), [], key)

    def test_limit_violations_detects_free_above_total(self):
        devs = profile_devices(5, (0.1, 0.2))[:5]
        bad = dict(devs[0])
        bad["free_ram_kb"] = str(int(Fraction(bad["ram_kb"])) + 1)
        p = fs.scenarios()[0][3]
        res = fs.classify_devices([bad], p)
        self.assertEqual(ps.limit_violations([bad], res, p), [bad["device_id"]])

    def test_more_free_memory_never_worse(self):
        ranges = ps.threshold_ranges()
        rng = random.Random(12)
        for seed in (6, 7):
            devs = [d for d in profile_devices(seed, (0.0, 0.1)) if d["free_flash_kb"] != ""]
            for _ in range(3):
                p = ps.draw_params(rng, ranges)
                before = fs.classify_devices(devs, p)
                more = []
                for d in devs:
                    e = dict(d)
                    for free, total in (("free_flash_kb", "flash_kb"), ("free_ram_kb", "ram_kb")):
                        t = Fraction(d[total])
                        f = Fraction(d[free])
                        e[free] = str(int(f + (t - f) * Fraction(rng.randint(0, 10), 10)))
                    more.append(e)
                after = fs.classify_devices(more, p)
                for a, b in zip(before, after):
                    self.assertFalse(ps.worse(a.cls, b.cls), (a.device_id, a.cls, b.cls))
                    if a.cls in (NO_ACTION,):
                        self.assertEqual(b.cls, NO_ACTION)

    def test_worse_ordering(self):
        self.assertTrue(ps.worse(FIRMWARE_UPDATE, HARDWARE_REPLACEMENT))
        self.assertTrue(ps.worse(HYBRID, HARDWARE_REPLACEMENT))
        self.assertFalse(ps.worse(HARDWARE_REPLACEMENT, HYBRID))
        self.assertFalse(ps.worse(UNKNOWN, HARDWARE_REPLACEMENT))


if __name__ == "__main__":
    unittest.main()
