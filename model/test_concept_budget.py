#!/usr/bin/env python3
"""Unit tests for model/concept_budget.py (standard library unittest only).

Every figure the ORBIT-AI v0.1 brief publishes is asserted at the precision
the brief printed it.  A final test lists any published figure that does NOT
follow from the stated assumptions; with the current brief the list is empty,
and a negative control shows the check would catch a wrong figure.

Run:  python3 model/test_concept_budget.py [-v]
Env:  MODEL_RTL_DIR   RTL directory for the parameter cross-check (default rtl/)
"""

import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import concept_budget as cb  # noqa: E402

REPO = os.path.dirname(HERE)


def at(value, printed):
    """Model value formatted with the number of decimals the brief printed."""
    return cb.format_at(value, printed)


class TestCompute(unittest.TestCase):
    def test_mac_count(self):
        self.assertEqual(cb.macs_total(), 16384)

    def test_peak_200mhz(self):          # brief p.1 and p.2: 6.55
        self.assertEqual(at(cb.peak_tops(200e6), "6.55"), "6.55")
        self.assertAlmostEqual(cb.peak_tops(200e6), 6.5536, places=12)

    def test_peak_800mhz(self):          # brief p.2: 26.21, p.1: 26.2
        self.assertEqual(at(cb.peak_tops(800e6), "26.21"), "26.21")
        self.assertEqual(at(cb.peak_tops(800e6), "26.2"), "26.2")
        self.assertAlmostEqual(cb.peak_tops(800e6), 26.2144, places=12)

    def test_protected_peak_is_half(self):   # brief p.2: duplication halves peak
        for hz in (200e6, 800e6):
            self.assertAlmostEqual(cb.protected_peak_tops(hz) * 2, cb.peak_tops(hz))
        self.assertAlmostEqual(cb.protected_peak_tops(800e6), 13.1072, places=12)

    def test_throttled_peak_is_half(self):
        self.assertAlmostEqual(cb.throttled_peak_tops(800e6), 13.1072, places=12)

    def test_tops_per_watt_allocation(self):
        self.assertAlmostEqual(cb.tops_per_watt_allocation(800e6), 26.2144 / 40, places=12)
        self.assertAlmostEqual(cb.tops_per_watt_allocation(200e6), 6.5536 / 40, places=12)


class TestMemory(unittest.TestCase):
    def test_usable_sram_from_tiles(self):   # 16 x 2 MiB = 32 MiB
        self.assertEqual(cb.TILES * cb.SRAM_PER_TILE_BYTES, cb.SRAM_USABLE_BYTES)

    def test_raw_sram_36mib(self):           # brief p.1/p.2: 36 MiB raw bits
        self.assertEqual(cb.sram_raw_bytes(), 36 * 2**20)

    def test_local_bw_per_tile(self):        # brief p.2: 51.2 GB/s (64 B/cycle)
        self.assertEqual(cb.LOCAL_INPUT_BYTES_PER_CYCLE, 64)
        self.assertEqual(at(cb.local_input_bw_per_tile(800e6) / 1e9, "51.2"), "51.2")

    def test_local_bw_total(self):           # brief p.2: 819.2 GB/s
        self.assertEqual(at(cb.local_input_bw_total(800e6) / 1e9, "819.2"), "819.2")

    def test_matvec_ceiling(self):           # brief p.2: 0.512 TOPS
        self.assertEqual(at(cb.matvec_ceiling_tops(), "0.512"), "0.512")

    def test_ops_per_byte_for_peak(self):    # brief p.2: 102.4
        self.assertEqual(at(cb.ops_per_ext_byte_for_peak(), "102.4"), "102.4")
        self.assertAlmostEqual(cb.ops_per_ext_byte_for_peak(), 102.4, places=9)

    def test_ridge_needs_decimal_gbs(self):
        # 102.4 only follows with decimal GB/s; binary GiB/s would give 95.4.
        self.assertEqual(at(cb.ops_per_ext_byte_for_peak(bw=256 * 2**30), "95.4"), "95.4")

    def test_roofline(self):
        self.assertAlmostEqual(cb.attainable_tops(2), 0.512)
        self.assertAlmostEqual(cb.attainable_tops(102.4), cb.peak_tops(800e6))
        self.assertAlmostEqual(cb.attainable_tops(1000), cb.peak_tops(800e6))
        # Monotone non-decreasing in intensity and capped at peak.
        vals = [cb.attainable_tops(i) for i in cb.ROOFLINE_INTENSITIES]
        self.assertEqual(vals, sorted(vals))
        self.assertLessEqual(max(vals), cb.peak_tops(800e6) + 1e-12)


class TestThermal(unittest.TestCase):
    AREAS = {300.0: ("2.42", "242"), 320.0: ("1.87", "187"), 350.0: ("1.31", "131")}

    def test_radiator_area_per_kw(self):     # brief p.3 table
        for t, (per_kw, _) in self.AREAS.items():
            with self.subTest(T=t):
                self.assertEqual(at(cb.radiator_area_m2(1e3, t), per_kw), per_kw)

    def test_radiator_area_per_100kw(self):
        for t, (_, per_100kw) in self.AREAS.items():
            with self.subTest(T=t):
                self.assertEqual(at(cb.radiator_area_m2(100e3, t), per_100kw), per_100kw)

    def test_radiator_law(self):
        # P = e sigma A T^4 round trip.
        a = cb.radiator_area_m2(1e3, 320.0)
        self.assertAlmostEqual(cb.EMISSIVITY * cb.STEFAN_BOLTZMANN * a * 320.0 ** 4, 1e3)

    def test_junction_rise(self):            # brief p.3: 20 C warmer
        self.assertEqual(cb.junction_rise_k(), 20.0)

    def test_junction_320k(self):            # brief p.3: 66.85 C
        self.assertEqual(at(cb.junction_c(320.0), "66.85"), "66.85")

    def test_junction_350k_above_stop(self):  # brief p.3: 96.85 C, above 95 C stop
        self.assertEqual(at(cb.junction_c(350.0), "96.85"), "96.85")
        self.assertGreater(cb.junction_c(350.0), cb.T_STOP_C)
        self.assertEqual(cb.thermal_state_from_normal(cb.junction_c(350.0)), "STOP")

    def test_junction_states(self):
        self.assertEqual(cb.thermal_state_from_normal(cb.junction_c(300.0)), "NORMAL")
        self.assertEqual(cb.thermal_state_from_normal(cb.junction_c(320.0)), "NORMAL")
        self.assertEqual(cb.thermal_state_from_normal(80), "THROTTLE")
        self.assertEqual(cb.thermal_state_from_normal(79.99), "NORMAL")
        self.assertEqual(cb.thermal_state_from_normal(95), "STOP")

    def test_max_radiator(self):
        self.assertAlmostEqual(cb.max_radiator_k_for(80), 333.15)
        self.assertAlmostEqual(cb.max_radiator_k_for(95), 348.15)


class TestDemonstrator(unittest.TestCase):
    def test_demo_peak(self):
        self.assertAlmostEqual(cb.demo_peak_ops(100e6, 4), 0.8e9)

    def test_rtl_parameters_match_model(self):
        rtl_dir = os.environ.get("MODEL_RTL_DIR", os.path.join(REPO, "rtl"))
        p = cb.rtl_parameters(rtl_dir)
        self.assertEqual(p.get("LANES"), cb.DEMO_LANES_DEFAULT)
        self.assertEqual(p.get("T_THROTTLE"), cb.T_THROTTLE_C)
        self.assertEqual(p.get("T_STOP"), cb.T_STOP_C)
        self.assertEqual(p.get("T_RECOVER"), cb.T_RECOVER_C)

    def test_rtl_thresholds_reach_thermal_fsm(self):
        # The thresholds checked above only matter if orbit_demo passes them
        # through to orbit_thermal_tmr unchanged (.T_X (T_X)).
        rtl_dir = os.environ.get("MODEL_RTL_DIR", os.path.join(REPO, "rtl"))
        conn = cb.rtl_thermal_overrides(rtl_dir)
        for name in cb.THERMAL_PARAM_NAMES:
            with self.subTest(param=name):
                self.assertEqual(conn.get(name), name)

    def test_verilog_int_literals(self):
        self.assertEqual(cb.verilog_int("95"), 95)
        self.assertEqual(cb.verilog_int("8'sd95"), 95)
        self.assertEqual(cb.verilog_int("8'sh5F"), 95)
        self.assertEqual(cb.verilog_int("8'b0101_1111"), 95)
        self.assertEqual(cb.verilog_int("4'h8"), 8)      # not the width 4
        self.assertIsNone(cb.verilog_int("8'sd9x"))
        self.assertIsNone(cb.verilog_int("T_BASE+15"))

    def test_rtl_parameter_parser_negative_controls(self):
        # A hex-coded wrong LANES, a commented-out stale value and a miswired
        # threshold must all be seen by the cross-check readers.
        src = ("// parameter integer LANES = 4,\n"
               "module orbit_demo #(parameter integer LANES = 4'h8,\n"
               "  parameter signed [7:0] T_THROTTLE = 8'sd80,\n"
               "  parameter signed [7:0] T_STOP = 8'sh5F,\n"
               "  parameter signed [7:0] T_RECOVER = 8'sd70) ();\n"
               "orbit_thermal_tmr #(.T_THROTTLE (T_THROTTLE), .T_STOP (T_THROTTLE),\n"
               "  .T_RECOVER(T_RECOVER)) u_thermal (.clk(clk));\nendmodule\n")
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "orbit_demo.v"), "w") as fh:
                fh.write(src)
            self.assertEqual(cb.rtl_parameters(d),
                             {"LANES": 8, "T_THROTTLE": 80, "T_STOP": 95, "T_RECOVER": 70})
            self.assertEqual(cb.rtl_thermal_overrides(d),
                             {"T_THROTTLE": "T_THROTTLE", "T_STOP": "T_THROTTLE",
                              "T_RECOVER": "T_RECOVER"})

    def test_pd_clock_parsing(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "summary.md")
            self.assertIsNone(cb.pd_closed_clock_mhz(path))          # missing file
            with open(path, "w") as fh:
                fh.write("# pd\nclock period 7.0 ns (target)\n")
            self.assertIsNone(cb.pd_closed_clock_mhz(path))          # not stated as closed
            with open(path, "w") as fh:
                fh.write("Timing closed at period 8.0 ns\n")
            self.assertAlmostEqual(cb.pd_closed_clock_mhz(path), 125.0)
            with open(path, "w") as fh:
                fh.write("| closed clock | 142.86 MHz |\n")
            self.assertAlmostEqual(cb.pd_closed_clock_mhz(path), 142.86)
            with open(path, "w") as fh:                               # pd sweep wording
                fh.write("| 7 | 142.9 | 0.066 | CLOSED |\n"
                         "Best closed period: **7 ns (142.9 MHz)**.\n")
            self.assertAlmostEqual(cb.pd_closed_clock_mhz(path), 142.9)
            with open(path, "w") as fh:                               # negated closure
                fh.write("Timing not closed at 6.5 ns (153.8 MHz)\n"
                         "Timing closure failed at 150 MHz\n")
            self.assertIsNone(cb.pd_closed_clock_mhz(path))
            with open(path, "w") as fh:                               # target before result
                fh.write("Target 150 MHz; closed at period 8.0 ns\n")
            self.assertAlmostEqual(cb.pd_closed_clock_mhz(path), 125.0)


class TestBriefConsistency(unittest.TestCase):
    def test_no_brief_figure_disagrees(self):
        rows, bad = cb.check_brief()
        self.assertGreaterEqual(len(rows), 19)
        # Explicit flag: names every published figure that does not follow.
        self.assertEqual(bad, [], "brief figures NOT following from the assumptions: %s" % bad)
        for text, ok in cb.brief_qualitative_claims():
            with self.subTest(claim=text):
                self.assertTrue(ok, "brief claim does not follow: " + text)

    def test_check_detects_wrong_figure(self):
        # Negative control: a figure off by one unit in its last printed digit,
        # and one misrounded, must be flagged.
        figs = [("x", 2, "wrong peak", "26.22", cb.peak_tops(800e6)),
                ("y", 2, "misrounded", "6.56", cb.peak_tops(200e6)),
                ("z", 3, "correct", "66.85", cb.junction_c(320.0))]
        _, bad = cb.check_brief(figs)
        self.assertEqual(bad, ["x", "y"])

    def test_report_states_agreement(self):
        text = cb.report()
        self.assertIn("RESULT: all", text)
        self.assertNotIn("DISAGREES", text)


if __name__ == "__main__":
    unittest.main()
