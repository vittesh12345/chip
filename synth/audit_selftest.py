#!/usr/bin/env python3
"""Self-test of scripts/storage_audit.py (area: synth).

The audit is only useful if it fails when redundancy is lost. This script takes
the flat JSON view of a netlist that passes the audit, applies one deliberate
defect at a time (each a way synthesis could silently defeat the redundancy),
and requires the audit to FAIL with the matching diagnosis. The unmodified
netlist must PASS.

usage: audit_selftest.py <flat netlist.json> <work dir>
Exit status 0 only if the baseline passes and every defect is detected.
"""

import copy
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import storage_audit  # noqa: E402

FF_PREFIXES = ("$_DFF", "$_SDFF", "$_DFFE", "$_ALDFF")


def top_of(data):
    tops = [m for m, v in data["modules"].items()
            if str(v.get("attributes", {}).get("top", "0")).strip("0") != ""]
    assert len(tops) == 1, "expected exactly one top module"
    if len(data["modules"]) != 1:
        raise SystemExit("audit_selftest: needs a flat netlist (one module), got %d modules"
                         % len(data["modules"]))
    return data["modules"][tops[0]]


def bit_of(mod, net, idx):
    return mod["netnames"][net]["bits"][idx]


def ff_driving(mod, bit):
    for name, cell in mod["cells"].items():
        if cell["type"].startswith(FF_PREFIXES) and cell["connections"].get("Q") == [bit]:
            return name, cell
    raise KeyError("no flip-flop drives bit %r" % bit)


def replace_bit(mod, old, new):
    """Rewire every use of net bit `old` (cells and names) to `new`."""
    for cell in mod["cells"].values():
        for port, bits in cell["connections"].items():
            cell["connections"][port] = [new if b == old else b for b in bits]
    for nn in mod["netnames"].values():
        nn["bits"] = [new if b == old else b for b in nn["bits"]]


def fresh_bit(mod):
    top = 1
    for nn in mod["netnames"].values():
        top = max([top] + [b for b in nn["bits"] if isinstance(b, int)])
    for cell in mod["cells"].values():
        for bits in cell["connections"].values():
            top = max([top] + [b for b in bits if isinstance(b, int)])
    return top + 1


# Each defect: (name, expected fragment of the audit report, mutator(mod)).
def m_merge_thermal(mod):
    # What synthesis does without keep_hierarchy: copy1 bit 0 reuses copy0's flop.
    q0 = bit_of(mod, "u_thermal.u_copy0.q", 0)
    q1 = bit_of(mod, "u_thermal.u_copy1.q", 0)
    name, _ = ff_driving(mod, q1)
    del mod["cells"][name]
    replace_bit(mod, q1, q0)


def m_merge_acc_pair(mod):
    # Accumulator copy B bit 9 driven by copy A's flop.
    qa = bit_of(mod, "g_lane[1].u_lane.u_acc_a.q", 9)
    qb = bit_of(mod, "g_lane[1].u_lane.u_acc_b.q", 9)
    name, _ = ff_driving(mod, qb)
    del mod["cells"][name]
    replace_bit(mod, qb, qa)


def m_const_copy(mod):
    # A result bit optimized away to a constant.
    q = bit_of(mod, "g_lane[2].u_lane.u_res_b.q", 5)
    name, _ = ff_driving(mod, q)
    del mod["cells"][name]
    replace_bit(mod, q, "0")


def m_const_d(mod):
    _, cell = ff_driving(mod, bit_of(mod, "g_lane[1].u_lane.u_acc_a.q", 3))
    cell["connections"]["D"] = ["0"]


def m_d_is_q(mod):
    q = bit_of(mod, "u_thermal.u_copy2.q", 1)
    _, cell = ff_driving(mod, q)
    cell["connections"]["D"] = [q]


def m_pair_d_merged(mod):
    _, ca = ff_driving(mod, bit_of(mod, "g_lane[0].u_lane.u_acc_a.q", 7))
    _, cb = ff_driving(mod, bit_of(mod, "g_lane[0].u_lane.u_acc_b.q", 7))
    cb["connections"]["D"] = list(ca["connections"]["D"])


def m_bits_d_merged(mod):
    _, c1 = ff_driving(mod, bit_of(mod, "g_lane[3].u_lane.u_res_a.q", 1))
    _, c2 = ff_driving(mod, bit_of(mod, "g_lane[3].u_lane.u_res_a.q", 2))
    c1["connections"]["D"] = list(c2["connections"]["D"])


def m_copy_missing(mod):
    # The copy's net name disappears (e.g. renamed or swept); other names of
    # the same net may remain, but the audit identifies a copy by <inst>.q.
    del mod["netnames"]["g_lane[1].u_lane.u_res_a.q"]


def m_not_ff(mod):
    # A copy bit driven by a gate instead of a flip-flop (e.g. retimed away).
    q = bit_of(mod, "g_lane[0].u_lane.u_res_b.q", 0)
    name, cell = ff_driving(mod, q)
    d = cell["connections"]["D"][0]
    mod["cells"][name] = {"hide_name": 1, "type": "$_BUF_", "parameters": {}, "attributes": {},
                          "port_directions": {"A": "input", "Y": "output"},
                          "connections": {"A": [d], "Y": [q]}}


def m_wrong_clock(mod):
    _, cell = ff_driving(mod, bit_of(mod, "u_thermal.u_copy1.q", 0))
    cell["connections"]["C"] = [bit_of(mod, "rst_n", 0)]


def m_extra_ff(mod):
    # An extra unprotected flop: total count and unprotected list change.
    nb = fresh_bit(mod)
    mod["cells"]["selftest_extra_ff"] = {
        "hide_name": 0, "type": "$_DFF_P_", "parameters": {}, "attributes": {},
        "port_directions": {"C": "input", "D": "input", "Q": "output"},
        "connections": {"C": [bit_of(mod, "clk", 0)], "D": [bit_of(mod, "in_valid", 0)], "Q": [nb]}}
    mod["netnames"]["selftest_extra_q"] = {"hide_name": 0, "bits": [nb], "attributes": {}}


def m_latch(mod):
    nb = fresh_bit(mod)
    mod["cells"]["selftest_latch"] = {
        "hide_name": 0, "type": "$_DLATCH_P_", "parameters": {}, "attributes": {},
        "port_directions": {"E": "input", "D": "input", "Q": "output"},
        "connections": {"E": [bit_of(mod, "in_valid", 0)], "D": [bit_of(mod, "in_first", 0)], "Q": [nb]}}


DEFECTS = [
    ("thermal copies merged", "(copies merged)", m_merge_thermal),
    ("accumulator pair bit merged", "(copies merged)", m_merge_acc_pair),
    ("copy bit is a constant", "(flip-flop optimized away)", m_const_copy),
    ("constant D input", "has constant D input", m_const_d),
    ("D tied to own Q", "has D tied to its own Q", m_d_is_q),
    ("pair next-state logic merged", "(next-state logic merged)", m_pair_d_merged),
    ("bits of one copy share D", "(bits merged)", m_bits_d_merged),
    ("copy net missing", "not found (copy optimized away or renamed)", m_copy_missing),
    ("copy bit driven by a gate", "is not driven by exactly one flip-flop output", m_not_ff),
    ("copy flop on wrong clock", "is not clocked by top-level clk", m_wrong_clock),
    ("extra unprotected flop", "total flip-flop bits 522, expected 521", m_extra_ff),
    ("latch present", "latches present", m_latch),
]


def run_audit(path):
    return storage_audit.audit(path, None, 4, 521,
                               ["fault_q", "out_valid_q", "u_thermal.phase"], "clk")


def main():
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    src, work = sys.argv[1], sys.argv[2]
    os.makedirs(work, exist_ok=True)
    with open(src) as fh:
        base = json.load(fh)
    top_of(base)

    failures = 0
    ok, _, _ = run_audit(src)
    print("%-32s %s" % ("baseline (unmodified)", "PASS as expected" if ok else "UNEXPECTED FAIL"))
    failures += 0 if ok else 1

    for i, (name, expect, mutate) in enumerate(DEFECTS):
        data = copy.deepcopy(base)
        mutate(top_of(data))
        path = os.path.join(work, "defect_%02d.json" % i)
        with open(path, "w") as fh:
            json.dump(data, fh)
        ok, text, _ = run_audit(path)
        detected = (not ok) and (expect in text)
        with open(os.path.join(work, "defect_%02d.txt" % i), "w") as fh:
            fh.write(text)
        print("%-32s %s" % (name, "detected" if detected else
                            ("NOT DETECTED" if ok else "failed, but without '%s'" % expect)))
        failures += 0 if detected else 1

    print("AUDIT_SELFTEST %s: %d defect classes, %d problems"
          % ("PASS" if failures == 0 else "FAIL", len(DEFECTS), failures))
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
