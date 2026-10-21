"""Tests for the boot and update chain model. Author: Huda Mueen.

Run from the repository root:  python3 -m unittest discover -s bootchain/tests -t .
Expected values are computed by hand in the comments. Label: estimated, not measured.
"""
import os
import unittest

from bootchain import model as bm
from energy import model as em


class TestBoot(unittest.TestCase):
    def test_hash_time(self):
        # 1e6 B * 76 cycles/B / 168 MHz = 0.452381 s
        self.assertAlmostEqual(bm.hash_time_s(1e6, 76, 168), 76e6 / 168e6)

    def test_verify_time(self):
        # 1e5 B * 10 cycles/B / 100 MHz = 10 ms; 2e6 cycles / 100 MHz = 20 ms; total 30 ms
        self.assertAlmostEqual(bm.verify_time_s(1e5, 10, 2e6, 100), 0.030)

    def test_ab_layout(self):
        # 20000 + 2 * (100000 + 5000) + 4096 = 234096
        self.assertEqual(bm.ab_layout_bytes(100000, 5000, 20000, 4096), 234096)

    def test_max_image_ab(self):
        # (1e6 - 20000 - 4096) / 2 - 5000 = 487952 - 5000 = 482952
        self.assertAlmostEqual(bm.max_image_ab(1e6, 5000, 20000, 4096), 482952)
        img = bm.max_image_ab(1e6, 5000, 20000, 4096)
        self.assertAlmostEqual(bm.ab_layout_bytes(img, 5000, 20000, 4096), 1e6)

    def test_transfer(self):
        # 1000 B * 8 / (250 bit/s * 0.01) = 3200 s
        self.assertAlmostEqual(bm.transfer_time_s(1000, 250, 1.0, 0.01), 3200)

    def test_pct(self):
        self.assertAlmostEqual(bm.pct_increase(50, 75), 50.0)

    def test_link_rates(self):
        params = bm.link_param_rows()
        r = bm.link_rates(params)
        # SiK 64000 * 0.9 = 57600 bit/s; LoRaWAN 250 * 0.01 = 2.5 bit/s
        self.assertAlmostEqual(r["SiK 64 kbit/s air rate, 90 percent usable"][0], 57600)
        self.assertAlmostEqual(r["LoRaWAN DR0 250 bit/s at 1 percent duty cycle"][0], 2.5)

    def test_inputs_and_schemes(self):
        inp = bm.load_inputs()
        self.assertEqual(bm.inval(inp, "suit_u2_lms_increase_pct"), 9.0)
        for r in inp.values():
            self.assertIn(r["label"], ("published", "assumption", "derived from published"))
        ev = em.load_evidence()
        for s in bm.load_schemes():
            for ref in [s["sig_bytes_ref"], s["boot_row"], s["suit_sig_bytes_ref"]] + s["suit_lib_flash_ref"].split("|"):
                if ref:
                    self.assertIn(ref, ev, ref)

    def test_wolfboot_times_parse(self):
        ev = em.load_evidence()
        self.assertAlmostEqual(em.parse_time_ms(ev["S2-0347"]["compiler_flags_or_notes"]), 55.662)
        self.assertAlmostEqual(em.parse_time_ms(ev["S2-0351"]["compiler_flags_or_notes"]), 82.791)


if __name__ == "__main__":
    unittest.main()
