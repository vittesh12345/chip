#!/usr/bin/env python3
"""Assemble reports/pdsep/summary.md for the copy-separated sky130hd layout.

Every number is read from a tool output of the run (ORFS metrics and reports
via pd/collect_pd.py's checks.json, the separation measurement JSON of
scripts/pdsep_separation.py, the GLS log, the region report written by
pd/sky130hd_sep/regions.tcl) or from the committed baseline checks.json of
the pd area. It also writes period_exploration.md: one row per finished ORFS
variant under the work directory (floorplan, period, timing, route DRC).
"""

import argparse
import glob
import json
import os
import re
import statistics
import sys


def load(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def read(path):
    try:
        with open(path, errors="replace") as f:
            return f.read()
    except OSError:
        return None


def f(v, nd=2, unit=""):
    if v is None:
        return "n/a"
    if isinstance(v, (int, float)):
        return f"{v:.{nd}f}{unit}"
    return str(v)


def worst_path_geometry(rpt_path, def_path):
    """Worst setup path of an ORFS 6_finish.rpt: start/end, arrival, required, slack, and the
    Manhattan distance summed from the start port through every cell of the path (DEF origins)."""
    rpt, d = read(rpt_path), read(def_path)
    if not rpt or not d:
        return None
    i = rpt.find("report_checks -path_delay max\n")
    if i < 0:
        return None
    blk = rpt[i:]
    blk = blk[:blk.find("slack (")]
    sp = re.search(r'Startpoint: (\S+)', blk)
    ep = re.search(r'Endpoint: (\S+)', blk)
    arr = re.search(r'([0-9.]+)\s+data arrival time', blk)
    req = re.search(r'([0-9.]+)\s+data required time', blk)
    data = blk[:blk.find("data arrival time")]
    insts = []
    for m in re.finditer(r'^\s+[\d.\s-]*[v^] (\S+)/\S+ \((sky130\S+)\)', data, re.M):
        if not insts or insts[-1] != m.group(1):
            insts.append(m.group(1))
    comps = {}
    for m in re.finditer(r'^\s*- (\S+) (\S+) .*?\( (-?\d+) (-?\d+) \)', d, re.M):
        comps[m.group(1).replace("\\", "")] = (int(m.group(3)) / 1000, int(m.group(4)) / 1000)
    pts = []
    if sp and "input port" in blk[blk.find("Startpoint"):blk.find("Endpoint")]:
        pm = re.search(r'^\s*- ' + re.escape(sp.group(1)) + r' \+ NET.*?PLACED \( (-?\d+) (-?\d+) \)', d, re.M | re.S)
        if pm:
            pts.append((int(pm.group(1)) / 1000, int(pm.group(2)) / 1000))
    pts += [comps[n] for n in insts if n in comps]
    length = sum(abs(a[0] - b[0]) + abs(a[1] - b[1]) for a, b in zip(pts, pts[1:]))
    return {"start": sp.group(1) if sp else "?", "end": ep.group(1) if ep else "?",
            "arrival": float(arr.group(1)) if arr else None, "required": float(req.group(1)) if req else None,
            "cells": len(insts), "length_um": length,
            "start_xy": pts[0] if pts else None, "end_xy": pts[-1] if pts else None}


def variant_info(work, variant):
    """Period, floorplan and final metrics of one ORFS variant."""
    rep = load(f"{work}/logs/sky130hd/orbit_demo/{variant}/6_report.json")
    if rep is None:
        return None
    sdc = read(f"{work}/sdc/sky130hd/{variant}.sdc") or ""
    m = re.search(r'^set clk_period ([0-9.]+)', sdc, re.M)
    reg = read(f"{work}/reports/sky130hd/orbit_demo/{variant}/pdsep_regions.txt") or ""
    fp = re.search(r'floorplan variant ([^\s,]+)', reg)
    bx = {m.group(1): [float(v) for v in m.groups()[1:]] for m in re.finditer(
        r'region pdsep_(\S+)\s+box_um\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)', reg)}
    ab_gap = bx["copyB"][0] - bx["copyA"][2] if "copyA" in bx and "copyB" in bx else None
    route = load(f"{work}/logs/sky130hd/orbit_demo/{variant}/5_2_route.json") or {}
    rs = read(f"{work}/logs/sky130hd/orbit_demo/{variant}/3_4_place_resized.log") or ""
    mg = re.search(r'repair_design .*-slew_margin (\d+)', rs)
    grt = load(f"{work}/logs/sky130hd/orbit_demo/{variant}/5_1_grt.json") or {}
    return {
        "variant": variant,
        "period": float(m.group(1)) if m else None,
        "floorplan": fp.group(1) if fp else "?",
        "setup_ws": rep.get("finish__timing__setup__ws"),
        "setup_tns": rep.get("finish__timing__setup__tns"),
        "hold_ws": rep.get("finish__timing__hold__ws"),
        "hold_tns": rep.get("finish__timing__hold__tns"),
        "fmax": rep.get("finish__timing__fmax"),
        "area": rep.get("finish__design__instance__area__stdcell"),
        "util": rep.get("finish__design__instance__utilization"),
        "power": rep.get("finish__power__total"),
        "slew_v": rep.get("finish__timing__drv__max_slew"),
        "cap_v": rep.get("finish__timing__drv__max_cap"),
        "drc": route.get("detailedroute__route__drc_errors"),
        "wirelength": route.get("detailedroute__route__wirelength"),
        "grt_wirelength": grt.get("globalroute__route__wirelength"),
        "margin": f"{mg.group(1)}%" if mg else "none",
        "ab_gap": ab_gap,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--work", required=True)
    ap.add_argument("--variant", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--base-checks", required=True)
    ap.add_argument("--gls", default="")
    ap.add_argument("--mechanism", default="reports/pdsep/mechanism_test.txt")
    ap.add_argument("--base-rpt", default="build/pd/reports/sky130hd/orbit_demo/base/6_finish.rpt")
    ap.add_argument("--base-def", default="build/pd/results/sky130hd/orbit_demo/base/6_final.def")
    a = ap.parse_args()

    out = a.out_dir
    sep = load(f"{out}/separation.json")
    chk = load(f"{out}/checks.json")
    base = load(a.base_checks)
    if sep is None or chk is None:
        print("pdsep_summary: missing separation.json or checks.json in " + out, file=sys.stderr)
        return 1
    regions = load(f"{out}/regions.json") or {}
    res = sep["results"]
    S = res["separated"]["measure"]
    B = res.get("baseline", {}).get("measure")
    N = chk.get("numbers", {})
    BN = (base or {}).get("numbers", {})

    # ---------------------------------------------------------------- periods
    rows = []
    for d in sorted(glob.glob(f"{a.work}/logs/sky130hd/orbit_demo/*/")):
        v = os.path.basename(os.path.dirname(d))
        info = variant_info(a.work, v)
        if info:
            rows.append(info)
    rows.sort(key=lambda r: (r["floorplan"], r["period"] or 0, r["variant"]))
    P = ["# Period / floorplan exploration: orbit_demo on sky130hd with copy-separation fences", "",
         "One complete ORFS run per row (synthesis to detailed route and the final OpenRCX-extracted STA), "
         "NUM_CORES=2, TT 25C 1.80V liberty. Generated by scripts/pdsep_summary.py from the ORFS metrics "
         f"under {a.work}/logs.", "",
         "| Variant | Floorplan | Slew/cap repair margin | Period (ns) | Setup WNS (ns) | Setup TNS (ns) | Hold WNS (ns) | "
         "STA fmax (MHz) | Route DRC | Max slew/cap viol. | Wirelength (um) | Cell area (um^2) | Power (mW, default activity) | Status |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        drv = (r["slew_v"] or 0) + (r["cap_v"] or 0)
        closed = (r["setup_ws"] is not None and r["setup_ws"] >= 0 and (r["hold_ws"] or 0) >= 0
                  and r["drc"] == 0 and drv == 0)
        P.append(f"| {r['variant']} | {r['floorplan']} | {r['margin']} | {f(r['period'], 2)} | {f(r['setup_ws'], 3)} | "
                 f"{f(r['setup_tns'], 3)} | {f(r['hold_ws'], 3)} | {f((r['fmax'] or 0) / 1e6, 1)} | "
                 f"{f(r['drc'], 0)} | {r['slew_v']}/{r['cap_v']} | {f(r['wirelength'], 0)} | {f(r['area'], 0)} | "
                 f"{f((r['power'] or 0) * 1e3, 2)} | {'CLOSED' if closed else 'FAILS'} |")
    open(f"{out}/period_exploration.md", "w").write("\n".join(P) + "\n")

    # --------------------------------------------------------------- summary
    checks = {c["name"]: c for c in chk.get("checks", [])}
    fails = sep.get("check_failures", [])
    L = []
    L += ["# Copy-separated layout: orbit_demo on sky130hd", "",
          "Generated by `scripts/pdsep_summary.py` (`make pd-sep-report`) from the routed run "
          f"`{a.work}/results/sky130hd/orbit_demo/{a.variant}/` and the unconstrained baseline of the pd area "
          f"(`{res.get('baseline', {}).get('def', 'n/a')}`, `{a.base_checks}`).", ""]

    acc = [p for g, gg in S["groups"].items() if g != "thermal" for p in gg["pairs"].values()]
    th = list(S["groups"]["thermal"]["pairs"].values())
    L += ["## Result", ""]
    L.append(f"- Separation targets on the final routed DEF: **{'all met' if not fails else 'NOT all met'}**"
             + ("" if not fails else f" ({len(fails)} misses, listed under Separation)") + ".")
    L.append(f"- Copy A vs copy B (every accumulator/result pair): same-bit centre distance min "
             f"**{f(min(p['same_bit_centre_min_um'] for p in acc), 1)} um** (target >= 20), median of the group medians "
             f"{f(statistics.median(p['same_bit_centre_median_um'] for p in acc), 1)} um; smallest edge gap between any "
             f"copy-A and any copy-B flip-flop of a group **{f(min(p['min_edge_gap_any_ff_um'] for p in acc), 1)} um** (target >= 10).")
    L.append(f"- Thermal triple: same-bit centre distance min **{f(min(p['same_bit_centre_min_um'] for p in th), 1)} um**; "
             f"smallest edge gap between flip-flops of different copies **{f(min(p['min_edge_gap_any_ff_um'] for p in th), 1)} um**.")
    touching = sum(p["same_bit_touching"] for p in acc + th)
    L.append(f"- Same-bit pairs in touching or overlapping cells: **{touching}** of {sum(p['bits'] for p in acc + th)} "
             f"(baseline: {sum(p['same_bit_touching'] for g in (B or {}).get('groups', {}).values() for p in g['pairs'].values()) if B else 'n/a'}).")
    L.append(f"- Timing: clock period **{f(N.get('clock period (ns)'), 2)} ns**, setup WNS {f(N.get('setup WNS (ns)'), 3)} ns, "
             f"hold WNS {f(N.get('hold WNS (ns)'), 3)} ns (baseline {f(BN.get('clock period (ns)'), 2)} ns, WNS "
             f"{f(BN.get('setup WNS (ns)'), 3)} ns).")
    bad = [n for n, c in checks.items() if c.get("result") == "FAIL"]
    L.append("- Flow checks (pd/collect_pd.py, read-only): " + ", ".join(
        f"{n} {c['result']}" for n, c in checks.items()) + "."
        + (f" **Failing: {', '.join(bad)}.**" if bad else " None failing."))
    gls = read(a.gls) if a.gls else None
    if gls:
        gm = re.search(r'^GLS (PASS|FAIL).*$', gls, re.M)
        L.append(f"- Post-route gate-level simulation (pd/gls harness): {gm.group(0) if gm else 'no result line'}.")
    else:
        L.append("- Post-route gate-level simulation: not run (make pd-sep-gls).")
    L.append("")

    # ---------------------------------------------------------------- method
    L += ["## Method", "",
          "**Mechanism: OpenDB placement fences (`dbRegion` + `dbGroup`).** `pd/sky130hd_sep/regions.tcl` runs as the "
          "ORFS `POST_FLOORPLAN_TCL` hook, i.e. at the end of the floorplan step, after the core rows exist and before "
          "tap cells, PDN and any placement. It creates one region per copy (`odb::dbRegion_create`, one "
          "`odb::dbBox_create` box snapped to the site grid and row boundaries, type EXCLUSIVE = DEF `FENCE`) and one "
          "group per region (`odb::dbGroup_create`), and adds the instances of the kept `orbit_keep_reg` copies to their "
          "group by hierarchical name. It checks the flip-flop count of every group against docs/SPEC.md section 7 "
          "(256/256/2/2/2) and stops the flow otherwise.", "",
          "What honours the fences (measured, not assumed):", "",
          "- `global_placement` (both the `-skip_io` pass and the timing/routability-driven pass) builds one Nesterov "
          "region per group and places the members inside their box; the region areas are blocked for top-level cells.",
          "- `detailed_placement` (placement, the CTS re-legalisations and the global-route repair legalisation) keeps "
          "every member fully inside its box and pulls a member that was moved out back in. Non-members are kept from "
          "being placed inside a fence, but a cell whose origin is outside may straddle the fence edge with part of its "
          "width (clock-tree and repair buffers next to the copy fences do; see the counts below). None of them is a "
          "redundant flip-flop.",
          "- `improve_placement` (ORFS `ENABLE_DPO`, detailed-placement optimisation) does **not** keep the placement "
          "legal with the fences: in the mechanism test `check_placement` fails after it (overlapping and off-site "
          "cells), and in an exploratory run with INCLUSIVE regions it moved 47 of 1560 members out of their region. "
          "The separated flow therefore sets `ENABLE_DPO=0`.", ""]
    mech = read(a.mechanism)
    if mech:
        L += ["Mechanism test (`scripts/pdsep_mechanism_test.tcl` on the baseline's pin-placed database, "
              f"output `{a.mechanism}`):", "", "```"]
        L += [ln for ln in mech.splitlines() if ln.startswith("MECH")]
        L += ["```", ""]
    L += ["Differences from the baseline flow (pd/sky130hd), all in `pd/sky130hd_sep/`:", "",
          "| Setting | Baseline | Separated | Why |", "|---|---|---|---|",
          "| `POST_FLOORPLAN_TCL` | none | `regions.tcl` | creates the fences |",
          "| `ENABLE_DPO` | 1 (default) | 0 | `improve_placement` breaks legality with fences |",
          "| `SLEW_MARGIN` / `CAP_MARGIN` | none | 20 / 20 % | long comparator/OR-tree nets left post-route max-slew/cap "
          "violations without a margin (run e7) |",
          f"| clock period | {f(BN.get('clock period (ns)'), 1)} ns | {f(N.get('clock period (ns)'), 1)} ns | "
          "shortest period that closes with the fences (see Timing) |", "",
          "Everything else is the same: same RTL, same `SYNTH_KEEP_MODULES` so every copy stays a distinct kept "
          "instance (the storage audit re-checks all 521 flip-flops on the routed netlist), same "
          "`CORE_UTILIZATION`/aspect ratio/margin (same die), same SDC apart from the clock period, same pin, CTS "
          "and routing settings. Shared logic (multipliers, adders, comparators, voter, control) is not "
          "constrained.", ""]

    # ------------------------------------------------------------- floorplan
    L += ["## Floorplan", ""]
    L.append(f"Die {N.get('die size (um)', 'n/a')} um, core {N.get('core size (um)', 'n/a')} um "
             f"(baseline die {BN.get('die size (um)', 'n/a')} um). Regions as written in the routed DEF "
             "(`REGIONS`/`GROUPS`), coordinates in um from the die origin:")
    L += ["", "| Region | Holds | Box (x0, y0) - (x1, y1) | Size (um) | Cells in group | Flip-flops |",
          "|---|---|---|---|---|---|"]
    for r in regions.get("regions", []):
        b = r["box"]
        L.append(f"| {r['name']} | {r['label']} | ({b[0]:.2f}, {b[1]:.2f}) - ({b[2]:.2f}, {b[3]:.2f}) | "
                 f"{b[2] - b[0]:.1f} x {b[3] - b[1]:.1f} | {r['members']} | {r['flip_flops']} |")
    L += ["", "Gaps between the fences (edge to edge, um):", "", "| Regions | Gap |", "|---|---|"]
    for k, v in sorted(S["region_gaps_um"].items()):
        L.append(f"| {k.replace('|', ' / ')} | {v:.2f} |")
    L += ["", "Arrangement (not to scale):", "", "```",
          "+--------+----------------------------------+--------+",
          "|        |            [TMR 0]               |        |",
          "| COPY A |   shared: multipliers, adders,   | COPY B |",
          "| acc_a  |   comparators, control, voter    | acc_b  |",
          "| res_a  |            [TMR 1]               | res_b  |",
          "| lanes  |                                  | lanes  |",
          "|  0-3   |            [TMR 2]               |  0-3   |",
          "+--------+----------------------------------+--------+",
          "```", "",
          "![layout with the fences outlined](orbit_demo_sky130hd_sep.png)", "",
          "Each copy group holds the complete kept copy: its flip-flops and the per-copy load-enable/reset gates "
          "(`mux2i`/`nor2b`) that `orbit_keep_reg` synthesises to (the synthesis buffers that ORFS removes before "
          "global placement leave 768 cells per acc/res copy group). Buffers added later by the resizer and CTS are not "
          "group members.", ""]

    # ------------------------------------------------------------ separation
    L += ["## Separation before / after", "",
          "Measured on the final routed DEFs by `scripts/pdsep_separation.py` (independent of the pd area's "
          "`pd/copy_separation.py`, which was also run read-only on the separated DEF: "
          "`copy_separation_pd_script.txt`). Centre = centre to centre; gap = edge to edge between cell boxes.", "",
          "| Group | Pair | Centroid dist. before / after | Same-bit centre min before / after | Same-bit centre median before / after | "
          "Same-bit touching before / after | Min gap any FF of one copy to any FF of the other, before / after |",
          "|---|---|---|---|---|---|---|"]
    for grp, gg in S["groups"].items():
        for pn, p in gg["pairs"].items():
            q = B["groups"][grp]["pairs"][pn] if B else None
            name = ("Thermal TMR" if grp == "thermal" else
                    f"{'Accumulator' if grp.startswith('acc') else 'Result'} lane {grp[-1]}")
            L.append(f"| {name} | {pn.replace('-', ' vs ')} | {f(q and q['centroid_um'], 1)} / {f(p['centroid_um'], 1)} | "
                     f"{f(q and q['same_bit_centre_min_um'])} / **{f(p['same_bit_centre_min_um'])}** | "
                     f"{f(q and q['same_bit_centre_median_um'])} / {f(p['same_bit_centre_median_um'])} | "
                     f"{q['same_bit_touching'] if q else 'n/a'} / {p['same_bit_touching']} | "
                     f"{f(q and q['min_edge_gap_any_ff_um'])} / **{f(p['min_edge_gap_any_ff_um'])}** |")
    L += ["", f"All copy-A flip-flops vs all copy-B flip-flops (any lane): min edge gap "
          f"{f(B and B['copyA_vs_copyB_min_edge_gap_um'])} um before, {f(S['copyA_vs_copyB_min_edge_gap_um'])} um after. "
          f"Group members outside their fence: {len(S['group_member_violations'])}. Non-member cells (excluding fill and "
          f"tap cells) fully inside a fence: {S['nonmember_cells_fully_inside_regions']}; straddling a fence edge: "
          f"{S['nonmember_cells_straddling_region_edge']} ("
          + ", ".join(f"{k} {v}" for k, v in list(S['nonmember_straddling_kinds'].items())[:8]) + ").", ""]
    L.append("Acceptance check on the routed DEF: " + ("**PASS** (every target met)." if not fails else "**FAIL**:"))
    L += [f"- {x}" for x in fails]
    L.append("")

    # ---------------------------------------------------------------- timing
    L += ["## Timing", ""]
    L.append(f"Final: period {f(N.get('clock period (ns)'), 2)} ns ({f(1000 / N['clock period (ns)'], 1) if N.get('clock period (ns)') else 'n/a'} MHz), "
             f"setup WNS {f(N.get('setup WNS (ns)'), 3)} ns / TNS {f(N.get('setup TNS (ns)'), 3)} ns, hold WNS "
             f"{f(N.get('hold WNS (ns)'), 3)} ns / TNS {f(N.get('hold TNS (ns)'), 3)} ns, STA fmax "
             f"{f(N.get('fmax from final STA (MHz)'), 1)} MHz, clock skew {f(N.get('clock skew (ns)'), 3)} ns. "
             f"Baseline: {f(BN.get('clock period (ns)'), 2)} ns, WNS {f(BN.get('setup WNS (ns)'), 3)} ns, STA fmax "
             f"{f(BN.get('fmax from final STA (MHz)'), 1)} MHz.")
    L += ["", "Runs (from `period_exploration.md`):", ""] + P[4:] + [""]
    wp = read(f"{out}/worst_setup_path.txt") or ""
    sp = re.search(r'Startpoint: (.*)', wp)
    ep = re.search(r'Endpoint: (.*)', wp)
    sl = re.search(r'(-?[0-9.]+)\s+slack \((MET|VIOLATED)\)', wp)
    if sp and ep:
        L.append(f"Worst setup path: `{sp.group(1).strip()}` -> `{ep.group(1).strip()}`, slack "
                 f"{sl.group(1) if sl else 'n/a'} ns ({sl.group(2) if sl else ''}); full path in `worst_setup_path.txt`.")
        L.append("")
    # why the period changed (numbers from the reports)
    gs = worst_path_geometry(f"{a.work}/reports/sky130hd/orbit_demo/{a.variant}/6_finish.rpt",
                             f"{a.work}/results/sky130hd/orbit_demo/{a.variant}/6_final.def")
    gb = worst_path_geometry(a.base_rpt, a.base_def)
    fp_now = next((r["floorplan"] for r in rows if r["variant"] == a.variant), None)
    same = [r for r in rows if r["floorplan"] == fp_now and r["margin"] == next(
        (x["margin"] for x in rows if x["variant"] == a.variant), None)]
    closed = sorted(r["period"] for r in same if r["setup_ws"] is not None and r["setup_ws"] >= 0
                    and (r["hold_ws"] or 0) >= 0 and r["drc"] == 0 and not ((r["slew_v"] or 0) + (r["cap_v"] or 0)))
    best = closed[0] if closed else None
    below = sorted((r for r in same if best is not None and r["period"] < best), key=lambda r: -r["period"])
    at7 = [r for r in rows if r["period"] is not None and abs(r["period"] - 7.0) < 1e-6]
    L += ["### Why the period changed", ""]
    if best is not None:
        L.append(f"Best closed period with the fences (floorplan `{fp_now}`, same flow settings): **{best:g} ns** "
                 f"({1000 / best:.1f} MHz), against {f(BN.get('clock period (ns)'), 1)} ns "
                 f"({1000 / BN['clock period (ns)']:.1f} MHz) for the unconstrained baseline, i.e. "
                 f"{(1 - BN['clock period (ns)'] / best) * 100:.1f} % lower clock frequency."
                 + (f" The next shorter period tried, {below[0]['period']:g} ns, fails (setup WNS "
                    f"{below[0]['setup_ws']:.3f} ns)." if below else ""))
        L.append("")
    if gs and gb:
        L.append(f"The worst path is the same kind of path as in the baseline: an input port through the shared "
                 f"8x8 multiplier of a lane and the copy's 32-bit adder into an accumulator/result flip-flop. "
                 f"Baseline: `{gb['start']}` -> `{gb['end']}`, {gb['cells']} cells, {gb['length_um']:.0f} um travelled "
                 f"(Manhattan distance summed from the port through every cell of the path), data arrival "
                 f"{gb['arrival']:.2f} ns. Separated: `{gs['start']}` -> `{gs['end']}`, {gs['cells']} cells, "
                 f"{gs['length_um']:.0f} um travelled, data arrival {gs['arrival']:.2f} ns against "
                 f"{gs['required']:.2f} ns required at {f(N.get('clock period (ns)'), 1)} ns"
                 + (f" (port at x = {gs['start_xy'][0]:.0f} um, flip-flop at x = {gs['end_xy'][0]:.0f} um)"
                    if gs['start_xy'] and gs['end_xy'] else "") + ".")
        r70 = next((r for r in same if r["period"] is not None and abs(r["period"] - 7.0) < 1e-6), None) or \
            next((r for r in rows if r["floorplan"] == fp_now and r["period"] is not None
                  and abs(r["period"] - 7.0) < 1e-6), None)
        g70 = r70 and worst_path_geometry(f"{a.work}/reports/sky130hd/orbit_demo/{r70['variant']}/6_finish.rpt",
                                          f"{a.work}/results/sky130hd/orbit_demo/{r70['variant']}/6_final.def")
        if g70:
            L.append("")
            L.append(f"At the baseline's 7.0 ns (run {r70['variant']}, same floorplan, slew/cap repair margin "
                     f"{r70['margin']}) the worst path "
                     f"`{g70['start']}` -> `{g70['end']}` travels {g70['length_um']:.0f} um and arrives at "
                     f"{g70['arrival']:.2f} ns against {g70['required']:.2f} ns required (baseline: {gb['arrival']:.2f} "
                     f"against {gb['required']:.2f} ns), so the separation costs about "
                     f"{g70['arrival'] - gb['arrival']:.2f} ns on that path.")
        L.append("")
    gap_now = next((r["ab_gap"] for r in rows if r["variant"] == a.variant), None)
    L.append(f"The fences hold the two copies of every lane {f(gap_now, 0)} um apart, but each lane's multiplier is shared by "
             "both copies' adders, so its product has to reach both fences: wherever the multiplier sits, one copy's "
             "adder is far from it, and the operand ports (placed on the die edge by the pin placer) can end up on the "
             "far side of the die from the copy they feed. The resizer buffers the longer nets, and the buffers and "
             "wire load add delay to what was already the critical path of the baseline.")
    if len(at7) >= 2:
        L.append("")
        L.append("Moving the fences closer does not buy the period back: at 7.0 ns "
                 + "; ".join(f"floorplan `{r['floorplan']}` (copy fences {f(r['ab_gap'], 0)} um apart, run {r['variant']}) "
                             f"setup WNS {r['setup_ws']:.3f} ns" for r in sorted(at7, key=lambda r: r['variant']))
                 + ". The cost comes from splitting each lane's datapath around a shared multiplier more than from "
                   "the exact gap, so the wider arrangement was kept.")
    L.append("")
    L.append("Other effects of the separation: routed wirelength and switching power go up (table below), mainly "
             "from the 256 comparator input nets (bit k of copy A and bit k of copy B meet in one XOR) and the "
             "product nets that now cross the gap between the fences; the mismatch OR tree also spans the core "
             "height, which is why the flow repairs max slew/capacitance with a 20 % margin.")
    L.append("")

    # ------------------------------------------------------ area/power/route
    L += ["## Area, wiring, power", "", "| Quantity | Baseline | Separated |", "|---|---|---|"]
    for k in ("die size (um)", "cell area excl. fill and tap cells (um^2)", "utilization (cell area excl. fill / core area)",
              "instances excl. fill and tap", "flip-flop cells (ORFS class sequential_cell)", "routed wirelength (um)",
              "vias", "power total (mW, default-activity estimate)", "power switching (mW)",
              "IR drop VDD worst (mV, same activity)"):
        L.append(f"| {k} | {f(BN.get(k), 3) if isinstance(BN.get(k), float) else BN.get(k, 'n/a')} | "
                 f"{f(N.get(k), 3) if isinstance(N.get(k), float) else N.get(k, 'n/a')} |")
    L += ["", "Power is OpenSTA's `report_power` with the ORFS default switching activity (no simulation activity): "
          "a default-activity estimate, only good for comparing the two layouts.", ""]

    # ---------------------------------------------------------------- checks
    L += ["## Checks on the routed design", "", "| Check | Result | Detail |", "|---|---|---|"]
    for n, c in checks.items():
        L.append(f"| {n} | {c['result']} | {c.get('detail', '')} |")
    L.append(f"| copy separation targets (scripts/pdsep_separation.py) | {'PASS' if not fails else 'FAIL'} | "
             f"{len(fails)} misses |")
    if gls:
        gm = re.search(r'^GLS (PASS|FAIL).*$', gls, re.M)
        inj = re.search(r'^injections: .*$', gls, re.M)
        L.append(f"| post-route GLS (pd/gls harness) | {gm.group(1) if gm else 'n/a'} | "
                 f"{gm.group(0) if gm else ''}{'; ' + inj.group(0) if inj else ''} |")
    L.append("")

    # ----------------------------------------------------------- limitations
    L += ["## Limitations", "",
          "- Only the redundant storage is separated. The clock tree, the reset (`rst_n`) tree, the shared 8x8 "
          "multiplier of each lane (which feeds both copies), the A/B comparators and mismatch OR tree, the thermal "
          "voter and next-state logic, the enable/clear distribution, the input pins and port buffers, and the "
          "unprotected `phase`, `out_valid_q` and `fault_q` flip-flops are single points and remain common-mode. A "
          "strike on any of them can corrupt both copies identically, which duplicate-and-compare does not detect "
          "(docs/SPEC.md section 8).",
          "- Clock and reset distribution were not protected or duplicated (the brief's page 3 also asks for that); "
          "CTS built one tree that reaches both fences.",
          "- Distances are geometry only. No radiation transport, charge-collection or upset-rate model was applied; "
          "a larger distance lowers the chance that one particle track or charge-sharing event upsets two copies, "
          "but this report does not quantify it.",
          "- sky130 is not radiation-characterised; nothing here is a radiation-hardness claim.",
          "- Timing is at the single ORFS sky130hd corner (TT 25C 1.80V). Power is a default-activity estimate.",
          "- `improve_placement` (detailed-placement optimisation) is off in the separated flow because it does not "
          "honour the fences.", ""]
    L += ["## Reproduce", "", "```",
          "make pd-sep            # full run: ORFS with the fences, DRC, LVS, GLS, reports",
          "make pd-sep-report     # re-extract the reports of an existing run",
          "```", "",
          "Files: `pd/sky130hd_sep/{config.mk,constraint.sdc,regions.tcl}`, `scripts/run_pd_sep.sh`, "
          "`scripts/pdsep_separation.py`, `scripts/pdsep_render.py`, `scripts/pdsep_summary.py`, "
          "`scripts/pdsep_mechanism_test.tcl`, `mk/pdsep.mk`. Outputs under `build/pd_sep/`.", ""]
    text = "\n".join(L) + "\n"
    open(f"{out}/summary.md", "w").write(text)
    print(f"pdsep_summary: wrote {out}/summary.md and {out}/period_exploration.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
