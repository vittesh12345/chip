#!/usr/bin/env python3
"""Mutation testing of the ORBIT-AI demonstrator verification suite.

Tests the tests: every mutant is a copy of the production RTL directory with one
realistic, single-point design error (one text substitution, or a few that
together make one bug). For each mutant the fast self-checking make targets of
the other areas are run against the copy with

    make RTL_DIR=<out>/m<NN>/rtl BUILD=<out>/m<NN>/build -k <target>

and the target "kills" the mutant if it exits non-zero. The production rtl/ is
never touched.

Rules that keep the result honest:
  * Every substitution must match exactly the listed number of times. If the
    RTL moved on and a pattern no longer matches, the mutant is STALE and the
    run fails, instead of silently testing an unmodified copy.
  * Every mutant must still compile with Icarus Verilog; a mutant that does
    not is INVALID (a compile error would be a trivial kill) and is excluded
    from the score.
  * The unmodified copy (m00) is run first through the same targets; if any
    target fails on it, the suite is not green and the mutation score would be
    meaningless, so the run stops.
  * A target that exceeds --timeout is recorded as TIMEOUT, not as a kill.

Surviving mutants are optionally run through --extra-targets (slower checks,
e.g. the full `formal` set) to see whether the gap is closed elsewhere.

Outputs: <out>/results.json (resumable with --resume), per-target logs under
<out>/m<NN>/logs/, and the report (--report, default <out>/summary.md) with the
kill matrix, the mutation score and an analysis of every survivor. The
survivor analyses are written by hand in ANALYSIS below after inspecting the
results; a survivor without one is flagged in the report and fails the run.
"""

import argparse
import concurrent.futures
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

RTL_FILES = ("orbit_keep_reg.v", "orbit_mac_lane.v", "orbit_thermal_tmr.v", "orbit_demo.v")
KEEP, LANE, TMR, TOP = RTL_FILES

# (name, description, [(file, old, new, expected count), ...])
MUTANTS = [
    # ---- MAC lane arithmetic ------------------------------------------------
    ("prod_zext", "product zero-extended instead of sign-extended to 32 bits",
     [(LANE, "{{16{prod[15]}}, prod}", "{16'd0, prod}", 1)]),
    ("prod_unsigned", "operands multiplied as unsigned",
     [(LANE, "$signed(a) * $signed(b)", "a * b", 1)]),
    ("first_ignored", "accumulate ignores in_first (both copies)",
     [(LANE, "(first ? 32'd0 : acc_a) + prod32", "acc_a + prod32", 1),
      (LANE, "(first ? 32'd0 : acc_b) + prod32", "acc_b + prod32", 1)]),
    ("acc_b_from_a", "copy B accumulates from copy A's stored value (loses independence)",
     [(LANE, "(first ? 32'd0 : acc_b) + prod32", "(first ? 32'd0 : acc_a) + prod32", 1)]),
    ("res_en_every_beat", "result registers load on every beat, not only on in_last",
     [(LANE, "wire res_en = clr | (mac_en & last);", "wire res_en = clr | mac_en;", 1)]),
    ("res_a_from_acc_b", "result A loaded from accumulator copy B",
     [(LANE, ".d(clr ? 32'd0 : acc_a_sum), .q(res_a)", ".d(clr ? 32'd0 : acc_b_sum), .q(res_a)", 1)]),
    ("result_from_b", "out_data driven from result copy B instead of A",
     [(LANE, "assign result   = res_a;", "assign result   = res_b;", 1)]),
    # ---- duplicate compare --------------------------------------------------
    ("mismatch_no_res", "mismatch compares the accumulators but not the results",
     [(LANE, "assign mismatch = (acc_a != acc_b) | (res_a != res_b);",
       "assign mismatch = (acc_a != acc_b);", 1)]),
    ("mismatch_no_acc", "mismatch compares the results but not the accumulators",
     [(LANE, "assign mismatch = (acc_a != acc_b) | (res_a != res_b);",
       "assign mismatch = (res_a != res_b);", 1)]),
    ("mismatch_low16", "accumulator compare covers bits [15:0] only",
     [(LANE, "assign mismatch = (acc_a != acc_b) |",
       "assign mismatch = (acc_a[15:0] != acc_b[15:0]) |", 1)]),
    # ---- clear_fault / reset of lane storage --------------------------------
    ("acc_en_no_clr", "clear_fault does not enable the accumulators (they keep their sum)",
     [(LANE, "wire acc_en = clr | mac_en;", "wire acc_en = mac_en;", 1)]),
    ("clr_skips_acc_b", "clear_fault does not zero accumulator copy B",
     [(LANE, ".d(clr ? 32'd0 : acc_b_sum), .q(acc_b)", ".d(acc_b_sum), .q(acc_b)", 1)]),
    ("clr_skips_res_b", "clear_fault does not zero result copy B",
     [(LANE, ".d(clr ? 32'd0 : acc_b_sum), .q(res_b)", ".d(acc_b_sum), .q(res_b)", 1)]),
    ("keep_reset_ones", "orbit_keep_reg default reset value all ones (lane storage resets to -1)",
     [(KEEP, "RESET_VAL = {W{1'b0}}", "RESET_VAL = {W{1'b1}}", 1)]),
    # ---- top level: handshake, output buffer, fault latch -------------------
    ("in_ready_ignores_out_ready", "in_ready ignores out_ready (bubble when replacing the result)",
     [(TOP, "(~out_valid_q | out_ready);", "~out_valid_q;", 1)]),
    ("in_ready_no_buffer_check", "in_ready ignores a full output buffer (result overwritten)",
     [(TOP, "(~out_valid_q | out_ready);", "1'b1;", 1)]),
    ("in_ready_no_mismatch", "in_ready not masked by the combinational mismatch",
     [(TOP, "assign in_ready = admit & ~fault_q & ~mismatch & ~clear_fault &",
       "assign in_ready = admit & ~fault_q & ~clear_fault &", 1)]),
    ("in_ready_no_clear", "in_ready not masked by clear_fault (beat accepted and lost)",
     [(TOP, "assign in_ready = admit & ~fault_q & ~mismatch & ~clear_fault &",
       "assign in_ready = admit & ~fault_q & ~mismatch &", 1)]),
    ("out_valid_no_mismatch", "out_valid not masked by the combinational mismatch",
     [(TOP, "assign out_valid = out_valid_q & ~fault_q & ~mismatch;",
       "assign out_valid = out_valid_q & ~fault_q;", 1)]),
    ("out_valid_no_fault", "out_valid not masked by the latched fault",
     [(TOP, "assign out_valid = out_valid_q & ~fault_q & ~mismatch;",
       "assign out_valid = out_valid_q & ~mismatch;", 1)]),
    ("out_fire_unmasked", "out_fire uses the raw buffer flag (drains while masked)",
     [(TOP, "wire out_fire = out_valid & out_ready;", "wire out_fire = out_valid_q & out_ready;", 1)]),
    ("fault_not_sticky", "fault_q follows mismatch instead of being sticky",
     [(TOP, "            if (mismatch)\n                fault_q <= 1'b1;\n",
       "            fault_q <= mismatch;\n", 1)]),
    ("clear_keeps_out_valid", "clear_fault does not empty the output buffer",
     [(TOP, "        end else if (clear_fault) begin\n            fault_q     <= 1'b0;\n"
            "            out_valid_q <= 1'b0;\n",
       "        end else if (clear_fault) begin\n            fault_q     <= 1'b0;\n", 1)]),
    ("out_fire_priority", "out_fire wins over a same-cycle in_last (replacement result lost)",
     [(TOP, "            if (in_fire && in_last)\n                out_valid_q <= 1'b1;\n"
            "            else if (out_fire)\n                out_valid_q <= 1'b0;\n",
       "            if (out_fire)\n                out_valid_q <= 1'b0;\n"
       "            else if (in_fire && in_last)\n                out_valid_q <= 1'b1;\n", 1)]),
    ("lane_a_offbyone", "lane operand A sliced one bit too high (in_a[8*i+1 +: 8])",
     [(TOP, ".a        (in_a[8*i +: 8]),", ".a        (in_a[8*i+1 +: 8]),", 1)]),
    ("lane_b_reversed", "lane operand B taken from the mirrored lane",
     [(TOP, ".b        (in_b[8*i +: 8]),", ".b        (in_b[8*(LANES-1-i) +: 8]),", 1)]),
    ("shutdown_only_stop", "shutdown_req only for code 2, not for the unused code 3",
     [(TOP, "assign shutdown_req = therm_state[1];", "assign shutdown_req = (therm_state == 2'd2);", 1)]),
    # ---- thermal TMR ------------------------------------------------------------
    ("throttle_gt", "throttle at > 80 instead of >= 80",
     [(TMR, "(t >= T_THROTTLE)", "(t > T_THROTTLE)", 1)]),
    ("stop_gt", "stop at > 95 instead of >= 95",
     [(TMR, "t >= T_STOP", "t > T_STOP", 1)]),
    ("recover_lt_throttle", "THROTTLE recovers at < 70 instead of <= 70",
     [(TMR, "S_THROTTLE: nxt = (t <= T_RECOVER)", "S_THROTTLE: nxt = (t < T_RECOVER)", 1)]),
    ("recover_lt_stop", "STOP recovers at < 70 instead of <= 70",
     [(TMR, "default:    nxt = (t <= T_RECOVER)", "default:    nxt = (t < T_RECOVER)", 1)]),
    ("temp_unsigned", "temperature compared unsigned (negative readings look hot)",
     [(TMR, "wire signed [7:0] t = temp_c;", "wire [7:0] t = temp_c;", 1)]),
    ("invalid_ignored", "invalid sensor reading does not force STOP",
     [(TMR, "if (!temp_valid || t >= T_STOP)", "if (t >= T_STOP)", 1)]),
    ("reset_copy0_normal", "thermal copy 0 resets to NORMAL (outvoted by copies 1 and 2)",
     [(TMR, ".RESET_VAL(S_STOP)) u_copy0", ".RESET_VAL(S_NORMAL)) u_copy0", 1)]),
    ("reset_all_normal", "all thermal copies reset to NORMAL instead of STOP",
     [(TMR, ".RESET_VAL(S_STOP))", ".RESET_VAL(S_NORMAL))", 3)]),
    ("voter_two_copies", "voter uses only copies 0 and 1 (AND of two copies)",
     [(TMR, "wire [1:0] voted = (c0 & c1) | (c1 & c2) | (c0 & c2);", "wire [1:0] voted = c0 & c1;", 1)]),
    ("repair_no_c2", "therm_repair compares copies 0 and 1 only",
     [(TMR, "assign repair = (c0 != c1) | (c1 != c2);", "assign repair = (c0 != c1);", 1)]),
    ("copy2_no_feedback", "thermal copy 2 is not rewritten from the voted next state",
     [(TMR, ".en(1'b1), .d(nxt), .q(c2)", ".en(1'b1), .d(c2), .q(c2)", 1)]),
    ("phase_not_reset", "throttle phase not forced to 0 outside THROTTLE",
     [(TMR, "phase <= (voted == S_THROTTLE) ? ~phase : 1'b0;",
       "phase <= (voted == S_THROTTLE) ? ~phase : phase;", 1)]),
    ("throttle_first_blocks", "first THROTTLE cycle blocks (admit = phase)",
     [(TMR, "((voted == S_THROTTLE) & ~phase)", "((voted == S_THROTTLE) & phase)", 1)]),
]

# Hand-written analysis of mutants that survive the fast suite, filled in
# after inspecting results.json. Keys are mutant names; value: (equivalent?, text).
ANALYSIS = {
    "result_from_b": (False,
        "Not observable in any *transferred* result: `out_data` differs from production only while "
        "`res_a != res_b`, and then `mismatch` forces `out_valid = 0` in the same cycle; reset and "
        "`clear_fault` zero both copies. It is observable at the `out_data` port, though: after a single "
        "upset of `u_res_b` while a result is held, production keeps showing the correct copy-A value "
        "(SPEC 5: \"`out_data` comes from copy A\"), the mutant shows the corrupted copy. No check looks "
        "at `out_data` while `out_valid` is low (the sim benches and the fault harness compare data only on "
        "transfer), so SPEC 5's sentence is untested. Low severity. Missing check: in the fault harness / "
        "SEU campaign, for `u_res_b` (and `u_acc_*`) upsets, `out_data` of the faulty design must equal "
        "the fault-free reference in every cycle, not only on `out_fire` (evidence bench T2). If the "
        "project regards `out_data` as don't-care while `out_valid` is low, this mutant becomes equivalent "
        "and SPEC 5 should say so instead."),
    "out_valid_no_fault": (False,
        "Differs only when `fault_q = 1`, `mismatch = 0` and `out_valid_q = 1`. Fault-free, `fault_q` never "
        "rises; after a single lane-storage upset the copies stay different until `clear_fault` (no beat "
        "can be accepted while `mismatch`/`fault_q` is high), so `~mismatch` alone already masks, which is "
        "why the lane scenarios of fault-quick cannot see it. It is reachable with one upset of the "
        "unprotected `fault_q` (SPEC 8; bit 520 of the SEU campaign) while a result is held: production "
        "stops (`out_valid = 0`, the SPEC 4 formula), the mutant keeps offering the result with `fault = 1`. "
        "`fault/campaign_report.py` reports the `fault_q` trials but does not check them, and the fault "
        "formal scenarios have no `fault_q` scenario. Missing check: the port invariant "
        "`fault -> !out_valid && !in_ready` in every cycle of every SEU-campaign trial (including bit 520), "
        "or as an always-on property in `fault/fi_harness.sv` together with a `fault_q` upset scenario "
        "(evidence bench T1)."),
    "fault_not_sticky": (False,
        "`fault_q <= mismatch` instead of sticky. After a single lane upset the copies never re-agree "
        "without `clear_fault`/reset (all writes are blocked), so `fault_q` stays high in the mutant too, and "
        "fault-free it is never set: that is why every single-upset lane check passes. It is observable with "
        "one `fault_q` 0->1 upset (SPEC 8): production holds the false fault stop until `clear_fault`, the "
        "mutant drops `fault` at the next edge and presents the held result again; also with two lane "
        "upsets that restore agreement. Missing check: stickiness at the port, `$past(fault) && "
        "$past(rst_n) && !$past(clear_fault) -> fault`, in the fault harness (it holds under any single "
        "upset, so it can be always on) and in the SEU campaign for bit 520 (after a `fault_q` 0->1 upset "
        "`fault` must stay high and `out_valid`/`in_ready` low until the next `clear_fault`; evidence bench T1)."),
    "out_fire_unmasked": (True,
        "Equivalent under the SPEC's fault model (fault-free, or one upset). `out_fire` differs only in "
        "cycles with `out_valid_q & out_ready & (fault_q | mismatch)`, where the mutant clears `out_valid_q`. "
        "In those cycles both designs drive `out_valid = 0` and `in_ready = 0`. From such a cycle on, "
        "`fault_q` is (or becomes, one cycle later) 1 and stays 1 until `clear_fault` or reset, because a "
        "lane mismatch cannot heal without a write and no write is admitted, and a spurious `fault_q` "
        "0->1 upset is itself sticky; `clear_fault` and reset then write `out_valid_q = 0` in both designs. "
        "So the only state difference is overwritten before it can reach a port. It becomes visible only "
        "with a second, independent upset (`fault_q` 0->1 with `out_ready` high, then `fault_q` 1->0: "
        "production re-presents the held result, the mutant has silently drained it; evidence bench T4, "
        "run with +t4). SPEC 8 names the `fault_q` 1->0 upset as a known escape, so no check is proposed."),
    "shutdown_only_stop": (False,
        "Differs only in voted state 3. Every copy resets to STOP and is written from `nxt`, which is never 3; "
        "one upset copy is outvoted, and two copies agreeing on a value in {0,1,2} vote to it, so code 3 needs "
        "two copies upset before the next repair edge (formal proves `P5_never_code3` fault-free). The mutant "
        "is therefore equivalent under the single-upset model, but SPEC 2/6 specify code 3 explicitly as a "
        "defensive requirement (\"3 unused, behaves as STOP\", `shutdown_req = therm_state[1]`), and "
        "`P5_shutdown_req` / `P4_blocked_stop_or_3` are vacuous for code 3 because the harness cannot reach it. "
        "Test gap for a defensive requirement. Missing check: force two thermal copies to 2'b11 in simulation "
        "(or a formal task with the three copies' state unconstrained after reset, or a double-upset "
        "thermal scenario) and assert `therm_state == 3 -> shutdown_req && !in_ready` (evidence bench T3)."),
}

# Hand-written observations on the kill matrix (not about single survivors).
NOTES = [
    "* The baseline (unmodified copy) passes every target, so every kill is caused by the mutation.",
    "* The targets are complementary. `sim` alone lets through every mutant whose effect needs an upset "
    "(`mismatch_*`, `in_ready_no_mismatch`, `out_valid_no_mismatch`, `voter_two_copies`, `repair_no_c2`); "
    "`fault-quick` is the only killer of `in_ready_no_mismatch`, `out_valid_no_mismatch` and `repair_no_c2`.",
    "* `acc_b_from_a` and `res_a_from_acc_b` remove the independence of the two copies without changing any "
    "single-upset behaviour (a lone upset is still caught by the compare); only the synthesis storage audit "
    "(shared D-input logic between copies) kills them. That is the right check for a common-mode defect.",
    "* Most `synth` kills are not independent: `synth-gls` first runs the directed bench "
    "`tb/tb_orbit_demo.v` on the RTL as its reference, and that reference run is what fails "
    "(`synth-gls: RTL reference run FAILED`) for every functional mutant also killed by `sim`. "
    "The kills that belong to synthesis itself are the storage audit (`acc_b_from_a`, `res_a_from_acc_b`, "
    "`mismatch_no_res`, `lane_a_offbyone`, `copy2_no_feedback`) and the netlist equivalence check "
    "(`prod_zext`, `lane_a_offbyone`).",
    "* The `lint` kills (Verilator -Wall: an input or register left unused, an out-of-range part select) are "
    "incidental side effects of those mutations; every lint-killed mutant is also killed by a functional target.",
    "* All five fast-suite survivors also pass the full `formal` set (liveness and pdr tasks included), "
    "which checks the fault-free design only.",
    "* Four of the five survivors concern `fault_q`, `out_valid` masking or code 3, i.e. behaviour that is "
    "only reachable through an upset of an unprotected flip-flop or a double upset. The single-upset lane "
    "and thermal scenarios are tested thoroughly; the gap is at the port-level invariants around the "
    "fault latch (`fault` sticky, `fault -> !out_valid && !in_ready`) under a `fault_q` upset.",
    "* No RTL or SPEC defect was found by this campaign.",
]


def log(msg):
    print(f"[mutation {datetime.datetime.now():%H:%M:%S}] {msg}", flush=True)


def make_copy(src, dst, edits):
    """Copy the four RTL files to dst and apply the edits. Returns a diff-like note or raises."""
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True)
    for f in RTL_FILES:
        shutil.copy2(src / f, dst / f)
    for f, old, new, count in edits:
        text = (dst / f).read_text()
        n = text.count(old)
        if n != count:
            raise ValueError(f"STALE: '{old[:60]}' found {n}x in {f}, expected {count}x")
        (dst / f).write_text(text.replace(old, new))


def diff_text(src, dst, name):
    r = subprocess.run(["diff", "-u", "--label", f"a/{name}", "--label", f"b/{name}", str(src), str(dst)],
                       capture_output=True, text=True)
    return r.stdout


def compiles(rtl_dir, workdir):
    """Icarus Verilog elaboration of the copy (validity check, not a test)."""
    workdir.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["iverilog", "-g2005", "-o", str(workdir / "compile.vvp"), "-s", "orbit_demo"]
                       + [str(rtl_dir / f) for f in RTL_FILES], capture_output=True, text=True)
    (workdir / "compile.log").write_text(r.stdout + r.stderr)
    return r.returncode == 0


def clean_env():
    env = dict(os.environ)
    for k in ("MAKEFLAGS", "MFLAGS", "MAKELEVEL", "MAKEOVERRIDES", "MAKE_TERMOUT", "MAKE_TERMERR"):
        env.pop(k, None)
    return env


FAILED_RULE = re.compile(r"\*\*\* \[[^\]]*?:\s*\d+:\s*([^\]]+)\] Error")
EVIDENCE = re.compile(r"FAIL|ERROR|Error|error:|mismatch|Assert|assert", re.I)


def run_target(repo, rtl_dir, build_dir, target, logfile, timeout):
    """Run one make target on one copy; returns a result dict."""
    cmd = ["make", "--no-print-directory", "-k", f"RTL_DIR={rtl_dir}", f"BUILD={build_dir}", target]
    t0 = time.time()
    with open(logfile, "w") as fh:
        fh.write("$ " + " ".join(cmd) + "\n")
        fh.flush()
        try:
            p = subprocess.Popen(cmd, cwd=repo, stdout=fh, stderr=subprocess.STDOUT,
                                 env=clean_env(), start_new_session=True)
            rc = p.wait(timeout=timeout)
            status = "PASS" if rc == 0 else "KILL"
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, 9)
            p.wait()
            rc, status = None, "TIMEOUT"
    wall = time.time() - t0
    text = Path(logfile).read_text(errors="replace")
    rules = sorted(set(FAILED_RULE.findall(text)))
    evidence = [l.strip()[:200] for l in text.splitlines()
                if EVIDENCE.search(l) and "Error 1" not in l and not l.startswith("$ ")][:6]
    return {"status": status, "rc": rc, "wall_s": round(wall, 1), "failed_rules": rules,
            "evidence": evidence if status != "PASS" else []}


def run_gap_bench(bench, rtl_dir, workdir):
    """Compile and run the evidence bench on one RTL copy; returns PASS / FAIL / ERROR."""
    workdir.mkdir(parents=True, exist_ok=True)
    vvp = workdir / "gap_bench.vvp"
    r = subprocess.run(["iverilog", "-g2005", "-o", str(vvp), str(bench)]
                       + [str(rtl_dir / f) for f in RTL_FILES], capture_output=True, text=True)
    if r.returncode != 0:
        (workdir / "gap_bench.log").write_text(r.stdout + r.stderr)
        return "ERROR", []
    r = subprocess.run(["vvp", "-n", str(vvp), "+t4"], capture_output=True, text=True, timeout=300)
    (workdir / "gap_bench.log").write_text(r.stdout + r.stderr)
    status = "PASS" if re.search(r"^TB_MUTATION_GAPS PASS", r.stdout, re.M) else \
             "FAIL" if re.search(r"^TB_MUTATION_GAPS FAIL", r.stdout, re.M) else "ERROR"
    return status, [l for l in r.stdout.splitlines() if l.startswith("ERR")][:4]


class Results:
    """results.json, written after every completed target so a run can resume."""

    def __init__(self, path, resume):
        self.path = path
        self.lock = threading.Lock()
        self.data = json.loads(path.read_text()) if resume and path.exists() else {}

    def get(self, mid, target):
        return self.data.get(mid, {}).get("targets", {}).get(target)

    def set_meta(self, mid, **kw):
        with self.lock:
            self.data.setdefault(mid, {"targets": {}}).update(kw)
            self._save()

    def set(self, mid, target, res):
        with self.lock:
            self.data.setdefault(mid, {"targets": {}})["targets"][target] = res
            self._save()

    def _save(self):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=1, sort_keys=True))
        tmp.replace(self.path)


def run_mutant(a, res, mid, name, targets):
    base = a.out / mid
    for t in targets:
        if a.resume and res.get(mid, t) and res.get(mid, t)["status"] != "TIMEOUT":
            continue
        (base / "logs").mkdir(parents=True, exist_ok=True)
        r = run_target(a.repo, base / "rtl", base / "build", t, base / "logs" / f"{t}.log", a.timeout)
        res.set(mid, t, r)
        log(f"{mid} {name:28s} {t:14s} {r['status']:7s} {r['wall_s']:7.1f}s "
            f"{' '.join(r['failed_rules'])}")
    if not a.keep_build:
        shutil.rmtree(base / "build", ignore_errors=True)


def md_escape(s):
    return s.replace("|", "\\|")


def write_report(a, res, mutants, targets, extra):
    lines = ["# Mutation testing of the verification suite", ""]
    try:
        out_shown = a.out.relative_to(a.repo)
    except ValueError:
        out_shown = a.out
    lines.append(f"Generated by `scripts/mutation_test.py` on {datetime.date.today()} "
                 f"(`make mutation`). Source RTL: `{a.rtl_dir}`. Each mutant is a copy under "
                 f"`{out_shown}/m<NN>/rtl` with one design error; each column is "
                 f"`make RTL_DIR=<copy> BUILD=<dir> -k <target>`.")
    lines.append("")
    lines.append("K = target failed (mutant killed), . = target passed (mutant survived it), "
                 "T = timeout (not counted as a kill), - = not run.")
    lines.append("")
    base = res.data.get("m00", {}).get("targets", {})
    lines.append("Baseline (unmodified copy m00): " + ", ".join(
        f"{t} {base.get(t, {}).get('status', 'not run')} ({base.get(t, {}).get('wall_s', '-')} s)"
        for t in targets) + ".")
    lines.append("")
    hdr = "| # | mutant | description | " + " | ".join(targets) + " | killed |"
    lines += [hdr, "|" + "---|" * (4 + len(targets))]
    killed = valid = 0
    per_target = {t: 0 for t in targets}
    survivors = []
    for mid, (name, desc, _) in mutants:
        d = res.data.get(mid, {})
        if d.get("invalid"):
            lines.append(f"| {mid} | `{name}` | {md_escape(desc)} | " + " | ".join("-" for _ in targets)
                         + " | INVALID (does not compile) |")
            continue
        cells, k = [], False
        for t in targets:
            r = d.get("targets", {}).get(t)
            s = r["status"] if r else None
            cells.append({"KILL": "K", "PASS": ".", "TIMEOUT": "T"}.get(s, "-"))
            if s == "KILL":
                k = True
                per_target[t] += 1
        complete = all(d.get("targets", {}).get(t) for t in targets)
        valid += 1
        killed += k
        if not k:
            survivors.append((mid, name, desc, complete))
        lines.append(f"| {mid} | `{name}` | {md_escape(desc)} | " + " | ".join(cells)
                     + f" | {'yes' if k else ('**no**' if complete else 'incomplete')} |")
    lines.append("")
    lines.append(f"**Mutation score: {killed}/{valid} valid mutants killed "
                 f"({100.0 * killed / max(valid, 1):.1f} %).**")
    n_equiv = sum(1 for _, n, _, _ in survivors if ANALYSIS.get(n, (None,))[0] is True)
    if valid - n_equiv > 0:
        lines.append(f"Excluding the {n_equiv} survivor(s) argued equivalent below: "
                     f"{killed}/{valid - n_equiv} ({100.0 * killed / (valid - n_equiv):.1f} %).")
    lines.append("")
    lines.append("Kills per target: " + ", ".join(f"{t} {per_target[t]}" for t in targets) + ".")
    lines.append("")
    sole = {t: [] for t in targets}
    for mid, (name, _, _) in mutants:
        ks = [t for t in targets if (res.data.get(mid, {}).get("targets", {}).get(t) or {}).get("status") == "KILL"]
        if len(ks) == 1:
            sole[ks[0]].append(f"`{name}`")
    lines.append("Mutants killed by exactly one target (no redundancy in the suite for these): "
                 + "; ".join(f"{t}: {', '.join(v)}" for t, v in sole.items() if v) + ".")
    lines.append("")
    gb0 = res.data.get("m00", {}).get("gap_bench")
    if gb0:
        lines.append(f"Evidence bench `{a.gap_bench}` (checks the suite lacks, see the survivors) "
                     f"on the unmodified RTL: **{gb0['status']}**.")
        lines.append("")
    if NOTES:
        lines += ["## Observations", ""] + NOTES + [""]
    lines.append("## Surviving mutants")
    lines.append("")
    if not survivors:
        lines.append("None.")
    missing = []
    for mid, name, desc, complete in survivors:
        lines.append(f"### {mid} `{name}`: {desc}")
        lines.append("")
        diff = (a.out / mid / "mutation.diff")
        if diff.exists():
            body = [l for l in diff.read_text().splitlines()
                    if (l.startswith("+") or l.startswith("-")) and not l.startswith(("+++", "---"))]
            lines += ["```diff"] + body + ["```", ""]
        ex = res.data.get(mid, {}).get("extra", {})
        if ex:
            lines.append("Slower checks run on this survivor: " + ", ".join(
                f"`{t}` {'KILLED it' if r['status'] == 'KILL' else r['status']}"
                + (f" ({', '.join(r['failed_rules'])})" if r['failed_rules'] else "")
                for t, r in ex.items()) + ".")
            lines.append("")
        gb = res.data.get(mid, {}).get("gap_bench")
        if gb:
            lines.append(f"Evidence bench `{a.gap_bench}` on this mutant: **{gb['status']}**"
                         + (" (" + "; ".join(f"`{e}`" for e in gb['errors']) + ")" if gb['errors'] else "")
                         + ".")
            lines.append("")
        if name in ANALYSIS:
            eq, text = ANALYSIS[name]
            lines.append(f"**Verdict: {'equivalent mutant' if eq else 'real test gap'}.** {text}")
        else:
            missing.append(name)
            lines.append("**NO ANALYSIS WRITTEN YET.**")
        lines.append("")
    if extra:
        lines.append(f"Extra (slower) targets run on the survivors only: {', '.join(extra)}.")
        lines.append("")
    lines.append("## Kill evidence (first failing rules per killed mutant)")
    lines.append("")
    for mid, (name, _, _) in mutants:
        ts = res.data.get(mid, {}).get("targets", {})
        parts = [f"{t}: {', '.join(r['failed_rules']) or 'failed'}" for t, r in ts.items()
                 if r["status"] == "KILL"]
        if parts:
            lines.append(f"* {mid} `{name}`: " + "; ".join(parts))
    lines.append("")
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text("\n".join(lines))
    log(f"wrote {a.report}: {killed}/{valid} killed, {len(survivors)} survivor(s)")
    return killed, valid, survivors, missing


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rtl-dir", default="rtl", help="RTL directory to mutate (read only)")
    ap.add_argument("--out", default="build/mutation", help="work directory")
    ap.add_argument("--targets", default="lint sim formal-quick fault-quick synth")
    ap.add_argument("--extra-targets", default="", help="slower targets run on fast-suite survivors")
    ap.add_argument("--jobs", type=int, default=2, help="mutants in parallel (<= 2 on this machine)")
    ap.add_argument("--timeout", type=int, default=3600, help="seconds per make target")
    ap.add_argument("--only", default="", help="comma-separated mutant names (default all)")
    ap.add_argument("--resume", action="store_true", help="reuse results.json, skip finished runs")
    ap.add_argument("--keep-build", action="store_true", help="keep each mutant's build directory")
    ap.add_argument("--gap-bench", default="", help="evidence bench run on the source RTL "
                    "(must pass) and on every survivor (should fail); recorded in the report")
    ap.add_argument("--report", default=None, help="summary.md path (default <out>/summary.md)")
    ap.add_argument("--list", action="store_true", help="list the mutants and exit")
    ap.add_argument("--report-only", action="store_true", help="rewrite the report from results.json")
    a = ap.parse_args()

    a.repo = Path(__file__).resolve().parent.parent
    # Same tool set as the Makefile (which prepends the OSS CAD Suite to PATH).
    oss = os.environ.get("OSS_CAD", "/opt/eda/oss-cad-suite")
    if shutil.which("iverilog") is None and Path(oss, "bin").is_dir():
        os.environ["PATH"] = f"{oss}/bin:{os.environ['PATH']}"
    a.rtl_dir = Path(a.rtl_dir)
    a.out = Path(a.out).resolve()
    a.report = Path(a.report) if a.report else a.out / "summary.md"
    targets = a.targets.split()
    extra = a.extra_targets.split()
    if len(MUTANTS) != len({m[0] for m in MUTANTS}):
        sys.exit("duplicate mutant names")
    if a.list:
        for i, (n, d, _) in enumerate(MUTANTS, 1):
            print(f"m{i:02d} {n:28s} {d}")
        return 0
    # Paths passed to make are relative to the repository (make runs there).
    src = (a.rtl_dir if a.rtl_dir.is_absolute() else a.repo / a.rtl_dir)
    a.out.mkdir(parents=True, exist_ok=True)
    res = Results(a.out / "results.json", a.resume or a.report_only)
    only = set(filter(None, a.only.split(",")))
    selected = [(f"m{i:02d}", m) for i, m in enumerate(MUTANTS, 1) if not only or m[0] in only]

    if not a.report_only:
        # Generate every copy first so that a stale pattern stops the run early.
        make_copy(src, a.out / "m00" / "rtl", [])
        for mid, (name, desc, edits) in selected:
            d = a.out / mid
            try:
                make_copy(src, d / "rtl", edits)
            except ValueError as e:
                sys.exit(f"{mid} {name}: {e}")
            (d / "mutation.diff").write_text("".join(
                diff_text(src / f, d / "rtl" / f, f) for f in RTL_FILES))
            ok = compiles(d / "rtl", d)
            res.set_meta(mid, name=name, description=desc, invalid=not ok)
            if not ok:
                log(f"{mid} {name}: INVALID (Icarus compile failed, see {d}/compile.log)")
        log(f"generated {len(selected)} mutant(s) under {a.out}")

        # Baseline: the unmodified copy must pass every target.
        res.set_meta("m00", name="baseline", description="unmodified copy", invalid=False)
        run_mutant(a, res, "m00", "baseline", targets)
        bad = [t for t in targets if res.get("m00", t)["status"] != "PASS"]
        if bad:
            log(f"baseline FAILED on {bad}: the suite is not green, mutation results would be meaningless")
            return 2

        todo = [(mid, m[0]) for mid, m in selected if not res.data.get(mid, {}).get("invalid")]
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, min(a.jobs, 2))) as ex:
            for f in [ex.submit(run_mutant, a, res, mid, name, targets) for mid, name in todo]:
                f.result()

        # Slower checks on the survivors of the fast suite.
        if extra:
            surv = [(mid, name) for mid, name in todo
                    if not any(res.get(mid, t)["status"] == "KILL" for t in targets)]
            for mid, name in surv:
                base = a.out / mid
                for t in extra:
                    if a.resume and res.data.get(mid, {}).get("extra", {}).get(t):
                        continue
                    (base / "logs").mkdir(parents=True, exist_ok=True)
                    r = run_target(a.repo, base / "rtl", base / "build", t,
                                   base / "logs" / f"extra_{t}.log", a.timeout)
                    with res.lock:
                        res.data[mid].setdefault("extra", {})[t] = r
                        res._save()
                    log(f"{mid} {name:28s} extra {t:10s} {r['status']}")
                if not a.keep_build:
                    shutil.rmtree(base / "build", ignore_errors=True)

    gap_bad = []
    if a.gap_bench and not a.report_only:
        bench = a.repo / a.gap_bench
        surv = ["m00"] + [mid for mid, m in selected if not res.data.get(mid, {}).get("invalid") and
                          not any((res.get(mid, t) or {}).get("status") == "KILL" for t in targets)]
        for mid in surv:
            rtl = a.out / mid / "rtl"
            st, errs = run_gap_bench(bench, rtl, a.out / mid)
            res.set_meta(mid, gap_bench={"status": st, "errors": errs})
            log(f"{mid} gap bench {st}")
            if (mid == "m00") != (st == "PASS"):
                gap_bad.append(mid)
    killed, valid, survivors, missing = write_report(a, res, selected, targets, extra)
    if gap_bad:
        log(f"evidence bench gave an unexpected result on: {', '.join(gap_bad)}")
        return 1
    if missing:
        log(f"survivor(s) without a written analysis: {', '.join(missing)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
