# Formal verification summary: orbit_demo (fault-free)

Generated 2026-09-30 00:14 UTC by `formal/summarize.py` from the SymbiYosys run directories.
RTL: `rtl`. Tools: Yosys 0.69+154 (git sha1 30d62572e-dirty, Release, Clang /usr/bin/clang++ 21.1.8); SBY v0.69; Yices 2.7.0; bitwuzla 0.9.1.

Harness: `formal/orbit_demo_fv.sv` (independent reference model from docs/SPEC.md, all DUT
inputs free, reset only in the first cycle; reset and clear_fault stay free afterwards;
the `clear` task starts from an unconstrained state and `wrap` from a consistent one).
Jobs: `formal/orbit_demo.sby`, one task per property group.

## Per-property status

| Property | Meaning | Status | Evidence (task: assertions, method, solver, time) |
|---|---|---|---|
| P1 | on every out_fire, out_data equals the reference result for every lane (exact, INT32 wraparound) | PROVEN unbounded | `datapath`: PASS, 8 assertions + 8 helpers, k-induction, k = 6, smtbmc/yices, 3s<br>`product`: PASS, 1 assertion, k-induction, k = 1, smtbmc/bitwuzla, 6s<br>`datapath_pdr`: PASS, 8 assertions, no helper invariants, PDR (unbounded), abc/pdr, 837s |
| P2 | every accepted in_last produces exactly one out_fire, in order (no loss, no duplication) | PROVEN unbounded | `handshake`: PASS, 5 assertions + 1 helper, k-induction, k = 8, smtbmc/yices, 0s<br>`handshake_pdr`: PASS, 5 assertions, no helper invariants, PDR (unbounded), abc/pdr, 7s<br>`live`: PASS, 1 assertion, liveness (unbounded), fair consumer, aiger/suprove, 25s |
| P3 | out_valid && !out_ready: out_valid stays high and out_data is unchanged next cycle | PROVEN unbounded | `handshake`: PASS, 2 assertions, k-induction, k = 8, smtbmc/yices, 0s<br>`handshake_pdr`: PASS, 2 assertions, no helper invariants, PDR (unbounded), abc/pdr, 7s |
| P4 | in_ready low when thermal STOP/3, fault, clear_fault, or buffer full && !out_ready | PROVEN unbounded | `handshake`: PASS, 6 assertions, k-induction, k = 8, smtbmc/yices, 0s<br>`handshake_pdr`: PASS, 6 assertions, no helper invariants, PDR (unbounded), abc/pdr, 7s |
| P5 | voted thermal state follows the SPEC table (independent FSM); reset gives STOP | PROVEN unbounded | `thermal`: PASS, 6 assertions + 4 helpers, k-induction, k = 8, smtbmc/yices, 0s<br>`handshake`: PASS, 6 assertions + 4 helpers, k-induction, k = 8, smtbmc/yices, 0s<br>`clear`: PASS, 2 assertions, k-induction, k = 3, unconstrained start state (no reset), smtbmc/yices, 0s<br>`thermal_pdr`: PASS, 6 assertions, no helper invariants, PDR (unbounded), abc/pdr, 2s |
| P6 | throttle: first THROTTLE cycle admits, consecutive THROTTLE cycles alternate | PROVEN unbounded | `thermal`: PASS, 5 assertions, k-induction, k = 8, smtbmc/yices, 0s<br>`handshake`: PASS, 5 assertions, k-induction, k = 8, smtbmc/yices, 0s<br>`thermal_pdr`: PASS, 5 assertions, no helper invariants, PDR (unbounded), abc/pdr, 2s |
| P7 | fault-free: fault and therm_repair never rise, duplicated / triplicated copies equal | PROVEN unbounded | `dup`: PASS, 12 assertions, k-induction, k = 6, smtbmc/yices, 0s<br>`handshake`: PASS, 12 assertions, k-induction, k = 8, smtbmc/yices, 0s<br>`datapath`: PASS, 12 assertions, k-induction, k = 6, smtbmc/yices, 3s<br>`dup_pdr`: PASS, 12 assertions, PDR (unbounded), abc/pdr, 2s |
| P8 | clear_fault: then fault = 0, out_valid = 0, storage zero, next beat sums from 0 (also from a latched fault) | PROVEN unbounded | `datapath`: PASS, 23 assertions + 8 helpers, k-induction, k = 6, smtbmc/yices, 3s<br>`clear`: PASS, 6 assertions, k-induction, k = 3, unconstrained start state (no reset), smtbmc/yices, 0s<br>`datapath_pdr`: PASS, 23 assertions, no helper invariants, PDR (unbounded), abc/pdr, 837s |

## Jobs

| Task | Groups | Mode / method | Engine / solver | Status | Wall time (s) | Assertions | Covers |
|---|---|---|---|---|---|---|---|
| thermal | thermal | k-induction, k = 8 | smtbmc/yices | PASS | 0 | 15 | 0 |
| dup | dup | k-induction, k = 6 | smtbmc/yices | PASS | 0 | 12 | 0 |
| handshake | handshake thermal dup | k-induction, k = 8 | smtbmc/yices | PASS | 0 | 41 | 0 |
| datapath | datapath dup | k-induction, k = 6 | smtbmc/yices | PASS | 3 | 59 | 0 |
| clear | clear | k-induction, k = 3, unconstrained start state (no reset) | smtbmc/yices | PASS | 0 | 8 | 0 |
| product | product | k-induction, k = 1 | smtbmc/bitwuzla | PASS | 6 | 1 | 0 |
| thermal_pdr | thermal (no helpers) | PDR (unbounded) | abc/pdr | PASS | 2 | 11 | 0 |
| dup_pdr | dup | PDR (unbounded) | abc/pdr | PASS | 2 | 12 | 0 |
| handshake_pdr | handshake (no helpers) | PDR (unbounded) | abc/pdr | PASS | 7 | 13 | 0 |
| live | live | liveness (unbounded), fair consumer | aiger/suprove | PASS | 25 | 1 | 0 |
| cover | cover | cover, depth 24 | smtbmc/yices | PASS | 1 | 0 | 14 |
| wrap | free_start wrap datapath handshake thermal dup | cover, depth 8, consistent arbitrary start state, assertions checked on the traces | smtbmc/yices | PASS | 0 | 88 | 3 |
| datapath_pdr | datapath (no helpers) | PDR (unbounded) | abc/pdr | PASS | 837 | 31 | 0 |

## Covers

| Cover | Task | Result |
|---|---|---|
| C01_out_fire | cover | COVER reached at step 4 |
| C02_back_to_back_fire | cover | COVER reached at step 5 |
| C03_throttle_entered | cover | COVER reached at step 4 |
| C04_stop_by_temperature | cover | COVER reached at step 4 |
| C05_stop_by_invalid | cover | COVER reached at step 4 |
| C06_recover_from_stop | cover | COVER reached at step 3 |
| C07_recover_from_throttle | cover | COVER reached at step 5 |
| C08_clear_then_result | cover | COVER reached at step 6 |
| C09_throttle_blocks | cover | COVER reached at step 5 |
| C10_backpressure_then_fire | cover | COVER reached at step 6 |
| C11_replace_no_bubble | cover | COVER reached at step 4 |
| C12_edge_min_min | cover | COVER reached at step 4 |
| C13_edge_max_min | cover | COVER reached at step 4 |
| C14_throttle_admit_run | cover | COVER reached at step 6 |
| C20_wrap_pos_to_neg | wrap | COVER reached at step 2 |
| C21_wrap_neg_to_pos | wrap | COVER reached at step 2 |
| C22_wrap_all_lanes | wrap | COVER reached at step 2 |

Steps are sby step numbers; step 0 is the reset cycle. The covers are sampled at the
clock edge, so a condition that holds in cycle N is reported at step N + 1. The `wrap`
covers start from an arbitrary state in which DUT and model agree (see Method).

## Assertions by task

<details><summary><code>thermal</code>: PASS, 15 assertions</summary>

| Assertion | Result |
|---|---|
| P5_h_copy0 | PROVEN unbounded (k-induction k=8) |
| P5_h_copy1 | PROVEN unbounded (k-induction k=8) |
| P5_h_copy2 | PROVEN unbounded (k-induction k=8) |
| P5_h_phase | PROVEN unbounded (k-induction k=8) |
| P5_never_code3 | PROVEN unbounded (k-induction k=8) |
| P5_next_state | PROVEN unbounded (k-induction k=8) |
| P5_reset_phase | PROVEN unbounded (k-induction k=8) |
| P5_reset_stop | PROVEN unbounded (k-induction k=8) |
| P5_shutdown_req | PROVEN unbounded (k-induction k=8) |
| P5_state_matches_model | PROVEN unbounded (k-induction k=8) |
| P6_first_throttle_admits | PROVEN unbounded (k-induction k=8) |
| P6_normal_admits | PROVEN unbounded (k-induction k=8) |
| P6_port_throttle | PROVEN unbounded (k-induction k=8) |
| P6_stop_blocks | PROVEN unbounded (k-induction k=8) |
| P6_throttle_alternates | PROVEN unbounded (k-induction k=8) |

</details>

<details><summary><code>dup</code>: PASS, 12 assertions</summary>

| Assertion | Result |
|---|---|
| P7_acc_copies_equal_lane0 | PROVEN unbounded (k-induction k=6) |
| P7_acc_copies_equal_lane1 | PROVEN unbounded (k-induction k=6) |
| P7_acc_copies_equal_lane2 | PROVEN unbounded (k-induction k=6) |
| P7_acc_copies_equal_lane3 | PROVEN unbounded (k-induction k=6) |
| P7_no_fault | PROVEN unbounded (k-induction k=6) |
| P7_no_mismatch | PROVEN unbounded (k-induction k=6) |
| P7_no_therm_repair | PROVEN unbounded (k-induction k=6) |
| P7_res_copies_equal_lane0 | PROVEN unbounded (k-induction k=6) |
| P7_res_copies_equal_lane1 | PROVEN unbounded (k-induction k=6) |
| P7_res_copies_equal_lane2 | PROVEN unbounded (k-induction k=6) |
| P7_res_copies_equal_lane3 | PROVEN unbounded (k-induction k=6) |
| P7_therm_copies_equal | PROVEN unbounded (k-induction k=6) |

</details>

<details><summary><code>handshake</code>: PASS, 41 assertions</summary>

| Assertion | Result |
|---|---|
| P2_at_most_one_pending | PROVEN unbounded (k-induction k=8) |
| P2_fire_has_pending | PROVEN unbounded (k-induction k=8) |
| P2_h_out_valid_q | PROVEN unbounded (k-induction k=8) |
| P2_no_overwrite | PROVEN unbounded (k-induction k=8) |
| P2_out_valid_matches_model | PROVEN unbounded (k-induction k=8) |
| P2_valid_iff_pending | PROVEN unbounded (k-induction k=8) |
| P3_data_stable | PROVEN unbounded (k-induction k=8) |
| P3_valid_held | PROVEN unbounded (k-induction k=8) |
| P4_blocked_buffer_full | PROVEN unbounded (k-induction k=8) |
| P4_blocked_clear_fault | PROVEN unbounded (k-induction k=8) |
| P4_blocked_fault | PROVEN unbounded (k-induction k=8) |
| P4_blocked_out_valid | PROVEN unbounded (k-induction k=8) |
| P4_blocked_stop_or_3 | PROVEN unbounded (k-induction k=8) |
| P4_in_ready_matches_model | PROVEN unbounded (k-induction k=8) |
| P5_h_copy0 | PROVEN unbounded (k-induction k=8) |
| P5_h_copy1 | PROVEN unbounded (k-induction k=8) |
| P5_h_copy2 | PROVEN unbounded (k-induction k=8) |
| P5_h_phase | PROVEN unbounded (k-induction k=8) |
| P5_never_code3 | PROVEN unbounded (k-induction k=8) |
| P5_next_state | PROVEN unbounded (k-induction k=8) |
| P5_reset_phase | PROVEN unbounded (k-induction k=8) |
| P5_reset_stop | PROVEN unbounded (k-induction k=8) |
| P5_shutdown_req | PROVEN unbounded (k-induction k=8) |
| P5_state_matches_model | PROVEN unbounded (k-induction k=8) |
| P6_first_throttle_admits | PROVEN unbounded (k-induction k=8) |
| P6_normal_admits | PROVEN unbounded (k-induction k=8) |
| P6_port_throttle | PROVEN unbounded (k-induction k=8) |
| P6_stop_blocks | PROVEN unbounded (k-induction k=8) |
| P6_throttle_alternates | PROVEN unbounded (k-induction k=8) |
| P7_acc_copies_equal_lane0 | PROVEN unbounded (k-induction k=8) |
| P7_acc_copies_equal_lane1 | PROVEN unbounded (k-induction k=8) |
| P7_acc_copies_equal_lane2 | PROVEN unbounded (k-induction k=8) |
| P7_acc_copies_equal_lane3 | PROVEN unbounded (k-induction k=8) |
| P7_no_fault | PROVEN unbounded (k-induction k=8) |
| P7_no_mismatch | PROVEN unbounded (k-induction k=8) |
| P7_no_therm_repair | PROVEN unbounded (k-induction k=8) |
| P7_res_copies_equal_lane0 | PROVEN unbounded (k-induction k=8) |
| P7_res_copies_equal_lane1 | PROVEN unbounded (k-induction k=8) |
| P7_res_copies_equal_lane2 | PROVEN unbounded (k-induction k=8) |
| P7_res_copies_equal_lane3 | PROVEN unbounded (k-induction k=8) |
| P7_therm_copies_equal | PROVEN unbounded (k-induction k=8) |

</details>

<details><summary><code>datapath</code>: PASS, 59 assertions</summary>

| Assertion | Result |
|---|---|
| P1_h_acc_a_lane0 | PROVEN unbounded (k-induction k=6) |
| P1_h_acc_a_lane1 | PROVEN unbounded (k-induction k=6) |
| P1_h_acc_a_lane2 | PROVEN unbounded (k-induction k=6) |
| P1_h_acc_a_lane3 | PROVEN unbounded (k-induction k=6) |
| P1_h_res_a_lane0 | PROVEN unbounded (k-induction k=6) |
| P1_h_res_a_lane1 | PROVEN unbounded (k-induction k=6) |
| P1_h_res_a_lane2 | PROVEN unbounded (k-induction k=6) |
| P1_h_res_a_lane3 | PROVEN unbounded (k-induction k=6) |
| P1_out_fire_data_lane0 | PROVEN unbounded (k-induction k=6) |
| P1_out_fire_data_lane1 | PROVEN unbounded (k-induction k=6) |
| P1_out_fire_data_lane2 | PROVEN unbounded (k-induction k=6) |
| P1_out_fire_data_lane3 | PROVEN unbounded (k-induction k=6) |
| P1_out_valid_data_lane0 | PROVEN unbounded (k-induction k=6) |
| P1_out_valid_data_lane1 | PROVEN unbounded (k-induction k=6) |
| P1_out_valid_data_lane2 | PROVEN unbounded (k-induction k=6) |
| P1_out_valid_data_lane3 | PROVEN unbounded (k-induction k=6) |
| P7_acc_copies_equal_lane0 | PROVEN unbounded (k-induction k=6) |
| P7_acc_copies_equal_lane1 | PROVEN unbounded (k-induction k=6) |
| P7_acc_copies_equal_lane2 | PROVEN unbounded (k-induction k=6) |
| P7_acc_copies_equal_lane3 | PROVEN unbounded (k-induction k=6) |
| P7_no_fault | PROVEN unbounded (k-induction k=6) |
| P7_no_mismatch | PROVEN unbounded (k-induction k=6) |
| P7_no_therm_repair | PROVEN unbounded (k-induction k=6) |
| P7_res_copies_equal_lane0 | PROVEN unbounded (k-induction k=6) |
| P7_res_copies_equal_lane1 | PROVEN unbounded (k-induction k=6) |
| P7_res_copies_equal_lane2 | PROVEN unbounded (k-induction k=6) |
| P7_res_copies_equal_lane3 | PROVEN unbounded (k-induction k=6) |
| P7_therm_copies_equal | PROVEN unbounded (k-induction k=6) |
| P8_clear_no_fault | PROVEN unbounded (k-induction k=6) |
| P8_clear_no_valid | PROVEN unbounded (k-induction k=6) |
| P8_clear_zero_acc_a_lane0 | PROVEN unbounded (k-induction k=6) |
| P8_clear_zero_acc_a_lane1 | PROVEN unbounded (k-induction k=6) |
| P8_clear_zero_acc_a_lane2 | PROVEN unbounded (k-induction k=6) |
| P8_clear_zero_acc_a_lane3 | PROVEN unbounded (k-induction k=6) |
| P8_clear_zero_acc_b_lane0 | PROVEN unbounded (k-induction k=6) |
| P8_clear_zero_acc_b_lane1 | PROVEN unbounded (k-induction k=6) |
| P8_clear_zero_acc_b_lane2 | PROVEN unbounded (k-induction k=6) |
| P8_clear_zero_acc_b_lane3 | PROVEN unbounded (k-induction k=6) |
| P8_clear_zero_res_a_lane0 | PROVEN unbounded (k-induction k=6) |
| P8_clear_zero_res_a_lane1 | PROVEN unbounded (k-induction k=6) |
| P8_clear_zero_res_a_lane2 | PROVEN unbounded (k-induction k=6) |
| P8_clear_zero_res_a_lane3 | PROVEN unbounded (k-induction k=6) |
| P8_clear_zero_res_b_lane0 | PROVEN unbounded (k-induction k=6) |
| P8_clear_zero_res_b_lane1 | PROVEN unbounded (k-induction k=6) |
| P8_clear_zero_res_b_lane2 | PROVEN unbounded (k-induction k=6) |
| P8_clear_zero_res_b_lane3 | PROVEN unbounded (k-induction k=6) |
| P8_fresh_result_valid | PROVEN unbounded (k-induction k=6) |
| P8_fresh_sum_from_zero_lane0 | PROVEN unbounded (k-induction k=6) |
| P8_fresh_sum_from_zero_lane1 | PROVEN unbounded (k-induction k=6) |
| P8_fresh_sum_from_zero_lane2 | PROVEN unbounded (k-induction k=6) |
| P8_fresh_sum_from_zero_lane3 | PROVEN unbounded (k-induction k=6) |
| P8_h_fresh_acc_a_lane0 | PROVEN unbounded (k-induction k=6) |
| P8_h_fresh_acc_a_lane1 | PROVEN unbounded (k-induction k=6) |
| P8_h_fresh_acc_a_lane2 | PROVEN unbounded (k-induction k=6) |
| P8_h_fresh_acc_a_lane3 | PROVEN unbounded (k-induction k=6) |
| P8_h_fresh_acc_b_lane0 | PROVEN unbounded (k-induction k=6) |
| P8_h_fresh_acc_b_lane1 | PROVEN unbounded (k-induction k=6) |
| P8_h_fresh_acc_b_lane2 | PROVEN unbounded (k-induction k=6) |
| P8_h_fresh_acc_b_lane3 | PROVEN unbounded (k-induction k=6) |

</details>

<details><summary><code>clear</code>: PASS, 8 assertions</summary>

| Assertion | Result |
|---|---|
| P5_any_copies_next | PROVEN unbounded (k-induction k=3) |
| P5_any_reset_stop | PROVEN unbounded (k-induction k=3) |
| P8_any_fresh_acc | PROVEN unbounded (k-induction k=3) |
| P8_any_fresh_res | PROVEN unbounded (k-induction k=3) |
| P8_any_no_fault | PROVEN unbounded (k-induction k=3) |
| P8_any_no_valid | PROVEN unbounded (k-induction k=3) |
| P8_any_storage_zero | PROVEN unbounded (k-induction k=3) |
| P8_any_valid_q_zero | PROVEN unbounded (k-induction k=3) |

</details>

<details><summary><code>product</code>: PASS, 1 assertions</summary>

| Assertion | Result |
|---|---|
| P1_product_formula | PROVEN unbounded (k-induction k=1) |

</details>

<details><summary><code>thermal_pdr</code>: PASS, 11 assertions</summary>

| Assertion | Result |
|---|---|
| P5_never_code3 | PROVEN unbounded (pdr) |
| P5_next_state | PROVEN unbounded (pdr) |
| P5_reset_phase | PROVEN unbounded (pdr) |
| P5_reset_stop | PROVEN unbounded (pdr) |
| P5_shutdown_req | PROVEN unbounded (pdr) |
| P5_state_matches_model | PROVEN unbounded (pdr) |
| P6_first_throttle_admits | PROVEN unbounded (pdr) |
| P6_normal_admits | PROVEN unbounded (pdr) |
| P6_port_throttle | PROVEN unbounded (pdr) |
| P6_stop_blocks | PROVEN unbounded (pdr) |
| P6_throttle_alternates | PROVEN unbounded (pdr) |

</details>

<details><summary><code>dup_pdr</code>: PASS, 12 assertions</summary>

| Assertion | Result |
|---|---|
| P7_acc_copies_equal_lane0 | PROVEN unbounded (pdr) |
| P7_acc_copies_equal_lane1 | PROVEN unbounded (pdr) |
| P7_acc_copies_equal_lane2 | PROVEN unbounded (pdr) |
| P7_acc_copies_equal_lane3 | PROVEN unbounded (pdr) |
| P7_no_fault | PROVEN unbounded (pdr) |
| P7_no_mismatch | PROVEN unbounded (pdr) |
| P7_no_therm_repair | PROVEN unbounded (pdr) |
| P7_res_copies_equal_lane0 | PROVEN unbounded (pdr) |
| P7_res_copies_equal_lane1 | PROVEN unbounded (pdr) |
| P7_res_copies_equal_lane2 | PROVEN unbounded (pdr) |
| P7_res_copies_equal_lane3 | PROVEN unbounded (pdr) |
| P7_therm_copies_equal | PROVEN unbounded (pdr) |

</details>

<details><summary><code>handshake_pdr</code>: PASS, 13 assertions</summary>

| Assertion | Result |
|---|---|
| P2_at_most_one_pending | PROVEN unbounded (pdr) |
| P2_fire_has_pending | PROVEN unbounded (pdr) |
| P2_no_overwrite | PROVEN unbounded (pdr) |
| P2_out_valid_matches_model | PROVEN unbounded (pdr) |
| P2_valid_iff_pending | PROVEN unbounded (pdr) |
| P3_data_stable | PROVEN unbounded (pdr) |
| P3_valid_held | PROVEN unbounded (pdr) |
| P4_blocked_buffer_full | PROVEN unbounded (pdr) |
| P4_blocked_clear_fault | PROVEN unbounded (pdr) |
| P4_blocked_fault | PROVEN unbounded (pdr) |
| P4_blocked_out_valid | PROVEN unbounded (pdr) |
| P4_blocked_stop_or_3 | PROVEN unbounded (pdr) |
| P4_in_ready_matches_model | PROVEN unbounded (pdr) |

</details>

<details><summary><code>live</code>: PASS, 1 assertions</summary>

| Assertion | Result |
|---|---|
| P2_live_delivered | PROVEN unbounded (liveness, aiger/suprove) |

</details>

<details><summary><code>wrap</code>: PASS, 88 assertions</summary>

| Assertion | Result |
|---|---|
| P1_h_acc_a_lane0 | UNKNOWN |
| P1_h_acc_a_lane1 | UNKNOWN |
| P1_h_acc_a_lane2 | UNKNOWN |
| P1_h_acc_a_lane3 | UNKNOWN |
| P1_h_res_a_lane0 | UNKNOWN |
| P1_h_res_a_lane1 | UNKNOWN |
| P1_h_res_a_lane2 | UNKNOWN |
| P1_h_res_a_lane3 | UNKNOWN |
| P1_out_fire_data_lane0 | UNKNOWN |
| P1_out_fire_data_lane1 | UNKNOWN |
| P1_out_fire_data_lane2 | UNKNOWN |
| P1_out_fire_data_lane3 | UNKNOWN |
| P1_out_valid_data_lane0 | UNKNOWN |
| P1_out_valid_data_lane1 | UNKNOWN |
| P1_out_valid_data_lane2 | UNKNOWN |
| P1_out_valid_data_lane3 | UNKNOWN |
| P2_at_most_one_pending | UNKNOWN |
| P2_fire_has_pending | UNKNOWN |
| P2_h_out_valid_q | UNKNOWN |
| P2_no_overwrite | UNKNOWN |
| P2_out_valid_matches_model | UNKNOWN |
| P2_valid_iff_pending | UNKNOWN |
| P3_data_stable | UNKNOWN |
| P3_valid_held | UNKNOWN |
| P4_blocked_buffer_full | UNKNOWN |
| P4_blocked_clear_fault | UNKNOWN |
| P4_blocked_fault | UNKNOWN |
| P4_blocked_out_valid | UNKNOWN |
| P4_blocked_stop_or_3 | UNKNOWN |
| P4_in_ready_matches_model | UNKNOWN |
| P5_h_copy0 | UNKNOWN |
| P5_h_copy1 | UNKNOWN |
| P5_h_copy2 | UNKNOWN |
| P5_h_phase | UNKNOWN |
| P5_never_code3 | UNKNOWN |
| P5_next_state | UNKNOWN |
| P5_reset_phase | UNKNOWN |
| P5_reset_stop | UNKNOWN |
| P5_shutdown_req | UNKNOWN |
| P5_state_matches_model | UNKNOWN |
| P6_first_throttle_admits | UNKNOWN |
| P6_normal_admits | UNKNOWN |
| P6_port_throttle | UNKNOWN |
| P6_stop_blocks | UNKNOWN |
| P6_throttle_alternates | UNKNOWN |
| P7_acc_copies_equal_lane0 | UNKNOWN |
| P7_acc_copies_equal_lane1 | UNKNOWN |
| P7_acc_copies_equal_lane2 | UNKNOWN |
| P7_acc_copies_equal_lane3 | UNKNOWN |
| P7_no_fault | UNKNOWN |
| P7_no_mismatch | UNKNOWN |
| P7_no_therm_repair | UNKNOWN |
| P7_res_copies_equal_lane0 | UNKNOWN |
| P7_res_copies_equal_lane1 | UNKNOWN |
| P7_res_copies_equal_lane2 | UNKNOWN |
| P7_res_copies_equal_lane3 | UNKNOWN |
| P7_therm_copies_equal | UNKNOWN |
| P8_clear_no_fault | UNKNOWN |
| P8_clear_no_valid | UNKNOWN |
| P8_clear_zero_acc_a_lane0 | UNKNOWN |
| P8_clear_zero_acc_a_lane1 | UNKNOWN |
| P8_clear_zero_acc_a_lane2 | UNKNOWN |
| P8_clear_zero_acc_a_lane3 | UNKNOWN |
| P8_clear_zero_acc_b_lane0 | UNKNOWN |
| P8_clear_zero_acc_b_lane1 | UNKNOWN |
| P8_clear_zero_acc_b_lane2 | UNKNOWN |
| P8_clear_zero_acc_b_lane3 | UNKNOWN |
| P8_clear_zero_res_a_lane0 | UNKNOWN |
| P8_clear_zero_res_a_lane1 | UNKNOWN |
| P8_clear_zero_res_a_lane2 | UNKNOWN |
| P8_clear_zero_res_a_lane3 | UNKNOWN |
| P8_clear_zero_res_b_lane0 | UNKNOWN |
| P8_clear_zero_res_b_lane1 | UNKNOWN |
| P8_clear_zero_res_b_lane2 | UNKNOWN |
| P8_clear_zero_res_b_lane3 | UNKNOWN |
| P8_fresh_result_valid | UNKNOWN |
| P8_fresh_sum_from_zero_lane0 | UNKNOWN |
| P8_fresh_sum_from_zero_lane1 | UNKNOWN |
| P8_fresh_sum_from_zero_lane2 | UNKNOWN |
| P8_fresh_sum_from_zero_lane3 | UNKNOWN |
| P8_h_fresh_acc_a_lane0 | UNKNOWN |
| P8_h_fresh_acc_a_lane1 | UNKNOWN |
| P8_h_fresh_acc_a_lane2 | UNKNOWN |
| P8_h_fresh_acc_a_lane3 | UNKNOWN |
| P8_h_fresh_acc_b_lane0 | UNKNOWN |
| P8_h_fresh_acc_b_lane1 | UNKNOWN |
| P8_h_fresh_acc_b_lane2 | UNKNOWN |
| P8_h_fresh_acc_b_lane3 | UNKNOWN |

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

## Vacuity: the proofs fail on broken RTL

`make formal-vacuity` edits a generated copy of the RTL (never `rtl/`) and reruns the
task that should catch the bug. CAUGHT = sby status FAIL with a counterexample from the
initial state (reset asserted in step 0) on a property with the expected prefix (see
`vacuity.md`). Step 0 failures are P4 assertions, which hold in every state including
the unconstrained first cycle. Names with `_h_` are helper invariants, which are proof
obligations too; the `*_pdr` rows have no helpers, so they show the port-level
properties themselves failing.

| Mutant | Bug | Task | Result | Failed properties | Step | Time (s) |
|---|---|---|---|---|---|---|
| zext_product | product zero-extended instead of sign-extended | datapath | CAUGHT (FAIL) | P1_h_acc_a_lane0 P1_h_acc_a_lane1 P1_h_acc_a_lane2 P1_h_acc_a_lane3 | 3 | 1 |
| first_ignored | in_first ignored: every beat continues the sum (both copies) | datapath | CAUGHT (FAIL) | P1_h_acc_a_lane0 P1_h_res_a_lane0 P1_out_valid_data_lane0 | 4 | 1 |
| result_from_old_acc | result registers load the pre-beat sum (both copies) | datapath | CAUGHT (FAIL) | P1_h_res_a_lane1 P1_h_res_a_lane2 P1_out_valid_data_lane1 P1_out_valid_data_lane2 | 3 | 0 |
| clear_keeps_acc | clear_fault does not zero the accumulators (both copies) | datapath | CAUGHT (FAIL) | P1_h_acc_a_lane2 P8_h_fresh_acc_a_lane2 P8_h_fresh_acc_b_lane2 | 4 | 2 |
| clear_keeps_fault | clear_fault does not clear a latched fault | clear | CAUGHT (FAIL) | P8_any_no_fault | 2 | 1 |
| no_backpressure | in_ready ignores a full output buffer | handshake | CAUGHT (FAIL) | P4_blocked_buffer_full P4_blocked_out_valid | 0 | 0 |
| out_valid_never_cleared | out_valid_q not cleared by out_fire (duplicate delivery) | handshake | CAUGHT (FAIL) | P2_h_out_valid_q P2_out_valid_matches_model P2_valid_iff_pending | 4 | 1 |
| out_valid_never_set | out_valid_q never set: accepted results are never presented | live | CAUGHT (FAIL) | P2_live_delivered | - | 2 |
| stop_threshold_gt | STOP at t > 95 instead of t >= 95 | thermal | CAUGHT (FAIL) | P5_h_copy0 P5_h_copy1 P5_h_copy2 P5_state_matches_model | 3 | 1 |
| recover_threshold_lt | THROTTLE recovers at t < 70 instead of t <= 70 | thermal | CAUGHT (FAIL) | P5_h_copy0 P5_h_copy1 P5_h_copy2 P5_state_matches_model | 4 | 0 |
| throttle_every_cycle | THROTTLE admits every cycle | thermal | CAUGHT (FAIL) | P6_throttle_alternates | 5 | 1 |
| phase_not_reset | phase keeps its value outside THROTTLE | thermal | CAUGHT (FAIL) | P5_h_phase | 5 | 1 |
| acc_b_clear_value | clear_fault writes 1 into accumulator copy B | dup | CAUGHT (FAIL) | P7_acc_copies_equal_lane0 P7_acc_copies_equal_lane1 P7_acc_copies_equal_lane2 P7_acc_copies_equal_lane3 P7_no_mismatch | 2 | 1 |
| therm_copy2_frozen | thermal copy 2 is never rewritten after reset | dup | CAUGHT (FAIL) | P7_no_therm_repair P7_therm_copies_equal | 2 | 1 |
| zext_product_pdr | product zero-extended (abc pdr, no helpers) | datapath_pdr | CAUGHT (FAIL) | P1_out_valid_data_lane1 P8_fresh_sum_from_zero_lane1 | 4 | 16 |
| clear_keeps_acc_pdr | clear_fault does not zero the accumulators (abc pdr, no helpers) | datapath_pdr | CAUGHT (FAIL) | P8_clear_zero_acc_a_lane0 P8_clear_zero_acc_b_lane0 | 5 | 5 |
| throttle_every_cycle_pdr | THROTTLE admits every cycle (abc pdr, no helpers) | thermal_pdr | CAUGHT (FAIL) | P6_port_throttle P6_throttle_alternates | 5 | 2 |
| no_backpressure_pdr | in_ready ignores a full output buffer (abc pdr, no helpers) | handshake_pdr | CAUGHT (FAIL) | P4_blocked_buffer_full P4_blocked_out_valid | 0 | 1 |
| phase_not_reset_pdr | phase keeps its value outside THROTTLE (abc pdr, no helpers) | thermal_pdr | CAUGHT (FAIL) | P6_first_throttle_admits P6_port_throttle | 6 | 2 |

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

