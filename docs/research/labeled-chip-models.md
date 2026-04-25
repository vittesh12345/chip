# Labeled chip models: design guide for the ORBIT-AI die explorer

**Status (2026-09-29): the labeled version is not built yet.** The current
viewer (`viz/index.html`) labels layers and highlights flip-flops by copy. It
has no part labels or part tree, and the GLB has no named parts. This guide is
the spec for the labeled version. It combines four surveys (labeled die shots,
layout viewers, CAD drawing conventions, web 3D annotation) with measurements
of our own routed data. **The builder's requirements are the numbered list in
§5, "Implementation brief", at the end.**

## 0. What our data can label (measured on the committed `base` run)

Sources: `build/pd/results/sky130hd/orbit_demo/base/6_final.{def,v,gds}` and
`viz/layout.json`. The logic rows add up to the 6,166 logic cells the viewer
reports; the DEF has 18,158 components in all.

| Part group | How we know | Cells | FFs |
|---|---|---|---|
| Accumulator A/B and result A/B, ×4 lanes | instance names: flops `g_lane[i].u_lane.u_{acc,res}_{a,b}.q[n]$_SDFFE_PN0P_`, enable logic `g_lane[i].u_lane.u_acc_a/_NNN_` (512 each of `dfxtp_1`, `mux2i_1`, `nor2b_1`, plus 3 `buf_4`) | 1,539 | 512 |
| Thermal copies 0/1/2 | `u_thermal.u_copyN.q[n]$…` and `u_thermal.u_copyN/_NNN_` | 24 | 6 |
| `fault_q`, `out_valid_q`, `u_thermal.phase` | top-level names | 3 | 3 |
| Multipliers, adders, compare/fault, voter, handshake | **anonymous `_NNNN_` cells** (synthesis flattened them) | 3,390 | 0 |
| Timing-repair buffers `place*` (803), `rebuffer*` (66), `clone*` (2) | resizer name prefix (inferred) | 871 | 0 |
| Port buffers `input*` (79), `output*` (135) | name prefix | 214 | 0 |
| Clock tree: `clkbuf_*` (68), `clkload*` (55) | CTS name prefix | 123 | 0 |
| Antenna diodes | `ANTENNA_*` | 2 | 0 |
| Tap cells / fill cells (`fill_1/2/4/8`) | master name; in DEF and GDS only, not in `6_final.v` | 1,524 / 10,468 | – |

Name separators are mixed: `.` inside flattened register names and `/` before
Yosys-numbered cells. Split on both, and strip `[n]` and the `$_…_` suffix,
when building the tree. The `orbit_keep_reg` modules exist in the synthesis
netlist `1_2_yosys.v`; `6_final.v` is flat (`module orbit_demo` only) and
carries the hierarchy only in these names. `6_final.v` uses 137 masters (74
cell functions).

**The adders, multipliers, voter and compare logic have no names.** A
throwaway prototype sorted each anonymous cell by the registers and ports in
its fan-in and fan-out cones in `6_final.v`. It found:

* multiplier: 196–198 cells per lane
* adder A: 262–274 per lane
* adder B: 259–266 per lane
* compare/fault: 370
* voter/next-state: 11
* other control: 103

Mark all of these groups as **inferred**. This run has no decap cells and no
`hold*` buffers, so the legend should not list either.

Other measured facts:

* **Only the lanes and the thermal block are compact.** Box holding the 10th
  to 90th percentile of cell positions, as a share of the die: lanes 12–15%
  each, thermal 0.4%, clock tree 37%, timing-repair buffers 51%, anonymous
  logic 53%, port buffers 92%. The spread groups all have centroids within
  10 µm of the die centre, so a centroid label would stack them on top of each
  other. The clock root `clkbuf_0_clk` (`clkbuf_16`) is at (172, 169) µm.
* **Lanes sit roughly in quadrants.** Flip-flop centroids are L0 (115, 95) µm
  SW, L1 (241, 104) SE, L2 (242, 243) NE and L3 (101, 230) NW. Their bounding
  boxes overlap by about 30 µm at the centre lines, and copies A and B
  interleave (`reports/viz/viewer_redundancy.png`).
* **The six thermal flip-flops are in a strip on the west edge** (cell boxes
  x 7.8–29.4, y 176.8–225.8 µm), just north of `fault_q`, `out_valid_q` and
  `phase` (y 155–171). A `dfxtp_1` is 7.36 × 2.72 µm, about 19 × 7 px in the
  default view.
* **The 215 signal pins are spread over all four edges** (the DEF's 217 also
  counts the VDD/VSS pins on the met5 straps).
  * N 47 (met2): `out_data` 31, `in_a` 8, `in_b` 8.
  * S 53 (met2): `out_data` 36, `in_a` 8, `in_b` 8, `clear_fault`.
  * E 67 (met3): `out_data` 33, `in_a` 16, `in_b` 16, `fault`, `in_first`.
  * W 48 (met3): `out_data` 28, `clk`, `rst_n`, all handshake, temperature
    and thermal pins. No edge holds a single bus.
* **Routing shapes carry their net name** in GDS property 1 (standard-cell
  instances carry their instance name in property 1 as well). The power nets
  are `VDD`/`VSS`. met5 is all power, but met4 is not: of its 116 top-level
  wires, 25 are VDD/VSS, 51 clock and 40 signal. Select the power grid by net
  name, not by layer.
* **The base run has no placement regions.** The `sky130hd_sep` variant sets
  fences copyA, copyB and th0/1/2 in `pd/sky130hd_sep/regions.tcl`.
* **There are 125 cell rows**, each 2.72 µm tall with a 0.46 µm site pitch.

## 1. What well-labeled chip models have in common

1. **Colour for category, text for identity, about 8 categories at most.** See
   [TPU v1 Fig. 2](https://arxiv.org/pdf/1704.04760) (4 colours, % of die per
   category), the
   [Tiny Tapeout mux](https://github.com/TinyTapeout/tt-multiplexer/blob/main/docs/INFO.md)
   (4-entry legend) and the
   [OpenROAD web GUI](https://github.com/The-OpenROAD-Project/OpenROAD/tree/master/src/web)
   (31-colour module palette).
2. **A label shows only if it fits; deeper levels appear with zoom.** OpenROAD
   draws a cell name only if the text ascent is at least 10 px, the text is no
   taller than half the cell, and it is elided to 90% of the cell width
   ([`renderThread.cpp`](https://github.com/The-OpenROAD-Project/OpenROAD/blob/master/src/gui/src/renderThread.cpp),
   `drawTextInBBox`).
   [ChipAnnotationViewer](https://github.com/misdake/ChipAnnotationViewer) and
   [Potree](https://github.com/potree/potree/blob/develop/src/Annotation.js)
   (children collapse below 100 px) do the same.
3. **Picking a cell shows its record in a panel, not 3D text.** See the
   `instance ( cell )` breadcrumb and `setColorAt` highlight in the
   [Tiny Tapeout GDS viewer](https://github.com/TinyTapeout/tinytapeout_gds_viewer).
4. **A repeat is defined once and marked by index.** See the
   [WikiChip Skylake-SP tiles](https://fuse.wikichip.org/news/1017/isscc-2018-intels-skylake-sp-mesh-and-floorplan/)
   and SOLIDWORKS
   ["Ignore multiple instances"](https://help.solidworks.com/2021/english/SolidWorks/sldworks/hidd_dve_auto_balloon.htm).
5. **Real geometry gets an outline or a translucent tint, and text over it
   gets a background.** Solid fills are for schematics only.
   [Zero to ASIC](https://github.com/mattvenn/zero_to_asic_mpw6/blob/master/pics/multi_macro_annotated.png)
   shows the failure: bare black text over routing, and labels that run into
   the neighbouring box.
6. **Balloons are keyed to a parts list, with short leaders that never cross.**
   See [ISO 6433:2012](https://www.iso.org/standard/51527.html) and
   [Hartmann et al.](https://www.researchgate.net/publication/259323227_Label_Layout_for_Interactive_3D_Illustrations).
7. **Scale and exaggeration are always stated.** The
   [SKY130 metal stack](https://github.com/google/skywater-pdk/blob/main/docs/_static/metal_stack.svg)
   says "(Diagram not to scale!)", and
   [KLayout 2.5D](https://github.com/KLayout/klayout/blob/master/src/doc/doc/about/25d_view.xml)
   has a z-zoom slider separate from the overall zoom.
8. **Labels show where they come from.** Inferred labels carry a "?" in the
   [Lunar Lake annotation](https://www.tomshardware.com/pc-components/cpus/intel-lunar-lake-cpu-gets-die-annotation-four-skymont-e-cores-slightly-bigger-than-one-lion-cove-p-core).
   The [Caravel floorplan](https://github.com/efabless/caravel/blob/main/docs/source/_static/caravel_floorplan.jpg)
   uses RTL names.
9. **Names go into the exported file.** See the named instance nodes and
   `extras.type` in [GDS2glTF](https://github.com/mbalestrini/GDS2glTF).
10. **Declutter is greedy by priority, throttled and faded.** The
    [MapLibre collision index](https://github.com/maplibre/maplibre-gl-js/blob/main/src/symbol/collision_index.ts)
    uses a 25 px grid with 100 px viewport padding and fades over 300 ms.
    Madsen et al. (TVCG 2016) found that users prefer labels that update at a
    limited rate.

## 2. Example gallery

| Example | Type | Borrow |
|---|---|---|
| [Caravel floorplan](https://github.com/efabless/caravel/blob/main/docs/source/_static/caravel_floorplan.jpg) | sky130 floorplan | nested outlines, RTL names, letter key for tiny blocks |
| [Zero to ASIC MPW6](https://github.com/mattvenn/zero_to_asic_mpw6/blob/master/pics/multi_macro_annotated.png) ([script](https://github.com/mattvenn/multi_project_tools/blob/main/collect.py), `annotate_image`) | auto-annotated layout | 2 px outlines and labels generated from placement; 200 µm scale bar; its unhaloed text and label collisions are failures to avoid |
| [Tiny Tapeout mux diagram](https://github.com/TinyTapeout/tt-multiplexer/blob/main/docs/INFO.md) | schematic floorplan | solid category fills, 4-entry legend, repeated user tiles in neutral grey |
| [Tiny Tapeout GDS viewer](https://github.com/TinyTapeout/tinytapeout_gds_viewer) | three.js, sky130 | breadcrumb, `setColorAt`, keys 1 (filler), 3 (isolate/back), 4 (zoom), Esc, arrows (tree walk), B&W depth mode |
| [tiny-explorer](https://github.com/TinyTapeout/tiny-explorer) | WebGL2 instanced boxes | per-instance ID attribute, dim-the-rest, part list sorted by area |
| [OpenROAD web GUI](https://github.com/The-OpenROAD-Project/OpenROAD/tree/master/src/web) (`src/hierarchy-browser.js`) | P&R viewer | 31-colour module palette, collapsed node colours its subtree, tree synthesized from instance names (`NAME_GROUP`), instance count and area per node. [PR 11122](https://github.com/The-OpenROAD-Project/OpenROAD/pull/11122) (Instance Groups view) is still open. |
| [OpenROAD Qt GUI](https://github.com/The-OpenROAD-Project/OpenROAD/blob/master/src/gui/README.md) | P&R viewer | cell-type taxonomy; 10 px / half-height / 90%-width text rule |
| [ChipAnnotationViewer](https://github.com/misdake/ChipAnnotationViewer) | die-shot annotator | polygons, polylines and labels exported as JSON; real areas and lengths |
| [TPU v1 floorplan](https://arxiv.org/pdf/1704.04760) | paper figure | 4 category colours; caption gives % of die (buffers 37%, compute 30%, I/O 10%, control 2%) |
| [Locuza die walkthrough](https://locuza.substack.com/p/die-walkthrough-alder-lake-sp-and) | die shots | zoom from die to core to unit; same tint for the same role |
| [GDS2glTF](https://github.com/mbalestrini/GDS2glTF) | GDS to glTF | named instance nodes, `extras.type` = master, one material per layer. It reads names from GDS property 61; our GDS stores them in property 1. |
| [glTF spec](https://github.com/KhronosGroup/glTF/blob/main/specification/2.0/Specification.adoc), [GLTFLoader](https://github.com/mrdoob/three.js/blob/dev/examples/jsm/loaders/GLTFLoader.js), [Blender importer](https://github.com/KhronosGroup/glTF-Blender-IO/blob/main/addons/io_scene_gltf2/blender/imp/vnode.py) | file format | name and `extras` rules; empty nodes as group headers |
| [SKY130 metal_stack.svg](https://github.com/google/skywater-pdk/blob/main/docs/_static/metal_stack.svg) | PDK cross-section | named conductors, vias and dielectrics; z ruler; "not to scale" |
| [GDS3D](https://github.com/trilomix/GDS3D), [KLayout 2.5D](https://github.com/KLayout/klayout/blob/master/src/doc/doc/about/25d_view.xml) with the [sky130 script](https://github.com/efabless/sky130_klayout_pdk/blob/main/tech/sky130/d25/sky130.lyd25) | 3D layout viewers | z-zoom separate from explode; legend from the layer table; grey-out-except-selection. KLayout gives about 100k polygons as its practical limit, a seventh of our 720k. |
| [ISO 6433:2012](https://www.iso.org/standard/51527.html), [SOLIDWORKS Auto Balloon](https://help.solidworks.com/2021/english/SolidWorks/sldworks/hidd_dve_auto_balloon.htm) | CAD drawing rules | balloon numbers keyed to BOM rows; one balloon per repeated part; square or circular balloon layouts |
| [Sketchfab annotations](https://help.sketchfab.com/hc/en-us/articles/202512456-Annotations), [model-viewer](https://github.com/google/model-viewer/blob/master/packages/model-viewer/src/three-components/ModelScene.ts) | web 3D | numbered stops with saved cameras (10 per model on Basic, 20 on Pro); model-viewer hides a hotspot when its normal faces away |
| [MapLibre collision index](https://github.com/maplibre/maplibre-gl-js/blob/main/src/symbol/collision_index.ts) | map labels | priority greedy placement, candidate anchors, 300 ms fade |
| [Potree annotations](https://github.com/potree/potree/blob/develop/src/Annotation.js) | point-cloud viewer | collapse by pixel threshold (100 px); 500 ms Quartic-out fly-to; 0.5/0.8 label opacity |
| three.js [CSS2D](https://github.com/mrdoob/three.js/blob/dev/examples/css2d_label.html), [ViewHelper](https://github.com/mrdoob/three.js/blob/dev/examples/jsm/helpers/ViewHelper.js), [multi-view](https://github.com/mrdoob/three.js/blob/dev/examples/webgl_multiple_views.html) | library examples | DOM label overlay, orientation gizmo (Y-up only, see §3.12), inset viewport |
| [gds_3d_viewer](https://github.com/lkqiao/gds_3d_viewer) | three.js layout viewer | clip-plane section; one pick per frame; tiny objects left out of picking |

## 3. Rules for our model

### 3.1 One part table drives everything
- The pipeline (`scripts/viz_gds_to_3d.py`) writes `parts[]` into
  `layout.json`: `id`, `item`, `name`, `category`, `lane`, `cells`, `ffs`,
  `area_um2`, `bbox_um`, `spread_pct` (10th–90th percentile box as % of die),
  `compact` (`spread_pct` ≤ 20), `anchor_um`, `source`
  (`instance-name` | `name-prefix` | `netlist-cone`).
- `anchor_um` is the centre of the part's densest 10 µm bin, not its
  centroid. Parts interleave, so a centroid can land on another part's cells.
- It also writes a per-cell array for all 18,158 DEF components: box as four
  uint16 on the existing 10 nm grid, master index, part index. That is about
  11 bytes per cell, about 200 kB.
- Labels, colours, the inspector, the parts list and the GLB all read from this
  one table.
- Report the number of unassigned cells, and show them in the legend as
  "Other logic". Never hide them.

### 3.2 Label tiers and level of detail
Base the tiers on how large a part appears on screen, not on camera distance,
because the exaggeration and spread sliders change what the camera sees. The
default isometric view shows about 2.5 px per µm on a 1440×900 screen and about
1 px per µm on a phone.

| Tier | Labels | Shown when |
|---|---|---|
| 0 | Lane 0–3, Thermal TMR, Power grid, 4 pin-edge badges (10), plus Compare/fault and Control only if `compact` | always, in the part colour modes |
| 1 | a lane's 7 sub-parts; thermal copies 0/1/2 and the voter | lane selected, or lane ≥ 600 px wide on screen (fades in from 450 px) |
| 2 | bit index inside each flip-flop of the selected part | text fits OpenROAD's rule (§1.2) at 11 px, which for a 2.72 µm-tall `dfxtp_1` needs about 10 px/µm, 4× the default zoom |
| 3 | any cell | hover or tap inspector only (§3.11) |

- **Spread parts get no floating label.** A part that is not `compact` (clock
  tree, port buffers, timing-repair buffers, and any inferred group that
  measures as spread) appears only in the legend and parts list. Selecting it
  highlights its cells. The clock tree also highlights clock-net routing
  (§3.15) and gets a label at `clkbuf_0_clk` while it is selected.
- **Tier 2 is not DOM.** Draw it on one 2D canvas over the WebGL canvas. The
  cells do not overlap, so it needs no collision pass and does not count
  against the label budget.

### 3.3 Label and leader style
- **Where labels go**, tried in this order:
  1. Inside the part, at `anchor_um`, when the text fits in the part's
     projected 10–90% box.
  2. Otherwise, if the anchor is within 25% of the die width of an edge, in
     the margin outside that edge, with a leader. Order the margin labels
     along the edge by their anchors' position, so straight leaders cannot
     cross.
  3. Otherwise, as a 24 px numbered balloon next to the anchor, with a leader
     of at most 40 px. The full name is in the parts list.
- **Leaders.** Draw leaders as 1 px SVG lines. End a leader with a 5 px dot
  when it points into a part, and with an arrowhead when it points to an edge
  (pins, die outline). Keep leaders oblique.
- **Anchor height.** Anchor labels on the top face of the tint layer (§3.6) at
  the anchor, and recompute it in `applyZ()`. Do not anchor at the stack top
  (the flip-flop highlight's height): at ×3 and 36° elevation that shifts the
  anchor the equivalent of about 23 µm on screen from the cells it names.
- **Type.** Tier 0 is 13–14 px semibold, tier 1 is 12 px, and nothing is
  smaller than 11 px. Labels sit on a panel-coloured background at ≥ 85%
  opacity (text contrast ≥ 4.5:1). Inferred parts get a dashed outline and an
  "inferred" tag.

### 3.4 Numbered balloons and parts list (BOM)
Number the parts in tree order and keep the same numbers in every view.
Balloon lane 0 only, with Qty ×4:

1 Lane · 2 Multiplier · 3 Adder A · 4 Adder B · 5 Accumulator A · 6 Accumulator B · 7 Result A · 8 Result B · 9 Thermal copies · 10 Voter/next-state · 11 Compare/fault · 12 Control (handshake/output) · 13 Clock tree · 14 Port buffers · 15 Timing-repair buffers · 16 Pins · 17 Power grid · 18 Tap + fill · 19 Cell rows · 20 Other logic (only if any cells are unassigned)

- **Table columns:** Item | Part | Qty | Cells | FFs | Area µm² (%) | Source.
- **Area percentage.** State the denominator, for example "placed cell area
  from DEF+LEF, fill excluded".
- **Linking.** Hovering a table row highlights both the part and its balloon.
- **Balloons.** Draw balloons as 24 px circles. Use them for small parts, on
  phones and in the screenshot preset.

### 3.5 Part colours vs layer colours
The layer palette already uses almost every hue. Every one of today's six
highlight tokens is within CIEDE2000 ΔE ≈ 11 of a layer colour in at least one
theme, where about 10 is still hard to tell apart:

| Highlight token | Nearest layer colour (ΔE00, light / dark theme) |
|---|---|
| `--unprot` | poly (4.7 / 10.3) |
| `--copy-b` | met5 (5.9 / 11.3) |
| `--tmr-0` | mcon 10.5 (light), li1 5.0 (dark) |
| `--tmr-1` | met2 (10.0 / 6.5) |
| `--tmr-2` | diff (7.9 / 8.7) |
| `--copy-a` | met1 (9.5 / 7.9) |

Rules:

- **One "Color by" switch** with four modes: Layer (today) | Function | Lane |
  Copy (today's redundancy mode). Only one hue channel is active at a time.
- **In every mode except Layer:**
  - draw the layers as a grey depth ramp, extending today's "Fade the layout
    while highlighting";
  - draw met2 at about 35% opacity and met3–met5 at about 15%, because the
    straps hide the cells (`viewer_iso.png`).
- **Function mode uses 8 tokens,** each defined for light and dark themes:
  - storage
  - arithmetic
  - redundancy checking (compare/voter)
  - control
  - clock tree
  - port buffers
  - timing-repair buffers
  - physical-only (grey)

  Keep every pair of tokens at least ΔE00 15 apart, and each token at least
  ΔE00 20 from every grey in the ramp. Check the palette with a
  colour-blindness simulator. Every legend entry shows its count.
- **Lane mode** gives each lane one hue and draws shared blocks in a neutral
  colour. Sub-parts are not shaded; a selected lane switches its sub-parts to
  Function colours.

### 3.6 Block tint and region outlines
- Tint each part's **cell footprints**, using a new instanced layer built from
  the per-cell array. Do not draw rectangles, which would suggest a separation
  that does not exist.
- **Height.** The tint boxes are opaque and run from z 0 to the displayed top
  of met1, so the met1 rails and wires do not break up the colour. The layers
  under them are hidden while a part mode is on.
- **Physical-only cells.** Fill footprints are off by default, with one
  toggle, since fill covers the whole core; tap cells are grey.
- A hull or density-contour outline at 60% opacity is optional.
- Draw fences only when the DEF has `REGIONS` (the `sky130hd_sep` run), as
  dashed outlines labelled "fence copyA" and so on. For the base run, say that
  there are none.

### 3.7 Repeated lanes
Define the lane once in the legend: "Lane = Mult + Adder A/B + Acc A/B + Res
A/B, ×4". Label L0–L3 at their anchors as tier 0, and give the same role the
same colour in every lane. Clicking a lane frames it: fit its box with 12%
padding, keep the azimuth, and clamp the elevation to 35–60°. Tier 1 then
shows for that lane only.

### 3.8 Pin edges
Show one badge per edge, outside the die, with an arrow leader to the edge
midpoint. For example: **N · 47 pins (met2): out_data 31, in_a 8, in_b 8**.
Clicking the badge opens the full list. Tint the pin boxes by signal family.
Never call an edge "the result bus".

### 3.9 Layer-stack callout and Section A-A
- **Layer column.** In spread or Low-angle view, show a right-hand column of
  layer names (met5 down to nwell) with horizontal leaders. Name the via
  layers too.
- **Z ruler.** Add a z ruler with brackets for FEOL (nwell–licon1), local
  interconnect (li1, mcon) and BEOL (met1–met5). Label it "Z ×N, heights
  approximate below li1".
- **Section A-A.** Cut along x or y only, set in Top view and drawn dashed
  with A/A arrows at its ends; a linear scan of the 720k boxes finds the cut
  shapes in milliseconds. Draw a 30 µm window of the cut, centred on a
  slider, on a 2D canvas titled "SECTION A-A · Z ×N" with solid fills per
  layer (a full-length cut is 346 µm wide and 6.6 µm tall). State that the
  dielectrics are not modelled. three.js clipping planes also work with our
  shader-built boxes, but leave the cut faces open.

### 3.10 Exploded view
Explode only vertically, which is today's spread. A "Lift part" action raises
the selected part's footprints and draws dashed trails back to where it sits.
Never move a part sideways.

### 3.11 Hover and tap inspector
Any cell can be picked through the 2D grid in §3.15. The record looks like
this (the numbers are illustrative):

```
orbit_demo › Lane 2 › Accumulator B › bit 17
g_lane[2].u_lane.u_acc_b.q[17]$_SDFFE_PN0P_
sky130_fd_sc_hd__dfxtp_1 · "Delay flop, single output." · drive 1
$_SDFFE_PN0P_ = Yosys: rising-edge clock, active-low sync reset to 0, active-high enable
(x, y) µm · row 57 · FS · 7.36 × 2.72 µm · same bit in copy A: 24.7 µm · source: instance name
```

- **Decode the cell name.** `sky130` is the process, `fd` means SkyWater
  foundry, `sc` means standard cells, and `hd` means high density. The rest
  is `__<function>_<drive>`.
- **Function text.** At build time, take `description` and, where present,
  `equation` (for example a21oi: `Y = !((A1 & A2) | B1)`) from the PDK's
  `cells/<function>/definition.json` for the 74 functions in use. Flops have
  no `equation`; fall back to the Liberty `function`/`ff` group from the
  platform `.lib`.
- **Unnamed cells** show their part and "inferred from netlist cone".

### 3.12 Orientation and scale
- Add a 96 px DOM/SVG compass that rotates with the camera azimuth and shows
  N/E/S/W, with N = layout +y, matching the pin badges. Clicking a letter
  snaps the azimuth; a Home button does the same as Reset. Do not use
  three.js `ViewHelper` as is: its click targets are hard-coded Euler
  rotations for a Y-up scene, and ours is Z-up.
- Keep the edge rulers and the "vertical ×N" chip.
- Show a 1-2-5 µm scale bar only in Top view and in insets. Never present the
  vertical exaggeration as a scale.

### 3.13 Detail inset for tiny parts
- **Main view.** Put a circle marked "A" on the thermal strip.
- **Inset.** Draw an SVG top-down view of x 5–31, y 153–228 µm from the
  per-cell array: footprints in part colours, about 4.3 px/µm in a 115×325 px
  box, so a flip-flop is about 32×12 px. A second WebGL viewport would
  redraw all 720k boxes every frame for about 30 cells.
- **Title and scale.** Title it "DETAIL A · thermal TMR and fault latches" and
  give it a 10 µm scale bar.
- **Labels.** Balloon all nine flip-flops: six thermal (copy and bit), plus
  `fault_q`, `out_valid_q` and `phase`.
- **No ratio label.** Leave out ratios like "10:1", because the parent view is
  in perspective.
- **Behaviour.** Clicking the inset flies the camera there. On phones the
  inset opens as a sheet.

### 3.14 GLB node hierarchy
```
orbit_demo_sky130hd        Empty; extras {units:"um", up:"+Y", layout_y:"-Z", z_scale, gds_sha256}
├─ Parts
│  ├─ Lane0                Empty; extras {display_name, item, cells, ffs, area_um2}
│  │  └─ Lane0_Mult, Lane0_AdderA, Lane0_AdderB, Lane0_AccA, Lane0_AccB, Lane0_ResA, Lane0_ResB
│  ├─ Lane1 … Lane3
│  ├─ Thermal_TMR > Thermal_Copy0..2, Thermal_Voter
│  └─ Compare_Fault, Control, Clock_Tree, Port_Buffers, Timing_Repair, Tap_Cells, Fill_Cells
├─ Routing > met1 … met5, via … via4, Power_Grid (VDD/VSS shapes by net name)
├─ Pins > Pins_N, Pins_S, Pins_E, Pins_W
└─ Die_Substrate
```
- **Part meshes** are merged footprint boxes below li1 (z 0–0.94 µm). Today's
  GLB has 9 routing-layer meshes (met1–met5 and vias) plus a substrate box,
  and leaves out everything below met1, so it shows no cells at all.
- **Node names** use only `[A-Za-z0-9_]`, must be unique, and are at most 63
  bytes (Blender's long-standing name limit). GLTFLoader turns whitespace into
  `_` and strips `[ ] . : /` (`PropertyBinding.sanitizeNodeName`), so put the
  RTL paths in `extras.hier`.
- **Materials** are named by category.
- **Hotspots.** Ship a `labels.json` with anchors in GLB coordinates (x, height,
  −y, origin at the die centre), for model-viewer hotspots.
- **Compatibility.** The file uses `KHR_mesh_quantization` as a required
  extension. three.js and Blender read it; say so in the README for other
  tools.
- **Checks.** Load the file in the Blender outliner, test it with
  `getObjectByName` in the screenshot harness, and run gltf-validator where
  it is installed.

### 3.15 Performance limits
- **Do not raycast the layer meshes.** The boxes are built in the shader, so
  the raycaster only sees a unit box.
- **Pick through a grid.** Intersect the ray with the plane at the displayed
  top of the tint layer (from the same uniforms `applyZ()` sets), then look up
  the cell in a 10 µm grid (35×35 bins, about 15 cells each) of the 18,158
  cell boxes. Pick at most once per frame, and never on touch hover.
- **Highlight and recolour without rebuilding geometry.** Give each footprint
  instance a part id. Colour comes from a part-id lookup (a small
  `DataTexture` or uniform array) that the colour mode rewrites; selection is
  a `uSelectedPart` uniform. Dim everything else to about 25%.
- **Net classes.** Store a class per routing rectangle (power, clock, signal,
  none) from GDS property 1; vias take the class of the wire they land on.
  This adds about 0.7 MB to `layout.bin` and lets Power grid and Clock tree
  highlight exactly.
- **Label budget.** Show at most 15 labels at once on desktop and at most 8
  when the stage is under 600 px wide. Keep no more than 60 label elements in
  the DOM.
- **Label updates.**
  - Re-project the visible labels in every rendered frame (at most 60
    anchors). Only the layout decisions are throttled.
  - Re-run the layout at most every 120 ms while the camera moves, and once
    more when a frame finds the camera at rest (no tween, and
    `controls.update()` returned false). OrbitControls fires `end` on pointer
    up, before damping settles.
  - Each pass: (1) hide labels when the camera is below the die plane;
    (2) drop anchors outside the view frustum; (3) apply the tier rules from
    §3.2; (4) place labels greedily in priority order, trying 4–8 candidate
    anchors each, with 4 px padding.
- **No occlusion raycasts.** The drawn stack is at most 6.6 µm × N tall on a
  346 µm die, and labels sit on its top face, so the facing and frustum checks
  are enough.
- **Stability.** A placed label stays unless more than 30% of it is
  overlapped. Fade labels in and out over 200 ms.
- **Rendering.** Keep rendering on demand, with no continuous loop.

### 3.16 Mobile and accessibility
- **Narrow screens (under 600 px).**
  - Show numbered balloons only.
  - Tapping a part selects it and opens the inspector as a bottom sheet.
  - Make touch targets at least 24 px (44 px preferred).
- **Keyboard and screen reader.** The parts list is the model: each row is a
  real button, and the list uses a roving tabindex.
  - Enter flies to the part.
  - Esc clears the selection.
  - Arrow keys walk the part tree.
  - Floating labels are `aria-hidden`.
  - A polite live region announces the selection, for example "Lane 2,
    Accumulator B: 96 cells, 32 flip-flops".
- **Reduced motion.** When `prefers-reduced-motion` is set, jump instead of
  flying, use 0 ms fades and do not autoplay the tour.
- **Colour.** Never rely on hue alone. Each colour has a legend entry with
  text and a count, and inferred parts have a dashed outline.

## 4. Sources

Die shots and floorplans:
- https://github.com/efabless/caravel
- https://github.com/mattvenn/zero_to_asic_mpw6/blob/master/pics/multi_macro_annotated.png
- https://github.com/mattvenn/multi_project_tools/blob/main/collect.py
- https://github.com/TinyTapeout/tt-multiplexer/blob/main/docs/INFO.md
- https://github.com/misdake/ChipAnnotationViewer
- https://arxiv.org/pdf/1704.04760
- https://eems.mit.edu/wp-content/uploads/2016/02/eyeriss_isscc_2016.pdf
- https://locuza.substack.com/p/die-walkthrough-alder-lake-sp-and
- https://www.tomshardware.com/pc-components/cpus/intel-lunar-lake-cpu-gets-die-annotation-four-skymont-e-cores-slightly-bigger-than-one-lion-cove-p-core
- https://fuse.wikichip.org/news/1017/isscc-2018-intels-skylake-sp-mesh-and-floorplan/
- https://www.righto.com/search/label/8086
- https://www.techinsights.com/blog/apple-m4-soc-digital-floorplan-analysis

Layout viewers:
- https://github.com/TinyTapeout/tinytapeout_gds_viewer
- https://github.com/TinyTapeout/tiny-explorer
- https://github.com/mbalestrini/GDS2glTF
- https://github.com/trilomix/GDS3D
- https://github.com/KLayout/klayout/blob/master/src/doc/doc/about/25d_view.xml (rendered at https://www.klayout.de/doc-qt5/about/25d_view.html)
- https://github.com/efabless/sky130_klayout_pdk/blob/main/tech/sky130/d25/sky130.lyd25
- https://github.com/The-OpenROAD-Project/OpenROAD/blob/master/src/gui/README.md
- https://github.com/The-OpenROAD-Project/OpenROAD/blob/master/src/gui/src/renderThread.cpp
- https://github.com/The-OpenROAD-Project/OpenROAD/tree/master/src/web
- https://github.com/The-OpenROAD-Project/OpenROAD/blob/master/src/web/src/hierarchy-browser.js
- https://github.com/The-OpenROAD-Project/OpenROAD/pull/11122 (open, not merged)
- https://github.com/RTimothyEdwards/magic/blob/master/doc/html/wind3d/render.html
- https://github.com/TinyTapeout/siliwiz
- https://github.com/lkqiao/gds_3d_viewer
- https://github.com/EECSB/GDSViewer

CAD conventions:
- https://www.iso.org/standard/51527.html
- https://help.solidworks.com/2021/english/SolidWorks/sldworks/hidd_dve_auto_balloon.htm
- https://grail.cs.washington.edu/wp-content/uploads/2015/08/li2008ago.pdf
- https://www.researchgate.net/publication/259323227_Label_Layout_for_Interactive_3D_Illustrations
- https://www.researchgate.net/publication/261050920_Hedgehog_Labeling_View_Management_Techniques_for_External_Labels_in_3D_Space
- https://www.autodeskresearch.com/publications/viewcube
- https://www.asme.org/codes-standards/find-codes-standards/y14-3-orthographic-pictorial-views
- https://cad.onshape.com/help/Content/Drawing/detail_view.htm
- https://aps.autodesk.com/en/docs/viewer/v7/reference/Viewing/Viewer3D/

glTF and PDK:
- https://github.com/KhronosGroup/glTF/blob/main/specification/2.0/Specification.adoc
- https://github.com/KhronosGroup/glTF-Blender-IO
- https://github.com/mrdoob/three.js/blob/dev/src/animation/PropertyBinding.js (`sanitizeNodeName`)
- https://github.com/CesiumGS/glTF/blob/3d-tiles-next/extensions/2.0/Vendor/EXT_mesh_features/README.md
- https://github.com/google/skywater-pdk/blob/main/docs/_static/metal_stack.svg
- https://github.com/google/skywater-pdk/blob/main/docs/contents/libraries.rst
- https://github.com/google/skywater-pdk-libs-sky130_fd_sc_hd (`cells/*/definition.json`)
- https://github.com/YosysHQ/yosys/blob/main/techlibs/common/simcells.v

Web 3D annotation:
- https://github.com/mrdoob/three.js/blob/dev/examples/css2d_label.html
- https://github.com/mrdoob/three.js/blob/dev/examples/webgl_interactive_cubes_gpu.html
- https://github.com/mrdoob/three.js/blob/dev/examples/webgl_postprocessing_outline.html
- https://github.com/mrdoob/three.js/blob/dev/examples/jsm/helpers/ViewHelper.js
- https://github.com/mrdoob/three.js/blob/dev/examples/webgl_clipping_stencil.html
- https://github.com/google/model-viewer
- https://help.sketchfab.com/hc/en-us/articles/202512456-Annotations
- https://github.com/xeokit/xeokit-sdk/blob/master/src/plugins/AnnotationsPlugin/AnnotationsPlugin.js
- https://github.com/potree/potree/blob/develop/src/Annotation.js
- https://github.com/CesiumGS/cesium/blob/main/packages/engine/Source/DataSources/EntityCluster.js
- https://github.com/maplibre/maplibre-gl-js/blob/main/src/symbol/collision_index.ts
- https://github.com/ColinEberhardt/d3fc-label-layout
- https://doi.org/10.1109/tvcg.2016.2518318
- https://github.com/yomotsu/camera-controls

**Caveat on sources.** On 2026-09-29 the GitHub-hosted claims were checked in
the source itself (OpenROAD, Tiny Tapeout, MapLibre, Potree, model-viewer,
GDS2glTF, three.js, KLayout doc, SKY130 files, Zero to ASIC, Caravel). Two
links were fixed: Zero to ASIC is on `master`, and ISO 6433 now points to the
current 2012 edition. Pages on ISO, ASME, SOLIDWORKS, Autodesk, Onshape,
Sketchfab, WikiChip, Substack, righto.com, Tom's Hardware, TechInsights,
arXiv, MIT, klayout.de, doi.org and ResearchGate were blocked here. The TPU
percentages, Lunar Lake "?" marks, SOLIDWORKS options, Sketchfab caps and
Madsen et al.'s finding rest on search-result excerpts; spot-check those
before quoting numbers. The counts in §0 were measured from this repo's
`base` run on 2026-09-29. The netlist-cone figures come from a throwaway
prototype and should be treated as estimates.

## 5. Implementation brief

**Today** (`viz/index.html`, `reports/viz/*.png`): 16 layer toggles, vertical
scale ×1–20, layer spread 0–12 µm, Iso/Top/Low/Reset presets, edge rulers,
flip-flop highlight by copy with a mouse-only tooltip, dark mode, phone
layout, reduced-motion camera, provenance footer. **Missing:** part labels,
part tree, picking of anything but flip-flops, cell footprints, pin and
orientation labels, and named parts in the GLB.

Requirements, in priority order. Each ends with how to test it; add the hooks
`orbitViz.labels()` (visible label and leader rectangles), `orbitViz.pickAt(x,
y)` and `orbitViz.select(id)` to the existing screenshot harness object.

1. **Part table.** `make viz` writes `parts[]` (§3.1) and the per-cell array
   for all 18,158 DEF components. Each of the 6,166 logic cells has exactly
   one part id, and unassigned cells form an "Other logic" part. *Test:* the
   build fails if the part cell counts do not sum to 6,166 or if a
   cone-inferred part lacks `source: "netlist-cone"`.
2. **Footprint tint layer.** One instanced draw of the logic and tap cells
   (fill off by default), z 0 to the displayed top of met1, coloured through a
   part-id lookup (§3.6, §3.15). *Test:* switching colour mode or selection
   leaves `renderer.info.memory.geometries` unchanged.
3. **"Color by" switch** (Layer | Function | Lane | Copy). Outside Layer mode
   the layers turn grey, met2 ≤ 35% and met3–met5 ≤ 15% opacity. Function mode
   has ≤ 8 tokens per theme with a legend entry, text and count each (§3.5).
   *Test:* a palette script checks token pairs ≥ ΔE00 15 apart and ≥ 20 from
   every grey; at the Iso preset, the pixel at each lane anchor is within
   ΔE00 10 of its token.
4. **Floating labels for compact parts only.** In Function mode at the Iso
   preset the tier-0 set is Lane 0–3, Thermal TMR, Power grid and 4 pin-edge badges, plus
   Compare/fault and Control only if `compact`. Spread parts are list-only
   (§3.2). *Test:* `labels()` at Iso contains exactly that set, and no label
   for the clock tree, port buffers or timing-repair buffers.
5. **Label layout engine.** Per-frame re-projection. Layout at most every
   120 ms in motion and once at rest. Greedy by priority with 4 px padding.
   Tiers by projected size. ≤ 15 visible labels on desktop, ≤ 8 under 600 px,
   ≤ 60 in the DOM, 30% hysteresis, 200 ms fades (0 ms under reduced motion)
   (§3.15). *Test:* at Iso, Top, Low and phone width, no two label rectangles
   overlap and the counts are within budget.
6. **Placement and leaders.** Internal, then edge-margin, then balloon
   (§3.3). 1 px leaders with dot or arrow ends, anchors on the tint top, text
   ≥ 11 px on a ≥ 85%-opaque background. *Test:* no two leader segments
   intersect in `labels()` output at the four views above.
7. **Parts list (BOM).** Items numbered as in §3.4, with columns Item | Part |
   Qty | Cells | FFs | Area µm² (%) | Source and a stated denominator. Lane
   parts are ballooned once with Qty ×4. Hover highlights the part (others
   dimmed to about 25%). Click or Enter flies to it in ≤ 500 ms (instant under
   reduced motion) with 12% padding and elevation 35–60°. *Test:*
   `select('lane2')` leaves the camera target inside lane 2's box and sets
   `uSelectedPart` to its id.
8. **Any-cell picking and inspector.** Mouse hover and touch tap pick any
   cell by ray–plane intersection and a 10 µm bin lookup, at most once per
   frame. The inspector shows breadcrumb, full instance name, master with PDK
   description (and equation where available), the decoded Yosys suffix,
   position, row, orientation, size, part and source (§3.11). *Test:*
   `pickAt()` at the projected centres of 20 random logic cells returns the
   right name for at least 19.
9. **Pin-edge badges.** Four badges outside the die with per-edge counts by
   signal family and layer, generated from the DEF (N 47 met2, S 53 met2,
   E 67 met3, W 48 met3). No label calls an edge a bus. *Test:* badge text
   equals the counts the build computes from the DEF.
10. **Provenance.** Inferred parts carry a dashed outline and an "inferred"
    tag in the label, list and inspector. The legend has no decap or hold
    entries for this run. The panel says the run has no placement regions;
    with `REGIONS` in the DEF, fences are drawn as dashed, named outlines.
    *Test:* the base run shows no fence objects; the `sky130hd_sep` run shows
    five.
11. **Net classes for power and clock.** `layout.bin` carries a class per
    routing rectangle (§3.15). Selecting Power grid highlights only VDD/VSS
    shapes; selecting Clock tree highlights clock nets and buffers and labels
    `clkbuf_0_clk`. *Test:* the highlighted met4 count equals the build's
    VDD/VSS met4 count, not all 273 met4 rectangles.
12. **DETAIL A inset** (§3.13). An SVG of x 5–31, y 153–228 µm with nine
    balloons, a 10 µm scale bar and an "A" marker on the main view. On phones
    it opens as a sheet. *Test:* nine balloons, and each flip-flop drawn at
    least 30 px wide.
13. **Keyboard, screen reader and touch** (§3.16). A parts tree of real
    buttons with roving tabindex: Enter flies, Esc clears, arrows walk the
    tree. Floating labels are `aria-hidden`, a polite live region announces
    the selection with counts, touch targets are ≥ 24 px, and there is no
    hover picking on touch. *Test:* a Playwright keyboard walk reaches every
    part and the live region text updates.
14. **Orientation.** A DOM compass with N/E/S/W that rotates with the azimuth
    (N = layout +y), plus Home; a 1-2-5 µm scale bar in Top view and the inset
    only (§3.12). *Test:* at the Top preset, N points up the screen and the
    scale bar length matches its µm value within 2%.
15. **GLB with named parts** (§3.14). Node tree, part meshes from footprints,
    `[A-Za-z0-9_]` names of at most 63 bytes, `extras` per part, category
    materials, and `labels.json` in GLB coordinates. *Test:* the harness loads
    the GLB with GLTFLoader and finds every part by `getObjectByName` with its
    name unchanged; gltf-validator reports 0 errors where it is installed.

**Deferred** (not required for this build): the layer-name column and
FEOL/BEOL brackets and the Section A-A panel (§3.9), Lift-part explode
(§3.10), a saved-view tour of at most 12 labels per stop, an OpenROAD
`save_image -web` cross-check (our `6_final.odb` is flat, so it would need a
hierarchical run or the name-grouped tree), and a per-lane density overlay.
