#!/usr/bin/env python3
"""Summarise per-corner OpenSTA logs written by pd/sta_corners.tcl.

Usage: corners_summary.py --period NS --out FILE LOG [LOG ...]
Prints and writes a table: corner, liberty, setup WNS/TNS, hold WNS/TNS,
minimum period, followed by the worst setup path endpoints per corner.
"""

import argparse
import re
import sys


def grab(pat, text):
    m = re.search(pat, text)
    return m.group(1) if m else "n/a"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--period", default="?")
    ap.add_argument("--note", action="append", default=[])
    ap.add_argument("--out", required=True)
    ap.add_argument("logs", nargs="+")
    a = ap.parse_args()

    lines = ["Multi-corner STA of the routed orbit_demo (information only)",
             "",
             f"Constraint: the committed SDC, clock period {a.period} ns. The design was optimised by",
             "ORFS at the TT corner only; the other corners re-time the same routed database.",
             "Parasitics: ORFS OpenRCX SPEF (nominal rules) for every corner.", ""]
    lines += a.note + ([""] if a.note else [])
    lines.append(f"{'corner':13s} {'liberty':36s} {'setup WNS':>10s} {'setup TNS':>10s} "
                 f"{'hold WNS':>9s} {'hold TNS':>9s} {'min period':>11s} {'fmax':>9s}")
    paths = []
    for log in a.logs:
        t = open(log, errors="replace").read()
        name = grab(r'CORNER (\S+)', t)
        lib = grab(r'CORNER \S+ liberty (\S+)', t)
        m = re.search(r'period_min = ([0-9.]+) fmax = ([0-9.]+)', t)
        lines.append(f"{name:13s} {lib:36s} {grab(r'worst slack max (-?[0-9.]+)', t):>10s} "
                     f"{grab(r'tns max (-?[0-9.]+)', t):>10s} {grab(r'worst slack min (-?[0-9.]+)', t):>9s} "
                     f"{grab(r'tns min (-?[0-9.]+)', t):>9s} {(m.group(1) + ' ns') if m else 'n/a':>11s} "
                     f"{(m.group(2) + ' MHz') if m else 'n/a':>9s}")
        sp = re.search(r'=== worst setup path ===\n(.*?)(?:=== worst hold path|\Z)', t, re.S)
        if sp:
            st = grab(r'Startpoint: (.*)', sp.group(1))
            en = grab(r'Endpoint: (.*)', sp.group(1))
            paths.append(f"  {name}: worst setup path {st} -> {en}")
    lines += ["", "(ns; negative slack = violation at that corner; min period from",
              " report_clock_min_period -include_port_paths)", ""] + paths
    text = "\n".join(lines) + "\n"
    open(a.out, "w").write(text)
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
