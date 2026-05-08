#!/usr/bin/env python3
"""Part attribution for the ORBIT-AI die viewer (area: viz).

Assigns every placed DEF component of the routed orbit_demo layout to one
named part (Lane 2 / Adder B, Clock tree, Tap cells, ...) and collects the
IO pins, the power-grid wires and the placement rows. Used by
scripts/viz_gds_to_3d.py; can also be run on its own to print the part table:

    python3 scripts/viz_parts.py --def 6_final.def --cell-lef merged.lef

Method (deterministic; documented in viz/README.md, "Part attribution"):

1. Instance names. The flow keeps the RTL hierarchy in the names of the
   kept orbit_keep_reg copies and of CTS / resizer / physical cells:
     g_lane[i].u_lane.u_{acc,res}_{a,b}/q[n]$...   flip-flops of a copy
     g_lane[i].u_lane.u_{acc,res}_{a,b}/_NNN_      that copy's enable/clear
                                                   gates (mux2i + nor2b)
     u_thermal.u_copyK...                          thermal copy K
     u_thermal.phase, out_valid_q, fault_q         single flip-flops
     clkbuf_*, clkload*                            clock tree (CTS)
     input*, output*                               port buffers
     place*, rebuffer*, wire*, split*, clone*      timing-repair buffers
     hold*, dlygate*/dlymetal* masters             hold-fix delay cells
     ANTENNA_*, TAP_*, FILLER_*, decap/fill        physical-only cells
2. Netlist cones for the anonymous `_NNNN_` cells (flattened synthesis
   logic). Connectivity comes from the DEF NETS section and pin directions
   from the cell LEF. Every combinational cell gets
     fwd = set of *sinks* reached through combinational fan-out
           (flip-flop groups via their D pin, output ports),
     bwd = set of *sources* in its combinational fan-in
           (flip-flop groups via their Q pin, input ports),
   propagated over the (acyclic) combinational graph; flip-flops stop the
   cones. The first matching rule below names the part:
     a. fwd holds only lane-i copy-A registers (acc_a/res_a)  -> Lane i / Adder A
        fwd holds only lane-i copy-B registers                 -> Lane i / Adder B
     b. fwd holds lane-i registers of both copies and bwd holds
        only lane-i operand inputs (in_a/in_b byte i, constants) -> Lane i / Multiplier
     c. bwd holds lane-i registers of both copies and fwd
        leads to the fault/handshake logic                     -> Lane i / Mismatch comparator
        (bwd holds registers of several lanes)                 -> Mismatch OR tree / fault
     d. bwd holds only thermal copies (no temperature input)   -> Thermal voter
        fwd reaches thermal copies or phase, bwd holds temp_*  -> Thermal next-state
     e. bwd holds only rst_n                                   -> Reset distribution
     f. fwd reaches registers of several lanes, or the
        out_valid_q / fault_q / in_ready / out_valid logic      -> Handshake and enable control
     g. anything else                                          -> Other logic
   Buffers placed by the resizer keep their own part (step 1) but their
   cone result is kept as `serves` for the inspector.
"""

import argparse
import collections
import math
import re
import sys

FLOP_RE = re.compile(r"__(?:s|e|se)?df")


def clean(n):
    return n.replace("\\", "")


# ---------------------------------------------------------------------------
# DEF reader (components, pins, nets, special nets, rows, regions, groups)
# ---------------------------------------------------------------------------
def read_def_full(path):
    txt = open(path).read()
    units = float(re.search(r"UNITS\s+DISTANCE\s+MICRONS\s+(\d+)", txt).group(1))
    m = re.search(r"DIEAREA((?:\s*\(\s*-?\d+\s+-?\d+\s*\))+)\s*;", txt)
    pts = [(int(a), int(b)) for a, b in re.findall(r"\(\s*(-?\d+)\s+(-?\d+)\s*\)", m.group(1))]
    die = (min(p[0] for p in pts) / units, min(p[1] for p in pts) / units,
           max(p[0] for p in pts) / units, max(p[1] for p in pts) / units)

    def section(name):
        mm = re.search(r"^" + name + r"\s+\d+\s*;(.*?)^END " + name, txt, re.S | re.M)
        return mm.group(1) if mm else ""

    comps = []  # (name, master, x, y, orient, status) in DEF order
    for stmt in section("COMPONENTS").split(";"):
        s = stmt.strip()
        if not s.startswith("-"):
            continue
        tok = s.split()
        pm = re.search(r"\+\s*(PLACED|FIXED|COVER)\s*\(\s*(-?\d+)\s+(-?\d+)\s*\)\s*(\S+)", s)
        if not pm:
            continue
        comps.append((clean(tok[1]), tok[2], int(pm.group(2)) / units, int(pm.group(3)) / units,
                      pm.group(4), pm.group(1)))

    pins = []
    for stmt in re.split(r"\n\s*-\s", "\n" + section("PINS")):
        s = stmt.strip()
        if not s:
            continue
        name = s.split()[0]
        d = re.search(r"DIRECTION\s+(\S+)", s)
        use = re.search(r"USE\s+(\S+)", s)
        lay = re.search(r"LAYER\s+(\S+)\s*\(\s*(-?\d+)\s+(-?\d+)\s*\)\s*\(\s*(-?\d+)\s+(-?\d+)\s*\)", s)
        pl = re.search(r"(PLACED|FIXED)\s*\(\s*(-?\d+)\s+(-?\d+)\s*\)\s*(\S+)", s)
        if not pl:
            continue
        rec = {"name": clean(name).rstrip(";").strip(), "dir": d.group(1) if d else "?",
               "use": use.group(1) if use else "SIGNAL",
               "x": int(pl.group(2)) / units, "y": int(pl.group(3)) / units}
        if lay:
            rec["layer"] = lay.group(1)
            rec["rect"] = [int(lay.group(i)) / units for i in range(2, 6)]
        pins.append(rec)

    nets = {}
    pair_re = re.compile(r"\(\s*(\S+)\s+(\S+)\s*\)")
    for stmt in section("NETS").split(";"):
        s = stmt.strip()
        if not s.startswith("-"):
            continue
        head = s.split("+", 1)[0]
        tok = head.split()
        nets[clean(tok[1])] = [(clean(i), p) for i, p in pair_re.findall(head)]

    power = []  # (net, layer, x0, y0, x1, y1) um
    cur = None
    for line in section("SPECIALNETS").splitlines():
        mm = re.match(r"\s*-\s+(\S+)", line)
        if mm:
            cur = mm.group(1)
        mm = re.search(r"(?:ROUTED|NEW)\s+(met\d|li1)\s+(\d+)\s*\+\s*SHAPE\s+(\S+)\s*\(\s*(-?\d+)\s+(-?\d+)\s*\)\s*\(\s*(\S+)\s+(\S+)\s*\)", line)
        if mm and cur:
            lay, w = mm.group(1), int(mm.group(2))
            if w == 0:
                continue
            x0, y0 = int(mm.group(4)), int(mm.group(5))
            x1 = x0 if mm.group(6) == "*" else int(mm.group(6))
            y1 = y0 if mm.group(7) == "*" else int(mm.group(7))
            h = w / 2
            if y0 == y1:
                r = (min(x0, x1), y0 - h, max(x0, x1), y0 + h)
            else:
                r = (x0 - h, min(y0, y1), x0 + h, max(y0, y1))
            power.append((cur, lay, mm.group(3)) + tuple(v / units for v in r))

    rows = []
    for rm in re.finditer(r"^\s*ROW\s+(\S+)\s+(\S+)\s+(-?\d+)\s+(-?\d+)\s+(\S+)\s+DO\s+(\d+)\s+BY\s+(\d+)\s+STEP\s+(\d+)\s+(\d+)",
                          txt, re.M):
        rows.append({"name": rm.group(1), "site": rm.group(2), "x": int(rm.group(3)) / units,
                     "y": int(rm.group(4)) / units, "orient": rm.group(5), "n": int(rm.group(6)),
                     "step": int(rm.group(8)) / units})

    regions = []
    for rm in re.finditer(r"^\s*-\s+(\S+)((?:\s*\(\s*-?\d+\s+-?\d+\s*\)\s*\(\s*-?\d+\s+-?\d+\s*\))+)\s*\+\s*TYPE\s+(\S+)",
                          section("REGIONS"), re.M):
        nums = [int(v) / units for v in re.findall(r"-?\d+", rm.group(2))]
        boxes = [nums[i:i + 4] for i in range(0, len(nums), 4)]
        regions.append({"name": rm.group(1), "type": rm.group(3), "boxes": boxes})
    groups = {}
    for stmt in section("GROUPS").split(";"):
        s = stmt.strip()
        if not s.startswith("-"):
            continue
        tok = s.split()
        reg = re.search(r"REGION\s+(\S+)", s)
        members = [clean(t) for t in tok[2:] if t != "+" and not t.startswith("REGION")]
        if reg:
            members = [m for m in members if m != reg.group(1)]
        groups[tok[1]] = {"region": reg.group(1) if reg else None, "members": members}
    return {"units": units, "die": die, "components": comps, "pins": pins, "nets": nets,
            "power": power, "rows": rows, "regions": regions, "groups": groups}


# ---------------------------------------------------------------------------
# Part catalogue
# ---------------------------------------------------------------------------
# kind: colour family used by the viewer's "Parts" colouring (same role, same
# colour in every lane); category: coarse function class.
KINDS = [
    # kind id,    display,                        category,     light,     dark
    ("accA",   "Accumulator copy A",               "storage",    "#1f5fbf", "#5b95f0"),
    ("resA",   "Result copy A",                    "storage",    "#4b86e0", "#8cb6f5"),
    ("muxA",   "Copy A load/clear gates",          "storage",    "#9dbde9", "#3b5f8f"),
    ("accB",   "Accumulator copy B",               "storage",    "#c85f0f", "#f2994a"),
    ("resB",   "Result copy B",                    "storage",    "#e8913d", "#f7bd7f"),
    ("muxB",   "Copy B load/clear gates",          "storage",    "#f1c28f", "#8f5a24"),
    ("addA",   "Adder A (copy A sum)",             "arithmetic", "#2e9e8f", "#4fc9b7"),
    ("addB",   "Adder B (copy B sum)",             "arithmetic", "#8a9a1c", "#bccb4a"),
    ("mult",   "Shared multiplier",                "arithmetic", "#7a4fc9", "#a987ec"),
    ("cmp",    "Mismatch comparator",              "checking",   "#c2368c", "#ec6fb8"),
    ("fault",  "Mismatch OR tree and fault latch", "checking",   "#a8233a", "#f0607a"),
    ("thc0",   "Thermal copy 0",                   "storage",    "#6d3fb0", "#b596f0"),
    ("thc1",   "Thermal copy 1",                   "storage",    "#b0479e", "#e58fd3"),
    ("thc2",   "Thermal copy 2",                   "storage",    "#2f8f3a", "#5cc167"),
    ("thvote", "Thermal voter",                    "checking",   "#d0342c", "#ff6d63"),
    ("thnext", "Thermal next-state logic",         "control",    "#b5752a", "#e3a458"),
    ("phase",  "Throttle phase flop",              "control",    "#8c5a2b", "#d49a63"),
    ("ctrl",   "Handshake and enable control",     "control",    "#5b6f1e", "#a8c24f"),
    ("rst",    "Reset distribution",               "control",    "#8a6f00", "#d9bb3f"),
    ("clk",    "Clock tree",                       "clock",      "#e0a800", "#ffd23f"),
    ("io",     "Port buffers",                     "io",         "#3f6f8a", "#79a9c4"),
    ("repair", "Timing-repair buffers",            "buffer",     "#6d8793", "#95abb5"),
    ("hold",   "Hold-fix delay cells",             "buffer",     "#51646d", "#b8c8cf"),
    ("tie",    "Tie cells",                        "physical",   "#8e8e8e", "#9a9a9a"),
    ("ant",    "Antenna diodes",                   "physical",   "#6f6f6f", "#b0b0b0"),
    ("tap",    "Well-tap cells",                   "physical",   "#9aa4a8", "#6d787d"),
    ("decap",  "Decap cells",                      "physical",   "#b9c1c4", "#56616a"),
    ("fill",   "Fill cells",                       "physical",   "#cfd5d8", "#3d484e"),
    ("other",  "Other logic",                      "other",      "#444444", "#dddddd"),
]
KIND = {k[0]: k for k in KINDS}

LANE_KINDS = ["mult", "addA", "addB", "accA", "accB", "resA", "resB", "muxA", "muxB", "cmp"]


def part_catalogue(lanes):
    """Ordered list of part dicts (without counts)."""
    parts = []

    def add(pid, kind, name, group, lane=None, source="instance-name", note=None):
        k = KIND[kind]
        parts.append({"id": pid, "kind": kind, "name": name, "group": group, "lane": lane,
                      "category": k[2], "source": source, "note": note})

    for i in lanes:
        g = f"Lane {i}"
        add(f"L{i}.mult", "mult", f"Lane {i} / Multiplier", g, i, "netlist-cone",
            "8x8 signed multiplier shared by both copies of the lane")
        add(f"L{i}.addA", "addA", f"Lane {i} / Adder A", g, i, "netlist-cone", "acc_a_sum = (first ? 0 : acc_a) + prod")
        add(f"L{i}.addB", "addB", f"Lane {i} / Adder B", g, i, "netlist-cone", "acc_b_sum = (first ? 0 : acc_b) + prod")
        add(f"L{i}.accA", "accA", f"Lane {i} / Accumulator A", g, i, "instance-name", "32 flip-flops u_acc_a")
        add(f"L{i}.accB", "accB", f"Lane {i} / Accumulator B", g, i, "instance-name", "32 flip-flops u_acc_b")
        add(f"L{i}.resA", "resA", f"Lane {i} / Result A", g, i, "instance-name", "32 flip-flops u_res_a")
        add(f"L{i}.resB", "resB", f"Lane {i} / Result B", g, i, "instance-name", "32 flip-flops u_res_b")
        add(f"L{i}.muxA", "muxA", f"Lane {i} / Load mux A", g, i, "instance-name",
            "per-bit enable/clear gates of u_acc_a and u_res_a (mux2i + nor2b)")
        add(f"L{i}.muxB", "muxB", f"Lane {i} / Load mux B", g, i, "instance-name",
            "per-bit enable/clear gates of u_acc_b and u_res_b (mux2i + nor2b)")
        add(f"L{i}.cmp", "cmp", f"Lane {i} / Mismatch comparator", g, i, "netlist-cone",
            "acc_a != acc_b, res_a != res_b")
    tg = "Thermal TMR"
    add("th.c0", "thc0", "Thermal / Copy 0", tg, None, "instance-name", "2-bit state copy u_copy0 + its gates")
    add("th.c1", "thc1", "Thermal / Copy 1", tg, None, "instance-name", "2-bit state copy u_copy1 + its gates")
    add("th.c2", "thc2", "Thermal / Copy 2", tg, None, "instance-name", "2-bit state copy u_copy2 + its gates")
    add("th.vote", "thvote", "Thermal / Voter", tg, None, "netlist-cone", "2-of-3 majority and repair detect")
    add("th.next", "thnext", "Thermal / Next-state logic", tg, None, "netlist-cone",
        "temperature compare, next state, admit")
    add("th.phase", "phase", "Thermal / Throttle phase flop", tg, None, "instance-name",
        "u_thermal.phase (unprotected)")
    cg = "Shared control"
    add("fault", "fault", "Mismatch OR tree / fault_q", cg, None, "netlist-cone",
        "OR of the lane mismatches and the sticky fault latch fault_q (unprotected)")
    add("ctrl", "ctrl", "Handshake / out_valid_q / enables", cg, None, "netlist-cone",
        "in_ready, out_valid, out_valid_q (unprotected), in_fire enable and clear distribution")
    add("rst", "rst", "Reset distribution (rst_n)", cg, None, "netlist-cone", "buffers fed only by rst_n")
    pg = "Physical"
    add("clk", "clk", "Clock tree", pg, None, "name-prefix", "CTS buffers clkbuf_*, clkload*")
    add("io", "io", "IO port buffers", pg, None, "name-prefix", "input*/output* buffers at the pins")
    add("repair", "repair", "Timing-repair buffers", pg, None, "name-prefix",
        "resizer buffers place*, rebuffer*, wire*, split*, clone*")
    add("hold", "hold", "Hold-fix delay cells", pg, None, "name-prefix", "hold* buffers / dlygate delay cells")
    add("tie", "tie", "Tie cells", pg, None, "master", "conb constant drivers not inside a named copy")
    add("ant", "ant", "Antenna diodes", pg, None, "name-prefix", "router repair diodes ANTENNA_*")
    add("tap", "tap", "Well-tap cells", pg, None, "master", "tapvpwrvgnd: tie n-well/p-substrate to VPWR/VGND")
    add("decap", "decap", "Decap cells", pg, None, "master", "decoupling capacitors")
    add("fill", "fill", "Fill cells", pg, None, "master", "empty row filler (fill_1/2/4/8)")
    add("other", "other", "Other logic", "Unattributed", None, "netlist-cone",
        "combinational cells no rule could place")
    return parts


# ---------------------------------------------------------------------------
# Attribution
# ---------------------------------------------------------------------------
def name_part(name, master):
    """Step 1: part id from the instance name / master, or None."""
    short = master.replace("sky130_fd_sc_hd__", "")
    m = re.match(r"g_lane\[(\d+)\]\.u_lane\.u_(acc|res)_([ab])(.)", name)
    if m:
        lane, what, cp, sep = m.groups()
        if FLOP_RE.search(master):
            return f"L{lane}.{what}{cp.upper()}"
        return f"L{lane}.mux{cp.upper()}"
    m = re.match(r"u_thermal\.u_copy(\d)", name)
    if m:
        return f"th.c{m.group(1)}"
    if name.startswith("u_thermal.phase"):
        return "th.phase"
    if name.startswith("out_valid_q"):
        return "ctrl"
    if name.startswith("fault_q"):
        return "fault"
    if name.startswith("FILLER") or short.startswith("fill"):
        return "fill"
    if short.startswith("decap"):
        return "decap"
    if name.startswith("TAP") or short.startswith("tapvpwrvgnd"):
        return "tap"
    if name.startswith("ANTENNA") or short.startswith("diode"):
        return "ant"
    if name.startswith(("clkbuf_", "clkload", "cts")):
        return "clk"
    if re.match(r"(input|output)\d+$", name):
        return "io"
    if name.startswith("hold") or short.startswith(("dlygate", "dlymetal")):
        return "hold"
    if re.match(r"(place|rebuffer|wire|split|clone|rsz|max_length|max_cap|fanout)", name):
        return "repair"
    if short.startswith("conb"):
        return "tie"
    return None


def attribute(defd, macros, lanes=range(4)):
    """Return (part_of: {inst: part id}, serves: {inst: part id}, parts, notes)."""
    comps = {c[0]: c for c in defd["components"]}
    nets = defd["nets"]

    def pin_dir(inst, pin):
        mac = macros.get(comps[inst][1]) if inst in comps else None
        return (mac or {}).get("pins", {}).get(pin, "?")

    part_of = {}
    for name, master, *_ in defd["components"]:
        part_of[name] = name_part(name, master)

    flops = {n for n, c in comps.items() if FLOP_RE.search(c[1])}

    # --- sink / source groups (bit masks) --------------------------------
    bits = {}

    def bit(key):
        if key not in bits:
            bits[key] = 1 << len(bits)
        return bits[key]

    def reg_group(name):
        m = re.match(r"g_lane\[(\d+)\]\.u_lane\.u_(acc|res)_([ab])", name)
        if m:
            return f"L{m.group(1)}.{m.group(2)}{m.group(3).upper()}"
        m = re.match(r"u_thermal\.u_copy(\d)", name)
        if m:
            return f"th{m.group(1)}"
        for k in ("u_thermal.phase", "out_valid_q", "fault_q"):
            if name.startswith(k):
                return k
        return "ff_other"

    def port_group(p):
        m = re.match(r"(in_a|in_b)\[(\d+)\]", p)
        if m:
            return f"{m.group(1)}{int(m.group(2)) // 8}"
        m = re.match(r"out_data\[(\d+)\]", p)
        if m:
            return f"out{int(m.group(1)) // 32}"
        return re.sub(r"\[\d+\]", "", p)

    drivers = {}
    loads = collections.defaultdict(list)
    src_of_net = {}   # net -> source bit when driven by a flop Q / input port
    sink_of_load = {}  # (inst) -> sink bit when the load is a flop D-side pin
    for net, conns in nets.items():
        for inst, pin in conns:
            if inst == "PIN":
                # top-level port: input ports drive the net, outputs load it
                pass
        for inst, pin in conns:
            if inst == "PIN":
                continue
            d = pin_dir(inst, pin)
            if d == "OUTPUT":
                drivers[net] = inst
            else:
                loads[net].append((inst, pin))
    port_dir = {p["name"]: p["dir"] for p in defd["pins"]}
    net_src_bits = {}
    net_sink_bits = {}
    for net, conns in nets.items():
        for inst, pin in conns:
            if inst == "PIN":
                if port_dir.get(pin) == "INPUT":
                    net_src_bits[net] = net_src_bits.get(net, 0) | bit("src:" + port_group(pin))
                elif port_dir.get(pin) == "OUTPUT":
                    net_sink_bits[net] = net_sink_bits.get(net, 0) | bit("snk:" + port_group(pin))
        drv = drivers.get(net)
        if drv in flops:
            net_src_bits[net] = net_src_bits.get(net, 0) | bit("src:" + reg_group(drv))

    # combinational instances that appear in nets
    inst_out_nets = collections.defaultdict(list)
    inst_in_nets = collections.defaultdict(list)
    for net, conns in nets.items():
        for inst, pin in conns:
            if inst == "PIN":
                continue
            if pin_dir(inst, pin) == "OUTPUT":
                inst_out_nets[inst].append(net)
            else:
                inst_in_nets[inst].append((net, pin))

    clock_nets = set()
    # clock network: nets that reach a flop CLK pin through buffers
    for net, conns in nets.items():
        if any(pin == "CLK" and inst in flops for inst, pin in conns):
            clock_nets.add(net)

    fwd_net = {}
    bwd_net = {}

    def post_order(start, succ):
        """Iterative DFS post-order over nets."""
        order, seen = [], set()
        for s0 in start:
            if s0 in seen:
                continue
            stack = [(s0, iter(succ(s0)))]
            seen.add(s0)
            while stack:
                n, it = stack[-1]
                nxt = next(it, None)
                if nxt is None:
                    stack.pop()
                    order.append(n)
                elif nxt not in seen:
                    seen.add(nxt)
                    stack.append((nxt, iter(succ(nxt))))
        return order

    def succ_fwd(net):
        for inst, pin in loads.get(net, ()):
            if inst not in flops:
                yield from inst_out_nets.get(inst, ())

    def succ_bwd(net):
        d = drivers.get(net)
        if d is not None and d not in flops:
            for n2, _p in inst_in_nets.get(d, ()):
                yield n2

    all_nets = [n for n in nets if n not in clock_nets]
    for net in post_order(all_nets, succ_fwd):
        v = net_sink_bits.get(net, 0)
        for inst, pin in loads.get(net, ()):
            if inst in flops:
                if pin != "CLK":
                    v |= bit("snk:" + reg_group(inst))
            else:
                for on in inst_out_nets.get(inst, ()):
                    v |= fwd_net.get(on, 0)
        fwd_net[net] = v
    for net in post_order(all_nets, succ_bwd):
        v = net_src_bits.get(net, 0)
        d = drivers.get(net)
        if d is not None and d not in flops:
            for n2, _p in inst_in_nets.get(d, ()):
                if n2 in clock_nets:
                    continue
                v |= bwd_net.get(n2, 0)
        bwd_net[net] = v

    inv = {v: k for k, v in bits.items()}

    def names(mask, prefix):
        out = set()
        while mask:
            low = mask & -mask
            k = inv[low]
            if k.startswith(prefix):
                out.add(k[len(prefix):])
            mask ^= low
        return out

    lane_re = re.compile(r"L(\d)\.(acc|res)([AB])$")

    def classify(fwd, bwd):
        f = names(fwd, "snk:")
        b = names(bwd, "src:")
        f_lane = {}
        for s in f:
            m = lane_re.match(s)
            if m:
                f_lane.setdefault(int(m.group(1)), set()).add(m.group(3))
        b_lane = {}
        for s in b:
            m = lane_re.match(s)
            if m:
                b_lane.setdefault(int(m.group(1)), set()).add(m.group(3))
        f_out = {s for s in f if s.startswith("out") and s[3:].isdigit()}
        f_other = f - {s for s in f if lane_re.match(s)} - f_out
        ops = {s for s in b if re.match(r"in_[ab]\d$", s)}
        # a. adders
        if len(f_lane) == 1 and not f_other:
            (ln, cps), = f_lane.items()
            if cps == {"A"}:
                return f"L{ln}.addA"
            if cps == {"B"}:
                return f"L{ln}.addB"
            # b. multiplier
            if cps == {"A", "B"} and ops and all(o[-1] == str(ln) for o in ops) and not b_lane:
                return f"L{ln}.mult"
        # a'. buffers/inverters on one copy's Q outputs (feedback into its adder)
        if len(b_lane) == 1 and not (b - {s for s in b if lane_re.match(s)}):
            (ln, cps), = b_lane.items()
            if len(cps) == 1:
                return f"L{ln}.add{next(iter(cps))}"
        # c. comparators: fan-in from both copies of a lane
        both = sorted(ln for ln, cps in b_lane.items() if cps == {"A", "B"})
        ctl_in = {s for s in b if s in ("in_valid", "out_ready", "clear_fault", "in_first", "in_last",
                                        "out_valid_q", "fault_q", "u_thermal.phase", "th0", "th1", "th2")
                  or s.startswith("temp")}
        if both:
            if len(b_lane) == 1 and not ctl_in:
                return f"L{both[0]}.cmp"
            if not ctl_in or ctl_in <= {"fault_q"}:
                return "fault"
            return "ctrl"
        # d. thermal
        th = {s for s in b if s in ("th0", "th1", "th2")}
        temp = {s for s in b if s.startswith("temp")}
        f_th = {s for s in f if s in ("th0", "th1", "th2", "u_thermal.phase")}
        if th and not temp and not b_lane and not f_th:
            return "th.vote"
        if f_th or (temp and not b_lane):
            return "th.next"
        if th and not b_lane:
            return "th.vote"
        # e. reset
        if b == {"rst_n"}:
            return "rst"
        # f. control
        if len(f_lane) > 1 or f & {"out_valid_q", "fault_q", "in_ready", "out_valid"}:
            return "ctrl"
        if b_lane and ("fault_q" in f or "out_valid" in f or "in_ready" in f):
            return "fault"
        return "other"

    serves = {}
    sig = {}
    for inst, c in comps.items():
        if inst in flops or inst not in inst_out_nets:
            continue
        outs = inst_out_nets[inst]
        if any(o in clock_nets for o in outs):
            continue
        fwd = 0
        for o in outs:
            fwd |= fwd_net.get(o, 0)
        bwd = 0
        for n2, _p in inst_in_nets.get(inst, ()):
            if n2 not in clock_nets:
                bwd |= bwd_net.get(n2, 0)
        # constants / ties: a cell with no sources is judged by its sinks alone
        pid = classify(fwd, bwd)
        sig[inst] = (fwd, bwd)
        if part_of.get(inst) is None:
            part_of[inst] = pid
        else:
            serves[inst] = pid
            # buffers that only carry rst_n form the reset tree
            if part_of[inst] == "repair" and pid == "rst":
                part_of[inst] = "rst"

    # g. cells with no connectivity at all
    for inst in comps:
        if part_of.get(inst) is None:
            part_of[inst] = "other"

    # the clock tree also holds any non-CTS cell that drives a clock net
    for inst in comps:
        if part_of[inst] in ("other",) and any(o in clock_nets for o in inst_out_nets.get(inst, ())):
            part_of[inst] = "clk"
    return part_of, serves, clock_nets, sig, names


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--def", dest="def_path", required=True)
    ap.add_argument("--cell-lef", required=True)
    args = ap.parse_args()
    sys.path.insert(0, __file__.rsplit("/", 1)[0])
    from viz_gds_to_3d import read_cell_lef
    macros = read_cell_lef(args.cell_lef)
    d = read_def_full(args.def_path)
    part_of, serves, clock_nets, sig, names = attribute(d, macros)
    import os
    if os.environ.get("VIZ_PARTS_DEBUG"):
        for inst, pid in sorted(part_of.items()):
            if pid == os.environ["VIZ_PARTS_DEBUG"] and inst in sig:
                f, b = sig[inst]
                print(inst, sorted(names(f, "snk:")), sorted(names(b, "src:")))
    cnt = collections.Counter(part_of.values())
    for p in part_catalogue(range(4)):
        print(f"{cnt.get(p['id'], 0):6d}  {p['id']:10s} {p['name']}")
    print("total", sum(cnt.values()), "components", len(d["components"]))
    print("serves", collections.Counter(serves.values()).most_common(12))
    print("pins", len(d["pins"]), "power rects", len(d["power"]), "rows", len(d["rows"]),
          "regions", len(d["regions"]), "groups", {k: len(v["members"]) for k, v in d["groups"].items()})


if __name__ == "__main__":
    main()


# ---------------------------------------------------------------------------
# sky130_fd_sc_hd master names -> plain-language description + equation
# ---------------------------------------------------------------------------
FIXED_DESC = {
    "dfxtp": ("D flip-flop", "positive-edge-triggered D flip-flop (one bit of storage)", "Q <= D on the rising CLK edge"),
    "dfrtp": ("D flip-flop, async reset", "positive-edge D flip-flop with active-low asynchronous reset", "Q <= D on rising CLK; Q = 0 while RESET_B = 0"),
    "dfstp": ("D flip-flop, async set", "positive-edge D flip-flop with active-low asynchronous set", "Q <= D on rising CLK; Q = 1 while SET_B = 0"),
    "edfxtp": ("D flip-flop with enable", "positive-edge D flip-flop with a data enable", "Q <= DE ? D : Q on rising CLK"),
    "sdfxtp": ("scan D flip-flop", "positive-edge D flip-flop with a scan mux", "Q <= SCE ? SCD : D on rising CLK"),
    "fa": ("full adder", "one-bit full adder", "SUM = A ^ B ^ CIN; COUT = majority(A, B, CIN)"),
    "ha": ("half adder", "one-bit half adder", "SUM = A ^ B; COUT = A & B"),
    "maj3": ("majority gate", "3-input majority (2-of-3 vote)", "X = (A & B) | (A & C) | (B & C)"),
    "mux2": ("2:1 multiplexer", "2-input multiplexer", "X = S ? A1 : A0"),
    "mux2i": ("2:1 inverting multiplexer", "2-input multiplexer with inverted output", "Y = !(S ? A1 : A0)"),
    "mux4": ("4:1 multiplexer", "4-input multiplexer", "X = {S1,S0} selects A0..A3"),
    "buf": ("buffer", "non-inverting buffer (drive strength / fan-out repair)", "X = A"),
    "bufbuf": ("buffer", "two-stage non-inverting buffer", "X = A"),
    "bufinv": ("inverting buffer", "large inverting buffer", "Y = !A"),
    "inv": ("inverter", "inverter", "Y = !A"),
    "clkbuf": ("clock buffer", "balanced-rise/fall buffer used in the clock tree (also used as an ordinary buffer)", "X = A"),
    "clkinv": ("clock inverter", "balanced clock inverter", "Y = !A"),
    "clkinvlp": ("low-power clock inverter", "low-power clock inverter", "Y = !A"),
    "clkdlybuf4s50": ("delay buffer", "4-stage clock delay buffer (slow, used as a delay or port buffer)", "X = A (delayed)"),
    "clkdlybuf4s25": ("delay buffer", "4-stage clock delay buffer", "X = A (delayed)"),
    "clkdlybuf4s15": ("delay buffer", "4-stage clock delay buffer", "X = A (delayed)"),
    "clkdlybuf4s18": ("delay buffer", "4-stage clock delay buffer", "X = A (delayed)"),
    "dlygate4sd1": ("hold-fix delay", "delay gate inserted to fix hold timing", "X = A (delayed)"),
    "dlygate4sd2": ("hold-fix delay", "delay gate inserted to fix hold timing", "X = A (delayed)"),
    "dlygate4sd3": ("hold-fix delay", "delay gate inserted to fix hold timing", "X = A (delayed)"),
    "dlymetal6s2s": ("hold-fix delay", "metal-loaded delay buffer inserted to fix hold timing", "X = A (delayed)"),
    "dlymetal6s4s": ("hold-fix delay", "metal-loaded delay buffer inserted to fix hold timing", "X = A (delayed)"),
    "dlymetal6s6s": ("hold-fix delay", "metal-loaded delay buffer inserted to fix hold timing", "X = A (delayed)"),
    "conb": ("tie cell", "constant driver: HI is tied to VPWR, LO to VGND", "HI = 1; LO = 0"),
    "tapvpwrvgnd": ("well tap", "well-tap cell: ties the n-well to VPWR and the p-substrate to VGND (latch-up protection, no logic)", None),
    "decap": ("decap", "decoupling capacitor between VPWR and VGND (no logic)", None),
    "fill": ("fill", "filler cell: continues the wells and power rails in an empty row slot (no logic)", None),
    "diode": ("antenna diode", "diode on a long net; drains plasma-etch charge so thin gate oxide is not damaged (no logic)", None),
    "lpflow_isobufsrc": ("isolation buffer", "isolation buffer", None),
}
SIMPLE_OPS = {"and": ("AND", " & ", False), "nand": ("NAND", " & ", True), "or": ("OR", " | ", False),
              "nor": ("NOR", " | ", True), "xor": ("XOR", " ^ ", False), "xnor": ("XNOR", " ^ ", True)}


def _lit(p):
    return "!" + p if p.endswith("_N") else p


def describe_master(master, pins):
    """Return {'short', 'desc', 'eq', 'drive'} for a sky130_fd_sc_hd master
    (pins: {name: direction} from the cell LEF). Raises KeyError for a
    master it cannot decode, so an unknown cell stops the build."""
    s = master.replace("sky130_fd_sc_hd__", "")
    m = re.match(r"(.+?)_(\d+)$", s)
    func, drive = (m.group(1), int(m.group(2))) if m else (s, None)
    ins = [p for p, d in pins.items() if d == "INPUT" and p not in ("VPWR", "VGND", "VPB", "VNB")]
    outs = [p for p, d in pins.items() if d == "OUTPUT"]
    out = outs[0] if outs else "Y"
    if func in FIXED_DESC:
        short, desc, eq = FIXED_DESC[func]
        return {"short": short, "desc": desc, "eq": eq, "drive": drive, "func": func}
    mm = re.match(r"(and|nand|or|nor|xor|xnor)(\d)(b{0,2})$", func)
    if mm:
        name, sep, inv = SIMPLE_OPS[mm.group(1)]
        n = int(mm.group(2))
        body = sep.join(_lit(p) for p in ins)
        eq = f"{out} = " + (f"!({body})" if inv else body)
        extra = f", {len(mm.group(3))} input(s) inverted" if mm.group(3) else ""
        return {"short": f"{n}-input {name}", "desc": f"{n}-input {name} gate{extra}", "eq": eq,
                "drive": drive, "func": func}
    mm = re.match(r"([ao])(\d[\dbB]*?)(oi|ai|o|a)$", func)
    if mm and mm.group(1) + mm.group(3) in ("ao", "aoi", "oa", "oai"):
        first, last = mm.group(1), mm.group(3)
        inner, outer = (" & ", " | ") if first == "a" else (" | ", " & ")
        groups = collections.OrderedDict()
        for p in ins:
            groups.setdefault(p[0], []).append(p)
        terms = []
        for letter, ps in groups.items():
            lits = [_lit(p) for p in ps]
            terms.append(lits[0] if len(lits) == 1 else "(" + inner.join(lits) + ")")
        body = outer.join(terms)
        invert = last in ("oi", "ai")
        eq = f"{out} = " + (f"!({body})" if invert else body)
        kind = {"ao": "AND-OR", "aoi": "AND-OR-invert", "oa": "OR-AND", "oai": "OR-AND-invert"}[first + last]
        return {"short": kind, "desc": f"{kind} complex gate ({len(ins)} inputs)", "eq": eq,
                "drive": drive, "func": func}
    raise KeyError(master)


# ---------------------------------------------------------------------------
# Per-cell arrays and part statistics for the viewer / GLB
# ---------------------------------------------------------------------------
def cell_box(comp, macros):
    name, master, x, y, orient, _st = comp
    mac = macros.get(master) or {"w": 0.0, "h": 0.0}
    w, h = mac["w"], mac["h"]
    if orient in ("E", "W", "FE", "FW"):
        w, h = h, w
    return (x, y, x + w, y + h)


def _pct(vals, q):
    s = sorted(vals)
    if not s:
        return 0.0
    k = (len(s) - 1) * q
    f = int(k)
    c = min(f + 1, len(s) - 1)
    return s[f] + (s[c] - s[f]) * (k - f)


def part_stats(parts, boxes_by_part, ffs_by_part, die, bin_um=10.0):
    """Fill cells/area/ffs/bbox/p10-p90 box/centroid/anchor/spread per part.
    anchor = centre of the 3x3-bin window (bin_um bins) holding the most
    cell area of the part (a label point that sits on the part's own cells,
    unlike a centroid, which can land on another part)."""
    dw, dh = die[2] - die[0], die[3] - die[1]
    nb_x, nb_y = int(math.ceil(dw / bin_um)), int(math.ceil(dh / bin_um))
    for p in parts:
        bx = boxes_by_part.get(p["id"], [])
        p["cells"] = len(bx)
        p["area_um2"] = round(sum((b[2] - b[0]) * (b[3] - b[1]) for b in bx), 2)
        p["ffs"] = ffs_by_part.get(p["id"], 0)
        if not bx:
            p.update(bbox_um=None, core_um=None, centroid_um=None, anchor_um=None, spread_pct=None, compact=False)
            continue
        xs = [(b[0] + b[2]) / 2 - die[0] for b in bx]
        ys = [(b[1] + b[3]) / 2 - die[1] for b in bx]
        p["bbox_um"] = [round(min(b[0] for b in bx) - die[0], 2), round(min(b[1] for b in bx) - die[1], 2),
                        round(max(b[2] for b in bx) - die[0], 2), round(max(b[3] for b in bx) - die[1], 2)]
        core = [_pct(xs, .1), _pct(ys, .1), _pct(xs, .9), _pct(ys, .9)]
        p["core_um"] = [round(v, 2) for v in core]
        p["centroid_um"] = [round(sum(xs) / len(xs), 2), round(sum(ys) / len(ys), 2)]
        grid = collections.Counter()
        for b, x, y in zip(bx, xs, ys):
            grid[(min(int(x // bin_um), nb_x - 1), min(int(y // bin_um), nb_y - 1))] += (b[2] - b[0]) * (b[3] - b[1])
        best, best_v = None, -1
        for (i, j) in grid:
            v = sum(grid.get((i + di, j + dj), 0) for di in (-1, 0, 1) for dj in (-1, 0, 1))
            if v > best_v or (v == best_v and (i, j) < best):
                best, best_v = (i, j), v
        # area-weighted centre of the cells inside the best window
        wx = wy = wt = 0.0
        for b, x, y in zip(bx, xs, ys):
            if abs(int(x // bin_um) - best[0]) <= 1 and abs(int(y // bin_um) - best[1]) <= 1:
                a = (b[2] - b[0]) * (b[3] - b[1])
                wx += x * a
                wy += y * a
                wt += a
        p["anchor_um"] = [round(wx / wt, 2), round(wy / wt, 2)] if wt else p["centroid_um"]
        p["spread_pct"] = round(100.0 * (core[2] - core[0]) * (core[3] - core[1]) / (dw * dh), 1)
        p["compact"] = bool(p["spread_pct"] <= 20.0)
    return parts

