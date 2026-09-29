#!/usr/bin/env python3
"""Physical separation of the redundant storage copies in the placed design.

The brief asks for redundant state to be separated physically (a single
particle strike can upset neighbouring cells together). The ORFS flow used
here does NOT constrain placement for that, so this script only measures what
the placer did: for every redundant bit (4 lanes x {acc, res} x 32 bits, and
the 2 thermal bits), the centre-to-centre distance between the flip-flop cells
holding its copies, read from the final DEF.

Information only (no pass/fail): it reports the distribution and the closest
copies so the reader can judge the multi-cell-upset exposure.
"""

import argparse
import math
import re
import statistics
import sys
from collections import defaultdict


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--def", dest="deffile", required=True)
    ap.add_argument("--lef", help="merged cell LEF, for cell sizes (centre instead of origin)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--boxes", help="write the thermal-copy cell boxes (JSON) for the layout detail image")
    a = ap.parse_args()

    text = open(a.deffile, errors="replace").read()
    units = int(re.search(r'UNITS DISTANCE MICRONS (\d+)', text).group(1))
    comps = re.search(r'\nCOMPONENTS \d+ ;(.*?)\nEND COMPONENTS', text, re.S).group(1)

    sizes = {}
    if a.lef:
        lef = open(a.lef, errors="replace").read()
        for m in re.finditer(r'\nMACRO (\S+)(.*?)\nEND \1', lef, re.S):
            s = re.search(r'SIZE\s+([0-9.]+)\s+BY\s+([0-9.]+)', m.group(2))
            if s:
                sizes[m.group(1)] = (float(s.group(1)), float(s.group(2)))

    pos, box = {}, {}
    for m in re.finditer(r'-\s+(\S+)\s+(\S+)\s+\+\s+(?:PLACED|FIXED)\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)\s+(\S+)', comps):
        name = m.group(1).replace('\\', '')
        w, h = sizes.get(m.group(2), (0.0, 0.0))
        x0, y0 = int(m.group(3)) / units, int(m.group(4)) / units
        pos[name] = (x0 + w / 2, y0 + h / 2)
        box[name] = (x0, y0, x0 + w, y0 + h)

    copies = defaultdict(dict)  # bit key -> copy -> (x, y)
    for name, xy in pos.items():
        m = re.match(r'^g_lane\[(\d)\]\.u_lane\.u_(acc|res)_([ab])/q\[(\d+)\]', name)
        if m:
            copies[(f"lane{m.group(1)}.{m.group(2)}", int(m.group(4)))][m.group(3)] = xy
            continue
        m = re.match(r'^u_thermal\.u_copy([012])/q\[(\d+)\]', name)
        if m:
            copies[("thermal", int(m.group(2)))][m.group(1)] = xy

    # Every bit must have all its copies (2 for acc/res, 3 thermal) placed;
    # a missing copy would otherwise be measured as a smaller group, or crash.
    incomplete = [f"{k[0]} bit {k[1]}: copies {sorted(cp)}" for k, cp in sorted(copies.items())
                  if len(cp) != (3 if k[0] == "thermal" else 2)]
    if incomplete:
        print("copy_separation: bits with missing copies: " + "; ".join(incomplete[:8]), file=sys.stderr)
        return 1

    dist = defaultdict(list)  # group kind -> [(d, key)]
    for key, cp in copies.items():
        pts = list(cp.values())
        dmin = min(math.dist(p, q) for i, p in enumerate(pts) for q in pts[i + 1:])
        kind = "thermal" if key[0] == "thermal" else key[0].split(".")[1]
        dist[kind].append((dmin, key))

    lines = ["Physical separation of redundant copies (centre-to-centre, um), from " + a.deffile.split("/")[-1],
             "Placement was NOT constrained to separate copies; these are the placer's choices.", "",
             f"{'group':8s} {'bits':>5s} {'min':>8s} {'median':>8s} {'max':>8s} {'<5um':>6s} {'<10um':>6s} {'<20um':>6s}"]
    for kind in ("acc", "res", "thermal"):
        ds = sorted(d for d, _k in dist[kind])
        if not ds:
            continue
        lines.append(f"{kind:8s} {len(ds):5d} {ds[0]:8.2f} {statistics.median(ds):8.2f} {ds[-1]:8.2f} "
                     f"{sum(d < 5 for d in ds):6d} {sum(d < 10 for d in ds):6d} {sum(d < 20 for d in ds):6d}")
    lines += ["", "(for thermal: the closest two of the three copies of each bit)", "", "Closest copies:"]
    allds = sorted((d, k) for v in dist.values() for d, k in v)
    for d, k in allds[:8]:
        lines.append(f"  {k[0]} bit {k[1]}: {d:.2f} um")
    th = sorted(dist["thermal"])
    for d, k in th:
        pts = copies[k]
        lines.append(f"  thermal bit {k[1]} copies at " +
                     ", ".join(f"copy{c} ({x:.1f}, {y:.1f})" for c, (x, y) in sorted(pts.items())))
    if a.boxes:
        import json
        tb = [{"name": n, "box": box[n]} for n in sorted(pos) if re.match(r'^u_thermal\.u_copy[012]/q\[', n)]
        with open(a.boxes, "w") as fh:
            json.dump(tb, fh, indent=1)
    text_out = "\n".join(lines) + "\n"
    open(a.out, "w").write(text_out)
    sys.stdout.write(text_out)
    n_bits = sum(len(v) for v in dist.values())
    if n_bits != 4 * 2 * 32 + 2:
        print(f"copy_separation: expected 258 redundant bits, found {n_bits}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
