# orbit_demo physical design (sky130hd, variant sep)

Package section 06_physical_design of `orbit_demo_design_review`, written 2026-10-06. Links are relative to this file. Paths in backticks that start with `build/` or `viz/` are repository paths (repo `/home/user/chip`) that are not in the package. The `pd/`, `scripts/` and `mk/` files cited here are copied byte-identical under [04_digital_design/source/](../04_digital_design/source/), except `scripts/viz_parts.py` (repository only); `reports/pdsep/` is copied under [07_verification/published_reports/](../07_verification/published_reports/) except its GDS archive (see Related evidence below). Repository HEAD at writing: 54745f7; `git diff 0495cfa 54745f7 -- rtl pd mk scripts reports docs viz` is empty, so the design sources are those of the package commit in the revision table. Discrepancies are listed in the discrepancy register (09_review_notes).

Status labels: **VERIFIED** = a tool log or report shows it. **REPRODUCED 2026-10-06** = re-run for this package. **TARGET** = design goal, not measured. **ASSUMPTION**. **CLAIM (unverified)** = stated in a document, no log found. **MISSING**. **N/A** = not applicable (reason given).

This section covers only the reviewed layout (variant `sep`, 7.2 ns). The reference layouts are not the reviewed layout. Baseline (variant `base`, 7.0 ns) numbers appear only as comparison values (section 4.2 here; [07_verification/baseline_reference/](../07_verification/baseline_reference/)). No IHP SG13G2 result is used in this section. The ORBIT-AI brief's 16-tile architecture, 200-800 MHz clock target and 40 W sizing assumption describe a different, unbuilt chip and have no counterpart in this layout.

## Design revision covered by this package

| Item | Revision / identifier | Note |
|---|---|---|
| Design | orbit_demo (ORBIT-AI 4-lane INT8 digital demonstrator) | top module `orbit_demo`, LANES=4 |
| RTL | rtl/orbit_demo.v, orbit_mac_lane.v, orbit_thermal_tmr.v, orbit_keep_reg.v at git commit 26566f0 (2026-09-29 18:54 UTC); unchanged through the package commit | sha256 a3fffb22… / efef3d33… / bba77a5a… / ea05bdc1… (full hashes in MANIFEST.sha256 at the package root) |
| Specification | docs/SPEC.md at 26566f0 (never revised) | sha256 aef5d9fb… |
| Concept brief | docs/orbit-ai-design-brief.pdf, "ORBIT-AI v0.1, 29 September 2026" (never revised; describes an earlier project state, see discrepancy register) | sha256 9d5f33d3… |
| Reviewed layout | ORFS sky130hd, variant `sep` (copy-separation fences), run 2026-09-29 21:56–22:12 UTC, outputs build/pd_sep/results/sky130hd/orbit_demo/sep/ | 6_final.gds sha256 cd19afa9…; 6_final.def f5c544f3…; 6_final.v 68093c41…; 6_final.spef 014e655a… |
| Layout configuration | pd/sky130hd_sep/config.mk and regions.tcl at c10c59b; constraint.sdc at 21917cf (`set clk_period 7.2`) | The run (21:56 UTC) used config.mk/regions.tcl as in ed553f8, identical to c10c59b once comments are stripped. It used the working-tree constraint.sdc with period 7.2 ns, which was committed in 21917cf at 22:00 UTC and is byte-identical to the flow copy build/pd_sep/sdc/sky130hd/sep.sdc. ed553f8's constraint.sdc has a 7.0 ns period, so a rebuild must not use it |
| Flow / tools | ORFS docker image tag openroad/orfs:latest; the only local image is sha256:2e5bf6fe865e… (created 2026-09-29 02:00 UTC, before the run). Linking the run to this digest is an ASSUMPTION: the run logged no digest. OpenROAD prints version "unknown". KLayout 0.30.12 (DRC/LVS). Yosys 0.69+154 (local sims/schematics) | No PDK commit is recorded in the logs |
| Process / library | SkyWater SKY130, sky130_fd_sc_hd, liberty sky130_fd_sc_hd__tt_025C_1v80 (the single corner ORFS optimised at) | — |
| Package assembled | 2026-10-06; design inputs copied from the repository tree at commit 0495cfa (branch claude/hopeful-rubin-0yf8io) | Every later commit on the branch changes only review/ or is empty (git diff --name-only 0495cfa..HEAD outside review/ is empty). Re-runs made for this package are dated 2026-10-06 |

Other implementations in the repo (sky130hd baseline at 7.0 ns, variant `base`; IHP SG13G2) are reference runs only and are NOT the reviewed layout.

Notes for this section: the image tag is set in `mk/pdsep.mk` line 25 and logged in `build/pd_sep/make_pd_sep.out` line 1. The ORFS commit and the open_pdks / skywater-pdk version are MISSING (not logged; the image's `/OpenROAD-flow-scripts` is not a git repository).

## Contents of this folder

| Path | Content | Origin |
|---|---|---|
| [layout_db/](layout_db/) | final GDS, DEF, SPEF, gate netlist (gzip), final SDC, clock period | copied from `build/pd_sep/results/sky130hd/orbit_demo/sep/` |
| [klayout_views/](klayout_views/) | 10 KLayout renders of the final GDS (v01-v08) and [render_gds.py](klayout_views/render_gds.py) | rendered for this package, KLayout 0.30.12 Python module |
| [orfs_images/](orfs_images/) | 10 OpenROAD GUI images written by the ORFS final report step | copied from `build/pd_sep/reports/sky130hd/orbit_demo/sep/` |
| [floorplan_plot/](floorplan_plot/) | [floorplan_fences_pins.png](floorplan_plot/floorplan_fences_pins.png) and its script [plot_floorplan.py](floorplan_plot/plot_floorplan.py) | plotted for this package from package files only |
| [physical_design.pdf](physical_design.pdf) | this document rendered to PDF | `md2pdf.py README.md physical_design.pdf` |

Related evidence elsewhere in the package: ORFS step logs [07_verification/orfs_logs/](../07_verification/orfs_logs/) (byte-identical copies of 39 of the 40 files in `build/pd_sep/logs/sky130hd/orbit_demo/sep/`; `5_1_grt.json` not copied), ORFS reports [07_verification/orfs_reports/](../07_verification/orfs_reports/) (all non-image report files of `build/pd_sep/reports/sky130hd/orbit_demo/sep/` except `drt_antennas.log` and `grt_antennas.log`), the published copy-separation reports [07_verification/published_reports/](../07_verification/published_reports/) (= `reports/pdsep/` except `orbit_demo_sky130hd_sep.gds.gz`, the same GDS as [layout_db/6_final.gds.gz](layout_db/6_final.gds.gz)), the pin table [08_pinout_packaging/pinout.csv](../08_pinout_packaging/pinout.csv), the ORFS design configuration [04_digital_design/source/pd/sky130hd_sep/](../04_digital_design/source/pd/sky130hd_sep/config.mk), and the LVS reference netlist [03_schematics/netlists/6_final.cdl.gz](../03_schematics/netlists/6_final.cdl.gz).

## 1. Layout database inventory

Run: `make pd-sep` (ORFS, sky130hd, variant `sep`), files written 2026-09-29 UTC. The sha256 values are of the uncompressed originals in `build/pd_sep/results/sky130hd/orbit_demo/sep/`. Check made for this package: `gunzip -c <file>.gz | sha256sum` compared with `sha256sum` of the build file, and `gzip -t` on all four archives: all four match, archives intact (**REPRODUCED 2026-10-06**).

| Package file | Original in `build/pd_sep/results/sky130hd/orbit_demo/sep/` (mtime UTC) | Bytes .gz / uncompressed | gunzip = build | Status |
|---|---|---|---|---|
| [6_final.gds.gz](layout_db/6_final.gds.gz) | `6_final.gds` (22:09:49) | 1088094 / 8174720 | match | REPRODUCED 2026-10-06 |
| [6_final.def.gz](layout_db/6_final.def.gz) | `6_final.def` (22:09:33) | 852148 / 6992153 | match | REPRODUCED 2026-10-06 |
| [6_final.spef.gz](layout_db/6_final.spef.gz) | `6_final.spef` (22:09:39) | 1956262 / 6827076 | match | REPRODUCED 2026-10-06 |
| [6_final.v.gz](layout_db/6_final.v.gz) | `6_final.v` (22:09:33) | 96856 / 812562 | match | REPRODUCED 2026-10-06 |
| [6_final.sdc](layout_db/6_final.sdc) | `6_final.sdc` (22:09:33) | - / 19270 | byte-identical (cmp) | REPRODUCED 2026-10-06 |
| [clock_period.txt](layout_db/clock_period.txt) | `clock_period.txt` (21:56:09), content `7.2` | - / 4 | byte-identical (cmp) | REPRODUCED 2026-10-06 |

| File (uncompressed original) | sha256 |
|---|---|
| 6_final.gds | `cd19afa93221c8468567278bcd627657bd6841f5ace7e0bbe749e0c76b93bc64` |
| 6_final.def | `f5c544f37701038b0cf24fdc09481c58b249c425539b229d000ccb8a9df20ec1` |
| 6_final.spef | `014e655ae938245ace4ebc279b9c6c311ddf57f23bfae44367af342aeb8d5acb` |
| 6_final.v | `68093c41fca50e9e532205b1128490a1e7807e63d998ff1a179ca985981c8b06` |
| 6_final.sdc | `1dbe8e7e8cd2853f6b5d533496b080b2aca8bfa82e5f10ed1714f37922409680` |
| clock_period.txt | `69cd84998732b964b8b9c218f595f2aa1c438cd71d725a2542227075cd721969` |

What the files contain:

| File | Content (checked for this package) | Source / conditions | Status |
|---|---|---|---|
| 6_final.gds | top cell `orbit_demo`, 154 cells, dbu 0.001 um, bbox (0,0;346.295,346.295) um; identical to `6_1_merged.gds` (same size) | read with KLayout 0.30.12 Python module (`klayout.db`) | REPRODUCED 2026-10-06 |
| 6_final.gds merge | "All LEF cells have matching GDS/OAS cells", "No orphan cells in the final layout"; standard-cell GDS `sky130_fd_sc_hd.gds` of the ORFS sky130hd platform | [6_1_merge.log](../07_verification/orfs_logs/6_1_merge.log) lines 1-5, KLayout 0.30.12 | VERIFIED |
| 6_final.def | DEF 5.8, `UNITS DISTANCE MICRONS 1000`, `DIEAREA ( 0 0 ) ( 346295 346295 )`, 125 `ROW`s, `REGIONS 5`, `COMPONENTS 18175`, `PINS 217`, `SPECIALNETS 2`, `NETS 6886`, `GROUPS 5` | decompressed lines 1-6, 7-131, 162-168, 169, 18346, 19239-27606, 27607, 126373-126769 | REPRODUCED 2026-10-06 |
| 6_final.spef | IEEE 1481-1999, written by OpenROAD (`*VERSION "unknown"`) 22:09:39; OpenRCX with `platforms/sky130hd/rcx_patterns.rules`, one extraction corner `X`, coupling threshold 0.1 fF; 6886 nets, 30095 rsegs, 60471 coupling caps | SPEF header; [6_report.log](../07_verification/orfs_logs/6_report.log) lines 16-26. Provenance/qualification of `rcx_patterns.rules`: MISSING | VERIFIED |
| 6_final.v | routed gate netlist, module `orbit_demo`, 18 ports / 215 bits, 6250 cell instances; fill, tap and antenna-diode cells are not written; no VDD/VSS ports | `zcat` + count of `sky130_*` instance lines | REPRODUCED 2026-10-06 |
| 6_final.sdc | `create_clock -name clk -period 7.2000`, `set_propagated_clock`, 79 `set_input_delay` and 135 `set_output_delay` of 1.44 ns (0.2 x period, an ASSUMPTION of the SDC for the unknown outside world) | file lines 8-10; constraint source [constraint.sdc](../04_digital_design/source/pd/sky130hd_sep/constraint.sdc) | VERIFIED |

Not in this folder: `6_final.odb` (14668665 bytes, needed to re-run OpenROAD STA/PSM directly; build path only), the LVS database `6_lvs.lvsdb` and `6_final_concat.cdl` (build only). The CDL `6_final.cdl` is in [03_schematics/netlists/](../03_schematics/netlists/6_final.cdl.gz); the KLayout LVS extracted netlist `orbit_demo_extracted.cir` is in [07_verification/lvs/](../07_verification/lvs/orbit_demo_extracted.cir.gz).

## 2. Run settings that shape the layout

| Setting | Value | Source | Status |
|---|---|---|---|
| Design config | `SYNTH_KEEP_MODULES = *orbit_keep_reg*`; `CORE_UTILIZATION 40`, `CORE_ASPECT_RATIO 1`, `CORE_MARGIN 2`, `PLACE_DENSITY_LB_ADDON 0.20`; `PLACE_PINS_ARGS = -min_distance 2 -min_distance_in_tracks`; `TNS_END_PERCENT 100`; `POST_FLOORPLAN_TCL = regions.tcl`, `PDSEP_FLOORPLAN edges`, `PDSEP_REGION_TYPE EXCLUSIVE`, `ENABLE_DPO 0`, `SLEW_MARGIN 20`, `CAP_MARGIN 20` | [config.mk](../04_digital_design/source/pd/sky130hd_sep/config.mk) lines 30, 35-42, 66-71 | VERIFIED (used values appear in the logs, e.g. 2_1_floorplan.log line 16, 3_2_place_iop.log line 10) |
| Liberty | `sky130_fd_sc_hd__tt_025C_1v80.lib` only (TT, 25 C, 1.80 V) | every step log, line 6 (e.g. [2_1_floorplan.log](../07_verification/orfs_logs/2_1_floorplan.log)) | VERIFIED |
| Tools | OpenROAD version printed as `unknown` (`-GPU +GUI -Python`); KLayout 0.30.12 (merge, DRC, LVS); Yosys 0.68+post (synthesis, git sha1 UNKNOWN) | log line 1 of each step; [1_2_yosys.log](../07_verification/orfs_logs/1_2_yosys.log) line 1 | VERIFIED; OpenROAD and ORFS commits MISSING |
| Platform scripts | ORFS `platforms/sky130hd/{pdn.tcl, tapcell.tcl, config.mk}` are not logged; values quoted below from the image on this host match the DEF | read from the image layer on this host 2026-10-06 | ASSUMPTION (same image as the run) |

## 3. Floorplan

![floorplan summary plot](floorplan_plot/floorplan_fences_pins.png){: style="width:78%"}

*Figure F1. Source: [plot_floorplan.py](floorplan_plot/plot_floorplan.py) (matplotlib, rvenv Python 3.11) reading [regions.json](../07_verification/published_reports/regions.json) (die, core, fence boxes, the 518 redundant flip-flop cell boxes from the routed DEF), [pinout.csv](../08_pinout_packaging/pinout.csv) (215 signal pin origins and layers) and [6_final.def.gz](layout_db/6_final.def.gz) SPECIALNETS (met4/met5 strap centre lines). The dotted line only joins the two endpoints of the worst setup path; it is not the route.*

Floorplan command: `initialize_floorplan -utilization 40 -aspect_ratio 1 -core_space 2 -site unithd` ([2_1_floorplan.log](../07_verification/orfs_logs/2_1_floorplan.log) line 16).

| Item | Value | Source | Status |
|---|---|---|---|
| Die | (0, 0) - (346.295, 346.295) um, 119920 um^2 | [2_1_floorplan.log](../07_verification/orfs_logs/2_1_floorplan.log) line 20; DEF line 6 | VERIFIED |
| Core | (2.300, 2.720) - (344.080, 342.720) um = 341.780 x 340.000 um, 116205.200 um^2; lower-left snapped from (2.000, 2.000) (IFP-0028) | 2_1_floorplan.log lines 18, 21-22 | VERIFIED |
| Rows | 125 rows x 743 sites `unithd` (site 0.46 x 2.72 um), alternating N / FS, x 2.30-344.08 um | 2_1_floorplan.log line 19 (IFP-0001); DEF `ROW` lines 7-131 (`STEP 460`, row pitch 2720) | VERIFIED |
| Macros | none ("Found 0 macro blocks") | [3_2_place_iop.log](../07_verification/orfs_logs/3_2_place_iop.log) line 11 | N/A: standard-cell-only block |
| Utilization | target 40 % (config); effective 0.403 at floorplan (46866.198 um^2 synthesis cell area); 41 % after floorplan repair_timing; 43 % after tap cells; final 54 % (`Design area 62300 um^2`, i.e. cell area excluding fill, including tap: 62299.8 um^2 / 116205.2 um^2 = 0.536) | 2_1_floorplan.log lines 24, 398; [2_3_floorplan_tapcell.log](../07_verification/orfs_logs/2_3_floorplan_tapcell.log) line 11; [6_report.log](../07_verification/orfs_logs/6_report.log) line 67; [results.md](../07_verification/published_reports/results.md) lines 42-44 | VERIFIED |
| Placement density | `global_placement -skip_io`: 0.53 = 0.40 lower bound + (1 - 0.40) x `PLACE_DENSITY_LB_ADDON` 0.20 + 0.01; main (timing- and routability-driven) global placement: 0.546 (lower bound 0.42) | [3_1_place_gp_skip_io.log](../07_verification/orfs_logs/3_1_place_gp_skip_io.log) lines 11-12; [3_3_place_gp.log](../07_verification/orfs_logs/3_3_place_gp.log) lines 15-16; formula from ORFS `flow/scripts/util.tcl` line 198 in the image on this host | VERIFIED (values); formula ASSUMPTION (same script as the run) |
| Tap cells | 1524 `sky130_fd_sc_hd__tapvpwrvgnd_1`, inserted before placement | 2_3_floorplan_tapcell.log line 10 (TAP-0005); DEF COMPONENTS | VERIFIED |
| Tap arrangement | 123 rows with 12 taps at 27.6 um pitch, alternate rows offset by 13.8 um (checkerboard); first and last row 24 taps at 13.8 um; platform `tapcell -distance 14`; conditions: arrangement measured on the DEF; script value from the current image | DEF COMPONENTS (counted per row); `platforms/sky130hd/tapcell.tcl` line 2 in the image | REPRODUCED 2026-10-06 (arrangement); ASSUMPTION (script) |
| Filler cells | 10381 (53905.45 um^2): `fill_8` 3465, `fill_1` 2521, `fill_2` 2369, `fill_4` 2026; conditions: `filler_placement` with fill_1/2/4/8 only | [5_3_fillcell.log](../07_verification/orfs_logs/5_3_fillcell.log) lines 10-11; 6_report.log line 52; DEF COMPONENTS | VERIFIED |
| Decap cells | 0. The filler list contains no decap master; `sky130_ef_sc_hd__decap_12` "is loaded but not used in the design". `results.md` labels the 10381 filler cells "fill/decap"; see discrepancy register (09_review_notes). Decoupling capacitance budget: MISSING | 5_3_fillcell.log line 10; 2_1_floorplan.log line 10; DEF COMPONENTS (no `decap` master) | VERIFIED |
| Metal fill / density | not run: step 6_1_fill only copies the ODB (`exec cp ... 5_route.odb ... 6_1_fill.odb`); no density rules in the KLayout deck. The tech LEF `sky130_fd_sc_hd.tlef` lists `MAXIMUMDENSITY 70` (window 700 x 700, step 70) for met1-met4 (image copy, ASSUMPTION same file as the run); no step checks it | [6_1_fill.log](../07_verification/orfs_logs/6_1_fill.log) line 10 | VERIFIED (not run); fill and density check MISSING |
| Other physical cells | 20 `diode_2` antenna-repair cells; 6 `conb_1` tie cells (RSZ-0042) | 6_report.log lines 51-61; 2_1_floorplan.log line 31 | VERIFIED |

Final cell report (6_report.log lines 51-61, **VERIFIED**):

| Cell type | Count | Area (um^2) |
|---|---|---|
| Fill cell | 10381 | 53905.45 |
| Tap cell | 1524 | 1906.83 |
| Antenna cell | 20 | 50.05 |
| Clock buffer | 88 | 1672.85 |
| Timing Repair Buffer | 1201 | 9959.55 |
| Inverter | 171 | 648.12 |
| Clock inverter | 8 | 127.62 |
| Sequential cell | 521 | 10430.00 |
| Multi-Input combinational cell | 4261 | 37504.72 |
| Total | 18175 | 116205.20 |

### 3.1 Power distribution network

One voltage domain `CORE` (VDD/VSS). [2_4_floorplan_pdn.log](../07_verification/orfs_logs/2_4_floorplan_pdn.log) records only `[INFO PDN-0001] Inserting grid: grid` (line 12) and two `PDN-1051` warnings for the empty macro grids (lines 10-11), so the geometry below is measured from the DEF SPECIALNETS ([6_final.def.gz](layout_db/6_final.def.gz), decompressed lines 19239-27606). The values agree with `platforms/sky130hd/pdn.tcl` lines 21-26 in the image on this host (ASSUMPTION that the run used the same script).

| Layer | Use | Width (um) | Pitch per net (um) | Position / offset | VDD / VSS shapes | Source | Status |
|---|---|---|---|---|---|---|---|
| met1 | followpin rails on every row boundary | 0.48 | 5.44 | x 2.30-344.08 um | 63 / 63 | DEF SPECIALNETS (`SHAPE FOLLOWPIN`) | REPRODUCED 2026-10-06 |
| met4 | vertical straps | 1.60 | 27.14 | VSS from x 15.87 um (core x0 + 13.57), VDD from x 29.44 um; VDD-VSS 13.57 um | 12 / 13 | DEF SPECIALNETS (`SHAPE STRIPE`) | REPRODUCED 2026-10-06 |
| met5 | horizontal straps; also the VDD/VSS pins | 1.60 | 27.20 | VSS from y 16.32 um (core y0 + 13.6), VDD from y 29.92 um; x 2.30-344.08 um | 12 / 13 | DEF SPECIALNETS and PINS (VDD/VSS `+ LAYER met5`, decompressed lines 18347-18376) | REPRODUCED 2026-10-06 |
| via stack met1-met4 | `via`/`via2`/`via3` arrays 1.6 x 0.48 um at every followpin x met4 crossing | - | - | - | 756 / 819 of each via level | DEF SPECIALNETS (`via2_3_1600_480_1_5_320_320`, `via3_4_1600_480_1_4_400_400`, `via4_5_1600_480_1_4_400_400`) | REPRODUCED 2026-10-06 |
| via4 met4-met5 | 1.6 x 1.6 um at every met4 x met5 crossing of the same net | - | - | - | 144 / 169 | DEF SPECIALNETS (`via5_6_1600_1600_1_1_1600_1600`) | REPRODUCED 2026-10-06 |

Static IR drop of this grid (OpenROAD PSM `analyze_power_grid`, corner `default`, VDD 1.80 V / VSS 0.0 V, total power 5.21e-02 W from `report_power` with the tool's default switching activity, TT 25 C, OpenRCX parasitics, 7.2 ns): VDD worst 4.54e-04 V (0.454 mV), average 9.58e-05 V; VSS worst 6.28e-04 V (0.628 mV), average 8.72e-05 V; 0.03 % each; "All shapes on net VDD/VSS are connected". Source [6_report.log](../07_verification/orfs_logs/6_report.log) lines 27-50 (**VERIFIED**); same values from a PSM re-run on `6_final.odb` ([ir.log](../07_verification/rerun_2026-10-06/pd_sep/ir.log), [ir.tcl](../07_verification/rerun_2026-10-06/pd_sep/ir.tcl); **REPRODUCED 2026-10-06**). The activity is not a workload activity (ASSUMPTION of the tool default). The re-run also computed PSM EM currents at the same default activity (`-enable_em`): maximum resistor current VDD 4.05e-04 A, VSS 4.33e-04 A (ir.log lines 17-23, 36-42; REPRODUCED 2026-10-06). The tech LEF read by the run, `sky130_fd_sc_hd.tlef` ([1_synth.log](../07_verification/orfs_logs/1_synth.log) line 7), contains `DCCURRENTDENSITY`/`ACCURRENTDENSITY` limits for mcon, met1-met5 and via-via4 (e.g. met1 `DCCURRENTDENSITY AVERAGE 2.8` mA/um; read from the image copy on this host, ASSUMPTION same file as the run). The comparison of the PSM currents with these limits: MISSING. Dynamic IR drop: MISSING (needs switching activity from simulation).

### 3.2 IO pin placement

The layout is a core block: there is no pad ring, IO cells, ESD structures, bond pads or package (N/A: not designed; see 08_pinout_packaging). Pin locations are tool output, not a specified pinout: `global_placement -skip_io` ran first, then `place_pins`, and no pin constraint exists in `pd/`, `scripts/` or `mk/`. A pinout specification is MISSING.

| Item | Value | Source | Status |
|---|---|---|---|
| Command | `place_pins -hor_layers met3 -ver_layers met2 -min_distance 2 -min_distance_in_tracks` (layers from the platform defaults `IO_PLACER_H met3`, `IO_PLACER_V met2`) | [3_2_place_iop.log](../07_verification/orfs_logs/3_2_place_iop.log) line 10; config.mk line 40 | VERIFIED |
| Pins | 215 signal I/O, all with sinks, 1254 available slots, I/O nets HPWL 34567.11 um | 3_2_place_iop.log lines 12-18 | VERIFIED |
| DEF pins | 217 = 215 signal + `VDD` (USE POWER) + `VSS` (USE GROUND); VDD/VSS pins are the met5 straps (FIXED) | DEF line 18346 `PINS 217 ;` and PINS section | VERIFIED |
| Edges and layers | W 102 and E 29 on met3 (shape 0.8 x 0.3 um); S 42 and N 42 on met2 (shape 0.14 x 0.485 um); `clk` at W (0.400, 334.900) um | [pinout.csv](../08_pinout_packaging/pinout.csv); DEF lines 18382-18393 | REPRODUCED 2026-10-06 |
| Minimum pin pitch | 1.36 um on W/E (2 met3 tracks of 0.68 um), 0.92 um on N/S (2 met2 tracks of 0.46 um) | computed from pinout.csv; DEF `TRACKS` lines 136-139 | REPRODUCED 2026-10-06 |

The worst setup path starts at `in_a[27]` on the E edge (345.895, 109.140) um and ends at `g_lane[3].u_lane.u_res_a/q[29]` inside the copy-A fence (cell box x 43.70-51.06 um, y 108.80-111.52 um in regions.json; Figure F1; [worst_setup_path.txt](../07_verification/published_reports/worst_setup_path.txt)). Full pin table and lane/bit mapping: [08_pinout_packaging/pinout.csv](../08_pinout_packaging/pinout.csv).

## 4. Copy-separation fences

Mechanism ([regions.tcl](../04_digital_design/source/pd/sky130hd_sep/regions.tcl), run as `POST_FLOORPLAN_TCL` at the end of the floorplan step): one OpenDB `dbRegion` (one box, snapped to the site grid and row boundaries) and one `dbGroup` per copy, region type EXCLUSIVE, written to the DEF as `TYPE FENCE`. Members are selected by instance name: `^g_lane\[[0-9]+\]\.u_lane\.u_(acc|res)_a/` (copy A), `..._b/` (copy B), `^u_thermal\.u_copyK/` (thermal copies, lines 77-83); the script stops the flow if a group's flip-flop count differs from 256/256/2/2/2 (lines 85, 170-175). `improve_placement` is disabled (`ENABLE_DPO 0`) because it does not keep the fences legal (published [mechanism_test.txt](../07_verification/published_reports/mechanism_test.txt); test run on the baseline's `3_2_place_iop.odb`, not on this run). Everything else (multipliers, adders, comparators, voter, control, clock tree, port buffers) is unconstrained.

### 4.1 Regions

From [regions.json](../07_verification/published_reports/regions.json) (generator [`scripts/pdsep_separation.py`](../04_digital_design/source/scripts/pdsep_separation.py), source `build/pd_sep/results/sky130hd/orbit_demo/sep/6_final.def`); boxes agree with DEF `REGIONS` (decompressed lines 162-168) and the floorplan log ([2_1_floorplan.log](../07_verification/orfs_logs/2_1_floorplan.log) lines 400-404). **VERIFIED**; regions.json re-generated byte-identical on 2026-10-06 (**REPRODUCED 2026-10-06**).

| Region (group) | Holds | Box (x0, y0) - (x1, y1) um | Size um | Members at floorplan | Members in routed DEF | Flip-flops |
|---|---|---|---|---|---|---|
| pdsep_copyA (pdsep_grp_copyA) | copy A of every accumulator/result pair: `u_acc_a` + `u_res_a`, lanes 0-3 | (2.30, 2.72) - (52.44, 342.72) | 50.14 x 340.00 | 824 | 768 | 256 |
| pdsep_copyB (pdsep_grp_copyB) | copy B: `u_acc_b` + `u_res_b`, lanes 0-3 | (293.94, 2.72) - (344.08, 342.72) | 50.14 x 340.00 | 824 | 768 | 256 |
| pdsep_th0 (pdsep_grp_th0) | thermal state copy `u_thermal.u_copy0` | (161.92, 272.00) - (184.92, 288.32) | 23.00 x 16.32 | 8 | 8 | 2 |
| pdsep_th1 (pdsep_grp_th1) | `u_thermal.u_copy1` | (161.92, 165.92) - (184.92, 182.24) | 23.00 x 16.32 | 8 | 8 | 2 |
| pdsep_th2 (pdsep_grp_th2) | `u_thermal.u_copy2` | (161.92, 57.12) - (184.92, 73.44) | 23.00 x 16.32 | 8 | 8 | 2 |

The 824 -> 768 change per copy group is the synthesis buffers removed before global placement ("Removed 182 buffers", [3_3_place_gp.log](../07_verification/orfs_logs/3_3_place_gp.log) line 10); the routed DEF `GROUPS` section holds 768/768/8/8/8 members (counted for this package). Copy-A/B members: the 256 kept flip-flops plus 256 `mux2i_1` and 256 `nor2b_1` enable/reset gates. Thermal members: 2 `dfxtp_1`, 2 `mux2i_1`, 1 `nor2b_1`, 1 `nand2_1` and the 2 `conb_1` tie cells inserted by `repair_tie_fanout` (RSZ-0042, 2_1_floorplan.log line 31, before `regions.tcl` runs at line 399). Resizer and CTS buffers are not members.

Fence edge-to-edge gaps ([separation.md](../07_verification/published_reports/separation.md), region-pair table): copyA/copyB 241.50 um; copyA to th0/th1/th2 109.48 um; copyB to th0/th1/th2 109.02 um; th0/th1 89.76 um; th1/th2 92.48 um; th0/th2 198.56 um (**VERIFIED**, **REPRODUCED 2026-10-06**).

### 4.2 Separation metrics

Measured by [`scripts/pdsep_separation.py`](../04_digital_design/source/scripts/pdsep_separation.py) on the final routed DEFs: separated = this layout, baseline = `build/pd/results/sky130hd/orbit_demo/base/6_final.def` (the unconstrained 7.0 ns reference run, not in the package). Cell boxes = DEF origin + LEF SIZE from `build/pd_sep/platform/cells.lef`; centre = centre-to-centre, gap = edge-to-edge. Geometry only: no radiation transport, charge-collection or upset-rate model. Published results: [separation.md](../07_verification/published_reports/separation.md), [separation.json](../07_verification/published_reports/separation.json), [summary.md](../07_verification/published_reports/summary.md) lines 5-10. Re-run 2026-10-06 (Python 3.11.15, command from [`mk/pdsep.mk`](../04_digital_design/source/mk/pdsep.mk) lines 90-94): separation.md, separation.json and regions.json byte-identical to the published files, "acceptance check (separated): PASS".

| Quantity | Baseline | Separated | Acceptance target | Status |
|---|---|---|---|---|
| acc/res same-bit centre distance, min | 2.76 um | 251.17 um (lane1.res bit 25, lane3.res bit 10) | >= 20 um (TARGET) | REPRODUCED 2026-10-06 |
| acc/res same-bit centre distance, median of group medians | 30.70 um | 292.57 um | - | REPRODUCED 2026-10-06 |
| min edge gap, any copy-A FF vs any copy-B FF | 0.00 um | 242.94 um | >= 10 um (TARGET) | REPRODUCED 2026-10-06 |
| copy fence edge gap (pdsep_copyA / pdsep_copyB) | no fences | 241.50 um | - | REPRODUCED 2026-10-06 |
| thermal same-bit centre distance, min / median | 5.52 / 8.44 um | 97.92 / 106.26 um | >= 20 um (TARGET) | REPRODUCED 2026-10-06 |
| thermal min edge gap between any two copies (FFs) | 0.00 um | 92.54 um | >= 10 um (TARGET) | REPRODUCED 2026-10-06 |
| thermal fence gap, min | no fences | 89.76 um (th0/th1) | >= 10 um (TARGET) | REPRODUCED 2026-10-06 |
| same-bit pairs in touching or overlapping cells | 13 of 262 | 0 of 262 | 0 (TARGET) | REPRODUCED 2026-10-06 |
| group members outside their region | n/a | 0 | 0 (TARGET) | REPRODUCED 2026-10-06 |
| non-member cells fully inside a fence / straddling a fence edge (excl. fill, tap) | n/a | 2 (`diode_2`, antenna repair after placement) / 107 | none set | REPRODUCED 2026-10-06 |

Notes:

- The acceptance targets (0 touching, >= 20 um centre, >= 10 um gap, every member inside) are hard-coded in [`scripts/pdsep_separation.py`](../04_digital_design/source/scripts/pdsep_separation.py) lines 24-33 and 46-48 with no stated rationale; the brief gives no distance. They are TARGETs; a physical basis (sky130 multi-node-upset / charge-sharing data) is MISSING.
- The "242 um" copy distance quoted in [summary.md](../07_verification/published_reports/summary.md) lines 151 and 153 (and "about 240 um" in regions.tcl) is the rounded FF-to-FF gap 242.94 um, not the fence gap 241.50 um; see discrepancy register (09_review_notes).
- The second, older measurement script [`pd/copy_separation.py`](../04_digital_design/source/pd/copy_separation.py) agrees ([copy_separation_pd_script.txt](../07_verification/published_reports/copy_separation_pd_script.txt): res min 251.17 um, acc min 252.55 um, thermal min 97.92 um), but its line 2 "Placement was NOT constrained" is fixed text written for the baseline; see discrepancy register (09_review_notes).
- Common-mode logic is not separated: one clock tree (TritonCTS, net `clk`, 521 sinks, one tree, [4_1_cts.log](../07_verification/orfs_logs/4_1_cts.log) lines 17-18, 43-54), the `rst_n` tree, the shared 8x8 multiplier of each lane, the A/B comparators and mismatch OR tree, the thermal voter and next-state logic, the port buffers and the single flip-flops `u_thermal.phase`, `out_valid_q`, `fault_q` (list in regions.json `unconstrained_common_mode`; summary.md lines 192-200). The clock root buffer `clkbuf_0_clk` overlaps fence pdsep_th1 by 95 % of its area (summary.md line 123). Clock/reset protection requested on brief p.3: not implemented (VERIFIED absence: one CTS tree).
- Cost of separation relative to the baseline (period 7.0 -> 7.2 ns, wirelength, power): numbers in 07_verification ([summary.md](../07_verification/published_reports/summary.md) lines 129-170).

## 5. Routing (summary)

Detailed evidence (STA, DRC/LVS scope, LEC, GLS) is in 07_verification; the routing-stage figures that describe the layout are:

| Item | Value | Source | Conditions | Status |
|---|---|---|---|---|
| Global-route congestion | total usage 39.36 %, overflow 0 on every layer; met1 62.90 %, met2 40.23 %, met3 22.09 %, met4 12.33 %, met5 0.00 %; GRT wirelength 326452 um, 6833 routed nets | [5_1_grt.log](../07_verification/orfs_logs/5_1_grt.log) lines 138-152 | FastRoute in OpenROAD (`unknown`) | VERIFIED |
| Detailed route | TritonRoute "Number of violations = 0"; wirelength 244368 um (met1 118302, met2 73048, met3 43697, met4 9180, met5 138 um); 45501 vias; [5_route_drc.rpt](../07_verification/orfs_reports/5_route_drc.rpt) is empty | [5_2_route.log](../07_verification/orfs_logs/5_2_route.log) lines 1007, 1031-1038 | `DRT-0349`: LEF58_ENCLOSURE rules skipped for mcon, via, via2, via3, via4 (lines 12-21); see discrepancy register (09_review_notes) | VERIFIED |
| Antenna | 0 net / 0 pin violations after repair; 20 diodes | 5_2_route.log lines 1056-1059; 6_report.log line 54 | OpenROAD ANT checker only | VERIFIED |
| Clock tree | H-tree on `clk`, root/sink buffer `clkbuf_16`, 56 clock buffers created, 51 leaf buffers, 40 dummy loads, path depth 2-3, average sink wire length 596.74 um | [4_1_cts.log](../07_verification/orfs_logs/4_1_cts.log) lines 10-54 | `clock_tree_synthesis -sink_clustering_enable -repair_clock_nets` | VERIFIED |

## 6. Figures

### 6.1 KLayout views (klayout_views/)

Rendered from the final GDS by [render_gds.py](klayout_views/render_gds.py) (sha256 `d3603e13…`), KLayout 0.30.12 Python module (`klayout.db`, `klayout.lay`), layer colours from the ORFS `sky130hd.lyp` (`build/pd_sep/platform/sky130hd.lyp`, copied from the ORFS platform; not in the package), white background, text off. Command, from the repository root:

```
<python with klayout==0.30.12> -I review/orbit_demo_design_review/06_physical_design/klayout_views/render_gds.py \
    build/pd_sep/results/sky130hd/orbit_demo/sep/6_final.gds \
    build/pd_sep/platform/sky130hd.lyp \
    reports/pdsep/regions.json \
    viz/layout.json \
    review/orbit_demo_design_review/06_physical_design/klayout_views
```

The command that wrote the package images was not logged (MISSING); the command above, run on 2026-10-06 into a scratch directory, reproduced all 10 PNGs byte-for-byte, and so did a second run with the package inputs (gunzipped [6_final.gds.gz](layout_db/6_final.gds.gz) and [regions.json](../07_verification/published_reports/regions.json), which is byte-identical to `reports/pdsep/regions.json`) (**REPRODUCED 2026-10-06**). The black outlines in v03, v04 and v05 are a review overlay (layer 1000/0 added in memory, not written to any GDS) drawn from the fence boxes in regions.json; they are not layout geometry.

Layer sets used by the script (GDS layer/datatype, names from sky130hd.lyp):

| Set | Layers |
|---|---|
| all | every layer listed in sky130hd.lyp, default visibility |
| PDN | met4 71/20, via4 71/44, met5 72/20 |
| LOW | li1 67/20, mcon 67/44, met1 68/20, via 68/44, met2 69/20 |
| FEOL | nwell 64/20, diff 65/20, tap 65/44, poly 66/20, licon1 66/44, li1 67/20, mcon 67/44, met1 68/20, nsdm 93/44, psdm 94/20, npc 95/20 |

![v01](klayout_views/v01_full_die_all_layers.png){: style="width:72%"}

*v01_full_die_all_layers.png (2400 x 2400 px; window (-4, -4)-(350.295, 350.295) um): full die, all layers; source 6_final.gds via render_gds.py.*

![v02](klayout_views/v02_full_die_pdn_met4_met5.png){: style="width:72%"}

*v02_full_die_pdn_met4_met5.png (2400 x 2400 px; full die): PDN set (met4, via4, met5): the 25 met4 and 25 met5 straps of section 3.1 plus the signal wires routed on met4 (9180 um) and met5 (138 um); source 6_final.gds.*

![v03](klayout_views/v03_full_die_li1_met1_met2_with_fence_overlay.png){: style="width:72%"}

*v03_full_die_li1_met1_met2_with_fence_overlay.png (2400 x 2400 px; full die): LOW set (li1, mcon, met1, via, met2) with the five fence boxes as a black overlay from regions.json; source 6_final.gds + regions.json.*

![v04 th0](klayout_views/v04_detail_thermal_fence_th0.png){: style="width:80%"}

*v04_detail_thermal_fence_th0.png (2000 x 1618 px; window (155.92, 266.00)-(190.92, 294.32) um = pdsep_th0 box + 6 um): FEOL + LOW sets, black overlay = pdsep_th0 box from regions.json; shows the 8 member cells of `u_thermal.u_copy0` and the non-member cells around and overlapping the fence.*

![v04 th1](klayout_views/v04_detail_thermal_fence_th1.png){: style="width:80%"}

*v04_detail_thermal_fence_th1.png (2000 x 1618 px; window (155.92, 159.92)-(190.92, 188.24) um): FEOL + LOW sets, overlay = pdsep_th1 box (`u_thermal.u_copy1`); `clkbuf_0_clk` overlaps this fence (summary.md line 123).*

![v04 th2](klayout_views/v04_detail_thermal_fence_th2.png){: style="width:80%"}

*v04_detail_thermal_fence_th2.png (2000 x 1618 px; window (155.92, 51.12)-(190.92, 79.44) um): FEOL + LOW sets, overlay = pdsep_th2 box (`u_thermal.u_copy2`).*

![v05](klayout_views/v05_detail_copyA_fence_lower_left.png){: style="width:80%"}

*v05_detail_copyA_fence_lower_left.png (2400 x 1714 px; window (0, 0)-(70, 50) um): FEOL + LOW sets, overlay = pdsep_copyA box; lower-left corner of the copy-A fence with its right edge at x = 52.44 um and unconstrained logic to the right; source 6_final.gds + regions.json.*

![v06](klayout_views/v06_detail_lane0_multiplier_region.png){: style="width:80%"}

*v06_detail_lane0_multiplier_region.png (2400 x 1481 px; window (123.33, 8.24)-(206.81, 59.76) um): LOW set, no overlay. The window is the `core_um` box of part `L0.mult` in `viz/layout.json` plus 4 um; see 6.3 for what that box is.*

![v07](klayout_views/v07_detail_std_cell_rows_feol.png){: style="width:80%"}

*v07_detail_std_cell_rows_feol.png (2400 x 1440 px; window (150, 150)-(170, 162) um, about 4.4 rows): FEOL set; standard-cell rows with nwell, diffusion, poly, licon, li1, mcon and the met1 followpin rails.*

![v08](klayout_views/v08_detail_die_corner_lower_right_all_layers.png){: style="width:80%"}

*v08_detail_die_corner_lower_right_all_layers.png (2400 x 1828 px; window (306.295, -2)-(348.295, 30) um): all layers; lower-right die corner inside the copy-B fence area, with the core edge, the die boundary, met4 straps and the first met5 straps; no IO pins lie in this window (pinout.csv).*

Also in the package: [orbit_demo_sky130hd_sep.png](../07_verification/published_reports/orbit_demo_sky130hd_sep.png), a KLayout render with coloured fence outlines from regions.json written by [`scripts/pdsep_render.py`](../04_digital_design/source/scripts/pdsep_render.py) (published report, 07_verification). Its label "fence gap 242 um" is the 241.50 um fence gap formatted to whole micrometres (`{gap:.0f}`, script line 151).

### 6.2 OpenROAD GUI images (orfs_images/)

Written by the ORFS final report step (`save_images.tcl`) at 22:09:44-45 on 2026-09-29 ([6_report.log](../07_verification/orfs_logs/6_report.log) lines 68-77; the `.webp.png` names come from warning GUI-0010) and byte-identical to `build/pd_sep/reports/sky130hd/orbit_demo/sep/*.webp.png` (cmp, **REPRODUCED 2026-10-06**). OpenROAD version `unknown`, final database `6_final.odb`, TT liberty. 1099 x 1099 px except cts_default_clk (1022 x 1022). The view descriptions follow `flow/scripts/save_images.tcl` in the image on this host (ASSUMPTION: same script as the run). Status of each image as tool output: **VERIFIED**.

![final_all](orfs_images/final_all.webp.png){: style="width:62%"}

*final_all.webp.png: routing view with all layers, nets including power/ground, instances and pins.*

![final_routing](orfs_images/final_routing.webp.png){: style="width:62%"}

*final_routing.webp.png: same view with the power and ground nets hidden (signal routing).*

![final_placement](orfs_images/final_placement.webp.png){: style="width:62%"}

*final_placement.webp.png: placement without routing shapes and without fill cells; the IO pins are drawn at the die edge.*

![final_clocks](orfs_images/final_clocks.webp.png){: style="width:62%"}

*final_clocks.webp.png: clock nets, clock-tree cells and sequential cells only; most of the 521 sinks sit in the two copy fences at the left and right core edges, one tree reaches both (4_1_cts.log).*

![cts_default_clk](orfs_images/cts_default_clk.webp.png){: style="width:62%"}

*cts_default_clk.webp.png: Clock Tree Viewer for clock `clk`, scene `default`: insertion delay axis in ns, root buffer, four level-1 buffers, leaf buffers and sink arrivals (axis to 0.70 ns); final STA skew 0.0538 ns ([results.md](../07_verification/published_reports/results.md) line 37).*

![cts_default_clk_layout](orfs_images/cts_default_clk_layout.webp.png){: style="width:62%"}

*cts_default_clk_layout.webp.png: the same tree in the layout, coloured by branch.*

![final_congestion](orfs_images/final_congestion.webp.png){: style="width:62%"}

*final_congestion.webp.png: routing-congestion heat map (no colour legend in the image); the GRT report gives 0 overflow on all layers (5_1_grt.log lines 138-148).*

![final_ir_drop](orfs_images/final_ir_drop.webp.png){: style="width:62%"}

*final_ir_drop.webp.png: static IR-drop heat map on layer met1 (platform `IR_DROP_LAYER ?= met1`); legend 0.000-627.544 uV. The net is not named in the image; the maximum equals the VSS worst-case 6.28e-04 V of 6_report.log line 48. Default-activity power, see 3.1.*

![final_resizer](orfs_images/final_resizer.webp.png){: style="width:62%"}

*final_resizer.webp.png: instances created by the resizer highlighted by name: `input*`/`output*` port buffers yellow, `repeater*`/`fanout*`/`wire*`/`max_*` magenta, `rebuffer*` red, `split*` dark green, `hold*` green (no hold cells exist in this run). The 867 `place*` repair buffers (count from the DEF) are not highlighted by that script.*

![final_worst_path](orfs_images/final_worst_path.webp.png){: style="width:62%"}

*final_worst_path.webp.png: worst setup path (`gui::show_worst_path`): data path (red) from `in_a[27]` on the E edge to `g_lane[3].u_lane.u_res_a/q[29]` in the copy-A fence; launch/capture clock paths in green; slack 0.03 ns at 7.2 ns, TT ([worst_setup_path.txt](../07_verification/published_reports/worst_setup_path.txt)).*

### 6.3 Detailed views of blocks: what exists

| View | Exists | Block box source | Status |
|---|---|---|---|
| Lane-0 multiplier region | v06 | `viz/layout.json` part `L0.mult` ("Lane 0 / Multiplier", 197 cells, attributed by netlist cone: cells whose combinational fan-out reaches both copies of lane 0 and whose fan-in is only lane-0 operand inputs). `core_um` = 10th-90th percentile box of the cell centres, (127.33, 12.24)-(202.81, 55.76) um; the full extent `bbox_um` is (109.48, 5.44)-(214.36, 68.00) um, so the view shows the dense core of the multiplier, not all of its cells, and also contains cells of other parts (e.g. the lane-0 comparator `L0.cmp`, core box (139.56, 17.68)-(206.54, 93.02) um). `viz/layout.json` was derived from 6_final.def (inputs `def_sha256` f5c544f3…, `gds_sha256` cd19afa9…, both equal to the package files) by `scripts/viz_parts.py` (lines 711-751 for the boxes), generated 2026-09-29 23:02:30 UTC | REPRODUCED 2026-10-06 (hashes; the v06 window equals `core_um` ± 4 um); part attribution itself is CLAIM (unverified) |
| Thermal fences th0, th1, th2 | v04 (three files) | regions.json fence boxes | REPRODUCED 2026-10-06 |
| Copy-A fence corner | v05 | regions.json `pdsep_copyA` box | REPRODUCED 2026-10-06 |
| Standard-cell rows (FEOL) | v07 | fixed window, no block | REPRODUCED 2026-10-06 |
| Die corner | v08 | fixed window at the die bbox | REPRODUCED 2026-10-06 |
| Other blocks (lanes 1-3, adders `L*.addA/addB`, comparators `L*.cmp`, mismatch OR tree `fault`, thermal voter `th.vote`, clock root) | no view | boxes exist in `viz/layout.json` parts list (59 parts) | MISSING (render with render_gds.py using those `core_um` boxes if needed) |

## 7. Open items for this section

| Item | Status | Needed |
|---|---|---|
| ORFS commit, OpenROAD build version, open_pdks / skywater-pdk version, image digest in the run log | MISSING | record per run; pin the image by digest in `mk/pdsep.mk` |
| Platform scripts used by the run (pdn.tcl, tapcell.tcl, save_images.tcl) | ASSUMPTION (read from the current image) | copy them into the build directory at run time |
| Pinout specification | MISSING (pins are placer output) | specified pinout, then `set_io_pin_constraint` / pin file |
| Pad ring, IO cells, ESD, package | N/A for this core block (none designed) | padframe and package if the block is to be fabricated |
| Decap insertion and decoupling budget | MISSING (0 decap cells) | decision on decap fill, dynamic IR analysis |
| Metal fill and density check | MISSING (6_1_fill copies the ODB; KLayout deck has no density rules) | fill generation and density check on the filled GDS |
| Dynamic IR drop; EM check | MISSING (PSM EM currents at default activity computed 2026-10-06, not compared with the tlef current-density limits) | switching activity from simulation; comparison of the PSM currents with the `DCCURRENTDENSITY` limits |
| Physical basis of the 20 um / 10 um separation targets | MISSING | sky130 multi-node-upset / charge-sharing data |
| Detailed views of blocks other than lane-0 multiplier and the fences | MISSING | additional render windows |
| Command log of the original package renders | MISSING (reproduced byte-for-byte on 2026-10-06) | - |
