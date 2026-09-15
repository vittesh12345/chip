# orbit_demo verification summary

Package section 07_verification of `orbit_demo_design_review`, written 2026-10-06. Links are relative to this file. Paths in backticks without a link (`reports/...`, `build/...`, `pd/...`, ORFS image paths) are repository, build or tool-image paths. Byte-identical copies of the repository directories `pd/`, `mk/`, `fault/`, `formal/`, `synth/`, `rtl/` and of part of `scripts/` and `docs/` are in [04_digital_design/source/](../04_digital_design/source/) (cmp 2026-10-06); copies of `reports/{formal,fault,synth,ecc,mutation}` and of most of `reports/pdsep/` are in this folder (section 2). `build/...` and ORFS image paths are not in the package unless section 2 lists a copy. Every result row carries one status label: VERIFIED (a tool log or report shows it), REPRODUCED 2026-10-06 (re-run for this package), TARGET (design goal, not measured), ASSUMPTION, CLAIM (unverified) (stated in a document, no log found), MISSING, N/A. Discrepancies are collected in the discrepancy register ([09_review_notes](../09_review_notes/)); this document only flags them.

Scope: the reviewed layout is the copy-separated sky130hd run (variant `sep`, 7.2 ns). The baseline sky130hd run (variant `base`, 7.0 ns) is used only for comparison and is labelled as such. The ECC block is standalone and not in the layout (section 15).

## 1 Design revision covered by this package

Package revision table, verbatim from the package revision record:

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

Checked for this section on 2026-10-06: `MANIFEST.sha256` is not present in the package. The fault summary [fault/summary.md](fault/summary.md) lines 15-20 records the full sha256 of the four RTL files, and they match the table prefixes. The SPEF copy [6_final.spef.gz](../06_physical_design/layout_db/6_final.spef.gz) decompresses to sha256 014e655ae938245a…, the value in the table. `git diff --name-only 0495cfa..HEAD` outside `review/` is empty (checked 2026-10-06 at HEAD 23c72ac); no design, report or flow file changed after the package commit.

## 2 Evidence in this folder

Unless a source cell names another path, the original of a package file is the folder origin below plus the same file name.

| Package folder | Contents | Origin (repository or build path) | How it got here |
|---|---|---|---|
| [orfs_logs/](orfs_logs/) | ORFS step logs and metrics JSON of the sep run | `build/pd_sep/logs/sky130hd/orbit_demo/sep/` | copied before this section; 39 of 40 files, byte-identical (cmp 2026-10-06) |
| [orfs_reports/](orfs_reports/) | 6_finish.rpt, 6_drc.lyrdb, 6_drc_count.rpt, synth_stat/check, stage timing reports | `build/pd_sep/reports/sky130hd/orbit_demo/sep/` | copied before this section; with 06_physical_design/orfs_images/ 23 of 25 files, byte-identical |
| [published_reports/](published_reports/) | results.md, checks.json, storage_audit.txt, power, paths, separation | `reports/pdsep/` | copied before this section; 18 of 19 files, byte-identical |
| [gls/](gls/) | post-route GLS log and injection list | `build/pd_sep/gls/sep/` | copied before this section; byte-identical |
| [formal_rerun_2026-10-06/](formal_rerun_2026-10-06/) | `make formal` (12 tasks) and `make formal-vacuity` re-run | review scratch build | re-run 2026-10-06 |
| [sta_corners_sep_2026-10-06/](sta_corners_sep_2026-10-06/) | multi-corner STA of the sep layout, scripts and logs | review scratch | new run 2026-10-06 |
| [formal/](formal/) | summary.md, vacuity.md, logs/ (13 tasks, 19 vacuity mutants) | `reports/formal/` | copied by this section (cp, not moved) |
| [fault/](fault/) | summary.md, campaign.md, campaign_per_bit.tsv, injection/, logs/ | `reports/fault/` | copied by this section |
| [synth/](synth/) | generic synthesis, audits, negative control, equivalence, GLS | `reports/synth/` | copied by this section |
| [ecc/](ecc/) | results.txt, synth_stat.txt, logs/ | `reports/ecc/` | copied by this section |
| [mutation/](mutation/) | summary.md, results.json, tb_mutation_gaps.v | `reports/mutation/` | copied by this section |
| [baseline_reference/](baseline_reference/) | sta_corners_baseline_7p0ns.txt; negctl_cfgkeep_audit.txt, negctl_nokeep_audit.txt (baseline ORFS keep controls); results_baseline_7p0ns.md | `reports/pd/sky130hd/`: sta_corners.txt, negctl_*_audit.txt, results.md | copied by this section; sta_corners.txt and results.md renamed |
| [lec_inputs/](lec_inputs/) | 4_rsz_lec_test.yml, 6_final_lec_test.yml (kepler-formal test configurations; they name the compared netlists, which are not copied) | `build/pd_sep/objects/sky130hd/orbit_demo/sep/` | copied by this section |
| [lvs/](lvs/) | orbit_demo_extracted.cir.gz (layout-extracted netlist from KLayout LVS) | `build/pd_sep/results/` `sky130hd/orbit_demo/sep/` | gzip copy of orbit_demo_extracted.cir by this section (decompresses byte-identical) |
| [rerun_2026-10-06/](rerun_2026-10-06/) | re-run logs: `make fault`, `make formal-extra`, a second `make formal-vacuity`, `make synth`, `make ecc`, ECC sec_bmc sanity, sep storage audit with the current script, final STA/power/IR/EM re-query, GLS re-run, GLS netlist-mutant control | review scratch `review_work/` (formal_fault, synth, ecc, pd_sep, pd_ref) | copied by this section; logs contain scratch paths |

Not copied (size): `build/pd_sep/results/sky130hd/orbit_demo/sep/6_lvs.lvsdb` (17.7 MB), `build/pd_sep/make_pd_sep.out` (console log, 7931 lines), formal and fault counterexample/cover VCDs under `build/formal/` and `build/fault/`, per-trial campaign log `build/fault/campaign/trials.tsv`. Also not copied: `5_1_grt.json` (global-route metrics, 586912 B) from the ORFS log folder; `drt_antennas.log` and `grt_antennas.log` (both 0 bytes) from the ORFS report folder; `reports/pdsep/orbit_demo_sky130hd_sep.gds.gz` (decompresses to the same sha256 cd19afa9… as [6_final.gds.gz](../06_physical_design/layout_db/6_final.gds.gz)); the LEC netlists `1_synth_lec.v`, `6_final_lec.v`, `4_before_rsz_lec.v`, `4_after_rsz_lec.v` in `build/pd_sep/results/sky130hd/orbit_demo/sep/`, so the LEC cannot be re-run from the package alone (register D-99).

## 3 Tools, conditions, targets and assumptions

### 3.1 Tools

| Tool | Version as recorded | Used for | Source | Status |
|---|---|---|---|---|
| OpenROAD (OpenSTA, TritonRoute, TritonCTS, OpenRCX, PSM, ANT) | prints "unknown"; build features -GPU +GUI -Python | P&R, STA, extraction, IR, antenna | [6_report.log](orfs_logs/6_report.log) line 1; SPEF header `*VERSION "unknown"` | VERIFIED |
| ORFS docker image | tag `openroad/orfs:latest`; local image digest sha256:2e5bf6fe865e…, created 2026-09-29 02:00 UTC | whole flow | no log records the digest; only one ORFS image on the host | ASSUMPTION (that this image ran the 2026-09-29 flow) |
| ORFS commit, PDK (open_pdks / skywater-pdk) commit | not recorded | — | — | MISSING |
| Yosys (ORFS synthesis) | 0.68+post (git sha1 UNKNOWN) | sky130hd mapping | [1_2_yosys.log](orfs_logs/1_2_yosys.log) line 1 | VERIFIED |
| KLayout | 0.30.12 | DRC, LVS, GDS merge | [6_drc.log](orfs_logs/6_drc.log) line 1; [6_lvs.log](orfs_logs/6_lvs.log) line 1 | VERIFIED |
| kepler-formal | version not printed; tool name only in ORFS `flow/scripts/formal_check.tcl` and [pd/collect_pd.py](../04_digital_design/source/pd/collect_pd.py) line 150 | LEC | [6_final_lec_check.log](orfs_logs/6_final_lec_check.log) | MISSING (version) |
| Yosys / SBY / Yices / bitwuzla (formal, fault, generic synthesis, ECC) | Yosys 0.69+154 (git sha1 30d62572e-dirty); SBY v0.69; Yices 2.7.0; bitwuzla 0.9.1; abc pdr and aiger suprove from the same OSS CAD Suite, versions not stated | formal, fault formal, synth, ECC | [formal/summary.md](formal/summary.md) line 4; [fault/summary.md](fault/summary.md) line 11 | VERIFIED |
| Icarus Verilog | 14.0 (devel) (s20260301-500-g2e81fcccb-dirty) | SEU campaign, GLS, ECC sim | [fault/summary.md](fault/summary.md) line 11 | VERIFIED |
| Verilator | 5.053 devel rev v5.052-233-gf5f9ddef9 | ECC lint | [lint_verilator.log](rerun_2026-10-06/ecc/lint_verilator.log) line 1 | VERIFIED |

### 3.2 Common timing / physical conditions

Unless stated: sep layout `6_final.odb` / [6_final.sdc](../06_physical_design/layout_db/6_final.sdc) / [6_final.spef.gz](../06_physical_design/layout_db/6_final.spef.gz); `create_clock clk -period 7.2000` (6_final.sdc line 8), `set_propagated_clock` (line 9); `set_input_delay 1.4400` on 79 inputs and `set_output_delay 1.4400` on 135 outputs (0.2 x period); no `set_clock_uncertainty`, `set_timing_derate`, `set_load`, `set_driving_cell` or `set_input_transition` in 6_final.sdc (grep 2026-10-06). Liberty `sky130_fd_sc_hd__tt_025C_1v80.lib` (TT, 25 C, 1.80 V), the only liberty ORFS read ([6_report.log](orfs_logs/6_report.log) line 6).

### 3.3 Targets and assumptions referenced in this section (not results)

| Item | Value | Source | Status |
|---|---|---|---|
| Demonstrator clock requirement | none in SPEC.md; 7.2 ns is the shortest period tried that closed at TT ([period_exploration.md](published_reports/period_exploration.md)) | [SPEC.md](../04_digital_design/source/docs/SPEC.md) | MISSING (requirement) |
| Concept chip: 16 tiles, 200-800 MHz, 6.55-26.21 TOPS | concept targets for a different, unbuilt chip (p.1 "unvalidated targets"; p.5 also calls the tile count and clock range project assumptions); they do not apply to orbit_demo and nothing in this section verifies them | [brief](../04_digital_design/source/docs/orbit-ai-design-brief.pdf) p.1-2, p.5 | TARGET |
| Concept chip: 40 W per chip | conceptual sizing allocation, not a power estimate (p.1 "sizing assumption - not an estimate"; p.2 "for conceptual sizing only"); does not apply to orbit_demo | [brief](../04_digital_design/source/docs/orbit-ai-design-brief.pdf) p.1-2, p.5 | ASSUMPTION |
| SPEC section 5 integrity target | an upset in one copy of accumulator/result storage never transfers a wrong `out_data`; it causes a stop | SPEC.md lines 93-94 | TARGET (checked in section 12) |
| I/O delay 20 % of period | placeholder for the unknown outside world | [constraint.sdc](../04_digital_design/source/pd/sky130hd_sep/constraint.sdc) lines 19-27 | ASSUMPTION |
| Fault model | single upset per trace/trial; synchronous model, timing closure assumed, metastability out of scope | [fault/summary.md](fault/summary.md) lines 33-41 | ASSUMPTION |
| Copy-separation acceptance limits | same-bit centre >= 20 um, edge gap >= 10 um; no rationale given | [scripts/pdsep_separation.py](../04_digital_design/source/scripts/pdsep_separation.py) lines 46-48 | TARGET |

## 4 Physical verification

### 4.1 DRC

| Check | Result | Tool + version | Conditions | Status | Source |
|---|---|---|---|---|---|
| Detailed-route DRC | 0 violations after the last iteration (35 at the preceding report step); `5_route_drc.rpt` is empty (0 bytes) | TritonRoute in OpenROAD "unknown" | `detailed_route -droute_end_iter 64`; router rules from the sky130hd tech LEF. DRT-0349: LEF58_ENCLOSURE without CUTCLASS not supported, enclosure rules skipped for mcon, via, via2, via3, via4 | VERIFIED | [5_2_route.log](orfs_logs/5_2_route.log) lines 10-21, 973, 1007; [5_route_drc.rpt](orfs_reports/5_route_drc.rpt) |
| KLayout DRC, ORFS deck | 0 markers: `6_drc_count.rpt` = `0`; `6_drc.lyrdb` has 145 rule categories and 0 items | KLayout 0.30.12, ORFS deck `sky130hd.lydrc` ("v1.0 : initial release", 2020-10-04) | Deck scope: `FEOL = false`, `BEOL = true`, `OFFGRID = true` (deck lines 46-48, read from the ORFS image). Log runs only "DRC section", "BEOL section", "OFFGRID-ANGLES section". Categories: li, ct, m1-m5, via-via4, nsm, pad.2, plus `*_OFFGRID` / `*_angle`. No FEOL rules (well, diff/tap, poly, licon, implants), no metal-density rules, no antenna or latch-up rules. Run on 6_final.gds without metal fill. This is NOT a sign-off DRC | VERIFIED | [6_drc_count.rpt](orfs_reports/6_drc_count.rpt); [6_drc.lyrdb](orfs_reports/6_drc.lyrdb); [6_drc.log](orfs_logs/6_drc.log) lines 1, 257-258, 1222; command in `build/pd_sep/make_pd_sep.out` lines 5517-5519 |
| Metal fill | not inserted: step 6_1_fill only copies `5_route.odb` to `6_1_fill.odb` | OpenROAD "unknown" | ORFS sky130hd platform default | VERIFIED (that no fill was run) | [6_1_fill.log](orfs_logs/6_1_fill.log) line 10 |
| Metal density on a filled GDS | not run | — | needs fill and a density check. The tech LEF read by the flow defines MAXIMUMDENSITY 70 / DENSITYCHECKWINDOW 700 700 for met1-met4 (no minimum density); no step compared the layout with it | MISSING | `sky130_fd_sc_hd.tlef` (ORFS image copy) lines 120-121, 165-166, 206-207, 247-248; read by the flow per [1_synth.log](orfs_logs/1_synth.log) line 7 (ODB-0227) |
| FEOL DRC (full sky130 rule deck, e.g. open_pdks KLayout sign-off deck) | not run | — | — | MISSING | — |
| Magic DRC | not run; no Magic log or tech file use in the flow | — | — | MISSING | — |

The PASS row in [results.md](published_reports/results.md) line 20 ("KLayout DRC PASS, 0 markers") does not state the deck scope; see discrepancy register (09_review_notes).

### 4.2 LVS

| Check | Result | Tool + version | Conditions | Status | Source |
|---|---|---|---|---|---|
| Layout vs schematic | "INFO : Congratulations! Netlists match." | KLayout 0.30.12, ORFS deck `sky130hd.lylvs` | Layout: 6_final.gds extracted at device level (`orbit_demo_extracted.cir`). Reference: `6_final_concat.cdl` = `6_final.cdl` (written by OpenROAD from 6_final.odb) concatenated with the platform cell CDL `sky130hd.cdl`. The reference comes from the same database as the GDS, so this confirms stream-out and cell connectivity, not an independent netlist | VERIFIED | [6_lvs.log](orfs_logs/6_lvs.log) lines 1, 649, 652; [6_cdl.log](orfs_logs/6_cdl.log); reference [6_final.cdl.gz](../03_schematics/netlists/6_final.cdl.gz); extracted [orbit_demo_extracted.cir.gz](lvs/orbit_demo_extracted.cir.gz); see note below |
| Independent LVS (Magic extraction + Netgen against 6_final.v or the synthesized netlist) | not run | — | — | MISSING | — |

Note: the concatenation command is in `build/pd_sep/make_pd_sep.out` line 7244; the LVS database is `build/pd_sep/results/sky130hd/orbit_demo/sep/6_lvs.lvsdb` (17.7 MB, not copied). Deck paths are inside the ORFS image under `/OpenROAD-flow-scripts/flow/`.

### 4.3 Logic equivalence (LEC) inside the flow

| Check | Result | Tool + version | Conditions | Status | Source |
|---|---|---|---|---|---|
| `4_rsz` LEC, published as "LEC synth vs post-CTS repair" | "Circuits are IDENTICAL"; 613 / 613 PIs, 1177 POs, SAT UNSAT | kepler-formal (version MISSING), called by ORFS `cts.tcl` | Compares `4_before_rsz_lec.v` with `4_after_rsz_lec.v`: the netlists immediately before and after `repair_timing` inside the CTS step (ORFS `flow/scripts/cts.tcl` lines 61-71). It is NOT synthesis vs post-CTS. Liberty TT | VERIFIED | [4_rsz_lec_check.log](orfs_logs/4_rsz_lec_check.log) lines 4, 6, 95; [4_rsz_lec_test.yml](lec_inputs/4_rsz_lec_test.yml); [4_1_cts.log](orfs_logs/4_1_cts.log) line 469 |
| `6_final` LEC, "synth vs final" | "Circuits are IDENTICAL"; 603 / 613 PIs, 1177 common POs, SAT UNSAT | kepler-formal (version MISSING) | Compares `1_synth_lec.v` with `6_final_lec.v`. Combinational miter with the 521 `dfxtp_1` Q pins as cut points; 1177 POs = 521 CLK + 521 D + 135 output bits. The 10 extra PIs are tie-cell outputs (`conb_1` HI/LO: 1+1 in synthesis, 6+6 in the final netlist). Does not cover RTL vs synthesis | VERIFIED | [6_final_lec_check.log](orfs_logs/6_final_lec_check.log) lines 4, 6, 8-24, 44, 109; [6_final_lec_test.yml](lec_inputs/6_final_lec_test.yml) |

The label in [results.md](published_reports/results.md) line 22 and [pd/collect_pd.py](../04_digital_design/source/pd/collect_pd.py) line 151 misnames the `4_rsz` check; see discrepancy register (09_review_notes). RTL-to-gate equivalence is in section 13.

### 4.4 Antenna

| Check | Result | Tool + version | Conditions | Status | Source |
|---|---|---|---|---|---|
| Global-route antenna repair | 31 antenna violations found, 0 after repair | OpenROAD GRT / ANT, "unknown" | ORFS default antenna rules from the sky130hd tech LEF | VERIFIED | [5_1_grt.log](orfs_logs/5_1_grt.log) lines 663-668 |
| Detailed-route antenna repair | 18 diodes inserted, then 2 more | OpenROAD DRT / GRT-0015 | — | VERIFIED | [5_2_route.log](orfs_logs/5_2_route.log) lines 425, 765 |
| Final antenna check | 0 net violations, 0 pin violations; 20 antenna cells in the final cell report | OpenROAD ANT-0002 / ANT-0001 | routed database | VERIFIED | [5_2_route.log](orfs_logs/5_2_route.log) lines 1056-1059; [6_report.json](orfs_logs/6_report.json) line 14; [6_report.log](orfs_logs/6_report.log) cell report |
| Antenna check by KLayout or Magic | not run: the KLayout deck has no antenna rule categories | — | — | MISSING | [6_drc.lyrdb](orfs_reports/6_drc.lyrdb) category list |

## 5 Extracted-parasitic results

| Check | Result | Tool + version | Conditions | Status | Source |
|---|---|---|---|---|---|
| Parasitic extraction | 6886 nets, 30095 rsegs, 30095 caps, 60471 coupling caps; written to 6_final.spef (6827076 bytes, sha256 014e655a…) and read back for the final STA, power and IR reports | OpenRCX in OpenROAD "unknown" | Rules `rcx_patterns.rules` of the ORFS sky130hd platform (the only RCX rules file there); one process corner `X`, `ext_model_index 0` (a single nominal extraction corner); coupling threshold 0.1 fF; `max_merge_res 50.0`. Provenance and qualification of rcx_patterns.rules are not documented | VERIFIED | [6_report.log](orfs_logs/6_report.log) lines 16-26; [6_final.spef.gz](../06_physical_design/layout_db/6_final.spef.gz) header; ORFS `flow/scripts/final_outputs.tcl` lines 27-37 |
| STA on the SPEF | final ORFS STA, power and IR use the OpenRCX SPEF; the 2026-10-06 corner runs read the same SPEF (`read_spef`) at every liberty corner | OpenSTA in OpenROAD "unknown" | see section 6 | VERIFIED | ORFS `final_outputs.tcl` line 37; [sta_corners_extra.tcl](sta_corners_sep_2026-10-06/sta_corners_extra.tcl); [pd/sta_corners.tcl](../04_digital_design/source/pd/sta_corners.tcl) lines 14-18 |
| RC corners (min/max extraction rules) | not available; nominal SPEF used at every PVT corner | — | — | MISSING | [pd/sta_corners.tcl](../04_digital_design/source/pd/sta_corners.tcl) lines 9-10 |
| Post-layout SPICE / transistor-level simulation | not run (the LVS-extracted device netlist exists but carries no parasitics and was never simulated) | — | — | MISSING | — |
| Post-layout timing (SDF-annotated) gate-level simulation | not run; every GLS in the package is zero-delay | — | — | MISSING | [tb_gls.v header](../04_digital_design/source/pd/gls/tb_gls.v) lines 12-13 |

## 6 Timing

### 6.1 ORFS final STA at TT (the flow's own final report; single corner)

| Check | Result | Tool + version | Conditions | Status | Source |
|---|---|---|---|---|---|
| Setup | WNS +0.0310081 ns, TNS 0, 0 setup violations | OpenSTA in OpenROAD "unknown" | section 3.2; TT 25 C 1.80 V; OpenRCX SPEF | VERIFIED | [6_report.json](orfs_logs/6_report.json) lines 30, 32; [6_finish.rpt](orfs_reports/6_finish.rpt) lines 5, 15, 416 |
| Worst setup path | `in_a[27]` (input, 1.44 ns external delay) -> `g_lane[3].u_lane.u_res_a/q[29]$_SDFFE_PN0P_`, slack 0.03 ns (MET); an I/O path that crosses the die from the east-edge pin to the copy-A fence | same | same | VERIFIED | [worst_setup_path.txt](published_reports/worst_setup_path.txt) lines 1-2, 125; [6_final.def.gz](../06_physical_design/layout_db/6_final.def.gz): pin `in_a[27]` PLACED (345895 109140) dbu, flip-flop PLACED (43700 108800) dbu (0.001 um/dbu) |
| Hold | WNS +0.435959 ns, TNS 0, 0 hold violations; worst path `u_thermal.phase$_SDFF_PN0_` -> itself, slack 0.44 | same | same | VERIFIED | [6_report.json](orfs_logs/6_report.json) lines 31, 33; [worst_hold_path.txt](published_reports/worst_hold_path.txt) line 53; 6_finish.rpt line 421 |
| Clock skew | setup skew 0.0538434 ns (latency 0.65 at `u_thermal.u_copy0/q[0]$_SDFFE_PN0P_/CLK`, -0.59 at `g_lane[3].u_lane.u_res_b/q[20]$_SDFFE_PN0P_/CLK`); one TritonCTS H-tree for all 521 sinks, 56 clock buffers | OpenSTA / TritonCTS | propagated clock | VERIFIED | [6_report.json](orfs_logs/6_report.json) line 36; [6_finish.rpt](orfs_reports/6_finish.rpt) lines 23-30; [4_1_cts.log](orfs_logs/4_1_cts.log) lines 17-43 |
| Min period / fmax incl. I/O paths | 7.17 ns / 139.49 MHz (`report_clock_min_period -include_port_paths`, with the assumed 1.44 ns I/O delays held fixed) | OpenSTA | same | VERIFIED | [6_finish.rpt](orfs_reports/6_finish.rpt) line 20; ORFS `report_metrics.tcl` line 39 |
| Min period reg-to-reg (no port paths) | 5.85 ns / 170.82 MHz; same-database re-query also returns setup WNS 0.031008 ns, hold WNS 0.435959 ns, 7.17 ns with port paths | OpenSTA in OpenROAD "unknown", image sha256:2e5bf6fe865e | [sta.tcl](rerun_2026-10-06/pd_sep/sta.tcl): read 6_final.odb/sdc, setRC.tcl, 6_final.spef | REPRODUCED 2026-10-06 | [sta.log](rerun_2026-10-06/pd_sep/sta.log) lines 5, 10-11 |
| Intermediate (estimate-based) timing | did not close before the final RCX-based STA: `RSZ-0062 Unable to repair all setup violations` at floorplan, CTS and global route | OpenROAD resizer | placement/route estimates | VERIFIED | [2_1_floorplan.log](orfs_logs/2_1_floorplan.log) line 362; [4_1_cts.log](orfs_logs/4_1_cts.log) line 463; [5_1_grt.log](orfs_logs/5_1_grt.log) line 620 |

![ORFS final_worst_path view of the sep layout](../06_physical_design/orfs_images/final_worst_path.webp.png){: style="width:55%"}

*Figure 1: ORFS GUI export `final_worst_path` of the sep layout (TT, 7.2 ns): the worst setup path runs from the east-edge port `in_a[27]` to the copy-A fence at the west edge. Source [final_worst_path.webp.png](../06_physical_design/orfs_images/final_worst_path.webp.png) (= `build/pd_sep/reports/sky130hd/orbit_demo/sep/final_worst_path.webp.png`).*

### 6.2 Multi-corner re-time of the sep layout (new, 2026-10-06)

Conditions for every row: [pd/sta_corners.tcl](../04_digital_design/source/pd/sta_corners.tcl) unmodified, run through [scripts/run_pd.sh](../04_digital_design/source/scripts/run_pd.sh) `--shell` with `openroad -no_init -threads 1` in image `openroad/orfs:latest` (sha256:2e5bf6fe865e), inputs `build/pd_sep/results/sky130hd/orbit_demo/sep/6_final.{odb,sdc,spef}`, 7.2000 ns, 1.44 ns I/O delay, propagated clock, nominal OpenRCX SPEF at every corner. The design was optimised by ORFS at TT only; SS and FF re-time the same routed database (information only). SS/FF liberty from the `master` branch of efabless/skywater-pdk-libs-sky130_fd_sc_hd (sha256 prefixes ss 9b24f0db3967ac67, ff fb61d91c55a7f85b; no commit pinned), reused from `build/pd/platform/sky130hd/corners/`. The script header line "Constraint: the committed SDC" is fixed text; the input is the ORFS-written 6_final.sdc (same 7.2 ns); see discrepancy register (09_review_notes).

| Corner (liberty) | Setup WNS / TNS (ns) | Hold WNS / TNS (ns) | Min period / fmax (incl. I/O) | Worst setup path | Tool + version | Status | Source |
|---|---|---|---|---|---|---|---|
| tt (`tt_025C_1v80`) | +0.031 / 0.000 | +0.436 / 0.000 | 7.17 ns / 139.49 MHz | `in_a[27]` -> `g_lane[3].u_lane.u_res_a/q[29]$_SDFFE_PN0P_` | OpenSTA, OpenROAD "unknown" | REPRODUCED 2026-10-06 (matches 6.1) | [sta_corners_sep.txt](sta_corners_sep_2026-10-06/sta_corners_sep.txt) line 13; [sta_tt.log](sta_corners_sep_2026-10-06/sta_tt.log) |
| ss_100C_1v60 (`ss_100C_1v60`) | -6.131 / -2463.532: FAILS at 7.2 ns | +0.891 / 0.000 | 13.33 ns / 75.01 MHz | `in_a[12]` -> `g_lane[1].u_lane.u_acc_a/q[31]$_SDFFE_PN0P_` | same | REPRODUCED 2026-10-06 | line 14; [sta_ss_100C_1v60.log](sta_corners_sep_2026-10-06/sta_ss_100C_1v60.log) lines 6-11 |
| ff_n40C_1v95 (`ff_n40C_1v95`) | +2.276 / 0.000 | +0.281 / 0.000 (smallest hold margin) | 4.92 ns / 203.07 MHz | `in_b[30]` -> `g_lane[3].u_lane.u_res_a/q[29]$_SDFFE_PN0P_` | same | REPRODUCED 2026-10-06 | line 15; [sta_ff_n40C_1v95.log](sta_corners_sep_2026-10-06/sta_ff_n40C_1v95.log) |

Supplementary queries ([sta_corners_extra.tcl](sta_corners_sep_2026-10-06/sta_corners_extra.tcl), same setup as [pd/sta_corners.tcl](../04_digital_design/source/pd/sta_corners.tcl); [sta_corners_sep_supplement.txt](sta_corners_sep_2026-10-06/sta_corners_sep_supplement.txt), generated by [extract_supplement.py](sta_corners_sep_2026-10-06/extract_supplement.py)):

| Check | Result | Tool + version | Conditions | Status | Source |
|---|---|---|---|---|---|
| Worst setup slack by path class, TT | reg2reg +1.346 (`g_lane[0].u_lane.u_res_b/q[30]`), in2reg +0.031, reg2out +0.654 (`in_ready`), in2out +2.577 | OpenSTA | `report_checks -from/-to` class, `-format end` | REPRODUCED 2026-10-06 | supplement, corner tt |
| Worst setup slack by path class, SS | reg2reg -4.420, in2reg -6.131, reg2out -4.142 (`in_ready`), in2out +1.195. The SS failure is not only the I/O budget: reg-to-reg fails by 4.420 ns | OpenSTA | same | REPRODUCED 2026-10-06 | supplement, corner ss_100C_1v60 |
| Worst setup slack by path class, FF | reg2reg +3.571, in2reg +2.276, reg2out +2.558, in2out +3.165 | OpenSTA | same | REPRODUCED 2026-10-06 | supplement, corner ff_n40C_1v95 |
| Setup-violating endpoints at SS | 516: all 32 bits of each of the 16 registers `g_lane[0..3].u_lane.u_{acc_a,acc_b,res_a,res_b}` (512), `out_valid_q$_SDFFE_PP0P_/D`, `fault_q$_SDFFE_PP0P_/D`, outputs `in_ready` and `out_valid`. 0 at TT and FF. Hold-violating endpoints: 0 at all three corners | OpenSTA | `report_checks -slack_max 0 -group_path_count 1000000 -endpoint_path_count 1` | REPRODUCED 2026-10-06 | [sta_extra_ss_100C_1v60.log](sta_corners_sep_2026-10-06/sta_extra_ss_100C_1v60.log) section "setup violating endpoints" |
| Max slew / cap at SS | 37 max-slew violating pins (worst `_6342_/Y` 2.004 ns vs limit 1.492 ns) and 12 max-capacitance violating pins (worst `_4662_/Y` 0.128 pF vs limit 0.115 pF). None at TT or FF | OpenSTA | `report_check_types -max_slew -max_capacitance -max_fanout -violators`; limits from each corner liberty | REPRODUCED 2026-10-06 | [sta_extra_ss_100C_1v60.log](sta_corners_sep_2026-10-06/sta_extra_ss_100C_1v60.log) section "drv" |

### 6.3 Baseline layout corners, for comparison only (not the reviewed layout)

Baseline variant `base` (no fences), `build/pd/results/sky130hd/orbit_demo/base/6_final.*`, 7.0000 ns, same script and liberty files, run 2026-09-29 20:15.

| Corner | Setup WNS / TNS (ns) | Hold WNS (ns) | Min period / fmax | sep minus base min period | Status | Source |
|---|---|---|---|---|---|---|
| tt | +0.066 / 0.000 | +0.437 | 6.93 ns / 144.21 MHz | +0.24 ns | VERIFIED | [sta_corners_baseline_7p0ns.txt](baseline_reference/sta_corners_baseline_7p0ns.txt) line 11 (= `reports/pd/sky130hd/sta_corners.txt`) |
| ss_100C_1v60 | -6.016 / -2240.224 | +0.893 | 13.02 ns / 76.83 MHz | +0.31 ns | VERIFIED | line 12 |
| ff_n40C_1v95 | +2.256 / 0.000 | +0.280 | 4.74 ns / 210.80 MHz | +0.18 ns | VERIFIED | line 13 |

The committed corner report covers only the baseline layout and its header does not name the variant; read as evidence for the sep layout it understates the SS deficit; see discrepancy register (09_review_notes).

### 6.4 Not modelled in any timing result

| Item | State | Status |
|---|---|---|
| On-chip variation, timing derates, clock uncertainty / jitter | none in 6_final.sdc or [pd/sta_corners.tcl](../04_digital_design/source/pd/sta_corners.tcl) | MISSING |
| I/O environment (load, drive, input transition, real I/O budget) | not constrained; the I/O delay is the 20 % placeholder listed in 3.3 | MISSING |
| RC corners | nominal OpenRCX SPEF at every corner | MISSING |
| Other liberty corners (e.g. ss_n40C_1v60, ff_100C_1v95, low-voltage SS) | only `tt_025C_1v80` (ORFS image) and `ss_100C_1v60`, `ff_n40C_1v95` (downloaded) exist on disk (search 2026-10-06) | MISSING |
| Multi-corner optimisation / closure at SS | ORFS optimised at TT only; SS fails at 7.2 ns | MISSING |
| Repo make target for corners of the sep layout | [mk/pd.mk](../04_digital_design/source/mk/pd.mk) `pd-corners` runs only `build/pd/.../base`; [mk/pdsep.mk](../04_digital_design/source/mk/pdsep.mk) has none; the 2026-10-06 run used the same commands by hand ([run_corners_sep.sh](sta_corners_sep_2026-10-06/run_corners_sep.sh)) | MISSING |

## 7 Max slew, max capacitance, max fanout

| Check | Result | Tool + version | Conditions | Status | Source |
|---|---|---|---|---|---|
| Max slew, TT | 0 violations; worst slack 0.326 ns against a 1.486 ns limit | OpenSTA, OpenROAD "unknown" | TT, final STA; `repair_design -cap_margin 20 -slew_margin 20` applied during the flow (SLEW_MARGIN = CAP_MARGIN = 20) | VERIFIED | [6_finish.rpt](orfs_reports/6_finish.rpt) lines 359-371, 401; [3_4_place_resized.log](orfs_logs/3_4_place_resized.log) line 12; [config.mk](../04_digital_design/source/pd/sky130hd_sep/config.mk) lines 70-71 |
| Max capacitance, TT | 0 violations; worst slack 0.00733 pF against a 0.02107 pF limit | same | same | VERIFIED | 6_finish.rpt lines 384-396, 411 |
| Max fanout, TT | "0 violations" reported, but no fanout limit is defined (`max_fanout_check_limit` 1.0000000150474662e+30; `finish__timing__drv__max_fanout_limit` 0 in the metrics), so the PASS is vacuous | same | same | VERIFIED | 6_finish.rpt lines 374-381, 406; [6_report.json](orfs_logs/6_report.json) line 42 |
| Max fanout against a defined limit | not checked: no limit in the liberty, SDC or flow config | — | — | MISSING | — |
| Max slew / cap at SS and FF | SS: 37 slew and 12 cap violating pins; FF: none | OpenSTA | section 6.2 | REPRODUCED 2026-10-06 | section 6.2 |

The published "max slew/cap/fanout PASS" ([results.md](published_reports/results.md) line 17) does not name the corner and counts a fanout check that has no limit; see discrepancy register (09_review_notes). The metrics keys `finish__timing__drv__max_slew_limit` (0.219284) and `..._max_cap_limit` (0.347765) in [6_report.json](orfs_logs/6_report.json) are the slack-to-limit ratios printed in 6_finish.rpt as `max_slew_check_slack_limit 0.2193` and `max_capacitance_check_slack_limit 0.3478`, not limits.

## 8 Power

| Check | Result | Tool + version | Conditions | Status | Source |
|---|---|---|---|---|---|
| Total power | 52.1092 mW: internal 26.3633 mW, switching 25.7459 mW, leakage 0.0279 uW (2.79317e-08 W). By group: Sequential 5.96 mW (11.4 %), Combinational 43.2 mW (83.0 %), Clock 2.90 mW (5.6 %), Macro 0, Pad 0 | OpenSTA `report_power`, OpenROAD "unknown" | TT 25 C 1.80 V, 7.2 ns, OpenRCX SPEF; the tool's default switching activity, no VCD/SAIF annotated; the numeric default activity is not reported. A tool estimate, not a measurement | VERIFIED | [6_report.json](orfs_logs/6_report.json) line 49 and power keys; [6_finish.rpt](orfs_reports/6_finish.rpt) lines 549-561; [power_default_activity.txt](published_reports/power_default_activity.txt); [results.md](published_reports/results.md) lines 53-56 |
| Same query on the same database | 5.21e-02 W total, identical group table | same | [sta.tcl](rerun_2026-10-06/pd_sep/sta.tcl) | REPRODUCED 2026-10-06 | [sta.log](rerun_2026-10-06/pd_sep/sta.log) |
| Activity-based power (workload VCD/SAIF), power at SS/FF | not run | — | — | MISSING | — |
| Baseline layout, for comparison | 47.4874 mW, same TT / default-activity conditions at 7.0 ns | OpenSTA | baseline | VERIFIED | [results_baseline_7p0ns.md](baseline_reference/results_baseline_7p0ns.md) line 53 (= `reports/pd/sky130hd/results.md`) |

## 9 IR drop

| Check | Result | Tool + version | Conditions | Status | Source |
|---|---|---|---|---|---|
| Static IR drop, VDD | worst 0.4539 mV (4.53888e-04 V), average 0.0958 mV, 0.03 %; "All shapes on net VDD are connected" | OpenROAD PSM `analyze_power_grid` (called by ORFS `final_outputs.tcl` lines 39-56), OpenROAD "unknown" | supply 1.80 V (`PWR_NETS_VOLTAGES`), corner `default`, total power 5.21e-02 W from the same default-activity estimate as section 8; PSM default voltage-source placement; OpenRCX SPEF | VERIFIED | [6_report.log](orfs_logs/6_report.log) lines 27-38; [6_report.json](orfs_logs/6_report.json) line 5; [results.md](published_reports/results.md) line 61 |
| Static IR drop, VSS | worst 0.6275 mV (6.27544e-04 V), average 0.0872 mV, 0.03 %; all VSS shapes connected | same | VSS 0.0 V (`GND_NETS_VOLTAGES`), same activity | VERIFIED | [6_report.log](orfs_logs/6_report.log) lines 39-50; 6_report.json line 9; results.md line 62 |
| Same analysis re-run | VDD worst 4.54e-04 V, VSS worst 6.28e-04 V, identical | PSM `analyze_power_grid` | [ir.tcl](rerun_2026-10-06/pd_sep/ir.tcl) | REPRODUCED 2026-10-06 | [ir.log](rerun_2026-10-06/pd_sep/ir.log) lines 14, 33 |
| Dynamic / vectored IR drop | not run | — | — | MISSING | — |

![ORFS final_ir_drop view of the sep layout](../06_physical_design/orfs_images/final_ir_drop.webp.png){: style="width:55%"}

*Figure 2: ORFS GUI export `final_ir_drop` (static, default activity). The export does not name the net; its legend maximum 627.544 uV equals the VSS worst-case drop, so it most likely shows VSS (ASSUMPTION). Source [final_ir_drop.webp.png](../06_physical_design/orfs_images/final_ir_drop.webp.png) (= `build/pd_sep/reports/sky130hd/orbit_demo/sep/final_ir_drop.webp.png`).*

## 10 Electromigration

| Check | Result | Tool + version | Conditions | Status | Source |
|---|---|---|---|---|---|
| EM in the flow | NOT RUN: ORFS calls `analyze_power_grid` without `-enable_em`; no EM text in any sep log (grep of `build/pd_sep/logs/...` and `make_pd_sep.out`, 2026-10-06) | — | — | MISSING | ORFS `final_outputs.tcl` lines 39-56; [orfs_logs/](orfs_logs/) |
| Power-grid currents only (scratch, for information) | max segment current VDD 4.05e-04 A, VSS 4.33e-04 A; no current-density limits applied, so no pass/fail | PSM `analyze_power_grid -enable_em` | same default activity; per-segment reports `em_vdd.rpt` / `em_vss.rpt` stay in review scratch | REPRODUCED 2026-10-06 (currents only) | [ir.log](rerun_2026-10-06/pd_sep/ir.log) lines 17-23, 36-42 (max current lines 20, 39) |
| EM pass/fail (power grid; signal and clock nets) | not run. `sky130_fd_sc_hd.tlef` (read by the flow, [1_synth.log](orfs_logs/1_synth.log) line 7 ODB-0227) defines DCCURRENTDENSITY / ACCURRENTDENSITY for mcon, via-via4 and met1-met5 (15 entries); no step compared the PSM currents or signal/clock-net currents with them | — | — | MISSING | `sky130_fd_sc_hd.tlef` (ORFS image copy; 13 layers and 25 vias, as in the ODB-0227 line) lines 91, 118-119, 135, 159-160, 178, 200-201, 218, 241-242, 260, 282-283 |

## 11 Formal property verification (fault-free RTL)

Conditions for every row: harness [orbit_demo_fv.sv](../04_digital_design/source/formal/orbit_demo_fv.sv) with an independent reference model written from SPEC.md; every DUT input free in every cycle; only assumption reset in the first cycle (`clear` starts from an unconstrained state, `wrap` from a consistent arbitrary state); parameters fixed LANES = 4, T_THROTTLE = 80, T_STOP = 95, T_RECOVER = 70; Yosys 0.69+154, SBY v0.69, Yices 2.7.0, bitwuzla 0.9.1; `FORMAL_TIMEOUT` 1800 s. Published run 2026-09-30 00:14 UTC ([formal/summary.md](formal/summary.md) lines 3-4). Re-run 2026-10-06 at 0495cfa with a scratch BUILD. `formal/summary.md` names the RTL only as `rtl`, with no hash; see discrepancy register (09_review_notes).

### 11.1 Tasks

| Task | Property groups | Mode / engine / depth | Assertions / covers | Published (2026-09-30) | Re-run 2026-10-06 | Status | Source |
|---|---|---|---|---|---|---|---|
| thermal | P5, P6 (+4 helpers) | prove, smtbmc yices, k-induction k = 8 | 15 | PASS, 0 s | PASS | REPRODUCED 2026-10-06 | [formal/summary.md](formal/summary.md) line 28; [logs/thermal.log](formal/logs/thermal.log); [make_formal.log](formal_rerun_2026-10-06/make_formal.log) |
| dup | P7 | prove, smtbmc yices, k = 6 | 12 | PASS, 0 s | PASS | REPRODUCED 2026-10-06 | line 29; [logs/dup.log](formal/logs/dup.log) |
| handshake | P2, P3, P4 + thermal + dup | prove, smtbmc yices, k = 8 | 41 | PASS, 0 s | PASS | REPRODUCED 2026-10-06 | line 30; [logs/handshake.log](formal/logs/handshake.log) |
| datapath | P1, P7, P8 (+8+8 helpers) | prove, smtbmc yices, k = 6 | 59 | PASS, 3 s | PASS | REPRODUCED 2026-10-06 | line 31; [logs/datapath.log](formal/logs/datapath.log) |
| clear | P5, P8 from an unconstrained start state (no reset) | prove, smtbmc yices, k = 3 | 8 | PASS, 0 s | PASS | REPRODUCED 2026-10-06 | line 32; [logs/clear.log](formal/logs/clear.log) |
| product | P1 lemma `sext32(signed8(a)*signed8(b)) == sign*(abs(a)*abs(b))`, all 2^16 operand pairs | prove, smtbmc bitwuzla, k = 1 | 1 | PASS, 6 s | PASS | REPRODUCED 2026-10-06 | line 33; [logs/product.log](formal/logs/product.log) |
| thermal_pdr | P5, P6, no helper invariants | prove, abc pdr (unbounded) | 11 | PASS, 2 s | PASS | REPRODUCED 2026-10-06 | line 34; [logs/thermal_pdr.log](formal/logs/thermal_pdr.log) |
| dup_pdr | P7 | prove, abc pdr | 12 | PASS, 2 s | PASS | REPRODUCED 2026-10-06 | line 35; [logs/dup_pdr.log](formal/logs/dup_pdr.log) |
| handshake_pdr | P2, P3, P4, no helpers | prove, abc pdr | 13 | PASS, 7 s | PASS | REPRODUCED 2026-10-06 | line 36; [logs/handshake_pdr.log](formal/logs/handshake_pdr.log) |
| live | P2_live_delivered `s_eventually !f_watch` under fairness `s_eventually out_ready` | live, aiger suprove (liveness-to-safety) | 1 | PASS, 25 s; suprove gives no per-property status or trace | PASS, 17 s | REPRODUCED 2026-10-06 | line 37; [logs/live.log](formal/logs/live.log) |
| cover | C01-C14 from reset | cover, smtbmc yices, depth 24 | 14 covers, all reached at step 3-6 | PASS | PASS, same steps | REPRODUCED 2026-10-06 | lines 38, 44-59; [logs/cover.log](formal/logs/cover.log) |
| wrap | C20-C22 INT32 wraparound from a consistent arbitrary state | cover, smtbmc yices, depth 8, cover_assert | 3 covers reached at step 2; 88 assertions UNKNOWN (checked only along the 3 traces, not proven by this task) | PASS | PASS | REPRODUCED 2026-10-06 | lines 39, 60-62, 313-404; [logs/wrap.log](formal/logs/wrap.log) |
| datapath_pdr | P1, P8, no helpers (`make formal-extra` only) | prove, abc pdr | 31 | PASS, 837 s | PASS, 941 s (15 m 41 s wall) | REPRODUCED 2026-10-06 | line 40; [logs/datapath_pdr.log](formal/logs/datapath_pdr.log); [make_formal-extra.log](rerun_2026-10-06/formal_extra/make_formal-extra.log); [summary_extra.md](rerun_2026-10-06/formal_extra/summary_extra.md) |

Re-run totals: `make formal` "[formal] all 12 tasks passed", 46.6 s wall, exit 0 ([make_formal.log](formal_rerun_2026-10-06/make_formal.log)); per-property status P1-P8 and cover steps identical to the published summary ([formal_summary.md](formal_rerun_2026-10-06/formal_summary.md) lines 13-62).

### 11.2 Per-property result

| Property | Meaning (short) | Result | Status | Source |
|---|---|---|---|---|
| P1 | every `out_fire` delivers the reference result per lane, INT32 wraparound | PROVEN unbounded (datapath k = 6, product, datapath_pdr) | REPRODUCED 2026-10-06 | [formal/summary.md](formal/summary.md) line 15 |
| P2 | every accepted `in_last` gives exactly one `out_fire`, in order | PROVEN unbounded (handshake, handshake_pdr, live) | REPRODUCED 2026-10-06 | line 16 |
| P3 | `out_valid && !out_ready`: held and stable | PROVEN unbounded | REPRODUCED 2026-10-06 | line 17 |
| P4 | `in_ready` low in STOP/3, fault, clear_fault, buffer full && !out_ready | PROVEN unbounded; the code-3 branch is vacuous because voted code 3 is unreachable fault-free (`P5_never_code3`) and mutant m27 survives (section 14); see discrepancy register (09_review_notes) | REPRODUCED 2026-10-06 | line 18 |
| P5 | voted thermal state follows the SPEC table; reset gives STOP | PROVEN unbounded (`P5_shutdown_req` vacuous for code 3, as P4) | REPRODUCED 2026-10-06 | line 19 |
| P6 | throttle: first THROTTLE cycle admits, then alternate | PROVEN unbounded | REPRODUCED 2026-10-06 | line 20 |
| P7 | fault-free: `fault` and `therm_repair` never rise, copies equal | PROVEN unbounded | REPRODUCED 2026-10-06 | line 21 |
| P8 | `clear_fault` gives fault = 0, out_valid = 0, storage zero, next beat sums from 0 (also from a latched fault) | PROVEN unbounded | REPRODUCED 2026-10-06 | line 22 |
| Induction depth | "closes at k = 2 for thermal, handshake and datapath and at k = 1 for dup (measured 2026-09-29)"; the logs are consistent (third / second "Trying induction" step succeeds) but the measurement itself has no log | — | CLAIM (unverified) | [formal/summary.md](formal/summary.md) lines 504-508 |
| Development claims | "a first attempt ran for over 10 minutes at step 4"; the clear task "added after an independent review found ..." | no log | CLAIM (unverified) | lines 499-500, 516-517 |

SPEC section 6 says `phase` is "forced to 0 whenever the voted state is not THROTTLE"; the RTL clears it at the next edge. The formal summary documents the difference (lines 525-532) and P6 proves admission is unaffected; see discrepancy register (09_review_notes).

### 11.3 Vacuity check (19 one-line RTL mutants that the proofs must fail)

Method: `make formal-vacuity` applies one sed edit to a generated RTL copy (never `rtl/`) and runs the task that should catch it; CAUGHT = sby FAIL with a counterexample from reset on a property with the expected prefix; ERROR, UNKNOWN or timeout (`FORMAL_VAC_TIMEOUT` 900 s) count as MISSED ([formal/vacuity.md](formal/vacuity.md) lines 3-7).

| Result | Tool + version | Conditions | Status | Source |
|---|---|---|---|---|
| 19 / 19 CAUGHT (published 2026-09-30 00:13-00:14) | SBY v0.69, smtbmc yices / abc pdr / aiger suprove | 14 mutants on the k-induction tasks, 5 on the pdr tasks | VERIFIED | [formal/vacuity.md](formal/vacuity.md) lines 11-29; [`formal/logs/vacuity_*.log`](formal/logs/) |
| 19 / 19 CAUGHT, "[vacuity] all mutants caught", 31.4 s | same | re-run at 0495cfa, scratch BUILD | REPRODUCED 2026-10-06 | [formal_vacuity.md](formal_rerun_2026-10-06/formal_vacuity.md); [make_formal-vacuity.log](../05_simulation/rerun_logs_2026-10-06/make_formal-vacuity.log) |
| 19 / 19 CAUGHT, 31.0 s (second, independent re-run) | same | separate scratch BUILD | REPRODUCED 2026-10-06 | [make_formal-vacuity_second_run.log](rerun_2026-10-06/formal_extra/make_formal-vacuity_second_run.log) |

The verdicts are stable; the failing property and step reported for two abc-pdr mutants are not:

| Mutant | Published | Re-run A (package formal_rerun) | Re-run B (second run) |
|---|---|---|---|
| zext_product_pdr | `P1_out_valid_data_lane1 P8_fresh_sum_from_zero_lane1`, step 4 | `P8_fresh_sum_from_zero_lane2`, step 6 | `P1_out_valid_data_lane3 P8_fresh_sum_from_zero_lane3`, step 4 |
| clear_keeps_acc_pdr | `P8_clear_zero_acc_a_lane0 P8_clear_zero_acc_b_lane0`, step 5 | same properties, step 8 | same properties, step 7 |

The other 17 rows (property names and steps) are identical in all three runs. The "step 0" entries for `no_backpressure` and `no_backpressure_pdr` cannot be checked from the trimmed published logs; see discrepancy register (09_review_notes).

### 11.4 Formal limits

Fault-free RTL only (fault detection is section 12); RTL only, no property check on any netlist; single clock; parameters fixed; covers from reset searched to depth 24; the harness depends on Yosys `hierconn`. Source: [formal/summary.md](formal/summary.md) lines 534-549. Status of any netlist-level property check: MISSING.

## 12 Fault injection

### 12.1 Formal fault injection on generated RTL copies

Conditions: [fault/gen_fault_copies.py](../04_digital_design/source/fault/gen_fault_copies.py) writes one RTL copy per scenario with one storage element made upsettable (`q <= q_next ^ fi_mask`, `fi_bit = $anyconst`, `fi_req = $anyseq`); production RTL is the fault-free twin in lockstep in [fi_harness.sv](../04_digital_design/source/fault/fi_harness.sv); at most one upset per trace, any cycle including reset cycles, any lane, any bit; protected scenarios: prove with k-induction k = 4 (`FAULT_PROVE_DEPTH`), cover depth 12; negative scenarios: BMC depth 12; engine smtbmc yices; Yosys 0.69+154, SBY v0.69, Yices 2.7.0. Injection is on RTL copies, not on any netlist. Published run 2026-09-30 00:41-00:44; re-run 2026-10-06 with `make BUILD=<scratch> FAULT_PUBLISH= fault` (reports/fault not written), "[fault] all checks passed", 3 m 17 s.

| Scenario | Injected element | Result | Status | Source |
|---|---|---|---|---|
| acc_a, acc_b | `u_acc_a`, `u_acc_b`, any lane/bit/cycle | prove PASS, 18 assertions, induction closed; cover 8/8 | REPRODUCED 2026-10-06 | [fault/summary.md](fault/summary.md) lines 45-46; [fault/logs/acc_a_prove.log](fault/logs/acc_a_prove.log); [formal_results.md](rerun_2026-10-06/fault/formal_results.md) |
| res_a, res_b | `u_res_a` (drives `out_data`), `u_res_b` | prove PASS, 18 assertions, induction closed; cover 8/8 | REPRODUCED 2026-10-06 | lines 47-48; [fault/logs/](fault/logs/) |
| therm_c0, therm_c1, therm_c2 | `u_thermal.u_copy0/1/2`, any bit/cycle | prove PASS, 16 assertions, induction closed; cover 8/8 (incl. C_upset_copy_code3, C_upset_in_throttle, C_upset_in_stop) | REPRODUCED 2026-10-06 | lines 49-51 |
| neg_out_valid_q (unprotected) | `out_valid_q` | cover 5/5; fire FAIL as expected (`D_out_fire_matches_ref`, step 1); loss FAIL as expected (`D_no_silent_loss`, step 3) | REPRODUCED 2026-10-06 | line 52; [neg_out_valid_q_fire.log](fault/logs/neg_out_valid_q_fire.log), [neg_out_valid_q_loss.log](fault/logs/neg_out_valid_q_loss.log) |
| neg_product (unprotected) | one-cycle transient on the shared `prod32` of one lane | cover 2/2; fire FAIL as expected (`D_out_fire_matches_ref`, step 3): wrong `out_data` transferred with no fault (SDC) | REPRODUCED 2026-10-06 | line 53; [neg_product_fire.log](fault/logs/neg_product_fire.log); [neg_product.diff](fault/injection/neg_product.diff) |
| Negative control `no_compare` (`assign mismatch = 1'b0;`) | acc_a, res_a on the mutant | 4 / 4 FAIL as expected (`L_stop_in_upset_cycle` step 1; `D_out_fire_matches_ref` step 3) | REPRODUCED 2026-10-06 | lines 143-163; [negctl_no_compare.diff](fault/injection/negctl_no_compare.diff); [negctl_formal_results.md](rerun_2026-10-06/fault/negctl_formal_results.md) |
| Totals | 19 scenario tasks, 0 unexpected; 4 negctl tasks, 0 unexpected | — | REPRODUCED 2026-10-06 | [make_fault.log](rerun_2026-10-06/fault/make_fault.log); [summary.md (re-run)](rerun_2026-10-06/fault/summary.md) |
| Hand-run BMC without helpers (about step 8 / frame 10 after about 10 min) and 24-step BMC with helpers (7 min) | no log | — | CLAIM (unverified) | [fault/summary.md](fault/summary.md) lines 57-62 |

### 12.2 RTL SEU simulation campaign

Conditions: [tb_seu_campaign.v](../04_digital_design/source/fault/tb_seu_campaign.v), Icarus Verilog 14.0 (devel); two copies of the production RTL behind identical hosts on one random workload; seed=1 tpb=12 tpb_unprot=200 controls=20 prefix=8..127 post=64 drain=24+8; one bit flipped by hierarchical assignment at the falling edge; zero-delay RTL, 10 ns sim clock; host reaction `clear_fault` 2 cycles after `fault`. Re-run 2026-10-06: `trials.tsv` byte-identical to `build/fault/campaign/trials.tsv`, report byte-identical to the published campaign.md.

| Storage group | Result (trials: outcomes) | Status | Source |
|---|---|---|---|
| All | 6836 trials, 0 bench errors; 20 controls all MASKED; 6816 injected; all 521 bits, each at least 12 times; 9 / 9 campaign checks PASS | REPRODUCED 2026-10-06 | [fault/campaign.md](fault/campaign.md) lines 12, 36-46; [campaign_report.md](rerun_2026-10-06/fault/campaign_report.md); per-bit table [campaign_per_bit.tsv](fault/campaign_per_bit.tsv) |
| Accumulator pairs (256 bits) | 3072: MASKED 3, DETECTED 3069, escapes 0 | REPRODUCED 2026-10-06 | campaign.md line 5 |
| Result pairs (256 bits) | 3072: MASKED 4, DETECTED 3067, TIMING 1, escapes 0 | REPRODUCED 2026-10-06 | line 6 |
| Detection latency (acc + res) | all 6136 detected trials: `fault` = 1 one cycle after the upset cycle; `in_ready` and `out_valid` already 0 at the end of the upset cycle | REPRODUCED 2026-10-06 | line 14 |
| 8 acc/res upsets not DETECTED | all had `clear_fault` in the upset cycle (both copies zeroed); 7 MASKED, 1 TIMING (trial 3836 `g_lane[1].u_lane.u_res_a.q[30]`) | REPRODUCED 2026-10-06 | lines 16-17 |
| Thermal triple (6 bits) | 72: REPAIRED 72, escapes 0 | REPRODUCED 2026-10-06 | line 7 |
| Throttle `phase` (unprotected) | 200: MASKED 156, TIMING 44 (all in THROTTLE). Escapes column 0 because TIMING is not counted as an escape although SPEC section 8 lists `phase` as an expected escape; see discrepancy register (09_review_notes) | REPRODUCED 2026-10-06 | lines 8, 25-27 |
| `out_valid_q` (unprotected) | 200: LOST 38, EXTRA 162 (129 duplicate, 33 stale), escapes 200 (100 %) | REPRODUCED 2026-10-06 | lines 9, 23-24, 30 |
| `fault_q` 0 -> 1 (unprotected) | 200: DETECTED 200, a false fault stop with no data error | REPRODUCED 2026-10-06 | lines 10, 28 |
| `fault_q` 1 -> 0 (SPEC section 8 escape) | not measured: needs two faults, the single-upset campaign cannot reach `fault_q` = 1 first | MISSING | [fault/summary.md](fault/summary.md) lines 254-256 |
| Negative control campaign on `no_compare` | 535 trials, 0 errors; acc 256: MASKED 196, SDC 60; res 256: MASKED 230, SDC 26; escape checks PASS | REPRODUCED 2026-10-06 | [fault/summary.md](fault/summary.md) lines 230-239; [negctl_campaign_report.md](rerun_2026-10-06/fault/negctl_campaign_report.md) |

### 12.3 Post-route gate-level fault campaign (sep netlist)

| Check | Result | Tool + version | Conditions | Status | Source |
|---|---|---|---|---|---|
| GLS lockstep with injection | "GLS PASS: 30000 cycles, 0 mismatches"; 702 duplicated-copy flips (702 stopped), 234 thermal-copy flips (234 repaired); 518 of 518 redundant bits hit; coverage: 8729 beats, 1037 results, 6 resets, 733 clears; NORMAL 14075 / THROTTLE 1737 / STOP 14182 cycles, code3 0 | Icarus Verilog (version not logged in 2026-09-29 run); cell models from `cells.lib` (tt_025C_1v80) via Yosys `read_liberty` | [tb_gls.v](../04_digital_design/source/pd/gls/tb_gls.v): RTL and routed sep `6_final.v` in lockstep, zero-delay, seed 1, one flip per 32 cycles at the falling edge (list in [gl_inject.vh](gls/gl_inject.vh)); checks stop/repair behaviour and lockstep outputs, no golden-result scoreboard | VERIFIED | [gls/gls.log](gls/gls.log) lines 1-5 (= `build/pd_sep/gls/sep/gls.log` = `reports/pdsep/gls.log`); [pdsep.mk](../04_digital_design/source/mk/pdsep.mk) lines 127-137 |
| Same campaign re-run | identical output, 2 m 18 s | Icarus Verilog 14.0 (devel) s20260301-500-g2e81fcccb-dirty | same | REPRODUCED 2026-10-06 | [gls_rerun.log](rerun_2026-10-06/pd_sep/gls_rerun.log) |
| Netlist-mutant control on the sep netlist | instance `_4098_` `sky130_fd_sc_hd__and2_1` -> `sky130_fd_sc_hd__or2_1` (#0 of 184): first MISMATCH at cycle 7, "GLS FAIL: 1148 errors" (the harness observes the netlist) | Icarus 14.0 | 3000 cycles, seed 1. The log does not name the netlist; "#0 of 184" matches the 184 `and2_1` instances of the sep 6_final.v (the base netlist has 189) | REPRODUCED 2026-10-06 | [gls_mutant.log](rerun_2026-10-06/pd_sep/gls_mutant.log) |
| Directed bench on the sep netlist | see [05_simulation](../05_simulation/simulation_report.md) (S8): TB_ORBIT_DEMO PASS, summary identical to RTL | Icarus 14.0 | zero-delay | REPRODUCED 2026-10-06 | [gls_sky130hd_sep_directed.log](../05_simulation/rerun_logs_2026-10-06/gls_sky130hd_sep_directed.log) |

### 12.4 Not injected

| Item | Status | Source |
|---|---|---|
| Comparators (`lane_mismatch`, `mismatch`), voter, clock, reset, sensor and handshake inputs | MISSING (listed in SPEC section 8, not injected in either flow) | [fault/summary.md](fault/summary.md) lines 243-246 |
| Multi-bit upsets, common-mode upsets of both copies | MISSING | same |
| `fault_q` 1 -> 0 (needs two faults); thermal voted code 3 (needs two copies upset) | MISSING | lines 254-256; [mutation/summary.md](mutation/summary.md) (m27) |
| Shared-product transient in the simulation campaign (only formal `neg_product`) | MISSING | campaign injects stored bits only |
| Fault injection with SDF timing (SET width, latching window) | MISSING | all GLS zero-delay |
| Multi-seed campaign statistics, confidence intervals | MISSING (seed 1 only) | [fault/summary.md](fault/summary.md) lines 251-253 |
| Radiation test data, cross-sections, FIT | MISSING ("Nothing here is a radiation test") | line 257 |

## 13 Synthesis checks

| Check | Result | Tool + version | Conditions | Status | Source |
|---|---|---|---|---|---|
| keep_hierarchy in the ORFS (reviewed) synthesis | hierarchy kept: 19 `orbit_keep_reg` submodules (16 x W=32, 3 x W=2 RESET_VAL=2'10); 521 `sky130_fd_sc_hd__dfxtp_1`; 5130 cells, 46866.1984 um^2. Kept by `(* keep_hierarchy *)` in [orbit_keep_reg.v](../04_digital_design/source/rtl/orbit_keep_reg.v) line 14 and `SYNTH_KEEP_MODULES = *orbit_keep_reg*` ([config.mk](../04_digital_design/source/pd/sky130hd_sep/config.mk) line 30). Log warning `Selection "*orbit_keep_reg*\$*" did not match any module` (the second, slang-frontend pattern) | Yosys 0.68+post (ORFS) | ABC speed script, `-D 7.2`, liberty TT | VERIFIED | [synth_stat.txt](orfs_reports/synth_stat.txt) lines 152-154, 265-269; [1_2_yosys.log](orfs_logs/1_2_yosys.log) lines 1-9 |
| ORFS synthesis structural check | CHECK pass "Found and reported 0 problems" on both `orbit_keep_reg` variants and `orbit_demo` | Yosys 0.68+post | — | VERIFIED | [synth_check.txt](orfs_reports/synth_check.txt) |
| keep negative control, ORFS (baseline platform, synthesis stage only) | cfgkeep (RTL attribute removed, SYNTH_KEEP_MODULES set): PASS 19/19, 521 FF; nokeep (both removed): FAIL 17/19, 517 FF, thermal `u_copy1`/`u_copy2` 0 cells | Yosys 0.68+post, [pd/audit_storage.py](../04_digital_design/source/pd/audit_storage.py) | baseline `pd/sky130hd` config, not the sep run | VERIFIED | [negctl_cfgkeep_audit.txt](baseline_reference/negctl_cfgkeep_audit.txt); [negctl_nokeep_audit.txt](baseline_reference/negctl_nokeep_audit.txt) |
| keep negative control, generic flow | nokeep: 517 FF, 4865 cells, thermal copies MERGED, audit FAIL 8/9; regkeep (`(* keep *)` on `q` only): same, does not prevent the merge; NEGATIVE_CONTROL PASS | Yosys 0.69+154 | [synth/synth_generic.ys](../04_digital_design/source/synth/synth_generic.ys) | REPRODUCED 2026-10-06 | [negative_control.txt](synth/negative_control.txt) (re-run byte-identical, [make_synth.log](rerun_2026-10-06/synth/make_synth.log)) |
| Storage audit, routed sep `6_final.v` (published) | RESULT: PASS (18/18 checks passed); 6250 leaf cells; 521 dfxtp_1; 9 redundant groups OK; 521 distinct Q nets; 51 clock-leaf nets. Produced by the older `pd/audit_storage.py` (report 2026-09-29 22:30; script changed in b1da230, 23:47, adding a 19th check) | `pd/audit_storage.py` (pre-b1da230), liberty `build/pd_sep/platform/cells.lib` | — | VERIFIED | [storage_audit.txt](published_reports/storage_audit.txt) lines 3, 36 |
| Storage audit, same netlist, current script | RESULT: PASS (19/19); added check "clock pins on the clock tree: 0 flip-flops whose clock net does not trace back to port 'clk'" PASS; all other lines identical | [pd/audit_storage.py](../04_digital_design/source/pd/audit_storage.py) at HEAD | same netlist and liberty | REPRODUCED 2026-10-06 | [storage_audit_current_script.txt](rerun_2026-10-06/pd_sep/storage_audit_current_script.txt) lines 35, 37 |
| Storage audit, generic netlist | STORAGE_AUDIT PASS: 9/9 groups, 521 FF bits, 3 unprotected (`fault_q`, `out_valid_q`, `u_thermal.phase`); flat view identical; self-test: 12 defect classes all detected | Yosys 0.69+154, [scripts/storage_audit.py](../04_digital_design/source/scripts/storage_audit.py) | generic netlist `build/synth/orbit_demo_synth.json` | REPRODUCED 2026-10-06 | [synth/storage_audit.txt](synth/storage_audit.txt); [storage_audit_flat.txt](synth/storage_audit_flat.txt); [audit_selftest.log](synth/audit_selftest.log) |
| Generic synthesis structural checks | SYNTH_GENERIC PASS: 4899 cells = 4373 generic logic + 521 FF + 5 `$scopeinfo`; no latches; no warnings | Yosys 0.69+154 | `synth -flatten` with kept instances | REPRODUCED 2026-10-06 | [synth_counts.txt](synth/synth_counts.txt) (re-run byte-identical) |
| Equivalence RTL vs generic netlist | EQUIV PASS: 47 register ports cut and matched by name; tasks lane0-lane3, ctrl PASS; mutants mut_throttle (T_THROTTLE 80 -> 81) and mut_zext FAIL as required | SymbiYosys, smtbmc bitwuzla, BMC depth 1 per partition (register-correspondence combinational check) | gold RTL vs `build/synth/orbit_demo_synth.v` (generic cells, not sky130) | REPRODUCED 2026-10-06 | [equiv_result.txt](synth/equiv_result.txt); [re-run](rerun_2026-10-06/synth/equiv_result.txt) (44 s vs 40 s wall) |
| GLS of the generic netlist | TB_ORBIT_DEMO PASS, summary identical to the RTL run (14 scenarios, 133601 cycles, 0 errors) | Icarus 14.0, Yosys simcells/simlib | zero-delay, seed 1 | REPRODUCED 2026-10-06 | [gls_result.txt](synth/gls_result.txt); [make_synth.log](rerun_2026-10-06/synth/make_synth.log) |
| `make synth` overall | "SYNTH PASS: generic synthesis + checks, storage audit (+ self-test), keep_hierarchy negative control, equivalence to RTL, gate-level simulation", 2 m 0.2 s | Yosys 0.69+154 | scratch BUILD | REPRODUCED 2026-10-06 | [make_synth.log](rerun_2026-10-06/synth/make_synth.log) |
| RTL vs sky130-mapped netlist (`1_2_yosys.v` / `1_synth_lec.v`) formal equivalence | not run; only zero-delay GLS links RTL to the sky130 netlists (12.3) | — | — | MISSING | — |
| Brief p.4 "4,356 generic logic cells" | not reproduced: 4373 native, 4384 YoWASP Yosys 0.69; no script given | — | — | CLAIM (unverified) | [synth/summary.md](synth/summary.md) lines 12, 21; [yowasp_compare.txt](synth/yowasp_compare.txt) |

Two different storage audits exist (generic [scripts/storage_audit.py](../04_digital_design/source/scripts/storage_audit.py), "9/9 groups"; sky130 [pd/audit_storage.py](../04_digital_design/source/pd/audit_storage.py), "18/18" or "19/19 checks"), and the published sep reports (results.md line 24, checks.json, summary.md) still quote the superseded 18/18; see discrepancy register (09_review_notes).

## 14 Mutation testing of the verification suite (context for formal and fault)

| Check | Result | Tool + version | Conditions | Status | Source |
|---|---|---|---|---|---|
| Mutation score | 35/40 valid mutants killed (87.5 %); 35/39 (89.7 %) excluding m21, argued equivalent | `scripts/mutation_test.py`; targets lint, sim, formal-quick, fault-quick, synth | 40 RTL mutants, baseline m00 passes all targets; generated 2026-09-30; not re-run | VERIFIED | [mutation/summary.md](mutation/summary.md) lines 5-52 |
| Survivors | m07 `result_from_b`, m20 `out_valid_no_fault`, m22 `fault_not_sticky`, m27 `shutdown_only_stop` (real test gaps), m21 `out_fire_unmasked` (equivalent); all also pass the full `formal` set. Missing checks named: `fault -> !out_valid && !in_ready` and fault stickiness under a `fault_q` upset; `out_data` equal to reference while `out_valid` low; `therm_state == 3 -> shutdown_req && !in_ready` | evidence bench [tb_mutation_gaps.v](mutation/tb_mutation_gaps.v) FAILs on each survivor, PASS on unmodified RTL | — | VERIFIED | [mutation/summary.md](mutation/summary.md) lines 72-140 |

## 15 ECC standalone block (not in the layout)

[rtl/ecc/orbit_secded72.v](../04_digital_design/source/rtl/ecc/orbit_secded72.v) (Hsiao (72,64) SECDED encoder/decoder) and [rtl/ecc/orbit_ecc_bank.v](../04_digital_design/source/rtl/ecc/orbit_ecc_bank.v) (16 rows x 2 interleaved codewords, scrubber, error log) are not instantiated by `orbit_demo`, are not in `$(RTL)`, and were not read by the ORFS synthesis of the reviewed layout ([1_1_yosys_canonicalize.log](orfs_logs/1_1_yosys_canonicalize.log) lines 7-11 read only the four orbit_demo RTL files; [mk/ecc.mk](../04_digital_design/source/mk/ecc.mk) line 3 "NOT part of orbit_demo"). Physical checks (timing, area, power, DRC, LVS, IR, EM) of ECC: N/A for this layout (block not placed); MISSING if ECC is to be integrated.

Conditions: published run [ecc/results.txt](ecc/results.txt) (= `reports/ecc/results.txt`); full `make BUILD=<scratch> ecc` re-run 2026-10-06 at 0495cfa: "ECC: PASS", exit 0, 20 m 41 s; summary identical to the published results except run times. Tools Yosys 0.69+154, SBY, smtbmc bitwuzla/yices, Icarus 14.0, Verilator 5.053.

| Check | Result | Tool | Conditions | Status | Source |
|---|---|---|---|---|---|
| Lint | Verilator -Wall and Icarus -Wall clean | Verilator 5.053, Icarus 14.0 | `--top-module orbit_ecc_bank` | REPRODUCED 2026-10-06 | [ecc/results.txt](ecc/results.txt) line 14; [summary.txt](rerun_2026-10-06/ecc/summary.txt) |
| H matrix | Hsiao construction: 72 distinct odd-weight columns, 26 ones per data row | [rtl/ecc/gen_hsiao72.py](../04_digital_design/source/rtl/ecc/gen_hsiao72.py) `--check` | — | REPRODUCED 2026-10-06 | results.txt line 13; [hsiao.log](ecc/logs/hsiao.log) |
| Codec simulation | seed 1: 20003 no-error words; 21600 single-bit errors corrected (300 words x 72); 30672 double-bit errors detected (12 x 2556 pairs); 19189 triple-bit: 8417 UE, 10772 miscorrected; errors 0; PASS | Icarus 14.0 | reference H built from the construction rule | REPRODUCED 2026-10-06 | [sim_codec_seed1.log](ecc/logs/sim_codec_seed1.log) |
| Bank simulation | seeds 1 and 2, 15098 cycles each (15000 random + directed), errors 0; seed 1: 3462 writes / 4971 reads, 270 CE / 14 UE reads, 1075 scrub repairs | Icarus 14.0 | DEPTH 16, INTERLEAVE 2, CNT_W 16 plus a CNT_W 3 copy; upsets by hierarchical writes, never a third error per codeword | REPRODUCED 2026-10-06 | [sim_bank_seed1.log](ecc/logs/sim_bank_seed1.log), [sim_bank_seed2.log](ecc/logs/sim_bank_seed2.log) |
| Simulation negative controls | 7 / 7 mutants killed (bank_cnt_wrap, bank_log_prio, bank_no_interleave, bank_no_writeback, bank_read_way_swap, bank_scrub_on_read, codec_even_col) | Icarus 14.0 | exact text substitution, bank bench 3000 cycles | REPRODUCED 2026-10-06 | results.txt lines 18-24 |
| Codec proof | PASS: no error unchanged; any single error corrected (ce=1); any double error ue=1, no flip; encoder linear | SBY prove depth 1, smtbmc bitwuzla | combinational, all inputs free (complete) | REPRODUCED 2026-10-06 | results.txt line 8; [formal_codec_orbit_secded72_codec.log](ecc/logs/formal_codec_orbit_secded72_codec.log) |
| Bank proofs clean / sec / ded | PASS by k-induction (41 s / 135 s / 89 s published) | SBY prove depth 2, smtbmc bitwuzla | DEPTH 16, INTERLEAVE 2, CNT_W 3; decoder replaced by an abstraction constrained to the codec contract; at most one upset event per edge (1 bit or 2 adjacent columns) | REPRODUCED 2026-10-06 | results.txt lines 1, 4, 7; [`formal_bank_*.log`](ecc/logs/) |
| Covers | cover: c_scrub_two step 2, c_ce_read_adj 3, c_saturate 6, c_bound_tight 17; cover_ded: c_ue_read step 4 | SBY cover depth 24, smtbmc yices | — | REPRODUCED 2026-10-06 | results.txt lines 2-3 |
| End-to-end with the real decoder | e2e_clean PASS (BMC 5 steps), e2e_upset PASS (BMC 4 steps); bounded only; U4 scrub bound not reached at this depth | SBY bmc, bitwuzla | DEPTH 2 (chparam) | REPRODUCED 2026-10-06 | results.txt lines 5-6 |
| Unbounded end-to-end statement (real encoder + decoder + bank) | rests on a written composition argument, not machine-checked | — | — | CLAIM (unverified) | [rtl/ecc/README.md](../04_digital_design/source/rtl/ecc/README.md) lines 186-206 |
| Formal negative controls | 4 / 4 FAIL as expected (il1_neg, codec_even_col, bank_no_writeback, bank_read_way_swap) | SBY | — | REPRODUCED 2026-10-06 | results.txt lines 9-12 |
| sec_bmc positive control, published log | incomplete run of an older harness: steps 0-3 without failure, terminated at 600 s during step 4; neither PASS nor FAIL; not listed in results.txt | SBY bmc depth 6, bitwuzla | DEPTH 16, INTERLEAVE 2, CNT_W 3; harness before commit e80a7b2 | VERIFIED (as an incomplete run) | [formal_sanity_sec_bmc_production_timeout.log](ecc/logs/formal_sanity_sec_bmc_production_timeout.log) |
| sec_bmc positive control, re-run with the current harness | PASS at depth 6 (steps 0-5), 2672 s | SBY bmc depth 6, bitwuzla | same parameters, harness at 0495cfa | REPRODUCED 2026-10-06 | [sanity_sec_bmc_result.txt](rerun_2026-10-06/ecc/sanity_sec_bmc_result.txt); [sanity_sec_bmc_production_pass_trimmed.log](rerun_2026-10-06/ecc/sanity_sec_bmc_production_pass_trimmed.log) |
| Generic synthesis | enc 154 cells, 0 FF, depth 6; dec 431 cells, 0 FF, depth 18; bank 10690 cells, 2414 FF (expected 2414), depth 48; no latches | Yosys 0.69+154 | generic cells, no liberty | REPRODUCED 2026-10-06 | results.txt lines 25-27; [ecc/synth_stat.txt](ecc/synth_stat.txt) |

The stale sec_bmc timeout log and the orphan [sim_bank_quick.log](ecc/logs/sim_bank_quick.log) (= `reports/ecc/logs/sim_bank_quick.log`) are flagged; see discrepancy register (09_review_notes).

## 16 Not done / missing

| Item | Why it matters here | What would be needed | Status |
|---|---|---|---|
| Sign-off DRC (FEOL, density, latch-up), Magic DRC | KLayout ORFS deck runs BEOL + OFFGRID only; no fill | Magic DRC or the open_pdks KLayout sign-off deck on a filled GDS | MISSING |
| Metal fill and density checks | no fill inserted; `sky130_fd_sc_hd.tlef` (read by the flow, 1_synth.log ODB-0227) defines MAXIMUMDENSITY 70 / DENSITYCHECKWINDOW 700 700 (met1-met4), but no step compared the metal density with it | fill generation, then a density check against these values or a sign-off deck | MISSING |
| Independent LVS | KLayout LVS reference comes from the same 6_final.odb | Magic extraction + Netgen against 6_final.v or the synthesized netlist | MISSING |
| Antenna check outside OpenROAD | only the OpenROAD ANT checker ran | Magic / KLayout antenna rules | MISSING |
| RTL vs sky130 netlist formal equivalence | kepler-formal covers synth -> final only; RTL -> generic proven, RTL -> sky130 only simulated | eqy or equiv_cut.ys flow with sky130 cell models on 1_2_yosys.v / 6_final.v | MISSING |
| kepler-formal, OpenROAD, ORFS, PDK versions | not recorded in any log | log image digest, ORFS/OpenROAD commit, open_pdks version per run | MISSING |
| RC corners, OCV / derates, clock uncertainty, I/O budgets | timing uses nominal RC and placeholder I/O delays | min/max RCX rules, uncertainty/derate spec, interface budget | MISSING |
| Additional liberty corners; timing closure at SS | SS fails by 6.131 ns with 516 endpoints and 37/12 slew/cap violations | more corners; MCMM optimisation, or a decision on operating corner and period | MISSING |
| Demonstrator speed / PVT requirement | no requirement to judge corner results against | stated target frequency and PVT range | MISSING |
| Post-layout SPICE; SDF-annotated GLS | all GLS zero-delay; no transistor-level simulation | SDF from OpenSTA with 6_final.spef; timing GLS; SPICE of critical paths if needed | MISSING |
| Activity-based and corner power; dynamic IR | power and IR use default activity at TT | VCD/SAIF from a workload; read in OpenSTA; vectored PSM | MISSING |
| Electromigration | not run; `sky130_fd_sc_hd.tlef` (read by the flow, 1_synth.log ODB-0227) defines DCCURRENTDENSITY / ACCURRENTDENSITY per via and metal layer, but no step compared the PSM currents (section 10) or signal/clock-net currents with them | the comparison, per layer and via, for power, signal and clock nets | MISSING |
| Fault injection gaps | comparators, voter, clock, reset, inputs, MBU, common mode, `fault_q` 1 -> 0, thermal code 3, product in campaign, netlist/SDF injection, multi-seed | see 12.4; double-fault scenarios; netlist-level campaign | MISSING |
| Property checks the mutation run asks for | m07, m20, m22, m27 survive | assertions listed in section 14 | MISSING |
| Formal on a netlist | all properties checked on RTL only | rerun `orbit_demo_fv.sv` on a netlist | MISSING |
| Regenerated published sep storage audit | published reports quote 18/18 from a superseded script | re-run `make pd-sep-report` and republish | MISSING (re-run only in this package) |
| Make target for sep multi-corner STA | results exist only as a hand run | `pd-sep-corners` target in mk/pdsep.mk publishing to reports/pdsep/ | MISSING |
| Counterexample / cover VCDs, per-trial campaign log | only in gitignored build/ | copy build/formal, build/fault traces and trials.tsv | MISSING (not in package) |
| ECC integration and physical data | ECC is standalone | integration spec, RTL, layout run | N/A for this layout |
| Pad ring, IO cells, ESD, package checks | the layout is a core block: 0 padcells ([6_report.json](orfs_logs/6_report.json) line 60) | — | N/A (no pad ring, no package) |
| Analog / mixed-signal verification | no analog blocks | — | N/A (digital only) |
| Silicon measurement | not fabricated | — | N/A (no silicon) |
