# Formal vacuity check: proofs against deliberately broken RTL

Each mutant is one sed edit of a generated copy of the RTL (never rtl/
itself). CAUGHT = the named SymbiYosys task ended with status FAIL and a
counterexample from the initial state (reset asserted in step 0) violated a
property with the expected prefix. Step 0 failures are properties that are
asserted in every state, including the unconstrained first cycle (P4).

| Mutant | File | Task | Expect | Result | sby status | Failed properties | First step | Time (s) | Bug |
|---|---|---|---|---|---|---|---|---|---|
| zext_product | orbit_mac_lane.v | datapath | P1_* | CAUGHT | FAIL | P1_h_acc_a_lane0 P1_h_acc_a_lane1 P1_h_acc_a_lane2 P1_h_acc_a_lane3 | 3 | 1 | product zero-extended instead of sign-extended |
| first_ignored | orbit_mac_lane.v | datapath | P1_* | CAUGHT | FAIL | P1_h_acc_a_lane0 P1_h_res_a_lane0 P1_out_valid_data_lane0 | 4 | 1 | in_first ignored: every beat continues the sum (both copies) |
| result_from_old_acc | orbit_mac_lane.v | datapath | P1_* | CAUGHT | FAIL | P1_h_res_a_lane1 P1_h_res_a_lane2 P1_out_valid_data_lane1 P1_out_valid_data_lane2 | 3 | 0 | result registers load the pre-beat sum (both copies) |
| clear_keeps_acc | orbit_mac_lane.v | datapath | P8_* | CAUGHT | FAIL | P1_h_acc_a_lane2 P8_h_fresh_acc_a_lane2 P8_h_fresh_acc_b_lane2 | 4 | 2 | clear_fault does not zero the accumulators (both copies) |
| clear_keeps_fault | orbit_demo.v | clear | P8_any_no_fault* | CAUGHT | FAIL | P8_any_no_fault | 2 | 1 | clear_fault does not clear a latched fault |
| no_backpressure | orbit_demo.v | handshake | P4_* | CAUGHT | FAIL | P4_blocked_buffer_full P4_blocked_out_valid | 0 | 0 | in_ready ignores a full output buffer |
| out_valid_never_cleared | orbit_demo.v | handshake | P2_* | CAUGHT | FAIL | P2_h_out_valid_q P2_out_valid_matches_model P2_valid_iff_pending | 4 | 1 | out_valid_q not cleared by out_fire (duplicate delivery) |
| out_valid_never_set | orbit_demo.v | live | P2_* | CAUGHT | FAIL | P2_live_delivered | - | 2 | out_valid_q never set: accepted results are never presented |
| stop_threshold_gt | orbit_thermal_tmr.v | thermal | P5_* | CAUGHT | FAIL | P5_h_copy0 P5_h_copy1 P5_h_copy2 P5_state_matches_model | 3 | 1 | STOP at t > 95 instead of t >= 95 |
| recover_threshold_lt | orbit_thermal_tmr.v | thermal | P5_* | CAUGHT | FAIL | P5_h_copy0 P5_h_copy1 P5_h_copy2 P5_state_matches_model | 4 | 0 | THROTTLE recovers at t < 70 instead of t <= 70 |
| throttle_every_cycle | orbit_thermal_tmr.v | thermal | P6_* | CAUGHT | FAIL | P6_throttle_alternates | 5 | 1 | THROTTLE admits every cycle |
| phase_not_reset | orbit_thermal_tmr.v | thermal | P5_h_phase* | CAUGHT | FAIL | P5_h_phase | 5 | 1 | phase keeps its value outside THROTTLE |
| acc_b_clear_value | orbit_mac_lane.v | dup | P7_* | CAUGHT | FAIL | P7_acc_copies_equal_lane0 P7_acc_copies_equal_lane1 P7_acc_copies_equal_lane2 P7_acc_copies_equal_lane3 P7_no_mismatch | 2 | 1 | clear_fault writes 1 into accumulator copy B |
| therm_copy2_frozen | orbit_thermal_tmr.v | dup | P7_* | CAUGHT | FAIL | P7_no_therm_repair P7_therm_copies_equal | 2 | 1 | thermal copy 2 is never rewritten after reset |
| zext_product_pdr | orbit_mac_lane.v | datapath_pdr | P1_* or P8_fresh* | CAUGHT | FAIL | P1_out_valid_data_lane1 P8_fresh_sum_from_zero_lane1 | 4 | 16 | product zero-extended (abc pdr, no helpers) |
| clear_keeps_acc_pdr | orbit_mac_lane.v | datapath_pdr | P8_* or P1_* | CAUGHT | FAIL | P8_clear_zero_acc_a_lane0 P8_clear_zero_acc_b_lane0 | 5 | 5 | clear_fault does not zero the accumulators (abc pdr, no helpers) |
| throttle_every_cycle_pdr | orbit_thermal_tmr.v | thermal_pdr | P6_* | CAUGHT | FAIL | P6_port_throttle P6_throttle_alternates | 5 | 2 | THROTTLE admits every cycle (abc pdr, no helpers) |
| no_backpressure_pdr | orbit_demo.v | handshake_pdr | P4_* or P2_* | CAUGHT | FAIL | P4_blocked_buffer_full P4_blocked_out_valid | 0 | 1 | in_ready ignores a full output buffer (abc pdr, no helpers) |
| phase_not_reset_pdr | orbit_thermal_tmr.v | thermal_pdr | P6_* | CAUGHT | FAIL | P6_first_throttle_admits P6_port_throttle | 6 | 2 | phase keeps its value outside THROTTLE (abc pdr, no helpers) |
