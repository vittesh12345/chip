# Labeled chip models: design guide for the ORBIT-AI die explorer

**Status (2026-09-29): the labeled version is not built yet.** The current
viewer (`viz/index.html`) labels layers and highlights flip-flops by copy. It
has no part labels or part tree, and the GLB has no named parts. This guide is
the spec for the labeled version. It combines four surveys (labeled die shots,
layout viewers, CAD drawing conventions, web 3D annotation) with measurements
of our own routed data.

## 0. What our data can label (measured on the committed `base` run)

Sources: `build/pd/results/sky130hd/orbit_demo/base/6_final.{def,v}` and
`viz/layout.json`. The rows add up to the 6,166 logic cells the viewer reports.

| Part group | How we know | Cells | FFs |
|---|---|---|---|
| Accumulator A/B and result A/B, ×4 lanes | instance name `g_lane[i].u_lane.u_{acc,res}_{a,b}/…` (`orbit_keep_reg` hierarchy kept) | 1,539 | 512 |
| Thermal copies 0/1/2 | `u_thermal.u_copyN/…` | 24 | 6 |
| `fault_q`, `out_valid_q`, `u_thermal.phase` | top-level names | 3 | 3 |
| Multipliers, adders, compare/fault, voter, handshake | **anonymous `_NNNN_` cells** (synthesis flattened them) | 3,390 | 0 |
| Timing-repair buffers `place*`, `rebuffer*`, `clone*` | resizer name prefix (inferred) | 871 | 0 |
| Port buffers `input*`, `output*` | name prefix | 214 | 0 |
| Clock tree: `clkbuf_*` (68), `clkload*` (55) | CTS name prefix | 123 | 0 |
| Antenna diodes | `ANTENNA_*` | 2 | 0 |
| Tap cells / fill cells (`fill_1/2/4/8`) | master name | 1,524 / 10,468 | – |

**The adders, multipliers, voter and compare logic have no names.** The
synthesized netlist contains only `orbit_demo` and two `orbit_keep_reg`
variants, so these blocks have to be inferred. A throwaway prototype sorted
each anonymous cell by the registers and ports in its fan-in and fan-out cones
in `6_final.v`. It found:

* multiplier: 196–198 cells per lane
* adder A: 262–274 per lane
* adder B: 259–266 per lane
* compare/fault: 370
* voter/next-state: 11
* other control: 103

Mark all of these groups as **inferred**. This run has no decap cells and no
`hold*` buffers, so the legend should not list either.

Other measured facts:

* **Lanes sit roughly in quadrants.** Flip-flop centroids are L0 (115, 95) µm
  SW, L1 (241, 104) SE, L2 (242, 243) NE and L3 (101, 230) NW. Their bounding
  boxes overlap by about 30 µm at the centre lines, and copies A and B
  interleave (`reports/viz/viewer_redundancy.png`).
* **The six thermal flip-flops are in a strip on the west edge** (x 12–26,
  y 178–224 µm), next to `fault_q`, `out_valid_q` and `phase` (y 156–170). A
  `dfxtp_1` is 7.36 × 2.72 µm, which is about 19 × 7 px in the default view.
* **The 215 pins are spread over all four edges.**
  * `out_data`: S 36, N 31, W 28, E 33.
  * `in_a` and `in_b`: each S 8, E 16, N 8.
  * Most control pins and all temperature pins are on W. `clear_fault` is on
    S; `fault` and `in_first` are on E.
  * N/S pins are on met2 and E/W pins on met3. No edge holds a single bus.
* **The base run has no placement regions.** The `sky130hd_sep` variant sets
  fences copyA, copyB and th0/1/2 in `pd/sky130hd_sep/regions.tcl`.
* **There are 125 cell rows**, each 2.72 µm tall with a 0.46 µm site pitch.

## 1. What well-labeled chip models have in common

1. **Colour for category, text for identity, about 8 categories at most.** See
   [TPU v1 Fig. 2](https://arxiv.org/pdf/1704.04760), the
   [Tiny Tapeout mux](https://github.com/TinyTapeout/tt-multiplexer/blob/main/docs/INFO.md)
   and the [OpenROAD module view](https://github.com/The-OpenROAD-Project/OpenROAD/tree/master/src/web).
2. **A label shows only if it fits; deeper levels appear with zoom.** OpenROAD
   uses a 10 px / 90%-of-box rule.
   [ChipAnnotationViewer](https://github.com/misdake/ChipAnnotationViewer) and
   [Potree](https://github.com/potree/potree/blob/develop/src/Annotation.js)
   (100 px collapse) do the same.
3. **Picking a part shows its record in a panel; no 3D text.** See the breadcrumb and
   `setColorAt` highlight in the
   [Tiny Tapeout GDS viewer](https://github.com/TinyTapeout/tinytapeout_gds_viewer).
4. **A repeat is defined once and marked by index.** See the
   [WikiChip Skylake-SP tiles](https://fuse.wikichip.org/news/1017/isscc-2018-intels-skylake-sp-mesh-and-floorplan/)
   and SOLIDWORKS
   ["ignore multiple instances"](https://help.solidworks.com/2021/english/SolidWorks/sldworks/hidd_dve_auto_balloon.htm).
5. **Real geometry gets an outline or a translucent tint.** See
   [Zero to ASIC](https://github.com/mattvenn/zero_to_asic_mpw6/blob/main/pics/multi_macro_annotated.png).
   Solid fills are for schematics only.
6. **Balloons are keyed to a parts list, with short leaders that never cross.**
   See [ISO 6433](https://www.iso.org/standard/12788.html) and
   [Hartmann et al.](https://www.researchgate.net/publication/259323227_Label_Layout_for_Interactive_3D_Illustrations).
7. **Scale and exaggeration are always stated.** The
   [SKY130 metal stack](https://github.com/google/skywater-pdk/blob/main/docs/_static/metal_stack.svg)
   is marked "not to scale", and
   [KLayout 2.5D](https://www.klayout.de/doc-qt5/about/25d_view.html) has a
   separate z-zoom control.
8. **Labels show where they come from.** Inferred labels carry a "?" in the
   [Lunar Lake annotation](https://www.tomshardware.com/pc-components/cpus/intel-lunar-lake-cpu-gets-die-annotation-four-skymont-e-cores-slightly-bigger-than-one-lion-cove-p-core).
   The [Caravel floorplan](https://github.com/efabless/caravel/blob/main/docs/source/_static/caravel_floorplan.jpg)
   uses RTL names.
9. **Names go into the exported file.** See the named instance nodes and
   `extras` in [GDS2glTF](https://github.com/mbalestrini/GDS2glTF).
10. **Declutter is greedy by priority, throttled and faded.** The
    [MapLibre collision index](https://github.com/maplibre/maplibre-gl-js/blob/main/src/symbol/collision_index.ts)
    fades over 300 ms. Madsen et al. (TVCG 2016) found that users prefer
    labels that update at a limited rate.

## 2. Example gallery

| Example | Type | Borrow |
|---|---|---|
| [Caravel floorplan](https://github.com/efabless/caravel/blob/main/docs/source/_static/caravel_floorplan.jpg) | sky130 floorplan | nested outlines, RTL names, letter key for tiny blocks |
| [Zero to ASIC MPW6](https://github.com/mattvenn/zero_to_asic_mpw6/blob/main/pics/multi_macro_annotated.png) ([script](https://github.com/mattvenn/multi_project_tools/blob/main/collect.py)) | auto-annotated layout | labels generated from placement coordinates; its label collision is a failure to avoid |
| [Tiny Tapeout mux diagram](https://github.com/TinyTapeout/tt-multiplexer/blob/main/docs/INFO.md) | schematic floorplan | category fills, legend with counts, repeated tiles in grey |
| [Tiny Tapeout GDS viewer](https://github.com/TinyTapeout/tinytapeout_gds_viewer) | three.js, sky130 | breadcrumb, `setColorAt`, isolate/zoom keys, fill/tap toggle, B&W depth mode |
| [tiny-explorer](https://github.com/TinyTapeout/tiny-explorer) | WebGL2 instanced boxes | per-instance ID attribute, dim-the-rest, part list sorted by area |
| [OpenROAD web GUI](https://github.com/The-OpenROAD-Project/OpenROAD/tree/master/src/web), [PR 11122](https://github.com/The-OpenROAD-Project/OpenROAD/pull/11122) | P&R viewer | module colours, collapse-to-inherit, tree built from names, area per node |
| [OpenROAD Qt GUI](https://github.com/The-OpenROAD-Project/OpenROAD/blob/master/src/gui/README.md) | P&R viewer | cell-type taxonomy; 10 px / 90% text rule |
| [ChipAnnotationViewer](https://github.com/misdake/ChipAnnotationViewer) | die-shot annotator | label JSON (polygons, RGBA, two-part font size), real areas |
| [TPU v1 floorplan](https://arxiv.org/pdf/1704.04760) | paper figure | 4 category colours, % of die with the denominator stated |
| [Locuza die walkthrough](https://locuza.substack.com/p/die-walkthrough-alder-lake-sp-and) | die shots | zoom from die to core to unit; same tint for the same role |
| [GDS2glTF](https://github.com/mbalestrini/GDS2glTF) | GDS to glTF | named instance nodes, `extras`, one material per layer |
| [glTF spec](https://github.com/KhronosGroup/glTF/blob/main/specification/2.0/Specification.adoc), [GLTFLoader](https://github.com/mrdoob/three.js/blob/dev/examples/jsm/loaders/GLTFLoader.js), [Blender importer](https://github.com/KhronosGroup/glTF-Blender-IO/blob/main/addons/io_scene_gltf2/blender/imp/vnode.py) | file format | name and `extras` rules; empty nodes as group headers |
| [SKY130 metal_stack.svg](https://github.com/google/skywater-pdk/blob/main/docs/_static/metal_stack.svg) | PDK cross-section | named conductors, vias and dielectrics; z ruler; "not to scale" |
| [GDS3D](https://github.com/trilomix/GDS3D), [KLayout sky130 2.5D](https://github.com/efabless/sky130_klayout_pdk/blob/main/tech/sky130/d25/sky130.lyd25) | 3D layout viewers | exaggeration separate from explode; legend from the layer table; grey-out-except-selection |
| [ISO 6433](https://www.iso.org/standard/12788.html), [SOLIDWORKS balloons](https://help.solidworks.com/2021/english/solidworks/sldworks/c_balloons_overview.htm) | CAD drawing rules | balloon numbers keyed to BOM rows; dot or arrow leader ends |
| [Sketchfab annotations](https://help.sketchfab.com/hc/en-us/articles/202512456-Annotations), [model-viewer](https://github.com/google/model-viewer/blob/master/packages/model-viewer/src/three-components/ModelScene.ts) | web 3D | numbered stops with saved cameras; hide a hotspot when its normal faces away |
| [MapLibre collision index](https://github.com/maplibre/maplibre-gl-js/blob/main/src/symbol/collision_index.ts) | map labels | priority greedy placement, candidate anchors, 300 ms fade |
| [Potree annotations](https://github.com/potree/potree/blob/develop/src/Annotation.js) | point-cloud viewer | collapse by pixel threshold; 500 ms ease-out fly-to |
| three.js [CSS2D](https://github.com/mrdoob/three.js/blob/dev/examples/css2d_label.html), [ViewHelper](https://github.com/mrdoob/three.js/blob/dev/examples/jsm/helpers/ViewHelper.js), [multi-view](https://github.com/mrdoob/three.js/blob/dev/examples/webgl_multiple_views.html) | library examples | DOM label overlay, orientation gizmo, inset viewport |
| [gds_3d_viewer](https://github.com/lkqiao/gds_3d_viewer) | three.js layout viewer | clip-plane section; one pick per frame; tiny objects left out of picking |

## 3. Rules for our model

### 3.1 One part table drives everything
- The pipeline (`scripts/viz_gds_to_3d.py`) writes `parts[]` into
  `layout.json`: `id`, `item`, `name`, `category`, `lane`, `cells`, `ffs`,
  `area_um2`, `bbox_um`, `hull_um`, `centroid_um`, `anchor_um`, `source`
  (`instance-name` | `name-prefix` | `netlist-cone`).
- It also writes a per-cell array (box, master, part id) for all 18,158 DEF
  components.
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
| 0 | Lane 0–3, Thermal TMR, Compare/fault, Control, Clock tree, 4 pin edges, Power grid (≤ 12) | always, in the part colour modes |
| 1 | a lane's 7 sub-parts; thermal copies 0/1/2 and the voter | lane selected, or lane ≥ 600 px wide on screen (fades in from 450 px) |
| 2 | flip-flop text inside the cell | selected part only; text ≥ 10 px tall and ≤ 90% of the cell width (about 6 px/µm for `dfxtp_1`) |
| 3 | any cell | hover or tap inspector only (§3.11) |

### 3.3 Label and leader style
- **Where labels go.** A part gets its label inside it, at the centroid, when
  the text fits in the part's on-screen outline. Otherwise the label goes
  outside, 40–80 px out, with a leader line.
- **Leaders.** Draw leaders as 1 px SVG lines. End a leader with a 5 px dot
  when it points into a part, and with an arrowhead when it points to an edge
  (pins, die outline). Keep leaders oblique and at most 120 px long. Sort them
  by angle around the die centre so they never cross.
- **Anchor height.** Anchor labels at `stackTopDisplay()*1.06 +
  dieSize*0.004`, the same lift the flip-flop highlight uses. Recompute the
  anchors in `applyZ()`.
- **Type.** Tier 0 is 13–14 px semibold, tier 1 is 12 px, and nothing is
  smaller than 11 px. Inferred parts get a dashed outline and an "inferred"
  tag.

### 3.4 Numbered balloons and parts list (BOM)
Number the parts in tree order and keep the same numbers in every view.
Balloon lane 0 only, with Qty ×4:

1 Lane · 2 Multiplier · 3 Adder A · 4 Adder B · 5 Accumulator A · 6 Accumulator B · 7 Result A · 8 Result B · 9 Thermal copies · 10 Voter/next-state · 11 Compare/fault · 12 Handshake/control · 13 Clock tree · 14 Port buffers · 15 Timing-repair buffers · 16 Pins · 17 Power grid · 18 Tap + fill · 19 Cell rows

- **Table columns:** Item | Part | Qty | Cells | FFs | Area µm² (%) | Source.
- **Area percentage.** State the denominator, for example "placed cell area
  from DEF+LEF, fill excluded".
- **Linking.** Hovering a table row highlights both the part and its balloon.
- **Balloons.** Draw balloons as 24 px circles. Use them for small parts, on
  phones and in the screenshot preset.

### 3.5 Part colours vs layer colours
The layer palette already uses almost every hue, and three of today's
highlight colours collide with it:

| Highlight token | Collides with |
|---|---|
| `--copy-a` #2465c7 | met1 #3f7fd6 |
| `--copy-b` #e0761c | met5 #c8783e |
| `--tmr-2` #2f8f3a | diff #43a45c |

Rules:

- **One "Color by" switch** with four modes: Layer (today) | Function | Lane |
  Copy (today's redundancy mode). Only one hue channel is active at a time.
- **In every mode except Layer:**
  - draw the layers as a grey depth ramp, extending today's "Fade the layout
    while highlighting";
  - fade met3–met5 to about 15%, because the straps hide the cells
    (`viewer_iso.png`).
- **Function mode uses 8 tokens,** each defined for light and dark themes:
  - storage
  - arithmetic
  - redundancy checking (compare/voter)
  - control
  - clock tree
  - port buffers
  - timing-repair buffers
  - physical-only (grey)

  Check the palette with a colour-blindness simulator and keep at least 3:1
  contrast against the die. Every legend entry shows its count.
- **Lane mode** gives each lane one hue, uses lighter and darker shades of it
  for the lane's sub-parts, and draws shared blocks in a neutral colour.

### 3.6 Block tint and region outlines
- Tint each part's **cell footprints**, using a new instanced layer built from
  the DEF boxes. Do not draw rectangles, which would suggest a separation that
  does not exist.
- A hull or density-contour outline at 60% opacity is optional.
- Draw fences only when the DEF has `REGIONS` (the `sky130hd_sep` run), as
  dashed outlines labelled "fence copyA" and so on. For the base run, say that
  there are none.

### 3.7 Repeated lanes
Define the lane once in the legend: "Lane = Mult + Adder A/B + Acc A/B + Res
A/B, ×4". Label L0–L3 at their centroids as tier 0, and give the same role the
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
- **Section A-A.** Drag a cut line in Top view and draw it dashed, with A/A
  arrows at its ends. Every shape is an axis-aligned box, so the slice is
  exact to compute on the CPU. Show it in an SVG panel titled "SECTION A-A ·
  Z ×N" with solid fills per layer, and state that the dielectrics are not
  modelled.

### 3.10 Exploded view
Explode only vertically, which is today's spread. A "Lift part" action raises
the selected part's footprints and draws dashed trails back to where it sits.
Never move a part sideways.

### 3.11 Hover and tap inspector
Any cell can be picked through the 2D grid in §3.15. The record looks like
this (the numbers are illustrative):

```
orbit_demo › Lane 2 › Accumulator B › bit 17
g_lane[2].u_lane.u_acc_b/q[17]$_SDFFE_PN0P_
sky130_fd_sc_hd__dfxtp_1 · "Delay flop, single output" (D flip-flop), drive 1
$_SDFFE_PN0P_ = Yosys: rising-edge clock, active-low sync reset to 0, active-high enable
(x, y) µm · row 57 · FS · 7.36 × 2.72 µm · same bit in copy A: 24.7 µm · source: instance name
```

- **Decode the cell name.** `sky130` is the process, `fd` means SkyWater
  foundry, `sc` means standard cells, and `hd` means high density. The rest
  is `__<function>_<drive>`.
- **Function text.** Generate the description and equation (for example
  a21oi: `Y = !((A1 & A2) | B1)`) at build time from the PDK's
  `cells/<name>/definition.json`, for the roughly 60 cell types in use.
- **Unnamed cells** show their part and "inferred from netlist cone".

### 3.12 Orientation and scale
- Add a 96–128 px corner gizmo based on `ViewHelper` (our scene is Z-up). Its
  faces are TOP, BOTTOM, N, S, E and W, with N = layout +y, matching the pin
  badges. A Home button does the same as Reset.
- Keep the edge rulers and the "vertical ×N" chip.
- Show a 1-2-5 µm scale bar only in Top view and in insets. Never present the
  vertical exaggeration as a scale.

### 3.13 Detail inset for tiny parts
- **Main view.** Put a circle marked "A" on the thermal strip.
- **Inset.** Add an orthographic top-down inset (`setViewport`/`setScissor`,
  about 220×320 px) framing x 8–30, y 174–228 µm, which is about 6 px/µm.
- **Title and scale.** Title it "DETAIL A · thermal TMR" and give it a 10 µm
  scale bar.
- **Labels.** Label each of the six flip-flops with a balloon showing its copy
  and bit. Show `fault_q`, `out_valid_q` and `phase` (just south of the frame)
  as balloons in the main view.
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
├─ Routing > met1 … met5, via … via4    (optional: power straps split out by net name)
├─ Pins > Pins_N, Pins_S, Pins_E, Pins_W
└─ Die_Substrate
```
- **Part meshes** are merged footprint boxes below li1 (z 0–0.94 µm). Today's
  GLB leaves out everything below met1, so it shows no cells at all.
- **Node names** use only `[A-Za-z0-9_]`, must be unique, and are at most 63
  bytes. GLTFLoader strips `[ ] . : /`, so put the RTL paths in
  `extras.hier`.
- **Materials** are named by category.
- **Hotspots.** Ship a `labels.json` with the anchors in GLB coordinates, for
  model-viewer hotspots.
- **Checks.** Load the file in the Blender outliner, test it with
  `getObjectByName`, and run gltf-validator.

### 3.15 Performance limits
- **Do not raycast the layer meshes.** The boxes are built in the shader, so
  the raycaster only sees a unit box.
- **Pick through a grid.** Intersect the ray with the plane at the top of the
  footprints, then look up the cell in a 10 µm grid (35×35 bins) of the 18,158
  cell boxes. Pick at most once per frame, and never on touch hover.
- **Highlight without rebuilding geometry.** Give each footprint instance a
  part id and compare it with a `uSelectedPart` uniform. Dim everything else
  to about 25%.
- **Label budget.** Show at most 15 labels at once on desktop and at most 8 on
  a phone. Keep no more than 60 label elements in the DOM.
- **When to lay out labels.** Run the layout on OrbitControls `change`,
  throttled to 120 ms, and again on `end`. Each pass:
  1. Hide labels when the camera is below the die plane.
  2. Apply the tier rules from §3.2.
  3. Place labels greedily, trying 4–8 candidate anchors each, with 4 px
     padding.
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

## 4. Implementation brief (prioritized checklist)

**What exists today** (`viz/index.html`, `reports/viz/*.png`):
- 16 layer toggles with z bars
- vertical scale ×1–20 and layer spread 0–12 µm
- Iso, Top, Low and Reset presets
- edge rulers and a "vertical ×N" chip
- flip-flop highlighting by copy, with a mouse-only tooltip, a group table and
  lines between same-bit copies
- dark mode, phone layout, reduced-motion camera and a provenance footer

**Gaps:**
- no part labels or part tree
- only flip-flops can be picked, and there is no cell-footprint layer
- met4 and met5 dominate the overview
- no labels for pins or orientation, and no section view
- the GLB has 10 per-layer meshes, no cells and no part names

**Must**
- [ ] M1 `parts[]` plus a part id for every cell, including cone inference
      for the 3,390 unnamed cells and a count of unassigned cells (§0, §3.1)
- [ ] M2 Instanced cell-footprint layer with part-id highlighting (§3.6,
      §3.15)
- [ ] M3 "Color by" switch, grey layer ramp and upper-metal fade (§3.5)
- [ ] M4 Tier-0 labels with leaders, level of detail, declutter and throttle
      (§3.2, §3.3, §3.15)
- [ ] M5 Parts list: hover highlights, click flies and isolates, area
      denominator stated (§3.4)
- [ ] M6 Grid-picked inspector for any cell, with cell-name and Yosys suffix
      decoding (§3.11)
- [ ] M7 Pin-edge badges (§3.8)
- [ ] M8 Tags for inferred parts. No legend entries for decap or hold. State
      that the base run has no placement regions.
- [ ] M9 Mobile and accessibility basics (§3.16). Add labeled iso, lane-zoom
      and phone shots to `make viz-shots`.

**Should**
- [ ] S1 Tier-1 lane labels and lane zoom (§3.7)
- [ ] S2 DETAIL A inset (§3.13)
- [ ] S3 GLB with named part nodes plus `labels.json`, checked in Blender and
      gltf-validator (§3.14)
- [ ] S4 Orientation gizmo with N/S/E/W and Home (§3.12)
- [ ] S5 Layer-name column and FEOL/BEOL brackets (§3.9)
- [ ] S6 Saved views or tour: Floorplan, Lane 0, Thermal TMR, Clock/I/O,
      Power grid. At most 12 labels each; navigate with prev/next and j/k.
- [ ] S7 Fence outlines when the DEF has `REGIONS` (§3.6)

**Could**
- [ ] C1 Section A-A panel (§3.9)
- [ ] C2 Lift-part explode with trails (§3.10)
- [ ] C3 An owner id for each FEOL/li1 rectangle, and routing net classes from
      GDS property #1 (not 61)
- [ ] C4 Cross-check against OpenROAD `save_image -web` in module view
- [ ] C5 Placement-density overlay per lane

## 5. Sources

Die shots and floorplans:
- https://github.com/efabless/caravel
- https://github.com/mattvenn/zero_to_asic_mpw6/blob/main/pics/multi_macro_annotated.png
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
- https://www.klayout.de/doc-qt5/about/25d_view.html
- https://github.com/efabless/sky130_klayout_pdk/blob/main/tech/sky130/d25/sky130.lyd25
- https://github.com/The-OpenROAD-Project/OpenROAD/blob/master/src/gui/README.md
- https://github.com/The-OpenROAD-Project/OpenROAD/tree/master/src/web
- https://github.com/The-OpenROAD-Project/OpenROAD/pull/11122
- https://github.com/RTimothyEdwards/magic/blob/master/doc/html/wind3d/render.html
- https://github.com/TinyTapeout/siliwiz
- https://github.com/lkqiao/gds_3d_viewer
- https://github.com/EECSB/GDSViewer

CAD conventions:
- https://www.iso.org/standard/12788.html
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

**Caveat on sources.** The GitHub-hosted sources were read directly. Pages on
ISO, ASME, SOLIDWORKS, Autodesk, Onshape, Sketchfab, WikiChip, Substack,
righto.com, Tom's Hardware, arXiv, MIT, klayout.de and ResearchGate were
blocked here, so what this guide says about them comes from search-result
excerpts. Spot-check those before quoting numbers. The counts in §0 were
measured from this repo's `base` run on 2026-09-29. The netlist-cone figures
come from a throwaway prototype and should be treated as estimates.
