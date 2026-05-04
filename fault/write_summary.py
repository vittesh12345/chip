#!/usr/bin/env python3
"""Write the fault-injection summary (and optionally publish the evidence).

Collects, from <build> = $(BUILD)/fault:
  formal/results.json           formal scenarios (fault/run_formal.py)
  formal/<scenario>/...         generated copies, injection diffs, sby logs
  campaign/report.{md,json}     SEU simulation campaign (fault/campaign_report.py)
  campaign/trials.tsv           per-trial log of the campaign
  negctl/formal/results.json    negative control: formal on the no_compare mutant
  negctl/campaign/report.json   negative control: campaign on the no_compare mutant
and writes one markdown summary. With --publish DIR it also copies the
summary, the injection diffs, a per-bit campaign table and trimmed sby logs
to DIR (the committed reports/fault/). Missing parts are reported as NOT RUN.
"""

import argparse
import collections
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

SCEN_TEXT = {
    "acc_a": "accumulator copy A (`u_acc_a`)",
    "acc_b": "accumulator copy B (`u_acc_b`)",
    "res_a": "result copy A (`u_res_a`, drives `out_data`)",
    "res_b": "result copy B (`u_res_b`)",
    "therm_c0": "thermal copy 0 (`u_thermal.u_copy0`)",
    "therm_c1": "thermal copy 1 (`u_thermal.u_copy1`)",
    "therm_c2": "thermal copy 2 (`u_thermal.u_copy2`)",
    "neg_out_valid_q": "`out_valid_q` (unprotected)",
    "neg_product": "shared product `prod32` of a lane (unprotected, one-cycle transient)",
}
SCOPE = {"acc_a": "any lane, any bit, any cycle", "acc_b": "any lane, any bit, any cycle",
         "res_a": "any lane, any bit, any cycle", "res_b": "any lane, any bit, any cycle",
         "therm_c0": "any bit, any cycle", "therm_c1": "any bit, any cycle", "therm_c2": "any bit, any cycle",
         "neg_out_valid_q": "any cycle", "neg_product": "any lane, any bit, one cycle"}
ORDER = ["acc_a", "acc_b", "res_a", "res_b", "therm_c0", "therm_c1", "therm_c2", "neg_out_valid_q", "neg_product"]

# Noise dropped from the published sby logs.
LOG_NOISE = re.compile(r"\] Copy '|Checking (assumptions|assertions|cover reachability) in step|Trying induction in step|Writing trace to|"
                       r"starting process|finished \(returncode|Removing directory")


def load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def tool(cmd):
    try:
        out = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=30).stdout
        return out.strip().splitlines()[0] if out.strip() else "unknown"
    except (OSError, subprocess.SubprocessError):
        return "not found"


def sha256(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def md_table(head, rows):
    out = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def formal_rows(results):
    by = collections.OrderedDict()
    for t in results:
        by.setdefault(t["scenario"], []).append(t)
    rows = []
    for s in sorted(by, key=lambda x: ORDER.index(x) if x in ORDER else 99):
        tasks = {t["task"]: t for t in by[s]}
        cells = []
        for name in ("prove", "cover", "fire", "loss"):
            t = tasks.get(name)
            if not t:
                continue
            res = t["status"] if t["ok"] else "**%s (expected %s)**" % (t["status"], t["expect"])
            if name == "prove":
                det = "%s (k-induction, %d assertions%s, %.0f s)" % (
                    res, len(t.get("assertions", [])), ", induction closed" if t.get("induction") else "", t["secs"])
            elif name == "cover":
                det = "%s (%d/%d covers reached)" % (res, len(t["covers_reached"]),
                                                     len(t["covers_reached"]) + len(t["covers_unreached"]))
            else:
                det = "%s (expected %s%s)" % (res, t["expect"],
                                              ": `%s` fails at step %d" % (t["failed_assertion"], t["fail_step"])
                                              if "failed_assertion" in t else "")
            cells.append("%s: %s" % (name, det))
        rows.append([s, SCEN_TEXT.get(s, s), SCOPE.get(s, ""), "<br>".join(cells),
                     "yes" if all(t["ok"] for t in by[s]) else "**NO**"])
    return rows


def per_bit_table(trials_tsv, out_path):
    """Per-bit outcome counts of the campaign (521 rows)."""
    counts = collections.defaultdict(collections.Counter)
    cols = None
    with open(trials_tsv) as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            v = line.rstrip("\n").split("\t")
            if v[0] == "trial":
                cols = v
                continue
            t = dict(zip(cols, v))
            if int(t["id"]) >= 0:
                counts[int(t["id"])][t["outcome"]] += 1
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from campaign_report import OUTCOMES, bit_name
    with open(out_path, "w") as f:
        f.write("id\tbit\ttrials\t" + "\t".join(OUTCOMES) + "\n")
        for i in range(521):
            c = counts[i]
            f.write("%d\t%s\t%d\t%s\n" % (i, bit_name(i), sum(c.values()), "\t".join(str(c[o]) for o in OUTCOMES)))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--build", required=True, help="$(BUILD)/fault")
    ap.add_argument("--rtl", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--status", type=int, default=0, help="exit status of the checks (0 = all passed)")
    ap.add_argument("--publish", default="", help="copy the evidence to this directory")
    args = ap.parse_args()
    b = args.build

    formal = load_json(os.path.join(b, "formal", "results.json"))
    neg_formal = load_json(os.path.join(b, "negctl", "formal", "results.json"))
    camp = load_json(os.path.join(b, "campaign", "report.json"))
    neg_camp = load_json(os.path.join(b, "negctl", "campaign", "report.json"))
    camp_md = ""
    if os.path.exists(os.path.join(b, "campaign", "report.md")):
        with open(os.path.join(b, "campaign", "report.md")) as f:
            camp_md = f.read()

    L = []
    L.append("# ORBIT-AI demonstrator: fault injection (area `fault`)")
    L.append("")
    L.append("Generated by `make fault` on %s. Overall result of the checks: **%s**." % (
        datetime.date.today().isoformat(), "PASS" if args.status == 0 else "FAIL (see below)"))
    L.append("")
    L.append("What this shows: which single-event upsets (SEU) the duplicated lane storage and the")
    L.append("triplicated thermal state catch, what escapes from the unprotected flip-flops, and how")
    L.append("often, measured on the production RTL. Faults are injected only into generated copies of")
    L.append("the RTL (formal) or from the testbench by hierarchical assignment (simulation); the")
    L.append("production RTL in `rtl/` is read, never modified, and has no fault ports.")
    L.append("")
    L.append("Tools: %s; %s; %s; %s." % (tool(["yosys", "-V"]), tool(["sby", "--version"]),
                                        tool(["yices", "--version"]), tool(["iverilog", "-V"])))
    L.append("")
    L.append("RTL checked (sha256):")
    L.append("")
    L.append("```")
    for f in args.rtl:
        L.append("%s  %s" % (sha256(f), f))
    L.append("```")
    L.append("")

    # ------------------------------------------------------------------ Part A
    L.append("## Part A: formal fault injection on generated copies (SymbiYosys)")
    L.append("")
    L.append("`fault/gen_fault_copies.py` reads the RTL and writes one copy per scenario to")
    L.append("`$(BUILD)/fault/formal/<scenario>/`: every module renamed `*_fi`, and exactly one storage")
    L.append("element of the lane (or thermal) module made upsettable. For an `orbit_keep_reg` instance the")
    L.append("copy switches that one instance name to `orbit_keep_reg_seu_fi`, a variant whose")
    L.append("sequential block is split into the unchanged next-state logic and a register")
    L.append("`q <= q_next ^ fi_mask`, with `fi_mask` one bit (`fi_bit = $anyconst`) in one solver-chosen")
    L.append("cycle (`fi_req = $anyseq`). The copy keeps the production port list (checked by the")
    L.append("generator). Each diff is in `injection/<scenario>.diff`.")
    L.append("")
    L.append("Harness `fault/fi_harness.sv`: the production `orbit_demo` (fault-free reference) and the")
    L.append("copy run in lockstep on the same unconstrained inputs (reset in cycle 0 only; reset,")
    L.append("`clear_fault`, temperature, handshakes free afterwards). Fault model: at most one upset per")
    L.append("trace in the whole design, in any cycle including reset cycles, any lane, any bit. An upset")
    L.append("requested in cycle k is stored at the edge ending cycle k and is visible from cycle k+1")
    L.append("(the *upset-visible cycle*), which is what a flip at the falling edge does in simulation.")
    L.append("In this synchronous model a flip anywhere inside a clock period acts at the next edge like a")
    L.append("flip at the start of that period (timing closure assumed; a flip inside the setup / hold window,")
    L.append("i.e. metastability, is out of scope), so the model covers every flip time.")
    L.append("")
    if formal:
        L.append(md_table(["Scenario", "Injected element", "Upset", "Tasks and results", "As expected"],
                          formal_rows(formal)))
    else:
        L.append("**NOT RUN**: `%s` is missing." % os.path.join(b, "formal", "results.json"))
    L.append("")
    L.append("Depth: every protected scenario is an **unbounded** proof (k-induction with k = 4; the base")
    L.append("case is BMC over 4 steps and the induction step closes), so it holds for traces of any length,")
    L.append("not only the 8 steps of the brief. Not part of the flow, tried once by hand during development")
    L.append("on `acc_a`: a BMC of the port-level properties *without* the helper invariants did not get far")
    L.append("(after about 10 minutes yices was at step 8 and abc bmc3 at frame 10, each step slower than the")
    L.append("last, because the solver re-derives the equality of the two multiplier / adder datapaths in")
    L.append("every unrolled step); a 24-step BMC *with* them passed in 7 minutes, which the unbounded proof")
    L.append("already implies.")
    L.append("")
    L.append("### What is proven (accumulator and result scenarios, `L_*` and `D_*`)")
    L.append("")
    L.append("For an upset in one copy of accumulator or result storage (any lane, bit, cycle):")
    L.append("")
    L.append("* `L_lockstep_before_upset`: until the upset, all 521 state bits of the copy equal the reference.")
    L.append("* `L_single_bit_in_target`: in the upset-visible cycle exactly one state bit differs, inside the target element.")
    L.append("* `L_stop_in_upset_cycle`: in that same cycle `mismatch` is 1 and `in_ready` = `out_valid` = 0.")
    L.append("* `L_fault_next_cycle`: `fault` is 1 in the next cycle, unless reset or `clear_fault` is asserted")
    L.append("  in the upset-visible cycle; `L_overwritten_no_fault`: in that case (the only way the upset copy")
    L.append("  can be overwritten before it is used, since `in_ready` is already 0 so no beat or result can")
    L.append("  write it) there is no fault and all 521 state bits equal the reference again one cycle later.")
    L.append("* `L_fault_sticky`: `fault` stays 1 until reset / `clear_fault`; `L_resync_after_clear`: after any")
    L.append("  reset / `clear_fault` the copy equals the reference bit for bit (recovery).")
    L.append("* `L_stop_blocks`, `L_stop_only_after_upset`: a stop blocks both handshakes and never happens")
    L.append("  without an upset (no false alarm); `L_thermal_unaffected`: voted state, admission, repair flag")
    L.append("  and shutdown request equal the reference in every cycle.")
    L.append("* `D_out_fire_matches_ref`: **every `out_fire` of the upset copy is an `out_fire` of the reference")
    L.append("  in the same cycle with identical `out_data`** (no wrong, extra or duplicated result, ever);")
    L.append("  `D_no_wrong_result`, `D_no_extra_result`: the same for presented results; `D_no_silent_loss`:")
    L.append("  a result the reference presents is withheld only while the copy is stopped (`fault` or")
    L.append("  `mismatch`); `D_no_silent_beat_divergence`: `in_ready` differs from the reference only while stopped.")
    L.append("")
    L.append("### What is proven (thermal scenarios, `T_*` and `D_*`)")
    L.append("")
    L.append("For an upset in one thermal copy (either bit, any cycle): `T_voted_state_equal` and")
    L.append("`T_admission_equal` (voted state, `admit` and `in_ready` equal the reference in every cycle),")
    L.append("`T_other_ports_equal` (`out_valid`, `out_data`, `fault`, `shutdown_req` too; no fault stop),")
    L.append("`T_copy_rewritten_next_cycle` (one cycle after the upset-visible cycle the upset copy equals")
    L.append("the other two and the reference), `T_repair_iff_disagree` (`therm_repair` is high exactly while")
    L.append("the three copies do not all agree), `T_repair_only_upset_cycle` (which is exactly the")
    L.append("upset-visible cycle), `T_repaired_after_upset` (from then on all 521 bits equal the reference),")
    L.append("plus `T_lockstep_before_upset`, `T_single_bit_in_target` and the `D_*` checks.")
    L.append("")
    L.append("`H_*` are helper invariants for the induction (the reference's copies agree and its `fault_q`")
    L.append("is 0; after the upset the copy is either back in lockstep or stopped with a latched fault). They")
    L.append("are asserted and proven like the others, not assumed. The cover tasks show that the upset is")
    L.append("reachable at the lowest and highest bit of the target, while a result is being transferred /")
    L.append("a beat accepted, in NORMAL, THROTTLE and STOP, with the upset copy reading the unused code 3,")
    L.append("in the `clear_fault`-overwrite case, and that results flow again after fault and `clear_fault`.")
    L.append("")

    if formal:
        negs = [t for t in formal if t["scenario"].startswith("neg_")]
        L.append("### Negative scenarios: expected escapes (SPEC section 8)")
        L.append("")
        L.append("The same data-integrity checks, applied to an upset of an unprotected element, must FAIL,")
        L.append("and do (bounded model check, depth 12). Counterexample excerpts (step = cycle; `fi_fire` = 1")
        L.append("means the upset is stored at the end of that cycle; `out_data` is shown for the lane that")
        L.append("differs, else lane 0):")
        L.append("")
        for t in negs:
            what = {"neg_out_valid_q/fire": "out_valid_q 0 -> 1: the copy transfers a result that the reference does not transfer. The shortest counterexample presents a never-computed buffer content right after reset; the cover task of this scenario also reaches `C_duplicate_result` (an already delivered result delivered again)",
                    "neg_out_valid_q/loss": "out_valid_q 1 -> 0: the reference presents a result, the copy silently drops it (lost result, no fault)",
                    "neg_product/fire": "one-cycle upset of the shared product: both copies take the same wrong value, no mismatch, wrong result transferred (SDC)"}.get(
                        "%s/%s" % (t["scenario"], t["task"]), "")
            L.append("**%s / %s**: %s. Result: %s (expected %s)%s." % (
                t["scenario"], t["task"], what, t["status"], t["expect"],
                ", `%s` fails at step %d" % (t["failed_assertion"], t["fail_step"]) if "failed_assertion" in t else ""))
            if "trace" in t:
                L.append("")
                L.append("```")
                L.append(t["trace"])
                L.append("```")
            L.append("")

    L.append("### Negative control: copy comparator removed")
    L.append("")
    L.append("`gen_fault_copies.py --write-mutant no_compare` writes an RTL copy with `assign mismatch = 1'b0;`")
    L.append("in `orbit_mac_lane` (diff: `injection/negctl_no_compare.diff`). The lane proofs must then fail:")
    L.append("")
    if neg_formal:
        rows = []
        for t in neg_formal:
            rows.append([t["scenario"], t["task"], t["status"], t["expect"], "yes" if t["ok"] else "**NO**",
                         "`%s` fails at step %d" % (t["failed_assertion"], t["fail_step"]) if "failed_assertion" in t else ""])
        L.append(md_table(["Scenario (mutant)", "Task", "Result", "Expected", "As expected", "Detail"], rows))
        for t in neg_formal:
            if t["task"] == "fire" and "trace" in t:
                L.append("")
                L.append("Counterexample, %s / fire (the upset reaches `out_data` and is transferred, no fault):" % t["scenario"])
                L.append("")
                L.append("```")
                L.append(t["trace"])
                L.append("```")
                break
    else:
        L.append("**NOT RUN**")
    L.append("")

    # ------------------------------------------------------------------ Part B
    L.append("## Part B: simulation SEU campaign (Icarus Verilog)")
    L.append("")
    L.append("`fault/tb_seu_campaign.v`: two copies of the production design, each behind its own host")
    L.append("(driver, scoreboard written from SPEC sections 3-5, fault reaction = `clear_fault` two cycles")
    L.append("after `fault` is seen). Both get the same random workload (beats with random `in_first` /")
    L.append("`in_last`, random and edge-case operands, 85 % beat offers, 75 % `out_ready`, a temperature")
    L.append("profile of random segments through NORMAL, the hysteresis band, THROTTLE, STOP, invalid")
    L.append("sensor and cold; 1 trial in 8 also has rare scheduled `clear_fault` pulses). Per trial: reset,")
    L.append("a random prefix (8..127 cycles, stratified per bit), one bit of one copy flipped by")
    L.append("hierarchical assignment at the falling clock edge, 64 more cycles, then a drain (cool, consumer")
    L.append("ready; 24 cycles with beats, 8 without). The bench checks that the two copies are identical")
    L.append("before the flip and differ in exactly the intended bit after it. Outcomes: MASKED (port trace")
    L.append("identical to the fault-free copy), DETECTED (`fault` rose, no wrong data transferred),")
    L.append("REPAIRED (only `therm_repair` differed), TIMING (no fault, every result correct, but the port")
    L.append("trace differs, e.g. a shifted throttled admission), SDC (a transferred result is wrong), LOST")
    L.append("(an accepted result dropped without fault), EXTRA (a result transferred with none pending:")
    L.append("duplicate or stale), HANG (no fault but no progress in the drain), OTHER.")
    L.append("")
    if camp_md:
        L.append(camp_md.strip())
    else:
        L.append("**NOT RUN**: `%s` is missing." % os.path.join(b, "campaign", "report.md"))
    L.append("")
    L.append("### Negative control: campaign on the no_compare mutant")
    L.append("")
    if neg_camp:
        g = neg_camp["groups"]
        rows = [[g[k]["title"], g[k]["trials"]] + [g[k]["counts"][o] for o in
                                                   ("MASKED", "DETECTED", "SDC", "LOST", "EXTRA")]
                for k in ("acc", "res")]
        L.append(md_table(["Storage group (mutant)", "Trials", "MASKED", "DETECTED", "SDC", "LOST", "EXTRA"], rows))
        L.append("")
        L.append("Checks: " + "; ".join("%s: %s" % (c["name"], c["result"]) for c in neg_camp["checks"]
                                     if "escapes observed" in c["name"]) + ".")
        L.append("With the comparator removed the same bench reports silent data corruption, so its SDC /")
        L.append("loss classification is able to see an escape in the protected groups.")
    else:
        L.append("**NOT RUN**")
    L.append("")

    # ------------------------------------------------------------------ Notes
    L.append("## Limits of these results")
    L.append("")
    L.append("* Single-upset model: one flipped bit per trace / trial. Multiple-bit upsets, an upset in both")
    L.append("  copies of a pair (common mode) and upsets in combinational logic other than the shared product")
    L.append("  (comparators, voter, handshake logic, clock, reset) are not injected. The product scenario")
    L.append("  stands for the whole class of common-mode datapath faults: they are not detected.")
    L.append("* The formal reference is the production RTL itself. Its own correctness against the SPEC is")
    L.append("  the formal area's job (`reports/formal/`); here it is only the fault-free twin.")
    L.append("* `D_no_silent_loss` / `D_no_silent_beat_divergence` treat the internal `mismatch` as a stop in")
    L.append("  the upset-visible cycle, because `fault` only rises one cycle later by design.")
    L.append("* The campaign measures outcomes for one workload distribution and one seed (deterministic); the")
    L.append("  rates of the unprotected flip-flops (e.g. how often `out_valid_q` is 1 at the upset) depend on")
    L.append("  that workload. The formal part is exhaustive over inputs, lane, bit and cycle.")
    L.append("* `fault_q` can only flip 0 -> 1 in a single-upset campaign (it is 0 whenever the fault-free")
    L.append("  design runs), which gives a false fault stop (availability loss, no data error). Its 1 -> 0")
    L.append("  case (re-enabling a stopped design, SPEC section 8) needs two faults and is not measured.")
    L.append("* Nothing here is a radiation test; it checks the logic of the protection only.")
    L.append("")
    L.append("Reproduce: `make fault` (about 3 minutes; `make fault-quick`, about 1 minute, is the subset in")
    L.append("`make test`).")
    L.append("Individual parts: `make fault-formal`, `make fault-campaign`, `make fault-negctl`.")
    L.append("")

    with open(args.out, "w") as f:
        f.write("\n".join(L))
    print("[fault] summary written to %s" % args.out)

    if args.publish:
        pub = args.publish
        os.makedirs(os.path.join(pub, "injection"), exist_ok=True)
        os.makedirs(os.path.join(pub, "logs"), exist_ok=True)
        shutil.copy(args.out, os.path.join(pub, "summary.md"))
        for root in ("formal",):
            d = os.path.join(b, root)
            for s in sorted(os.listdir(d)) if os.path.isdir(d) else []:
                src = os.path.join(d, s, "injection.diff")
                if os.path.exists(src):
                    shutil.copy(src, os.path.join(pub, "injection", s + ".diff"))
        mut = os.path.join(b, "negctl", "rtl", "mutation.diff")
        if os.path.exists(mut):
            shutil.copy(mut, os.path.join(pub, "injection", "negctl_no_compare.diff"))
        for res, prefix in ((formal, ""), (neg_formal, "negctl_")):
            for t in res or []:
                lf = os.path.join(t["work"], "logfile.txt")
                if os.path.exists(lf):
                    with open(lf) as fi, open(os.path.join(pub, "logs", "%s%s_%s.log" % (prefix, t["scenario"], t["task"])), "w") as fo:
                        for line in fi:
                            if not LOG_NOISE.search(line):
                                fo.write(re.sub(r"/\S*/build/fault/", "$(BUILD)/fault/", line))
        trials = os.path.join(b, "campaign", "trials.tsv")
        if os.path.exists(trials):
            per_bit_table(trials, os.path.join(pub, "campaign_per_bit.tsv"))
        for name in ("report.md",):
            src = os.path.join(b, "campaign", name)
            if os.path.exists(src):
                shutil.copy(src, os.path.join(pub, "campaign.md"))
        print("[fault] evidence published to %s/" % pub)
    return 0


if __name__ == "__main__":
    sys.exit(main())
