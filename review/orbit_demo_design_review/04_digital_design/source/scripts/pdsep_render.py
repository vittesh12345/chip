#!/usr/bin/env python3
"""Render the separated sky130hd layout of orbit_demo with the copy regions outlined.

Uses the standalone KLayout Python module (klayout.lay) for the layout image and
Pillow for the labels and legend. Region boxes and flip-flop boxes come from
reports/pdsep/regions.json (written by scripts/pdsep_separation.py from the
routed DEF), so the picture shows exactly what was measured.

  python scripts/pdsep_render.py --gds 6_final.gds --lyp sky130hd.lyp \
      --regions reports/pdsep/regions.json --out orbit_demo_sky130hd_sep.png
"""

import argparse
import json
import sys

import klayout.db as kdb
import klayout.lay as klay
from PIL import Image, ImageDraw, ImageFont

ROLE_STYLE = {
    "copyA": (0x00d0ff, "Copy A: u_acc_a + u_res_a, lanes 0-3"),
    "copyB": (0xff40c0, "Copy B: u_acc_b + u_res_b, lanes 0-3"),
    "th0": (0xffe000, "Thermal copy 0 (u_thermal.u_copy0)"),
    "th1": (0x60ff60, "Thermal copy 1 (u_thermal.u_copy1)"),
    "th2": (0xff8c00, "Thermal copy 2 (u_thermal.u_copy2)"),
}


def hexrgb(c):
    return ((c >> 16) & 255, (c >> 8) & 255, c & 255)


def font(size):
    for f in ("DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "LiberationSans-Bold.ttf", "Arial.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            continue
    return ImageFont.load_default()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gds", required=True)
    ap.add_argument("--lyp", default="")
    ap.add_argument("--regions", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--width", type=int, default=1400)
    ap.add_argument("--hide", default="81,235", help="GDS layer numbers to hide (areaid, prBoundary)")
    a = ap.parse_args()

    rj = json.load(open(a.regions))
    view = klay.LayoutView()
    view.load_layout(a.gds, True)
    if a.lyp:
        view.load_layer_props(a.lyp)
    view.max_hier()
    hide = {int(x) for x in a.hide.split(",") if x.strip()}
    it = view.begin_layers()
    while not it.at_end():
        lp = it.current()
        if lp.source_layer in hide:
            node = lp.dup()
            node.visible = False
            view.set_layer_properties(it, node)
        it.next()
    view.set_config("background-color", "#000000")
    view.set_config("grid-visible", "false")
    view.set_config("text-visible", "false")

    top = view.active_cellview().cell
    bbox = top.dbbox()
    x0, y0, x1, y1 = rj["die_um"]
    die = kdb.DBox(x0, y0, x1, y1)
    if abs(bbox.width() - die.width()) > 1.0:
        print(f"pdsep_render: GDS bbox {bbox} differs from the DEF die {die}", file=sys.stderr)
    tgt = die.enlarged(die.width() * 0.01, die.height() * 0.01)
    W = a.width
    H = int(round(W * tgt.height() / tgt.width()))

    view.zoom_box(tgt)
    tmp = a.out + ".tmp.png"
    view.save_image_with_options(tmp, W, H, 0, 2, 0, tgt, False)

    # dim the layout so the copies stand out, then draw flip-flops and fences on top
    img = Image.open(tmp).convert("RGB")
    img = Image.eval(img, lambda v: int(v * 0.42))
    panel_w = 570
    canvas = Image.new("RGB", (W + panel_w, max(H, 760)), (12, 14, 18))
    canvas.paste(img, (0, 0))
    d = ImageDraw.Draw(canvas)

    def px(x, y):
        return ((x - tgt.left) / tgt.width() * W, (tgt.top - y) / tgt.height() * H)

    for ff in rj["flip_flops"]:
        col = hexrgb(ROLE_STYLE.get(ff.get("region_role"), (0xffffff, ""))[0])
        bx0, by0, bx1, by1 = ff["box"]
        p0, p1 = px(bx0, by1), px(bx1, by0)
        d.rectangle((p0[0], p0[1], p1[0], p1[1]), fill=col, outline=(0, 0, 0))
    for r in rj["regions"]:
        col = hexrgb(ROLE_STYLE.get(r["role"], (0xffffff, ""))[0])
        bx0, by0, bx1, by1 = r["box"]
        p0, p1 = px(bx0, by1), px(bx1, by0)
        d.rectangle((p0[0], p0[1], p1[0], p1[1]), outline=col, width=3)

    f_lab, f_title, f_txt, f_small = font(22), font(24), font(17), font(15)
    for r in rj["regions"]:
        col = hexrgb(ROLE_STYLE.get(r["role"], (0xffffff, ""))[0])
        bx0, by0, bx1, by1 = r["box"]
        short = {"copyA": "COPY A", "copyB": "COPY B", "th0": "TMR 0", "th1": "TMR 1", "th2": "TMR 2"}[r["role"]]
        if r["role"] in ("copyA", "copyB"):
            cx, cy = px((bx0 + bx1) / 2, by1 - 6)
            anchor = "mt"
        else:
            cx, cy = px(bx1 + 3, (by0 + by1) / 2)
            anchor = "lm"
        tb = d.textbbox((cx, cy), short, font=f_lab, anchor=anchor)
        d.rectangle((tb[0] - 4, tb[1] - 3, tb[2] + 4, tb[3] + 3), fill=(0, 0, 0))
        d.text((cx, cy), short, fill=col, font=f_lab, anchor=anchor)

    # per-lane labels: centroid of each lane's 64 flip-flops (acc + res) in each copy fence
    f_anc = font(14)
    lanes = {}
    for ff in rj["flip_flops"]:
        if ff["group"] == "thermal":
            continue
        lane = ff["group"].split("_lane")[1]
        b = ff["box"]
        lanes.setdefault((lane, ff["copy"]), []).append(((b[0] + b[2]) / 2, (b[1] + b[3]) / 2))
    for (lane, cp), pts in sorted(lanes.items()):
        cx, cy = px(sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
        t = f"lane {lane}"
        tb = d.textbbox((cx, cy), t, font=f_anc, anchor="mm")
        d.rectangle((tb[0] - 3, tb[1] - 2, tb[2] + 3, tb[3] + 2), fill=(0, 0, 0), outline=(255, 255, 255))
        d.text((cx, cy), t, fill=(255, 255, 255), font=f_anc, anchor="mm")

    # gap annotation between copy A and copy B
    ra = next((r for r in rj["regions"] if r["role"] == "copyA"), None)
    rb = next((r for r in rj["regions"] if r["role"] == "copyB"), None)
    if ra and rb:
        ymid = (die.bottom + die.top) / 2 - 40
        p0 = px(ra["box"][2], ymid)
        p1 = px(rb["box"][0], ymid)
        d.line((p0, p1), fill=(255, 255, 255), width=2)
        for p in (p0, p1):
            d.line((p[0], p[1] - 8, p[0], p[1] + 8), fill=(255, 255, 255), width=2)
        gap = rb["box"][0] - ra["box"][2]
        t = f"fence gap {gap:.0f} um"
        mx = ((p0[0] + p1[0]) / 2, p0[1] - 6)
        tb = d.textbbox(mx, t, font=f_txt, anchor="mb")
        d.rectangle((tb[0] - 4, tb[1] - 3, tb[2] + 4, tb[3] + 3), fill=(0, 0, 0))
        d.text(mx, t, fill=(255, 255, 255), font=f_txt, anchor="mb")

    X = W + 20
    y = 18
    d.text((X, y), "orbit_demo on sky130hd:", fill=(235, 235, 235), font=f_title)
    y += 30
    d.text((X, y), "redundant copies in separate fences", fill=(235, 235, 235), font=f_title)
    y += 38
    d.text((X, y), f"final routed GDS; die {die.width():.1f} x {die.height():.1f} um", fill=(190, 190, 190), font=f_small)
    y += 30
    for role in ("copyA", "copyB", "th0", "th1", "th2"):
        r = next((r for r in rj["regions"] if r["role"] == role), None)
        if not r:
            continue
        col = hexrgb(ROLE_STYLE[role][0])
        d.rectangle((X, y + 2, X + 22, y + 20), outline=col, width=3)
        d.text((X + 32, y), ROLE_STYLE[role][1], fill=col, font=f_small)
        y += 22
        b = r["box"]
        d.text((X + 32, y), f"fence ({b[0]:.1f}, {b[1]:.1f}) - ({b[2]:.1f}, {b[3]:.1f}) um; {r['flip_flops']} FFs",
               fill=(170, 170, 170), font=f_small)
        y += 30
    s = rj.get("separation", {})
    y += 6
    d.text((X, y), "Measured on the routed DEF:", fill=(235, 235, 235), font=f_txt)
    y += 26
    lines = []
    if s:
        lines = [
            f"acc/res same-bit centre min {s['accres_same_bit_centre_min_um']:.1f} um",
            f"  (median {s['accres_same_bit_centre_median_um']:.1f} um)",
            f"any copy-A FF to any copy-B FF gap {s['accres_min_edge_gap_um']:.1f} um",
            f"thermal same-bit centre min {s['thermal_same_bit_centre_min_um']:.1f} um",
            f"thermal copies min gap {s['thermal_min_edge_gap_um']:.1f} um",
            f"same-bit pairs touching: {s['same_bit_touching']}",
        ]
    for ln in lines:
        d.text((X, y), ln, fill=(200, 200, 200), font=f_small)
        y += 21
    y += 12
    for ln in ["Filled boxes: the flip-flops of each copy;",
               "'lane x': centroid of lane x's 64 flip-flops (acc + res).",
               "Frames: placement fences (dbRegion/dbGroup).",
               "Layout (dimmed): final routed GDS, KLayout.",
               "Shared logic, clock and reset trees,",
               "voter and comparators are unconstrained",
               "and remain common-mode.",
               "Distances are geometry, not an upset-rate model."]:
        d.text((X, y), ln, fill=(150, 150, 150), font=f_small)
        y += 20
    canvas.save(a.out)
    import os
    os.remove(tmp)
    print(f"pdsep_render: wrote {a.out} ({canvas.size[0]}x{canvas.size[1]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
