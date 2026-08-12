Bench: `fault/tb_seu_campaign.v` (Icarus Verilog), seed=1 tpb=12 tpb_unprot=200 controls=20 prefix=8..127 post=64 drain=24+8.

| Storage group | Protection | Bits | Trials | MASKED | DETECTED | REPAIRED | TIMING | SDC | LOST | EXTRA | HANG | OTHER | Escapes (SDC+LOST+EXTRA+HANG+OTHER) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Accumulator pairs (4 lanes x A/B x 32) | duplicate + compare | 256 | 3072 | 3 | 3069 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 (0.0 %) |
| Result pairs (4 lanes x A/B x 32) | duplicate + compare | 256 | 3072 | 4 | 3067 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 (0.0 %) |
| Thermal triple (3 copies x 2) | TMR + repair | 6 | 72 | 0 | 0 | 72 | 0 | 0 | 0 | 0 | 0 | 0 | 0 (0.0 %) |
| Throttle phase | none | 1 | 200 | 156 | 0 | 0 | 44 | 0 | 0 | 0 | 0 | 0 | 0 (0.0 %) |
| out_valid_q | none | 1 | 200 | 0 | 0 | 0 | 0 | 0 | 38 | 162 | 0 | 0 | 200 (100.0 %) |
| fault_q | none | 1 | 200 | 0 | 200 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 (0.0 %) |

Controls (no upset): 20 trials, 20 MASKED. Injected trials: 6816; every one of the 521 bits at least 12 times.

Detection latency of the accumulator / result upsets (cycles from the upset cycle to the first cycle with `fault` = 1): 1: 6136 trials. In every detected trial `in_ready` and `out_valid` were already 0 at the end of the upset cycle.

Accumulator / result upsets not DETECTED: 8, all with `clear_fault` asserted in the upset cycle (the workload of 1 trial in 8 schedules rare clear_fault pulses), which zeroes both copies before the fault latch samples the mismatch: trial 356 g_lane[0].u_lane.u_acc_a.q[28] MASKED; trial 1660 g_lane[0].u_lane.u_acc_b.q[8] MASKED; trial 2252 g_lane[1].u_lane.u_acc_b.q[26] MASKED; trial 3836 g_lane[1].u_lane.u_res_a.q[30] TIMING; trial 4068 g_lane[2].u_lane.u_res_a.q[17] MASKED; trial 4388 g_lane[3].u_lane.u_res_a.q[12] MASKED; trial 5036 g_lane[1].u_lane.u_res_b.q[2] MASKED; trial 5260 g_lane[1].u_lane.u_res_b.q[20] MASKED.
A TIMING trial here is one where the fault-free run transferred its pending result in that clear_fault cycle while the upset copy held `out_valid` low (mismatch); the clear then discarded the result, as SPEC section 5 says clear_fault does. No fault, no wrong data.

Unprotected flip-flops by the state at the moment of the upset:

| Element / condition | Trials | MASKED | DETECTED | REPAIRED | TIMING | SDC | LOST | EXTRA | HANG | OTHER |
|---|---|---|---|---|---|---|---|---|---|---|
| out_valid_q = 0 (flips to 1) | 162 | 0 | 0 | 0 | 0 | 0 | 0 | 162 | 0 | 0 |
| out_valid_q = 1 (flips to 0) | 38 | 0 | 0 | 0 | 0 | 0 | 38 | 0 | 0 | 0 |
| phase, voted state NORMAL | 101 | 101 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| phase, voted state THROTTLE | 44 | 0 | 0 | 0 | 44 | 0 | 0 | 0 | 0 | 0 |
| phase, voted state STOP | 55 | 55 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| fault_q (always 0 before a single upset, flips to 1) | 200 | 0 | 200 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

out_valid_q EXTRA trials: 129 re-presented the last delivered result (duplicate), 33 a stale buffer content that had not been delivered before (zero after reset / clear_fault).

Reading the unprotected rows: an `out_valid_q` upset always escapes (a result lost when it flips 1 -> 0, an extra one when it flips 0 -> 1); a `phase` upset only matters in THROTTLE, where it shifts the alternating admission (TIMING: every result still correct); a `fault_q` upset is counted as DETECTED although no data was corrupted: it is a false fault stop (availability, not integrity).

Checks:

| Check | Result | Detail |
|---|---|---|
| bench finished without internal errors | PASS | footer: {'trials': '6836', 'errors': '0'} |
| fault-free controls are MASKED | PASS | 20 controls, not MASKED: none |
| coverage of the 521 storage bits | PASS | 521 bits covered, min 12 trials per bit (need 10), 6816 injected trials (need 5001) |
| acc: no escape (DETECTED, or overwritten by clear_fault in the upset cycle) | PASS | 3072 trials; none escaped |
| acc: fault one cycle after the upset, handshakes blocked in the upset cycle | PASS | 3069 detected trials checked; exceptions: none |
| res: no escape (DETECTED, or overwritten by clear_fault in the upset cycle) | PASS | 3072 trials; none escaped |
| res: fault one cycle after the upset, handshakes blocked in the upset cycle | PASS | 3067 detected trials checked; exceptions: none |
| therm: every upset REPAIRED, nothing else visible | PASS | 72 trials; all REPAIRED |
| negative control: out_valid_q upsets escape | PASS | 200 of 200 out_valid_q trials escaped |
