# 04_digital_design: RTL, testbenches and build files

Package section 04_digital_design of `orbit_demo_design_review`, written 2026-10-06. Links are relative to this file. Paths written as `reports/...`, `build/...`, `viz/`, `site/` or `docs/research/...` are repository paths (checkout `/home/user/chip`). Where the package holds a byte-identical copy, the text links the copy; parts of `reports/` and `build/` are copied into 03, 05, 06 and 07 (section 2 lists the `reports/` subsets). Unlinked repository paths are not in the package. Discrepancies: see discrepancy register (09_review_notes). Section 1 is the package revision table, included verbatim; sections 2-6 follow.

Status labels: **VERIFIED** = a tool log or report shows it. **REPRODUCED 2026-10-06** = re-run for this package. **TARGET** = design goal, not measured. **ASSUMPTION**. **CLAIM (unverified)** = stated in a document, no log found. **MISSING**. **N/A** = not applicable (reason given).

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

Notes on the revision table (checked 2026-10-06):

- The table refers to `MANIFEST.sha256` at the package root; it is there ([../MANIFEST.sha256](../MANIFEST.sha256), generated last on 2026-10-06; register D-53). Full sha256 of the copies in `source/` (sha256sum, 2026-10-06; status REPRODUCED 2026-10-06):

  | File | sha256 |
  |---|---|
  | [rtl/orbit_demo.v](source/rtl/orbit_demo.v) | a3fffb229df3e166694d9259cee45411537118aa2673f84bb26b0f4108f3183a |
  | [rtl/orbit_mac_lane.v](source/rtl/orbit_mac_lane.v) | efef3d33e617683a30540933549e61c2a1054762168e8be8a95bd652793571bc |
  | [rtl/orbit_thermal_tmr.v](source/rtl/orbit_thermal_tmr.v) | bba77a5a9db0da79917d7cc946c8c80a5d92e1087b8829ea41809adbc72b87d1 |
  | [rtl/orbit_keep_reg.v](source/rtl/orbit_keep_reg.v) | ea05bdc17462933e80fa7e8becc039d68c870f2bf89353e9ae165fdb2c0c7e05 |
  | [docs/SPEC.md](source/docs/SPEC.md) | aef5d9fb92d6e69bfa58735e44a93beea0279aebe354eb6319a35d513aaed828 |
  | [docs/orbit-ai-design-brief.pdf](source/docs/orbit-ai-design-brief.pdf) | 9d5f33d344249985d82660f6ad6e4358444c143d210eb9c8254c2747c36d8069 |

- The checkout HEAD has moved past 0495cfa while this package was written; 0495cfa is an ancestor. As stated in the table's "Package assembled" note, `git diff --name-only 0495cfa HEAD` lists only `review/` paths (last checked 2026-10-06 at HEAD de1890d), so every file in `source/` is the same at 0495cfa and at HEAD (section 2). See discrepancy register D-54.
- [pd/sky130hd_sep/constraint.sdc](source/pd/sky130hd_sep/constraint.sdc) (`set clk_period 7.2`, line 19) is byte-identical to the SDC that the reviewed run read, `build/pd_sep/sdc/sky130hd/sep.sdc` (cmp, 2026-10-06). The `ed553f8` version of this file has `set clk_period 7` (table row "Layout configuration"; register D-52).

## 2. Contents of `source/`

`source/` holds byte-identical copies of `rtl/`, `tb/`, `formal/`, `fault/`, `synth/`, `model/`, `mk/`, `pd/`, the `Makefile`, `requirements-tools.txt`, 8 of the 15 files in `scripts/` and 2 of the 5 files in `docs/`, at the package revision.

Copy check, REPRODUCED 2026-10-06. Each of the 86 files under `source/` was compared with `cmp` against (a) `/home/user/chip/<path>` in the working tree, (b) `git show 0495cfa:<path>` and (c) `git show HEAD:<path>` (HEAD = 47c7af9; repeated at 54745f7, 0477235 and de1890d). Result: 86 of 86 identical in all comparisons, none missing. All 86 are git-tracked. Within the copied directories (`rtl tb formal fault synth model mk pd`), no tracked file was left out.

| Path in `source/` | Files | Contents |
|---|---|---|
| [rtl/](source/rtl/) | 4 + 4 in `rtl/ecc/` | orbit_demo RTL (section 3); standalone ECC block (section 4) |
| [tb/](source/tb/) | 9 | directed bench, cocotb random test and Python reference model, sim mutant and report scripts, ECC benches (section 5) |
| [formal/](source/formal/) | 6 + 7 in `formal/ecc/` | SymbiYosys template [orbit_demo.sby](source/formal/orbit_demo.sby) and harness [orbit_demo_fv.sv](source/formal/orbit_demo_fv.sv); runners `gen_sby.sh`, `run_task.sh`, `summarize.py`, `vacuity.sh`; ECC proofs |
| [fault/](source/fault/) | 6 | SEU injection: formal harness `fi_harness.sv`, copy generator `gen_fault_copies.py`, runner `run_formal.py`; Icarus campaign `tb_seu_campaign.v` and `campaign_report.py`; `write_summary.py` |
| [synth/](source/synth/) | 8 | Yosys generic synthesis [synth_generic.ys](source/synth/synth_generic.ys); netlist-vs-RTL equivalence (`equiv_cut.ys`, `equiv.sby`, `run_equiv.py`); storage-audit self-test; keep_hierarchy negative control (`negative_control.py`, `make_variant.py`); `synth_report.py` |
| [model/](source/model/) | 2 | `concept_budget.py` (arithmetic of the concept brief) and its unit tests |
| [mk/](source/mk/) | 10 | per-area make fragments: ecc, fault, formal, model, mutation, pd, pdsep, sim, synth, viz |
| [pd/](source/pd/) | 18 | ORFS design configs: [sky130hd_sep/](source/pd/sky130hd_sep/) (reviewed layout: `config.mk`, `constraint.sdc`, `regions.tcl`), [sky130hd/](source/pd/sky130hd/) (baseline `base`), [ihp-sg13g2/](source/pd/ihp-sg13g2/); report and check scripts (`collect_pd.py`, `audit_storage.py`, `copy_separation.py`, `render_layout.py`, `sweep_summary.py`, `corners_summary.py`, `sta_corners.tcl`, `write_netlist.tcl`); post-route GLS harness [pd/gls/](source/pd/gls/) |
| [scripts/](source/scripts/) | 8 | see table below |
| [docs/](source/docs/) | 2 | [SPEC.md](source/docs/SPEC.md) (behavioural contract), [orbit-ai-design-brief.pdf](source/docs/orbit-ai-design-brief.pdf) (concept brief v0.1) |
| [Makefile](source/Makefile), [requirements-tools.txt](source/requirements-tools.txt) | 2 | top-level build (includes `mk/*.mk`), tool pins |

`scripts/` in the package versus the repo:

| Included in `source/scripts/` | Used by |
|---|---|
| `run_pd.sh` | ORFS runner in Docker: `pd*`, `pd-corners`, `pd-negctl`, `pd-sweep` |
| `run_pd_sep.sh` | ORFS runner for the reviewed `sep` layout: `pd-sep*` |
| `pdsep_separation.py`, `pdsep_render.py`, `pdsep_summary.py`, `pdsep_mechanism_test.tcl` | `pd-sep-report`, `pd-sep-mechanism` |
| `storage_audit.py` | `synth-audit`, `synth-audit-selftest`, `synth-nokeep`, `synth-yowasp` |
| `setup_tools.sh` | tool installation (section 6.1) |

| Not copied (repo only) | Needed by |
|---|---|
| `scripts/mutation_test.py` | `mutation`, `mutation-gaps`, `mutation-list`, `mutation-report` |
| `scripts/viz_gds_to_3d.py`, `viz_parts.py`, `viz_shots.py` | `viz`, `viz-shots`, `viz-serve` |
| `scripts/space_build.py`, `space_shots.py`, `story_build.py` | web pages under `site/` (no make target) |
| `build/` (gitignored) | every target writes here; the reviewed layout outputs are `build/pd_sep/results/sky130hd/orbit_demo/sep/` (layout database copied to [../06_physical_design/layout_db/](../06_physical_design/layout_db/)) |
| `reports/` (243 tracked files) | published evidence. Not part of `source/`; byte-identical copies of these subsets are elsewhere in the package: `reports/{ecc,fault,formal,mutation,synth}/` as [../07_verification/](../07_verification/)`{ecc,fault,formal,mutation,synth}/`; `reports/pdsep/` except its GDS as [../07_verification/published_reports/](../07_verification/published_reports/); `reports/pd/sky130hd/{results.md,sta_corners.txt,negctl_*_audit.txt}` in [../07_verification/baseline_reference/](../07_verification/baseline_reference/); all 9 files of `reports/sim/` in [../05_simulation/published_logs/](../05_simulation/published_logs/) (cmp/sha256, 2026-10-06). `reports/model/`, `reports/space/`, `reports/viz/` and most of `reports/pd/` have no copy. Read by `pd-sep-report` (`PDSEP_BASE_CHECKS ?= reports/pd/sky130hd/checks.json`, [mk/pdsep.mk](source/mk/pdsep.mk) line 39) and `mutation` (`reports/mutation/tb_mutation_gaps.v`, [mk/mutation.mk](source/mk/mutation.mk) line 34); written by the publishing targets (section 6.2) |
| `viz/`, `site/`, `docs/research/` (3 notes), `.gitignore` | 3D viewer and web pages, research notes; not design inputs |

The make targets must therefore be run from a full repository checkout at the package commit, not from `source/`. Check in a scratch copy of `source/` (REPRODUCED 2026-10-06): `make lint` passes (0.11 s), but `make mutation-list` stops with `python3: can't open file '.../scripts/mutation_test.py'` (mk/mutation.mk:66). Targets that read the reviewed layout (`pd-sep-gls`, `pd-sep-report`, `sim-gls` on the sep netlist) also need `build/pd_sep/`. That directory is not in git, so a fresh clone must first run `make pd-sep`. That is a new ORFS run; whether it reproduces the reviewed database byte for byte was not checked (MISSING). The reviewed netlist itself is [../06_physical_design/layout_db/6_final.v.gz](../06_physical_design/layout_db/6_final.v.gz) (uncompressed md5 ef90cdacf4741ef8a1a9282bbc7f0584, equal to `build/pd_sep/results/sky130hd/orbit_demo/sep/6_final.v`).

## 3. RTL of `orbit_demo`

Language and conventions (from [SPEC.md](source/docs/SPEC.md) lines 21-22 and the RTL): Verilog-2005, `` `default_nettype none ``, one clock `clk`, synchronous active-low reset `rst_n`. `make lint` (Verilator 5.053 `--lint-only -Wall --top-module orbit_demo`) exits 0 with no warnings: REPRODUCED 2026-10-06 ([make_lint.log](../05_simulation/rerun_logs_2026-10-06/make_lint.log)).

| File | Module | Lines | Role |
|---|---|---|---|
| [rtl/orbit_demo.v](source/rtl/orbit_demo.v) | `orbit_demo #(LANES=4, T_THROTTLE=8'sd80, T_STOP=8'sd95, T_RECOVER=8'sd70)` | 129 | Top level. valid/ready input stream, one-result output buffer (`out_valid_q`), sticky mismatch fault latch (`fault_q`), `in_ready`/`out_valid` gating, `g_lane[0..3]` lanes and `u_thermal` |
| [rtl/orbit_mac_lane.v](source/rtl/orbit_mac_lane.v) | `orbit_mac_lane` | 64 | One signed INT8 x INT8 multiply, INT32 accumulate (wraps mod 2^32) lane. Duplicated accumulator (`u_acc_a`/`u_acc_b`) and result (`u_res_a`/`u_res_b`) copies, one shared multiplier, copy compare -> `mismatch`; `result = res_a` (lines 39-60) |
| [rtl/orbit_thermal_tmr.v](source/rtl/orbit_thermal_tmr.v) | `orbit_thermal_tmr #(T_THROTTLE, T_STOP, T_RECOVER)` | 86 | Thermal FSM NORMAL/THROTTLE/STOP. Three 2-bit state copies `u_copy0..2` (reset STOP), majority vote (line 40), one next-state cone written back to all copies (repair), `phase` bit for alternate-cycle admission in THROTTLE, `repair` flag (lines 58-82) |
| [rtl/orbit_keep_reg.v](source/rtl/orbit_keep_reg.v) | `orbit_keep_reg #(W=32, RESET_VAL=0)` with `(* keep_hierarchy *)` | 35 | One copy of a redundantly stored register (enable, sync reset). Every redundant copy is its own instance, so synthesis cannot merge copies with identical D inputs |

Instance hierarchy and storage (block diagram: [../02_block_diagram/orbit_demo_block_diagram.svg](../02_block_diagram/orbit_demo_block_diagram.svg)):

| Instance path | Module | Flip-flop bits | Protection |
|---|---|---|---|
| `g_lane[i].u_lane`, i = 0..3 | `orbit_mac_lane` | — | — |
| `g_lane[i].u_lane.u_acc_a`, `.u_acc_b` | `orbit_keep_reg` W=32 | 4 x 2 x 32 = 256 | duplicate + compare, sticky fault-stop |
| `g_lane[i].u_lane.u_res_a`, `.u_res_b` | `orbit_keep_reg` W=32 | 4 x 2 x 32 = 256 | duplicate + compare; `out_data` driven by copy A |
| `u_thermal.u_copy0`, `.u_copy1`, `.u_copy2` | `orbit_keep_reg` W=2, RESET_VAL=S_STOP | 3 x 2 = 6 | TMR vote + feedback repair |
| `u_thermal.phase`, `fault_q`, `out_valid_q` | plain `reg` | 3 | unprotected |
| Total | 19 `orbit_keep_reg` instances | 521 | |

Status of the table: VERIFIED on the reviewed sep run. ORFS synthesis keeps 19 `orbit_keep_reg` instances, 3 of the W=2 variant and 16 of the W=32 variant ([synth_stat.txt](../07_verification/orfs_reports/synth_stat.txt) lines 153-154). The storage audit [storage_audit.txt](../07_verification/published_reports/storage_audit.txt) (= `reports/pdsep/storage_audit.txt`; conditions: `pd/audit_storage.py` on `build/pd_sep/results/sky130hd/orbit_demo/sep/6_final.v`, liberty tt_025C_1v80, run 2026-09-29 22:30 UTC) reports 521 `sky130_fd_sc_hd__dfxtp_1`, 9 groups OK, 3 singles, `RESULT: PASS (18/18 checks passed)`. The [pd/audit_storage.py](source/pd/audit_storage.py) in `source/` was changed after that report (commit b1da230, 23:47 UTC) and adds a clock-tree check. Re-run on the same netlist it gives `RESULT: PASS (19/19 checks passed)` with otherwise identical lines ([storage_audit_current_script.txt](../07_verification/rerun_2026-10-06/pd_sep/storage_audit_current_script.txt)): REPRODUCED 2026-10-06. The published report therefore comes from an older audit script than the one in the package; see discrepancy register (09_review_notes).

The reviewed layout was synthesized from exactly these four files. The ORFS log [1_1_yosys_canonicalize.log](../07_verification/orfs_logs/1_1_yosys_canonicalize.log), lines 7-11, reads `rtl/orbit_keep_reg.v`, `orbit_mac_lane.v`, `orbit_thermal_tmr.v`, `orbit_demo.v` and the platform file `cells_clkgate_hd.v`: VERIFIED. Known wording differences between SPEC and RTL (`phase` cleared at the next edge rather than "forced"; the undocumented combinational path `clear_fault` -> `in_ready`; a presented result withdrawn on `clear_fault`/`rst_n`): see discrepancy register (09_review_notes).

## 4. ECC block `rtl/ecc/` (standalone)

`rtl/ecc/` is a standalone (72,64) Hsiao SECDED codec and scrubbed, bit-interleaved storage bank. `orbit_demo` does not instantiate it, and it is not in the reviewed layout.

| Check | Result | Source | Status |
|---|---|---|---|
| Instantiation in orbit_demo | No ECC module is instantiated. The only ECC text in the four RTL files is the comment "Not included: automatic replay, ECC SRAM, ..." | [rtl/orbit_demo.v](source/rtl/orbit_demo.v) line 9 (grep of the 4 files) | REPRODUCED 2026-10-06 |
| Build file list | `RTL` = the 4 orbit_demo files only | [Makefile](source/Makefile) lines 15-17 | REPRODUCED 2026-10-06 |
| Synthesis input of the reviewed run | only the 4 orbit_demo files + `cells_clkgate_hd.v` | [1_1_yosys_canonicalize.log](../07_verification/orfs_logs/1_1_yosys_canonicalize.log) lines 7-11 | VERIFIED |
| Layout content | 0 case-insensitive matches of `secded` or `ecc_bank` in 6_final.v, 6_final.def, 1_2_yosys.v and the GDS strings | [6_final.v.gz](../06_physical_design/layout_db/6_final.v.gz), [6_final.gds.gz](../06_physical_design/layout_db/6_final.gds.gz), [6_final.def.gz](../06_physical_design/layout_db/6_final.def.gz), [1_2_yosys.v.gz](../03_schematics/netlists/1_2_yosys.v.gz) (copies of the `build/pd_sep/results/sky130hd/orbit_demo/sep/` files) | REPRODUCED 2026-10-06 |
| Block's own statement | "It is **not** part of the built demonstrator: `orbit_demo` does not instantiate anything here" | [rtl/ecc/README.md](source/rtl/ecc/README.md) lines 3-8; [mk/ecc.mk](source/mk/ecc.mk) line 3 | VERIFIED by the rows above |

| File | Module(s) | Role |
|---|---|---|
| [rtl/ecc/orbit_secded72.v](source/rtl/ecc/orbit_secded72.v) | `orbit_secded72_enc` (line 29), `orbit_secded72_dec` (line 53) | Hsiao (72,64) SECDED encoder and decoder, purely combinational. The decoder derives its syndrome from an encoder instance |
| [rtl/ecc/orbit_ecc_bank.v](source/rtl/ecc/orbit_ecc_bank.v) | `orbit_ecc_bank #(DEPTH=16, INTERLEAVE=2, CNT_W=16)` (line 41) | flip-flop array standing in for an SRAM. Bit-interleaved codewords, latency-1 read port, write port, background scrubber, saturating CE/UE counters and last-error record |
| [rtl/ecc/gen_hsiao72.py](source/rtl/ecc/gen_hsiao72.py) | — | generates the H-matrix block of `orbit_secded72.v`; `--check` verifies it |
| [rtl/ecc/README.md](source/rtl/ecc/README.md) | — | interface, protocol and verification contract of the block (SPEC.md does not cover `rtl/ecc/`) |

ECC verification status (detail belongs to 07_verification; summarised here because the block lives in `source/`):

| Result | Conditions | Source | Status |
|---|---|---|---|
| 27 of 27 checks `OK`: lint; H matrix; codec simulation; bank simulation seeds 1, 2; 7 simulation mutants killed; codec proof and bank proofs `clean`, `sec`, `ded`, covers, `e2e_clean`, `e2e_upset` PASS; 4 negative controls FAIL as expected; generic synthesis of the 3 tops | Yosys 0.69+154, SBY v0.69 (smtbmc bitwuzla/yices), Icarus 14.0 devel, Verilator 5.053. DEPTH 16, INTERLEAVE 2; bank proofs at CNT_W 3 | [../07_verification/ecc/results.txt](../07_verification/ecc/results.txt) (= `reports/ecc/results.txt`); per-check logs in [../07_verification/ecc/logs/](../07_verification/ecc/logs/) | VERIFIED |
| `make ecc` re-run: `ECC: PASS`, exit 0; summary identical to [results.txt](../07_verification/ecc/results.txt) apart from run times | scratch `BUILD`, 4 CPUs, 20 min 41 s wall while other jobs ran | [make_ecc.log](../07_verification/rerun_2026-10-06/ecc/make_ecc.log), [summary.txt](../07_verification/rerun_2026-10-06/ecc/summary.txt) | REPRODUCED 2026-10-06 |
| Generic synthesis: `orbit_secded72_enc` 154 cells, 0 FF, depth 6; `orbit_secded72_dec` 431 cells, 0 FF, depth 18; `orbit_ecc_bank` 10690 cells, 2414 FF (expected 2414), depth 48 | Yosys generic cells, no liberty, default parameters; depth = `ltp -noff` (topological) | [../07_verification/ecc/results.txt](../07_verification/ecc/results.txt) lines 25-27; [synth_stat.txt](../07_verification/ecc/synth_stat.txt) | VERIFIED |
| End-to-end checks with the real decoder are bounded BMC only: `e2e_clean` 5 steps, `e2e_upset` 4 steps, at DEPTH 2 | smtbmc bitwuzla | [rtl/ecc/README.md](source/rtl/ecc/README.md) section 3; [../07_verification/ecc/results.txt](../07_verification/ecc/results.txt) lines 5-6 | VERIFIED (bounded) |
| Unbounded end-to-end correctness (codec contract + bank proof with abstracted decoder) | written composition argument, not machine-checked | [rtl/ecc/README.md](source/rtl/ecc/README.md) section 3 | CLAIM (unverified) |
| Timing, sky130hd area, power, DRC/LVS of the ECC block | never mapped to a PDK, no SDC | — | N/A for the reviewed layout (the block is not in it); MISSING if it is to be integrated |
| 32 MiB SRAM with SECDED 64+8 and scrub | concept chip, not built | [brief](source/docs/orbit-ai-design-brief.pdf) p.1-2 | TARGET |

## 5. Testbenches and harnesses

All simulations below are zero-delay functional runs; the testbench clock period (10 ns where a `` `timescale `` is set) has no timing meaning. No simulation has a process, voltage or temperature corner (N/A: no SDF or corner-annotated simulation exists; `temp_c` is a digital input, not a die temperature).

| File | Top | DUT and method | Pass line | Make target |
|---|---|---|---|---|
| [tb/tb_orbit_demo.v](source/tb/tb_orbit_demo.v) | `tb_orbit_demo` | `orbit_demo` through its ports only (so the same bench runs on netlists). Cycle-accurate reference model from SPEC 3, 4, 6, transaction scoreboard, 14 directed scenarios (`reset_stop` ... `reset_midrun`), xorshift32 stimulus, `+seed`. Fault-free: `fault` and `therm_repair` are expected 0 throughout | `TB_ORBIT_DEMO PASS` | `sim-directed`, `sim-verilator`, `sim-gls`, `synth-gls` |
| [tb/cocotb/orbit_ref.py](source/tb/cocotb/orbit_ref.py) | `OrbitRef` | Python golden model written from SPEC, independent of the RTL. Running the file runs its self-test | `orbit_ref self-test PASS (38 checks)` | `sim-model` |
| [tb/cocotb/test_orbit_random.py](source/tb/cocotb/test_orbit_random.py) | `random_workload`, `wrap_soak` | cocotb constrained-random test against `OrbitRef`, compared every cycle; functional coverage must be non-zero; `wrap_soak` forces INT32 wraparound | via the runner | `sim-random`, `sim-random-verilator` |
| [tb/cocotb/run_random.py](source/tb/cocotb/run_random.py) | runner | builds once, runs each seed, writes coverage JSON and summary; needs `tabbypy3` (cocotb) | `SIM_RANDOM PASS: ...` | same |
| [tb/sim_mutants.py](source/tb/sim_mutants.py) | — | negative control: 26 SPEC-violating RTL copies; each must be killed by the directed bench and by the random bench | `SIM_MUTANTS PASS: every mutant killed by both benches` | `sim-mutants` |
| [tb/sim_report.py](source/tb/sim_report.py) | — | writes `reports/sim/summary.md` from the logs | — | `sim-report` |
| [tb/ecc/tb_orbit_secded72.v](source/tb/ecc/tb_orbit_secded72.v) | `tb_orbit_secded72` | ECC codec: every single (72) and double (2556) error position over random words, against its own H matrix built from the construction rule | `TB_ORBIT_SECDED72 PASS` | `ecc-sim-codec` |
| [tb/ecc/tb_orbit_ecc_bank.v](source/tb/ecc/tb_orbit_ecc_bank.v) | `tb_orbit_ecc_bank` | ECC bank: random traffic and single, adjacent 2-bit and double upsets against an independent model; second DUT at CNT_W 3 | `TB_ORBIT_ECC_BANK PASS` | `ecc-sim-bank`, `ecc-sim-quick` |
| [tb/ecc/ecc_mutants.py](source/tb/ecc/ecc_mutants.py) | — | 7 broken ECC copies (exact text substitutions with checked counts) | per-mutant `OK simneg_...` | `ecc-sim-mutants`, `ecc-formal-neg` |
| [pd/gls/tb_gls.v](source/pd/gls/tb_gls.v) | `tb_gls` | RTL `orbit_demo` vs routed netlist `orbit_demo_gl` in lockstep; one redundant bit flipped every 32 cycles (518 bits), duplicated-copy flips must stop the design, thermal-copy flips must be repaired | `GLS PASS: <n> cycles, 0 mismatches` | `pd-gls`, `pd-sep-gls`, `pd-gls-mutant` |
| [fault/tb_seu_campaign.v](source/fault/tb_seu_campaign.v) | `tb_seu_campaign` (+ `seu_host`) | Icarus SEU campaign: `u_dut` (upset) beside `u_gold`, one flip per trial over all 521 stored bits; outcomes classified and checked by `campaign_report.py` | `SEU_CAMPAIGN ...` line, then report checks | `fault-campaign`, `fault-quick`, `fault-negctl` |
| [fault/fi_harness.sv](source/fault/fi_harness.sv) | `fi_harness` | formal SEU harness: production `orbit_demo` vs generated `orbit_demo_fi` copy with one injectable element | sby status per task | `fault-formal`, `fault-quick` |
| [formal/orbit_demo_fv.sv](source/formal/orbit_demo_fv.sv) | `orbit_demo_fv` | formal harness with a SPEC reference model, all inputs free, properties P1-P8 and covers | `[formal] all <n> tasks passed` | `formal`, `formal-quick`, `formal-extra`, `formal-<task>`, `formal-vacuity` |
| [formal/ecc/](source/formal/ecc/) `orbit_secded72_fv.sv`, `orbit_ecc_bank_fv.sv`, `orbit_ecc_bank_e2e_fv.sv`, `orbit_secded72_dec_abs.v` | — | ECC codec proof, bank proofs with the decoder abstracted to the proven contract, bounded end-to-end BMC | `OK formal_...` | `ecc-formal*` |

Written for this package and not in the repo: [../05_simulation/waveforms/tb_orbit_wave.v](../05_simulation/waveforms/tb_orbit_wave.v). It has 5 waveform scenarios on the RTL, including upsets by hierarchical assignment; see [../05_simulation/waveforms/README.txt](../05_simulation/waveforms/README.txt).

## 6. Running the flows

### 6.1 Tool setup

| Tool | Pin in [requirements-tools.txt](source/requirements-tools.txt) | Found in this environment (2026-10-06) | Used by |
|---|---|---|---|
| OSS CAD Suite | `oss-cad-suite==2026-09-28`, extracted to `/opt/eda/oss-cad-suite`: yosys 0.69+154 (git 30d62572e), iverilog 14.0 (devel) s20260301-500-g2e81fcccb, verilator 5.053 devel rev v5.052-233-gf5f9ddef9; sby, yices, bitwuzla, abc, eqy bundled (lines 4-10) | `/opt/eda/oss-cad-suite`: Yosys 0.69+154 (git sha1 30d62572e-dirty), Icarus Verilog 14.0 (devel) (s20260301-500-g2e81fcccb-dirty), Verilator 5.053 devel rev v5.052-233-gf5f9ddef9 (mod), SBY v0.69, Yices 2.7.0, bitwuzla 0.9.1, cocotb 2.1.0.dev0+41564633 under `tabbypy3` (Python 3.11.6) | lint, sim, formal, fault, synth, ecc, GLS |
| ORFS Docker image | `openroad/orfs@sha256:2e5bf6fe865e102ca2313aba1d849da50f5973bc91c4212a2f68e7d905a39c8f` (line 13; comment: Yosys 0.68, KLayout 0.30.12) | same digest, tagged `openroad/orfs:latest`, created 2026-09-29T02:00:37Z. Its Yosys prints `0.68+post`, OpenROAD prints `unknown` | `pd*`, `pd-sep*`, `pd-corners`, `viz-platform` (needs a running Docker daemon) |
| Python | `python==3.11` (line 16) | `/usr/local/bin/python3` 3.11.15 | all `.py` scripts except the cocotb runner |
| YoWASP Yosys (optional) | `yowasp-yosys==0.69.0.0.post1233` (line 19) | not installed globally; `synth-yowasp` installs it into a venv | `synth-yowasp` (network) |

Status of the "found" column: REPRODUCED 2026-10-06 (`yosys -V`, `iverilog -V`, `verilator --version`, `sby --version`, `yices --version`, `bitwuzla --version`, `tabbypy3 -c 'import cocotb'`, `docker image inspect`).

Other run-time downloads: `pd-sep-report` creates a venv with `klayout==0.30.12 pillow` from PyPI ([mk/pdsep.mk](source/mk/pdsep.mk) line 83). `pd-corners` downloads the ss_100C_1v60 and ff_n40C_1v95 liberty files from the efabless GitHub repository if they are not cached in `build/pd/platform/sky130hd/corners/`. `viz` uses npm.

Setup, from [scripts/setup_tools.sh](source/scripts/setup_tools.sh). It downloads the OSS CAD Suite release to `$EDA_HOME` (default `/opt/eda`), pulls the pinned ORFS image and tags it `openroad/orfs:latest`, which `PD_IMAGE`/`PDSEP_IMAGE` use by default ([mk/pd.mk](source/mk/pd.mk) line 38, [mk/pdsep.mk](source/mk/pdsep.mk) line 25). The [Makefile](source/Makefile), lines 12-13, prepends `$(OSS_CAD)/bin` (default `/opt/eda/oss-cad-suite`) to `PATH`. `setup_tools.sh` was not run for this package, because the tools were already installed.

```sh
git clone https://github.com/vittesh12345/chip && cd chip   # remote recorded as origin in the checkout (access not checked)
git checkout 0495cfa          # package commit (on branch claude/hopeful-rubin-0yf8io)
EDA_HOME=/opt/eda scripts/setup_tools.sh
make help                     # lists lint, test, clean (Makefile lines 25-29)
```

### 6.2 Conventions and side effects

- `BUILD=<dir>` sends all outputs to `<dir>` instead of `build/`. Use it for review runs: `build/` holds the reviewed layout (`build/pd_sep/`), and `make clean` deletes `build/`. Default `make sim` overwrites `build/sim/`; the default `build/sim/` already holds the 2026-10-06 re-run outputs.
- `RTL_DIR=<copy>` runs any target on a modified RTL copy. Outputs are then never published.
- With the default `RTL_DIR=rtl`, these targets copy results into the tracked `reports/`: `fault` (reports/fault), `model` (reports/model, so `make test` changes reports/model as well), `pd-report`, `pd-gls`, `pd-gls-mutant`, `pd-negctl`, `pd-sweep`, `pd-corners` (reports/pd), `pd-sep-report`, `pd-sep-gls`, `pd-sep-mechanism` (reports/pdsep), `mutation*` (reports/mutation). `viz` always writes `viz/` and `reports/viz/`. The `*-report` targets (`sim-report`, `synth-report`, `formal-report`, `ecc-report`) exist to rewrite reports/. To leave reports/ unchanged, add `FAULT_PUBLISH= MODEL_PUBLISH= PD_PUBLISH= PDSEP_PUBLISH= MUTATION_PUBLISH=` on the command line. Checked for `model`: `make model MODEL_PUBLISH= BUILD=<dir>` leaves reports/ untouched (REPRODUCED 2026-10-06).

### 6.3 Fast targets (no Docker)

All run from the repo root. Wall times are from 2026-10-06 re-runs on 4 CPUs, with `SIM_JOBS=2`/`SYNTH_JOBS=2` defaults, `+seed=1` and default plusargs unless noted. "Review log" = log kept in the review work area; the four review logs below were copied into [../05_simulation/rerun_logs_2026-10-06/review_runs/](../05_simulation/rerun_logs_2026-10-06/review_runs/) on 2026-10-06, and all other evidence links point to package files.

| Command | Expected final line | Wall time, conditions | Evidence | Status |
|---|---|---|---|---|
| `make lint` | Verilator report, exit 0, no `%Warning` | 0.12 s | [make_lint.log](../05_simulation/rerun_logs_2026-10-06/make_lint.log) | REPRODUCED 2026-10-06 |
| `make sim-model` | `orbit_ref self-test PASS (38 checks)` | 0.05 s | [make_sim-model.log](../05_simulation/rerun_logs_2026-10-06/make_sim-model.log) | REPRODUCED 2026-10-06 |
| `make sim-directed` | `TB_ORBIT_DEMO PASS` (14 scenarios, 133601 cycles, errors 0) | 6.5 s; Icarus `-g2005 -Wall` | [make_sim-directed.log](../05_simulation/rerun_logs_2026-10-06/make_sim-directed.log), [directed_icarus.log](../05_simulation/rerun_logs_2026-10-06/directed_icarus.log) (identical to [published](../05_simulation/published_logs/directed_icarus.log)) | REPRODUCED 2026-10-06 |
| `make sim-verilator` | `sim-verilator: summary identical to Icarus` | 8.8 s with the existing Verilator build; 28.5 s from an empty `BUILD` | [make_sim-verilator.log](../05_simulation/rerun_logs_2026-10-06/make_sim-verilator.log), [make_sim-verilator_cleanbuild.log](../05_simulation/rerun_logs_2026-10-06/make_sim-verilator_cleanbuild.log) | REPRODUCED 2026-10-06 |
| `make sim-random` | `SIM_RANDOM PASS: 6 runs, 249226 cycles, 7544 results checked, 0 mismatches` | 42.4 s; seeds 1-5 x 20000 cycles + wrap_soak seed 1 | [make_sim-random.log](../05_simulation/rerun_logs_2026-10-06/make_sim-random.log) | REPRODUCED 2026-10-06 |
| `make sim-random-verilator` | `SIM_RANDOM PASS: 2 runs, 40000 cycles, 1844 results checked, 0 mismatches` | 46.2 s, including the prerequisite `sim-random`; cocotb Verilator build of 2026-09-30 reused, not rebuilt | [make_sim-random-verilator.log](../05_simulation/rerun_logs_2026-10-06/make_sim-random-verilator.log) | REPRODUCED 2026-10-06 |
| `make sim-gls` | `sim-gls: summary identical to the RTL run` | 46.6 s; Yosys generic netlist (4899 cells) | [make_sim-gls_yosys.log](../05_simulation/rerun_logs_2026-10-06/make_sim-gls_yosys.log) | REPRODUCED 2026-10-06 |
| `make sim` | `SIM PASS: model self-test, directed (Icarus + Verilator), cocotb random (Icarus + Verilator), gate-level (yosys)` | 2 min 19 s (mk/sim.mk:7 says "about 2 minutes") | review log `sim/make_sim.log` = [make_sim.log](../05_simulation/rerun_logs_2026-10-06/review_runs/make_sim.log) | REPRODUCED 2026-10-06 |
| `make sim-mutants` | `directed bench killed 26/26, random bench killed 26/26`, then `SIM_MUTANTS PASS: every mutant killed by both benches` | 28 s; `SIM_MUT_CYCLES=20000` | review log `sim/make_mutants.log` = [make_mutants.log](../05_simulation/rerun_logs_2026-10-06/review_runs/make_mutants.log) | REPRODUCED 2026-10-06 |
| `make formal-quick` | `[formal] all 8 tasks passed` | about 17 s (sum of per-task times; no wall-clock line) | review log `spec_rtl/formal_quick.log` = [formal_quick.log](../05_simulation/rerun_logs_2026-10-06/review_runs/formal_quick.log) | REPRODUCED 2026-10-06 |
| `make formal` | `[formal] all 12 tasks passed` | 46.6 s; SBY v0.69, yices/bitwuzla/abc pdr/suprove, `FORMAL_TIMEOUT` 1800 | [make_formal.log](../07_verification/formal_rerun_2026-10-06/make_formal.log), [formal_summary.md](../07_verification/formal_rerun_2026-10-06/formal_summary.md) | REPRODUCED 2026-10-06 |
| `make formal-vacuity` | `[vacuity] all mutants caught` (19 of 19) | 31.4 s | [make_formal-vacuity.log](../05_simulation/rerun_logs_2026-10-06/make_formal-vacuity.log), [formal_vacuity.md](../07_verification/formal_rerun_2026-10-06/formal_vacuity.md) | REPRODUCED 2026-10-06 |
| `make formal-extra` | `[formal] all 1 tasks passed` (datapath_pdr, abc pdr, no helpers) | 15 min 41 s wall, task 941 s (published run: 837 s, [../07_verification/formal/summary.md](../07_verification/formal/summary.md) line 40) | [make_formal-extra.log](../07_verification/rerun_2026-10-06/formal_extra/make_formal-extra.log) | REPRODUCED 2026-10-06 |
| `make fault FAULT_PUBLISH=` | `[fault] all checks passed: see <BUILD>/fault/summary.md` | 3 min 17 s; `FAULT_SEED=1`, `FAULT_TPB=12`, `FAULT_TPB_UNPROT=200`, prove depth 4 | [make_fault.log](../07_verification/rerun_2026-10-06/fault/make_fault.log) | REPRODUCED 2026-10-06 |
| `make fault-quick` | `[fault] fault-quick passed` | "about 1 minute" ([mk/fault.mk](source/mk/fault.mk) line 22) | not re-run | CLAIM (unverified) |
| `make synth` | `SYNTH PASS: generic synthesis + checks, storage audit (+ self-test), keep_hierarchy negative control, equivalence to RTL, gate-level simulation` | 2 min 0 s; Yosys 0.69+154, SBY/bitwuzla equivalence | [make_synth.log](../07_verification/rerun_2026-10-06/synth/make_synth.log) | REPRODUCED 2026-10-06 |
| `make synth-yowasp` | `YOWASP_COMPARE PASS` | needs network and `BUILD` outside `/tmp`; not re-run | [../07_verification/synth/yowasp_compare.txt](../07_verification/synth/yowasp_compare.txt) line 28 (= `reports/synth/yowasp_compare.txt`, run 2026-09-30) | VERIFIED |
| `make model MODEL_PUBLISH=` | `Ran 31 tests ... OK`; report ends `RESULT: all 19 published figures and 4 qualitative claims follow from the stated assumptions.` | 0.12 s, run in a scratch copy of `source/` with `BUILD=<scratch>`; demonstrator clock is a parameter (50/100/200 MHz), see 6.5 | review log `digital_design_srccheck/model_nopublish.log` = [model_nopublish.log](../05_simulation/rerun_logs_2026-10-06/review_runs/model_nopublish.log); report identical to `reports/model/concept_budget.txt` | REPRODUCED 2026-10-06 |
| `make ecc` | `ECC: PASS` | 20 min 41 s with other jobs running (mk/ecc.mk:9 says "about 14 minutes") | [make_ecc.log](../07_verification/rerun_2026-10-06/ecc/make_ecc.log) | REPRODUCED 2026-10-06 |
| `make ecc-quick` | `ECC-QUICK: PASS` | no time documented; not re-run as a target. It runs `ecc-lint`, `ecc-hsiao`, `ecc-sim-codec`, `ecc-formal-codec`, `ecc-formal-clean` (also run by `make ecc`) and `ecc-sim-quick` (`+seed=7 +cycles=3000`, [mk/ecc.mk](source/mk/ecc.mk) lines 92, 144-148), which `make ecc` does not | published `ecc-sim-quick` log [sim_bank_quick.log](../07_verification/ecc/logs/sim_bank_quick.log): seed 7, `TB_ORBIT_ECC_BANK PASS`, errors 0 | VERIFIED (`ecc-sim-quick` part); MISSING (`ECC-QUICK: PASS` line and run time) |
| `make test` | `ALL TEST TARGETS PASSED: lint ecc-quick fault-quick formal-quick formal model sim synth` (Makefile line 37; target list confirmed by `make help`) | not run as a whole. Sum of the measured parts lint, formal-quick, formal, model, sim, synth: about 323 s (5.4 min), plus `ecc-quick` and `fault-quick` (not measured) | — | MISSING (run); time ASSUMPTION |

### 6.4 Physical design and slow targets (Docker)

| Command | Expected final line | Time, conditions | Evidence | Status |
|---|---|---|---|---|
| `make pd-sep` (reviewed layout) | `pd-sep: all checks passed (variant sep)` ([mk/pdsep.mk](source/mk/pdsep.mk) line 61) | header: 15-25 min with `PDSEP_CORES=2` (line 23). Reviewed run: ORFS logs from 21:56:09 (synthesis) to 22:12:02 (LVS) UTC on 2026-09-29, about 16 min | ORFS logs [../07_verification/orfs_logs/](../07_verification/orfs_logs/) (39 of the 40 files in `build/pd_sep/logs/sky130hd/orbit_demo/sep/`; the 40th, `5_1_grt.json`, is in [../07_verification/additional_evidence/flow/](../07_verification/additional_evidence/flow/)). Final make line `pd-sep: all checks passed (variant sep)` at `build/pd_sep/make_pd_sep.out`:7931, packaged as [make_pd_sep.out.gz](../07_verification/additional_evidence/flow/make_pd_sep.out.gz) (console log of the same run, line 3 `run_pd_sep.sh: variant=sep ... period=default`, mtime 2026-09-29 22:14:12 UTC) | VERIFIED (ORFS stages and make final line); not re-run |
| `make pd-sep-gls PDSEP_PUBLISH=` | `injections: 702 duplicated-copy flips (702 stopped), 234 thermal-copy flips (234 repaired); 518 of 518 redundant bits hit` and `GLS PASS: 30000 cycles, 0 mismatches` | equivalent command sequence (mk/pdsep.mk lines 127-137) re-run into scratch: 2 min 18 s, seed 1, zero-delay | published: [../07_verification/gls/gls.log](../07_verification/gls/gls.log) (= `build/pd_sep/gls/sep/gls.log` = `reports/pdsep/gls.log`); re-run: [gls_rerun.log](../07_verification/rerun_2026-10-06/pd_sep/gls_rerun.log) | VERIFIED; REPRODUCED 2026-10-06 |
| `make sim-gls SIM_GLS_TAG=sky130hd_sep SIM_GLS_SRCS="build/pd_sep/results/sky130hd/orbit_demo/sep/6_final.v build/pd_sep/gls/sep/cells.v"` (cell models written by `pd-sep-gls`) | `sim-gls: summary identical to the RTL run` | 2 min 3 s; directed bench on the routed sep netlist, zero-delay. The re-run used `build/pd/gls/sky130hd/cells.v`, which has the same md5 (c54da581bda5e84a0b1167b0059f6e62) | [make_sim-gls_sky130hd_sep.log](../05_simulation/rerun_logs_2026-10-06/make_sim-gls_sky130hd_sep.log), [gls_sky130hd_sep_directed.log](../05_simulation/rerun_logs_2026-10-06/gls_sky130hd_sep_directed.log) | REPRODUCED 2026-10-06 |
| `make pd-sep-report PDSEP_PUBLISH=` | `acceptance check (separated): PASS`; collect_pd all checks passed | needs `build/pd/results/sky130hd/orbit_demo/base/6_final.def` and `reports/pd/sky130hd/checks.json`; the storage audit now reads 19/19, not the published 18/18 (section 3) | [../07_verification/published_reports/](../07_verification/published_reports/) | VERIFIED (published); not re-run as a make target |
| `make pd-sep-mechanism` | MECH lines as in [mechanism_test.txt](../07_verification/published_reports/mechanism_test.txt) | needs the baseline database `build/pd/results/sky130hd/orbit_demo/base/3_2_place_iop.odb` | published file | VERIFIED; not re-run |
| Multi-corner STA of the sep layout (no make target) | table in [sta_corners_sep.txt](../07_verification/sta_corners_sep_2026-10-06/sta_corners_sep.txt). Setup fails at ss_100C_1v60 (WNS -6.131 ns at 7.2 ns) | [run_corners_sep.sh](../07_verification/sta_corners_sep_2026-10-06/run_corners_sep.sh): `pd/sta_corners.tcl` through `scripts/run_pd.sh --shell`, about 2 s per corner. Edit its `OUT=` scratch path before use | package logs in the same folder | REPRODUCED 2026-10-06 |
| `make pd` (baseline `base`, 7.0 ns; reference only) | `pd: all checks passed (sky130hd, base)` | 7-13 min per ORFS run with `PD_CORES=2`, more with DRC/LVS ([mk/pd.mk](source/mk/pd.mk) line 35) | — | CLAIM (unverified) time; not re-run |
| `make pd-corners` | writes `sta_corners.txt` for the baseline `base` run only (not the reviewed layout) | needs the corner liberty files (network if not cached) | [../07_verification/baseline_reference/sta_corners_baseline_7p0ns.txt](../07_verification/baseline_reference/sta_corners_baseline_7p0ns.txt) (= `reports/pd/sky130hd/sta_corners.txt`) | VERIFIED (baseline reference only); not re-run |
| `make pd-ihp` (reference only) | exits non-zero: KLayout DRC FAIL, 5 markers | ORFS on ihp-sg13g2, `PD_REQUIRE=drc` | `reports/pd/ihp-sg13g2/results.md` line 20 | VERIFIED; not re-run |
| `make mutation` | `35/40 killed, 5 survivor(s)` | "about 65 minutes" ([mk/mutation.mk](source/mk/mutation.mk) line 10). Needs `scripts/mutation_test.py` and `reports/mutation/tb_mutation_gaps.v` (not in `source/`; the latter is copied as [../07_verification/mutation/tb_mutation_gaps.v](../07_verification/mutation/tb_mutation_gaps.v)) | [../07_verification/mutation/summary.md](../07_verification/mutation/summary.md) line 52; `build/mutation/run.log` (not in the package) | VERIFIED (result); CLAIM (unverified) time; not re-run |
| `make viz` | 3D viewer data | needs `scripts/viz_*.py`, `viz/requirements.txt`, npm | — | N/A: viewer, not design evidence |

### 6.5 Stale references in the build files

| Location | Text | Fact | Status |
|---|---|---|---|
| [Makefile](source/Makefile) line 29 (`make help`) | "See README.md for the area targets (sim, formal, fault, synth, pd, model, ecc)." | No `README.md` at the repo root (and no `rtl/README.md`, which brief p.4 also names). The list also omits `mutation`, `pd-sep*`, `viz` and `synth-yowasp`. The only per-area run guide is the header comment of each `mk/*.mk` (and [rtl/ecc/README.md](source/rtl/ecc/README.md) for ECC) | REPRODUCED 2026-10-06 (`ls`, `make help`); see discrepancy register (09_review_notes) |
| [mk/model.mk](source/mk/model.mk) line 17 | `MODEL_PD_SUMMARY ?= reports/pd/summary.md` | The file does not exist. [model/concept_budget.py](source/model/concept_budget.py) lines 500-507 then fall back silently to the command-line clocks 50/100/200 MHz, so the demonstrator throughput is never given at a closed clock. 200 MHz is above every period that closed at TT | REPRODUCED 2026-10-06; see discrepancy register (09_review_notes) |
| [mk/ecc.mk](source/mk/ecc.mk) line 9 | "results in reports/ecc/results.txt" | `make ecc` writes `$(BUILD)/ecc/summary.txt`; only `ecc-report` copies it to `reports/ecc/results.txt` | see discrepancy register (09_review_notes) |
| [requirements-tools.txt](source/requirements-tools.txt) line 15 | "model/ and the scripts use the standard library only" | [scripts/pdsep_render.py](source/scripts/pdsep_render.py) lines 17-19 import `klayout` and `PIL` (venv from mk/pdsep.mk line 83); [pd/render_layout.py](source/pd/render_layout.py) needs KLayout `pya` (ORFS image); [tb/cocotb/run_random.py](source/tb/cocotb/run_random.py) needs cocotb (`tabbypy3`) | REPRODUCED 2026-10-06 (grep of imports); see discrepancy register (09_review_notes) |
| [mk/model.mk](source/mk/model.mk) line 38 | `model: RTL_DIR=$(RTL_DIR) is not the production rtl/; report left in $(MODEL_OUT)` | Printed whenever `MODEL_PUBLISH` is empty, also when publishing is switched off on purpose with the production `RTL_DIR=rtl` (`make model MODEL_PUBLISH=` printed `model: RTL_DIR=rtl is not the production rtl/; ...`, review log [model_nopublish.log](../05_simulation/rerun_logs_2026-10-06/review_runs/model_nopublish.log) line 41). Misleading message only; outputs unaffected | REPRODUCED 2026-10-06 |
| [rtl/orbit_keep_reg.v](source/rtl/orbit_keep_reg.v) line 10 | "the storage audit in scripts/ checks the result" | `scripts/storage_audit.py` covers generic Yosys netlists only; the audit of the routed layout is [pd/audit_storage.py](source/pd/audit_storage.py) | see discrepancy register (09_review_notes) |

### 6.6 Missing for this section

- A top-level run guide (README) owned by the design: MISSING. Needed: revision, prerequisites, the target list of 6.3/6.4 and the publish side effects. Makefile line 29 already points to one.
- `make test` as one run, `ecc-quick`, `fault-quick` and a full `make pd-sep` at the package commit: not re-run for this package (MISSING). Needed: a run log with wall time on a clean checkout, using `BUILD=<dir>` and the `*_PUBLISH=` overrides.
- `MANIFEST.sha256`, named in the revision table: resolved in package, [../MANIFEST.sha256](../MANIFEST.sha256), generated last (D-53).
- Logs formerly outside the package, resolved in package on 2026-10-06: the review logs `sim/make_sim.log`, `sim/make_mutants.log`, `spec_rtl/formal_quick.log` and `digital_design_srccheck/model_nopublish.log` (6.3) are in [../05_simulation/rerun_logs_2026-10-06/review_runs/](../05_simulation/rerun_logs_2026-10-06/review_runs/), and the console log of the reviewed run, `build/pd_sep/make_pd_sep.out` (6.4), is [../07_verification/additional_evidence/flow/make_pd_sep.out.gz](../07_verification/additional_evidence/flow/make_pd_sep.out.gz). The pass lines and times quoted above can be checked there.
