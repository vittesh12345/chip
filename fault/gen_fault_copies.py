#!/usr/bin/env python3
"""Generate single-event-upset (SEU) test copies of the ORBIT-AI RTL.

The production RTL (the files of $(RTL), read from $(RTL_DIR)) is never
modified. For every scenario this script writes, under <out>/<scenario>/:

  orbit_*_fi.v        a copy of every production module, renamed with the
                      suffix _fi so that it can sit next to the unmodified
                      production design (the fault-free reference) in one
                      formal model. The copy has the same ports as the
                      production design: no fault port is added anywhere.
  orbit_keep_reg_seu_fi.v
                      (storage scenarios on orbit_keep_reg instances) a variant
                      of orbit_keep_reg with an injectable upset; exactly one
                      instance name of the parent module is switched to it.
  injection.diff      unified diff of the injected copy against the plain
                      renamed copy, i.e. exactly what the injection changed.
  fi_scenario.vh      defines for the harness (fault/fi_harness.sv).
  fi_points.vh        hierconn declarations of the injection controls.
  fault.sby           SymbiYosys job (reference RTL + copy + harness).
  tasks.tsv           the tasks of fault.sby and their expected status.

Injection model. The injected storage element is rewritten as
    R <= R_next ^ fi_mask
where R_next is the unchanged next-state logic of the production RTL and
fi_mask has at most one bit set, in a cycle chosen by the solver
(fi_req = $anyseq) at a bit chosen by the solver (fi_bit = $anyconst). This is
a bit flip of the stored value between two clock edges: it is visible from
the next cycle on and stays until the register is written again, which is
what a flip at the falling edge does in simulation. The harness allows one
upset in the whole design per trace (single-upset model). The negative
scenario neg_product instead applies a one-cycle transient (SET) to the
shared product of one lane, which is combinational.

With --write-mutant no_compare the script instead writes a copy of the RTL
whose copy comparator is removed (a negative control for the checks).

The transforms are plain text rewrites of the production sources. Each one
checks that its pattern matches exactly where expected and stops with an
error otherwise, so a changed RTL cannot silently produce a copy without a
fault.
"""

import argparse
import difflib
import hashlib
import os
import re
import sys

SUFFIX = "_fi"
MODULES = ("orbit_keep_reg", "orbit_mac_lane", "orbit_thermal_tmr", "orbit_demo")

# Harness state-vector groups (see fault/fi_harness.sv).
GROUP = {"acc_a": 0, "acc_b": 1, "res_a": 2, "res_b": 3,
         "copy0": 4, "copy1": 5, "copy2": 6,
         "phase": 7, "out_valid_q": 8, "fault_q": 9}

# name -> scenario description.
#   kind  keep: switch instance `inst` of `module` to the SEU keep_reg variant
#         reg:  inject into plain register `reg` of `module`
#         wire: one-cycle transient on combinational wire `wire` of `module`
#   klass LANE (duplicated lane storage), THERM (thermal copy), NEG (unprotected)
SCENARIOS = {
    "acc_a": dict(kind="keep", module="orbit_mac_lane", inst="u_acc_a", klass="LANE", group="acc_a",
                  what="accumulator copy A (u_acc_a), any lane, any bit, any cycle"),
    "acc_b": dict(kind="keep", module="orbit_mac_lane", inst="u_acc_b", klass="LANE", group="acc_b",
                  what="accumulator copy B (u_acc_b), any lane, any bit, any cycle"),
    "res_a": dict(kind="keep", module="orbit_mac_lane", inst="u_res_a", klass="LANE", group="res_a",
                  what="result copy A (u_res_a, drives out_data), any lane, any bit, any cycle"),
    "res_b": dict(kind="keep", module="orbit_mac_lane", inst="u_res_b", klass="LANE", group="res_b",
                  what="result copy B (u_res_b), any lane, any bit, any cycle"),
    "therm_c0": dict(kind="keep", module="orbit_thermal_tmr", inst="u_copy0", klass="THERM", group="copy0",
                     what="thermal state copy 0 (u_thermal.u_copy0), any bit, any cycle"),
    "therm_c1": dict(kind="keep", module="orbit_thermal_tmr", inst="u_copy1", klass="THERM", group="copy1",
                     what="thermal state copy 1 (u_thermal.u_copy1), any bit, any cycle"),
    "therm_c2": dict(kind="keep", module="orbit_thermal_tmr", inst="u_copy2", klass="THERM", group="copy2",
                     what="thermal state copy 2 (u_thermal.u_copy2), any bit, any cycle"),
    "neg_out_valid_q": dict(kind="reg", module="orbit_demo", reg="out_valid_q", klass="NEG", group="out_valid_q",
                            what="out_valid_q (unprotected output-buffer valid flag), any cycle"),
    "neg_product": dict(kind="wire", module="orbit_mac_lane", wire="prod32", klass="NEG", group=None,
                        what="shared product prod32 (combinational, feeds both copies), any lane, any bit, one cycle"),
}

# SymbiYosys tasks: name -> (sby options, harness defines, expected status, description).
TASKS_PROTECTED = [
    ("prove", ["mode prove", "depth {prove_depth}"], "", "PASS",
     "all properties, unbounded (k-induction, k={prove_depth})"),
    ("cover", ["mode cover", "depth {cover_depth}"], "-DFI_COVER_TASK", "PASS",
     "reachability of the upset situations (non-vacuity)"),
]
# Negative control (--negctl, on an RTL copy without the copy comparator):
# the same checks must now fail.
TASKS_NEGCTL = [
    ("prove", ["mode prove", "depth {prove_depth}"], "", "FAIL",
     "all properties; must FAIL without the comparator"),
    ("fire", ["mode bmc", "depth {neg_depth}"], "-DFI_SELECT -DFI_CHK_FIRE", "FAIL",
     "D_out_fire_matches_ref must FAIL without the comparator (wrong result transferred)"),
]
TASK_NEG_COVER = ("cover", ["mode cover", "depth {cover_depth}"], "-DFI_COVER_TASK", "PASS",
                  "the escape situations are reachable")
TASKS_NEG = {
    "neg_out_valid_q": [
        TASK_NEG_COVER,
        ("fire", ["mode bmc", "depth {neg_depth}"], "-DFI_SELECT -DFI_CHK_FIRE", "FAIL",
         "D_out_fire_matches_ref must FAIL (extra / duplicated result)"),
        ("loss", ["mode bmc", "depth {neg_depth}"], "-DFI_SELECT -DFI_CHK_LOSS", "FAIL",
         "D_no_silent_loss must FAIL (result dropped without fault)"),
    ],
    "neg_product": [
        TASK_NEG_COVER,
        ("fire", ["mode bmc", "depth {neg_depth}"], "-DFI_SELECT -DFI_CHK_FIRE", "FAIL",
         "D_out_fire_matches_ref must FAIL (wrong result transferred, no fault)"),
    ],
}

# Negative controls: RTL copies with the protection removed (module names
# unchanged, so that every bench and harness can run them via RTL_DIR).
MUTANTS = {
    "no_compare": ("orbit_mac_lane", r"assign\s+mismatch\s*=\s*[^;]*;",
                   "assign mismatch = 1'b0;   // MUTANT no_compare: copy comparator removed"),
}

GEN_BEGIN = "// ---- fault-injection copy: generated by fault/gen_fault_copies.py ----"
GEN_END = "// ---- end of generated fault injection ----"


class GenError(Exception):
    pass


def sha256(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def module_of(text):
    names = re.findall(r"^\s*module\s+(\w+)", text, re.M)
    if len(names) != 1:
        raise GenError("expected exactly one module per file, found %s" % names)
    return names[0]


def rename_modules(text):
    for m in MODULES:
        text = re.sub(r"\b%s\b" % m, m + SUFFIX, text)
    return text


def reg_range(text, name):
    """(range text, width expression) of `reg [msb:lsb] name`; ("", "1")
    without a range."""
    m = re.search(r"\breg\s*(\[\s*([^\]:]+?)\s*:\s*([^\]]+?)\s*\])?\s*%s\b" % re.escape(name), text)
    if not m:
        raise GenError("no reg declaration for %s" % name)
    if not m.group(1):
        return "", "1"
    return m.group(1), "((%s) - (%s) + 1)" % (m.group(2), m.group(3))


def fi_decls(width, indent="    "):
    """Declarations of the injection control for a `width`-bit element."""
    lines = [
        GEN_BEGIN,
        "// fi_req: inject in this cycle (free; fault/fi_harness.sv allows one",
        "// upset in the whole design per trace). fi_bit: which bit (free constant).",
        "localparam integer FI_W  = %s;" % width,
        "localparam integer FI_BW = (FI_W > 1) ? $clog2(FI_W) : 1;",
        "wire             fi_req = $anyseq;",
        "wire [FI_BW-1:0] fi_bit = $anyconst;",
        "wire [FI_W-1:0]  fi_one = 1;",
        "wire [FI_W-1:0]  fi_mask = fi_req ? (fi_one << fi_bit) : {FI_W{1'b0}};",
        "`ifdef FORMAL",
        "always @* assume (fi_bit < FI_W);",
        "`endif",
    ]
    return "".join((l if l.startswith("`") else indent + l) + "\n" for l in lines)


def find_seq_block(text, reg):
    """(start, body_start, body_end, end) of the `always @(posedge clk) begin
    ... end` block that assigns `reg`."""
    found = []
    for m in re.finditer(r"always\s*@\s*\(\s*posedge\s+clk\s*\)\s*begin\b", text):
        depth = 1
        for t in re.finditer(r"\b(begin|end)\b", text[m.end():]):
            depth += 1 if t.group(1) == "begin" else -1
            if depth == 0:
                body_end = m.end() + t.start()
                end = m.end() + t.end()
                break
        else:
            raise GenError("unbalanced begin/end after %r" % m.group(0))
        body = text[m.end():body_end]
        if re.search(r"\b%s\s*<=" % re.escape(reg), body):
            # Start at the beginning of the line to keep the indentation.
            start = text.rfind("\n", 0, m.start()) + 1
            found.append((start, m.end(), body_end, end))
    if len(found) != 1:
        raise GenError("expected one sequential block assigning %s, found %d" % (reg, len(found)))
    return found[0]


def nba_targets(body):
    """Nonblocking-assignment targets at statement positions (so that a `<=`
    comparison inside a condition is never mistaken for an assignment)."""
    targets = []
    for m in re.finditer(r"(\w+)(\s*\[[^\]]*\])?\s*<=", body):
        before = body[:m.start()].rstrip()
        if before == "" or before.endswith((";", ")")) or re.search(r"\b(begin|else)$", before):
            if m.group(2):
                raise GenError("bit-select assignment %r is not supported" % m.group(0))
            targets.append((m.start(), m.end(), m.group(1)))
    return targets


def inject_reg(text, reg):
    """Split the sequential block that assigns `reg` into next-state logic and
    a register, and apply the upset mask to `reg` as it is stored."""
    start, body_start, body_end, end = find_seq_block(text, reg)
    body = text[body_start:body_end]
    targets = nba_targets(body)
    names = []
    for _, _, n in targets:
        if n not in names:
            names.append(n)
    if reg not in names:
        raise GenError("%s is not a statement-level target of its block" % reg)
    # Every other `<=` in the body must be a comparison inside a
    # parenthesised condition; refuse anything that was not classified.
    stripped = body
    for s, e, _ in reversed(targets):
        stripped = stripped[:s] + stripped[e:]
    for m in re.finditer(r"<=", stripped):
        if stripped[:m.start()].count("(") <= stripped[:m.start()].count(")"):
            raise GenError("unclassified '<=' in the block of %s" % reg)
    new_body = body
    for s, e, n in reversed(targets):
        new_body = new_body[:s] + new_body[s:e].replace("<=", "=").replace(n, n + "__fi_n", 1) + new_body[e:]

    ind = re.match(r"[ \t]*", text[start:]).group(0)
    ranges = {n: reg_range(text, n) for n in names}
    out = [fi_decls(ranges[reg][1], ind)]
    out.append(ind + "// The production sequential block, split into its unchanged next-state\n")
    out.append(ind + "// logic (now blocking assignments to *__fi_n) and a plain register.\n")
    for n in names:
        rng = ranges[n][0] + " " if ranges[n][0] else ""
        out.append("%sreg %s%s__fi_n;\n" % (ind, rng, n))
    out.append(ind + "always @* begin\n")
    for n in names:
        out.append("%s    %s__fi_n = %s;\n" % (ind, n, n))
    out.append(new_body.strip("\n").rstrip() + "\n")
    out.append(ind + "end\n")
    out.append(ind + "always @(posedge clk) begin\n")
    for n in names:
        if n == reg:
            out.append("%s    %s <= %s__fi_n ^ fi_mask;   // single-event upset\n" % (ind, n, n))
        else:
            out.append("%s    %s <= %s__fi_n;\n" % (ind, n, n))
    out.append(ind + "end\n")
    out.append(ind + GEN_END)
    return text[:start] + "".join(out) + text[end:]


def inject_wire(text, wire):
    """One-cycle transient on a combinational wire: `wire [..] w = expr;`
    becomes `wire [..] w = (expr) ^ fi_mask;`."""
    pat = re.compile(r"^([ \t]*)wire\s*(\[\s*([^\]:]+?)\s*:\s*([^\]]+?)\s*\])?\s*%s\s*=\s*(.*?);[^\n]*$"
                     % re.escape(wire), re.M)
    ms = list(pat.finditer(text))
    if len(ms) != 1:
        raise GenError("expected one declaration-assignment of wire %s, found %d" % (wire, len(ms)))
    m = ms[0]
    ind = m.group(1)
    width = "1" if not m.group(2) else "((%s) - (%s) + 1)" % (m.group(3), m.group(4))
    new = (fi_decls(width, ind) +
           "%swire %s%s = (%s) ^ fi_mask;   // single-event transient\n%s%s"
           % (ind, m.group(2) + " " if m.group(2) else "", wire, m.group(5), ind, GEN_END))
    return text[:m.start()] + new + text[m.end():]


def switch_instance(text, parent, inst):
    """Instantiate the SEU keep_reg variant for instance `inst`."""
    pat = re.compile(r"\borbit_keep_reg%s(\s*#\s*\((?:[^()]|\([^()]*\))*\))?(\s+%s\s*\()" % (SUFFIX, re.escape(inst)))
    ms = list(pat.finditer(text))
    if len(ms) != 1:
        raise GenError("expected one orbit_keep_reg instance %s in %s, found %d" % (inst, parent, len(ms)))
    m = ms[0]
    return text[:m.start()] + "orbit_keep_reg_seu%s%s%s" % (SUFFIX, m.group(1) or "", m.group(2)) + text[m.end():]


def lanes_of(demo_text):
    m = re.search(r"parameter\s+integer\s+LANES\s*=\s*(\d+)", demo_text)
    if not m:
        raise GenError("LANES parameter not found in orbit_demo")
    return int(m.group(1))


def instance_paths(module, lanes, demo_text):
    """Hierarchical paths (below the top instance) of every instance of `module`."""
    if module == "orbit_demo":
        return [""]
    if module == "orbit_mac_lane":
        if not re.search(r"begin\s*:\s*g_lane\b", demo_text) or not re.search(r"\borbit_mac_lane\s+u_lane\s*\(", demo_text):
            raise GenError("orbit_demo no longer instantiates orbit_mac_lane as g_lane[i].u_lane")
        return ["g_lane[%d].u_lane." % i for i in range(lanes)]
    if module == "orbit_thermal_tmr":
        if not re.search(r"\borbit_thermal_tmr\b(\s*#\s*\((?:[^()]|\([^()]*\))*\))?\s+u_thermal\s*\(", demo_text):
            raise GenError("orbit_demo no longer instantiates orbit_thermal_tmr as u_thermal")
        return ["u_thermal."]
    raise GenError("no instance path for module %s" % module)


def ports_of(text, module):
    m = re.search(r"\bmodule\s+%s\b.*?\)\s*;" % re.escape(module), text, re.S)
    if not m:
        raise GenError("header of %s not found" % module)
    hdr = re.sub(r"//[^\n]*", "", m.group(0))
    # The port list follows the (optional) parameter list.
    return re.findall(r"\b(?:input|output|inout)\s+(?:wire|reg)?\s*(?:signed\s*)?(?:\[[^\]]*\]\s*)?(\w+)", hdr)


def write(path, text):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        f.write(text)
    os.replace(tmp, path)


def gen_scenario(name, sc, src, out_root, harness, rtl_files, depths, negctl=False):
    lanes = lanes_of(src["orbit_demo"])
    copies = {m: rename_modules(src[m]) for m in MODULES}
    plain = dict(copies)
    files = {}
    if sc["kind"] == "keep":
        seu = copies["orbit_keep_reg"].replace("module orbit_keep_reg%s" % SUFFIX,
                                               "module orbit_keep_reg_seu%s" % SUFFIX, 1)
        if seu == copies["orbit_keep_reg"]:
            raise GenError("module header of orbit_keep_reg not found")
        seu = inject_reg(seu, "q")
        files["orbit_keep_reg_seu%s.v" % SUFFIX] = seu
        copies[sc["module"]] = switch_instance(copies[sc["module"]], sc["module"], sc["inst"])
        points = [p + sc["inst"] + "." for p in instance_paths(sc["module"], lanes, src["orbit_demo"])]
    elif sc["kind"] == "reg":
        copies[sc["module"]] = inject_reg(copies[sc["module"]], sc["reg"])
        points = instance_paths(sc["module"], lanes, src["orbit_demo"])
    elif sc["kind"] == "wire":
        copies[sc["module"]] = inject_wire(copies[sc["module"]], sc["wire"])
        points = instance_paths(sc["module"], lanes, src["orbit_demo"])
    else:
        raise GenError("unknown kind %s" % sc["kind"])

    # No fault port: the copy's top has exactly the production port list.
    p_prod = ports_of(src["orbit_demo"], "orbit_demo")
    p_copy = ports_of(copies["orbit_demo"], "orbit_demo" + SUFFIX)
    if p_prod != p_copy or not p_prod:
        raise GenError("port list of the copy differs from production: %s vs %s" % (p_copy, p_prod))

    d = os.path.join(out_root, name)
    os.makedirs(d, exist_ok=True)
    for m in MODULES:
        files["%s%s.v" % (m, SUFFIX)] = copies[m]
    for fn, text in files.items():
        write(os.path.join(d, fn), text)

    # Diff of the injected copy against the plain renamed copy.
    diff = []
    for m in MODULES:
        diff += difflib.unified_diff(plain[m].splitlines(True), copies[m].splitlines(True),
                                     "renamed/%s%s.v" % (m, SUFFIX), "injected/%s%s.v" % (m, SUFFIX))
    if sc["kind"] == "keep":
        diff += difflib.unified_diff(plain["orbit_keep_reg"].splitlines(True), files["orbit_keep_reg_seu%s.v" % SUFFIX].splitlines(True),
                                     "renamed/orbit_keep_reg%s.v" % SUFFIX, "injected/orbit_keep_reg_seu%s.v" % SUFFIX)
    if not diff:
        raise GenError("scenario %s: the copy is identical to the production RTL" % name)
    write(os.path.join(d, "injection.diff"), "".join(diff))

    # Harness include files.
    vh = ["// Generated by fault/gen_fault_copies.py: scenario %s" % name,
          "// %s" % sc["what"],
          '`define FI_SCENARIO_NAME "%s"' % name,
          "`define FI_CLASS_%s" % sc["klass"],
          "`define FI_SCN_%s" % name,
          "`define FI_NREQ %d" % len(points)]
    if sc["group"] is not None:
        vh.append("`define FI_TARGET_GROUP %d" % GROUP[sc["group"]])
    write(os.path.join(d, "fi_scenario.vh"), "\n".join(vh) + "\n")
    pts = ["// Generated by fault/gen_fault_copies.py: injection controls of scenario %s," % name,
           "// one per instance of the injected element (read through Yosys hierconn)."]
    for p in points:
        pts.append("(* hierconn *) wire \\dut_f.%sfi_req ;" % p)
    pts.append("wire [`FI_NREQ-1:0] fi_req_vec = {%s};" %
               ", ".join("\\dut_f.%sfi_req " % p for p in reversed(points)))
    write(os.path.join(d, "fi_points.vh"), "\n".join(pts) + "\n")

    # SymbiYosys job.
    if sc["klass"] == "NEG":
        tasks = TASKS_NEG[name]
    elif negctl:
        if sc["klass"] != "LANE":
            raise GenError("--negctl applies to the lane scenarios only")
        tasks = TASKS_NEGCTL
    else:
        tasks = TASKS_PROTECTED
    copy_files = sorted(files)
    sby = ["# Generated by fault/gen_fault_copies.py: scenario %s" % name,
           "# %s" % sc["what"], "", "[tasks]"]
    sby += [t[0] for t in tasks]
    sby += ["", "[options]"]
    for t in tasks:
        for o in t[1]:
            sby.append("%s: %s" % (t[0], o.format(**depths)))
    sby += ["", "[engines]", "smtbmc yices", "", "[script]",
            "# Fault-free reference: the production RTL.",
            "read_verilog -formal %s" % " ".join(os.path.basename(f) for f in rtl_files),
            "# Generated copy with one injectable element (modules renamed *%s)." % SUFFIX,
            "read_verilog -formal %s" % " ".join(copy_files)]
    for t in tasks:
        sby.append("%s: read_verilog -formal -sv %s fi_harness.sv" % (t[0], t[2]))
    sby += ["hierarchy -top fi_harness",
            "proc",
            "# hierconn wires need flatten right after proc, without keep_hierarchy.",
            "setattr -mod -unset keep_hierarchy",
            "flatten",
            "# Fails if a hierconn path of the harness does not exist.",
            "check -assert",
            "prep -top fi_harness",
            "", "[files]"]
    sby += [os.path.abspath(f) for f in rtl_files]
    sby += [os.path.abspath(os.path.join(d, f)) for f in copy_files]
    sby += [os.path.abspath(os.path.join(d, "fi_scenario.vh")),
            os.path.abspath(os.path.join(d, "fi_points.vh")),
            os.path.abspath(harness)]
    write(os.path.join(d, "fault.sby"), "\n".join(sby) + "\n")
    write(os.path.join(d, "tasks.tsv"),
          "".join("%s\t%s\t%s\t%s\n" % (name, t[0], t[3], t[4].format(**depths)) for t in tasks))
    return d


def write_mutant(name, rtl_files, out):
    """Copy the RTL to `out` with the protection named `name` removed."""
    module, pat, repl = MUTANTS[name]
    os.makedirs(out, exist_ok=True)
    diff = []
    for f in rtl_files:
        with open(f) as fh:
            text = fh.read()
        new = text
        if module_of(text) == module:
            new, n = re.subn(pat, repl, text)
            if n != 1:
                raise GenError("mutant %s: expected one match in %s, found %d" % (name, f, n))
            diff += difflib.unified_diff(text.splitlines(True), new.splitlines(True), f, "mutant/" + os.path.basename(f))
        write(os.path.join(out, os.path.basename(f)), new)
    write(os.path.join(out, "mutation.diff"), "".join(diff))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--rtl", nargs="+", required=True, help="production RTL files ($(RTL))")
    ap.add_argument("--out", required=True, help="output root, e.g. $(BUILD)/fault/formal")
    ap.add_argument("--harness", help="fault/fi_harness.sv (scenario generation)")
    ap.add_argument("--write-mutant", choices=sorted(MUTANTS),
                    help="instead: write a copy of the RTL with this protection removed to --out")
    ap.add_argument("--negctl", action="store_true",
                    help="lane scenarios expect FAIL (use with --rtl pointing at a no_compare mutant)")
    ap.add_argument("--scenarios", default="all", help="comma-separated names or 'all'")
    ap.add_argument("--prove-depth", type=int, default=4)
    ap.add_argument("--cover-depth", type=int, default=12)
    ap.add_argument("--neg-depth", type=int, default=12)
    args = ap.parse_args()

    if args.write_mutant:
        try:
            write_mutant(args.write_mutant, args.rtl, args.out)
        except GenError as e:
            print("gen_fault_copies.py: error: %s" % e, file=sys.stderr)
            return 1
        print("[fault] mutant %s written to %s" % (args.write_mutant, args.out))
        return 0
    if not args.harness:
        ap.error("--harness is required for scenario generation")
    depths = dict(prove_depth=args.prove_depth, cover_depth=args.cover_depth,
                  neg_depth=args.neg_depth)
    names = list(SCENARIOS) if args.scenarios == "all" else args.scenarios.split(",")
    try:
        before = {f: sha256(f) for f in args.rtl}
        src = {}
        for f in args.rtl:
            with open(f) as fh:
                text = fh.read()
            src[module_of(text)] = text
        missing = [m for m in MODULES if m not in src]
        if missing:
            raise GenError("modules missing from --rtl: %s" % missing)
        for m, text in src.items():
            if re.search(r"\$any(seq|const)|\bfi_(req|mask|bit)\b", text):
                raise GenError("production module %s already contains fault-injection constructs" % m)
        os.makedirs(args.out, exist_ok=True)
        tsv = []
        for n in names:
            if n not in SCENARIOS:
                raise GenError("unknown scenario %s (known: %s)" % (n, ", ".join(SCENARIOS)))
            d = gen_scenario(n, SCENARIOS[n], src, args.out, args.harness, args.rtl, depths, args.negctl)
            with open(os.path.join(d, "tasks.tsv")) as fh:
                tsv.append(fh.read())
            print("[fault] generated %-16s %s" % (n, d))
        after = {f: sha256(f) for f in args.rtl}
        if before != after:
            raise GenError("production RTL changed while generating copies")
        write(os.path.join(args.out, "tasks.tsv"), "".join(tsv))
        write(os.path.join(args.out, "rtl.sha256"), "".join("%s  %s\n" % (h, f) for f, h in before.items()))
    except GenError as e:
        print("gen_fault_copies.py: error: %s" % e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
