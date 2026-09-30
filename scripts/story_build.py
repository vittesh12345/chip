#!/usr/bin/env python3
"""Build the ORBIT-AI scroll story page (site/chip-story/index.html).

Crops the viewer renders into site/chip-story/img/*.jpg, traces the real
floorplan (placement fences, lane multipliers and adders, thermal copies) from
viz/layout.json into SVG line-art, and writes one self-contained HTML page with
the images embedded as data URIs, ready to publish as an Artifact or drop into a
website section.

    python3 scripts/story_build.py --renders <dir with die_top.png, ...>
"""

import argparse
import base64
import io
import json
import os

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "site", "chip-story")


def die_bbox(img, bg_tol=18):
    """Bounding box of everything that differs from the corner background colour."""
    rgb = img.convert("RGB")
    w, h = rgb.size
    bg = rgb.getpixel((4, 4))
    px = rgb.load()
    xs, ys = [], []
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            p = px[x, y]
            if sum(abs(p[i] - bg[i]) for i in range(3)) > bg_tol:
                xs.append(x)
                ys.append(y)
    return min(xs), min(ys), max(xs) + 1, max(ys) + 1


def save_jpg(img, name, size, quality=82):
    img = img.convert("RGB")
    img.thumbnail((size, size), Image.LANCZOS)
    path = os.path.join(OUT_DIR, "img", name)
    img.save(path, "JPEG", quality=quality, optimize=True, progressive=True)
    return path


def data_uri(path):
    with open(path, "rb") as f:
        return "data:image/jpeg;base64," + base64.b64encode(f.read()).decode("ascii")


def prepare_images(renders):
    os.makedirs(os.path.join(OUT_DIR, "img"), exist_ok=True)
    out = {}
    top = Image.open(os.path.join(renders, "die_top.png"))
    out["die_top"] = save_jpg(top.crop(die_bbox(top)), "die_top.jpg", 1600)
    for name in ("die_tilt", "layout_parts", "package_exploded"):
        im = Image.open(os.path.join(renders, name + ".png"))
        x0, y0, x1, y1 = die_bbox(im)
        pad = 24
        box = (max(0, x0 - pad), max(0, y0 - pad), min(im.width, x1 + pad), min(im.height, y1 + pad))
        out[name] = save_jpg(im.crop(box), name + ".jpg", 1500)
    return out


def floorplan_svg(meta):
    """Line-art of the real floorplan in die micrometres (y up flipped to SVG y down)."""
    W = meta["die_um"][2]
    H = meta["die_um"][3]

    def rect(b, cls, delay):
        x0, y0, x1, y1 = b
        return (f'<rect class="{cls}" style="--d:{delay:.2f}" x="{x0:.2f}" y="{H - y1:.2f}" '
                f'width="{x1 - x0:.2f}" height="{y1 - y0:.2f}" pathLength="1"/>')

    def label(x, y, text, anchor="start", delay=0.0):
        return (f'<text class="tag" style="--d:{delay:.2f}" x="{x:.2f}" y="{H - y:.2f}" '
                f'text-anchor="{anchor}">{text}</text>')

    parts = {p["id"]: p for p in meta["parts"]["list"]}
    regions = {r["role"]: r for r in meta["regions"]["list"]}
    el = [rect([0, 0, W, H], "edge", 0.00), rect(meta["core_um"], "core", 0.04)]
    el.append(rect(regions["copyA"]["boxes"][0], "fence", 0.10))
    el.append(rect(regions["copyB"]["boxes"][0], "fence", 0.14))
    for i, role in enumerate(("th0", "th1", "th2")):
        el.append(rect(regions[role]["boxes"][0], "fence hot", 0.30 + 0.05 * i))
    for lane in range(4):
        for j, kind in enumerate(("mult", "addA", "addB")):
            el.append(rect(parts[f"L{lane}.{kind}"]["core_um"], "block", 0.42 + 0.03 * (3 * lane + j)))
    # Guide lines between the two copy fences, like a dimension.
    a = regions["copyA"]["boxes"][0]
    b = regions["copyB"]["boxes"][0]
    y = 336.0
    el.append(f'<path class="dim" style="--d:0.20" d="M{a[2]:.2f} {H - y:.2f} H{b[0]:.2f}" pathLength="1"/>')
    el.append(label((a[2] + b[0]) / 2, y + 4, f"{b[0] - a[2]:.0f} µm between copies", "middle", 0.26))
    el.append(label(a[0] + 3, a[3] - 10, "COPY A", "start", 0.18))
    el.append(label(b[2] - 3, b[3] - 10, "COPY B", "end", 0.20))
    for i, role in enumerate(("th0", "th1", "th2")):
        r = regions[role]["boxes"][0]
        el.append(label(r[2] + 3, (r[1] + r[3]) / 2 - 2, f"TMR {i}", "start", 0.40 + 0.05 * i))
    for lane in range(4):
        m = parts[f"L{lane}.mult"]["core_um"]
        el.append(label(m[0] + 2.5, m[3] - 7, f"LANE {lane} ×", "start", 0.60 + 0.04 * lane))
    return (f'<svg class="trace" viewBox="0 0 {W:.3f} {H:.3f}" preserveAspectRatio="none" '
            f'aria-hidden="true">{"".join(el)}</svg>')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--renders", required=True, help="directory with die_top.png, die_tilt.png, layout_parts.png, package_exploded.png")
    ap.add_argument("--explorer-url", default="https://claude.ai/artifact/5R9GAuPsfhBUXSWFermUvm")
    args = ap.parse_args()

    meta = json.load(open(os.path.join(ROOT, "viz", "layout.json")))
    imgs = prepare_images(args.renders)
    tpl = open(os.path.join(ROOT, "site", "chip-story", "template.html")).read()
    html = (tpl.replace("{{TRACE}}", floorplan_svg(meta))
               .replace("{{EXPLORER}}", args.explorer_url))
    for k, p in imgs.items():
        html = html.replace("{{IMG_" + k.upper() + "}}", data_uri(p))
    out = os.path.join(OUT_DIR, "index.html")
    open(out, "w").write(html)
    print(f"wrote {out} ({os.path.getsize(out) / 1e6:.2f} MB)")


if __name__ == "__main__":
    main()
