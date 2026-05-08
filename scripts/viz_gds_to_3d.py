#!/usr/bin/env python3
"""Routed GDS/DEF -> compact 3D layout data for the ORBIT-AI die viewer.

Reads the final GDS of an OpenROAD-flow-scripts run (sky130hd), the matching
DEF and the platform LEFs, and writes

  <out-dir>/layout.bin    per-layer rectangles, quantized (format in viz/README.md)
  <out-dir>/layout.json   metadata: die/core boxes, layer stack (z, thickness,
                          source, colour, counts, byte offsets), design stats,
                          redundant-storage groups and their placement numbers
  --glb FILE              binary glTF of the metal stack + die slab
  --redundancy-report F   Markdown summary of copy separation

Design-agnostic: redundancy grouping looks for the orbit_demo instance names
(g_lane[i].u_lane.u_acc_a / u_res_b / u_thermal.u_copyK ...) and simply finds
no groups on other designs.

Needs the klayout and numpy Python modules (see viz/requirements.txt).
"""

import argparse
import collections
import datetime as _dt
import json
import math
import os
import re
import statistics
import struct
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import viz_parts  # noqa: E402  (scripts/viz_parts.py: part attribution)

try:
    import klayout.db as kdb
except ImportError:  # pragma: no cover
    sys.exit("viz_gds_to_3d.py: the 'klayout' Python module is missing "
             "(pip install -r viz/requirements.txt)")

MAGIC = b"ORBITVZ2"
HEADER_BYTES = 16

# ---------------------------------------------------------------------------
# Layer stack.
#
# z (bottom of layer) comes from the open_pdks Magic technology file for
# sky130A (sky130.tech, section "extract", `height <layer> <z> <thickness>`,
# standard non-ReRAM stack), because the ORFS sky130hd tech LEF carries no
# HEIGHT statement. Routing-layer thickness comes from the platform tech LEF
# (THICKNESS); cut layers span from the top of the metal below to the bottom of
# the metal above, so the drawn stack has no gaps. Front-end values (nwell,
# diff, tap, poly, licon1) are Magic's 3D-rendering values and are approximate
# (no oxide, silicide or well depth modelling).
# ---------------------------------------------------------------------------
MAGIC_TECH_SRC = ("open_pdks sky130/magic/sky130.tech, extract section "
                  "'height' statements (standard stack, not RERAM)")
MAGIC_HEIGHTS = {  # name: (z_bottom_um, thickness_um) from the Magic tech file
    "nwell":  (0.0,    0.2062),
    "diff":   (0.2062, 0.12),
    "tap":    (0.2062, 0.12),
    "poly":   (0.3262, 0.18),
    "licon1": (0.3262, 0.61),
    "li1":    (0.9361, 0.10),
    "mcon":   (1.0361, 0.34),
    "met1":   (1.3761, 0.36),
    "via":    (1.7361, 0.27),
    "met2":   (2.0061, 0.36),
    "via2":   (2.3661, 0.42),
    "met3":   (2.7861, 0.845),
    "via3":   (3.6311, 0.39),
    "met4":   (4.0211, 0.845),
    "via4":   (4.8661, 0.505),
    "met5":   (5.3711, 1.26),
}

# name, GDS layer/datatype (checked against the platform .lyt layer map),
# kind, colour (loosely after the KLayout/Magic sky130 conventions),
# lower/upper metal for cuts.
LAYERS = [
    ("nwell",  (64, 20), "well",  "#7c9f6e", None, None),
    ("diff",   (65, 20), "fe",    "#43a45c", None, None),
    ("tap",    (65, 44), "fe",    "#98c254", None, None),
    ("poly",   (66, 20), "fe",    "#cf4a3c", None, None),
    ("licon1", (66, 44), "cut",   "#565a78", None, "li1"),
    ("li1",    (67, 20), "metal", "#9a82d0", None, None),
    ("mcon",   (67, 44), "cut",   "#5b4b93", "li1", "met1"),
    ("met1",   (68, 20), "metal", "#3f7fd6", None, None),
    ("via",    (68, 44), "cut",   "#274d8c", "met1", "met2"),
    ("met2",   (69, 20), "metal", "#d160a3", None, None),
    ("via2",   (69, 44), "cut",   "#8c3a6c", "met2", "met3"),
    ("met3",   (70, 20), "metal", "#34a39b", None, None),
    ("via3",   (70, 44), "cut",   "#1e6b66", "met3", "met4"),
    ("met4",   (71, 20), "metal", "#d4ae37", None, None),
    ("via4",   (71, 44), "cut",   "#8a7026", "met4", "met5"),
    ("met5",   (72, 20), "metal", "#c8783e", None, None),
]
FE_LAYERS = ("nwell", "diff", "tap", "poly", "licon1", "li1", "mcon")
GLB_ORDER = ["met5", "via4", "met4", "via3", "met3", "via2", "met2", "via",
             "met1", "mcon", "li1", "poly", "diff", "tap", "licon1"]
GLB_REQUIRED = {"met1", "via", "met2", "via2", "met3", "via3", "met4", "via4", "met5"}

NAMES_FROM_LYT = {  # purpose-qualified names in the .lyt layer_map
    "nwell": "nwell.drawing", "diff": "diff.drawing", "tap": "tap.drawing",
    "poly": "poly.drawing", "licon1": "licon1.drawing", "li1": "li1.drawing",
    "mcon": "mcon.drawing", "met1": "met1.drawing", "via": "via.drawing",
    "met2": "met2.drawing", "via2": "via2.drawing", "met3": "met3.drawing",
    "via3": "via3.drawing", "met4": "met4.drawing", "via4": "via4.drawing",
    "met5": "met5.drawing",
}


def log(*a):
    print("[viz]", *a, flush=True)


# ---------------------------------------------------------------------------
# Platform files
# ---------------------------------------------------------------------------
def read_tech_lef(path):
    """Return {layer: {'type', 'thickness', 'height'}} from a tech LEF."""
    out = {}
    cur = None
    with open(path) as f:
        for line in f:
            s = line.split("#", 1)[0].strip()
            if not s:
                continue
            m = re.match(r"LAYER\s+(\S+)\s*$", s)
            if m and cur is None:
                cur = m.group(1)
                out[cur] = {}
                continue
            if cur is not None:
                if re.match(r"END\s+" + re.escape(cur) + r"\s*$", s):
                    cur = None
                    continue
                m = re.match(r"(TYPE|THICKNESS|HEIGHT)\s+(\S+)\s*;", s)
                if m:
                    k, v = m.group(1).lower(), m.group(2)
                    out[cur][k] = v if k == "type" else float(v)
    return out


def read_lyt_layer_map(path):
    """Return {purpose_name: (layer, datatype)} from a KLayout .lyt file."""
    if not path or not os.path.exists(path):
        return {}
    txt = open(path).read()
    res = {}
    for body in re.findall(r"layer_map\((.*?)\)</layer-map>", txt, re.S):
        for name, l, d in re.findall(r"'([^':]+?)\s*:\s*(\d+)/(\d+)'", body):
            res.setdefault(name.strip(), (int(l), int(d)))
    return res


def read_cell_lef(path):
    """Return {macro: {'w', 'h', 'pins': {name: direction}}}."""
    macros = {}
    cur = None
    pin = None
    with open(path) as f:
        for line in f:
            s = line.strip()
            if cur is None:
                m = re.match(r"MACRO\s+(\S+)", s)
                if m:
                    cur = m.group(1)
                    macros[cur] = {"w": 0.0, "h": 0.0, "pins": {}}
                continue
            if s == "END " + cur:
                cur = None
                pin = None
                continue
            m = re.match(r"SIZE\s+([\d.]+)\s+BY\s+([\d.]+)", s)
            if m:
                macros[cur]["w"] = float(m.group(1))
                macros[cur]["h"] = float(m.group(2))
                continue
            m = re.match(r"PIN\s+(\S+)", s)
            if m:
                pin = m.group(1)
                macros[cur]["pins"][pin] = "?"
                continue
            m = re.match(r"DIRECTION\s+(\S+)", s)
            if m and pin:
                macros[cur]["pins"][pin] = m.group(1)
                continue
            if pin and s == "END " + pin:
                pin = None
    return macros


# ---------------------------------------------------------------------------
# DEF
# ---------------------------------------------------------------------------
def read_def(path, want_nets_for=None):
    """Minimal DEF reader: units, die area, rows, components, and (optionally)
    the net connected to given (instance, pin) pairs."""
    txt = open(path).read()
    units = 1000.0
    m = re.search(r"UNITS\s+DISTANCE\s+MICRONS\s+(\d+)", txt)
    if m:
        units = float(m.group(1))
    design = None
    m = re.search(r"^\s*DESIGN\s+(\S+)\s*;", txt, re.M)
    if m:
        design = m.group(1)
    m = re.search(r"DIEAREA((?:\s*\(\s*-?\d+\s+-?\d+\s*\))+)\s*;", txt)
    pts = [(int(a), int(b)) for a, b in re.findall(r"\(\s*(-?\d+)\s+(-?\d+)\s*\)", m.group(1))]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    die = (min(xs) / units, min(ys) / units, max(xs) / units, max(ys) / units)

    rows = []
    for rm in re.finditer(r"^\s*ROW\s+\S+\s+(\S+)\s+(-?\d+)\s+(-?\d+)\s+\S+\s+DO\s+(\d+)\s+BY\s+(\d+)\s+STEP\s+(\d+)\s+(\d+)",
                          txt, re.M):
        rows.append((rm.group(1), int(rm.group(2)), int(rm.group(3)), int(rm.group(4)),
                     int(rm.group(5)), int(rm.group(6)), int(rm.group(7))))

    comps = {}
    cm = re.search(r"^COMPONENTS\s+\d+\s*;(.*?)^END COMPONENTS", txt, re.S | re.M)
    if cm:
        for stmt in cm.group(1).split(";"):
            s = stmt.strip()
            if not s.startswith("-"):
                continue
            tok = s.split()
            name, master = tok[1], tok[2]
            pm = re.search(r"\+\s*(PLACED|FIXED|COVER)\s*\(\s*(-?\d+)\s+(-?\d+)\s*\)\s*(\S+)", s)
            if not pm:
                continue
            comps[name] = (master, int(pm.group(2)) / units, int(pm.group(3)) / units, pm.group(4))

    q_nets = {}
    if want_nets_for:
        nm = re.search(r"^NETS\s+\d+\s*;(.*?)^END NETS", txt, re.S | re.M)
        if nm:
            pair_re = re.compile(r"\(\s*(\S+)\s+(\S+)\s*\)")
            for stmt in nm.group(1).split(";"):
                s = stmt.strip()
                if not s.startswith("-"):
                    continue
                head = s.split("+", 1)[0]
                tok = head.split()
                net = tok[1]
                for inst, pin in pair_re.findall(head):
                    if (inst, pin) in want_nets_for:
                        q_nets[(inst, pin)] = net
    return {"units": units, "design": design, "die": die, "rows": rows,
            "components": comps, "q_nets": q_nets}


def core_from_rows(rows, units, macros):
    """Bounding box of all placement rows (um), used as the core box."""
    if not rows:
        return None
    x0 = y0 = float("inf")
    x1 = y1 = float("-inf")
    site_h = 2.72
    for site, x, y, nx, ny, sx, sy in rows:
        w = (nx - 1) * sx + (0.46 * units if site.startswith("unithd") else sx)
        h = (ny - 1) * sy + site_h * units
        x0 = min(x0, x)
        y0 = min(y0, y)
        x1 = max(x1, x + w)
        y1 = max(y1, y + h)
    return (x0 / units, y0 / units, x1 / units, y1 / units)


# ---------------------------------------------------------------------------
# Redundant storage groups (orbit_demo naming; see docs/SPEC.md section 7)
# ---------------------------------------------------------------------------
FLOP_MASTER_RE = re.compile(r"__(?:s|e|se)?df")


def norm_name(n):
    return n.replace("\\", "").replace("/", ".")


def classify_flop(name):
    """Return (group_id, group_label, kind, copy, width) or None."""
    n = norm_name(name)
    m = re.search(r"g_lane\[(\d+)\]\.u_lane\.u_(acc|res)_([ab])(?:\.|$)", n) or \
        re.search(r"g_lane_(\d+)_\.u_lane\.u_(acc|res)_([ab])(?:\.|$)", n)
    if m:
        lane, what, cp = m.group(1), m.group(2), m.group(3).upper()
        label = ("Accumulator" if what == "acc" else "Result") + " lane " + lane
        return (f"{what}_lane{lane}", label, "pair", cp, 32)
    m = re.search(r"u_thermal\.u_copy(\d)(?:\.|$)", n)
    if m:
        return ("thermal", "Thermal state", "triple", m.group(1), 2)
    if re.search(r"u_thermal\.phase", n):
        return ("phase", "Throttle phase", "single", None, 1)
    if re.search(r"(^|\.)out_valid_q", n):
        return ("out_valid_q", "Output valid", "single", None, 1)
    if re.search(r"(^|\.)fault_q", n):
        return ("fault_q", "Fault latch", "single", None, 1)
    return None


def bit_index(name, q_net, width):
    """Bit index of a storage flop: from the instance name after the copy
    token (e.g. ...u_acc_a.q[5]$_DFF...), else from the Q net name."""
    n = norm_name(name)
    m = re.search(r"u_(?:acc|res)_[ab]\.(.*)$", n) or re.search(r"u_copy\d\.(.*)$", n)
    tail = m.group(1) if m else ""
    idx = re.findall(r"\[(\d+)\]", tail)
    if idx:
        return int(idx[-1]) % width, "instance"
    if q_net:
        idx = re.findall(r"\[(\d+)\]", norm_name(q_net))
        if idx:
            return int(idx[-1]) % width, "q_net"
    if width == 1:
        return 0, "width1"
    return None, None


def box_gap(a, b):
    dx = max(0.0, max(a[0], b[0]) - min(a[2], b[2]))
    dy = max(0.0, max(a[1], b[1]) - min(a[3], b[3]))
    return math.hypot(dx, dy)


def center(b):
    return ((b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0)


def dist(p, q):
    return math.hypot(p[0] - q[0], p[1] - q[1])


def build_flop_records(defd, macros):
    comps = defd["components"]
    recs = []
    for name, (master, x, y, orient) in sorted(comps.items()):
        if not FLOP_MASTER_RE.search(master):
            continue
        mac = macros.get(master, {"w": 0.0, "h": 0.0, "pins": {}})
        w, h = mac["w"], mac["h"]
        if orient in ("E", "W", "FE", "FW"):
            w, h = h, w
        box = (x, y, x + w, y + h)
        cls = classify_flop(name)
        q_pin = "Q" if "Q" in mac["pins"] else next(
            (p for p, d in mac["pins"].items() if d == "OUTPUT"), None)
        q_net = defd["q_nets"].get((name, q_pin))
        rec = {"name": norm_name(name), "master": master, "box": box, "q_net": q_net}
        if cls:
            gid, label, kind, cp, width = cls
            b, bsrc = bit_index(name, q_net, width)
            rec.update(group=gid, label=label, kind=kind, copy=cp, bit=b, bit_src=bsrc)
        else:
            rec.update(group="other", label="Other flip-flop", kind="other", copy=None,
                       bit=None, bit_src=None)
        recs.append(rec)
    return recs


def group_stats(recs):
    groups = {}
    for r in recs:
        g = groups.setdefault(r["group"], {"id": r["group"], "label": r["label"],
                                           "kind": r["kind"], "copies": {}})
        g["copies"].setdefault(r["copy"] if r["copy"] is not None else "-", []).append(r)
    out = []
    for gid, g in groups.items():
        copies = g["copies"]
        entry = {"id": gid, "label": g["label"], "kind": g["kind"],
                 "copies": {k: len(v) for k, v in sorted(copies.items())},
                 "flops": sum(len(v) for v in copies.values())}
        if g["kind"] in ("pair", "triple") and len(copies) >= 2:
            keys = sorted(copies)
            cents = {}
            for k in keys:
                cs = [center(r["box"]) for r in copies[k]]
                cents[k] = (sum(c[0] for c in cs) / len(cs), sum(c[1] for c in cs) / len(cs))
                entry.setdefault("centroids_um", {})[k] = [round(cents[k][0], 3), round(cents[k][1], 3)]
            pairs = [(a, b) for i, a in enumerate(keys) for b in keys[i + 1:]]
            cdist = {f"{a}-{b}": round(dist(cents[a], cents[b]), 3) for a, b in pairs}
            entry["centroid_distance_um"] = cdist
            entry["centroid_distance_um_min"] = min(cdist.values())
            # corresponding bits
            same_c, same_g = [], []
            bits_ok = True
            for k in keys:
                bits = [r["bit"] for r in copies[k]]
                if None in bits or len(set(bits)) != len(bits):
                    bits_ok = False
            if bits_ok:
                by_bit = {k: {r["bit"]: r for r in copies[k]} for k in keys}
                for a, b in pairs:
                    for bit in sorted(set(by_bit[a]) & set(by_bit[b])):
                        ra, rb = by_bit[a][bit], by_bit[b][bit]
                        same_c.append(dist(center(ra["box"]), center(rb["box"])))
                        same_g.append(box_gap(ra["box"], rb["box"]))
                entry["bit_pairs"] = len(same_c)
                entry["bit_index_source"] = sorted({r["bit_src"] for k in keys for r in copies[k]})
            if same_c:
                entry["same_bit_center_um"] = {
                    "min": round(min(same_c), 3), "median": round(statistics.median(same_c), 3),
                    "max": round(max(same_c), 3)}
                entry["same_bit_gap_um"] = {
                    "min": round(min(same_g), 3), "median": round(statistics.median(same_g), 3)}
                entry["same_bit_pairs_abutting"] = sum(1 for g_ in same_g if g_ < 0.01)
                entry["same_bit_pairs_within_5um_gap"] = sum(1 for g_ in same_g if g_ < 5.0)
            else:
                entry["same_bit_center_um"] = None
                entry["same_bit_gap_um"] = None
            # closest cells of different copies, any bit
            anyg = []
            for a, b in pairs:
                for ra in copies[a]:
                    anyg.append(min(box_gap(ra["box"], rb["box"]) for rb in copies[b]))
            entry["any_bit_gap_um_min"] = round(min(anyg), 3) if anyg else None
            entry["any_bit_pairs_abutting"] = sum(1 for g_ in anyg if g_ < 0.01)
        out.append(entry)
    order = {"pair": 0, "triple": 1, "single": 2, "other": 3}
    out.sort(key=lambda e: (order.get(e["kind"], 9), e["id"]))
    return out


# ---------------------------------------------------------------------------
# Stats from reports
# ---------------------------------------------------------------------------
def parse_pd_summary(paths):
    """Tolerant parse of the pd area's summary (format owned by the pd area).
    `paths` is a comma-separated list; the first existing file is used."""
    path = next((p for p in (paths or "").split(",") if p and os.path.exists(p)), None)
    if not path:
        return {}
    res = {}
    txt = open(path).read()
    lines = txt.splitlines()

    def num(s):
        m = re.search(r"-?\d+(?:\.\d+)?(?:[eE]-?\d+)?", s.replace(",", ""))
        return float(m.group(0)) if m else None

    for ln in lines:
        low = ln.lower()
        cells = [c.strip() for c in ln.strip().strip("|").split("|")] if "|" in ln else [ln]
        val_txt = cells[1] if len(cells) > 1 else ln
        if "clock" not in res and re.search(r"clock\s*(period)?", low) and ("ns" in low or "mhz" in low):
            v = num(val_txt if len(cells) > 1 else ln.split(":", 1)[-1])
            if v is not None:
                if "mhz" in val_txt.lower() and "ns" not in val_txt.lower():
                    res["clock_mhz"] = v
                    res["clock_period_ns"] = round(1000.0 / v, 4) if v else None
                else:
                    res["clock_period_ns"] = v
                res["clock"] = val_txt.strip() if len(cells) > 1 else ln.split(":", 1)[-1].strip()
        if "wns_ns" not in res and "hold" not in low and re.search(r"\bwns\b|worst negative slack|setup slack", low):
            v = num(val_txt if len(cells) > 1 else ln.split(":", 1)[-1])
            if v is not None:
                res["wns_ns"] = v
        if "area_um2" not in res and "synth" not in low and re.search(r"(design|cell|instance|std.?cell)\s*area", low):
            v = num(val_txt if len(cells) > 1 else ln.split(":", 1)[-1])
            if v is not None:
                res["area_um2"] = v
        if "cell_count" not in res and "synth" not in low and re.search(r"(cell|instance)\s*count|#\s*cells|number of cells", low):
            v = num(val_txt if len(cells) > 1 else ln.split(":", 1)[-1])
            if v is not None:
                res["cell_count"] = int(v)
    if res:
        res["source"] = os.path.relpath(path)
    return res


def orfs_metrics(gds_path):
    """Metrics from the ORFS run that produced the GDS (read-only)."""
    res = {}
    d = os.path.dirname(os.path.abspath(gds_path))
    parts = d.split(os.sep)
    try:
        i = len(parts) - 1 - parts[::-1].index("results")
    except ValueError:
        return res
    work = os.sep.join(parts[:i])
    rest = parts[i + 1:]
    rep = os.path.join(work, "logs", *rest, "6_report.json")
    if os.path.exists(rep):
        try:
            j = json.load(open(rep))
        except Exception:
            j = {}
        m = {}
        if "finish__timing__setup__ws" in j:
            m["wns_ns"] = round(float(j["finish__timing__setup__ws"]), 4)
        if "finish__design__instance__area__stdcell" in j:
            m["area_um2"] = round(float(j["finish__design__instance__area__stdcell"]), 2)
        if "finish__design__instance__count__stdcell" in j:
            # ORFS counts tap cells as standard cells (fill cells are not);
            # report logic cells, i.e. without taps, like the pd summary does.
            taps = int(j.get("finish__design__instance__count__class:tap_cell", 0) or 0)
            m["cell_count"] = int(j["finish__design__instance__count__stdcell"]) - taps
            m["tap_cells"] = taps
        if "finish__design__instance__utilization" in j:
            m["utilization"] = round(float(j["finish__design__instance__utilization"]), 4)
        if "finish__design__die__area" in j:
            m["die_area_um2"] = round(float(j["finish__design__die__area"]), 2)
        if m:
            m["source"] = os.path.relpath(rep)
            res.update(m)
    sdc = os.path.join(d, "6_final.sdc")
    if os.path.exists(sdc):
        mm = re.search(r"create_clock\s+-name\s+(\S+)\s+-period\s+([\d.]+)", open(sdc).read())
        if mm:
            res["clock_period_ns"] = float(mm.group(2))
            res["clock_name"] = mm.group(1)
            res["clock_source"] = os.path.relpath(sdc)
    return res


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------
def region_to_boxes(region, dbu):
    """Merged-vs-raw decomposition into rectangles, whichever is smaller.
    Returns (int64 array [n,4] in DBU, method, nonrect_count)."""
    cands = []
    raw = region.dup()
    raw.merged_semantics = False
    boxes_raw = []
    nonbox = kdb.Region()
    nonbox.merged_semantics = False
    for p in raw.each():
        if p.is_box():
            b = p.bbox()
            boxes_raw.append((b.left, b.bottom, b.right, b.top))
        else:
            nonbox.insert(p)
    if nonbox.count():
        h = nonbox.decompose_trapezoids_to_region(kdb.Polygon.TD_htrapezoids)
        v = nonbox.decompose_trapezoids_to_region(kdb.Polygon.TD_vtrapezoids)
        extra = h if h.count() <= v.count() else v
    else:
        extra = kdb.Region()
    cands.append(("raw", boxes_raw, extra))
    merged = region.merged()
    for mode, name in ((kdb.Polygon.TD_htrapezoids, "merged-h"), (kdb.Polygon.TD_vtrapezoids, "merged-v")):
        cands.append((name, [], merged.decompose_trapezoids_to_region(mode)))
    best = min(cands, key=lambda c: len(c[1]) + c[2].count())
    name, boxes, extra = best
    nonrect = 0
    out = list(boxes)
    for p in extra.each():
        b = p.bbox()
        if not p.is_box():
            nonrect += 1  # trapezoid: kept as its bounding box
        out.append((b.left, b.bottom, b.right, b.top))
    arr = np.array(out, dtype=np.int64).reshape(-1, 4)
    return arr, name, nonrect


def srgb_to_linear(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


# ---------------------------------------------------------------------------
# glTF 2.0 binary writer (flat normals computed by viewers)
# ---------------------------------------------------------------------------
BOX_TRIS = np.array([
    0, 2, 1, 0, 3, 2,        # bottom (z0), facing -z
    4, 5, 6, 4, 6, 7,        # top (z1), facing +z
    0, 1, 5, 0, 5, 4,        # y0 side
    1, 2, 6, 1, 6, 5,        # x1 side
    2, 3, 7, 2, 7, 6,        # y1 side
    3, 0, 4, 3, 4, 7,        # x0 side
], dtype=np.uint16)


def box_corners(rects, z0, z1):
    """rects [n,4] (x0,y0,x1,y1) + per-box z0/z1 ([n] arrays or scalars) ->
    corners [n,8,3] in glTF Y-up axes: (x, z, -y)."""
    n = rects.shape[0]
    x0, y0, x1, y1 = (rects[:, i] for i in range(4))
    zb = np.broadcast_to(np.asarray(z0, dtype=rects.dtype), (n,))
    zt = np.broadcast_to(np.asarray(z1, dtype=rects.dtype), (n,))
    corners = [(x0, y0, zb), (x1, y0, zb), (x1, y1, zb), (x0, y1, zb),
               (x0, y0, zt), (x1, y0, zt), (x1, y1, zt), (x0, y1, zt)]
    pos = np.empty((n, 8, 3), dtype=rects.dtype)
    for k, (x, y, z) in enumerate(corners):
        pos[:, k, 0] = x
        pos[:, k, 1] = z
        pos[:, k, 2] = -y
    return pos


def glb_node(name, children=None, mesh=None, extras=None):
    """Scene-tree node for write_glb. mesh = dict(material, rgba, metallic,
    rects [n,4] um (die-centre origin), z0, z1 (scalars or [n] um))."""
    return {"name": name, "children": children or [], "mesh": mesh, "extras": extras}


def write_glb(path, root, asset_extras, quantize_um=None, z_scale=1.0):
    """Write a binary glTF 2.0 file from a glb_node tree.

    Every rectangle becomes a closed box (8 corners, 12 triangles, no
    normals). quantize_um=None: core glTF, float32 positions and one uint32
    index buffer per mesh (the input for Draco compression); a step in um:
    KHR_mesh_quantization (int16 positions, 8-byte stride, node scale = step)
    with primitives of <= 8191 boxes sharing one uint16 index buffer.
    Returns (bytes written, list of node names, box count)."""
    bin_chunks = []
    offset = 0
    buffer_views, accessors, gl_meshes, materials, nodes = [], [], [], [], []
    mat_index = {}
    names = []
    total_boxes = 0

    def add_view(data, target, stride=None):
        nonlocal offset
        pad = (-offset) % 4
        if pad:
            bin_chunks.append(b"\x00" * pad)
            offset += pad
        bv = {"buffer": 0, "byteOffset": offset, "byteLength": len(data)}
        if target:
            bv["target"] = target
        if stride:
            bv["byteStride"] = stride
        buffer_views.append(bv)
        bin_chunks.append(data)
        offset += len(data)
        return len(buffer_views) - 1

    max_boxes = 65536 // 8 - 1
    idx16_view = None
    idx_acc = {}

    def index16(nb):
        nonlocal idx16_view
        if idx16_view is None:
            idx_all = (BOX_TRIS[None, :].astype(np.uint32) +
                       (np.arange(max_boxes, dtype=np.uint32) * 8)[:, None]).astype(np.uint16).reshape(-1)
            idx16_view = add_view(idx_all.tobytes(), 34963)
        if nb not in idx_acc:
            accessors.append({"bufferView": idx16_view, "componentType": 5123,
                              "count": int(nb * 36), "type": "SCALAR"})
            idx_acc[nb] = len(accessors) - 1
        return idx_acc[nb]

    def material(m):
        key = m["material"]
        if key not in mat_index:
            rgba = m["rgba"]
            mat = {"name": key, "pbrMetallicRoughness": {
                "baseColorFactor": [round(v, 5) for v in rgba],
                "metallicFactor": m.get("metallic", 0.0), "roughnessFactor": 0.55}}
            if rgba[3] < 1.0:
                mat["alphaMode"] = "BLEND"
            if m.get("double_sided"):
                mat["doubleSided"] = True
            materials.append(mat)
            mat_index[key] = len(materials) - 1
        return mat_index[key]

    def add_mesh(name, m):
        nonlocal total_boxes
        rects = np.asarray(m["rects"], dtype=np.float64).reshape(-1, 4)
        n = rects.shape[0]
        z0 = np.broadcast_to(np.asarray(m["z0"], dtype=np.float64), (n,)) * z_scale
        z1 = np.broadcast_to(np.asarray(m["z1"], dtype=np.float64), (n,)) * z_scale
        if quantize_um and n:
            qa = np.rint(rects / quantize_um)
            keep = (qa[:, 2] > qa[:, 0]) & (qa[:, 3] > qa[:, 1])
            rects, z0, z1 = rects[keep], z0[keep], z1[keep]
            n = rects.shape[0]
        if n == 0:
            return None
        total_boxes += n
        mi = material(m)
        prims = []
        if quantize_um:
            for s0 in range(0, n, max_boxes):
                sl = slice(s0, s0 + max_boxes)
                q = np.rint(rects[sl] / quantize_um).astype(np.int32)
                pos = box_corners(q, np.rint(z0[sl] / quantize_um).astype(np.int32),
                                  np.rint(z1[sl] / quantize_um).astype(np.int32)).reshape(-1, 3)
                if np.abs(pos).max() > 32767:
                    raise SystemExit("GLB quantization overflow: use a coarser --glb-quant-um")
                packed = np.zeros((pos.shape[0], 4), dtype="<i2")
                packed[:, :3] = pos
                pv = add_view(packed.tobytes(), 34962, stride=8)
                accessors.append({"bufferView": pv, "componentType": 5122, "count": int(pos.shape[0]),
                                  "type": "VEC3", "min": [int(v) for v in pos.min(axis=0)],
                                  "max": [int(v) for v in pos.max(axis=0)]})
                prims.append({"attributes": {"POSITION": len(accessors) - 1},
                              "indices": index16(q.shape[0]), "material": mi, "mode": 4})
        else:
            pos = box_corners(rects.astype(np.float32), z0.astype(np.float32), z1.astype(np.float32)).reshape(-1, 3)
            pv = add_view(pos.astype("<f4").tobytes(), 34962)
            accessors.append({"bufferView": pv, "componentType": 5126, "count": int(pos.shape[0]),
                              "type": "VEC3", "min": [float(v) for v in pos.min(axis=0)],
                              "max": [float(v) for v in pos.max(axis=0)]})
            pa = len(accessors) - 1
            idx = (BOX_TRIS[None, :].astype(np.uint32) + (np.arange(n, dtype=np.uint32) * 8)[:, None]).reshape(-1)
            iv = add_view(idx.astype("<u4").tobytes(), 34963)
            accessors.append({"bufferView": iv, "componentType": 5125, "count": int(idx.shape[0]), "type": "SCALAR"})
            prims.append({"attributes": {"POSITION": pa}, "indices": len(accessors) - 1, "material": mi, "mode": 4})
        gl_meshes.append({"name": name, "primitives": prims})
        return len(gl_meshes) - 1

    def visit(nd):
        entry = {"name": nd["name"]}
        names.append(nd["name"])
        if nd.get("extras"):
            entry["extras"] = nd["extras"]
        idx = len(nodes)
        nodes.append(entry)
        if nd.get("mesh") is not None:
            mi = add_mesh(nd["name"], nd["mesh"])
            if mi is not None:
                entry["mesh"] = mi
                if quantize_um:
                    entry["scale"] = [quantize_um, quantize_um, quantize_um]
        kids = [visit(c) for c in nd.get("children", [])]
        if kids:
            entry["children"] = kids
        return idx

    if len({n for n in _walk_names(root)}) != len(list(_walk_names(root))):
        raise SystemExit("GLB node names must be unique")
    visit(root)
    gltf = {
        "asset": {"version": "2.0", "generator": "ORBIT-AI scripts/viz_gds_to_3d.py", "extras": asset_extras},
        "scene": 0,
        "scenes": [{"name": root["name"], "nodes": [0]}],
        "nodes": nodes, "meshes": gl_meshes, "materials": materials,
        "accessors": accessors, "bufferViews": buffer_views,
        "buffers": [{"byteLength": offset}],
    }
    if quantize_um:
        gltf["extensionsUsed"] = ["KHR_mesh_quantization"]
        gltf["extensionsRequired"] = ["KHR_mesh_quantization"]
    js = json.dumps(gltf, separators=(",", ":")).encode()
    js += b" " * ((-len(js)) % 4)
    binary = b"".join(bin_chunks)
    binary += b"\x00" * ((-len(binary)) % 4)
    total = 12 + 8 + len(js) + 8 + len(binary)
    with open(path, "wb") as f:
        f.write(struct.pack("<4sII", b"glTF", 2, total))
        f.write(struct.pack("<I4s", len(js), b"JSON"))
        f.write(js)
        f.write(struct.pack("<I4s", len(binary), b"BIN\x00"))
        f.write(binary)
    return total, names, total_boxes


def _walk_names(nd):
    yield nd["name"]
    for c in nd.get("children", []):
        yield from _walk_names(c)


def glb_box_bytes(n, quantized):
    return n * (8 * (8 if quantized else 12))



# ---------------------------------------------------------------------------
# Cells / parts / pins / power grid blocks
# ---------------------------------------------------------------------------
PIN_BUSES = [  # (bus id, label, family)
    ("in_a", "in_a[31:0]", "data in"), ("in_b", "in_b[31:0]", "data in"),
    ("out_data", "out_data[127:0]", "data out"), ("temp_c", "temp_c[7:0]", "thermal"),
]
PIN_FAMILY = {"clk": ("clk", "clock"), "rst_n": ("rst_n", "reset"),
              "in_valid": ("handshake", "handshake"), "in_ready": ("handshake", "handshake"),
              "in_first": ("handshake", "handshake"), "in_last": ("handshake", "handshake"),
              "out_valid": ("handshake", "handshake"), "out_ready": ("handshake", "handshake"),
              "temp_valid": ("temp_c", "thermal"), "therm_state": ("thermal status", "thermal"),
              "therm_repair": ("thermal status", "thermal"), "shutdown_req": ("thermal status", "thermal"),
              "clear_fault": ("fault", "fault"), "fault": ("fault", "fault"),
              "VDD": ("power", "power"), "VSS": ("power", "power")}


def pin_bus(name):
    base = re.sub(r"\[\d+\]$", "", name)
    for bid, _lab, fam in PIN_BUSES:
        if base == bid:
            return bid, fam
    return PIN_FAMILY.get(base, (base, "other"))


def build_cell_blocks(full, macros, part_of, serves, die, grid_um, off, regions_json_path):
    """Binary blocks for cells and the power grid (appended after the layer
    blocks, 4-byte aligned) plus their JSON descriptions."""
    ox, oy = die[0], die[1]
    die_w, die_h = die[2] - die[0], die[3] - die[1]
    catalogue = viz_parts.part_catalogue(range(4))
    pidx = {p["id"]: i for i, p in enumerate(catalogue)}
    comps = full["components"]
    masters = sorted({c[1] for c in comps})
    midx = {m: i for i, m in enumerate(masters)}
    if len(masters) > 255 or len(catalogue) > 254:
        raise SystemExit("too many masters/parts for uint8 indices")
    boxes = np.array([viz_parts.cell_box(c, macros) for c in comps], dtype=np.float64)
    rel = boxes.copy()
    rel[:, [0, 2]] -= ox
    rel[:, [1, 3]] -= oy
    q = np.clip(np.rint(rel / grid_um), 0, 65535).astype("<u2")
    m_arr = np.array([midx[c[1]] for c in comps], dtype=np.uint8)
    p_arr = np.array([pidx[part_of[c[0]]] for c in comps], dtype=np.uint8)
    s_arr = np.array([pidx[serves[c[0]]] if c[0] in serves else 255 for c in comps], dtype=np.uint8)
    flop = np.array([1 if viz_parts.FLOP_RE.search(c[1]) else 0 for c in comps], dtype=np.uint8)

    chunks = []

    def put(data):
        nonlocal off
        pad = (-off) % 4
        if pad:
            chunks.append(b"\x00" * pad)
            off += pad
        at = off
        chunks.append(data)
        off += len(data)
        return at

    cells = {"count": len(comps), "rect_offset": put(q.tobytes()), "master_offset": put(m_arr.tobytes()),
             "part_offset": put(p_arr.tobytes()), "serves_offset": put(s_arr.tobytes()),
             "rect": "uint16 x0,y0,x1,y1 per cell on the layer grid (DEF PLACED origin + LEF SIZE)",
             "master": "uint8 index into masters", "part": "uint8 index into parts",
             "serves": "uint8 part index the buffer's net cone belongs to (255 = none)",
             "names": [c[0] for c in comps], "orient": None,
             "masters": [m.replace("sky130_fd_sc_hd__", "") for m in masters]}
    info = {}
    for m in masters:
        d = viz_parts.describe_master(m, (macros.get(m) or {}).get("pins", {}))
        mac = macros.get(m) or {"w": 0, "h": 0}
        d.update(w=mac["w"], h=mac["h"])
        info[m.replace("sky130_fd_sc_hd__", "")] = d
    cells["master_info"] = info
    orients = sorted({c[4] for c in comps})
    cells["orient_values"] = orients
    cells["orient"] = "".join("0123456789"[orients.index(c[4])] for c in comps)

    # parts table
    boxes_by_part = collections.defaultdict(list)
    ffs_by_part = collections.Counter()
    for c, b in zip(comps, boxes):
        pid = part_of[c[0]]
        boxes_by_part[pid].append(tuple(float(v) for v in b))
        if viz_parts.FLOP_RE.search(c[1]):
            ffs_by_part[pid] += 1
    parts = viz_parts.part_stats(catalogue, boxes_by_part, ffs_by_part, die)
    for i, p in enumerate(parts):
        p["index"] = i
        p["color"] = viz_parts.KIND[p["kind"]][3]
        p["color_dark"] = viz_parts.KIND[p["kind"]][4]
        p["kind_name"] = viz_parts.KIND[p["kind"]][1]
    logic = [c for c in comps if part_of[c[0]] not in ("fill", "tap", "decap", "ant")]
    parts_meta = {
        "list": parts,
        "kinds": [{"id": k[0], "name": k[1], "category": k[2], "color": k[3], "color_dark": k[4]}
                  for k in viz_parts.KINDS],
        "counts": {"components": len(comps), "logic_cells": len(logic),
                   "unattributed": sum(1 for c in comps if part_of[c[0]] == "other"),
                   "by_source": dict(collections.Counter(p["source"] for p in parts for _ in range(p["cells"])))},
        "method": ("Step 1 instance names (kept orbit_keep_reg copies, CTS/resizer/physical-cell prefixes and masters); "
                   "step 2 netlist cones from the DEF NETS section for the anonymous synthesis cells: forward sinks "
                   "(flip-flop groups via D, output ports) and backward sources (flip-flop groups via Q, input ports) "
                   "through combinational cells, then first-match rules (adder A/B, multiplier, comparator, OR tree, "
                   "thermal voter/next-state, reset, control, other). See viz/README.md."),
        "total_cell_area_um2": round(float(sum((b[2] - b[0]) * (b[3] - b[1]) for b in boxes)), 2),
    }

    # pins
    pins = []
    for pn in full["pins"]:
        if "rect" not in pn:
            continue
        r = pn["rect"]
        x0, y0, x1, y1 = pn["x"] + r[0] - ox, pn["y"] + r[1] - oy, pn["x"] + r[2] - ox, pn["y"] + r[3] - oy
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        side = min((("W", cx), ("E", die_w - cx), ("S", cy), ("N", die_h - cy)), key=lambda t: t[1])[0]
        bus, fam = pin_bus(pn["name"])
        pins.append({"n": pn["name"], "dir": pn["dir"][0] if pn["dir"] else "?", "layer": pn.get("layer"),
                     "box": [round(v, 3) for v in (x0, y0, x1, y1)], "side": side, "bus": bus, "fam": fam})
    pin_groups = {}
    for pn in pins:
        key = pn["bus"] + "|" + pn["side"]
        g = pin_groups.setdefault(key, {"bus": pn["bus"], "side": pn["side"], "fam": pn["fam"], "pins": [],
                                        "layer": pn["layer"]})
        g["pins"].append(pn["n"])
    for g in pin_groups.values():
        mem = [p for p in pins if p["bus"] == g["bus"] and p["side"] == g["side"]]
        g["count"] = len(mem)
        g["center_um"] = [round(sum((p["box"][0] + p["box"][2]) / 2 for p in mem) / len(mem), 2),
                          round(sum((p["box"][1] + p["box"][3]) / 2 for p in mem) / len(mem), 2)]
        g["label"] = bus_label(g["bus"], g["pins"])
    sides = {}
    for pn in pins:
        sd = sides.setdefault(pn["side"], {"count": 0, "layers": collections.Counter(), "buses": collections.Counter()})
        sd["count"] += 1
        sd["layers"][pn["layer"]] += 1
        sd["buses"][pn["bus"]] += 1
    pins_meta = {"list": pins, "groups": sorted(pin_groups.values(), key=lambda g: (g["side"], g["center_um"])),
                 "sides": {k: {"count": v["count"], "layers": dict(v["layers"]), "buses": dict(v["buses"])}
                           for k, v in sides.items()},
                 "note": "DEF PINS: pin shapes at the die edge; VDD/VSS pins are the met5/met4 straps"}

    # power grid (SPECIALNETS wires with width)
    pw_layers = sorted({w[1] for w in full["power"]}, key=lambda n: (n != "li1", n))
    pr = np.array([[w[3] - ox, w[4] - oy, w[5] - ox, w[6] - oy] for w in full["power"]], dtype=np.float64).reshape(-1, 4)
    pq = np.clip(np.rint(pr / grid_um), 0, 65535).astype("<u2")
    pa = np.array([pw_layers.index(w[1]) + (16 if w[0] == "VSS" else 0) for w in full["power"]], dtype=np.uint8)
    shape_counts = collections.Counter((w[0], w[1], w[2]) for w in full["power"])
    power = {"count": int(pq.shape[0]), "rect_offset": put(pq.tobytes()), "attr_offset": put(pa.tobytes()),
             "layers": pw_layers, "attr": "uint8: layer index (low 4 bits) + 16 for VSS",
             "shapes": [{"net": k[0], "layer": k[1], "shape": k[2], "count": v} for k, v in sorted(shape_counts.items())],
             "source": "DEF SPECIALNETS wires (stripes, follow-pin rails, DRC fill); vias not listed"}

    # rows
    rows = []
    for r in full["rows"]:
        site_w = 0.46 if r["site"].startswith("unithd") else r["step"]
        rows.append([round(r["x"] - ox, 3), round(r["y"] - oy, 3),
                     round(r["x"] - ox + (r["n"] - 1) * r["step"] + site_w, 3), r["orient"]])
    rows_meta = {"list": rows, "height_um": 2.72, "site": full["rows"][0]["site"] if full["rows"] else None,
                 "count": len(rows)}

    # placement regions (DEF REGIONS / GROUPS), labelled from pdsep regions.json
    rj = {}
    if regions_json_path and os.path.exists(regions_json_path):
        try:
            rj = json.load(open(regions_json_path))
        except Exception:
            rj = {}
    by_name = {r["name"]: r for r in rj.get("regions", [])}
    nice = {"copyA": "Copy A region", "copyB": "Copy B region", "th0": "Thermal copy 0 region",
            "th1": "Thermal copy 1 region", "th2": "Thermal copy 2 region"}
    group_of_region = {g["region"]: (gn, g) for gn, g in full["groups"].items() if g.get("region")}
    regions = []
    for r in full["regions"]:
        info_r = by_name.get(r["name"], {})
        role = info_r.get("role") or re.sub(r"^pdsep_", "", r["name"])
        gn, g = group_of_region.get(r["name"], (None, {"members": []}))
        if gn is None:
            gm = [v for k, v in full["groups"].items() if k.endswith(role)]
            members = gm[0]["members"] if gm else []
        else:
            members = g["members"]
        regions.append({"name": r["name"], "type": r["type"], "role": role,
                        "label": nice.get(role, r["name"]), "long_label": info_r.get("label"),
                        "boxes": [[round(v - (ox if i % 2 == 0 else oy), 3) for i, v in enumerate(b)] for b in r["boxes"]],
                        "members": len(members),
                        "flip_flops": info_r.get("flip_flops")})
    regions_meta = {"list": regions, "source": ("DEF REGIONS (TYPE FENCE) + GROUPS of the routed run; labels from "
                                                 + (os.path.relpath(regions_json_path) if rj else "the region names")),
                    "separation": rj.get("separation"), "unconstrained_common_mode": rj.get("unconstrained_common_mode"),
                    "mechanism": rj.get("mechanism")}
    return cells, parts_meta, power, pins_meta, rows_meta, regions_meta, chunks, off


def bus_label(bus, names):
    """Compact label for the pins of one bus (or pin family) on one edge."""
    bases = collections.OrderedDict()
    for n in sorted(names, key=lambda t: (re.sub(r"\[\d+\]$", "", t), int((re.search(r"\[(\d+)\]$", t) or [0, 0])[1]))):
        m = re.search(r"\[(\d+)\]$", n)
        bases.setdefault(re.sub(r"\[\d+\]$", "", n), []).append(int(m.group(1)) if m else None)
    parts = []
    for base, idx in bases.items():
        idx = sorted(i for i in idx if i is not None)
        if not idx:
            parts.append(base)
            continue
        runs = []
        s0 = p = idx[0]
        for v in idx[1:]:
            if v == p + 1:
                p = v
                continue
            runs.append((s0, p))
            s0 = p = v
        runs.append((s0, p))
        txt = ",".join(f"{b}" if a == b else f"{b}:{a}" for a, b in reversed(runs))
        parts.append(f"{base}[{txt}]" if len(txt) <= 14 else f"{base} ×{len(idx)}")
    return ", ".join(parts)


# ---------------------------------------------------------------------------
# GLB scene tree
# ---------------------------------------------------------------------------
def gl_name(text):
    """glTF node name safe for Blender and three.js GLTFLoader (which strips
    [ ] . : / and turns spaces into _): [A-Za-z0-9_], at most 63 bytes."""
    t = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_")
    return t[:63]


def lin_rgba(hexcol, a=1.0):
    return tuple(srgb_to_linear(v) for v in hex_rgb(hexcol)) + (a,)


def build_glb_tree(c, layer_names, variant):
    die_w, die_h, ox, oy = c["die_w"], c["die_h"], c["ox"], c["oy"]
    cx, cy = die_w / 2.0, die_h / 2.0
    stack, top = c["stack"], c["stack_top"]
    root = glb_node(gl_name(c["design"] + "_sky130hd"), extras={
        "variant": variant, "units": "um", "up": "+Y", "layout_x": "+X", "layout_y": "-Z",
        "origin": "die centre, z = 0 at the substrate surface", "z_scale": c["z_scale"],
        "die_um": [die_w, die_h], "source_gds": c["source_gds"], "gds_sha256": c["gds_sha256"],
        "note": "Layer heights: tech LEF thickness + open_pdks Magic z (approximate below li1). Part tiles "
                "and the die slab are display aids below z = 0. Not radiation-qualified; sky130 open PDK."})
    root["children"].append(glb_node("Die_Substrate", mesh={
        "material": "die_substrate", "rgba": lin_rgba("#a9b4bb"), "rects": [[-cx, -cy, cx, cy]],
        "z0": -1.2, "z1": -0.2}, extras={"display_name": "Die substrate (display slab)"}))
    # layers
    lay = glb_node("Layers", extras={"display_name": "Drawn GDS layers", "order": "bottom to top"})
    for name, gds_ld, kind, color, below, above in LAYERS:
        if name not in layer_names:
            continue
        a = c["layer_rects"][name].astype(np.float64) * c["dbu"]
        a[:, [0, 2]] -= ox + cx
        a[:, [1, 3]] -= oy + cy
        st = stack[name]
        lay["children"].append(glb_node(gl_name(name), mesh={
            "material": "layer_" + name, "rgba": lin_rgba(color), "rects": a, "z0": st["z"], "z1": st["z"] + st["t"],
            "metallic": 0.3 if kind in ("metal", "cut") else 0.0},
            extras={"display_name": name, "gds": list(gds_ld), "z_um": round(st["z"], 4),
                    "thickness_um": round(st["t"], 4), "boxes": int(a.shape[0]), "approximate_z": st["approx"]}))
    root["children"].append(lay)
    # parts
    comps = c["full"]["components"]
    by_part = collections.defaultdict(list)
    for comp in comps:
        b = viz_parts.cell_box(comp, c["macros"])
        by_part[c["part_of"][comp[0]]].append((b[0] - ox - cx, b[1] - oy - cy, b[2] - ox - cx, b[3] - oy - cy))
    parts_node = glb_node("Parts", extras={"display_name": "Cells by part (footprint tiles below the devices)"})
    groups = collections.OrderedDict()
    for p in c["parts"]:
        if not p["cells"]:
            continue
        g = groups.get(p["group"])
        if g is None:
            g = glb_node(gl_name(p["group"]), extras={"display_name": p["group"]})
            groups[p["group"]] = g
            parts_node["children"].append(g)
        short = p["name"].split(" / ", 1)[-1] if p["group"].startswith(("Lane", "Thermal")) else p["name"]
        prefix = p["group"].replace(" ", "") if p["group"].startswith("Lane") else "Thermal" if p["group"].startswith("Thermal") else ""
        nm = gl_name((prefix + "_" if prefix else "") + short)
        rects = np.array(by_part[p["id"]], dtype=np.float64)
        an = p.get("anchor_um")
        g["children"].append(glb_node(nm, mesh={
            "material": "part_" + p["kind"], "rgba": lin_rgba(p["color"]), "rects": rects, "z0": -0.2, "z1": 0.0},
            extras={"display_name": p["name"], "part_id": p["id"], "kind": p["kind_name"], "category": p["category"],
                    "cells": p["cells"], "flip_flops": p["ffs"], "area_um2": p["area_um2"], "source": p["source"],
                    "note": p.get("note"),
                    "label_anchor": [round(an[0] - cx, 3), 0.0, round(-(an[1] - cy), 3)] if an else None}))
    root["children"].append(parts_node)
    # pins
    pins_node = glb_node("Pins", extras={"display_name": "IO pins (DEF PINS), grouped by bus"})
    by_bus = collections.OrderedDict()
    for pn in sorted(c["pins"], key=lambda q: (q["bus"], q["n"])):
        if pn["bus"] == "power":
            continue
        by_bus.setdefault(pn["bus"], []).append(pn)
    fam_col = {"data in": "#2465c7", "data out": "#e0761c", "thermal": "#7c4fcb", "clock": "#e0a800",
               "reset": "#a8233a", "handshake": "#2f8f3a", "fault": "#c2368c"}
    for bus, pl in by_bus.items():
        rects, z0s, z1s = [], [], []
        for pn in pl:
            x0, y0, x1, y1 = pn["box"]
            ex = max(0.0, 1.0 - (x1 - x0)) / 2
            ey = max(0.0, 1.0 - (y1 - y0)) / 2
            rects.append([x0 - ex - cx, y0 - ey - cy, x1 + ex - cx, y1 + ey - cy])
            z0s.append(stack.get(pn["layer"], {"z": 0})["z"])
            z1s.append(top + 1.0)
        pins_node["children"].append(glb_node(gl_name("Pins_" + bus), mesh={
            "material": "pin_" + gl_name(pl[0]["fam"]), "rgba": lin_rgba(fam_col.get(pl[0]["fam"], "#5e7684")),
            "rects": rects, "z0": z0s, "z1": z1s},
            extras={"display_name": bus, "pins": [q["n"] for q in pl], "family": pl[0]["fam"],
                    "marker": "pin shape widened to >= 1 um, drawn from its layer up to 1 um above the stack"}))
    root["children"].append(pins_node)
    # regions
    if c["regions"]:
        reg_node = glb_node("Regions", extras={"display_name": "Placement fences (DEF REGIONS)"})
        rcol = {"copyA": "#2465c7", "copyB": "#e0761c", "th0": "#7c4fcb", "th1": "#c2368c", "th2": "#2f8f3a"}
        for r in c["regions"]:
            walls = []
            w = 0.8
            for (x0, y0, x1, y1) in r["boxes"]:
                x0, y0, x1, y1 = x0 - cx, y0 - cy, x1 - cx, y1 - cy
                walls += [[x0, y0, x1, y0 + w], [x0, y1 - w, x1, y1], [x0, y0, x0 + w, y1], [x1 - w, y0, x1, y1]]
            reg_node["children"].append(glb_node(gl_name("Region_" + r["label"].replace(" region", "")), mesh={
                "material": "region_" + gl_name(r["role"]), "rgba": lin_rgba(rcol.get(r["role"], "#183a4a")),
                "rects": walls, "z0": 0.0, "z1": top + 0.5},
                extras={"display_name": r["label"], "def_region": r["name"], "type": r["type"],
                        "box_um": r["boxes"], "members": r["members"], "flip_flops": r.get("flip_flops"),
                        "drawn_as": "0.8 um wide outline walls, z 0 to 0.5 um above the stack"}))
        root["children"].append(reg_node)
    return root


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gds", required=True)
    ap.add_argument("--def", dest="def_path", required=True)
    ap.add_argument("--tech-lef", required=True)
    ap.add_argument("--cell-lef", required=True)
    ap.add_argument("--lyt", default=None, help="KLayout .lyt with the layer map (verification)")
    ap.add_argument("--pd-summary", default="reports/pd/summary.md,reports/pd/sky130hd/results.md",
                    help="comma-separated candidates; the first existing file supplies clock/WNS/area/cells")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--glb", default=None,
                    help="portable GLB: metals + vias (uncompressed, KHR_mesh_quantization) + parts, pins, regions, die")
    ap.add_argument("--glb-full", default=None,
                    help="detailed GLB: ALL drawn layers + parts, pins, regions, die; Draco-compressed with "
                         "gltf-transform when --gltf-transform is given and the raw file exceeds --glb-full-raw-mb")
    ap.add_argument("--gltf-transform", default=None, help="path to the @gltf-transform/cli executable")
    ap.add_argument("--glb-full-raw-mb", type=float, default=40.0)
    ap.add_argument("--glb-budget-mb", type=float, default=9.5,
                    help="(portable GLB) optional layers (li1, mcon, poly, ...) are added only while under this size")
    ap.add_argument("--regions-json", default=None,
                    help="pdsep regions.json: labels/colours of the placement fences (optional)")
    ap.add_argument("--baseline-def", default=None,
                    help="DEF of the unconstrained baseline run: its copy-distance numbers are kept as 'before'")
    ap.add_argument("--write-bin", action="store_true",
                    help="also write the raw layout.bin next to layout.b64.txt (local use; not committed)")
    ap.add_argument("--glb-quant-um", type=float, default=0.01,
                    help="KHR_mesh_quantization step (um); int16 must cover half the die")
    ap.add_argument("--glb-core", action="store_true",
                    help="core glTF with float32 positions and no extensions (larger file)")
    ap.add_argument("--glb-z-scale", type=float, default=1.0,
                    help="vertical scale baked into the GLB (1.0 = true stack)")
    ap.add_argument("--redundancy-report", default=None)
    ap.add_argument("--bin-budget-mb", type=float, default=8.0,
                    help="total layout.bin budget; front-end layers are cut to a detail window above it")
    ap.add_argument("--fe-window", default=None, help="x0,y0,x1,y1 um: explicit front-end detail window")
    ap.add_argument("--label", default=None, help="data label shown in the page")
    ap.add_argument("--pd-config", default="pd/sky130hd/config.mk",
                    help="pd flow configuration, only read to report placement constraints")
    args = ap.parse_args()

    t_start = _dt.datetime.now(_dt.timezone.utc)

    # --- platform --------------------------------------------------------
    tech = read_tech_lef(args.tech_lef)
    lyt_map = read_lyt_layer_map(args.lyt)
    macros = read_cell_lef(args.cell_lef)
    layer_check = {}
    for name, gds_ld, *_ in LAYERS:
        ref = lyt_map.get(NAMES_FROM_LYT[name])
        layer_check[name] = ("match" if ref == gds_ld else f"MISMATCH lyt={ref}") if lyt_map else "not checked"
        if lyt_map and ref != gds_ld:
            log(f"WARNING layer {name}: script uses {gds_ld}, platform .lyt says {ref}")

    # --- DEF -------------------------------------------------------------
    defd = read_def(args.def_path)
    flop_names = [(n, m) for n, (m, *_r) in defd["components"].items() if FLOP_MASTER_RE.search(m)]
    want = set()
    for n, m in flop_names:
        mac = macros.get(m)
        if mac:
            qp = "Q" if "Q" in mac["pins"] else next((p for p, d in mac["pins"].items() if d == "OUTPUT"), None)
            if qp:
                want.add((n, qp))
    if want:
        defd = read_def(args.def_path, want_nets_for=want)
    die = defd["die"]
    core = core_from_rows(defd["rows"], defd["units"], macros)
    design = defd["design"] or "design"
    log(f"design {design}: die {die}, core {core}, {len(defd['components'])} components, {len(flop_names)} flip-flops")
    full = viz_parts.read_def_full(args.def_path)
    part_of, serves, clock_nets, _sig, _names = viz_parts.attribute(full, macros)
    log(f"parts: {len(set(part_of.values()))} parts over {len(part_of)} components, "
        f"{sum(1 for v in part_of.values() if v == 'other')} unattributed")

    # --- GDS -------------------------------------------------------------
    ly = kdb.Layout()
    ly.read(args.gds)
    dbu = ly.dbu
    tops = ly.top_cells()
    top = next((c for c in tops if c.name == design), None) or max(tops, key=lambda c: c.bbox().area())
    ox, oy = die[0], die[1]
    die_w, die_h = die[2] - die[0], die[3] - die[1]

    present = {}
    for li in ly.layer_indexes():
        info = ly.get_info(li)
        cnt = 0
        it = top.begin_shapes_rec(li)
        while not it.at_end():
            cnt += 1
            it.next()
        if cnt:
            present[(info.layer, info.datatype)] = (li, cnt)
    rev_lyt = {}
    for k, v in lyt_map.items():
        if v not in rev_lyt or k.endswith(".drawing"):
            rev_lyt[v] = k
    used = {ld for _n, ld, *_ in LAYERS}
    dropped = [{"gds": list(ld), "name": rev_lyt.get(ld, "?"), "shapes": c}
               for ld, (li, c) in sorted(present.items()) if ld not in used]

    grid_um = 0.005
    grid_dbu = grid_um / dbu
    span = max(die_w, die_h)
    if span / grid_um <= 65535:
        dtype, dname = np.uint16, "uint16"
    elif span / 0.010 <= 65535:
        grid_um, grid_dbu, dtype, dname = 0.010, 0.010 / dbu, np.uint16, "uint16"
    else:
        dtype, dname = np.uint32, "uint32"
    log(f"quantization: {dname} on a {grid_um * 1000:.0f} nm grid relative to the die origin")

    layer_rects = {}
    layer_meta = {}
    offgrid_total = 0
    for name, gds_ld, kind, color, below, above in LAYERS:
        if gds_ld not in present:
            layer_rects[name] = np.zeros((0, 4), dtype=np.int64)
            layer_meta[name] = {"method": None, "nonrect": 0, "shapes": 0}
            continue
        li, cnt = present[gds_ld]
        reg = kdb.Region(top.begin_shapes_rec(li))
        arr, method, nonrect = region_to_boxes(reg, dbu)
        layer_rects[name] = arr
        layer_meta[name] = {"method": method, "nonrect": nonrect, "shapes": cnt}
        log(f"  {name:6s} {gds_ld[0]}/{gds_ld[1]}: {cnt} shapes -> {arr.shape[0]} rects ({method})")

    # --- z stack ---------------------------------------------------------
    stack = {}
    for name, gds_ld, kind, color, below, above in LAYERS:
        mz, mt = MAGIC_HEIGHTS[name]
        t_lef = tech.get(name, {}).get("thickness")
        h_lef = tech.get(name, {}).get("height")
        z = h_lef if h_lef is not None else mz
        if kind == "metal":
            t = t_lef if t_lef is not None else mt
            src_t = "tech LEF THICKNESS" if t_lef is not None else "Magic tech"
            src_z = "tech LEF HEIGHT" if h_lef is not None else "Magic tech height (tech LEF has no HEIGHT)"
            approx = False
        else:
            t = mt
            src_t = "Magic tech"
            src_z = "Magic tech height"
            approx = kind in ("well", "fe")
        stack[name] = {"z": z, "t": t, "src_z": src_z, "src_t": src_t, "approx": approx,
                       "magic": [mz, mt], "lef_thickness": t_lef}
    # cuts span the metals they connect
    for name, gds_ld, kind, color, below, above in LAYERS:
        if kind == "cut" and above:
            top_z = stack[above]["z"]
            bot_z = (stack[below]["z"] + stack[below]["t"]) if below else stack[name]["z"]
            stack[name]["z"] = bot_z
            stack[name]["t"] = top_z - bot_z
            stack[name]["src_z"] = f"top of {below}" if below else "Magic tech height"
            stack[name]["src_t"] = f"spans to bottom of {above}"
            if name == "licon1":
                stack[name]["approx"] = True
    stack_top = max(v["z"] + v["t"] for v in stack.values())

    # --- payload budget: front-end detail window --------------------------
    bpr = 8 if dname == "uint16" else 16
    total_bytes = sum(a.shape[0] for a in layer_rects.values()) * bpr
    budget = args.bin_budget_mb * 1e6
    fe_window = None
    if args.fe_window:
        fe_window = tuple(float(v) for v in args.fe_window.split(","))
    elif total_bytes > budget:
        be_bytes = sum(layer_rects[n].shape[0] for n in layer_rects if n not in FE_LAYERS) * bpr
        fe_bytes = total_bytes - be_bytes
        frac = max(0.02, min(1.0, (budget - be_bytes) / max(fe_bytes, 1)))
        c = core or die
        cxw, cyw = (c[0] + c[2]) / 2, (c[1] + c[3]) / 2
        side_x = (c[2] - c[0]) * math.sqrt(frac)
        side_y = (c[3] - c[1]) * math.sqrt(frac)
        fe_window = (cxw - side_x / 2, cyw - side_y / 2, cxw + side_x / 2, cyw + side_y / 2)
    fe_clipped = {}
    if fe_window:
        wx0, wy0, wx1, wy1 = (v / dbu for v in fe_window)
        for n in FE_LAYERS:
            if n == "nwell":
                continue
            a = layer_rects[n]
            keep = (a[:, 2] > wx0) & (a[:, 0] < wx1) & (a[:, 3] > wy0) & (a[:, 1] < wy1)
            fe_clipped[n] = int(a.shape[0] - keep.sum())
            layer_rects[n] = a[keep]
        log(f"front-end detail window {fe_window}: dropped {sum(fe_clipped.values())} rects")

    # --- binary ----------------------------------------------------------
    os.makedirs(args.out_dir, exist_ok=True)
    chunks = [MAGIC + struct.pack("<II", len(LAYERS), 1)]
    off = HEADER_BYTES
    layers_json = []
    for name, gds_ld, kind, color, below, above in LAYERS:
        a = layer_rects[name]
        rel = a.astype(np.float64)
        rel[:, 0] -= ox / dbu
        rel[:, 2] -= ox / dbu
        rel[:, 1] -= oy / dbu
        rel[:, 3] -= oy / dbu
        q = rel / grid_dbu
        qi = np.rint(q)
        # Slab decomposition can leave 5 nm slivers (half a 10 nm grid step);
        # rounded, they have zero width or height and draw nothing. Drop them
        # here so the GLB (built from layer_rects below) skips them too.
        keep = (qi[:, 2] > qi[:, 0]) & (qi[:, 3] > qi[:, 1])
        degenerate = int(a.shape[0] - keep.sum())
        if degenerate:
            a, q, qi = a[keep], q[keep], qi[keep]
            layer_rects[name] = a
        offgrid = int(np.count_nonzero(np.abs(q - qi) > 1e-6))
        offgrid_total += offgrid
        lim = np.iinfo(dtype).max
        qi = np.clip(qi, 0, lim).astype(dtype)
        data = qi.astype("<" + ("u2" if dname == "uint16" else "u4")).tobytes()
        pad = (-off) % 4
        if pad:
            chunks.append(b"\x00" * pad)
            off += pad
        s = stack[name]
        layers_json.append({
            "name": name, "gds": list(gds_ld), "kind": kind, "color": color,
            "z_um": round(s["z"], 4), "thickness_um": round(s["t"], 4),
            "z_source": s["src_z"], "thickness_source": s["src_t"], "approximate": s["approx"],
            "magic_z_thickness_um": s["magic"], "tech_lef_thickness_um": s["lef_thickness"],
            "layer_map_check": layer_check[name],
            "count": int(a.shape[0]), "offset": off, "bytes": len(data),
            "gds_shapes": layer_meta[name]["shapes"], "decomposition": layer_meta[name]["method"],
            "non_rect_as_bbox": layer_meta[name]["nonrect"],
            "clipped_to_detail_window": name in fe_clipped, "clipped_rects": fe_clipped.get(name, 0),
            "off_grid_rounded": offgrid, "degenerate_dropped": degenerate,
        })
        chunks.append(data)
        off += len(data)
    # --- cells, parts, power grid: extra blocks after the layers ----------
    cells_json, parts_json, power_json, pins_json, rows_json, regions_json_out, extra_chunks, off = build_cell_blocks(
        full, macros, part_of, serves, die, grid_um, off, args.regions_json)
    chunks.extend(extra_chunks)
    blob = b"".join(chunks)
    import base64
    b64_path = os.path.join(args.out_dir, "layout.b64.txt")
    with open(b64_path, "wb") as f:
        f.write(base64.b64encode(blob))
    bin_size = len(blob)
    if args.write_bin:
        with open(os.path.join(args.out_dir, "layout.bin"), "wb") as f:
            f.write(blob)
    log(f"wrote {b64_path}: {os.path.getsize(b64_path)} bytes (base64 of {bin_size} bytes), "
        f"{sum(l['count'] for l in layers_json)} rects, {cells_json['count']} cells")

    # --- redundancy ------------------------------------------------------
    recs = build_flop_records(defd, macros)
    groups = group_stats(recs)
    redundant_groups = [g for g in groups if g["kind"] in ("pair", "triple")]
    flops_json = [{"n": r["name"], "g": r["group"], "c": r["copy"], "b": r["bit"],
                   "box": [round(v - (ox if i % 2 == 0 else oy), 3) for i, v in enumerate(r["box"])],
                   "m": r["master"].replace("sky130_fd_sc_hd__", "")}
                  for r in recs]

    # --- stats -----------------------------------------------------------
    pd_sum = parse_pd_summary(args.pd_summary)
    orfs = orfs_metrics(args.gds)
    # Values from the ORFS run that produced this GDS win (same provenance as
    # the geometry); the pd area's summary only fills gaps.
    stats = {
        "clock_period_ns": orfs.get("clock_period_ns", pd_sum.get("clock_period_ns")),
        "wns_ns": orfs.get("wns_ns", pd_sum.get("wns_ns")),
        "area_um2": orfs.get("area_um2", pd_sum.get("area_um2")),
        "cell_count": orfs.get("cell_count", pd_sum.get("cell_count")),
        "utilization": orfs.get("utilization"),
        "tap_cells": orfs.get("tap_cells"),
        "cell_count_note": "standard cells excluding fill/decap and tap cells",
        "components_in_def": len(defd["components"]),
        "flip_flops": len(recs),
        "sources": {
            "pd_summary": pd_sum.get("source"),
            "orfs_metrics": orfs.get("source"),
            "sdc": orfs.get("clock_source"),
            "note": ("ORFS 6_report.json / 6_final.sdc of the run that wrote the GDS win; the pd summary "
                     "only fills values they lack"),
            "pd_summary_values": {k: v for k, v in pd_sum.items() if k != "source"} or None,
        },
    }

    def rel(p):
        return os.path.relpath(os.path.abspath(p), os.getcwd()) if p else None

    meta = {
        "format": {
            "name": "orbit-viz-layout", "version": 2, "bin": "layout.b64.txt", "encoding": "base64",
            "bin_bytes": bin_size, "magic": MAGIC.decode(),
            "header_bytes": HEADER_BYTES, "byte_order": "little", "dtype": dname,
            "grid_um": grid_um, "origin_um": [ox, oy],
            "rect": "x0,y0,x1,y1 per rectangle, grid units relative to the die lower-left corner",
        },
        "design": design,
        "label": args.label or design,
        "platform": "sky130hd (SkyWater SKY130 open PDK, sky130_fd_sc_hd)",
        "generated_utc": t_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "inputs": {"gds": rel(args.gds), "def": rel(args.def_path), "tech_lef": rel(args.tech_lef),
                   "cell_lef": rel(args.cell_lef), "layer_map": rel(args.lyt),
                   # which pd run this is: file times and a content hash of the inputs
                   "gds_mtime_utc": _mtime_utc(args.gds), "def_mtime_utc": _mtime_utc(args.def_path),
                   "gds_sha256": _sha256(args.gds), "def_sha256": _sha256(args.def_path)},
        "tools": {"klayout_python": getattr(kdb, "__version__", None) or _klayout_version(),
                  "numpy": np.__version__, "python": sys.version.split()[0]},
        "die_um": [0.0, 0.0, round(die_w, 4), round(die_h, 4)],
        "die_abs_um": list(die),
        "core_um": [round(v - (ox if i % 2 == 0 else oy), 4) for i, v in enumerate(core)] if core else None,
        "core_note": "bounding box of the DEF placement rows",
        "stack_top_um": round(stack_top, 4),
        "layers": layers_json,
        "z_sources": {
            "routing_thickness": "platform tech LEF sky130_fd_sc_hd.tlef (ORFS flow/platforms/sky130hd/lef), THICKNESS",
            "z": MAGIC_TECH_SRC + "; the ORFS sky130hd tech LEF has no HEIGHT statements",
            "cuts": "span from the top of the lower metal to the bottom of the upper metal",
            "approximate": "nwell, diff, tap, poly, licon1: Magic 3D-view heights, no oxides/silicide/well depth",
        },
        "dropped_layers": dropped,
        "dropped_note": "GDS layers not drawn: implants, pins/labels, area ids, boundaries and other purposes",
        "fe_detail_window_um": [round(v - (ox if i % 2 == 0 else oy), 3) for i, v in enumerate(fe_window)] if fe_window else None,
        "fe_detail_note": ("front-end layers (diff, tap, poly, licon1, li1, mcon) kept only inside the detail window "
                           "to stay within the payload budget; metal and via layers are complete") if fe_window else None,
        "off_grid_rounded_rects": offgrid_total,
        "stats": stats,
        "redundancy": {
            "groups": groups,
            "redundant_group_count": len(redundant_groups),
            "flops": flops_json,
            "method": ("flip-flops = DEF components whose master matches sky130_fd_sc_hd__{,e,s,se}df*; "
                       "group/copy from the instance name (docs/SPEC.md section 7); bit index from the "
                       "instance name after the copy token, else from the Q net name (mod register width); "
                       "distances between placed cell boxes (DEF PLACED + LEF SIZE): centre-to-centre and "
                       "edge-to-edge gap"),
        },
    }
    meta["redundancy"]["summary"] = summarize_redundancy(groups)
    meta["redundancy"]["placement_constraints_note"] = placement_constraint_note(
        args.pd_config, [r for r in full["regions"] if r["type"] == "FENCE"])
    meta["cells"] = cells_json
    meta["parts"] = parts_json
    meta["pins"] = pins_json
    meta["power"] = power_json
    meta["rows"] = rows_json
    meta["regions"] = regions_json_out
    if args.baseline_def and os.path.exists(args.baseline_def):
        bdef = read_def(args.baseline_def)
        bwant = set()
        for n, (m, *_r) in bdef["components"].items():
            if FLOP_MASTER_RE.search(m):
                bwant.add((n, "Q"))
        bdef = read_def(args.baseline_def, want_nets_for=bwant)
        bgroups = group_stats(build_flop_records(bdef, macros))
        meta["redundancy"]["baseline"] = {
            "def": rel(args.baseline_def), "def_sha256": _sha256(args.baseline_def),
            "groups": [{k: v for k, v in g.items() if k != "centroids_um"} for g in bgroups
                       if g["kind"] in ("pair", "triple")],
            "summary": summarize_redundancy(bgroups),
            "note": "unconstrained baseline run (no placement fences), same RTL and die"}
        log("baseline redundancy: " + json.dumps(meta["redundancy"]["baseline"]["summary"]))

    # --- GLB -------------------------------------------------------------
    meta["glb"] = {}
    glb_ctx = dict(die_w=die_w, die_h=die_h, ox=ox, oy=oy, dbu=dbu, stack=stack, stack_top=stack_top,
                   layer_rects=layer_rects, full=full, macros=macros, part_of=part_of, parts=parts_json["list"],
                   pins=pins_json["list"], regions=regions_json_out["list"], design=design,
                   gds_sha256=meta["inputs"]["gds_sha256"], source_gds=rel(args.gds), z_scale=args.glb_z_scale)
    if args.glb:
        quant = None if args.glb_core else args.glb_quant_um
        glb_budget = args.glb_budget_mb * 1e6
        used_bytes = 8191 * 36 * 2 + 256 * 1024 + glb_box_bytes(len(full["components"]) + 400, quant is not None)
        included, excluded = [], []
        for name in GLB_ORDER:
            n = layer_rects[name].shape[0]
            if n == 0:
                continue
            nbytes = glb_box_bytes(n, quant is not None)
            if name not in GLB_REQUIRED and used_bytes + nbytes > glb_budget:
                excluded.append(name)
                continue
            used_bytes += nbytes
            included.append(name)
        root = build_glb_tree(glb_ctx, included, "portable: metals and vias")
        os.makedirs(os.path.dirname(os.path.abspath(args.glb)), exist_ok=True)
        size, node_names, nboxes = write_glb(args.glb, root, root["extras"], quantize_um=quant, z_scale=args.glb_z_scale)
        meta["glb"]["portable"] = {
            "path": rel(args.glb), "bytes": size, "boxes": nboxes, "layers_included": included,
            "layers_excluded": excluded, "z_scale": args.glb_z_scale,
            "position_encoding": (f"KHR_mesh_quantization int16, step {quant} um" if quant else "float32"),
            "nodes": node_names}
        log(f"wrote {args.glb}: {size} bytes, {nboxes} boxes, layers {included}, excluded {excluded}")
    if args.glb_full:
        all_layers = [n for n in GLB_ORDER + ["nwell"] if layer_rects[n].shape[0]]
        root = build_glb_tree(glb_ctx, all_layers, "detailed: every drawn layer")
        raw = args.glb_full + ".raw.glb" if args.gltf_transform else args.glb_full
        os.makedirs(os.path.dirname(os.path.abspath(args.glb_full)), exist_ok=True)
        size, node_names, nboxes = write_glb(raw, root, root["extras"], quantize_um=None, z_scale=args.glb_z_scale)
        log(f"wrote {raw}: {size} bytes (float32), {nboxes} boxes")
        enc = "float32 (core glTF, no extensions)"
        if args.gltf_transform and size > args.glb_full_raw_mb * 1e6:
            import subprocess
            cmd = [args.gltf_transform, "draco", raw, args.glb_full, "--method", "edgebreaker",
                   "--quantize-position", "16"]
            log("running " + " ".join(cmd))
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode != 0:
                raise SystemExit("gltf-transform draco failed:\n" + r.stdout + r.stderr)
            os.remove(raw)
            size = os.path.getsize(args.glb_full)
            enc = "KHR_draco_mesh_compression (edgebreaker, 16-bit positions) via @gltf-transform/cli"
        elif raw != args.glb_full:
            os.replace(raw, args.glb_full)
        meta["glb"]["full"] = {"path": rel(args.glb_full), "bytes": size, "boxes": nboxes, "layers_included": all_layers,
                               "z_scale": args.glb_z_scale, "position_encoding": enc, "nodes": node_names}
        log(f"wrote {args.glb_full}: {size} bytes ({enc})")
    if meta["glb"]:
        meta["glb"].update({"units": "1 unit = 1 um; +X = layout x, +Y = up, -Z = layout y; origin at the die centre, "
                                     "z = 0 at the substrate surface",
                            "die_slab": "Die_Substrate: 1 um thick box from z -1.2 to -0.2 um (display only)",
                            "part_tiles": "Parts: one box per placed cell footprint from z -0.2 to 0 um (display only)"})

    json_path = os.path.join(args.out_dir, "layout.json")
    with open(json_path, "w") as f:
        json.dump(meta, f, separators=(",", ":"))
    log(f"wrote {json_path}: {os.path.getsize(json_path)} bytes")

    if args.redundancy_report:
        write_redundancy_md(args.redundancy_report, meta, groups)
        log(f"wrote {args.redundancy_report}")
    return 0


def placement_constraint_note(path, regions=None):
    """Say whether anything asked the placer to separate the copies."""
    if regions:
        names = ", ".join(r["name"] for r in regions)
        src = f" ({os.path.relpath(path)})" if path and os.path.exists(path) else ""
        return (f"The routed DEF carries {len(regions)} placement fences (DEF REGIONS, TYPE FENCE: {names}) with "
                f"their GROUPS; the pd flow{src} created them to keep the redundant copies apart.")
    if not path or not os.path.exists(path):
        return "The pd configuration was not available to check for placement constraints."
    txt = open(path).read()
    code = "\n".join(l.split("#", 1)[0] for l in txt.splitlines())
    hits = sorted(set(re.findall(r"(?i)\b(fence|region|keep.?out|blockage|create_group|group_place|"
                                 r"PLACE_SITE|MACRO_PLACE|min.?spacing)\w*", code)))
    rel = os.path.relpath(path)
    if not hits:
        return (f"The pd configuration ({rel}, read when this report was generated) sets no region, fence, "
                "keep-out or spacing constraint, so nothing asked the placer to keep copies apart.")
    return (f"The pd configuration ({rel}) mentions {', '.join(hits)}; check whether those settings "
            "target the redundant copies before reading the distances below as intended separation.")


def _mtime_utc(path):
    t = _dt.datetime.fromtimestamp(os.path.getmtime(path), _dt.timezone.utc)
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def _klayout_version():
    try:
        from importlib.metadata import version
        return version("klayout")
    except Exception:
        return None


def summarize_redundancy(groups):
    red = [g for g in groups if g["kind"] in ("pair", "triple")]
    if not red:
        return {"text": "No redundant storage groups (orbit_demo instance names) were found in this DEF.",
                "groups": 0}
    mins = [g["same_bit_center_um"]["min"] for g in red if g.get("same_bit_center_um")]
    meds = [g["same_bit_center_um"]["median"] for g in red if g.get("same_bit_center_um")]
    gaps = [g["same_bit_gap_um"]["min"] for g in red if g.get("same_bit_gap_um")]
    cents = [g["centroid_distance_um_min"] for g in red]
    abut = sum(g.get("same_bit_pairs_abutting", 0) for g in red)
    pairs = sum(g.get("bit_pairs", 0) for g in red)
    s = {"groups": len(red), "centroid_distance_um_min": min(cents), "centroid_distance_um_max": max(cents)}
    anyg = [g["any_bit_gap_um_min"] for g in red if g.get("any_bit_gap_um_min") is not None]
    if anyg:
        s["any_copy_gap_um_min"] = min(anyg)
    pairs_c = [g for g in red if g["kind"] == "pair"]
    trip = [g for g in red if g["kind"] == "triple"]
    if pairs_c and all(g.get("same_bit_center_um") for g in pairs_c):
        s["pair_same_bit_center_um_min"] = min(g["same_bit_center_um"]["min"] for g in pairs_c)
        s["pair_centroid_um_min"] = min(g["centroid_distance_um_min"] for g in pairs_c)
        s["pair_centroid_um_max"] = max(g["centroid_distance_um_min"] for g in pairs_c)
        s["pair_any_gap_um_min"] = min(g["any_bit_gap_um_min"] for g in pairs_c)
        s["pair_same_bit_center_um_median_of_medians"] = statistics.median(
            g["same_bit_center_um"]["median"] for g in pairs_c)
    if trip and all(g.get("same_bit_center_um") for g in trip):
        s["thermal_same_bit_center_um_min"] = min(g["same_bit_center_um"]["min"] for g in trip)
        s["thermal_centroid_um_min"] = min(g["centroid_distance_um_min"] for g in trip)
        s["thermal_any_gap_um_min"] = min(g["any_bit_gap_um_min"] for g in trip)
    if mins:
        s.update({"same_bit_center_um_min": min(mins), "same_bit_center_um_median_of_medians": statistics.median(meds),
                  "same_bit_gap_um_min": min(gaps), "same_bit_pairs": pairs, "same_bit_pairs_abutting": abut})
    return s


def _grp_row(g):
    cd = ", ".join(f"{k} {v:.2f}" for k, v in g["centroid_distance_um"].items())
    sc = g.get("same_bit_center_um")
    sg = g.get("same_bit_gap_um")
    sc_t = f"{sc['min']:.2f} / {sc['median']:.2f} / {sc['max']:.2f}" if sc else "n/a"
    sg_t = f"{sg['min']:.2f} / {sg['median']:.2f}" if sg else "n/a"
    ab = f"{g.get('same_bit_pairs_abutting', 0)} of {g.get('bit_pairs', 0)}" if sc else "n/a"
    return cd, sc_t, sg_t, ab, g.get("any_bit_gap_um_min")


def write_redundancy_md(path, meta, groups):
    red = [g for g in groups if g["kind"] in ("pair", "triple")]
    singles = [g for g in groups if g["kind"] not in ("pair", "triple")]
    base = meta["redundancy"].get("baseline")
    L = []
    L.append(f"# Redundant storage placement: {meta['design']} on sky130hd")
    L.append("")
    L.append(f"Generated by `scripts/viz_gds_to_3d.py` on {meta['generated_utc']} from "
             f"`{meta['inputs']['def']}` (placement) and `{meta['inputs']['gds']}`"
             + (f"; the baseline column comes from `{base['def']}`." if base else "."))
    L.append("Distances are between placed standard-cell boxes (DEF `PLACED` origin + LEF `SIZE`), in µm. "
             "*Centre* is centre-to-centre; *gap* is the edge-to-edge distance (0 = the cells touch). "
             "A sky130_fd_sc_hd row is 2.72 µm tall; a dfxtp_1 flip-flop is 7.36 µm wide.")
    L.append("")
    if not red:
        L.append("No redundant storage groups were found: the DEF has no instances named like "
                 "`g_lane[i].u_lane.u_acc_a` / `u_res_b` / `u_thermal.u_copyK` (docs/SPEC.md section 7).")
        L.append("")
        L.append(f"Flip-flops in the DEF: {meta['stats']['flip_flops']}.")
    else:
        s = meta["redundancy"]["summary"]
        if base:
            b = base["summary"]
            L.append("## Before and after")
            L.append("")
            L.append("| Measure | Baseline (unconstrained) | This layout |")
            L.append("|---|---|---|")
            rows = [
                ("Closest same-bit pair, acc/res copies A vs B (centre)", "pair_same_bit_center_um_min", "{:.2f} µm"),
                ("Closest same-bit pair, thermal copies (centre)", "thermal_same_bit_center_um_min", "{:.2f} µm"),
                ("Median of the group medians, same-bit centre (acc/res)", "pair_same_bit_center_um_median_of_medians", "{:.1f} µm"),
                ("Same-bit pairs in touching cells", None, None),
                ("Smallest gap, any copy-A vs any copy-B flip-flop of a group", "pair_any_gap_um_min", "{:.2f} µm"),
                ("Smallest gap between flip-flops of different thermal copies", "thermal_any_gap_um_min", "{:.2f} µm"),
                ("Copy centroid distance, acc/res (min to max)", None, None),
                ("Copy centroid distance, thermal (min)", "thermal_centroid_um_min", "{:.1f} µm"),
            ]
            for label, key, f in rows:
                if key:
                    bv, sv = b.get(key), s.get(key)
                    L.append(f"| {label} | {f.format(bv) if bv is not None else 'n/a'} | {f.format(sv) if sv is not None else 'n/a'} |")
                elif "touching" in label:
                    L.append(f"| {label} | {b.get('same_bit_pairs_abutting')} of {b.get('same_bit_pairs')} | "
                             f"{s.get('same_bit_pairs_abutting')} of {s.get('same_bit_pairs')} |")
                else:
                    L.append(f"| {label} | {b.get('pair_centroid_um_min', 0):.1f}-{b.get('pair_centroid_um_max', 0):.1f} µm | "
                             f"{s.get('pair_centroid_um_min', 0):.1f}-{s.get('pair_centroid_um_max', 0):.1f} µm |")
            L.append("")
        L.append("## Per group (this layout)")
        L.append("")
        L.append("| Group | Copies (flops) | Centroid distance | Same-bit centre min / median / max | Same-bit gap min / median | Same-bit pairs abutting | Closest cells of different copies (gap) |")
        L.append("|---|---|---|---|---|---|---|")
        for g in red:
            cp = ", ".join(f"{k}: {v}" for k, v in g["copies"].items())
            cd, sc_t, sg_t, ab, anyg = _grp_row(g)
            L.append(f"| {g['label']} | {cp} | {cd} | {sc_t} | {sg_t} | {ab} | {anyg} |")
        L.append("")
        if base:
            L.append("## Per group (baseline)")
            L.append("")
            L.append("| Group | Centroid distance | Same-bit centre min / median / max | Same-bit gap min / median | Same-bit pairs abutting | Closest cells of different copies (gap) |")
            L.append("|---|---|---|---|---|---|")
            for g in base["groups"]:
                cd, sc_t, sg_t, ab, anyg = _grp_row(g)
                L.append(f"| {g['label']} | {cd} | {sc_t} | {sg_t} | {ab} | {anyg} |")
            L.append("")
        if singles:
            L.append("Unprotected single flip-flops: " + ", ".join(
                f"{g['label']} ({g['flops']})" for g in singles) + ".")
            L.append("")
        L.append("## What this shows")
        L.append("")
        L.append(meta["redundancy"].get("placement_constraints_note", ""))
        L.append("")
        txt = (f"Across the {s['groups']} redundant groups the copies' centroids are "
               f"{s['centroid_distance_um_min']:.1f}-{s['centroid_distance_um_max']:.1f} µm apart.")
        if "same_bit_center_um_min" in s:
            txt += (f" Corresponding bits of different copies are at least {s['same_bit_center_um_min']:.2f} µm "
                    f"apart centre-to-centre (median of the group medians {s['same_bit_center_um_median_of_medians']:.1f} µm); "
                    f"{s['same_bit_pairs_abutting']} of {s['same_bit_pairs']} same-bit pairs sit in cells that touch.")
        L.append(txt)
        L.append("")
        if base:
            b = base["summary"]
            L.append(f"In the unconstrained baseline the closest same-bit pair was {b.get('same_bit_center_um_min', 0):.2f} µm "
                     f"centre to centre and {b.get('same_bit_pairs_abutting')} of {b.get('same_bit_pairs')} same-bit pairs "
                     "touched, so one particle track or charge-sharing event could upset both copies of a bit. "
                     "With the fences no copy pair touches and the copies are hundreds of µm (acc/res) or about "
                     "100 µm (thermal) apart.")
            L.append("")
        L.append("What the fences do not separate: the clock tree, the reset tree, the shared per-lane multipliers, "
                 "the A/B comparators and mismatch OR tree, the thermal voter and next-state logic, the enable/clear "
                 "distribution, the ports, and the unprotected phase, out_valid_q and fault_q flip-flops (common-mode "
                 "elements). These are geometric distances only, not an upset-rate model; sky130 is not "
                 "radiation-characterised.")
    L.append("")
    L.append("Regenerate: `make viz` (see viz/README.md).")
    with open(path, "w") as f:
        f.write("\n".join(L) + "\n")


if __name__ == "__main__":
    sys.exit(main())
