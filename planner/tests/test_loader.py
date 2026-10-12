"""Tests of the strict loader. Author: Huda Mueen"""

import os
import tempfile
import unittest

from .helpers import BASE, COLUMNS, csv_text
from fleetplan.loader import LoaderError, load_path, parse_text


def field(text, name, row=0):
    return parse_text(text).records[row].fields[name]


class StructureTests(unittest.TestCase):
    def test_comments_and_blank_lines_skipped(self):
        text = "# note\n\n" + csv_text({}) + "\n# trailing\n"
        inv = parse_text(text)
        self.assertEqual(len(inv.records), 1)
        self.assertEqual(len(inv.comments), 2)

    def test_missing_required_column(self):
        text = csv_text({}).replace("flash_kb,", "flashkb,", 1)
        with self.assertRaises(LoaderError) as cm:
            parse_text(text)
        self.assertIn("flash_kb", str(cm.exception))

    def test_optional_columns_may_be_absent(self):
        text = ("device_id,ram_kb,flash_kb,bootrom_verifier_updatable,link_bandwidth_bps,"
                "service_life_remaining_years,data_lifetime_years\nA,1,2,yes,3,4,5\n")
        rec = parse_text(text).records[0]
        self.assertEqual(rec.fields["free_flash_kb"].status, "missing")

    def test_duplicate_device_id(self):
        with self.assertRaises(LoaderError) as cm:
            parse_text(csv_text({"device_id": "A"}, {"device_id": "A"}))
        self.assertIn("duplicate", str(cm.exception))

    def test_blank_device_id(self):
        with self.assertRaises(LoaderError):
            parse_text(csv_text({"device_id": " "}))

    def test_wrong_field_count_names_line(self):
        text = csv_text({}) + "X,1,2\n"
        with self.assertRaises(LoaderError) as cm:
            parse_text(text)
        self.assertIn("line 3", str(cm.exception))

    def test_duplicate_header(self):
        with self.assertRaises(LoaderError):
            parse_text("device_id,device_id\nA,B\n")

    def test_empty_and_comment_only(self):
        for text in ("", "# only a comment\n", "\n\n"):
            with self.assertRaises(LoaderError):
                parse_text(text)

    def test_missing_file(self):
        with self.assertRaises(LoaderError):
            load_path("/nonexistent/inventory.csv")

    def test_not_utf8(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "bad.csv")
            with open(path, "wb") as h:
                h.write(b"\xff\xfe\x00bad")
            with self.assertRaises(LoaderError):
                load_path(path)


class SyntheticMarkerTests(unittest.TestCase):
    def test_marker_in_comment(self):
        self.assertTrue(parse_text(csv_text({}, comments=["# SYNTHETIC: test"])).synthetic)

    def test_marker_in_notes(self):
        self.assertTrue(parse_text(csv_text({"notes": "synthetic"})).synthetic)

    def test_no_marker(self):
        self.assertFalse(parse_text(csv_text({}, comments=["# real fleet"])).synthetic)

    def test_marker_in_core_is_ignored(self):
        self.assertFalse(parse_text(csv_text({"core": "SYNTHETIC"})).synthetic)


class ValueTests(unittest.TestCase):
    def test_numbers(self):
        self.assertEqual(field(csv_text({"ram_kb": "64"}), "ram_kb").value, 64)
        self.assertEqual(field(csv_text({"service_life_remaining_years": "4.5"}),
                               "service_life_remaining_years").status, "ok")

    def test_blank_and_unknown_are_missing(self):
        for raw in ("", " ", "unknown", "UNKNOWN"):
            self.assertEqual(field(csv_text({"ram_kb": raw}), "ram_kb").status, "missing", raw)

    def test_non_numeric_invalid(self):
        for raw in ("abc", "12kB", "1e3", '"1,000"', "nan", "inf", "+5", ".5", "0x10", "--3", "n/a"):
            f = field(csv_text({"ram_kb": raw}), "ram_kb")
            self.assertEqual(f.status, "invalid", raw)

    def test_negative_invalid(self):
        f = field(csv_text({"flash_kb": "-1"}), "flash_kb")
        self.assertEqual(f.status, "invalid")
        self.assertIn("negative", f.detail)

    def test_zero_bandwidth_invalid(self):
        for raw in ("0", "0.0"):
            f = field(csv_text({"link_bandwidth_bps": raw}), "link_bandwidth_bps")
            self.assertEqual(f.status, "invalid", raw)
            self.assertIn("greater than 0", f.detail)

    def test_zero_ram_allowed_by_loader(self):
        self.assertEqual(field(csv_text({"ram_kb": "0"}), "ram_kb").status, "ok")

    def test_yes_no(self):
        self.assertIs(field(csv_text({"bootrom_verifier_updatable": "YES"}),
                            "bootrom_verifier_updatable").value, True)
        self.assertIs(field(csv_text({"bootrom_verifier_updatable": "no"}),
                            "bootrom_verifier_updatable").value, False)
        self.assertEqual(field(csv_text({"bootrom_verifier_updatable": "maybe"}),
                               "bootrom_verifier_updatable").status, "invalid")
        self.assertEqual(field(csv_text({"updatable_bootloader_stage": ""}),
                               "updatable_bootloader_stage").status, "missing")

    def test_free_larger_than_total_is_invalid(self):
        f = field(csv_text({"flash_kb": "100", "free_flash_kb": "200"}), "free_flash_kb")
        self.assertEqual(f.status, "invalid")
        self.assertIn("exceeds", f.detail)
        f = field(csv_text({"ram_kb": "10", "free_ram_kb": "11"}), "free_ram_kb")
        self.assertEqual(f.status, "invalid")

    def test_free_equal_total_is_ok(self):
        self.assertEqual(field(csv_text({"flash_kb": "100", "free_flash_kb": "100"}),
                               "free_flash_kb").status, "ok")

    def test_extra_columns_ignored_and_listed(self):
        text = csv_text({}).replace("notes", "notes,extra", 1).replace("\nT1", "\nT1", 1)
        lines = text.splitlines()
        lines[1] += ",x"
        inv = parse_text("\n".join(lines) + "\n")
        self.assertEqual(inv.ignored_columns, ["extra"])


if __name__ == "__main__":
    unittest.main()
