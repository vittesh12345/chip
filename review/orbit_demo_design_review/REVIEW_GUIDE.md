# Reviewer guide: how to review orbit_demo

This guide takes a reviewer through the package in a fixed order, says what to check at each step, and ends with a feedback template. The package [README.md](README.md) has the exact revision, folder map and status legend; this guide does not repeat them.

**What is being reviewed.** `orbit_demo` is a 4-lane INT8 MAC digital demonstrator with duplicated storage and a mismatch fault-stop, plus a thermal FSM with TMR state. It is implemented as a core-only standard-cell block on SkyWater sky130hd. The reviewed layout is the ORFS run `sep` at 7.2 ns with copy-separation fences. Timing was optimised at TT only and fails setup at ss_100C_1v60 (K-01). It has not been fabricated, has no pad ring or package, and has had no radiation testing (K-05, K-08).

**Out of scope.** The unbuilt 16-tile concept chip in the brief, the reference layouts (`base` at 7.0 ns, IHP SG13G2), and the presentation material in `site/`, `viz/` and `docs/research/`. The review notes list where the presentation material overstates the evidence (D-62 to D-84); question 14 asks only whether it should be corrected or withdrawn.

## What you need

| Purpose | Needed |
|---|---|
| Reading (steps 1-4) | A PDF viewer, or GitHub's Markdown view. Each section's text is a `.md` file, and the main ones also have a `.pdf`. Step 4 also needs `sha256sum` |
| Inspecting the layout | KLayout (the package used 0.30.12) to open [06_physical_design/layout_db/6_final.gds.gz](06_physical_design/layout_db/6_final.gds.gz). The sky130 layer-properties file is not in the package, so KLayout uses default colours. The pre-rendered views in [06_physical_design/klayout_views/](06_physical_design/klayout_views/) use the ORFS `sky130hd.lyp` |
| Re-running checks (step 5, optional) | A checkout of the repository at the package commit and the OSS CAD Suite. The layout rows also need Docker with the ORFS image and the outputs of a `make pd-sep` run. See [04_digital_design/README.md](04_digital_design/README.md) section 6 |

## Time plan

| Step | Activity | Time |
|---|---|---|
| 1 | Orientation | 20 min |
| 2 | Known issues and the reviewer questions | 30 min |
| 3 | Area-by-area review (seven areas) | 1.5-3 h |
| 4 | Revision and consistency check | 15 min |
| 5 | Reproduce selected results (optional) | 15 min to 1 h |
| 6 | Write feedback | 20 min |

Total without step 5: about 3-4.5 h.

## Step 1. Orientation (20 min)

1. [README.md](README.md): read the revision table, the status legend and the verification status overview.
2. [01_overview/design_overview.pdf](01_overview/design_overview.pdf): read the scope split (built demonstrator vs concept-chip TARGETs), then the requirements table. Note that the demonstrator has **no** specified clock target, supply specification, power budget or PVT range (all MISSING, G-01). Every timing or power number in the package is therefore a result without a requirement to compare against.
3. [02_block_diagram/orbit_demo_top_level.pdf](02_block_diagram/orbit_demo_top_level.pdf): keep this open for the rest of the review. The detailed diagram is [orbit_demo_block_diagram.pdf](02_block_diagram/orbit_demo_block_diagram.pdf).

## Step 2. Known issues and questions (30 min)

Read [09_review_notes/review_notes.pdf](09_review_notes/review_notes.pdf) sections 1-3.

**Section 1, known issues K-01 to K-16.** The five High items:

- K-01: setup fails at ss_100C_1v60.
- K-02: single points of failure.
- K-03: common-mode faults are not detected, and several are not injected.
- K-04: the DRC deck runs BEOL and off-grid checks only (FEOL off), and LVS is not independent.
- K-05: no pad ring or package.

For each, decide whether it blocks the next step, and record any you disagree with.

**Section 2, trade-offs T-01 to T-07.** Check that each trade-off is justified by its cited evidence.

**Section 3, questions 1-14.** These are the decisions the design owner is asking you to make. Answer them in your feedback (step 6). The area checklists below point to the questions that each area informs.

## Step 3. Area-by-area review

Work through the areas in order. Each checklist item names the document and, where relevant, the review-notes item it relates to.

### 3.1 Architecture and RTL

Documents: [04_digital_design/README.md](04_digital_design/README.md) sections 3-5; RTL in [04_digital_design/source/rtl/](04_digital_design/source/rtl/); [source/docs/SPEC.md](04_digital_design/source/docs/SPEC.md); schematics in [03_schematics/](03_schematics/).

- [ ] Compare the RTL with SPEC sections 3-6: the MAC equation and wrap-around, the `in_ready`/`out_valid` equations, the duplicate-and-compare and sticky `fault_q`, the TMR vote and feedback repair, and the throttle/stop/recover thresholds. Known differences: `phase` wording (K-16, D-02), a presented result withdrawn by `clear_fault` or `rst_n` (D-03), and the combinational `clear_fault` -> `in_ready` path (D-04).
- [ ] Check the fault model against SPEC section 8 and K-02/K-03. One instance feeds both copies: the multiplier and `prod32`, the comparators and the mismatch OR-tree, the lane control (`in_fire`, `clr`, `in_first`, `in_last`), the thermal voter and the `nxt` cone, the clock, the reset and the inputs. `phase`, `fault_q` and `out_valid_q` are unprotected. SPEC section 8 lists only part of this (D-01). Questions 3-6.
- [ ] Reset and clear: `rst_n` is synchronous with no on-chip synchronizer. `clear_fault` zeroes lane storage but not the thermal state. Question 8 covers the host re-send protocol.
- [ ] Clocking: single domain, no CDC, no clock gating in the RTL.
- [ ] Schematics: [03_schematics/README.md](03_schematics/README.md) explains why transistor sizes and bias currents are N/A (standard cells only). The gate-level sheets come from the synthesized netlist, before placement; 03 lists the differences from the routed netlist.
- [ ] ECC: [rtl/ecc](04_digital_design/source/rtl/ecc/) is standalone and not in the layout (K-12). Decide whether it should be reviewed now.

### 3.2 Functional verification

Documents: [05_simulation/simulation_report.pdf](05_simulation/simulation_report.pdf); formal and fault sections of [07_verification/verification_summary.pdf](07_verification/verification_summary.pdf).

- [ ] Test inventory S1-S14: check that the stimulus, pass criterion and checked properties cover each SPEC requirement. Use the requirements table in 01 as the index.
- [ ] Formal: 12 tasks plus `datapath_pdr` pass, and the vacuity check catches 19/19. The code-3 branch is vacuous (K-10). The mutation campaign kills 35 of 40 mutants: m07, m20, m22 and m27 survive as test gaps, and m21 is argued equivalent. Question 10.
- [ ] Fault injection: the RTL SEU campaign and the gate-level campaign on the routed sep netlist (702 duplicated-copy flips stopped, 234 thermal-copy flips repaired, 0 mismatches). Known escapes: `out_valid_q` 200/200, `fault_q` 0->1 200/200 false stops, `phase` 44/200 shifted admissions; `fault_q` 1->0 is not measured. `neg_product` shows silent data corruption (K-03).
- [ ] Every simulation is zero-delay. No SDF-annotated gate-level simulation exists (MISSING). Decide whether that is needed.
- [ ] Waveforms in [05_simulation/waveforms/](05_simulation/waveforms/) are plotted from VCDs of RTL runs at a 10 ns functional clock. Spot-check scenario (c), the fault-stop, against SPEC section 5.

### 3.3 Timing and constraints

Documents: [07_verification/verification_summary.pdf](07_verification/verification_summary.pdf) timing sections; [sta_corners_sep_2026-10-06/sta_corners_sep.txt](07_verification/sta_corners_sep_2026-10-06/sta_corners_sep.txt); SDC [06_physical_design/layout_db/6_final.sdc](06_physical_design/layout_db/6_final.sdc).

- [ ] Constraints: one clock at 7.2 ns, input and output delays of 20 % of the period (1.44 ns, an ASSUMPTION), no load, drive, input transition, uncertainty or derate. Questions 1-2.
- [ ] TT: setup WNS 0.031 ns, hold WNS 0.436 ns, fmax 139.49 MHz including the I/O paths (170.82 MHz reg-to-reg). The critical path is in2reg, from `in_a[27]` through the lane's shared multiplier to `g_lane[3].u_lane.u_res_a/q[29]`.
- [ ] ss_100C_1v60 (re-run for this package): WNS -6.131 ns, 516 endpoints, min period 13.33 ns, also 37 max-slew and 12 max-cap violations. FF passes. Only these three liberty corners exist on disk, and the SPEF has one nominal RC corner.
- [ ] LEC: both kepler-formal checks report "Circuits are IDENTICAL". The "4_rsz" check compares the netlist before and after `repair_timing`, not synthesis against post-CTS (K-14). The compared netlists are in [additional_evidence/lec_netlists/](07_verification/additional_evidence/lec_netlists/).

### 3.4 Floorplan and layout

Documents: [06_physical_design/physical_design.pdf](06_physical_design/physical_design.pdf); full-resolution images in [klayout_views/](06_physical_design/klayout_views/) and [orfs_images/](06_physical_design/orfs_images/).

- [ ] Die 346.295 um square, utilization 0.5361. The PDN has met1 rails and met4/met5 straps, single VDD/VSS.
- [ ] Copy-separation fences (v03, v04, v05): copy A on the left edge, copy B on the right, three thermal fences. Accumulator and result same-bit copies are at least 251.17 um apart, thermal copies 97.92 um, and none of the 262 same-bit pairs touch. Non-member cells overlap the fences, including clock-tree buffers (K-13; question 13). Shared drivers across copies (D-93; question 6).
- [ ] Open the GDS in KLayout and check one area yourself, for example the cells in and around a thermal fence. The fences are not drawn in the GDS: take the box coordinates from 06 section 4.1.

### 3.5 Physical verification, power and reliability

Documents: [07_verification/verification_summary.pdf](07_verification/verification_summary.pdf).

- [ ] DRC: TritonRoute 0, KLayout 0 markers. The deck has FEOL disabled, no density rules and no fill, so this is not sign-off DRC (K-04; question 7).
- [ ] LVS: KLayout, netlists match, but the reference CDL is written from the same database as the GDS. No independent Netgen LVS.
- [ ] Antenna: 0 violations, 20 diodes.
- [ ] Power 52.1092 mW and IR drop (VDD 0.4539 mV, VSS 0.6275 mV) both use default activity at TT. They are tool estimates, not measurements (K-06; question 11).
- [ ] Electromigration: no check against current-density limits (MISSING); a package re-run gives grid currents only (K-06).

### 3.6 Pinout and packaging

Documents: [08_pinout_packaging/pinout_packaging.pdf](08_pinout_packaging/pinout_packaging.pdf); [pinout.csv](08_pinout_packaging/pinout.csv).

- [ ] 217 pins = 215 signal bits of the 18 RTL ports + VDD + VSS, placed on the die edge by the ORFS pin placer.
- [ ] No pad ring, ESD, seal ring or package (K-05), and no electrical ratings (G-15). Check the external-connection list: clock source, reset, sensor inputs and supply.

### 3.7 Provenance

Documents: README revision table; [09_review_notes/review_notes.pdf](09_review_notes/review_notes.pdf) section 4.3.

- [ ] The OpenROAD version is "unknown", no PDK commit is logged, and linking the run to the ORFS image digest is an ASSUMPTION. The SDC with the 7.2 ns period was originally committed after the run started (K-09, D-52; question 12). Decide whether the run must be repeated from a pinned image and a clean commit.

## Step 4. Revision and consistency check (15 min)

- [ ] Verify the package files: run `sha256sum -c MANIFEST.sha256` in the package folder. Every line should end `OK`.
- [ ] Skim the discrepancy register (review_notes section 4). Most items are inconsistencies between files; some are marked fixed in the package, and the rest are for the design owner to resolve. Flag any you consider blocking.
- [ ] Skim the gaps table (review_notes section 5). It lists what a complete review needs that does not exist.

## Step 5. Reproduce selected results (optional)

From a repository checkout at the package commit (see [04_digital_design/README.md](04_digital_design/README.md) section 6.1 for setup). Times are the 2026-10-06 package re-runs (04 sections 6.3 and 6.4).

| What | Command | Expected | Time |
|---|---|---|---|
| Lint | `make lint` | exit 0, no `%Warning` lines | 0.12 s |
| Directed simulation | `make sim-directed BUILD=/tmp/r` | `TB_ORBIT_DEMO PASS` | 6.5 s |
| Formal | `make formal BUILD=/tmp/r` | line starting `[formal] all 12 tasks passed` | 47 s |
| Gate-level fault campaign, routed sep netlist | `make pd-sep-gls PDSEP_PUBLISH=` (needs `build/pd_sep/results/sky130hd/orbit_demo/sep/6_final.v` from a `make pd-sep` run, and Docker for the cell library) | `GLS PASS: 30000 cycles, 0 mismatches` | 2 min 18 s (the target's commands run by hand) |
| Multi-corner STA of the sep layout | [run_corners_sep.sh](07_verification/sta_corners_sep_2026-10-06/run_corners_sep.sh) (edit its `REPO=` and `OUT=` paths first; needs Docker, the `pd-sep` outputs and the SS/FF liberty files that `make pd-corners` downloads to `build/pd/platform/sky130hd/corners/`) | one `sta_<corner>.log` per corner, with the values in sta_corners_sep.txt | about 2 s per corner |

Use `BUILD=<dir>` and the `*_PUBLISH=` overrides so the tracked `reports/` folder is not rewritten (04 section 6.2).

## Step 6. Write feedback

Reference the package IDs so each comment can be traced. Questions are 1-14, known issues K-01..K-16, trade-offs T-01..T-07, discrepancies D-01..D-101 and gaps G-01..G-38, all in the review notes. Drawing items BD-1..BD-5 and SC-1..SC-4 are in 02_block_diagram and 03_schematics. Template:

| # | Ref (Q / K / T / D / G / file:section) | Finding or answer | Severity (blocking / major / minor / note) | Requested action |
|---|---|---|---|---|
| 1 | Q1 | | | |
| 2 | K-01 | | | |
| 3 | | | | |

Close with an overall outcome, for example: ready for the next step; ready with listed conditions; or not ready, with the blocking items. Say which step the outcome applies to, for example "continue design iteration" or "start pad-ring and sign-off DRC/LVS work". The package does not claim tapeout readiness.
