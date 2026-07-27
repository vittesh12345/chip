#!/usr/bin/env python3
"""Run the SymbiYosys tasks of the generated fault-injection scenarios.

Reads <dir>/<scenario>/tasks.tsv (written by fault/gen_fault_copies.py),
runs every task one after another (`sby -f <dir>/<scenario>/fault.sby <task>`;
a k-induction task uses two solver processes), compares the final status with
the expected one, and writes <out>.json and <out>.md. For a task that fails
(expected for the negative scenarios) the failing assertion and a short trace
of the counterexample are recorded. Exit status 1 if any task ended with a
status other than the expected one (an ERROR or a timeout never counts as an
expected FAIL).
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time

# Harness signals shown in counterexample excerpts.
TRACE_SIGNALS = ["rst_n", "clear_fault", "fi_fire", "in_valid", "in_last", "out_ready",
                 "in_ready_r", "in_ready_f", "out_valid_r", "out_valid_f",
                 "out_data_r", "out_data_f", "mismatch_f", "fault_f"]


def read_vcd(path):
    """{signal: {time: value}} for the top-level signals of the harness."""
    ids, scope, vals, t = {}, [], {}, 0
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("$scope"):
                scope.append(line.split()[2])
            elif line.startswith("$upscope"):
                scope.pop()
            elif line.startswith("$var"):
                p = line.split()
                if len(scope) == 1:
                    ids.setdefault(p[3], []).append(p[4])
            elif line.startswith("#"):
                t = int(line[1:])
            elif line and line[0] in "01xz" and len(line) > 1 and not line.startswith("$"):
                for n in ids.get(line[1:], []):
                    vals.setdefault(n, {})[t] = line[0]
            elif line.startswith("b"):
                v, i = line[1:].split()
                for n in ids.get(i, []):
                    vals.setdefault(n, {})[t] = v
    return vals


def value_at(series, t):
    best = None
    for tt in sorted(series):
        if tt <= t:
            best = series[tt]
    return best


def trace_excerpt(vcd, steps):
    """Text table of TRACE_SIGNALS at every step (smtbmc writes step k at time 10k)."""
    vals = read_vcd(vcd)
    # Show out_data as the lane in which the two designs differ first (else lane 0).
    lane = 0
    for k in range(steps + 1):
        r, f = value_at(vals.get("out_data_r", {}), 10 * k), value_at(vals.get("out_data_f", {}), 10 * k)
        if r and f and r != f and "x" not in r + f:
            ri, fi = int(r, 2), int(f, 2)
            lane = next(i for i in range(4) if (ri >> 32 * i) & 0xffffffff != (fi >> 32 * i) & 0xffffffff)
            break
    cols = [s for s in TRACE_SIGNALS if s in vals]
    head = ["step"] + [("%s[l%d]" % (c, lane)) if c.startswith("out_data") else c for c in cols]
    rows = [head]
    for k in range(steps + 1):
        row = [str(k)]
        for c in cols:
            v = value_at(vals[c], 10 * k)
            if v is None:
                row.append("-")
            elif c.startswith("out_data"):
                row.append("x" if "x" in v else "%08x" % ((int(v, 2) >> (32 * lane)) & 0xffffffff))
            else:
                row.append(v if len(v) == 1 else ("x" if "x" in v else "%x" % int(v, 2)))
        rows.append(row)
    w = [max(len(r[i]) for r in rows) for i in range(len(head))]
    return "\n".join("  ".join(r[i].rjust(w[i]) for i in range(len(r))) for r in rows)


def run_task(sby, scen_dir, task, timeout):
    work = os.path.join(scen_dir, "fault_" + task)
    log = os.path.join(scen_dir, "fault_%s.console.log" % task)
    t0 = time.time()
    try:
        with open(log, "w") as fh:
            rc = subprocess.run([sby, "-f", "fault.sby", task], cwd=scen_dir, stdout=fh,
                                stderr=subprocess.STDOUT, timeout=timeout).returncode
        status = "ERROR"
        sf = os.path.join(work, "status")
        if os.path.exists(sf):
            with open(sf) as fh:
                status = (fh.read().split() or ["ERROR"])[0]
    except subprocess.TimeoutExpired:
        rc, status = None, "TIMEOUT"
    secs = time.time() - t0
    res = dict(status=status, rc=rc, secs=round(secs, 1), work=work)
    lf = os.path.join(work, "logfile.txt")
    text = open(lf).read() if os.path.exists(lf) else ""
    m = re.search(r"failed assertion fi_harness\.(\w+) at \S+ step (\d+)", text)
    if m:
        res["failed_assertion"], res["fail_step"] = m.group(1), int(m.group(2))
        vcd = os.path.join(work, "engine_0", "trace.vcd")
        if os.path.exists(vcd):
            res["trace"] = trace_excerpt(vcd, int(m.group(2)))
    res["induction"] = "Temporal induction successful" in text
    smt2 = os.path.join(work, "model", "design_smt2.smt2")
    model = open(smt2).read() if os.path.exists(smt2) else ""
    res["assertions"] = sorted(set(re.findall(r"yosys-smt2-assert \d+ (\S+)", model)))
    covers = set(re.findall(r"yosys-smt2-cover \d+ (\S+)", model))
    reached = set(re.findall(r"Reached cover statement in step \d+ at fi_harness: (\w+)", text))
    res["covers_reached"] = sorted(reached)
    res["covers_unreached"] = sorted(covers - reached)
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dir", required=True, help="generated scenarios ($(BUILD)/fault/formal)")
    ap.add_argument("--scenarios", default="all")
    ap.add_argument("--tasks", default="all", help="comma-separated task names to run (default all)")
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("--sby", default="sby")
    ap.add_argument("--out", required=True, help="output prefix for .json / .md")
    args = ap.parse_args()

    scen = sorted(d for d in os.listdir(args.dir) if os.path.exists(os.path.join(args.dir, d, "tasks.tsv")))
    if args.scenarios != "all":
        want = args.scenarios.split(",")
        missing = [s for s in want if s not in scen]
        if missing:
            print("run_formal.py: scenarios not generated: %s" % missing, file=sys.stderr)
            return 1
        scen = want
    tasks = []
    for s in scen:
        with open(os.path.join(args.dir, s, "tasks.tsv")) as fh:
            for line in fh:
                name, task, expect, desc = line.rstrip("\n").split("\t")
                if args.tasks == "all" or task in args.tasks.split(","):
                    tasks.append(dict(scenario=name, task=task, expect=expect, desc=desc))

    bad = 0
    for t in tasks:
        r = run_task(args.sby, os.path.join(args.dir, t["scenario"]), t["task"], args.timeout)
        t.update(r)
        t["ok"] = (t["status"] == t["expect"])
        # A cover task passes only if every cover was reached.
        if t["task"] == "cover" and t["covers_unreached"]:
            t["ok"] = False
        # An expected failure must come from a real counterexample.
        if t["expect"] == "FAIL" and "failed_assertion" not in t:
            t["ok"] = False
        bad += not t["ok"]
        extra = ""
        if "failed_assertion" in t:
            extra = "  %s at step %d" % (t["failed_assertion"], t["fail_step"])
        elif t["task"] == "cover":
            extra = "  %d covers reached, %d unreached" % (len(t["covers_reached"]), len(t["covers_unreached"]))
        print("[fault] %-16s %-6s %-7s (expected %s, %5.1fs)%s%s" % (
            t["scenario"], t["task"], t["status"], t["expect"], t["secs"], extra,
            "" if t["ok"] else "   <-- UNEXPECTED, see %s/logfile.txt" % t["work"]), flush=True)

    with open(args.out + ".json", "w") as fh:
        json.dump(tasks, fh, indent=1)
    with open(args.out + ".md", "w") as fh:
        fh.write("| scenario | task | result | expected | time | detail |\n|---|---|---|---|---|---|\n")
        for t in tasks:
            if "failed_assertion" in t:
                det = "`%s` fails at step %d" % (t["failed_assertion"], t["fail_step"])
            elif t["task"] == "cover":
                det = "%d/%d covers reached" % (len(t["covers_reached"]),
                                                len(t["covers_reached"]) + len(t["covers_unreached"]))
            elif t["task"] == "prove":
                det = "%d assertions, %s" % (len(t.get("assertions", [])),
                                             "k-induction closed" if t["induction"] else "no induction proof")
            else:
                det = ""
            fh.write("| %s | %s | %s | %s | %.1fs | %s |\n" % (
                t["scenario"], t["task"], t["status"] if t["ok"] else "**%s (unexpected)**" % t["status"],
                t["expect"], t["secs"], det))
    print("[fault] formal: %d tasks, %d unexpected; see %s.md" % (len(tasks), bad, args.out))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
