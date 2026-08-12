"""Render native KLayout views of the reviewed GDS for the design review package.
usage: python render_gds.py <gds> <lyp> <regions.json> <layout.json> <outdir>"""
import json, sys, os
import klayout.db as db
import klayout.lay as lay

gds, lyp, regions_json, layout_json, out = sys.argv[1:6]
os.makedirs(out, exist_ok=True)
regions = json.load(open(regions_json))
parts = {p["id"]: p for p in json.load(open(layout_json))["parts"]["list"]}

def view(visible=None, overlay=None):
    v = lay.LayoutView()
    v.set_config("background-color", "#ffffff")
    v.set_config("grid-visible", "false")
    v.set_config("text-visible", "false")
    idx = v.load_layout(gds, True)
    v.load_layer_props(lyp)
    v.max_hier()
    if visible is not None:
        it = v.begin_layers()
        while not it.at_end():
            n = it.current()
            n.visible = (n.source_layer, n.source_datatype) in visible
            v.set_layer_properties(it, n)
            it.next()
    if overlay:
        ly = v.cellview(idx).layout()
        top = v.cellview(idx).cell
        li = ly.layer(db.LayerInfo(1000, 0, "review_overlay"))
        for (x0, y0, x1, y1) in overlay:
            top.shapes(li).insert(db.DBox(x0, y0, x1, y1))
        p = lay.LayerPropertiesNode()
        p.source = "1000/0@1"
        p.frame_color = 0x000000
        p.fill_color = 0x000000
        p.dither_pattern = 1  # hollow
        p.width = 3
        p.name = "review overlay: fence boxes from reports/pdsep/regions.json"
        v.insert_layer(v.end_layers(), p)
    return v

def save(v, name, box, w=2400):
    v.zoom_box(db.DBox(*box))
    bw, bh = box[2] - box[0], box[3] - box[1]
    h = max(200, int(w * bh / bw))
    path = os.path.join(out, name)
    v.save_image_with_options(path, w, h, 0, 0, 0, db.DBox(*box), False)
    print(path, w, h, box)

die = regions["die_um"]
pad = 4
full = [die[0] - pad, die[1] - pad, die[2] + pad, die[3] + pad]

METALS = {(67, 20), (67, 44), (68, 20), (68, 44), (69, 20), (69, 44), (70, 20), (70, 44), (71, 20), (71, 44), (72, 20)}
FEOL = {(64, 20), (65, 20), (65, 44), (66, 20), (66, 44), (67, 20), (67, 44), (68, 20), (93, 44), (94, 20), (95, 20)}
PDN = {(71, 20), (71, 44), (72, 20)}
LOW = {(67, 20), (67, 44), (68, 20), (68, 44), (69, 20)}
fence_boxes = [b for r in regions["regions"] for b in r["boxes"]]

save(view(), "v01_full_die_all_layers.png", full)
save(view(visible=PDN), "v02_full_die_pdn_met4_met5.png", full)
save(view(visible=LOW, overlay=fence_boxes), "v03_full_die_li1_met1_met2_with_fence_overlay.png", full)
th = [r for r in regions["regions"] if r["role"].startswith("th")]
for r in th:
    x0, y0, x1, y1 = r["box"]
    save(view(visible=FEOL | LOW, overlay=[r["box"]]), "v04_detail_thermal_fence_%s.png" % r["role"], [x0 - 6, y0 - 6, x1 + 6, y1 + 6], 2000)
save(view(visible=FEOL | LOW, overlay=[regions["regions"][0]["box"]]), "v05_detail_copyA_fence_lower_left.png", [0, 0, 70, 50], 2400)
m = parts["L0.mult"]["core_um"]
save(view(visible=LOW), "v06_detail_lane0_multiplier_region.png", [m[0] - 4, m[1] - 4, m[2] + 4, m[3] + 4], 2400)
save(view(visible=FEOL), "v07_detail_std_cell_rows_feol.png", [150, 150, 170, 162], 2400)
save(view(), "v08_detail_die_corner_lower_right_all_layers.png", [die[2] - 40, die[1] - 2, die[2] + 2, die[1] + 30], 2400)
