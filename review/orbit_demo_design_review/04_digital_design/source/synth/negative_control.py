#!/usr/bin/env python3
"""Storage-retention negative control for the synth area.

Synthesizes two generated variants of the RTL with the production script
(synth/synth_generic.ys) and runs the storage audit on each:

  nokeep   (* keep_hierarchy *) removed from orbit_keep_reg. Expected: Yosys
           merges the three thermal copies (identical D, clock, reset), the
           flip-flop count drops below the baseline and the audit FAILS on the
           thermal triple with "copies merged". If this does not happen, the
           control proves nothing and this script fails.
  regkeep  keep_hierarchy removed and (* keep *) put on the register only.
           Observation (the brief says signal attributes alone initially let
           copies merge); reported, not required either way.

usage: negative_control.py --out <dir> --script <synth_generic.ys>
                           --baseline <synth_stat.json> <RTL files...>
Writes <dir>/<variant>/... and <dir>/negative_control.txt.
"""

import argparse
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import storage_audit  # noqa: E402

FF_TYPE = re.compile(r"^\$_(DFF|DFFE|SDFF|SDFFE|SDFFCE|DFFSR|DFFSRE|ALDFF|ALDFFE)_[NP01]+_$")


def ff_bits(stat_json):
    with open(stat_json) as fh:
        design = json.load(fh)["design"]
    return sum(n for t, n in design["num_cells_by_type"].items() if FF_TYPE.match(t)), design["num_cells"]


def run_variant(variant, out, script, rtl, yosys):
    vdir = os.path.join(out, variant)
    rtl_dir = os.path.join(vdir, "rtl")
    os.makedirs(rtl_dir, exist_ok=True)
    subprocess.run([sys.executable, os.path.join(HERE, "make_variant.py"), variant, rtl_dir] + rtl,
                   check=True, stdout=subprocess.DEVNULL)
    srcs = [os.path.abspath(os.path.join(rtl_dir, os.path.basename(f))) for f in rtl]
    res = subprocess.run([yosys, "-q", "-l", "synth.log", "-s", os.path.abspath(script)] + srcs,
                         cwd=vdir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if res.returncode != 0:
        print(res.stdout)
        raise SystemExit("negative_control: yosys failed on variant %s (see %s/synth.log)" % (variant, vdir))
    ok, text, info = storage_audit.audit(os.path.join(vdir, "orbit_demo_synth.json"), None, 4, 521,
                                         ["fault_q", "out_valid_q", "u_thermal.phase"], "clk")
    with open(os.path.join(vdir, "storage_audit.txt"), "w") as fh:
        fh.write(text)
    thermal = [g for g in info["groups"] if g[0] == "thermal triple"][0]
    merged = any("thermal triple" in e and "(copies merged)" in e for e in info["errors"])
    nff, ncells = ff_bits(os.path.join(vdir, "synth_stat.json"))
    with open(os.path.join(rtl_dir, "variant.diff")) as fh:
        diff = [l.rstrip("\n") for l in fh if l[:1] in "+-" and l[:3] not in ("+++", "---")]
    return {"variant": variant, "audit_ok": ok, "ff_bits": nff, "cells": ncells,
            "thermal_ok_bits": thermal[3], "thermal_expected": thermal[4],
            "thermal_merged": merged, "diff": diff,
            "groups_pass": sum(1 for g in info["groups"] if g[6])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--script", required=True)
    ap.add_argument("--baseline", required=True, help="synth_stat.json of the production run")
    ap.add_argument("--yosys", default="yosys")
    ap.add_argument("rtl", nargs="+")
    args = ap.parse_args()

    base_ff, base_cells = ff_bits(args.baseline)
    results = [run_variant(v, args.out, args.script, args.rtl, args.yosys) for v in ("nokeep", "regkeep")]

    lines = ["Storage-retention negative control (synth/negative_control.py)", "",
             "baseline (production RTL, keep_hierarchy): %d flip-flop bits, %d cells" % (base_ff, base_cells), ""]
    lines.append("%-8s %8s %7s %-16s %-11s %s" % ("variant", "FF bits", "cells", "thermal copies", "audit", "groups"))
    for r in results:
        lines.append("%-8s %8d %7d %-16s %-11s %d/9 pass" % (
            r["variant"], r["ff_bits"], r["cells"],
            "MERGED" if r["thermal_merged"] else "distinct (%d/%d)" % (r["thermal_ok_bits"], r["thermal_expected"]),
            "PASS" if r["audit_ok"] else "FAIL", r["groups_pass"]))
    lines.append("")
    for r in results:
        lines.append("%s change to orbit_keep_reg.v:" % r["variant"])
        lines.extend("    " + d for d in r["diff"])
    lines.append("")

    nk, rk = results
    problems = []
    if nk["audit_ok"]:
        problems.append("nokeep: the audit PASSED, so it did not detect the missing keep_hierarchy")
    if not nk["thermal_merged"]:
        problems.append("nokeep: the thermal copies were not merged; the control shows nothing")
    if nk["ff_bits"] >= base_ff:
        problems.append("nokeep: flip-flop count did not drop (%d >= %d)" % (nk["ff_bits"], base_ff))
    lines.append("nokeep:  keep_hierarchy removed -> thermal copies %s, %d -> %d flip-flop bits, audit %s (%s)"
                 % ("merged" if nk["thermal_merged"] else "NOT merged", base_ff, nk["ff_bits"],
                    "FAIL" if not nk["audit_ok"] else "PASS",
                    "expected" if not problems else "UNEXPECTED"))
    lines.append("regkeep: (* keep *) on the register alone %s the merge (%d flip-flop bits, audit %s)"
                 % ("does NOT prevent" if rk["thermal_merged"] else "prevents",
                    rk["ff_bits"], "PASS" if rk["audit_ok"] else "FAIL"))
    lines.append("")
    if problems:
        lines.extend("ERROR: " + p for p in problems)
    lines.append("NEGATIVE_CONTROL %s" % ("PASS" if not problems else "FAIL"))
    text = "\n".join(lines) + "\n"
    sys.stdout.write(text)
    with open(os.path.join(args.out, "negative_control.txt"), "w") as fh:
        fh.write(text)
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
