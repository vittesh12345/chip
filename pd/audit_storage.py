#!/usr/bin/env python3
"""Storage audit of an ORFS gate-level netlist of orbit_demo.

Checks that every flip-flop bit of docs/SPEC.md section 7 exists as its own
standard cell in the (routed) netlist, in particular that the redundant copies
were not merged by synthesis or physical optimisation:

  * exactly 521 flip-flop cells, one bit each;
  * per lane i in 0..3: u_acc_a, u_acc_b, u_res_a, u_res_b hold bits q[0..31]
    once each (4 pairs of accumulators, 4 pairs of results);
  * u_thermal.u_copy0/1/2 hold bits q[0..1] once each (the TMR triple);
  * phase, out_valid_q and fault_q exist exactly once, and nothing else is a
    flip-flop;
  * all 521 flip-flops are distinct cell instances with distinct Q nets, every
    Q net has at least one load, and the copies of one bit do not share a D
    net (they are written through separate cells);
  * every flip-flop clock pin is on the clock tree: its net traces back
    through single-input cells (clock buffers/inverters) to the top-level
    clock port (not tied off, not driven from a data net).

Flip-flops are identified from the Liberty file (cells with an ff group), not
from cell names. Group membership comes from the instance paths that OpenROAD
writes for a flat link, e.g. "g_lane[0].u_lane.u_acc_a/q[5]$_SDFFE_PN0P_": the
part before '/' is the kept orbit_keep_reg instance, q[5] the stored bit.

Exit status 0 only if every check passes. A report is written with --report.
"""

import argparse
import re
import sys
from collections import defaultdict

LANES = 4
LANE_REGS = ("u_acc_a", "u_acc_b", "u_res_a", "u_res_b")
THERMAL_COPIES = ("u_copy0", "u_copy1", "u_copy2")
SINGLE_FFS = ("u_thermal.phase", "out_valid_q", "fault_q")
EXPECTED_TOTAL = LANES * len(LANE_REGS) * 32 + len(THERMAL_COPIES) * 2 + len(SINGLE_FFS)


# --------------------------------------------------------------------------
# Liberty: which cells are flip-flops, and their pin roles.
# --------------------------------------------------------------------------
def liberty_sequential_cells(path):
    """Return {cell: {"q": set(out pins), "clk": clocked_on pin, "d": next_state pins}}
    for every cell that contains an ff group. Latches are reported separately."""
    text = open(path, encoding="utf-8", errors="replace").read()
    ffs, latches = {}, set()
    # Split at cell headers; the liberty grammar is regular enough for this.
    parts = re.split(r'\n\s*cell\s*\(\s*"?([^")\s]+)"?\s*\)\s*\{', text)
    for name, body in zip(parts[1::2], parts[2::2]):
        if re.search(r'\blatch\s*\(', body):
            latches.add(name)
        m = re.search(r'\bff\s*\(([^)]*)\)\s*\{(.*?)\}', body, re.S)
        if not m:
            continue
        ffbody = m.group(2)
        clk = re.search(r'clocked_on\s*:\s*"([^"]+)"', ffbody)
        nxt = re.search(r'next_state\s*:\s*"([^"]+)"', ffbody)
        outs = set()
        for pm in re.finditer(r'\bpin\s*\(\s*"?([^")\s]+)"?\s*\)\s*\{(.*?)\n\s*\}', body, re.S):
            if re.search(r'direction\s*:\s*"?output', pm.group(2)):
                outs.add(pm.group(1))
        ffs[name] = {
            "q": outs,
            "clk": re.sub(r'[^A-Za-z0-9_]', '', clk.group(1)) if clk else None,
            "d": set(re.findall(r'[A-Za-z_][A-Za-z0-9_]*', nxt.group(1))) if nxt else set(),
        }
    return ffs, latches


def liberty_output_pins(path):
    """Return {cell: set(output pin names)} for every cell of the Liberty file
    (used to find the driver of a net when tracing the clock tree)."""
    text = open(path, encoding="utf-8", errors="replace").read()
    parts = re.split(r'\n\s*cell\s*\(\s*"?([^")\s]+)"?\s*\)\s*\{', text)
    outs = {}
    for name, body in zip(parts[1::2], parts[2::2]):
        outs[name] = {pm.group(1) for pm in
                      re.finditer(r'\bpin\s*\(\s*"?([^")\s]+)"?\s*\)\s*\{(.*?)\n\s*\}', body, re.S)
                      if re.search(r'direction\s*:\s*"?output', pm.group(2))}
    return outs


# --------------------------------------------------------------------------
# Structural Verilog netlist reader (as written by Yosys and OpenROAD).
# --------------------------------------------------------------------------
_TOKEN = re.compile(r'\\\S+|[A-Za-z_][A-Za-z0-9_$]*|\d+\'[bBhHdDoO][0-9a-fA-FxXzZ_]+|\d+|\S')


def _strip_comments(text):
    text = re.sub(r'/\*.*?\*/', ' ', text, flags=re.S)
    text = re.sub(r'//[^\n]*', ' ', text)
    text = re.sub(r'\(\*.*?\*\)', ' ', text, flags=re.S)  # attributes
    return text


def _ident(tok):
    """Unescape a Verilog identifier: drop the leading backslash, and the
    backslashes OpenSTA puts in front of [ ] and / inside escaped names."""
    if tok.startswith('\\'):
        tok = tok[1:]
    return tok.replace('\\[', '[').replace('\\]', ']')


def parse_netlist(path):
    """Return {module: [(celltype, instname, {pin: net-expression-string})]}"""
    toks = _TOKEN.findall(_strip_comments(open(path, encoding="utf-8").read()))
    modules = {}
    i, n = 0, len(toks)
    keywords = {"input", "output", "inout", "wire", "reg", "assign", "supply0", "supply1", "tri"}
    while i < n:
        if toks[i] != "module":
            i += 1
            continue
        mname = _ident(toks[i + 1])
        insts = []
        # skip header up to ';'
        while toks[i] != ';':
            i += 1
        i += 1
        while toks[i] != "endmodule":
            t = toks[i]
            if t in keywords:
                while toks[i] != ';':
                    i += 1
                i += 1
                continue
            # cell instance: TYPE [#(...)] NAME ( .pin(expr), ... );
            ctype = _ident(t)
            i += 1
            if toks[i] == '#':
                depth = 0
                i += 1
                while True:
                    if toks[i] == '(':
                        depth += 1
                    elif toks[i] == ')':
                        depth -= 1
                        if depth == 0:
                            i += 1
                            break
                    i += 1
            iname = _ident(toks[i])
            i += 1
            assert toks[i] == '(', f"parse error near {ctype} {iname}"
            pins = {}
            depth = 0
            i += 1
            while True:
                if toks[i] == ')' and depth == 0:
                    i += 1
                    break
                if toks[i] == '.':
                    pin = _ident(toks[i + 1])
                    assert toks[i + 2] == '('
                    j, d, expr = i + 3, 1, []
                    while True:
                        if toks[j] == '(':
                            d += 1
                        elif toks[j] == ')':
                            d -= 1
                            if d == 0:
                                break
                        expr.append(_ident(toks[j]))
                        j += 1
                    pins[pin] = "".join(expr)
                    i = j + 1
                    continue
                i += 1
            assert toks[i] == ';', f"parse error after {ctype} {iname}"
            i += 1
            insts.append((ctype, iname, pins))
        modules[mname] = insts
        i += 1
    return modules


def leaf_cells(modules, top):
    """Return [(instance path, celltype, pins)] of the top module. Only flat
    netlists are supported (OpenROAD writes one for a flat link: 1_synth_lec.v,
    6_final.v); a hierarchical Yosys netlist is rejected rather than guessed."""
    sub = [(t, i) for (t, i, _p) in modules[top] if t in modules]
    if sub:
        raise SystemExit(f"netlist is hierarchical ({len(sub)} module instances, e.g. "
                         f"{sub[0][1]} of {sub[0][0]}); audit a flat OpenROAD netlist")
    return [(iname, ctype, pins) for (ctype, iname, pins) in modules[top]]


# --------------------------------------------------------------------------
# The audit.
# --------------------------------------------------------------------------
def classify(path):
    """Map a flip-flop instance path to (group, copy, bit) or None."""
    # A kept orbit_keep_reg copy is "<instance>/q[<bit>]<yosys suffix>". A
    # netlist in which the copies were flattened (no keep_hierarchy) names the
    # same bits "<instance>.q[<bit>]..."; accept both so that such a netlist
    # fails on the merged copies themselves, not on naming.
    m = re.match(r'^g_lane\[(\d)\]\.u_lane\.(u_(?:acc|res)_[ab])[/.]q\[(\d+)\]', path)
    if m:
        lane, reg, bit = int(m.group(1)), m.group(2), int(m.group(3))
        return (f"lane{lane}.{reg[2:5]}", reg, bit)
    m = re.match(r'^u_thermal\.(u_copy[012])[/.]q\[(\d+)\]', path)
    if m:
        return ("thermal", m.group(1), int(m.group(2)))
    for s in SINGLE_FFS:
        if re.match(re.escape(s) + r'(\$|$|_reg)', path):
            return (s, s, 0)
    return None


def audit(netlist, liberty, top, clock="clk"):
    ffs, latches = liberty_sequential_cells(liberty)
    lib_outs = liberty_output_pins(liberty)
    modules = parse_netlist(netlist)
    if top not in modules:
        raise SystemExit(f"top module {top} not found in {netlist}")
    cells = leaf_cells(modules, top)

    checks = []  # (name, ok, detail)

    def check(name, ok, detail):
        checks.append((name, bool(ok), detail))

    seq = [(p, t, pins) for (p, t, pins) in cells if t in ffs]
    lat = [(p, t) for (p, t, _pins) in cells if t in latches]
    celltypes = defaultdict(int)
    for _p, t, _pins in seq:
        celltypes[t] += 1

    check("latches", not lat, f"{len(lat)} latch cells")
    check("flip-flop count", len(seq) == EXPECTED_TOTAL,
          f"{len(seq)} flip-flop cells (expected {EXPECTED_TOTAL}); types: "
          + ", ".join(f"{t} x{c}" for t, c in sorted(celltypes.items())))

    # Q net of each flip-flop (the one output pin that is connected).
    qnet, dnet, cknet = {}, {}, {}
    for p, t, pins in seq:
        q = [pins[o] for o in ffs[t]["q"] if pins.get(o)]
        qnet[p] = q[0] if len(q) == 1 else None
        dn = [pins[d] for d in ffs[t]["d"] if d in pins and pins[d]]
        dnet[p] = dn[0] if dn else None
        cknet[p] = pins.get(ffs[t]["clk"]) if ffs[t]["clk"] else None

    # Loads: count input-pin references of every net (any pin that is not a
    # flip-flop output; good enough for a fan-out >= 1 check).
    refs = defaultdict(int)
    for p, t, pins in cells:
        outs = ffs[t]["q"] if t in ffs else set()
        for pin, net in pins.items():
            if pin not in outs:
                refs[net] += 1
    # A flip-flop that drives a top-level output port directly (e.g. fault)
    # has the port as its load.
    top_outputs = set()
    text = _strip_comments(open(netlist, encoding="utf-8").read())
    mtop = re.search(r'\bmodule\s+\\?' + re.escape(top) + r'\b(.*?)\bendmodule', text, re.S)
    for decl in re.finditer(r'\boutput\s+(\[\d+:\d+\]\s*)?([^;]+);', mtop.group(1)):
        rng = decl.group(1)
        for nm in decl.group(2).split(','):
            nm = _ident(nm.strip())
            if rng:
                hi, lo = map(int, re.findall(r'\d+', rng))
                for k in range(min(hi, lo), max(hi, lo) + 1):
                    top_outputs.add(f"{nm}[{k}]")
            else:
                top_outputs.add(nm)

    groups = defaultdict(lambda: defaultdict(list))  # group -> copy -> [bits]
    unknown = []
    for p, _t, _pins in seq:
        c = classify(p)
        if c is None:
            unknown.append(p)
        else:
            groups[c[0]][c[1]].append((c[2], p))

    check("no unexpected flip-flops", not unknown,
          f"{len(unknown)} unclassified" + (": " + ", ".join(unknown[:5]) if unknown else ""))

    audited = []
    for lane in range(LANES):
        for kind in ("acc", "res"):
            audited.append((f"lane{lane}.{kind}", (f"u_{kind}_a", f"u_{kind}_b"), 32))
    audited.append(("thermal", THERMAL_COPIES, 2))

    group_lines = []
    for gname, copies, width in audited:
        ok = True
        notes = []
        for cp in copies:
            bits = sorted(b for b, _p in groups[gname][cp])
            if bits != list(range(width)):
                ok = False
                notes.append(f"{cp}: bits {bits[:4]}... ({len(bits)} cells)")
        # Copies of the same bit must be distinct cells with distinct Q nets
        # and must not share a D net.
        by_bit = defaultdict(list)
        for cp in copies:
            for b, p in groups[gname][cp]:
                by_bit[b].append(p)
        shared_q = shared_d = 0
        for b, ps in by_bit.items():
            qs = [qnet[p] for p in ps]
            ds = [dnet[p] for p in ps]
            if len(set(ps)) != len(ps) or None in qs or len(set(qs)) != len(qs):
                shared_q += 1
            if None in ds or len(set(ds)) != len(ds):
                shared_d += 1
        if shared_q:
            ok = False
            notes.append(f"{shared_q} bits whose copies share a cell or Q net")
        if shared_d:
            ok = False
            notes.append(f"{shared_d} bits whose copies share a D net")
        ncells = sum(len(groups[gname][cp]) for cp in copies)
        group_lines.append(f"  {gname:12s} {' / '.join(copies):28s} {ncells:3d} cells "
                           f"({len(copies)} x {width} bits)  {'OK' if ok else 'FAIL: ' + '; '.join(notes)}")
        check(f"group {gname}", ok, f"{ncells} cells, {len(copies)} distinct copies x {width} bits"
              + ("" if ok else " -- " + "; ".join(notes)))

    for s in SINGLE_FFS:
        n_s = len(groups[s][s])
        check(f"single {s}", n_s == 1, f"{n_s} cells")

    qs = [qnet[p] for p, _t, _pins in seq]
    check("distinct Q nets", None not in qs and len(set(qs)) == len(qs),
          f"{len(set(q for q in qs if q))} distinct Q nets for {len(qs)} flip-flops")
    unloaded = [p for p, _t, _pins in seq if qnet[p] and refs[qnet[p]] == 0 and qnet[p] not in top_outputs]
    check("every Q net has a load", not unloaded,
          f"{len(unloaded)} unloaded" + (": " + ", ".join(unloaded[:5]) if unloaded else ""))
    const = [p for p, _t, _pins in seq if not cknet[p] or re.match(r"^1'b[01]$", cknet[p] or "")]
    ck_nets = {cknet[p] for p, _t, _pins in seq}
    check("clock pins connected", not const,
          f"{len(const)} flip-flops with tied/missing clock; {len(ck_nets)} distinct clock-leaf nets")

    # Clock tree: from each clock-leaf net walk back through the driving
    # cells; every driver must be a single-input cell (clock buffer or
    # inverter) and the walk must end at the top-level clock port. A flip-flop
    # clocked from a data net or a constant fails here.
    driver = {}
    for p, t, pins in cells:
        for o in lib_outs.get(t, ()):
            if pins.get(o):
                driver[pins[o]] = (p, t, pins)
    bad_leaf = []
    for net in sorted(n for n in ck_nets if n):
        cur, ok = net, False
        for _ in range(64):
            if cur == clock:
                ok = True
                break
            drv = driver.get(cur)
            if drv is None:
                break
            _p, t, pins = drv
            ins = [n for pin, n in pins.items() if pin not in lib_outs.get(t, ()) and n]
            if len(ins) != 1:
                break
            cur = ins[0]
        if not ok:
            bad_leaf.append(net)
    off_tree = [p for p, _t, _pins in seq if cknet[p] in bad_leaf]
    check("clock pins on the clock tree", not off_tree and not const,
          f"{len(off_tree)} flip-flops whose clock net does not trace back to port '{clock}' "
          f"through buffers/inverters" + (": " + ", ".join(off_tree[:5]) if off_tree else ""))

    return checks, group_lines, len(cells), celltypes


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--netlist", required=True, help="gate-level Verilog (e.g. 6_final.v)")
    ap.add_argument("--liberty", required=True, help="Liberty file of the standard cells")
    ap.add_argument("--top", default="orbit_demo")
    ap.add_argument("--clock", default="clk", help="top-level clock port")
    ap.add_argument("--report", help="write the audit report here")
    a = ap.parse_args()

    checks, group_lines, ncells, celltypes = audit(a.netlist, a.liberty, a.top, a.clock)
    lines = [f"Storage audit of {a.netlist}",
             f"liberty: {a.liberty}",
             f"leaf cells in netlist: {ncells}",
             "",
             "Redundant groups (SPEC section 7):"] + group_lines + ["", "Checks:"]
    for name, ok, detail in checks:
        lines.append(f"  {'PASS' if ok else 'FAIL'}  {name}: {detail}")
    failed = [c for c in checks if not c[1]]
    lines += ["", f"RESULT: {'PASS' if not failed else 'FAIL'} ({len(checks) - len(failed)}/{len(checks)} checks passed)"]
    text = "\n".join(lines) + "\n"
    sys.stdout.write(text)
    if a.report:
        with open(a.report, "w") as f:
            f.write(text)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
