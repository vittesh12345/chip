"""Pin-position map of the reviewed orbit_demo layout (sky130hd, variant sep).

Review package section 08_pinout_packaging. Plots package data only:
  - signal pin origins, layer, edge and SPEC port:  pinout.csv (this folder;
    written by parse_pins.py from build/pd_sep/results/sky130hd/orbit_demo/sep/6_final.def)
  - die area, core rows and the VDD/VSS met5 strap rectangles:
    ../06_physical_design/layout_db/6_final.def.gz (gzip copy of the same DEF,
    sha256 of the decompressed file f5c544f3...0ec1)

Every signal pin is drawn as a short tick outside the die edge it sits on. The
tick's position along the edge is the real DEF pin origin; its distance band from
the edge encodes the port group (in_a, in_b, out_data, control/status) so that
group identity does not rely on colour alone. Tick length and band offset have no
physical meaning (all signal pin origins lie within 0.4 um of the die boundary). Pin shapes themselves are
0.8 x 0.3 um (met3) and 0.14 x 0.485 um (met2), far too small to draw to scale.

usage: python plot_pin_map.py   (writes pin_map.png next to this script)
"""
import collections
import csv
import gzip
import os
import re

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.normpath(os.path.join(HERE, ".."))
PINOUT = os.path.join(HERE, "pinout.csv")
DEF = os.path.join(PKG, "06_physical_design", "layout_db", "6_final.def.gz")
OUT = os.path.join(HERE, "pin_map.png")

# Categorical slots 1-3 of the dataviz reference palette (validated all-pairs,
# light mode); control/status pins use a neutral ink so only three hues are in play.
GROUP_COLOR = {"in_a": "#2a78d6", "in_b": "#eb6834", "out_data": "#1baf7a", "ctrl": "#3a3936"}
GROUP_LABEL = {
    "in_a": "in_a[31:0] (32 in)",
    "in_b": "in_b[31:0] (32 in)",
    "out_data": "out_data[127:0] (128 out)",
    "ctrl": "clock, reset, handshake, thermal, fault (23 bits)",
}
BAND = {"in_a": 0, "in_b": 1, "out_data": 2, "ctrl": 3}   # outward band index
BAND_W = 8.0                                              # um per band (drawing only)
INK, INK2, MUTED = "#0b0b0b", "#52514e", "#8f8d87"
VDD_C, VSS_C = "#d6d4cd", "#a9a7a0"


def read_def(path):
    """Die area, core row extent and VDD/VSS met5 rectangles (um) from the DEF."""
    with gzip.open(path, "rt") as f:
        txt = f.read()
    units = int(re.search(r"UNITS DISTANCE MICRONS (\d+)", txt).group(1))
    die = [int(v) / units for v in re.search(
        r"DIEAREA \( (-?\d+) (-?\d+) \) \( (-?\d+) (-?\d+) \)", txt).groups()]
    rows = re.findall(r"^ROW \S+ \S+ (\d+) (\d+) \S+ DO (\d+) BY 1 STEP (\d+) 0", txt, re.M)
    x0 = min(int(r[0]) for r in rows) / units
    x1 = max(int(r[0]) + int(r[2]) * int(r[3]) for r in rows) / units
    y0 = min(int(r[1]) for r in rows) / units
    y1 = (max(int(r[1]) for r in rows) + 2720) / units      # unithd row height 2.72 um
    pins = txt[txt.index("\nPINS "):txt.index("\nEND PINS")]
    straps = {}
    for net in ("VDD", "VSS"):
        blk = re.search(r"- %s \+ NET %s .*?;" % (net, net), pins, re.S).group(0)
        ox, oy = (int(v) for v in re.search(r"\+ FIXED \( (-?\d+) (-?\d+) \)", blk).groups())
        rects = re.findall(r"LAYER met5 \( (-?\d+) (-?\d+) \) \( (-?\d+) (-?\d+) \)", blk)
        straps[net] = [((ox + int(a)) / units, (oy + int(b)) / units,
                        (ox + int(c)) / units, (oy + int(d)) / units) for a, b, c, d in rects]
    return die, (x0, y0, x1, y1), straps


def group_of(port):
    return port if port in ("in_a", "in_b", "out_data") else "ctrl"


def main():
    rows = list(csv.DictReader(open(PINOUT)))
    sig = [r for r in rows if r["use"] == "SIGNAL"]
    assert len(rows) == 217 and len(sig) == 215, (len(rows), len(sig))
    die, core, straps = read_def(DEF)
    assert die == [0.0, 0.0, 346.295, 346.295], die
    D = die[2]

    fig, ax = plt.subplots(figsize=(10.0, 9.2), dpi=200)
    ax.set_aspect("equal")

    # VDD / VSS met5 strap pins (true geometry, 1.6 um tall)
    for net, col in (("VDD", VDD_C), ("VSS", VSS_C)):
        for (a, b, c, d) in straps[net]:
            ax.add_patch(Rectangle((a, b), c - a, d - b, facecolor=col, edgecolor="none", zorder=1))
    # core rows extent and die outline
    ax.add_patch(Rectangle((core[0], core[1]), core[2] - core[0], core[3] - core[1],
                           fill=False, ls=(0, (4, 3)), lw=0.7, ec=MUTED, zorder=2))
    ax.add_patch(Rectangle((0, 0), D, D, fill=False, lw=1.2, ec=INK, zorder=3))

    # pin ticks, outward from the real pin origin
    by_edge = collections.defaultdict(list)
    for r in sig:
        x, y, e, g = float(r["x_um"]), float(r["y_um"]), r["edge"], group_of(r["spec_port"])
        by_edge[e].append(r)
        k = BAND[g]
        lo, hi = k * BAND_W + 0.8, (k + 1) * BAND_W
        if e == "W":
            seg = ((-lo, -hi), (y, y))
        elif e == "E":
            seg = ((D + lo, D + hi), (y, y))
        elif e == "S":
            seg = ((x, x), (-lo, -hi))
        else:
            seg = ((x, x), (D + lo, D + hi))
        ax.plot(*seg, color=GROUP_COLOR[g], lw=0.9, solid_capstyle="butt", zorder=4)

    outer = 4 * BAND_W  # 24 um

    # leader labels for single-bit control/status pins and temp_c[7:0]
    def fan(edge, items, x_text, ha):
        items = sorted(items, key=lambda t: t[1])
        n = len(items)
        mid = sum(t[1] for t in items) / n
        step = 9.5
        ys = [mid + (i - (n - 1) / 2) * step for i in range(n)]
        for (name, y), yt in zip(items, ys):
            xe = -outer if edge == "W" else D + outer
            ax.plot([xe, (xe + x_text) / 2, x_text], [y, yt, yt], color=INK2, lw=0.4, zorder=2)
            ax.text(x_text + (-1.5 if ha == "right" else 1.5), yt, name, ha=ha, va="center",
                    fontsize=6.6, color=INK)

    singles = {r["pin"]: float(r["y_um"]) for r in sig
               if group_of(r["spec_port"]) == "ctrl" and r["spec_port"] != "temp_c"}
    w_names = {p["pin"] for p in by_edge["W"]}
    w_ctrl = [(n, y) for n, y in singles.items() if n in w_names]
    w_far = [t for t in w_ctrl if t[0] in ("clk", "rst_n")]
    w_near = [t for t in w_ctrl if t[0] not in ("clk", "rst_n")]
    fan("W", w_near, -outer - 34, "right")
    fan("W", w_far, -outer - 34, "right")
    e_names = {p["pin"] for p in by_edge["E"]}
    e_ctrl = [(n, y) for n, y in singles.items() if n in e_names]
    tc = [float(r["y_um"]) for r in sig if r["spec_port"] == "temp_c"]
    e_ctrl.append(("temp_c[7:0] (y %.2f-%.2f)" % (min(tc), max(tc)), sum(tc) / len(tc)))
    fan("E", e_ctrl, D + outer + 34, "left")
    # in_first is the only control pin on S
    for r in by_edge["S"]:
        if r["spec_port"] == "in_first":
            xf = float(r["x_um"])
            ax.annotate("in_first", xy=(xf, -outer), xytext=(xf + 22, -outer - 16),
                        fontsize=6.6, color=INK, ha="left", va="center",
                        arrowprops=dict(arrowstyle="-", color=INK2, lw=0.4))

    # per-edge summaries (counts by group, layer, coordinate)
    def summary(e):
        c = collections.Counter(group_of(r["spec_port"]) for r in by_edge[e])
        lay = sorted({r["layer"] for r in by_edge[e]})
        parts = ["%s %d" % (g, c[g]) for g in ("in_a", "in_b", "out_data", "ctrl") if c[g]]
        return "%s edge: %d pins on %s\n%s" % (e, len(by_edge[e]), "/".join(lay), ", ".join(parts))

    ax.text(D / 2, D + outer + 10, summary("N") + "   (y = 346.052 um)", ha="center", va="bottom",
            fontsize=7.2, color=INK)
    ax.text(D / 2, -outer - 26, summary("S") + "   (y = 0.242 um)", ha="center", va="top",
            fontsize=7.2, color=INK)
    ax.text(-outer - 4, 20, summary("W") + "\n(x = 0.400 um)", ha="right",
            va="bottom", fontsize=7.2, color=INK)
    ax.text(D + outer + 4, 20, summary("E") + "\n(x = 345.895 um)", ha="left", va="bottom",
            fontsize=7.2, color=INK)

    box = dict(boxstyle="square,pad=0.25", fc="#ffffff", ec="none")
    ax.text(D / 2, D / 2 + 7, "core (no signal pins inside the die)", ha="center", va="center",
            fontsize=7.5, color=INK2, bbox=box)
    ax.text(D / 2, D / 2 - 6,
            "light bands: VDD (%d) and VSS (%d) met5 strap pins, 1.6 um, x %.2f-%.2f um"
            % (len(straps["VDD"]), len(straps["VSS"]), straps["VDD"][0][0], straps["VDD"][0][2]),
            ha="center", va="center", fontsize=6.6, color=INK2, bbox=box)

    ax.set_xlim(-150, D + 150)
    ax.set_ylim(-80, D + 62)
    ax.set_xticks(range(0, 351, 50))
    ax.set_yticks(range(0, 351, 50))
    ax.tick_params(labelsize=7, colors=INK2, length=2)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_xlabel("x (um)", fontsize=8, color=INK2)
    ax.set_ylabel("y (um)", fontsize=8, color=INK2)
    ax.set_title("orbit_demo sep layout: 215 signal pins + VDD/VSS on the 346.295 x 346.295 um die\n"
                 "source: pinout.csv and 6_final.def.gz (ORFS sky130hd, place_pins output)",
                 fontsize=9, color=INK)

    handles = [Line2D([0], [0], color=GROUP_COLOR[g], lw=2.2,
                      label="band %d: %s" % (BAND[g] + 1, GROUP_LABEL[g]))
               for g in ("in_a", "in_b", "out_data", "ctrl")]
    handles += [Rectangle((0, 0), 1, 1, fc=VDD_C, ec="none", label="VDD met5 strap pin (USE POWER)"),
                Rectangle((0, 0), 1, 1, fc=VSS_C, ec="none", label="VSS met5 strap pin (USE GROUND)"),
                Line2D([0], [0], color=MUTED, lw=0.7, ls=(0, (4, 3)), label="core row extent"),
                Line2D([0], [0], color=INK, lw=1.2, label="die boundary (DIEAREA)")]
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.06), ncol=2,
              fontsize=7, frameon=False, handlelength=2.2, columnspacing=1.6)
    fig.text(0.5, 0.012,
             "Tick position along each edge = DEF pin origin. Offset band 1 (nearest the edge) to 4 encodes "
             "the port group only; band offset and tick length are not physical (bands drawn 8 um wide).",
             ha="center", fontsize=6.5, color=INK2)
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    fig.savefig(OUT, facecolor="#ffffff", bbox_inches="tight", pad_inches=0.15)
    print(OUT)


if __name__ == "__main__":
    main()
