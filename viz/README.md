# ORBIT-AI Die Explorer (3D layout viewer)

Design references: `docs/research/labeled-chip-models.md` (survey of labeled
chip models and the implementation brief this viewer follows).

An interactive, labeled 3D view of the routed `orbit_demo` layout, built from
the real GDS and DEF that OpenROAD-flow-scripts writes for the SkyWater
sky130hd open PDK. It shows the **copy-separated placement** of the pdsep
area (placement fences keep copy A, copy B and the three thermal copies
apart). It is the 4-lane INT8 demonstrator, not the 16-tile ORBIT-AI concept
chip, and nothing in it is radiation-qualified.

| File | What it is |
|---|---|
| `viz/index.html` | The viewer page (three.js 0.170.0). Written as claude.ai Artifact content: no doctype/html/head/body tags, starts with `<title>`; loads `./layout.json` and `./layout.b64.txt` with relative URLs. |
| `viz/layout.json`, `viz/layout.b64.txt` | Generated, committed page data (the publishable set). The binary geometry is stored as base64 text because Artifacts serve text files, not `.bin`. |
| `viz/layout.bin` | Optional raw copy for local use (`VIZ_FLAGS=--write-bin`); git-ignored, never published. |
| `reports/viz/orbit_demo_sky130hd_3d_full.glb` | Detailed portable model: all 16 drawn layers for the whole die + named parts, pins, fences (Draco). |
| `reports/viz/orbit_demo_sky130hd_3d.glb` | Metals-only model that needs no Draco decoder: met1-met5 and vias + the same parts/pins/fences (KHR_mesh_quantization, int16 positions scaled by 0.01). Fewer layers than the detailed file but larger in bytes (12.8 MB vs 9.2 MB), because it is not Draco-compressed. |
| `reports/viz/redundancy_placement.md` | Before/after placement of the redundant storage copies. |
| `reports/viz/viewer_*.png`, `glb_preview_*.png` | Headless renders of the page and of both GLBs. |
| `scripts/viz_gds_to_3d.py` | GDS/DEF/LEF to page data + GLBs + redundancy report. |
| `scripts/viz_parts.py` | Part attribution (every placed cell to a named part), pins, power straps, rows. |
| `scripts/viz_shots.py` | Serves the page locally and takes the screenshots (Playwright + Chromium). |
| `mk/viz.mk` | Make targets. |

## Regenerate

```sh
make viz          # page data + both GLBs + redundancy report
make viz-shots    # screenshots and GLB previews into reports/viz/
make viz-serve    # open http://localhost:8765/ in a browser
```

`make viz` reads the separated run of the pdsep area,
`$(BUILD)/pd_sep/results/sky130hd/orbit_demo/sep/6_final.{gds,def}`, its fence
labels `reports/pdsep/regions.json` and its stats `reports/pdsep/summary.md`.
If that run does not exist it falls back to the pd area's baseline
`$(BUILD)/pd/results/sky130hd/orbit_demo/base/` and prints a NOTE. The
baseline DEF is also read (`--baseline-def`) so the page and the report show
before/after copy distances. Override with
`make viz VIZ_GDS=path/6_final.gds VIZ_DEF=path/6_final.def`. The viz targets
only read the pd/pdsep areas.

The committed data comes from `build/pd_sep/results/sky130hd/orbit_demo/sep/`
(GDS written 2026-09-29 22:09 UTC; clock 7.2 ns, setup WNS +0.031 ns, 6,270
logic cells, 346.3 x 346.3 µm die, 750,439 drawn rectangles, 18,175 placed
components). `inputs` in `layout.json` records the GDS/DEF paths, file times
and SHA-256; the page footer shows them. Design stats come from the ORFS run
that wrote the GDS (`logs/.../6_report.json`, `results/.../6_final.sdc`).

First use creates a Python venv in `build/viz/venv` from `viz/requirements.txt`
(klayout, numpy, playwright, trimesh, pygltflib), installs
`@gltf-transform/cli@4.5.1` from npm into `build/viz/node/` (Draco compression
of the detailed GLB) and copies the platform files out of the ORFS image
(`openroad/orfs:latest`) into `build/viz/platform/`. Nothing needs the
container at view time.

Screenshots run Chromium headless with SwiftShader (software WebGL), so
`make viz-shots` takes several minutes. The harness wraps `viz/index.html`
unmodified like the Artifact host does (with `<meta charset="utf-8">`), under a
Content-Security-Policy modelled on the Artifact sandbox. Build machines
often cannot reach the CDNs, so Playwright request routing answers the page's
CDN URLs with byte-identical local copies (three.js 0.170.0 from the npm
registry tarball, the IBM Plex fonts; cached in `build/viz/vendor-cache/`);
`--cdn` uses the real CDNs. It exits non-zero on a host outside the
allowlist, a CSP violation, a page error, a viewer error state, horizontal
overflow, overlapping labels, failed picking or a GLB that does not load.

Shots (1440x900 unless noted): `viewer_iso` (whole die, labels), `viewer_top`,
`viewer_lowangle` (layer colours, layers spread), `viewer_lane` (zoomed on
lane 0 copy A: per-register labels), `viewer_inspector` (a picked cell's
tooltip), `viewer_parts` (Parts mode, lane 2 focused), `viewer_section`
(cross-section at x = 173 µm with the layer callout), `viewer_redundancy`
(flip-flops by copy, fences), `viewer_redundancy_lane0` (same-bit lines),
`viewer_dark`, `viewer_phone` / `viewer_phone_dark` (390x844, full page),
`glb_preview_full` / `glb_preview_portable` (the GLBs in three.js GLTFLoader).

## What the page shows

* **Colour by**: Layers (real layer colours), Parts (cell footprints coloured
  by part; layers up to met1 replaced by the footprints, upper metal faint),
  Lanes, Copies (copy A / copy B / thermal 0-2 / unprotected / shared).
* **3D labels**: HTML labels anchored to 3D points, re-projected every frame
  with 1 px leader lines; a layout pass (at most every 120 ms while moving,
  once at rest) places them greedily by priority with 4 px padding, avoiding
  each other and the HUD, with a budget of 15 labels (8 under 600 px) plus up
  to 40 register labels. Detail tiers by zoom (projected px per µm): tier 0
  (whole die) = fence regions, Lane 0-3 datapaths, pin-edge badges, clock
  root, layer-stack callout, compact shared parts; tier 1 = every compact
  part and the pin buses; tier 2 = spread parts and individual register
  labels (`L0 acc_a[5]`, `th1[0]`, ...). Parts spread over the whole die
  (clock tree, port and repair buffers) are list-only until zoomed. Labels
  toggle with **Labels**; clicking a label focuses its part.
* **Layer-stack callout** at the die corner nearest the camera (met5 ... nwell
  with z ranges in µm, one leader per layer); with the section on it points
  at the cut.
* **Parts panel**: every part with colour chip, cell count, cell area (µm²)
  and flip-flop bits; groups fold (folded by default on phones); the box
  shows/hides a part, the name or Focus flies the camera to it and dims
  everything else. "inferred" marks parts named from netlist cones.
* **Fences**: the five DEF REGIONS drawn as dashed, tinted outlines labeled
  "Copy A region", "Copy B region", "Thermal copy 0/1/2 region".
* **Picking**: hover (mouse) or tap (touch) any standard cell; a 10 µm bin grid
  over the footprints finds it. The tooltip shows the hierarchy crumb,
  instance name, master with a plain-language description and equation
  (all 143 masters of this run are decoded, see `FIXED_DESC` in
  `scripts/viz_parts.py`), drive strength, register group/copy/bit, the
  decoded Yosys cell suffix, the part and how it was attributed, what net cone
  a buffer serves, and the cell size, position and orientation. Click pins it.
* **IO pins** (DEF PINS, coloured by signal family, grouped into buses with
  compressed bit ranges such as `in_a[23:19,16]`), **power grid** (DEF
  SPECIALNETS VDD/VSS: met1 follow-pin rails, met4/met5 straps, DRC fill),
  **cell rows** (125 rows, 2.72 µm) and **fill cells** are toggles.
* **Cross-section**: a clipping plane across x or y with a position slider,
  "Section view" camera and "Keep other half"; the layer callout labels the
  layers at the cut. Labels anchored in the removed half are hidden, and a
  fence label moves to the middle of the part of its fence that is still drawn.
* **Redundant storage**: baseline vs separated numbers side by side, the
  flip-flop highlight by copy, a per-group table (click a row to draw lines
  between same-bit copies) and the list of what is still shared.
* Stats strip (clock, WNS, cells, flip-flops, rectangles), sky130 /
  not-radiation-qualified notice, provenance footer. Light and dark themes
  come only from CSS tokens on `:root` (the WebGL clear colour too);
  reduced motion disables camera animation; below 820 px the panel stacks
  under the canvas.

## Part attribution

`scripts/viz_parts.py` assigns **every** DEF component to exactly one part.
Deterministic, in two steps:

1. **Instance names and masters.** The flow keeps the RTL hierarchy in the
   names of the kept `orbit_keep_reg` copies and of CTS/resizer/physical
   cells: `g_lane[i].u_lane.u_{acc,res}_{a,b}` flip-flops -> Lane i /
   Accumulator|Result A|B, the same prefix on `mux2i`/`nor2b` gates -> Lane i /
   Load mux A|B; `u_thermal.u_copyK` -> Thermal / Copy K; `u_thermal.phase`,
   `out_valid_q`, `fault_q`; `clkbuf_*`/`clkload*` -> Clock tree;
   `input*`/`output*` -> IO port buffers; `place*`, `rebuffer*`, `wire*`,
   `split*`, `clone*` -> Timing-repair buffers; `hold*` or `dlygate`/`dlymetal`
   masters -> Hold-fix delay cells; `ANTENNA_*`, `tapvpwrvgnd`, `decap`,
   `fill` masters -> physical parts.
2. **Netlist cones for the anonymous `_NNNN_` cells** (synthesis flattened the
   multipliers, adders, comparators and control). Connectivity comes from the
   DEF NETS section, pin directions from the cell LEF. For every net two bit
   sets are propagated over the acyclic combinational graph (flip-flops and
   clock nets stop the cones): *fwd* = the register groups (via D) and output
   ports it reaches, *bwd* = the register groups (via Q) and input ports in its
   fan-in. The first matching rule names the cell:
   a. fwd only lane-i copy-A registers -> Adder A; only copy B -> Adder B;
      also cells fed only by one copy's Q (the accumulate feedback);
   b. fwd both copies of lane i and bwd only lane-i operand bytes of
      `in_a`/`in_b` -> Lane i / Multiplier (shared by both copies);
   c. bwd both copies of one lane, no control inputs -> Lane i / Mismatch
      comparator; several lanes -> Mismatch OR tree / fault_q;
   d. bwd only thermal copies -> Thermal voter; fwd into thermal copies/phase
      or bwd `temp_*` -> Thermal next-state logic;
   e. bwd only `rst_n` -> Reset distribution (also resizer buffers that carry
      only `rst_n`);
   f. fwd several lanes or the `out_valid_q`/`fault_q`/`in_ready`/`out_valid`
      logic -> Handshake / out_valid_q / enables;
   g. anything else -> Other logic.
   Named buffers keep their step-1 part; their cone result is stored as
   `serves` and shown in the inspector ("Buffers a net of: Lane 0 / Adder A").

Result for the committed data (18,175 components, 6,250 logic + 11,925
physical-only cells; **0 left in Other logic**):

| Part (per lane, lanes 0-3) | Cells | Source |
|---|---|---|
| Multiplier | 196-198 | netlist cone |
| Adder A / Adder B | 271-281 / 272-279 | netlist cone |
| Accumulator A, B, Result A, B | 32 each (32 FF bits) | instance name |
| Load mux A / B | 128-129 | instance name (128 = 64 `mux2i` + 64 `nor2b`; the 5 parts with 129 also hold one resizer `buf_4`, e.g. `g_lane[0].u_lane.u_acc_a/place1698`, that the resizer inserted inside the copy's hierarchy on the mux select net, so it keeps that prefix) |
| Mismatch comparator | 54-58 | netlist cone |

| Shared part | Cells | Source |
|---|---|---|
| Thermal copy 0 / 1 / 2 | 8 each (2 FF) | instance name |
| Thermal voter / next-state / phase flop | 3 / 18 / 1 | cone / cone / name |
| Mismatch OR tree / fault_q | 144 (1 FF) | cone (+ name for fault_q) |
| Handshake / out_valid_q / enables | 14 (1 FF) | cone (+ name) |
| Reset distribution | 6 | cone |
| Clock tree | 96 | name prefix |
| IO port buffers | 214 | name prefix |
| Timing-repair buffers | 976 | name prefix |
| Antenna diodes | 20 | name prefix |
| Well taps / fill | 1,524 / 10,381 | master |
| Hold-fix, tie, decap cells | 0 | (none in this run) |

The cone parts are **inferred** (marked so in the page and the GLB extras):
the counts depend on how synthesis shared logic, and a cell used by two
functions goes to the first matching rule. The timing-repair buffers are a
large, die-wide part because the resizer names them by prefix only; their
`serves` field says which datapath net each one buffers. The clock tree and
port/repair buffers spread over the whole die, so their labels are shown
only when zoomed in or selected.

## Data format

### layout.b64.txt (base64 of the binary block)

Little-endian after base64 decoding (the page uses `atob`; `format.encoding`
is `"base64"`, `format.bin_bytes` the decoded size).

| Offset | Size | Content |
|---|---|---|
| 0 | 8 | ASCII `ORBITVZ2` |
| 8 | 4 | uint32: number of layers |
| 12 | 4 | uint32: format version |
| per layer | `count * 4 * 2` | uint16 rectangles `x0,y0,x1,y1` at `layers[i].offset` |
| cells | | `cells.rect_offset`: uint16 x4 per placed cell; `master_offset`, `part_offset`, `serves_offset`: uint8 per cell |
| power | | `power.rect_offset`: uint16 x4 per VDD/VSS wire; `attr_offset`: uint8 layer index + 16 for VSS |

Coordinates are grid units relative to the die lower-left corner:
`x_um = x * format.grid_um` (10 nm; the 346.3 µm die does not fit 16 bits at
sky130's 5 nm grid, so values are rounded by at most 5 nm). Layer rectangles
come from KLayout (all shapes of a GDS layer flattened; the smaller of the
merged horizontal slabs, vertical slabs or original boxes is kept). Cell boxes
are DEF `PLACED` origin + LEF `SIZE`.

### layout.json

`format`, `design`, `die_um`, `core_um`, `stack_top_um`, `layers[]` (name,
GDS layer/datatype, colour, z, thickness and their sources, count, offset),
`stats` (clock, WNS, area, cells, with sources), `redundancy` (`groups` with
distances, `flops` with every flip-flop's name, group, copy, bit and box,
`summary`, and `baseline` with the same numbers for the unconstrained run),
`cells` (names, masters, `master_info` descriptions, orientations and the
binary offsets), `parts` (`list` with id, name, group, lane, kind, category,
source, cells, area, FF bits, bbox/core/centroid/anchor; `kinds` colours;
`counts`; `method`), `pins` (every DEF pin with layer, box, side, bus and
family; `groups` per bus and edge; `sides` counts), `power`, `rows`,
`regions` (fence boxes, labels, member counts, separation numbers,
unconstrained common-mode list), `glb` (paths, sizes, node names), `inputs`,
`tools`.

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
  budget (`--bin-budget-mb`, default 8 MB); above it, diff/tap/poly/licon1/li1/mcon
  are cut to a detail window around the core centre and the window is drawn on
  the die. For the current orbit_demo run the whole die fits (750,439 rectangles), so nothing is cut.
* **Colours** loosely follow the KLayout/Magic sky130 conventions (poly red,
  diff green, li1 lilac, met1 blue, met2 pink, met3 teal, met4 amber, met5
  copper); they are not the PDK's `.lyp` stipples.

## The GLBs

Both files share one node tree (names are `[A-Za-z0-9_]`, at most 63 bytes):

```
orbit_demo_sky130hd
  Die_Substrate
  Layers        nwell diff tap poly licon1 li1 mcon met1 via met2 via2 met3 via3 met4 via4 met5
  Parts
    Lane_0 .. Lane_3     LaneN_Multiplier, LaneN_Adder_A, LaneN_Adder_B, LaneN_Accumulator_A/B,
                         LaneN_Result_A/B, LaneN_Load_mux_A/B, LaneN_Mismatch_comparator
    Thermal_TMR          Thermal_Copy_0/1/2, Thermal_Voter, Thermal_Next_state_logic,
                         Thermal_Throttle_phase_flop
    Shared_control       Mismatch_OR_tree_fault_q, Handshake_out_valid_q_enables, Reset_distribution_rst_n
    Physical             Clock_tree, IO_port_buffers, Timing_repair_buffers, Antenna_diodes,
                         Well_tap_cells, Fill_cells
  Pins          Pins_in_a, Pins_in_b, Pins_out_data, Pins_clk, Pins_rst_n, Pins_temp_c,
                Pins_handshake, Pins_fault, Pins_thermal_status
  Regions       Region_Copy_A, Region_Copy_B, Region_Thermal_copy_0/1/2
```

Part nodes hold one box per placed cell footprint (z -0.2 to 0 µm, a thin tile
under the layout, display only), with the part's colour as material and
`extras` (`display_name` such as "Lane 0 / Accumulator A", part id, cell
count, area, FF bits, source, label anchor). Pins are markers at their DEF pin
shapes (drawn from the pin layer to 1 µm above the stack); regions are 0.8 µm
outline walls. The root node's extras state units and axes.

**Units: 1 unit = 1 µm.** Axes: +X = layout x, +Y = up, -Z = layout y; origin
at the die centre; z = 0 at the substrate surface; heights are true scale
(the stack is 6.57 µm on a 346 µm die; scale Y in the viewer to exaggerate).
No exaggerated variant is written by default (`--glb-z-scale` bakes one in).

| File | Content | Encoding | Size |
|---|---|---|---|
| `orbit_demo_sky130hd_3d_full.glb` | all 16 layers, 768,850 boxes, whole die + parts/pins/regions | `KHR_draco_mesh_compression` via `@gltf-transform/cli` (uncompressed it would exceed 40 MB) | 9.2 MB |
| `orbit_demo_sky130hd_3d.glb` | met1-met5 + vias (190,165 boxes) + parts/pins/regions | `KHR_mesh_quantization` int16 positions, 10 nm step | 12.8 MB |

Verified: the Khronos validator (`gltf-transform validate`) reports 0 errors
and 0 warnings for both (the Draco file lists its compressed buffer views as
"unused", which is expected); pygltflib loads both (98 / 91 nodes); trimesh
loads the portable file (bounds ±173 µm, -1.2 to 7.6 µm; trimesh cannot
decode Draco); and `make viz-shots` loads both with three.js GLTFLoader (+
DRACOLoader), finds every expected node with `getObjectByName` and renders
`glb_preview_full.png` / `glb_preview_portable.png`. Blender's glTF importer
supports both extensions; it was not run here.

## Redundant storage

Flip-flops are the DEF components whose master matches
`sky130_fd_sc_hd__{,e,s,se}df*`; their group, copy and bit come from the
instance names (docs/SPEC.md section 7). For each duplicated or triplicated
group the pipeline reports centroid distances and min/median/max same-bit
distances (centre to centre and edge to edge) and touching same-bit pairs,
for this layout and for the baseline DEF. For the committed data:

| Measure | Baseline | Separated |
|---|---|---|
| Closest same-bit pair, acc/res A vs B | 2.76 µm | 251.18 µm |
| Closest same-bit pair, thermal | 5.52 µm | 97.92 µm |
| Same-bit pairs in touching cells | 13 of 262 | 0 of 262 |
| Smallest gap, any copy A vs copy B flip-flop | 0.00 µm | 242.94 µm |
| Copy centroid distance, acc/res | 17.3-46.3 µm | 288.3-296.0 µm |

These match the pdsep area's own measurements (`reports/pdsep/separation.md`).
The fences do not separate the clock and reset trees, the shared multipliers,
the comparators/OR tree, the thermal voter, the ports, or the unprotected
phase/out_valid_q/fault_q flops; distances are geometry, not an upset-rate
model. See `reports/viz/redundancy_placement.md`.

## Viewer notes

* One instanced mesh per layer (the rectangle array is a per-instance
  attribute; the vertex shader builds each box), one instanced mesh for all
  18,175 cell footprints coloured through a 256-entry part texture, so colour
  mode, selection and show/hide are texture/uniform changes. Renders on
  demand, caps the pixel ratio at 2.
* Harness hooks: `window.orbitViz` (`setView`, `setMode`, `focusPart`,
  `focusLane`, `selectGroup`, `pickAt`, `labels`, `cellScreen`, ...).
* WebGL 2 is required; the page says so if it is missing, and shows a readable
  error if the data fail to load or do not match.
