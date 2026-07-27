#!/usr/bin/env python3
"""Measure the physical separation of the redundant copies in a placed DEF.

Independent of pd/copy_separation.py (the baseline measurement): it reads the
DEF COMPONENTS (cell origin + orientation) and the cell sizes from the LEF,
identifies the redundant flip-flops by their kept-hierarchy instance names
(docs/SPEC.md section 7), and for every redundant group reports

  * the distance between the centroids of the copies,
  * the same-bit centre-to-centre distance (bit k of copy A vs bit k of copy B;
    for the thermal triple, every pair of copies): min / median / max,
  * how many same-bit pairs sit in touching or overlapping cells (edge gap 0),
  * the minimum edge-to-edge gap between ANY flip-flop of one copy and ANY
    flip-flop of another copy of the same group (not only same-bit pairs),
  * the same minimum over all cells of the copies (flip-flops plus the per-copy
    enable/reset gates of the kept orbit_keep_reg instance).

If the DEF has REGIONS/GROUPS (the separated flow writes them), it also checks
that every group member lies inside its region box and reports the gaps
between region boxes.

Several DEFs can be measured in one call (--def LABEL=PATH, repeatable); the
Markdown report then has a before/after table. --check LABEL applies the
acceptance targets to that DEF and makes the exit status non-zero on a miss:

  * zero same-bit pairs in touching or overlapping cells,
  * every same-bit pair >= 20 um apart centre to centre,
  * min edge gap between any two flip-flops of different copies of a group
    >= 10 um,
  * thermal copy regions pairwise disjoint with >= 10 um gaps (needs REGIONS),
  * 518 redundant flip-flops found, each a distinct placed cell, every group
    member inside its region.

Geometric distances only; no radiation or upset-rate model is implied.
"""

import argparse
import json
import math
import re
import statistics
import sys
from collections import defaultdict

LANES = 4
TARGET_CENTRE_UM = 20.0
TARGET_EDGE_UM = 10.0
TARGET_THERMAL_REGION_GAP_UM = 10.0


# --------------------------------------------------------------------------
def read_lef_sizes(path):
    sizes = {}
    text = open(path, errors="replace").read()
    for m in re.finditer(r'\nMACRO\s+(\S+)(.*?)\nEND\s+\1\b', text, re.S):
        s = re.search(r'SIZE\s+([0-9.]+)\s+BY\s+([0-9.]+)', m.group(2))
        if s:
            sizes[m.group(1)] = (float(s.group(1)), float(s.group(2)))
    return sizes


def read_def(path, sizes):
    text = open(path, errors="replace").read()
    units = int(re.search(r'UNITS\s+DISTANCE\s+MICRONS\s+(\d+)', text).group(1))
    die = re.search(r'DIEAREA\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)', text)
    die = tuple(int(v) / units for v in die.groups())
    comps = re.search(r'\nCOMPONENTS\s+\d+\s*;(.*?)\nEND COMPONENTS', text, re.S).group(1)
    cells = {}
    missing = set()
    for stmt in comps.split(';'):
        m = re.search(r'-\s+(\S+)\s+(\S+)', stmt)
        if not m:
            continue
        p = re.search(r'\+\s+(PLACED|FIXED|FIRM|COVER)\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)\s+(\S+)', stmt)
        if not p:
            continue
        name = m.group(1).replace('\\', '')
        master = m.group(2)
        if master not in sizes:
            missing.add(master)
            w = h = 0.0
        else:
            w, h = sizes[master]
        orient = p.group(4)
        if orient in ("E", "W", "FE", "FW"):
            w, h = h, w
        x0, y0 = int(p.group(2)) / units, int(p.group(3)) / units
        cells[name] = {"master": master, "box": (x0, y0, x0 + w, y0 + h), "status": p.group(1)}
    regions = {}
    rs = re.search(r'\nREGIONS\s+\d+\s*;(.*?)\nEND REGIONS', text, re.S)
    if rs:
        for stmt in rs.group(1).split(';'):
            m = re.search(r'-\s+(\S+)', stmt)
            if not m:
                continue
            boxes = [tuple(int(v) / units for v in b) for b in
                     re.findall(r'\(\s*(-?\d+)\s+(-?\d+)\s*\)\s*\(\s*(-?\d+)\s+(-?\d+)\s*\)', stmt)]
            t = re.search(r'\+\s*TYPE\s+(\S+)', stmt)
            regions[m.group(1)] = {"boxes": boxes, "type": t.group(1) if t else None}
    groups = {}
    gs = re.search(r'\nGROUPS\s+\d+\s*;(.*?)\nEND GROUPS', text, re.S)
    if gs:
        for stmt in gs.group(1).split(';'):
            toks = stmt.split()
            if len(toks) < 2 or toks[0] != '-':
                continue
            name = toks[1]
            region = None
            members = []
            i = 2
            while i < len(toks):
                if toks[i] == '+' and i + 2 < len(toks) + 1 and toks[i + 1] == 'REGION':
                    region = toks[i + 2]
                    i += 3
                    continue
                members.append(toks[i].replace('\\', ''))
                i += 1
            groups[name] = {"region": region, "members": members}
    core = None
    rows = re.findall(r'\nROW\s+\S+\s+(\S+)\s+(-?\d+)\s+(-?\d+)\s+\S+\s+DO\s+(\d+)\s+BY\s+(\d+)\s+STEP\s+(\d+)\s+(\d+)', text)
    if rows:
        xs0 = min(int(r[1]) for r in rows)
        ys0 = min(int(r[2]) for r in rows)
        xs1 = max(int(r[1]) + int(r[3]) * int(r[5]) for r in rows)
        rh = sizes.get("__site_height__", 2.72)
        ys1 = max(int(r[2]) for r in rows) + int(round(rh * units))
        core = (xs0 / units, ys0 / units, xs1 / units, ys1 / units)
    return {"units": units, "die": die, "core": core, "cells": cells, "regions": regions, "groups": groups,
            "missing_masters": sorted(missing)}


# --------------------------------------------------------------------------
def centre(b):
    return ((b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0)


def edge_gap(a, b):
    dx = max(0.0, b[0] - a[2], a[0] - b[2])
    dy = max(0.0, b[1] - a[3], a[1] - b[3])
    return math.hypot(dx, dy)


def box_gap(a, b):
    """Edge-to-edge gap between two boxes; negative (the overlap depth) if they overlap."""
    dx = max(b[0] - a[2], a[0] - b[2])
    dy = max(b[1] - a[3], a[1] - b[3])
    if dx < 0 and dy < 0:
        return max(dx, dy)
    return math.hypot(max(dx, 0.0), max(dy, 0.0))


def min_gap_between(boxes_a, boxes_b):
    """Minimum edge gap between any box of set a and any box of set b (brute force with pruning)."""
    best = float("inf")
    bs = sorted(boxes_b)
    for a in boxes_a:
        for b in bs:
            if b[0] - a[2] > best:
                break
            g = edge_gap(a, b)
            if g < best:
                best = g
    return best


FF_RE = re.compile(r'^(?P<inst>g_lane\[(?P<lane>\d+)\]\.u_lane\.u_(?P<reg>acc|res)_(?P<copy>[ab])|'
                   r'u_thermal\.u_copy(?P<tcopy>[012]))/q\[(?P<bit>\d+)\]')
CELL_RE = re.compile(r'^(?:g_lane\[(?P<lane>\d+)\]\.u_lane\.u_(?P<reg>acc|res)_(?P<copy>[ab])|'
                     r'u_thermal\.u_copy(?P<tcopy>[012]))/')


def classify(cells):
    """Return ffs[group][copy][bit] = box and allcells[group][copy] = [boxes]."""
    ffs = defaultdict(lambda: defaultdict(dict))
    allc = defaultdict(lambda: defaultdict(list))
    dup = []
    for name, c in cells.items():
        m = CELL_RE.match(name)
        if not m:
            continue
        if m.group("tcopy") is not None:
            grp, cp = "thermal", m.group("tcopy")
        else:
            grp, cp = f"{m.group('reg')}_lane{m.group('lane')}", m.group("copy").upper()
        allc[grp][cp].append(c["box"])
        f = FF_RE.match(name)
        if f and "__df" in c["master"]:
            bit = int(f.group("bit"))
            if bit in ffs[grp][cp]:
                dup.append(name)
            ffs[grp][cp][bit] = c["box"]
    return ffs, allc, dup


def group_order():
    order = []
    for kind in ("acc", "res"):
        for i in range(LANES):
            order.append(f"{kind}_lane{i}")
    order.append("thermal")
    return order


def measure(d):
    cells = d["cells"]
    ffs, allc, dup = classify(cells)
    res = {"groups": {}, "n_redundant_ff": sum(len(b) for g in ffs.values() for b in g.values()),
           "duplicate_bits": dup}
    for grp in group_order():
        copies = ffs.get(grp, {})
        names = sorted(copies)
        pairs = [(p, q) for i, p in enumerate(names) for q in names[i + 1:]]
        g = {"copies": {c: len(copies[c]) for c in names}, "pairs": {}}
        all_same = []
        for p, q in pairs:
            bits = sorted(set(copies[p]) & set(copies[q]))
            ds, gaps = [], []
            for k in bits:
                a, b = copies[p][k], copies[q][k]
                ds.append(math.dist(centre(a), centre(b)))
                gaps.append(edge_gap(a, b))
            ca = [centre(b) for b in copies[p].values()]
            cb = [centre(b) for b in copies[q].values()]
            cent = math.dist((statistics.fmean(x for x, _ in ca), statistics.fmean(y for _, y in ca)),
                             (statistics.fmean(x for x, _ in cb), statistics.fmean(y for _, y in cb)))
            pr = {
                "bits": len(bits),
                "centroid_um": cent,
                "same_bit_centre_min_um": min(ds), "same_bit_centre_median_um": statistics.median(ds),
                "same_bit_centre_max_um": max(ds),
                "same_bit_gap_min_um": min(gaps),
                "same_bit_touching": sum(1 for x in gaps if x <= 1e-9),
                "min_edge_gap_any_ff_um": min_gap_between(list(copies[p].values()), list(copies[q].values())),
                "min_edge_gap_any_cell_um": min_gap_between(allc[grp][p], allc[grp][q]),
            }
            g["pairs"][f"{p}-{q}"] = pr
            all_same += ds
        res["groups"][grp] = g
    # whole copy A vs whole copy B (all lanes, acc + res)
    a_all = [b for grp in group_order()[:-1] for b in ffs[grp].get("A", {}).values()]
    b_all = [b for grp in group_order()[:-1] for b in ffs[grp].get("B", {}).values()]
    res["copyA_vs_copyB_min_edge_gap_um"] = min_gap_between(a_all, b_all) if a_all and b_all else None
    # regions
    regs = d["regions"]
    res["regions"] = {}
    for rn, r in regs.items():
        res["regions"][rn] = {"type": r["type"], "boxes_um": r["boxes"]}
    rnames = sorted(regs)
    res["region_gaps_um"] = {}
    for i, p in enumerate(rnames):
        for q in rnames[i + 1:]:
            res["region_gaps_um"][f"{p}|{q}"] = min(box_gap(a, b) for a in regs[p]["boxes"] for b in regs[q]["boxes"])
    # membership check
    viol, members, member_ffs = [], 0, 0
    for gn, g in d["groups"].items():
        r = regs.get(g["region"])
        for m in g["members"]:
            c = cells.get(m)
            if c is None:
                viol.append(f"{gn}: member {m} not placed / not found")
                continue
            members += 1
            member_ffs += "__df" in c["master"]
            b = c["box"]
            if not r or not any(b[0] >= x0 - 1e-6 and b[1] >= y0 - 1e-6 and b[2] <= x1 + 1e-6 and b[3] <= y1 + 1e-6
                                for x0, y0, x1, y1 in r["boxes"]):
                viol.append(f"{gn}: {m} at {b} outside region {g['region']}")
    # non-member logic cells vs the fences (informational): fully inside a fence, or straddling its edge
    member_set = {m for g in d["groups"].values() for m in g["members"]}
    inside_n, straddle_n = 0, 0
    straddle_kinds = defaultdict(int)
    inside_kinds = defaultdict(int)
    by_region = defaultdict(list)
    if regs:
        for n, c in cells.items():
            if n in member_set:
                continue
            if c["master"].startswith(("sky130_fd_sc_hd__tap", "sky130_fd_sc_hd__fill", "sky130_fd_sc_hd__decap",
                                       "sky130_ef_sc_hd__decap")):
                continue
            b = c["box"]
            for rn, r in regs.items():
                for x0, y0, x1, y1 in r["boxes"]:
                    if b[0] < x1 - 1e-6 and b[2] > x0 + 1e-6 and b[1] < y1 - 1e-6 and b[3] > y0 + 1e-6:
                        if b[0] >= x0 - 1e-6 and b[2] <= x1 + 1e-6 and b[1] >= y0 - 1e-6 and b[3] <= y1 + 1e-6:
                            inside_n += 1
                            inside_kinds[c["master"].replace("sky130_fd_sc_hd__", "")] += 1
                        else:
                            straddle_n += 1
                            straddle_kinds[c["master"].replace("sky130_fd_sc_hd__", "")] += 1
                        ov = (min(b[2], x1) - max(b[0], x0)) * (min(b[3], y1) - max(b[1], y0))
                        by_region[rn].append({"inst": n, "master": c["master"].replace("sky130_fd_sc_hd__", ""),
                                              "origin_inside": bool(x0 <= b[0] < x1 and y0 <= b[1] < y1),
                                              "overlap_um2": round(ov, 3),
                                              "overlap_fraction": round(ov / ((b[2] - b[0]) * (b[3] - b[1])), 3)})
    intr = inside_n + straddle_n
    res["nonmember_cells_fully_inside_regions"] = inside_n
    res["nonmember_cells_straddling_region_edge"] = straddle_n
    res["nonmember_straddling_kinds"] = dict(sorted(straddle_kinds.items(), key=lambda kv: -kv[1]))
    res["nonmember_inside_kinds"] = dict(sorted(inside_kinds.items(), key=lambda kv: -kv[1]))
    # every non-member cell that overlaps a fence, per region (largest overlap first)
    res["nonmember_overlaps_by_region"] = {rn: sorted(v, key=lambda e: -e["overlap_um2"])
                                           for rn, v in sorted(by_region.items())}
    res["group_members_placed"] = members
    res["group_member_ffs"] = member_ffs
    res["group_member_violations"] = viol
    res["nonmember_logic_cells_in_regions"] = intr
    # which region holds each copy (by the flip-flops' location)
    loc = {}
    for grp in group_order():
        for cp, bits in ffs.get(grp, {}).items():
            inside = defaultdict(int)
            for b in bits.values():
                for rn, r in regs.items():
                    if any(b[0] >= x0 - 1e-6 and b[1] >= y0 - 1e-6 and b[2] <= x1 + 1e-6 and b[3] <= y1 + 1e-6
                           for x0, y0, x1, y1 in r["boxes"]):
                        inside[rn] += 1
            loc[f"{grp}.{cp}"] = dict(inside)
    res["copy_region_occupancy"] = loc
    return res


def check(res):
    fails = []
    if res["n_redundant_ff"] != 518:
        fails.append(f"found {res['n_redundant_ff']} redundant flip-flops, expected 518")
    if res["duplicate_bits"]:
        fails.append(f"duplicate bits: {res['duplicate_bits'][:5]}")
    for grp, g in res["groups"].items():
        exp = {"thermal": {"0": 2, "1": 2, "2": 2}}.get(grp, {"A": 32, "B": 32})
        if g["copies"] != exp:
            fails.append(f"{grp}: copies {g['copies']} expected {exp}")
        for pn, p in g["pairs"].items():
            if p["same_bit_touching"]:
                fails.append(f"{grp} {pn}: {p['same_bit_touching']} same-bit pairs touch/overlap")
            if p["same_bit_centre_min_um"] < TARGET_CENTRE_UM:
                fails.append(f"{grp} {pn}: same-bit centre min {p['same_bit_centre_min_um']:.2f} um < {TARGET_CENTRE_UM}")
            if p["min_edge_gap_any_ff_um"] < TARGET_EDGE_UM:
                fails.append(f"{grp} {pn}: min edge gap {p['min_edge_gap_any_ff_um']:.2f} um < {TARGET_EDGE_UM}")
    th = {k: v for k, v in res["region_gaps_um"].items()
          if all(re.search(r'th[012]$', x) for x in k.split("|"))}
    if len(th) != 3:
        fails.append(f"expected 3 thermal region pairs in the DEF REGIONS, found {len(th)}")
    for k, v in th.items():
        if v < TARGET_THERMAL_REGION_GAP_UM:
            fails.append(f"thermal regions {k}: gap {v:.2f} um < {TARGET_THERMAL_REGION_GAP_UM}")
    for k, v in res["region_gaps_um"].items():
        if v <= 0:
            fails.append(f"regions {k} overlap or touch (gap {v:.2f})")
    if res["group_member_violations"]:
        fails.append(f"{len(res['group_member_violations'])} group members outside their region, e.g. "
                     f"{res['group_member_violations'][0]}")
    for key, occ in res["copy_region_occupancy"].items():
        grp = key.split(".")[0]
        n = 2 if grp == "thermal" else 32
        if sum(occ.values()) != n or len(occ) != 1:
            fails.append(f"{key}: flip-flops not all inside one region: {occ}")
    return fails


# --------------------------------------------------------------------------
def fmt(v, nd=2):
    return "n/a" if v is None else f"{v:.{nd}f}"


def pretty_group(g):
    if g == "thermal":
        return "Thermal state (TMR)"
    kind, lane = g.split("_lane")
    return f"{'Accumulator' if kind == 'acc' else 'Result'} lane {lane}"


def summarise(res):
    """Aggregate per label: overall numbers used in the before/after table."""
    rows = []
    for grp, g in res["groups"].items():
        for pn, p in g["pairs"].items():
            rows.append((grp, pn, p))
    return rows


def write_md(results, out, check_label, fails):
    labels = list(results)
    L = ["# Copy separation measurement (scripts/pdsep_separation.py)", "",
         "Distances between placed standard-cell boxes (DEF origin + LEF SIZE), in um. "
         "*Centre* is centre-to-centre; *gap* is edge-to-edge (0 = the cells touch or overlap). "
         "A sky130_fd_sc_hd row is 2.72 um tall; a dfxtp_1 flip-flop is 7.36 um wide.", ""]
    for lab in labels:
        L.append(f"- **{lab}**: `{results[lab]['def']}`")
    L.append("")
    L += ["## Per group", "",
          "| Group | Copies | " + " | ".join(
              f"{lab}: centroid | {lab}: same-bit centre min / median / max | {lab}: same-bit touching | "
              f"{lab}: min gap any FF / any cell" for lab in labels) + " |",
          "|---|---|" + "---|---|---|---|" * len(labels)]
    first = results[labels[0]]["measure"]
    for grp in group_order():
        for pn in first["groups"][grp]["pairs"]:
            cells = []
            for lab in labels:
                p = results[lab]["measure"]["groups"][grp]["pairs"].get(pn)
                if p is None:
                    cells += ["n/a"] * 4
                    continue
                cells += [fmt(p["centroid_um"], 1),
                          f"{fmt(p['same_bit_centre_min_um'])} / {fmt(p['same_bit_centre_median_um'])} / "
                          f"{fmt(p['same_bit_centre_max_um'])}",
                          f"{p['same_bit_touching']} of {p['bits']}",
                          f"{fmt(p['min_edge_gap_any_ff_um'])} / {fmt(p['min_edge_gap_any_cell_um'])}"]
            L.append(f"| {pretty_group(grp)} | {pn.replace('-', ' vs ')} | " + " | ".join(cells) + " |")
    L += ["", "## Overall", "", "| Quantity | " + " | ".join(labels) + " |", "|---|" + "---|" * len(labels)]

    def agg(lab, fn):
        return fn(results[lab]["measure"])

    def all_pairs(m, grp_filter=None):
        return [p for grp, g in m["groups"].items() if grp_filter is None or grp_filter(grp)
                for p in g["pairs"].values()]

    q = [
        ("redundant flip-flops found", lambda m: str(m["n_redundant_ff"])),
        ("acc/res same-bit centre distance, min (um)",
         lambda m: fmt(min(p["same_bit_centre_min_um"] for p in all_pairs(m, lambda g: g != "thermal")))),
        ("acc/res same-bit centre distance, median of group medians (um)",
         lambda m: fmt(statistics.median(p["same_bit_centre_median_um"] for p in all_pairs(m, lambda g: g != "thermal")))),
        ("acc/res min edge gap, any copy-A FF vs any copy-B FF of the same group (um)",
         lambda m: fmt(min(p["min_edge_gap_any_ff_um"] for p in all_pairs(m, lambda g: g != "thermal")))),
        ("all copy-A FFs vs all copy-B FFs (any lane), min edge gap (um)",
         lambda m: fmt(m["copyA_vs_copyB_min_edge_gap_um"])),
        ("acc/res centroid distance, min / max (um)",
         lambda m: f"{fmt(min(p['centroid_um'] for p in all_pairs(m, lambda g: g != 'thermal')), 1)} / "
                   f"{fmt(max(p['centroid_um'] for p in all_pairs(m, lambda g: g != 'thermal')), 1)}"),
        ("thermal same-bit centre distance, min / median (um)",
         lambda m: f"{fmt(min(p['same_bit_centre_min_um'] for p in all_pairs(m, lambda g: g == 'thermal')))} / "
                   f"{fmt(statistics.median(d for p in all_pairs(m, lambda g: g == 'thermal') for d in (p['same_bit_centre_min_um'], p['same_bit_centre_max_um'])))}"),
        ("thermal min edge gap between any two copies (um)",
         lambda m: fmt(min(p["min_edge_gap_any_ff_um"] for p in all_pairs(m, lambda g: g == "thermal")))),
        ("same-bit pairs in touching/overlapping cells",
         lambda m: f"{sum(p['same_bit_touching'] for p in all_pairs(m))} of {sum(p['bits'] for p in all_pairs(m))}"),
        ("placement regions in the DEF", lambda m: str(len(m["regions"]))),
        ("group members outside their region", lambda m: str(len(m["group_member_violations"])) if m["regions"] else "n/a"),
        ("non-member cells fully inside a fence / straddling a fence edge (excl. fill, tap)",
         lambda m: f"{m['nonmember_cells_fully_inside_regions']} / {m['nonmember_cells_straddling_region_edge']}"
         if m["regions"] else "n/a"),
    ]
    for name, fn in q:
        L.append(f"| {name} | " + " | ".join(agg(lab, fn) for lab in labels) + " |")
    for lab in labels:
        m = results[lab]["measure"]
        if m["regions"]:
            L += ["", f"## Regions in {lab}", "", "| Region | Type | Box (um) |", "|---|---|---|"]
            for rn, r in sorted(m["regions"].items()):
                L.append(f"| {rn} | {r['type']} | " + "; ".join(
                    f"({b[0]:.2f}, {b[1]:.2f}) - ({b[2]:.2f}, {b[3]:.2f})" for b in r["boxes_um"]) + " |")
            L += ["", "| Region pair | Edge gap (um) |", "|---|---|"]
            for k, v in sorted(m["region_gaps_um"].items()):
                L.append(f"| {k.replace('|', ' / ')} | {v:.2f} |")
    if check_label:
        L += ["", f"## Acceptance check ({check_label})", ""]
        L.append("PASS: every target met." if not fails else "FAIL:")
        L += [f"- {f}" for f in fails]
        L += ["", f"Targets: no same-bit pair in touching/overlapping cells; every same-bit pair >= {TARGET_CENTRE_UM:g} um "
              f"centre to centre; min edge gap between any flip-flops of different copies of a group >= {TARGET_EDGE_UM:g} um; "
              f"thermal regions pairwise >= {TARGET_THERMAL_REGION_GAP_UM:g} um apart; every group member inside its region."]
    L += ["", "Geometric distances only: no radiation transport or upset-rate model is implied."]
    open(out, "w").write("\n".join(L) + "\n")


ROLE_LABEL = {
    "copyA": "Copy A of every accumulator/result pair (u_acc_a + u_res_a, lanes 0-3)",
    "copyB": "Copy B of every accumulator/result pair (u_acc_b + u_res_b, lanes 0-3)",
    "th0": "Thermal state copy 0 (u_thermal.u_copy0)",
    "th1": "Thermal state copy 1 (u_thermal.u_copy1)",
    "th2": "Thermal state copy 2 (u_thermal.u_copy2)",
}


ROLE_COLOR = {"copyA": "#00d0ff", "copyB": "#ff40c0", "th0": "#ffe000", "th1": "#60ff60", "th2": "#ff8c00"}
ROLE_SHORT = {"copyA": "COPY A", "copyB": "COPY B", "th0": "TMR copy 0", "th1": "TMR copy 1", "th2": "TMR copy 2"}


def role_of(region_name):
    m = re.search(r'(copyA|copyB|th[012])$', region_name or "")
    return m.group(1) if m else None


def regions_json(d, m, path, def_path):
    """Machine-readable region boxes and group assignment (for the 3D viewer)."""
    cells = d["cells"]
    ffs, _allc, _dup = classify(cells)
    regs = []
    grp_of_region = {g["region"]: gn for gn, g in d["groups"].items()}
    for rn, r in sorted(d["regions"].items()):
        role = role_of(rn)
        gname = grp_of_region.get(rn)
        members = d["groups"].get(gname, {}).get("members", [])
        nff = sum(1 for x in members if x in cells and "__df" in cells[x]["master"])
        regs.append({"name": rn, "group": gname, "role": role, "short_label": ROLE_SHORT.get(role, rn),
                     "label": ROLE_LABEL.get(role, rn), "color": ROLE_COLOR.get(role, "#ffffff"),
                     "type": r["type"], "box": list(r["boxes"][0]) if r["boxes"] else None,
                     "boxes": [list(b) for b in r["boxes"]], "members": len(members), "flip_flops": nff})
    role_region = {x["role"]: x["name"] for x in regs}
    flops = []
    for grp in group_order():
        for cp, bits in sorted(ffs.get(grp, {}).items()):
            for bit, box in sorted(bits.items()):
                if grp == "thermal":
                    inst, role = f"u_thermal.u_copy{cp}", f"th{cp}"
                else:
                    kind, lane = grp.split("_lane")
                    inst, role = f"g_lane[{lane}].u_lane.u_{kind}_{cp.lower()}", f"copy{cp}"
                flops.append({"inst": inst, "bit": bit, "group": grp, "copy": cp, "box": [round(v, 3) for v in box],
                              "region": role_region.get(role), "region_role": role})
    # label anchors: centroid and bounding box of each copy's flip-flops (for viewer labels)
    anchors = []
    for grp in group_order():
        for cp, bits in sorted(ffs.get(grp, {}).items()):
            bs = list(bits.values())
            if not bs:
                continue
            cx = statistics.fmean((b[0] + b[2]) / 2 for b in bs)
            cy = statistics.fmean((b[1] + b[3]) / 2 for b in bs)
            if grp == "thermal":
                text = f"thermal copy {cp}"
            else:
                kind, lane = grp.split("_lane")
                text = f"lane {lane} {'accumulator' if kind == 'acc' else 'result'} copy {cp}"
            anchors.append({"text": text, "group": grp, "copy": cp, "centroid": [round(cx, 3), round(cy, 3)],
                            "bbox": [round(min(b[0] for b in bs), 3), round(min(b[1] for b in bs), 3),
                                     round(max(b[2] for b in bs), 3), round(max(b[3] for b in bs), 3)],
                            "flip_flops": len(bs)})
    groups = {}
    for grp in group_order():
        if grp == "thermal":
            groups[grp] = {"label": "Thermal state TMR triple (2 bits x 3 copies)",
                           "copies": {c: role_region.get(f"th{c}") for c in "012"}}
        else:
            kind, lane = grp.split("_lane")
            groups[grp] = {"label": f"{'Accumulator' if kind == 'acc' else 'Result'} pair, lane {lane} (32 bits x 2 copies)",
                           "copies": {"A": role_region.get("copyA"), "B": role_region.get("copyB")}}
    acc = [p for g, gg in m["groups"].items() if g != "thermal" for p in gg["pairs"].values()]
    th = list(m["groups"]["thermal"]["pairs"].values())
    sep = {
        "accres_same_bit_centre_min_um": min(p["same_bit_centre_min_um"] for p in acc),
        "accres_same_bit_centre_median_um": statistics.median(p["same_bit_centre_median_um"] for p in acc),
        "accres_min_edge_gap_um": min(p["min_edge_gap_any_ff_um"] for p in acc),
        "copyA_vs_copyB_min_edge_gap_um": m["copyA_vs_copyB_min_edge_gap_um"],
        "thermal_same_bit_centre_min_um": min(p["same_bit_centre_min_um"] for p in th),
        "thermal_min_edge_gap_um": min(p["min_edge_gap_any_ff_um"] for p in th),
        "same_bit_touching": sum(p["same_bit_touching"] for p in acc + th),
        "region_gaps_um": m["region_gaps_um"],
    }
    out = {
        "design": "orbit_demo", "platform": "sky130hd", "units": "um",
        "source_def": def_path,
        "generator": "scripts/pdsep_separation.py",
        "mechanism": "odb dbRegion + dbGroup placement fences created at the end of the ORFS floorplan step "
                     "(pd/sky130hd_sep/regions.tcl); honoured by global_placement and every detailed_placement",
        "die_um": list(d["die"]), "core_um": list(d["core"]) if d["core"] else None,
        "regions": regs, "groups": groups, "copy_labels": anchors, "flip_flops": flops, "separation": sep,
        "unconstrained_common_mode": ["clock tree", "reset (rst_n) tree", "shared 8x8 multipliers (one per lane)",
                                      "A/B comparators and mismatch OR tree", "thermal voter and next-state logic",
                                      "input/output pins and port buffers", "unprotected phase, out_valid_q, fault_q"],
    }
    with open(path, "w") as fh:
        json.dump(out, fh, indent=1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--def", dest="defs", action="append", required=True, help="LABEL=PATH (repeatable)")
    ap.add_argument("--lef", required=True, help="merged standard-cell LEF (cell sizes)")
    ap.add_argument("--md", help="Markdown report")
    ap.add_argument("--json", help="JSON with every number")
    ap.add_argument("--check", help="label whose DEF must meet the acceptance targets")
    ap.add_argument("--regions-json", help="write region boxes + group assignment of the --check DEF (3D viewer)")
    a = ap.parse_args()
    sizes = read_lef_sizes(a.lef)
    results = {}
    for spec in a.defs:
        lab, _, path = spec.partition("=")
        if not path:
            ap.error(f"--def needs LABEL=PATH, got {spec}")
        d = read_def(path, sizes)
        if d["missing_masters"]:
            print(f"pdsep_separation: {lab}: no LEF size for {d['missing_masters'][:5]}", file=sys.stderr)
        results[lab] = {"def": path, "measure": measure(d), "die_um": d["die"], "core_um": d["core"]}
        if a.regions_json and lab == a.check:
            regions_json(d, results[lab]["measure"], a.regions_json, path)
    fails = check(results[a.check]["measure"]) if a.check else []
    if a.md:
        write_md(results, a.md, a.check, fails)
    if a.json:
        with open(a.json, "w") as fh:
            json.dump({"results": results, "check": a.check, "check_failures": fails,
                       "targets": {"same_bit_centre_min_um": TARGET_CENTRE_UM, "min_edge_gap_um": TARGET_EDGE_UM,
                                   "thermal_region_gap_um": TARGET_THERMAL_REGION_GAP_UM}}, fh, indent=1)
    for lab, r in results.items():
        m = r["measure"]
        acc = [p for grp, g in m["groups"].items() if grp != "thermal" for p in g["pairs"].values()]
        th = [p for p in m["groups"]["thermal"]["pairs"].values()]
        print(f"{lab}: {m['n_redundant_ff']} redundant FFs; acc/res same-bit centre min "
              f"{min(p['same_bit_centre_min_um'] for p in acc):.2f} um, min gap any A/B FF "
              f"{min(p['min_edge_gap_any_ff_um'] for p in acc):.2f} um; thermal same-bit min "
              f"{min(p['same_bit_centre_min_um'] for p in th):.2f} um, min gap "
              f"{min(p['min_edge_gap_any_ff_um'] for p in th):.2f} um; touching "
              f"{sum(p['same_bit_touching'] for p in acc + th)}")
    if a.check:
        print(f"acceptance check ({a.check}): " + ("PASS" if not fails else "FAIL"))
        for f in fails:
            print(f"  - {f}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
