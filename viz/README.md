# ORBIT-AI Die Explorer (3D layout viewer)

An interactive 3D view of the routed `orbit_demo` silicon layout, built from
the real GDS and DEF that OpenROAD-flow-scripts writes for the SkyWater
sky130hd open PDK. It is the 4-lane INT8 demonstrator, not the 16-tile
ORBIT-AI concept chip, and nothing in it is radiation-qualified.

| File | What it is |
|---|---|
| `viz/index.html` | The viewer page (three.js). Written as claude.ai Artifact content: no doctype/html/head/body tags; it loads `./layout.json` and `./layout.bin` with relative URLs. |
| `viz/layout.bin`, `viz/layout.json` | Generated layout data (committed so the page can be published as is). |
| `reports/viz/orbit_demo_sky130hd_3d.glb` | Portable 3D model (binary glTF) of the metal stack for Blender and other glTF viewers. |
| `reports/viz/redundancy_placement.md` | Measured placement of the redundant storage copies. |
| `reports/viz/viewer_*.png`, `glb_preview.png` | Headless renders of the page and of the GLB. |
| `scripts/viz_gds_to_3d.py` | GDS/DEF/LEF to `layout.bin` + `layout.json` + GLB + redundancy report. |
| `scripts/viz_shots.py` | Serves the page locally and takes the screenshots (Playwright + Chromium). |
| `mk/viz.mk` | Make targets. |

## Regenerate

```sh
make viz          # data + GLB + redundancy report from the newest routed orbit_demo
make viz-shots    # screenshots into reports/viz/
make viz-serve    # open http://localhost:8765/ in a browser
```

`make viz` reads the pd area's production run,
`$(BUILD)/pd/results/sky130hd/orbit_demo/base/6_final.{gds,def}` (`VIZ_PD_VARIANT`,
default `base` like the pd area's `PD_VARIANT`); if that does not exist yet it
takes the newest `6_final.gds` under `$(BUILD)/pd/results/sky130hd/orbit_demo/*/`
(sweep and negative-control runs live elsewhere and are never picked). The viz
targets only read the pd area. Override with
`make viz VIZ_GDS=path/6_final.gds VIZ_DEF=path/6_final.def`.

Run it again after every new pd run: the committed `viz/layout.*` describe
whichever run they were generated from (`inputs` and `generated_utc` in
`layout.json`, and the footer of the page, name it). The committed data comes
from the pd area's production run `build/pd/results/sky130hd/orbit_demo/base/`
(clock 7 ns, setup WNS +0.066 ns, 6,166 logic cells plus 1,524 tap and 10,468
fill/decap cells, 346.3 x 346.3 µm die, 722,187 drawn rectangles).

Design stats (clock, WNS, area, cell count, utilisation) come from the ORFS
run that wrote the GDS (`logs/.../6_report.json` and `results/.../6_final.sdc`),
so they always match the geometry; the pd area's summary
(`reports/pd/summary.md` or `reports/pd/sky130hd/results.md`, whichever exists)
only fills gaps and is recorded under `stats.sources`.

First use creates a Python venv in `build/viz/venv` from `viz/requirements.txt`
(klayout 0.30.12, numpy 2.4.6, playwright 1.56.0 on Python 3.11) and copies the
platform files it needs out of the ORFS image (`openroad/orfs:latest`) into
`build/viz/platform/`: `sky130_fd_sc_hd.tlef`, `sky130_fd_sc_hd_merged.lef`,
`sky130hd.lyt`, `sky130hd.lyp`. Nothing needs the container at view time.

`make viz-gcd` routes the stock ORFS sky130hd `gcd` design into
`build/viz/gcd_run/` (development data only; it has no redundant storage).

Screenshots run Chromium headless with SwiftShader (software WebGL), so each
frame of the full die takes 10-40 s. Build machines often cannot reach the
CDNs, so the harness serves the same pinned three.js release from the npm
registry tarball and the Google Fonts files locally (`--cdn` keeps the CDN
URLs). The published page itself loads three.js 0.170.0 from
`cdn.jsdelivr.net/npm/` and the IBM Plex fonts from Google Fonts.

## Data format

### layout.bin

Little-endian.

| Offset | Size | Content |
|---|---|---|
| 0 | 8 | ASCII `ORBITVZ1` |
| 8 | 4 | uint32: number of layers |
| 12 | 4 | uint32: format version (1) |
| per layer | `count * 4 * sizeof(dtype)` | rectangles, at `layers[i].offset` (4-byte aligned) |

Each rectangle is four unsigned integers `x0, y0, x1, y1` in grid units
relative to the die lower-left corner: `x_um = x * format.grid_um` (plus
`format.origin_um` for absolute DEF coordinates). `format.dtype` is `uint16`
when the die fits in 65,535 grid steps. sky130's manufacturing grid is 5 nm,
but the orbit_demo die is 346.3 µm wide, which does not fit 16 bits at 5 nm,
so the pipeline uses a 10 nm grid (coordinates rounded by at most 5 nm) and
falls back to `uint32` only for dies wider than 655 µm. The page uploads these
arrays to the GPU as they are (one instanced attribute per layer).

Rectangles come from KLayout: all shapes of a GDS layer are flattened from
the top cell, and the smaller of three decompositions is kept: the merged
region cut into horizontal slabs, into vertical slabs, or the original
shapes (boxes kept, other polygons sliced). No non-rectangular shapes occur
in sky130hd; if any did, their bounding box would be used and counted in
`non_rect_as_bbox`.

### layout.json

Main keys: `format` (above), `design`, `die_um` / `core_um` (µm, relative to
the die origin; core = bounding box of the DEF placement rows),
`stack_top_um`, `layers[]` (`name`, `gds` layer/datatype, `kind`, `color`,
`z_um`, `thickness_um`, `z_source`, `thickness_source`, `approximate`,
`count`, `offset`, `bytes`, decomposition details, `layer_map_check`),
`z_sources`, `dropped_layers`, `fe_detail_window_um` (null when every layer
is complete), `stats` (clock, WNS, area, cell count and where each came from),
`redundancy` (`groups` with the distance numbers, `flops` with every
flip-flop's name, group, copy, bit index and placed box in µm, `summary`,
`method`), `glb`, `inputs` and `tools`.

## Layers and heights

GDS layer/datatype numbers were checked against the platform's KLayout layer
map (`sky130hd.lyt`); all 16 match (`layer_map_check` in `layout.json`).

| Layer | GDS | z (µm) | thickness (µm) | Source |
|---|---|---|---|---|
| nwell | 64/20 | 0 | 0.2062 | approximate |
| diff, tap | 65/20, 65/44 | 0.2062 | 0.12 | approximate |
| poly | 66/20 | 0.3262 | 0.18 | approximate |
| licon1 | 66/44 | 0.3262 | 0.6099 (to li1) | approximate |
| li1 | 67/20 | 0.9361 | 0.10 | z: Magic; t: tech LEF |
| mcon | 67/44 | 1.0361 | 0.34 | spans li1 to met1 |
| met1 | 68/20 | 1.3761 | 0.35 | z: Magic; t: tech LEF |
| via | 68/44 | 1.7261 | 0.28 | spans met1 to met2 |
| met2 | 69/20 | 2.0061 | 0.35 | z: Magic; t: tech LEF |
| via2 | 69/44 | 2.3561 | 0.43 | spans |
| met3 | 70/20 | 2.7861 | 0.80 | z: Magic; t: tech LEF |
| via3 | 70/44 | 3.5861 | 0.435 | spans |
| met4 | 71/20 | 4.0211 | 0.80 | z: Magic; t: tech LEF |
| via4 | 71/44 | 4.8211 | 0.55 | spans |
| met5 | 72/20 | 5.3711 | 1.20 | z: Magic; t: tech LEF |

Sources:

* **Thickness of routing layers**: the platform tech LEF
  `flow/platforms/sky130hd/lef/sky130_fd_sc_hd.tlef` in the ORFS image
  (`THICKNESS` statements).
* **Height (z)**: that tech LEF has no `HEIGHT` statements, so layer bottoms
  come from the open_pdks Magic technology file for sky130
  (`sky130/magic/sky130.tech`, `extract` section, `height <layer> <z>
  <thickness>`, standard stack without ReRAM), which follows the SkyWater
  process cross-section. Magic's own thicknesses differ slightly from the LEF
  (met1/met2 0.36, met3/met4 0.845, met5 1.26 µm); both are kept in
  `layout.json` (`magic_z_thickness_um`, `tech_lef_thickness_um`).
* **Cuts** (mcon, via to via4) are drawn from the top of the metal below to
  the bottom of the metal above, so the stack has no gaps.
* **Approximate**: nwell, diff, tap, poly and licon1 use Magic's 3D-view
  values. They ignore field oxide, silicide, well depth and the real contact
  profile; treat them as a readable ordering, not a process cross-section.

The GDS carries no per-layer height, and neither the tech LEF nor Magic
models dielectrics, so nothing between the layers is drawn.

## What is dropped or reduced

* **Not drawn**: implants and marker layers (nsdm 93/44, psdm 94/20, npc
  95/20, hvtp 78/44, areaid 81/4), pin and label purposes (x/16, x/5, 64/59,
  122/16), text 83/44, poly.short 66/15, the PR boundary 235/4 (used as the
  die outline instead) and the router's blockage layer 236/0. The exact list
  for the current data is `dropped_layers` in `layout.json`.
* **Front-end detail**: kept for the whole die. The pipeline has a payload
  budget (`--bin-budget-mb`, default 7 MB); above it, diff/tap/poly/licon1/li1/mcon
  are cut to a detail window around the core centre and the window is drawn on
  the die. For the current orbit_demo run the whole die fits (722,187
  rectangles, 5.8 MB of `layout.bin`; page + data about 5.9 MB), so nothing
  is cut.
* **Colours** loosely follow the KLayout/Magic sky130 conventions (poly red,
  diff green, li1 lilac, met1 blue, met2 pink, met3 teal, met4 amber, met5
  copper); they are not the PDK's `.lyp` stipples.

## The GLB

`reports/viz/orbit_demo_sky130hd_3d.glb`: every rectangle of met1-met5 and
via-via4 as a closed box, one named mesh and material per layer
(`met1`, `via`, ...), plus a `die_substrate` slab (1 µm thick, display only).
Axes: +X = layout x, +Y = up, -Z = layout y; origin at the die centre;
1 unit = 1 µm; heights are true scale (the stack is 6.6 µm on a 346 µm die,
so it looks flat until you scale Y or zoom in; `--glb-z-scale` bakes in an
exaggeration).

To stay near 10 MB with all 148,674 boxes (10.1 MB, 9.6 MiB) it uses
`KHR_mesh_quantization` (int16 positions on a 10 nm step, the node scale
converts back to µm) and one shared index buffer. The Khronos glTF validator (gltf-validator
2.0.0-dev.3.10, run during development) reports no errors, warnings or infos,
and `make viz-shots` loads it with three.js GLTFLoader
(`reports/viz/glb_preview.png`, rendered with a ×4 vertical scale); Blender's
glTF importer and three.js/Babylon.js based web viewers support the
extension. A viewer without `KHR_mesh_quantization` support refuses the file:
`make viz VIZ_FLAGS=--glb-core` writes a plain glTF with float positions
instead (about 14.9 MB for the same content). li1, mcon, poly,
diff/tap and licon1 are left out of the GLB to keep it small (they are in the
web viewer).

## Redundant storage

Flip-flops are the DEF components whose master matches
`sky130_fd_sc_hd__{,e,s,se}df*`. Their group and copy come from the instance
names that ORFS keeps from the RTL hierarchy (docs/SPEC.md section 7), for
example `g_lane\[0\].u_lane.u_acc_a/q\[5\]$_SDFFE_PN0P_`; the bit index is
the last `[n]` after the copy name, or else the one in the Q net name. The cell
box is the DEF `PLACED` origin plus the LEF `SIZE`. For every duplicated or
triplicated group the pipeline reports the centroid distance between copies
and the minimum/median/maximum distance between the same bit in different
copies (centre to centre and edge to edge), plus how many same-bit pairs sit
in touching cells. On other designs (such as `gcd`) no groups are found and
the page says so.

For the committed data the numbers agree with the pd area's independent
measurement (`reports/pd/sky130hd/copy_separation.txt`: closest same-bit
copies 2.76 µm centre to centre, thermal 5.52 µm).

The pipeline also reads `pd/sky130hd/config.mk` (only to look for region,
fence, keep-out or spacing settings) and says in the report whether anything
asked the placer to separate copies. For the committed data nothing did, so
the distances are simply where timing and wirelength put the copies. See
`reports/viz/redundancy_placement.md` for the numbers and their reading.

## Viewer notes

* One instanced mesh per layer; the rectangle array is a per-instance vertex
  attribute and the vertex shader builds each box, so the vertical scale and
  layer spread are uniform changes. It renders on demand (no idle loop),
  caps the pixel ratio at 2, and skips camera animation when the system asks
  for reduced motion. There is no auto-rotation.
* Hovering a highlighted flip-flop shows its instance name, group, copy and
  bit (mouse only; `make viz-shots` checks this once). Choosing one group,
  or clicking its row in the table, draws lines between the same bits of
  its copies.
* Arrow keys pan when the 3D view has keyboard focus.
* WebGL 2 is required; the page says so if it is missing, and it shows a
  readable error if `layout.json`/`layout.bin` fail to load or do not match.
