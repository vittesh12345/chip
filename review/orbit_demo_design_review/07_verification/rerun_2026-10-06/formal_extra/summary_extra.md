# Formal verification summary: orbit_demo (fault-free)

Generated 2026-10-06 18:41 UTC by `formal/summarize.py` from the SymbiYosys run directories.
RTL: `rtl`. Tools: Yosys 0.69+154 (git sha1 30d62572e-dirty, Release, Clang /usr/bin/clang++ 21.1.8); SBY v0.69; Yices 2.7.0; bitwuzla 0.9.1.

Harness: `formal/orbit_demo_fv.sv` (independent reference model from docs/SPEC.md, all DUT
inputs free, reset only in the first cycle; reset and clear_fault stay free afterwards;
the `clear` task starts from an unconstrained state and `wrap` from a consistent one).
Jobs: `formal/orbit_demo.sby`, one task per property group.

## Per-property status

| Property | Meaning | Status | Evidence (task: assertions, method, solver, time) |
|---|---|---|---|
| P1 | on every out_fire, out_data equals the reference result for every lane (exact, INT32 wraparound) | PROVEN unbounded | `datapath_pdr`: PASS, 8 assertions, no helper invariants, PDR (unbounded), abc/pdr, 940s<br>`datapath_pdr`: PASS, 8 assertions, no helper invariants, PDR (unbounded), abc/pdr, 940s |
| P2 | every accepted in_last produces exactly one out_fire, in order (no loss, no duplication) | not run / no result | - |
| P3 | out_valid && !out_ready: out_valid stays high and out_data is unchanged next cycle | not run / no result | - |
| P4 | in_ready low when thermal STOP/3, fault, clear_fault, or buffer full && !out_ready | not run / no result | - |
| P5 | voted thermal state follows the SPEC table (independent FSM); reset gives STOP | not run / no result | - |
| P6 | throttle: first THROTTLE cycle admits, consecutive THROTTLE cycles alternate | not run / no result | - |
| P7 | fault-free: fault and therm_repair never rise, duplicated / triplicated copies equal | not run / no result | - |
| P8 | clear_fault: then fault = 0, out_valid = 0, storage zero, next beat sums from 0 (also from a latched fault) | PROVEN unbounded | `datapath_pdr`: PASS, 23 assertions, no helper invariants, PDR (unbounded), abc/pdr, 940s<br>`datapath_pdr`: PASS, 23 assertions, no helper invariants, PDR (unbounded), abc/pdr, 940s |

## Jobs

| Task | Groups | Mode / method | Engine / solver | Status | Wall time (s) | Assertions | Covers |
|---|---|---|---|---|---|---|---|
| datapath_pdr | datapath (no helpers) | PDR (unbounded) | abc/pdr | PASS | 940 | 31 | 0 |
| datapath_pdr | datapath (no helpers) | PDR (unbounded) | abc/pdr | PASS | 940 | 31 | 0 |

## Assertions by task

<details><summary><code>datapath_pdr</code>: PASS, 31 assertions</summary>

| Assertion | Result |
|---|---|
| P1_out_fire_data_lane0 | PROVEN unbounded (pdr) |
| P1_out_fire_data_lane1 | PROVEN unbounded (pdr) |
| P1_out_fire_data_lane2 | PROVEN unbounded (pdr) |
| P1_out_fire_data_lane3 | PROVEN unbounded (pdr) |
| P1_out_valid_data_lane0 | PROVEN unbounded (pdr) |
| P1_out_valid_data_lane1 | PROVEN unbounded (pdr) |
| P1_out_valid_data_lane2 | PROVEN unbounded (pdr) |
| P1_out_valid_data_lane3 | PROVEN unbounded (pdr) |
| P8_clear_no_fault | PROVEN unbounded (pdr) |
| P8_clear_no_valid | PROVEN unbounded (pdr) |
| P8_clear_zero_acc_a_lane0 | PROVEN unbounded (pdr) |
| P8_clear_zero_acc_a_lane1 | PROVEN unbounded (pdr) |
| P8_clear_zero_acc_a_lane2 | PROVEN unbounded (pdr) |
| P8_clear_zero_acc_a_lane3 | PROVEN unbounded (pdr) |
| P8_clear_zero_acc_b_lane0 | PROVEN unbounded (pdr) |
| P8_clear_zero_acc_b_lane1 | PROVEN unbounded (pdr) |
| P8_clear_zero_acc_b_lane2 | PROVEN unbounded (pdr) |
| P8_clear_zero_acc_b_lane3 | PROVEN unbounded (pdr) |
| P8_clear_zero_res_a_lane0 | PROVEN unbounded (pdr) |
| P8_clear_zero_res_a_lane1 | PROVEN unbounded (pdr) |
| P8_clear_zero_res_a_lane2 | PROVEN unbounded (pdr) |
| P8_clear_zero_res_a_lane3 | PROVEN unbounded (pdr) |
| P8_clear_zero_res_b_lane0 | PROVEN unbounded (pdr) |
| P8_clear_zero_res_b_lane1 | PROVEN unbounded (pdr) |
| P8_clear_zero_res_b_lane2 | PROVEN unbounded (pdr) |
| P8_clear_zero_res_b_lane3 | PROVEN unbounded (pdr) |
| P8_fresh_result_valid | PROVEN unbounded (pdr) |
| P8_fresh_sum_from_zero_lane0 | PROVEN unbounded (pdr) |
| P8_fresh_sum_from_zero_lane1 | PROVEN unbounded (pdr) |
| P8_fresh_sum_from_zero_lane2 | PROVEN unbounded (pdr) |
| P8_fresh_sum_from_zero_lane3 | PROVEN unbounded (pdr) |

</details>

<details><summary><code>datapath_pdr</code>: PASS, 31 assertions</summary>

| Assertion | Result |
|---|---|
| P1_out_fire_data_lane0 | PROVEN unbounded (pdr) |
| P1_out_fire_data_lane1 | PROVEN unbounded (pdr) |
| P1_out_fire_data_lane2 | PROVEN unbounded (pdr) |
| P1_out_fire_data_lane3 | PROVEN unbounded (pdr) |
| P1_out_valid_data_lane0 | PROVEN unbounded (pdr) |
| P1_out_valid_data_lane1 | PROVEN unbounded (pdr) |
| P1_out_valid_data_lane2 | PROVEN unbounded (pdr) |
| P1_out_valid_data_lane3 | PROVEN unbounded (pdr) |
| P8_clear_no_fault | PROVEN unbounded (pdr) |
| P8_clear_no_valid | PROVEN unbounded (pdr) |
| P8_clear_zero_acc_a_lane0 | PROVEN unbounded (pdr) |
| P8_clear_zero_acc_a_lane1 | PROVEN unbounded (pdr) |
| P8_clear_zero_acc_a_lane2 | PROVEN unbounded (pdr) |
| P8_clear_zero_acc_a_lane3 | PROVEN unbounded (pdr) |
| P8_clear_zero_acc_b_lane0 | PROVEN unbounded (pdr) |
| P8_clear_zero_acc_b_lane1 | PROVEN unbounded (pdr) |
| P8_clear_zero_acc_b_lane2 | PROVEN unbounded (pdr) |
| P8_clear_zero_acc_b_lane3 | PROVEN unbounded (pdr) |
| P8_clear_zero_res_a_lane0 | PROVEN unbounded (pdr) |
| P8_clear_zero_res_a_lane1 | PROVEN unbounded (pdr) |
| P8_clear_zero_res_a_lane2 | PROVEN unbounded (pdr) |
| P8_clear_zero_res_a_lane3 | PROVEN unbounded (pdr) |
| P8_clear_zero_res_b_lane0 | PROVEN unbounded (pdr) |
| P8_clear_zero_res_b_lane1 | PROVEN unbounded (pdr) |
| P8_clear_zero_res_b_lane2 | PROVEN unbounded (pdr) |
| P8_clear_zero_res_b_lane3 | PROVEN unbounded (pdr) |
| P8_fresh_result_valid | PROVEN unbounded (pdr) |
| P8_fresh_sum_from_zero_lane0 | PROVEN unbounded (pdr) |
| P8_fresh_sum_from_zero_lane1 | PROVEN unbounded (pdr) |
| P8_fresh_sum_from_zero_lane2 | PROVEN unbounded (pdr) |
| P8_fresh_sum_from_zero_lane3 | PROVEN unbounded (pdr) |

</details>

## Method

* **Harness and model.** `formal/orbit_demo_fv.sv` instantiates `orbit_demo` as `dut` and keeps
  an independent reference model written from docs/SPEC.md: thermal FSM (SPEC table, SPEC
  thresholds), throttle phase, predicted `in_ready` / `out_valid`, per-lane running sums,
  expected output-buffer contents, and sequence counters of accepted `in_last` beats and
  delivered results. The model follows the DUT's port handshakes like a scoreboard.
* **Environment.** Every DUT input is a free input in every cycle. The only assumption is
  reset in the first cycle (except `clear` and `wrap`, see below); `rst_n` and `clear_fault` stay free later, so the proofs also
  cover reset and clear_fault at arbitrary times.
* **DUT internals** (P7, P8 storage checks and induction helpers) are read through Yosys
  `hierconn` wires (`(* hierconn *) wire \dut.<path>`), connected by `flatten` after
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

