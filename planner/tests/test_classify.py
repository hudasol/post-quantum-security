"""One test per rule branch, boundaries, missing fields and malformed values.

Author: Huda Mueen
"""

import random
import unittest
from fractions import Fraction

from .helpers import CONF, SIG, BASE, Parameters, classify_all, csv_text, one, parse_text
from fleetplan import classify as C
from fleetplan.loader import REQUIRED_COLUMNS


def has_rule(result, number):
    return any(r.startswith(f"Rule {number}") for r in result.reasons)


class Rule1Missing(unittest.TestCase):
    def test_each_required_field_blank_gives_unknown(self):
        for name in REQUIRED_COLUMNS[1:]:
            for raw in ("", "unknown"):
                with self.subTest(field=name, raw=raw):
                    r = one(**{name: raw})
                    self.assertEqual(r.cls, C.UNKNOWN)
                    self.assertEqual(r.missing_fields, (name,))
                    self.assertTrue(r.reasons[0].startswith("Rule 1"))
                    self.assertIn(name, r.reasons[0])

    def test_unknown_even_when_otherwise_not_exposed(self):
        r = one(bootrom_verifier_updatable="")
        self.assertEqual(r.cls, C.UNKNOWN)

    def test_several_missing_fields_all_listed(self):
        r = one(ram_kb="", flash_kb="abc", data_lifetime_years="-3")
        self.assertEqual(r.cls, C.UNKNOWN)
        self.assertEqual(set(r.missing_fields), {"ram_kb", "flash_kb", "data_lifetime_years"})

    def test_missing_bandwidth_gives_no_estimate(self):
        r = one(link_bandwidth_bps="")
        self.assertEqual(r.cls, C.UNKNOWN)
        self.assertIsNone(r.handshake_s)


class MalformedInput(unittest.TestCase):
    def test_non_numeric(self):
        for name in ("ram_kb", "flash_kb", "link_bandwidth_bps",
                     "service_life_remaining_years", "data_lifetime_years"):
            with self.subTest(field=name):
                r = one(**{name: "twelve"})
                self.assertEqual(r.cls, C.UNKNOWN)
                self.assertIn(name, r.missing_fields)
                self.assertIn("not a number", r.reasons[0])

    def test_negative(self):
        for name in ("ram_kb", "flash_kb", "link_bandwidth_bps",
                     "service_life_remaining_years", "data_lifetime_years"):
            with self.subTest(field=name):
                r = one(**{name: "-1"})
                self.assertEqual(r.cls, C.UNKNOWN)
                self.assertIn("negative", r.reasons[0])

    def test_zero_bandwidth(self):
        r = one(link_bandwidth_bps="0")
        self.assertEqual(r.cls, C.UNKNOWN)
        self.assertEqual(r.missing_fields, ("link_bandwidth_bps",))
        self.assertIsNone(r.handshake_s)

    def test_bad_yes_no(self):
        r = one(bootrom_verifier_updatable="maybe")
        self.assertEqual(r.cls, C.UNKNOWN)

    def test_invalid_optional_free_is_flagged_and_not_guessed(self):
        r = one(free_flash_kb="lots", **SIG)
        self.assertEqual(r.cls, C.UNKNOWN)
        self.assertIn("free_flash_kb", r.missing_fields)
        self.assertIn("INVALID_OPTIONAL:free_flash_kb", r.flags)

    def test_free_above_total_is_not_trusted(self):
        r = one(flash_kb="100", free_flash_kb="500", **SIG)
        self.assertEqual(r.cls, C.UNKNOWN)
        self.assertIn("INVALID_OPTIONAL:free_flash_kb", r.flags)

    def test_invalid_optional_with_small_total_is_insufficient(self):
        r = one(flash_kb="20", free_flash_kb="lots", **SIG)
        self.assertEqual(r.cls, C.HARDWARE_REPLACEMENT)

    def test_invalid_bootloader_stage(self):
        r = one(bootrom_verifier_updatable="no", updatable_bootloader_stage="perhaps", **SIG)
        self.assertEqual(r.cls, C.UNKNOWN)
        self.assertEqual(r.missing_fields, ("updatable_bootloader_stage",))
        self.assertIn("INVALID_OPTIONAL:updatable_bootloader_stage", r.flags)


class Rule2Boundaries(unittest.TestCase):
    def test_service_life_equal_threshold_not_exposed(self):
        r = one(service_life_remaining_years="4")
        self.assertEqual(r.cls, C.NO_ACTION)

    def test_service_life_just_above_threshold_exposed(self):
        r = one(service_life_remaining_years="4.01")
        self.assertEqual(r.cls, C.FIRMWARE_UPDATE)

    def test_data_lifetime_equal_threshold_not_exposed(self):
        self.assertEqual(one(data_lifetime_years="9").cls, C.NO_ACTION)
        self.assertEqual(one(data_lifetime_years="9.0").cls, C.NO_ACTION)

    def test_data_lifetime_just_above_threshold_exposed(self):
        self.assertEqual(one(data_lifetime_years="9.5").cls, C.FIRMWARE_UPDATE)

    def test_zero_years_not_exposed(self):
        r = one(service_life_remaining_years="0", data_lifetime_years="0")
        self.assertEqual(r.cls, C.NO_ACTION)

    def test_horizon_overrides_move_thresholds(self):
        p = Parameters(today_year=2026, sig_horizon_year=2040)
        self.assertEqual(one(p, service_life_remaining_years="10").cls, C.NO_ACTION)
        self.assertEqual(one(p, service_life_remaining_years="15").cls, C.FIRMWARE_UPDATE)
        p = Parameters(today_year=2030)  # SIG_YEARS 0, CONF_YEARS 5
        self.assertEqual(one(p, service_life_remaining_years="0").cls, C.NO_ACTION)
        self.assertEqual(one(p, service_life_remaining_years="1").cls, C.FIRMWARE_UPDATE)
        self.assertEqual(one(p, service_life_remaining_years="0", data_lifetime_years="5").cls,
                         C.NO_ACTION)

    def test_reason_cites_rule_2(self):
        self.assertTrue(has_rule(one(**SIG), 2))


class Rule3NoAction(unittest.TestCase):
    def test_no_action_flagged_and_cited(self):
        r = one()
        self.assertEqual(r.cls, C.NO_ACTION)
        self.assertIn(C.FLAG_FIFTH_CLASS, r.flags)
        self.assertTrue(r.reasons[0].startswith("Rule 3"))

    def test_no_action_does_not_need_headroom_or_stage(self):
        r = one(free_flash_kb="", free_ram_kb="", updatable_bootloader_stage="",
                bootrom_verifier_updatable="no")
        self.assertEqual(r.cls, C.NO_ACTION)


class Rule4And5Headroom(unittest.TestCase):
    """Needs are 30/7 (signature), 14/9 (KEM) and 44/9 (both). Equal is enough."""

    def test_signature_only_need_boundary(self):
        self.assertEqual(one(free_flash_kb="30", free_ram_kb="7", **SIG).cls, C.FIRMWARE_UPDATE)
        self.assertEqual(one(free_flash_kb="29", free_ram_kb="7", **SIG).cls, C.HARDWARE_REPLACEMENT)
        self.assertEqual(one(free_flash_kb="30", free_ram_kb="6", **SIG).cls, C.HARDWARE_REPLACEMENT)

    def test_kem_only_need_boundary(self):
        self.assertEqual(one(free_flash_kb="14", free_ram_kb="9", **CONF).cls, C.FIRMWARE_UPDATE)
        self.assertEqual(one(free_flash_kb="13", free_ram_kb="9", **CONF).cls, C.HARDWARE_REPLACEMENT)
        self.assertEqual(one(free_flash_kb="14", free_ram_kb="8", **CONF).cls, C.HARDWARE_REPLACEMENT)

    def test_both_need_boundary(self):
        both = {**SIG, **CONF}
        self.assertEqual(one(free_flash_kb="44", free_ram_kb="9", **both).cls, C.FIRMWARE_UPDATE)
        self.assertEqual(one(free_flash_kb="43", free_ram_kb="9", **both).cls, C.HARDWARE_REPLACEMENT)
        self.assertEqual(one(free_flash_kb="44", free_ram_kb="8", **both).cls, C.HARDWARE_REPLACEMENT)
        # 30 flash would be enough for the signature alone but not for both
        self.assertEqual(one(free_flash_kb="30", free_ram_kb="9", **both).cls, C.HARDWARE_REPLACEMENT)

    def test_reason_states_need(self):
        r = one(**{**SIG, **CONF})
        self.assertIn("44 kB flash and 9 kB RAM", " ".join(r.reasons))
        self.assertTrue(has_rule(r, 4))
        self.assertTrue(has_rule(r, 5))

    def test_unknown_free_with_small_total_is_insufficient(self):
        r = one(flash_kb="29", free_flash_kb="", free_ram_kb="", **SIG)
        self.assertEqual(r.cls, C.HARDWARE_REPLACEMENT)
        r = one(ram_kb="6", free_flash_kb="", free_ram_kb="", **SIG)
        self.assertEqual(r.cls, C.HARDWARE_REPLACEMENT)

    def test_total_equal_to_need_is_not_below(self):
        r = one(flash_kb="30", ram_kb="7", free_flash_kb="", free_ram_kb="", **SIG)
        self.assertEqual(r.cls, C.UNKNOWN)

    def test_unknown_free_with_large_total_is_unknown_and_named(self):
        r = one(free_flash_kb="", free_ram_kb="", **SIG)
        self.assertEqual(r.cls, C.UNKNOWN)
        self.assertEqual(r.missing_fields, ("free_flash_kb", "free_ram_kb"))
        self.assertTrue(r.reasons[0].startswith("Rule 5"))

    def test_only_one_free_field_missing_names_only_that_one(self):
        r = one(free_ram_kb="", **SIG)
        self.assertEqual(r.cls, C.UNKNOWN)
        self.assertEqual(r.missing_fields, ("free_ram_kb",))
        r = one(free_flash_kb="", **SIG)
        self.assertEqual(r.missing_fields, ("free_flash_kb",))

    def test_known_shortfall_beats_unknown_other_field(self):
        r = one(free_flash_kb="1", free_ram_kb="", **SIG)
        self.assertEqual(r.cls, C.HARDWARE_REPLACEMENT)

    def test_known_ok_but_other_unknown_stays_unknown(self):
        r = one(free_flash_kb="500", free_ram_kb="", **CONF)
        self.assertEqual(r.cls, C.UNKNOWN)

    def test_unknown_free_in_conf_only(self):
        r = one(free_flash_kb="", free_ram_kb="", **CONF)
        self.assertEqual(r.cls, C.UNKNOWN)
        self.assertEqual(r.missing_fields, ("free_flash_kb", "free_ram_kb"))
        self.assertEqual(one(flash_kb="13", free_flash_kb="", free_ram_kb="", **CONF).cls,
                         C.HARDWARE_REPLACEMENT)

    def test_parameter_override_changes_need(self):
        p = Parameters(sig_flash_kb=Fraction(100))
        self.assertEqual(one(p, free_flash_kb="99", **SIG).cls, C.HARDWARE_REPLACEMENT)
        self.assertEqual(one(p, free_flash_kb="100", **SIG).cls, C.FIRMWARE_UPDATE)


class Rule6Signature(unittest.TestCase):
    def test_bootrom_updatable_enough(self):
        r = one(bootrom_verifier_updatable="yes", **SIG)
        self.assertEqual(r.cls, C.FIRMWARE_UPDATE)
        self.assertTrue(r.reasons[0].startswith("Rule 6"))

    def test_bootrom_updatable_insufficient(self):
        r = one(bootrom_verifier_updatable="yes", free_flash_kb="5", **SIG)
        self.assertEqual(r.cls, C.HARDWARE_REPLACEMENT)
        self.assertTrue(r.reasons[0].startswith("Rule 6"))

    def test_bootrom_fixed_stage_yes_enough_is_hybrid(self):
        r = one(bootrom_verifier_updatable="no", updatable_bootloader_stage="yes", **SIG)
        self.assertEqual(r.cls, C.HYBRID)
        self.assertIn("both", r.reasons[0])

    def test_bootrom_fixed_stage_yes_insufficient(self):
        r = one(bootrom_verifier_updatable="no", updatable_bootloader_stage="yes",
                free_ram_kb="1", **SIG)
        self.assertEqual(r.cls, C.HARDWARE_REPLACEMENT)

    def test_bootrom_fixed_stage_no(self):
        r = one(bootrom_verifier_updatable="no", updatable_bootloader_stage="no", **SIG)
        self.assertEqual(r.cls, C.HARDWARE_REPLACEMENT)

    def test_bootrom_fixed_stage_no_needs_no_headroom_info(self):
        r = one(bootrom_verifier_updatable="no", updatable_bootloader_stage="no",
                free_flash_kb="", free_ram_kb="", **SIG)
        self.assertEqual(r.cls, C.HARDWARE_REPLACEMENT)

    def test_bootrom_fixed_stage_blank_is_unknown(self):
        r = one(bootrom_verifier_updatable="no", updatable_bootloader_stage="", **SIG)
        self.assertEqual(r.cls, C.UNKNOWN)
        self.assertEqual(r.missing_fields, ("updatable_bootloader_stage",))

    def test_stage_yes_unknown_headroom_is_unknown(self):
        r = one(bootrom_verifier_updatable="no", updatable_bootloader_stage="yes",
                free_flash_kb="", free_ram_kb="", **SIG)
        self.assertEqual(r.cls, C.UNKNOWN)
        self.assertEqual(r.missing_fields, ("free_flash_kb", "free_ram_kb"))

    def test_stage_is_ignored_when_bootrom_updatable(self):
        r = one(bootrom_verifier_updatable="yes", updatable_bootloader_stage="no", **SIG)
        self.assertEqual(r.cls, C.FIRMWARE_UPDATE)

    def test_signature_branch_when_both_exposed(self):
        r = one(**{**SIG, **CONF})
        self.assertEqual(r.cls, C.FIRMWARE_UPDATE)
        r = one(bootrom_verifier_updatable="no", updatable_bootloader_stage="yes", **SIG, **CONF)
        self.assertEqual(r.cls, C.HYBRID)

    def test_slow_link_does_not_change_signature_result(self):
        r = one(link_bandwidth_bps="1", **{**SIG, **CONF})
        self.assertEqual(r.cls, C.FIRMWARE_UPDATE)
        self.assertIn(C.FLAG_HS_OVER, r.flags)
        self.assertTrue(any("not applied" in x for x in r.reasons))

    def test_bootrom_value_not_needed_for_conf_only_but_required(self):
        self.assertEqual(one(bootrom_verifier_updatable="no", **CONF).cls, C.FIRMWARE_UPDATE)
        self.assertEqual(one(bootrom_verifier_updatable="", **CONF).cls, C.UNKNOWN)


class Rule7Confidentiality(unittest.TestCase):
    def test_enough_headroom_fast_link(self):
        r = one(**CONF)
        self.assertEqual(r.cls, C.FIRMWARE_UPDATE)
        self.assertTrue(r.reasons[0].startswith("Rule 7"))

    def test_insufficient_headroom(self):
        r = one(free_flash_kb="10", **CONF)
        self.assertEqual(r.cls, C.HARDWARE_REPLACEMENT)
        self.assertTrue(r.reasons[0].startswith("Rule 7"))

    def test_slow_link_becomes_hybrid_and_says_so(self):
        r = one(link_bandwidth_bps="100", **CONF)   # 485.44 s > 300 s
        self.assertEqual(r.cls, C.HYBRID)
        self.assertIn("gateway", r.reasons[0])
        self.assertIn(C.FLAG_GATEWAY, r.flags)

    def test_handshake_equal_to_budget_is_not_over(self):
        p = Parameters(hs_budget_s=Fraction(1))
        r = one(p, link_bandwidth_bps=str(6068 * 8), **CONF)   # exactly 1 s
        self.assertEqual(r.cls, C.FIRMWARE_UPDATE)
        self.assertEqual(r.handshake_s, 1.0)

    def test_handshake_just_over_budget(self):
        p = Parameters(hs_budget_s=Fraction(1))
        r = one(p, link_bandwidth_bps=str(6068 * 8 - 1), **CONF)
        self.assertEqual(r.cls, C.HYBRID)

    def test_default_budget_boundary(self):
        # 6068 * 8 / 300 = 161.8133 bit/s is the lowest rate that fits 300 s
        self.assertEqual(one(link_bandwidth_bps="162", **CONF).cls, C.FIRMWARE_UPDATE)
        self.assertEqual(one(link_bandwidth_bps="161", **CONF).cls, C.HYBRID)

    def test_slow_link_with_insufficient_headroom_stays_hardware(self):
        r = one(link_bandwidth_bps="100", free_flash_kb="1", **CONF)
        self.assertEqual(r.cls, C.HARDWARE_REPLACEMENT)
        self.assertIn(C.FLAG_HS_OVER, r.flags)

    def test_slow_link_with_unknown_headroom_stays_unknown(self):
        r = one(link_bandwidth_bps="100", free_flash_kb="", free_ram_kb="", **CONF)
        self.assertEqual(r.cls, C.UNKNOWN)

    def test_slow_link_alone_is_not_an_action(self):
        r = one(link_bandwidth_bps="1")
        self.assertEqual(r.cls, C.NO_ACTION)
        self.assertNotIn(C.FLAG_HS_OVER, r.flags)

    def test_budget_override_flag_effect(self):
        p = Parameters(hs_budget_s=Fraction(1000))
        self.assertEqual(one(p, link_bandwidth_bps="100", **CONF).cls, C.FIRMWARE_UPDATE)


class Rule8Estimate(unittest.TestCase):
    def test_estimate_and_label_on_every_class(self):
        cases = [one(), one(**SIG), one(**CONF), one(bootrom_verifier_updatable=""),
                 one(bootrom_verifier_updatable="no", updatable_bootloader_stage="yes", **SIG),
                 one(free_flash_kb="1", **SIG)]
        for r in cases:
            with self.subTest(cls=r.cls):
                self.assertAlmostEqual(r.handshake_s, 6068 * 8 / 57600)
                self.assertTrue(any("estimated from published sizes, not measured" in x
                                    for x in r.reasons))

    def test_every_reason_cites_a_rule(self):
        results = [one(), one(**SIG), one(**CONF), one(link_bandwidth_bps="100", **CONF),
                   one(ram_kb=""), one(free_flash_kb="", **SIG)]
        for r in results:
            for reason in r.reasons:
                self.assertRegex(reason, r"^Rule [1-8]")


class Determinism(unittest.TestCase):
    ROWS = [
        {"device_id": "A", **SIG}, {"device_id": "B", **CONF},
        {"device_id": "C", "ram_kb": ""}, {"device_id": "D"},
        {"device_id": "E", "bootrom_verifier_updatable": "no", "updatable_bootloader_stage": "no", **SIG},
        {"device_id": "F", "link_bandwidth_bps": "100", **CONF},
    ]

    def test_repeat_runs_identical(self):
        inv = parse_text(csv_text(*self.ROWS))
        self.assertEqual(classify_all(inv), classify_all(inv))
        self.assertEqual(classify_all(inv), classify_all(parse_text(csv_text(*self.ROWS))))

    def test_row_order_does_not_change_a_device_result(self):
        base = {r.device_id: r for r in classify_all(parse_text(csv_text(*self.ROWS)))}
        rows = list(self.ROWS)
        random.Random(7).shuffle(rows)
        shuffled = classify_all(parse_text(csv_text(*rows)))
        self.assertEqual([r.device_id for r in shuffled], [x["device_id"] for x in rows])
        for r in shuffled:
            self.assertEqual(r, base[r.device_id])

    def test_summary_counts(self):
        res = classify_all(parse_text(csv_text(*self.ROWS)))
        counts = C.summarise(res)
        self.assertEqual(sum(counts.values()), len(self.ROWS))
        self.assertEqual(counts[C.UNKNOWN], 1)
        self.assertEqual(counts[C.NO_ACTION], 1)


if __name__ == "__main__":
    unittest.main()
