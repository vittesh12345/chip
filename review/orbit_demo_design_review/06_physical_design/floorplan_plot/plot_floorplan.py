"""Floorplan summary plot for the orbit_demo sep layout (review package 06_physical_design).

Plots package data only:
  - die/core outline, fence boxes and the 518 redundant flip-flop boxes:
      ../../07_verification/published_reports/regions.json
      (written by scripts/pdsep_separation.py from the routed 6_final.def)
  - signal pin positions and layers:  ../../08_pinout_packaging/pinout.csv
  - met4/met5 PDN strap centre lines: ../layout_db/6_final.def.gz (SPECIALNETS)
The straight line between in_a[27] and g_lane[3].u_lane.u_res_a/q[29] only joins the
two endpoints of the worst setup path (07_verification/published_reports/results.md);
it is not the routed path.

usage: python plot_floorplan.py   (writes floorplan_fences_pins.png next to this script)
"""
import csv, gzip, json, os, re
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.normpath(os.path.join(HERE, "..", ".."))
REGIONS = os.path.join(PKG, "07_verification", "published_reports", "regions.json")
PINOUT = os.path.join(PKG, "08_pinout_packaging", "pinout.csv")
DEF = os.path.join(PKG, "06_physical_design", "layout_db", "6_final.def.gz")
OUT = os.path.join(HERE, "floorplan_fences_pins.png")

# categorical slots 1-3 of the dataviz reference palette (validated, light mode)
ROLE_COLOR = {"copyA": "#2a78d6", "copyB": "#eb6834", "th": "#1baf7a"}
INK, INK2, GRID = "#0b0b0b", "#52514e", "#d9d8d4"


def role_key(role):
    return "th" if role.startswith("th") else role


def pdn_straps(path):
    """Return {(net, layer): [centre coordinate um]} for met4/met5 STRIPE shapes."""
    out = {}
    net = None
    in_special = False
    with gzip.open(path, "rt") as f:
        for line in f:
            if line.startswith("SPECIALNETS"):
                in_special = True
                continue
            if line.startswith("END SPECIALNETS"):
                break
            if not in_special:
                continue
            m = re.match(r"\s+- (\S+)", line)
            if m:
                net = m.group(1)
                continue
            m = re.search(r"(met4|met5) \d+ \+ SHAPE STRIPE \( (\S+) (\S+) \) \( (\S+) (\S+) \)", line)
            if m:
                lay, x1, y1, x2, y2 = m.groups()
                c = float(x1) / 1000 if x1 == x2 else float(y1) / 1000
                out.setdefault((net, lay), []).append(c)
    return out


def main():
    reg = json.load(open(REGIONS))
    pins = list(csv.DictReader(open(PINOUT)))
    straps = pdn_straps(DEF)
    die, core = reg["die_um"], reg["core_um"]

    fig, ax = plt.subplots(figsize=(8.2, 8.2), dpi=150)
    fig.patch.set_facecolor("#ffffff")
    ax.set_facecolor("#ffffff")

    # PDN strap centre lines (recessive)
    for (net, lay), cs in straps.items():
        for c in cs:
            if lay == "met4":
                ax.plot([c, c], [core[1], core[3]], color=GRID, lw=0.5, zorder=1)
            else:
                ax.plot([core[0], core[2]], [c, c], color=GRID, lw=0.5, zorder=1)

    ax.add_patch(Rectangle((die[0], die[1]), die[2] - die[0], die[3] - die[1], fill=False, ec=INK, lw=1.0, zorder=2))
    ax.add_patch(Rectangle((core[0], core[1]), core[2] - core[0], core[3] - core[1], fill=False, ec=INK2, lw=0.8, ls="--", zorder=2))

    # fences
    for r in reg["regions"]:
        x0, y0, x1, y1 = r["box"]
        col = ROLE_COLOR[role_key(r["role"])]
        ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fc=col, alpha=0.12, ec=col, lw=1.4, zorder=3))
        label = "%s\n(%.2f, %.2f)-(%.2f, %.2f)\n%d members, %d FFs" % (r["name"], x0, y0, x1, y1, r["members"], r["flip_flops"])
        if r["role"] in ("copyA", "copyB"):
            ax.text((x0 + x1) / 2, y1 + 5, r["name"], ha="center", va="bottom", fontsize=7.5, color=INK, zorder=6)
        else:
            ax.text(x1 + 3, (y0 + y1) / 2, label, ha="left", va="center", fontsize=6.3, color=INK, zorder=6)

    # redundant flip-flops (cell boxes from the routed DEF via regions.json)
    for f in reg["flip_flops"]:
        x0, y0, x1, y1 = f["box"]
        col = ROLE_COLOR[role_key(f["region_role"])]
        ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fc=col, ec="#ffffff", lw=0.3, zorder=4))

    # signal pins
    sig = [p for p in pins if p["use"] == "SIGNAL"]
    for lay, mk, fc in (("met3", "s", INK2), ("met2", "o", "none")):
        xs = [float(p["x_um"]) for p in sig if p["layer"] == lay]
        ys = [float(p["y_um"]) for p in sig if p["layer"] == lay]
        n = len(xs)
        ax.scatter(xs, ys, s=9, marker=mk, facecolors=fc, edgecolors=INK2, linewidths=0.6, zorder=5,
                   label="signal pins on %s (%d)" % (lay, n))

    # worst setup path endpoints
    p = next(p for p in pins if p["pin"] == "in_a[27]")
    ff = next(f for f in reg["flip_flops"] if f["inst"] == "g_lane[3].u_lane.u_res_a" and f["bit"] == 29)
    fx, fy = (ff["box"][0] + ff["box"][2]) / 2, (ff["box"][1] + ff["box"][3]) / 2
    px, py = float(p["x_um"]), float(p["y_um"])
    ax.plot([px, fx], [py, fy], color=INK, lw=0.8, ls=":", zorder=5)
    ax.text(px + 4, py, "in_a[27]", ha="left", va="center", fontsize=6.5, color=INK, zorder=6)
    ax.text(fx + 2, fy - 7, "g_lane[3].u_lane.u_res_a/q[29]", ha="left", va="top", fontsize=6.5, color=INK, zorder=6)
    ax.text((px + fx) / 2, (py + fy) / 2 + 3, "worst setup path endpoints (straight line, not the route)",
            ha="center", va="bottom", fontsize=6.3, color=INK2, zorder=6)
    for name in ("clk", "rst_n"):
        q = next(q for q in pins if q["pin"] == name)
        ax.text(float(q["x_um"]) - 4, float(q["y_um"]), name, ha="right", va="center", fontsize=6.5, color=INK, zorder=6)

    # legend proxies for fences / FFs
    for key, txt in (("copyA", "copy A fence and its FFs"), ("copyB", "copy B fence and its FFs"), ("th", "thermal copy fences and FFs")):
        ax.add_patch(Rectangle((0, 0), 0, 0, fc=ROLE_COLOR[key], alpha=0.5, ec=ROLE_COLOR[key], label=txt))
    ax.plot([], [], color=GRID, lw=1.0, label="met4 / met5 PDN strap centre lines")
    ax.plot([], [], color=INK2, lw=0.8, ls="--", label="core boundary")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.07), ncol=2, fontsize=7, frameon=False)

    ax.set_xlim(die[0] - 30, die[2] + 34)
    ax.set_ylim(die[1] - 12, die[3] + 22)
    ax.set_aspect("equal")
    ax.set_xlabel("x (um)", fontsize=8, color=INK2)
    ax.set_ylabel("y (um)", fontsize=8, color=INK2)
    ax.tick_params(labelsize=7, colors=INK2)
    for s in ax.spines.values():
        s.set_color(GRID)
    ax.set_title("orbit_demo sep: die %.3f x %.3f um, fences, redundant FFs and signal pins" % (die[2], die[3]),
                 fontsize=9, color=INK)
    fig.tight_layout()
    fig.savefig(OUT, bbox_inches="tight", pad_inches=0.15)
    print(OUT)


if __name__ == "__main__":
    main()
