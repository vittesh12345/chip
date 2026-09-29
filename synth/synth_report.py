#!/usr/bin/env python3
"""Reporting helpers for the synth area.

  synth_report.py counts <synth_stat.json> <synth_ltp.txt>
      cell / flip-flop counts and logic depth of one synthesis run
  synth_report.py yowasp-compare <native dir> <yowasp dir>
      compare two runs of synth/synth_generic.ys (cells by type, FF bits);
      exit 1 if the flip-flop counts differ
  synth_report.py trim-log <synth.log>
      pass headings, check results, statistics and warnings of a Yosys log
  synth_report.py summary --build <$(BUILD)/synth> --out <summary.md> --rtl "<files>"
      reports/synth/summary.md from the result files of every synth target
"""

import argparse
import json
import os
import re
import sys

FF_TYPE = re.compile(r"^\$_(DFF|DFFE|SDFF|SDFFE|SDFFCE|DFFSR|DFFSRE|ALDFF|ALDFFE)_[NP01]+_$|^\$_FF_$")
BRIEF_LOGIC_CELLS = 4356          # brief page 4: "4,356 generic logic cells"
BRIEF_FF_BITS = 521               # brief page 4 and SPEC section 7


def counts(stat_json):
    """Counts from `stat -json -top orbit_demo` (design section = whole hierarchy)."""
    with open(stat_json) as fh:
        data = json.load(fh)
    design = data["design"]
    by_type = {t: n for t, n in design["num_cells_by_type"].items() if t.startswith("$_") or t == "$scopeinfo"}
    ff = sum(n for t, n in by_type.items() if FF_TYPE.match(t))
    scope = by_type.get("$scopeinfo", 0)
    total = design["num_cells"]
    return {"total": total, "ff": ff, "scopeinfo": scope, "logic": total - ff - scope,
            "by_type": by_type, "submodules": design.get("num_submodules", 0),
            "creator": data.get("creator", "?")}


def ltp_depth(ltp_txt):
    try:
        with open(ltp_txt) as fh:
            text = fh.read()
    except OSError:
        return None, None
    m = re.search(r"Longest topological path in \S+ \(length=(\d+)\)", text)
    start = re.search(r"^\s+0: (\S+ ?\[?\d*\]?)", text, re.M)
    end = re.search(r"^\s+ff: (\S+ ?\[?\d*\]?)", text, re.M)
    path = "%s -> %s" % (start.group(1).strip() if start else "?", end.group(1).strip() if end else "?")
    return (int(m.group(1)) if m else None), path


def fmt_counts(c, depth=None, path=None):
    lines = ["cells (whole hierarchy)       %d" % c["total"],
             "  generic logic cells         %d" % c["logic"],
             "  flip-flop cells (1 bit)     %d" % c["ff"],
             "  $scopeinfo (no logic)       %d" % c["scopeinfo"],
             "kept orbit_keep_reg instances %d" % c["submodules"],
             "cell types                    %s" % ", ".join("%s %d" % kv for kv in sorted(c["by_type"].items()))]
    if depth is not None:
        lines.append("logic depth (ltp -noff)       %d generic gates, %s" % (depth, path))
    return "\n".join(lines) + "\n"


def cmd_counts(args):
    c = counts(args.stat)
    depth, path = ltp_depth(args.ltp)
    sys.stdout.write(fmt_counts(c, depth, path))
    return 0


def cmd_yowasp_compare(args):
    a = counts(os.path.join(args.native, "synth_stat.json"))
    b = counts(os.path.join(args.yowasp, "synth_stat.json"))
    types = sorted(set(a["by_type"]) | set(b["by_type"]))
    lines = ["Native Yosys vs YoWASP Yosys, same script (synth/synth_generic.ys) and RTL", "",
             "native: %s" % a["creator"], "yowasp: %s" % b["creator"], "",
             "%-18s %8s %8s %6s" % ("", "native", "yowasp", "diff")]
    for key, label in (("total", "cells"), ("logic", "logic cells"), ("ff", "flip-flop bits")):
        lines.append("%-18s %8d %8d %+6d" % (label, a[key], b[key], b[key] - a[key]))
    lines.append("")
    for t in types:
        x, y = a["by_type"].get(t, 0), b["by_type"].get(t, 0)
        lines.append("  %-16s %8d %8d %+6d" % (t, x, y, y - x))
    lines.append("")
    same_ff = a["ff"] == b["ff"]
    same_cells = a["total"] == b["total"] and a["by_type"] == b["by_type"]
    lines.append("flip-flop bits %s; logic cell counts %s" % (
        "MATCH" if same_ff else "DIFFER", "MATCH" if same_cells else "DIFFER (%+d logic cells)" % (b["logic"] - a["logic"])))
    lines.append("YOWASP_COMPARE %s" % ("PASS" if same_ff else "FAIL"))
    text = "\n".join(lines) + "\n"
    sys.stdout.write(text)
    return 0 if same_ff else 1


def cmd_trim_log(args):
    keep = []
    in_stat = False
    with open(args.log) as fh:
        lines = fh.read().splitlines()
    for i, l in enumerate(lines):
        heading = re.match(r"^(\d+)(\.\d+)?\. Executing", l)
        if re.match(r"^\d+(\.\d+)*\. Printing statistics", l):
            in_stat = True
        elif heading or l.startswith("End of script"):
            in_stat = False
        if (in_stat or heading or re.search(r"Yosys \d+\.\d+", l) or l.startswith(("Warning", "ERROR"))
                or re.search(r"Found and reported \d+ problems|found no problems|^Checking module|"
                             r"Longest topological path|^End of script|^Time spent|Removed \d+ unused", l)):
            keep.append(l)
    sys.stdout.write("# trimmed from %s: %d of %d lines (pass headings, checks, statistics)\n"
                     % (os.path.basename(args.log), len(keep), len(lines)))
    sys.stdout.write("\n".join(keep) + "\n")
    return 0


def last_line(path, prefix):
    """The result line (starting with prefix) of a result file, or None."""
    try:
        with open(path) as fh:
            for l in reversed(fh.read().splitlines()):
                if l.startswith(prefix):
                    return l
    except OSError:
        pass
    return None


def verdict(line, word="PASS"):
    if line is None:
        return "NOT RUN"
    return "PASS" if (" %s" % word) in line or line.endswith(word) else "FAIL"


def cmd_summary(args):
    b = args.build
    rows = []
    notes = []

    # 1. synthesis and structural checks
    gen = last_line(os.path.join(b, "synth_counts.txt"), "SYNTH_GENERIC")
    c = counts(os.path.join(b, "synth_stat.json")) if os.path.exists(os.path.join(b, "synth_stat.json")) else None
    depth, path = ltp_depth(os.path.join(b, "synth_ltp.txt"))
    if c:
        rows.append(("Generic synthesis + structural checks (check -assert, no latches, generic cells only)",
                     verdict(gen), "%d cells: %d generic logic cells + %d flip-flops (+%d $scopeinfo)"
                     % (c["total"], c["logic"], c["ff"], c["scopeinfo"])))
        rows.append(("Brief p.4: 521 flip-flop bits", "PASS" if c["ff"] == BRIEF_FF_BITS else "FAIL",
                     "%d flip-flop bits" % c["ff"]))
        rows.append(("Brief p.4: 4,356 generic logic cells", "DIFFERS" if c["logic"] != BRIEF_LOGIC_CELLS else "MATCH",
                     "%d generic logic cells (%+d, %+.1f%%) with native Yosys"
                     % (c["logic"], c["logic"] - BRIEF_LOGIC_CELLS, 100.0 * (c["logic"] - BRIEF_LOGIC_CELLS) / BRIEF_LOGIC_CELLS)))
    else:
        rows.append(("Generic synthesis + structural checks", "NOT RUN", "no synth_stat.json"))

    # 2. storage audit
    for fname, label in (("storage_audit.txt", "Storage audit, netlist as synthesized (hierarchical)"),
                         ("storage_audit_flat.txt", "Storage audit, same netlist flattened (no re-optimization)")):
        l = last_line(os.path.join(b, fname), "STORAGE_AUDIT")
        rows.append((label, verdict(l), l.split(": ", 1)[1] if l else "-"))
    l = last_line(os.path.join(b, "audit_selftest.log"), "AUDIT_SELFTEST")
    rows.append(("Audit self-test (defects injected into the flat netlist must be detected)", verdict(l),
                 l.split(": ", 1)[1] if l else "-"))

    # 3. negative control
    nc_path = os.path.join(b, "negative_control.txt")
    l = last_line(nc_path, "NEGATIVE_CONTROL")
    nk = last_line(nc_path, "nokeep:")
    rk = last_line(nc_path, "regkeep:")
    rows.append(("Negative control: keep_hierarchy removed (audit must FAIL)", verdict(l),
                 nk.split(": ", 1)[1].strip() if nk else "-"))
    rows.append(("Observation: (* keep *) on the register only", "INFO",
                 rk.split(": ", 1)[1].strip() if rk else "NOT RUN"))

    # 4. equivalence
    l = last_line(os.path.join(b, "equiv_result.txt"), "EQUIV")
    rows.append(("Equivalence netlist vs RTL (+2 mutants that must fail)", verdict(l),
                 l.split(": ", 1)[1] if l and ": " in l else (l or "-")))

    # 5. gate-level simulation
    l = last_line(os.path.join(b, "gls", "result.txt"), "SYNTH_GLS")
    rows.append(("Gate-level simulation of tb/tb_orbit_demo.v on the netlist (simcells/simlib)", verdict(l),
                 l.split(": ", 1)[1] if l and ": " in l else (l or "-")))

    # 6. YoWASP
    cmp_path = os.path.join(b, "yowasp", "compare.txt")
    l = last_line(cmp_path, "YOWASP_COMPARE")
    detail = last_line(cmp_path, "flip-flop bits")
    au = last_line(os.path.join(b, "yowasp", "storage_audit.txt"), "STORAGE_AUDIT")
    rows.append(("YoWASP Yosys 0.69 run: FF bits equal native, audit passes",
                 "PASS" if verdict(l) == "PASS" and verdict(au) == "PASS" else
                 ("NOT RUN" if l is None else "FAIL"),
                 "%s; audit %s" % (detail or "-", verdict(au))))
    if c and os.path.exists(os.path.join(b, "yowasp", "synth_stat.json")):
        y = counts(os.path.join(b, "yowasp", "synth_stat.json"))
        rows.append(("Brief p.4 cell count with YoWASP", "DIFFERS" if y["logic"] != BRIEF_LOGIC_CELLS else "MATCH",
                     "%d generic logic cells, %d cells total, %d flip-flop bits" % (y["logic"], y["total"], y["ff"])))

    if depth is not None:
        rows.append(("Logic depth estimate (ltp -noff, generic gates)", "INFO", "%d gates: %s" % (depth, path)))

    out = ["# Synth area: generic synthesis and structural checks", "",
           "Generated by `make synth-report` (synth/synth_report.py) from `%s`." % b,
           "RTL: `%s`. Top: `orbit_demo`." % args.rtl, ""]
    if c:
        out.append("Tool: %s" % c["creator"])
        out.append("")
    out += ["| Check | Result | Evidence |", "|---|---|---|"]
    for name, res, ev in rows:
        out.append("| %s | %s | %s |" % (name, res, ev.replace("|", "/")))
    out.append("")
    with open(args.notes) as fh:
        out.append(fh.read().rstrip())
    out.append("")
    with open(args.out, "w") as fh:
        fh.write("\n".join(out))
    bad = [r for r in rows if r[1] in ("FAIL", "NOT RUN")]
    print("synth-report: wrote %s (%d checks, %d failed or not run)" % (args.out, len(rows), len(bad)))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("counts")
    p.add_argument("stat")
    p.add_argument("ltp")
    p.set_defaults(func=cmd_counts)
    p = sub.add_parser("yowasp-compare")
    p.add_argument("native")
    p.add_argument("yowasp")
    p.set_defaults(func=cmd_yowasp_compare)
    p = sub.add_parser("trim-log")
    p.add_argument("log")
    p.set_defaults(func=cmd_trim_log)
    p = sub.add_parser("summary")
    p.add_argument("--build", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--rtl", default="")
    p.add_argument("--notes", required=True, help="markdown appended after the table")
    p.set_defaults(func=cmd_summary)
    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
