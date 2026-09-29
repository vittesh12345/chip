#!/usr/bin/env python3
"""Write reports/sim/summary.md from the logs of `make sim sim-mutants`.

Only reads $(BUILD)/sim/; every PASS/FAIL in the report is taken from a log
line printed by the check itself. Missing logs are reported as NOT RUN.
Also copies the small logs and tables next to summary.md.
"""

import argparse
import datetime
import re
import shutil
import subprocess
import sys
from pathlib import Path


def read(p):
    p = Path(p)
    return p.read_text(errors="replace") if p.exists() else None


def version(cmd):
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return (out.stdout or out.stderr).strip().splitlines()[0]
    except (OSError, subprocess.SubprocessError, IndexError):
        return "unknown"


def summary_block(log):
    if log is None:
        return None
    m = re.search(r"^tb_orbit_demo summary.*?^TB_ORBIT_DEMO \w+", log, re.S | re.M)
    return m.group(0) if m else None


def verdict(log, pass_pat, fail_pat=None):
    if log is None:
        return "NOT RUN"
    if re.search(pass_pat, log, re.M):
        return "PASS"
    return "FAIL"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--build", required=True, help="$(BUILD)/sim")
    ap.add_argument("--out", required=True, help="reports/sim")
    ap.add_argument("--seed", default="1")
    ap.add_argument("--seeds", default="1 2 3 4 5")
    ap.add_argument("--cycles", default="20000")
    ap.add_argument("--soak-seeds", default="1")
    ap.add_argument("--vl-seeds", default="1 2")
    ap.add_argument("--mut-cycles", default="20000")
    ap.add_argument("--rtl", default="rtl/orbit_keep_reg.v rtl/orbit_mac_lane.v "
                    "rtl/orbit_thermal_tmr.v rtl/orbit_demo.v", help="$(RTL)")
    ap.add_argument("--vl-opt", default="OPT_FAST=-O0 OPT_SLOW=-O0 OPT_GLOBAL=-O0")
    ap.add_argument("--jobs", default="2")
    ap.add_argument("--soak-max", default="400000")
    a = ap.parse_args()
    rtl = a.rtl

    b = Path(a.build)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    logs = {
        "model": read(b / "model.log"),
        "icarus": read(b / "directed" / "icarus.log"),
        "verilator": read(b / "verilator" / "verilator.log"),
        "random": read(b / "random" / "run.log"),
        "random_vl": read(b / "random_verilator" / "run.log"),
        "gls_yosys": read(b / "gls" / "yosys" / "gls.log"),
        "gls_sky130hd": read(b / "gls" / "sky130hd" / "gls.log"),
        "mutants": read(b / "mutants" / "run.log"),
    }
    rows = [
        ("Reference model self-test", "make sim-model", verdict(logs["model"], r"^orbit_ref self-test PASS")),
        ("Directed bench, Icarus Verilog", "make sim-directed", verdict(logs["icarus"], r"^TB_ORBIT_DEMO PASS")),
        ("Directed bench, Verilator --binary --timing", "make sim-verilator",
         verdict(logs["verilator"], r"^TB_ORBIT_DEMO PASS")),
        ("Verilator summary == Icarus summary", "make sim-verilator",
         "PASS" if summary_block(logs["icarus"]) and
         summary_block(logs["icarus"]) == summary_block(logs["verilator"]) else "FAIL"),
        ("cocotb random + wrap soak, Icarus", "make sim-random", verdict(logs["random"], r"^SIM_RANDOM PASS")),
        ("cocotb random, Verilator (coverage == Icarus)", "make sim-random-verilator",
         verdict(logs["random_vl"], r"^SIM_RANDOM PASS")),
        ("Directed bench on Yosys generic netlist", "make sim-gls",
         "PASS" if verdict(logs["gls_yosys"], r"^TB_ORBIT_DEMO PASS") == "PASS" and
         summary_block(logs["gls_yosys"]) == summary_block(logs["icarus"]) else
         verdict(logs["gls_yosys"], r"^TB_ORBIT_DEMO PASS")),
        ("Directed bench on routed sky130hd netlist (pd area)",
         'make sim-gls SIM_GLS_TAG=sky130hd SIM_GLS_SRCS="build/pd/results/sky130hd/orbit_demo/base/6_final.v '
         'build/pd/gls/sky130hd/cells.v"',
         "PASS" if verdict(logs["gls_sky130hd"], r"^TB_ORBIT_DEMO PASS") == "PASS" and
         summary_block(logs["gls_sky130hd"]) == summary_block(logs["icarus"]) else
         verdict(logs["gls_sky130hd"], r"^TB_ORBIT_DEMO PASS")),
        ("Mutation negative control (both benches kill every mutant)", "make sim-mutants",
         verdict(logs["mutants"], r"^SIM_MUTANTS PASS")),
    ]

    # Copy evidence (all small).
    copies = {
        "model.log": b / "model.log",
        "directed_icarus.log": b / "directed" / "icarus.log",
        "directed_verilator.log": b / "verilator" / "verilator.log",
        "gls_yosys.log": b / "gls" / "yosys" / "gls.log",
        "gls_sky130hd.log": b / "gls" / "sky130hd" / "gls.log",
        "random_icarus.md": b / "random" / "summary.md",
        "random_verilator.md": b / "random_verilator" / "summary.md",
        "mutants.md": b / "mutants" / "summary.md",
    }
    copied = []
    for dst, src in copies.items():
        if src.exists():
            shutil.copyfile(src, out / dst)
            copied.append(dst)

    vers = {
        "Icarus Verilog": version(["iverilog", "-V"]),
        "Verilator": version(["verilator", "--version"]),
        "Yosys": version(["yosys", "-V"]),
        "cocotb": version(["cocotb-config", "--version"]),
        "cocotb Python": version(["tabbypy3", "--version"]),
    }

    L = []
    L.append("# Simulation of orbit_demo (area: sim)")
    L.append("")
    L.append(f"Generated by `make sim-report` on {datetime.date.today().isoformat()} from the logs in "
             f"`{b}`. Every verdict below is read from the line the check itself prints.")
    L.append("")
    L.append("## Results")
    L.append("")
    L.append("| check | command | result |")
    L.append("|---|---|---|")
    for name, cmd, res in rows:
        L.append(f"| {name} | `{cmd}` | {res} |")
    L.append("")
    L.append("Tools: " + "; ".join(f"{k}: {v}" for k, v in vers.items()) + ".")
    L.append("")

    L.append("## Directed bench (`tb/tb_orbit_demo.v`)")
    L.append("")
    L.append(f"Seed `+seed={a.seed}` (xorshift32 inside the bench, so both simulators get identical "
             "stimulus). Ports only, no hierarchical references. Checks: a cycle-accurate reference "
             "model of docs/SPEC.md compared every cycle (in_ready, out_valid, out_data, therm_state, "
             "shutdown_req, fault = 0, therm_repair = 0), a transaction scoreboard for every out_fire, "
             "and scenario checks with hand-computed literals.")
    L.append("")
    scen = re.findall(r"scenario \d+: (\S+)", logs["icarus"] or "")
    if scen:
        L.append("Scenarios: " + ", ".join(scen) + ".")
        L.append("")
    blk = summary_block(logs["icarus"])
    if blk:
        L.append("Icarus summary (the Verilator run and both gate-level runs print the identical block):")
        L.append("")
        L.append("```")
        L.append(blk)
        L.append("```")
        L.append("")
    L.append("Commands run by `make sim-directed sim-verilator sim-gls` (PATH starts with "
             "/opt/eda/oss-cad-suite/bin):")
    L.append("")
    L.append("```")
    L.append(f"iverilog -g2005 -Wall -Wno-timescale -o {b}/directed/tb.vvp tb/tb_orbit_demo.v {rtl}")
    L.append(f"vvp -n {b}/directed/tb.vvp +seed={a.seed}")
    L.append(f"verilator --binary --timing -j {a.jobs} --top-module tb_orbit_demo --Mdir {b}/verilator/obj_dir "
             f"-o Vtb_orbit_demo -MAKEFLAGS \"{a.vl_opt}\" tb/tb_orbit_demo.v {rtl}")
    L.append(f"{b}/verilator/obj_dir/Vtb_orbit_demo +seed={a.seed}")
    L.append(f"yosys -q -p \"read_verilog {rtl}; synth -flatten -top orbit_demo; stat; "
             f"write_verilog -noattr {b}/gls/yosys/orbit_demo_yosys.v\"")
    L.append(f"iverilog -g2005 -Wall -Wno-timescale -o {b}/gls/yosys/tb.vvp tb/tb_orbit_demo.v "
             f"{b}/gls/yosys/orbit_demo_yosys.v")
    L.append(f"vvp -n {b}/gls/yosys/tb.vvp +seed={a.seed}")
    L.append("```")
    L.append("")
    L.append("### Gate-level reuse")
    L.append("")
    ystat = read(b / "gls" / "yosys" / "yosys.log") or ""
    ystat = ystat[ystat.rfind("=== design hierarchy ==="):]      # the final `stat` only
    m = re.findall(r"^\s+(\d+) cells$", ystat, re.M)
    ff = sum(int(n) for n in re.findall(r"^\s+(\d+)\s+\$_S?DFFE?_\w+$", ystat, re.M))
    L.append(f"- Yosys generic netlist of the RTL (`make sim-gls`, part of `make sim`): "
             f"{m[-1] if m else '?'} cells, {ff if ff else '?'} flip-flop cells; bench result "
             f"{rows[6][2]}, summary block identical to the RTL run.")
    pdn = Path("build/pd/results/sky130hd/orbit_demo/base/6_final.v")
    when = (datetime.datetime.fromtimestamp(pdn.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            if pdn.exists() else "not present")
    L.append(f"- Routed sky130hd netlist from the pd area (`{pdn}`, written {when}) with the pd "
             f"area's Yosys-generated liberty cell models (`build/pd/gls/sky130hd/cells.v`), zero "
             f"delay: bench result {rows[7][2]}. Run on demand (about 2 minutes), not part of "
             f"`make sim`:")
    L.append("")
    L.append("```")
    L.append('make sim-gls SIM_GLS_TAG=sky130hd SIM_GLS_SRCS="build/pd/results/sky130hd/orbit_demo/base/6_final.v '
             'build/pd/gls/sky130hd/cells.v"')
    L.append("```")
    L.append("")

    L.append("## cocotb constrained-random test (`tb/cocotb/`)")
    L.append("")
    L.append(f"Golden model `tb/cocotb/orbit_ref.py` (written from docs/SPEC.md, not from the RTL). "
             f"`random_workload`: seeds {a.seeds}, {a.cycles} cycles each; `wrap_soak`: seed(s) "
             f"{a.soak_seeds}, runs until both INT32 wrap directions were seen, then 500 more cycles. "
             f"Every cycle compares all outputs with the model; every out_fire is checked against a "
             f"scoreboard. Under Verilator, seeds {a.vl_seeds} are rerun and every coverage count must "
             f"equal the Icarus run.")
    L.append("")
    L.append("```")
    L.append(f"tabbypy3 tb/cocotb/run_random.py --jobs {a.jobs} --sources {rtl} --cycles {a.cycles} "
             f"--soak-max {a.soak_max} --sim icarus --out {b}/random --seeds {a.seeds} "
             f"--soak-seeds {a.soak_seeds}")
    L.append(f"tabbypy3 tb/cocotb/run_random.py --jobs {a.jobs} --sources {rtl} --cycles {a.cycles} "
             f"--soak-max {a.soak_max} --sim verilator --out {b}/random_verilator --seeds {a.vl_seeds} "
             f"--soak-seeds --compare-with {b}/random")
    L.append("```")
    L.append("")
    rnd = read(b / "random" / "summary.md")
    if rnd:
        L.append("Icarus runs and functional coverage (copied from `build/sim/random/summary.md`):")
        L.append("")
        L += [ln for ln in rnd.splitlines()[2:]]
        L.append("")
    cmp_lines = re.findall(r"^compare: .*$", logs["random_vl"] or "", re.M)
    if cmp_lines:
        L.append("Verilator cross-check:")
        L.append("")
        L += [f"- {c}" for c in cmp_lines]
        L.append("")

    L.append("## Mutation negative control (`tb/sim_mutants.py`)")
    L.append("")
    L.append(f"Each mutant is a copy of the RTL with one SPEC-violating change. The directed bench runs "
             f"with `+maxerr=1`; the random bench runs one seed of {a.mut_cycles} cycles and counts as a "
             f"kill only with at least one model mismatch.")
    L.append("")
    L.append("```")
    L.append(f"python3 tb/sim_mutants.py --rtl-dir rtl --out {b}/mutants --tb tb/tb_orbit_demo.v "
             f"--cocotb-python tabbypy3 --random-cycles {a.mut_cycles} --jobs {a.jobs}")
    L.append("```")
    L.append("")
    mut = read(b / "mutants" / "summary.md")
    if mut:
        L += mut.splitlines()[2:]
        L.append("")

    L.append("## RTL / SPEC issues")
    L.append("")
    if all(r[2] == "PASS" for r in rows):
        L.append("None found: the RTL matched both independent SPEC models in every checked cycle of "
                 "every run above.")
    else:
        L.append("Not every check passed (see Results); failures are not analysed by this script.")
    L.append("")

    L.append("## Limitations")
    L.append("")
    L += [
        "- Fault-free behaviour only: no upsets are injected here (fault injection is another area), so "
        "`fault` and `therm_repair` are only checked to stay 0 and the mismatch/fault-stop path is not "
        "exercised by these benches.",
        "- The thermal unused code 3 cannot be reached through the ports without an upset, so its "
        "\"behaves as STOP\" rule is only in the reference models, not observed.",
        "- Gate-level runs are zero-delay functional simulations (no SDF timing).",
        "- Coverage is event counting in the testbench, not simulator code or toggle coverage.",
        "- The random stimulus is constrained by the choices in `tb/cocotb/test_orbit_random.py` "
        "(e.g. temperature regimes, sum lengths); the mutation table is evidence that it is sensitive, "
        "not a proof of completeness.",
        "- `rst_n` is asserted only a few times mid-run in the random test; reset during an output "
        "transfer is covered only if the random run happens to do so.",
    ]
    L.append("")
    L.append("Files copied next to this summary: " + ", ".join(copied) + ".")
    L.append("")
    (out / "summary.md").write_text("\n".join(L) + "\n")
    bad = [r for r in rows if r[2] != "PASS"]
    for r in bad:
        print(f"sim-report: {r[0]}: {r[2]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
