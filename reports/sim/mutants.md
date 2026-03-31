# sim mutation negative control

RTL: rtl; directed bench tb/tb_orbit_demo.v (+maxerr=1); random bench: 1 seed x 20000 cycles.

| mutant | injected bug | directed | random |
|---|---|---|---|
| therm_unsigned | temperature compared unsigned (negative readings look hot) | KILLED: ERROR t=14244000 [negative_temps] DUT outputs differ from the reference model | KILLED: 27 mismatches in 484 cycles |
| throttle_gt | throttle at > 80 instead of >= 80 | KILLED: ERROR t=12424000 [throttle] DUT outputs differ from the reference model | KILLED: 26 mismatches in 695 cycles |
| stop_gt | stop at > 95 instead of >= 95 | KILLED: ERROR t=13514000 [throttle] DUT outputs differ from the reference model | KILLED: 25 mismatches in 4762 cycles |
| recover_lt_throttle | THROTTLE recovers at < 70 instead of <= 70 | KILLED: ERROR t=13234000 [throttle] DUT outputs differ from the reference model | KILLED: 25 mismatches in 1322 cycles |
| recover_lt_stop | STOP recovers at < 70 instead of <= 70 | KILLED: ERROR t=244000 [reset_stop] DUT outputs differ from the reference model | KILLED: 25 mismatches in 856 cycles |
| invalid_ignored | invalid sensor reading does not force STOP | KILLED: ERROR t=64000 [reset_stop] DUT outputs differ from the reference model | KILLED: 26 mismatches in 708 cycles |
| stop_to_throttle | STOP falls back to THROTTLE at >= 80 instead of holding | KILLED: ERROR t=124000 [reset_stop] DUT outputs differ from the reference model | KILLED: 27 mismatches in 995 cycles |
| reset_normal | reset lands in NORMAL instead of STOP | KILLED: ERROR t=24000 [reset_stop] DUT outputs differ from the reference model | KILLED: 25 mismatches in 3952 cycles |
| phase_not_forced | throttle phase not forced to 0 outside THROTTLE | KILLED: ERROR t=13444000 [throttle] DUT outputs differ from the reference model | KILLED: 25 mismatches in 910 cycles |
| throttle_every_cycle | THROTTLE admits every cycle | KILLED: ERROR t=12434000 [throttle] DUT outputs differ from the reference model | KILLED: 25 mismatches in 704 cycles |
| throttle_first_blocks | first THROTTLE cycle blocks (admit = phase) | KILLED: ERROR t=12424000 [throttle] DUT outputs differ from the reference model | KILLED: 26 mismatches in 695 cycles |
| zext_product | product zero-extended instead of sign-extended | KILLED: ERROR t=254000 [reset_stop] DUT outputs differ from the reference model | KILLED: 25 mismatches in 29 cycles |
| first_ignored | in_first does not restart the sum (both copies) | KILLED: ERROR t=274000 [signed_edges] DUT outputs differ from the reference model | KILLED: 25 mismatches in 42 cycles |
| result_from_old_acc | result register loads the pre-beat sum (both copies) | KILLED: ERROR t=254000 [reset_stop] DUT outputs differ from the reference model | KILLED: 25 mismatches in 29 cycles |
| clear_keeps_acc | clear_fault does not zero the accumulators | KILLED: ERROR t=1335744000 [clear_fault] DUT outputs differ from the reference model | KILLED: 25 mismatches in 1090 cycles |
| clear_keeps_result | clear_fault does not zero the result registers | KILLED: ERROR t=1335684000 [clear_fault] DUT outputs differ from the reference model | KILLED: 25 mismatches in 678 cycles |
| clear_keeps_out_valid | clear_fault does not empty the output buffer | KILLED: ERROR t=1335684000 [clear_fault] DUT outputs differ from the reference model | KILLED: 25 mismatches in 1463 cycles |
| ready_during_clear | in_ready not held low while clear_fault | KILLED: ERROR t=1335684000 [clear_fault] DUT outputs differ from the reference model | KILLED: 25 mismatches in 2565 cycles |
| nonlast_not_blocked | full buffer blocks only in_last beats | KILLED: ERROR t=3174000 [multi_beat] DUT outputs differ from the reference model | KILLED: 26 mismatches in 152 cycles |
| bubble | no same-cycle drain and refill (in_ready ignores out_ready) | KILLED: ERROR t=254000 [reset_stop] DUT outputs differ from the reference model | KILLED: 25 mismatches in 54 cycles |
| drop_on_back_to_back | out_fire wins over a same-cycle in_last (result dropped) | KILLED: ERROR t=284000 [signed_edges] DUT outputs differ from the reference model | KILLED: 25 mismatches in 168 cycles |
| no_drain_in_stop | output buffer cannot drain while STOP | KILLED: ERROR t=13514000 [throttle] DUT outputs differ from the reference model | KILLED: 25 mismatches in 11804 cycles |
| shutdown_from_bit0 | shutdown_req taken from the wrong state bit | KILLED: ERROR t=24000 [reset_stop] DUT outputs differ from the reference model | KILLED: 25 mismatches in 695 cycles |
| lanes_reversed | out_data lanes in reverse order | KILLED: ERROR t=254000 [reset_stop] DUT outputs differ from the reference model | KILLED: 25 mismatches in 29 cycles |
| b_lane_rotated | lane i multiplies by lane i+1's b operand | KILLED: ERROR t=254000 [reset_stop] DUT outputs differ from the reference model | KILLED: 25 mismatches in 29 cycles |

directed bench killed 25/25, random bench killed 25/25
