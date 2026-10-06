# ORBIT-AI 4-lane INT8 digital demonstrator (`orbit_demo`)

A small, testable slice of the ORBIT-AI space-compute concept: four signed INT8 multiply / INT32 accumulate lanes, duplicated accumulator and result storage with a sticky mismatch fault-stop, and a triplicated (TMR) thermal state machine that throttles, stops and recovers input admission. The RTL is synthesizable Verilog-2005 with a single clock (`clk`) and a synchronous active-low reset (`rst_n`).

Status, stated plainly:

- **Not fabricated.** There is no silicon, no pad ring and no package. The layout is a core-only block.
- **Implemented** with OpenROAD-flow-scripts on SkyWater sky130hd. The reviewed layout is the copy-separated run (`pd/sky130hd_sep`) at 7.2 ns. It closes timing at the TT corner (1.80 V, 25 C) only and fails setup at ss_100C_1v60.
- **Verified in simulation and formally**: directed and random simulation, formal proofs, RTL and gate-level fault injection. It has **no** radiation testing or qualification, and sky130 is not radiation-characterized.
- The 16-tile / 200-800 MHz / 40 W figures in the concept brief are targets for an unbuilt chip, not results for this design.

## Reviewing this design

The design review package is in **[review/orbit_demo_design_review/](review/orbit_demo_design_review/)**.

1. Read **[REVIEW_GUIDE.md](review/orbit_demo_design_review/REVIEW_GUIDE.md)**, the step-by-step walkthrough for a reviewer (about 2-4 hours).
2. The package **[README.md](review/orbit_demo_design_review/README.md)** has the exact revision, the folder map and the status legend.
3. The most important document is **[review_notes.pdf](review/orbit_demo_design_review/09_review_notes/review_notes.pdf)**: known issues, trade-offs, 14 questions for the reviewer, and the discrepancy register.

Each result in the package gives its source file, test conditions and a status (VERIFIED, REPRODUCED 2026-10-06, TARGET, ASSUMPTION, CLAIM (unverified), MISSING or N/A). `MANIFEST.sha256` in the package lists the hash of every file in it.

## Repository layout

| Path | Contents |
|---|---|
| [docs/SPEC.md](docs/SPEC.md) | Behavioral specification: the contract for the RTL, testbenches, formal properties and implementation scripts |
| [docs/orbit-ai-design-brief.pdf](docs/orbit-ai-design-brief.pdf) | ORBIT-AI v0.1 concept brief (29 Sep 2026). It describes an earlier project state and the unbuilt full chip; see the package's discrepancy register |
| [rtl/](rtl/) | `orbit_demo` (top), `orbit_mac_lane`, `orbit_thermal_tmr`, `orbit_keep_reg`. [rtl/ecc/](rtl/ecc/) is a standalone SECDED ECC block, **not** instantiated in `orbit_demo` |
| [tb/](tb/) | Directed testbench, cocotb random test with a Python reference model, RTL mutants |
| [formal/](formal/), [fault/](fault/) | SymbiYosys properties; fault-injection harness and SEU campaign |
| [synth/](synth/) | Generic Yosys synthesis, storage audit, equivalence check |
| [pd/](pd/) | ORFS configurations: `sky130hd` (baseline, 7.0 ns), `sky130hd_sep` (reviewed, copy-separated, 7.2 ns), `ihp-sg13g2` (reference); GLS and corner-STA scripts |
| [model/](model/) | Concept-chip throughput/budget calculator (calculations, not measurements) |
| [mk/](mk/), [Makefile](Makefile) | Build targets, one `mk/<area>.mk` per area |
| [reports/](reports/) | Published results of each area |
| [review/](review/) | Design review package |
| `viz/`, `site/`, `docs/research/` | 3D viewer, presentation pages and research notes. These are presentation material, not design evidence; the review notes list claims in them that overstate the evidence |

## Running the checks

Tools are pinned in [requirements-tools.txt](requirements-tools.txt): the OSS CAD Suite (Yosys, Icarus Verilog, Verilator, SymbiYosys, cocotb), Python 3.11, and the ORFS Docker image for physical design. [scripts/setup_tools.sh](scripts/setup_tools.sh) installs them.

```sh
EDA_HOME=/opt/eda scripts/setup_tools.sh   # OSS CAD Suite + ORFS image
make lint                                  # Verilator -Wall lint of the RTL
make test                                  # all fast self-checking targets
```

Area targets (each `mk/<area>.mk` starts with a header comment that describes it). Times are from the 2026-10-06 re-runs on 4 CPUs:

| Target | What it runs | Approx. time |
|---|---|---|
| `make sim` | model self-test, directed bench (Icarus + Verilator), cocotb random (Icarus + Verilator), generic gate-level sim | 2.5 min |
| `make sim-mutants` | 26 RTL mutants against both benches | 0.5 min |
| `make formal` / `formal-quick` / `formal-vacuity` | 12 / 8 property tasks; 19 vacuity mutants | 1 min / 20 s / 30 s |
| `make fault` | formal fault injection and RTL SEU campaign | 3.5 min |
| `make synth` | generic synthesis, storage audit, keep_hierarchy negative control, RTL equivalence, gate-level sim | 2 min |
| `make model` | concept budget model and its tests | < 1 s |
| `make ecc` | standalone ECC block: lint, sims, formal, mutants | 15-20 min |
| `make mutation` | 40-mutant campaign through every check | about 65 min |
| `make pd-sep` | reviewed copy-separated layout: ORFS flow, DRC, LVS, LEC, reports (Docker) | about 16 min |
| `make pd-sep-gls` | gate-level fault campaign on the routed sep netlist | 2.5 min |
| `make pd` / `pd-corners` / `pd-ihp` | baseline layout, its multi-corner STA, IHP reference (Docker) | 10+ min each |

Targets that publish write into the tracked `reports/`. Pass `BUILD=<dir>` and the `*_PUBLISH=` overrides to keep `reports/` unchanged; see [04_digital_design/README.md](review/orbit_demo_design_review/04_digital_design/README.md) section 6 for the full table, the expected final lines and the side effects.
