#!/usr/bin/env python3
"""Collect and check the results of one ORFS run of orbit_demo.

Reads the ORFS metrics (logs/<platform>/<design>/<variant>/*.json), the final
timing report (6_finish.rpt), the LEC logs, KLayout DRC/LVS results if those
steps ran, and the storage audit of the routed netlist, then

  * writes <out>/results.md (tables) and <out>/checks.json (machine readable),
  * copies small final reports into <out>/ (trimmed where they are large),
  * exits non-zero if any check FAILs. A check whose input does not exist
    (e.g. LVS was not run) is NOT_RUN, which is not a failure unless it is
    listed in --require.

Every number comes from a tool report; nothing is estimated here.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys


def load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def read(path):
    try:
        with open(path, errors="replace") as f:
            return f.read()
    except OSError:
        return None


def section(rpt, title):
    """Return one '====\\n<when> <title>\\n----' section of an ORFS report."""
    if rpt is None:
        return None
    m = re.search(r'=+\n[^\n]*' + re.escape(title) + r'\n-+\n(.*?)(?=\n=+\n|\Z)', rpt, re.S)
    return m.group(1).strip() if m else None


def fmt(v, unit="", nd=3):
    if v is None:
        return "n/a"
    if isinstance(v, float):
        return f"{v:.{nd}f}{unit}"
    return f"{v}{unit}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--work", required=True, help="ORFS WORK_HOME")
    ap.add_argument("--platform", default="sky130hd")
    ap.add_argument("--design", default="orbit_demo")
    ap.add_argument("--variant", default="base")
    ap.add_argument("--liberty", required=True, help="liberty file for the storage audit")
    ap.add_argument("--out", required=True, help="output directory for the extracted reports")
    ap.add_argument("--require", default="", help="comma separated checks that must have run (e.g. drc,lvs)")
    a = ap.parse_args()

    tail = os.path.join(a.platform, a.design, a.variant)
    logs = os.path.join(a.work, "logs", tail)
    reps = os.path.join(a.work, "reports", tail)
    ress = os.path.join(a.work, "results", tail)
    os.makedirs(a.out, exist_ok=True)

    fin = load_json(os.path.join(logs, "6_report.json"))
    drt = load_json(os.path.join(logs, "5_2_route.json"))
    syn = load_json(os.path.join(logs, "1_synth.json"))
    if not fin:
        sys.exit(f"collect_pd: no finish metrics in {logs}/6_report.json (did the flow finish?)")

    def f(key):
        return fin.get("finish__" + key)

    rpt = read(os.path.join(reps, "6_finish.rpt"))
    sdc = read(os.path.join(ress, "6_final.sdc")) or ""
    m = re.search(r'create_clock -name clk -period ([0-9.]+)', sdc)
    period = float(m.group(1)) if m else None

    checks = []  # dicts: name, result, detail

    def check(name, result, detail):
        checks.append({"name": name, "result": result, "detail": detail})

    def check_bool(name, ok, detail, ran=True):
        check(name, ("PASS" if ok else "FAIL") if ran else "NOT_RUN", detail)

    # --- timing (ORFS corner for sky130hd: the single TT liberty) ----------
    setup_ws, setup_tns = f("timing__setup__ws"), f("timing__setup__tns")
    hold_ws, hold_tns = f("timing__hold__ws"), f("timing__hold__tns")
    check_bool("setup timing", setup_ws is not None and setup_ws >= 0 and (setup_tns or 0) >= 0,
               f"period {fmt(period, ' ns')}: setup WNS {fmt(setup_ws, ' ns')}, TNS {fmt(setup_tns, ' ns')}")
    check_bool("hold timing", hold_ws is not None and hold_ws >= 0 and (hold_tns or 0) >= 0,
               f"hold WNS {fmt(hold_ws, ' ns')}, TNS {fmt(hold_tns, ' ns')}")
    drv = {k: f("timing__drv__" + k) for k in ("max_slew", "max_cap", "max_fanout",
                                                "setup_violation_count", "hold_violation_count")}
    check_bool("max slew/cap/fanout", all((drv[k] or 0) == 0 for k in ("max_slew", "max_cap", "max_fanout")),
               f"violations: slew {drv['max_slew']}, cap {drv['max_cap']}, fanout {drv['max_fanout']}")

    # --- routing / antenna -------------------------------------------------
    drc_err = drt.get("detailedroute__route__drc_errors")
    check_bool("detailed-route DRC", drc_err == 0, f"TritonRoute DRC errors after the last iteration: {drc_err}",
               ran=drc_err is not None)
    ant_nets = drt.get("detailedroute__antenna__violating__nets")
    ant_pins = drt.get("detailedroute__antenna__violating__pins")
    diodes = drt.get("detailedroute__antenna_diodes_count")
    check_bool("antenna", ant_nets == 0, f"violating nets {ant_nets}, pins {ant_pins}, repair diodes {diodes}",
               ran=ant_nets is not None)

    # --- KLayout DRC (ORFS 'drc' target) -----------------------------------
    lyrdb = os.path.join(reps, "6_drc.lyrdb")
    cnt = read(os.path.join(reps, "6_drc_count.rpt"))
    drc_categories = {}
    if cnt is not None:
        n_drc = int(cnt.strip() or 0)
        txt = read(lyrdb) or ""
        for cat in re.findall(r'<item>\s*<tags>[^<]*</tags>\s*<category>([^<]*)</category>', txt):
            drc_categories[cat.strip("'")] = drc_categories.get(cat.strip("'"), 0) + 1
        check_bool("KLayout DRC", n_drc == 0,
                   f"{n_drc} markers ({os.path.basename(lyrdb)}, sky130hd.lydrc from ORFS)"
                   + ("; " + ", ".join(f"{k}: {v}" for k, v in sorted(drc_categories.items())) if drc_categories else ""))
    else:
        check("KLayout DRC", "NOT_RUN", "6_drc.lyrdb not produced (run the ORFS 'drc' target)")

    # --- KLayout LVS (ORFS 'lvs' target) -----------------------------------
    lvs_log = read(os.path.join(logs, "6_lvs.log"))
    if lvs_log is not None:
        ok = re.search(r'Congratulations! Netlists match', lvs_log) is not None
        bad = re.search(r"Netlists don't match|ERROR", lvs_log)
        check_bool("KLayout LVS", ok and not bad,
                   "netlists match" if ok and not bad else "LVS log does not report a match (see 6_lvs.log)")
    else:
        check("KLayout LVS", "NOT_RUN", "6_lvs.log not produced (run the ORFS 'lvs' target)")

    # --- ORFS logic equivalence (kepler-formal) ----------------------------
    for step, label in (("4_rsz", "LEC synth vs post-CTS repair"), ("6_final", "LEC synth vs final")):
        log = read(os.path.join(logs, f"{step}_lec_check.log"))
        if log is None:
            check(label, "NOT_RUN", f"{step}_lec_check.log missing (LEC_CHECK off?)")
        else:
            ok = "Circuits are IDENTICAL" in log
            check_bool(label, ok, "kepler-formal: " + ("Circuits are IDENTICAL" if ok else "not identical / error"))

    # --- storage audit of the routed netlist -------------------------------
    audit_rpt = os.path.join(a.out, "storage_audit.txt")
    netlist = os.path.join(ress, "6_final.v")
    audit = subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                         "audit_storage.py"),
                            "--netlist", netlist, "--liberty", a.liberty, "--report", audit_rpt],
                           capture_output=True, text=True)
    at = audit.stdout
    mcount = re.search(r'flip-flop count: (\d+) flip-flop cells', at)
    check_bool("storage audit (6_final.v)", audit.returncode == 0,
               (f"{mcount.group(1)} flip-flop cells; " if mcount else "")
               + (re.search(r'RESULT: .*', at).group(0) if re.search(r'RESULT: .*', at) else audit.stderr.strip()[-200:]))

    # --- GDS -----------------------------------------------------------------
    gds = os.path.join(ress, "6_final.gds")
    check_bool("final GDS written", os.path.isfile(gds),
               f"{gds} ({os.path.getsize(gds) / 1e6:.1f} MB)" if os.path.isfile(gds) else "no 6_final.gds")

    # --- numbers -------------------------------------------------------------
    nums = {
        "clock period (ns)": period,
        "fmax from final STA (MHz)": (f("timing__fmax") or 0) / 1e6 if f("timing__fmax") else None,
        "setup WNS (ns)": setup_ws, "setup TNS (ns)": setup_tns,
        "hold WNS (ns)": hold_ws, "hold TNS (ns)": hold_tns,
        "clock skew setup (ns)": f("clock__skew__setup"),
        "die area (um^2)": f("design__die__area"), "core area (um^2)": f("design__core__area"),
        "std-cell area incl. fill/tap/buffers (um^2)": f("design__instance__area__stdcell"),
        "utilization (cell area / core area)": f("design__instance__utilization"),
        "instance count (incl. tap/fill-free physical cells)": f("design__instance__count"),
        "synthesis cell area (um^2)": syn.get("synth__design__instance__area__stdcell"),
        "synthesis cell count": syn.get("synth__design__instance__count__stdcell"),
        "IO pins": f("design__io"),
        "power total (W, default activity)": f("power__total"),
        "power internal (W)": f("power__internal__total"),
        "power switching (W)": f("power__switching__total"),
        "power leakage (W)": f("power__leakage__total"),
        "routed wirelength (um)": drt.get("detailedroute__route__wirelength"),
        "vias": drt.get("detailedroute__route__vias"),
        "detailed-route DRC errors": drc_err,
        "antenna violating nets": ant_nets,
        "IR drop VDD worst (V)": f("design_powergrid__drop__worst__net:VDD__corner:default"),
    }

    # Cell usage from the final report log (report_cell_usage).
    rlog = read(os.path.join(logs, "6_report.log")) or ""
    usage = None
    mu = re.search(r'(Cell type report:.*?)(?:\n\s*\n|\Z)', rlog, re.S)
    if mu:
        usage = mu.group(1).rstrip()

    # Worst setup and hold paths.
    worst_max = section(rpt, "report_checks -path_delay max")
    worst_min = section(rpt, "report_checks -path_delay min")
    power_sec = section(rpt, "report_power")

    # --- write outputs -------------------------------------------------------
    with open(os.path.join(a.out, "checks.json"), "w") as fh:
        json.dump({"platform": a.platform, "variant": a.variant, "checks": checks,
                   "numbers": nums}, fh, indent=2)
    if worst_max:
        with open(os.path.join(a.out, "worst_setup_path.txt"), "w") as fh:
            fh.write(worst_max + "\n")
    if worst_min:
        with open(os.path.join(a.out, "worst_hold_path.txt"), "w") as fh:
            fh.write(worst_min + "\n")
    if power_sec:
        with open(os.path.join(a.out, "power_default_activity.txt"), "w") as fh:
            fh.write("OpenSTA report_power on the routed design with RCX parasitics and the\n"
                     "tool's DEFAULT switching activity (no simulation activity annotated).\n"
                     "This is an estimate, not a measurement.\n\n" + power_sec + "\n")
    if usage:
        with open(os.path.join(a.out, "cell_usage.txt"), "w") as fh:
            fh.write(usage + "\n")
    for src, dst in ((os.path.join(reps, "synth_stat.txt"), "synth_stat.txt"),
                     (os.path.join(reps, "6_finish.rpt"), "6_finish.rpt"),
                     (os.path.join(reps, "6_drc_count.rpt"), "6_drc_count.rpt")):
        if os.path.isfile(src) and os.path.getsize(src) < 400_000:
            shutil.copyfile(src, os.path.join(a.out, dst))

    lines = [f"# ORFS results: {a.design} on {a.platform} (variant {a.variant})", "",
             "Generated by pd/collect_pd.py from the ORFS logs, reports and results.", "",
             "## Checks", "", "| Check | Result | Detail |", "|---|---|---|"]
    for c in checks:
        lines.append(f"| {c['name']} | {c['result']} | {c['detail']} |")
    lines += ["", "## Numbers", "", "| Quantity | Value |", "|---|---|"]
    for k, v in nums.items():
        lines.append(f"| {k} | {fmt(v, nd=4) if isinstance(v, float) else fmt(v)} |")
    if worst_max:
        lines += ["", "## Worst setup path (report_checks -path_delay max)", "", "```", worst_max, "```"]
    with open(os.path.join(a.out, "results.md"), "w") as fh:
        fh.write("\n".join(lines) + "\n")

    required = {r.strip().lower() for r in a.require.split(",") if r.strip()}
    failed = []
    for c in checks:
        if c["result"] == "FAIL":
            failed.append(c["name"])
        elif c["result"] == "NOT_RUN" and any(r in c["name"].lower() for r in required):
            failed.append(c["name"] + " (required, not run)")
    for c in checks:
        print(f"  {c['result']:8s} {c['name']}: {c['detail']}")
    print(f"collect_pd: {'FAIL: ' + ', '.join(failed) if failed else 'all checks passed'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
