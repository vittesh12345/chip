# cocotb random test of orbit_demo

cocotb 2.1.0.dev0+41564633, simulator verilator, Python 3.11.6 (/opt/eda/oss-cad-suite/bin/tabbypy3)

| test | seed | cycles | results checked | errors | missing coverage | wall s | result |
|---|---|---|---|---|---|---|---|
| random_workload | 1 | 20000 | 866 | 0 | - | 1.7 | PASS |
| random_workload | 2 | 20000 | 978 | 0 | - | 1.5 | PASS |

Functional coverage (event counts; * = required > 0 in the test that lists it)

| event | random:1 | random:2 | total |
|---|---|---|---|
| back_to_back * | 146 | 174 | 320 |
| backpressure_cycles * | 2347 | 3271 | 5618 |
| buffer_full_blocks_last * | 375 | 471 | 846 |
| buffer_full_blocks_nonlast * | 1335 | 1923 | 3258 |
| clear_dropped_result * | 10 | 9 | 19 |
| clear_fault_cycles * | 138 | 119 | 257 |
| clear_with_transfer | 5 | 1 | 6 |
| continue_after_last * | 343 | 390 | 733 |
| cycles | 20000 | 20000 | 40000 |
| drain_in_stop * | 5 | 10 | 15 |
| first_restarts_sum * | 98 | 94 | 192 |
| in_fire * | 8468 | 9355 | 17823 |
| invalid_sensor_cycles | 555 | 300 | 855 |
| multi_beat_sums * | 715 | 795 | 1510 |
| negative_temp_cycles * | 587 | 792 | 1379 |
| normal_at_71_79 * | 2255 | 2111 | 4366 |
| normal_hold_at_79 * | 229 | 223 | 452 |
| out_fire * | 866 | 978 | 1844 |
| prod_max_min * | 135 | 137 | 272 |
| prod_min_min * | 53 | 77 | 130 |
| recover_at_70_from_stop * | 29 | 11 | 40 |
| recover_at_70_from_throttle * | 58 | 52 | 110 |
| recover_from_stop * | 72 | 135 | 207 |
| recover_from_throttle * | 85 | 102 | 187 |
| reset_cycles | 6 | 2 | 8 |
| results_checked | 866 | 978 | 1844 |
| single_beat_sums * | 162 | 192 | 354 |
| stop_at_95 * | 23 | 10 | 33 |
| stop_blocked * | 3366 | 3369 | 6735 |
| stop_by_invalid * | 32 | 42 | 74 |
| stop_by_temp * | 38 | 93 | 131 |
| stop_hold_at_71 * | 58 | 91 | 149 |
| stop_hysteresis_hold * | 1910 | 1901 | 3811 |
| throttle_admit * | 1729 | 1183 | 2912 |
| throttle_at_80 * | 87 | 72 | 159 |
| throttle_entry * | 119 | 128 | 247 |
| throttle_hold_at_71 * | 116 | 98 | 214 |
| throttle_hold_at_94 * | 98 | 58 | 156 |
| throttle_hysteresis_hold * | 1240 | 955 | 2195 |
| throttle_phase_block * | 1871 | 1430 | 3301 |
| wrap_neg * | 0 | 0 | 0 |
| wrap_pos * | 0 | 0 | 0 |

