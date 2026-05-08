#!/usr/bin/env python3
"""ORBIT-AI v0.1 concept budget: the arithmetic behind the design brief.

The brief (docs/orbit-ai-design-brief.pdf, pages 2, 3 and 5) states a set of
project assumptions and publishes numbers derived from them.  This module
recomputes every published number from the assumptions alone, adds a few
derived figures the brief implies but does not print, and prints a report.

Nothing here is a measurement.  Throughput figures are calculated peak
bounds; the TOPS/W figure divides a peak bound by a 40 W *allocation*, which
the brief explicitly says is not a power estimate.

Units: GB/s and TOPS are decimal (1e9, 1e12).  MiB/GiB are binary (2^20, 2^30).
The 256 GB/s external bandwidth is taken as decimal; the published 102.4
ops/byte only follows with that reading (with 256 GiB/s it would be 95.4).

Standard library only.  Usage:
    python3 model/concept_budget.py [--rtl-dir DIR] [--pd-summary FILE]
                                    [--demo-clock-mhz F]
"""

import argparse
import math
import os
import re
import sys

# ---------------------------------------------------------------------------
# Project assumptions (brief pages 2, 3 and 5).  Change them here only.
# ---------------------------------------------------------------------------
TILES = 16                       # INT8 tensor tiles
ARRAY_ROWS = 32                  # MAC array per tile: 32 x 32
ARRAY_COLS = 32
OPS_PER_MAC = 2                  # a multiply-accumulate counts as two operations
CLOCK_MIN_HZ = 200e6             # explored clock range
CLOCK_MAX_HZ = 800e6

SRAM_USABLE_BYTES = 32 * 2**20   # 32 MiB usable local SRAM ...
SRAM_PER_TILE_BYTES = 2 * 2**20  # ... distributed 2 MiB per tile
ECC_DATA_BITS = 64               # SECDED (72,64): 64 data + 8 check bits
ECC_CHECK_BITS = 8

EXT_BW_BYTES_S = 256e9           # external memory bandwidth scenario (decimal GB/s)
EXT_CAPACITY_BYTES = 16 * 2**30  # 16 GiB+ external memory (a floor, "16 GiB+")

POWER_ALLOC_W = 40.0             # per-chip sizing allocation, NOT an estimate
R_DIE_TO_RADIATOR_K_PER_W = 0.5  # lumped die-to-radiator thermal resistance
EMISSIVITY = 0.9
STEFAN_BOLTZMANN = 5.670374419e-8  # W m^-2 K^-4 (CODATA 2018, exact in SI)
RADIATOR_TEMPS_K = (300.0, 320.0, 350.0)
KELVIN_OFFSET = 273.15

T_RECOVER_C = 70                 # illustrative thermal thresholds (brief p.3,
T_THROTTLE_C = 80                # SPEC section 6)
T_STOP_C = 95

DUPLICATION_FACTOR = 2           # fully duplicated execution halves useful peak
THROTTLE_ADMIT_FRACTION = 0.5    # alternate-cycle admission in THROTTLE

# Local-input bandwidth assumption: a conventional 32 x 32 array fed from its
# two edges takes one INT8 operand per row and one per column every cycle,
# i.e. 32 + 32 = 64 bytes/cycle per tile.  Reuse inside the array (each
# operand touches 32 MACs) is what makes this far below 2 bytes per MAC.
LOCAL_INPUT_BYTES_PER_CYCLE = ARRAY_ROWS + ARRAY_COLS

# Streaming INT8 matrix-vector: each weight byte is used by exactly one MAC.
MATVEC_OPS_PER_BYTE = OPS_PER_MAC

# 4-lane demonstrator (SPEC section 1/3): LANES independent INT8 MACs, one beat
# per cycle in NORMAL.  Duplicated storage shares the product, so all lanes are
# useful lanes.  Overridden by the RTL parameter when --rtl-dir is given.
DEMO_LANES_DEFAULT = 4
DEMO_CLOCKS_MHZ_DEFAULT = (50.0, 100.0, 200.0)

ROOFLINE_INTENSITIES = (0.5, 1, 2, 4, 8, 16, 32, 64, 102.4, 128, 256, 512)


# ---------------------------------------------------------------------------
# Derived quantities
# ---------------------------------------------------------------------------
def macs_total():
    return TILES * ARRAY_ROWS * ARRAY_COLS


def peak_ops(clock_hz, tiles=TILES):
    """Dense INT8 peak in operations per second."""
    return tiles * ARRAY_ROWS * ARRAY_COLS * OPS_PER_MAC * clock_hz


def peak_tops(clock_hz):
    return peak_ops(clock_hz) / 1e12


def protected_peak_tops(clock_hz):
    """Useful peak with every operation executed twice and compared."""
    return peak_tops(clock_hz) / DUPLICATION_FACTOR


def throttled_peak_tops(clock_hz):
    """Useful peak under alternate-cycle admission (THROTTLE state)."""
    return peak_tops(clock_hz) * THROTTLE_ADMIT_FRACTION


def tops_per_watt_allocation(clock_hz):
    """Peak bound divided by the 40 W allocation.  Allocation-derived, not measured."""
    return peak_tops(clock_hz) / POWER_ALLOC_W


def sram_raw_bytes():
    """Raw bits (as bytes) needed to store the usable SRAM under 64+8 SECDED."""
    return SRAM_USABLE_BYTES * (ECC_DATA_BITS + ECC_CHECK_BITS) / ECC_DATA_BITS


def ecc_overhead_fraction():
    return ECC_CHECK_BITS / ECC_DATA_BITS


def local_input_bw_per_tile(clock_hz):
    return LOCAL_INPUT_BYTES_PER_CYCLE * clock_hz


def local_input_bw_total(clock_hz):
    return TILES * local_input_bw_per_tile(clock_hz)


def matvec_ceiling_tops(bw=EXT_BW_BYTES_S, ops_per_byte=MATVEC_OPS_PER_BYTE):
    """Memory-bound ideal ceiling of a streaming matrix-vector workload."""
    return bw * ops_per_byte / 1e12


def ops_per_ext_byte_for_peak(clock_hz=CLOCK_MAX_HZ, bw=EXT_BW_BYTES_S):
    """Roofline ridge point: arithmetic intensity needed to reach peak."""
    return peak_ops(clock_hz) / bw


def attainable_tops(intensity, clock_hz=CLOCK_MAX_HZ, bw=EXT_BW_BYTES_S):
    """Classic roofline: min(compute peak, intensity x bandwidth)."""
    return min(peak_ops(clock_hz), intensity * bw) / 1e12


def radiator_area_m2(power_w, temp_k, emissivity=EMISSIVITY):
    """Ideal emitting area, P = e * sigma * A * T^4, 0 K view, no external loads."""
    return power_w / (emissivity * STEFAN_BOLTZMANN * temp_k ** 4)


def junction_rise_k(power_w=POWER_ALLOC_W, r=R_DIE_TO_RADIATOR_K_PER_W):
    return power_w * r


def junction_c(radiator_k, power_w=POWER_ALLOC_W, r=R_DIE_TO_RADIATOR_K_PER_W):
    return radiator_k + junction_rise_k(power_w, r) - KELVIN_OFFSET


def max_radiator_k_for(junction_limit_c, power_w=POWER_ALLOC_W, r=R_DIE_TO_RADIATOR_K_PER_W):
    return junction_limit_c + KELVIN_OFFSET - junction_rise_k(power_w, r)


def thermal_state_from_normal(t_c):
    """Steady-state thermal state reached from NORMAL at a constant reading.

    Follows the SPEC section 6 table (first match wins): t >= stop -> STOP,
    t >= throttle -> THROTTLE, else NORMAL.  The RTL compares whole degrees;
    a fractional junction temperature is compared as is (a sensor reporting
    floor(t) gives the same answer for all figures in this report).
    """
    if t_c >= T_STOP_C:
        return "STOP"
    if t_c >= T_THROTTLE_C:
        return "THROTTLE"
    return "NORMAL"


def demo_peak_ops(clock_hz, lanes=DEMO_LANES_DEFAULT):
    """4-lane demonstrator peak: every lane does one MAC per accepted beat."""
    return lanes * OPS_PER_MAC * clock_hz


# ---------------------------------------------------------------------------
# Published figures and the check against them
# ---------------------------------------------------------------------------
# (key, page, description, printed text, computed value in the printed unit).
# The check formats the computed value with the number of decimals the brief
# printed and compares strings, i.e. "agrees at the brief's printed precision".
def brief_figures():
    f = []
    add = lambda key, page, desc, printed, value: f.append((key, page, desc, printed, value))
    add("peak_200", 2, "dense INT8 TOPS at 200 MHz", "6.55", peak_tops(CLOCK_MIN_HZ))
    add("peak_800", 2, "dense INT8 TOPS at 800 MHz", "26.21", peak_tops(CLOCK_MAX_HZ))
    add("peak_200_p1", 1, "dense INT8 TOPS at 200 MHz (cover)", "6.55", peak_tops(CLOCK_MIN_HZ))
    add("peak_800_p1", 1, "dense INT8 TOPS at 800 MHz (cover)", "26.2", peak_tops(CLOCK_MAX_HZ))
    add("sram_usable", 2, "usable SRAM MiB = tiles x 2 MiB", "32",
        TILES * SRAM_PER_TILE_BYTES / 2**20)
    add("sram_raw", 2, "raw SRAM MiB with 64+8 SECDED", "36", sram_raw_bytes() / 2**20)
    add("bw_tile", 2, "local input GB/s per tile at 800 MHz", "51.2",
        local_input_bw_per_tile(CLOCK_MAX_HZ) / 1e9)
    add("bw_total", 2, "local input GB/s, 16 tiles at 800 MHz", "819.2",
        local_input_bw_total(CLOCK_MAX_HZ) / 1e9)
    add("matvec", 2, "matrix-vector ceiling TOPS at 256 GB/s, 2 ops/byte", "0.512",
        matvec_ceiling_tops())
    add("ridge", 2, "ops per external byte for the 800 MHz peak", "102.4",
        ops_per_ext_byte_for_peak())
    for t, per_kw, per_100kw in ((300.0, "2.42", "242"), (320.0, "1.87", "187"),
                                 (350.0, "1.31", "131")):
        add("area_kw_%d" % t, 3, "emitting area m2 per kW at %d K" % t, per_kw,
            radiator_area_m2(1e3, t))
        add("area_100kw_%d" % t, 3, "emitting area m2 per 100 kW at %d K" % t, per_100kw,
            radiator_area_m2(100e3, t))
    add("rise", 3, "junction rise over radiator, C (40 W x 0.5 K/W)", "20", junction_rise_k())
    add("tj_320", 3, "junction C with a 320 K radiator", "66.85", junction_c(320.0))
    add("tj_350", 3, "junction C with a 350 K radiator", "96.85", junction_c(350.0))
    return f


def decimals_of(printed):
    return len(printed.split(".")[1]) if "." in printed else 0


def format_at(value, printed):
    return "%.*f" % (decimals_of(printed), value)


def check_brief(figures=None):
    """Return (rows, disagreements).  Each row: key, page, desc, printed, computed, ok."""
    rows, bad = [], []
    for key, page, desc, printed, value in (figures if figures is not None else brief_figures()):
        ok = format_at(value, printed) == printed
        rows.append((key, page, desc, printed, value, ok))
        if not ok:
            bad.append(key)
    return rows, bad


def brief_qualitative_claims():
    """Statements in the brief that are comparisons rather than printed numbers."""
    return [
        ("350 K radiator junction is above the 95 C stop threshold (p.3)",
         junction_c(350.0) > T_STOP_C),
        ("fully duplicated work halves useful peak (p.2)",
         math.isclose(protected_peak_tops(CLOCK_MAX_HZ) * 2, peak_tops(CLOCK_MAX_HZ))),
        ("2 MiB per tile x 16 tiles equals the 32 MiB usable (p.2)",
         TILES * SRAM_PER_TILE_BYTES == SRAM_USABLE_BYTES),
        ("local traffic (819.2 GB/s) exceeds the 256 GB/s external bandwidth (p.2)",
         local_input_bw_total(CLOCK_MAX_HZ) > EXT_BW_BYTES_S),
    ]


# ---------------------------------------------------------------------------
# Optional inputs from other areas
# ---------------------------------------------------------------------------
def rtl_parameters(rtl_dir):
    """Read LANES and the thermal thresholds from $(RTL_DIR)/orbit_demo.v."""
    path = os.path.join(rtl_dir, "orbit_demo.v")
    with open(path) as fh:
        text = fh.read()
    params = {}
    for name in ("LANES", "T_THROTTLE", "T_STOP", "T_RECOVER"):
        m = re.search(r"parameter\b[^;,)]*?\b%s\s*=\s*(?:\d+'s?d)?(\d+)" % name, text)
        if m:
            params[name] = int(m.group(1))
    return params


def pd_closed_clock_mhz(path):
    """Closed clock from the pd area's summary, or None.

    Accepts a line mentioning a closed/achieved clock with a MHz value, or a
    closed clock period in ns, e.g. "closed clock: 142.9 MHz" or
    "timing closed at period 7.0 ns".  Returns the first match.
    """
    if not path or not os.path.isfile(path):
        return None
    with open(path) as fh:
        for line in fh:
            low = line.lower()
            if "clos" not in low:
                continue
            m = re.search(r"(\d+(?:\.\d+)?)\s*mhz", low)
            if m:
                return float(m.group(1))
            m = re.search(r"period[^0-9]*(\d+(?:\.\d+)?)\s*ns", low)
            if m and float(m.group(1)) > 0:
                return 1e3 / float(m.group(1))
    return None


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
def report(demo_lanes=DEMO_LANES_DEFAULT, demo_clocks_mhz=DEMO_CLOCKS_MHZ_DEFAULT,
           demo_clock_source="parameter (no closed clock supplied)", rtl_params=None):
    out = []
    w = out.append
    mhz = lambda hz: "%.0f MHz" % (hz / 1e6)

    w("ORBIT-AI v0.1 concept budget (model/concept_budget.py)")
    w("=" * 72)
    w("Calculated bounds from the brief's stated assumptions. No measurement,")
    w("benchmark, power estimate or thermal simulation is represented here.")
    w("")
    w("Assumptions")
    w("-" * 72)
    w("  tiles x array               %d x %d x %d = %d INT8 MACs" %
      (TILES, ARRAY_ROWS, ARRAY_COLS, macs_total()))
    w("  ops per MAC                 %d" % OPS_PER_MAC)
    w("  clock range                 %s - %s (no timing measurement)" %
      (mhz(CLOCK_MIN_HZ), mhz(CLOCK_MAX_HZ)))
    w("  local SRAM                  %d MiB usable, %d MiB per tile, SECDED %d+%d" %
      (SRAM_USABLE_BYTES // 2**20, SRAM_PER_TILE_BYTES // 2**20, ECC_DATA_BITS, ECC_CHECK_BITS))
    w("  external memory             %d GiB+ at %.0f GB/s (decimal GB)" %
      (EXT_CAPACITY_BYTES // 2**30, EXT_BW_BYTES_S / 1e9))
    w("  power allocation            %.0f W (sizing allocation, not an estimate)" % POWER_ALLOC_W)
    w("  die-to-radiator resistance  %.1f K/W" % R_DIE_TO_RADIATOR_K_PER_W)
    w("  radiator                    emissivity %.1f, sigma %.9e W/m2/K4, 0 K view" %
      (EMISSIVITY, STEFAN_BOLTZMANN))
    w("  thermal thresholds          recover %d C, throttle %d C, stop %d C" %
      (T_RECOVER_C, T_THROTTLE_C, T_STOP_C))
    w("  local input per tile        %d bytes/cycle (32 row + 32 column INT8 operands)" %
      LOCAL_INPUT_BYTES_PER_CYCLE)
    w("  matrix-vector intensity     %d ops per weight byte (one MAC per byte)" %
      MATVEC_OPS_PER_BYTE)
    w("")

    w("Compute")
    w("-" * 72)
    w("  %-10s %12s %14s %14s %14s" % ("clock", "peak TOPS", "protected", "throttled",
                                       "TOPS/W @40W*"))
    for hz in (CLOCK_MIN_HZ, 400e6, 600e6, CLOCK_MAX_HZ):
        w("  %-10s %12.4f %14.4f %14.4f %14.4f" %
          (mhz(hz), peak_tops(hz), protected_peak_tops(hz), throttled_peak_tops(hz),
           tops_per_watt_allocation(hz)))
    w("  * allocation-derived: peak bound / 40 W allocation. Not measured, not an")
    w("    efficiency estimate. Protected = fully duplicated execution (1/2);")
    w("    throttled = alternate-cycle admission (1/2).")
    w("")

    w("Memory")
    w("-" * 72)
    w("  raw SRAM bits for 32 MiB usable      %.2f MiB (+%.1f%% check bits, before spares)" %
      (sram_raw_bytes() / 2**20, 100 * ecc_overhead_fraction()))
    w("  local input bandwidth @ 800 MHz      %.1f GB/s per tile, %.1f GB/s for %d tiles" %
      (local_input_bw_per_tile(CLOCK_MAX_HZ) / 1e9, local_input_bw_total(CLOCK_MAX_HZ) / 1e9,
       TILES))
    w("  local / external bandwidth ratio     %.1f x" %
      (local_input_bw_total(CLOCK_MAX_HZ) / EXT_BW_BYTES_S))
    w("  matrix-vector ceiling @ 256 GB/s     %.3f TOPS (%.2f%% of the 800 MHz peak)" %
      (matvec_ceiling_tops(), 100 * matvec_ceiling_tops() / peak_tops(CLOCK_MAX_HZ)))
    w("  ops per external byte for peak       %.1f @ 800 MHz, %.1f @ 200 MHz" %
      (ops_per_ext_byte_for_peak(CLOCK_MAX_HZ), ops_per_ext_byte_for_peak(CLOCK_MIN_HZ)))
    w("  time to stream 16 GiB once           %.3f s at 256 GB/s" %
      (EXT_CAPACITY_BYTES / EXT_BW_BYTES_S))
    w("")

    w("Roofline (external bandwidth 256 GB/s; attainable = min(peak, I x BW))")
    w("-" * 72)
    w("  %-16s %16s %16s" % ("ops/byte I", "TOPS @ 200 MHz", "TOPS @ 800 MHz"))
    for i in ROOFLINE_INTENSITIES:
        t200 = attainable_tops(i, CLOCK_MIN_HZ)
        t800 = attainable_tops(i, CLOCK_MAX_HZ)
        tag = lambda t, hz: "%.4f%s" % (t, " (peak)" if t >= peak_tops(hz) else "")
        w("  %-16s %16s %16s" % (("%g" % i), tag(t200, CLOCK_MIN_HZ), tag(t800, CLOCK_MAX_HZ)))
    w("")

    w("Radiator and junction (lumped, steady state, 40 W allocation)")
    w("-" * 72)
    w("  %-10s %12s %14s %12s %12s" % ("radiator", "m2 per kW", "m2 per 100 kW",
                                       "junction C", "state"))
    for t in RADIATOR_TEMPS_K:
        tj = junction_c(t)
        w("  %-10s %12.4f %14.2f %12.2f %12s" %
          ("%.0f K" % t, radiator_area_m2(1e3, t), radiator_area_m2(100e3, t), tj,
           thermal_state_from_normal(tj)))
    w("  junction rise over radiator: %.1f K" % junction_rise_k())
    w("  hottest radiator keeping the junction below throttle (%d C): %.2f K" %
      (T_THROTTLE_C, max_radiator_k_for(T_THROTTLE_C)))
    w("  hottest radiator keeping the junction below stop (%d C):     %.2f K" %
      (T_STOP_C, max_radiator_k_for(T_STOP_C)))
    w("  Emitting area only: excludes sunlight, Earth IR/albedo, view factor,")
    w("  gradients, ageing and margin.")
    w("")

    w("4-lane demonstrator (rtl/orbit_demo.v)")
    w("-" * 72)
    if rtl_params:
        w("  RTL parameters read: " + ", ".join("%s=%d" % kv for kv in sorted(rtl_params.items())))
    w("  lanes %d, %d ops per MAC, one beat per cycle in NORMAL; clock: %s" %
      (demo_lanes, OPS_PER_MAC, demo_clock_source))
    w("  %-12s %16s %16s" % ("clock", "peak GOPS", "throttled GOPS"))
    for f in demo_clocks_mhz:
        p = demo_peak_ops(f * 1e6, demo_lanes) / 1e9
        w("  %-12s %16.4f %16.4f" % ("%.3f MHz" % f, p, p * THROTTLE_ADMIT_FRACTION))
    w("  Duplicated storage shares one product per lane, so all lanes are useful;")
    w("  a mismatch stops the design (no replay). STOP admits nothing.")
    w("")

    rows, bad = check_brief()
    w("Brief figures checked at the brief's printed precision")
    w("-" * 72)
    w("  %-4s %-52s %8s %12s %s" % ("page", "figure", "brief", "model", "result"))
    for key, page, desc, printed, value, ok in rows:
        w("  %-4d %-52s %8s %12s %s" %
          (page, desc, printed, format_at(value, printed), "agrees" if ok else "DISAGREES"))
    w("")
    w("  Qualitative claims:")
    for text, ok in brief_qualitative_claims():
        w("  %-9s %s" % ("agrees" if ok else "DISAGREES", text))
    w("")
    bad += [text for text, ok in brief_qualitative_claims() if not ok]
    if bad:
        w("RESULT: brief figures that do NOT follow from the assumptions: " + "; ".join(bad))
    else:
        w("RESULT: all %d published figures and %d qualitative claims follow from the "
          "stated assumptions." % (len(rows), len(brief_qualitative_claims())))
    return "\n".join(out) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rtl-dir", help="read LANES and thresholds from DIR/orbit_demo.v")
    ap.add_argument("--pd-summary", default="reports/pd/summary.md",
                    help="pd summary giving a closed clock (used if it exists)")
    ap.add_argument("--demo-clock-mhz", type=float, action="append",
                    help="demonstrator clock(s) to tabulate when no closed clock is known")
    args = ap.parse_args(argv)

    lanes, rtl_params = DEMO_LANES_DEFAULT, None
    if args.rtl_dir:
        rtl_params = rtl_parameters(args.rtl_dir)
        lanes = rtl_params.get("LANES", lanes)
        # The model's thresholds must match the RTL it describes.
        expect = {"T_RECOVER": T_RECOVER_C, "T_THROTTLE": T_THROTTLE_C, "T_STOP": T_STOP_C}
        for k, v in expect.items():
            if k in rtl_params and rtl_params[k] != v:
                print("warning: RTL %s=%d differs from model %d" % (k, rtl_params[k], v),
                      file=sys.stderr)

    closed = pd_closed_clock_mhz(args.pd_summary)
    if closed is not None:
        clocks, source = (closed,), "closed clock from %s" % args.pd_summary
    elif args.demo_clock_mhz:
        clocks, source = tuple(args.demo_clock_mhz), "parameter (command line)"
    else:
        clocks = DEMO_CLOCKS_MHZ_DEFAULT
        source = "parameter; %s not found or states no closed clock" % args.pd_summary

    text = report(lanes, clocks, source, rtl_params)
    sys.stdout.write(text)
    return 0 if "RESULT: all" in text else 1


if __name__ == "__main__":
    sys.exit(main())
