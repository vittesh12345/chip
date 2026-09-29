#!/usr/bin/env python3
"""Driver of the synth-area equivalence check (netlist vs RTL).

1. Main check, in <out>/equiv/: synth/equiv_cut.ys cuts every flip-flop of the
   RTL (gold) and of the synthesized netlist (gate) into input/output pairs,
   then synth/equiv.sby proves every output and next-state function equal,
   one SymbiYosys task per partition (lane0..lane3, ctrl). All must PASS.
2. Negative controls, in <out>/equiv_neg/<mutant>/: the same netlist against a
   deliberately changed copy of the RTL (synth/make_variant.py). The partition
   that contains the change must FAIL, i.e. the method finds the difference:
     mut_throttle  T_THROTTLE 80 -> 81      (task ctrl)
     mut_zext      product zero-extended    (task lane0)

usage: run_equiv.py --netlist <v> --out <dir> [--jobs N] <RTL files...>
Writes <out>/equiv_result.txt; exit 0 only if (1) passes and every mutant fails.
"""

import argparse
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TASKS = ["lane0", "lane1", "lane2", "lane3", "ctrl"]
MUTANTS = [("mut_throttle", "ctrl", "T_THROTTLE 80 -> 81 (orbit_demo.v)"),
           ("mut_zext", "lane0", "product zero- instead of sign-extended (orbit_mac_lane.v)")]


def prepare(workdir, netlist, rtl, yosys):
    """Cut both designs into gold_gate.il; returns the number of cut register ports."""
    if os.path.isdir(workdir):
        shutil.rmtree(workdir)
    os.makedirs(workdir)
    shutil.copy(netlist, os.path.join(workdir, "gate.v"))
    shutil.copy(os.path.join(HERE, "equiv.sby"), os.path.join(workdir, "equiv.sby"))
    res = subprocess.run([yosys, "-q", "-l", "equiv_prep.log", "-s", os.path.join(HERE, "equiv_cut.ys")]
                         + [os.path.abspath(f) for f in rtl],
                         cwd=workdir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if res.returncode != 0:
        tail = [l for l in res.stdout.splitlines() if "undriven" not in l][-10:]
        raise RuntimeError("equiv_cut.ys failed in %s:\n%s" % (workdir, "\n".join(tail)))

    def ports(side):
        with open(os.path.join(workdir, side + "_ports.txt")) as fh:
            return sorted(l.strip().split("/", 1)[1] for l in fh if "/" in l)
    gold, gate = ports("gold"), ports("gate")
    if gold != gate:
        raise RuntimeError("cut port lists differ between RTL and netlist")
    return sum(1 for p in gold if p.endswith(".q"))


def task_status(workdir, task):
    """PASS / FAIL / ERROR from the status file SymbiYosys writes per task."""
    path = os.path.join(workdir, "equiv_%s" % task, "status")
    try:
        with open(path) as fh:
            return fh.read().split()[0]
    except (OSError, IndexError):
        return "ERROR"


def run_sby(workdir, sby, jobs, tasks):
    cmd = [sby, "-f", "-j", str(jobs), "equiv.sby"] + tasks
    with open(os.path.join(workdir, "sby.log"), "w") as log:
        subprocess.run(cmd, cwd=workdir, stdout=log, stderr=subprocess.STDOUT)
    return {t: task_status(workdir, t) for t in tasks}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--netlist", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--yosys", default="yosys")
    ap.add_argument("--sby", default="sby")
    ap.add_argument("rtl", nargs="+")
    args = ap.parse_args()

    lines = ["Equivalence: synthesized netlist vs RTL (synth/run_equiv.py)", "",
             "method: register-correspondence combinational equivalence; every flip-flop cut",
             "        into Q input / D output by name (synth/equiv_cut.ys), outputs proven",
             "        equal per partition by SymbiYosys smtbmc + bitwuzla (synth/equiv.sby)",
             "netlist: %s" % args.netlist, ""]
    problems = []

    main_dir = os.path.join(args.out, "equiv")
    try:
        nq = prepare(main_dir, args.netlist, args.rtl, args.yosys)
        lines.append("register ports cut (incl. alias names): %d, identical names in RTL and netlist" % nq)
        t0 = time.time()
        res = run_sby(main_dir, args.sby, args.jobs, TASKS)
        lines.append("tasks (%d in parallel, %.0f s wall):" % (args.jobs, time.time() - t0))
        for t in TASKS:
            st = res[t]
            lines.append("  task %-6s %s" % (t, st))
            if st != "PASS":
                problems.append("task %s: %s (see %s/equiv_%s/logfile.txt)" % (t, st, main_dir, t))
    except RuntimeError as exc:
        problems.append(str(exc))
    lines.append("")

    lines.append("negative controls (must FAIL):")
    for mut, task, what in MUTANTS:
        mdir = os.path.join(args.out, "equiv_neg", mut)
        rtl_dir = os.path.join(mdir, "rtl")
        os.makedirs(rtl_dir, exist_ok=True)
        subprocess.run([sys.executable, os.path.join(HERE, "make_variant.py"), mut, rtl_dir] + args.rtl,
                       check=True, stdout=subprocess.DEVNULL)
        mrtl = [os.path.join(rtl_dir, os.path.basename(f)) for f in args.rtl]
        work = os.path.join(mdir, "work")
        try:
            prepare(work, args.netlist, mrtl, args.yosys)
            st = run_sby(work, args.sby, 1, [task])[task]
        except RuntimeError as exc:
            st = "ERROR"
            problems.append("%s: %s" % (mut, exc))
        ok = st == "FAIL"
        lines.append("  %-13s %-58s task %-5s %s" % (mut, what, task,
                                                     "FAIL (detected, as required)" if ok else st + " (NOT detected)"))
        if not ok and st != "ERROR":
            problems.append("%s: task %s returned %s, expected FAIL" % (mut, task, st))
    lines.append("")
    if problems:
        lines.extend("ERROR: " + p for p in problems)
    lines.append("EQUIV %s" % ("PASS: netlist equivalent to RTL; both mutants detected"
                              if not problems else "FAIL"))
    text = "\n".join(lines) + "\n"
    sys.stdout.write(text)
    with open(os.path.join(args.out, "equiv_result.txt"), "w") as fh:
        fh.write(text)
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
