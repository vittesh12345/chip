Bench: `fault/tb_seu_campaign.v` (Icarus Verilog), seed=1 tpb=1 tpb_unprot=4 controls=5 prefix=8..127 post=64 drain=24+8.

| Storage group | Protection | Bits | Trials | MASKED | DETECTED | REPAIRED | TIMING | SDC | LOST | EXTRA | HANG | OTHER | Escapes (SDC+LOST+EXTRA+HANG+OTHER) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Accumulator pairs (4 lanes x A/B x 32) | duplicate + compare | 256 | 256 | 196 | 0 | 0 | 0 | 60 | 0 | 0 | 0 | 0 | 60 (23.4 %) |
| Result pairs (4 lanes x A/B x 32) | duplicate + compare | 256 | 256 | 230 | 0 | 0 | 0 | 26 | 0 | 0 | 0 | 0 | 26 (10.2 %) |
| Thermal triple (3 copies x 2) | TMR + repair | 6 | 6 | 0 | 0 | 6 | 0 | 0 | 0 | 0 | 0 | 0 | 0 (0.0 %) |
| Throttle phase | none | 1 | 4 | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 (0.0 %) |
| out_valid_q | none | 1 | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 4 | 0 | 0 | 4 (100.0 %) |
| fault_q | none | 1 | 4 | 0 | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 (0.0 %) |

Controls (no upset): 5 trials, 5 MASKED. Injected trials: 530; every one of the 521 bits at least 1 times.

Detection latency of the accumulator / result upsets (cycles from the upset cycle to the first cycle with `fault` = 1): none. In every detected trial `in_ready` and `out_valid` were already 0 at the end of the upset cycle.

Accumulator / result upsets not DETECTED: 0, all with `clear_fault` asserted in the upset cycle (the workload of 1 trial in 8 schedules rare clear_fault pulses), which zeroes both copies before the fault latch samples the mismatch: none.

Unprotected flip-flops by the state at the moment of the upset:

| Element / condition | Trials | MASKED | DETECTED | REPAIRED | TIMING | SDC | LOST | EXTRA | HANG | OTHER |
|---|---|---|---|---|---|---|---|---|---|---|
| out_valid_q = 0 (flips to 1) | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 4 | 0 | 0 |
| phase, voted state NORMAL | 2 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| phase, voted state STOP | 2 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| fault_q (always 0 before a single upset, flips to 1) | 4 | 0 | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

out_valid_q EXTRA trials: 4 re-presented the last delivered result (duplicate), 0 a stale buffer content that had not been delivered before (zero after reset / clear_fault).

Reading the unprotected rows: an `out_valid_q` upset always escapes (a result lost when it flips 1 -> 0, an extra one when it flips 0 -> 1); a `phase` upset only matters in THROTTLE, where it shifts the alternating admission (TIMING: every result still correct); a `fault_q` upset is counted as DETECTED although no data was corrupted: it is a false fault stop (availability, not integrity).

Checks:

| Check | Result | Detail |
|---|---|---|
| bench finished without internal errors | PASS | footer: {'trials': '535', 'errors': '0'} |
| fault-free controls are MASKED | PASS | 5 controls, not MASKED: none |
| coverage of the 521 storage bits | PASS | 521 bits covered, min 1 trials per bit (need 1), 530 injected trials (need 500) |
| acc: escapes observed (negative control, protection disabled) | PASS | 60 of 256 trials escaped (SDC 60, LOST 0, EXTRA 0) |
| res: escapes observed (negative control, protection disabled) | PASS | 26 of 256 trials escaped (SDC 26, LOST 0, EXTRA 0) |
| therm: every upset REPAIRED, nothing else visible | PASS | 6 trials; all REPAIRED |
| negative control: out_valid_q upsets escape | PASS | 4 of 4 out_valid_q trials escaped |
