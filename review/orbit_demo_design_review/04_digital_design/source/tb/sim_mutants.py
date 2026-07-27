#!/usr/bin/env python3
"""Negative control for the sim benches: each must FAIL on broken RTL.

Every mutant is a copy of the RTL directory with one deliberate, SPEC-violating
change (one text substitution, or a few that together make one bug). The
substitution text must be found exactly as often as listed; if the RTL moved on
and a pattern no longer matches, that mutant is reported as STALE and the run
fails, rather than silently testing an unmodified copy.

For each mutant:
  directed  tb/tb_orbit_demo.v under Icarus (+maxerr=1); killed if it prints
            TB_ORBIT_DEMO FAIL (a compile error is an invalid mutant, not a kill)
  random    tb/cocotb/run_random.py, one seed of --random-cycles cycles; killed
            if the model comparison reports at least one mismatch (a coverage
            shortfall alone does not count as a kill)

Exit status is non-zero unless every mutant is killed by both benches.
Writes <out>/summary.md and per-mutant logs.
"""

import argparse
import concurrent.futures
import json
import shutil
import subprocess
import sys
from pathlib import Path

RTL_FILES = ("orbit_keep_reg.v", "orbit_mac_lane.v", "orbit_thermal_tmr.v", "orbit_demo.v")

TMR = "orbit_thermal_tmr.v"
LANE = "orbit_mac_lane.v"
TOP = "orbit_demo.v"

# name: (description, [(file, old, new, expected count), ...])
MUTANTS = {
    "therm_unsigned": ("temperature compared unsigned (negative readings look hot)", [
        (TMR, "wire signed [7:0] t = temp_c;", "wire [7:0] t = temp_c;", 1)]),
    "throttle_gt": ("throttle at > 80 instead of >= 80", [
        (TMR, "(t >= T_THROTTLE)", "(t > T_THROTTLE)", 1)]),
    "stop_gt": ("stop at > 95 instead of >= 95", [
        (TMR, "t >= T_STOP", "t > T_STOP", 1)]),
    "recover_lt_throttle": ("THROTTLE recovers at < 70 instead of <= 70", [
        (TMR, "S_THROTTLE: nxt = (t <= T_RECOVER)", "S_THROTTLE: nxt = (t < T_RECOVER)", 1)]),
    "recover_lt_stop": ("STOP recovers at < 70 instead of <= 70", [
        (TMR, "default:    nxt = (t <= T_RECOVER)", "default:    nxt = (t < T_RECOVER)", 1)]),
    "invalid_ignored": ("invalid sensor reading does not force STOP", [
        (TMR, "if (!temp_valid || t >= T_STOP)", "if (t >= T_STOP)", 1)]),
    "stop_to_throttle": ("STOP falls back to THROTTLE at >= 80 instead of holding", [
        (TMR, "default:    nxt = (t <= T_RECOVER)  ? S_NORMAL   : S_STOP;",
         "default:    nxt = (t <= T_RECOVER)  ? S_NORMAL   : (t >= T_THROTTLE) ? S_THROTTLE : S_STOP;", 1)]),
    "reset_normal": ("reset lands in NORMAL instead of STOP", [
        (TMR, ".RESET_VAL(S_STOP)", ".RESET_VAL(S_NORMAL)", 3)]),
    "phase_not_forced": ("throttle phase not forced to 0 outside THROTTLE", [
        (TMR, "phase <= (voted == S_THROTTLE) ? ~phase : 1'b0;",
         "phase <= (voted == S_THROTTLE) ? ~phase : phase;", 1)]),
    "throttle_every_cycle": ("THROTTLE admits every cycle", [
        (TMR, "((voted == S_THROTTLE) & ~phase)", "(voted == S_THROTTLE)", 1)]),
    "throttle_first_blocks": ("first THROTTLE cycle blocks (admit = phase)", [
        (TMR, "((voted == S_THROTTLE) & ~phase)", "((voted == S_THROTTLE) & phase)", 1)]),
    "zext_product": ("product zero-extended instead of sign-extended", [
        (LANE, "prod32 = {{16{prod[15]}}, prod};", "prod32 = {16'd0, prod};", 1)]),
    "first_ignored": ("in_first does not restart the sum (both copies)", [
        (LANE, "(first ? 32'd0 : acc_a)", "acc_a", 1),
        (LANE, "(first ? 32'd0 : acc_b)", "acc_b", 1)]),
    "result_from_old_acc": ("result register loads the pre-beat sum (both copies)", [
        (LANE, ".d(clr ? 32'd0 : acc_a_sum), .q(res_a)", ".d(clr ? 32'd0 : acc_a), .q(res_a)", 1),
        (LANE, ".d(clr ? 32'd0 : acc_b_sum), .q(res_b)", ".d(clr ? 32'd0 : acc_b), .q(res_b)", 1)]),
    "clear_keeps_acc": ("clear_fault does not zero the accumulators", [
        (LANE, "wire acc_en = clr | mac_en;", "wire acc_en = mac_en;", 1)]),
    "clear_keeps_result": ("clear_fault does not zero the result registers", [
        (LANE, "wire res_en = clr | (mac_en & last);", "wire res_en = mac_en & last;", 1)]),
    "clear_keeps_out_valid": ("clear_fault does not empty the output buffer", [
        (TOP, "        end else if (clear_fault) begin\n            fault_q     <= 1'b0;\n            out_valid_q <= 1'b0;\n",
         "        end else if (clear_fault) begin\n            fault_q     <= 1'b0;\n", 1)]),
    "reset_keeps_out_valid": ("reset does not empty the output buffer", [
        (TOP, "        if (!rst_n) begin\n            fault_q     <= 1'b0;\n            out_valid_q <= 1'b0;\n",
         "        if (!rst_n) begin\n            fault_q     <= 1'b0;\n", 1)]),
    "ready_during_clear": ("in_ready not held low while clear_fault", [
        (TOP, "~mismatch & ~clear_fault &", "~mismatch &", 1)]),
    "nonlast_not_blocked": ("full buffer blocks only in_last beats", [
        (TOP, "(~out_valid_q | out_ready);", "(~out_valid_q | out_ready | ~in_last);", 1)]),
    "bubble": ("no same-cycle drain and refill (in_ready ignores out_ready)", [
        (TOP, "(~out_valid_q | out_ready);", "~out_valid_q;", 1)]),
    "drop_on_back_to_back": ("out_fire wins over a same-cycle in_last (result dropped)", [
        (TOP, "            if (in_fire && in_last)\n                out_valid_q <= 1'b1;\n"
              "            else if (out_fire)\n                out_valid_q <= 1'b0;\n",
         "            if (out_fire)\n                out_valid_q <= 1'b0;\n"
         "            else if (in_fire && in_last)\n                out_valid_q <= 1'b1;\n", 1)]),
    "no_drain_in_stop": ("output buffer cannot drain while STOP", [
        (TOP, "assign out_valid = out_valid_q & ~fault_q & ~mismatch;",
         "assign out_valid = out_valid_q & ~fault_q & ~mismatch & ~therm_state[1];", 1)]),
    "shutdown_from_bit0": ("shutdown_req taken from the wrong state bit", [
        (TOP, "assign shutdown_req = therm_state[1];", "assign shutdown_req = therm_state[0];", 1)]),
    "lanes_reversed": ("out_data lanes in reverse order", [
        (TOP, ".result   (out_data[32*i +: 32]),", ".result   (out_data[32*(LANES-1-i) +: 32]),", 1)]),
    "b_lane_rotated": ("lane i multiplies by lane i+1's b operand", [
        (TOP, ".b        (in_b[8*i +: 8]),", ".b        (in_b[8*((i+1)%LANES) +: 8]),", 1)]),
}


def make_mutant(rtl_dir, out_dir, edits):
    out_dir.mkdir(parents=True, exist_ok=True)
    for f in RTL_FILES:
        shutil.copyfile(rtl_dir / f, out_dir / f)
    for f, old, new, count in edits:
        p = out_dir / f
        text = p.read_text()
        found = text.count(old)
        if found != count:
            return f"pattern found {found}x in {f}, expected {count}x: {old.splitlines()[0]!r}"
        p.write_text(text.replace(old, new))
    return None


def run(cmd, log, cwd=None, timeout=900):
    with open(log, "w") as f:
        try:
            r = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, cwd=cwd, timeout=timeout)
            return r.returncode
        except subprocess.TimeoutExpired:
            f.write("\nTIMEOUT\n")
            return -1


def check_directed(name, mdir, tb, iverilog):
    srcs = [str(mdir / "rtl" / f) for f in RTL_FILES]
    vvp = mdir / "tb.vvp"
    rc = run(iverilog + ["-o", str(vvp), tb] + srcs, mdir / "directed_build.log")
    if rc != 0:
        return "INVALID (compile error)"
    run(["vvp", "-n", str(vvp), "+maxerr=1"], mdir / "directed.log")
    log = (mdir / "directed.log").read_text(errors="replace")
    if "TB_ORBIT_DEMO FAIL" in log:
        first = next((ln.strip() for ln in log.splitlines() if ln.startswith("ERROR")), "")
        return "KILLED" + (f": {first[:150]}" if first else "")
    if "TB_ORBIT_DEMO PASS" in log:
        return "SURVIVED"
    return "INVALID (no verdict)"


def check_random(name, mdir, python, runner, cycles):
    srcs = [str(mdir / "rtl" / f) for f in RTL_FILES]
    out = mdir / "random"
    run([python, runner, "--out", str(out), "--sources"] + srcs +
        ["--seeds", "1", "--cycles", str(cycles), "--soak-seeds"], mdir / "random.log")
    cov = out / "random_workload_seed1" / "coverage.json"
    if not cov.exists():
        return "INVALID (no report)"
    rep = json.loads(cov.read_text())
    if rep["errors"] > 0:
        return f"KILLED: {rep['errors']} mismatches in {rep['cycles']} cycles"
    return "SURVIVED"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rtl-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--tb", default="tb/tb_orbit_demo.v")
    ap.add_argument("--cocotb-python", default="tabbypy3")
    ap.add_argument("--random-cycles", type=int, default=5000)
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--only", nargs="*", help="run only these mutants")
    a = ap.parse_args()

    rtl_dir = Path(a.rtl_dir).resolve()
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    tb = str(Path(a.tb).resolve())
    runner = str(Path(__file__).resolve().parent / "cocotb" / "run_random.py")
    iverilog = ["iverilog", "-g2005", "-Wno-timescale"]
    names = a.only or list(MUTANTS)

    def one(name):
        desc, edits = MUTANTS[name]
        mdir = out / name
        if mdir.exists():
            shutil.rmtree(mdir)
        stale = make_mutant(rtl_dir, mdir / "rtl", edits)
        if stale:
            return name, desc, f"STALE ({stale})", "STALE"
        d = check_directed(name, mdir, tb, iverilog)
        r = check_random(name, mdir, a.cocotb_python, runner, a.random_cycles)
        return name, desc, d, r

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, a.jobs)) as ex:
        results = list(ex.map(one, names))

    lines = ["# sim mutation negative control", "",
             f"RTL: {a.rtl_dir}; directed bench {a.tb} (+maxerr=1); random bench: "
             f"1 seed x {a.random_cycles} cycles.", "",
             "| mutant | injected bug | directed | random |", "|---|---|---|---|"]
    ok = True
    for name, desc, d, r in results:
        lines.append(f"| {name} | {desc} | {d} | {r} |")
        if not (d.startswith("KILLED") and r.startswith("KILLED")):
            ok = False
    kd = sum(1 for _n, _d, d, _r in results if d.startswith("KILLED"))
    kr = sum(1 for _n, _d, _dd, r in results if r.startswith("KILLED"))
    lines += ["", f"directed bench killed {kd}/{len(results)}, random bench killed {kr}/{len(results)}"]
    text = "\n".join(lines) + "\n"
    (out / "summary.md").write_text(text)
    print(text)
    print("SIM_MUTANTS PASS: every mutant killed by both benches" if ok else
          "SIM_MUTANTS FAIL: a mutant survived or could not be built")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
