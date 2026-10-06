#!/usr/bin/env python3
"""Summarize SymbiYosys runs of formal/orbit_demo.sby into a Markdown report.

Everything in the report is read from the run directories (status file,
logfile.txt, config.sby and the JUnit XML that sby writes), never assumed:

  summarize.py --run <run-dir> --tasks "thermal dup ..." -o summary.md
               [--optional-tasks "..."] [--vacuity <vacuity.tsv>] [--rtl-dir <dir>]

Exit status is 0 even when tasks failed; the make targets decide pass/fail.
"""

import argparse
import datetime
import os
import re
import subprocess
import xml.etree.ElementTree as ET

PROPERTIES = [
    ("P1", "on every out_fire, out_data equals the reference result for every lane (exact, INT32 wraparound)"),
    ("P2", "every accepted in_last produces exactly one out_fire, in order (no loss, no duplication)"),
    ("P3", "out_valid && !out_ready: out_valid stays high and out_data is unchanged next cycle"),
    ("P4", "in_ready low when thermal STOP/3, fault, clear_fault, or buffer full && !out_ready"),
    ("P5", "voted thermal state follows the SPEC table (independent FSM); reset gives STOP"),
    ("P6", "throttle: first THROTTLE cycle admits, consecutive THROTTLE cycles alternate"),
    ("P7", "fault-free: fault and therm_repair never rise, duplicated / triplicated copies equal"),
    ("P8", "clear_fault: then fault = 0, out_valid = 0, storage zero, next beat sums from 0 (also from a latched fault)"),
]


METHOD = """## Method

* **Harness and model.** `formal/orbit_demo_fv.sv` instantiates `orbit_demo` as `dut` and keeps
  an independent reference model written from docs/SPEC.md: thermal FSM (SPEC table, SPEC
  thresholds), throttle phase, predicted `in_ready` / `out_valid`, per-lane running sums,
  expected output-buffer contents, and sequence counters of accepted `in_last` beats and
  delivered results. The model follows the DUT's port handshakes like a scoreboard.
* **Environment.** Every DUT input is a free input in every cycle. The only assumption is
  reset in the first cycle (except `clear` and `wrap`, see below); `rst_n` and `clear_fault` stay free later, so the proofs also
  cover reset and clear_fault at arbitrary times.
* **DUT internals** (P7, P8 storage checks and induction helpers) are read through Yosys
  `hierconn` wires (`(* hierconn *) wire \\dut.<path>`), connected by `flatten` after
  `hierarchy; proc` with `keep_hierarchy` removed. `check -assert` in the script fails the
  run if a path does not exist. Open-source Yosys has no `bind`.
* **Reset / clear_fault from any state.** In the fault-free reachable states `fault` is
  always 0, so "fault = 0 after clear_fault" cannot fail there. The `clear` task starts
  from a completely unconstrained state (latched fault, stale `out_valid_q`, disagreeing
  copies) and proves that reset or clear_fault gives fault = 0, out_valid = 0 and all 16
  storage copies zero, that the next beat without in_first sums from 0 in both copies,
  that reset gives STOP in all three thermal copies, and that every thermal copy is
  rewritten with the SPEC next state of the bitwise majority (so clear_fault does not
  touch the thermal state). Added after an independent review found that a
  "clear_fault does not clear fault_q" bug passed every other task.
* **Liveness.** `P2_live_delivered` (`assert property (s_eventually !f_watch)`) under the
  fairness assumption `assume property (s_eventually out_ready)`, proven with suprove
  (liveness-to-safety).
* **Unbounded proofs.** smtbmc k-induction (yices) closes with helper invariants that tie
  every DUT register to the model (labels `*_h_*`); the helpers are asserted and proven,
  never assumed. Measured on 2026-09-29, the induction closes at k = 2 for thermal,
  handshake and datapath and at k = 1 for dup; the configured depths (8, 8, 6, 6) are
  larger so that the base case also finds the short counterexamples of the vacuity check.
  `thermal_pdr` and `handshake_pdr` re-prove the same properties with abc
  pdr **without** the helpers, as an independent check; `datapath_pdr` does the same for
  P1 / P8 but takes about 15 minutes, so it runs only in `make formal-extra` and appears
  above only if it was run. `dup_pdr` re-proves P7.
* **Product.** The model uses the SPEC formula `sext32(signed8(a) * signed8(b))`. The
  `product` task proves it equal to an independent sign * (|a| * |b|) formulation for all
  2^16 operand pairs (bitwuzla). Using the sign-magnitude form inside the sequential proofs
  makes the solver re-prove multiplier equivalence in every unrolled step (a first attempt
  ran for over 10 minutes at step 4 without finishing).
* **INT32 wraparound.** The unbounded P1 proof covers every reachable accumulator value,
  including wrapped ones. A wraparound *trace* from reset needs at least 2^31 / 2^14 =
  131072 beats, far beyond BMC, so the `wrap` covers start from an arbitrary state that
  satisfies the proven invariants (DUT storage = model, copies equal, no fault) and check
  every assertion group along the traces. Every 32-bit sum is reachable from reset (e.g.
  by repeated +1 / -1 products), so these start states are reachable, just not in a few steps.

## Note on the SPEC

SPEC section 6 says the throttle `phase` flip-flop is "forced to 0 whenever the voted state
is not THROTTLE". The RTL does this at the next clock edge, so `phase` can still be 1 in the
first non-THROTTLE cycle after THROTTLE. Admission is unaffected (admit uses phase only in
THROTTLE) and `P6_first_throttle_admits` proves the first THROTTLE cycle always admits. The
reference model uses the registered reading; a first helper invariant that assumed
phase = 0 in every non-THROTTLE cycle was refuted by the base case at step 4.

## Limitations

* Fault-free design only; fault injection is a separate area. P7 shows the fault latch and
  repair flag never rise without an upset; it says nothing about detection of upsets.
* P2 combines safety (at most one outstanding result, every out_fire delivers exactly that
  result, P3 holds it until taken) with a liveness check (`live` task): a result chosen by
  the solver among the accepted ones is eventually delivered, assuming only that the
  consumer raises out_ready infinitely often. A result accepted before `clear_fault` or
  reset is discarded, as the SPEC states. suprove gives no per-property status or trace in
  live mode; the task holds exactly one liveness assertion.
* Covers from reset are searched to depth 24 only (all were reached by step 6).
* The model's product is the SPEC formula, which is also how the RTL writes it; its
  arithmetic meaning is established separately by the `product` lemma.
* Parameters are fixed at LANES = 4, T_THROTTLE = 80, T_STOP = 95, T_RECOVER = 70.
* The harness depends on Yosys `hierconn` handling of hierarchical names; it is not
  portable to other tools as is.
"""


def read(path):
    try:
        with open(path) as f:
            return f.read()
    except OSError:
        return ""


def tool_version(cmd):
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        text = (out.stdout or out.stderr).strip().splitlines()
        return text[0] if text else "?"
    except (OSError, subprocess.SubprocessError):
        return "?"


class Task:
    """Results of one SymbiYosys task directory."""

    def __init__(self, run_dir, name):
        self.name = name
        self.dir = os.path.join(run_dir, "orbit_demo_" + name)
        self.present = os.path.isdir(self.dir)
        status = read(os.path.join(self.dir, "status")).split()
        self.status = status[0] if status else ("MISSING" if not self.present else "ERROR")
        cfg = read(os.path.join(self.dir, "config.sby"))
        self.mode = self._opt(cfg, "mode") or "?"
        self.depth = self._opt(cfg, "depth")
        self.cover_assert = self._opt(cfg, "cover_assert") == "on"
        eng = re.search(r"^\[engines\]\s*\n(.+)$", cfg, re.M)
        self.engine = eng.group(1).strip() if eng else "?"
        defines = re.findall(r"-D(FV_[A-Z_]+)", cfg)
        self.groups = [d for d in defines if d != "FV_NO_HELPERS"]
        self.no_helpers = "FV_NO_HELPERS" in defines
        self.free_start = "FV_FREE_START" in defines
        self.any_start = "FV_ANY_START" in defines
        log = read(os.path.join(self.dir, "logfile.txt"))
        m = re.search(r"Elapsed clock time \[H:MM:SS \(secs\)\]: \S+ \((\d+)\)", log)
        self.seconds = int(m.group(1)) if m else None
        self.basecase_pass = bool(re.search(r"returned pass for basecase", log))
        self.failed, self.reached = self._parse_log(log)
        self.props = self._properties()

    @staticmethod
    def _parse_log(log):
        """Failed assertions and reached covers, with their step.

        The engine lines are complete (sby's own summary stops after five
        traces). Induction-step failures are not counterexamples from reset
        and are skipped; they carry no step in the summary either.
        """
        failed, reached, step, in_induction = {}, {}, {}, False
        for line in log.splitlines():
            m = re.search(r"\] (engine_\d+(?:\.\w+)?): .*Checking assertions in step (\d+)", line)
            if m:
                step[m.group(1)] = int(m.group(2))
                continue
            m = re.search(r"\] (engine_\d+(?:\.\w+)?): .*Assert failed in orbit_demo_fv: (\w+)", line)
            if m and not m.group(1).endswith(".induction"):
                failed.setdefault(m.group(2), step.get(m.group(1)))
                continue
            m = re.search(r"Reached cover statement in step (\d+) at orbit_demo_fv: (\w+)", line)
            if m:
                reached.setdefault(m.group(2), int(m.group(1)))
                continue
            if "counterexample trace" in line:
                in_induction = "[induction]" in line
                continue
            m = re.search(r"failed assertion orbit_demo_fv\.(\w+) at \S+(?: step (\d+))?$", line)
            if m and not in_induction:
                st = int(m.group(2)) if m.group(2) else failed.get(m.group(1))
                failed[m.group(1)] = st
        return failed, reached

    def _properties(self):
        """{name: (ASSERT|COVER, PASS|FAIL|UNKNOWN)} for every labelled property.

        Names come from the prepared model (the pdr and live engines give no
        per-property results); per-property results come from the JUnit XML
        where sby writes them, otherwise from the task status and the log.
        """
        il = read(os.path.join(self.dir, "model", "design_prep.il"))
        xml = self._junit()
        props = {}
        for kind, name in re.findall(r"^\s*cell \$(assert|cover|live) \\(\S+)$", il, re.M):
            ptype = "COVER" if kind == "cover" else "ASSERT"
            st = xml.get(name, (None, None))[1]
            if st is None:
                if ptype == "COVER":
                    st = "PASS" if name in self.reached else "UNKNOWN"
                elif name in self.failed:
                    st = "FAIL"
                elif self.status == "PASS":
                    st = "PASS"
                else:
                    st = "UNKNOWN"
            props[name] = (ptype, st)
        return props

    @staticmethod
    def _opt(cfg, key):
        m = re.search(r"^\[options\](.*?)^\[", cfg, re.M | re.S)
        if not m:
            return None
        k = re.search(r"^%s\s+(\S+)" % key, m.group(1), re.M)
        return k.group(1) if k else None

    def _junit(self):
        """{property id: (type, PASS|FAIL|UNKNOWN|ERROR)} from the JUnit XML."""
        props = {}
        path = os.path.join(self.dir, "orbit_demo_%s.xml" % self.name)
        if not os.path.exists(path):
            return props
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError:
            return props
        for tc in root.iter("testcase"):
            pid, ptype = tc.get("id"), tc.get("type")
            if not pid or not ptype:
                continue
            if tc.find("failure") is not None:
                st = "FAIL"
            elif tc.find("error") is not None:
                st = "ERROR"
            elif tc.find("skipped") is not None:
                st = "UNKNOWN"
            else:
                st = "PASS"
            props[pid] = (ptype, st)
        return props

    @property
    def solver(self):
        parts = self.engine.split()
        if parts[:1] == ["smtbmc"]:
            return "smtbmc/" + (parts[1] if len(parts) > 1 else "yices")
        return "/".join(parts)

    @property
    def unbounded(self):
        """Modes whose PASS is an unbounded proof."""
        return self.mode in ("prove", "live")

    def method(self):
        if self.mode == "live":
            return "liveness (unbounded), fair consumer"
        if self.mode == "prove" and self.engine.startswith("smtbmc"):
            what = "k-induction, k = %s" % self.depth
            if self.any_start:
                what += ", unconstrained start state (no reset)"
            return what
        if self.mode == "prove":
            return "PDR (unbounded)"
        if self.mode == "cover":
            what = "cover, depth %s" % self.depth
            if self.free_start:
                what += ", consistent arbitrary start state"
            if self.cover_assert:
                what += ", assertions checked on the traces"
            return what
        return "%s, depth %s" % (self.mode, self.depth)

    def assert_result(self, pid):
        """Human-readable result of one assertion in this task."""
        ptype, st = self.props.get(pid, ("ASSERT", None))
        if self.mode == "live" and st == "PASS":
            return "PROVEN unbounded (liveness, %s)" % self.solver
        if self.mode == "prove" and st == "PASS":
            return "PROVEN unbounded (%s)" % ("k-induction k=%s" % self.depth
                                               if self.engine.startswith("smtbmc") else "pdr")
        if self.mode == "cover" and st == "PASS":
            return "no violation on cover traces (depth %s)" % self.depth
        if pid in self.failed:
            return "FAIL (counterexample%s)" % (
                "" if self.failed[pid] is None else ", step %d" % self.failed[pid])
        if self.mode == "prove" and self.basecase_pass:
            return "BMC depth %s only (induction did not close)" % self.depth
        return st or self.status


def md_escape(s):
    return s.replace("|", "\\|")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--tasks", required=True)
    ap.add_argument("--optional-tasks", default="",
                    help="tasks reported only if their run directory exists")
    ap.add_argument("--vacuity")
    ap.add_argument("--rtl-dir", default="rtl")
    ap.add_argument("--title", default="Formal verification summary: orbit_demo (fault-free)")
    ap.add_argument("-o", "--output", required=True)
    args = ap.parse_args()

    tasks = [Task(args.run, t) for t in args.tasks.split()]
    tasks += [t for t in (Task(args.run, n) for n in args.optional_tasks.split()) if t.present]
    out = []
    w = out.append

    w("# " + args.title)
    w("")
    w("Generated %s UTC by `formal/summarize.py` from the SymbiYosys run directories."
      % datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M"))
    w("RTL: `%s`. Tools: %s; %s; %s; %s." % (
        args.rtl_dir,
        tool_version(["yosys", "-V"]),
        tool_version(["sby", "--version"]),
        tool_version(["yices-smt2", "--version"]),
        "bitwuzla " + tool_version(["bitwuzla", "--version"])))
    w("")
    w("Harness: `formal/orbit_demo_fv.sv` (independent reference model from docs/SPEC.md, all DUT")
    w("inputs free, reset only in the first cycle; reset and clear_fault stay free afterwards;")
    w("the `clear` task starts from an unconstrained state and `wrap` from a consistent one).")
    w("Jobs: `formal/orbit_demo.sby`, one task per property group.")
    w("")

    # --- per-property table ---------------------------------------------
    w("## Per-property status")
    w("")
    w("| Property | Meaning | Status | Evidence (task: assertions, method, solver, time) |")
    w("|---|---|---|---|")
    for pnum, meaning in PROPERTIES:
        evidence, results = [], []
        for t in tasks:
            if not t.unbounded:
                continue
            ids = sorted(p for p, (ty, _) in t.props.items() if ty == "ASSERT" and p.startswith(pnum + "_"))
            if not ids:
                continue
            main_ids = [p for p in ids if "_h_" not in p]
            n_help = len(ids) - len(main_ids)
            if t.status == "PASS":
                results.append("proven")
            elif any(p in t.failed for p in ids):
                results.append("fail")
            elif t.basecase_pass:
                results.append("bmc")
            else:
                results.append("none")
            desc = "%d assertion%s" % (len(main_ids), "" if len(main_ids) == 1 else "s")
            if n_help:
                desc += " + %d helper%s" % (n_help, "" if n_help == 1 else "s")
            elif t.no_helpers:
                desc += ", no helper invariants"
            evidence.append("`%s`: %s, %s, %s, %s, %ss" % (
                t.name, t.status, desc, t.method(), t.solver,
                "?" if t.seconds is None else t.seconds))
        if "fail" in results:
            status = "**FAIL**"
        elif results and all(r == "proven" for r in results):
            status = "PROVEN unbounded"
        elif "proven" in results:
            status = "PROVEN unbounded (some jobs inconclusive)"
        elif "bmc" in results:
            status = "BMC only"
        else:
            status = "not run / no result"
        w("| %s | %s | %s | %s |" % (pnum, md_escape(meaning), status, "<br>".join(evidence) or "-"))
    w("")

    # --- jobs --------------------------------------------------------------
    w("## Jobs")
    w("")
    w("| Task | Groups | Mode / method | Engine / solver | Status | Wall time (s) | Assertions | Covers |")
    w("|---|---|---|---|---|---|---|---|")
    for t in tasks:
        n_ass = sum(1 for ty, _ in t.props.values() if ty == "ASSERT")
        n_cov = sum(1 for ty, _ in t.props.values() if ty == "COVER")
        groups = " ".join(g[3:].lower() for g in t.groups if g != "FV_ANY_START") + (" (no helpers)" if t.no_helpers else "")
        w("| %s | %s | %s | %s | %s | %s | %d | %d |" % (
            t.name, groups or "-", t.method(), t.solver, t.status,
            "?" if t.seconds is None else t.seconds, n_ass, n_cov))
    w("")

    # --- covers --------------------------------------------------------------
    cov_tasks = [t for t in tasks if t.mode == "cover"]
    if cov_tasks:
        w("## Covers")
        w("")
        w("| Cover | Task | Result |")
        w("|---|---|---|")
        for t in cov_tasks:
            for pid in sorted(p for p, (ty, _) in t.props.items() if ty == "COVER"):
                if pid in t.reached:
                    res = "COVER reached at step %d" % t.reached[pid]
                else:
                    res = "**not reached** within depth %s" % t.depth
                w("| %s | %s | %s |" % (pid, t.name, res))
        w("")
        w("Steps are sby step numbers; step 0 is the reset cycle. The covers are sampled at the")
        w("clock edge, so a condition that holds in cycle N is reported at step N + 1. The `wrap`")
        w("covers start from an arbitrary state in which DUT and model agree (see Method).")
        w("")

    # --- per-assertion detail --------------------------------------------
    w("## Assertions by task")
    w("")
    for t in tasks:
        ids = sorted(p for p, (ty, _) in t.props.items() if ty == "ASSERT")
        if not ids:
            continue
        w("<details><summary><code>%s</code>: %s, %d assertions</summary>" % (t.name, t.status, len(ids)))
        w("")
        w("| Assertion | Result |")
        w("|---|---|")
        for pid in ids:
            w("| %s | %s |" % (pid, t.assert_result(pid)))
        w("")
        w("</details>")
        w("")

    # --- vacuity -------------------------------------------------------------
    if args.vacuity and os.path.exists(args.vacuity):
        w("## Vacuity: the proofs fail on broken RTL")
        w("")
        w("`make formal-vacuity` edits a generated copy of the RTL (never `rtl/`) and reruns the")
        w("task that should catch the bug. CAUGHT = sby status FAIL with a counterexample from the")
        w("initial state (reset asserted in step 0) on a property with the expected prefix (see")
        w("`vacuity.md`). Step 0 failures are P4 assertions, which hold in every state including")
        w("the unconstrained first cycle. Names with `_h_` are helper invariants, which are proof")
        w("obligations too; the `*_pdr` rows have no helpers, so they show the port-level")
        w("properties themselves failing.")
        w("")
        w("| Mutant | Bug | Task | Result | Failed properties | Step | Time (s) |")
        w("|---|---|---|---|---|---|---|")
        with open(args.vacuity) as f:
            next(f, None)
            for line in f:
                c = line.rstrip("\n").split("\t")
                if len(c) < 10:
                    continue
                w("| %s | %s | %s | %s (%s) | %s | %s | %s |" % (
                    c[0], md_escape(c[9]), c[2], c[4], c[5], c[6], c[7], c[8]))
        w("")

    w(METHOD)

    with open(args.output, "w") as f:
        f.write("\n".join(out) + "\n")
    print("wrote " + args.output)


if __name__ == "__main__":
    main()
