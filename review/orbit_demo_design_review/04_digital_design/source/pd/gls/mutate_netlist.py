#!/usr/bin/env python3
"""Make a one-cell mutant of a gate-level netlist, for the GLS sanity check.

Replaces the cell type of the N-th instance (0-based, --index) of --from with
--to, e.g. sky130_fd_sc_hd__and2_1 -> sky130_fd_sc_hd__or2_1 (same A, B, X
pins). make pd-gls-mutant simulates the mutant against the RTL and requires
the lockstep compare to report a MISMATCH: if it does not, the GLS harness is
not actually observing the netlist and its PASS means nothing.
"""

import argparse
import re
import sys


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--netlist", required=True, help="input netlist (e.g. the GLS copy orbit_demo_gl.v)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--from", dest="src", required=True, help="cell type to replace")
    ap.add_argument("--to", dest="dst", required=True, help="replacement cell type (same pins)")
    ap.add_argument("--index", type=int, default=0, help="which instance of --from (0-based)")
    a = ap.parse_args()

    text = open(a.netlist, encoding="utf-8").read()
    pat = re.compile(r'^(\s*)' + re.escape(a.src) + r'(\s+)(\S+)(\s*\()', re.M)
    hits = list(pat.finditer(text))
    if len(hits) <= a.index:
        sys.exit(f"mutate_netlist: only {len(hits)} instances of {a.src} in {a.netlist}")
    m = hits[a.index]
    text = text[:m.start()] + m.group(1) + a.dst + m.group(2) + m.group(3) + m.group(4) + text[m.end():]
    with open(a.out, "w") as f:
        f.write(text)
    print(f"mutate_netlist: instance {m.group(3)}: {a.src} -> {a.dst} (#{a.index} of {len(hits)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
