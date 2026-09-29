#!/usr/bin/env python3
"""Generate a negative-control copy of the RTL for the synth area.

Storage-retention controls (orbit_keep_reg.v):
  nokeep    the (* keep_hierarchy *) module attribute is removed
  regkeep   the module attribute is removed and (* keep *) is put on the
            register itself (output reg q), i.e. a signal attribute only
Equivalence-check controls (functional changes the check must detect):
  mut_throttle  orbit_demo.v: default T_THROTTLE 80 -> 81 degrees C
  mut_zext      orbit_mac_lane.v: product zero- instead of sign-extended
All other files are copied unchanged.

usage: make_variant.py <variant> <out dir> <RTL files...>
Writes the copies to <out dir>/ and the change to <out dir>/variant.diff.
Fails if the expected text is not found exactly once (so a change in the
production RTL cannot silently turn a negative control into a no-op).
"""

import difflib
import os
import re
import sys

KEEP_HIER = (r"^\(\*\s*keep_hierarchy\s*\*\)\s*\n", "")
REG_KEEP = (r"^(\s*)(output\s+reg\s+\[W-1:0\]\s+q\b)", r"\1(* keep *) \2")

# variant -> (file to change, [(regex, replacement), ...]); each regex must
# match exactly once.
VARIANTS = {
    "nokeep": ("orbit_keep_reg.v", [KEEP_HIER]),
    "regkeep": ("orbit_keep_reg.v", [KEEP_HIER, REG_KEEP]),
    "mut_throttle": ("orbit_demo.v",
                     [(r"(parameter\s+signed\s+\[7:0\]\s+T_THROTTLE\s*=\s*)8'sd80\b", r"\g<1>8'sd81")]),
    "mut_zext": ("orbit_mac_lane.v",
                 [(r"\{\{16\{prod\[15\]\}\},\s*prod\}", "{16'd0, prod}")]),
}


def transform(variant, text):
    for pattern, repl in VARIANTS[variant][1]:
        text, n = re.subn(pattern, repl, text, flags=re.M)
        if n != 1:
            raise SystemExit("make_variant: %s: pattern %r matched %d times, expected 1"
                             % (variant, pattern, n))
    return text


def main():
    if len(sys.argv) < 4 or sys.argv[1] not in VARIANTS:
        print(__doc__, file=sys.stderr)
        return 2
    variant, out, srcs = sys.argv[1], sys.argv[2], sys.argv[3:]
    os.makedirs(out, exist_ok=True)
    diff = []
    touched = 0
    for src in srcs:
        with open(src) as fh:
            text = fh.read()
        new = text
        if os.path.basename(src) == VARIANTS[variant][0]:
            new = transform(variant, text)
            touched += 1
            diff = difflib.unified_diff(text.splitlines(True), new.splitlines(True),
                                        fromfile=src, tofile=os.path.join(out, os.path.basename(src)))
            diff = list(diff)
        with open(os.path.join(out, os.path.basename(src)), "w") as fh:
            fh.write(new)
    if touched != 1:
        raise SystemExit("make_variant: %s not among the RTL files" % VARIANTS[variant][0])
    with open(os.path.join(out, "variant.diff"), "w") as fh:
        fh.writelines(diff)
    sys.stdout.writelines(diff)
    return 0


if __name__ == "__main__":
    sys.exit(main())
