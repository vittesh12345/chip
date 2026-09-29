#!/usr/bin/env python3
"""Storage audit of a Yosys JSON netlist of orbit_demo (docs/SPEC.md sections 7-9).

Checks, on a generically synthesized netlist (Yosys internal $_*FF*_ gates or
coarse $dff-style cells), that every redundant copy of every audited storage
group is still made of its own flip-flops:

  * the nine groups of SPEC section 7: accumulator pair and result pair of each
    of the four lanes (2 x 32 bits each) and the thermal triple (3 x 2 bits);
  * every bit of every copy is driven by the Q output of a flip-flop (not a
    constant, not combinational logic, not undriven): no copy optimized away;
  * no flip-flop bit drives two copy bits (in the same or another copy): no
    shared / merged flip-flop;
  * no flip-flop of a copy has a constant D input or D tied to its own Q
    (a constant flip-flop), and every one is clocked by the top-level clock;
  * within a copy the per-bit D nets are all distinct, and for the duplicated
    pairs copy A and copy B have distinct D nets bit by bit (each copy updates
    from its own stored value, SPEC section 5). The thermal copies share one D
    net per bit by design (voted next state written back into all three,
    SPEC section 6); that is reported, not failed.

It also counts every flip-flop bit in the design (SPEC: 521) and lists the
flip-flop bits outside the nine groups (SPEC section 8: fault_q, out_valid_q,
u_thermal.phase).

The netlist may be hierarchical (orbit_keep_reg kept as a separate module by
its keep_hierarchy attribute) or flat; hierarchical netlists are flattened in
memory here, so copies are identified by their hierarchical net names
(e.g. g_lane[2].u_lane.u_res_b.q) in both cases.

Exit status: 0 when every check passes, 1 when any check fails, 2 on usage or
input errors. A text report is written with --report.
"""

import argparse
import json
import re
import sys
from collections import defaultdict

# Flip-flop cell types of the Yosys internal cell library, with the name of
# their data input / output ports. Fine-grained gates are one bit wide.
FF_FINE_RE = re.compile(r"^\$_(DFF|DFFE|SDFF|SDFFE|SDFFCE|DFFSR|DFFSRE|ALDFF|ALDFFE)_[NP01]+_$|^\$_FF_$")
FF_COARSE = {"$dff", "$dffe", "$sdff", "$sdffe", "$sdffce", "$adff", "$adffe",
             "$aldff", "$aldffe", "$dffsr", "$dffsre", "$ff"}
LATCH_RE = re.compile(r"^\$_(DLATCH|DLATCHSR|SR)_[NP01]+_$|^\$(dlatch|adlatch|dlatchsr|sr)$")
CLOCK_PORTS = ("C", "CLK")


class UnionFind:
    """Nets of the flattened netlist. Constant bits ('0', '1', 'x', 'z') are
    nodes too and always win as representative, so a net tied to a constant
    anywhere in the hierarchy reads as that constant."""

    def __init__(self):
        self.parent = {}

    def find(self, x):
        self.parent.setdefault(x, x)
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if isinstance(ra, str):          # keep a constant as the representative
            ra, rb = rb, ra
        self.parent[ra] = rb


class FlatNetlist:
    """In-memory flattening of a (possibly hierarchical) Yosys JSON netlist.

    cells:    list of dicts {name, type, conns: {port: [net, ...]}, dirs}
    netnames: {hierarchical name: [net, ...]}
    Nets are opaque keys resolved through the UnionFind; constants are strings.
    """

    def __init__(self, modules, top):
        self.modules = modules
        self.uf = UnionFind()
        self.cells = []
        self.netnames = {}
        self._next = 0
        self._walk(top, "", None)

    def _fresh(self):
        self._next += 1
        return ("n", self._next)

    def _walk(self, mname, prefix, portmap):
        mod = self.modules[mname]
        local = {}

        def net(bit):
            if isinstance(bit, str):      # constant in the JSON: "0", "1", "x", "z"
                return bit
            if bit not in local:
                local[bit] = self._fresh()
            return local[bit]

        # Connect this module's port bits to the nets of the instantiating cell.
        if portmap is not None:
            for pname, pinfo in mod["ports"].items():
                outer = portmap.get(pname)
                if outer is None:
                    continue              # unconnected port
                for inner_bit, outer_net in zip(pinfo["bits"], outer):
                    self.uf.union(net(inner_bit), outer_net)

        for nname, ninfo in mod["netnames"].items():
            self.netnames[prefix + nname] = [net(b) for b in ninfo["bits"]]

        for cname, cell in mod["cells"].items():
            conns = {p: [net(b) for b in bits] for p, bits in cell["connections"].items()}
            ctype = cell["type"]
            if ctype in self.modules and not self._is_blackbox(ctype):
                self._walk(ctype, prefix + cname + ".", conns)
            else:
                self.cells.append({"name": prefix + cname, "type": ctype, "conns": conns,
                                   "dirs": cell.get("port_directions", {})})

    def _is_blackbox(self, mname):
        attrs = self.modules[mname].get("attributes", {})
        return any(k in attrs and str(attrs[k]).strip("0") != "" for k in ("blackbox", "whitebox"))

    def rep(self, n):
        return self.uf.find(n)


def is_ff(ctype):
    return bool(FF_FINE_RE.match(ctype)) or ctype in FF_COARSE


def ff_ports(cell):
    """(clock port, D port, Q port) names of a flip-flop cell."""
    if cell["type"].startswith("$_"):
        return ("C" if "C" in cell["conns"] else None), "D", "Q"
    return ("CLK" if "CLK" in cell["conns"] else None), "D", "Q"


def spec_groups(lanes):
    """The nine audited groups of SPEC section 7 (for LANES = 4)."""
    groups = []
    for i in range(lanes):
        base = "g_lane[%d].u_lane" % i
        groups.append(("acc pair lane %d" % i, "pair", 32,
                       [base + ".u_acc_a", base + ".u_acc_b"]))
    for i in range(lanes):
        base = "g_lane[%d].u_lane" % i
        groups.append(("result pair lane %d" % i, "pair", 32,
                       [base + ".u_res_a", base + ".u_res_b"]))
    groups.append(("thermal triple", "triple", 2,
                   ["u_thermal.u_copy0", "u_thermal.u_copy1", "u_thermal.u_copy2"]))
    return groups


def net_names(flat, names_of, n):
    """Every public name of a net (e.g. fault_q and the output port fault), or
    its internal name when it has no public one."""
    if isinstance(n, str):
        return ["const " + n]
    names = names_of.get(n, [])
    out = []
    for nm, idx in sorted(names, key=lambda t: (t[0].startswith("$"), t[0])):
        if nm.startswith("$") and out:
            break
        out.append(nm if len(flat.netnames[nm]) == 1 else "%s[%d]" % (nm, idx))
    return out or ["<unnamed net>"]


def pretty_net(flat, names_of, n):
    return " = ".join(net_names(flat, names_of, n))


def audit(path, top_name, lanes, expect_ff_bits, expect_unprot, clock_name):
    with open(path) as fh:
        data = json.load(fh)
    modules = data["modules"]
    if top_name is None:
        tops = [m for m, v in modules.items()
                if str(v.get("attributes", {}).get("top", "0")).strip("0") != ""]
        if len(tops) != 1:
            raise ValueError("cannot identify the top module (use --top)")
        top_name = tops[0]
    if top_name not in modules:
        raise ValueError("top module %r not in the netlist" % top_name)

    flat = FlatNetlist(modules, top_name)
    R = flat.rep

    # Reverse name map: net -> [(name, bit index)].
    names_of = defaultdict(list)
    for nm, bits in flat.netnames.items():
        for idx, n in enumerate(bits):
            if not isinstance(n, str):
                names_of[R(n)].append((nm, idx))

    # Drivers of every net (output ports of primitive cells), and all FF bits.
    drivers = defaultdict(list)
    ff_bits = []                      # (cell, bit index)
    latches = []
    ff_types = defaultdict(int)
    for cell in flat.cells:
        for port, bits in cell["conns"].items():
            if cell["dirs"].get(port) == "output":
                for idx, n in enumerate(bits):
                    drivers[R(n)].append((cell, port, idx))
        if is_ff(cell["type"]):
            q = cell["conns"]["Q"]
            ff_types[cell["type"]] += len(q)
            ff_bits.extend((cell, i) for i in range(len(q)))
        elif LATCH_RE.match(cell["type"]):
            latches.append(cell["name"])

    # Top-level input ports drive nets too (e.g. a copy wired straight to an input).
    top_ports = modules[top_name]["ports"]
    clock_nets = set()
    for pname, pinfo in top_ports.items():
        if pinfo["direction"] == "input":
            for idx, n in enumerate(flat.netnames.get(pname, [])):
                drivers[R(n)].append(({"name": "input port " + pname, "type": "port"}, pname, idx))
            if pname == clock_name:
                clock_nets = {R(n) for n in flat.netnames.get(pname, [])}

    errors = []
    lines = []
    claimed = {}                      # (ff cell name, bit) -> "copy[bit]"
    group_rows = []

    for gname, kind, width, copies in spec_groups(lanes):
        gerr_before = len(errors)
        copy_d = []                   # per copy: list of D nets (None if unknown)
        n_ok_bits = 0
        for inst in copies:
            qname = inst + ".q"
            qnets = flat.netnames.get(qname)
            dlist = [None] * width
            if qnets is None:
                errors.append("%s: net %s not found (copy optimized away or renamed)" % (gname, qname))
                copy_d.append(dlist)
                continue
            if len(qnets) != width:
                errors.append("%s: %s is %d bits wide, expected %d" % (gname, qname, len(qnets), width))
            d_seen = {}
            for b, n in enumerate(qnets[:width]):
                tag = "%s[%d]" % (qname, b)
                n = R(n)
                if isinstance(n, str):
                    errors.append("%s: %s is the constant %s (flip-flop optimized away)" % (gname, tag, n))
                    continue
                drv = drivers.get(n, [])
                ffd = [(c, p, i) for c, p, i in drv if c.get("type") != "port" and is_ff(c["type"]) and p == "Q"]
                if len(drv) != 1 or len(ffd) != 1:
                    what = ", ".join("%s.%s[%d] (%s)" % (c["name"], p, i, c.get("type")) for c, p, i in drv) or "nothing"
                    errors.append("%s: %s is not driven by exactly one flip-flop output (driven by %s)" % (gname, tag, what))
                    continue
                cell, _, qi = ffd[0]
                key = (cell["name"], qi)
                if key in claimed:
                    errors.append("%s: %s shares flip-flop %s with %s (copies merged)"
                                  % (gname, tag, cell["name"], claimed[key]))
                    continue
                claimed[key] = tag
                clk_port, d_port, _ = ff_ports(cell)
                clk_bits = cell["conns"].get(clk_port, []) if clk_port else []
                if not clk_bits or R(clk_bits[0]) not in clock_nets:
                    errors.append("%s: %s flip-flop %s is not clocked by top-level %s" % (gname, tag, cell["name"], clock_name))
                d = R(cell["conns"][d_port][qi])
                if isinstance(d, str):
                    errors.append("%s: %s flip-flop %s has constant D input %s (constant flip-flop)" % (gname, tag, cell["name"], d))
                    continue
                if d == n:
                    errors.append("%s: %s flip-flop %s has D tied to its own Q (constant flip-flop)" % (gname, tag, cell["name"]))
                    continue
                if d in d_seen:
                    errors.append("%s: %s and %s[%d] share one D net %s (bits merged)"
                                  % (gname, tag, qname, d_seen[d], pretty_net(flat, names_of, d)))
                    continue
                d_seen[d] = b
                dlist[b] = d
                n_ok_bits += 1
            copy_d.append(dlist)

        # D inputs across copies (only bits whose D is known in every copy).
        known = [b for b in range(width) if all(cd[b] is not None for cd in copy_d)]
        shared = sum(1 for b in known if len({cd[b] for cd in copy_d}) == 1)
        if kind == "pair":
            for b in range(width):
                da, db = copy_d[0][b], copy_d[1][b]
                if da is not None and da == db:
                    errors.append("%s: bit %d of %s and %s have the same D net %s (next-state logic merged)"
                                  % (gname, b, copies[0], copies[1], pretty_net(flat, names_of, da)))
            d_note = "distinct per copy" if shared == 0 else "%d/%d bits SHARED" % (shared, width)
        else:
            d_note = "shared by design (voted next state)" if shared == width else \
                     "%d/%d bits shared (voted next state)" % (shared, width)
        if len(known) < width:
            d_note = "not checkable (%d/%d bits have flops)" % (len(known), width)
        ok = len(errors) == gerr_before
        group_rows.append((gname, len(copies), width, n_ok_bits, len(copies) * width, d_note, ok))

    # Flip-flop bits outside the audited groups.
    unprot = []
    for cell, qi in ff_bits:
        if (cell["name"], qi) not in claimed:
            q = R(cell["conns"]["Q"][qi])
            unprot.append((net_names(flat, names_of, q), cell["type"], cell["name"]))
    unprot.sort()

    total_ff = len(ff_bits)
    if latches:
        errors.append("latches present: %s" % ", ".join(sorted(latches)))
    if expect_ff_bits is not None and total_ff != expect_ff_bits:
        errors.append("total flip-flop bits %d, expected %d" % (total_ff, expect_ff_bits))
    if expect_unprot is not None:
        # Each expected net must name exactly one unprotected bit, and there
        # must be no other unprotected bit.
        matched = [u for u in unprot if set(u[0]) & set(expect_unprot)]
        missing = [e for e in expect_unprot if not any(e in u[0] for u in unprot)]
        if missing or len(matched) != len(unprot) or len(unprot) != len(expect_unprot):
            errors.append("unprotected flip-flop bits [%s], expected exactly [%s]"
                          % ("; ".join(" = ".join(u[0]) for u in unprot), ", ".join(expect_unprot)))

    # Report.
    audited = sum(r[4] for r in group_rows)
    lines.append("ORBIT-AI storage audit (scripts/storage_audit.py)")
    lines.append("netlist        %s" % path)
    lines.append("creator        %s" % data.get("creator", "?"))
    lines.append("top            %s (%s)" % (top_name, "hierarchical: " + ", ".join(
        sorted(m for m in modules if m != top_name)) if len(modules) > 1 else "flat"))
    lines.append("")
    lines.append("%-22s %6s %5s %10s  %-38s %s" % ("group", "copies", "bits", "ok/expect", "D inputs across copies", "result"))
    for gname, nc, w, okb, exp, dnote, ok in group_rows:
        lines.append("%-22s %6d %5d %4d/%-5d  %-38s %s" % (gname, nc, w, okb, exp, dnote, "PASS" if ok else "FAIL"))
    lines.append("")
    lines.append("audited redundant flip-flop bits  %d distinct of %d expected" % (len(claimed), audited))
    lines.append("total flip-flop bits              %d%s" % (total_ff, "" if expect_ff_bits is None else " (expected %d)" % expect_ff_bits))
    lines.append("flip-flop cell types              %s" % ", ".join("%s x%d" % kv for kv in sorted(ff_types.items())))
    lines.append("latches                           %d" % len(latches))
    lines.append("unprotected flip-flop bits        %d" % len(unprot))
    for names, ctype, cname in unprot:
        lines.append("    %-28s %-16s %s" % (" = ".join(names), ctype, cname))
    lines.append("")
    if errors:
        lines.append("ERRORS (%d):" % len(errors))
        shown = errors[:60]
        lines.extend("  " + e for e in shown)
        if len(errors) > len(shown):
            lines.append("  ... %d more" % (len(errors) - len(shown)))
        lines.append("")
    passed = sum(1 for r in group_rows if r[6])
    lines.append("STORAGE_AUDIT %s: %d/%d groups pass, %d flip-flop bits, %d unprotected"
                 % ("PASS" if not errors else "FAIL", passed, len(group_rows), total_ff, len(unprot)))
    info = {"groups": group_rows, "total_ff": total_ff, "ff_types": dict(ff_types),
            "unprotected": unprot, "latches": latches, "errors": errors}
    return not errors, "\n".join(lines) + "\n", info


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("netlist", help="Yosys JSON netlist (write_json)")
    ap.add_argument("--top", default=None, help="top module (default: the one marked top)")
    ap.add_argument("--lanes", type=int, default=4)
    ap.add_argument("--clock", default="clk", help="top-level clock port")
    ap.add_argument("--expect-ff-bits", type=int, default=521,
                    help="expected total flip-flop bits (SPEC section 7); negative disables")
    ap.add_argument("--expect-unprotected", default="fault_q,out_valid_q,u_thermal.phase",
                    help="comma-separated expected unprotected flip-flop nets; empty disables")
    ap.add_argument("--report", help="write the report to this file too")
    args = ap.parse_args()

    expect_ff = args.expect_ff_bits if args.expect_ff_bits >= 0 else None
    expect_un = [s for s in args.expect_unprotected.split(",") if s] or None
    try:
        ok, text, _ = audit(args.netlist, args.top, args.lanes, expect_ff, expect_un, args.clock)
    except (OSError, ValueError, KeyError) as exc:
        print("storage_audit: cannot audit %s: %s" % (args.netlist, exc), file=sys.stderr)
        return 2
    sys.stdout.write(text)
    if args.report:
        with open(args.report, "w") as fh:
            fh.write(text)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
