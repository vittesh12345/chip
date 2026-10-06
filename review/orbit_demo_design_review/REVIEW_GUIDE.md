# Reviewer guide: how to review orbit_demo

This guide takes a reviewer through the package in a fixed order, says what to check at each step, and ends with a feedback template. The package [README.md](README.md) has the exact revision, folder map and status legend; this guide does not repeat them.

**What is being reviewed.** `orbit_demo` is a 4-lane INT8 MAC digital demonstrator with duplicated storage and a mismatch fault-stop, plus a TMR thermal FSM. It is implemented as a core-only standard-cell block on SkyWater sky130hd. The reviewed layout is the ORFS run `sep` at 7.2 ns with copy-separation fences. It has not been fabricated.

**Out of scope.** The unbuilt 16-tile concept chip in the brief, the reference layouts (`base` at 7.0 ns, IHP SG13G2), and the presentation material in `site/`, `viz/` and `docs/research/`. The review notes list where the presentation material overstates the evidence (D-62 to D-84).

## What you need

| Purpose | Needed |
|---|---|
| Reading (steps 1-4) | A PDF viewer, or GitHub's Markdown view. Every document exists as `.md`, and the main ones also as `.pdf` |
| Inspecting the layout | KLayout (any recent version) to open [06_physical_design/layout_db/6_final.gds.gz](06_physical_design/layout_db/6_final.gds.gz). The sky130 layer-properties file is not in the package, so KLayout uses default colours. The pre-rendered views in [06_physical_design/klayout_views/](06_physical_design/klayout_views/) use the ORFS `sky130hd.lyp` |
| Re-running checks (step 5, optional) | A checkout of the repository at the package commit, the OSS CAD Suite, and Docker with the ORFS image for layout checks. See [04_digital_design/README.md](04_digital_design/README.md) section 6 |

## Time plan

| Step | Activity | Time |
|---|---|---|
| 1 | Orientation | 20 min |
| 2 | Known issues and the reviewer questions | 30 min |
| 3 | Area-by-area review (seven areas) | 1.5-3 h |
| 4 | Revision and consistency check | 15 min |
| 5 | Reproduce selected results (optional) | 15 min to 1 h |
| 6 | Write feedback | 20 min |

## Step 1. Orientation (20 min)

1. [README.md](README.md): read the revision table, the status legend and the verification status overview.
2. [01_overview/design_overview.pdf](01_overview/design_overview.pdf): read the scope split (built demonstrator vs concept-chip TARGETs), then the requirements table. Note that the demonstrator has **no** specified clock target, supply specification, power budget or PVT range (all MISSING). Every timing or power number in the package is therefore a result without a requirement to compare against.
3. [02_block_diagram/orbit_demo_top_level.pdf](02_block_diagram/orbit_demo_top_level.pdf): keep this open for the rest of the review. The detailed diagram is [orbit_demo_block_diagram.pdf](02_block_diagram/orbit_demo_block_diagram.pdf).

## Step 2. Known issues and questions (30 min)

Read [09_review_notes/review_notes.pdf](09_review_notes/review_notes.pdf) sections 1-3.

- **Section 1, known issues K-01 to K-16.** The five High items:
  - K-01: setup fails at ss_100C_1v60.
  - K-02: single points of failure.
  - K-03: undetected common-mode faults.
  - K-04: the DRC deck is BEOL-only.
  - K-05: no pad ring or package.

  For each, decide whether it blocks the next step, and record any you disagree with.
- **Section 2, trade-offs T-01 to T-07.** Check that each trade-off is justified by its cited evidence.
- **Section 3, questions 1-14.** These are the decisions the design owner is asking you to make. Answer them in your feedback (step 6). The area checklists below point to the questions that each area informs.

## Step 3. Area-by-area review

Work through the areas in order. Each checklist item names the document and, where relevant, the review-notes item it relates to.

### 3.1 Architecture and RTL

Documents: [04_digital_design/README.md](04_digital_design/README.md) sections 3-5; RTL in [04_digital_design/source/rtl/](04_digital_design/source/rtl/); [source/docs/SPEC.md](04_digital_design/source/docs/SPEC.md); schematics in [03_schematics/](03_schematics/).

- [ ] Compare the RTL with SPEC sections 3-6: the MAC equation and wrap-around, the `in_ready`/`out_valid` equations, the duplicate-and-compare and sticky `fault_q`, the TMR vote and feedback repair, and the throttle/stop/recover thresholds. One known wording difference exists: `phase` (K-16).
- [ ] Check the fault model against SPEC section 8 and K-02/K-03. What is shared between copies: the multiplier and `prod32`, the comparators and the mismatch OR-tree, the voter and the `nxt` cone, `phase`, `fault_q`, `out_valid_q`, clock, reset and inputs. Questions 3-6.
- [ ] Reset and clear: `rst_n` is synchronous with no on-chip synchronizer. `clear_fault` zeroes lane storage but not the thermal state. Question 8 covers the host re-send protocol.
- [ ] Clocking: single domain, no CDC, no gating.
- [ ] Schematics: [03_schematics/README.md](03_schematics/README.md) explains why transistor sizes and bias currents are N/A (standard cells only). The gate-level sheets come from the synthesized netlist, before placement; 03 lists the differences from the routed netlist.
- [ ] ECC: [rtl/ecc](04_digital_design/source/rtl/ecc/) is standalone and not in the layout (K-12). Decide whether it should be reviewed now.

### 3.2 Functional verification

Documents: [05_simulation/simulation_report.pdf](05_simulation/simulation_report.pdf); formal and fault sections of [07_verification/verification_summary.pdf](07_verification/verification_summary.pdf).

- [ ] Test inventory S1-S14: check that the stimulus, pass criterion and checked properties cover each SPEC requirement. Use the requirements table in 01 as the index.
- [ ] Formal: 12 tasks plus `datapath_pdr` pass, and the vacuity check catches 19/19. The code-3 branch is vacuous (K-10). Mutants m07, m20, m22 and m27 survive the full campaign. Question 10.
- [ ] Fault injection: the RTL SEU campaign and the gate-level campaign on the routed sep netlist (702 flips stopped, 234 repaired, 0 mismatches). Expected escapes: `out_valid_q` 200/200, `fault_q` false stops; `fault_q` 1->0 is not measured. `neg_product` shows silent data corruption (K-03).
- [ ] Every simulation is zero-delay. No SDF-annotated gate-level simulation exists (MISSING). Decide whether that is needed.
- [ ] Waveforms in [05_simulation/waveforms/](05_simulation/waveforms/) are plotted from real VCDs at a 10 ns functional clock. Spot-check scenario (c), the fault-stop, against SPEC section 5.

### 3.3 Timing and constraints

Documents: [07_verification/verification_summary.pdf](07_verification/verification_summary.pdf) timing sections; [sta_corners_sep_2026-10-06/sta_corners_sep.txt](07_verification/sta_corners_sep_2026-10-06/sta_corners_sep.txt); SDC [06_physical_design/layout_db/6_final.sdc](06_physical_design/layout_db/6_final.sdc).

- [ ] Constraints: one clock at 7.2 ns, input and output delays of 20 % of the period (1.44 ns, an ASSUMPTION), no load, drive, uncertainty or derate. Questions 1-2.
- [ ] TT: WNS 0.031 ns, hold 0.436 ns, fmax 139.49 MHz. The critical path is in2reg from `in_a`/`in_b` through the shared multiplier.
- [ ] SS_100C_1v60 (re-run for this package): WNS -6.131 ns, 516 endpoints, min period 13.33 ns, plus slew and cap violations. FF passes. Only these three liberty corners exist on disk, and the SPEF has one nominal RC corner.
- [ ] LEC: the two kepler-formal checks are equivalent. The "4_rsz" check compares the netlist before and after `repair_timing`, not synthesis against post-CTS (K-14). The compared netlists are in [additional_evidence/lec_netlists/](07_verification/additional_evidence/lec_netlists/).

### 3.4 Floorplan and layout

Documents: [06_physical_design/physical_design.pdf](06_physical_design/physical_design.pdf); full-resolution images in [klayout_views/](06_physical_design/klayout_views/) and [orfs_images/](06_physical_design/orfs_images/).

- [ ] Die 346.295 um square, utilization 0.5361. The PDN has met4/met5 straps, single VDD/VSS.
- [ ] Copy-separation fences (v03, v04, v05): copy A on the left edge, copy B on the right, three thermal fences. Same-bit pairs are at least 251.2 um apart and none of 262 touch. Non-member cells overlap the fences, including clock-tree buffers (K-13; question 13). Shared drivers across copies (D-93; question 6).
- [ ] Open the GDS in KLayout and check one area yourself, for example a thermal fence.

### 3.5 Physical verification, power and reliability

Documents: [07_verification/verification_summary.pdf](07_verification/verification_summary.pdf).

- [ ] DRC: TritonRoute 0, KLayout 0 markers. The deck has FEOL disabled, no density rules and no fill, so this is not sign-off DRC (K-04; question 7).
- [ ] LVS: KLayout, netlists match. No independent Netgen LVS.
- [ ] Antenna: 0 violations, 20 diodes.
- [ ] Power 52.1092 mW and IR drop (VDD 0.4539 mV, VSS 0.6275 mV) both use default activity at TT. They are tool estimates, not measurements (K-06; question 11).
- [ ] Electromigration: not run (MISSING).

### 3.6 Pinout and packaging

Documents: [08_pinout_packaging/pinout_packaging.pdf](08_pinout_packaging/pinout_packaging.pdf); [pinout.csv](08_pinout_packaging/pinout.csv).

- [ ] 217 pins = 215 signal bits of the 18 RTL ports + VDD + VSS, placed on the die edge by the ORFS pin placer.
- [ ] No pad ring, ESD, seal ring, package or electrical ratings (K-05). Check the external-connection list: clock source, reset, sensor inputs and supply.

### 3.7 Provenance

Documents: README revision table; [09_review_notes/review_notes.pdf](09_review_notes/review_notes.pdf) section 4.3.

- [ ] The OpenROAD version is "unknown", no PDK commit is logged, and linking the run to the ORFS image digest is an ASSUMPTION. The SDC with the 7.2 ns period was committed after the run started (K-09, D-52; question 12). Decide whether the run must be repeated from a pinned image and a clean commit.

## Step 4. Revision and consistency check (15 min)

- [ ] Verify the package files: run `sha256sum -c MANIFEST.sha256` in the package folder. Every line should end `OK`.
- [ ] Skim the discrepancy register (review_notes section 4). The items are inconsistencies between files that the design owner has to resolve. None changes the RTL or layout. Flag any you consider blocking.
- [ ] Skim the gaps table (review_notes section 5). It lists what a complete review needs that does not exist.

## Step 5. Reproduce selected results (optional)

From a repository checkout at the package commit (see [04_digital_design/README.md](04_digital_design/README.md) section 6.1 for setup):

| What | Command | Expected | Time |
|---|---|---|---|
| Lint | `make lint` | no warnings | < 1 s |
| Directed simulation | `make sim-directed BUILD=/tmp/r` | `TB_ORBIT_DEMO PASS` | 7 s |
| Formal | `make formal BUILD=/tmp/r` | `[formal] all 12 tasks passed` | 1 min |
| Gate-level fault campaign, routed sep netlist | `make pd-sep-gls PDSEP_PUBLISH=` (needs the `pd-sep` build outputs) | `GLS PASS: 30000 cycles, 0 mismatches` | 2.5 min |
| Multi-corner STA of the sep layout | [run_corners_sep.sh](07_verification/sta_corners_sep_2026-10-06/run_corners_sep.sh) (edit its `OUT=` path first; needs Docker and the build outputs) | table as in sta_corners_sep.txt | < 1 min |

Use `BUILD=<dir>` and the `*_PUBLISH=` overrides so the tracked `reports/` folder is not rewritten (04 section 6.2).

## Step 6. Write feedback

Reference the package IDs so each comment can be traced. Questions are 1-14, known issues K-01..K-16, trade-offs T-01..T-07, discrepancies D-01..D-101 and gaps G-01..G-38, all in the review notes. Template:

| # | Ref (Q / K / T / D / G / file:section) | Finding or answer | Severity (blocking / major / minor / note) | Requested action |
|---|---|---|---|---|
| 1 | Q1 | | | |
| 2 | K-01 | | | |
| 3 | | | | |

Close with an overall outcome, for example: ready for the next step; ready with listed conditions; or not ready, with the blocking items. Say which step the outcome applies to, for example "submit to a sky130 shuttle" or "continue design iteration". The package does not claim tapeout readiness.
