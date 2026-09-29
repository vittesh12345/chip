#!/usr/bin/env python3
"""Build orbit_demo once and run the cocotb random tests for several seeds.

Run with the Python that has cocotb installed (the OSS CAD Suite's tabbypy3):

    tabbypy3 tb/cocotb/run_random.py --out build/sim/random \
        --sources rtl/orbit_keep_reg.v ... --seeds 1 2 3 4 5 --cycles 20000

Writes <out>/<test>_seed<N>/coverage.json per run and <out>/summary.md, and
exits non-zero if any run fails, any run is missing, or any required coverage
point (see REQUIRED in test_orbit_random.py) was never hit.
"""

import argparse
import json
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import cocotb                                          # noqa: E402
import cocotb_tools.runner                             # noqa: E402
from cocotb_tools.runner import get_runner             # noqa: E402
from test_orbit_random import REQUIRED                  # noqa: E402


def xunit_passed(xml, test):
    """True if the xunit file records exactly one run of `test` without failure."""
    try:
        root = ET.parse(xml).getroot()
    except (OSError, ET.ParseError):
        return False
    cases = [c for c in root.iter("testcase") if c.get("name") == test]
    if len(cases) != 1:
        return False
    return not any(ch.tag in ("failure", "error", "skipped") for ch in cases[0])


def run_one(runner, out, test, seed, env):
    test_dir = out / f"{test}_seed{seed}"
    test_dir.mkdir(parents=True, exist_ok=True)
    cov_file = test_dir / "coverage.json"
    if cov_file.exists():
        cov_file.unlink()
    xml = test_dir / "results.xml"
    env = dict(env, SIM_COV_FILE=str(cov_file), SIM_SEED=str(seed))
    t0 = time.time()
    try:
        runner.test(test_module="test_orbit_random", hdl_toplevel="orbit_demo",
                    test_filter=test, seed=seed, extra_env=env, test_dir=test_dir,
                    results_xml=str(xml), log_file=test_dir / "sim.log")
        sim_ok = True
    except SystemExit as e:                  # the runner exits on simulator failure
        sim_ok = e.code in (0, None)
    wall = time.time() - t0
    xml_ok = xunit_passed(xml, test)
    report = json.loads(cov_file.read_text()) if cov_file.exists() else None
    passed = sim_ok and xml_ok and report is not None and \
        report["errors"] == 0 and not report["missing_coverage"]
    return {"test": test, "seed": seed, "passed": passed, "wall_s": wall,
            "report": report, "dir": str(test_dir)}


def write_summary(path, args, runs, total_cov):
    lines = ["# cocotb random test of orbit_demo", ""]
    lines.append(f"cocotb {cocotb.__version__}, simulator {args.sim}, "
                 f"Python {sys.version.split()[0]} ({sys.executable})")
    lines.append("")
    lines.append("| test | seed | cycles | results checked | errors | missing coverage | wall s | result |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for r in runs:
        rep = r["report"] or {}
        cov = rep.get("coverage", {})
        lines.append(f"| {r['test']} | {r['seed']} | {rep.get('cycles', '-')} | "
                     f"{cov.get('results_checked', '-')} | {rep.get('errors', '-')} | "
                     f"{', '.join(rep.get('missing_coverage', [])) or '-' if rep else 'NO REPORT'} | "
                     f"{r['wall_s']:.1f} | {'PASS' if r['passed'] else 'FAIL'} |")
    lines.append("")
    keys = sorted(set(k for r in runs if r["report"] for k in r["report"]["coverage"]) |
                  set(k for v in REQUIRED.values() for k in v))
    head = [f"{r['test'].split('_')[0]}:{r['seed']}" for r in runs]
    lines.append("Functional coverage (event counts; * = required > 0 in the test that lists it)")
    lines.append("")
    lines.append("| event | " + " | ".join(head) + " | total |")
    lines.append("|---|" + "---|" * (len(head) + 1))
    for k in keys:
        req = any(k in v for v in REQUIRED.values())
        vals = [str((r["report"] or {}).get("coverage", {}).get(k, 0)) for r in runs]
        lines.append(f"| {k}{' *' if req else ''} | " + " | ".join(vals) + f" | {total_cov.get(k, 0)} |")
    lines.append("")
    Path(path).write_text("\n".join(lines) + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sim", default="icarus", choices=("icarus", "verilator"))
    ap.add_argument("--out", required=True, help="work directory")
    ap.add_argument("--sources", nargs="+", required=True)
    ap.add_argument("--seeds", nargs="*", type=int, default=[1, 2, 3, 4, 5])
    ap.add_argument("--cycles", type=int, default=20000)
    ap.add_argument("--soak-seeds", nargs="*", type=int, default=[1])
    ap.add_argument("--soak-max", type=int, default=400000)
    ap.add_argument("--jobs", type=int, default=2, help="build parallelism (Verilator only)")
    ap.add_argument("--compare-with", help="work directory of an earlier run (e.g. the other "
                    "simulator): every run here must have identical coverage counts there")
    a = ap.parse_args()

    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    sources = [Path(s).resolve() for s in a.sources]
    cocotb_tools.runner.MAX_PARALLEL_BUILD_JOBS = a.jobs   # C++ build of the Verilator model
    runner = get_runner(a.sim)
    build_args = ["-j", str(a.jobs)] if a.sim == "verilator" else []
    runner.build(sources=sources, hdl_toplevel="orbit_demo", build_dir=out / "sim_build",
                 timescale=("1ns", "1ps"), always=True, build_args=build_args,
                 log_file=out / "build.log")

    env = {"SIM_CYCLES": str(a.cycles), "SIM_SOAK_MAX": str(a.soak_max)}
    runs = [run_one(runner, out, "random_workload", s, env) for s in a.seeds]
    runs += [run_one(runner, out, "wrap_soak", s, env) for s in a.soak_seeds]

    total = {}
    for r in runs:
        for k, v in ((r["report"] or {}).get("coverage", {})).items():
            total[k] = total.get(k, 0) + v
    write_summary(out / "summary.md", a, runs, total)

    print((out / "summary.md").read_text())
    failed = [f"{r['test']}:{r['seed']}" for r in runs if not r["passed"]]
    if a.compare_with:
        # Same seed, same stimulus: another simulator must see exactly the same events.
        for r in runs:
            other = Path(a.compare_with) / Path(r["dir"]).name / "coverage.json"
            mine = (r["report"] or {}).get("coverage")
            theirs = json.loads(other.read_text())["coverage"] if other.exists() else None
            if mine is None or mine != theirs:
                print(f"compare: {r['test']} seed {r['seed']} differs from {other}")
                failed.append(f"{r['test']}:{r['seed']}(compare)")
            else:
                print(f"compare: {r['test']} seed {r['seed']} coverage identical to {other}")
    if failed:
        print(f"SIM_RANDOM FAIL: {' '.join(failed)}")
        return 1
    ncyc = sum(r["report"]["cycles"] for r in runs)
    print(f"SIM_RANDOM PASS: {len(runs)} runs, {ncyc} cycles, "
          f"{total.get('results_checked', 0)} results checked, 0 mismatches")
    return 0


if __name__ == "__main__":
    sys.exit(main())
