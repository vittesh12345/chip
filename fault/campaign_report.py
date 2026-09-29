#!/usr/bin/env python3
"""Summarize and check the SEU simulation campaign (fault/tb_seu_campaign.v).

Reads the per-trial log of the bench, groups the trials by storage group
(SPEC section 7), writes a markdown table and a JSON summary, and checks the
expectations of SPEC sections 5, 6 and 8. Exit status 1 if a check fails.

Checks:
  * the bench finished with 0 internal errors (lockstep before the upset, the
    flip changed exactly the intended bit, the fault-free run was perfect);
  * every fault-free control trial is MASKED;
  * coverage: every one of the 521 bits, at least --min-tpb trials per bit,
    more than --min-total trials;
  * accumulator and result pairs: every trial DETECTED (fault one cycle
    after the upset, handshakes blocked in the upset cycle) or MASKED; no
    SDC, lost, extra, hang or other outcome;
  * thermal triple: every trial REPAIRED (therm_repair seen, nothing else
    visible at the ports);
  * negative control: out_valid_q shows at least one escape, so the
    classifier is able to see one.
The phase, out_valid_q and fault_q escapes are reported, not failed: they are
the known unprotected elements of SPEC section 8.
"""

import argparse
import collections
import json
import sys

OUTCOMES = ["MASKED", "DETECTED", "REPAIRED", "TIMING", "SDC", "LOST", "EXTRA", "HANG", "OTHER"]
ESCAPES = ["SDC", "LOST", "EXTRA", "HANG", "OTHER"]
GROUPS = [
    ("acc", "Accumulator pairs (4 lanes x A/B x 32)", range(0, 256), "duplicate + compare"),
    ("res", "Result pairs (4 lanes x A/B x 32)", range(256, 512), "duplicate + compare"),
    ("therm", "Thermal triple (3 copies x 2)", range(512, 518), "TMR + repair"),
    ("phase", "Throttle phase", range(518, 519), "none"),
    ("ovq", "out_valid_q", range(519, 520), "none"),
    ("faultq", "fault_q", range(520, 521), "none"),
]
THERM = {0: "NORMAL", 1: "THROTTLE", 2: "STOP", 3: "code 3"}


def bit_name(i):
    if i < 512:
        grp = "acc" if i < 256 else "res"
        copy = "a" if (i % 256) < 128 else "b"
        lane = (i % 128) // 32
        return "g_lane[%d].u_lane.u_%s_%s.q[%d]" % (lane, grp, copy, i % 32)
    if i < 518:
        return "u_thermal.u_copy%d.q[%d]" % ((i - 512) // 2, (i - 512) % 2)
    return {518: "u_thermal.phase", 519: "out_valid_q", 520: "fault_q"}[i]


def load(path):
    trials, header, footer = [], None, None
    with open(path) as f:
        for line in f:
            line = line.rstrip("\n")
            if line.startswith("# done"):
                footer = dict(kv.split("=") for kv in line[2:].split()[1:])
            elif line.startswith("#"):
                header = line[2:]
            elif line.startswith("trial"):
                cols = line.split("\t")
            elif line:
                v = line.split("\t")
                t = dict(zip(cols, v))
                for k in cols:
                    if k != "outcome":
                        t[k] = int(t[k])
                trials.append(t)
    return trials, header, footer


def table(rows, head):
    out = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("trials")
    ap.add_argument("--out", required=True, help="output prefix for .md / .json")
    ap.add_argument("--min-tpb", type=int, default=10)
    ap.add_argument("--min-total", type=int, default=5001)
    args = ap.parse_args()

    trials, header, footer = load(args.trials)
    checks = []

    def check(name, ok, detail):
        checks.append(dict(name=name, result="PASS" if ok else "FAIL", detail=detail))

    check("bench finished without internal errors", footer is not None and footer.get("errors") == "0",
          "footer: %s" % (footer if footer else "missing (bench did not finish)"))

    controls = [t for t in trials if t["id"] < 0]
    inj = [t for t in trials if t["id"] >= 0]
    ctl_bad = [t["trial"] for t in controls if t["outcome"] != "MASKED"]
    check("fault-free controls are MASKED", controls and not ctl_bad,
          "%d controls, not MASKED: %s" % (len(controls), ctl_bad or "none"))

    per_bit = collections.Counter(t["id"] for t in inj)
    missing = [i for i in range(521) if per_bit[i] == 0]
    min_tpb = min(per_bit[i] for i in range(521)) if not missing else 0
    check("coverage of the 521 storage bits", not missing and min_tpb >= args.min_tpb and len(inj) >= args.min_total,
          "%d bits covered, min %d trials per bit (need %d), %d injected trials (need %d)" %
          (521 - len(missing), min_tpb, args.min_tpb, len(inj), args.min_total))

    by_group = {}
    rows = []
    for key, title, ids, prot in GROUPS:
        g = [t for t in inj if t["id"] in ids]
        c = collections.Counter(t["outcome"] for t in g)
        esc = sum(c[o] for o in ESCAPES)
        by_group[key] = dict(title=title, bits=len(ids), trials=len(g), counts={o: c[o] for o in OUTCOMES},
                             escapes=esc)
        rows.append([title, prot, len(ids), len(g)] + [c[o] for o in OUTCOMES] +
                    ["%d (%.1f %%)" % (esc, 100.0 * esc / len(g)) if g else "-"])

    # Duplicated storage: detected (latency 1, stop in the upset cycle) or masked.
    for key in ("acc", "res"):
        ids = dict((k, i) for k, _, i, _ in GROUPS)[key]
        g = [t for t in inj if t["id"] in ids]
        bad = [t for t in g if t["outcome"] not in ("DETECTED", "MASKED")]
        lat_bad = [t for t in g if t["outcome"] == "DETECTED" and (t["latency"] != 1 or t["stop_same_cycle"] != 1)]
        check("%s: no escape (only DETECTED or MASKED)" % key, g and not bad,
              "%d trials; %s" % (len(g), "; ".join("trial %d %s %s" % (t["trial"], bit_name(t["id"]), t["outcome"])
                                                  for t in bad[:5]) or "none escaped"))
        check("%s: fault one cycle after the upset, handshakes blocked in the upset cycle" % key, g and not lat_bad,
              "%d detected trials checked; exceptions: %s" %
              (sum(t["outcome"] == "DETECTED" for t in g),
               ", ".join("trial %d latency %d stop %d" % (t["trial"], t["latency"], t["stop_same_cycle"])
                         for t in lat_bad[:5]) or "none"))
    g = [t for t in inj if 512 <= t["id"] < 518]
    bad = [t for t in g if t["outcome"] != "REPAIRED"]
    check("therm: every upset REPAIRED, nothing else visible", g and not bad,
          "%d trials; %s" % (len(g), "; ".join("trial %d %s %s" % (t["trial"], bit_name(t["id"]), t["outcome"])
                                              for t in bad[:5]) or "all REPAIRED"))
    check("negative control: out_valid_q upsets escape", by_group["ovq"]["escapes"] > 0,
          "%d of %d out_valid_q trials escaped" % (by_group["ovq"]["escapes"], by_group["ovq"]["trials"]))

    # Breakdowns of the unprotected flip-flops by the condition at injection.
    ovq = collections.Counter((t["ovq_at_inj"], t["outcome"]) for t in inj if t["id"] == 519)
    ph = collections.Counter((t["therm_at_inj"], t["outcome"]) for t in inj if t["id"] == 518)
    fq = collections.Counter(t["outcome"] for t in inj if t["id"] == 520)
    lat = collections.Counter(t["latency"] for t in inj if t["id"] < 512 and t["outcome"] == "DETECTED")
    masked_dup = [t for t in inj if t["id"] < 512 and t["outcome"] == "MASKED"]

    md = []
    md.append("Bench: `fault/tb_seu_campaign.v` (Icarus Verilog), %s." % header)
    md.append("")
    md.append(table(rows, ["Storage group", "Protection", "Bits", "Trials"] + OUTCOMES + ["Escapes (SDC+LOST+EXTRA+HANG+OTHER)"]))
    md.append("")
    md.append("Controls (no upset): %d trials, %d MASKED. Injected trials: %d; every one of the 521 bits "
              "at least %d times." % (len(controls), len(controls) - len(ctl_bad), len(inj), min_tpb))
    md.append("")
    md.append("Detection latency of the accumulator / result upsets (cycles from the upset cycle to the "
              "first cycle with `fault` = 1): %s. MASKED accumulator / result trials: %d%s." % (
                  ", ".join("%d: %d trials" % (k, v) for k, v in sorted(lat.items())) or "none",
                  len(masked_dup),
                  (" (%s)" % ", ".join("trial %d %s" % (t["trial"], bit_name(t["id"])) for t in masked_dup[:6]))
                  if masked_dup else ""))
    md.append("")
    md.append("Unprotected flip-flops by the state at the moment of the upset:")
    md.append("")
    r2 = []
    for v in (0, 1):
        c = {o: ovq[(v, o)] for o in OUTCOMES}
        n = sum(c.values())
        if n:
            r2.append(["out_valid_q = %d (flips to %d)" % (v, 1 - v), n] + [c[o] for o in OUTCOMES])
    for s in (0, 1, 2, 3):
        c = {o: ph[(s, o)] for o in OUTCOMES}
        n = sum(c.values())
        if n:
            r2.append(["phase, voted state %s" % THERM[s], n] + [c[o] for o in OUTCOMES])
    n = sum(fq.values())
    if n:
        r2.append(["fault_q (always 0 before a single upset, flips to 1)", n] + [fq[o] for o in OUTCOMES])
    md.append(table(r2, ["Element / condition", "Trials"] + OUTCOMES))
    md.append("")
    md.append("Checks:")
    md.append("")
    md.append(table([[c["name"], c["result"], c["detail"]] for c in checks], ["Check", "Result", "Detail"]))
    md.append("")

    with open(args.out + ".md", "w") as f:
        f.write("\n".join(md))
    with open(args.out + ".json", "w") as f:
        json.dump(dict(header=header, footer=footer, controls=len(controls), injected=len(inj),
                       min_trials_per_bit=min_tpb, groups=by_group, checks=checks,
                       latency=dict((str(k), v) for k, v in lat.items())), f, indent=1)
    failed = [c for c in checks if c["result"] != "PASS"]
    for c in checks:
        print("[fault] campaign check %-4s %s: %s" % (c["result"], c["name"], c["detail"]))
    print("[fault] campaign: %d trials, %d checks failed; see %s.md" % (len(trials), len(failed), args.out))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
