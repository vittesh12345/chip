# KLayout batch script: render PNG images of the final GDS.
#
# Run headless inside the ORFS image, e.g.
#   klayout -zz -r pd/render_layout.py -rd gds=6_final.gds -rd lyp=sky130hd.lyp \
#           -rd out=layout.png -rd detail_out=detail.png -rd detail_frac=0.15
#
# Variables (-rd name=value):
#   gds          input GDS (required)
#   lyp          KLayout layer properties for colours (optional)
#   out          full-chip PNG (required)
#   detail_out   optional zoomed PNG, a square window at the centre of the die
#   detail_frac  width of that window as a fraction of the die (default 0.12)
#   highlight    optional JSON list of {"name", "box": [x0, y0, x1, y1]} (um):
#                these cells are outlined in both images and the detail window
#                is centred on them instead of the die centre (and widened if
#                needed so that all of them are inside it)
#   width        image width in pixels (default 1600)
#   hide         comma separated GDS layer numbers to hide (default "81,235":
#                the sky130 areaid markers, e.g. areaid.standardc over every
#                cell, and the place-and-route boundary, which otherwise paint
#                over the whole core in the full-chip view)
#   bg           background colour (default #000000)
#
# Prints the die bounding box and the detail window so the report can say
# what the images show.

import pya

gds = globals().get("gds")
out = globals().get("out")
if not gds or not out:
    raise SystemExit("render_layout.py: need -rd gds=... -rd out=...")
lyp = globals().get("lyp", "")
detail_out = globals().get("detail_out", "")
detail_frac = float(globals().get("detail_frac", "0.12"))
width = int(globals().get("width", "1600"))

view = pya.LayoutView()
view.load_layout(gds, True)
if lyp:
    view.load_layer_props(lyp)
view.max_hier()

hide = {int(x) for x in globals().get("hide", "81,235").split(",") if x.strip()}
it = view.begin_layers()
while not it.at_end():
    lp = it.current()
    if lp.source_layer in hide:
        node = lp.dup()
        node.visible = False
        view.set_layer_properties(it, node)
    it.next()
view.set_config("background-color", globals().get("bg", "#000000"))
view.set_config("grid-visible", "false")
view.set_config("text-visible", "false")

cv = view.active_cellview()
top = cv.cell
bbox = top.dbbox()
print(f"render_layout: top cell {top.name}, bbox {bbox.left:.2f} {bbox.bottom:.2f} "
      f"{bbox.right:.2f} {bbox.top:.2f} um ({bbox.width():.2f} x {bbox.height():.2f})")

# Optional highlighted cells (e.g. the thermal TMR flip-flops).
marks = []
hl = globals().get("highlight", "")
if hl:
    import json
    for item in json.load(open(hl)):
        x0, y0, x1, y1 = item["box"]
        mk = pya.Marker(view)
        mk.set(pya.DBox(x0, y0, x1, y1))
        mk.color = 0x00ff00
        mk.frame_color = 0x00ff00
        mk.line_width = 4
        mk.vertex_size = 0
        mk.dither_pattern = 1
        # Keep a reference: a Marker disappears when its Python object dies.
        marks.append((item["name"], pya.DBox(x0, y0, x1, y1), mk))
    print(f"render_layout: highlighted {len(marks)} cells from {hl}")

# Full chip, square-ish image with the die aspect ratio.
height = max(1, int(width * bbox.height() / max(bbox.width(), 1e-9)))
view.zoom_box(bbox.enlarged(bbox.width() * 0.01, bbox.height() * 0.01))
view.save_image_with_options(out, width, height, 0, 2, 0, pya.DBox(), False)
print(f"render_layout: wrote {out} ({width}x{height})")

if detail_out:
    c = bbox.center()
    half = 0.5 * detail_frac * min(bbox.width(), bbox.height())
    if marks:
        # Centre on the highlighted cells and make the window large enough to
        # show all of them with a small margin.
        u = pya.DBox()
        for _n, b, _m in marks:
            u = u + b
        c = u.center()
        half = max(half, 0.5 * max(u.width(), u.height()) + 4.0)
    # Keep the window inside the die.
    cx = min(max(c.x, bbox.left + half), bbox.right - half)
    cy = min(max(c.y, bbox.bottom + half), bbox.top - half)
    c = pya.DPoint(cx, cy)
    win = pya.DBox(c.x - half, c.y - half, c.x + half, c.y + half)
    view.zoom_box(win)
    view.save_image_with_options(detail_out, width, width, 0, 2, 0, pya.DBox(), False)
    print(f"render_layout: wrote {detail_out}, window {win.left:.2f} {win.bottom:.2f} "
          f"{win.right:.2f} {win.top:.2f} um")
