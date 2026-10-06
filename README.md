# ORBIT-AI 4-lane INT8 digital demonstrator (`orbit_demo`)

A small digital demonstrator for part of the ORBIT-AI space-compute concept: four signed INT8 multiply / INT32 accumulate lanes, duplicated accumulator and result storage with a sticky mismatch fault-stop, and a thermal state machine with triplicated (TMR) state that throttles, stops and recovers input admission. The RTL is synthesizable Verilog-2005 with a single clock (`clk`) and a synchronous active-low reset (`rst_n`).

Status:

- **Not fabricated.** There is no silicon, no pad ring and no package. The layout is a core-only block.
- **Placed and routed** with OpenROAD-flow-scripts (ORFS) on SkyWater sky130hd. The reviewed layout is the copy-separated run (`pd/sky130hd_sep`) at 7.2 ns. ORFS optimised timing at the TT corner (25 C, 1.80 V) only. A re-time of the same layout passes at ff_n40C_1v95 and fails setup at ss_100C_1v60 (WNS -6.131 ns). DRC used the ORFS deck with FEOL rules off, and LVS compares against a netlist from the same database, so neither is sign-off.
- **Checked** by zero-delay simulation (RTL and gate-level), formal proofs on the fault-free RTL, and fault injection on the RTL and the routed netlist. The review notes list the faults that are not detected or not injected and the gaps in the tests.
- **No radiation testing or qualification.** sky130 is not radiation-characterized; the copy separation is geometry only.
- The concept brief's 16 tiles and 200-800 MHz are targets, and its 40 W is a sizing assumption, for an unbuilt chip. None of them is a result for this design.

## Reviewing this design

The design review package is in **[review/orbit_demo_design_review/](review/orbit_demo_design_review/)**.

1. Start with **[REVIEW_GUIDE.md](review/orbit_demo_design_review/REVIEW_GUIDE.md)**, a step-by-step walkthrough for a reviewer with checklists and a feedback template (about 3-4.5 hours, plus up to 1 hour for optional re-runs).
2. The package **[README.md](review/orbit_demo_design_review/README.md)** has the exact revision, the folder map and the status legend.
3. **[review_notes.pdf](review/orbit_demo_design_review/09_review_notes/review_notes.pdf)** has the known issues, the trade-offs, the 14 questions for the reviewer, the discrepancy register and the list of gaps.

Each result in the package gives its source file, test conditions and a status (VERIFIED, REPRODUCED 2026-10-06, TARGET, ASSUMPTION, CLAIM (unverified), MISSING or N/A). `MANIFEST.sha256` in the package lists the sha256 of every other file in the package.

## Repository layout

| Path | Contents |
|---|---|
| [docs/SPEC.md](docs/SPEC.md) | Behavioral specification: the contract for the RTL, testbenches, formal properties and implementation scripts |
| [docs/orbit-ai-design-brief.pdf](docs/orbit-ai-design-brief.pdf) | ORBIT-AI v0.1 concept brief (29 Sep 2026). It describes an earlier project state and the unbuilt full chip; see the package's discrepancy register |
| [rtl/](rtl/) | `orbit_demo` (top), `orbit_mac_lane`, `orbit_thermal_tmr`, `orbit_keep_reg`. [rtl/ecc/](rtl/ecc/) is a standalone SECDED ECC block, **not** instantiated in `orbit_demo` |
| [tb/](tb/) | Directed testbench, cocotb random test with a Python reference model, RTL mutants, ECC testbenches |
| [formal/](formal/), [fault/](fault/) | SymbiYosys properties; fault-injection harness and SEU campaign |
| [synth/](synth/) | Generic Yosys synthesis, storage audit, equivalence check |
| [pd/](pd/) | ORFS configurations: `sky130hd` (baseline, 7.0 ns), `sky130hd_sep` (reviewed, copy-separated, 7.2 ns), `ihp-sg13g2` (reference); report, GLS and corner-STA scripts |
| [scripts/](scripts/) | ORFS Docker runners, separation and report scripts, generic-netlist storage audit, mutation campaign, tool setup, viewer and page builders |
| [model/](model/) | Concept-chip throughput/budget calculator (calculations, not measurements) |
| [mk/](mk/), [Makefile](Makefile) | Build targets, one `mk/<area>.mk` per area |
| [reports/](reports/) | Published results of each area |
| [review/](review/) | Design review package |
| `viz/`, `site/`, `docs/research/` | 3D viewer, presentation pages and research notes. They are not design evidence; the review notes (D-62 to D-84) list claims in them that overstate the evidence |

## Running the checks

[requirements-tools.txt](requirements-tools.txt) pins the OSS CAD Suite release 2026-09-28 (Yosys, Icarus Verilog, Verilator, SymbiYosys and solvers), Python 3.11 and the ORFS Docker image by digest. The cocotb bench uses the cocotb bundled with the OSS CAD Suite, which the file does not list. [scripts/setup_tools.sh](scripts/setup_tools.sh) installs the OSS CAD Suite and pulls the ORFS image.

```sh
EDA_HOME=/opt/eda scripts/setup_tools.sh   # OSS CAD Suite + ORFS image
make lint                                  # Verilator -Wall lint of the RTL
make test MODEL_PUBLISH=                   # lint ecc-quick fault-quick formal-quick formal model sim synth
```

`make test` has not been run as a whole for the package. It includes `model`, which rewrites `reports/model/` unless `MODEL_PUBLISH=` is given.

Area targets (each `mk/<area>.mk` starts with a header comment that describes it). Measured times are from the 2026-10-06 re-runs on 4 CPUs (package file 04_digital_design/README.md, section 6) unless the row says otherwise. "mk comment" marks the estimate in the `mk/*.mk` header.

| Target | What it runs | Time |
|---|---|---|
| `make sim` | model self-test, directed bench (Icarus + Verilator), cocotb random (Icarus + Verilator), generic gate-level sim | 2 min 19 s |
| `make sim-mutants` | 26 RTL mutants against both benches | 28 s |
| `make formal` / `formal-quick` / `formal-vacuity` | 12 / 8 property tasks; 19 vacuity mutants | 47 s / about 17 s (sum of task times) / 31 s |
| `make fault` | formal fault injection, RTL SEU campaign, negative controls | 3 min 17 s |
| `make synth` | generic synthesis, storage audit, keep_hierarchy negative control, RTL equivalence, gate-level sim | 2 min 0 s |
| `make model` | concept budget model and its tests | 0.12 s |
| `make ecc` | standalone ECC block: lint, H-matrix check, sims, formal, negative controls, synthesis | 20 min 41 s with other jobs running (mk comment: about 14 min) |
| `make mutation` | 40 RTL mutants through lint, sim, formal-quick, fault-quick and synth | about 65 min (mk comment; not measured) |
| `make pd-sep` | reviewed layout: ORFS flow to GDS with DRC, LVS and LEC, then `pd-sep-gls` and `pd-sep-report` (Docker) | about 16 min for the ORFS stages of the reviewed run, 2026-09-29 logs (mk comment: 15-25 min) |
| `make pd-sep-gls` | gate-level fault campaign on the routed sep netlist; needs a finished `pd-sep` run | 2 min 18 s (same commands run by hand) |
| `make pd` | baseline layout, reference only (Docker) | 7-13 min per ORFS run, more with DRC/LVS (mk comment; not measured) |
| `make pd-corners` / `pd-ihp` | multi-corner STA of the baseline run; IHP reference layout (Docker) | not measured |

Targets that publish write into the tracked `reports/`. Pass `BUILD=<dir>` and the `*_PUBLISH=` overrides to keep `reports/` unchanged. A new `make pd-sep` run has not been compared with the reviewed layout database. See [04_digital_design/README.md](review/orbit_demo_design_review/04_digital_design/README.md) section 6 for the full table, the expected final lines and the side effects.
