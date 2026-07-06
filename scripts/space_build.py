#!/usr/bin/env python3
"""Build the ORBIT-AI space scroll page (site/chip-space/index.html).

1. Rasterizes the real routed layout (viz/layout.b64.txt + viz/layout.json)
   into one texture per layer group (substrate, poly, li1, met1..met5) at
   site/chip-space/tex/*.png. Vias are merged into the metal above them
   (licon1 -> li1, mcon -> met1, via -> met2, ... via4 -> met5). Metal masks
   are 8-bit greyscale coverage (anti-aliased by 4x supersampling); the page
   tints them. The substrate texture is RGBA (nwell / diff / tap in colour).
2. Pulls the placement fences, pins and verified numbers from layout.json.
3. Writes site/chip-space/index.html from site/chip-space/template.html with
   every texture inlined as a data: URI, so the page is a single file that
   can be published as an Artifact.

    build/viz/venv/bin/python scripts/space_build.py [--size 1280]
"""

import argparse
import base64
import io
import json
import os

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "site", "chip-space")
TEX_DIR = os.path.join(OUT_DIR, "tex")
EXPLORER = "https://claude.ai/artifact/5R9GAuPsfhBUXSWFermUvm"
# Real photograph from the Vantage site checkout (vantage.industries), used as context only.
# NASA iss073e0703405, Cygnus XL on final approach to the ISS; credited in the page caption.
SITE_ASSETS = os.environ.get("VANTAGE_SITE", "/home/user/vittesh12345/vantage-defense") + "/assets"
PHOTO_SRC = "segments-approach.webp"
PHOTO_MAX_W = 2000

# texture group -> GDS layers merged into it (vias fold into the metal above)
GROUPS = [
    ("poly", ["poly"]),
    ("li1", ["li1", "licon1"]),
    ("met1", ["met1", "mcon"]),
    ("met2", ["met2", "via"]),
    ("met3", ["met3", "via2"]),
    ("met4", ["met4", "via3"]),
    ("met5", ["met5", "via4"]),
]
SS = 4  # supersampling factor for coverage


def load_rects(meta):
    raw = open(os.path.join(ROOT, "viz", "layout.b64.txt"), "rb").read()
    blob = base64.b64decode(raw)
    assert blob[:8] == meta["format"]["magic"].encode(), "bad magic"
    out = {}
    for l in meta["layers"]:
        a = np.frombuffer(blob, dtype="<u2", count=l["count"] * 4, offset=l["offset"])
        out[l["name"]] = a.reshape(-1, 4).astype(np.int64)
    return out


def coverage(rects_list, die_grid, size):
    """Anti-aliased coverage (0..1) of the union of rectangles, y flipped to image rows."""
    hi = size * SS
    d = np.zeros((hi + 1, hi + 1), dtype=np.int32)
    for r in rects_list:
        if len(r) == 0:
            continue
        s = hi / die_grid
        x0 = np.floor(r[:, 0] * s).astype(np.int64)
        x1 = np.maximum(np.ceil(r[:, 2] * s).astype(np.int64), x0 + 1)
        # image rows run top-down: row = hi - y
        y0 = np.floor((die_grid - r[:, 3]) * s).astype(np.int64)
        y1 = np.maximum(np.ceil((die_grid - r[:, 1]) * s).astype(np.int64), y0 + 1)
        x0, x1, y0, y1 = (np.clip(v, 0, hi) for v in (x0, x1, y0, y1))
        np.add.at(d, (y0, x0), 1)
        np.add.at(d, (y0, x1), -1)
        np.add.at(d, (y1, x0), -1)
        np.add.at(d, (y1, x1), 1)
    c = np.cumsum(np.cumsum(d, axis=0), axis=1)[:hi, :hi] > 0
    return c.reshape(size, SS, size, SS).mean(axis=(1, 3))


def save_png(arr, name, mode):
    os.makedirs(TEX_DIR, exist_ok=True)
    path = os.path.join(TEX_DIR, name + ".png")
    Image.fromarray(arr, mode).save(path, optimize=True)
    return path


def rasterize(meta, size):
    rects = load_rects(meta)
    die_grid = int(round(meta["die_um"][2] / meta["format"]["grid_um"]))
    paths = {}
    # substrate: dark silicon with wells / diffusion / taps in colour, opaque
    nw = coverage([rects["nwell"]], die_grid, size)
    df = coverage([rects["diff"]], die_grid, size)
    tp = coverage([rects["tap"]], die_grid, size)
    base = np.array([14, 30, 34], float)
    img = np.ones((size, size, 3)) * base
    img = img * (1 - 0.55 * nw[..., None]) + np.array([34, 58, 70]) * 0.55 * nw[..., None]
    img = img * (1 - df[..., None]) + np.array([58, 150, 112]) * df[..., None]
    img = img * (1 - tp[..., None]) + np.array([150, 190, 100]) * tp[..., None]
    paths["sub"] = save_png(np.clip(img, 0, 255).astype(np.uint8), "sub", "RGB")
    for name, layers in GROUPS:
        c = coverage([rects[n] for n in layers], die_grid, size)
        a = np.clip(np.round(c * 255), 0, 255).astype(np.uint8)
        paths[name] = save_png(a, name, "L")
        print(f"  {name:5s} fill {c.mean() * 100:5.1f}%  {os.path.getsize(paths[name]) / 1e3:7.0f} kB")
    return paths


def data_uri(path):
    mime = "image/png" if path.endswith(".png") else "image/jpeg"
    with open(path, "rb") as f:
        return f"data:{mime};base64," + base64.b64encode(f.read()).decode("ascii")


def photo_uri(src_dir=None):
    """Re-encode the site photograph as a webp data URI (resized to PHOTO_MAX_W, natural
    colour, no filter). Keeps whichever of the re-encode and the site's own file is smaller."""
    path = os.path.join(src_dir or SITE_ASSETS, PHOTO_SRC)
    raw = open(path, "rb").read()
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    if im.width > PHOTO_MAX_W:
        im = im.resize((PHOTO_MAX_W, round(im.height * PHOTO_MAX_W / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "WEBP", quality=80, method=6)
    data = buf.getvalue() if len(buf.getvalue()) < len(raw) else raw
    w, h = Image.open(io.BytesIO(data)).size
    print(f"  photo {PHOTO_SRC}: {w}x{h}, {len(data) / 1e3:.0f} kB")
    return "data:image/webp;base64," + base64.b64encode(data).decode("ascii"), w, h


def scene_data(meta):
    """Geometry the page needs, in die micrometres (origin lower-left, y up)."""
    regions = {r["role"]: r["boxes"][0] for r in meta["regions"]["list"]}
    pins = [{"side": p["side"], "box": p["box"], "fam": p["fam"]} for p in meta["pins"]["list"]]
    return {
        "die": meta["die_um"][2],
        "core": meta["core_um"],
        "regions": regions,
        "pins": pins,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--size", type=int, default=1400, help="texture edge in pixels")
    ap.add_argument("--skip-raster", action="store_true", help="reuse site/chip-space/tex/*.png")
    ap.add_argument("--explorer-url", default=EXPLORER)
    ap.add_argument("--site-assets", default=SITE_ASSETS, help="vantage.industries assets/ directory")
    args = ap.parse_args()

    meta = json.load(open(os.path.join(ROOT, "viz", "layout.json")))
    names = ["sub"] + [g[0] for g in GROUPS]
    if args.skip_raster:
        paths = {n: os.path.join(TEX_DIR, n + ".png") for n in names}
    else:
        print(f"rasterizing {len(names)} layer groups at {args.size}px ...")
        paths = rasterize(meta, args.size)
    tex = {n: data_uri(paths[n]) for n in names}

    photo, pw, ph = photo_uri(args.site_assets)
    tpl = open(os.path.join(OUT_DIR, "template.html")).read()
    html = (tpl.replace("{{PHOTO}}", photo).replace("{{PHOTO_W}}", str(pw)).replace("{{PHOTO_H}}", str(ph))
               .replace("{{TEXTURES}}", json.dumps(tex))
               .replace("{{SCENE}}", json.dumps(scene_data(meta), separators=(",", ":")))
               .replace("{{EXPLORER}}", args.explorer_url))
    out = os.path.join(OUT_DIR, "index.html")
    open(out, "w").write(html)
    print(f"wrote {out} ({os.path.getsize(out) / 1e6:.2f} MB)")


if __name__ == "__main__":
    main()
